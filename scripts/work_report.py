"""Preview or create a JARVIS daily or weekly Obsidian work report."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from urllib.parse import quote

from brain_health import mask_code, split_frontmatter
from resolve_environment import ROOT, relative_to, require_write_ready, resolve_environment
from task_knowledge import markdown_files


BEIJING = timezone(timedelta(hours=8))
DAY = timedelta(days=1)
WORK_LOG = Path('02 工作记录')
KINDS = {'daily': ('日报', 'daily-report'), 'weekly': ('周报', 'weekly-report')}
OUTCOME_HEADINGS = {'结果与验证', '结果及验证', '成果与验证', '已验证成果', '结果'}
FOLLOWUP_HEADINGS = {'问题、经验与后续行动', '后续可复用做法', '下一步', '待办', '问题与风险'}
PLACEHOLDER = '区分实际验证、助手报告和用户验收。'
FILENAME_DATE = re.compile(r'^(\d{4}-\d{2}-\d{2})(?:[_\-\s]|$)')


@dataclass(frozen=True)
class Summary:
    path: Path
    date: date
    status: str
    outcome: list[str]
    followup: list[str]
    digest: str
    date_source: str


def period(kind, requested):
    if kind == 'daily':
        return requested, requested, requested.strftime('%Y-%m-%d')
    start = requested - timedelta(days=requested.weekday())
    iso_year, iso_week, _ = requested.isocalendar()
    return start, start + 6 * DAY, f'{iso_year:04d}-W{iso_week:02d}'


def output_name(kind, label):
    folder, _ = KINDS[kind]
    return WORK_LOG / folder / label.split('-')[0] / f'{label}_{folder}.md'


def iso_date(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def summary_date(path, fields):
    for field in ('completed_on', 'date'):
        recorded = iso_date(fields.get(field))
        if recorded is not None:
            return recorded, field
    match = FILENAME_DATE.match(path.name)
    if match:
        recorded = iso_date(match.group(1))
        if recorded is not None:
            return recorded, 'filename'
    return None, None


def project_matches(fields, project):
    configured = fields.get('project')
    if isinstance(configured, str) and configured.casefold() == project.casefold():
        return True
    tags = fields.get('tags') or []
    if isinstance(tags, str):
        tags = [tags]
    project_tag = f'project/{project}'.casefold()
    return any(isinstance(tag, str) and tag.strip().casefold() == project_tag for tag in tags)


def vault_path(vault, relative):
    target = relative_to(vault, relative.as_posix(), 'report path')
    if target != vault / relative:
        raise ValueError(f'Report paths must not traverse links or junctions: {relative}')
    return target


def source_lines(body):
    """Take short evidence excerpts from the supported task-summary sections."""
    outcome, followup = [], []
    target = None
    for line, visible in zip(body.splitlines(), mask_code(body).splitlines()):
        if not visible.strip():
            continue
        heading = re.match(r'^#{1,6}\s+(.+?)\s*#*$', visible)
        if heading:
            title = heading.group(1)
            target = outcome if title in OUTCOME_HEADINGS else (
                followup if title in FOLLOWUP_HEADINGS else None
            )
            continue
        excerpt = line.strip().removeprefix('- ').removeprefix('* ')
        if target is not None and len(target) < 2 and excerpt and excerpt != PLACEHOLDER:
            # Relative links belong to the source note. Keep their label in the report.
            excerpt = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', excerpt)
            excerpt = re.sub(r'\[\[([^\]]+)\]\]', lambda match: match[1].split('|')[-1], excerpt)
            if len(excerpt) > 220:
                excerpt = excerpt[:220].rstrip() + '…'
            target.append(excerpt)
    return outcome, followup


def load_summaries(environment, vault, start, end):
    configured = environment['resolved_pointer']['project']
    folder = vault_path(vault, Path(configured['root']))
    if not folder.is_dir():
        raise ValueError(f'Project task-summary directory is unavailable: {configured["root"]}')
    skipped, undated, summaries = [], [], []

    for path in sorted(markdown_files(folder, skipped, vault)):
        if path.resolve() != path or not path.is_file():
            continue
        relative = path.relative_to(vault)
        try:
            data = path.read_bytes()
            fields, body = split_frontmatter(data.decode('utf-8-sig'))
        except (OSError, UnicodeError):
            skipped.append(relative.as_posix())
            continue
        if fields.get('type') != 'task-summary' or fields.get('status') == 'rejected':
            continue
        project = fields.get('project')
        if project and (not isinstance(project, str) or project.casefold() != configured['name'].casefold()):
            continue
        recorded, date_source = summary_date(path, fields)
        if recorded is None:
            undated.append(relative.as_posix())
            continue
        if start <= recorded <= end:
            outcomes, followups = source_lines(body)
            summaries.append(Summary(relative, recorded, fields.get('status') or '',
                                     outcomes, followups, sha256(data).hexdigest(), date_source))

    return sorted(summaries, key=lambda note: (note.date, note.path)), undated, sorted(skipped)


def note_link(path):
    target = path.with_suffix('').as_posix()
    if any(char in target for char in '[]|#^'):
        label = re.sub(r'([\[\]\\])', r'\\\1', path.stem)
        return f'[{label}](/' + quote(path.as_posix()) + ')'
    return f'[[{target}|{path.stem}]]'


def daily_links(vault, project, start, end):
    folder = vault_path(vault, WORK_LOG / '日报')
    if not folder.is_dir():
        return [], []
    skipped, matches = [], []
    for path in markdown_files(folder, skipped, vault):
        if path.resolve() != path or not path.is_file():
            continue
        relative = path.relative_to(vault)
        try:
            data = path.read_bytes()
            fields, _ = split_frontmatter(data.decode('utf-8-sig'))
        except (OSError, UnicodeError):
            skipped.append(relative.as_posix())
            continue
        if fields.get('type') != 'daily-report' or fields.get('status') == 'rejected':
            continue
        if not project_matches(fields, project):
            continue
        recorded = iso_date(fields.get('period_start') or fields.get('date'))
        if recorded is None or not start <= recorded <= end:
            continue
        matches.append((recorded, relative, sha256(data).hexdigest()))
    matches.sort(key=lambda item: (item[0], item[1].as_posix()))
    return [(relative, digest) for _, relative, digest in matches], sorted(skipped)


def render(kind, label, project, start, end, today, summaries, daily):
    folder, note_type = KINDS[kind]
    title = f'{label} {folder}'
    lines = ['---', f'title: "{title}"', f'type: "{note_type}"', 'status: "active"',
             f'project: {json.dumps(project, ensure_ascii=False)}', f'updated: "{today}"',
             'updated_source: "filesystem"', f'period_start: "{start}"', f'period_end: "{end}"',
             'source: "JARVIS 工作记录"', '---', f'# {title}', '']
    if kind == 'weekly':
        lines += [f'周期为 {start} 至 {end}，按北京时间。', '']
    if summaries:
        lines += ['## 工作记录与验证', '']
        for note in summaries:
            status = f'，笔记状态为 {note.status}' if note.status else ''
            date_source = '，日期取自文件名' if note.date_source == 'filename' else ''
            lines += [f'- {note.date} {note_link(note.path)}{status}{date_source}']
            lines.extend(f'  - {excerpt}' for excerpt in note.outcome)
        lines.append('')
    followups = [note for note in summaries if note.followup]
    if followups:
        lines += ['## 问题与后续', '']
        for note in followups:
            lines += [f'- {note_link(note.path)}', *(f'  - {line}' for line in note.followup)]
        lines.append('')
    if daily:
        lines += ['## 本周日报', '', *(f'- {note_link(path)}' for path, _ in daily), '']
    return '\n'.join(lines)


def publish(target, content):
    """Publish only a complete file while preserving concurrent creations."""
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = None
    try:
        with NamedTemporaryFile(mode='wb', dir=target.parent, prefix='.report-',
                                suffix='.tmp', delete=False) as stream:
            staged = Path(stream.name)
            stream.write(content.encode('utf-8'))
        os.link(staged, target)
    finally:
        if staged is not None:
            staged.unlink()


def generate(environment, kind, requested, today, baseline=None):
    vault = Path(environment['vault_root'])
    start, end, label = period(kind, requested)
    relative = output_name(kind, label)
    target = vault_path(vault, relative)
    result = {'target': relative.as_posix(), 'start': str(start), 'end': str(end)}
    if baseline is not None:
        require_write_ready(environment)
    if target.is_file():
        return {**result, 'status': 'exists'}
    if target.exists():
        raise ValueError(f'Report target is not a file: {relative}')

    summaries, undated, skipped = load_summaries(environment, vault, start, end)
    project = environment['resolved_pointer']['project']['name']
    daily, daily_skipped = daily_links(vault, project, start, end) if kind == 'weekly' else ([], [])
    date_fallbacks = [note.path.as_posix() for note in summaries if note.date_source == 'filename']
    sources = [(note.path.as_posix(), note.digest) for note in summaries]
    sources += [(path.as_posix(), digest) for path, digest in daily]
    result.update(sources=[path for path, _ in sources], undated=undated, date_fallbacks=date_fallbacks,
                  unreadable=sorted(set(skipped + daily_skipped)))
    if not sources:
        if baseline is not None:
            raise ValueError('The approved sources are no longer available. Generate a fresh preview.')
        return {**result, 'status': 'no_records'}

    content = render(kind, label, project, start, end, today, summaries, daily)
    snapshot = json.dumps([relative.as_posix(), sources, undated, skipped, content], ensure_ascii=False)
    digest = sha256(snapshot.encode('utf-8')).hexdigest()
    if baseline is None:
        return {**result, 'status': 'preview', 'baseline': digest, 'markdown': content}
    if digest != baseline:
        raise ValueError('Report sources or preview changed. Generate a fresh preview.')
    try:
        publish(target, content)
    except FileExistsError:
        if target.is_file():
            return {**result, 'status': 'exists'}
        raise
    return {**result, 'status': 'created'}


def main(argv=None, project_root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('period', choices=KINDS)
    parser.add_argument('--date', type=date.fromisoformat, help='Beijing date YYYY-MM-DD, defaults to today')
    parser.add_argument('--connector-vault', help='Actual vault root reported by the Obsidian connector')
    parser.add_argument('--write', metavar='PREVIEW_SHA256', help='Create the file from the approved preview')
    args = parser.parse_args(argv)
    today = datetime.now(BEIJING).date()
    try:
        environment = resolve_environment(project_root, args.connector_vault)
        result = generate(environment, args.period, args.date or today, today, args.write)
    except (OSError, ValueError, OverflowError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
