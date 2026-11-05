"""Compile shipped user Markdown into browser-readable, offline-only HTML."""

from html import escape
from html.parser import HTMLParser
from pathlib import Path
import os
import re
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

CSS = """
body{margin:0;background:#07111e;color:#d6e6f5;font:17px/1.65 system-ui,sans-serif}
nav{padding:16px 24px;background:#0d2033;position:sticky;top:0;display:flex;gap:24px;flex-wrap:wrap}
a{color:#6ddcff}main{max-width:1040px;margin:auto;padding:24px}
h1,h2,h3{line-height:1.25;color:#fff;scroll-margin-top:80px}
img{max-width:100%;height:auto}table{border-collapse:collapse;width:100%;display:block;overflow:auto}
th,td{border:1px solid #35506a;padding:10px;text-align:left;min-width:100px}
pre{overflow:auto;background:#102438;padding:16px}code{overflow-wrap:anywhere}
blockquote{border-left:3px solid #4ed4e5;padding-left:16px;margin-left:0}
@media(max-width:600px){main{padding:16px}body{font-size:16px}}
"""


def _relative(target: Path, source: Path) -> str:
    return Path(os.path.relpath(target, source.parent)).as_posix()


def _inside(folder: Path, source: Path, value: str) -> Path | None:
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    path = (source.parent / unquote(parsed.path)).resolve()
    return path if path.is_relative_to(folder) else None


def _navigation(folder: Path, source: Path, english: bool) -> str:
    home = source.parent / "Home.md"
    if not home.is_file():
        home = folder / "wiki" / "Home.md"
    href = _relative(home.with_suffix(".html"), source)
    label = "Blatero · Help" if english else "Blatero · Справка"
    links = f"<a href='{escape(href, quote=True)}'>{label}</a>"
    other = source.parent.parent / source.name if english else source.parent / "en" / source.name
    if other.is_file() and other.resolve().is_relative_to(folder):
        language = "ru" if english else "en"
        text = "Русский" if english else "English"
        links += (
            f"<a lang='{language}' hreflang='{language}' href='"
            f"{escape(_relative(other.with_suffix('.html'), source), quote=True)}'>{text}</a>"
        )
    return links


def build(folder: Path) -> int:
    folder = folder.resolve()
    parser = MarkdownIt("commonmark", {"html": False}).enable("table")
    count = 0
    for source in sorted(folder.rglob("*.md")):
        english = "en" in source.relative_to(folder).parts[:-1]
        tokens = parser.parse(source.read_text(encoding="utf-8"))
        for index, token in enumerate(tokens):
            if token.type == "heading_open" and index + 1 < len(tokens):
                slug = re.sub(r"[^\w\s-]", "", tokens[index + 1].content.lower())
                token.attrSet("id", re.sub(r"\s+", "-", slug.strip()))
        for token in tokens:
            for child in token.children or []:
                if child.type == "link_open":
                    href = child.attrGet("href") or ""
                    parsed = urlsplit(href)
                    target = _inside(folder, source, href)
                    if target and target.suffix != ".md":
                        target = target.with_name(target.name + ".md")
                    if target and target.is_file():
                        child.attrSet(
                            "href",
                            _relative(target.with_suffix(".html"), source)
                            + ("#" + parsed.fragment if parsed.fragment else ""),
                        )
                elif child.type == "image":
                    src = child.attrGet("src") or ""
                    # Never fetch external resources just by opening local help.
                    target = _inside(folder, source, src)
                    if (
                        not target
                        or not target.is_file()
                        or target.suffix.lower()
                        not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
                    ):
                        child.attrSet("src", "")
        body = parser.renderer.render(tokens, parser.options, {})
        language = "en" if english else "ru"
        html = (
            f"<!doctype html><html lang='{language}'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<meta http-equiv='Content-Security-Policy' content=\""
            "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline';\">"
            f"<title>Blatero — {escape(source.stem)}</title><style>{CSS}</style>"
            f"<nav>{_navigation(folder, source, english)}</nav><main>{body}</main></html>"
        )
        source.with_suffix(".html").write_text(html, encoding="utf-8")
        count += 1
    return count


class _Page(HTMLParser):
    def __init__(self, value: str):
        super().__init__()
        self.ids = set()
        self.links = []
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "a" and values.get("href"):
            self.links.append((values["href"], False))
        if tag == "img":
            self.links.append((values.get("src", ""), True))


def validate(folder: Path) -> list[str]:
    """Check the complete assembled tree, not Markdown-only link guesses."""
    folder = folder.resolve()
    pages = {p.resolve(): _Page(p.read_text(encoding="utf-8")) for p in folder.rglob("*.html")}
    errors = []
    for source, page in pages.items():
        for value, image in page.links:
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc:
                if image or parsed.scheme not in {"http", "https", "mailto"}:
                    errors.append(f"{source.relative_to(folder)}: unsafe resource {value}")
                continue
            target = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
            if not value or not target.is_relative_to(folder) or not target.is_file():
                errors.append(f"{source.relative_to(folder)}: missing or escaping resource {value}")
            elif (
                parsed.fragment
                and target in pages
                and unquote(parsed.fragment) not in pages[target].ids
            ):
                errors.append(f"{source.relative_to(folder)}: missing anchor {value}")
    return errors
