"""Steward verifies artifact availability and frozen-input integrity, not worker claims."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]


def main():
    manifest = json.loads((ROOT / 'input-manifest.json').read_text(encoding='utf-8'))
    frozen_ok = all(hashlib.sha256(Path(f['path']).read_bytes()).hexdigest() == f['sha256'] for f in manifest['files'])
    sources = {'steward-entry.md': PROJECT / 'AGENTS.md', 'steward-defaults.json': PROJECT / 'jarvis/defaults.json', 'task-template.md': PROJECT / 'jarvis/task-template.md'}
    original_ok = all(hashlib.sha256(sources[Path(f['path']).name].read_bytes()).hexdigest() == f['sha256'] for f in manifest['files'] if Path(f['path']).name in sources)
    doc = Path(manifest['architecture_source'])
    architecture_ok = hashlib.sha256(doc.read_bytes()).hexdigest() == manifest['architecture_sha256']
    artifacts = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'worker-output').rglob('*') if p.is_file() and '__pycache__' not in str(p))
    report = {'date': '2026-11-18', 'frozen_inputs_unchanged': frozen_ok, 'original_configuration_unchanged': original_ok, 'architecture_unchanged': architecture_ok, 'worker_files': artifacts, 'scope_note': 'Hashes cover listed inputs and original configurations only; they are not a complete filesystem-access audit or security isolation proof'}
    (ROOT / 'steward-integrity-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    if not all([frozen_ok, original_ok, architecture_ok]):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
