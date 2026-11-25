"""Behavioral boundaries for the local expression adapter; isolated profiles."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import persona
import setup_environment
import resolve_environment


def preference(statement, identifier='p1', date='2026-11-20', **changes):
    item = dict(id=identifier, statement=statement, scope='JARVIS', source='test user message',
                recorded_at=date, approved_at=date, status='approved')
    item.update(changes)
    return item


class PersonaTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(ROOT / 'config/personas', self.root / 'config/personas')
        self.save('.local/environment.json', {'version': 1, 'persona': {'enabled': True}})
        self.profile([])

    def save(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def profile(self, items, **changes):
        document = dict(schema_version='1.0', nickname='Test', preferences=items,
                        candidates=[], enabled=True, collect_candidates=True)
        document.update(changes)
        self.save('up.json', document)

    def run_policy(self, **kwargs):
        return persona.run(self.root, **kwargs)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def test_disabled_does_not_load_profile_module_or_state_or_write(self):
        self.run_policy(persist=True)
        self.save('.local/environment.json', {'version': 1, 'persona': {'enabled': False}})
        before = self.snapshot()
        with patch.object(persona, 'load_modules', side_effect=AssertionError('loaded modules')), \
                patch.object(persona, 'preferences', side_effect=AssertionError('read profile')), \
                patch.object(persona, 'load_state', side_effect=AssertionError('read state')):
            result = self.run_policy(persist=True)
        self.assertFalse(result['enabled'])
        self.assertEqual(before, self.snapshot())

    def test_legacy_missing_invalid_config_are_closed_and_preserved(self):
        path = self.root / '.local/environment.json'
        for value in ({'version': 1}, {'version': 1, 'persona': {'enabled': 'true'}},
                      {'version': 1, 'persona': {'enabled': True, 'command': 'run'}},
                      [], {'version': 2, 'persona': {'enabled': True}}):
            with self.subTest(value=value):
                self.save('.local/environment.json', value)
                before = self.snapshot()
                self.assertFalse(self.run_policy(persist=True)['enabled'])
                self.assertEqual(before, self.snapshot())
        path.write_text('{invalid', encoding='utf-8')
        self.assertFalse(self.run_policy(persist=True)['enabled'])
        self.assertEqual(path.read_text(encoding='utf-8'), '{invalid')
        path.unlink()
        self.assertFalse(self.run_policy(persist=True)['enabled'])
        self.assertFalse(path.exists())

    def test_six_real_modules_are_valid_and_replaceable(self):
        modules, diagnostics = persona.load_modules(self.root)
        self.assertEqual(len(modules), 6)
        self.assertEqual(diagnostics, [])
        changed = modules['witty']
        changed['version'] = '1.1.0'
        changed['dimensions']['humor'] = .75
        changed['dimensions']['guidance'] = .7
        self.save('config/personas/witty.json', changed)
        self.profile([preference('适度幽默')])
        result = self.run_policy()
        self.assertEqual(result['module_id'], 'witty')
        self.assertEqual(result['module_version'], '1.1.0')
        self.assertEqual(result['behavior']['dimensions']['guidance'], .7)

    def test_bad_modules_fallback_without_executing_arbitrary_fields(self):
        for mutate in (lambda x: x.update(command='write profile'),
                       lambda x: x.update(id='unknown'),
                       lambda x: x.update(version='unstable'),
                       lambda x: x['dimensions'].update(humor=2),
                       lambda x: x['dimensions'].update(humor=True),
                       lambda x: x['dimensions'].update(humor=float('nan')),
                       lambda x: x.update(name='OtherIdentity'),
                       lambda x: x['dimensions'].pop('guidance')):
            module = persona.builtin('steady')
            mutate(module)
            self.save('config/personas/steady.json', module)
            modules, diagnostics = persona.load_modules(self.root)
            self.assertEqual(modules['steady'], persona.builtin('steady'))
            self.assertEqual(diagnostics[0]['module'], 'steady')
        (self.root / 'config/personas/steady.json').unlink()
        self.assertTrue(persona.load_modules(self.root)[1])

    def test_automatic_matching_all_six_without_a_questionnaire(self):
        for statement, expected in [('语气沉稳', 'steady'), ('适度幽默', 'witty'),
                                    ('温暖一点', 'warm'), ('挑战我的假设', 'candid'),
                                    ('探索式提问', 'curious'), ('热情主动，多些引导', 'enthusiastic')]:
            with self.subTest(statement=statement):
                self.profile([preference(statement)])
                result = self.run_policy()
                self.assertEqual(result['module_id'], expected)
                self.assertTrue(result['reasons'])
                self.assertEqual(result['reasons'][0]['preference_ids'], ['p1'])

    def test_candidates_other_projects_paused_and_revoked_do_not_apply(self):
        self.profile([preference('热情主动', 'paused', status='paused'),
                      preference('热情主动', 'revoked', status='revoked'),
                      preference('热情主动', 'other', scope='OTHER')],
                     candidates=[preference('热情主动', 'candidate', status='candidate')])
        result = self.run_policy()
        self.assertEqual(result['module_id'], 'steady')
        self.assertFalse(result['reasons'])

    def test_demographics_occupation_nickname_and_transient_emotion_not_matched(self):
        self.profile([preference('我是工程师，今天很难过，喜欢蓝色')], nickname='热情主动')
        self.assertEqual(self.run_policy()['module_id'], 'steady')

    def test_unsupported_wording_and_negated_positive_phrase_not_inferred(self):
        for text in ('幽默', '不要热情主动', '不喜欢适度幽默', '希望不要多些引导'):
            self.assertFalse(persona.matches(text), text)
        self.assertEqual(persona.matches('不要幽默')['humor'], {0})

    def test_same_date_conflicts_default_affected_dimension(self):
        self.profile([preference('适度幽默', 'a'), preference('不要幽默', 'b')])
        result = self.run_policy()
        self.assertEqual(result['conflicts'], ['humor'])
        self.assertEqual(result['adaptation']['dimensions']['humor'], .1)
        self.assertEqual(result['module_id'], 'steady')

    def test_newer_approved_correction_wins_immediately(self):
        self.profile([preference('热情主动，多些引导')])
        self.assertEqual(self.run_policy(persist=True)['module_id'], 'enthusiastic')
        self.profile([preference('热情主动，多些引导'),
                      preference('语气沉稳，不要主动扩展，无需引导', 'new', '2026-11-21')])
        result = self.run_policy(persist=True)
        self.assertEqual(result['adaptation']['dimensions']['energy'], .2)
        self.assertEqual(result['adaptation']['dimensions']['initiative'], .2)
        self.assertEqual(result['module_id'], 'steady')

    def test_explicit_same_day_approved_correction_takes_priority(self):
        self.profile([preference('热情主动')])
        self.run_policy(persist=True)
        self.profile([preference('语气沉稳')])
        result = self.run_policy(persist=True, confirmed_correction=True)
        self.assertEqual(result['module_id'], 'steady')
        self.assertEqual(result['behavior']['dimensions']['energy'], .2)
        self.profile([], candidates=[preference('热情主动', status='candidate')])
        self.assertEqual(self.run_policy(confirmed_correction=True)['module_id'], 'steady')

    def test_new_correction_not_hidden_by_five_old_frequent_preferences(self):
        items = [preference('热情主动', 'old' + str(i), legacy_count=50) for i in range(6)]
        items.append(preference('语气沉稳', 'new', '2026-11-21'))
        self.profile(items)
        result = self.run_policy()
        self.assertEqual(result['adaptation']['dimensions']['energy'], .2)
        self.assertIn('new', result['adaptation']['preference_ids'])
        self.assertLessEqual(len(result['adaptation']['preference_ids']), 5)

    def test_no_information_disabled_invalid_or_missing_profile_resets_cached_style(self):
        self.profile([preference('热情主动')])
        self.run_policy(persist=True)
        for changes in ({'enabled': False}, {'nickname': ''}, {}):
            self.profile([], **changes)
            result = self.run_policy(persist=True)
            self.assertEqual(result['module_id'], 'steady')
        (self.root / 'up.json').write_text('{bad', encoding='utf-8')
        self.assertEqual(self.run_policy(persist=True)['module_id'], 'steady')
        (self.root / 'up.json').unlink()
        self.assertEqual(self.run_policy(persist=True)['profile_status'], 'needs_initialization')

    def test_collection_disabled_applies_approved_but_freezes_state(self):
        self.run_policy(persist=True)
        state = self.root / '.local/persona-state.json'
        before = state.read_bytes()
        self.profile([preference('热情主动')], collect_candidates=False)
        self.assertEqual(self.run_policy(persist=True)['module_id'], 'enthusiastic')
        self.assertEqual(state.read_bytes(), before)

    def test_temporary_override_and_context_never_persist(self):
        self.profile([preference('热情主动，多些引导')])
        self.run_policy(persist=True)
        state = self.root / '.local/persona-state.json'
        before = state.read_bytes()
        result = self.run_policy(persist=True, override={'energy': 0}, context='concerned', quick=True)
        self.assertEqual(result['behavior']['dimensions']['energy'], 0)
        self.assertEqual(result['behavior']['max_questions'], 0)
        self.assertEqual(state.read_bytes(), before)
        self.assertEqual(self.run_policy()['behavior']['context'], '平和')
        self.assertEqual(self.run_policy()['behavior']['dimensions']['energy'], .95)

    def test_all_contexts_and_restraint_have_explicit_limits(self):
        self.profile([preference('热情主动，多些引导，探索式提问，适度幽默')])
        for context in persona.CONTEXTS:
            behavior = self.run_policy(context=context)['behavior']
            self.assertEqual(behavior['context'], persona.CONTEXTS[context])
            self.assertLessEqual(behavior['max_questions'], 2)
            if context in ('focused', 'concerned', 'cautious'):
                self.assertEqual(behavior['dimensions']['humor'], 0)
                self.assertLessEqual(behavior['dimensions']['energy'], .4)
        for kwargs in ({'quick': True}, {'decided': True}):
            result = self.run_policy(**kwargs)['behavior']
            self.assertEqual(result['extra_angles'], 0)
            self.assertEqual(result['max_questions'], 0)

    def test_repeat_input_smooths_to_target_without_building_debounce(self):
        self.profile([preference('语气沉稳')])
        self.run_policy(persist=True)
        self.profile([preference('热情主动')])
        first = self.run_policy(persist=True)
        self.assertEqual(first['adaptation']['pending_count'], 1)
        self.assertEqual(first['module_id'], 'steady')
        previous = first['adaptation']['dimensions']
        for _ in range(4):
            repeat = self.run_policy(persist=True)
            self.assertEqual(repeat['adaptation']['pending_count'], 1)
            self.assertEqual(repeat['module_id'], 'steady')
            for key in persona.DIMENSIONS:
                self.assertLessEqual(abs(repeat['adaptation']['dimensions'][key] - previous[key]), .15001)
            previous = repeat['adaptation']['dimensions']
        self.profile([preference('热情主动，多些引导')])
        second = self.run_policy(persist=True)
        self.assertEqual(second['module_id'], 'enthusiastic')
        self.assertEqual(second['adaptation']['pending_count'], 2)
        for key in persona.DIMENSIONS:
            self.assertLessEqual(abs(second['adaptation']['dimensions'][key] - previous[key]), .15001)

    def test_corrupt_state_and_busy_writer_are_preserved(self):
        state = self.root / '.local/persona-state.json'
        state.write_text('{broken', encoding='utf-8')
        self.assertEqual(self.run_policy(persist=True)['state_write'], 'invalid_state_preserved')
        self.assertEqual(state.read_text(encoding='utf-8'), '{broken')
        state.unlink()
        lock = state.with_suffix('.lock')
        lock.write_text('other writer', encoding='utf-8')
        self.assertEqual(self.run_policy(persist=True)['state_write'], 'busy_preserved')
        self.assertEqual(lock.read_text(encoding='utf-8'), 'other writer')
        self.assertFalse(state.exists())

    def test_concurrent_baseline_change_is_preserved(self):
        path = self.root / '.local/persona-state.json'
        path.write_bytes(b'newer writer')
        self.assertEqual(persona.persist_state(path, {}, b'old'), 'baseline_changed_preserved')
        self.assertEqual(path.read_bytes(), b'newer writer')
        self.assertFalse(path.with_suffix('.lock').exists())

    def test_derived_state_has_no_dialogue_or_profile_content_and_profile_unchanged(self):
        self.profile([preference('热情主动，多些引导')])
        before = (self.root / 'up.json').read_bytes()
        result = self.run_policy(persist=True)
        text = (self.root / '.local/persona-state.json').read_text(encoding='utf-8')
        self.assertNotIn('Test', text)
        self.assertNotIn('热情主动', text)
        self.assertNotIn('statement', text)
        self.assertEqual((self.root / 'up.json').read_bytes(), before)
        self.assertEqual(result['behavior']['identity'], 'JARVIS')
        self.assertTrue(result['behavior']['task_and_permission_rules_unchanged'])

    def test_invalid_override_fails_before_state_write(self):
        for value in ({'permissions': 1}, {'humor': True}, {'energy': 2}):
            with self.assertRaises(ValueError):
                self.run_policy(persist=True, override=value)
        self.assertFalse((self.root / '.local/persona-state.json').exists())

    def test_read_only_default_creates_nothing(self):
        before = self.snapshot()
        self.run_policy()
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
