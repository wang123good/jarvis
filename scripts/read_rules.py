"""Read the project policies selected by JARVIS for the current request."""

import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = (
    '架构方案/JARVIS 管家Agent职责定义 v0.1.md'
    '#契约就绪、变更传播与恢复规程'
)
LIFECYCLE = 'docs/task-lifecycle.md'
ROUTES = {
    'task': ('docs/rules/task.md', 'docs/task-knowledge.md', CONTRACT),
    'intent': ('docs/rules/intent.md',),
    'new': ('docs/rules/session.md', LIFECYCLE, 'templates/task.md', 'templates/task-session-handoff.md'),
    'resume': ('docs/rules/session.md', 'docs/rules/resume.md', LIFECYCLE),
    'lifecycle': ('docs/rules/session.md', LIFECYCLE),
    'loop': ('docs/rules/loop.md', 'docs/task-loop.md', 'config/defaults.json'),
    'delivery': ('docs/rules/session.md', 'docs/rules/delivery.md', LIFECYCLE),
    'worker': ('docs/rules/worker.md',),
    'release': ('docs/rules/release.md',),
    'knowledge': ('docs/rules/knowledge.md',),
    'cleanup': ('docs/rules/cleanup.md',),
    'retention': ('docs/rules/retention.md', LIFECYCLE, 'docs/environment.md'),
    'profile': ('docs/rules/profile.md', 'docs/user-profile.md'),
}


def read_document(reference, root=ROOT):
    path, _, heading = reference.partition('#')
    content = (root / path).read_text(encoding='utf-8')
    if not heading:
        return content
    match = re.search(r'^ {0,3}(#{1,6}) ' + re.escape(heading) + r'[ \t]*$', content, re.M)
    if match is None:
        raise ValueError(f'Missing heading: {reference}')
    body = content[match.end():]
    end = re.search(r'^ {0,3}#{1,' + str(len(match[1])) + r'} ', body, re.M)
    return content[match.start():match.end() + end.start()] if end else content[match.start():]


def references(routes):
    return list(dict.fromkeys(ref for route in routes for ref in ROUTES[route]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('routes', nargs='+', choices=ROUTES)
    args = parser.parse_args()
    try:
        output = [
            f'--- {ref} ---\n{read_document(ref).rstrip()}'
            for ref in references(args.routes)
        ]
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    print('\n\n'.join(output))


if __name__ == '__main__':
    main()
