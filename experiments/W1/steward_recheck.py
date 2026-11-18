"""Independent reproduction of worker commands and evidence-line verification."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'worker-output'


def run(args):
    return subprocess.run([sys.executable, str(OUTPUT / 'audit_worker_contract.py'), *map(str, args)], cwd=ROOT, capture_output=True, encoding='utf-8', env=dict(os.environ, PYTHONIOENCODING='utf-8'))


def main():
    checkroot = OUTPUT / 'steward-recheck'
    checkroot.mkdir(exist_ok=True)
    normal = run(['--report-dir', checkroot / 'normal'])
    fixture = checkroot / 'missing-input'
    fixture.mkdir(exist_ok=True)
    for p in (ROOT / 'inputs').iterdir():
        if p.name != 'task-template.md':
            shutil.copy2(p, fixture / p.name)
    missing = run(['--input-dir', fixture, '--report-dir', checkroot / 'missing'])
    audited = json.loads((checkroot / 'normal/audit-report.json').read_text(encoding='utf-8'))
    negative = json.loads((checkroot / 'missing/audit-report.json').read_text(encoding='utf-8'))
    evidence = []
    for finding in audited.get('findings', []):
        for e in finding['evidence']:
            p = ROOT / 'inputs' / e['file']
            lines = p.read_text(encoding='utf-8').splitlines()
            number = e['line']
            actual = lines[number - 1] if isinstance(number, int) and 1 <= number <= len(lines) else None
            evidence.append({'finding': finding['id'], 'file': e['file'], 'line': number, 'line_exists': actual is not None, 'actual': actual})
    integrity = subprocess.run([sys.executable, str(ROOT / 'verify_handoff.py')], capture_output=True, encoding='utf-8', env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    checks = {'normal_exit_zero': normal.returncode == 0, 'normal_audit_completed': audited.get('status') == 'completed', 'missing_input_exit_nonzero': missing.returncode != 0, 'missing_input_reported_blocked': negative.get('status') == 'blocked', 'findings_have_valid_line_locations': bool(evidence) and all(e['line_exists'] for e in evidence), 'input_and_original_hashes_unchanged': integrity.returncode == 0}
    report = {'date': '2026-11-18', 'checks': checks, 'ok': all(checks.values()), 'normal_exit_code': normal.returncode, 'missing_input_exit_code': missing.returncode, 'normal_stdout': normal.stdout, 'missing_stderr': missing.stderr, 'evidence_line_checks': evidence, 'semantic_review': 'Findings are model-authored judgments tied to the frozen pre-template snapshot, not automated proof of semantic sufficiency or human approval', 'limits': ['Negative case tests audit script behavior, not full Agent recovery after tool failure', 'No comprehensive tool-access log or filesystem sandbox proof', 'No speed, cost or multi-worker benefit measured']}
    (ROOT / 'steward-recheck.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'ok': report['ok'], 'checks': checks, 'normal_exit': normal.returncode, 'missing_exit': missing.returncode}, ensure_ascii=False))
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
