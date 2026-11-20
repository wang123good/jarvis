"""Read-only resource checks plus scoped retrieval for JARVIS's initial trial."""
import argparse
import importlib.util
from datetime import datetime, timezone
import re
from uuid import uuid4
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / '.local/verification-runs'


def invoke(script, *args):
    result = subprocess.run([sys.executable, str(script), *map(str, args)], cwd=ROOT,
                            env=dict(os.environ, PYTHONIOENCODING='utf-8'),
                            capture_output=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def create_run_directory(base, run_id):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id):
        raise ValueError("run_id must be a simple identifier (1-80 letters/digits/_/-)")
    if run_id.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(1,10)), *('LPT'+str(i) for i in range(1,10))}:
        raise ValueError("reserved run_id")
    base.mkdir(parents=True, exist_ok=True)
    target = base / run_id
    target.mkdir(exist_ok=False)
    return target


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id')
    parser.add_argument('--environment-only', action='store_true', help='Check portable resources and local paths without a registry or external retrieval Skill')
    parser.add_argument('--connector-vault', help='Actual root reported by the connected Obsidian tool')
    args = parser.parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid4().hex[:12]
    out = create_run_directory(RUNS, run_id)
    write_json(out / 'started.json', {'run_id': run_id, 'started_at_utc': datetime.now(timezone.utc).isoformat()})
    try:
        run_checks(out, run_id, args.connector_vault, args.environment_only)
    except Exception as exc:
        write_json(out / 'error.json', {'run_id': run_id, 'status': 'failed', 'error_type': type(exc).__name__, 'message': str(exc)})
        raise


def run_checks(out, run_id, connector_vault=None, environment_only=False):
    spec = importlib.util.spec_from_file_location('environment_reader', Path(__file__).with_name('resolve_environment.py'))
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    resolved = reader.resolve_environment(ROOT, connector_vault)
    defaults = json.loads((ROOT / 'config/defaults.json').read_text(encoding='utf-8'))
    resources = ['agents/worker.md', 'templates/worker-work-package.md', 'scripts/verify_installation.py', 'AGENTS.md', 'config/defaults.json', 'config/environment.example.json', 'scripts/resolve_environment.py', 'templates/task.md', 'docs/operations.md', defaults['knowledge_pointer'], '架构方案/JARVIS 管家Agent职责定义 v0.1.md', 'scripts/read_profile.py', 'scripts/init_vault.py', 'docs/archive-index.md']
    resources += ['templates/vault/' + name + '.md' for name in
                  ['规则', '草稿', '日报', '周报', '决策', '任务总结', '任务契约', '业务对话', 'wiki主题']]
    environment_checks = {
        'declared_local_resources_exist': all((ROOT / p).is_file() for p in resources),
        'vault_exists': resolved['vault_exists'],
        'vault_project_root_exists': Path(resolved['project_knowledge_root']).is_dir(),
    }
    if resolved['connector_checked']:
        environment_checks['connected_vault_matches'] = resolved['connector_matches']
    environment_report = {
        'run_id': run_id, 'scope': 'environment-only', 'ok': all(environment_checks.values()),
        'checks': environment_checks, 'connector_checked': resolved['connector_checked'],
        'write_ready': resolved['write_ready'], 'vault_root': resolved['vault_root'],
        'registry_exists': Path(resolved['registry']).is_file(),
        'limitations': ['Environment validation does not prove registry or knowledge retrieval availability',
                        'An omitted connector path is not a connection verification; vault writes remain disallowed'],
    }
    write_json(out / 'environment-verification.json', environment_report)
    if environment_only:
        write_json(out / 'verification.json', environment_report)
        print(json.dumps({**environment_report, 'run_directory': str(out)}, ensure_ascii=False))
        if not environment_report['ok']:
            raise SystemExit(1)
        return
    reader.require_write_ready(resolved)
    registry = Path(resolved['registry'])
    if not registry.is_file():
        raise RuntimeError('Formal experience registry is missing; only environment validation completed. No registry was fabricated.')
    before = registry.read_bytes()
    registry_data = json.loads(before)
    candidates = [Path(path) / 'obsidian-kb/scripts/kb.py' for path in resolved['skill_roots']]
    kb = next((path for path in candidates if path.is_file()), None)
    if kb is None:
        raise RuntimeError('No installed obsidian-kb retrieval Skill found in local skill_roots')
    help_result = subprocess.run([sys.executable, str(kb), '--help'], cwd=ROOT,
                                 capture_output=True, encoding='utf-8',
                                 env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    if help_result.returncode or '--config' not in help_result.stdout:
        raise RuntimeError('Installed obsidian-kb must support an explicit global --config option; refusing implicit shared-path fallback')
    runtime_pointer = reader.write_runtime_pointer(resolved)
    query_script = registry.parent / 'query_experience.py'
    doctor = invoke(kb, '--config', runtime_pointer, 'doctor', '--json')
    retrieved = invoke(kb, '--config', runtime_pointer, 'search', 'JARVIS 项目协作约定', '--project-only', '--limit', '3', '--json')
    experiences = invoke(query_script, '--limit', '5')
    write_json(out / 'retrieval.json', retrieved)
    write_json(out / 'experiences.json', experiences)
    write_json(out / 'kb-doctor.json', doctor)
    checks = {
        **environment_checks,
        'registry_parses_and_query_runs': isinstance(registry_data.get('experiences'), list) and experiences['count'] == len(experiences['results']),
        'confirmed_agreement_retrieved': 'JARVIS 项目协作约定.md' in json.dumps(retrieved, ensure_ascii=False),
        'actual_retrieval_skill_exists': kb.is_file() and (kb.parents[1] / 'SKILL.md').is_file(),
        'registry_bytes_unchanged': registry.read_bytes() == before,
        'entry_matches_soft_defaults': all(text in (ROOT / 'AGENTS.md').read_text(encoding='utf-8') for text in ['2 次', '20 分钟', '--project-only', '图书管理员']),
    }
    report = {'run_id': run_id, 'completed_at_utc': datetime.now(timezone.utc).isoformat(), 'deployment': 'project-main-session', 'ok': all(checks.values()), 'checks': checks,
              'formal_experience_count': len(registry_data['experiences']),
              'registry_sha256': hashlib.sha256(before).hexdigest(),
              'resource_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in resources},
              'actual_mode': 'direct', 'workers_spawned': 0,
              'limitations': ['Existing session explicitly reread AGENTS.md; new-session automatic loading not tested', 'No hard budget, Worker isolation, semantic reuse quality or global user-model validation', 'No new formal experience, skill, named subagent or background service created']}
    write_json(out / 'verification.json', report)
    print(json.dumps({'ok': report['ok'], 'checks': checks, 'formal_experience_count': report['formal_experience_count'], 'run_directory': str(out)}, ensure_ascii=False))
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
