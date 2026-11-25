import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import brain_router


class RouterConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.vault = Path(self.temporary.name)
        self.config = json.loads(
            (ROOT / '.codex/obsidian-kb.json').read_text(encoding='utf-8')
        )

    def test_repository_registry_is_relative_and_policy_is_read_only(self):
        brain_router.validate_registry(self.config, self.vault)
        registry = self.config['project_registry']
        policy = self.config['research_policy']
        self.assertEqual(
            registry['current_project_id'], self.config['project']['id']
        )
        for project in registry['projects']:
            self.assertFalse(Path(project['root']).is_absolute(), project)
            self.assertNotIn('..', project['root'].replace('\\', '/').split('/'))
        self.assertEqual(policy['default_mode'], 'project')
        self.assertFalse(policy['write_allowed'])
        self.assertFalse(policy['allow_inbox_by_default'])
        self.assertFalse(policy['allow_archive_by_default'])

    def test_rejects_absolute_project_root(self):
        self.config['project_registry']['projects'][1]['root'] = str(
            self.vault / 'elsewhere'
        )
        with self.assertRaisesRegex(
            brain_router.RouterConfigError, 'relative to the vault'
        ):
            brain_router.validate_registry(self.config, self.vault)

    def test_rejects_unknown_shared_layer(self):
        self.config['research_policy']['shared_layers'].append('unknown')
        with self.assertRaisesRegex(
            brain_router.RouterConfigError, 'configured layers'
        ):
            brain_router.validate_registry(self.config, self.vault)

    def test_rejects_current_project_mismatch(self):
        self.config['project_registry']['current_project_id'] = 'another-project'
        with self.assertRaisesRegex(
            brain_router.RouterConfigError, 'must match project.id'
        ):
            brain_router.validate_registry(self.config, self.vault)

    def test_rejects_non_read_only_policy(self):
        self.config['research_policy']['write_allowed'] = True
        with self.assertRaisesRegex(
            brain_router.RouterConfigError, 'write_allowed'
        ):
            brain_router.validate_registry(self.config, self.vault)

    def test_scope_health_reports_missing_shared_scope(self):
        current = self.config['project_registry']['projects'][0]
        self.config['project_registry']['projects'] = [current]
        root = self.vault / current['root']
        root.mkdir(parents=True)
        (root / '00_项目索引.md').write_text('---\nstatus: active\n---\n', encoding='utf-8')
        health = brain_router.scope_health(self.config, self.vault)
        self.assertFalse(health['ok'])
        self.assertEqual(health['project_roots_missing'], [])
        self.assertEqual(health['project_indexes_missing'], [])
        self.assertEqual(
            health['shared_scopes_missing'],
            self.config['layers']['domain'] + self.config['layers']['resource'],
        )

    def test_scope_health_reports_missing_root_and_index(self):
        current = self.config['project_registry']['projects'][0]
        self.config['project_registry']['projects'] = [current]
        for layer in self.config['research_policy']['shared_layers']:
            for folder in self.config['layers'][layer]:
                (self.vault / folder).mkdir(parents=True)
        root = self.vault / current['root']
        root.mkdir(parents=True)
        health = brain_router.scope_health(self.config, self.vault)
        self.assertTrue(health['ok'])
        self.assertEqual(
            health['project_indexes_missing'],
            [f"{current['root']}/00_项目索引.md"],
        )

        current['root'] = '02 工作记录/任务总结/Missing'
        self.config['project']['root'] = current['root']
        health = brain_router.scope_health(self.config, self.vault)
        self.assertFalse(health['ok'])
        self.assertEqual(health['project_roots_missing'], [current['root']])


class RouterProjectModeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.vault = Path(self.temporary.name)
        self.config = json.loads(
            (ROOT / '.codex/obsidian-kb.json').read_text(encoding='utf-8')
        )
        current = self.config['project_registry']['projects'][0]
        other = {
            'id': 'other-project',
            'name': 'Other Project',
            'root': '02 工作记录/任务总结/Other',
            'aliases': [],
            'researchable': True,
        }
        self.config['project_registry']['projects'] = [current, other]

    def write_note(
        self,
        relative,
        status='active',
        note_type='task-summary',
        body='needle',
        title=None,
    ):
        path = self.vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '---\n'
            f'title: "{title or path.stem}"\n'
            f'type: "{note_type}"\n'
            f'status: "{status}"\n'
            'tags:\n'
            '  - jarvis\n'
            '---\n'
            f'# {path.stem}\n\n{body}\n',
            encoding='utf-8',
        )

    def write_fixture(self):
        self.write_note(
            '02 工作记录/任务总结/JARVIS/00_项目索引.md', note_type='index'
        )
        self.write_note('02 工作记录/任务总结/JARVIS/current.md')
        self.write_note('02 工作记录/任务总结/JARVIS/draft.md', status='draft')
        self.write_note(
            '02 工作记录/任务总结/JARVIS/archived.md', status='archived'
        )
        self.write_note(
            '02 工作记录/任务总结/JARVIS/superseded.md', status='superseded'
        )
        self.write_note('02 工作记录/任务总结/Other/secret.md')
        self.write_note('01 草稿/JARVIS/inbox.md')
        self.write_note('06 归档/JARVIS/archive.md')
        self.write_note('05 规则/JARVIS/rule.md', note_type='rule')
        self.write_note('05 规则/Other/other-rule.md', note_type='rule')
        self.write_note('03 wiki/主题/shared-topic.md', note_type='topic')
        self.write_note('03 wiki/参考资料/shared-reference.md', note_type='reference')

    def test_project_mode_is_hard_scoped_and_excludes_noncurrent_content(self):
        self.write_fixture()
        pack = brain_router.build_project_context(
            self.config, self.vault, 'needle', limit=20
        )
        paths = [item['path'] for item in pack['results']]
        self.assertIn('02 工作记录/任务总结/JARVIS/current.md', paths)
        self.assertIn('05 规则/JARVIS/rule.md', paths)
        self.assertIn('03 wiki/主题/shared-topic.md', paths)
        self.assertIn('03 wiki/参考资料/shared-reference.md', paths)
        self.assertFalse(any(path.startswith('02 工作记录/任务总结/Other/') for path in paths))
        self.assertFalse(any(path.startswith('05 规则/Other/') for path in paths))
        self.assertFalse(any(path.startswith('01 草稿/') for path in paths))
        self.assertFalse(any(path.startswith('06 归档/') for path in paths))
        self.assertFalse(any(path.endswith(('draft.md', 'archived.md', 'superseded.md')) for path in paths))
        self.assertEqual(pack['included_projects'], ['jarvis'])
        self.assertEqual(pack['exclusions']['blocked_projects'], ['other-project'])
        self.assertEqual(pack['exclusions']['blocked_layers'], ['inbox', 'archive'])
        self.assertEqual(pack['mode'], 'project')
        self.assertFalse(pack['write_allowed'])
        self.assertEqual(pack['result_count'], len(pack['results']))

    def test_project_mode_honors_limit(self):
        self.write_fixture()
        pack = brain_router.build_project_context(
            self.config, self.vault, 'needle', limit=1
        )
        self.assertEqual(pack['result_count'], 1)
        self.assertEqual(pack['result_count'], len(pack['results']))
        self.assertEqual(pack['requested_limit'], 1)

    def test_project_mode_reports_empty_scope_and_no_match(self):
        pack = brain_router.build_project_context(
            self.config, self.vault, 'not-present', limit=3
        )
        self.assertEqual(pack['results'], [])
        self.assertEqual(pack['result_count'], 0)
        self.assertTrue(pack['evidence_gaps'])
        self.assertTrue(
            any('No eligible' in item for item in pack['evidence_gaps'])
        )


class RouterResearchModeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.vault = Path(self.temporary.name)
        self.config = json.loads(
            (ROOT / '.codex/obsidian-kb.json').read_text(encoding='utf-8')
        )
        current = self.config['project_registry']['projects'][0]
        self.config['project_registry']['projects'] = [
            current,
            {
                'id': 'project-a',
                'name': 'Project A',
                'root': '02 工作记录/任务总结/Project A',
                'aliases': [],
                'researchable': True,
            },
            {
                'id': 'project-b',
                'name': 'Project B',
                'root': '02 工作记录/任务总结/Project B',
                'aliases': [],
                'researchable': True,
            },
        ]

    def write_note(
        self,
        relative,
        status='active',
        note_type='task-summary',
        body='needle',
        title=None,
    ):
        path = self.vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '---\n'
            f'title: "{title or path.stem}"\n'
            f'type: "{note_type}"\n'
            f'status: "{status}"\n'
            '---\n'
            f'# {title or path.stem}\n\n{body}\n',
            encoding='utf-8',
        )

    def test_auto_candidates_return_multiple_projects_with_sources(self):
        self.write_note('02 工作记录/任务总结/Project A/a.md')
        self.write_note('02 工作记录/任务总结/Project B/b.md')
        pack = brain_router.build_research_context(
            self.config, self.vault, 'needle', limit=5
        )
        self.assertEqual(pack['project_selection'], 'auto_candidates')
        self.assertEqual(pack['requested_projects'], ['project-a', 'project-b'])
        self.assertIn('project-a', pack['included_projects'])
        self.assertIn('project-b', pack['included_projects'])
        self.assertGreaterEqual(len(pack['included_projects']), 2)
        self.assertTrue(
            all(item['source_project'] != 'shared' for item in pack['results'])
        )
        self.assertFalse(pack['write_allowed'])
        self.assertLessEqual(pack['result_count'], 5)

    def test_noncurrent_content_requires_explicit_flags(self):
        self.write_note('02 工作记录/任务总结/Project A/current.md')
        self.write_note(
            '02 工作记录/任务总结/Project A/draft.md', status='draft'
        )
        self.write_note(
            '02 工作记录/任务总结/Project A/archived.md', status='archived'
        )
        self.write_note(
            '02 工作记录/任务总结/Project A/superseded.md',
            status='superseded',
        )
        self.write_note(
            '02 工作记录/任务总结/Project A/rejected.md', status='rejected'
        )
        default = brain_router.build_research_context(
            self.config,
            self.vault,
            'needle',
            projects='project-a',
            limit=10,
        )
        self.assertEqual(
            [item['path'] for item in default['results']],
            ['02 工作记录/任务总结/Project A/current.md'],
        )

        explicit = brain_router.build_research_context(
            self.config,
            self.vault,
            'needle',
            projects='project-a',
            limit=10,
            include_archived=True,
            include_superseded=True,
            include_drafts=True,
        )
        by_name = {
            Path(item['path']).name: item for item in explicit['results']
        }
        self.assertEqual(
            set(by_name), {'current.md', 'draft.md', 'archived.md', 'superseded.md'}
        )
        for name in ('draft.md', 'archived.md', 'superseded.md'):
            self.assertFalse(by_name[name]['current'])
            self.assertEqual(by_name[name]['status_warning'], 'non_current')

    def test_conflicts_are_reported_without_merging(self):
        self.write_note(
            '02 工作记录/任务总结/Project A/deployment.md',
            title='Deployment Rule',
        )
        self.write_note(
            '02 工作记录/任务总结/Project B/deployment.md',
            title='Deployment Rule',
        )
        pack = brain_router.build_research_context(
            self.config, self.vault, 'needle', limit=5
        )
        deployment = [
            item for item in pack['results'] if item['title'] == 'Deployment Rule'
        ]
        self.assertEqual(len(deployment), 2)
        self.assertEqual(len(pack['conflicts']), 1)
        self.assertEqual(pack['conflicts'][0]['resolution'], 'not_merged')
        self.assertEqual(
            pack['conflicts'][0]['source_projects'],
            ['project-a', 'project-b'],
        )

    def test_shared_topic_link_expands_only_into_allowed_scope(self):
        self.write_note(
            '02 工作记录/任务总结/Project A/project-note.md',
            title='Project Note',
            body='Project-only evidence',
        )
        self.write_note(
            '03 wiki/主题/linked-topic.md',
            title='Linked Topic',
            note_type='topic',
            body='needle [[Project Note]]',
        )
        pack = brain_router.build_research_context(
            self.config,
            self.vault,
            'needle',
            projects='project-a',
            limit=3,
        )
        linked = [
            item
            for item in pack['results']
            if item['selection_reason'] == 'linked_cross_scope_evidence'
        ]
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]['source_project'], 'project-a')
        self.assertEqual(linked[0]['via'], '03 wiki/主题/linked-topic.md')
        self.assertNotIn('02 工作记录/任务总结/Project B/', str(pack['results']))

    def test_research_limit_is_strict(self):
        self.write_note('02 工作记录/任务总结/Project A/a.md')
        self.write_note('02 工作记录/任务总结/Project B/b.md')
        self.write_note(
            '03 wiki/主题/shared-topic.md',
            title='Shared Topic',
            note_type='topic',
        )
        pack = brain_router.build_research_context(
            self.config, self.vault, 'needle', limit=2
        )
        self.assertEqual(pack['result_count'], 2)
        self.assertEqual(len(pack['results']), 2)
        self.assertEqual(
            {item['source_project'] for item in pack['results']},
            {'project-a', 'project-b'},
        )

    def test_unknown_research_project_is_rejected(self):
        with self.assertRaisesRegex(
            brain_router.RouterConfigError, 'Unknown or non-researchable'
        ):
            brain_router.build_research_context(
                self.config,
                self.vault,
                'needle',
                projects='missing-project',
            )


if __name__ == '__main__':
    unittest.main()
