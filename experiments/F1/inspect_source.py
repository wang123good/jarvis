import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VAULT = Path('D:/个人知识库')
THREAD = '01a1e893-ce4d-7ff2-bf55-00845bf74786'


def main():
    state = json.loads(Path('D:/codex-project/JARVIS/.codex/obsidian-links.json').read_text(encoding='utf-8'))
    t = state['threads'][THREAD]
    base = (VAULT / t['raw_note']).parent
    selected = []
    needles = ['注册表中未找到对应skill的经验', '按B方案修改实验计划', '按 B 方案修改实验计划']
    for number, line in enumerate((base / 'source.jsonl').read_text(encoding='utf-8').splitlines(), 1):
        r = json.loads(line)
        p = r.get('payload', {})
        if r.get('type') == 'response_item' and p.get('type') == 'message' and p.get('role') == 'user':
            content = p.get('content', [])
            text = '\n'.join(x.get('text', '') for x in content if isinstance(x, dict))
            if any(n in text for n in needles) and len(text) < 1500:
                selected.append({'record': number, 'text': text})
    skills = []
    for name in ['report-analysis-loop', 'codex-memory-sync', 'obsidian-curator', 'obsidian-kb']:
        p = Path('C:/Users/10013463/.codex/skills') / name / 'SKILL.md'
        b = p.read_bytes()
        skills.append({'skill_id': name, 'path': str(p), 'sha256': hashlib.sha256(b).hexdigest(), 'version': None, 'version_method': 'content-sha256; no semantic version inferred'})
    facts = {'thread': THREAD, 'source_raw': t['raw_note'], 'source_hash': t['source_hash'], 'source_jsonl': str(base / 'source.jsonl'), 'coverage': t['coverage'], 'selected_user_records': selected, 'skills': skills}
    (ROOT / 'source-evidence.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(facts, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
