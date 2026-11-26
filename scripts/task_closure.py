"""Read-only validation of task-local closure evidence and separate review states."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from resolve_environment import relative_to


ROOT = Path(__file__).resolve().parents[1]
LAYERS = ('summary', 'wiki', 'archive')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_file(directory, entry, *, closure_only=False):
    require(isinstance(entry, dict), 'File reference must be an object')
    name, digest = entry.get('file'), entry.get('sha256')
    require(isinstance(name, str) and name, 'Missing evidence file')
    path = relative_to(directory, name, 'closure evidence')
    if closure_only:
        require(path.is_relative_to((directory / 'closure').resolve()), 'Candidate must stay in closure/')
    require(path.is_file() and path.stat().st_size > 0, f'Missing or empty evidence: {name}')
    require(isinstance(digest, str) and re.fullmatch(r'[a-f0-9]{64}', digest), 'Invalid SHA-256')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'Evidence changed: {name}')
    return path


def validate(directory, manifest):
    require(isinstance(manifest, dict) and type(manifest.get('schema_version')) is int
            and manifest['schema_version'] == 1, 'Unsupported closure manifest')
    require(manifest.get('template_only', False) is False, 'Instantiate the manifest before validation')
    require(manifest.get('task_id') == directory.name, 'Task ID mismatch')
    require(isinstance(manifest.get('contract'), dict)
            and manifest['contract'].get('file') == 'contract.md', 'Pin the current contract.md')
    checked_file(directory, manifest.get('contract'))
    business = manifest.get('business', {})
    notes = manifest.get('notes', {})
    require(isinstance(business, dict) and isinstance(notes, dict), 'Reviews must be objects')
    acceptance = business.get('status')
    require(acceptance in ('pending', 'accepted', 'not_required', 'returned'), 'Invalid business status')
    review = notes.get('status')
    require(review in ('pending', 'approved', 'skipped', 'returned'), 'Invalid note status')
    # Review evidence records a human decision; hashes alone cannot authenticate that decision.
    for label, record, pending in [('business', business, ('pending',)),
                                   ('notes', notes, ('pending',))]:
        if record['status'] not in pending:
            checked_file(directory, record.get('decision'))
            require(isinstance(record.get('basis'), str) and record['basis'].strip(),
                    f'{label} decision needs a specific approval or exception basis')
    if review != 'skipped':
        sources = manifest.get('sources')
        require(isinstance(sources, list) and sources, 'Record source evidence and coverage')
        for source in sources:
            checked_file(directory, source)
        coverage = manifest.get('coverage')
        require(isinstance(coverage, str) and coverage.strip(), 'Record source coverage and omissions')
        layers = manifest.get('layers')
        require(isinstance(layers, dict) and set(layers) == set(LAYERS), 'All three layers need a disposition')
        candidates = set()
        for layer in LAYERS:
            entry = layers[layer]
            require(isinstance(entry, dict), f'Invalid {layer} disposition')
            disposition = entry.get('disposition')
            if disposition == 'candidate':
                path = checked_file(directory, entry, closure_only=True)
                require(path not in candidates, 'Each layer needs its own candidate or an explicit omission')
                candidates.add(path)
            elif disposition == 'no_candidate' and layer == 'wiki':
                require(isinstance(entry.get('reason'), str) and entry['reason'].strip(),
                        'Explain why wiki has no new knowledge')
            elif disposition == 'excluded':
                require(isinstance(entry.get('reason'), str) and entry['reason'].strip(),
                        'Explain the layer exclusion')
                checked_file(directory, entry.get('decision'))
            else:
                raise ValueError(f'Invalid {layer} disposition')
        checked_file(directory, manifest.get('risk_review'), closure_only=True)
    if acceptance == 'returned' or review == 'returned':
        status = '执行中'
    elif acceptance == 'pending':
        status = '已交付待验收'
    elif review == 'pending':
        status = '已交付待笔记复核'
    elif acceptance == 'accepted':
        status = '已验收'
    else:
        status = '已交付无需验收'
    return {'ok': True, 'task_id': directory.name, 'status': status,
            'business_status': acceptance, 'note_status': review,
            'vault_write_authorized': False, 'semantic_review_verified': False,
            'limitations': ['Hashes check file integrity, not truth or human approval authenticity.',
                            'No vault write, chat deletion, or business acceptance is performed.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_id')
    args = parser.parse_args(argv)
    try:
        require(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}', args.task_id), 'Invalid task ID')
        task_root = ROOT / '.local/tasks'
        require(task_root.resolve() == task_root, 'Task root must not be redirected')
        directory = relative_to(task_root, args.task_id, 'task ID')
        require(directory == task_root / args.task_id and directory.is_dir(), 'Use an existing task directory')
        path = relative_to(directory, 'closure/manifest.json', 'closure manifest')
        manifest = json.loads(path.read_text(encoding='utf-8'))
        result = validate(directory, manifest)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=True))
        return 2
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
