"""Read-only resource checks plus scoped retrieval for JARVIS's initial trial."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'jarvis/tasks'


def invoke(script, *args):
    result = subprocess.run([sys.executable, str(script), *map(str, args)], cwd=ROOT,
                            env=dict(os.environ, PYTHONIOENCODING='utf-8'),
                            capture_output=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    defaults = json.loads((ROOT / 'jarvis/defaults.json').read_text(encoding='utf-8'))
    pointer = json.loads((ROOT / defaults['knowledge_pointer']).read_text(encoding='utf-8'))
    registry = Path(defaults['registry'])
    before = registry.read_bytes()
    registry_data = json.loads(before)
    kb = Path(defaults['skill_roots'][0]) / 'obsidian-kb/scripts/kb.py'
    query_script = registry.parent / 'query_experience.py'
    doctor = invoke(kb, 'doctor', '--json')
    retrieved = invoke(kb, 'search', 'JARVIS 项目协作约定', '--project-only', '--limit', '3', '--json')
    experiences = invoke(query_script, '--limit', '5')
    (OUT / 'JV-20261118-001-retrieval.json').write_text(json.dumps(retrieved, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OUT / 'JV-20261118-001-experiences.json').write_text(json.dumps(experiences, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OUT / 'JV-20261118-001-kb-doctor.json').write_text(json.dumps(doctor, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    resources = ['AGENTS.md', 'jarvis/defaults.json', 'jarvis/task-template.md', 'jarvis/README.md', defaults['knowledge_pointer'], '架构方案/JARVIS 管家Agent职责定义 v0.1.md', 'jarvis/backups/initial-deployment/AGENTS.pre-deployment.md']
    checks = {
        'declared_local_resources_exist': all((ROOT / p).is_file() for p in resources),
        'vault_project_root_exists': (Path(pointer['vault']) / pointer['project']['root']).is_dir(),
        'registry_parses_and_query_runs': isinstance(registry_data.get('experiences'), list) and experiences['count'] == len(experiences['results']),
        'confirmed_agreement_retrieved': 'JARVIS 项目协作约定.md' in json.dumps(retrieved, ensure_ascii=False),
        'actual_retrieval_skill_exists': kb.is_file() and (kb.parents[1] / 'SKILL.md').is_file(),
        'registry_bytes_unchanged': registry.read_bytes() == before,
        'entry_matches_soft_defaults': all(text in (ROOT / 'AGENTS.md').read_text(encoding='utf-8') for text in ['2 次', '20 分钟', '--project-only', '图书管理员']),
    }
    report = {'date': '2026-11-18', 'deployment': 'project-main-session', 'ok': all(checks.values()), 'checks': checks,
              'formal_experience_count': len(registry_data['experiences']),
              'registry_sha256': hashlib.sha256(before).hexdigest(),
              'resource_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in resources},
              'actual_mode': 'direct', 'workers_spawned': 0,
              'limitations': ['Existing session explicitly reread AGENTS.md; new-session automatic loading not tested', 'No hard budget, Worker isolation, semantic reuse quality or global user-model validation', 'No new formal experience, skill, named subagent or background service created']}
    (OUT / 'JV-20261118-001-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'ok': report['ok'], 'checks': checks, 'formal_experience_count': report['formal_experience_count']}, ensure_ascii=False))
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
