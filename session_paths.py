"""Portable, explicit session locations shared by read-only history adapters."""
import os
from pathlib import Path


def codex_roots():
    candidates = [Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex'),
                  Path.home() / '.codex']
    return list(dict.fromkeys(candidates))


def codex_state_path():
    if os.environ.get('CODEX_HOME'):
        return Path(os.environ['CODEX_HOME']) / 'state_5.sqlite'
    roots = codex_roots()
    return next((root / 'state_5.sqlite' for root in roots if (root / 'state_5.sqlite').is_file()),
                roots[0] / 'state_5.sqlite')
