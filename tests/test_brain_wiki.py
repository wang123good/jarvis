import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import brain_wiki as w
from environment_isolation import configure_fixture


class WikiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.vault = root / 'vault'
        self.repo = root / 'repo'
        self.work = root / 'work'
        self.vault.mkdir()
        self.repo.mkdir()
        self.env = configure_fixture(self.repo, self.vault)
        self.req = {'task_id': 'test', 'project': 'jarvis', 'approval': 'explicit test',
                    'vault_fingerprint': w.digest(str(self.vault.resolve())),
                    'targets': ['03 wiki/综合/test.md'], 'sources': []}
        for sid, text in [('one', 'Environment selects the vault.'), ('two', 'Approval controls content writes.')]:
            (self.repo / (sid + '.md')).write_text(text, encoding='utf-8')
            self.req['sources'].append({'id': sid, 'root': 'repo', 'path': sid + '.md',
                                       'kind': 'original', 'sha256': w.digest(text.encode())})
        self.candidate = {'target': self.req['targets'][0], 'title': 'Selection and approval',
                          'topic': 'selection', 'generator': 'active-session-llm', 'model_run': 'test-model-run',
                          'gaps': ['GUI not verified'], 'conflicts': [],
                          'claims': [{'text': 'Selection and authorization are distinct checks.', 'basis': 'synthesis',
                                      'evidence': [{'source': 'one', 'quote': 'Environment selects the vault.'},
                                                   {'source': 'two', 'quote': 'Approval controls content writes.'}]}]}
        self.patcher = patch.dict(os.environ, {'JARVIS_VAULT_ROOT': str(self.vault)})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def proposal(self):
        return w.prepare(self.env, self.req, self.candidate)

    def apply(self, proposal=None):
        p = proposal or self.proposal()
        return w.apply(self.env, self.req, p, p['proposal_hash'], self.work)

    def test_full_flow_repeat_and_review(self):
        p = self.proposal()
        self.assertIn('+status: "review"', p['diff'])
        self.apply(p)
        self.assertFalse(w.review(self.env, self.req, self.work)['topics'][0]['needs_review'])
        with self.assertRaisesRegex(ValueError, 'already applied'):
            self.apply(p)
        (self.repo / 'one.md').write_text('changed', encoding='utf-8')
        issues = w.review(self.env, self.req, self.work)['topics'][0]['issues']
        self.assertIn('source_changed', [i['reason'] for i in issues])
        (self.repo / 'two.md').unlink()
        self.assertIn('missing_or_outside_scope', [i['reason'] for i in w.review(self.env, self.req, self.work)['topics'][0]['issues']])

    def test_stale_source_and_human_target(self):
        p = self.proposal()
        target = self.vault / p['target']
        target.parent.mkdir(parents=True)
        target.write_text('human', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'baseline'):
            self.apply(p)
        self.assertEqual(target.read_text(), 'human')
        target.unlink()
        (self.repo / 'one.md').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            self.apply(p)

    def test_tamper_and_wrong_vault(self):
        p = self.proposal()
        p['markdown'] += 'tamper'
        with self.assertRaisesRegex(ValueError, 'modified'):
            self.apply(p)
        self.req['vault_fingerprint'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'another vault'):
            self.proposal()

    def test_scope_and_evidence(self):
        for path in ['../outside.md', '03 wiki/综合/not-approved.md']:
            self.candidate['target'] = path
            with self.assertRaises(ValueError):
                self.proposal()
        self.candidate['target'] = self.req['targets'][0]
        self.candidate['claims'][0]['evidence'][0]['quote'] = 'fabricated'
        with self.assertRaisesRegex(ValueError, 'fabricated'):
            self.proposal()

    def test_cross_project_and_circular_evidence(self):
        self.req['sources'][0].update(root='vault', path='02 工作记录/任务总结/other/secret.md')
        with self.assertRaisesRegex(ValueError, 'outside'):
            self.proposal()
        self.req['sources'][0].update(root='repo', path='one.md', kind='model-synthesis')
        with self.assertRaisesRegex(ValueError, 'primary'):
            self.proposal()

    def test_non_current_and_empty_model(self):
        source = self.req['sources'][0]
        raw = b'---\nstatus: superseded\n---\nEnvironment selects the vault.'
        (self.repo / source['path']).write_bytes(raw)
        source['sha256'] = w.digest(raw)
        with self.assertRaisesRegex(ValueError, 'Non-current'):
            self.proposal()
        source['allow_non_current'] = True
        with self.assertRaisesRegex(ValueError, 'Non-current'):
            self.proposal()
        self.candidate['claims'][0]['basis'] = 'historical'
        self.assertIn('superseded', self.proposal()['markdown'])
        self.candidate['claims'] = []
        with self.assertRaisesRegex(ValueError, 'Empty model'):
            self.proposal()

    def test_partial_failure_reconcile_no_replay(self):
        p = self.proposal()
        original = w.save
        def fail_registry(path, value, exclusive=False):
            if Path(path).name == 'registry.json':
                raise OSError('simulated ledger failure after target write')
            return original(path, value, exclusive)
        with patch.object(w, 'save', side_effect=fail_registry):
            with self.assertRaises(OSError):
                self.apply(p)
        target = self.vault / p['target']
        before = target.read_bytes()
        w.reconcile(self.env, self.req, self.work, p['proposal_hash'])
        self.assertEqual(target.read_bytes(), before)
        self.assertFalse(w.review(self.env, self.req, self.work)['topics'][0]['needs_review'])
        target.write_text('human recovery edit')
        self.assertEqual(w.reconcile(self.env, self.req, self.work, p['proposal_hash'])['status'], 'unknown_or_changed')

    def test_qa_feedback_and_embedded_escape(self):
        self.candidate.update(origin='qa', question='How to select a vault?', reuse_reason='Repeated setup question')
        self.assertIn('review', self.proposal()['markdown'])
        self.candidate['claims'][0]['text'] += ' [[../secret]]'
        with self.assertRaisesRegex(ValueError, 'wikilink'):
            self.proposal()

    def test_duplicate_topic_and_manual_update_backup(self):
        self.apply()
        self.candidate['target'] = '03 wiki/综合/duplicate.md'
        self.req['targets'].append(self.candidate['target'])
        with self.assertRaisesRegex(ValueError, 'Duplicate topic'):
            self.apply()
        self.candidate['target'] = self.req['targets'][0]
        self.candidate['gaps'].append('new gap')
        p = self.proposal()
        self.apply(p)
        self.assertTrue((self.work / (p['proposal_hash'] + '.backup')).exists())

    def test_version_registration_is_idempotent_and_preserves_history(self):
        self.assertEqual(len(w.register(self.env, self.req, self.work)['new_versions']), 2)
        self.assertEqual(w.register(self.env, self.req, self.work)['new_versions'], [])
        source = self.req['sources'][0]
        raw = b'New source version'
        (self.repo / source['path']).write_bytes(raw)
        source['sha256'] = w.digest(raw)
        self.assertEqual(w.register(self.env, self.req, self.work)['new_versions'], ['one'])
        self.assertEqual(len(w.load(self.work / 'source-versions.json')['versions']['one']), 2)

    def test_wrong_environment_and_external_lock(self):
        p = self.proposal()
        path = self.repo / '.local/environment.json'
        baseline = path.read_bytes()
        settings = json.loads(baseline)
        settings['instance_id'] = 'e7929d93-4937-4adc-a36f-f002e7701368'
        path.write_text(json.dumps(settings), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.apply(p)
        path.write_bytes(baseline)
        self.work.mkdir()
        (self.work / 'writer.lock').write_text('other writer')
        with self.assertRaises(FileExistsError):
            self.apply(p)
        self.assertEqual((self.work / 'writer.lock').read_text(), 'other writer')


if __name__ == '__main__':
    unittest.main()
