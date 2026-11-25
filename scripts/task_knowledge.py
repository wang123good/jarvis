"""Find scoped Obsidian note candidates and inspect exact Skill files for a task."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

import experience_registry
from resolve_environment import ROOT, read_object, relative_to, resolve_environment


def note_scope(environment, layer, folder):
    vault = Path(environment['vault_root'])
    pointer = environment['resolved_pointer']
    def scope_path(value):
        target = relative_to(vault, value, 'search folder')
        if target != vault / value.replace('\\', '/'):
            raise ValueError('Search scopes must not traverse links or junctions')
        return target

    if layer == 'project':
        rule_folder = Path(environment['agreement']).parent.relative_to(vault).as_posix()
        project_name = pointer['project']['name']
        bases = [pointer['project']['root'], f'05 规则/{project_name}']
        if rule_folder != bases[1]:
            raise ValueError('Configured agreement must stay within the project rule folder')
    else:
        bases = pointer['layers'][layer]
        if folder is None:
            raise ValueError('Choose an authorized folder for topic or reference notes')
    candidates = [scope_path(base) for base in bases]
    if folder is None:
        return candidates
    target = scope_path(folder)
    if not any(target.is_relative_to(base) for base in candidates):
        raise ValueError('Search folder is outside the selected layer or project')
    return [target]


def markdown_files(scope, unreadable, vault):
    def walk_error(error):
        unreadable.append(Path(error.filename).relative_to(vault).as_posix())

    for directory, subdirs, names in os.walk(scope, onerror=walk_error, followlinks=False):
        parent = Path(directory)
        subdirs[:] = [name for name in subdirs
                      if not name.startswith('.') and (parent / name).resolve() == parent / name]
        for name in names:
            if not name.startswith('.') and Path(name).suffix.casefold() == '.md':
                yield parent / name


def search_notes(environment, layer, folder, terms, limit):
    vault = Path(environment['vault_root'])
    if not vault.is_dir():
        raise ValueError('Configured vault directory is unavailable')
    scopes = note_scope(environment, layer, folder)
    needles = [term.strip().casefold() for term in terms]
    if not all(needles):
        raise ValueError('Provide nonempty search terms')
    matches, unavailable, skipped = [], [], []
    for scope in scopes:
        if not scope.is_dir():
            unavailable.append(scope.relative_to(vault).as_posix())
            continue
        for path in markdown_files(scope, skipped, vault):
            if path.resolve() != path or not path.is_file():
                continue
            name = path.relative_to(vault).as_posix()
            try:
                with path.open('rb') as stream:
                    data = stream.read(256_001)
                if len(data) > 256_000:
                    skipped.append(name)
                    continue
                body = data.decode('utf-8-sig')
            except (OSError, UnicodeError):
                skipped.append(name)
                continue
            searchable = (name + '\n' + body).casefold()
            if not all(term in searchable for term in needles):
                continue
            snippet = next((line.strip()[:240] for line in body.splitlines()
                            if any(term in line.casefold() for term in needles)), '')
            matches.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(),
                            'excerpt': snippet})
    return {
        'layer': layer,
        'scopes': [path.relative_to(vault).as_posix() for path in scopes],
        'matches': sorted(matches, key=lambda match: match['path'])[:limit],
        'match_count': len(matches), 'unavailable_scopes': unavailable,
        'skipped_unreadable_or_large': sorted(skipped),
        'formal_registry_present': Path(environment['registry']).is_file(),
    }


def inspect_skill(project_root, skill_roots, name):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or len(name) > 64:
        raise ValueError('Use an exact lowercase Skill identifier')
    roots = [project_root / '.agents/skills', project_root / '.codex/skills',
             *map(Path, skill_roots)]
    roots = list(dict.fromkeys(path.resolve() for path in roots))
    matches = []
    for root in roots:
        path = root / name / 'SKILL.md'
        if path.resolve() != path or not path.is_file():
            continue
        matches.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    status = {0: 'missing', 1: 'found'}.get(len(matches), 'ambiguous')
    return {'skill': name, 'status': status, 'matches': matches,
            'searched_roots': [str(path) for path in roots]}


def main(argv=None, project_root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_subparsers(dest='operation', required=True)
    search = operations.add_parser('search')
    search.add_argument('--layer', choices=('project', 'domain', 'resource'), required=True)
    search.add_argument('--folder', help='Explicit vault-relative scope, required for domain/resource')
    search.add_argument('--limit', type=int, choices=range(1, 21), default=5)
    search.add_argument('terms', nargs='+', help='Literal terms that must all match')
    skill = operations.add_parser('skill')
    skill.add_argument('name')
    experience = operations.add_parser('experience')
    experience.add_argument('terms', nargs='*')
    experience.add_argument('--limit', type=int, choices=range(1, 21), default=5)
    initialize = operations.add_parser('experience-init')
    initialize.add_argument('--connector-vault')
    register = operations.add_parser('experience-register')
    register.add_argument('entry', type=Path)
    register.add_argument('--baseline', required=True)
    register.add_argument('--connector-vault')
    args = parser.parse_args(argv)
    try:
        environment = resolve_environment(project_root, getattr(args, 'connector_vault', None))
        if args.operation == 'search':
            result = search_notes(environment, args.layer, args.folder, args.terms, args.limit)
        elif args.operation == 'skill':
            result = inspect_skill(Path(project_root), environment['skill_roots'], args.name)
        elif args.operation == 'experience':
            result = experience_registry.query(environment, args.terms, args.limit, inspect_skill)
        elif args.operation == 'experience-init':
            result = experience_registry.initialize(environment)
        else:
            result = experience_registry.register(
                environment, read_object(args.entry), args.baseline, inspect_skill)
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
