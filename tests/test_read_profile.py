import json
from pathlib import Path
import tempfile
import unittest

from scripts.read_profile import load
from scripts.update_profile import update


class ProfileEncodingTests(unittest.TestCase):
    def test_load_windows_utf8_bom_without_changing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / 'up.json'
            raw = json.dumps({'schema_version': '1.0', 'nickname': '测试',
                              'preferences': [], 'candidates': []},
                             ensure_ascii=False).encode('utf-8-sig')
            profile.write_bytes(raw)
            self.assertEqual(load(profile)['nickname'], '测试')
            self.assertEqual(profile.read_bytes(), raw)


class ProfileWorkflowTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'up.json'
        self.document = {'schema_version': '1.0', 'nickname': 'Andy',
                         'preferences': [], 'candidates': []}
        self.write_fixture()

    def write_fixture(self):
        self.path.write_text(json.dumps(self.document), encoding='utf-8')

    def observe(self, event, key='workflow'):
        return update(self.path, {'action': 'observe', 'id': key, 'event': event,
                                  'statement': 'Review workflow', 'source': 'user turn',
                                  'date': '2026-11-21'})

    def test_observe_replay_review_and_context(self):
        self.assertEqual(self.observe('turn-1')['proposals'][0]['count'], 1)
        self.assertFalse(self.observe('turn-1')['changed'])
        self.assertEqual(load(self.path, index=True)['preferences'], [])
        update(self.path, {'action': 'approve', 'id': 'workflow', 'date': '2026-11-21'})
        self.assertEqual(load(self.path, selected=['workflow'])['preferences'][0]['count'], 1)
        self.assertEqual(load(self.path, selected=['unrelated'])['preferences'], [])
        update(self.path, {'action': 'pause', 'id': 'workflow'})
        self.assertEqual(load(self.path, selected=['workflow'])['preferences'], [])
        update(self.path, {'action': 'settings', 'collect_candidates': False})
        self.assertFalse(self.observe('turn-2', 'new')['changed'])

    def test_capacity_threshold_and_reminder_deduplication(self):
        formal = self.document['preferences']
        for index in range(19):
            formal.append(dict(id=f'formal-{index}', statement='Formal preference',
                               scope='JARVIS', source='approved input', status='approved',
                               recorded_at='2026-11-21', approved_at='2026-11-21',
                               evidence=[str(n) for n in range(10)]))
        self.write_fixture()
        self.assertIsNone(self.observe('candidate-1')['proposals'][0]['target'])
        update(self.path, {'action': 'approve', 'id': 'workflow', 'date': '2026-11-21'})
        for n in range(2, 11):
            self.observe(f'candidate-{n}')
        for n in range(1, 12):
            result = self.observe(f'new-{n}', 'new')
            self.assertEqual(result['proposals'], [])
        with self.assertRaisesRegex(ValueError, 'full'):
            update(self.path, {'action': 'approve', 'id': 'new', 'date': '2026-11-21'})
        self.assertEqual(len(load(self.path)['preferences']), 20)
        result = self.observe('new-12', 'new')
        self.assertEqual(result['proposals'][0]['target'], 'workflow')
        update(self.path, {'action': 'shown', 'id': 'new', 'target': 'workflow'})
        self.assertEqual(self.observe('new-13', 'new')['proposals'], [])
        update(self.path, {'action': 'defer', 'id': 'new'})
        self.assertEqual(self.observe('new-14', 'new')['proposals'], [])
        self.assertEqual(self.observe('new-15', 'new')['proposals'][0]['count'], 15)
        update(self.path, {'action': 'replace', 'id': 'new', 'target': 'workflow',
                           'date': '2026-11-21'})
        index = load(self.path, index=True)['preferences']
        self.assertEqual(len(index), 20)
        self.assertEqual(len(load(self.path, selected=[item['id'] for item in index])['preferences']), 5)

    def test_existing_lock_preserves_profile(self):
        baseline = self.path.read_bytes()
        self.path.with_suffix('.json.lock').touch()
        with self.assertRaises(FileExistsError):
            self.observe('turn-1')
        self.assertEqual(self.path.read_bytes(), baseline)
