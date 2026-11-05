"""Merge native hooks, preserving existing Neon/status/quality hooks and settings."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import uuid
from pathlib import Path

from project_queue import atomic_json
from project_store import Store


def definitions(system: str) -> dict:
    script = Path(__file__).with_name("project_agent_hook.py").as_posix()
    command = f'py -3.14 "{script}" {system}' if os.name == "nt" else f'python3 "{script}" {system}'
    events = ["SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"]
    if system == "codex":
        events.append("Interrupt")
    return {event: [{"hooks": [{"type": "command", "command": command, "timeout": 3}]}]
            for event in events}


def merge(path: Path, system: str, *, dry_run=False) -> dict:
    original = json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}
    groups = original.setdefault("hooks", {})
    added = 0
    for event, entries in definitions(system).items():
        current = groups.setdefault(event, [])
        # Our definitions only: another plugin/user hook is never removed or rewritten.
        ours = [e for e in current if any("project_agent_hook.py" in h.get("command", "")
                                         for h in e.get("hooks", []))]
        if ours == entries:
            continue
        if ours:
            raise ValueError("старые определения Blatero требуют явной замены: " + str(path))
        current.extend(entries)
        added += len(entries)
    result = {"path": str(path), "added": added, "system": system, "dry_run": dry_run}
    if not dry_run and added:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            backup = path.with_name(path.name + ".before-blatero-" + uuid.uuid4().hex[:8])
            shutil.copy2(path, backup)
            result["backup"] = str(backup)
        atomic_json(path, original)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Установить локальные хуки задач Blatero")
    parser.add_argument("--codex", type=Path, required=True, help="активный hooks.json")
    parser.add_argument("--claude", type=Path, help="settings.json Claude Code")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run:
        Store().local_agent()
    results = [merge(args.codex, "codex", dry_run=args.dry_run)]
    if args.claude:
        results.append(merge(args.claude, "claude-code", dry_run=args.dry_run))
    print(json.dumps({"files": results, "codex_activation": "Новые определения требуют доверия через /hooks. "
                     "Установщик не изменяет доверие и не обходит проверку."}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
