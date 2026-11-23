import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import brain_health


class LinkResolutionTests(unittest.TestCase):
    def test_frontmatter_reads_multiline_tag_list(self):
        fields, body = brain_health.split_frontmatter(
            '---\ntitle: "旧日报"\ntype: daily-report\ntags:\n'
            '  - "project/jarvis"\n  - "日报"\n---\n# 旧日报\n'
        )
        self.assertEqual(fields['tags'], ['project/jarvis', '日报'])
        self.assertEqual(body, '# 旧日报\n')

    def test_exact_attachment_is_not_ambiguous_due_to_shared_basename(self):
        assets = {'99 附件/a/清单.json': ['99 附件/a/清单.json'],
                  '清单.json': ['99 附件/a/清单.json', '99 附件/b/清单.json']}
        self.assertEqual(brain_health.resolve('note.md', '99 附件/a/清单.json', {}, {}, assets),
                         ('resolved-attachment', '99 附件/a/清单.json'))

    def test_escaped_alias_in_table_resolves_exact_note(self):
        paths = {'03 wiki/索引/主题': ['03 wiki/索引/主题.md']}
        self.assertEqual(brain_health.resolve('note.md', '03 wiki/索引/主题\\|显示名', paths, {}, {}),
                         ('resolved-note', '03 wiki/索引/主题.md'))


if __name__ == '__main__':
    unittest.main()
