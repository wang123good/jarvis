"""Keep temporary-vault tests independent of the developer's selected vault."""
import os
from unittest.mock import patch


def isolate_vault_environment(test):
    clean = dict(os.environ)
    clean.pop('JARVIS_VAULT_ROOT', None)
    test.enterContext(patch.dict(os.environ, clean, clear=True))
    if os.name == 'nt':
        test.enterContext(patch('winreg.QueryValueEx', side_effect=FileNotFoundError))

def configure_fixture(project, vault):
    from pathlib import Path
    import shutil
    from setup_environment import configure

    source = Path(__file__).resolve().parents[1]
    for name in ('config/defaults.json', '.codex/obsidian-kb.json'):
        target = project / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target)
    configure(project, str(vault))
    from resolve_environment import resolve_environment
    return resolve_environment(project)
