"""Validate and query the configured project experience registry."""

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata
from uuid import uuid4

from resolve_environment import relative_to, require_write_ready


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('updated_at requires a UTC offset')
    return parsed


def parse_registry(data, project):
    value = json.loads(data)
    if (not isinstance(value, dict) or type(value.get('version')) is not int
            or value['version'] != 1 or value.get('project') != project
            or not isinstance(value.get('experiences'), list)):
        raise ValueError('Invalid registry version, project or experiences list')
    seen = set()
    for entry in value['experiences']:
        required = ('id', 'name', 'signature', 'goal', 'scope', 'updated_at',
                    'approval', 'shortcoming', 'evidence', 'evidence_sha256', 'skill', 'skill_sha256')
        if not isinstance(entry, dict) or any(
                not isinstance(entry.get(key), str) or not entry[key].strip() for key in required):
            raise ValueError('Incomplete experience entry')
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', entry['id']) or entry['id'] in seen:
            raise ValueError('Invalid or duplicate experience ID')
        seen.add(entry['id'])
        if entry.get('status') not in ('approved', 'paused', 'revoked'):
            raise ValueError('Invalid experience status')
        for key in ('evidence_sha256', 'skill_sha256'):
            if not re.fullmatch(r'[0-9a-f]{64}', entry[key]):
                raise ValueError(f'Invalid {key}')
        count = entry.get('use_count')
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError('use_count must be null or a nonnegative integer')
        timestamp(entry['updated_at'])
        keywords = entry.get('keywords', [])
        if not isinstance(keywords, list) or any(
                not isinstance(word, str) or len(normalized(word)) < 2 for word in keywords):
            raise ValueError('Invalid experience keywords')
    return value


def project_id(environment):
    return environment['resolved_pointer']['project']['id']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_entry(environment, entry, inspect_skill):
    project = Path(environment['project_root'])
    skill = inspect_skill(project, environment['skill_roots'], entry['skill'])
    if skill['status'] != 'found' or skill['matches'][0]['sha256'] != entry['skill_sha256']:
        return 'skill_missing_ambiguous_or_changed'
    vault = Path(environment['vault_root'])
    evidence = relative_to(vault, entry['evidence'], 'experience evidence')
    roots = [Path(environment['project_knowledge_root']), Path(environment['agreement']).parent]
    if not any(evidence.is_relative_to(root) for root in roots):
        return 'evidence_outside_project'
    if not evidence.is_file() or digest(evidence.read_bytes()) != entry['evidence_sha256']:
        return 'evidence_missing_or_changed'
    return None


def matched_fields(entry, terms):
    fields = {'name': entry['name'], 'signature': entry['signature'],
              'goal': entry['goal'], 'scope': entry['scope']}
    fields.update({f'keyword_{i}': word for i, word in enumerate(entry.get('keywords', []))})
    return [key for key, value in fields.items() if (candidate := normalized(value))
            and any(term == candidate or (min(len(term), len(candidate)) >= 3
                    and (term in candidate or candidate in term)) for term in terms)]


def query(environment, terms, limit, inspect_skill):
    path = Path(environment['registry'])
    if not environment['vault_exists']:
        raise ValueError('Configured vault is unavailable')
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return {'status': 'missing', 'count': 0, 'results': [], 'excluded': []}
    registry = parse_registry(data, project_id(environment))
    terms = [normalized(term) for term in terms]
    if any(len(term) < 2 for term in terms):
        raise ValueError('Use search terms with at least two letters or digits')
    results, excluded = [], []
    entries = sorted(registry['experiences'], key=lambda entry: (
        -(entry.get('use_count') if entry.get('use_count') is not None else -1),
        -timestamp(entry['updated_at']).timestamp(), entry['id']))
    for entry in entries:
        fields = matched_fields(entry, terms)
        if terms and not fields:
            continue
        try:
            issue = (check_entry(environment, entry, inspect_skill)
                     if entry['status'] == 'approved' else entry['status'])
        except (OSError, ValueError):
            issue = 'resource_unreadable_or_invalid'
        if issue:
            excluded.append({'id': entry['id'], 'reason': issue})
        else:
            results.append({**entry, 'matched_fields': fields})
    return {'status': 'ready', 'registry_sha256': digest(data), 'registered': len(entries),
            'count': len(results), 'results': results[:limit], 'excluded': excluded}


def encode(registry):
    return (json.dumps(registry, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def initialize(environment):
    require_write_ready(environment)
    path = Path(environment['registry'])
    path.parent.mkdir(parents=True, exist_ok=True)
    data = encode({'version': 1, 'project': project_id(environment), 'experiences': []})
    with path.open('xb') as stream:
        stream.write(data)
    return {'status': 'initialized', 'registry_sha256': digest(path.read_bytes())}


def register(environment, entry, baseline, inspect_skill):
    require_write_ready(environment)
    path = Path(environment['registry'])
    lock = path.with_suffix('.lock')
    temporary = path.with_name(f'{path.name}.{uuid4().hex}.tmp')
    with lock.open('x', encoding='utf-8') as stream:
        try:
            stream.write(f'{os.getpid()}\n')
            stream.flush()
            current = path.read_bytes()
            if digest(current) != baseline:
                raise ValueError('Registry changed; review the current baseline')
            registry = parse_registry(current, project_id(environment))
            registry['experiences'].append(entry)
            updated = encode(registry)
            parse_registry(updated, project_id(environment))
            if entry['status'] != 'approved' or check_entry(environment, entry, inspect_skill):
                raise ValueError('Registration requires approved status and matching evidence and Skill')
            with temporary.open('xb') as staged:
                staged.write(updated)
            if path.read_bytes() != current:
                raise ValueError('Registry changed during registration')
            os.replace(temporary, path)
        finally:
            stream.close()
            temporary.unlink(missing_ok=True)
            lock.unlink()
    return {'status': 'registered', 'id': entry['id'], 'registry_sha256': digest(updated)}
