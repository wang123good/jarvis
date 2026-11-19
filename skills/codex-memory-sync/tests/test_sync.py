"""Integration tests against synthetic SQLite/rollouts and isolated vaults only."""
import importlib.util
from contextlib import closing
from unittest.mock import patch
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('sync_under_test',Path(__file__).resolve().parents[1]/'scripts/sync.py')
sync=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(sync)


def message(role,text,channel=None):
    p={'type':'message','role':role,'content':[{'type':'input_text' if role=='user' else 'output_text','text':text}]}
    if channel: p['channel']=channel
    return {'type':'response_item','timestamp':'2026-11-19T00:00:00Z','payload':p}


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.old_home=sync.HOME;sync.HOME=self.root/'codex';sync.HOME.mkdir()
        self.vault=self.root/'vault';(self.vault/'.obsidian').mkdir(parents=True)
        self.project=self.root/'project';self.project.mkdir()
        self.rollout=sync.HOME/'selected.jsonl'
        self.records=[{'type':'session_meta','payload':{}},
            message('developer','HOST-NOISE do not archive'),
            message('user','<environment_context>HOST-NOISE env</environment_context>'),
            message('user','<environment_context>HOST-NOISE env</environment_context>\n请整理业务资料'),
            message('assistant','我会先查找资料。','commentary'),
            message('assistant','发现关键限制：仅内存重放，持久恢复未验证。','commentary'),
            {'type':'response_item','payload':{'type':'function_call_output','output':'runner: 2 tests passed; temporary debug details'}},
            message('assistant','交付完成；2项测试通过，跨进程恢复未验证。','final'),
            message('user','请解释 environment_context 和 AGENTS.md 对项目的影响'),
            message('user','# AGENTS.md instructions for D:/fixture\n\n<INSTRUCTIONS>HOST-NOISE rules</INSTRUCTIONS>\n<environment_context>HOST-NOISE env</environment_context>'),
            {'type':'event_msg','payload':{'type':'token_count','noise':'HOST-NOISE'}},
            message('assistant','HOST-NOISE hidden analysis','analysis'),
            message('user','增加事前契约和人工复核规则')]
        self.write_source()
        with closing(sqlite3.connect(sync.HOME/'state_5.sqlite')) as c, c:
            c.execute('create table threads (id text,title text,cwd text,project_id text,rollout_path text)')
            c.execute('insert into threads values (?,?,?,?,?)',('thread-1','fixture',str(self.project),None,str(self.rollout)))
            c.execute('create table thread_attachments (thread_id text,attachment_type text,identity_key text,payload text)')
        with closing(sqlite3.connect(sync.HOME/'thread_history_1.sqlite')) as c, c:
            c.execute('create table thread_items (thread_id text,rollout_ordinal integer,item_id text)')
            c.execute('create table thread_turns (thread_id text,rollout_ordinal integer)')
        self.review=self.root/'review.json'
        self.plan={'vault':str(self.vault),'review':str(self.review),'projects':[{'id':'fixture','name':'fixture','directory':str(self.project),'root':'01_项目/fixture','threads':['thread-1']}]}

    def tearDown(self):
        sync.HOME=self.old_home;self.tmp.cleanup()

    def write_source(self):
        self.rollout.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in self.records),encoding='utf-8')

    def reviewed(self):
        sync.prepare(self.plan,self.review)
        data=sync.load(self.review)
        for d in data['threads']['thread-1']['decisions']:
            if d['action']=='pending':d.update(action='omit' if d['record']==5 else 'keep',reason='routine progress' if d['record']==5 else 'substantive finding or outcome')
        data['threads']['thread-1']['evidence']=[{'record':7,'excerpt':'2 tests passed','reason':'observed test result; limited scope'}]
        sync.atomic(self.review,sync.encoded(data));return data

    def state(self):return sync.load(self.project/'.codex'/sync.BUSINESS_MANIFEST)

    def snapshot(self):
        return {str(p.relative_to(self.root)):(p.read_bytes(),p.stat().st_mtime_ns) for root in [self.vault,self.project] for p in root.rglob('*') if p.is_file()}

    def test_prepare_and_default_require_semantic_review(self):
        summary=sync.prepare(self.plan,self.review)
        self.assertEqual(summary['pending'],3)
        text=self.review.read_text(encoding='utf-8');self.assertNotIn('HOST-NOISE',text)
        self.assertIn('增加事前契约',text)
        t=sync.load(self.review)['threads']['thread-1']
        self.assertEqual(Path(t['source_locator']),self.rollout.resolve())
        self.assertEqual(t['evidence_candidates'][0]['record'],7)
        self.assertNotIn('temporary debug details',text)
        with self.assertRaisesRegex(ValueError,'Pending'):sync.sync(self.plan)
        self.assertEqual(self.snapshot(),{})

    def test_no_review_does_not_fall_back_to_full_export(self):
        plan={k:v for k,v in self.plan.items() if k!='review'}
        with self.assertRaisesRegex(ValueError,'requires review'):sync.sync(plan)
        self.assertEqual(self.snapshot(),{})

    def test_business_export_and_verify(self):
        self.reviewed();sync.sync(self.plan)
        s=self.state();t=s['threads']['thread-1'];note=self.vault/t['note']
        self.assertTrue(sync.verify(self.plan)['ok'])
        text=note.read_text(encoding='utf-8')
        for needed in ['请整理业务资料','关键限制','增加事前契约','2 tests passed','记录 6']:
            self.assertIn(needed,text)
        self.assertNotIn('我会先查找资料',text)
        for p in self.vault.rglob('*'):
            if p.is_file():self.assertNotIn('HOST-NOISE',p.read_text(encoding='utf-8'))
        self.assertFalse(list(self.vault.rglob('source.jsonl')))
        self.assertFalse(list(self.vault.rglob('desktop.json')))
        self.assertFalse((self.project/'.codex/obsidian-links.json').exists())

    def test_repeat_is_noop_including_mtimes(self):
        self.reviewed();sync.sync(self.plan);before=self.snapshot()
        self.assertEqual(sync.sync(self.plan)[0]['result'],'unchanged')
        self.assertEqual(self.snapshot(),before)

    def test_changed_source_requires_fresh_review_then_versions(self):
        self.reviewed();sync.sync(self.plan);before=self.snapshot();old=self.state()['threads']['thread-1']
        self.records.append(message('user','补充业务约束'));self.write_source()
        with self.assertRaisesRegex(ValueError,'Stale'):sync.sync(self.plan)
        self.assertEqual(self.snapshot(),before)
        self.review.unlink();self.reviewed();sync.sync(self.plan)
        new=self.state()['threads']['thread-1']
        self.assertNotEqual(new['source_hash'],old['source_hash'])
        self.assertTrue((self.vault/old['note']).exists());self.assertEqual(len(new['versions']),1)
        self.assertTrue(sync.verify(self.plan)['ok'])

    def test_changed_selection_versions_without_faking_source_hash(self):
        data=self.reviewed();sync.sync(self.plan);old=self.state()['threads']['thread-1']
        data['threads']['thread-1']['decisions'][1]['reason']='clearer selection rationale'
        sync.atomic(self.review,sync.encoded(data));sync.sync(self.plan)
        new=self.state()['threads']['thread-1']
        self.assertEqual(new['source_hash'],old['source_hash']);self.assertNotEqual(new['export_hash'],old['export_hash'])

    def test_edited_output_is_preserved_on_repeat(self):
        self.reviewed();sync.sync(self.plan);p=self.vault/self.state()['threads']['thread-1']['note'];p.write_text('human edit',encoding='utf-8')
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'edited'):sync.sync(self.plan)
        self.assertEqual(self.snapshot(),before);self.assertFalse(sync.verify(self.plan)['ok'])

    def test_index_conflict_preflights_all_new_files(self):
        self.reviewed();sync.sync(self.plan)
        index=self.vault/'01_项目/fixture/00_Codex业务对话索引.md';index.write_text('manual index',encoding='utf-8')
        self.records.append(message('user','新业务'));self.write_source();self.review.unlink();self.reviewed()
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'conflict'):sync.sync(self.plan)
        self.assertEqual(self.snapshot(),before)

    def test_forged_source_text_or_missing_coverage_rejected(self):
        data=self.reviewed();data['threads']['thread-1']['decisions'][0]['text']='forged'
        sync.atomic(self.review,sync.encoded(data))
        with self.assertRaisesRegex(ValueError,'text changed'):sync.sync(self.plan)
        data['threads']['thread-1']['decisions'].pop();sync.atomic(self.review,sync.encoded(data))
        with self.assertRaisesRegex(ValueError,'coverage'):sync.sync(self.plan)
        self.assertEqual(self.snapshot(),{})

    def test_business_user_correction_cannot_be_dropped(self):
        data=self.reviewed();data['threads']['thread-1']['decisions'][-1].update(action='omit',reason='unwanted')
        sync.atomic(self.review,sync.encoded(data))
        with self.assertRaisesRegex(ValueError,'must be preserved'):sync.sync(self.plan)

    def test_fabricated_evidence_rejected(self):
        data=self.reviewed();data['threads']['thread-1']['evidence'][0]['excerpt']='100 tests passed'
        sync.atomic(self.review,sync.encoded(data))
        with self.assertRaisesRegex(ValueError,'exact excerpt'):sync.sync(self.plan)

    def test_missing_output_and_rehashed_coverage_tampering_detected(self):
        self.reviewed();sync.sync(self.plan);s=self.state();base=(self.vault/s['threads']['thread-1']['note']).parent
        p=base/'coverage.json';meta=sync.load(p);meta['kept_messages']+=1;sync.atomic(p,sync.encoded(meta))
        s['files']['vault:'+p.relative_to(self.vault).as_posix()]=sync.digest(p.read_bytes())
        sync.atomic(self.project/'.codex'/sync.BUSINESS_MANIFEST,sync.encoded(s))
        self.assertFalse(sync.verify(self.plan)['ok'])
        p.unlink();self.assertFalse(sync.verify(self.plan)['ok'])

    def test_explicit_forensic_and_legacy_auto_verify(self):
        sync.sync(self.plan,mode='forensic')
        self.assertEqual(list(self.vault.rglob('source.jsonl'))[0].read_bytes(),self.rollout.read_bytes())
        self.assertTrue(sync.verify(self.plan)['ok'])
        self.assertFalse((self.project/'.codex'/sync.BUSINESS_MANIFEST).exists())

    def test_business_preserves_legacy_exports_and_manifests(self):
        sync.sync(self.plan,mode='forensic')
        legacy={p:p.read_bytes() for p in self.vault.rglob('*') if p.is_file()}
        manifest=self.project/'.codex/obsidian-links.json';raw_manifest=manifest.read_bytes()
        self.reviewed();sync.sync(self.plan)
        self.assertEqual(manifest.read_bytes(),raw_manifest)
        for p,data in legacy.items():self.assertEqual(p.read_bytes(),data)
        self.assertTrue(sync.verify(self.plan)['ok'])

    def test_review_outside_vault_and_path_escape(self):
        with self.assertRaisesRegex(ValueError,'outside vault'):sync.prepare(self.plan,self.vault/'review.json')
        with self.assertRaisesRegex(ValueError,'escapes root'):sync.within(self.vault,'../escape')

    def test_unclosed_prefix_is_pending_not_silently_stripped(self):
        self.records.append(message('user','<environment_context>unclosed and maybe business'));self.write_source()
        data=self.reviewed();d=data['threads']['thread-1']['decisions'][-1]
        self.assertTrue(d['uncertain_prefix'])
        with self.assertRaisesRegex(ValueError,'Unrecognized'):sync.sync(self.plan)

    def test_plain_user_indentation_and_quoted_wrapper_preserved(self):
        text='    example = "<environment_context>literal</environment_context>"'
        cleaned,removed,uncertain=sync.strip_injected_prefix(text)
        self.assertEqual(cleaned,text);self.assertEqual(removed,[]);self.assertFalse(uncertain)

    def test_partial_write_journal_blocks_uninspected_replay(self):
        self.reviewed();real=sync.managed;calls=[]
        def fail_second(path,data,state,key):
            calls.append(key)
            if len(calls)==2:raise OSError('injected fixture I/O failure')
            return real(path,data,state,key)
        with patch.object(sync,'managed',side_effect=fail_second):
            with self.assertRaises(OSError):sync.sync(self.plan)
        journal=self.project/'.codex/business-export-journal.json';log=sync.load(journal)
        self.assertEqual(log['status'],'partial');self.assertEqual(log['files'][0]['status'],'verified')
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'inspect'):sync.sync(self.plan)
        self.assertEqual(self.snapshot(),before)
        # Explicit fixture-state inspection is complete; resume with the assertion flag.
        sync.sync({**self.plan,'resume_after_inspection':True})
        self.assertEqual(sync.load(journal)['status'],'completed')
        self.assertTrue(sync.verify(self.plan)['ok'])
        self.assertTrue(list(journal.parent.glob('business-export-journal.*.json')))

    def test_manifest_write_failure_can_be_inspected_and_resumed(self):
        self.reviewed();real=sync.atomic
        def fail_manifest(path,data):
            if Path(path).name==sync.BUSINESS_MANIFEST:raise OSError('fixture manifest write interrupted')
            return real(path,data)
        with patch.object(sync,'atomic',side_effect=fail_manifest):
            with self.assertRaises(OSError):sync.sync(self.plan)
        journal=self.project/'.codex/business-export-journal.json'
        self.assertEqual(sync.load(journal)['status'],'files-completed-manifest-pending')
        with self.assertRaisesRegex(ValueError,'inspect'):sync.sync(self.plan)
        sync.sync({**self.plan,'resume_after_inspection':True})
        self.assertEqual(sync.load(journal)['status'],'completed')
        self.assertTrue(sync.verify(self.plan)['ok'])

    def test_prepare_rejects_forensic_plan_instead_of_mode_confusion(self):
        with self.assertRaisesRegex(ValueError,'business-mode'):sync.prepare({**self.plan,'mode':'forensic'},self.review)
        self.assertFalse(self.review.exists())


if __name__=='__main__':unittest.main(verbosity=2)
