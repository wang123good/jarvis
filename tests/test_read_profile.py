import json
from pathlib import Path
import tempfile
import unittest

from scripts.read_profile import load


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
