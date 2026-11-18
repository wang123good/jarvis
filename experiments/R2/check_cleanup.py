"""Verify cleanup counts, quarantine bytes, preserved reviews, and validator behavior."""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REG = Path('D:/个人知识库/01_项目/JARVIS/40_任务经验注册表')


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def main():
    manifest = read(ROOT / 'cleanup-manifest.json')
    archive = ROOT / 'quarantine-2026-11-18'
    registry = read(REG / 'experience-registry.json')
    checks = {
        'removed_seven': len(manifest['removed_ids']) == 7,
        'active_registry_empty': registry['experiences'] == [],
        'normal_query_empty': read(ROOT / 'query-after-cleanup.json')['count'] == 0,
        'all_nine_notes_outside_vault': len(manifest['files']) == 9 and all(not Path(f['original']).exists() and Path(f['archived']).resolve().is_relative_to(archive.resolve()) for f in manifest['files']),
        'all_note_backup_hashes_match': all(hashlib.sha256(Path(f['archived']).read_bytes()).hexdigest() == f['sha256'] for f in manifest['files']),
        'historical_reviews_byte_unchanged': (REG / 'experience-review-log.json').read_bytes() == (archive / 'experience-review-log.historical.json').read_bytes(),
        'mapping_ok_and_empty_warning': read(ROOT / 'cleanup-validation.json')['ok'] and bool(read(ROOT / 'cleanup-validation.json')['warnings']),
    }
    # The new historical-reference exception must not admit unknown IDs or silently resurrect removed entries.
    with tempfile.TemporaryDirectory(prefix='jarvis-cleanup-check-') as temp:
        folder = Path(temp)
        reviews = read(REG / 'experience-review-log.json')
        reviews['reviews'].append({'experience_id': 'exp-2099-999', 'decision': 'approved'})
        review_path = folder / 'bad-reviews.json'
        review_path.write_text(json.dumps(reviews, ensure_ascii=False), encoding='utf-8')
        output = folder / 'unknown-review-report.json'
        result = subprocess.run([sys.executable, str(REG / 'validate_registry.py'), '--review-log', str(review_path), '--output', str(output)], capture_output=True)
        checks['unknown_review_still_rejected'] = result.returncode != 0 and any('exp-2099-999' in e for e in read(output)['errors'])
        restored = read(archive / 'experience-registry.pre-cleanup.json')
        candidate_path = folder / 'restored-registry.json'
        candidate_path.write_text(json.dumps(restored, ensure_ascii=False), encoding='utf-8')
        output = folder / 'restoration-report.json'
        result = subprocess.run([sys.executable, str(REG / 'validate_registry.py'), '--registry', str(candidate_path), '--output', str(output)], capture_output=True)
        checks['unapproved_restoration_rejected'] = result.returncode != 0 and any('reintroduced' in e for e in read(output)['errors'])
    report = {'date': '2026-11-18', 'ok': all(checks.values()), 'checks': checks, 'active_experiences': 0, 'removed_experiences': 7, 'quarantined_markdown_files': 9, 'historical_reviews': 7, 'cross_session_reuse_verified': False}
    (ROOT / 'cleanup-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
