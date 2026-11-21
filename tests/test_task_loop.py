from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


class TaskLoopTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        scripts = root / 'scripts'
        scripts.mkdir()
        for name in ('task_loop.py', 'resolve_environment.py'):
            shutil.copyfile(SCRIPTS / name, scripts / name)
        self.cli = [sys.executable, str(scripts / 'task_loop.py'), 'TEST-LOOP']
        self.directory = root / '.local/tasks/TEST-LOOP'
        self.directory.mkdir(parents=True)
        self.contract = self.directory / 'contract.md'
        self.contract.write_text('Approved test fixture', encoding='utf-8')

    def call(self, *args, error=False):
        result = subprocess.run([*self.cli, *args], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2 if error else 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def steps(self):
        return [
            {'id': 'prepare', 'depends_on': [], 'acceptance': [], 'action': 'prepare',
             'verify': 'check preparation', 'failure_key': 'prepare'},
            {'id': 'finish', 'depends_on': ['prepare'], 'acceptance': ['result'], 'action': 'finish',
             'verify': 'check result', 'failure_key': 'finish'},
        ]

    def write(self, name, content):
        target = self.directory / name
        target.write_text(content, encoding='utf-8')
        return target

    def init(self, max_attempts=4):
        spec = {'contract_revision': 1, 'plan_revision': 1, 'approval': 'test fixture',
                'expires_at': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                'max_attempts': max_attempts, 'max_additional_retries': 1,
                'acceptance': {'result': 'Result verified'}, 'steps': self.steps()}
        return self.call('init', str(self.write('plan.json', json.dumps(spec))))

    def claim(self, expected):
        claim = self.call('next')
        self.assertEqual(claim['decision'], 'execute')
        self.assertEqual(claim['attempt']['step']['id'], expected)
        return claim['attempt']['id']

    def record(self, attempt, outcome, filename):
        self.write(filename, f'{attempt} {outcome}')
        return self.call('record', attempt, outcome, '--evidence', filename)

    def test_failed_step_replans_and_recovers_in_fresh_process(self):
        self.init()
        failed = self.claim('prepare')
        self.record(failed, 'failed', 'failure.txt')
        replacement = self.steps()
        replacement[0]['action'] = 'correct the preparation input'
        new_plan = self.write('replacement.json', json.dumps({'plan_revision': 2, 'steps': replacement}))
        self.call('replan', str(new_plan), '--evidence', 'failure.txt')

        active = self.claim('prepare')
        self.assertEqual(self.call('status')['decision'], 'reconcile')
        self.assertEqual(self.call('next')['attempt']['id'], active)
        self.record(active, 'unknown', 'unknown.txt')
        self.assertEqual(self.call('next')['decision'], 'reconcile')
        self.record(active, 'passed', 'actual-preparation.txt')
        self.assertEqual(self.call('pause')['decision'], 'paused')
        self.assertEqual(self.call('next')['decision'], 'paused')
        self.assertEqual(self.call('resume')['decision'], 'ready')
        finished = self.record(self.claim('finish'), 'passed', 'result.txt')
        self.assertEqual(finished['decision'], 'ready_to_deliver')
        self.assertEqual(finished['acceptance_evidence']['result'][0]['file'], 'result.txt')
        self.assertEqual(self.call('status')['state']['attempts_used'], 3)
        self.assertEqual(self.call('status')['state']['failures'], {'prepare': 1})

        self.write('actual-preparation.txt', 'altered evidence')
        self.assertEqual(self.call('next')['decision'], 'revalidate')

    def test_budget_and_contract_changes_block_claims(self):
        self.init(max_attempts=1)
        attempt = self.claim('prepare')
        self.call('record', attempt, 'passed', '--evidence', 'missing.txt', error=True)
        self.assertEqual(self.call('status')['decision'], 'reconcile')
        self.record(attempt, 'not-run', 'reconciliation.txt')
        self.assertEqual(self.call('next')['decision'], 'budget_exhausted')
        self.contract.write_text('Changed approval basis', encoding='utf-8')
        self.assertEqual(self.call('next')['decision'], 'review_contract')
