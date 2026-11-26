"""Read-only Obsidian CLI target check. Never infer a vault from its name or window.

Official protocol: https://help.obsidian.md/cli (vault=<id> vault info=path).
The discovered executable is transient diagnostic data, never instance configuration.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import resolve_environment as environment


class CLIError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def discover():
    # On Windows .exe is a GUI launcher; only .com carries CLI stdin/stdout.
    command = 'Obsidian.com' if os.name == 'nt' else 'obsidian'
    executable = shutil.which(command)
    return {'available': executable is not None, 'command': command,
            'executable': executable, 'source': 'process_PATH',
            'status': 'discovered' if executable else 'cli_not_on_path'}


def app_running():
    if os.name != 'nt':
        raise CLIError('running_state_unknown', 'Automatic running-state check supports Windows only')
    try:
        result = subprocess.run(['tasklist.exe', '/FI', 'IMAGENAME eq Obsidian.exe', '/FO', 'CSV', '/NH'],
                                capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CLIError('running_state_unknown', str(exc)) from exc
    if result.returncode:
        raise CLIError('running_state_unknown', 'Cannot query Obsidian process state')
    return any(row and row[0].lower() == 'obsidian.exe' for row in
               csv.reader(io.StringIO(result.stdout.decode('utf-8', errors='replace'))))


def target_id(vault, registry):
    entries = environment.read_object(registry).get('vaults')
    if not isinstance(entries, dict):
        raise CLIError('registry_invalid', 'Obsidian registry has no vault mapping')
    matches = []
    for identifier, entry in entries.items():
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
            continue
        path = Path(entry['path'])
        if path.is_absolute() and path.resolve() == vault:
            if not re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
                raise CLIError('registry_invalid', 'Unsupported vault ID')
            matches.append(identifier)
    if len(matches) != 1:
        raise CLIError('target_ambiguous' if matches else 'target_unregistered',
                       'Need exactly one registered ID for the configured vault path')
    return matches[0]


def check(project_root=environment.ROOT, connector_vault=None):
    resolved = environment.resolve_environment(project_root, connector_vault)
    found = discover()
    result = {'ok': False, 'cli_ready': False, 'filesystem_ready': resolved['write_ready'],
              'vault_root': resolved['vault_root'], 'discovery': found,
              'writes': False, 'launch_requested': False}
    try:
        if not found['available']:
            raise CLIError('cli_not_on_path', 'No CLI in current process PATH; installation, CLI registration and host PATH refresh are separate checks')
        if not app_running():
            raise CLIError('app_not_running', 'Start Obsidian explicitly before checking CLI; this check will not launch it')
        appdata = os.environ.get('APPDATA')
        if not appdata:
            raise CLIError('registry_unavailable', 'APPDATA is unavailable; cannot select a vault ID')
        registry = Path(appdata) / 'obsidian/obsidian.json'
        if not registry.is_file():
            raise CLIError('registry_unavailable', 'Obsidian vault registry is unavailable')
        identifier = target_id(Path(resolved['vault_root']), registry)
        command = [found['executable'], f'vault={identifier}', 'vault', 'info=path']
        result.update(vault_id=identifier, command=command)
        try:
            response = subprocess.run(command, cwd=resolved['project_root'], capture_output=True,
                                      text=True, encoding='utf-8-sig', timeout=15,
                                      **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
        except subprocess.TimeoutExpired as exc:
            raise CLIError('cli_timeout', 'CLI did not report its target within 15 seconds') from exc
        except (OSError, UnicodeError) as exc:
            raise CLIError('cli_unavailable', str(exc)) from exc
        if response.returncode:
            raise CLIError('cli_unavailable', f'CLI returned {response.returncode}: {response.stderr.strip()[:500]}')
        actual_text = response.stdout.strip()
        result['reported_path'] = actual_text
        # Reject headings, diagnostics, multiple lines and names; accept one absolute path only.
        if '\n' in actual_text or '\r' in actual_text or not Path(actual_text).is_absolute():
            raise CLIError('target_unverified', 'CLI did not return a single absolute vault path')
        actual = environment.absolute_path(actual_text, 'CLI reported path')
        if actual != Path(resolved['vault_root']):
            raise CLIError('target_mismatch', 'Live CLI path differs from the configured instance vault')
        environment.require_write_ready(resolved)
        if target_id(Path(resolved['vault_root']), registry) != identifier:
            raise CLIError('target_changed', 'Obsidian registry changed during the check')
        result.update(ok=True, cli_ready=True, status='verified', actual_vault_root=str(actual))
    except CLIError as exc:
        result.update(status=exc.status, error=str(exc))
    except (OSError, ValueError) as exc:
        result.update(status='target_unverified', error=str(exc))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connector-vault', help='Actual external connector root, when configured')
    args = parser.parse_args(argv)
    try:
        result = check(connector_vault=args.connector_vault)
    except (OSError, ValueError) as exc:
        result = {'ok': False, 'cli_ready': False, 'status': 'configuration_invalid', 'error': str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
