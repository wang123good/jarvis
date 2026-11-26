"""Resolve portable project settings against one ignored machine configuration."""
import argparse
import json
import os
from pathlib import Path, PureWindowsPath
from uuid import UUID, uuid4


ROOT = Path(__file__).resolve().parents[1]
VAULT_ENV = 'JARVIS_VAULT_ROOT'
PERSONA_NAMES = {'steady': '沉稳管家', 'enthusiastic': '热情好事',
                 'professional': '专业干练', 'curious': '好奇话痨', 'bold': '激进大胆'}


class EnvironmentConfigError(ValueError):
    """Configuration is incomplete, unsafe, or points at another connected vault."""


def user_vault_environment():
    """Read the persisted Windows user value even in an already running host."""
    if os.name != 'nt':
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
            value, kind = winreg.QueryValueEx(key, VAULT_ENV)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise EnvironmentConfigError(f'Cannot read user {VAULT_ENV}: {exc}') from exc
    if kind != winreg.REG_SZ:
        raise EnvironmentConfigError(f'{VAULT_ENV} must be a literal string, not an expandable path')
    return value


def vault_environment():
    """Legacy migration candidates only; never consulted by runtime resolution."""
    if VAULT_ENV in os.environ:
        return os.environ[VAULT_ENV], 'process_environment'
    value = user_vault_environment()
    return value, 'user_environment' if value is not None else 'legacy_local_file'


def validate_persona(value):
    """Validate the expression switch and optional machine selection."""
    if value is None:
        return {'enabled': False}
    if (not isinstance(value, dict) or set(value) - {'enabled', 'module'}
            or type(value.get('enabled')) is not bool
            or value.get('module', 'auto') not in ('auto', *PERSONA_NAMES)):
        raise ValueError('persona requires a boolean enabled and an optional supported module')
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


def instance_settings(root, path=None):
    root = Path(root).resolve()
    path = path or relative_to(root, '.local/environment.json', 'environment_file')
    if not path.is_file():
        raise EnvironmentConfigError('Missing .local/environment.json')
    local = read_object(path)
    if type(local.get('version')) is not int or local['version'] != 2:
        raise EnvironmentConfigError('Instance configuration version 2 required; run migration preview')
    try:
        UUID(local.get('instance_id'))
    except (ValueError, TypeError, AttributeError) as exc:
        raise EnvironmentConfigError('Invalid instance_id') from exc
    absolute_path(local.get('project_root'), 'project_root')
    if Path(local['project_root']) != root or absolute_path(local['project_root'], 'project_root') != root:
        raise EnvironmentConfigError('Configuration belongs to a different project directory')
    obsidian = local.get('obsidian')
    connector = obsidian.get('connector') if isinstance(obsidian, dict) else None
    if not isinstance(connector, dict) or connector.get('type') not in ('filesystem', 'external'):
        raise EnvironmentConfigError('Configure a filesystem or external Obsidian connector')
    return local


def resolve_environment(project_root=ROOT, connector_vault=None):
    root = Path(project_root).resolve()
    defaults = read_object(root / 'config/defaults.json')
    local_rel = defaults.get('environment_file')
    local_path = relative_to(root, local_rel, 'environment_file')
    pointer_path = relative_to(root, defaults.get('knowledge_pointer'), 'knowledge_pointer')
    pointer = read_object(pointer_path)
    if pointer.get('environment_file') != local_rel or 'vault' in pointer:
        raise EnvironmentConfigError('Shared knowledge pointer must reference environment_file, not an absolute vault')
    local = instance_settings(root, local_path)
    try:
        persona = validate_persona(local.get('persona'))
    except ValueError as exc:
        raise EnvironmentConfigError(str(exc)) from exc
    vault = absolute_path(local['obsidian'].get('vault_root'), 'obsidian.vault_root')
    if Path(local['obsidian']['vault_root']) != vault:
        raise EnvironmentConfigError('Configured vault path was redirected')
    if not vault.is_dir():
        raise EnvironmentConfigError(f'Configured vault does not exist: {vault}')
    if vault.is_relative_to(root) or root.is_relative_to(vault):
        raise EnvironmentConfigError('Project and vault must have distinct, non-overlapping roots')
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
    connector = local['obsidian']['connector']
    if connector['type'] == 'filesystem':
        actual = vault
        if connector_vault is not None:
            actual = absolute_path(connector_vault, 'connector_vault')
    else:
        if connector_vault is None:
            raise EnvironmentConfigError('External connector must report its actual vault root')
        actual = absolute_path(connector_vault, 'connector_vault')
    if actual != vault:
        raise EnvironmentConfigError(f'Connected vault mismatch: local={vault}; connector={actual}')
    resolved_pointer = {key: value for key, value in pointer.items() if key != 'environment_file'}
    resolved_pointer.update(version=1, vault=str(vault))
    return {
        'ok': True,
        'project_root': str(root),
        'environment_file': str(local_path),
        'knowledge_pointer': str(pointer_path),
        'vault_root': str(vault),
        'vault_source': 'local_instance',
        'instance_id': local['instance_id'],
        'connector': connector,
        'connector_vault': str(actual),
        'vault_exists': vault.is_dir(),
        'project_knowledge_root': str(project_path),
        'registry': str(registry),
        'agreement': str(agreement),
        'skill_roots': [str(path.resolve()) for path in skill_roots],
        'connector_checked': True,
        'connector_matches': True,
        'write_ready': True,
        'resolved_pointer': resolved_pointer,
        'persona': persona,
    }


def require_write_ready(resolved):
    if not resolved.get('write_ready'):
        raise EnvironmentConfigError('Resolve the configured instance before writing')
    current = resolve_environment(resolved['project_root'], resolved.get('connector_vault'))
    for key in ('instance_id', 'vault_root', 'connector'):
        if current[key] != resolved.get(key):
            raise EnvironmentConfigError('Instance configuration changed after resolution')


def write_runtime_pointer(resolved):
    require_write_ready(resolved)
    target = relative_to(Path(resolved['project_root']), '.local/obsidian-kb.resolved.json', 'runtime pointer')
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
                'Run setup_environment.py --vault with your selected vault, or preview legacy migration'
            )
        print(json.dumps(result, ensure_ascii=False))
        return 2
    print(json.dumps(resolved, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
