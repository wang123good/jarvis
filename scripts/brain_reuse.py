"""Check a task-local reuse evidence chain; never judge semantic reuse success.

No commands or note contents are executed. --live-sources rereads only the
explicit source paths under the environment-selected vault.
"""
import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_file(root, name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError('Use a nonempty relative POSIX file path')
    rel = Path(name)
    if rel.is_absolute() or PureWindowsPath(name).drive or '..' in rel.parts:
        raise ValueError('Evidence/source path escapes its root')
    target = (root / rel).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError('Missing file or path escapes its root')
    return target


def reference(root, ref):
    if not isinstance(ref, dict):
        raise ValueError('Expected file/sha256 reference')
    path = local_file(root, ref.get('file'))
    if path.stat().st_size == 0 or digest(path) != ref.get('sha256'):
        raise ValueError('Empty or changed evidence: ' + ref['file'])
    return path


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Missing ' + field)


def validate(request, root, source_root=None):
    """Return structural completeness only. Invalid/incomplete chains raise."""
    if request.get('schema_version') != 1:
        raise ValueError('Unsupported schema_version')
    for field in ('task_id', 'goal', 'failure_condition', 'limitations'):
        text(request.get(field), field)
    sources = request.get('sources')
    actions = request.get('actions')
    if not isinstance(sources, list) or not sources or not isinstance(actions, list) or not actions:
        raise ValueError('Sources and actual actions are required')
    ids = set()
    for source in sources:
        sid = source.get('id')
        text(sid, 'source id')
        if sid in ids:
            raise ValueError('Duplicate source id')
        ids.add(sid)
        if source.get('status') not in ('active', 'reviewed', 'trusted', 'review'):
            raise ValueError('Non-current or unsupported source status')
        snapshot = reference(root, source.get('snapshot'))
        # Revalidation is required even for active historical notes.
        reference(root, source.get('revalidation'))
        text(source.get('applicability'), 'source applicability')
        text(source.get('invalid_if'), 'source invalidation condition')
        if source_root is not None:
            original = local_file(source_root, source.get('path'))
            if digest(original) != digest(snapshot):
                raise ValueError('Live source drift: ' + sid)
    used = set()
    for action in actions:
        if action.get('source_id') not in ids:
            raise ValueError('Unknown action source')
        used.add(action['source_id'])
        for field in ('decision_change', 'result'):
            text(action.get(field), field)
        if action.get('outcome') != 'observed':
            raise ValueError('Action outcome must be observed, not planned/unknown')
        reference(root, action.get('evidence'))
        reference(root, action.get('artifact'))
    if used != ids:
        raise ValueError('Every adopted source must change an actual action')
    return {'status': 'evidence_complete', 'live_sources_checked': source_root is not None,
            'sources': len(ids), 'actions': len(actions),
            'semantic_reuse': 'requires_review', 'user_acceptance': 'not_assessed',
            'limitations': 'Hashes and required fields cannot prove truth, applicability, causality or benefit.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('--live-sources', action='store_true')
    args = parser.parse_args()
    try:
        source_root = None
        if args.live_sources:
            from resolve_environment import resolve_environment, require_write_ready
            env = resolve_environment()
            require_write_ready(env)
            source_root = Path(env['vault_root'])
        request = json.loads(args.request.read_text(encoding='utf-8'))
        result = validate(request, args.request.resolve().parent, source_root)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({'status': 'incomplete', 'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
