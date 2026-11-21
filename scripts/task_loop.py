"""Gate and record serial JARVIS task execution against an approved task card."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from resolve_environment import read_object, relative_to


ROOT = Path(__file__).resolve().parents[1]
IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,79}')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc)


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_ref(directory, name):
    path = relative_to(directory, name, 'evidence')
    require(path.is_file() and path.stat().st_size > 0, 'Evidence must be a nonempty task-local file')
    require(path.name not in {'contract.md', 'loop.sqlite3'} and not path.name.startswith('loop.sqlite3-'),
            'Provide an actual verification or reconciliation record')
    return {'file': path.relative_to(directory).as_posix(), 'sha256': fingerprint(path)}


def parse_plan(steps, acceptance):
    require(isinstance(steps, list) and steps, 'steps must be a nonempty list')
    seen, covered = set(), set()
    for step in steps:
        require(isinstance(step, dict) and set(step) == {'id', 'depends_on', 'acceptance', 'action', 'verify', 'failure_key'},
                'Each step needs id, depends_on, acceptance, action, verify and failure_key')
        for key in ('id', 'failure_key'):
            require(isinstance(step[key], str) and IDENTIFIER.fullmatch(step[key]), f'Invalid step {key}')
        for key in ('action', 'verify'):
            require(isinstance(step[key], str) and step[key].strip(), f'Missing step {key}')
        require(step['id'] not in seen, 'Duplicate step id')
        for key, allowed in [('depends_on', seen), ('acceptance', acceptance)]:
            require(isinstance(step[key], list) and
                    all(isinstance(item, str) and item in allowed for item in step[key]),
                    f'Invalid {key} for {step["id"]}')
        seen.add(step['id'])
        covered.update(step['acceptance'])
    require(covered == set(acceptance), 'Plan must cover every approved acceptance item')
    return steps


def initial_state(directory, path):
    spec = read_object(path)
    for key, minimum in [('contract_revision', 1), ('plan_revision', 1), ('max_attempts', 1), ('max_additional_retries', 0)]:
        require(type(spec.get(key)) is int and spec[key] >= minimum, f'Invalid {key}')
    expires = spec.get('expires_at')
    require(isinstance(expires, str), 'expires_at must include a UTC offset')
    deadline = datetime.fromisoformat(expires.replace('Z', '+00:00'))
    require(deadline.tzinfo and deadline > now(), 'expires_at must be a future time with a UTC offset')
    acceptance = spec.get('acceptance')
    require(isinstance(acceptance, dict) and acceptance and all(
        IDENTIFIER.fullmatch(key) and isinstance(value, str) and value.strip()
        for key, value in acceptance.items()), 'acceptance must map IDs to approved criteria')
    require(isinstance(spec.get('approval'), str) and spec['approval'].strip(), 'Record the approval reference')
    contract = directory / 'contract.md'
    require(contract.is_file() and contract.stat().st_size > 0, 'Existing task contract.md is required')
    return {
        'task_id': directory.name,
        'contract_revision': spec['contract_revision'],
        'contract_sha256': fingerprint(contract),
        'approval': spec['approval'],
        'plan_revision': spec['plan_revision'],
        'acceptance': acceptance,
        'steps': parse_plan(spec.get('steps'), acceptance),
        'max_attempts': spec['max_attempts'],
        'max_additional_retries': spec['max_additional_retries'],
        'expires_at': deadline.isoformat(),
        'attempts_used': 0,
        'no_progress': 0,
        'failures': {},
        'verified': {},
        'active': None,
        'paused': False,
    }


def budget_allows(state):
    return now() < datetime.fromisoformat(state['expires_at']) and state['attempts_used'] < state['max_attempts']


def next_decision(state, directory):
    if state['active']:
        return {'decision': 'reconcile', 'attempt': state['active']}
    if state['paused']:
        return {'decision': 'paused'}
    contract = directory / 'contract.md'
    if not contract.is_file() or fingerprint(contract) != state['contract_sha256']:
        return {'decision': 'review_contract'}
    for step_id, evidence in state['verified'].items():
        try:
            current = evidence_ref(directory, evidence['file'])
        except (OSError, ValueError):
            current = None
        if current != evidence:
            return {'decision': 'revalidate', 'step_id': step_id}
    pending = [step for step in state['steps'] if step['id'] not in state['verified']]
    if not pending:
        return {'decision': 'ready_to_deliver', 'acceptance_evidence': {
            criterion: [state['verified'][step['id']] for step in state['steps'] if criterion in step['acceptance']]
            for criterion in state['acceptance']
        }}
    if not budget_allows(state):
        return {'decision': 'budget_exhausted'}
    if state['no_progress'] >= 2:
        return {'decision': 'no_progress'}
    for step in pending:
        if (all(dep in state['verified'] for dep in step['depends_on']) and
                state['failures'].get(step['failure_key'], 0) <= state['max_additional_retries']):
            return {'decision': 'ready', 'step': step}
    return {'decision': 'no_eligible_step'}


def claim(state, directory):
    decision = next_decision(state, directory)
    if decision['decision'] != 'ready':
        return decision, False
    attempt = {'id': uuid4().hex, 'step': decision['step'], 'started_at': now().isoformat(),
               'plan_revision': state['plan_revision'], 'contract_revision': state['contract_revision']}
    state['attempts_used'] += 1
    state['active'] = attempt
    return {'decision': 'execute', 'attempt': attempt}, True


def record(state, directory, args):
    attempt = state['active']
    require(attempt and attempt['id'] == args.attempt, 'Use the current attempt ID')
    evidence = evidence_ref(directory, args.evidence)
    step = attempt['step']
    if args.outcome == 'passed':
        contract = directory / 'contract.md'
        require(contract.is_file() and fingerprint(contract) == state['contract_sha256'],
                'Contract changed. Record the actual action as unresolved or failed and review the contract')
        state['verified'][step['id']] = evidence
        state['no_progress'] = 0
    elif args.outcome == 'failed':
        key = step['failure_key']
        state['failures'][key] = state['failures'].get(key, 0) + 1
        state['no_progress'] += 1
    if args.outcome != 'unknown':
        state['active'] = None
    return {'attempt': attempt, 'outcome': args.outcome, 'evidence': evidence}


def revise(state, directory, args):
    require(not state['active'], 'Reconcile the active attempt before changing the plan')
    decision = next_decision(state, directory)
    require(decision['decision'] != 'review_contract' and
            (directory / 'contract.md').is_file() and
            fingerprint(directory / 'contract.md') == state['contract_sha256'],
            'Contract changed. Review before creating a new run under revised authorization')
    replacement = read_object(args.plan)
    require(replacement.get('plan_revision') == state['plan_revision'] + 1, 'Increase plan_revision by one')
    steps = parse_plan(replacement.get('steps'), state['acceptance'])
    evidence = evidence_ref(directory, args.evidence)
    previous = {step['id']: step for step in state['steps']}
    retained = {}
    for step in steps:
        step_id = step['id']
        if (previous.get(step_id) == step and step_id in state['verified'] and
                all(dep in retained for dep in step['depends_on'])):
            ref = state['verified'][step_id]
            try:
                if evidence_ref(directory, ref['file']) == ref:
                    retained[step_id] = ref
            except (OSError, ValueError):
                continue
    state['steps'] = steps
    state['plan_revision'] += 1
    state['verified'] = retained
    return {'revision_evidence': evidence, 'retained': list(retained)}


def dispatch(db, directory, args):
    if args.operation == 'init':
        db.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, operation TEXT, '
                   'recorded_at TEXT, detail TEXT, state TEXT)')
    row = db.execute('SELECT state FROM events ORDER BY seq DESC LIMIT 1').fetchone()
    if args.operation == 'init':
        require(not row, 'A loop already exists for this task')
        state = initial_state(directory, args.plan)
        detail = next_decision(state, directory)
    else:
        require(row, 'Initialize the task loop first')
        state = json.loads(row[0])
        if args.operation == 'status':
            return {'state': state, **next_decision(state, directory)}
        if args.operation == 'next':
            detail, changed = claim(state, directory)
            if not changed:
                return detail
        elif args.operation == 'record':
            detail = record(state, directory, args)
        elif args.operation == 'replan':
            detail = revise(state, directory, args)
        else:
            require(not state['active'], 'Pause or resume at a checkpoint after reconciling the active attempt')
            state['paused'] = args.operation == 'pause'
            detail = {'paused': state['paused']}
    db.execute('INSERT INTO events(operation, recorded_at, detail, state) VALUES (?, ?, ?, ?)',
               (args.operation, now().isoformat(), json.dumps(detail, ensure_ascii=False),
                json.dumps(state, ensure_ascii=False)))
    if args.operation == 'next':
        return detail
    return {**detail, **next_decision(state, directory)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_id', help='Existing task ID under .local/tasks')
    operations = parser.add_subparsers(dest='operation', required=True)
    for operation in ('init', 'replan'):
        subparser = operations.add_parser(operation)
        subparser.add_argument('plan', type=Path)
        if operation == 'replan':
            subparser.add_argument('--evidence', required=True)
    for operation in ('status', 'next', 'pause', 'resume'):
        operations.add_parser(operation)
    result = operations.add_parser('record')
    result.add_argument('attempt')
    result.add_argument('outcome', choices=('passed', 'failed', 'unknown', 'not-run'))
    result.add_argument('--evidence', required=True)
    args = parser.parse_args(argv)
    try:
        require(IDENTIFIER.fullmatch(args.task_id), 'Invalid task ID')
        task_root = ROOT / '.local/tasks'
        require(task_root.resolve() == task_root, 'The local task root must not be redirected')
        directory = relative_to(task_root, args.task_id, 'task ID')
        require(directory == task_root / args.task_id and directory.is_dir(), 'Use an existing task directory')
        database = directory / 'loop.sqlite3'
        require(database.resolve() == database, 'The loop database must not be redirected')
        require(args.operation == 'init' or database.is_file(), 'Initialize the task loop first')
        with closing(sqlite3.connect(database)) as db, db:
            db.execute('BEGIN IMMEDIATE' if args.operation != 'status' else 'BEGIN')
            response = dispatch(db, directory, args)
        print(json.dumps(response, ensure_ascii=True))
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=True))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
