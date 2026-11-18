import hashlib
import json
import shutil
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as E

ROOT = Path('D:/codex-project/JARVIS')
OUT = ROOT / 'experiments/W1'
INPUT = OUT / 'inputs'


def main():
    INPUT.mkdir(parents=True, exist_ok=True)
    for name, source in [('steward-entry.md', ROOT / 'AGENTS.md'), ('steward-defaults.json', ROOT / 'jarvis/defaults.json'), ('task-template.md', ROOT / 'jarvis/task-template.md')]:
        target = INPUT / name
        if target.exists():
            raise RuntimeError('Do not overwrite a frozen input: ' + name)
        shutil.copy2(source, target)
    doc = ROOT / '架构方案/JARVIS 管家 Worker Skill 与图书管理员架构设计 v1.5.docx'
    with ZipFile(doc) as z:
        xml = E.fromstring(z.read('word/document.xml'))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    ps = [''.join(t.text or '' for t in p.findall('.//w:t', ns)) for p in xml.findall('.//w:p', ns)]
    picked = []
    for a, b in [('二 角色边界', '三 目标架构'), ('六 规划与检索流程', '七 技术可行性'), ('附录 A 管家 Agent 控制面职责', None)]:
        start = ps.index(a)
        end = ps.index(b, start + 1) if b else len(ps)
        picked.extend(ps[start:end])
    (INPUT / 'architecture-excerpts.md').write_text('# v1.5 相关正文摘录\n\n仅为原文文本摘录，不包含图示或整份文档。\n\n' + '\n'.join(picked), encoding='utf-8')
    files = []
    for p in INPUT.iterdir():
        b = p.read_bytes()
        files.append({'path': str(p), 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()})
    (OUT / 'input-manifest.json').write_text(json.dumps({'files': files, 'architecture_source': str(doc), 'architecture_sha256': hashlib.sha256(doc.read_bytes()).hexdigest()}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'input_count': len(files), 'path': str(INPUT)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
