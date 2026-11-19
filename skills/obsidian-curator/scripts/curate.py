"""Template-backed draft writer. No model/API calls; synthesis supplied by agent."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

spec=importlib.util.spec_from_file_location('memory_sync',Path.home()/'.codex/skills/codex-memory-sync/scripts/sync.py')
sync=importlib.util.module_from_spec(spec); sys.modules[spec.name]=sync; spec.loader.exec_module(sync)
TYPES={'项目模板.md':'project','Codex任务经验模板.md':'task-experience','Codex决策记录模板.md':'decision',
       'Codex知识卡片模板.md':'knowledge-card','Codex领域主题模板.md':'domain-book',
       'Codex资源笔记模板.md':'resource'}

def render(template, fields, sections):
    if not template.startswith('---\n'): raise ValueError('Template frontmatter missing')
    header,body=template[4:].split('\n---',1)
    required=re.findall(r'^([\w_]+):',header,re.M)
    common={'status':'draft','created':sync.stamp()[:10],'updated':sync.stamp()[:10],
            'last_verified':None,'confidence':'low','sensitivity':'internal','tags':['Codex','curated-draft']}
    f={**common,**fields}
    if f.get('status')!='draft' or f.get('confidence') not in ('low','medium'): raise ValueError('Human review required for trust promotion')
    for k in required:
        if k not in f: raise ValueError('Missing template field '+k)
    if not f.get('source_raw') or not f.get('source_hash') or not f.get('source_thread'): raise ValueError('Source provenance required')
    headings=re.findall(r'^(#{2,3}) (.+)$',body,re.M)
    allowed={x[1] for x in headings}
    if set(sections)-allowed: raise ValueError('Unknown template headings '+str(set(sections)-allowed))
    out='---\n'+''.join(k+': '+json.dumps(v,ensure_ascii=False)+'\n' for k,v in f.items())+'---\n# '+f['title']+'\n\n'
    if f['type']=='task-experience': out+='> [!abstract] 草稿\n> '+sections.get('最终效果','来源与效果等待复核。').replace('\n','\n> ')+'\n\n'
    for i,(level,title) in enumerate(headings):
        out+=level+' '+title+'\n\n'
        has_children=i+1<len(headings) and len(headings[i+1][0])>len(level)
        content=sections.get(title,'' if has_children else '本次来源未单独确认此项；待人工复核。')
        if content: out+=content+'\n\n'
    placeholders=set(re.findall(r'<[^>\n]+>',template))
    if re.search(r'\{\{[^}]+\}\}',out) or any(x in out for x in placeholders):
        raise ValueError('Unresolved template placeholder')
    return out.encode('utf-8')

def run(batch):
    directory=Path(batch['project_dir']); mp=sync.control_directory(directory)/'obsidian-links.json'; state=sync.load(mp)
    if not state: raise ValueError('Export first')
    vault=Path(state['vault']).resolve(); staged={}; notes={}
    for n in batch['notes']:
        if n['template'] not in TYPES: raise ValueError('Unknown template')
        f=n['fields']; tid=f.get('source_thread'); t=state['threads'].get(tid)
        if not t or f.get('source_hash')!=t['source_hash'] or f.get('source_raw')!=t['raw_note']: raise ValueError('Stale/mismatched source')
        if f.get('type')!=TYPES[n['template']]: raise ValueError('Template type mismatch')
        if f['type'] in ('project','task-experience','decision') and f.get('project')!=state['project_id']:
            raise ValueError('Project metadata mismatch')
        path=sync.within(vault,n['path'])
        canonical=path.relative_to(vault).as_posix()
        if canonical!=n['path'] or path.suffix!='.md' or canonical.startswith(('04_归档/','06_模板/')):
            raise ValueError('Invalid/noncanonical draft target')
        target_layer={'project':state['project']['root']+'/', 'task-experience':state['project']['root']+'/', 'decision':state['project']['root']+'/',
                      'domain-book':'02_领域/','knowledge-card':'02_领域/','resource':'03_资源/'}[f['type']]
        layer_root=sync.within(vault,target_layer.rstrip('/'))
        if not path.is_relative_to(layer_root): raise ValueError('Wrong knowledge layer')
        template=sync.within(vault,'06_模板/'+n['template']).read_text(encoding='utf-8')
        dated_fields=dict(f)
        # Stable defaults across calendar days; no date-only rewrites on repeat.
        if path.exists():
            previous=sync.frontmatter(path)
            dated_fields.setdefault('created',previous.get('created',t['captured_at'][:10]))
            dated_fields.setdefault('updated',previous.get('updated',t['captured_at'][:10]))
        else:
            dated_fields.setdefault('created',t['captured_at'][:10])
            dated_fields.setdefault('updated',t['captured_at'][:10])
        data=render(template,dated_fields,n['sections'])
        if n['path'] in staged: raise ValueError('Duplicate target')
        # Preflight every destination before the first write.
        prior=state['files'].get('vault:'+n['path'])
        if path.exists() and sync.digest(path.read_bytes()) not in (prior,sync.digest(data)):
            raise ValueError('Manual/unknown draft conflict; preserved: '+str(path))
        staged[n['path']]=data; notes[n['path']]=n
    for tid,tasks in batch.get('tasks',{}).items():
        t=state['threads'].get(tid)
        if t is None: raise ValueError('Unknown source thread')
        for task in tasks:
            n=notes.get(task['note']); f=n['fields'] if n else {}
            if task.get('status')!='draft' or task.get('source_hash')!=t['source_hash'] or f.get('type')!='task-experience' or f.get('task_id')!=task['task_id'] or f.get('source_thread')!=tid:
                raise ValueError('Invalid semantic task mapping')
    writes=[(sync.within(vault,rel),data,'vault:'+rel) for rel,data in staged.items()]
    for tid,tasks in batch.get('tasks',{}).items():
        existing={x['task_id']:x for x in state['threads'][tid].get('tasks',[])}
        for task in tasks:
            old=existing.get(task['task_id'])
            if old and old['note']!=task['note']:
                key='vault:'+old['note']; old_path=sync.within(vault,old['note'])
                expected=state['files'].get(key)
                if old_path.exists() and expected and sync.digest(old_path.read_bytes())!=expected:
                    state.setdefault('human_owned_notes',{})[old['note']]={'reason':'superseded generated task; human edits preserved',
                        'previous_generated_sha256':expected,'observed_sha256':sync.digest(old_path.read_bytes()),'recorded_at':sync.stamp(),
                        'replacement':task['note'],'trust':'unreviewed'}
                    del state['files'][key]
        existing.update({x['task_id']:x for x in tasks}); state['threads'][tid]['tasks']=list(existing.values())
    state['curated_notes']=sorted(set(state.get('curated_notes',[]))|set(staged))
    sync.indexes(state['project'],vault,state,queue=writes)
    changed=sum(not path.exists() or path.read_bytes()!=data for path,data,key in writes[:len(staged)])
    sync.commit(writes,state)
    content=sync.encoded(state)
    if mp.read_bytes()!=content: sync.atomic(mp,content)
    return {'notes':len(staged),'changed':changed,'project':state['project_id']}

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--batch',required=True); a=p.parse_args()
    try: print(json.dumps(run(sync.load(a.batch)),ensure_ascii=False))
    except (ValueError,OSError,KeyError) as e: print(str(e),file=sys.stderr); sys.exit(2)
