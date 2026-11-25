"""Exercise independent JARVIS checkouts using the Windows command-line entry points."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstanceIsolationTests(unittest.TestCase):
    def command(self, project, legacy, script, *args, code=0):
        result = subprocess.run(
            [sys.executable, '-X', 'utf8', f'scripts/{script}.py', *args],
            cwd=project, env={**os.environ, 'JARVIS_VAULT_ROOT': str(legacy)},
            capture_output=True, text=True, encoding='utf-8', timeout=30,
        )
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_two_checkouts_and_vaults(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            projects = [base / 'copy-a', base / 'copy-b']
            vaults = [base / 'vault-a', base / 'vault-b']
            markers = ['Zebrastar', 'Quartzhill']
            for project in projects:
                for folder in ('scripts', 'config', '.codex', 'templates'):
                    shutil.copytree(ROOT / folder, project / folder,
                                    ignore=shutil.ignore_patterns('__pycache__'))
                shutil.copyfile(ROOT / 'up.example.json', project / 'up.example.json')

            def exercise(index):
                project, vault, legacy = projects[index], vaults[index], vaults[1-index]
                marker, other = markers[index], markers[1-index]

                def run(script, *args, **kwargs):
                    return self.command(project, legacy, script, *args, **kwargs)

                profile = json.loads((project / 'up.example.json').read_text(encoding='utf-8'))
                profile['nickname'] = marker
                (project / 'up.json').write_text(json.dumps(profile), encoding='utf-8')
                self.assertEqual(run('read_profile', '--status')['nickname'], marker)
                run('resolve_environment', code=2)
                run('onboarding', 'start', '--request-ref', marker)
                preview = run('onboarding', 'select', 'new', str(vault))
                run('onboarding', 'prepare', '--approved', preview['approval_code'])
                self.assertTrue(run('persona', '--persist')['enabled'])
                if index == 0:
                    displayed = run('onboarding', 'display')
                    run('onboarding', 'acknowledge', '--reply', displayed['reply'])
                self.assertEqual(run('onboarding', 'status')['stage'],
                                 'activated' if index == 0 else 'verified')
                settings = run('resolve_environment', '--require-write-ready')
                self.assertEqual(Path(settings['vault_root']), vault.resolve())
                run('resolve_environment', '--connector-vault', str(legacy), code=2)
                note = f'02 工作记录/任务总结/JARVIS/{marker}.md'
                args = ('--template', '任务总结', '--title', marker, '--path', note)
                preview = run('brain_note', *args)
                run('brain_note', *args, '--write', preview['baseline'])
                written = vault / note
                text = written.read_text(encoding='utf-8')
                self.assertIn(marker, text)
                active = text.replace('status: "review"', 'status: "active"')
                written.write_text(f'{active}\n\n{marker}\n', encoding='utf-8')
                results = run('brain_router', 'project', '--query', marker)['results']
                hit = next(item for item in results if item['path'] == note)
                self.assertIn(marker, hit['excerpt'])
                self.assertIn(marker, (vault / hit['path']).read_text(encoding='utf-8'))
                foreign = run('brain_router', 'project', '--query', other)['results']
                self.assertFalse(any(other in item['path'] or other in item['excerpt'] for item in foreign))
                task = project / '.local/tasks/ISOLATION'
                task.mkdir(parents=True)
                (task / 'contract.md').write_text(marker, encoding='utf-8')
                plan = {'contract_revision': 1, 'plan_revision': 1, 'approval': marker,
                        'expires_at': '2099-01-01T00:00:00+00:00', 'max_attempts': 1,
                        'max_additional_retries': 0, 'acceptance': {'check': marker},
                        'steps': [{'id': 'check', 'depends_on': [], 'acceptance': ['check'],
                                   'action': marker, 'verify': marker, 'failure_key': 'fixture'}]}
                (task / 'plan.json').write_text(json.dumps(plan), encoding='utf-8')
                run('task_loop', 'ISOLATION', 'init', str(task / 'plan.json'))
                self.assertEqual(run('task_loop', 'ISOLATION', 'next')['attempt']['step']['action'], marker)
                log = vault / '02 工作记录/Brain运行日志/log.md'
                with log.open('a', encoding='utf-8') as stream:
                    stream.write(f'\n{marker}\n')
                return settings['instance_id']

            with ThreadPoolExecutor(max_workers=2) as pool:
                identities = list(pool.map(exercise, (0, 1)))
            self.assertNotEqual(*identities)
            for index, vault in enumerate(vaults):
                other = markers[1-index]
                self.assertFalse(list(vault.rglob(f'{other}.md')))
                log = (vault / '02 工作记录/Brain运行日志/log.md').read_text(encoding='utf-8')
                self.assertIn(markers[index], log)
                self.assertNotIn(other, log)

            third = base / 'copied-settings'
            shutil.copytree(projects[0], third)
            rejected = self.command(third, vaults[1], 'resolve_environment', code=2)
            self.assertIn('different project', rejected['error'])

            if os.name == 'nt':
                link = vaults[0] / '02 工作记录/任务总结/JARVIS/foreign'
                target = vaults[1] / '02 工作记录/任务总结/JARVIS'
                subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(target)],
                               check=True, capture_output=True)
                try:
                    denied = self.command(projects[0], vaults[1], 'brain_note',
                                          '--template', '任务总结', '--title', 'Escape',
                                          '--path', '02 工作记录/任务总结/JARVIS/foreign/Escape.md', code=2)
                    self.assertIn('escapes', denied['error'])
                    pack = self.command(projects[0], vaults[1], 'brain_router',
                                        'project', '--query', markers[1])
                    self.assertFalse(any(markers[1] in item['path'] for item in pack['results']))
                    self.assertFalse((target / 'Escape.md').exists())
                finally:
                    link.rmdir()
