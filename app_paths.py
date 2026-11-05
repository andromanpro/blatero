"""Stable locations for program files and mutable user data.

Development checkouts retain the historical layout by default. Installed
copies may point to a separate data directory with ``BLATERO_DATA_DIR`` or a
local ``.blatero-data-dir`` pointer created by the installer. The pointer is
not shipped in release archives, so updates cannot overwrite user data.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
DATA_POINTER = APP_ROOT / ".blatero-data-dir"


def _expanded_path(value: str) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(value.strip()))
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = APP_ROOT / candidate
    return candidate.resolve()


def resolve_data_root() -> Path:
    configured = os.getenv("BLATERO_DATA_DIR", "").strip()
    if configured:
        return _expanded_path(configured)
    try:
        pointed = DATA_POINTER.read_text(encoding="utf-8").strip()
    except OSError:
        pointed = ""
    return _expanded_path(pointed) if pointed else APP_ROOT


DATA_ROOT = resolve_data_root()
SESSIONS_ROOT = DATA_ROOT / "sessions"
MODELS_ROOT = DATA_ROOT / ".models"
UPDATE_ROOT = DATA_ROOT / ".updates"


def ensure_data_root() -> Path:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    return DATA_ROOT
