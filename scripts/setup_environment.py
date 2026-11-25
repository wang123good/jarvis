"""Create or validate the ignored local vault configuration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

import resolve_environment as reader


ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_REL = Path(".local/environment.json")


class SetupError(ValueError):
    """The requested local configuration cannot be applied safely."""


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def configure(project_root, destination, *, replace=False, migration=None):
    root = Path(project_root).resolve()
    destination = reader.absolute_path(destination, 'vault')
    if not destination.is_dir() or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise SetupError('Select an existing vault outside the project directory')
    path = reader.relative_to(root, str(ENVIRONMENT_REL), 'environment_file')
    lock = reader.relative_to(root, '.local/environment.lock', 'environment lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('x', encoding='utf-8') as stream:
        stream.write(str(os.getpid()))
    try:
        return configure_locked(root, destination, path, replace=replace, migration=migration)
    finally:
        lock.unlink()


def configure_locked(root, vault, path, *, replace, migration):
    original = path.read_bytes() if path.is_file() else None
    existing = reader.read_object(path) if original is not None else None
    if existing is not None and existing.get('version') == 2:
        settings = reader.instance_settings(root, path)
        previous = reader.absolute_path(settings['obsidian'].get('vault_root'), 'vault')
        if previous != vault and not replace:
            raise SetupError('Use --replace to change the configured vault')
    else:
        if existing is not None and (existing.get('version') != 1 or migration is None):
            raise SetupError('Existing configuration requires explicit migration')
        if migration is not None and fingerprint(root, vault, original) != migration:
            raise SetupError('Migration confirmation does not match the current preview')
        settings = dict(existing) if existing is not None else {
            'persona': {'enabled': True, 'module': 'steady'}, 'skill_roots': [],
        }
        settings.update(version=2, instance_id=str(uuid4()), project_root=str(root))
        settings.pop('vault_root', None)
    if migration is not None and existing is not None and existing.get('version') == 2:
        if previous != vault or settings.get('migration_confirmation') != migration:
            raise SetupError('Migration confirmation does not match the completed migration')
    elif migration is not None:
        settings['migration_confirmation'] = migration
    status = ('created' if original is None else 'migrated' if existing.get('version') == 1
              else 'already_configured' if previous == vault else 'updated')
    obsidian = settings.get('obsidian', {'connector': {'type': 'filesystem'}})
    settings['obsidian'] = {**obsidian, 'vault_root': str(vault)}
    if status == 'updated':
        settings.pop('migration_confirmation', None)
    data = json_bytes(settings)
    if original != data:
        if (path.read_bytes() if path.is_file() else None) != original:
            raise SetupError('Instance configuration changed during setup')
        atomic_write_bytes(path, data)
    try:
        resolved = reader.resolve_environment(root)
        runtime = reader.write_runtime_pointer(resolved)
    except Exception:
        if original != data and path.is_file() and path.read_bytes() == data:
            if original is None:
                path.unlink()
            else:
                atomic_write_bytes(path, original)
        raise
    return {'ok': True, 'status': status, 'instance_id': resolved['instance_id'],
            'vault_root': str(vault), 'runtime_pointer': str(runtime), 'profile_modified': False}


def fingerprint(root, vault, original):
    from hashlib import sha256
    return sha256(json_bytes({'root': str(root), 'vault': str(vault),
                              'baseline': None if original is None else sha256(original).hexdigest()})).hexdigest()


def preview_migration(root, destination=None):
    root = Path(root).resolve()
    path = reader.relative_to(root, str(ENVIRONMENT_REL), 'environment_file')
    original = path.read_bytes() if path.is_file() else None
    settings = reader.read_object(path) if original is not None else {}
    if settings and settings.get('version') != 1:
        raise SetupError('Migration requires a version 1 configuration or a new instance')
    source = 'explicit'
    if destination is None:
        destination, source = reader.vault_environment()
        if destination is None:
            destination, source = settings.get('vault_root'), 'legacy_local_file'
    vault = reader.absolute_path(destination, 'migration vault')
    if not vault.is_dir() or vault.is_relative_to(root) or root.is_relative_to(vault):
        raise SetupError('Select an existing vault outside the project directory')
    return {'ok': True, 'project_root': str(root), 'vault_root': str(vault),
            'source': source, 'confirmation': fingerprint(root, vault, original)}


def main(argv=None, project_root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', '--connector-vault')
    parser.add_argument('--replace', action='store_true')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--preview-migration', action='store_true')
    mode.add_argument('--confirm-migration')
    args = parser.parse_args(argv)
    try:
        if args.preview_migration:
            result = preview_migration(project_root, args.vault)
        else:
            result = configure(project_root, args.vault, replace=args.replace,
                               migration=args.confirm_migration)
    except (OSError, ValueError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
