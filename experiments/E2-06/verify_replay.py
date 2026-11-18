"""Isolated E2-05 evidence-append replay; not a production librarian writer."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = Path('D:/个人知识库/01_项目/JARVIS')
REGISTRY = PROJECT / '40_任务经验注册表'
VAULT = PROJECT.parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replay(registry, notes, change):
    """Pure proposal: append reviewed evidence to existing IDs, preserving other fields."""
    if change['review'] != 'approved':
        raise ValueError('Review required')
    result, texts = copy.deepcopy(registry), dict(notes)
    ids = [e['experience_id'] for e in result['experiences']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate experience IDs')
    for eid, refs in change['append'].items():
        if eid not in ids or eid not in texts:
            raise ValueError('Unknown experience or missing note')
        record = next(e for e in result['experiences'] if e['experience_id'] == eid)
        text = texts[eid]
        start_marker, end_marker = '## 证据\n', '\n## '
        if text.count(start_marker) != 1:
            raise ValueError('Evidence heading missing or ambiguous')
        start = text.index(start_marker) + len(start_marker)
        end = text.find(end_marker, start)
        if end < 0:
            end = len(text)
        section = text[start:end]
        existing = {line[2:].strip() for line in section.splitlines() if line.startswith('- ')}
        additions = list(dict.fromkeys(ref for ref in refs if ref not in existing))
        if additions:
            texts[eid] = text[:start] + section.rstrip() + '\n' + ''.join('- ' + ref + '\n' for ref in additions) + '\n' + text[end:]
        for ref in refs:
            if ref not in record['evidence_refs']:
                record['evidence_refs'].append(ref)
    return result, texts


def main():
    live_path = REGISTRY / 'experience-registry.json'
    live_bytes = live_path.read_bytes()
    live = json.loads(live_bytes)
    before_path = REGISTRY / 'validation/backups/experience-registry.pre-e2-05.json'
    before_bytes = before_path.read_bytes()
    before = json.loads(before_bytes)
    targets = ['exp-2026-004', 'exp-2026-006']
    records = {e['experience_id']: e for e in live['experiences']}
    old_records = {e['experience_id']: e for e in before['experiences']}
    note_paths = {eid: VAULT / records[eid]['obsidian_path'] for eid in targets}
    note_bytes = {eid: path.read_bytes() for eid, path in note_paths.items()}
    notes = {eid: data.decode('utf-8-sig').replace('\r\n', '\n') for eid, data in note_bytes.items()}
    old_notes = {eid: (REGISTRY / f'validation/backups/{eid}.pre-e2-05.md').read_text(encoding='utf-8-sig') for eid in targets}
    change = {'review': 'approved', 'append': {eid: [ref for ref in records[eid]['evidence_refs'] if ref not in old_records[eid]['evidence_refs']] for eid in targets}}
    # Snapshot of actual bounded inputs, explicitly not a raw-session snapshot.
    source = {'kind': 'E2-05-reviewed-evidence-delta', 'session_id': '01a1e893-ce4d-7ff2-bf55-00845bf74786', 'change': change}
    source_bytes = json.dumps(source, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / 'source-snapshot.json').write_bytes(source_bytes)
    results = []

    def check(name, condition):
        results.append({'case': name, 'passed': bool(condition)})
        if not condition:
            raise AssertionError(name)

    out, out_notes = replay(before, old_notes, change)
    check('01_actual_delta_appended_once', all(out['experiences'][i]['evidence_refs'] == e['evidence_refs'] for i, e in enumerate(live['experiences'])) and all(all(t.count('- ' + ref + '\n') == 1 for ref in change['append'][eid]) for eid, t in out_notes.items()))
    repeated = replay(out, out_notes, change)
    check('02_repeat_has_no_changes', repeated == (out, out_notes))
    check('03_live_state_replay_no_changes', replay(live, notes, change) == (live, notes))
    edited = dict(notes)
    edited[targets[0]] += '\n## 人工补充（隔离测试）\n\n保留我对适用范围的判断。\n'
    edited_registry = copy.deepcopy(live)
    edited_registry['experiences'][3]['review_notes'] += '；隔离人工修改'
    incremental = copy.deepcopy(change)
    incremental['append'][targets[0]].append('test:synthetic-increment-only')
    inc, inc_notes = replay(edited_registry, edited, incremental)
    check('04_increment_preserves_human_content', inc_notes[targets[0]].endswith('保留我对适用范围的判断。\n') and inc['experiences'][3]['review_notes'] == edited_registry['experiences'][3]['review_notes'] and inc_notes[targets[1]] == edited[targets[1]])
    check('05_increment_replay_and_count', replay(inc, inc_notes, incremental) == (inc, inc_notes) and len(inc['experiences']) == 7 and len(set(e['experience_id'] for e in inc['experiences'])) == 7)
    pending = copy.deepcopy(incremental)
    pending['review'] = 'pending'
    try:
        replay(live, notes, pending)
    except ValueError:
        check('06_unreviewed_delta_rejected', True)
    else:
        check('06_unreviewed_delta_rejected', False)
    missing = dict(notes)
    missing[targets[0]] = missing[targets[0]].replace('## 证据', '## 其他')
    try:
        replay(live, missing, incremental)
    except ValueError:
        check('07_missing_section_rejected_without_mutation', live == json.loads(live_bytes) and notes[targets[0]] != missing[targets[0]])
    else:
        check('07_missing_section_rejected_without_mutation', False)
    check('08_live_files_byte_identical', live_path.read_bytes() == live_bytes and all(path.read_bytes() == note_bytes[eid] for eid, path in note_paths.items()))
    report = {'step': 'E2-06', 'date': '2026-11-18', 'scope': 'isolated evidence-append replay; no live registry writes', 'source_sha256': digest(source_bytes), 'source_kind': source['kind'], 'raw_session_exported': False, 'input_hashes': {str(live_path): digest(live_bytes), str(before_path): digest(before_bytes), **{str(note_paths[eid]): digest(b) for eid, b in note_bytes.items()}}, 'results': results, 'passed': len(results), 'limitations': ['No full-session extraction or semantic deduplication tested', 'No production writer, crash recovery or concurrent writer testing', 'Review flag is a fixture, not production approval enforcement', 'Existing last_updated versus note.updated mismatch retained; no metadata repair claimed', 'Skill installation/version and closed-loop reuse claims remain unverified']}
    (ROOT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': len(results), 'failed': 0, 'report': str(ROOT / 'report.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
