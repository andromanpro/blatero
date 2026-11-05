"""Read-only web presentation of saved meeting results. No generation or writes."""

from __future__ import annotations

import datetime as dt
from html import escape
from pathlib import Path
from urllib.parse import quote

from markdown_it import MarkdownIt

import report
import report_review

MAX_REPORT_BYTES = 2_000_000


def _file(session: Path, name: str) -> Path | None:
    path = session / name
    if path.is_symlink() or not path.is_file() or path.resolve().parent != session.resolve():
        return None
    return path


def summary(session: Path) -> dict:
    """Cheap metadata for init; source validity is checked on opening the result."""
    session = Path(session)
    final = _file(session, "report.md")
    draft = _file(session, "report.draft.md")
    docx = report.find_report_docx(session)
    if docx and (docx.is_symlink() or docx.resolve().parent != session.resolve()):
        docx = None
    return {
        "has_final": bool(final),
        "has_draft": bool(draft),
        "report_revision": [
            (p.stat().st_mtime_ns, p.stat().st_size) if p else None for p in (final, draft)
        ],
        "docx_url": (
            f"/files/{quote(session.name, safe='')}/{quote(docx.name, safe='')}" if docx else ""
        ),
        "docx_name": docx.name if docx else "",
    }


def render_markdown(markdown: str) -> tuple[str, list[dict]]:
    """Markdown with tables, but no raw HTML, remote resources or active links."""
    renderer = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")
    renderer.renderer.rules["image"] = lambda tokens, idx, *_: escape(tokens[idx].content)
    renderer.renderer.rules["link_open"] = lambda *_: ""
    renderer.renderer.rules["link_close"] = lambda *_: ""
    tokens = renderer.parse(markdown)
    headings = []
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            anchor = f"report-section-{len(headings)}"
            token.attrSet("id", anchor)
            headings.append(
                {"id": anchor, "level": int(token.tag[1:]), "text": tokens[i + 1].content}
            )
    return renderer.renderer.render(tokens, renderer.options, {}), headings


def payload(session: Path, source: str = "auto") -> dict:
    if source not in {"auto", "final", "draft"}:
        raise ValueError("неизвестный вид отчёта")
    session = Path(session)
    info = summary(session)
    manifest = report_review.load(session)
    pending = manifest.get("state") in {"needs_review", "ready", "stale", "blocked"}
    kind = (
        source
        if source != "auto"
        else (
            "draft" if pending and info["has_draft"] else "final" if info["has_final"] else "draft"
        )
    )
    path = _file(session, "report.md" if kind == "final" else "report.draft.md")
    if not path:
        raise FileNotFoundError("сохранённый отчёт не найден")
    with path.open("rb") as stream:
        raw = stream.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError("отчёт слишком большой для веб-просмотра; откройте файл")
    text = raw.decode("utf-8-sig", errors="replace")
    if not text.strip():
        raise ValueError("сохранённый отчёт пуст")
    stale = None
    source_revision = None
    if manifest.get("source_hash"):
        try:
            source_revision = report.source_fingerprint(session)
            stale = source_revision != manifest["source_hash"]
        except (OSError, ValueError, KeyError):
            stale = None
    html, headings = render_markdown(text)
    return {
        **info,
        "session": session.name,
        "kind": kind,
        "html": html,
        "headings": headings,
        "stale": stale,
        "source_revision": source_revision,
        "confirmed": kind == "final" and manifest.get("state") == "finalized",
        "review_state": manifest.get("state", "none"),
        "modified_at": dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat(),
        "filename": path.name,
    }
