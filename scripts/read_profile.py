"""Read the local profile without loading legacy profiles or candidates."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MAX_DIMENSIONS = 20
MAX_CONTEXT = 5


def evidence_count(item):
    return item.get('legacy_count', int('evidence' not in item)) + len(item.get('evidence', []))

def validate(document):
    if not isinstance(document, dict) or document.get('schema_version') != '1.0':
        raise ValueError('Unsupported profile schema')
    if not isinstance(document.get('nickname'), str):
        raise ValueError('nickname must be a string')
    if not isinstance(document.get('collect_candidates', True), bool):
        raise ValueError('collect_candidates must be boolean')
    if not isinstance(document.get('enabled', True), bool):
        raise ValueError('enabled must be boolean')
    ids = set()
    if isinstance(document.get('preferences'), list) and len(document['preferences']) > MAX_DIMENSIONS:
        raise ValueError('At most 20 formal dimensions are allowed')
    receipts = document.get('review_receipts', {})
    if not isinstance(receipts, dict):
        raise ValueError('Invalid review receipts')
    for receipt in receipts.values():
        if (not isinstance(receipt, dict) or 'target' not in receipt
                or receipt['target'] is not None and not isinstance(receipt['target'], str)
                or receipt.get('decision') not in ('shown', 'keep', 'defer')
                or type(receipt.get('count')) is not int or receipt['count'] < 1):
            raise ValueError('Invalid review receipt')
    for field in ('preferences', 'candidates'):
        if not isinstance(document.get(field), list):
            raise ValueError(field + ' must be a list')
        for item in document[field]:
            if not isinstance(item, dict):
                raise ValueError('Preference must be an object')
            for key in ('id', 'statement', 'scope', 'source', 'recorded_at', 'status'):
                if not isinstance(item.get(key), str) or not item[key].strip():
                    raise ValueError('Missing preference field: ' + key)
            if item['id'] in ids:
                raise ValueError('Duplicate preference id')
            ids.add(item['id'])
            allowed = ('approved', 'paused', 'revoked') if field == 'preferences' else ('candidate',)
            if item['status'] not in allowed:
                raise ValueError('Invalid preference status')
            evidence = item.get('evidence', [])
            if (not isinstance(evidence, list)
                    or any(not isinstance(event, str) or not event for event in evidence)
                    or len(set(evidence)) != len(evidence)):
                raise ValueError('Invalid or duplicated evidence event')
            legacy_count = item.get('legacy_count', 0)
            if type(legacy_count) is not int or legacy_count < 0 or evidence_count(item) < 1:
                raise ValueError('Invalid evidence count')
            if item['status'] == 'approved' and not isinstance(item.get('approved_at'), str):
                raise ValueError('Approved preference needs approved_at')
            from datetime import date
            date.fromisoformat(item['recorded_at'])
            if item['status'] == 'approved':
                date.fromisoformat(item['approved_at'])
    return document

def load(path=None, *, index=False, selected=()):
    path = Path(path) if path is not None else ROOT / 'up.json'
    if not path.exists():
        return {'status': 'needs_initialization', 'nickname': '', 'preferences': []}
    document = validate(json.loads(path.read_text(encoding='utf-8-sig')))
    if not document.get('enabled', True):
        return {'status': 'disabled', 'nickname': '', 'preferences': []}
    approved = [item for item in document['preferences']
                if item['status'] == 'approved' and item['scope'] == 'JARVIS']
    approved.sort(key=evidence_count, reverse=True)
    preferences = [dict(item, count=evidence_count(item)) for item in approved]
    if index:
        preferences = [{key: item[key] for key in ('id', 'statement', 'count')}
                       for item in preferences]
    elif selected:
        by_id = {item['id']: item for item in preferences}
        matches = [by_id[key] for key in dict.fromkeys(selected) if key in by_id][:MAX_CONTEXT]
        preferences = [{key: item[key] for key in ('id', 'statement', 'source', 'count')}
                       for item in matches]
    return {
        'status': 'ready' if document['nickname'].strip() else 'needs_initialization',
        'nickname': document['nickname'].strip(),
        'collect_candidates': document.get('collect_candidates', True),
        'preferences': preferences,
    }

if __name__ == '__main__':
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--index', action='store_true')
    modes.add_argument('--select', nargs='+')
    modes.add_argument('--status', action='store_true')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        result = load(index=args.index, selected=args.select or ())
        if args.status:
            result.pop('preferences', None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        raise SystemExit('Profile unavailable; preserve original and use current instructions: ' + str(exc))
