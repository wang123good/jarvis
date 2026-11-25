"""Evidence failure cases; fixtures are not a real reuse experiment."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('reuse', Path(__file__).resolve().parents[1] / 'scripts/brain_reuse.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class ReuseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name, value in [('source.md', 'old knowledge'), ('review.md', 'current independent check'),
                            ('command.json', '{"exit_code":0}'), ('report.md', 'observed result')]:
            (self.root / name).write_text(value, encoding='utf-8')
        def ref(name):
            return {'file': name, 'sha256': r.digest(self.root / name)}
        self.request = {'schema_version': 1, 'task_id': 'TEST', 'goal': 'diagnose',
                        'failure_condition': 'no result', 'limitations': 'fixture only',
                        'sources': [{'id': 'S1', 'status': 'review', 'path': 'source.md',
                                     'snapshot': ref('source.md'), 'revalidation': ref('review.md'),
                                     'applicability': 'current code checked', 'invalid_if': 'code changes'}],
                        'actions': [{'source_id': 'S1', 'decision_change': 'add connector check',
                                     'outcome': 'observed', 'result': 'connector unverified',
                                     'evidence': ref('command.json'), 'artifact': ref('report.md')}]}

    def test_complete_chain_does_not_claim_semantic_success(self):
        result = r.validate(self.request, self.root, self.root)
        self.assertEqual(result['status'], 'evidence_complete')
        self.assertEqual(result['semantic_reuse'], 'requires_review')

    def test_missing_empty_or_modified_artifact_rejected(self):
        for value in (None, '', 'changed'):
            with self.subTest(value=value):
                path = self.root / 'report.md'
                if value is None:
                    path.unlink()
                else:
                    path.write_text(value)
                with self.assertRaises(ValueError):
                    r.validate(self.request, self.root)

    def test_unknown_planned_and_failed_actions_rejected(self):
        for value in ('unknown', 'planned', 'failed'):
            self.request['actions'][0]['outcome'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                r.validate(self.request, self.root)

    def test_review_and_active_need_current_revalidation(self):
        for status in ('review', 'active'):
            self.request['sources'][0]['status'] = status
            self.request['sources'][0]['revalidation'] = None
            with self.subTest(status=status), self.assertRaises(ValueError):
                r.validate(self.request, self.root)

    def test_noncurrent_source_rejected(self):
        for status in ('superseded', 'expired', 'draft', 'archived'):
            self.request['sources'][0]['status'] = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                r.validate(self.request, self.root)

    def test_live_source_drift_rejected_even_if_snapshot_stable(self):
        vault = self.root / 'vault'
        vault.mkdir()
        (vault / 'source.md').write_text('new content')
        with self.assertRaisesRegex(ValueError, 'Live source drift'):
            r.validate(self.request, self.root, vault)

    def test_escape_paths_rejected_for_evidence_and_live_source(self):
        for path in ('../outside.md', 'C:/private/file.md', '/outside.md', '..\\outside.md'):
            for field in ('snapshot', 'path'):
                request = copy.deepcopy(self.request)
                if field == 'path':
                    request['sources'][0]['path'] = path
                else:
                    request['sources'][0][field]['file'] = path
                with self.subTest(path=path, field=field), self.assertRaises(ValueError):
                    r.validate(request, self.root, self.root)

    def test_missing_unlinked_or_duplicate_source_rejected(self):
        for mutate in (lambda q: q.update(sources=[]),
                       lambda q: q['actions'][0].update(source_id='missing'),
                       lambda q: q['sources'].append(copy.deepcopy(q['sources'][0]))):
            request = copy.deepcopy(self.request)
            mutate(request)
            with self.assertRaises(ValueError):
                r.validate(request, self.root)

    def test_public_example_is_incomplete(self):
        example = Path(__file__).resolve().parents[1] / 'templates/reuse/request.example.json'
        with self.assertRaises(ValueError):
            r.validate(json.loads(example.read_text(encoding='utf-8')), self.root)


if __name__ == '__main__':
    unittest.main()
