"""Версионированный журнал реплик и совместимый Markdown-транскрипт."""
from __future__ import annotations

import contextlib
import argparse
import datetime as dt
import json
import math
import os
import re
import uuid
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = 1
REMOTE_ROLE = "Собеседник"
_TRANSCRIPT_NAME = re.compile(r"transcript(?:-(\d+))?\.md", re.IGNORECASE)
_LEGACY_HEADER = re.compile(
    r"^#\s+Транскрипт:\s*(?P<title>.+?)\s+—\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2})\s*$")
_LEGACY_TURN = re.compile(
    r"^-\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"\*\*\[(?P<speaker>Я|Собеседник)\]\*\*\s+(?P<text>.+?)\s*$")
_SOURCE_BY_ROLE = {"Я": "microphone", REMOTE_ROLE: "loopback"}
_SPEAKER_BY_ROLE = {"Я": "local", REMOTE_ROLE: "remote_mix"}
_SOURCES = frozenset({"microphone", "loopback", "synthetic", "manual", "import"})


def journal_path(markdown_path: Path) -> Path:
    """Парный JSONL для transcript.md / transcript-N.md."""
    return Path(markdown_path).with_suffix(".jsonl")


def segment_number(markdown_path: Path) -> int:
    match = _TRANSCRIPT_NAME.fullmatch(Path(markdown_path).name)
    return int(match.group(1) or 1) if match else 1


@contextlib.contextmanager
def _locked_text(path: Path, mode: str) -> Iterator:
    """Эксклюзивная межпроцессная блокировка первого байта файла."""
    handle = Path(path).open(mode, encoding="utf-8", newline="")
    locked = False
    try:
        handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        locked = True
        yield handle
    finally:
        if locked:
            handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _iso_now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _parse_iso(value: object) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.astimezone()


def _confidence(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return round(min(1.0, max(0.0, number)), 6) if math.isfinite(number) else None


def event_confidence(event: dict) -> float | None:
    """Вернуть только содержательную оценку уверенности провайдера.

    SpeechKit v3 пока не использует поле ``Alternative.confidence`` и отдаёт
    protobuf-значение по умолчанию 0. Такой ноль означает «метрики нет», а не
    гарантированно плохое распознавание. Ненулевое значение сохраняем на случай,
    если провайдер начнёт заполнять поле в будущем.
    """
    confidence = _confidence(event.get("confidence"))
    provider = str(event.get("provider") or "").strip().casefold()
    if confidence == 0.0 and provider.startswith("yandex"):
        return None
    return confidence


def create_journal(path: Path, *, title: str, provider: str, segment: int,
                   audio_files: dict[str, str] | None = None,
                   speaker_names: dict[str, str] | None = None,
                   started_at: str | None = None,
                   recording_id: str | None = None) -> dict:
    """Создать JSONL и записать его единственную служебную header-запись."""
    header = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "recording",
        "recording_id": recording_id or uuid.uuid4().hex,
        "segment": max(1, int(segment)),
        "title": _clean_text(title) or "встреча",
        "started_at": started_at or _iso_now(),
        "provider": _clean_text(provider) or "unknown",
        "audio_files": {
            role: _clean_text(name)
            for role, name in (audio_files or {}).items() if _clean_text(name)
        },
        "speaker_names": {
            role: _clean_text(name)
            for role, name in (speaker_names or {}).items() if _clean_text(name)
        },
    }
    with Path(path).open("x", encoding="utf-8", newline="") as output:
        output.write(json.dumps(header, ensure_ascii=False) + "\n")
    return header


def _records_from_handle(handle) -> list[dict]:
    handle.seek(0)
    records = []
    for number, line in enumerate(handle, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"повреждён JSONL, строка {number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"повреждён JSONL, строка {number}: ожидался объект")
        records.append(value)
    return records


def read_records(path: Path) -> list[dict]:
    with _locked_text(Path(path), "r+") as handle:
        return _records_from_handle(handle)


def read_records_bytes(raw: bytes) -> list[dict]:
    from io import StringIO
    return _records_from_handle(StringIO(raw.decode("utf-8"), newline=None))


def _normalize_words(words: object, fallback_start: int) -> list[dict]:
    if not isinstance(words, list):
        return []
    result = []
    for item in words[:500]:
        if not isinstance(item, dict):
            continue
        text = _clean_text(item.get("text"))
        if not text:
            continue
        try:
            start = max(0, int(item.get("start_ms", fallback_start)))
            end = max(start, int(item.get("end_ms", start)))
        except (TypeError, ValueError):
            continue
        result.append({"text": text, "start_ms": start, "end_ms": end})
    return result


def _next_sequence(records: list[dict]) -> int:
    return max((int(item.get("sequence", 0)) for item in records
                if item.get("record_type") == "utterance"), default=0) + 1


def _event_timing(header: dict, meta: dict) -> tuple[int, int, str]:
    started = _parse_iso(header["started_at"])
    now = dt.datetime.now().astimezone()
    default_ms = max(0, round((now - started).total_seconds() * 1000))
    try:
        start_ms = max(0, int(meta.get("start_ms", default_ms)))
        end_ms = max(start_ms, int(meta.get("end_ms", start_ms)))
    except (TypeError, ValueError):
        start_ms = end_ms = default_ms
    captured_at = (started + dt.timedelta(milliseconds=start_ms)).isoformat(
        timespec="milliseconds")
    return start_ms, end_ms, captured_at


def _event_source(speaker: str, meta: dict) -> str:
    requested = _clean_text(meta.get("source"))
    return requested if requested in _SOURCES else _SOURCE_BY_ROLE[speaker]


def _event_audio_file(header: dict, meta: dict, speaker: str,
                      source: str) -> str | None:
    if "audio_file" in meta or source == "synthetic":
        return _clean_text(meta.get("audio_file")) or None
    return _clean_text((header.get("audio_files") or {}).get(speaker)) or None


def _event_record(header: dict, sequence: int, speaker: str, text: str,
                  meta: dict, provider: str | None) -> dict:
    start_ms, end_ms, captured_at = _event_timing(header, meta)
    source = _event_source(speaker, meta)
    speaker_names = header.get("speaker_names") or {}
    return {
        "schema_version": SCHEMA_VERSION, "record_type": "utterance",
        "event_id": uuid.uuid4().hex,
        "recording_id": str(header.get("recording_id", "")),
        "sequence": sequence, "segment": int(header.get("segment", 1)),
        "start_ms": start_ms, "end_ms": end_ms, "captured_at": captured_at,
        "received_at": _iso_now(), "source": source, "speaker_role": speaker,
        "speaker_id": (_clean_text(meta.get("speaker_id"))
                       or _SPEAKER_BY_ROLE[speaker]),
        "speaker_name": (_clean_text(meta.get("speaker_name"))
                         or _clean_text(speaker_names.get(speaker)) or None),
        "text": text, "confidence": _confidence(meta.get("confidence")),
        "provider": (_clean_text(provider) or _clean_text(meta.get("provider"))
                     or str(header.get("provider", "unknown"))),
        "audio_file": _event_audio_file(header, meta, speaker, source),
        "status": _clean_text(meta.get("status")) or "final",
        "suppression_reason": _clean_text(meta.get("suppression_reason")) or None,
        "echo_similarity": _confidence(meta.get("echo_similarity")),
        "timing_source": _clean_text(meta.get("timing_source")) or "wall_clock",
        "words": _normalize_words(meta.get("words"), start_ms),
    }


def _add_legacy_metadata(event: dict, meta: dict) -> None:
    if meta.get("legacy_line") is not None:
        event["legacy_line"] = int(meta["legacy_line"])
    if _clean_text(meta.get("legacy_timestamp")):
        event["legacy_timestamp"] = _clean_text(meta["legacy_timestamp"])


def append_event(path: Path, speaker: str, text: str, *,
                 metadata: dict | None = None, provider: str | None = None) -> dict:
    """Добавить финальную реплику; безопасно для live.py и процесса панели."""
    cleaned = _clean_text(text)
    if speaker not in _SOURCE_BY_ROLE or not cleaned:
        raise ValueError("реплика должна иметь роль Я/Собеседник и непустой текст")
    meta = metadata if isinstance(metadata, dict) else {}
    with _locked_text(Path(path), "r+") as handle:
        records = _records_from_handle(handle)
        if not records or records[0].get("record_type") != "recording":
            raise ValueError("в transcript.jsonl отсутствует recording header")
        header = records[0]
        event = _event_record(
            header, _next_sequence(records), speaker, cleaned, meta, provider)
        _add_legacy_metadata(event, meta)
        handle.seek(0, os.SEEK_END)
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event


def markdown_line(event: dict) -> str:
    captured = _parse_iso(event["captured_at"])
    role = str(event.get("speaker_role") or REMOTE_ROLE)
    return f"- {captured:%H:%M:%S} **[{role}]** {_clean_text(event.get('text'))}\n"


def append_markdown_event(path: Path, event: dict) -> None:
    with _locked_text(Path(path), "r+") as output:
        output.seek(0, os.SEEK_END)
        output.write(markdown_line(event))


def append_transcript_turn(markdown_path: Path, speaker: str, text: str, *,
                           metadata: dict | None = None,
                           provider: str | None = None) -> dict | None:
    """Добавить в JSONL+Markdown; legacy-сессии без JSONL оставить рабочими."""
    markdown_path = Path(markdown_path)
    paired = journal_path(markdown_path)
    if paired.exists():
        # Markdown служит общей блокировкой транзакции: два процесса не смогут
        # переставить в читаемом файле уже пронумерованные JSONL-события.
        with _locked_text(markdown_path, "r+") as output:
            event = append_event(paired, speaker, text, metadata=metadata,
                                 provider=provider)
            output.seek(0, os.SEEK_END)
            output.write(markdown_line(event))
        return event
    cleaned = _clean_text(text)
    if speaker not in _SOURCE_BY_ROLE or not cleaned:
        return None
    with _locked_text(markdown_path, "r+") as output:
        output.seek(0, os.SEEK_END)
        output.write(f"- {dt.datetime.now():%H:%M:%S} **[{speaker}]** {cleaned}\n")
    return None


def render_markdown(path: Path, output_path: Path | None = None) -> str:
    """Восстановить Markdown из JSONL и при необходимости атомарно записать."""
    records = read_records(Path(path))
    if not records or records[0].get("record_type") != "recording":
        raise ValueError("в transcript.jsonl отсутствует recording header")
    header = records[0]
    started = _parse_iso(header["started_at"])
    title = _clean_text(header.get("title")) or "встреча"
    utterances = [item for item in records
                  if item.get("record_type") == "utterance"
                  and item.get("status", "final") == "final"]
    # Два STT-потока завершают фразы с разной задержкой. sequence отражает
    # порядок получения результата, а не разговора; итоговый документ должен
    # идти по общей временной шкале записи.
    utterances.sort(key=lambda item: (int(item.get("start_ms", 0)),
                                      int(item.get("end_ms", 0)),
                                      int(item.get("sequence", 0))))
    text = (f"# Транскрипт: {title} — {started:%Y-%m-%d %H:%M}\n\n"
            + "".join(markdown_line(item) for item in utterances))
    if output_path is not None:
        target = Path(output_path)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target)
    return text


def _legacy_audio_files(markdown_path: Path) -> dict[str, str]:
    suffix = "" if segment_number(markdown_path) == 1 else (
        f"-{segment_number(markdown_path)}")
    candidates = {
        "Я": f"audio-me{suffix}.wav",
        REMOTE_ROLE: f"audio-guest{suffix}.wav",
    }
    return {role: name for role, name in candidates.items()
            if (markdown_path.parent / name).exists()}


def _legacy_duration_ms(text: str) -> int:
    """Грубая длительность речи; timestamp старого формата означал её конец."""
    words = max(1, len(_clean_text(text).split()))
    return max(700, min(120_000, round(words / 2.35 * 1000)))


def _legacy_header(lines: list[str]) -> tuple[re.Match, dt.datetime]:
    if not lines:
        raise ValueError("пустой Markdown-транскрипт")
    match = _LEGACY_HEADER.fullmatch(lines[0].strip())
    if not match:
        raise ValueError("не распознан заголовок старого транскрипта")
    started = dt.datetime.fromisoformat(
        f"{match['date']}T{match['time']}:00").astimezone()
    return match, started


def _crossed_midnight(clock: dt.time, previous: dt.time | None,
                      started: dt.datetime) -> bool:
    if previous is not None:
        return clock < previous
    clock_at_start_date = dt.datetime.combine(started.date(), clock)
    meeting_start = dt.datetime.combine(started.date(), started.time())
    return clock < started.time() and meeting_start - clock_at_start_date > dt.timedelta(
        hours=12)


def _legacy_turns(lines: list[str], started: dt.datetime) -> list[tuple]:
    result = []
    current_date = started.date()
    previous_clock: dt.time | None = None
    for line_number, line in enumerate(lines[1:], 2):
        match = _LEGACY_TURN.fullmatch(line.strip())
        if not match:
            continue
        clock = dt.time.fromisoformat(match["time"])
        if _crossed_midnight(clock, previous_clock, started):
            current_date += dt.timedelta(days=1)
        captured = dt.datetime.combine(current_date, clock, tzinfo=started.tzinfo)
        end_ms = max(0, round((captured - started).total_seconds() * 1000))
        result.append((line_number, match["speaker"], match["text"], end_ms,
                       match["time"]))
        previous_clock = clock
    if not result:
        raise ValueError("в Markdown не найдены реплики")
    return result


def _append_legacy_turns(output: Path, turns: list[tuple]) -> None:
    previous_end = 0
    for line_number, speaker, text, end_ms, legacy_timestamp in turns:
        start_ms = max(previous_end, end_ms - _legacy_duration_ms(text))
        append_event(
            output, speaker, text, provider="legacy_markdown",
            metadata={
                "start_ms": start_ms, "end_ms": max(start_ms, end_ms),
                "timing_source": "legacy_result_timestamp_estimate",
                "legacy_line": line_number,
                "legacy_timestamp": legacy_timestamp,
            })
        previous_end = max(start_ms, end_ms)


def migrate_legacy(markdown_path: Path, output_path: Path | None = None) -> Path:
    """Импортировать старый Markdown в JSONL, не изменяя исходный файл.

    Старый журнал сохранял только время получения финального результата. Поэтому
    начало реплики оценивается по числу слов и не пересекает предыдущую реплику.
    """
    markdown_path = Path(markdown_path)
    output = Path(output_path) if output_path else journal_path(markdown_path)
    if output.exists():
        raise FileExistsError(f"JSONL уже существует: {output}")
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    header_match, started = _legacy_header(lines)
    turns = _legacy_turns(lines, started)

    created = False
    try:
        create_journal(
            output, title=header_match["title"], provider="legacy_markdown",
            segment=segment_number(markdown_path),
            audio_files=_legacy_audio_files(markdown_path),
            started_at=started.isoformat(timespec="milliseconds"))
        created = True
        _append_legacy_turns(output, turns)
    except Exception:
        if created and output.exists():
            output.unlink()
        raise
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    rebuild = sub.add_parser("rebuild", help="восстановить Markdown из JSONL")
    rebuild.add_argument("journal", type=Path)
    rebuild.add_argument("output", type=Path, nargs="?")
    migrate = sub.add_parser(
        "migrate", help="импортировать старый Markdown в новый JSONL")
    migrate.add_argument("markdown", type=Path)
    migrate.add_argument("output", type=Path, nargs="?")
    args = parser.parse_args()
    if args.command == "rebuild":
        output = args.output or args.journal.with_suffix(".md")
        render_markdown(args.journal, output)
        print(f"Markdown восстановлен: {output}")
    elif args.command == "migrate":
        output = migrate_legacy(args.markdown, args.output)
        print(f"JSONL создан без изменения Markdown: {output}")


if __name__ == "__main__":
    main()
