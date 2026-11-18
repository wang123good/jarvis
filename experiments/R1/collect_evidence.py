"""Read-only bounded audit for the first task-driven JARVIS round."""
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

OUT = Path(__file__).resolve().parent
PROJECT = Path('D:/个人知识库/01_项目/JARVIS')
VAULT = PROJECT.parents[1]
DOC = Path('D:/codex-project/JARVIS/架构方案/JARVIS 管家 Worker Skill 与图书管理员架构设计 v1.5.docx')
REG = PROJECT / '40_任务经验注册表/experience-registry.json'
DESIGN = PROJECT / '10_设计笔记/JARVIS Agentic 架构设计笔记.md'


def fingerprint(p):
    b = p.read_bytes()
    return {'path': str(p), 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DOC) as z:
        root = ET.fromstring(z.read('word/document.xml'))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paragraphs = [''.join(t.text or '' for t in p.findall('.//w:t', ns)) for p in root.findall('.//w:p', ns)]
    (OUT / 'architecture-v1.5.txt').write_text('\n'.join(paragraphs), encoding='utf-8')
    registry = json.loads(REG.read_text(encoding='utf-8-sig'))
    skill_roots = [Path('C:/Users/10013463/.codex/skills'), Path('C:/Users/10013463/.agents/skills')]
    ids = sorted({s['skill_id'] for e in registry['experiences'] for s in e.get('skill_links', [])})
    skills = [{'skill_id': sid, 'expected_versions': sorted({s['skill_version'] for e in registry['experiences'] for s in e.get('skill_links', []) if s['skill_id'] == sid}), 'exact_directory_matches': [str(r / sid / 'SKILL.md') for r in skill_roots if (r / sid / 'SKILL.md').is_file()]} for sid in ids]
    notes = []
    inputs = [fingerprint(DOC), fingerprint(REG), fingerprint(DESIGN)]
    for e in registry['experiences']:
        p = VAULT / e['obsidian_path']
        exists = p.is_file()
        updated = None
        if exists:
            text = p.read_text(encoding='utf-8-sig')
            front = text.split('---', 2)[1]
            updated = next((l.split(':', 1)[1].strip() for l in front.splitlines() if l.startswith('updated:')), None)
            inputs.append(fingerprint(p))
        notes.append({'experience_id': e['experience_id'], 'note_exists': exists, 'registry_last_updated': e.get('last_updated'), 'note_updated': updated, 'date_match': e.get('last_updated') == updated, 'status': e['status'], 'call_frequency': e['call_frequency']})
    report = {'date': '2026-11-18', 'scope': 'v1.5 XML text, seven registry samples, exact Skill directories in two local roots', 'experience_count': len(notes), 'notes': notes, 'skills': skills, 'exact_skill_matches': sum(bool(s['exact_directory_matches']) for s in skills), 'skill_ids_checked': len(skills), 'limitations': ['Exact directory check is not an exhaustive semantic search of every installed plugin', 'No Skill version compatibility or task reuse tested', 'DOCX text extracted without visual layout QA', 'No actual independent Worker invoked in this direct-mode round'], 'inputs': inputs}
    (OUT / 'evidence-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['experience_count', 'exact_skill_matches', 'skill_ids_checked', 'skills', 'notes']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
