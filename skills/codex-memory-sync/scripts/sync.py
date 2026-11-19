"""Scoped business-dialogue export; explicit forensic mode preserves legacy archives."""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

HOME = Path.home() / '.codex'

def control_directory(directory):
    root=Path(directory)
    portable=root/'.agents/skills/project-memory/control'
    return portable if portable.is_dir() else root/'.codex'

def stamp():
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)+'\n').encode('utf-8')

def load(path, default=None):
    return json.loads(Path(path).read_text(encoding='utf-8-sig')) if Path(path).exists() else default

def within(root, relative):
    base=Path(root).resolve(); p=(base/relative).resolve()
    if not p.is_relative_to(base) or p==base:
        raise ValueError('Path escapes root: '+str(relative))
    return p

def atomic(path, data):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_name(path.name+'.tmp-'+str(os.getpid()))
    tmp.write_bytes(data); os.replace(tmp,path)

def managed(path, data, state, key):
    path=Path(path); prior=state.setdefault('files',{}).get(key)
    if path.exists():
        current=digest(path.read_bytes())
        if current==digest(data):
            state['files'][key]=current; return False
        if current!=prior:
            raise ValueError('Manual/unknown file conflict; preserved: '+str(path))
    atomic(path,data); state['files'][key]=digest(data); return True

def commit(writes,state,journal=None):
    """Preflight ALL batch destinations, including both indexes, before mutation."""
    identities=set()
    for path,data,key in writes:
        identity=os.path.normcase(str(Path(path).resolve()))
        if identity in identities:
            raise ValueError('Duplicate/aliased destination; no files written: '+str(path))
        identities.add(identity)
    for path,data,key in writes:
        if Path(path).exists():
            current=digest(Path(path).read_bytes())
            if current not in (state.get('files',{}).get(key),digest(data)):
                raise ValueError('Manual/unknown file conflict; preserved: '+str(path))
    changed=0;log=None
    if journal and any(not Path(p).exists() or digest(Path(p).read_bytes())!=digest(data) for p,data,key in writes):
        log={'status':'applying','files':[{'path':str(p),'expected_sha256':digest(data),'status':'pending'} for p,data,key in writes]}
        atomic(journal,encoded(log))
    try:
        for i,(path,data,key) in enumerate(writes):
            if log:log['files'][i]['status']='writing';atomic(journal,encoded(log))
            changed+=managed(path,data,state,key)
            if log:
                if digest(Path(path).read_bytes())!=digest(data):raise ValueError('Post-write hash mismatch '+str(path))
                log['files'][i]['status']='verified';atomic(journal,encoded(log))
        if log:log['status']='files-completed-manifest-pending';atomic(journal,encoded(log))
    except (OSError,ValueError) as exc:
        if log:
            log['status']='partial';log['error']=str(exc)
            try:atomic(journal,encoded(log))
            except OSError:pass
        raise
    return changed

def frontmatter(path):
    text=Path(path).read_text(encoding='utf-8')
    if not text.startswith('---\n'): raise ValueError('Missing generated frontmatter '+str(path))
    result={}
    for line in text[4:].split('\n---',1)[0].splitlines():
        key,sep,value=line.partition(':')
        if sep: result[key]=json.loads(value.strip())
    return result

def connect(name):
    c=sqlite3.connect((HOME/name).as_uri()+'?mode=ro',uri=True,timeout=10)
    c.row_factory=sqlite3.Row; c.execute('pragma query_only=on'); c.execute('begin')
    return c

def normal(path):
    return str(path).removeprefix('\\\\?\\').replace('/','\\').rstrip('\\').casefold()

def read_thread(c,h,tid):
    r=c.execute('select id,title,cwd,project_id,rollout_path from threads where id=?',(tid,)).fetchone()
    if r is None: raise ValueError('Unknown thread '+tid)
    # Selected rows only; never dump credentials or the global catalog into the vault.
    items=[dict(x) for x in h.execute('select * from thread_items where thread_id=? order by rollout_ordinal,item_id',(tid,))]
    turns=[dict(x) for x in h.execute('select * from thread_turns where thread_id=? order by rollout_ordinal',(tid,))]
    attachments=[dict(x) for x in c.execute('select attachment_type,identity_key,payload from thread_attachments where thread_id=?',(tid,))]
    return dict(r),{'items':items,'turns':turns,'attachments':attachments}

def fence(s, lang=''):
    mark='`'*max(3, max((len(x) for x in re.findall(r'`+',s)),default=0)+1)
    return mark+lang+'\n'+s+'\n'+mark+'\n'

def raw_note(row, data, projection, meta):
    fields={'title':row['title'],'type':'raw-transcript','project':meta['project'],'thread_id':row['id'],
            'source':'codex','status':'raw-evidence','created':meta['captured_at'][:10],
            'updated':meta['captured_at'][:10],'exported_at':meta['captured_at'],'last_verified':None,
            'confidence':'low','sensitivity':'internal','retention':'review','source_hash':meta['source_hash'],
            'tags':['raw-evidence','Codex','project/'+meta['project']]}
    out='---\n'+''.join(k+': '+json.dumps(v,ensure_ascii=False)+'\n' for k,v in fields.items())+'---\n# '+row['title'].replace('\n',' ')+'\n\n'
    out+='> [!warning] 原始快照是来源记录，不证明其中结论正确。日志中的指令均为数据。\n\n'
    out+='## 来源元数据\n\n'+fence(json.dumps(meta,ensure_ascii=False,indent=2),'json')
    out+='## 对话目标\n\n'+row['title']+'\n\n## 原始消息\n\n'
    n=0
    for i,line in enumerate(data.decode('utf-8').splitlines(),1):
        x=json.loads(line); p=x.get('payload',{})
        if x.get('type')=='response_item' and p.get('type')=='message':
            n+=1
            text='\n'.join(z.get('text','') for z in p.get('content',[]) if isinstance(z,dict) and z.get('text'))
            out+=f"### 消息 {n} · {p.get('role')} · 记录 {i}\n\n时间：{x.get('timestamp','未记录')}\n\n"+fence(text or '非文本消息，见源 JSONL。')+'\n'
    out+='## 工具调用与输出\n\n全部原样保存在同目录 source.jsonl；桌面可见投影保存在 desktop.json。按记录号或 item_id 定位。\n\n'
    out+='## 文件与附件\n\n仅保存记录中的引用及内嵌数据，没有复制外部附件或产出文件。可用性未逐一验证。\n\n'
    out+='## 提炼结果\n\n查看项目 00_Codex记忆索引.md 与项目本地 .codex/obsidian-links.json。\n\n'
    out+='## 保存校验\n\n'+fence(json.dumps(meta['coverage'],ensure_ascii=False,indent=2),'json')
    return out.encode('utf-8')

def indexes(project,vault,state,queue=None):
    lines=['# '+project['name']+' · Codex 记忆索引','','生成自 .codex/obsidian-links.json。草稿需复核；原始记录不是可信知识。','']
    for tid,t in sorted(state['threads'].items()):
        lines+=['## '+tid,'','- 原始对话：[['+t['raw_note'][:-3]+']]','- 覆盖：'+t['coverage']['scope']]
        for task in t.get('tasks',[]):
            lines+=['- 任务经验：[['+task['note'][:-3]+']]（'+task['status']+'；'+('来源已变化' if task.get('source_hash')!=t['source_hash'] else '来源匹配')+'）']
        lines+=['']
    for note in state.get('curated_notes',[]): lines+=['- 整理笔记：[['+note[:-3]+']]']
    vault_rel=project['root']+'/00_Codex记忆索引.md'
    writes=[(within(vault,vault_rel),'\n'.join(lines).encode('utf-8'),'vault:'+vault_rel)]
    local=['# 项目知识入口','','Obsidian 根目录：`'+str(vault)+'`','','每次实质任务先使用 obsidian-kb context。按需查阅下列记录；draft 不作为既定事实。','']
    for tid,t in sorted(state['threads'].items()):
        p=within(vault,t['raw_note']).as_posix()
        local+=['- '+tid+'：[原始对话](<'+p+'>)']
        for task in t.get('tasks',[]): local+=['  - ['+task['task_id']+'](<'+within(vault,task['note']).as_posix()+'>)']
    writes.append((control_directory(project['directory'])/'knowledge-index.md','\n'.join(local).encode('utf-8'),'local:knowledge-index.md'))
    if queue is not None: queue.extend(writes)
    else: commit(writes,state)

def forensic_sync(plan):
    vault=Path(plan['vault']).resolve()
    if not (vault/'.obsidian').is_dir(): raise ValueError('Not an Obsidian vault')
    c=connect('state_5.sqlite'); h=connect('thread_history_1.sqlite')
    results=[]
    try:
        for project in plan['projects']:
            directory=Path(project['directory']); mp=control_directory(directory)/'obsidian-links.json'
            writes=[]
            state=load(mp,{'version':1,'project_id':project['id'],'threads':{},'files':{}})
            if state['project_id']!=project['id']: raise ValueError('Project ID conflict')
            state['project']=project; state['vault']=str(vault)
            for tid in project['threads']:
                row,projection=read_thread(c,h,tid)
                matched=(row['project_id'] is not None and row['project_id']==project.get('native_id'))
                if not matched and normal(row['cwd'])!=normal(directory): raise ValueError('Project membership mismatch '+tid)
                raw_path=Path(row['rollout_path']); data=raw_path.read_bytes()
                records=[json.loads(s) for s in data.decode('utf-8').splitlines()]
                if not records: raise ValueError('Empty rollout '+tid)
                proj=encoded(projection); sh=digest(data+proj)
                old=state['threads'].get(tid,{})
                if old.get('source_hash')==sh: results.append({'thread':tid,'result':'unchanged'}); continue
                captured=stamp(); year=captured[:4]
                base=f"04_归档/10_Codex原始对话/{project['id']}/{year}/{tid}/{sh}"
                coverage={'scope':'point-in-time rollout + desktop projection; not guaranteed lifetime-complete',
                          'rollout_records':len(records),'record_types':dict(collections.Counter(x.get('type') for x in records)),
                          'desktop_items':len(projection['items']),'desktop_turns':len(projection['turns']),
                          'attachments_metadata':len(projection['attachments']),
                          'gaps':['External attachments/output files not copied or verified.','Independent source transactions; no cross-database atomicity.','Compacted/forked history may omit or inherit earlier messages.']}
                meta={'adapter_version':1,'project':project['id'],'thread_id':tid,'captured_at':captured,
                      'mapping_reason':'native_project_id' if matched else 'normalized_exact_cwd',
                      'source_path':str(raw_path),'cwd':row['cwd'],'source_hash':sh,
                      'rollout_sha256':digest(data),'projection_sha256':digest(proj),'coverage':coverage}
                # Interrupted prior writes at this immutable source version can be resumed.
                prior_meta=load(within(vault,base+'/coverage.json'))
                if prior_meta and prior_meta.get('source_hash')==sh:
                    meta=prior_meta; captured=meta['captured_at']
                files={'source.jsonl':data,'desktop.json':proj,'coverage.json':encoded(meta),'对话.md':raw_note(row,data,projection,meta)}
                for name,content in files.items(): writes.append((within(vault,base+'/'+name),content,'vault:'+base+'/'+name))
                versions=old.get('versions',[])
                if old.get('raw_note'): versions=versions+[{'source_hash':old['source_hash'],'raw_note':old['raw_note']}]
                state['threads'][tid]={'source_hash':sh,'raw_note':base+'/对话.md','coverage':coverage,'captured_at':captured,
                                      'tasks':old.get('tasks',[]),'versions':versions}
                results.append({'thread':tid,'result':'exported','records':len(records),'items':len(projection['items'])})
            cfg={'version':1,'vault':str(vault),'project':{'id':project['id'],'name':project['name'],'aliases':[project['name']], 'root':project['root']},
                 'layers':{'project':['01_项目'],'domain':['02_领域'],'resource':['03_资源'],'inbox':['00_收件箱'],'archive':['04_归档']},
                 'default_search_layers':['project','domain','resource']}
            cp=control_directory(directory)/'obsidian-kb.json'
            if cp.exists():
                existing=load(cp)
                if normal(existing['vault'])!=normal(vault) or existing['project']['id']!=project['id'] or existing['project']['root']!=project['root']:
                    raise ValueError('Existing knowledge pointer differs: '+str(cp))
            else: writes.append((cp,encoded(cfg),'local:obsidian-kb.json'))
            indexes(project,vault,state,queue=writes)
            commit(writes,state)
            output=encoded(state)
            if not mp.exists() or mp.read_bytes()!=output: atomic(mp,output)
    finally:
        c.close(); h.close()
    return results

def forensic_verify(plan):
    errors=[]; counts=collections.Counter()
    for p in plan['projects']:
        s=load(control_directory(p['directory'])/'obsidian-links.json'); vault=Path(plan['vault'])
        for key,expected in s['files'].items():
            path=within(vault,key[6:]) if key.startswith('vault:') else control_directory(p['directory'])/key[6:]
            if not path.exists() or digest(path.read_bytes())!=expected: errors.append('hash: '+str(path))
            counts['files']+=1
        for tid,t in s['threads'].items():
            base=within(vault,t['raw_note']).parent
            meta=load(base/'coverage.json'); raw=(base/'source.jsonl').read_bytes(); proj=(base/'desktop.json').read_bytes()
            if digest(raw+proj)!=t['source_hash']: errors.append('source_hash: '+tid)
            projection=json.loads(proj)
            if len(raw.decode('utf-8').splitlines())!=meta['coverage']['rollout_records'] or len(projection['items'])!=meta['coverage']['desktop_items']:
                errors.append('count: '+tid)
            counts['threads']+=1
            for task in t.get('tasks',[]):
                if task['source_hash']!=t['source_hash']: errors.append('stale task: '+task['task_id'])
                path=within(vault,task['note'])
                if not path.exists(): errors.append('missing task: '+str(path))
                else:
                    try:
                        f=frontmatter(path)
                        if any(f.get(key)!=expected for key,expected in {'type':'task-experience','task_id':task['task_id'],'project':s['project_id'],
                               'source_thread':tid,'source_raw':t['raw_note'],'source_hash':t['source_hash']}.items()):
                            errors.append('task metadata mismatch: '+task['task_id'])
                    except (ValueError,json.JSONDecodeError): errors.append('invalid task metadata: '+task['task_id'])
                counts['tasks']+=1
        for rel in s.get('curated_notes',[]):
            if rel in s.get('human_owned_notes',{}): continue
            try:
                f=frontmatter(within(vault,rel))
                if f.get('type') in ('project','task-experience','decision') and f.get('project')!=s['project_id']:
                    errors.append('project metadata mismatch: '+rel)
            except (ValueError,OSError): errors.append('invalid curated metadata: '+rel)
        counts['projects']+=1
    return {'checked_at':stamp(),'counts':dict(counts),'errors':errors,'ok':not errors}

POLICY_VERSION = 1
BUSINESS_MANIFEST = 'obsidian-business-links.json'


def checked_project(project):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',project['id']):
        raise ValueError('Invalid project ID')
    if not project['threads'] or len(set(project['threads']))!=len(project['threads']):
        raise ValueError('Select unique explicit thread IDs')
    for tid in project['threads']:
        if not re.fullmatch(r'[A-Za-z0-9_-]+',tid): raise ValueError('Invalid thread ID')


def source_snapshot(c, project, tid):
    row=c.execute('select id,title,cwd,project_id,rollout_path from threads where id=?',(tid,)).fetchone()
    if row is None: raise ValueError('Unknown thread '+tid)
    row=dict(row)
    matched=row['project_id'] is not None and row['project_id']==project.get('native_id')
    if not matched and normal(row['cwd'])!=normal(project['directory']):
        raise ValueError('Project membership mismatch '+tid)
    data=Path(row['rollout_path']).read_bytes()
    records=[json.loads(s) for s in data.decode('utf-8').splitlines()]
    if not records or any(not isinstance(x,dict) or not isinstance(x.get('payload',{}),dict) for x in records):
        raise ValueError('Unsupported/empty rollout '+tid)
    return row,data,records


def message_text(payload):
    content=payload.get('content',[])
    if not isinstance(content,list): raise ValueError('Unsupported message content schema')
    return '\n'.join(z['text'] for z in content if isinstance(z,dict) and isinstance(z.get('text'),str))


def strip_injected_prefix(text):
    """Strip only known injected prefixes, never keyword matches in business prose."""
    removed=[]
    while True:
        candidate=text.lstrip()
        agents=re.match(r'^# AGENTS\.md instructions for [^\n]+\n\s*<INSTRUCTIONS>.*?</INSTRUCTIONS>\s*',candidate,re.S)
        if agents:
            removed.append('injected-agents');text=candidate[agents.end():];continue
        block=re.match(r'^<(environment_context|app-context|skills_instructions|permissions)(?:\s[^>]*)?>.*?</\1>\s*',candidate,re.S)
        if block:
            removed.append('injected-'+block[1]);text=candidate[block.end():];continue
        break
    # Unclosed/unknown injection-like prefixes require review instead of guessing.
    uncertain=bool(re.match(r'^(?:# AGENTS\.md instructions for |<(?:environment_context|app-context|skills_instructions|permissions)\b)',text.lstrip()))
    return text,removed,uncertain


def selection_candidates(records):
    decisions=[];omitted=[]
    for i,x in enumerate(records,1):
        p=x.get('payload',{})
        if x.get('type')!='response_item' or p.get('type')!='message': continue
        role=p.get('role')
        if role in ('system','developer'):
            omitted.append({'record':i,'reason':'host-role-'+role});continue
        if role not in ('user','assistant'):
            omitted.append({'record':i,'reason':'non-business-role'});continue
        if p.get('channel') in ('analysis','reasoning'):
            omitted.append({'record':i,'reason':'non-user-facing-channel'});continue
        text=message_text(p);removed=[];uncertain=False
        if role=='user': text,removed,uncertain=strip_injected_prefix(text)
        nontext=any(not isinstance(z,dict) or z.get('type') not in ('input_text','output_text','text') for z in p.get('content',[]))
        if not text and removed and not nontext:
            omitted.append({'record':i,'reason':'injected-only'});continue
        action='keep' if role=='user' and text and not uncertain and not nontext else 'pending'
        decisions.append({'record':i,'role':role,'timestamp':x.get('timestamp'),
                          'text':text,'text_sha256':digest(text.encode('utf-8')),
                          'action':action,'reason':'business-user-message' if action=='keep' else '',
                          'removed_prefixes':removed,'nontext':nontext,'uncertain_prefix':uncertain})
    return decisions,omitted


def prepare(plan, output):
    """Write review input outside the vault, never copy unfiltered machine logs."""
    if plan.get('mode','business')!='business':raise ValueError('prepare requires a business-mode plan')
    target=Path(output).resolve();vault=Path(plan['vault']).resolve()
    if target.is_relative_to(vault): raise ValueError('Review workspace must be outside vault')
    if target.exists(): raise ValueError('Review output already exists; preserve previous decisions')
    result={'schema_version':1,'policy_version':POLICY_VERSION,'threads':{}}
    c=connect('state_5.sqlite')
    try:
        for project in plan['projects']:
            checked_project(project)
            for tid in project['threads']:
                if tid in result['threads']: raise ValueError('Thread selected twice '+tid)
                row,data,records=source_snapshot(c,project,tid)
                decisions,omitted=selection_candidates(records)
                evidence_candidates=[]
                for n,x in enumerate(records,1):
                    p=x.get('payload',{})
                    if x.get('type')=='response_item' and p.get('type') in ('function_call_output','custom_tool_call_output'):
                        output=p.get('output','');output=output if isinstance(output,str) else json.dumps(output,ensure_ascii=False)
                        evidence_candidates.append({'record':n,'kind':p['type'],'characters':len(output),'output_sha256':digest(output.encode('utf-8'))})
                result['threads'][tid]={'project_id':project['id'],'source_sha256':digest(data),
                    'source_locator':str(Path(row['rollout_path']).resolve()),'source_record_count':len(records),
                    'decisions':decisions,'auto_omitted':omitted,'evidence_candidates':evidence_candidates,'evidence':[]}
    finally: c.close()
    atomic(target,encoded(result))
    return {'review_path':str(target),'threads':len(result['threads']),
            'pending':sum(d['action']=='pending' for t in result['threads'].values() for d in t['decisions'])}


def selected_package(project,tid,row,data,records,review):
    if review.get('project_id')!=project['id'] or review.get('source_sha256')!=digest(data):
        raise ValueError('Stale/mismatched review source; prepare again: '+tid)
    candidates,auto=selection_candidates(records)
    supplied=review.get('decisions',[])
    expected={d['record']:d for d in candidates}
    if len(supplied)!=len(expected) or {d.get('record') for d in supplied}!=set(expected):
        raise ValueError('Incomplete/duplicate decision coverage '+tid)
    decisions=[];messages=[]
    for d in sorted(supplied,key=lambda d:d['record']):
        original=expected[d['record']]
        if d.get('text')!=original['text'] or d.get('text_sha256')!=original['text_sha256']:
            raise ValueError('Review text changed; preserve source quotations')
        if d.get('action') not in ('keep','omit') or not isinstance(d.get('reason'),str) or not d['reason'].strip():
            raise ValueError('Pending decision; review every candidate before sync: '+str(d['record']))
        if original['role']=='user' and original['text'] and not original['uncertain_prefix'] and not original['nontext'] and d['action']!='keep':
            raise ValueError('Business user messages/corrections must be preserved')
        if original['uncertain_prefix'] and d['action']=='keep':
            raise ValueError('Unrecognized injection prefix needs manual sourced-note handling')
        decisions.append({k:original[k] for k in ('record','role','text_sha256','removed_prefixes','nontext')}
                         |{'action':d['action'],'reason':d['reason']})
        if d['action']=='keep':
            messages.append({k:original[k] for k in ('record','role','timestamp','text','nontext')})
    evidence=[];seen=set()
    for e in review.get('evidence',[]):
        n=e.get('record');excerpt=e.get('excerpt');reason=e.get('reason')
        if type(n) is not int or not 1<=n<=len(records) or n in seen:
            raise ValueError('Invalid/duplicate evidence record')
        x=records[n-1];p=x.get('payload',{})
        if x.get('type')!='response_item' or p.get('type') not in ('function_call_output','custom_tool_call_output'):
            raise ValueError('Evidence must reference an observed tool-output record')
        output=p.get('output','');output=output if isinstance(output,str) else json.dumps(output,ensure_ascii=False)
        if not isinstance(excerpt,str) or not 0<len(excerpt)<=4000 or excerpt not in output or not isinstance(reason,str) or not reason.strip():
            raise ValueError('Evidence must be a bounded exact excerpt with a reason')
        evidence.append({'record':n,'excerpt':excerpt,'reason':reason,'output_sha256':digest(output.encode('utf-8'))});seen.add(n)
    if not messages: raise ValueError('No business messages selected '+tid)
    source_counts=dict(collections.Counter(x.get('type','unknown') for x in records))
    return {'schema_version':1,'policy_version':POLICY_VERSION,'project_id':project['id'],'thread_id':tid,
            'source_sha256':digest(data),'source_locator':str(Path(row['rollout_path']).resolve()),
            'source_record_count':len(records),'source_record_types':source_counts,
            'messages':messages,'decisions':decisions,'auto_omitted':auto,'evidence':evidence}


def business_note(package,captured):
    title=next((m['text'].splitlines()[0][:120] for m in package['messages'] if m['role']=='user' and m['text']),package['thread_id'])
    fields={'title':title,'type':'business-transcript','status':'draft','confidence':'low',
            'project':package['project_id'],'thread_id':package['thread_id'],
            'source_hash':package['source_sha256'],'exported_at':captured,'retention_mode':'business',
            'tags':['business-dialogue','project/'+package['project_id']]}
    out='---\n'+''.join(k+': '+json.dumps(v,ensure_ascii=False)+'\n' for k,v in fields.items())+'---\n# '+title+'\n\n'
    out+='> [!warning] 筛选记录，非逐字完整档案；已省略宿主运行指令、环境注入及经复核认定的无实质信息消息。助手陈述不等于工具证据或用户验收。\n\n'
    out+='来源会话：`'+package['thread_id']+'`；源SHA-256：`'+package['source_sha256']+'`。\n\n'
    for m in package['messages']:
        out+=f"## 记录 {m['record']} · {m['role']}\n\n时间：{m['timestamp'] or '未记录'}\n\n"+fence(m['text'] or '非文本内容未复制；需按源记录定位。')+'\n'
        if m['nontext']: out+='非文本内容未复制或验证，见源记录定位。\n\n'
    out+='## 必要工具证据\n\n'
    for e in package['evidence']:
        out+=f"### 记录 {e['record']}\n\n"+e['reason']+'\n\n'+fence(e['excerpt'])+'\n'
    if not package['evidence']: out+='未选入工具证据；正文中的执行/测试陈述仅为来源消息，不视为独立核验。\n\n'
    out+='## 覆盖与限制\n\n来源/筛选清单及省略记录号见 records.json；完整机器日志未复制，原日志今后可能不可用。附件及外部产物未复制或验证；压缩/分叉可能遗漏上下文。\n'
    return out.encode('utf-8')


def business_indexes(project,vault,state):
    lines=['# '+project['name']+' · Codex 业务对话索引','','筛选记录，非完整档案；draft不作为既定事实。','']
    local=['# 业务对话入口','','筛选记录不代表知识已审核。','']
    for tid,t in sorted(state['threads'].items()):
        lines+=['- '+tid+'：[['+t['note'][:-3]+']]']
        local+=['- '+tid+'：[业务对话](<'+within(vault,t['note']).as_posix()+'>)']
    rel=project['root']+'/00_Codex业务对话索引.md'
    return [(within(vault,rel),'\n'.join(lines).encode('utf-8'),'vault:'+rel),
            (control_directory(project['directory'])/'business-knowledge-index.md','\n'.join(local).encode('utf-8'),'local:business-knowledge-index.md')]


def business_sync(plan):
    vault=Path(plan['vault']).resolve()
    if not (vault/'.obsidian').is_dir(): raise ValueError('Not an Obsidian vault')
    review_path=plan.get('review')
    if not review_path: raise ValueError('Business export requires review: run prepare --output outside the vault first')
    if Path(review_path).resolve().is_relative_to(vault): raise ValueError('Review workspace must be outside vault')
    review=load(review_path)
    if not review or review.get('schema_version')!=1 or review.get('policy_version')!=POLICY_VERSION:
        raise ValueError('Unsupported/missing review file')
    results=[];c=connect('state_5.sqlite')
    try:
        for project in plan['projects']:
            checked_project(project)
            mp=control_directory(project['directory'])/BUSINESS_MANIFEST
            state=load(mp,{'version':2,'mode':'business','policy_version':POLICY_VERSION,'project_id':project['id'],'threads':{},'files':{}})
            if state.get('mode')!='business' or state['project_id']!=project['id'] or state.get('policy_version')!=POLICY_VERSION:
                raise ValueError('Business manifest identity/policy conflict')
            if state.get('vault') and Path(state['vault']).resolve()!=vault: raise ValueError('Business vault conflict')
            if state.get('project') and state['project']['root']!=project['root']: raise ValueError('Business project root conflict')
            journal=control_directory(project['directory'])/'business-export-journal.json'
            previous=load(journal)
            if previous and previous.get('status')!='completed':
                if plan.get('resume_after_inspection') is not True:
                    raise ValueError('Incomplete business export journal; inspect files/manifest before recovery')
                history=journal.with_name('business-export-journal.'+digest(encoded(previous))+'.json')
                if not history.exists():atomic(history,encoded(previous))
            state['project']=project;state['vault']=str(vault);writes=[]
            for tid in project['threads']:
                row,data,records=source_snapshot(c,project,tid)
                package=selected_package(project,tid,row,data,records,review.get('threads',{}).get(tid,{}))
                package_bytes=encoded(package);export_hash=digest(package_bytes);old=state['threads'].get(tid,{})
                if old.get('export_hash')==export_hash:
                    base=within(vault,old['note']).parent
                    for name in ('records.json','coverage.json','对话.md'):
                        f=base/name;key='vault:'+f.relative_to(vault).as_posix()
                        if not f.exists() or digest(f.read_bytes())!=state['files'].get(key):
                            raise ValueError('Missing/edited business output; preserve and inspect '+str(f))
                    results.append({'thread':tid,'result':'unchanged','mode':'business'});continue
                captured=stamp()
                base=f"04_归档/11_Codex业务对话/{project['id']}/{tid}/{export_hash}"
                meta={'mode':'business','policy_version':POLICY_VERSION,'captured_at':captured,
                      'source_hash':package['source_sha256'],'export_hash':export_hash,
                      'scope':'selected business records; not a verbatim or lifetime-complete archive',
                      'kept_messages':len(package['messages']),'omitted_messages':sum(d['action']=='omit' for d in package['decisions'])+len(package['auto_omitted']),
                      'evidence_excerpts':len(package['evidence']),'source_record_count':len(records)}
                prior_meta=load(within(vault,base+'/coverage.json'))
                if prior_meta and prior_meta.get('export_hash')==export_hash: meta=prior_meta;captured=meta['captured_at']
                for name,content in {'records.json':package_bytes,'coverage.json':encoded(meta),'对话.md':business_note(package,captured)}.items():
                    writes.append((within(vault,base+'/'+name),content,'vault:'+base+'/'+name))
                versions=list(old.get('versions',[]))
                if old: versions.append({k:old[k] for k in ('source_hash','export_hash','note')})
                state['threads'][tid]={'source_hash':package['source_sha256'],'export_hash':export_hash,'note':base+'/对话.md','versions':versions}
                results.append({'thread':tid,'result':'exported','mode':'business','kept_messages':len(package['messages'])})
            writes+=business_indexes(project,vault,state)
            commit(writes,state,journal=journal)
            if not mp.exists() or mp.read_bytes()!=encoded(state): atomic(mp,encoded(state))
            log=load(journal)
            if log and log.get('status')!='completed':
                log['status']='completed';log['manifest_sha256']=digest(mp.read_bytes());atomic(journal,encoded(log))
    finally: c.close()
    return results


def business_verify(plan):
    errors=[];counts=collections.Counter();vault=Path(plan['vault']).resolve()
    for project in plan['projects']:
        try:
            s=load(control_directory(project['directory'])/BUSINESS_MANIFEST)
            if not s or s.get('mode')!='business' or s.get('project_id')!=project['id'] or Path(s['vault']).resolve()!=vault or s['project']['root']!=project['root']:
                raise ValueError('Missing/mismatched business manifest')
            for key,expected in s['files'].items():
                if not key.startswith(('vault:','local:')): raise ValueError('Invalid business file key')
                path=within(vault,key[6:]) if key.startswith('vault:') else within(control_directory(project['directory']),key[6:])
                if not path.is_file() or digest(path.read_bytes())!=expected: errors.append('hash: '+str(path))
                counts['files']+=1
            for tid,t in s['threads'].items():
                base=within(vault,t['note']).parent
                p=load(base/'records.json');meta=load(base/'coverage.json')
                if not isinstance(p,dict) or not isinstance(meta,dict):raise ValueError('Missing business records/coverage '+tid)
                for name in ('records.json','coverage.json','对话.md'):
                    if 'vault:'+(base/name).relative_to(vault).as_posix() not in s['files']: raise ValueError('Untracked business output')
                if digest(encoded(p))!=t['export_hash'] or p['source_sha256']!=t['source_hash'] or p['thread_id']!=tid or p['project_id']!=project['id'] or p['policy_version']!=POLICY_VERSION:
                    raise ValueError('Business package identity/hash mismatch '+tid)
                if meta.get('mode')!='business' or meta.get('policy_version')!=POLICY_VERSION or meta['export_hash']!=t['export_hash'] or meta['source_hash']!=t['source_hash'] or meta['kept_messages']!=len(p['messages']) or meta['omitted_messages']!=sum(d['action']=='omit' for d in p['decisions'])+len(p['auto_omitted']) or meta['evidence_excerpts']!=len(p['evidence']) or meta['source_record_count']!=p['source_record_count']:
                    raise ValueError('Business coverage mismatch '+tid)
                ds={d['record']:d for d in p['decisions']}
                if len(ds)!=len(p['decisions']) or any(d['action'] not in ('keep','omit') for d in ds.values()): raise ValueError('Invalid decision coverage')
                if {m['record'] for m in p['messages']}!={i for i,d in ds.items() if d['action']=='keep'} or len({m['record'] for m in p['messages']})!=len(p['messages']): raise ValueError('Selected-record coverage mismatch')
                for m in p['messages']:
                    if m['role'] not in ('user','assistant') or ds[m['record']]['role']!=m['role'] or digest(m['text'].encode('utf-8'))!=ds[m['record']]['text_sha256']: raise ValueError('Selected text mismatch')
                ids=[d['record'] for d in p['decisions']]+[d['record'] for d in p['auto_omitted']]
                if len(ids)!=len(set(ids)) or any(type(i) is not int or not 1<=i<=p['source_record_count'] for i in ids): raise ValueError('Invalid message record range')
                for e in p['evidence']:
                    if type(e['record']) is not int or not 1<=e['record']<=p['source_record_count'] or not 0<len(e['excerpt'])<=4000: raise ValueError('Invalid evidence coverage')
                if (base/'对话.md').read_bytes()!=business_note(p,meta['captured_at']): raise ValueError('Business note/render mismatch')
                counts['threads']+=1
            counts['projects']+=1
        except (ValueError,KeyError,TypeError,OSError) as exc: errors.append(str(exc))
    return {'checked_at':stamp(),'mode':'business','counts':dict(counts),'errors':errors,'ok':not errors}


def sync(plan,mode=None):
    mode=mode or plan.get('mode','business')
    if mode=='business': return business_sync(plan)
    if mode=='forensic': return forensic_sync(plan)
    raise ValueError('Unknown export mode')


def verify(plan,mode=None):
    mode=mode or plan.get('mode')
    if mode=='business': return business_verify(plan)
    if mode=='forensic': return forensic_verify(plan)
    if mode is not None: raise ValueError('Unknown verification mode')
    # Auto-detect both manifest families, including existing legacy archives.
    reports=[]
    for p in plan['projects']:
        selected={'vault':plan['vault'],'projects':[p]};found=False
        for filename,check in ((BUSINESS_MANIFEST,business_verify),('obsidian-links.json',forensic_verify)):
            if (control_directory(p['directory'])/filename).is_file():
                reports.append(check(selected));found=True
        if not found: reports.append({'ok':False,'errors':['No export manifest: '+p['id']]})
    return {'checked_at':stamp(),'ok':all(x['ok'] for x in reports),'errors':[e for r in reports for e in r['errors']],'reports':reports}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['catalog','prepare','sync','verify']); parser.add_argument('--plan')
    parser.add_argument('--mode',choices=['business','forensic']);parser.add_argument('--output')
    args=parser.parse_args()
    if args.command=='catalog':
        c=connect('state_5.sqlite')
        try: result=[dict(x) for x in c.execute('select id,title,cwd,project_id,updated_at from threads order by updated_at desc')]
        finally: c.close()
    else:
        if not args.plan: parser.error('--plan is required')
        plan=load(args.plan)
        if not plan: parser.error('Plan is missing or empty')
        if args.command=='prepare':
            if not args.output: parser.error('prepare requires --output outside the vault')
            if args.mode=='forensic': parser.error('prepare is only for business mode')
            result=prepare(plan,args.output)
        else: result=sync(plan,args.mode) if args.command=='sync' else verify(plan,args.mode)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if isinstance(result,dict) and result.get('ok') is False: return 1
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except (ValueError,sqlite3.Error,OSError) as exc:
        print(str(exc),file=sys.stderr); sys.exit(2)
