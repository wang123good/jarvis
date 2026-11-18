"""Read-only, fail-closed project profile loader; no candidate ingestion."""
import hashlib
import json
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_entries(document, today):
    if document['project'] != 'JARVIS' or document['kind'] != 'profile':
        raise ValueError('Wrong project or document kind')
    result = []
    for item in document['entries']:
        if item['scope'] != 'JARVIS' or item['status'] != 'approved':
            continue
        if item['approved_by'] != 'user' or not item['approved_at']:
            continue
        if item['evidence_kind'] not in ('reviewed_agreement', 'explicit_user_statement'):
            continue
        if item['review_after'] and date.fromisoformat(item['review_after']) <= today:
            continue
        result.append(item)
    return result


def load():
    document = json.loads((BASE / 'profile.json').read_text(encoding='utf-8'))
    releases = [json.loads(s) for s in (BASE / 'changes.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    release = releases[-1]
    if release['profile_sha256'] != digest(BASE / 'profile.json') or release['version'] != document['version']:
        raise ValueError('Release integrity mismatch')
    # Asia/Shanghai date, independent of the host timezone.
    from datetime import datetime, timezone, timedelta
    today = datetime.now(timezone(timedelta(hours=8))).date()
    entries = select_entries(document, today)
    for item in entries:
        source = Path(item['source']['path'])
        if digest(source) != item['source']['sha256']:
            raise ValueError('Source changed: ' + item['id'])
    return {'project': 'JARVIS', 'version': document['version'], 'entries': entries}


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        print(json.dumps(load(), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, IndexError, OSError) as exc:
        raise SystemExit('Profile unavailable; use current instructions: ' + str(exc))
