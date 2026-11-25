"""Project first-run onboarding. Discovery and status are read-only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_hex
from shutil import disk_usage, which

import brain_router
import init_vault
import resolve_environment as environment
import setup_environment
from read_profile import load as load_profile

ROOT = environment.ROOT
PROTOCOL = 1
ZONE = timezone(timedelta(hours=8))
DISPLAY = """我是 JARVIS，你的智能管家。我会和你确认目标和验收标准，规划步骤、组织执行、核验结果，并交付证据。

- 普通聊天：帮我比较这两个想法，指出各自的适用条件。
- 长时任务：帮我把这份需求做成可交付的方案，先给我验收标准，确认后持续推进并验证。
- 研究探索：帮我研究这三种方案，先定问题和证据标准，再比较来源并交付结论。
- 检索：在我的知识库里找 JARVIS 的 Brain 运行规程，给我原文位置和关键段落。
- 总结：总结这个任务的决定、结果和证据，先给我预览。
- 日报和周报：预览我今天的工作日报。或：预览本周周报，按已完成事项和待推进事项整理。"""


def digest(value):
    return hashlib.sha256(setup_environment.json_bytes(value)).hexdigest()


def read_state(root):
    path = root / '.local/onboarding.json'
    state = environment.read_object(path) if path.exists() else {}
    if state and state.get('version') != PROTOCOL:
        raise ValueError('Unsupported onboarding state')
    return state


def local_settings(root):
    path = root / setup_environment.ENVIRONMENT_REL
    return environment.read_object(path) if path.exists() else {'version': 1}


def status(root):
    settings = local_settings(root)
    if settings.get('version') != 1:
        raise ValueError('Unsupported local environment version')
    activation = settings.get('onboarding', {})
    if not isinstance(activation, dict) or (
            'activated' in activation and type(activation['activated']) is not bool):
        raise ValueError('Invalid onboarding activation field')
    if activation.get('activated') is True:
        return {'stage': 'activated'}
    state = read_state(root)
    return {key: value for key, value in state.items() if key not in ('proof', 'change_plan')} | {
        'stage': state.get('stage', 'start')
    }


def save(root, state):
    setup_environment.atomic_write_bytes(root / '.local/onboarding.json',
                                         setup_environment.json_bytes({'version': PROTOCOL, **state}))


def software():
    locations = [Path(os.environ[key]) / relative for key, relative in (
        ('LOCALAPPDATA', 'Obsidian/Obsidian.exe'), ('PROGRAMFILES', 'Obsidian/Obsidian.exe'),
        ('LOCALAPPDATA', 'Programs/Obsidian/Obsidian.exe'), ('PROGRAMFILES(X86)', 'Obsidian/Obsidian.exe'))
        if os.environ.get(key)]
    if os.name == 'nt':
        import winreg

        uninstall = r'Software\Microsoft\Windows\CurrentVersion\Uninstall'
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, uninstall, 0, winreg.KEY_READ | view) as registry:
                        for index in range(winreg.QueryInfoKey(registry)[0]):
                            try:
                                name = winreg.EnumKey(registry, index)
                                with winreg.OpenKey(registry, name) as entry:
                                    label = winreg.QueryValueEx(entry, 'DisplayName')[0]
                                    if label != 'Obsidian':
                                        continue
                                    icon = winreg.QueryValueEx(entry, 'DisplayIcon')[0]
                                    candidate = Path(os.path.expandvars(icon.split(',')[0].strip('" ')))
                                    if candidate.is_absolute() and candidate.name.lower() == 'obsidian.exe':
                                        locations.append(candidate)
                            except OSError:
                                continue
                except OSError:
                    continue
    executable = which('Obsidian.exe') or next((str(p) for p in locations if p.is_file()), None)
    return {'executable': executable, 'official_download': 'https://obsidian.md/download'}


def fixed_drives():
    if os.name != 'nt':
        return []
    import ctypes
    kernel = ctypes.windll.kernel32
    drive_mask = kernel.GetLogicalDrives()
    drives = []
    for index, letter in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
        drive = Path(letter + ':\\')
        if drive_mask & (1 << index) and kernel.GetDriveTypeW(str(drive)) == 3:
            try:
                drives.append((drive, disk_usage(drive).free))
            except OSError:
                continue
    return sorted(drives, key=lambda item: (-item[1], str(item[0])))


def can_add_directory(path):
    if os.name != 'nt':
        return os.access(path, os.W_OK)
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32')
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    handle = create(str(path), 4, 7, None, 3, 0x02000000, None)
    if handle == ctypes.c_void_p(-1).value:
        return False
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle(handle)
    return True


def registered_vaults():
    appdata = os.environ.get('APPDATA')
    if not appdata:
        return []
    path = Path(appdata) / 'obsidian/obsidian.json'
    if not path.is_file():
        return []
    entries = environment.read_object(path).get('vaults', {})
    if not isinstance(entries, dict):
        raise ValueError('Invalid Obsidian vault registry')
    return [entry['path'] for entry in entries.values() if isinstance(entry, dict)
            and isinstance(entry.get('path'), str)]


def discovery(root):
    selected, source = environment.vault_environment()
    locations = []
    diagnostics = []
    if selected is not None:
        path = environment.absolute_path(selected, environment.VAULT_ENV)
        if not path.is_dir():
            raise ValueError('Invalid JARVIS_VAULT_ROOT. Correct the selected path before onboarding.')
        locations.append((path, source, True))
    legacy = local_settings(root).get('vault_root')
    if isinstance(legacy, str) and Path(legacy).is_absolute() and selected is None:
        locations.append((Path(legacy), 'legacy_local_file', True))
    try:
        locations.extend((Path(path), 'obsidian_registry', True) for path in registered_vaults())
    except ValueError as exc:
        diagnostics.append(str(exc))
    drives = fixed_drives()
    common = [Path.home() / 'Documents', Path.home() / 'Desktop']
    if os.environ.get('OneDrive'):
        common.append(Path(os.environ['OneDrive']) / 'Documents')
    for parent in [*common, *(drive for drive, _ in drives)]:
        locations.extend((parent / name, 'common_path', False) for name in ('个人知识库', 'Obsidian', 'Obsidian Vault'))
        if parent in common and parent.is_dir():
            try:
                locations.extend((path, 'common_path', False) for path in parent.iterdir()
                                 if not path.is_symlink() and (path / '.obsidian').is_dir())
            except OSError:
                diagnostics.append(f'Cannot inspect {parent}')
    candidates = {}
    for path, origin, known in locations:
        if not path.is_absolute():
            continue
        path = path.resolve()
        if path.is_dir() and (known or (path / '.obsidian').is_dir()):
            row = candidates.setdefault(path, {'name': path.name or path.anchor,
                                               'path': str(path), 'sources': [],
                                               'changes': '预览缺项，获批后补齐并配置环境变量'})
            if origin not in row['sources']:
                row['sources'].append(origin)
    proposals = []
    for drive, free in drives:
        path = drive / '个人知识库'
        available = not os.path.lexists(path) and can_add_directory(drive)
        proposals.append({'path': str(path), 'free_bytes': free, 'available': available,
                          'status': ('available' if available else
                                     'existing_vault' if path.resolve() in candidates else
                                     'occupied' if os.path.lexists(path) else 'parent_not_writable')})
    return {'candidates': list(candidates.values()), 'diagnostics': diagnostics,
            'new_vault': {'name': '个人知识库', 'source': 'fixed_drive_free_space',
                          'default': next((item['path'] for item in proposals if item['available']), None),
                          'drives': proposals, 'custom_path': True,
                          'changes': '新建目录、写入 Brain 种子和配置环境变量'},
            'obsidian': software()}


def managed_paths(root):
    registry = environment.read_object(root / '.codex/obsidian-kb.json')
    project_root = registry['project']['root']
    directories = init_vault.planned_folders()
    files = [str(path) for _, path in init_vault.seed_files()]
    files.append(f'{project_root}/00_项目索引.md')
    return registry, directories, files


def directory_identity(path):
    if path.resolve() != path or not path.is_dir():
        raise ValueError('Destination is missing or redirected')
    stat = path.stat()
    return [stat.st_dev, stat.st_ino]


def change_plan(root, path, kind, actual, *, resuming=False):
    if kind == 'new' and not resuming and os.path.lexists(path):
        raise ValueError('New vault target is occupied. Choose an existing vault or another name.')
    if kind == 'new' and not resuming and (not path.parent.is_dir() or not can_add_directory(path.parent)):
        raise ValueError('New vault requires an existing writable parent directory.')
    if kind == 'existing' and not path.is_dir():
        raise ValueError('Selected existing vault is unavailable.')
    if actual and environment.absolute_path(actual, 'connector_vault') != path:
        raise ValueError('Connected Obsidian vault differs from the selected vault.')
    process = os.environ.get(environment.VAULT_ENV)
    if process is not None and environment.absolute_path(process, environment.VAULT_ENV) != path:
        raise ValueError('The process JARVIS_VAULT_ROOT points elsewhere. Reconcile the host override first.')
    shared, directories, files = managed_paths(root)
    required_dirs = [*directories, *(str(Path(rel).parent) for rel in files)]
    missing_dirs, missing_files = [], []
    for rel in sorted(set(required_dirs)):
        item = environment.relative_to(path, rel, 'Brain folder')
        if item != path / rel or (os.path.lexists(item) and not item.is_dir()):
            raise ValueError(f'Brain folder is redirected or obstructed: {rel}')
        if not item.is_dir():
            missing_dirs.append(rel)
    for rel in sorted(set(files)):
        item = environment.relative_to(path, rel, 'Brain seed')
        if item != path / rel or (os.path.lexists(item) and not item.is_file()):
            raise ValueError(f'Brain seed is redirected or obstructed: {rel}')
        if not item.is_file():
            missing_files.append(rel)
    selection, source = environment.vault_environment()
    projects = [project['id'] for project in shared['project_registry']['projects']
                if project['id'] == shared['project']['id'] or
                environment.relative_to(path, project['root'], 'registered project').is_dir()]
    return {'path': str(path), 'kind': kind, 'connector': actual, 'directories_to_create': missing_dirs,
            'files_to_create': missing_files, 'projects': projects, 'configured_vault': selection,
            'configured_source': source, 'environment_baseline': digest(local_settings(root)),
            'destination_identity': directory_identity(path) if path.is_dir() else None,
            'seed_baseline': digest({str(relative): hashlib.sha256(source.read_bytes()).hexdigest()
                                     for source, relative in init_vault.seed_files()}),
            'registry_baseline': digest(shared),
            'actions': ['create missing paths only', 'persist JARVIS_VAULT_ROOT',
                        'configure local environment and Brain Router']}


def init_brain(root, path):
    config = environment.read_object(root / '.codex/obsidian-kb.json')
    init_vault.initialize(path)
    project = config['project']
    index = environment.relative_to(path, project['root'] + '/00_项目索引.md', 'JARVIS index')
    try:
        with index.open('x', encoding='utf-8') as stream:
            stream.write('---\ntitle: "JARVIS 项目索引"\nstatus: active\n---\n'
                         '# JARVIS 项目索引\n\n- [[Brain v1 运行规程]]\n')
    except FileExistsError:
        pass
    config['project_registry']['projects'] = [
        item for item in config['project_registry']['projects']
        if environment.relative_to(path, item['root'], 'registered project').is_dir()
    ]
    brain_router.validate_registry(config, path)
    router_config = brain_router.vault_router_file(root, path)
    if not router_config.exists() or environment.read_object(router_config) != config:
        setup_environment.atomic_write_bytes(router_config, setup_environment.json_bytes(config))


def verify_brain(root, path, connector):
    resolved = environment.resolve_environment(root, connector)
    environment.require_write_ready(resolved)
    if Path(resolved['vault_root']) != path:
        raise ValueError('Active vault changed')
    config = brain_router.load_registry(brain_router.router_config_path(resolved), path)
    health = brain_router.scope_health(config, path)
    composite = environment.relative_to(path, '03 wiki/综合', 'Brain synthesis')
    jarvis = next(item for item in health['projects'] if item['id'] == 'jarvis')
    if not health['ok'] or not jarvis['index_exists'] or not composite.is_dir():
        raise ValueError('Brain scopes are incomplete')
    query = 'Brain v1 运行规程'
    matches = brain_router.build_project_context(config, path, query, 8)['results']
    wanted = '05 规则/JARVIS/Brain v1 运行规程.md'
    match = next((item for item in matches if item['path'] == wanted), None)
    if not match:
        raise ValueError('Router did not retrieve the Brain operating guide')
    original = environment.relative_to(path, wanted, 'Router result').read_text(encoding='utf-8-sig')
    if not original.strip() or not match.get('excerpt', '').strip():
        raise ValueError('Router result has no readable source text')
    return {'path': wanted, 'query': query, 'source_sha256': hashlib.sha256(original.encode()).hexdigest(),
            'excerpt': match['excerpt'], 'health': health}


def execute(args, root):
    command = args.command
    if command == 'status':
        return status(root)
    if command == 'discover':
        return discovery(root)
    state = read_state(root)
    if command == 'restart':
        if args.confirm != 'restart':
            raise ValueError('Explicit restart confirmation required')
        settings = local_settings(root)
        if 'onboarding' in settings:
            del settings['onboarding']
            setup_environment.atomic_write_bytes(root / setup_environment.ENVIRONMENT_REL,
                                                 setup_environment.json_bytes(settings))
        save(root, {'stage': 'start'})
        return {'stage': 'start'}
    if status(root)['stage'] == 'activated':
        return {'stage': 'activated'}
    if command == 'pause':
        save(root, state | {'paused': True})
        return status(root)
    if command == 'resume':
        discovery(root)
        save(root, state | {'paused': False})
        return status(root)
    if state.get('paused'):
        raise ValueError('Onboarding is paused. Resume only at the user’s request.')
    if command == 'start':
        if state.get('stage', 'start') != 'start':
            return status(root)
        if not args.request_ref.strip():
            raise ValueError('Provide a conversation locator for the original request')
        try:
            profile = load_profile(root / 'up.json')
        except (OSError, ValueError):
            profile = {'status': 'unavailable'}
        profile_status = profile['status']
        state = {'stage': 'nickname' if profile_status == 'needs_initialization' else 'selection',
                 'request_ref': args.request_ref, 'profile_status': profile_status}
        if profile_status == 'ready':
            state['nickname'] = profile['nickname']
        save(root, state)
        return status(root)
    if command == 'nickname':
        if state.get('stage') != 'nickname':
            raise ValueError('Nickname step is not pending')
        if not args.skip and load_profile(root / 'up.json')['status'] != 'ready':
            raise ValueError('Save the nickname using update_profile.py first')
        state.update(stage='selection', nickname_skipped=args.skip)
        save(root, state)
        return status(root)
    if command == 'select':
        if state.get('stage') not in ('selection', 'selected', 'preparing', 'verified', 'display'):
            raise ValueError('Start onboarding before choosing a vault')
        path = environment.absolute_path(args.path, 'selected vault')
        discover = discovery(root)
        if args.kind == 'existing' and not any(Path(c['path']) == path for c in discover['candidates']):
            if not (path / '.obsidian').is_dir():
                raise ValueError('Custom existing destination must be an Obsidian vault')
        plan = change_plan(root, path, args.kind, args.connector_vault)
        state = {'stage': 'selected', 'request_ref': state['request_ref'],
                 'change_plan': plan, 'approval_code': digest(plan)}
        save(root, state)
        return {'stage': 'selected', 'change_plan': plan, 'approval_code': state['approval_code']}
    if command == 'prepare':
        if state.get('stage') not in ('selected', 'preparing') or state.get('approval_code') != args.approved:
            raise ValueError('Select a vault and obtain approval for the displayed plan first')
        approved = state['change_plan']
        path = Path(approved['path'])
        if not software()['executable']:
            raise ValueError('Install Obsidian from https://obsidian.md/download with separate authorization')
        actual = args.connector_vault
        if actual != approved['connector']:
            raise ValueError('Connector changed. Re-preview the selection.')
        if state['stage'] == 'selected':
            if change_plan(root, path, approved['kind'], actual) != approved:
                raise ValueError('Selection baseline changed. Re-preview and obtain approval again.')
            if approved['kind'] == 'new':
                path.mkdir()
            state.update(stage='preparing', directory_identity=directory_identity(path))
            save(root, state)
        else:
            if directory_identity(path) != state.get('directory_identity'):
                raise ValueError('Destination identity changed. Re-preview the selection.')
            current = change_plan(root, path, approved['kind'], actual, resuming=True)
            for field in ('seed_baseline', 'registry_baseline'):
                if current[field] != approved[field]:
                    raise ValueError('Project inputs changed. Re-preview the selection.')
            for field in ('directories_to_create', 'files_to_create', 'projects'):
                if set(current[field]) - set(approved[field]):
                    raise ValueError('Remaining changes exceed approval. Re-preview the selection.')
            selected, _ = environment.vault_environment()
            if selected not in (approved['configured_vault'], str(path)):
                raise ValueError('Vault selection changed. Re-preview the selection.')
        registered = environment.user_vault_environment()
        if registered is None or environment.absolute_path(registered, environment.VAULT_ENV) != path:
            setup_environment.initialize(root, str(path))
        else:
            setup_environment.configure(root, str(path))
        environment.require_write_ready(environment.resolve_environment(root, actual))
        init_brain(root, path)
        proof = verify_brain(root, path, actual)
        state.update(stage='verified', proof=proof)
        save(root, state)
        return {'stage': 'verified', 'proof': proof}
    if command == 'display':
        if state.get('stage') not in ('verified', 'display'):
            raise ValueError('Verify the selected vault before displaying examples')
        if state['stage'] == 'verified':
            state.update(stage='display', receipt=token_hex(4))
            save(root, state)
        return {'stage': 'display', 'message': DISPLAY,
                'reply': '已看到 ' + state['receipt']}
    if command == 'verify':
        if state.get('stage') not in ('verified', 'display'):
            raise ValueError('Prepare the approved vault first')
        plan = state['change_plan']
        if args.connector_vault != plan['connector']:
            raise ValueError('Connector changed. Re-preview the selection.')
        proof = verify_brain(root, Path(plan['path']), args.connector_vault)
        state.update(stage='verified', proof=proof)
        state.pop('receipt', None)
        save(root, state)
        return {'stage': 'verified', 'proof': proof}
    if command == 'acknowledge':
        if state.get('stage') != 'display' or args.reply != '已看到 ' + state['receipt']:
            raise ValueError('A new user turn must contain the displayed receipt phrase')
        plan = state['change_plan']
        current_proof = verify_brain(root, Path(plan['path']), args.connector_vault)
        if args.connector_vault != plan['connector'] or current_proof['source_sha256'] != state['proof']['source_sha256']:
            raise ValueError('Connector or retrieved source changed. Verify again before activation.')
        settings = local_settings(root)
        settings['onboarding'] = {'activated': True, 'flow_version': PROTOCOL,
                                  'completed_at': datetime.now(ZONE).isoformat(),
                                  'progress': 'display_confirmed', 'request_ref': state['request_ref']}
        local_path = root / setup_environment.ENVIRONMENT_REL
        setup_environment.atomic_write_bytes(local_path, setup_environment.json_bytes(settings))
        if local_settings(root) != settings:
            raise ValueError('Activation readback failed')
        return {'stage': 'activated', 'resume_request': state['request_ref']}
    raise ValueError('Unsupported command')


def main(argv=None, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('status', 'discover', 'display', 'pause', 'resume'):
        commands.add_parser(name)
    commands.add_parser('start').add_argument('--request-ref', required=True)
    commands.add_parser('nickname').add_argument('--skip', action='store_true')
    commands.add_parser('restart').add_argument('--confirm', required=True)
    select = commands.add_parser('select')
    select.add_argument('kind', choices=('existing', 'new'))
    select.add_argument('path')
    select.add_argument('--connector-vault')
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--approved', required=True)
    prepare.add_argument('--connector-vault')
    commands.add_parser('verify').add_argument('--connector-vault')
    ack = commands.add_parser('acknowledge')
    ack.add_argument('--reply', required=True)
    ack.add_argument('--connector-vault')
    args = parser.parse_args(argv)
    lock = root / '.local/onboarding.lock'
    try:
        if args.command in ('status', 'discover'):
            result = execute(args, root)
        else:
            lock.parent.mkdir(parents=True, exist_ok=True)
            with lock.open('x', encoding='utf-8') as stream:
                stream.write(str(os.getpid()))
            try:
                result = execute(args, root)
            finally:
                lock.unlink()
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({'ok': True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
