"""Check R1's declared local outputs, links, source preservation and figures."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VAULT = Path('D:/个人知识库')
PROJECT = VAULT / '01_项目/JARVIS'
OUTPUTS = [
    PROJECT / '20_实验计划/JARVIS Agentic 闭环实验计划 v0.3.md',
    PROJECT / '30_实验记录/2026-11-18 R1 任务闭环实验卡.md',
    PROJECT / '60_实验交付/2026-11-18 R1 JARVIS 实施就绪评审.md',
]


def main():
    audit = json.loads((ROOT / 'evidence-audit.json').read_text(encoding='utf-8'))
    errors = []
    for entry in audit['inputs']:
        p = Path(entry['path'])
        if hashlib.sha256(p.read_bytes()).hexdigest() != entry['sha256']:
            errors.append('Source changed: ' + str(p))
    for path in OUTPUTS:
        text = path.read_text(encoding='utf-8')
        if not text.startswith('---\n') or '\n---\n' not in text[4:]:
            errors.append('Frontmatter missing: ' + str(path))
        for target in re.findall(r'\[\[([^\]|]+)(?:\|[^\]]*)?\]\]', text):
            dest = VAULT / target.split('#')[0]
            if not dest.exists() and not Path(str(dest) + '.md').exists():
                errors.append('Unresolved link: ' + target)
    mapping = json.loads((ROOT / 'mapping-validation.json').read_text(encoding='utf-8'))
    figures = {'experience_count': audit['experience_count'], 'skill_ids_checked': audit['skill_ids_checked'], 'exact_skill_matches': audit['exact_skill_matches'], 'date_mismatches': sum(not n['date_match'] for n in audit['notes']), 'mapping_ok': mapping['ok']}
    if figures != {'experience_count': 7, 'skill_ids_checked': 7, 'exact_skill_matches': 0, 'date_mismatches': 2, 'mapping_ok': True}:
        errors.append('Report figures require revision')
    for name in ['registry-query.json', 'registry-librarian.json', 'registry-planning.json', 'evidence-audit.json']:
        json.loads((ROOT / name).read_text(encoding='utf-8'))
    files = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in OUTPUTS}
    report = {'date': '2026-11-18', 'ok': not errors, 'figures': figures, 'source_files_unchanged': not any(e.startswith('Source changed:') for e in errors), 'output_sha256': files, 'errors': errors, 'limits': ['Structural and claim-figure checks only; no Obsidian UI rendering tested', 'No human acceptance inferred']}
    (ROOT / 'delivery-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'ok': report['ok'], 'errors': errors, 'figures': figures}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
