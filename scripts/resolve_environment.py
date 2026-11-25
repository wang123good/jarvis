"""Resolve portable project settings against one ignored machine configuration."""
import argparse
import json
import os
from pathlib import Path, PureWindowsPath
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]


class EnvironmentConfigError(ValueError):
    """Configuration is incomplete, unsafe, or points at another connected vault."""


def validate_persona(value):
    """Validate the single expression switch; old environments stay disabled."""
    if value is None:
        return {'enabled': False}
    if (not isinstance(value, dict) or set(value) != {'enabled'}
            or type(value['enabled']) is not bool):
        raise ValueError('persona must contain only enabled: true/false')
    return dict(value)


def read_object(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise EnvironmentConfigError(f'Cannot read configuration {path}: {exc}') from exc
    if not isinstance(value, dict):
        raise EnvironmentConfigError(f'Configuration must be an object: {path}')
    return value


def relative_to(base, value, label):
    if not isinstance(value, str) or not value.strip():
        raise EnvironmentConfigError(f'{label} must be a nonempty relative path')
    portable = value.replace('\\', '/')
    if Path(portable).is_absolute() or PureWindowsPath(value).drive or '..' in portable.split('/'):
        raise EnvironmentConfigError(f'{label} must stay relative to its configured root')
    target = (base / portable).resolve()
    if not target.is_relative_to(base.resolve()):
        raise EnvironmentConfigError(f'{label} escapes its configured root')
    return target


def absolute_path(value, label):
    if not isinstance(value, str) or not value.strip() or not Path(value).is_absolute():
        raise EnvironmentConfigError(f'{label} must be an absolute path on this machine')
    return Path(value).resolve()


def resolve_environment(project_root=ROOT, connector_vault=None):
    root = Path(project_root).resolve()
    defaults = read_object(root / 'config/defaults.json')
    local_rel = defaults.get('environment_file')
    local_path = relative_to(root, local_rel, 'environment_file')
    pointer_path = relative_to(root, defaults.get('knowledge_pointer'), 'knowledge_pointer')
    pointer = read_object(pointer_path)
    if pointer.get('environment_file') != local_rel or 'vault' in pointer:
        raise EnvironmentConfigError('Shared knowledge pointer must reference environment_file, not an absolute vault')
    if not local_path.is_file():
        raise EnvironmentConfigError(
            'Missing .local/environment.json; run python scripts/setup_environment.py '
            '--connector-vault "<actual Obsidian vault path>"'
        )
    local = read_object(local_path)
    if local.get('version') != 1:
        raise EnvironmentConfigError('Unsupported local environment version; expected 1')
    try:
        persona = validate_persona(local.get('persona'))
    except ValueError as exc:
        raise EnvironmentConfigError(str(exc)) from exc
    vault = absolute_path(local.get('vault_root'), 'vault_root')
    project = pointer.get('project')
    if not isinstance(project, dict):
        raise EnvironmentConfigError('knowledge pointer project must be an object')
    project_path = relative_to(vault, project.get('root'), 'project.root')
    layers = pointer.get('layers')
    if not isinstance(layers, dict):
        raise EnvironmentConfigError('knowledge pointer layers must be an object')
    for name, paths in layers.items():
        if not isinstance(paths, list):
            raise EnvironmentConfigError(f'layers.{name} must be a list')
        for path in paths:
            relative_to(vault, path, f'layers.{name}')
    registry = relative_to(vault, defaults.get('registry'), 'registry')
    agreement = relative_to(vault, defaults.get('agreement'), 'agreement')
    skills = local.get('skill_roots', [])
    if not isinstance(skills, list):
        raise EnvironmentConfigError('skill_roots must be a list of absolute local paths')
    if skills:
        skill_roots = [absolute_path(path, 'skill_roots') for path in skills]
    else:
        skill_roots = [Path.home() / '.codex/skills', Path.home() / '.agents/skills']
    checked = connector_vault is not None
    if checked:
        actual = absolute_path(connector_vault, 'connector_vault')
        if actual != vault:
            raise EnvironmentConfigError(f'Connected vault mismatch: local={vault}; connector={actual}; no vault writes allowed')
    resolved_pointer = {key: value for key, value in pointer.items() if key != 'environment_file'}
    resolved_pointer.update(version=1, vault=str(vault))
    return {
        'ok': True,
        'project_root': str(root),
        'environment_file': str(local_path),
        'knowledge_pointer': str(pointer_path),
        'vault_root': str(vault),
        'vault_exists': vault.is_dir(),
        'project_knowledge_root': str(project_path),
        'registry': str(registry),
        'agreement': str(agreement),
        'skill_roots': [str(path.resolve()) for path in skill_roots],
        'connector_checked': checked,
        'connector_matches': True if checked else None,
        'write_ready': checked and vault.is_dir(),
        'resolved_pointer': resolved_pointer,
        'persona': persona,
    }


def require_write_ready(resolved):
    if not resolved['connector_checked']:
        raise EnvironmentConfigError('Provide --connector-vault from the connected tool; a configured path alone does not authorize vault writes')
    if not resolved['vault_exists']:
        raise EnvironmentConfigError('Configured vault does not exist; create/open it in Obsidian and verify the connection first')


def write_runtime_pointer(resolved):
    require_write_ready(resolved)
    target = Path(resolved['project_root']) / '.local/obsidian-kb.resolved.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.' + uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(resolved['resolved_pointer'], stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connector-vault', help='Actual vault root reported by the connected tool; do not guess')
    parser.add_argument('--require-write-ready', action='store_true')
    parser.add_argument('--write-runtime-pointer', action='store_true', help='Export a local version-1 pointer for tools supporting explicit configuration')
    args = parser.parse_args(argv)
    try:
        resolved = resolve_environment(connector_vault=args.connector_vault)
        if args.require_write_ready:
            require_write_ready(resolved)
        if args.write_runtime_pointer:
            resolved['runtime_pointer'] = str(write_runtime_pointer(resolved))
    except EnvironmentConfigError as exc:
        message = str(exc)
        result = {
            'ok': False,
            'status': 'configuration_required'
            if 'Missing .local/environment.json' in message
            else 'configuration_invalid',
            'error': message,
        }
        if result['status'] == 'configuration_required':
            result['next_action'] = (
                'python scripts/setup_environment.py '
                '--connector-vault "<actual Obsidian vault path>"'
            )
        print(json.dumps(result, ensure_ascii=False))
        return 2
    print(json.dumps(resolved, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
