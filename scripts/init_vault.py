"""Create the Brain v1 vault skeleton without overwriting user files."""

import argparse
from datetime import date
import json
from pathlib import Path


FOLDERS = [
    '01 草稿',
    '01 草稿/历史收件箱',
    '01 草稿/迁移待分类',
    '02 工作记录',
    '02 工作记录/任务总结',
    '02 工作记录/任务总结/JARVIS',
    '02 工作记录/任务总结/历史项目',
    '02 工作记录/Brain运行日志',
    '02 工作记录/日报',
    '02 工作记录/周报',
    '03 wiki',
    '03 wiki/主题',
    '03 wiki/主题/AI-Agent',
    '03 wiki/主题/Loop-Engineering',
    '03 wiki/主题/Obsidian使用技巧',
    '03 wiki/参考资料',
    '03 wiki/参考资料/AI-Agent',
    '03 wiki/参考资料/Loop-Engineering',
    '03 wiki/参考资料/Obsidian使用技巧',
    '03 wiki/综合',
    '03 wiki/索引',
    '03 wiki/视图',
    '04 模板',
    '04 模板/历史模板',
    '05 规则',
    '05 规则/JARVIS',
    '05 规则/决策',
    '06 归档',
    '99 附件',
]

BRAIN_FILE_SUFFIXES = {'.md', '.base'}


def create_file_exclusive(source: Path, target: Path, created: list[str], preserved: list[str]) -> None:
    """Create one target file without replacing an existing path."""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open('xb') as stream:
            stream.write(source.read_bytes())
        created.append(str(target))
    except (FileExistsError, IsADirectoryError):
        preserved.append(str(target))


def initialize(vault):
    vault = Path(vault).expanduser().resolve()
    vault.mkdir(parents=True, exist_ok=True)

    created_dirs = []
    folders = [*FOLDERS, f'02 工作记录/日报/{date.today().year}',
               f'02 工作记录/周报/{date.today().year}']
    for folder in folders:
        target = vault / folder
        if not target.exists():
            created_dirs.append(str(target))
        target.mkdir(parents=True, exist_ok=True)

    created, preserved = [], []
    project_root = Path(__file__).resolve().parents[1]
    template_root = project_root / 'templates/vault'
    templates = sorted(template_root.glob('*.md'))
    if not templates:
        raise RuntimeError(f'No vault templates found in: {template_root}')
    for source in templates:
        create_file_exclusive(source, vault / '04 模板' / source.name, created, preserved)

    seed_root = project_root / 'templates/brain'
    if not seed_root.is_dir():
        raise RuntimeError(f'Missing Brain v1 seed directory: {seed_root}')
    seeds = sorted(
        (path for path in seed_root.rglob('*') if path.is_file()
         and path.suffix.lower() in BRAIN_FILE_SUFFIXES),
        key=lambda path: path.relative_to(seed_root).as_posix(),
    )
    if not seeds:
        raise RuntimeError(f'No Brain v1 seed files found in: {seed_root}')
    for source in seeds:
        relative = source.relative_to(seed_root)
        create_file_exclusive(source, vault / relative, created, preserved)

    return {
        'vault': str(vault),
        'created_dirs': created_dirs,
        'created': created,
        'preserved': preserved,
    }

def main(argv=None, project_root=None):
    import importlib.util
    spec = importlib.util.spec_from_file_location('environment_reader', Path(__file__).with_name('resolve_environment.py'))
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', help='Optional explicit target; must match the local configuration')
    parser.add_argument('--connector-vault', help='Actual root reported by the connected Obsidian tool')
    args = parser.parse_args(argv)
    try:
        resolved = reader.resolve_environment(project_root or Path(__file__).resolve().parents[1], args.connector_vault)
        reader.require_write_ready(resolved)
        if args.vault is not None and reader.absolute_path(args.vault, '--vault') != Path(resolved['vault_root']):
            raise reader.EnvironmentConfigError('--vault differs from the configured and connected vault; nothing written')
    except reader.EnvironmentConfigError as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(initialize(resolved['vault_root']), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
