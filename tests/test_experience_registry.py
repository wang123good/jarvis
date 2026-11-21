import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import experience_registry as registry
from task_knowledge import inspect_skill


class RegistryTests(unittest.TestCase):
    def test_registry_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            notes = root / 'notes'
            notes.mkdir()
            evidence = notes / 'result.md'
            evidence.write_bytes(b'fixture evidence')
            skill = root / '.agents/skills/example/SKILL.md'
            skill.parent.mkdir(parents=True)
            skill.write_bytes(b'fixture skill')
            path = root / 'registry/file.json'
            env = {'project_root': str(root), 'vault_root': str(root), 'vault_exists': True,
                   'connector_checked': True, 'registry': str(path), 'skill_roots': [],
                   'project_knowledge_root': str(notes), 'agreement': str(notes / 'agreement.md'),
                   'resolved_pointer': {'project': {'id': 'fixture'}}}

            def query(*terms):
                return registry.query(env, terms, 5, inspect_skill)

            self.assertEqual(query()['status'], 'missing')
            with self.assertRaises(ValueError):
                registry.initialize({**env, 'connector_checked': False})
            baseline = registry.initialize(env)['registry_sha256']
            self.assertEqual(query()['registered'], 0)
            with self.assertRaises(FileExistsError):
                registry.initialize(env)
            item = {'id': 'fixture', 'name': 'Camera calibration',
                    'signature': 'camera-calibration', 'goal': 'Color accuracy',
                    'scope': 'Mobile sensor', 'keywords': ['ISP tuning'], 'status': 'approved',
                    'approval': 'fixture approval', 'shortcoming': 'fixture limits',
                    'updated_at': '2026-01-01T00:00:00+00:00', 'use_count': None,
                    'evidence': 'notes/result.md', 'evidence_sha256': registry.digest(evidence.read_bytes()),
                    'skill': 'example', 'skill_sha256': registry.digest(skill.read_bytes())}
            newest = registry.register(env, item, baseline, inspect_skill)['registry_sha256']
            self.assertEqual(query('mobile ISP tuning')['results'][0]['id'], 'fixture')
            self.assertEqual(query('spreadsheet')['count'], 0)
            with self.assertRaisesRegex(ValueError, 'baseline'):
                registry.register(env, {**item, 'id': 'another'}, baseline, inspect_skill)
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                registry.register(env, item, newest, inspect_skill)
            self.assertEqual(registry.digest(path.read_bytes()), newest)
            evidence.write_bytes(b'changed')
            self.assertEqual(query('ISP tuning')['excluded'][0]['reason'], 'evidence_missing_or_changed')
            skill.write_bytes(b'changed')
            self.assertEqual(query('ISP tuning')['excluded'][0]['reason'], 'skill_missing_ambiguous_or_changed')
            path.write_bytes(b'{')
            with self.assertRaises(ValueError):
                query()
