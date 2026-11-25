"""Keep temporary-vault tests independent of the developer's selected vault."""
import os
from unittest.mock import patch


def isolate_vault_environment(test):
    clean = dict(os.environ)
    clean.pop('JARVIS_VAULT_ROOT', None)
    test.enterContext(patch.dict(os.environ, clean, clear=True))
    if os.name == 'nt':
        test.enterContext(patch('winreg.QueryValueEx', side_effect=FileNotFoundError))
