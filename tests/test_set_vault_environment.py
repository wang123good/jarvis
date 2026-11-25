import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import set_vault_environment as setter
from environment_isolation import isolate_vault_environment


class UserVaultEnvironmentTests(unittest.TestCase):
    def setUp(self):
        isolate_vault_environment(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.vault = self.root / 'selected vault'
        self.vault.mkdir()
        for name, data in {
            'config/defaults.json': {'environment_file': '.local/environment.json',
                                    'knowledge_pointer': '.codex/obsidian-kb.json',
                                    'registry': 'registry.json', 'agreement': 'agreement.md'},
            '.codex/obsidian-kb.json': {'environment_file': '.local/environment.json',
                                      'project': {'root': 'notes'}, 'layers': {}},
        }.items():
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data), encoding='utf-8')
        self.values = {}
        owner = self

        class Key:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        def query(key, name):
            if name not in owner.values:
                raise FileNotFoundError(name)
            return owner.values[name]

        self.registry = SimpleNamespace(
            HKEY_CURRENT_USER=1, REG_SZ=1,
            CreateKey=lambda *a: Key(), OpenKey=lambda *a: Key(), QueryValueEx=query,
            SetValueEx=lambda key, name, reserved, kind, value: owner.values.update({name: (value, kind)}),
            DeleteValue=lambda key, name: owner.values.pop(name),
        )
        self.enterContext(patch.dict(sys.modules, winreg=self.registry))

    @unittest.skipUnless(os.name == 'nt', 'Windows user environment persistence')
    def test_persistence_readback_backup_and_runtime_pointer(self):
        result = setter.persist_user_vault(str(self.vault), self.root)
        self.assertEqual(self.values[setter.VAULT_ENV][0], str(self.vault.resolve()))
        self.assertNotIn(setter.VAULT_ENV, os.environ)
        self.assertTrue(Path(result['backup']).is_file())
        self.assertEqual(Path(json.loads(Path(result['runtime_pointer']).read_text())['vault']), self.vault)

    @unittest.skipUnless(os.name == 'nt', 'Windows user environment persistence')
    def test_pointer_failure_restores_prior_user_and_process_values(self):
        self.values[setter.VAULT_ENV] = ('old-user-vault', 1)
        with patch.dict(os.environ, {setter.VAULT_ENV: str(self.vault)}), \
                patch.object(setter, 'write_runtime_pointer', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError):
                setter.persist_user_vault(str(self.vault), self.root)
            self.assertEqual(os.environ[setter.VAULT_ENV], str(self.vault))
        self.assertEqual(self.values[setter.VAULT_ENV], ('old-user-vault', 1))

    @unittest.skipUnless(os.name == 'nt', 'Windows user environment persistence')
    def test_failed_first_persistence_removes_new_user_value(self):
        with patch.object(setter, 'write_runtime_pointer', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError):
                setter.persist_user_vault(str(self.vault), self.root)
        self.assertEqual(self.values, {})

    def test_conflicting_process_override_fails_before_side_effects(self):
        with patch.dict(os.environ, {setter.VAULT_ENV: str(self.root)}):
            with self.assertRaisesRegex(ValueError, 'Conflicting process'):
                setter.persist_user_vault(str(self.vault), self.root)
        self.assertEqual(self.values, {})
        self.assertFalse((self.root / '.local').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows persistence')
    def test_public_setup_persists_old_cli_and_next_resolution_is_ready(self):
        import setup_environment as setup
        import resolve_environment as reader
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            code = setup.main(['--connector-vault', str(self.vault)], self.root)
        self.assertEqual(code, 0)
        resolved = reader.resolve_environment(self.root)
        self.assertTrue(resolved['write_ready'])
        self.assertEqual(Path(resolved['vault_root']), self.vault)
        local = json.loads((self.root / '.local/environment.json').read_text())
        self.assertNotIn('vault_root', local)

    @unittest.skipUnless(os.name == 'nt', 'Windows persistence')
    def test_public_setup_rolls_back_registry_and_local_files_on_failure(self):
        import setup_environment as setup
        self.values[setter.VAULT_ENV] = ('old-user-vault', 1)
        with patch.object(setup.reader, 'write_runtime_pointer', side_effect=OSError('failure')):
            with self.assertRaises(OSError):
                setup.initialize(self.root, str(self.vault))
        self.assertEqual(self.values[setter.VAULT_ENV], ('old-user-vault', 1))
        self.assertFalse((self.root / '.local/environment.json').exists())

    def test_nonexistent_vault_cannot_change_user_environment(self):
        with self.assertRaises(ValueError):
            setter.persist_user_vault(str(self.root / 'missing'), self.root)
        self.assertEqual(self.values, {})
