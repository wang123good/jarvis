"""Verify template discovery and user-file protection after directory migration."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('init_vault', ROOT / 'scripts/init_vault.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class InitializationTests(unittest.TestCase):
    def test_templates_and_repeat_preserve_user_edits(self):
        sources = list((ROOT / 'templates/vault').glob('*.md'))
        self.assertEqual(len(sources), 9)
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            first = module.initialize(vault)
            self.assertTrue(first['created'])
            for source in sources:
                self.assertEqual(source.read_bytes(), (vault / '04 模板' / source.name).read_bytes())
            edited = vault / '04 模板' / sources[0].name
            edited.write_bytes(b'user content')
            second = module.initialize(vault)
            self.assertEqual(second['created'], [])
            self.assertEqual(edited.read_bytes(), b'user content')
