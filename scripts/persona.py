"""Load a bounded JARVIS expression policy from confirmed interaction preferences.

No module code, chat history, psychological inference, or profile writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
from uuid import uuid4

import read_profile
from resolve_environment import PERSONA_NAMES as NAMES, instance_settings, relative_to, validate_persona

ROOT = Path(__file__).resolve().parents[1]
ENGINE = '1.0.0'
STATE_KEYS = {'schema_version', 'engine', 'module_id', 'dimensions', 'input_hash',
              'modules_hash', 'approved_at', 'preference_ids', 'pending', 'pending_count'}
DIMENSIONS = ('direct', 'warmth', 'humor', 'inquiry', 'challenge', 'energy', 'initiative', 'guidance')
VECTORS = {
    'steady': (.8, .8, .1, .3, .4, .2, .5, .65),
    'enthusiastic': (.7, .85, .5, .45, .45, .95, .95, .95),
    'professional': (.95, .35, .05, .15, .6, .3, .2, .25),
    'curious': (.65, .6, .3, .95, .55, .55, .8, .7),
    'bold': (.9, .35, .15, .35, .99, .75, .85, .5),
}
# Response moves survive contextual tone adjustments.
STYLES = {
    'steady': '耐心说明现状，按顺序给步骤，解释先做哪一步及如何确认结果。适量展开。',
    'enthusiastic': '像熟悉的同事一样自然接话，主动给出自己的判断，再给一个马上能试的主意。严肃时收敛熟络和玩笑。',
    'professional': '结论先行，用准确的领域术语交代决定性依据和适用条件。短句优先，证据不足时点名缺项。',
    'curious': '先给结论，再条理清楚地交代核对过程和疑点。认真碎碎念，偶尔顺口分享一个有用的小发现，可展开细节。',
    'bold': '有依据时挑战默认方案，明确押注方向和取舍，提出快速验证办法及停止条件。',
}
CONTEXT_CUES = {
    'calm': '平实表达。',
    'focused': '围绕当前目标，给可执行步骤。',
    'curious': '指出值得探究的未知点。',
    'pleased': '用轻快语气回应已确认的进展。',
    'concerned': '承接用户明确表达的困难，降低下一步负担。',
    'cautious': '优先交代证据边界、风险与停止条件。',
}
CONTEXTS = {'calm': '平和', 'focused': '专注', 'curious': '好奇',
            'pleased': '欣喜', 'concerned': '关切', 'cautious': '审慎'}
# Explicit interaction phrases only. Negative phrases are separate rules, never
# a bare keyword match such as "幽默" or any demographic/occupational label.
RULES = {
    'direct': ((.95, r'直接简洁|开门见山|直说结论|be direct'), (.3, r'委婉表达|委婉一点')),
    'warmth': ((.95, r'温暖一点|温和回应|多些关怀|warm responses'), (.3, r'保持冷静|少些安慰')),
    'humor': ((.9, r'适度幽默|幽默一点|机智一点|use humor'), (.0, r'不要幽默|避免玩笑|严肃表达')),
    'inquiry': ((.95, r'多问探索问题|多提问题|探索式提问|ask exploratory questions'), (.1, r'少提问题|不要追问')),
    'challenge': ((.95, r'挑战我的假设|坦率反驳|指出盲点|challenge my assumptions'), (.2, r'少些挑战|不要争辩')),
    'energy': ((.95, r'热情主动|热情一点|表达有活力|enthusiastic tone'), (.2, r'语气沉稳|低调克制|沉稳表达')),
    'initiative': ((.95, r'热情主动|主动拓展思考|主动补充角度|proactive thinking'), (.2, r'只回答所问|不要主动扩展')),
    'guidance': ((.95, r'提供框架和例子|多些引导|给出框架|guide with examples'), (.2, r'无需引导|不要举例')),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def vector(values):
    return dict(zip(DIMENSIONS, values))


def validate_vector(value):
    if (not isinstance(value, dict) or set(value) != set(DIMENSIONS)
            or any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1
                   for x in value.values())):
        raise ValueError('Expected all eight numeric dimensions in 0..1')
    return dict(value)


def builtin(identifier):
    return {'schema_version': 1, 'id': identifier, 'version': '1.0.0',
            'name': NAMES[identifier], 'dimensions': vector(VECTORS[identifier])}


def validate_module(value, identifier):
    if (not isinstance(value, dict)
            or set(value) != {'schema_version', 'id', 'version', 'name', 'dimensions'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['id'] != identifier or value['name'] != NAMES[identifier]
            or not isinstance(value['version'], str)
            or re.fullmatch(r'\d+\.\d+\.\d+', value['version']) is None):
        raise ValueError('Invalid declarative module interface')
    validate_vector(value['dimensions'])
    return value


def load_modules(root):
    modules, diagnostics = {}, []
    directory = root / 'config/personas'
    for identifier in NAMES:
        path = directory / (identifier + '.json')
        try:
            if not path.resolve().is_relative_to(directory.resolve()) or directory.is_symlink():
                raise ValueError('Module path escapes persona directory')
            modules[identifier] = validate_module(read_json(path), identifier)
        except (OSError, ValueError) as exc:
            modules[identifier] = builtin(identifier)
            diagnostics.append({'module': identifier, 'fallback': 'builtin', 'reason': str(exc)})
    return modules, diagnostics


def matches(statement):
    # Avoid interpreting negated positive instructions as a preference. These
    # clauses are deliberately conservative; unsupported wording stays unknown.
    clauses = re.split(r'[，。；;\n,]', statement.lower())
    result = {}
    for dimension, rules in RULES.items():
        values = set()
        for value, pattern in rules:
            for clause in clauses:
                for match in re.finditer(pattern, clause):
                    prefix = clause[:match.start()].rstrip()
                    if re.search(r'(不要|不需要|不喜欢|避免|不希望|不|never|not)\s*$', prefix):
                        continue
                    values.add(value)
        if values:
            result[dimension] = values
    return result


def preferences(root):
    path = root / 'up.json'
    try:
        index = read_profile.load(path, index=True)
        if index['status'] != 'ready':
            return [], index['status'], False
        related = [item['id'] for item in index['preferences'] if matches(item['statement'])]
        # New approved corrections must not be crowded out by high-count old
        # preferences. This validated snapshot also detects profile edits.
        document = read_profile.validate(read_json(path))
        formal = {item['id']: item for item in document['preferences']
                  if item['status'] == 'approved' and item['scope'] == 'JARVIS'}
        ids = sorted(related, key=lambda key: formal[key]['approved_at'], reverse=True)[:5]
        # Read only selected approved records for behavior; no candidate use.
        if not ids:
            return [], 'no_related_preferences', index.get('collect_candidates', True)
        selected = read_profile.load(path, selected=ids)['preferences']
        if digest(read_json(path)) != digest(document):
            raise ValueError('Profile changed during matching; retry with current snapshot')
        return [formal[item['id']] for item in selected], 'ready', document.get('collect_candidates', True)
    except (ValueError, OSError, KeyError) as exc:
        return [], 'profile_unavailable: ' + str(exc), False


def match_preferences(items, modules):
    target = dict(modules['steady']['dimensions'])
    reasons, conflicts = [], []
    for dimension in DIMENSIONS:
        records = [(item, matches(item['statement']).get(dimension)) for item in items]
        records = [(item, values) for item, values in records if values]
        if not records:
            continue
        newest = max(item['approved_at'] for item, _ in records)
        records = [(item, values) for item, values in records if item['approved_at'] == newest]
        values = set().union(*(values for _, values in records))
        reasons.append({'dimension': dimension, 'preference_ids': [i['id'] for i, _ in records],
                        'evidence': [digest(i) for i, _ in records], 'rule': 'explicit-interaction-phrase-v1'})
        if len(values) != 1:
            conflicts.append(dimension)
        else:
            target[dimension] = values.pop()
    relevant = [reason['dimension'] for reason in reasons if reason['dimension'] not in conflicts]
    if not relevant:
        return target, 'steady', reasons, conflicts
    distances = {key: distance(target, item['dimensions'], relevant) for key, item in modules.items()}
    ordered = sorted(distances, key=distances.get)
    winner = ordered[0] if distances[ordered[1]] - distances[ordered[0]] > 1e-9 else 'steady'
    # A module is a real replaceable base, overlaid by the confirmed dimensions.
    # Unmentioned dimensions come from that module, not from the steady default.
    applied = dict(modules[winner]['dimensions'])
    for reason in reasons:
        key = reason['dimension']
        applied[key] = target[key]
    return applied, winner, reasons, conflicts


def distance(first, second, keys=DIMENSIONS):
    return sum(abs(first[key] - second[key]) for key in keys) / len(keys)


def load_state(path):
    if not path.exists():
        return None, None, None
    before = path.read_bytes()
    try:
        state = json.loads(before.decode('utf-8-sig'))
        if (not isinstance(state, dict) or set(state) != STATE_KEYS
                or type(state.get('schema_version')) is not int or state.get('schema_version') != 1
                or state.get('module_id') not in (*NAMES, 'witty', 'warm', 'candid')
                or state.get('pending') not in (*NAMES, 'witty', 'warm', 'candid', None)
                or type(state.get('pending_count')) is not int or not 0 <= state['pending_count'] <= 2
                or any(not isinstance(state.get(k), str) for k in
                       ('engine', 'input_hash', 'modules_hash', 'approved_at'))):
            raise ValueError('Invalid adaptation state')
        if (any(re.fullmatch(r'[0-9a-f]{64}', state[key]) is None for key in ('input_hash', 'modules_hash'))
                or not isinstance(state['preference_ids'], list)
                or any(not isinstance(item, str) for item in state['preference_ids'])
                or len(state['preference_ids']) > 5):
            raise ValueError('Invalid adaptation evidence')
        if state['approved_at']:
            from datetime import date
            date.fromisoformat(state['approved_at'])
        validate_vector(state.get('dimensions'))
        return state, before, None
    except (ValueError, UnicodeError) as exc:
        return None, before, 'state_unavailable: ' + str(exc)


def adapt(target, winner, items, modules, previous):
    fingerprint = digest(items)
    modules_hash = digest(modules)
    newest = max((item['approved_at'] for item in items), default='')
    valid_previous = (previous and previous['engine'] == ENGINE
                      and previous['modules_hash'] == modules_hash
                      and previous['module_id'] in modules)
    chosen, applied, pending, count = winner, dict(target), None, 0
    if items and valid_previous and newest <= previous['approved_at']:
        applied = {key: round(previous['dimensions'][key] + max(-.15, min(.15,
                   target[key] - previous['dimensions'][key])), 4) for key in DIMENSIONS}
        if fingerprint == previous['input_hash']:
            # Continue parameter smoothing, but repeated reads are never new
            # evidence for a module switch. Once converged, writes are idempotent.
            return dict(previous, dimensions=applied)
        current = previous['module_id']
        relevant = set().union(*(set(matches(item['statement'])) for item in items)) or set(DIMENSIONS)
        if winner != current and distance(target, modules[current]['dimensions'], relevant) - distance(target, modules[winner]['dimensions'], relevant) >= .08:
            pending = winner
            count = min(2, previous['pending_count'] + 1) if previous['pending'] == winner else 1
            chosen = winner if count == 2 else current
        else:
            chosen = current
    return {'schema_version': 1, 'engine': ENGINE, 'module_id': chosen,
            'dimensions': applied, 'input_hash': fingerprint, 'modules_hash': modules_hash,
            'approved_at': newest, 'preference_ids': [item['id'] for item in items],
            'pending': pending, 'pending_count': count}


def persist_state(path, state, before):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix('.lock')
    try:
        stream = lock.open('x', encoding='utf-8')
    except FileExistsError:
        return 'busy_preserved'
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with stream:
            stream.write(str(os.getpid()))
        current = path.read_bytes() if path.exists() else None
        if current != before:
            return 'baseline_changed_preserved'
        encoded = (json.dumps(state, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        if current == encoded:
            return 'unchanged'
        with temporary.open('xb') as output:
            output.write(encoded)
        # Recheck after preparing the file, for editors that don't honor our lock.
        if (path.read_bytes() if path.exists() else None) != before:
            return 'baseline_changed_preserved'
        os.replace(temporary, path)
        return 'written'
    finally:
        if temporary.exists():
            temporary.unlink()
        lock.unlink()


def compose(dimensions, context, quick, decided, override):
    values = dict(dimensions)
    if context == 'curious':
        values['inquiry'] = min(1, values['inquiry'] + .1)
    elif context == 'pleased':
        values['energy'] = min(1, values['energy'] + .1)
    elif context == 'concerned':
        values['warmth'] = max(.7, values['warmth'])
    elif context in ('focused', 'cautious'):
        values['direct'] = max(.8, values['direct'])
    if override:
        if (not isinstance(override, dict) or not set(override) <= set(DIMENSIONS)
                or any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1
                       for x in override.values())):
            raise ValueError('Invalid temporary dimension override')
        values.update(override)
    restrained = quick or decided or context in ('focused', 'concerned', 'cautious')
    if restrained:
        for key, cap in {'humor': 0, 'energy': .4, 'inquiry': .2}.items():
            values[key] = min(values[key], cap)
    return {'context': CONTEXTS[context], 'dimensions': values,
            'max_questions': 0 if quick or decided else (1 if restrained else 2),
            'extra_angles': 0 if quick or decided else (1 if values['initiative'] >= .6 else 0),
            'framework_or_example': not quick and not decided and values['guidance'] >= .6,
            'expression_only': True, 'identity': 'JARVIS',
            'task_and_permission_rules_unchanged': True}


def run(root=ROOT, *, persist=False, context='calm', quick=False, decided=False, override=None,
        confirmed_correction=False):
    root = Path(root).resolve()
    # This gate must precede every profile/module/state access, including locks.
    try:
        environment = read_json(relative_to(root, '.local/environment.json', 'environment file'))
        if not isinstance(environment, dict) or environment.get('version') not in (1, 2):
            raise ValueError('Unsupported local environment')
        if environment['version'] == 2:
            instance_settings(root)
        policy = validate_persona(environment.get('persona'))
    except (ValueError, OSError) as exc:
        return {'enabled': False, 'reason': 'configuration_unavailable: ' + str(exc), 'state_write': 'skipped'}
    if not policy['enabled']:
        return {'enabled': False, 'reason': 'disabled_or_legacy', 'state_write': 'skipped'}
    if context not in CONTEXTS:
        raise ValueError('Unknown context')
    modules, diagnostics = load_modules(root)
    items, profile_status, collect = preferences(root)
    selection = policy.get('module', 'auto')
    if selection == 'auto':
        target, winner, reasons, conflicts = match_preferences(items, modules)
    else:
        target, winner = modules[selection]['dimensions'], selection
        items, reasons, conflicts = [], [], []
    state_path = relative_to(root, '.local/persona-state.json', 'persona state')
    try:
        previous, before, state_error = load_state(state_path)
    except OSError as exc:
        previous, before, state_error = None, None, str(exc)
    # Never let a cached adaptation override a stopped/missing/invalid profile.
    if (confirmed_correction and items and previous
            and digest(items) != previous['input_hash']):
        previous = None
    state = adapt(target, winner, items, modules, previous if items else None)
    behavior = compose(state['dimensions'], context, quick, decided, override)
    if quick or decided:
        behavior['style'] = '用最短篇幅回答所问，或落实已决定事项。'
    else:
        behavior['style'] = STYLES[state['module_id']]
    behavior['context_cue'] = CONTEXT_CUES[context]
    write = 'read_only'
    if persist:
        if state_error:
            write = 'invalid_state_preserved'
        elif not collect:
            write = 'collection_disabled_or_profile_unavailable'
        else:
            try:
                write = persist_state(state_path, state, before)
            except OSError as exc:
                write = 'write_failed_preserved: ' + str(exc)
    return {'enabled': True, 'engine': ENGINE, 'module_id': state['module_id'],
            'module_version': modules[state['module_id']]['version'],
            'name': NAMES[state['module_id']], 'selection': selection, 'profile_status': profile_status,
            'reasons': reasons, 'conflicts': conflicts, 'diagnostics': diagnostics,
            'state_error': state_error, 'state_write': write,
            'adaptation': state, 'behavior': behavior}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--persist', action='store_true')
    parser.add_argument('--context', choices=CONTEXTS, default='calm')
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--decided', action='store_true')
    parser.add_argument('--confirmed-correction', action='store_true',
                        help='After an explicit long-term correction has been approved in up.json')
    parser.add_argument('--override', help='Temporary numeric dimension JSON; never persisted')
    args = parser.parse_args(argv)
    try:
        result = run(persist=args.persist, context=args.context, quick=args.quick,
                     decided=args.decided, override=json.loads(args.override) if args.override else None,
                     confirmed_correction=args.confirmed_correction)
    except (ValueError, OSError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
