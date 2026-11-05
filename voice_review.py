"""Short, local post-meeting voice review. Never rewrites WAV or transcripts."""

from __future__ import annotations

import hashlib
import datetime as dt
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import uuid

import numpy as np

from operation_lock import OperationLock, lock_is_held
import speaker_diarization as diarization
import speaker_profiles as profiles

ROOT = "speaker-analysis"
FILE = "voice-review.json"
_LOCK = threading.RLock()
_AUDIO = re.compile(r"audio-guest(?:-\d+)?\.wav\Z")


def _digest(path):
    if path.is_symlink():
        raise ValueError("Источник разбора не может быть ссылкой")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if _stat(path) != (before.st_size, before.st_mtime_ns, before.st_ctime_ns):
        raise ValueError("Исходная дорожка изменилась во время проверки")
    return digest.hexdigest()


def _stat(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _sources(session):
    return {p.name: {"sha256": _digest(_audio(session, p.name)),
                     "stat": list(_stat(p))}
            for p in sorted(Path(session).iterdir()) if _AUDIO.fullmatch(p.name)}


def _bank_identity():
    # Names, deleted profiles, matrices and thresholds all affect suggestions.
    files = []
    if profiles.PROFILE_ROOT.exists():
        if profiles.PROFILE_ROOT.is_symlink():
            raise ValueError("Банк голосов не может быть ссылкой")
        for folder in sorted(profiles.PROFILE_ROOT.iterdir()):
            if folder.is_dir() and not folder.name.startswith('.'):
                if folder.is_symlink():
                    raise ValueError("Профиль голоса не может быть ссылкой")
                for name in ("profile.json", "embeddings.npz"):
                    path = folder / name
                    files.append((folder.name, name, _digest(path) if path.exists() else None))
    return hashlib.sha256(json.dumps([files, profiles.SUGGEST_THRESHOLD,
        profiles.HIGH_CONFIDENCE_THRESHOLD, profiles.HIGH_CONFIDENCE_MARGIN],
        sort_keys=True).encode()).hexdigest()


def _recipe():
    models = [(p.name, _digest(p) if p.is_file() else None) for p in
              (diarization.SEGMENTATION_MODEL, diarization.EMBEDDING_MODEL)]
    return hashlib.sha256(json.dumps([2, "3dspeaker", 0, 0.5, models]).encode()).hexdigest()


def _validate_sources(session, expected):
    current = _sources(session)
    if (not expected or set(current) != set(expected) or any(
            not old.get("sha256") or current[name]["sha256"] != old["sha256"]
            for name, old in expected.items())):
        raise ValueError("Исходная дорожка изменилась или не подтверждена; голос не сохранён")


def _analysis(root, entry):
    name = entry.get("file", "")
    if not re.fullmatch(r"diarization-review-[a-f0-9]+\.json", name):
        raise ValueError("Недопустимый файл разделения голосов")
    path = root / name
    if not entry.get("sha256") or _digest(path) != entry["sha256"]:
        raise ValueError("Разделение голосов изменилось; повторите разбор")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("Разделение голосов изменилось при чтении")
    return json.loads(raw)["segments"]


def _cached_analyses_valid(root, value):
    entries = value.get("analyses", {})
    if set(entries) != set(value.get("sources", {})):
        return False
    try:
        recipe = _recipe()
        for name, entry in entries.items():
            if entry.get("recipe") != recipe:
                return False
            if entry.get("source_sha256") != value["sources"][name].get("sha256"):
                return False
            _analysis(root, entry)
    except (OSError, ValueError, KeyError):
        return False
    return True


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


class _Progress:
    def __init__(self, root, value):
        self.root, self.value = root, value
        self.started = time.monotonic()
        self.last_write = 0.0

    def update(self, stage, *, done=0, total=0, force=True, **fields):
        now = time.monotonic()
        changed = stage != self.value.get("stage") or total != self.value.get("stage_total")
        self.value.update(stage=stage, stage_done=done, stage_total=total,
                          elapsed_seconds=round(now - self.started, 3),
                          updated_at=_now(), **fields)
        if force or changed or now - self.last_write >= 0.4 or (total and done >= total):
            _write(self.root, self.value)
            self.last_write = now


def _root(session):
    root = Path(session) / ROOT
    if root.is_symlink():
        raise ValueError("Папка разбора голосов не может быть ссылкой")
    return root


def _write(root, value):
    temporary = root / (FILE + ".tmp")
    if temporary.is_symlink() or (root / FILE).is_symlink():
        raise ValueError("Результат разбора не может быть ссылкой")
    temporary.write_text(json.dumps(_stored(value), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, root / FILE)


def _stored(value):
    derived = {"enrollment_active", "enrollment_recovered", "consent_revision"}
    return {**value, "voices":[{k:v for k,v in row.items() if k not in derived}
                               for row in value.get("voices", [])]}


def _enrollment_id(session, row):
    return hashlib.sha256(
        (str(Path(session).resolve()) + ":" + row["id"]).encode()
    ).hexdigest()[:32]


class ConsentChanged(ValueError):
    pass


def _consent_revision(session, row):
    identity = _enrollment_id(session, row)
    legacy = row.get("enrolled_profile") or identity
    pairs = [(key, profiles.consent_epoch(key)) for key in sorted({identity, legacy})]
    return hashlib.sha256(json.dumps(pairs).encode()).hexdigest()


def _require_consent(session, row, body):
    if body.get("consent") is not True:
        raise ValueError("Подтвердите согласие на сохранение голосового отпечатка")
    if body.get("consent_revision") != _consent_revision(session, row):
        raise ConsentChanged("Согласие изменилось. Проверьте его и отметьте заново.")


def _bank_profile(identity):
    if not identity:
        return {}
    try:
        path = profiles._profile_dir(identity)
        return profiles._manifest(path) if (path / "embeddings.npz").is_file() else {}
    except (OSError, ValueError, KeyError):
        return {}


def payload(session):
    root = _root(session)
    path = root / FILE
    if path.is_symlink():
        raise ValueError("Результат разбора не может быть ссылкой")
    if path.is_file():
        if path.stat().st_size > 2_000_000:
            raise ValueError("Слишком большой результат разбора голосов")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema") != 1:
            raise ValueError("Повреждён результат разбора голосов")
        if value.get("state") == "running" and not lock_is_held(root / "voice-review.lock"):
            value = {
                **value,
                "state": "interrupted",
                "message": "Предыдущий разбор прерван. Можно повторить; исходные записи сохранены.",
            }
        if value.get("state") == "running" and value.get("started_at"):
            started = dt.datetime.fromisoformat(value["started_at"])
            value["elapsed_seconds"] = max(0, round(
                (dt.datetime.now(dt.timezone.utc) - started).total_seconds(), 1))
        cache_valid = _cached_analyses_valid(root, value) if value.get("state") == "ready" else True
        if value.get("state") == "ready" and (not cache_valid or
                set(value.get("sources", {})) != {
                    p.name for p in Path(session).iterdir() if _AUDIO.fullmatch(p.name)}
                or any(not old.get("sha256") or not (Path(session) / name).is_file()
                       or list(_stat(Path(session) / name)) != old.get("stat")
                       for name, old in value.get("sources", {}).items())
                or value.get("bank_identity") != _bank_identity()):
            value = {
                **value,
                "state": "needs_update",
                "message": ("Дорожки или банк голосов обновились. Повторите разбор; подтверждённые имена для неизменённых дорожек сохранятся."
                            if cache_valid else "Результат разделения голосов изменился. Повторите разбор; предыдущая версия сохранена."),
                "voices": [dict(row) if row.get("name_source") == "operator_confirmed" else
                           {**row, "name": "", "name_source": "unknown", "match": {
                               "state": "stale", "reason": "Повторите сравнение с банком голосов"}}
                           for row in value.get("voices", [])],
            }
        if value.get("state") in {"ready", "needs_update"}:
            for row in value.get("voices", []):
                recorded = row.get("enrolled_profile")
                recovered = _enrollment_id(session, row)
                active = bool(_bank_profile(recorded))
                if not active and _bank_profile(recovered).get("source_kind") == "session_cluster":
                    row["enrolled_profile"] = recovered
                    row["enrollment_recovered"] = True
                    active = True
                if row.get("enrolled_profile"):
                    row["enrollment_active"] = active
                row["consent_revision"] = _consent_revision(session, row)
        return value
    models = all(p.is_file() for p in (diarization.SEGMENTATION_MODEL, diarization.EMBEDDING_MODEL))
    return {
        "schema": 1,
        "state": "not_prepared" if models else "needs_models",
        "voices": [],
        "message": "Локально найдём голоса во всех дорожках встречи. Аудио никуда не отправляется."
        if models
        else "Для автоматического поиска нужны локальные модели разделения и распознавания голосов. Установите их в настройках → Локальные модели.",
    }


def _audio(session, name):
    path = Path(session) / name
    if not _AUDIO.fullmatch(name) or path.is_symlink() or not path.is_file():
        raise ValueError("Недопустимая дорожка встречи")
    return path


def _chunks(audio, segments, speaker):
    # Do not enrol overlapped speech or micro-utterances into somebody's profile.
    selected = []
    for item in sorted(segments, key=lambda s: int(s["end_ms"]) - int(s["start_ms"]), reverse=True):
        if item["speaker_id"] != speaker:
            continue
        start, end = int(item["start_ms"]), int(item["end_ms"])
        if end - start < 2000 or any(
            s["speaker_id"] != speaker and int(s["start_ms"]) < end and int(s["end_ms"]) > start
            for s in segments
        ):
            continue
        chunk = audio[start * 16 : min(end, start + 10000) * 16]
        if chunk.size >= 32000:
            selected.append(chunk)
        if len(selected) >= 6:
            break
    if not selected:
        raise ValueError("Недостаточно чистой речи без наложения голосов")
    return profiles._speech_windows(np.concatenate(selected))[: profiles.MAX_EMBEDDINGS]


def prepare(session):
    session = Path(session)
    root = _root(session)
    root.mkdir(exist_ok=True)
    lock = root / "voice-review.lock"
    if lock.is_symlink():
        raise ValueError("Блокировка разбора не может быть ссылкой")
    with _LOCK, OperationLock(lock):
        existing = payload(session)
        tracks = sorted(p for p in session.iterdir() if _AUDIO.fullmatch(p.name))
        if not tracks:
            raise ValueError(
                "Нет записанного звука встречи; микрофонная дорожка не заменяет звук участников"
            )
        sources = _sources(session)
        recipe = _recipe()
        bank_identity = _bank_identity()
        if any(old.get("sha256") and sources.get(name, {}).get("sha256") != old["sha256"]
               for name, old in existing.get("sources", {}).items()):
            raise ValueError(
                "Дорожки изменились. Старый разбор сохранён; требуется отдельный новый разбор"
            )
        analyses = existing.get("analyses", {})
        valid_cache = True
        trusted_analyses = {}
        for name, entry in analyses.items():
            try:
                if entry.get("source_sha256") != sources.get(name, {}).get("sha256") or entry.get("recipe") != recipe:
                    raise ValueError("cache identity")
                _analysis(root, entry)
                trusted_analyses[name] = entry
            except (OSError, ValueError, KeyError):
                valid_cache = False
        if (existing.get("state") == "ready" and existing.get("sources") == sources
                and existing.get("bank_identity") == bank_identity
                and set(analyses) == set(sources) and valid_cache):
            return existing
        # Preserve the old named result, including legacy/unverifiable analyses.
        if existing.get("sources"):
            stored = _stored(existing)
            archive = root / ("voice-review-history-" + hashlib.sha256(
                json.dumps(stored, sort_keys=True).encode()).hexdigest() + ".json")
            if not archive.exists():
                archive.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
        value = {
            "schema": 1,
            "state": "running",
            "voices": [dict(r) for r in existing.get("voices", [])
                       if r.get("audio") in trusted_analyses
                       and r.get("analysis") == trusted_analyses[r["audio"]]["file"]],
            "analyses": dict(trusted_analyses), "bank_identity": bank_identity,
            "sources": sources,
            "message": "Ищем голоса локально",
            "started_at": _now(), "timings": [], "warnings": [],
            "track_index": 0, "track_total": len(tracks),
        }
        progress = _Progress(root, value)
        progress.update("bank")
        try:
            stage_start = time.monotonic()
            centroids = profiles._profile_centroids()
            value["timings"].append({"stage": "bank", "seconds": round(time.monotonic() - stage_start, 3)})
            value["bank_profiles"] = len(centroids)
            for index, track in enumerate(tracks, 1):
                _audio(session, track.name)
                progress.update("diarization", track_index=index)
                entry = analyses.get(track.name, {})
                reused = False
                stage_start = time.monotonic()
                try:
                    if entry.get("source_sha256") == sources[track.name]["sha256"] and entry.get("recipe") == recipe:
                        segments = _analysis(root, entry)
                        reused = True
                except (OSError, ValueError, KeyError):
                    pass
                if not reused:
                    # Never overwrite an orphaned, corrupt or legacy result.
                    result = root / f"diarization-review-{uuid.uuid4().hex}.json"
                    diarization.diarize_audio(
                        track,
                        result,
                        audio_name=track.name,
                        speakers=0,
                        embedding_model="3dspeaker",
                        progress_callback=lambda done, total: progress.update(
                            "diarization", done=done, total=total, force=False),
                    )
                    _validate_sources(session, sources)
                    entry = {"file": result.name, "sha256": _digest(result),
                             "source_sha256": sources[track.name]["sha256"], "recipe": recipe}
                    segments = _analysis(root, entry)
                result = root / entry["file"]
                value["analyses"][track.name] = entry
                value["voices"] = [r for r in value["voices"] if r.get("audio") != track.name]
                value["timings"].append({"stage": "diarization", "track": index,
                                         "seconds": round(time.monotonic() - stage_start, 3),
                                         "reused": reused})
                speakers = sorted({s["speaker_id"] for s in segments})
                if len(speakers) > 20:
                    value["warnings"].append({"code": "many_clusters", "track": index,
                                              "clusters": len(speakers)})
                audio = None
                if centroids:
                    progress.update("load_audio")
                    stage_start = time.monotonic()
                    audio = diarization._load_audio(track, 16000)
                    value["timings"].append({"stage": "load_audio", "track": index,
                                             "seconds": round(time.monotonic() - stage_start, 3)})
                for number, speaker in enumerate(speakers, 1):
                    progress.update("embeddings" if centroids else "samples",
                                    done=number - 1, total=len(speakers))
                    key = hashlib.sha256((track.name + ":" + sources[track.name]["sha256"] + ":" + entry["sha256"] + ":" + speaker).encode()).hexdigest()[:24]
                    previous = next((r for r in existing.get("voices", []) if r.get("id") == key), None) if reused else None
                    if previous and previous.get("name_source") == "operator_confirmed":
                        value["voices"].append(dict(previous))
                        progress.update("samples", done=number, total=len(speakers))
                        continue
                    clips = sorted(
                        (s for s in segments if s["speaker_id"] == speaker),
                        key=lambda s: int(s["end_ms"]) - int(s["start_ms"]),
                        reverse=True,
                    )
                    best = clips[0]
                    row = {
                        "id": key,
                        "audio": track.name,
                        "speaker": speaker,
                        "analysis": result.name,
                        "name": "",
                        "start_ms": best["start_ms"],
                        "end_ms": min(best["end_ms"], best["start_ms"] + 8000),
                    }
                    try:
                        if centroids:
                            stage_start = time.monotonic()
                            try:
                                chunks = _chunks(audio, segments, speaker)
                                if len(chunks) < profiles.MIN_EMBEDDINGS:
                                    raise ValueError("Нужно хотя бы два пригодных голосовых фрагмента")
                                matrix = profiles._embeddings(chunks)
                            finally:
                                value["timings"].append({"stage": "embeddings", "track": index,
                                    "seconds": round(time.monotonic() - stage_start, 3)})
                            progress.update("matching", done=number - 1, total=len(speakers))
                            stage_start = time.monotonic()
                            match = profiles._match(profiles._normalise(matrix.mean(axis=0)), centroids)
                            value["timings"].append({"stage": "matching", "track": index,
                                "seconds": round(time.monotonic() - stage_start, 3)})
                        else:
                            # No possible identity match; extract only on explicit enrolment.
                            match = profiles._match(np.empty(0), [])
                        row.update(
                            match=match,
                            name=match["name"] if match.get("strong_suggestion") else "",
                            name_source="bank_suggestion"
                            if match.get("strong_suggestion")
                            else "unknown",
                        )
                    except (OSError, ValueError, RuntimeError) as exc:
                        row.update(
                            match={"state": "insufficient", "reason": str(exc)},
                            name_source="unknown",
                        )
                    value["voices"].append(row)
                    progress.update("matching" if centroids else "samples",
                                    done=number, total=len(speakers))
            _validate_sources(session, sources)
            if _bank_identity() != bank_identity:
                raise ValueError("Банк голосов изменился во время разбора; повторите сравнение")
            value.update(
                state="ready",
                message="Проверьте только неизвестные голоса. Совпадения с банком — предположения, не доказательство личности. Транскрипты не менялись.",
            )
            progress.update("completed", done=len(tracks), total=len(tracks))
            return payload(session)
        except Exception:
            value.update(
                state="failed",
                message="Разбор не завершён. Исходные записи сохранены; можно повторить локальную подготовку.",
            )
            progress.update("failed")
            raise


def save(session, body):
    root = _root(session)
    lock = root / "voice-review.lock"
    if lock.is_symlink():
        raise ValueError("Блокировка разбора не может быть ссылкой")
    with _LOCK, OperationLock(lock):
        value = payload(session)
        if value.get("state") not in {"ready", "needs_update"}:
            raise ValueError("Дождитесь завершения поиска голосов")
        row = next((r for r in value["voices"] if r["id"] == body.get("id")), None)
        if row is None:
            raise ValueError("Голос не найден")
        name = profiles._clean_name(body.get("name"))
        _validate_sources(session, value["sources"])
        entry = value.get("analyses", {}).get(row["audio"], {})
        segments = _analysis(root, entry)
        if row["analysis"] != entry["file"] or entry.get("recipe") != _recipe():
            raise ValueError("Разделение голосов устарело; повторите разбор")
        if body.get("enroll") is True:
            _require_consent(session, row, body)
            profile_id = _enrollment_id(session, row)
            matrix = None
            if not row.get("enrollment_active"):
                source = _audio(session, row["audio"])
                digest = hashlib.sha256()
                with tempfile.TemporaryFile() as verified, source.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                        verified.write(chunk)
                    if digest.hexdigest() != value["sources"][row["audio"]]["sha256"]:
                        raise ValueError("Исходная дорожка изменилась при чтении")
                    verified.seek(0)
                    audio = diarization._load_audio(verified, 16000)
                matrix = profiles._embeddings(_chunks(audio, segments, row["speaker"]))

            def verify():
                _require_consent(session, row, body)
                _validate_sources(session, value["sources"])
                _analysis(root, entry)

            with profiles.bank_operation():
                verify()
                if row.get("enrollment_recovered"):
                    profiles.rename_profile(profile_id, name)
                elif matrix is not None:
                    profiles._save_profile(name, matrix, source_kind="session_cluster",
                                           profile_id=profile_id, verify_source=verify)
                if matrix is not None or row.get("enrollment_recovered"):
                    row["enrolled_profile"] = profile_id
                _save_name(root, value, row, name)
        else:
            _save_name(root, value, row, name)
        return payload(session)


def _save_name(root, value, row, name):
    row.update(name=name, name_source="operator_confirmed")
    # Other machine suggestions remain stale until prepare() rematches them.
    _write(root, value)
