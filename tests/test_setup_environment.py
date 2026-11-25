"""First-run local environment setup tests using temporary vaults."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup = load_script("setup_environment")


from environment_isolation import isolate_vault_environment

class SetupEnvironmentTests(unittest.TestCase):
    def setUp(self):
        isolate_vault_environment(self)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "checkout"
        self.vault = self.base / "vault with spaces"
        self.vault.mkdir()
        self.save(
            "config/defaults.json",
            {
                "environment_file": ".local/environment.json",
                "knowledge_pointer": ".codex/obsidian-kb.json",
                "registry": "05 规则/JARVIS/任务经验注册表/experience-registry.json",
                "agreement": "05 规则/JARVIS/JARVIS 项目协作约定.md",
            },
        )
        self.save(
            ".codex/obsidian-kb.json",
            {
                "version": 2,
                "environment_file": ".local/environment.json",
                "project": {"id": "jarvis", "root": "02 工作记录/任务总结/JARVIS"},
                "layers": {"project": ["02 工作记录/任务总结", "05 规则"]},
            },
        )

    def save(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_creates_ignored_environment_and_runtime_pointer_without_profile_change(self):
        profile = self.root / "up.json"
        profile.write_bytes(b'{"nickname":"Andy"}')
        before = profile.read_bytes()

        result = setup.configure(self.root, str(self.vault))

        environment = json.loads(
            (self.root / ".local/environment.json").read_text(encoding="utf-8")
        )
        runtime = json.loads(
            (self.root / ".local/obsidian-kb.resolved.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result["status"], "created")
        self.assertEqual(Path(environment["obsidian"]["vault_root"]), self.vault)
        self.assertEqual(Path(runtime["vault"]), self.vault)
        self.assertEqual(profile.read_bytes(), before)
        self.assertFalse(result["profile_modified"])
        self.assertEqual(list((self.root / ".local").glob("*.tmp")), [])

    def test_second_run_is_idempotent(self):
        first = setup.configure(self.root, str(self.vault))
        second = setup.configure(self.root, str(self.vault))
        self.assertEqual(first["status"], "created")
        self.assertEqual(second["status"], "already_configured")

    def test_legacy_preview_and_confirmation_preserve_settings(self):
        existing = {'version': 1, 'vault_root': 'old', 'persona': {'enabled': False}, 'custom': [1, 2]}
        self.save('.local/environment.json', existing)
        with patch.dict(os.environ, {setup.reader.VAULT_ENV: str(self.vault)}):
            preview = setup.preview_migration(self.root)
        target = preview['vault_root']
        token = preview['confirmation']
        result = setup.configure(self.root, target, migration=token)
        self.assertEqual(result['status'], 'migrated')
        actual = setup.reader.instance_settings(self.root)
        self.assertEqual(actual['persona'], existing['persona'])
        self.assertEqual(actual['custom'], existing['custom'])
        self.assertEqual(setup.configure(self.root, target, migration=token)['instance_id'],
                         result['instance_id'])

    def test_new_install_enables_persona_and_preserves_it_and_unknown_fields(self):
        setup.configure(self.root, str(self.vault))
        path = self.root / '.local/environment.json'
        configured = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(configured['persona'], {'enabled': True, 'module': 'steady'})
        configured['persona']['enabled'] = False
        configured['custom'] = {'keep': ['user setting']}
        path.write_text(json.dumps(configured), encoding='utf-8')
        before = path.read_bytes()
        setup.configure(self.root, str(self.vault))
        after = path.read_bytes()
        setup.configure(self.root, str(self.vault))
        self.assertEqual(path.read_bytes(), after)
        self.assertEqual(json.loads(before), json.loads(after))

    def test_old_environment_is_not_silently_enabled(self):
        configured = {'version': 1, 'vault_root': str(self.vault), 'skill_roots': [],
                      'custom': {'keep': 1}}
        self.save('.local/environment.json', configured)
        preview = setup.preview_migration(self.root, str(self.vault))
        setup.configure(self.root, str(self.vault), migration=preview['confirmation'])
        actual = setup.reader.instance_settings(self.root)
        self.assertEqual(actual['custom'], configured['custom'])
        self.assertFalse(setup.reader.resolve_environment(self.root)['persona']['enabled'])

    def test_invalid_persona_is_rejected_and_original_preserved(self):
        configured = {'version': 1, 'vault_root': str(self.vault), 'skill_roots': [],
                      'persona': {'enabled': 'yes'}}
        self.save('.local/environment.json', configured)
        path = self.root / '.local/environment.json'
        before = path.read_bytes()
        preview = setup.preview_migration(self.root, str(self.vault))
        with self.assertRaises(setup.reader.EnvironmentConfigError):
            setup.configure(self.root, str(self.vault), migration=preview['confirmation'])
        self.assertEqual(path.read_bytes(), before)

    def test_different_path_requires_explicit_replace(self):
        setup.configure(self.root, str(self.vault))
        other = self.base / "other-vault"
        other.mkdir()
        with self.assertRaisesRegex(setup.SetupError, "--replace"):
            setup.configure(self.root, str(other))
        configured = json.loads(
            (self.root / ".local/environment.json").read_text(encoding="utf-8")
        )
        self.assertEqual(Path(configured["obsidian"]["vault_root"]), self.vault)

    def test_explicit_replace_preserves_skill_roots(self):
        setup.configure(self.root, str(self.vault))
        environment_path = self.root / ".local/environment.json"
        configured = json.loads(environment_path.read_text(encoding="utf-8"))
        configured["skill_roots"] = [str(self.base / "skills")]
        environment_path.write_text(json.dumps(configured), encoding="utf-8")
        other = self.base / "other-vault"
        other.mkdir()

        result = setup.configure(self.root, str(other), replace=True)

        configured = json.loads(environment_path.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "updated")
        self.assertEqual(Path(configured["obsidian"]["vault_root"]), other)
        self.assertEqual(configured["skill_roots"], [str(self.base / "skills")])

    def test_missing_or_relative_vault_is_rejected_without_writes(self):
        for value in (str(self.base / "missing"), "relative/vault"):
            with self.subTest(value=value), self.assertRaises(
                (setup.SetupError, setup.reader.EnvironmentConfigError)
            ):
                setup.configure(self.root, value)
        self.assertFalse((self.root / ".local/environment.json").exists())

    def test_failed_resolution_restores_original_environment(self):
        environment_path = self.root / ".local/environment.json"
        original = b'{"version":1,"vault_root":"C:/old","skill_roots":[]}'
        environment_path.parent.mkdir(parents=True)
        environment_path.write_bytes(original)
        self.save(
            ".codex/obsidian-kb.json",
            {
                "version": 2,
                "environment_file": "different.json",
                "project": {"id": "jarvis", "root": "project"},
                "layers": {"project": ["project"]},
            },
        )
        preview = setup.preview_migration(self.root, str(self.vault))
        with self.assertRaises(setup.reader.EnvironmentConfigError):
            setup.configure(self.root, str(self.vault), migration=preview['confirmation'])
        self.assertEqual(environment_path.read_bytes(), original)

    def test_invalid_configuration_is_preserved(self):
        path = self.root / ".local/environment.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"{invalid")
        with self.assertRaises(setup.reader.EnvironmentConfigError):
            setup.configure(self.root, str(self.vault), replace=True)
        self.assertEqual(path.read_bytes(), b"{invalid")

    def test_cli_returns_json_failure(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = setup.main(
                ["--connector-vault", str(self.base / "missing")],
                self.root,
            )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main()
