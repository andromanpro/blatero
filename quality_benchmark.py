"""Локальный эталонный набор транскриптов и ручная разметка качества."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import threading
import uuid
import wave
from copy import deepcopy
from pathlib import Path

import transcript_eval
import transcript_events


_PRIMARY = re.compile(r"transcript(?:-[1-9]\d*)?\.jsonl", re.IGNORECASE)
_LOCK = threading.Lock()
MAX_UTTERANCES = 3_000
TARGET_MIN = 10
TARGET_MAX = 20


class BenchmarkConflictError(ValueError):
    """Эталон изменился после загрузки экрана."""


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _session(root: Path, name: object) -> Path:
    base = Path(root).resolve(strict=True)
    value = str(name or "")
    if not value or Path(value).name != value:
        raise ValueError("некорректная папка встречи")
    raw = base / value
    if raw.is_symlink():
        raise ValueError("ссылки вместо папки встречи запрещены")
    candidate = raw.resolve(strict=True)
    if candidate.parent != base or not candidate.is_dir():
        raise ValueError("встреча должна находиться прямо в локальном архиве")
    return candidate


def _journal(session: Path, name: object) -> Path:
    value = str(name or "")
    if not _PRIMARY.fullmatch(value):
        raise ValueError("разрешены только transcript.jsonl / transcript-N.jsonl")
    raw = Path(session) / value
    if raw.is_symlink():
        raise ValueError("ссылки вместо журнала встречи запрещены")
    candidate = raw.resolve(strict=True)
    if (candidate.parent != Path(session).resolve() or candidate.name != value
            or not candidate.is_file()):
        raise ValueError("журнал встречи не найден")
    return candidate


def _reference(journal: Path) -> Path:
    candidate = journal.with_name(
        journal.name.removesuffix(".jsonl") + ".reference.jsonl")
    if candidate.is_symlink():
        raise ValueError("ссылки вместо эталона запрещены")
    resolved = candidate.resolve(strict=False)
    if (resolved.parent != journal.parent.resolve()
            or resolved.name != candidate.name):
        raise ValueError("эталон должен находиться прямо в папке встречи")
    return candidate


def _state(reference: Path, journal: Path | None = None) -> str:
    if not reference.is_file():
        return "missing"
    try:
        records = transcript_events.read_records(reference)
        if journal is not None:
            source = transcript_events.read_records(journal)
            transcript_eval.validate_reference_binding(
                source, records, hypothesis_name=journal.name)
        if records and records[0].get("annotation_state") == "reviewed":
            transcript_eval.validate_reference(records)
    except (OSError, TypeError, ValueError):
        return "invalid"
    if not records or records[0].get("record_type") != "recording":
        return "invalid"
    return ("reviewed" if records[0].get("annotation_state") == "reviewed"
            else "draft")


def _etag(event: dict) -> str:
    raw = json.dumps(event, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _audio_file(session: Path, header: dict, event: dict) -> str | None:
    source = str(event.get("source") or "")
    routed_role = ({"microphone": "Я", "loopback": "Собеседник"}.get(source))
    routed = str((header.get("audio_files") or {}).get(routed_role) or "")
    name = routed or str(event.get("audio_file") or "")
    candidate = (session / name).resolve() if name else None
    return (name if candidate is not None and candidate.parent == session.resolve()
            and candidate.is_file() and Path(name).name == name else None)


def _utterance_payload(session: Path, header: dict, event: dict) -> dict:
    return {
        "event_id": str(event.get("event_id") or ""),
        "revision": _etag(event),
        "sequence": int(event.get("sequence") or 0),
        "start_ms": max(0, int(event.get("start_ms") or 0)),
        "end_ms": max(0, int(event.get("end_ms") or 0)),
        "speaker_role": str(event.get("speaker_role") or "Собеседник"),
        "speaker_id": str(event.get("speaker_id") or "unknown"),
        "speaker_name": str(event.get("speaker_name") or ""),
        "source": str(event.get("source") or "loopback"),
        "status": str(event.get("status") or "final"),
        "text": str(event.get("text") or ""),
        "annotation_confidence": event.get("annotation_confidence"),
        "annotation_note": str(event.get("annotation_note") or ""),
        "audio_file": _audio_file(session, header, event),
    }


def _session_label(session: Path) -> str:
    try:
        meta = json.loads((session / "meta.json").read_text(encoding="utf-8"))
        for key in ("title", "candidate_name", "name"):
            value = str(meta.get(key) or "").strip()
            if value:
                return value[:240]
    except (OSError, TypeError, ValueError):
        pass
    return session.name


def _journal_item(session: Path, journal: Path) -> tuple[dict, dict | None]:
    reference = _reference(journal)
    state = _state(reference, journal)
    try:
        records = transcript_events.read_records(journal)
        utterances = sum(item.get("record_type") == "utterance" for item in records)
        source_error = ""
    except (OSError, TypeError, ValueError) as exc:
        utterances, source_error, state = 0, str(exc), "invalid"
    item = {
        "session": session.name,
        "label": _session_label(session),
        "journal": journal.name,
        "reference": reference.name,
        "state": state,
        "utterances": utterances,
        "audio": sum(path.is_file() for path in session.glob("audio-*.wav")),
    }
    if source_error:
        item["error"] = f"повреждён исходный журнал: {source_error}"
    score = None
    if state in {"draft", "reviewed"}:
        try:
            score = transcript_eval.score(journal, reference, allow_draft=True)
            item["metrics"] = {key: score[key] for key in (
                "wer", "der", "jer", "channel_error_rate",
                "false_suppression_rate")}
        except (OSError, TypeError, ValueError) as exc:
            item["error"] = str(exc)
    return item, score if state == "reviewed" else None


def catalog(sessions_root: Path) -> dict:
    """Вернуть прогресс корпуса и агрегат только по подтверждённым эталонам."""
    root = Path(sessions_root).resolve(strict=True)
    items = []
    reviewed_scores = []
    for session in sorted(root.iterdir(), key=lambda item: item.name,
                          reverse=True):
        if not session.is_dir() or session.is_symlink():
            continue
        for journal in sorted(session.glob("transcript*.jsonl")):
            if (not _PRIMARY.fullmatch(journal.name) or not journal.is_file()
                    or journal.is_symlink()):
                continue
            try:
                item, score = _journal_item(session, journal)
            except (OSError, TypeError, ValueError) as exc:
                item, score = ({
                    "session": session.name,
                    "label": _session_label(session),
                    "journal": journal.name,
                    "reference": "",
                    "state": "invalid",
                    "utterances": 0,
                    "audio": sum(path.is_file()
                                 for path in session.glob("audio-*.wav")),
                    "error": str(exc),
                }, None)
            if item["utterances"] or item["state"] == "invalid":
                items.append(item)
            if score is not None:
                reviewed_scores.append(score)
    states = {name: sum(item["state"] == name for item in items)
              for name in ("missing", "draft", "reviewed", "invalid")}
    return {
        "items": items,
        "total": len(items),
        **states,
        "target_min": TARGET_MIN,
        "target_max": TARGET_MAX,
        "metrics": (transcript_eval.aggregate_scores(reviewed_scores)
                    if reviewed_scores else None),
    }


def create_reference(sessions_root: Path, session_name: object,
                     journal_name: object) -> dict:
    session = _session(sessions_root, session_name)
    journal = _journal(session, journal_name)
    reference = _reference(journal)
    with _LOCK:
        transcript_eval.init_reference(journal, reference)
    return payload(sessions_root, session.name, journal.name)


def payload(sessions_root: Path, session_name: object,
            journal_name: object) -> dict:
    session = _session(sessions_root, session_name)
    journal = _journal(session, journal_name)
    reference = _reference(journal)
    records = transcript_events.read_records(reference)
    if not records or records[0].get("record_type") != "recording":
        raise ValueError("эталон не создан или повреждён")
    items = [_utterance_payload(session, records[0], item) for item in records[1:]
             if item.get("record_type") == "utterance"]
    total = len(items)
    return {
        "session": session.name,
        "label": _session_label(session),
        "journal": journal.name,
        "reference": reference.name,
        "state": _state(reference, journal),
        "annotation_note": str(records[0].get("annotation_note") or ""),
        "utterances": items[:MAX_UTTERANCES],
        "total": total,
        "shown": min(total, MAX_UTTERANCES),
        "truncated": total > MAX_UTTERANCES,
    }


def _clean_changes(changes: object) -> dict:
    if not isinstance(changes, dict):
        raise ValueError("правка реплики должна быть объектом")
    allowed = {"text", "start_ms", "end_ms", "speaker_role", "speaker_id",
               "speaker_name", "source", "status", "annotation_confidence",
               "annotation_note", "suppression_reason"}
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"запрещённые поля правки: {sorted(unknown)}")
    return changes


def _sync_audio_file(header: dict, event: dict) -> None:
    role = {"microphone": "Я", "loopback": "Собеседник"}.get(event.get("source"))
    if role is None:
        return
    audio = str((header.get("audio_files") or {}).get(role) or "")
    if audio:
        event["audio_file"] = audio


def _validate_review_audio(session: Path, records: list[dict]) -> None:
    """Не выдавать локальную копию/пустышку за сверенный по аудио эталон."""
    if not records:
        raise ValueError("эталон не найден")
    header = records[0]
    durations: dict[str, int] = {}
    checked = 0
    for event in records[1:]:
        if (event.get("record_type") != "utterance"
                or event.get("status", "final") != "final"
                or event.get("source") not in {"microphone", "loopback"}):
            continue
        name = _audio_file(session, header, event)
        if not name:
            raise ValueError("не все реплики эталона привязаны к локальному WAV")
        if name not in durations:
            try:
                with wave.open(str(session / name), "rb") as source:
                    rate = int(source.getframerate())
                    frames = int(source.getnframes())
                    if rate <= 0 or frames <= 0 or source.getsampwidth() <= 0:
                        raise ValueError
                    durations[name] = round(frames * 1000 / rate)
            except (OSError, EOFError, wave.Error, ValueError) as exc:
                raise ValueError(f"аудиодорожка {name} повреждена или пуста") from exc
        if int(event.get("end_ms") or 0) > durations[name] + 1_000:
            raise ValueError(
                f"реплика выходит за длительность аудиодорожки {name}")
        checked += 1
    if checked == 0:
        raise ValueError(
            "эталон не содержит реплик, сверяемых с локальной аудиодорожкой")


def edit(sessions_root: Path, session_name: object, journal_name: object, *,
         event_id: object, expected_revision: object,
         changes: object) -> dict:
    session = _session(sessions_root, session_name)
    journal = _journal(session, journal_name)
    reference = _reference(journal)
    wanted = str(event_id or "")
    revision = str(expected_revision or "").lower()
    checked = _clean_changes(changes)
    if not re.fullmatch(r"[0-9a-f]{32,64}", wanted, re.IGNORECASE):
        raise ValueError("некорректный event_id")
    if not re.fullmatch(r"[0-9a-f]{64}", revision):
        raise ValueError("некорректная редакция реплики")
    with _LOCK:
        records = transcript_events.read_records(reference)
        if not records or records[0].get("annotation_state") == "reviewed":
            raise ValueError("подтверждённый эталон сначала нужно вернуть в черновик")
        matches = [item for item in records[1:]
                   if str(item.get("event_id") or "") == wanted]
        if len(matches) != 1:
            raise BenchmarkConflictError("реплика не найдена или не уникальна")
        event = matches[0]
        if _etag(event) != revision:
            raise BenchmarkConflictError(
                "эталон уже изменился; обновите экран перед сохранением")
        candidate = {**event, **checked}
        transcript_eval.validate_annotation(
            candidate, int(event.get("sequence") or 0))
        event.update(checked)
        if "source" in checked:
            _sync_audio_file(records[0], event)
        records[0]["annotation_state"] = "draft"
        records[0]["annotation_updated_at"] = _now()
        transcript_eval.write_records(reference, records)
    return {"changed": True,
            "utterance": _utterance_payload(session, records[0], event)}


def split(sessions_root: Path, session_name: object, journal_name: object, *,
          event_id: object, expected_revision: object, at_ms: object,
          left_text: object, right_text: object,
          right_changes: object | None = None) -> dict:
    """Разделить склеенную реплику, сохранив исходный event_id у первой части."""
    session = _session(sessions_root, session_name)
    journal = _journal(session, journal_name)
    reference = _reference(journal)
    wanted = str(event_id or "")
    revision = str(expected_revision or "").lower()
    if not re.fullmatch(r"[0-9a-f]{32,64}", wanted, re.IGNORECASE):
        raise ValueError("некорректный event_id")
    if not re.fullmatch(r"[0-9a-f]{64}", revision):
        raise ValueError("некорректная редакция реплики")
    try:
        boundary = int(at_ms)
    except (TypeError, ValueError) as exc:
        raise ValueError("точка разделения должна быть временем в миллисекундах") from exc
    left_value = " ".join(str(left_text or "").split()).strip()
    right_value = " ".join(str(right_text or "").split()).strip()
    if not left_value or not right_value:
        raise ValueError("у обеих частей должен быть непустой текст")
    changes = _clean_changes(right_changes or {})
    forbidden = set(changes) & {"text", "start_ms", "end_ms"}
    if forbidden:
        raise ValueError("текст и время частей передаются отдельными полями")

    with _LOCK:
        records = transcript_events.read_records(reference)
        if not records or records[0].get("annotation_state") == "reviewed":
            raise ValueError("подтверждённый эталон сначала нужно вернуть в черновик")
        matches = [(index, item) for index, item in enumerate(records[1:], 1)
                   if str(item.get("event_id") or "") == wanted]
        if len(matches) != 1:
            raise BenchmarkConflictError("реплика не найдена или не уникальна")
        index, event = matches[0]
        if _etag(event) != revision:
            raise BenchmarkConflictError(
                "эталон уже изменился; обновите экран перед разделением")
        start, end = int(event.get("start_ms") or 0), int(event.get("end_ms") or 0)
        if boundary < start + 200 or boundary > end - 200:
            raise ValueError("оставьте не менее 0,2 секунды у каждой части")
        sequence = int(event.get("sequence") or 0)
        for later in records[index + 1:]:
            if (later.get("record_type") == "utterance"
                    and int(later.get("sequence") or 0) > sequence):
                later["sequence"] = int(later["sequence"]) + 1
        right = deepcopy(event)
        event["text"], event["end_ms"] = left_value, boundary
        event["words"] = []
        event["word_timing_state"] = "invalidated_by_reference_split"
        right.update(changes)
        right.update({
            "event_id": uuid.uuid4().hex,
            "sequence": sequence + 1,
            "start_ms": boundary,
            "end_ms": end,
            "text": right_value,
            "words": [],
            "word_timing_state": "invalidated_by_reference_split",
            "reference_split_from": wanted,
        })
        try:
            captured = dt.datetime.fromisoformat(str(event.get("captured_at")))
            right["captured_at"] = (captured + dt.timedelta(
                milliseconds=boundary - start)).isoformat(timespec="milliseconds")
        except (TypeError, ValueError):
            pass
        _sync_audio_file(records[0], right)
        transcript_eval.validate_annotation(event, sequence)
        transcript_eval.validate_annotation(right, sequence + 1)
        records.insert(index + 1, right)
        records[0]["annotation_state"] = "draft"
        records[0]["annotation_updated_at"] = _now()
        transcript_eval.write_records(reference, records)
    return payload(sessions_root, session.name, journal.name)


def set_reviewed(sessions_root: Path, session_name: object,
                 journal_name: object, *, reviewed: bool,
                 confirmed: bool = False) -> dict:
    session = _session(sessions_root, session_name)
    journal = _journal(session, journal_name)
    reference = _reference(journal)
    if reviewed and confirmed is not True:
        raise ValueError("подтвердите, что реплики сверены с аудио")
    with _LOCK:
        records = transcript_events.read_records(reference)
        if not records:
            raise ValueError("эталон не найден")
        current = records[0].get("annotation_state") == "reviewed"
        if current == reviewed:
            return payload(sessions_root, session.name, journal.name)
        if reviewed:
            transcript_eval.validate_reference_binding(
                transcript_events.read_records(journal), records,
                hypothesis_name=journal.name)
            _validate_review_audio(session, records)
            transcript_eval.finalize_reference(reference)
        else:
            records[0]["annotation_state"] = "draft"
            records[0]["annotation_reopened_at"] = _now()
            transcript_eval.write_records(reference, records)
    return payload(sessions_root, session.name, journal.name)
