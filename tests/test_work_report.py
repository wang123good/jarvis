"""Exercise report generation from the command line against an isolated vault."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


from environment_isolation import configure_fixture


ROOT = Path(__file__).resolve().parents[1]


class WorkReportTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name) / 'project'
        self.project.mkdir()
        self.vault = Path(temp.name) / 'vault'
        self.summaries = self.vault / '02 工作记录/任务总结/JARVIS'
        self.summaries.mkdir(parents=True)
        for name in ('scripts', 'config', '.codex', '.local'):
            (self.project / name).mkdir()
        for name in ('work_report', 'resolve_environment', 'task_knowledge', 'brain_health', 'experience_registry'):
            shutil.copyfile(ROOT / f'scripts/{name}.py', self.project / f'scripts/{name}.py')
        for name in ('config/defaults.json', '.codex/obsidian-kb.json'):
            shutil.copyfile(ROOT / name, self.project / name)
        configure_fixture(self.project, self.vault)

    def note(self, name, dates, project='JARVIS', status='archived'):
        path = self.summaries / f'{name}.md'
        path.write_text(
            f'---\nproject: {project}\ntype: task-summary\nstatus: {status}\n'
            f'{dates}\n---\n## 结果与验证\n\n- 核对通过。\n',
            encoding='utf-8',
        )
        return path

    def run_report(self, *args, code=0):
        result = subprocess.run(
            [sys.executable, '-X', 'utf8', str(self.project / 'scripts/work_report.py'), *args],
            capture_output=True, encoding='utf-8', check=False,
            env=dict(os.environ, JARVIS_VAULT_ROOT=str(self.vault)),
        )
        self.assertEqual(result.returncode, code, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_daily_period_scope_preview_and_existing_note_protection(self):
        source = self.note('跨天任务', 'date: 2026-11-20\ncompleted_on: 2026-11-21')
        self.note('无业务日期', 'updated: 2026-11-21')
        self.note('其他项目', 'date: 2026-11-21', project='Other')
        self.note('已拒绝', 'date: 2026-11-21', status='rejected')
        options = ('daily', '--date', '2026-11-21')
        preview = self.run_report(*options)
        self.assertEqual(preview['status'], 'preview')
        self.assertEqual(preview['sources'], [source.relative_to(self.vault).as_posix()])
        self.assertEqual(len(preview['undated']), 1)
        report = self.vault / preview['target']
        self.assertFalse(report.exists())
        self.assertIn('核对通过。', preview['markdown'])
        writer = ('--write', preview['baseline'])
        self.assertEqual(self.run_report(*options, '--write', 'outdated-baseline', code=2)['status'], 'error')
        self.assertEqual(self.run_report(*options, '--connector-vault', str(self.project),
                                         *writer, code=2)['status'], 'error')
        connected = ('--connector-vault', str(self.vault))
        self.assertEqual(self.run_report(*options, *writer)['status'], 'created')
        self.assertEqual(report.read_text(encoding='utf-8'), preview['markdown'])
        report.write_text('人工修改', encoding='utf-8')
        self.assertEqual(self.run_report(*options, *connected, *writer)['status'], 'exists')
        self.assertEqual(report.read_text(encoding='utf-8'), '人工修改')

    def test_weekly_spans_iso_year_and_detects_preview_drift(self):
        source = self.note('年末记录', 'date: 2025-12-29')
        self.note('周日记录', 'date: 2026-01-04')
        self.note('下一周', 'date: 2026-01-05')
        daily_options = ('daily', '--date', '2025-12-29')
        daily = self.run_report(*daily_options)
        connected = ('--connector-vault', str(self.vault))
        self.run_report(*daily_options, *connected, '--write', daily['baseline'])
        options = ('weekly', '--date', '2025-12-31')
        weekly = self.run_report(*options)
        self.assertEqual(weekly['target'], '02 工作记录/周报/2026/2026-W01_周报.md')
        self.assertEqual((weekly['start'], weekly['end']), ('2025-12-29', '2026-01-04'))
        self.assertEqual(len(weekly['sources']), 3)
        self.assertIn(daily['target'], weekly['sources'])
        source.write_text(source.read_text(encoding='utf-8') + '\n后续修订。\n', encoding='utf-8')
        self.run_report(*options, *connected, '--write', weekly['baseline'], code=2)
        self.assertFalse((self.vault / weekly['target']).exists())
        updated = self.run_report(*options)
        self.assertEqual(self.run_report(*options, *connected, '--write',
                                         updated['baseline'])['status'], 'created')

    def test_empty_period_does_not_create_output_directory(self):
        result = self.run_report('daily', '--date', '2026-11-22')
        self.assertEqual(result['status'], 'no_records')
        self.assertFalse((self.vault / result['target']).parent.exists())

    def test_filename_date_fallback_is_explicit(self):
        source = self.summaries / '2026-11-21_旧任务总结.md'
        source.write_text(
            '---\nproject: JARVIS\ntype: task-summary\nstatus: archived\n'
            '---\n## 结果与验证\n\n- 兼容旧数据。\n',
            encoding='utf-8',
        )
        preview = self.run_report('daily', '--date', '2026-11-21')
        relative = source.relative_to(self.vault).as_posix()
        self.assertEqual(preview['status'], 'preview')
        self.assertEqual(preview['sources'], [relative])
        self.assertEqual(preview['date_fallbacks'], [relative])
        self.assertIn('日期取自文件名', preview['markdown'])
        self.assertIn('兼容旧数据。', preview['markdown'])

    def test_weekly_finds_legacy_daily_name_by_frontmatter(self):
        source = self.note('周任务', 'date: 2026-11-20')
        daily_folder = self.vault / '02 工作记录/日报/2026'
        daily_folder.mkdir(parents=True)
        legacy = daily_folder / '2026-11-20 日报.md'
        legacy.write_text(
            '---\ntitle: "2026-11-20 日报"\ndate: 2026-11-20\ntype: daily-report\n'
            'status: active\ntags:\n  - "project/jarvis"\n  - "日报"\n---\n# 日报\n',
            encoding='utf-8',
        )
        other = daily_folder / '2026-11-20_其他项目日报.md'
        other.write_text(
            '---\ndate: 2026-11-20\ntype: daily-report\nstatus: active\n'
            'project: Other\n---\n# 其他项目\n',
            encoding='utf-8',
        )
        preview = self.run_report('weekly', '--date', '2026-11-20')
        self.assertEqual(preview['status'], 'preview')
        self.assertIn(source.relative_to(self.vault).as_posix(), preview['sources'])
        self.assertIn(legacy.relative_to(self.vault).as_posix(), preview['sources'])
        self.assertNotIn(other.relative_to(self.vault).as_posix(), preview['sources'])
        self.assertIn(legacy.relative_to(self.vault).with_suffix('').as_posix(), preview['markdown'])


if __name__ == '__main__':
    unittest.main()
