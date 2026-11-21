"""Read the local profile without loading legacy profiles or candidates."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

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
            if item['status'] == 'approved' and not isinstance(item.get('approved_at'), str):
                raise ValueError('Approved preference needs approved_at')
            from datetime import date
            date.fromisoformat(item['recorded_at'])
            if item['status'] == 'approved':
                date.fromisoformat(item['approved_at'])
    return document

def load(path=None):
    path = Path(path) if path is not None else ROOT / 'up.json'
    if not path.exists():
        return {'status': 'needs_initialization', 'nickname': '', 'preferences': []}
    document = validate(json.loads(path.read_text(encoding='utf-8-sig')))
    if not document.get('enabled', True):
        return {'status': 'disabled', 'nickname': '', 'preferences': []}
    return {
        'status': 'ready' if document['nickname'].strip() else 'needs_initialization',
        'nickname': document['nickname'].strip(),
        'collect_candidates': document.get('collect_candidates', True),
        'preferences': [item for item in document['preferences']
                        if item['status'] == 'approved' and item['scope'] == 'JARVIS'],
    }

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        print(json.dumps(load(), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        raise SystemExit('Profile unavailable; preserve original and use current instructions: ' + str(exc))
