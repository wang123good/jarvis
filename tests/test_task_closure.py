import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import task_closure


class TaskClosureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.task = Path(temporary.name) / 'TEST-CLOSURE'
        (self.task / 'closure').mkdir(parents=True)
        self.manifest = {
            'schema_version': 1, 'task_id': self.task.name,
            'contract': self.file('contract.md', 'Approved scope'),
            'business': {'status': 'pending'}, 'notes': {'status': 'pending'},
            'sources': [self.file('checks/result.md', 'Actual scoped verification')],
            'coverage': 'Only this test fixture; no complete chat source.',
            'layers': {layer: {'disposition': 'candidate', **self.file(f'closure/{layer}.md', layer)}
                       for layer in task_closure.LAYERS},
            'risk_review': self.file('closure/review.md', 'Specific evidence gaps and recommendations'),
        }

    def file(self, name, content):
        path = self.task / name
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(content, encoding='utf-8')
        return {'file': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def decide(self, field, status):
        self.manifest[field] = {'status': status, 'basis': f'Explicit fixture {status} decision',
                                'decision': self.file(f'{field}-decision.md', status)}

    def result(self):
        return task_closure.validate(self.task, self.manifest)

    def test_business_and_notes_are_separate_and_never_grant_vault_write(self):
        self.assertEqual(self.result()['status'], '已交付待验收')
        self.decide('notes', 'approved')
        self.assertEqual(self.result()['status'], '已交付待验收')
        self.decide('business', 'accepted')
        self.assertEqual(self.result()['status'], '已验收')
        self.assertFalse(self.result()['vault_write_authorized'])
        self.assertFalse(self.result()['semantic_review_verified'])
        self.manifest['notes'] = {'status': 'pending'}
        self.assertEqual(self.result()['status'], '已交付待笔记复核')
        self.decide('business', 'not_required')
        self.assertEqual(self.result()['status'], '已交付待笔记复核')
        self.decide('notes', 'approved')
        self.assertEqual(self.result()['status'], '已交付无需验收')

    def test_decisions_need_specific_basis_and_existing_evidence(self):
        for field, status in [('business', 'accepted'), ('business', 'not_required'),
                              ('notes', 'approved'), ('notes', 'skipped')]:
            with self.subTest(field=field, status=status):
                original = copy.deepcopy(self.manifest)
                self.manifest[field] = {'status': status}
                with self.assertRaises(ValueError):
                    self.result()
                self.manifest = original

    def test_explicit_skip_needs_no_generated_notes(self):
        self.decide('notes', 'skipped')
        for key in ('sources', 'coverage', 'layers', 'risk_review'):
            del self.manifest[key]
        self.assertEqual(self.result()['status'], '已交付待验收')
        self.decide('business', 'accepted')
        self.assertEqual(self.result()['status'], '已验收')

    def test_returned_business_or_notes_reopens_work(self):
        self.decide('business', 'returned')
        self.assertEqual(self.result()['status'], '执行中')
        self.decide('business', 'accepted')
        self.decide('notes', 'returned')
        self.assertEqual(self.result()['status'], '执行中')

    def test_no_new_wiki_knowledge_requires_reason(self):
        self.manifest['layers']['wiki'] = {'disposition': 'no_candidate'}
        with self.assertRaises(ValueError):
            self.result()
        self.manifest['layers']['wiki']['reason'] = 'No reusable finding beyond linked existing note.'
        self.assertTrue(self.result()['ok'])

    def test_layer_exclusion_needs_decision_and_reason(self):
        self.manifest['layers']['archive'] = {'disposition': 'excluded', 'reason': 'User limited notes'}
        with self.assertRaises(ValueError):
            self.result()
        self.manifest['layers']['archive']['decision'] = self.file('limit.md', 'Only summary and wiki')
        self.assertTrue(self.result()['ok'])

    def test_changed_sources_candidates_and_contract_are_rejected(self):
        for name in ('contract.md', 'checks/result.md', 'closure/wiki.md', 'closure/review.md'):
            with self.subTest(name=name):
                path = self.task / name
                original = path.read_bytes()
                path.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'Evidence changed'):
                    self.result()
                path.write_bytes(original)

    def test_paths_cannot_escape_or_replace_contract(self):
        for name in ('../outside.md', '/outside.md', 'C:\\outside.md'):
            with self.subTest(name=name):
                self.manifest['sources'][0]['file'] = name
                with self.assertRaises(ValueError):
                    self.result()
        self.manifest['contract'] = self.file('other.md', 'Not the contract')
        with self.assertRaisesRegex(ValueError, 'Pin the current contract'):
            self.result()

    def test_three_layers_are_accounted_without_duplicate_candidates(self):
        del self.manifest['layers']['wiki']
        with self.assertRaises(ValueError):
            self.result()
        self.manifest['layers']['wiki'] = self.manifest['layers']['summary']
        with self.assertRaisesRegex(ValueError, 'Each layer'):
            self.result()

    def test_candidate_outside_closure_rejected(self):
        self.manifest['layers']['summary'] = {'disposition': 'candidate', **self.file('summary.md', 'outside')}
        with self.assertRaisesRegex(ValueError, 'Candidate must stay'):
            self.result()

    def test_validation_is_read_only(self):
        before = {p.relative_to(self.task): p.read_bytes() for p in self.task.rglob('*') if p.is_file()}
        self.result()
        after = {p.relative_to(self.task): p.read_bytes() for p in self.task.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_cli_missing_task_fails_without_creation(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / 'task_closure.py'), '../OUTSIDE'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)['ok'])


if __name__ == '__main__':
    unittest.main()
