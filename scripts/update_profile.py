"""Apply a scoped profile action supplied by the JARVIS conversation."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import tempfile

if __package__:
    from .read_profile import MAX_DIMENSIONS, ROOT, evidence_count, validate
else:
    from read_profile import MAX_DIMENSIONS, ROOT, evidence_count, validate


def proposals(document):
    if not document.get('enabled', True) or not document.get('collect_candidates', True):
        return []
    formal = document['preferences']
    ranked = sorted(formal, key=evidence_count, reverse=True)
    last = ranked[-1] if len(ranked) == MAX_DIMENSIONS else None
    seen = document.get('review_receipts', {})
    result = []
    for item in sorted(document['candidates'], key=evidence_count, reverse=True):
        if item['scope'] != 'JARVIS':
            continue
        count = evidence_count(item)
        if last and 10 * count <= 11 * evidence_count(last):
            continue
        target = last['id'] if last else None
        previous = seen.get(item['id'])
        if previous and previous['target'] == target:
            if previous['decision'] == 'shown':
                continue
            if previous['decision'] in ('keep', 'defer') and count < previous['count'] + 2:
                continue
        result.append({
            'id': item['id'], 'statement': item['statement'], 'source': item['source'],
            'count': count, 'target': target,
            'target_statement': last['statement'] if last else None,
            'target_count': evidence_count(last) if last else None,
        })
    return result


def add_evidence(item, event):
    if 'evidence' not in item:
        item['legacy_count'] = evidence_count(item)
        item['evidence'] = []
    if event not in item['evidence']:
        item['evidence'].append(event)


def required(action, field):
    value = action.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Required field: ' + field)
    return value.strip()


def apply(document, action):
    operation = required(action, 'action')
    if not document.get('enabled', True) and operation != 'settings':
        raise ValueError('Profile is disabled')
    formal = document['preferences']
    candidates = document['candidates']
    if operation == 'settings':
        for key in ('enabled', 'collect_candidates'):
            if key in action:
                if type(action[key]) is not bool:
                    raise ValueError(key + ' must be boolean')
                document[key] = action[key]
        return

    key = required(action, 'id')
    official = next((item for item in formal if item['id'] == key), None)
    candidate = next((item for item in candidates if item['id'] == key), None)
    if operation == 'observe':
        if not document.get('collect_candidates', True):
            return
        event = required(action, 'event')
        if official:
            if official['scope'] == 'JARVIS' and official['status'] == 'approved':
                add_evidence(official, event)
        elif candidate:
            if candidate['scope'] != 'JARVIS':
                raise ValueError('Evidence scope mismatch')
            add_evidence(candidate, event)
        else:
            candidates.append(dict(id=key, scope='JARVIS', status='candidate',
                                   statement=required(action, 'statement'),
                                   source=required(action, 'source'),
                                   recorded_at=required(action, 'date'), evidence=[event]))
        return

    if operation in ('delete', 'pause', 'resume', 'revoke', 'correct'):
        item = official or candidate
        if not item or item['scope'] != 'JARVIS':
            raise ValueError('Unknown JARVIS dimension')
        if operation == 'delete':
            (formal if official else candidates).remove(item)
            document.get('review_receipts', {}).pop(key, None)
            for other, receipt in list(document.get('review_receipts', {}).items()):
                if receipt['target'] == key:
                    del document['review_receipts'][other]
        elif operation == 'correct':
            item['statement'] = required(action, 'statement')
            item['source'] = required(action, 'source')
        elif official:
            if operation == 'resume':
                official['approved_at'] = required(action, 'date')
            official['status'] = {'pause': 'paused', 'resume': 'approved', 'revoke': 'revoked'}[operation]
        else:
            raise ValueError('Status changes require a formal dimension')
        return

    if not candidate or candidate['scope'] != 'JARVIS':
        raise ValueError('Unknown JARVIS candidate')
    if operation in ('shown', 'keep', 'defer'):
        target = action.get('target')
        if operation == 'shown' and not any(
                item['id'] == key and item['target'] == target for item in proposals(document)):
            raise ValueError('Review proposal changed')
        receipts = document.setdefault('review_receipts', {})
        if operation != 'shown' and key in receipts:
            target = receipts[key]['target']
        receipts[key] = dict(target=target, decision=operation, count=evidence_count(candidate))
        return

    if operation not in ('approve', 'replace', 'merge'):
        raise ValueError('Unknown profile action')
    approved_at = required(action, 'date')
    date.fromisoformat(approved_at)
    target = None
    if operation in ('replace', 'merge'):
        target_id = required(action, 'target')
        target = next((item for item in formal
                       if item['id'] == target_id and item['scope'] == 'JARVIS'), None)
        if not target:
            raise ValueError('Unknown JARVIS replacement target')
    if operation == 'merge':
        target['statement'] = required(action, 'statement')
        for event in candidate.get('evidence', []):
            add_evidence(target, event)
        inherited = candidate.get('legacy_count', int('evidence' not in candidate))
        target.setdefault('evidence', [])
        target['legacy_count'] = target.get('legacy_count', 1 if not target['evidence'] else 0) + inherited
        target['status'] = 'approved'
        target['approved_at'] = approved_at
    else:
        if target:
            formal.remove(target)
        if len(formal) >= MAX_DIMENSIONS:
            raise ValueError('Formal profile is full. Select a replacement or merge target.')
        formal.append(dict(candidate, status='approved', approved_at=approved_at))
    candidates.remove(candidate)
    document.get('review_receipts', {}).pop(key, None)


def update(path, action):
    path = Path(path)
    lock = path.with_name(path.name + '.lock')
    with lock.open('x', encoding='utf-8') as handle:
        handle.write(str(os.getpid()))
    temp = None
    try:
        baseline = path.read_bytes()
        document = validate(json.loads(baseline.decode('utf-8-sig')))
        original = json.dumps(document, ensure_ascii=False, sort_keys=True)
        apply(document, action)
        validate(document)
        changed = original != json.dumps(document, ensure_ascii=False, sort_keys=True)
        if changed:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                             prefix=path.name + '.', suffix='.tmp',
                                             delete=False) as handle:
                temp = Path(handle.name)
                json.dump(document, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            if path.read_bytes() != baseline:
                raise ValueError('Profile changed concurrently. Re-read before retrying.')
            os.replace(temp, path)
        return {'changed': changed, 'proposals': proposals(document)}
    finally:
        if temp:
            temp.unlink(missing_ok=True)
        lock.unlink()


def main():
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, default=ROOT / 'up.json')
    parser.add_argument('--proposals', action='store_true')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stdin.reconfigure(encoding='utf-8-sig')
    try:
        if args.proposals:
            document = validate(json.loads(args.profile.read_text(encoding='utf-8-sig')))
            result = {'proposals': proposals(document)}
        else:
            result = update(args.profile, json.load(sys.stdin))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc))


if __name__ == '__main__':
    main()
