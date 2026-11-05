"""Высокоточный поиск случайно закоммиченных секретов.

Сканируются только файлы под контролем Git. Проверки намеренно консервативны:
лучше пропустить нестандартный секрет, чем приучить команду игнорировать шумный CI.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_BYTES = 2_000_000
PLACEHOLDERS = re.compile(
    r"(?i)(?:example|placeholder|changeme|your[-_]|dummy|fake|test[-_]|"
    r"do-not-leak|very-secret|valid-secret|openai-secret|anthropic-secret|"
    r"stable-secret|secret-token|user:password@|\$\{|<[^>]+>)"
)
SENSITIVE_KEYS = (
    "DATABASE_URL|DB_URL|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|"
    "AZURE_CLIENT_SECRET|GOOGLE_CLIENT_SECRET|GITEA_TOKEN|GITHUB_TOKEN|"
    "OPENAI_API_KEY|ANTHROPIC_API_KEY|OPENROUTER_API_KEY|DEEPSEEK_API_KEY|"
    "BLATERO_LLM_API_KEY|YANDEX_API_KEY|CALDAV_PASSWORD"
)
PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{24,}\b")),
    (
        "credentialed connection string",
        re.compile(
            r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://"
            r"[^/\s:@]+:[^@\s/]+@"
        ),
    ),
    (
        "credentialed SQL connection string",
        re.compile(
            r"(?i)\b(?:server|data\s+source)=[^;\r\n]+;"
            r"(?:[^;\r\n]+;){0,8}(?:password|pwd)=[^;\s\"'}]{4,}"
        ),
    ),
    (
        "sensitive assignment",
        re.compile(
            rf"(?im)(?:^|[{{,]\s*)(?:export\s+)?[\"']?(?:{SENSITIVE_KEYS})"
            r"[\"']?\s*[:=]\s*[\"']?[^\s\"',}\]]{16,}"
        ),
    ),
)


def tracked_files(root: Path = ROOT) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True
    )
    return [
        root / item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]


def scan_text(path: Path, text: str) -> list[str]:
    findings = []
    accepted_spans: list[tuple[int, int]] = []
    for label, pattern in PATTERNS:
        for match in pattern.finditer(text):
            fragment = match.group(0)
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            if line_end < 0:
                line_end = len(text)
            if "pragma: allowlist secret" in text[line_start:line_end].casefold():
                continue
            if PLACEHOLDERS.search(fragment):
                continue
            if any(match.start() < end and match.end() > start for start, end in accepted_spans):
                continue
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"{path.as_posix()}:{line}: возможен {label}")
            accepted_spans.append(match.span())
    return findings


def scan_repository(root: Path = ROOT) -> list[str]:
    findings = []
    for path in tracked_files(root):
        try:
            data = path.read_bytes()
        except OSError as exc:
            findings.append(f"{path.as_posix()}: файл не прочитан: {exc}")
            continue
        if len(data) > MAX_TEXT_BYTES or b"\0" in data:
            continue
        text = data.decode("utf-8", errors="replace")
        findings.extend(scan_text(path.relative_to(root), text))
    return findings


def main() -> int:
    findings = scan_repository()
    if findings:
        print("Secret gate: найдены подозрительные значения:", file=sys.stderr)
        print("\n".join(f"- {item}" for item in findings), file=sys.stderr)
        return 1
    print("Secret gate: tracked-файлы чисты")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
