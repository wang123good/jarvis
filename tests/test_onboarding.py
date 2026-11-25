import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import onboarding


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()
        self.root = self.base / 'project'
        for rel in ('config/defaults.json', '.codex/obsidian-kb.json'):
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, target)
        self.vault = self.base / '个人知识库'
        self.selected = None
        self.addCleanup(patch.stopall)
        patch.object(onboarding.environment, 'vault_environment', side_effect=lambda: (
            self.selected, 'user_environment' if self.selected else 'legacy_local_file')).start()
        patch.object(onboarding.environment, 'user_vault_environment', side_effect=lambda: self.selected).start()
        patch.dict(onboarding.os.environ, {'APPDATA': str(self.base)}).start()
        onboarding.os.environ.pop(onboarding.environment.VAULT_ENV, None)
        patch.object(onboarding, 'fixed_drives', return_value=[]).start()
        patch.object(onboarding.Path, 'home', return_value=self.base).start()
        patch.object(onboarding, 'software', return_value={'executable': 'fixture/Obsidian.exe'}).start()
        patch.object(onboarding.setup_environment, 'initialize', side_effect=self.configure).start()

    def configure(self, root, destination):
        self.selected = destination
        return onboarding.setup_environment.configure(root, destination)

    def run_command(self, *args, expected=0):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = onboarding.main(args, self.root)
        result = json.loads(stream.getvalue())
        self.assertEqual(code, expected, result)
        return result

    def preview(self, kind='new'):
        self.run_command('start', '--request-ref', 'fixture-turn-1')
        self.run_command('nickname', '--skip')
        return self.run_command('select', kind, str(self.vault))

    def test_entry_and_nickname_are_resumable(self):
        self.assertEqual(self.run_command('status')['stage'], 'start')
        self.assertFalse((self.root / '.local').exists())
        first = self.run_command('start', '--request-ref', 'original')
        self.assertEqual(first['stage'], 'nickname')
        self.assertEqual(self.run_command('start', '--request-ref', 'later')['request_ref'], 'original')
        self.assertTrue(self.run_command('pause')['paused'])
        self.run_command('nickname', '--skip', expected=2)
        self.assertFalse(self.run_command('resume')['paused'])
        self.run_command('nickname', expected=2)
        self.assertEqual(self.run_command('nickname', '--skip')['stage'], 'selection')
        self.assertTrue(self.run_command('status')['nickname_skipped'])

    def test_ready_profile_needs_no_nickname(self):
        profile = json.loads((ROOT / 'up.example.json').read_text(encoding='utf-8'))
        profile['nickname'] = 'Fixture'
        (self.root / 'up.json').write_text(json.dumps(profile), encoding='utf-8')
        result = self.run_command('start', '--request-ref', 'original')
        self.assertEqual(result['stage'], 'selection')
        self.assertEqual(result['nickname'], 'Fixture')

    def test_bounded_discovery_and_default_disk(self):
        self.assertEqual(self.run_command('discover')['candidates'], [])
        drives = [self.base / name for name in ('largest', 'occupied', 'available')]
        for drive in drives:
            drive.mkdir()
        existing = drives[0] / '个人知识库'
        (existing / '.obsidian').mkdir(parents=True)
        (drives[1] / '个人知识库').mkdir()
        appdata = self.base / 'obsidian'
        appdata.mkdir()
        config = appdata / 'obsidian.json'
        config.write_text(json.dumps({'vaults': {'one': {'path': str(existing)}}}), encoding='utf-8')
        with patch.object(onboarding, 'fixed_drives', return_value=list(zip(drives, [900, 800, 700]))):
            result = self.run_command('discover')
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(result['candidates'][0]['sources'], ['obsidian_registry', 'common_path'])
        self.assertEqual([item['status'] for item in result['new_vault']['drives']],
                         ['existing_vault', 'occupied', 'available'])
        self.assertEqual(Path(result['new_vault']['default']).parent, drives[2])
        second = self.base / 'alternate'
        second.mkdir()
        config.write_text(json.dumps({'vaults': {'one': {'path': str(existing)},
                                               'two': {'path': str(second)}}}), encoding='utf-8')
        self.assertEqual(len(self.run_command('discover')['candidates']), 2)
        with patch.object(onboarding, 'fixed_drives', return_value=list(zip(drives, [900, 800, 700]))), \
                patch.object(onboarding, 'can_add_directory', return_value=False):
            result = self.run_command('discover')
        self.assertIsNone(result['new_vault']['default'])
        self.assertEqual(result['new_vault']['drives'][-1]['status'], 'parent_not_writable')

    def test_new_vault_real_router_and_activation(self):
        selection = self.preview()
        approval = selection['approval_code']
        self.run_command('prepare', '--approved', 'wrong', expected=2)
        self.assertFalse(self.vault.exists())
        self.run_command('display', expected=2)
        verified = self.run_command('prepare', '--approved', approval)
        source = self.vault / verified['proof']['path']
        self.assertIn('运行规程', source.read_text(encoding='utf-8'))
        self.assertTrue(verified['proof']['excerpt'])
        self.assertEqual([p['id'] for p in verified['proof']['health']['projects']], ['jarvis'])
        runtime = onboarding.environment.resolve_environment(self.root)
        self.assertTrue(onboarding.brain_router.router_config_path(runtime).is_file())
        self.assertTrue(runtime['persona']['enabled'])
        self.assertEqual(runtime['persona'].get('module', 'steady'), 'steady')
        router_output = io.StringIO()
        with patch.object(onboarding.environment, 'resolve_environment', return_value=runtime), \
                contextlib.redirect_stdout(router_output):
            self.assertEqual(onboarding.brain_router.main(
                ['project', '--query', 'Brain v1 运行规程']), 0)
        self.assertIn(verified['proof']['path'], [item['path'] for item in
                                                 json.loads(router_output.getvalue())['results']])
        displayed = self.run_command('display')
        self.assertEqual(displayed, self.run_command('display'))
        self.run_command('acknowledge', '--reply', '已看到 bad', expected=2)
        self.assertEqual(self.run_command('status')['stage'], 'display')
        with source.open('a', encoding='utf-8') as stream:
            stream.write('\n补充验证。\n')
        self.run_command('acknowledge', '--reply', displayed['reply'], expected=2)
        self.run_command('verify')
        displayed = self.run_command('display')
        activated = self.run_command('acknowledge', '--reply', displayed['reply'])
        self.assertEqual(activated['resume_request'], 'fixture-turn-1')
        self.selected = str(self.base / 'offline')
        self.assertEqual(self.run_command('status')['stage'], 'activated')
        self.run_command('restart', '--confirm', 'restart')
        self.assertEqual(self.run_command('status')['stage'], 'start')

    def test_existing_vault_write_and_retry_preserve_existing_seed(self):
        (self.vault / '.obsidian').mkdir(parents=True)
        existing = self.vault / '首页.md'
        existing.write_text('existing note', encoding='utf-8')
        preview = self.preview('existing')
        self.assertNotIn('首页.md', preview['change_plan']['files_to_create'])
        original = onboarding.verify_brain
        with patch.object(onboarding, 'verify_brain', side_effect=ValueError('fixture interruption')):
            self.run_command('prepare', '--approved', preview['approval_code'], expected=2)
        self.assertEqual(self.run_command('status')['stage'], 'preparing')
        self.assertEqual(existing.read_text(encoding='utf-8'), 'existing note')
        self.run_command('prepare', '--approved', preview['approval_code'])
        self.assertTrue(original(self.root, self.vault, None)['health']['ok'])
        self.assertEqual(existing.read_text(encoding='utf-8'), 'existing note')

    def test_new_target_drift_and_connector_mismatch_block_writes(self):
        selection = self.preview()
        self.vault.mkdir()
        self.run_command('prepare', '--approved', selection['approval_code'], expected=2)
        self.assertEqual(list(self.vault.iterdir()), [])
        self.run_command('select', 'existing', str(self.vault), '--connector-vault',
                         str(self.base), expected=2)
        self.assertIsNone(self.selected)


if __name__ == '__main__':
    unittest.main()
