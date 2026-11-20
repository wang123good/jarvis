"""Create missing vault folders/templates without overwriting user files."""
import argparse
import json
from pathlib import Path

FOLDERS = ['01 草稿', '02 工作记录/任务总结', '02 工作记录/日报',
           '02 工作记录/周报', '03 wiki', '04 模板', '05 规则', '06 归档', '99 附件']

def initialize(vault):
    vault = Path(vault).expanduser().resolve()
    vault.mkdir(parents=True, exist_ok=True)
    for folder in FOLDERS:
        (vault / folder).mkdir(parents=True, exist_ok=True)
    created, preserved = [], []
    assets = Path(__file__).resolve().parents[1] / 'templates/vault'
    for source in sorted(assets.glob('*.md')):
        target = vault / '04 模板' / source.name
        try:
            with target.open('xb') as stream:
                stream.write(source.read_bytes())
            created.append(str(target))
        except FileExistsError:
            preserved.append(str(target))
    home = vault / '首页.md'
    try:
        with home.open('x', encoding='utf-8') as stream:
            stream.write('# 知识库首页\n\n'
                         '- [[01 草稿/草稿说明|草稿入口]]\n'
                         '- [[02 工作记录/工作记录|工作记录]]\n'
                         '- [[03 wiki/wiki索引|wiki]]\n'
                         '- [[05 规则/知识库使用规则|使用规则]]\n\n'
                         '待处理资料进入草稿；任务形成总结；通用知识整理到 wiki；'
                         '业务对话单文件保存在归档。模板位于 04 模板。\n')
        created.append(str(home))
    except FileExistsError:
        preserved.append(str(home))
    seeds = {
        '01 草稿/草稿说明.md': '# 草稿\n\n待整理资料与未确认内容；保留来源和待决问题。\n',
        '02 工作记录/工作记录.md': '# 工作记录\n\n任务总结、日报与周报分别存放；按需生成，不自动填造工作成果。\n',
        '03 wiki/wiki索引.md': '# wiki\n\n组织跨任务复用的主题知识，链接来源，保留状态与不确定性。\n',
        '05 规则/知识库使用规则.md': '# 知识库使用规则\n\n草稿 → 工作记录 → wiki；业务对话保存在 06 归档。\n\n'
        '归档命名：年月日_任务名称_对话名.md，日期按北京时间；同名追加 _02。'
        '仅保存可读业务对话，不复制来源 JSON、运行日志或附件。\n\n'
        '日报按北京时间，周报按周一至周日、ISO 周编号并标起止日期。'
        '模板复制不覆盖已有文件；生成和迁移须有明确范围与授权。\n',
    }
    for rel, content in seeds.items():
        target = vault / rel
        try:
            with target.open('x', encoding='utf-8') as stream:
                stream.write(content)
            created.append(str(target))
        except FileExistsError:
            preserved.append(str(target))
    return {'vault': str(vault), 'created': created, 'preserved': preserved}

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
