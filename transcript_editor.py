"""Локальное редактирование финальных реплик канонического транскрипта."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import threading
import uuid
from pathlib import Path

import transcript_events


SCHEMA_VERSION = 1
AUDIT_FILE = "transcript-edits.jsonl"
MAX_TEXT_LENGTH = 12_000
MAX_UTTERANCES = 3_000
_PRIMARY_JOURNAL = re.compile(r"transcript(?:-[1-9]\d*)?\.jsonl", re.IGNORECASE)
_EDIT_LOCK = threading.Lock()


class EditConflictError(ValueError):
    """Реплика изменилась после загрузки редактора."""


def _iso_now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _clean_text(value: object) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        raise ValueError("текст реплики не может быть пустым")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"реплика длиннее {MAX_TEXT_LENGTH} знаков")
    if "\x00" in text:
        raise ValueError("текст реплики содержит недопустимый символ")
    return text


def _journal_path(session: Path, journal_name: object, *, must_exist: bool = True) -> Path:
    name = str(journal_name or "")
    if not _PRIMARY_JOURNAL.fullmatch(name):
        raise ValueError("разрешены только основные журналы transcript.jsonl / transcript-N.jsonl")
    root = Path(session).resolve(strict=True)
    candidate = (root / name).resolve(strict=must_exist)
    if candidate.parent != root or candidate.name != name:
        raise ValueError("журнал должен находиться прямо в папке встречи")
    if must_exist and not candidate.is_file():
        raise ValueError("журнал транскрипта не найден")
    return candidate


def _journals(session: Path) -> list[Path]:
    root = Path(session).resolve(strict=True)
    result = []
    for candidate in root.glob("transcript*.jsonl"):
        if (_PRIMARY_JOURNAL.fullmatch(candidate.name) and candidate.is_file()
                and candidate.resolve().parent == root):
            result.append(candidate)
    return sorted(result, key=lambda item: transcript_events.segment_number(
        item.with_suffix(".md")))


def _etag(event: dict) -> str:
    encoded = json.dumps(
        event, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _audio_file(session: Path, event: dict) -> str | None:
    name = str(event.get("audio_file") or "").strip()
    if not name or Path(name).name != name or not name.lower().endswith(".wav"):
        return None
    candidate = (session / name).resolve()
    return name if candidate.parent == session.resolve() and candidate.is_file() else None


def _payload_item(session: Path, journal: Path, event: dict) -> dict:
    confidence = transcript_events.event_confidence(event)
    return {
        "journal": journal.name,
        "event_id": str(event.get("event_id") or ""),
        "revision": _etag(event),
        "segment": int(event.get("segment") or transcript_events.segment_number(
            journal.with_suffix(".md"))),
        "sequence": int(event.get("sequence") or 0),
        "start_ms": max(0, int(event.get("start_ms") or 0)),
        "end_ms": max(0, int(event.get("end_ms") or 0)),
        "speaker_role": str(event.get("speaker_role") or "Собеседник"),
        "speaker_id": str(event.get("speaker_id") or ""),
        "speaker_name": str(event.get("speaker_name") or "").strip() or None,
        "source": str(event.get("source") or ""),
        "text": str(event.get("text") or ""),
        "confidence": confidence,
        "audio_file": _audio_file(session, event),
        "edited": event.get("edited_by_user") is True,
        "edit_revision": max(0, int(event.get("edit_revision") or 0)),
        "edited_at": str(event.get("edited_at") or "") or None,
    }


def payload(session: Path) -> dict:
    """Вернуть финальные реплики основных сегментов, не включая производные копии."""
    root = Path(session).resolve(strict=True)
    items = []
    journals = _journals(root)
    for journal in journals:
        records = transcript_events.read_records(journal)
        for event in records:
            if (event.get("record_type") != "utterance"
                    or event.get("status", "final") != "final"):
                continue
            if not str(event.get("event_id") or "").strip():
                continue
            items.append(_payload_item(root, journal, event))
    items.sort(key=lambda item: (
        item["segment"], item["start_ms"], item["end_ms"], item["sequence"]))
    total = len(items)
    return {
        "session": root.name,
        "journals": [item.name for item in journals],
        "utterances": items[:MAX_UTTERANCES],
        "total": total,
        "shown": min(total, MAX_UTTERANCES),
        "truncated": total > MAX_UTTERANCES,
    }


def _serialize(records: list[dict]) -> bytes:
    return ("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records)
            .encode("utf-8"))


def _atomic_bytes(path: Path, content: bytes) -> None:
    tmp = path.with_name(path.name + ".edit.tmp")
    try:
        with tmp.open("wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _restore(path: Path, existed: bool, content: bytes) -> None:
    if existed:
        _atomic_bytes(path, content)
    else:
        path.unlink(missing_ok=True)


def _backup_path(journal: Path) -> Path:
    suffix = journal.name.removesuffix(".jsonl")
    return journal.with_name(f"{suffix}.before-manual-edit.jsonl")


def edit(session: Path, *, journal_name: object, event_id: object,
         expected_revision: object, text: object) -> dict:
    """Изменить одну реплику атомарно и сохранить локальный след правки."""
    root = Path(session).resolve(strict=True)
    journal = _journal_path(root, journal_name)
    wanted_id = str(event_id or "").strip()
    wanted_revision = str(expected_revision or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32,64}", wanted_id, re.IGNORECASE):
        raise ValueError("некорректный event_id реплики")
    if not re.fullmatch(r"[0-9a-f]{64}", wanted_revision):
        raise ValueError("некорректная редакция реплики")
    cleaned = _clean_text(text)

    with _EDIT_LOCK:
        records = transcript_events.read_records(journal)
        matches = [item for item in records
                   if item.get("record_type") == "utterance"
                   and str(item.get("event_id") or "") == wanted_id]
        if len(matches) != 1:
            raise EditConflictError("реплика не найдена или event_id не уникален")
        current = matches[0]
        if current.get("status", "final") != "final":
            raise ValueError("редактировать можно только финальную реплику")
        if _etag(current) != wanted_revision:
            raise EditConflictError(
                "реплика уже изменилась; перезагрузите редактор")
        previous_text = str(current.get("text") or "")
        if cleaned == previous_text:
            return {"changed": False, "utterance": _payload_item(root, journal, current)}

        old_journal = journal.read_bytes()
        markdown = journal.with_suffix(".md")
        old_markdown_exists = markdown.exists()
        old_markdown = markdown.read_bytes() if old_markdown_exists else b""
        backup = _backup_path(journal)
        old_backup_exists = backup.exists()
        old_backup = backup.read_bytes() if old_backup_exists else b""
        audit = root / AUDIT_FILE
        old_audit_exists = audit.exists()
        old_audit = audit.read_bytes() if old_audit_exists else b""

        current.setdefault("original_text", previous_text)
        current["text"] = cleaned
        current["edited_by_user"] = True
        current["edited_at"] = _iso_now()
        current["edit_revision"] = max(0, int(current.get("edit_revision") or 0)) + 1
        if current.get("words"):
            current["words"] = []
            current["word_timing_state"] = "invalidated_by_manual_edit"
        after_revision = _etag(current)
        audit_record = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "transcript_edit",
            "edit_id": uuid.uuid4().hex,
            "edited_at": current["edited_at"],
            "journal": journal.name,
            "event_id": wanted_id,
            "event_revision_before": wanted_revision,
            "event_revision_after": after_revision,
            "edit_revision": current["edit_revision"],
            "previous_text": previous_text,
            "new_text": cleaned,
        }
        new_audit = old_audit + (json.dumps(
            audit_record, ensure_ascii=False) + "\n").encode("utf-8")

        try:
            _atomic_bytes(backup, old_journal)
            _atomic_bytes(journal, _serialize(records))
            transcript_events.render_markdown(journal, markdown)
            _atomic_bytes(audit, new_audit)
        except Exception:
            _restore(journal, True, old_journal)
            _restore(markdown, old_markdown_exists, old_markdown)
            _restore(backup, old_backup_exists, old_backup)
            _restore(audit, old_audit_exists, old_audit)
            raise

        return {
            "changed": True,
            "utterance": _payload_item(root, journal, current),
            "audit_file": AUDIT_FILE,
            "backup_file": backup.name,
        }
