"""One-off authorized removal; keep byte-verified backups outside the Obsidian vault."""
import hashlib
import json
import shutil
from pathlib import Path

REG = Path('D:/个人知识库/01_项目/JARVIS/40_任务经验注册表').resolve()
VAULT = REG.parents[2]
OUT = Path(__file__).resolve().parent
ARCHIVE = OUT / 'quarantine-2026-11-18'
MISSING = {'agent-boundary-analysis', 'agent-self-evolution-review', 'agentic-gap-analysis', 'architecture-document-revision', 'architecture-review', 'experiment-planning', 'librarian-registry-design'}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    registry_path = REG / 'experience-registry.json'
    registry_bytes = registry_path.read_bytes()
    registry = json.loads(registry_bytes)
    candidates = [e for e in registry['experiences'] if e.get('skill_links') and all(s['skill_id'] in MISSING for s in e['skill_links'])]
    if not candidates:
        print('No matching entries remain; no changes made.')
        return
    if ARCHIVE.exists():
        raise RuntimeError('Archive already exists; inspect prior run before proceeding')
    # Validate all source and destination boundaries before any move/removal.
    sources = [(VAULT / e['obsidian_path']).resolve() for e in candidates]
    sources += list((REG / 'validation/backups').glob('exp-2026-*.md'))
    for p in sources:
        if not p.is_relative_to(REG) or not p.is_file():
            raise ValueError('Unexpected source: ' + str(p))
    ARCHIVE.mkdir(parents=True)
    (ARCHIVE / 'experience-registry.pre-cleanup.json').write_bytes(registry_bytes)
    shutil.copy2(REG / 'experience-review-log.json', ARCHIVE / 'experience-review-log.historical.json')
    shutil.copy2(REG / 'validate_registry.py', ARCHIVE / 'validate_registry.pre-cleanup.py')
    files = []
    # Copy and verify every selected note before changing the live registry.
    for p in sources:
        dest = (ARCHIVE / 'notes' / p.relative_to(REG)).resolve()
        if not dest.is_relative_to(ARCHIVE.resolve()):
            raise ValueError('Unexpected destination')
        dest.parent.mkdir(parents=True, exist_ok=True)
        b = p.read_bytes()
        dest.write_bytes(b)
        if dest.read_bytes() != b:
            raise RuntimeError('Backup verification failed')
        files.append({'original': str(p), 'archived': str(dest), 'sha256': sha(b)})
    ids = {e['experience_id'] for e in candidates}
    updated = dict(registry)
    updated['updated_at'] = '2026-11-18'
    updated['experiences'] = [e for e in registry['experiences'] if e['experience_id'] not in ids]
    removal = {'schema_version': '0.1', 'updated_at': '2026-11-18', 'removals': [{'experience_id': e['experience_id'], 'removed_at': '2026-11-18', 'decision': 'removed', 'reviewer': 'user', 'reason': 'No corresponding installed Skill confirmed; user requested removal to avoid knowledge pollution', 'skill_ids': [s['skill_id'] for s in e['skill_links']], 'backup_registry': str(ARCHIVE / 'experience-registry.pre-cleanup.json')} for e in candidates]}
    # Sequential writes; journal is created before the live replacement.
    manifest = {'date': '2026-11-18', 'phase': 'backed_up', 'user_instruction': '注册表中未找到对应skill的经验，先去除，避免产生数据污染。建议可行', 'removed_ids': sorted(ids), 'registry_before_sha256': sha(registry_bytes), 'remaining_count': len(updated['experiences']), 'files': files, 'historical_reviews_preserved': True}
    manifest_path = OUT / 'cleanup-manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (REG / 'experience-removals.json').write_text(json.dumps(removal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp = registry_path.with_suffix('.cleanup.tmp')
    temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(registry_path)
    for entry in files:
        p = Path(entry['original'])
        if sha(p.read_bytes()) != entry['sha256']:
            raise RuntimeError('Source changed after backup; retained for manual inspection: ' + str(p))
        p.unlink()
    manifest['phase'] = 'completed'
    manifest['registry_after_sha256'] = sha(registry_path.read_bytes())
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'removed': len(ids), 'remaining': len(updated['experiences']), 'notes_quarantined': len(files), 'manifest': str(manifest_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
