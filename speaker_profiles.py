"""Локальный opt-in банк голосовых отпечатков и open-set Speaker ID."""
from __future__ import annotations

from contextlib import contextmanager
import datetime as dt
import json
import os
import re
import threading
import uuid
from pathlib import Path

import numpy as np

import app_paths
from operation_lock import OperationLock
import speaker_diarization
import transcript_events


BASE = app_paths.DATA_ROOT
PROFILE_ROOT = BASE / ".speaker-profiles"
SCHEMA_VERSION = 1
MODEL_ID = speaker_diarization.EMBEDDING_MODEL.name
SUGGEST_THRESHOLD = 0.55
HIGH_CONFIDENCE_THRESHOLD = 0.68
HIGH_CONFIDENCE_MARGIN = 0.08
MIN_EMBEDDINGS = 2
MAX_EMBEDDINGS = 6
MAX_CALIBRATION_UTTERANCES = 12
MIN_CALIBRATION_SESSIONS = 2
ROBUST_SAMPLE_THRESHOLD = 0.55
SESSION_MATCH_THRESHOLD = 0.72
ROUTE_LEAK_THRESHOLD = 0.65
MIN_DIARIZED_SEGMENT_MS = 800
OVERLAP_REJECT_MS = 250
ECHO_CORRELATION_THRESHOLD = 0.92
_PROFILE_ID = re.compile(r"[a-f0-9]{32}")
_SPEAKER_ID = re.compile(r"SPEAKER_\d{2,4}(?:_SPLIT_\d{2,3})?", re.IGNORECASE)
_PRIMARY_JOURNAL = re.compile(r"transcript(?:-(?:[2-9]|[1-9]\d+))?\.jsonl",
                              re.IGNORECASE)
_DIARIZED_JOURNAL = re.compile(
    r"transcript(?:-\d+)?\.local\.diarized\.jsonl", re.IGNORECASE)
_EXTRACTOR = None
_EXTRACTOR_LOCK = threading.RLock()
_CALIBRATION_LOCK = threading.Lock()
_VERIFY_LOCK = threading.Lock()
_BANK_LOCK = threading.RLock()
_BANK_DEPTH = 0


@contextmanager
def bank_operation():
    """Serialize publishing, revoking and renaming, including across processes."""
    global _BANK_DEPTH
    with _BANK_LOCK:
        if PROFILE_ROOT.is_symlink():
            raise ValueError("Банк голосов не может быть ссылкой")
        lock_path = PROFILE_ROOT / ".bank.lock"
        if lock_path.is_symlink():
            raise ValueError("Блокировка банка не может быть ссылкой")
        lock = None if _BANK_DEPTH else OperationLock(lock_path)
        if lock:
            lock.acquire()
        _BANK_DEPTH += 1
        try:
            yield
        finally:
            _BANK_DEPTH -= 1
            if lock:
                lock.release()


def _revocation_path(profile_id: str) -> Path:
    root = PROFILE_ROOT / ".revocations"
    if PROFILE_ROOT.is_symlink() or root.is_symlink():
        raise ValueError("Журнал отзыва согласий не может быть ссылкой")
    path = root / (_profile_dir(profile_id).name + ".json")
    if path.is_symlink():
        raise ValueError("Запись об отзыве согласия не может быть ссылкой")
    return path


def consent_epoch(profile_id: str) -> str:
    try:
        marker = json.loads(_revocation_path(profile_id).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "initial"
    if not isinstance(marker, dict) or not _PROFILE_ID.fullmatch(str(marker.get("epoch", ""))):
        raise ValueError("Не удалось проверить отзыв голосового согласия")
    return marker["epoch"]


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _clean_name(value: object) -> str:
    name = " ".join(str(value or "").split())
    if not 1 <= len(name) <= 80:
        raise ValueError("имя голосового профиля должно содержать 1–80 символов")
    if any(ord(char) < 32 or char in "<>[]{}" for char in name):
        raise ValueError("имя голосового профиля содержит недопустимые символы")
    return name


def _profile_dir(profile_id: str) -> Path:
    checked = str(profile_id).casefold()
    if not _PROFILE_ID.fullmatch(checked):
        raise ValueError("недопустимый идентификатор голосового профиля")
    return PROFILE_ROOT / checked


def _manifest(path: Path) -> dict:
    value = json.loads((path / "profile.json").read_text(encoding="utf-8"))
    if (not isinstance(value, dict)
            or value.get("schema_version") != SCHEMA_VERSION
            or value.get("profile_id") != path.name
            or not isinstance(value.get("name"), str)
            or value.get("model") != MODEL_ID):
        raise ValueError(f"повреждён голосовой профиль: {path.name}")
    return value


def list_profiles() -> list[dict]:
    """Вернуть безопасные метаданные без самих биометрических embeddings."""
    if not PROFILE_ROOT.is_dir():
        return []
    result = []
    for path in PROFILE_ROOT.iterdir():
        if not path.is_dir() or not _PROFILE_ID.fullmatch(path.name):
            continue
        try:
            value = _manifest(path)
            with np.load(path / "embeddings.npz", allow_pickle=False) as saved:
                embeddings = np.asarray(saved["embeddings"], dtype=np.float32)
            if (embeddings.ndim != 2 or embeddings.shape[0] < MIN_EMBEDDINGS
                    or embeddings.shape[1] < 16 or not np.isfinite(embeddings).all()):
                raise ValueError("некорректная матрица embeddings")
            calibration = value.get("calibration")
            safe_calibration = ({key: calibration[key] for key in (
                "accepted_sessions", "rejected_sessions", "genuine_min",
                "negative_max", "negative_tests", "false_accepts",
                "false_accept_rate", "suggest_threshold", "profile_consistency",
            ) if key in calibration} if isinstance(calibration, dict) else None)
            result.append({
                "profile_id": path.name,
                "name": value["name"],
                "created_at": value.get("created_at", ""),
                "updated_at": value.get("updated_at", ""),
                "source_kind": value.get("source_kind", "unknown"),
                "embedding_count": int(embeddings.shape[0]),
                "retention": value.get("retention", "until_deleted"),
                "model": value["model"],
                "calibration": safe_calibration,
            })
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            result.append({
                "profile_id": path.name, "name": "Повреждённый профиль",
                "state": "error", "embedding_count": 0,
            })
    return sorted(result, key=lambda item: (
        str(item.get("name", "")).casefold(), str(item.get("profile_id", ""))))


def status() -> dict:
    profiles = list_profiles()
    return {
        "model_ready": speaker_diarization.EMBEDDING_MODEL.is_file(),
        "model": MODEL_ID,
        "profiles": profiles,
        "count": sum(item.get("state") != "error" for item in profiles),
        "local_only": True,
    }


def _extractor():
    global _EXTRACTOR
    with _EXTRACTOR_LOCK:
        if _EXTRACTOR is not None:
            return _EXTRACTOR
        if not speaker_diarization.EMBEDDING_MODEL.is_file():
            raise FileNotFoundError(
                "модель Speaker ID не установлена; сначала установите модели диаризации")
        import sherpa_onnx

        config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(speaker_diarization.EMBEDDING_MODEL),
            num_threads=max(1, min(8, os.cpu_count() or 1)), provider="cpu")
        if not config.validate():
            raise RuntimeError("невалидная конфигурация модели Speaker ID")
        _EXTRACTOR = sherpa_onnx.SpeakerEmbeddingExtractor(config)
        return _EXTRACTOR


def _normalise(vector: np.ndarray) -> np.ndarray:
    checked = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(checked))
    if checked.size < 16 or not np.isfinite(checked).all() or norm < 1e-6:
        raise ValueError("модель вернула некорректный голосовой отпечаток")
    return np.ascontiguousarray(checked / norm, dtype=np.float32)


def _compute_embedding(samples: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    extractor = _extractor()
    checked = np.ascontiguousarray(samples, dtype=np.float32)
    with _EXTRACTOR_LOCK:
        stream = extractor.create_stream()
        stream.accept_waveform(sample_rate=sample_rate, waveform=checked)
        stream.input_finished()
        if not extractor.is_ready(stream):
            raise ValueError("фрагмент слишком короткий для голосового отпечатка")
        return _normalise(np.asarray(extractor.compute(stream), dtype=np.float32))


def _trim_speech(samples: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    checked = np.asarray(samples, dtype=np.float32).reshape(-1)
    frame = max(1, sample_rate // 50)
    usable = checked[:len(checked) - len(checked) % frame]
    if len(usable) < sample_rate:
        raise ValueError("голосовой фрагмент короче одной секунды")
    frames = usable.reshape(-1, frame)
    levels = np.sqrt(np.mean(frames ** 2, axis=1))
    threshold = max(0.003, min(0.025, float(np.percentile(levels, 70)) * 0.3))
    active = np.flatnonzero(levels >= threshold)
    if len(active) * frame < sample_rate * 1.2:
        raise ValueError("в голосовом фрагменте недостаточно речи")
    if float(np.mean(np.abs(usable) >= 0.998)) > 0.01:
        raise ValueError("голосовой фрагмент перегружен и содержит клиппинг")
    margin = sample_rate // 10
    start = max(0, int(active[0]) * frame - margin)
    end = min(len(checked), (int(active[-1]) + 1) * frame + margin)
    result = checked[start:end]
    peak = float(np.max(np.abs(result)))
    rms = float(np.sqrt(np.mean(result ** 2)))
    if peak < 0.008 or rms < 0.002:
        raise ValueError("голосовой фрагмент записан слишком тихо")
    return np.ascontiguousarray(result, dtype=np.float32)


def _speech_windows(samples: np.ndarray, sample_rate: int = 16000) -> list[np.ndarray]:
    trimmed = _trim_speech(samples, sample_rate)
    window = sample_rate * 6
    minimum = sample_rate * 2
    chunks = []
    for start in range(0, len(trimmed), window):
        chunk = trimmed[start:min(len(trimmed), start + window)]
        if len(chunk) < minimum:
            continue
        try:
            chunks.append(_trim_speech(chunk, sample_rate))
        except ValueError:
            continue
        if len(chunks) >= MAX_EMBEDDINGS:
            break
    return chunks


def _embeddings(chunks: list[np.ndarray]) -> np.ndarray:
    vectors = []
    for chunk in chunks[:MAX_CALIBRATION_UTTERANCES]:
        try:
            vectors.append(_compute_embedding(chunk))
        except ValueError:
            continue
    if len(vectors) < MIN_EMBEDDINGS:
        raise ValueError(
            "нужно хотя бы два пригодных голосовых фрагмента; запишите больше чистой речи")
    return _robust_matrix(vectors)


def _robust_matrix(vectors: list[np.ndarray] | np.ndarray, *,
                   limit: int = MAX_EMBEDDINGS) -> np.ndarray:
    """Оставить согласованное ядро образцов, не усредняя чужой голос с нужным."""
    matrix = np.stack([_normalise(row) for row in np.asarray(vectors)])
    if len(matrix) < MIN_EMBEDDINGS:
        raise ValueError("нужно хотя бы два голосовых отпечатка")
    similarities = matrix @ matrix.T
    centrality = []
    for index in range(len(matrix)):
        others = np.delete(similarities[index], index)
        centrality.append(float(np.median(others)) if len(others) else 1.0)
    medoid = int(np.argmax(centrality))
    order = sorted(range(len(matrix)),
                   key=lambda index: float(similarities[medoid, index]),
                   reverse=True)
    selected = [index for index in order
                if float(similarities[medoid, index]) >= ROBUST_SAMPLE_THRESHOLD]
    selected = selected[:max(MIN_EMBEDDINGS, min(MAX_EMBEDDINGS, int(limit)))]
    if len(selected) < MIN_EMBEDDINGS:
        raise ValueError(
            "голосовые фрагменты не похожи друг на друга; перезапишите образец")
    return np.ascontiguousarray(matrix[selected], dtype=np.float32)


def _matrix_consistency(matrix: np.ndarray) -> float:
    checked = np.asarray(matrix, dtype=np.float32)
    pairs = [float(np.dot(checked[first], checked[second]))
             for first in range(len(checked))
             for second in range(first + 1, len(checked))]
    return round(float(np.median(pairs)), 4) if pairs else 1.0


def _save_profile(name: str, embeddings: np.ndarray, *, source_kind: str,
                  calibration: dict | None = None, profile_id: str | None = None,
                  verify_source=None) -> dict:
    with bank_operation():
        return _publish_profile(name, embeddings, source_kind=source_kind, calibration=calibration,
                                profile_id=profile_id, verify_source=verify_source)


def _clear_staged_profile(stage: Path) -> None:
    if stage.is_symlink():
        raise ValueError("Временный профиль не может быть ссылкой")
    if not stage.exists():
        return
    allowed = {"profile.json","profile.json.tmp","embeddings.npz","embeddings.npz.tmp"}
    files = list(stage.iterdir())
    if any(item.name not in allowed or item.is_symlink() or not item.is_file() for item in files):
        raise ValueError("Временный профиль содержит неожиданные данные")
    for item in files:
        item.unlink()
    stage.rmdir()


def _publish_profile(name, embeddings, *, source_kind, calibration, profile_id, verify_source):
    checked_name = _clean_name(name)
    matrix = np.asarray(embeddings, dtype=np.float32)
    if (matrix.ndim != 2 or not MIN_EMBEDDINGS <= matrix.shape[0] <= MAX_EMBEDDINGS
            or matrix.shape[1] < 16 or not np.isfinite(matrix).all()):
        raise ValueError("некорректный набор голосовых отпечатков")
    matrix = np.stack([_normalise(row) for row in matrix])
    profile_id = profile_id or uuid.uuid4().hex
    target = _profile_dir(profile_id)
    if target.is_symlink():
        raise ValueError("Профиль голоса не может быть ссылкой")
    PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
    if target.exists():
        saved = _manifest(target)
        if saved['name'] != checked_name or saved.get('source_kind') != source_kind:
            raise ValueError('Идентификатор голосового профиля уже занят')
        return next(item for item in list_profiles() if item['profile_id'] == profile_id)
    stage = PROFILE_ROOT / (".pending-" + target.name)
    _clear_staged_profile(stage)
    stage.mkdir()
    try:
        temporary = stage / "embeddings.npz.tmp"
        with temporary.open("wb") as output:
            np.savez_compressed(output, embeddings=matrix)
        os.replace(temporary, stage / "embeddings.npz")
        timestamp = _now()
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "profile_id": profile_id,
            "name": checked_name,
            "created_at": timestamp,
            "updated_at": timestamp,
            "model": MODEL_ID,
            "model_sha256": speaker_diarization.EMBEDDING_SHA256,
            "source_kind": str(source_kind)[:40],
            "consent": "operator_confirmed",
            "retention": "until_deleted",
            "raw_audio_saved": False,
            "embedding_count": int(matrix.shape[0]),
        }
        if isinstance(calibration, dict):
            manifest["calibration"] = calibration
        _atomic_json(stage / "profile.json", manifest)
        if verify_source is not None:
            verify_source()
        os.replace(stage, target)
    except Exception:
        _clear_staged_profile(stage)
        raise
    return next(item for item in list_profiles() if item["profile_id"] == profile_id)


def enroll_audio_file(name: str, audio: Path, *, consent: bool,
                      source_kind: str = "audio_file") -> dict:
    """Создать профиль из локального WAV, не сохраняя копию исходного аудио."""
    if consent is not True:
        raise ValueError("для создания голосового профиля нужно явное подтверждение")
    path = Path(audio).resolve()
    if not path.is_file():
        raise FileNotFoundError("голосовой образец не найден")
    samples = speaker_diarization._load_audio(path, 16000)
    return _save_profile(
        name, _embeddings(_speech_windows(samples)), source_kind=source_kind)


def rename_profile(profile_id: str, name: str) -> dict:
    """Переименовать профиль, не затрагивая его биометрические признаки."""
    with bank_operation():
        return _rename_profile(profile_id, name)


def _rename_profile(profile_id: str, name: str) -> dict:
    checked_name = _clean_name(name)
    path = _profile_dir(profile_id)
    if not path.is_dir():
        raise FileNotFoundError("голосовой профиль не найден")
    manifest = _manifest(path)
    manifest["name"] = checked_name
    manifest["updated_at"] = _now()
    _atomic_json(path / "profile.json", manifest)
    return next(item for item in list_profiles()
                if item["profile_id"] == path.name)


def _role_audio_events(session: Path, role: str) -> tuple[Path, list[dict]]:
    choices = []
    for journal in Path(session).glob("transcript*.jsonl"):
        if not _PRIMARY_JOURNAL.fullmatch(journal.name):
            continue
        try:
            records = transcript_events.read_records(journal)
        except (OSError, ValueError):
            continue
        if not records:
            continue
        audio_name = str((records[0].get("audio_files") or {}).get(role) or "")
        if (Path(audio_name).name != audio_name
                or not speaker_diarization._AUDIO_NAME.fullmatch(audio_name)):
            continue
        audio = Path(session) / audio_name
        if not audio.is_file():
            continue
        events = [item for item in records[1:]
                  if item.get("record_type") == "utterance"
                  and item.get("status", "final") == "final"
                  and item.get("speaker_role") == role]
        if events:
            choices.append((len(events), audio, events))
    if not choices:
        raise ValueError(f"в сессии нет размеченной дорожки «{role}»")
    _, audio, events = max(choices, key=lambda item: item[0])
    return audio, events


def _role_chunks(session: Path, role: str) -> list[np.ndarray]:
    audio, events = _role_audio_events(session, role)
    samples = speaker_diarization._load_audio(audio, 16000)
    candidates = []
    for event in events:
        try:
            start = max(0, int(event.get("start_ms", 0)) * 16)
            end = min(len(samples), int(event.get("end_ms", 0)) * 16)
        except (TypeError, ValueError):
            continue
        if end - start < 32_000:
            continue
        # Длинный финал STT часто включает паузы. Для embedding достаточно 10 с.
        end = min(end, start + 160_000)
        try:
            chunk = _trim_speech(samples[start:end])
        except ValueError:
            continue
        candidates.append((end - start, chunk))
    return [chunk for _, chunk in sorted(
        candidates, key=lambda item: item[0], reverse=True
    )[:MAX_CALIBRATION_UTTERANCES]]


def _session_voiceprint(session: Path, role: str) -> dict:
    matrix = _embeddings(_role_chunks(session, role))
    centroid = _normalise(matrix.mean(axis=0))
    return {
        "matrix": matrix,
        "centroid": centroid,
        "consistency": _matrix_consistency(matrix),
    }


def _dominant_sessions(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    if len(entries) < MIN_CALIBRATION_SESSIONS:
        raise ValueError(
            "для калибровки нужны хотя бы две завершённые встречи с чистым микрофоном")
    similarity = np.asarray([
        [float(np.dot(first["centroid"], second["centroid"]))
         for second in entries] for first in entries], dtype=np.float32)
    neighborhoods = []
    for index in range(len(entries)):
        members = [item for item in range(len(entries))
                   if float(similarity[index, item]) >= SESSION_MATCH_THRESHOLD]
        mean = float(np.mean([similarity[index, item] for item in members]))
        neighborhoods.append((len(members), mean, index, members))
    _, _, _, members = max(neighborhoods)
    accepted = [entries[index] for index in members]
    rejected = [entry for index, entry in enumerate(entries) if index not in members]
    if len(accepted) < MIN_CALIBRATION_SESSIONS:
        raise ValueError(
            "архивные образцы не образуют устойчивый профиль одного голоса")
    return accepted, rejected


def _calibration_profile_matrix(entries: list[dict]) -> np.ndarray:
    ranked = []
    for entry in entries:
        centroid = entry["centroid"]
        ranked.append(sorted(
            list(entry["matrix"]),
            key=lambda vector: float(np.dot(vector, centroid)), reverse=True))
    selected = []
    for offset in range(MAX_EMBEDDINGS):
        for vectors in ranked:
            if offset < len(vectors):
                selected.append(vectors[offset])
                if len(selected) >= MAX_EMBEDDINGS:
                    return _robust_matrix(selected)
    return _robust_matrix(selected)


def _calibrate_sessions_profile(name: str, sessions_root: Path, *,
                                consent: bool) -> dict:
    """Создать профиль оператора из согласованного ядра архивных mic-дорожек."""
    if consent is not True:
        raise ValueError("для создания голосового профиля нужно явное подтверждение")
    root = Path(sessions_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError("архив встреч не найден")
    candidates = []
    negatives = []
    rejected_count = 0
    for session in sorted(root.iterdir(), key=lambda path: path.name):
        if (not session.is_dir() or session.is_symlink()
                or session.resolve().parent != root):
            continue
        try:
            mine = _session_voiceprint(session, "Я")
        except (OSError, ValueError):
            continue
        remote = None
        try:
            remote = _session_voiceprint(session, "Собеседник")
            negatives.append(remote["centroid"])
        except (OSError, ValueError):
            pass
        if (remote is not None and float(np.dot(
                mine["centroid"], remote["centroid"])) >= ROUTE_LEAK_THRESHOLD):
            rejected_count += 1
            continue
        candidates.append(mine)
    accepted, outliers = _dominant_sessions(candidates)
    rejected_count += len(outliers)
    matrix = _calibration_profile_matrix(accepted)
    centroid = _normalise(matrix.mean(axis=0))
    genuine = []
    for entry in accepted:
        others = [item["centroid"] for item in accepted if item is not entry]
        reference = _normalise(np.mean(others, axis=0)) if others else centroid
        genuine.append(float(np.dot(entry["centroid"], reference)))
    negative_scores = [float(np.dot(centroid, item)) for item in negatives]
    false_accepts = sum(score >= SUGGEST_THRESHOLD for score in negative_scores)
    calibration = {
        "accepted_sessions": len(accepted),
        "rejected_sessions": rejected_count,
        "genuine_min": round(min(genuine), 4),
        "negative_max": round(max(negative_scores), 4) if negative_scores else None,
        "negative_tests": len(negative_scores),
        "false_accepts": false_accepts,
        "false_accept_rate": round(false_accepts / max(1, len(negative_scores)), 4),
        "suggest_threshold": SUGGEST_THRESHOLD,
        "profile_consistency": _matrix_consistency(matrix),
    }
    return _save_profile(
        name, matrix, source_kind="calibrated_sessions",
        calibration=calibration)


def calibrate_sessions_profile(name: str, sessions_root: Path, *,
                               consent: bool) -> dict:
    if consent is not True:
        raise ValueError("для создания голосового профиля нужно явное подтверждение")
    checked_name = _clean_name(name)
    if not _CALIBRATION_LOCK.acquire(blocking=False):
        raise RuntimeError("калибровка банка голосов уже выполняется")
    try:
        return _calibrate_sessions_profile(
            checked_name, sessions_root, consent=consent)
    finally:
        _CALIBRATION_LOCK.release()


def _overlap_ms(left: tuple[int, int], right: tuple[int, int]) -> int:
    return max(0, min(left[1], right[1]) - max(left[0], right[0]))


def _excluded_speaker_intervals(session: Path, speaker_id: str) -> list[tuple[int, int]]:
    """Найти интервалы TTS, явного эха и почти нераспознанного шума."""
    result = []
    for journal in Path(session).glob("transcript*.local.diarized.jsonl"):
        if not _DIARIZED_JOURNAL.fullmatch(journal.name):
            continue
        try:
            records = transcript_events.read_records(journal)
        except (OSError, ValueError):
            continue
        for item in records[1:]:
            if (item.get("record_type") != "utterance"
                    or str(item.get("speaker_id") or "") != speaker_id):
                continue
            confidence = transcript_events.event_confidence(item)
            echo_similarity = item.get("echo_similarity")
            contaminated = (
                str(item.get("source") or "").casefold() == "synthetic"
                or (isinstance(echo_similarity, (int, float))
                    and float(echo_similarity) >= 0.75)
                or (isinstance(confidence, (int, float))
                    and float(confidence) < 0.15)
            )
            if contaminated:
                result.append((max(0, int(item.get("start_ms", 0))),
                               max(0, int(item.get("end_ms", 0)))))
    return result


def _paired_audio(session: Path, audio_name: str) -> np.ndarray | None:
    matched = re.fullmatch(
        r"audio-(me|guest)(-\d+)?\.wav", audio_name, re.IGNORECASE)
    if not matched:
        return None
    role = "guest" if matched.group(1).casefold() == "me" else "me"
    candidate = Path(session) / f"audio-{role}{matched.group(2) or ''}.wav"
    if not candidate.is_file():
        return None
    try:
        return speaker_diarization._load_audio(candidate, 16000)
    except (OSError, ValueError):
        return None


def _rms_envelope(samples: np.ndarray, frame: int = 320) -> np.ndarray:
    checked = np.asarray(samples, dtype=np.float32).reshape(-1)
    usable = checked[:len(checked) - len(checked) % frame]
    if len(usable) < frame * 10:
        return np.empty(0, dtype=np.float32)
    return np.sqrt(np.mean(usable.reshape(-1, frame) ** 2, axis=1))


def _echo_correlation(primary: np.ndarray, reference: np.ndarray,
                      start: int, end: int, sample_rate: int = 16000) -> float:
    """Консервативно искать одно и то же огибающее в соседней дорожке."""
    margin = sample_rate
    target = _rms_envelope(primary[start:end])
    left = max(0, start - margin)
    right = min(len(reference), end + margin)
    candidate = _rms_envelope(reference[left:right])
    if len(target) < 20 or len(candidate) < len(target):
        return 0.0
    centered_target = target - float(np.mean(target))
    target_norm = float(np.linalg.norm(centered_target))
    if target_norm < 1e-5 or float(np.max(target)) < 0.002:
        return 0.0
    best = 0.0
    for offset in range(0, len(candidate) - len(target) + 1):
        window = candidate[offset:offset + len(target)]
        centered = window - float(np.mean(window))
        denominator = target_norm * float(np.linalg.norm(centered))
        if denominator < 1e-8:
            continue
        best = max(best, float(np.dot(centered_target, centered) / denominator))
    return round(best, 4)


def _fragment_signal_ok(samples: np.ndarray) -> bool:
    checked = np.asarray(samples, dtype=np.float32)
    if not len(checked):
        return False
    peak = float(np.max(np.abs(checked)))
    rms = float(np.sqrt(np.mean(checked ** 2)))
    clipping = float(np.mean(np.abs(checked) >= 0.998))
    return peak >= 0.008 and rms >= 0.002 and clipping <= 0.01


def _session_chunk_selection(session: Path, speaker_id: str) -> tuple[list[np.ndarray], dict]:
    session = Path(session).resolve()
    checked_id = str(speaker_id)
    if not _SPEAKER_ID.fullmatch(checked_id):
        raise ValueError("недопустимый кластер говорящего")
    diarization = json.loads(
        (session / speaker_diarization.DIARIZATION_FILE).read_text(encoding="utf-8"))
    audio_name = str(diarization.get("audio_file") or "")
    if (Path(audio_name).name != audio_name
            or not speaker_diarization._AUDIO_NAME.fullmatch(audio_name)):
        raise ValueError("в результате диаризации указан недопустимый WAV")
    audio = session / audio_name
    if not audio.is_file():
        raise FileNotFoundError("исходный WAV диаризации не найден")
    all_segments = []
    for item in diarization.get("segments", []):
        if not isinstance(item, dict):
            continue
        try:
            start_ms = max(0, int(item.get("start_ms", 0)))
            end_ms = max(start_ms, int(item.get("end_ms", 0)))
        except (TypeError, ValueError):
            continue
        if end_ms <= start_ms:
            continue
        all_segments.append({
            "start_ms": start_ms, "end_ms": end_ms,
            "speaker_id": str(item.get("speaker_id") or ""),
        })
    segments = [item for item in all_segments
                if item["speaker_id"] == checked_id]
    if not segments:
        raise ValueError(f"в диаризации нет кластера {checked_id}")
    samples = speaker_diarization._load_audio(audio, 16000)
    paired = _paired_audio(session, audio_name)
    excluded = _excluded_speaker_intervals(session, checked_id)
    quality = {
        "segments_total": len(segments), "segments_used": 0,
        "rejected_short": 0, "rejected_overlap": 0,
        "rejected_noise": 0, "rejected_tts_or_echo": 0,
    }
    selected_audio = []
    # Сначала длинные и информативные интервалы, затем сохраняем их временной порядок.
    selected = sorted(segments, key=lambda item: int(item.get("end_ms", 0))
                      - int(item.get("start_ms", 0)), reverse=True)[:20]
    for item in sorted(selected, key=lambda value: int(value.get("start_ms", 0))):
        start_ms = max(0, int(item.get("start_ms", 0)))
        end_ms = max(start_ms, int(item.get("end_ms", 0)))
        duration_ms = end_ms - start_ms
        if duration_ms < MIN_DIARIZED_SEGMENT_MS:
            quality["rejected_short"] += 1
            continue
        overlap = max((
            _overlap_ms((start_ms, end_ms), (
                int(other.get("start_ms", 0)), int(other.get("end_ms", 0))))
            for other in all_segments
            if str(other.get("speaker_id") or "") != checked_id
        ), default=0)
        if overlap >= max(OVERLAP_REJECT_MS, round(duration_ms * 0.2)):
            quality["rejected_overlap"] += 1
            continue
        if any(_overlap_ms((start_ms, end_ms), interval)
               >= min(OVERLAP_REJECT_MS, max(1, duration_ms // 3))
               for interval in excluded):
            quality["rejected_tts_or_echo"] += 1
            continue
        start = start_ms * 16
        end = min(len(samples), end_ms * 16)
        if end <= start:
            continue
        chunk = samples[start:end]
        if not _fragment_signal_ok(chunk):
            quality["rejected_noise"] += 1
            continue
        if (paired is not None and _echo_correlation(
                samples, paired, start, end) >= ECHO_CORRELATION_THRESHOLD):
            quality["rejected_tts_or_echo"] += 1
            continue
        selected_audio.append(chunk)
        quality["segments_used"] += 1
        if len(selected_audio) >= 10:
            break
    if not selected_audio:
        return [], quality
    # Короткие реплики одного кластера объединяем: модель требует минимум две
    # секунды, а диаризация часто режет живую речь на интервалы по 0.5–1.5 с.
    separator = np.zeros(1600, dtype=np.float32)
    joined = []
    for index, chunk in enumerate(selected_audio):
        if index:
            joined.append(separator)
        joined.append(np.asarray(chunk, dtype=np.float32))
    return _speech_windows(np.concatenate(joined))[:MAX_EMBEDDINGS], quality


def _session_chunks(session: Path, speaker_id: str) -> list[np.ndarray]:
    return _session_chunk_selection(session, speaker_id)[0]


def enroll_session_speaker(session: Path, speaker_id: str, name: str, *,
                           consent: bool) -> dict:
    if consent is not True:
        raise ValueError("для создания голосового профиля нужно явное подтверждение")
    return _save_profile(
        name, _embeddings(_session_chunks(session, speaker_id)),
        source_kind="session_cluster")


def delete_profile(profile_id: str) -> dict:
    with bank_operation():
        return _delete_profile(profile_id)


def _delete_profile(profile_id: str) -> dict:
    path = _profile_dir(profile_id)
    if path.is_symlink() or not path.is_dir():
        raise FileNotFoundError("голосовой профиль не найден")
    try:
        name = _manifest(path)["name"]
    except (OSError, ValueError, json.JSONDecodeError):
        name = "Повреждённый профиль"
    allowed = {"profile.json", "profile.json.tmp", "embeddings.npz",
               "embeddings.npz.tmp"}
    unexpected = [item.name for item in path.iterdir()
                  if not item.is_file() or item.name not in allowed]
    if unexpected:
        raise ValueError("папка голосового профиля содержит неожиданные данные")
    revocation = _revocation_path(profile_id)
    revocation.parent.mkdir(exist_ok=True)
    _atomic_json(revocation, {"epoch":uuid.uuid4().hex})
    _clear_staged_profile(PROFILE_ROOT / (".pending-" + path.name))
    for filename in allowed:
        (path / filename).unlink(missing_ok=True)
    path.rmdir()
    return {"deleted": str(profile_id), "name": name}


def _profile_centroids() -> list[tuple[dict, np.ndarray]]:
    result = []
    for item in list_profiles():
        if item.get("state") == "error":
            continue
        path = _profile_dir(item["profile_id"])
        with np.load(path / "embeddings.npz", allow_pickle=False) as saved:
            matrix = np.asarray(saved["embeddings"], dtype=np.float32)
        result.append((item, _normalise(matrix.mean(axis=0))))
    return result


def _match(query: np.ndarray, profiles: list[tuple[dict, np.ndarray]]) -> dict:
    scores = sorted((
        (float(np.dot(query, centroid)), profile)
        for profile, centroid in profiles), key=lambda value: value[0], reverse=True)
    if not scores:
        return {"state": "no_profiles", "name": "", "similarity": None,
                "margin": None, "strong_suggestion": False,
                "reason_code": "no_profiles",
                "reason": "В банке ещё нет пригодных голосовых профилей.",
                "alternatives": []}
    best_score, best = scores[0]
    second_score = scores[1][0] if len(scores) > 1 else 0.0
    margin = best_score - second_score
    if best_score < SUGGEST_THRESHOLD:
        state = "unknown"
        name = ""
        reason_code = "below_threshold"
        reason = (f"Лучшее сходство {best_score:.0%} ниже безопасного порога "
                  f"{SUGGEST_THRESHOLD:.0%}.")
    elif (best_score >= HIGH_CONFIDENCE_THRESHOLD
          and margin >= HIGH_CONFIDENCE_MARGIN):
        state = "high"
        name = best["name"]
        reason_code = "clear_leader"
        reason = (f"Профиль — явный лидер: сходство {best_score:.0%}, "
                  f"отрыв от следующего {margin:.0%}.")
    else:
        state = "review"
        name = best["name"]
        if best_score < HIGH_CONFIDENCE_THRESHOLD:
            reason_code = "moderate_similarity"
            reason = (f"Сходство {best_score:.0%} прошло минимальный порог, "
                      "но имя нужно проверить на слух.")
        else:
            reason_code = "close_alternative"
            reason = (f"Два профиля слишком близки: отрыв только {margin:.0%}; "
                      "выберите имя вручную после прослушивания.")
    return {
        "state": state,
        "profile_id": best["profile_id"] if name else "",
        "best_profile_id": best["profile_id"],
        "name": name,
        "similarity": round(best_score, 4),
        "margin": round(margin, 4),
        "strong_suggestion": state == "high",
        "reason_code": reason_code,
        "reason": reason,
        "alternatives": [{"profile_id": profile["profile_id"],
                           "name": profile["name"], "similarity": round(score, 4)}
                          for score, profile in scores[:3]],
    }


def identify_audio_file(audio: Path) -> dict:
    """Сопоставить локальный WAV со всем банком, не сохраняя исходное аудио."""
    path = Path(audio).resolve()
    if not path.is_file():
        raise FileNotFoundError("проверочная запись не найдена")
    samples = speaker_diarization._load_audio(path, 16000)
    matrix = _embeddings(_speech_windows(samples))
    result = _match(_normalise(matrix.mean(axis=0)), _profile_centroids())
    return {**result, "fragments": int(matrix.shape[0]),
            "raw_audio_saved": False}


def verify_microphone(profile_id: str, selector: str, *, seconds: int = 15) -> dict:
    """Записать одноразовую проверку и сравнить её с выбранным профилем."""
    target = _profile_dir(profile_id)
    if not target.is_dir():
        raise FileNotFoundError("голосовой профиль не найден")
    expected = _manifest(target)
    if not _VERIFY_LOCK.acquire(blocking=False):
        raise RuntimeError("проверка банка голосов уже выполняется")
    sample: Path | None = None
    try:
        PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
        sample = PROFILE_ROOT / f".verification-{uuid.uuid4().hex}.wav"
        import voice_clone
        captured = voice_clone.record_temporary_sample(
            selector, sample, seconds=seconds)
        result = identify_audio_file(sample)
        matched = result.get("best_profile_id") == target.name
        return {
            **result,
            "expected_profile_id": target.name,
            "expected_name": expected["name"],
            "matched_expected": bool(matched),
            "device": str(captured.get("device") or ""),
            "seconds": captured.get("seconds", seconds),
        }
    finally:
        if sample is not None:
            sample.unlink(missing_ok=True)
            sample.with_suffix(sample.suffix + ".tmp").unlink(missing_ok=True)
        _VERIFY_LOCK.release()


def identify_session(session: Path) -> dict:
    """Сопоставить анонимные кластеры с банком, ничего не применяя автоматически."""
    profiles = _profile_centroids()
    diarization = json.loads((Path(session) / speaker_diarization.DIARIZATION_FILE)
                             .read_text(encoding="utf-8"))
    speaker_ids = sorted({str(item.get("speaker_id") or "")
                          for item in diarization.get("segments", [])
                          if isinstance(item, dict)
                          and _SPEAKER_ID.fullmatch(str(item.get("speaker_id") or ""))})
    suggestions = {}
    for speaker_id in speaker_ids:
        try:
            chunks, quality = _session_chunk_selection(session, speaker_id)
            matrix = _embeddings(chunks)
            query = _normalise(matrix.mean(axis=0))
            suggestions[speaker_id] = {
                **_match(query, profiles), "fragments": int(matrix.shape[0]),
                "quality": quality}
        except (OSError, ValueError) as exc:
            suggestions[speaker_id] = {
                "state": "insufficient", "name": "", "similarity": None,
                "fragments": 0, "message": str(exc), "alternatives": [],
                "reason_code": "insufficient_audio",
                "reason": str(exc)}
    return {
        "schema_version": 1,
        "created_at": _now(),
        "model": MODEL_ID,
        "thresholds": {"suggest": SUGGEST_THRESHOLD,
                       "high_confidence": HIGH_CONFIDENCE_THRESHOLD,
                       "margin": HIGH_CONFIDENCE_MARGIN},
        "applied": False,
        "suggestions": suggestions,
    }
