"""Evidence preservation checks; no live knowledge retrieval."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('verifier', Path(__file__).with_name('verify_installation.py'))
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

class PreservationTests(unittest.TestCase):
    def test_existing_run_is_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            run = v.create_run_directory(base, 'existing')
            evidence = run / 'verification.json'
            evidence.write_bytes(b'original evidence')
            with self.assertRaises(FileExistsError):
                v.create_run_directory(base, 'existing')
            self.assertEqual(evidence.read_bytes(), b'original evidence')

    def test_evidence_file_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'result.json'
            v.write_json(p, {'ok': True})
            original = p.read_bytes()
            with self.assertRaises(FileExistsError):
                v.write_json(p, {'ok': False})
            self.assertEqual(p.read_bytes(), original)

    def test_unsafe_ids_rejected_before_directory_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'runs'
            for run_id in ('../escape', '..', 'a/b', 'a\\b', '', 'CON', 'NUL', 'LPT1'):
                with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                    v.create_run_directory(base, run_id)
            self.assertFalse(base.exists())

    def test_separate_runs_preserve_both_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            a = v.create_run_directory(base, 'one')
            b = v.create_run_directory(base, 'two')
            v.write_json(a / 'result.json', {'run': 1})
            v.write_json(b / 'result.json', {'run': 2})
            self.assertNotEqual((a / 'result.json').read_bytes(), (b / 'result.json').read_bytes())

if __name__ == '__main__':
    unittest.main()
