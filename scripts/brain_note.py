"""Preview or create a Brain note without inheriting a template's active status."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

from resolve_environment import resolve_environment, require_write_ready, relative_to


KINDS = {'草稿': 'draft', '任务总结': 'task-summary', '任务契约': 'task-summary',
         '决策': 'decision', '日报': 'daily-report', '周报': 'weekly-report',
         'wiki主题': 'topic', '规则': 'rule', '业务对话': 'conversation'}


def render_note(template, title, kind, source=None, now=None):
    now = now or datetime.now(timezone(timedelta(hours=8)))
    match = re.match(r'\A---\r?\n.*?\r?\n---(?:\r?\n|$)', template, re.S)
    body = template[match.end():] if match else template
    body = re.sub(r'> \[!important\] 实例属性\r?\n(?:>[^\n]*\n)*', '', body)
    body = body.replace('{{title}}', title).replace('{{date}}', now.strftime('%Y-%m-%d')).replace('{{time}}', now.strftime('%H:%M'))
    metadata = {'title': title, 'type': kind,
                'status': 'inbox' if kind == 'draft' else 'archived' if kind == 'conversation' else 'review',
                'updated': now.strftime('%Y-%m-%d'), 'updated_source': 'user',
                'brain_schema': '1.0', 'confidence': 'unknown', 'authority': 'personal'}
    if source:
        metadata['source'] = source
    else:
        metadata['source_gap'] = '待填写实际来源；新建笔记不构成已复核知识'
    return '---\n' + '\n'.join(key + ': ' + json.dumps(value, ensure_ascii=False) for key, value in metadata.items()) + '\n---\n' + body


def proposal(environment, template_name, title, destination, source=None):
    vault = Path(environment['vault_root'])
    target = relative_to(vault, destination, 'note destination')
    if target.suffix != '.md' or not destination.startswith(('01 草稿/', '02 工作记录/', '03 wiki/', '05 规则/', '06 归档/')):
        raise ValueError('Choose a Markdown business-note destination inside the approved vault folders')
    if target.exists():
        raise ValueError('Target already exists; user content will not be overwritten')
    template_path = vault / '04 模板' / (template_name + '.md')
    raw = template_path.read_bytes()
    text = render_note(raw.decode('utf-8-sig'), title, KINDS[template_name], source)
    value = {'target': str(target), 'template': str(template_path),
             'template_sha256': hashlib.sha256(raw).hexdigest(), 'markdown': text}
    value['baseline'] = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', required=True, choices=KINDS)
    parser.add_argument('--title', required=True)
    parser.add_argument('--path', required=True)
    parser.add_argument('--source')
    parser.add_argument('--connector-vault')
    parser.add_argument('--write', metavar='APPROVED_BASELINE')
    args = parser.parse_args(argv)
    try:
        environment = resolve_environment(connector_vault=args.connector_vault)
        value = proposal(environment, args.template, args.title, args.path, args.source)
        if args.write:
            require_write_ready(environment)
            if args.write != value['baseline']:
                raise ValueError('Preview or template changed; request a new preview')
            target = Path(value['target'])
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('x', encoding='utf-8') as stream:
                stream.write(value['markdown'])
            value['status'] = 'created'
            value['sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
        else:
            value['status'] = 'preview'
        print(json.dumps(value, ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
