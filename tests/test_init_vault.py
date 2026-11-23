"""Verify the Brain v1 skeleton, templates and user-file protection."""

import importlib.util
from datetime import date
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('init_vault', ROOT / 'scripts/init_vault.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InitializationTests(unittest.TestCase):
    def test_brain_skeleton_templates_and_repeat_preserve_user_edits(self):
        sources = list((ROOT / 'templates/vault').glob('*.md'))
        brain_sources = [
            path for path in (ROOT / 'templates/brain').rglob('*')
            if path.is_file() and path.suffix in {'.md', '.base'}
        ]
        self.assertEqual(len(sources), 9)
        self.assertEqual(len(brain_sources), 16)
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            first = module.initialize(vault)
            self.assertTrue(first['created'])
            self.assertIn(str(vault / '03 wiki/综合'), first['created_dirs'])
            self.assertFalse(first['preserved'])
            for source in sources:
                self.assertEqual(source.read_bytes(), (vault / '04 模板' / source.name).read_bytes())
                header = source.read_text(encoding='utf-8').split('---', 2)[1]
                self.assertIn('type: "template"', header)
                self.assertIn('status: "active"', header)
                expected_updated = '2026-11-23' if source.name == '任务总结.md' else '2026-11-22'
                self.assertIn(f'updated: "{expected_updated}"', header)
            for source in brain_sources:
                relative = source.relative_to(ROOT / 'templates/brain')
                self.assertEqual(source.read_bytes(), (vault / relative).read_bytes())
            for relative in [
                '01 草稿/历史收件箱',
                '01 草稿/迁移待分类',
                '02 工作记录/任务总结/JARVIS',
                '02 工作记录/任务总结/历史项目',
                '02 工作记录/Brain运行日志',
                '03 wiki/主题/AI-Agent',
                '03 wiki/主题/Loop-Engineering',
                '03 wiki/主题/Obsidian使用技巧',
                '03 wiki/参考资料/AI-Agent',
                '03 wiki/参考资料/Loop-Engineering',
                '03 wiki/参考资料/Obsidian使用技巧',
                '03 wiki/综合',
                '03 wiki/索引',
                '03 wiki/视图',
                '04 模板/历史模板',
                '05 规则/JARVIS',
                '05 规则/决策',
                f'02 工作记录/日报/{date.today().year}',
                f'02 工作记录/周报/{date.today().year}',
            ]:
                self.assertTrue((vault / relative).is_dir(), relative)
            for base_name in ['待复核.base', '需要复审.base', '主题地图.base', '证据缺口.base']:
                self.assertTrue((vault / '03 wiki/视图' / base_name).is_file())

            edited = vault / '04 模板' / sources[0].name
            edited.write_bytes(b'user content')
            readme = vault / 'README.md'
            readme.write_text('# user readme\n', encoding='utf-8')
            second = module.initialize(vault)
            self.assertEqual(second['created'], [])
            self.assertEqual(second['created_dirs'], [])
            self.assertEqual(edited.read_bytes(), b'user content')
            self.assertEqual(readme.read_text(encoding='utf-8'), '# user readme\n')
            self.assertGreaterEqual(len(second['preserved']), 2)
