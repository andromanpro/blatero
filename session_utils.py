"""Безопасные имена и порядок файлов сессий."""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path


_TRANSCRIPT_SEGMENT = re.compile(
    r"transcript(?:-(\d+))?\.md", re.IGNORECASE)


def safe_component(value: object, *, max_length: int = 60) -> str:
    """Преобразовать пользовательское значение в один компонент имени файла."""
    text = str(value or "").strip().replace(" ", "_")
    text = re.sub(r"[^\w-]+", "_", text, flags=re.UNICODE).strip("_.-")
    return (text[:max_length] or "meeting")


def schedule_slug(meeting: dict) -> str:
    """Проверенный slug встречи из schedule.json без разделителей пути."""
    date_text = str(meeting.get("date", ""))
    time_text = str(meeting.get("time", ""))
    try:
        dt.date.fromisoformat(date_text)
        parsed_time = dt.datetime.strptime(time_text, "%H:%M").time()
    except ValueError as exc:
        raise ValueError(
            f"некорректные дата/время встречи: {date_text!r} {time_text!r}"
        ) from exc
    name_text = str(meeting.get("name", "")).strip()
    if not name_text:
        raise ValueError("у встречи не задано имя")
    if len(name_text) > 200 or any(ord(char) < 32 for char in name_text):
        raise ValueError("имя встречи должно содержать 1–200 печатных символов")
    return f"{date_text}_{parsed_time:%H%M}_{safe_component(name_text)}"


def direct_child(root: Path, name: str, *, must_exist: bool = False) -> Path:
    """Вернуть только прямого ребёнка root; абсолютные пути и traversal запрещены."""
    root = root.resolve()
    raw = Path(str(name))
    if raw.is_absolute() or raw.name != str(name) or str(name) in ("", ".", ".."):
        raise ValueError("сессия должна быть именем прямого подкаталога sessions")
    candidate = (root / raw).resolve()
    if candidate.parent != root:
        raise ValueError("путь сессии выходит за пределы sessions")
    if must_exist and not candidate.is_dir():
        raise ValueError(f"сессия не найдена: {name}")
    return candidate


def unique_session_dir(root: Path, base_slug: str) -> Path:
    """Атомарно создать уникальную папку, добавляя -2, -3, ... при коллизии."""
    root.mkdir(parents=True, exist_ok=True)
    for number in range(1, 10_000):
        suffix = "" if number == 1 else f"-{number}"
        candidate = direct_child(root, base_slug + suffix)
        try:
            candidate.mkdir(exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError("не удалось подобрать уникальное имя сессии")


def transcript_sort_key(path: Path) -> tuple[int, str]:
    """Хронологический порядок transcript.md, transcript-2.md, ..."""
    match = _TRANSCRIPT_SEGMENT.fullmatch(path.name)
    if not match or (match.group(1) is not None
                     and (int(match.group(1)) < 2
                          or str(int(match.group(1))) != match.group(1))):
        return (10**9, path.name.casefold())
    return (int(match.group(1) or 1), path.name.casefold())


def is_transcript_segment(path: Path) -> bool:
    """Отличить первичный сегмент от refined/reference/notes-файлов."""
    match = _TRANSCRIPT_SEGMENT.fullmatch(Path(path).name)
    if match is None or match.group(1) is None:
        return match is not None
    number = match.group(1)
    return int(number) >= 2 and str(int(number)) == number


def transcript_segments(session: Path) -> list[Path]:
    """Канонические Markdown-сегменты встречи в числовой хронологии."""
    return sorted(
        (path for path in Path(session).glob("transcript*.md")
         if is_transcript_segment(path)),
        key=transcript_sort_key)
