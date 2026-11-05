"""Owner-controlled optional adapters. Disabled adapters perform no discovery or I/O.

Stored separately from meeting/audio configuration; toggling never deletes source links.
"""
from __future__ import annotations

import json

from project_store import Conflict

KEY = "optional-connections-v1"
DEFAULTS = {"neon": False, "granka": False}


def read(store):
    with store.connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (KEY,)).fetchone()
    try:
        value = json.loads(row[0]) if row else {}
    except (ValueError, TypeError):
        value = {}
    flags = value.get("enabled", {}) if isinstance(value, dict) else {}
    if not isinstance(flags, dict):
        flags = {}
    revision = value.get("revision", 0) if isinstance(value, dict) else 0
    if type(revision) is not int or revision < 0:
        revision = 0
    return {"revision": revision,
            "enabled": {name: flags.get(name) is True for name in DEFAULTS}}


def enabled(store, name):
    return read(store)["enabled"].get(name, False)


def update(store, body):
    flags = body.get("enabled")
    if not isinstance(flags, dict) or set(flags) != set(DEFAULTS) or any(type(v) is not bool for v in flags.values()):
        raise ValueError("enabled must contain boolean neon and granka flags")
    if type(body.get("revision")) is not int:
        raise ValueError("revision is required")
    with store.transaction() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (KEY,)).fetchone()
        current = json.loads(row[0]) if row else {"revision": 0}
        if current["revision"] != body["revision"]:
            raise Conflict("Connection settings changed; reload before saving")
        result = {"revision": current["revision"] + 1, "enabled": flags}
        conn.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (KEY, json.dumps(result)))
    return result
