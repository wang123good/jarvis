import sys
from pathlib import Path
from datetime import datetime, timezone
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import brain_note


class BrainNoteTests(unittest.TestCase):
    def test_business_note_does_not_inherit_template_authority_or_lineage(self):
        template = '---\ntype: template\nstatus: active\nsource_hash: old\nmigration_task: old\n---\n# {{title}}\n日期 {{date}}\n'
        text = brain_note.render_note(template, '待复核结论', 'topic', now=datetime(2026, 11, 23, tzinfo=timezone.utc))
        self.assertIn('type: "topic"', text)
        self.assertIn('status: "review"', text)
        self.assertIn('source_gap:', text)
        self.assertNotIn('source_hash:', text)
        self.assertNotIn('migration_task:', text)
        self.assertNotIn('{{', text)

    def test_preview_protects_existing_notes_and_rejects_outside_business_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = Path(folder)
            (vault / '04 模板').mkdir()
            (vault / '04 模板/wiki主题.md').write_text('# {{title}}', encoding='utf-8')
            environment = {'vault_root': str(vault)}
            value = brain_note.proposal(environment, 'wiki主题', '新笔记', '03 wiki/主题/新笔记.md')
            self.assertFalse(Path(value['target']).exists())
            for target in ['../outside.md', '04 模板/override.md', '99 附件/original.md']:
                with self.assertRaises(ValueError):
                    brain_note.proposal(environment, 'wiki主题', 'test', target)
            target = vault / '03 wiki/主题/新笔记.md'
            target.parent.mkdir(parents=True)
            target.write_text('human edit', encoding='utf-8')
            with self.assertRaises(ValueError):
                brain_note.proposal(environment, 'wiki主题', '新笔记', '03 wiki/主题/新笔记.md')
            self.assertEqual(target.read_text(encoding='utf-8'), 'human edit')


if __name__ == '__main__':
    unittest.main()
