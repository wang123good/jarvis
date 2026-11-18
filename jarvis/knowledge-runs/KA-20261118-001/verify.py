"""Validate the delivered topic files without modifying the vault."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VAULT = Path('D:/个人知识库')
TOPIC = VAULT / '02_领域/移动影像软硬件方案设计'
EXPECTED = ['00_主题地图.md', '10_方案设计工作台.md', '20_资料与问题清单.md']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

checks = []
unresolved = []
for name in EXPECTED:
    path = TOPIC / name
    checks.append({'check': name + ' exists', 'ok': path.is_file()})
    if not path.is_file():
        continue
    content = path.read_text(encoding='utf-8-sig')
    front = content.split('---', 2)[1] if content.startswith('---') else ''
    checks.append({'check': name + ' draft', 'ok': bool(re.search(r'^status:\s*[\"\x27]?draft[\"\x27]?\s*$', front, re.M))})
    checks.append({'check': name + ' no template placeholders', 'ok': '{{' not in content and '<knowledge-card>' not in content})
    for link in re.findall(r'\[\[([^\]]+)\]\]', content):
        target = link.split('|')[0].split('#')[0]
        if not target:
            continue
        candidates = [VAULT / target, TOPIC / target]
        if not any(p.is_file() or p.with_suffix('.md').is_file() for p in candidates):
            unresolved.append({'note': name, 'link': target})
checks.append({'check': 'all delivered wikilinks resolve', 'ok': not unresolved})
for item in json.loads((ROOT / 'baseline.json').read_text(encoding='utf-8-sig')):
    checks.append({'check': 'preserved ' + item['path'], 'ok': sha(Path(item['path'])) == item['sha256']})
checks.append({'check': 'run report exists', 'ok': (ROOT / 'run-report.md').is_file()})
result = {'ok': all(c['ok'] for c in checks), 'checks': checks, 'unresolved': unresolved,
          'scope': 'file structure, draft metadata, links and baseline preservation; no technical or GUI validation',
          'files': [{'path': str(TOPIC / n), 'sha256': sha(TOPIC / n)} for n in EXPECTED if (TOPIC / n).is_file()]}
(ROOT / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result['ok'] else 1)
