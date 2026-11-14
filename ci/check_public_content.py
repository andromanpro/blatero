"""Review the files selected for the public repository before publication."""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ci.check_secrets import MAX_TEXT_BYTES, scan_text

PRIVATE_PARTS = frozenset({
    ".local", ".tmp", ".release", ".projects", ".knowledge-runtime", ".meeting-memory",
    ".speaker-profiles", ".voice-profile", ".calendar-tokens", ".venv", ".venv-tts",
    "sessions", "поставки", "internal",
})
INTERNAL_DOCUMENTS = frozenset({
    "devlog.md", "agents.md", "claude.md", "audit_fix_report.md", "product_strategy.md",
})
PRIVATE_NAMES = frozenset({
    "config.json", "schedule.json", "stats.jsonl", "calendar_sources.json", "calendar_cache.json",
    ".github-token", ".gitea-token", ".call-watch-token", "release-signing-key.pem",
})
PRIVATE_SUFFIXES = frozenset({".sqlite", ".sqlite3", ".db", ".log", ".jsonl"})
TEXT_SUFFIXES = frozenset({
    ".py", ".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".ini", ".cmd",
    ".js", ".css", ".html", ".pem", ".properties", ".lock", ".cs", ".ps1", ".sh",
    ".bat", ".cfg", ".svg", ".xml", ".csv", ".rst", ".in", "",
})
PERSONAL_HOME = re.compile(
    r"(?i)\b[A-Z]:[/\\]Users[/\\](?!(?:public|default|demo|example|user)(?:[/\\]|\b))"
    r"[^\s/\\\"'<>]+[/\\]"
)


def check_inventory(root: Path, names: list[str]) -> list[str]:
    findings = []
    for name in sorted(set(names)):
        relative = PurePosixPath(name)
        basename = relative.name.casefold()
        if (PRIVATE_PARTS.intersection(part.casefold() for part in relative.parts) or basename in PRIVATE_NAMES
                or basename in INTERNAL_DOCUMENTS or basename.startswith(("audit_", "_tmp_"))
                or relative.suffix.casefold() in PRIVATE_SUFFIXES):
            findings.append(f"{name}: internal or local data file")
            continue
        path = root / name
        if path.is_symlink() or path.is_junction():
            findings.append(f"{name}: linked file requires a publication review")
            continue
        try:
            data = path.read_bytes()
        except OSError:
            findings.append(f"{name}: file could not be read")
            continue
        if relative.suffix.casefold() not in TEXT_SUFFIXES or b"\0" in data:
            continue
        if len(data) > MAX_TEXT_BYTES:
            findings.append(f"{name}: text exceeds the reviewed scan limit")
            continue
        text = data.decode("utf-8-sig", errors="replace")
        findings.extend(scan_text(Path(name), text))
        for match in PERSONAL_HOME.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"{name}:{line}: personal Windows home path")
    return findings


def check_repository(root: Path = ROOT) -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True,
                            capture_output=True)
    names = [name.decode("utf-8") for name in result.stdout.split(b"\0") if name]
    return check_inventory(root, names)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    findings = check_repository(args.root.resolve())
    for item in findings:
        print(item)
    if findings:
        return 1
    print("Public content check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
