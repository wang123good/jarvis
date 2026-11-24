"""Portable configuration and fail-closed vault initialization, using temporary vaults."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


env = load_script('resolve_environment')
initializer = load_script('init_vault')
verifier = load_script('verify_installation')


class PortableEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'checkout'
        self.vault = self.base / '知识库 with spaces'
        self.vault.mkdir()
        self.defaults = {
            'environment_file': '.local/environment.json',
            'knowledge_pointer': '.codex/obsidian-kb.json',
            'registry': '05 规则/JARVIS/任务经验注册表/experience-registry.json',
            'agreement': '05 规则/JARVIS/JARVIS 项目协作约定.md',
        }
        self.pointer = {
            'version': 2, 'environment_file': '.local/environment.json',
            'project': {'id': 'jarvis', 'root': '02 工作记录/任务总结/JARVIS'},
            'layers': {'project': ['02 工作记录/任务总结', '05 规则']},
        }
        self.local = {'version': 1, 'vault_root': str(self.vault), 'skill_roots': []}
        self.save('config/defaults.json', self.defaults)
        self.save('.codex/obsidian-kb.json', self.pointer)
        self.save('.local/environment.json', self.local)

    def save(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def resolve(self, connector=None):
        return env.resolve_environment(self.root, connector)

    def test_resolves_relative_vault_assets(self):
        result = self.resolve()
        self.assertEqual(Path(result['registry']), self.vault / self.defaults['registry'])
        self.assertEqual(Path(result['agreement']), self.vault / self.defaults['agreement'])
        self.assertEqual(Path(result['project_root']), self.root)
        self.assertFalse(result['write_ready'])
        self.assertIsNone(result['connector_matches'])

    def test_second_machine_only_changes_ignored_file(self):
        shared = {p: (self.root / p).read_bytes() for p in ['config/defaults.json', '.codex/obsidian-kb.json']}
        other = self.base / 'another-vault'
        other.mkdir()
        self.local['vault_root'] = str(other)
        self.save('.local/environment.json', self.local)
        self.assertEqual(Path(self.resolve(str(other))['vault_root']), other)
        for name, content in shared.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_missing_local_file_does_not_guess_or_recreate(self):
        local = self.root / '.local/environment.json'
        local.unlink()
        with self.assertRaisesRegex(env.EnvironmentConfigError, 'Missing .local/environment.json'):
            self.resolve()
        self.assertFalse(local.exists())

    def test_cli_missing_configuration_returns_next_action(self):
        with patch.object(
            env,
            'resolve_environment',
            side_effect=env.EnvironmentConfigError(
                'Missing .local/environment.json; run setup_environment.py'
            ),
        ), contextlib.redirect_stdout(io.StringIO()) as output:
            code = env.main([])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload['status'], 'configuration_required')
        self.assertIn('setup_environment.py', payload['next_action'])

    def test_invalid_json_is_preserved(self):
        local = self.root / '.local/environment.json'
        local.write_bytes(b'{invalid')
        with self.assertRaises(env.EnvironmentConfigError):
            self.resolve()
        self.assertEqual(local.read_bytes(), b'{invalid')

    def test_local_root_must_be_absolute(self):
        for value in ['', 'REPLACE_WITH_ABSOLUTE_VAULT_PATH', 'relative/vault', None]:
            with self.subTest(value=value):
                self.local['vault_root'] = value
                self.save('.local/environment.json', self.local)
                with self.assertRaises(env.EnvironmentConfigError):
                    self.resolve()

    def test_shared_absolute_vault_is_rejected(self):
        self.pointer['vault'] = str(self.vault)
        self.save('.codex/obsidian-kb.json', self.pointer)
        with self.assertRaises(env.EnvironmentConfigError):
            self.resolve()

    def test_registry_and_project_paths_cannot_escape_vault(self):
        for value in ['../escape.json', '..\\escape.json', str(self.base / 'escape'), 'C:/escape.json']:
            with self.subTest(value=value):
                self.defaults['registry'] = value
                self.save('config/defaults.json', self.defaults)
                with self.assertRaises(env.EnvironmentConfigError):
                    self.resolve()
        self.defaults['registry'] = '05 规则/registry.json'
        self.save('config/defaults.json', self.defaults)
        self.pointer['project']['root'] = '../another-project'
        self.save('.codex/obsidian-kb.json', self.pointer)
        with self.assertRaises(env.EnvironmentConfigError):
            self.resolve()

    def test_layer_paths_cannot_escape_vault(self):
        self.pointer['layers']['project'] = ['../unrelated']
        self.save('.codex/obsidian-kb.json', self.pointer)
        with self.assertRaises(env.EnvironmentConfigError):
            self.resolve()

    def test_shared_configs_must_use_same_local_entry(self):
        self.pointer['environment_file'] = 'different.json'
        self.save('.codex/obsidian-kb.json', self.pointer)
        with self.assertRaises(env.EnvironmentConfigError):
            self.resolve()

    def test_mismatched_connector_blocks_writes(self):
        with self.assertRaisesRegex(env.EnvironmentConfigError, 'Connected vault mismatch'):
            self.resolve(str(self.base / 'wrong-vault'))
        self.assertEqual(list(self.vault.iterdir()), [])

    def test_matching_connector_allows_write_readiness(self):
        result = self.resolve(str(self.vault))
        env.require_write_ready(result)
        self.assertTrue(result['write_ready'])

    def test_missing_connector_cannot_export_runtime_pointer(self):
        with self.assertRaises(env.EnvironmentConfigError):
            env.write_runtime_pointer(self.resolve())
        self.assertFalse((self.root / '.local/obsidian-kb.resolved.json').exists())

    def test_nonexistent_vault_not_write_ready(self):
        missing = self.base / 'missing-vault'
        self.local['vault_root'] = str(missing)
        self.save('.local/environment.json', self.local)
        result = self.resolve(str(missing))
        self.assertFalse(result['write_ready'])
        with self.assertRaises(env.EnvironmentConfigError):
            env.require_write_ready(result)
        self.assertFalse(missing.exists())

    def test_runtime_pointer_is_local_legacy_shape(self):
        path = env.write_runtime_pointer(self.resolve(str(self.vault)))
        self.assertEqual(path, self.root / '.local/obsidian-kb.resolved.json')
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data['version'], 1)
        self.assertEqual(Path(data['vault']), self.vault)
        self.assertNotIn('environment_file', data)
        self.assertEqual(json.loads((self.root / '.codex/obsidian-kb.json').read_text(encoding='utf-8')), self.pointer)

    def test_initializer_never_called_on_missing_or_mismatched_connection(self):
        for args in [[], ['--connector-vault', str(self.base / 'wrong')],
                     ['--connector-vault', str(self.vault), '--vault', str(self.base / 'override')]]:
            with self.subTest(args=args), patch.object(initializer, 'initialize') as write:
                with contextlib.redirect_stdout(io.StringIO()):
                    code = initializer.main(args, self.root)
                self.assertEqual(code, 2)
                write.assert_not_called()
        self.assertEqual(list(self.vault.iterdir()), [])

    def test_initializer_targets_only_matching_connected_vault(self):
        with patch.object(initializer, 'initialize', return_value={'created': []}) as write:
            with contextlib.redirect_stdout(io.StringIO()):
                code = initializer.main(['--connector-vault', str(self.vault)], self.root)
            self.assertEqual(code, 0)
            write.assert_called_once_with(str(self.vault))

    def test_environment_check_does_not_run_external_retrieval(self):
        out = self.base / 'environment-check'
        out.mkdir()
        with patch.object(verifier, 'ROOT', self.root), patch.object(verifier, 'invoke') as external:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                # This isolated fixture intentionally lacks the distributable resources.
                verifier.run_checks(out, 'fixture', str(self.vault), environment_only=True)
            external.assert_not_called()
        report = json.loads((out / 'verification.json').read_text(encoding='utf-8'))
        self.assertEqual(report['scope'], 'environment-only')
        self.assertFalse(report['ok'])
        self.assertTrue(report['checks']['connected_vault_matches'])

    def test_full_check_reports_missing_registry_without_fabricating_one(self):
        out = self.base / 'full-check'
        out.mkdir()
        with patch.object(verifier, 'ROOT', self.root), patch.object(verifier, 'invoke') as external:
            with self.assertRaisesRegex(RuntimeError, 'registry is missing'):
                verifier.run_checks(out, 'fixture', str(self.vault))
            external.assert_not_called()
        self.assertFalse((self.vault / self.defaults['registry']).exists())
        report = json.loads((out / 'environment-verification.json').read_text(encoding='utf-8'))
        self.assertFalse(report['registry_exists'])


if __name__ == '__main__':
    unittest.main()
