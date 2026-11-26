"""CLI protocol fixtures are isolated; they do not claim a real CLI was installed."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import obsidian_cli as cli
from environment_isolation import configure_fixture


class CLITests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.root = self.base / 'repo'
        self.vault = self.base / 'one' / '同名 库'
        self.other = self.base / 'two' / '同名 库'
        self.vault.mkdir(parents=True)
        self.other.mkdir(parents=True)
        configure_fixture(self.root, self.vault)
        self.registry = self.base / 'obsidian/obsidian.json'
        self.registry.parent.mkdir()
        self.entries = {'vaults': {'abc123': {'path': str(self.vault)},
                                  'def456': {'path': str(self.other)}}}
        self.save_registry()
        self.enterContext(patch.dict(os.environ, {'APPDATA': str(self.base),
                                                  'JARVIS_VAULT_ROOT': str(self.other)}))
        self.which = self.enterContext(patch.object(cli.shutil, 'which', return_value='fixture/Obsidian.com'))
        self.running = self.enterContext(patch.object(cli, 'app_running', return_value=True))
        self.run = self.enterContext(patch.object(cli.subprocess, 'run', return_value=
            subprocess.CompletedProcess([], 0, str(self.vault) + '\n', '')))

    def save_registry(self):
        self.registry.write_text(json.dumps(self.entries), encoding='utf-8')

    def test_same_names_use_path_matched_id_and_live_path(self):
        result = cli.check(self.root)
        self.assertTrue(result['cli_ready'], result)
        self.assertEqual(result['vault_id'], 'abc123')
        args = self.run.call_args.args[0]
        self.assertEqual(args, ['fixture/Obsidian.com', 'vault=abc123', 'vault', 'info=path'])
        self.assertEqual(list(self.vault.iterdir()), [])
        self.assertNotIn('vault=同名 库', args)

    def test_windows_discovers_terminal_redirector_only(self):
        cli.discover()
        self.which.assert_called_with('Obsidian.com' if os.name == 'nt' else 'obsidian')

    def test_missing_cli_and_stopped_app_do_not_invoke(self):
        self.which.return_value = None
        self.assertEqual(cli.check(self.root)['status'], 'cli_not_on_path')
        self.run.assert_not_called()
        self.which.return_value = 'fixture/Obsidian.com'
        self.running.return_value = False
        self.assertEqual(cli.check(self.root)['status'], 'app_not_running')
        self.run.assert_not_called()

    def test_wrong_name_path_and_multiline_fail_closed(self):
        for reported, status in [(str(self.other), 'target_mismatch'),
                                 ('同名 库', 'target_unverified'),
                                 ('Warning\n' + str(self.vault), 'target_unverified'),
                                 ('', 'target_unverified')]:
            with self.subTest(reported=reported):
                self.run.return_value.stdout = reported
                result = cli.check(self.root)
                self.assertFalse(result['cli_ready'])
                self.assertTrue(result['filesystem_ready'])
                self.assertEqual(result['status'], status)

    def test_registry_missing_unregistered_duplicate_id_paths(self):
        self.entries['vaults'].pop('abc123')
        self.save_registry()
        self.assertEqual(cli.check(self.root)['status'], 'target_unregistered')
        self.entries['vaults'].update({'a': {'path': str(self.vault)}, 'b': {'path': str(self.vault)}})
        self.save_registry()
        self.assertEqual(cli.check(self.root)['status'], 'target_ambiguous')
        self.registry.unlink()
        self.assertEqual(cli.check(self.root)['status'], 'registry_unavailable')
        self.run.assert_not_called()

    def test_timeout_error_and_invalid_utf8(self):
        for error, status in [(subprocess.TimeoutExpired('fixture', 15), 'cli_timeout'),
                              (OSError('unavailable'), 'cli_unavailable'),
                              (UnicodeError('invalid response'), 'cli_unavailable')]:
            with self.subTest(status=status):
                self.run.side_effect = error
                self.assertEqual(cli.check(self.root)['status'], status)
        self.run.side_effect = None
        self.run.return_value.returncode = 1
        self.assertEqual(cli.check(self.root)['status'], 'cli_unavailable')

    def test_configuration_and_registry_drift_are_rechecked(self):
        def drift(*args, **kwargs):
            self.entries['vaults']['abc123']['path'] = str(self.other)
            self.save_registry()
            return subprocess.CompletedProcess([], 0, str(self.vault), '')
        self.run.side_effect = drift
        self.assertFalse(cli.check(self.root)['cli_ready'])
        self.entries['vaults']['abc123']['path'] = str(self.vault)
        self.save_registry()
        def config_drift(*args, **kwargs):
            path = self.root / '.local/environment.json'
            settings = json.loads(path.read_text(encoding='utf-8'))
            settings['obsidian']['vault_root'] = str(self.other)
            path.write_text(json.dumps(settings), encoding='utf-8')
            return subprocess.CompletedProcess([], 0, str(self.vault), '')
        self.run.side_effect = config_drift
        self.assertFalse(cli.check(self.root)['cli_ready'])


if __name__ == '__main__':
    unittest.main()
