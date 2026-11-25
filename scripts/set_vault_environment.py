"""Persist the explicitly selected vault in the Windows user environment."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from resolve_environment import ROOT, VAULT_ENV, absolute_path, resolve_environment, write_runtime_pointer


def persist_user_vault(value, project_root=ROOT, *, configure_local=None):
    if os.name != 'nt':
        raise ValueError('On this platform export JARVIS_VAULT_ROOT in your shell profile')
    import winreg
    vault = absolute_path(value, VAULT_ENV)
    if not vault.is_dir():
        raise ValueError('Selected vault directory does not exist')
    process_before = os.environ.get(VAULT_ENV)
    if process_before is not None and absolute_path(process_before, VAULT_ENV) != vault:
        raise ValueError('Conflicting process JARVIS_VAULT_ROOT; update or remove the host process override before switching vaults')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
        try:
            user_before, kind_before = winreg.QueryValueEx(key, VAULT_ENV)
        except FileNotFoundError:
            user_before, kind_before = None, None
        # Validate all project-relative paths before changing the user environment.
        os.environ[VAULT_ENV] = str(vault)
        try:
            resolved = resolve_environment(project_root)
            backup = Path(project_root) / '.local/environment-backups'
            backup.mkdir(parents=True, exist_ok=True)
            record = backup / ('vault-env-' + uuid4().hex + '.json')
            with record.open('x', encoding='utf-8') as stream:
                json.dump({'variable': VAULT_ENV, 'user_before': user_before,
                           'kind_before': kind_before, 'process_before': process_before,
                           'selected': str(vault), 'time': datetime.now(timezone.utc).isoformat()},
                          stream, ensure_ascii=False, indent=2)
            winreg.SetValueEx(key, VAULT_ENV, 0, winreg.REG_SZ, str(vault))
            try:
                if winreg.QueryValueEx(key, VAULT_ENV)[0] != str(vault):
                    raise ValueError('User environment readback failed')
                if configure_local is not None:
                    configure_local()
                resolved = resolve_environment(project_root)
                pointer = write_runtime_pointer(resolved)
            except Exception:
                if user_before is None:
                    winreg.DeleteValue(key, VAULT_ENV)
                else:
                    winreg.SetValueEx(key, VAULT_ENV, 0, kind_before, user_before)
                raise
        finally:
            if process_before is None:
                os.environ.pop(VAULT_ENV, None)
            else:
                os.environ[VAULT_ENV] = process_before
    return {'ok': True, 'variable': VAULT_ENV, 'user_value': str(vault),
            'backup': str(record), 'runtime_pointer': str(pointer),
            'note': 'User value and current process selection agree; subsequent commands use the selected vault'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', required=True, help='Explicitly selected vault; no default scanning')
    args = parser.parse_args()
    try:
        result = persist_user_vault(args.vault)
    except (ValueError, OSError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
