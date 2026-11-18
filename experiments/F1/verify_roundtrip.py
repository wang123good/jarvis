import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = Path('D:/codex-project/JARVIS')
SKILLS = Path('C:/Users/10013463/.codex/skills')
VAULT = Path('D:/个人知识库')


def call(args):
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    p = subprocess.run([sys.executable, *map(str, args)], cwd=PROJECT, env=env, capture_output=True, encoding='utf-8')
    if p.returncode:
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout)


def main():
    proposal = json.loads((ROOT / 'candidate-proposal.json').read_text(encoding='utf-8'))
    note = VAULT / proposal['note']
    before = note.read_bytes()
    repeat = call([SKILLS / 'obsidian-curator/scripts/curate.py', '--batch', ROOT / 'candidate-batch.json'])
    verify = call([SKILLS / 'codex-memory-sync/scripts/sync.py', 'verify', '--plan', ROOT / 'sync-plan.json'])
    retrieval = call([SKILLS / 'obsidian-kb/scripts/kb.py', 'search', '真实 Skill 核验', '--project-only', '--limit', '3', '--json'])
    (ROOT / 'retrieval-project-only.json').write_text(json.dumps(retrieval, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    found = proposal['note'] in json.dumps(retrieval, ensure_ascii=False).replace('\\\\', '/')
    # Paths in the helper response are vault-relative or absolute; normalize separators for the assertion.
    if not found:
        found = '2026-11-18 F1 真实Skill核验与经验清理草稿.md' in json.dumps(retrieval, ensure_ascii=False)
    registry = json.loads((VAULT / '01_项目/JARVIS/40_任务经验注册表/experience-registry.json').read_text(encoding='utf-8'))
    skill = Path(proposal['skill']['path'])
    checks = {'source_verification': verify['ok'], 'repeat_no_note_changes': repeat['changed'] == 0 and note.read_bytes() == before, 'candidate_retrievable': found, 'actual_skill_hash_matches': hashlib.sha256(skill.read_bytes()).hexdigest() == proposal['skill']['sha256'], 'formal_registry_still_empty': registry['experiences'] == []}
    report = {'date': '2026-11-18', 'checks': checks, 'ok': all(checks.values()), 'source_verify': verify, 'repeat': repeat, 'isolated_process_retrieval': True, 'fresh_agent_session_tested': False, 'behavioral_reuse_verified': False, 'limitations': ['Initial layer=project search returned an unrelated project excerpt; excluded from synthesis; rerun with --project-only', 'Exact exported source is point-in-time, not guaranteed lifetime-complete', 'SKILL.md hash is not a full skill-package checksum', 'Draft retrieval is not approved experience reuse']}
    (ROOT / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
