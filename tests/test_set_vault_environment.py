"""Migration must bind approval to one checkout, target, and baseline."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from setup_environment import SetupError, configure, preview_migration


class MigrationTests(unittest.TestCase):
    def test_confirmation_rejects_different_checkout_and_changed_baseline(self):
        with TemporaryDirectory() as directory:
            base = Path(directory)
            vault = base / 'vault'
            vault.mkdir()
            first = base / 'one'
            second = base / 'two'
            preview = preview_migration(first, str(vault))
            with self.assertRaisesRegex(SetupError, 'confirmation'):
                configure(second, str(vault), migration=preview['confirmation'])
            settings = first / '.local/environment.json'
            settings.parent.mkdir(parents=True)
            settings.write_text('{"version":1}', encoding='utf-8')
            with self.assertRaisesRegex(SetupError, 'confirmation'):
                configure(first, str(vault), migration=preview['confirmation'])
            self.assertEqual(settings.read_text(encoding='utf-8'), '{"version":1}')
