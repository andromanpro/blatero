"""Изолированные повторы архивного аудио через STT/AEC/диаризацию."""
from __future__ import annotations

import datetime as dt
import difflib
import filecmp
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
import wave
from pathlib import Path

import audio_echo
import copilot
import evidence
import pulse_timing
import speaker_diarization
import transcript_backfill
import transcript_eval
import transcript_events
from meeting_types import preset


ROOT_NAME = "replay-runs"
MANIFEST_NAME = "replay.json"
COMPARISON_NAME = "comparison.json"
SCHEMA_VERSION = 1
_RUN_ID = re.compile(r"run-\d{8}-\d{6}-[a-f0-9]{6}")
_BATCH_ID = re.compile(r"matrix-\d{8}-\d{6}-[a-f0-9]{6}")
_AUDIO_NAME = transcript_backfill._AUDIO_NAME
_MODELS = frozenset({"tiny", "base", "small", "medium", "large-v3"})
_AEC = frozenset({"off", "correlation", "auto", "native"})
_RUN_FILE = re.compile(
    r"(?:replay|comparison|diarization)\.json|"
    r"transcript(?:\.local(?:\.diarized)?|\.diarized)?\.(?:jsonl|md)|"
    r"hints\.jsonl|audio-clean\.wav|meta\.json|"
    r"(?:questions|dossier|workspace-context|agenda|interview-script|"
    r"rubric|brief)\.md")
_PROMOTED_FILES = (
    "transcript.local.jsonl", "transcript.local.diarized.jsonl",
    "diarization.json",
)
_STALE_SPEAKER_FILES = (
    "speaker-map.json", "transcript.refined.jsonl", "transcript.refined.md",
    evidence.DIARIZED_OUTPUT,
)
_ACTIVE: set[Path] = set()
_ACTIVE_BATCH_IDS: dict[Path, str] = {}
_CANCELLED: set[Path] = set()
_ACTIVE_BATCHES: set[Path] = set()
_CANCELLED_BATCHES: set[str] = set()
_LOCK = threading.RLock()


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _manifest(run: Path) -> dict:
    value = json.loads((run / MANIFEST_NAME).read_text(encoding="utf-8"))
    if (not isinstance(value, dict)
            or value.get("schema_version") != SCHEMA_VERSION
            or value.get("run_id") != run.name):
        raise ValueError(f"повреждённый Replay run: {run.name}")
    return value


def _run_dir(session: Path, run_id: str, *, must_exist: bool = True) -> Path:
    if not _RUN_ID.fullmatch(str(run_id)):
        raise ValueError("недопустимый идентификатор Replay run")
    root = (Path(session).resolve() / ROOT_NAME).resolve()
    run = (root / str(run_id)).resolve()
    if run.parent != root:
        raise ValueError("Replay run находится вне папки результатов")
    if must_exist and not run.is_dir():
        raise FileNotFoundError("Replay run не найден")
    return run


def _audio_seconds(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as source:
            return round(source.getnframes() / max(1, source.getframerate()), 2)
    except (OSError, EOFError, wave.Error):
        return None


def _options(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("настройки Replay Lab должны быть JSON-объектом")
    audio_name = str(value.get("audio_name") or "")
    model = str(value.get("model") or "small")
    aec = str(value.get("aec") or "off")
    if Path(audio_name).name != audio_name or not _AUDIO_NAME.fullmatch(audio_name):
        raise ValueError("выберите WAV-канал audio-me/audio-guest")
    if model not in _MODELS:
        raise ValueError("неизвестная модель Whisper")
    if aec not in _AEC:
        raise ValueError("неизвестный режим AEC")
    if aec != "off" and not audio_name.casefold().startswith("audio-me"):
        raise ValueError("AEC применим только к микрофонной дорожке")
    try:
        speakers = int(value.get("speakers", 2))
        threshold = float(value.get("threshold", 0.5))
    except (TypeError, ValueError) as exc:
        raise ValueError("некорректные параметры диаризации") from exc
    if not 0 <= speakers <= 20:
        raise ValueError("число говорящих должно быть от 0 (авто) до 20")
    if not 0 < threshold <= 1:
        raise ValueError("порог диаризации должен быть от 0 до 1")
    embedding = str(value.get("diarization_embedding")
                    or speaker_diarization.DEFAULT_DIARIZATION_EMBEDDING)
    if embedding not in speaker_diarization.DIARIZATION_EMBEDDINGS:
        raise ValueError("неизвестная модель голосовых признаков")
    try:
        beam = int(value.get("stt_beam", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError("некорректный beam_size распознавания") from exc
    if not 1 <= beam <= 5:
        raise ValueError("beam_size распознавания должен быть от 1 до 5")
    return {
        "audio_name": audio_name, "model": model, "aec": aec,
        "diarization": value.get("diarization") is True,
        "speakers": speakers, "threshold": round(threshold, 3),
        "diarization_embedding": embedding,
        "generate_hint": value.get("generate_hint") is True,
        "stt_beam": beam,
        "reuse_transcript": value.get("reuse_transcript") is not False,
    }


def _matching_render(session: Path, audio_name: str) -> Path:
    suffix = audio_name[len("audio-me"):]
    render = Path(session) / f"audio-guest{suffix}"
    if not render.is_file():
        raise FileNotFoundError(
            f"для AEC нужна парная системная дорожка {render.name}")
    return render


def _file_sha256(path: Path, copy_to=None) -> str:
    if path.is_symlink():
        raise ValueError("Replay не читает источник через ссылку")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            if copy_to is not None:
                copy_to.write(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("Источник изменился во время проверки; создайте новый прогон")
    return digest.hexdigest()


def _source_identity(session: Path, options: dict) -> dict:
    identity = {"sha256": _file_sha256(session / options["audio_name"])}
    if options["aec"] != "off":
        identity["render_sha256"] = _file_sha256(
            _matching_render(session, options["audio_name"]))
    header = _source_header(session, options["audio_name"])
    identity["recording_sha256"] = hashlib.sha256(
        json.dumps(header, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return identity


def _verify_source(session: Path, run: Path, value: dict, *, persist=True) -> dict:
    """Fail closed even when an input cannot be read (unknown is not unchanged)."""
    try:
        identity = _source_identity(session, value["options"])
    except (OSError, ValueError, KeyError):
        if persist:
            _update(run, source_unchanged=None)
        raise
    if any(value.get("source", {}).get(k) != v for k, v in identity.items()):
        if persist:
            _update(run, source_unchanged=False)
        raise ValueError("Источник изменился или не подтверждён; создайте новый Replay run")
    if persist:
        _update(run, source_unchanged=True)
    return identity


def _verify_completed(session: Path, run: Path, value: dict, *, persist=True,
                      read_journal=False) -> bytes | None:
    _verify_source(session, run, value, persist=persist)
    expected = value.get("output_sha256") or {}
    cleaned = run / "audio-clean.wav"
    if (cleaned.exists() or cleaned.is_symlink() or cleaned.name in expected
            or cleaned.name in (value.get("outputs") or [])):
        if (not cleaned.is_file() or not expected.get(cleaned.name)
                or _file_sha256(cleaned) != expected[cleaned.name]):
            raise ValueError("Очищенная дорожка Replay изменена или недоступна; выполните новый прогон")
    journal = _run_journal(run)
    names = {"transcript.local.jsonl", journal.name}
    if value.get("options", {}).get("diarization"):
        names.update(_PROMOTED_FILES)
    for name in names:
        if read_journal and name == journal.name:
            continue
        if not expected.get(name) or _file_sha256(run / name) != expected[name]:
            raise ValueError("Результат Replay изменён или не подтверждён; выполните новый прогон")
    if read_journal:
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as checked:
            if not expected.get(journal.name) or _file_sha256(journal, checked) != expected[journal.name]:
                raise ValueError("Результат Replay изменён или не подтверждён; выполните новый прогон")
            checked.seek(0)
            return checked.read()
    return None


def _source_header(session: Path, audio_name: str) -> dict:
    suffix = audio_name[len("audio-me"):].removesuffix(".wav") \
        if audio_name.casefold().startswith("audio-me") else \
        audio_name[len("audio-guest"):].removesuffix(".wav")
    journal = Path(session) / f"transcript{suffix}.jsonl"
    candidates = [journal, Path(session) / "transcript.jsonl"]
    candidates.extend(sorted(Path(session).glob("transcript*.jsonl")))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            records = transcript_events.read_records(candidate)
            if records and records[0].get("record_type") == "recording":
                return records[0]
        except (OSError, ValueError):
            continue
    meta_path = Path(session) / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        started = dt.datetime.fromisoformat(
            f"{meta['date']}T{meta.get('time') or '00:00'}:00").astimezone()
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "не найден transcript*.jsonl и недостаточно meta.json для Replay") from exc
    return {
        "record_type": "recording", "title": str(meta.get("name") or "встреча"),
        "started_at": started.isoformat(timespec="milliseconds"), "segment": 1,
    }


def _safe_context_copy(session: Path, run: Path) -> None:
    meta = {}
    try:
        raw = json.loads((session / "meta.json").read_text(encoding="utf-8"))
        meta = {key: raw[key] for key in (
            "name", "type", "date", "time", "duration") if key in raw}
    except (OSError, TypeError, ValueError):
        pass
    _atomic_json(run / "meta.json", meta)
    meeting = preset(str(meta.get("type") or "встреча"))
    names = {"questions.md", "dossier.md", "workspace-context.md",
             str(meeting.get("agenda_file") or "agenda.md")}
    for name in names:
        source = session / name
        if source.is_file() and source.stat().st_size <= 1_000_000:
            (run / name).write_text(
                source.read_text(encoding="utf-8", errors="replace"),
                encoding="utf-8")


def _assert_available(session: Path) -> None:
    resolved_root = (session / ROOT_NAME).resolve()
    with _LOCK:
        if (resolved_root in _ACTIVE_BATCHES
                or any(item.parent == resolved_root for item in _ACTIVE)):
            raise RuntimeError("Для этой встречи уже выполняется Replay run")


def _create_run(session: Path, checked: dict, *, batch: dict | None = None) -> dict:
    audio = session / checked["audio_name"]
    if not audio.is_file():
        raise FileNotFoundError("исходная аудиодорожка не найдена")
    if checked["aec"] != "off":
        _matching_render(session, checked["audio_name"])
    identity = _source_identity(session, checked)
    root = session / ROOT_NAME
    run_id = dt.datetime.now().strftime("run-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    root.mkdir(exist_ok=True)
    run = _run_dir(session, run_id, must_exist=False)
    run.mkdir()
    manifest = {
        "schema_version": SCHEMA_VERSION, "run_id": run_id,
        "created_at": _now(), "updated_at": _now(), "state": "queued",
        "stage": "queued", "progress": 0, "message": "Ожидает запуска",
        "source": {"session": session.name, "audio_name": audio.name,
                   "seconds": _audio_seconds(audio),
                   "bytes": audio.stat().st_size, **identity},
        "options": checked, "stt": transcript_backfill.recipe_metadata(),
        "source_unchanged": True,
    }
    if batch:
        manifest["batch"] = dict(batch)
    _atomic_json(run / MANIFEST_NAME, manifest)
    return manifest


def prepare_run(session: Path, options: object) -> dict:
    session = Path(session).resolve()
    checked = _options(options)
    _assert_available(session)
    return _create_run(session, checked)


def _matrix_variants(options: object, preset_name: str) -> list[tuple[str, dict]]:
    base = _options(options)
    if base["generate_hint"]:
        raise ValueError(
            "контрольная LLM-подсказка недоступна в пакетной матрице")
    preset_name = str(preset_name or "").strip().lower()
    raw: list[tuple[str, dict]] = []
    if preset_name == "stt":
        for model in ("base", "small", "medium"):
            raw.append((f"Whisper {model}", {**base, "model": model}))
    elif preset_name == "aec":
        if not base["audio_name"].casefold().startswith("audio-me"):
            raise ValueError("матрица AEC доступна только для микрофонной дорожки")
        for aec, label in (("off", "без AEC"),
                           ("correlation", "корреляционный AEC"),
                           ("auto", "WebRTC AEC3 → резерв")):
            raw.append((label, {**base, "aec": aec}))
    elif preset_name == "speakers":
        for embedding, threshold, label in (
                ("nemo", 0.4, "NeMo · порог 0,40"),
                ("nemo", 0.5, "NeMo · порог 0,50"),
                ("nemo", 0.6, "NeMo · порог 0,60"),
                ("3dspeaker", 0.5, "3D-Speaker · порог 0,50")):
            raw.append((label, {**base, "diarization": True,
                                "diarization_embedding": embedding,
                                "threshold": threshold}))
    else:
        raise ValueError("неизвестная пакетная матрица Replay Lab")
    unique: list[tuple[str, dict]] = []
    seen: set[str] = set()
    for label, item in raw:
        checked = _options(item)
        marker = json.dumps(checked, ensure_ascii=False, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            unique.append((label, checked))
    if not 2 <= len(unique) <= 6:
        raise ValueError("матрица должна содержать от 2 до 6 вариантов")
    return unique


def prepare_matrix(session: Path, options: object, preset_name: str) -> dict:
    """Атомарно подготовить несколько изолированных вариантов одного WAV."""
    session = Path(session).resolve()
    variants = _matrix_variants(options, preset_name)
    _assert_available(session)
    batch_id = (dt.datetime.now().strftime("matrix-%Y%m%d-%H%M%S-")
                + uuid.uuid4().hex[:6])
    created: list[dict] = []
    try:
        for index, (label, checked) in enumerate(variants, 1):
            created.append(_create_run(session, checked, batch={
                "batch_id": batch_id, "preset": str(preset_name),
                "index": index, "total": len(variants), "label": label,
            }))
    except Exception:
        for item in created:
            shutil.rmtree(_run_dir(session, item["run_id"]), ignore_errors=True)
        root = session / ROOT_NAME
        if root.is_dir() and not any(root.iterdir()):
            root.rmdir()
        raise
    return {"batch_id": batch_id, "preset": str(preset_name),
            "runs": created, "count": len(created)}


def _update(run: Path, **changes) -> dict:
    with _LOCK:
        value = _manifest(run)
        value.update(changes)
        value["updated_at"] = _now()
        _atomic_json(run / MANIFEST_NAME, value)
        return value


class _Progress:
    def __init__(self, run: Path):
        self.run = run
        self.last_percent = -1
        self.last_write = 0.0

    def set(self, stage: str, percent: int, message: str, *, force: bool = False):
        checked = max(0, min(99, int(percent)))
        now = time.monotonic()
        if (not force and checked == self.last_percent
                and now - self.last_write < 0.75):
            return
        self.last_percent = checked
        self.last_write = now
        _update(self.run, state="running", stage=stage,
                progress=checked, message=str(message)[:300])

    def portion(self, stage: str, start: int, end: int, done: int, total: int,
                message: str):
        ratio = done / max(1, total)
        self.set(stage, start + round((end - start) * min(1.0, ratio)), message)


def _is_cancelled(run: Path) -> bool:
    with _LOCK:
        batch_id = _ACTIVE_BATCH_IDS.get(run, "")
        return run in _CANCELLED or bool(
            batch_id and batch_id in _CANCELLED_BATCHES)


def request_cancel(session: Path, run_id: str) -> dict:
    run = _run_dir(session, run_id)
    value = _manifest(run)
    if value.get("state") not in {"queued", "running"}:
        return value
    batch_id = str((value.get("batch") or {}).get("batch_id") or "")
    with _LOCK:
        _CANCELLED.add(run)
        if batch_id:
            _CANCELLED_BATCHES.add(batch_id)
    if batch_id:
        for sibling in run.parent.iterdir():
            if not sibling.is_dir() or not _RUN_ID.fullmatch(sibling.name):
                continue
            try:
                sibling_value = _manifest(sibling)
            except (OSError, TypeError, ValueError):
                continue
            if (str((sibling_value.get("batch") or {}).get("batch_id") or "")
                    == batch_id and sibling_value.get("state") == "queued"):
                _update(sibling, state="cancelled", stage="cancelled", progress=0,
                        message="Пакетная матрица остановлена пользователем",
                        completed_at=_now())
    return _update(run, cancel_requested=True,
                   message=("Останавливаю всю матрицу после текущей операции…"
                            if batch_id else
                            "Останавливаю после текущей операции…"))


def reserve_run(session: Path, run_id: str) -> dict:
    """Пометить queued-run активным до передачи в занятый thread pool."""
    run = _run_dir(session, run_id)
    value = _manifest(run)
    if value.get("state") != "queued":
        raise ValueError("зарезервировать можно только ожидающий Replay run")
    with _LOCK:
        other = [item for item in _ACTIVE
                 if item.parent == run.parent and item != run]
        if other:
            raise RuntimeError("Для этой встречи уже выполняется Replay run")
        _ACTIVE.add(run)
    return value


def reserve_matrix(session: Path, batch_id: str, run_ids: list[str]) -> dict:
    """Зарезервировать встречу на всё последовательное выполнение матрицы."""
    session = Path(session).resolve()
    if not _BATCH_ID.fullmatch(str(batch_id)):
        raise ValueError("недопустимый идентификатор матрицы Replay Lab")
    if not isinstance(run_ids, list) or not 2 <= len(run_ids) <= 6:
        raise ValueError("матрица должна содержать от 2 до 6 вариантов")
    root = (session / ROOT_NAME).resolve()
    values = []
    for run_id in run_ids:
        run = _run_dir(session, run_id)
        value = _manifest(run)
        if (value.get("state") != "queued"
                or (value.get("batch") or {}).get("batch_id") != batch_id):
            raise ValueError("вариант не принадлежит ожидающей матрице")
        values.append(value)
    with _LOCK:
        if root in _ACTIVE_BATCHES or any(item.parent == root for item in _ACTIVE):
            raise RuntimeError("Для этой встречи уже выполняется Replay run")
        _ACTIVE_BATCHES.add(root)
    return {"batch_id": batch_id, "runs": values}


def _reusable_transcript(session: Path, options: dict, identity: dict) -> tuple[str, Path] | None:
    """Готовый транскрипт завершённого прогона с теми же параметрами STT.

    Матрица кластеризации и повторный разбор делят одинаковый этап Whisper;
    переиспользуется только транскрипт, записанный версией с явным stt_beam.
    """
    if not options.get("reuse_transcript", True):
        return None
    root = session / ROOT_NAME
    if not root.is_dir():
        return None
    wanted = (options["audio_name"], options["model"], options["aec"],
              int(options.get("stt_beam", 1)))
    for candidate in sorted(root.iterdir()):
        if not candidate.is_dir() or not _RUN_ID.fullmatch(candidate.name):
            continue
        journal = candidate / "transcript.local.jsonl"
        if not journal.is_file():
            continue
        try:
            value = _manifest(candidate)
        except (OSError, TypeError, ValueError):
            continue
        other = value.get("options") or {}
        if not isinstance(other, dict) or not isinstance(value.get("source"), dict):
            continue
        if (value.get("state") != "completed"
                or not _uses_current_stt_recipe(value)
                or "stt_beam" not in other):
            continue
        try:
            key = (other.get("audio_name"), other.get("model"), other.get("aec"),
                   int(other.get("stt_beam", 1)))
            source = value.get("source") or {}
            if (key == wanted and all(source.get(k) == v for k, v in identity.items())
                    and value.get("transcript_sha256") == _file_sha256(journal)):
                return str(value.get("run_id") or candidate.name), journal
        except (OSError, TypeError, ValueError):
            continue
    return None


def _diarization_speaker_stats(path: Path | None) -> dict[str, dict[str, int]]:
    if path is None or not Path(path).is_file():
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    stats: dict[str, dict[str, int]] = {}
    for segment in payload.get("segments", []):
        if not isinstance(segment, dict):
            continue
        speaker = str(segment.get("speaker_id") or "")
        if not speaker:
            continue
        try:
            start_ms = max(0, int(segment.get("start_ms", 0)))
            end_ms = max(start_ms, int(segment.get("end_ms", start_ms)))
        except (TypeError, ValueError):
            continue
        item = stats.setdefault(speaker, {
            "utterances": 0, "words": 0, "duration_ms": 0})
        item["utterances"] += 1
        item["duration_ms"] += end_ms - start_ms
    return stats


def _quality(journal: Path, diarization: Path | None = None) -> dict:
    records = transcript_events.read_records(journal)
    utterances = [item for item in records[1:]
                  if item.get("record_type") == "utterance"
                  and item.get("status", "final") == "final"]
    confidences = [confidence for item in utterances
                   if (confidence := transcript_events.event_confidence(item))
                   is not None]
    speaker_stats: dict[str, dict[str, int]] = {}
    for item in utterances:
        speaker = str(item.get("speaker_id") or "")
        if not speaker:
            continue
        stats = speaker_stats.setdefault(
            speaker, {"utterances": 0, "words": 0, "duration_ms": 0})
        stats["utterances"] += 1
        stats["words"] += len(str(item.get("text") or "").split())
        stats["duration_ms"] += max(
            0, int(item.get("end_ms", 0)) - int(item.get("start_ms", 0)))
    journal_speakers = speaker_stats
    diarization_speakers = _diarization_speaker_stats(diarization)
    balance_speakers = diarization_speakers or journal_speakers
    total_speaker_duration = sum(
        item["duration_ms"] for item in balance_speakers.values())
    dominant_share = (max(
        (item["duration_ms"] for item in balance_speakers.values()), default=0)
        / max(1, total_speaker_duration))
    tiny_clusters = sum(
        1 for item in balance_speakers.values()
        if item["duration_ms"] < 4_000
        or (not diarization_speakers and item["words"] < 8))
    needs_speaker_review = bool(
        len(balance_speakers) > 1
        and (dominant_share >= 0.82 or tiny_clusters > 0))
    return {
        "utterances": len(utterances),
        "words": sum(len(str(item.get("text") or "").split()) for item in utterances),
        "duration_ms": max((int(item.get("end_ms", 0)) for item in utterances),
                           default=0),
        "speakers": len(balance_speakers),
        "utterance_speakers": len(journal_speakers),
        "average_confidence": (round(sum(confidences) / len(confidences), 4)
                               if confidences else None),
        "confidence_kind": "raw_model_word_probability",
        "confidence_calibrated": False,
        "speaker_balance": {
            "dominant_share": round(dominant_share, 4),
            "tiny_clusters": tiny_clusters,
            "needs_review": needs_speaker_review,
        },
    }


def _track_records(records: list[dict], audio_name: str) -> list[dict]:
    if not records:
        return []
    utterances = [item for item in records[1:]
                  if item.get("record_type") == "utterance"]
    selected = [item for item in utterances
                if str(item.get("audio_file") or "") == audio_name]
    if not selected:
        source = "microphone" if audio_name.startswith("audio-me") else "loopback"
        selected = [item for item in utterances
                    if str(item.get("source") or "") == source]
    return [records[0], *selected] if selected else []


def _reference(session: Path, audio_name: str) -> tuple[Path | None, str]:
    candidates = sorted(session.glob("transcript*.reference.jsonl"))
    reviewed = []
    drafts = []
    found_reference = False
    for path in candidates:
        try:
            records = transcript_events.read_records(path)
            found_reference = True
            baseline_name = str(records[0].get("reference_for") or "")
            if Path(baseline_name).name != baseline_name:
                continue
            baseline = session / baseline_name
            if not baseline.is_file():
                continue
            transcript_eval.validate_reference_binding(
                transcript_events.read_records(baseline), records,
                hypothesis_name=baseline.name)
            if not _track_records(records, audio_name):
                continue
            (reviewed if records[0].get("annotation_state") == "reviewed"
             else drafts).append(path)
        except (OSError, IndexError, ValueError):
            continue
    if reviewed:
        return reviewed[0], "reviewed"
    if drafts:
        return drafts[0], "draft"
    return None, "incompatible" if found_reference else "missing"


def _safe_score(hypothesis: Path, reference: Path, audio_name: str) -> dict:
    hypothesis_records = _track_records(
        transcript_events.read_records(hypothesis), audio_name)
    reference_records = _track_records(
        transcript_events.read_records(reference), audio_name)
    raw = transcript_eval.score_records(
        hypothesis_records, reference_records, allow_draft=True)
    return {key: raw[key] for key in (
        "wer", "der", "jer", "channel_error_rate", "channel_coverage",
        "echo_precision", "echo_recall", "false_suppression_rate")}


def _baseline(session: Path, reference: Path) -> Path | None:
    try:
        records = transcript_events.read_records(reference)
        name = str(records[0].get("reference_for") or "")
        if Path(name).name == name and (session / name).is_file():
            return session / name
    except (OSError, IndexError, ValueError):
        pass
    return session / "transcript.jsonl" if (session / "transcript.jsonl").is_file() else None


def _comparison(session: Path, journal: Path, aec: dict | None,
                audio_name: str, diarization: Path | None = None) -> dict:
    reference, reference_state = _reference(session, audio_name)
    result = {"schema_version": 1, "created_at": _now(),
              "quality": _quality(journal, diarization),
              "reference_state": reference_state,
              "reference_name": reference.name if reference else "", "aec": aec}
    if reference:
        result["replay"] = _safe_score(journal, reference, audio_name)
        baseline = _baseline(session, reference)
        if baseline:
            result["baseline_name"] = baseline.name
            result["baseline"] = _safe_score(baseline, reference, audio_name)
            result["delta"] = {
                key: round(result["replay"][key] - result["baseline"][key], 6)
                for key in result["replay"]}
    return result


def _hint(run: Path) -> dict:
    hints = copilot.pulse(run, [])
    return {
        "answers": len(hints.get("answers", [])),
        "questions": len(hints.get("questions", [])),
        "flags": len(hints.get("flags", [])),
        "first_question": str((hints.get("questions") or [{}])[0].get("q") or ""),
    }


def execute_run(session: Path, run_id: str) -> dict:
    session = Path(session).resolve()
    run = _run_dir(session, run_id)
    progress = _Progress(run)
    with _LOCK:
        other = [item for item in _ACTIVE
                 if item.parent == run.parent and item != run]
        if other:
            return _update(run, state="error", stage="error", progress=0,
                           message="Для этой встречи уже выполняется Replay run")
        _ACTIVE.add(run)
    started = time.monotonic()
    try:
        value = _manifest(run)
        if not _uses_current_stt_recipe(value):
            raise ValueError(
                "параметры распознавания устарели; создайте новый Replay run")
        batch_id = str((value.get("batch") or {}).get("batch_id") or "")
        if batch_id:
            with _LOCK:
                _ACTIVE_BATCH_IDS[run] = batch_id
        options = value["options"]
        audio_name = options["audio_name"]
        source_audio = session / audio_name
        identity = _verify_source(session, run, value)
        header = _source_header(session, audio_name)
        _safe_context_copy(session, run)
        progress.set("prepare", 3, "Проверяю исходники…", force=True)
        transcribe_audio = source_audio
        aec_result = None
        reused = _reusable_transcript(session, options, identity)
        # Очищенная дорожка нужна самому Whisper либо диаризации поверх неё;
        # при переиспользованном транскрипте без диаризации AEC не запускаем.
        if options["aec"] != "off" and (reused is None or options["diarization"]):
            progress.set("aec", 5, "Повторяю AEC по двум дорожкам…", force=True)
            cleaned = run / "audio-clean.wav"
            aec_result = audio_echo.process_wav(
                source_audio, _matching_render(session, audio_name), cleaned,
                backend=options["aec"], cancelled=lambda: _is_cancelled(run),
                progress=lambda done, total: progress.portion(
                    "aec", 5, 25, done, total, f"AEC: {done}/{total} блоков"))
            transcribe_audio = cleaned
        if _is_cancelled(run):
            raise InterruptedError("прогон отменён")
        if reused is not None:
            reused_id, reused_journal = reused
            progress.set("stt", 70,
                         f"Использую готовый транскрипт прогона {reused_id}",
                         force=True)
            shutil.copy2(reused_journal, run / "transcript.local.jsonl")
            transcript = run / "transcript.local.jsonl"
            if _file_sha256(transcript) != _manifest(reused_journal.parent).get("transcript_sha256"):
                raise ValueError("Кешированный транскрипт изменился при чтении")
        else:
            reused_id = None
            progress.set("stt", 25, f"Whisper {options['model']} распознаёт запись…",
                         force=True)
            transcript = transcript_backfill.transcribe_audio(
                transcribe_audio, run / "transcript.local.jsonl", header,
                audio_name=audio_name, model_name=options["model"],
                beam_size=int(options.get("stt_beam", 1)),
                cancelled=lambda: _is_cancelled(run),
                progress=lambda done, total, text: progress.portion(
                    "stt", 25, 70, done, total,
                    f"STT {done / 1000:.0f} с · {text[:80]}"))
        final_journal = transcript
        if options["diarization"]:
            progress.set("diarization", 70, "Разделяю голосовые кластеры…",
                         force=True)
            diarization = speaker_diarization.diarize_audio(
                transcribe_audio, run / "diarization.json", audio_name=audio_name,
                speakers=options["speakers"], threshold=options["threshold"],
                embedding_model=options["diarization_embedding"],
                cancelled=lambda: _is_cancelled(run),
                progress_callback=lambda done, total: progress.portion(
                    "diarization", 70, 90, done, total,
                    f"Диаризация: {round(done * 100 / max(1, total))}%"))
            final_journal = speaker_diarization.merge_transcript(
                run, transcript_name=transcript.name,
                diarization_name=diarization.name,
                output_name="transcript.local.diarized.jsonl")
            transcript_events.render_markdown(
                final_journal, run / "transcript.diarized.md")
        transcript_events.render_markdown(final_journal, run / "transcript.md")
        progress.set("metrics", 92, "Считаю качество и сравнение…", force=True)
        comparison = _comparison(
            session, final_journal, aec_result, audio_name,
            run / "diarization.json" if options["diarization"] else None)
        _atomic_json(run / COMPARISON_NAME, comparison)
        hint_summary = None
        if options["generate_hint"]:
            progress.set("hints", 97, "Генерирую контрольную подсказку…", force=True)
            try:
                hint_summary = _hint(run)
            except Exception as exc:
                hint_summary = {
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                }
        elapsed = round(time.monotonic() - started, 2)
        _verify_source(session, run, value)
        message = f"Готово за {elapsed:.1f} с"
        if hint_summary and hint_summary.get("error"):
            message += "; контрольная подсказка не сформирована"
        return _update(
            run, state="completed", stage="completed", progress=100,
            message=message, completed_at=_now(),
            elapsed_seconds=elapsed, comparison=comparison,
            transcript_sha256=_file_sha256(run / "transcript.local.jsonl"),
            output_sha256={item.name: _file_sha256(item) for item in run.iterdir()
                           if item.name != MANIFEST_NAME and item.is_file()
                           and _RUN_FILE.fullmatch(item.name)},
            hint_summary=hint_summary,
            **({"transcript_reused_from": reused_id} if reused_id else {}),
            outputs=[item.name for item in run.iterdir()
                     if item.is_file() and _RUN_FILE.fullmatch(item.name)])
    except InterruptedError as exc:
        return _update(run, state="cancelled", stage="cancelled",
                       message=str(exc), completed_at=_now())
    except Exception as exc:
        return _update(run, state="error", stage="error",
                       message=f"{type(exc).__name__}: {exc}"[:500],
                       completed_at=_now())
    finally:
        with _LOCK:
            _ACTIVE.discard(run)
            _ACTIVE_BATCH_IDS.pop(run, None)
            _CANCELLED.discard(run)


def execute_matrix(session: Path, batch_id: str, run_ids: list[str]) -> dict:
    """Последовательно выполнить матрицу, не загружая модели параллельно."""
    session = Path(session).resolve()
    if (not _BATCH_ID.fullmatch(str(batch_id)) or not isinstance(run_ids, list)
            or not 2 <= len(run_ids) <= 6):
        raise ValueError("повреждена очередь матрицы Replay Lab")
    root = (session / ROOT_NAME).resolve()
    results = []
    try:
        for run_id in run_ids:
            run = _run_dir(session, run_id)
            value = _manifest(run)
            if (value.get("batch") or {}).get("batch_id") != batch_id:
                raise ValueError("вариант не принадлежит матрице Replay Lab")
            with _LOCK:
                cancelled = batch_id in _CANCELLED_BATCHES
            if cancelled or value.get("state") == "cancelled":
                if value.get("state") == "queued":
                    value = _update(
                        run, state="cancelled", stage="cancelled", progress=0,
                        message="Пакетная матрица остановлена пользователем",
                        completed_at=_now())
                results.append(value)
                continue
            results.append(execute_run(session, run_id))
        return {"batch_id": batch_id, "runs": results,
                "completed": sum(item.get("state") == "completed"
                                  for item in results)}
    finally:
        with _LOCK:
            _ACTIVE_BATCHES.discard(root)
            _CANCELLED_BATCHES.discard(batch_id)


def list_runs(session: Path) -> list[dict]:
    root = Path(session).resolve() / ROOT_NAME
    if not root.is_dir():
        return []
    result = []
    for run in sorted(root.iterdir(), key=lambda path: path.name, reverse=True):
        if not run.is_dir() or not _RUN_ID.fullmatch(run.name):
            continue
        try:
            value = _manifest(run)
            if value.get("state") in {"queued", "running"}:
                with _LOCK:
                    active = (run in _ACTIVE
                              or run.parent in _ACTIVE_BATCHES)
                freshly_queued = (value.get("state") == "queued"
                                  and time.time() - run.stat().st_mtime < 5)
                if not active and not freshly_queued:
                    value = _update(
                        run, state="interrupted", stage="interrupted",
                        message="Сервер был остановлен до завершения прогона",
                        completed_at=_now())
            value["stt_current"] = _uses_current_stt_recipe(value)
            if value.get("state") == "completed":
                try:
                    _verify_completed(session, run, value, persist=False)
                except (OSError, ValueError, KeyError) as exc:
                    value.update(state="error", integrity_ok=False, message=str(exc), outputs=[])
                else:
                    value["outputs"] = [name for name in value.get("outputs", [])
                                        if name in (value.get("output_sha256") or {})]
            result.append(value)
        except (OSError, ValueError, json.JSONDecodeError):
            result.append({"run_id": run.name, "state": "error", "progress": 0,
                           "message": "Повреждённый Replay run"})
    result.sort(key=lambda item: int((item.get("batch") or {}).get("index") or 1))
    result.sort(key=lambda item: str(
        (item.get("batch") or {}).get("batch_id") or item.get("run_id") or ""),
                reverse=True)
    return _recommend_runs(result)


def _number(value: object, fallback: float = 1_000_000.0) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if number == number and abs(number) != float("inf"):
            return number
    return fallback


def _uses_current_stt_recipe(run: dict) -> bool:
    stt = run.get("stt") or {}
    return (
        isinstance(stt, dict)
        and stt.get("recipe") == transcript_backfill.TRANSCRIPTION_RECIPE
        and stt.get("language") == "ru"
        and stt.get("task") == "transcribe"
        and stt.get("condition_on_previous_text") is False
    )


def _heuristic_recommendation_key(run: dict) -> tuple | None:
    quality = (run.get("comparison") or {}).get("quality") or {}
    if not isinstance(quality, dict) or int(quality.get("utterances") or 0) <= 0:
        return None
    balance = quality.get("speaker_balance") or {}
    speakers = int(quality.get("speakers") or 0)
    if speakers <= 0:
        return None
    tiny = max(0, int(balance.get("tiny_clusters") or 0))
    dominant = min(1.0, max(0.0, _number(
        balance.get("dominant_share"), 1.0)))
    needs_review = balance.get("needs_review") is True
    confidence = _number(quality.get("average_confidence"), 0.0)
    elapsed = _number(run.get("elapsed_seconds"))
    return (
        1 if needs_review else 0,
        1 if speakers > 12 else 0,
        tiny,
        max(0.0, dominant - 0.82),
        -confidence,
        elapsed,
    )


def _reference_recommendation_key(run: dict) -> tuple | None:
    comparison = run.get("comparison") or {}
    metrics = comparison.get("replay") or {}
    if comparison.get("reference_state") != "reviewed" or not isinstance(
            metrics, dict):
        return None
    values = tuple(_number(metrics.get(name)) for name in ("wer", "der", "jer"))
    if any(value >= 1_000_000 for value in values):
        return None
    heuristic = _heuristic_recommendation_key(run)
    return (*values, *(heuristic or ()))


def _recommend_runs(runs: list[dict]) -> list[dict]:
    """Mark one completed run per source without auto-applying it."""
    groups: dict[str, list[dict]] = {}
    for run in runs:
        run.pop("recommendation", None)
        if (run.get("state") != "completed"
                or run.get("stt_current") is False):
            continue
        audio_name = str((run.get("source") or {}).get("audio_name") or "")
        if audio_name:
            groups.setdefault(audio_name, []).append(run)
    for candidates in groups.values():
        if len(candidates) < 2:
            continue
        reference_candidates = [
            (key, run) for run in candidates
            if (key := _reference_recommendation_key(run)) is not None]
        if len(reference_candidates) >= 2:
            _key, winner = min(reference_candidates, key=lambda item: item[0])
            basis = "reviewed_reference"
            reason = ("Лучший результат по проверенному эталону: сначала WER, "
                      "затем DER и JER. Перед заменой всё равно прослушайте голоса.")
        else:
            # Без проверенного эталона признаки кластеров и raw confidence дают
            # только очередь для ручного A/B, но не доказательство улучшения.
            continue
        winner["recommendation"] = {
            "recommended": True, "basis": basis, "reason": reason,
            "candidates": len(candidates),
        }
    return runs


def _run_journal(run: Path) -> Path:
    for name in ("transcript.local.diarized.jsonl", "transcript.local.jsonl"):
        candidate = run / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("вариант не содержит структурированный транскрипт")


def _utterances(raw: bytes) -> list[dict]:
    result = []
    for item in transcript_events.read_records_bytes(raw)[1:]:
        if (item.get("record_type") != "utterance"
                or item.get("status", "final") != "final"):
            continue
        try:
            start_ms = max(0, int(item.get("start_ms", 0)))
            end_ms = max(start_ms + 1, int(item.get("end_ms", start_ms + 1)))
        except (TypeError, ValueError):
            continue
        text = " ".join(str(item.get("text") or "").split())[:1200]
        if text:
            result.append({
                "start_ms": start_ms, "end_ms": end_ms, "text": text,
                "speaker": str(item.get("speaker_id")
                               or item.get("speaker") or "")[:80],
                "confidence": transcript_events.event_confidence(item),
            })
        if len(result) >= 5000:
            break
    return result


def _parse_time(value: object) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo is not None else parsed.astimezone()
    except (TypeError, ValueError):
        return None


def _percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1,
                max(0, round((len(ordered) - 1) * fraction)))
    return int(ordered[index])


def _source_timing(session: Path, audio_name: str) -> dict:
    """Измерить live STT delay; офлайн-перераспознавание не выдавать за live."""
    suffix = audio_name.removeprefix("audio-me").removeprefix(
        "audio-guest").removesuffix(".wav")
    preferred = session / f"transcript{suffix}.jsonl"
    names = [preferred]
    names.extend(sorted(session.glob("transcript*.jsonl"),
                        key=lambda item: item.name, reverse=True))
    seen: set[Path] = set()
    best: tuple[Path | None, list[int]] = (None, [])
    for journal in names:
        resolved = journal.resolve()
        if (resolved in seen or resolved.parent != session.resolve()
                or not re.fullmatch(r"transcript(?:-\d+)?\.jsonl", journal.name)
                or not journal.is_file()):
            continue
        seen.add(resolved)
        try:
            records = transcript_events.read_records(journal)
            started = _parse_time(records[0].get("started_at"))
        except (OSError, ValueError, IndexError):
            continue
        if started is None:
            continue
        samples: list[int] = []
        for item in records[1:]:
            if (item.get("record_type") != "utterance"
                    or item.get("status", "final") != "final"
                    or str(item.get("audio_file") or "") != audio_name
                    or str(item.get("timing_source") or "").startswith("offline")):
                continue
            received = _parse_time(item.get("received_at"))
            try:
                end_ms = int(item.get("end_ms", 0))
            except (TypeError, ValueError):
                continue
            if received is None:
                continue
            latency = round((received - started).total_seconds() * 1000) - end_ms
            # Часы могут слегка расходиться, но многочасовая задержка означает
            # backfill и не является задержкой живого распознавания.
            if -1000 <= latency <= 120_000:
                samples.append(max(0, latency))
        if len(samples) > len(best[1]):
            best = (journal, samples)
    journal, samples = best
    return {
        "kind": "measured" if samples else "unavailable",
        "samples": len(samples), "journal": journal.name if journal else "",
        "p50_ms": _percentile(samples, 0.5),
        "p95_ms": _percentile(samples, 0.95),
        "note": ("По received_at живого STT; офлайн-backfill исключён."
                 if samples else
                 "В архиве нет сопоставимых live-меток; используется оценка."),
    }


def _hint_count(session: Path) -> int:
    path = session / "hints.jsonl"
    if path.is_symlink() or not path.is_file():
        return 0
    count = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as source:
            for line in source:
                try:
                    if isinstance(json.loads(line), dict):
                        count += 1
                except json.JSONDecodeError:
                    continue
    except OSError:
        return 0
    return count


def _pulse_summary(session: Path, duration_ms: int) -> dict:
    events = pulse_timing.completed(session)
    successful = [item for item in events
                  if item.get("outcome") == "success"
                  and isinstance(item.get("duration_ms"), int)
                  and 0 <= item["duration_ms"] <= 120_000]
    durations = [item["duration_ms"] for item in successful]
    actual = []
    for item in successful:
        offset = item.get("meeting_offset_ms")
        transcript_end = item.get("transcript_end_ms")
        if (not isinstance(offset, int) or not isinstance(transcript_end, int)
                or offset > duration_ms + 60_000):
            continue
        actual.append({
            "pulse_id": item["pulse_id"], "trigger": item.get("trigger"),
            "requested_ms": offset, "transcript_end_ms": transcript_end,
            "ready_ms": offset + item["duration_ms"],
            "duration_ms": item["duration_ms"],
        })
    historical = _hint_count(session)
    return {
        "kind": "measured" if durations else "unavailable",
        "samples": len(durations), "p50_ms": _percentile(durations, 0.5),
        "p95_ms": _percentile(durations, 0.95),
        "legacy_without_timing": max(0, historical - len(successful)),
        "interrupted": sum(item.get("outcome") == "interrupted"
                           for item in events),
        "actual": actual,
        "note": ("Реальные локальные замеры от запуска до готовой подсказки."
                 if durations else
                 "Старые подсказки сохранены без времени; ниже только симуляция."),
    }


def timeline(session: Path, run_id: str) -> dict:
    """Подготовить безопасный playback payload для завершённого Replay run."""
    session = Path(session).resolve()
    run = _run_dir(session, run_id)
    manifest = _manifest(run)
    if manifest.get("state") != "completed":
        raise ValueError("таймлайн доступен только для завершённого варианта")
    utterances = _utterances(_verify_completed(session, run, manifest, read_journal=True))
    if not utterances:
        raise ValueError("вариант не содержит реплик для воспроизведения")
    audio_name = str((manifest.get("source") or {}).get("audio_name") or "")
    if not _AUDIO_NAME.fullmatch(audio_name):
        raise ValueError("в варианте повреждено имя исходной дорожки")
    seconds = _audio_seconds(run / "audio-clean.wav") \
        if (run / "audio-clean.wav").is_file() else _audio_seconds(session / audio_name)
    duration_ms = max(round(float(seconds or 0) * 1000),
                      max(item["end_ms"] for item in utterances))
    stt = _source_timing(session, audio_name)
    pulses = _pulse_summary(session, duration_ms)
    try:
        meta = json.loads((session / "meta.json").read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        meta = {}
    candidate_mode = preset(str(meta.get("type") or "встреча")).get(
        "mode") == "candidate"
    _verify_completed(session, run, manifest)
    return {
        "schema_version": 1, "created_at": _now(),
        "run_id": run_id, "source_audio": audio_name,
        "audio_kind": "cleaned" if (run / "audio-clean.wav").is_file()
                      else "source",
        "duration_ms": duration_ms, "utterances": utterances,
        "stt_latency": stt, "pulse_latency": pulses,
        "simulation": {
            "stt_ms": stt["p50_ms"] if stt["p50_ms"] is not None else 1500,
            "llm_ms": pulses["p50_ms"] if pulses["p50_ms"] is not None else 6000,
            "silence_ms": 2000 if candidate_mode else 4000,
            "cooldown_ms": 6000 if candidate_mode else 20_000,
            "basis": "measured" if pulses["p50_ms"] is not None else "estimate",
        },
    }


def _normalized_text(value: str) -> str:
    return " ".join(re.findall(r"[\wё]+", str(value).casefold(), re.UNICODE))


def _matching_text(events: list[dict], anchor: dict) -> dict:
    overlaps = []
    anchor_mid = (anchor["start_ms"] + anchor["end_ms"]) / 2
    for item in events:
        overlap = min(anchor["end_ms"], item["end_ms"]) - max(
            anchor["start_ms"], item["start_ms"])
        item_mid = (item["start_ms"] + item["end_ms"]) / 2
        if overlap > 0 or abs(item_mid - anchor_mid) <= 1200:
            overlaps.append(item)
    if not overlaps:
        return {"text": "", "speaker": "", "confidence": None}
    overlaps.sort(key=lambda item: (item["start_ms"], item["end_ms"]))
    text = " ".join(dict.fromkeys(item["text"] for item in overlaps))[:1800]
    speakers = list(dict.fromkeys(item["speaker"] for item in overlaps
                                  if item["speaker"]))
    confidences = [item["confidence"] for item in overlaps
                   if isinstance(item["confidence"], (int, float))]
    return {
        "text": text, "speaker": " / ".join(speakers)[:160],
        "confidence": (round(sum(confidences) / len(confidences), 4)
                       if confidences else None),
    }


def compare_runs(session: Path, run_ids: object) -> dict:
    """Return the most divergent time-aligned excerpts for 2–4 completed runs."""
    session = Path(session).resolve()
    if not isinstance(run_ids, list) or not 2 <= len(run_ids) <= 4:
        raise ValueError("для сравнения выберите от 2 до 4 вариантов")
    if len(set(map(str, run_ids))) != len(run_ids):
        raise ValueError("один вариант нельзя сравнивать с самим собой")
    variants = []
    audio_names = set()
    for run_id in run_ids:
        run = _run_dir(session, str(run_id))
        value = _manifest(run)
        if value.get("state") != "completed":
            raise ValueError("сравнивать можно только завершённые варианты")
        journal = _verify_completed(session, run, value, read_journal=True)
        value["stt_current"] = _uses_current_stt_recipe(value)
        value.pop("recommendation", None)
        events = _utterances(journal)
        if not events:
            raise ValueError("один из вариантов не содержит распознанных реплик")
        audio_name = str((value.get("source") or {}).get("audio_name") or "")
        audio_names.add(audio_name)
        variants.append({
            "run_id": value["run_id"], "label": str(
                (value.get("batch") or {}).get("label") or value["run_id"]),
            "options": value.get("options") or {},
            "comparison": value.get("comparison") or {},
            "stt_current": value["stt_current"],
            "recommended": False, "manifest": value,
            "audio_kind": "cleaned" if (run / "audio-clean.wav").is_file()
                          else "source",
            "events": events,
        })
    if len(audio_names) != 1 or not next(iter(audio_names), ""):
        raise ValueError("варианты должны относиться к одной аудиодорожке")
    _recommend_runs([item["manifest"] for item in variants])
    for item in variants:
        item["recommended"] = bool(
            (item["manifest"].get("recommendation") or {}).get("recommended"))
    recommended = next((item for item in variants if item["recommended"]), None)
    anchor_variant = recommended or next((item for item in variants if item["stt_current"]), variants[0])
    scored = []
    for anchor in anchor_variant["events"]:
        cells = []
        normalized = []
        for variant in variants:
            cell = _matching_text(variant["events"], anchor)
            cells.append({"run_id": variant["run_id"], **cell})
            normalized.append(_normalized_text(cell["text"]))
        similarities = [
            difflib.SequenceMatcher(None, left, right, autojunk=False).ratio()
            for index, left in enumerate(normalized)
            for right in normalized[index + 1:]
        ]
        difference = 1 - min(similarities, default=1.0)
        if difference >= 0.04:
            scored.append({
                "start_ms": max(0, anchor["start_ms"] - 700),
                "end_ms": anchor["end_ms"] + 900,
                "difference": round(difference, 4), "cells": cells,
            })
    strongest = sorted(scored, key=lambda row: row["difference"], reverse=True)[:40]
    strongest.sort(key=lambda row: row["start_ms"])
    anchor_utterances = len(anchor_variant["events"])
    for variant in variants:
        variant.pop("events", None)
        variant.pop("manifest", None)
    return {
        "schema_version": 1, "created_at": _now(),
        "source_audio": next(iter(audio_names)),
        "anchor_run_id": anchor_variant["run_id"], "variants": variants,
        "rows": strongest,
        "summary": {"selected": len(variants),
                    "anchor_utterances": anchor_utterances,
                    "difference_rows": len(strongest),
                    "truncated": len(scored) > len(strongest)},
    }


def run_file(session: Path, run_id: str, name: str) -> Path:
    run = _run_dir(session, run_id)
    if Path(name).name != name or not _RUN_FILE.fullmatch(name):
        raise ValueError("недопустимый файл Replay run")
    path = run / name
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError("файл Replay run не найден")
    return path


def download_snapshot(session: Path, run_id: str, name: str) -> Path:
    """Check the exact private copy handed to FileResponse (including Range)."""
    path = run_file(session, run_id, name)
    run = path.parent
    value = _manifest(run)
    expected = (value.get("output_sha256") or {}).get(name)
    if value.get("state") != "completed" or not expected:
        raise ValueError("Файл Replay не подтверждён; выполните новый прогон")
    _verify_source(session, run, value, persist=False)
    with tempfile.NamedTemporaryFile(prefix="blatero-replay-", suffix=path.suffix,
                                     delete=False) as stream:
        snapshot = Path(stream.name)
        try:
            if _file_sha256(path, stream) != expected:
                raise ValueError("Файл Replay изменён; выполните новый прогон")
        except BaseException:
            stream.close()
            snapshot.unlink(missing_ok=True)
            raise
    return snapshot


def apply_diarization(session: Path, run_id: str, *, replace: bool = False) -> dict:
    """Перенести выбранный Replay-разбор в штатную проверку голосов.

    Исходные WAV и живой transcript*.jsonl не меняются. Переносятся только
    локальные производные файлы; повторное применение того же run идемпотентно.
    """
    session = Path(session).resolve()
    run = _run_dir(session, run_id)
    value = _manifest(run)
    if value.get("state") != "completed":
        raise ValueError("применить можно только завершённый Replay run")
    if not _uses_current_stt_recipe(value):
        raise ValueError(
            "этот разбор создан устаревшим STT-контуром; выполните новый прогон")
    if not value.get("options", {}).get("diarization"):
        raise ValueError("в этом Replay run разделение голосов не выполнялось")
    _verify_completed(session, run, value)
    sources = {name: run / name for name in _PROMOTED_FILES}
    missing = [name for name, path in sources.items() if not path.is_file()]
    if missing:
        raise ValueError(
            "Replay run не содержит готовый разбор: " + ", ".join(missing))
    evidence_path = session / evidence.DIARIZED_OUTPUT
    still_current = all(
        filecmp.cmp(source, session / name, shallow=False)
        for name, source in sources.items()
        if (session / name).is_file()
    ) and all((session / name).is_file() for name in sources)
    if value.get("applied_at") and evidence_path.is_file() and still_current:
        _verify_completed(session, run, value)
        return {
            "run_id": run_id, "applied": True, "already_applied": True,
            "evidence_url": f"/files/{session.name}/{evidence_path.name}",
        }

    # Проверяем содержимое до любых изменений в папке встречи.
    transcript_events.read_records(sources["transcript.local.jsonl"])
    transcript_events.read_records(sources["transcript.local.diarized.jsonl"])
    try:
        diarization = json.loads(sources["diarization.json"].read_text(
            encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("повреждён результат диаризации Replay run") from exc
    if not isinstance(diarization, dict) or not isinstance(
            diarization.get("segments"), list) or not diarization["segments"]:
        raise ValueError("в результате Replay run нет голосовых сегментов")

    staged: dict[str, Path] = {}
    backups: dict[str, Path] = {}
    managed = (*_PROMOTED_FILES, *_STALE_SPEAKER_FILES)
    try:
        for name, source in sources.items():
            temporary = session / f".{name}.{run_id}.tmp"
            shutil.copyfile(source, temporary)
            staged[name] = temporary
        with _LOCK:
            _verify_completed(session, run, value)
            if any(_file_sha256(path) != value["output_sha256"][name]
                   for name, path in staged.items()):
                raise ValueError("Результат Replay изменился при копировании")
            conflicts = [name for name in managed if (session / name).is_file()]
            if conflicts and not replace:
                raise FileExistsError(
                    "встреча уже содержит разбор голосов; подтвердите его замену")
            try:
                for name in conflicts:
                    backup = session / f".{name}.{run_id}.backup.tmp"
                    os.replace(session / name, backup)
                    backups[name] = backup
                for name, temporary in staged.items():
                    os.replace(temporary, session / name)
                mapping = speaker_diarization.load_speaker_map(session)
                mapping = speaker_diarization.save_speaker_map(session, mapping)
                speaker_diarization.apply_speaker_map(session)
                page, _entries = evidence.build(
                    session, journal_name="transcript.local.diarized.jsonl",
                    output_name=evidence.DIARIZED_OUTPUT, speaker_map=mapping)
                if page is None:
                    raise ValueError("не удалось собрать страницу проверки голосов")
                _verify_completed(session, run, value)
                url = f"/files/{session.name}/{evidence.DIARIZED_OUTPUT}"
                _update(run, applied_at=_now(), applied_to=session.name,
                        evidence_url=url, applied_files=[*_PROMOTED_FILES, *_STALE_SPEAKER_FILES])
            except Exception as original_error:
                rollback_errors = []
                for name in managed:
                    if name not in conflicts:
                        try:
                            (session / name).unlink(missing_ok=True)
                        except OSError as exc:
                            rollback_errors.append(exc)
                for name, backup in backups.items():
                    try:
                        os.replace(backup, session / name)
                    except OSError as exc:
                        rollback_errors.append(exc)
                if rollback_errors:
                    raise ExceptionGroup("Replay apply and rollback failed; backups retained", [original_error, *rollback_errors])
                raise
            else:
                for backup in backups.values():
                    try:
                        backup.unlink(missing_ok=True)
                    except OSError:
                        # Publication is committed; cleanup is not a failed apply.
                        pass
    finally:
        for temporary in staged.values():
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    url = f"/files/{session.name}/{evidence.DIARIZED_OUTPUT}"
    return {
        "run_id": run_id, "applied": True, "already_applied": False,
        "replaced": bool(conflicts), "speakers": len(mapping["speakers"]),
        "evidence_url": url,
    }


def delete_run(session: Path, run_id: str) -> dict:
    run = _run_dir(session, run_id)
    value = _manifest(run)
    if value.get("state") in {"queued", "running"}:
        raise ValueError("сначала остановите Replay run")
    with _LOCK:
        if run in _ACTIVE:
            raise ValueError("сначала остановите Replay run")
    unexpected = [item.name for item in run.iterdir()
                  if not item.is_file()
                  or not (_RUN_FILE.fullmatch(item.name)
                          or item.name.endswith(".tmp"))]
    if unexpected:
        raise ValueError("Replay run содержит неожиданные файлы")
    count = 0
    for item in run.iterdir():
        item.unlink()
        count += 1
    run.rmdir()
    root = run.parent
    if not any(root.iterdir()):
        root.rmdir()
    return {"deleted": run_id, "files": count}
