"""Локальная постдиаризация WAV и перенос кластеров на word timestamps."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
from collections.abc import Callable
from pathlib import Path

import numpy as np

import app_paths
import evidence
import transcript_events


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE = app_paths.DATA_ROOT
MODEL_ROOT = BASE / ".models" / "speaker-diarization"
SEGMENTATION_MODEL = (
    MODEL_ROOT / "sherpa-onnx-pyannote-segmentation-3-0" / "model.int8.onnx")
EMBEDDING_MODEL = (
    MODEL_ROOT / "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx")
NEMO_EMBEDDING_MODEL = MODEL_ROOT / "nemo_en_titanet_small.onnx"
SEGMENTATION_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-segmentation-models/"
    "sherpa-onnx-pyannote-segmentation-3-0.tar.bz2")
SEGMENTATION_SHA256 = (
    "24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488")
SEGMENTATION_MODEL_SHA256 = (
    "d582f4b4c6b48205de7e0643c57df0df5615a3c176189be3fc461e9d18827b5d")
EMBEDDING_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-recongition-models/"
    "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx")
EMBEDDING_SHA256 = (
    "1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b")
NEMO_EMBEDDING_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-recongition-models/nemo_en_titanet_small.onnx")
NEMO_EMBEDDING_SHA256 = (
    "ad4a1802485d8b34c722d2a9d04249662f2ece5d28a7a039063ca22f515a789e")
DIARIZATION_EMBEDDINGS = {
    "nemo": NEMO_EMBEDDING_MODEL,
    "3dspeaker": EMBEDDING_MODEL,
}
DEFAULT_DIARIZATION_EMBEDDING = "nemo"
_AUDIO_NAME = re.compile(r"audio-(?:me|guest)(?:-\d+)?\.wav", re.IGNORECASE)
_TRANSCRIPT_NAME = re.compile(
    r"transcript(?:-\d+)?\.local(?:\.diarized)?\.jsonl", re.IGNORECASE)
_SPEAKER_ID = re.compile(
    r"SPEAKER_\d{2,4}(?:_SPLIT_\d{2,3})?", re.IGNORECASE)
REMOTE_ROLE = "Собеседник"
DIARIZATION_FILE = "diarization.json"
DIARIZED_TRANSCRIPT_FILE = "transcript.local.diarized.jsonl"
_MAP_ROLES = frozenset({"Я", REMOTE_ROLE})


def _clustering_num_clusters(speakers: int) -> int:
    """Convert the public auto-count value to sherpa-onnx semantics."""
    checked = int(speakers)
    if not 0 <= checked <= 20:
        raise ValueError("число говорящих должно быть от 0 (авто) до 20")
    return -1 if checked == 0 else checked


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, output: Path, expected_sha256: str) -> None:
    import requests

    temporary = output.with_name(output.name + ".download")
    temporary.unlink(missing_ok=True)
    digest = hashlib.sha256()
    size = 0
    try:
        with requests.get(url, stream=True, timeout=(10, 120)) as response:
            response.raise_for_status()
            with temporary.open("xb") as target:
                for chunk in response.iter_content(1024 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > 150 * 1024 * 1024:
                        raise ValueError("файл модели превысил безопасный лимит")
                    digest.update(chunk)
                    target.write(chunk)
        if digest.hexdigest() != expected_sha256:
            raise ValueError("контрольная сумма модели не совпала")
        os.replace(temporary, output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _safe_rmtree(path: Path) -> None:
    root = MODEL_ROOT.resolve()
    resolved = path.resolve()
    if resolved.parent != root or not resolved.name.endswith(".extract"):
        raise ValueError(f"отказ от удаления неожиданного пути: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _ensure_model(path: Path, url: str, checksum: str) -> bool:
    if not path.exists():
        print(f"Скачиваю {path.name}…", flush=True)
        _download(url, path, checksum)
        return False
    if _sha256(path) != checksum:
        raise ValueError(f"неожиданный файл модели: {path}")
    print(f"Уже установлена: {path.name}")
    return True


def _installed_model(path: Path, checksum: str) -> bool:
    if not path.exists():
        return False
    if _sha256(path) != checksum:
        raise ValueError(f"неожиданный файл модели: {path}")
    print(f"Уже установлена: {path.name}")
    return True


def _validate_archive_members(bundle: tarfile.TarFile, extraction: Path) -> None:
    root = extraction.resolve()
    for member in bundle.getmembers():
        target = (extraction / member.name).resolve()
        if target != root and root not in target.parents:
            raise ValueError("архив модели содержит небезопасный путь")


def _move_segmentation_model(extraction: Path) -> None:
    extracted = extraction / SEGMENTATION_MODEL.parent.name
    if _sha256(extracted / SEGMENTATION_MODEL.name) != SEGMENTATION_MODEL_SHA256:
        raise ValueError("контрольная сумма распакованной модели не совпала")
    destination = SEGMENTATION_MODEL.parent
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise ValueError(
                f"папка модели уже занята неполной установкой: {destination}")
        destination.rmdir()
    os.replace(extracted, destination)


def _install_segmentation_archive() -> None:
    archive = MODEL_ROOT / "segmentation.tar.bz2"
    extraction = MODEL_ROOT / "segmentation.extract"
    print("Скачиваю pyannote segmentation ONNX…", flush=True)
    _download(SEGMENTATION_URL, archive, SEGMENTATION_SHA256)
    _safe_rmtree(extraction)
    extraction.mkdir()
    try:
        with tarfile.open(archive, "r:bz2") as bundle:
            _validate_archive_members(bundle, extraction)
            bundle.extractall(extraction, filter="data")
        _move_segmentation_model(extraction)
    finally:
        archive.unlink(missing_ok=True)
        _safe_rmtree(extraction)


def install_models() -> None:
    """Скачать закреплённые открытые модели и проверить SHA-256."""
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    print("Локальные модели: около 82 МБ; pyannote segmentation — MIT; "
          "NeMo TitaNet и 3D-Speaker — Apache-2.0.")
    _ensure_model(
        NEMO_EMBEDDING_MODEL, NEMO_EMBEDDING_URL, NEMO_EMBEDDING_SHA256)
    _ensure_model(EMBEDDING_MODEL, EMBEDDING_URL, EMBEDDING_SHA256)
    if _installed_model(SEGMENTATION_MODEL, SEGMENTATION_MODEL_SHA256):
        return
    _install_segmentation_archive()


def _direct_file(session: Path, name: str, pattern: re.Pattern) -> Path:
    if Path(name).name != name or not pattern.fullmatch(name):
        raise ValueError(f"недопустимое имя файла: {name}")
    return session / name


def _load_audio(path, sample_rate: int = 16000) -> np.ndarray:
    """Декодировать и качественно привести WAV к mono float32/16 kHz."""
    import av

    chunks = []
    with av.open(str(path) if isinstance(path, (str, Path)) else path) as container:
        resampler = av.AudioResampler(
            format="flt", layout="mono", rate=sample_rate)
        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                chunks.append(converted.to_ndarray().reshape(-1).astype(
                    np.float32, copy=False))
        for converted in resampler.resample(None):
            chunks.append(converted.to_ndarray().reshape(-1).astype(
                np.float32, copy=False))
    if not chunks:
        raise ValueError("аудиофайл не содержит декодируемых сэмплов")
    return np.concatenate(chunks)


def diarize(session: Path, *, audio_name: str = "audio-me.wav",
            output_name: str = DIARIZATION_FILE, speakers: int = 2,
            threshold: float = 0.5,
            embedding_model: str = DEFAULT_DIARIZATION_EMBEDDING) -> Path:
    """Выполнить diarization целого файла через sherpa-onnx на CPU."""
    session = Path(session).resolve()
    audio = _direct_file(session, audio_name, _AUDIO_NAME)
    output = _diarization_path(session, output_name)
    return diarize_audio(
        audio, output, audio_name=audio_name,
        speakers=speakers, threshold=threshold,
        embedding_model=embedding_model)


def diarize_audio(audio: Path, output: Path, *, audio_name: str,
                  speakers: int = 2, threshold: float = 0.5,
                  embedding_model: str = DEFAULT_DIARIZATION_EMBEDDING,
                  progress_callback: Callable[[int, int], None] | None = None,
                  cancelled: Callable[[], bool] | None = None) -> Path:
    """Диаризовать явно заданный WAV в новый JSON, не меняя источник."""
    import sherpa_onnx

    audio = Path(audio).resolve()
    output = Path(output).resolve()
    if (Path(audio_name).name != audio_name
            or not _AUDIO_NAME.fullmatch(audio_name)):
        raise ValueError("разрешён только WAV-канал audio-me/audio-guest")
    if not re.fullmatch(
            r"diarization(?:-[a-z0-9_-]+)?\.json", output.name, re.IGNORECASE):
        raise ValueError("результат диаризации должен называться diarization*.json")
    if output.exists():
        raise FileExistsError(f"результат уже существует: {output}")
    if not audio.is_file():
        raise FileNotFoundError(f"аудиофайл не найден: {audio}")
    clustering_speakers = _clustering_num_clusters(speakers)
    if not 0 < float(threshold) <= 1:
        raise ValueError("порог кластеризации должен быть больше 0 и не больше 1")
    embedding_key = str(embedding_model).strip().casefold()
    embedding_path = DIARIZATION_EMBEDDINGS.get(embedding_key)
    if embedding_path is None:
        raise ValueError("неизвестная модель голосовых признаков")
    for model in (SEGMENTATION_MODEL, embedding_path):
        if not model.is_file():
            raise FileNotFoundError(
                f"модель не установлена: {model}; см. раздел «Аудио и говорящие» в справке")
    threads = max(1, min(8, os.cpu_count() or 1))
    segmentation = sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
        pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
            model=str(SEGMENTATION_MODEL)),
        num_threads=threads, provider="cpu")
    embedding = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
        model=str(embedding_path), num_threads=threads, provider="cpu")
    checked_speakers = int(speakers)
    clustering = sherpa_onnx.FastClusteringConfig(
        num_clusters=clustering_speakers,
        threshold=float(threshold))
    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=segmentation, embedding=embedding, clustering=clustering,
        min_duration_on=0.3, min_duration_off=0.5)
    if not config.validate():
        raise RuntimeError(f"невалидная конфигурация diarization: {config}")
    engine = sherpa_onnx.OfflineSpeakerDiarization(config)
    print(f"Читаю {audio.name} и привожу к {engine.sample_rate} Hz…", flush=True)
    samples = _load_audio(audio, engine.sample_rate)
    last_percent = -5

    def progress(done: int, total: int) -> int:
        nonlocal last_percent
        percent = int(done * 100 / max(1, total))
        if percent >= last_percent + 5 or percent == 100:
            last_percent = percent
            print(f"Диаризация: {percent}% ({done}/{total})", flush=True)
        if progress_callback:
            progress_callback(int(done), int(total))
        return 1 if cancelled and cancelled() else 0

    result = engine.process(samples, progress)
    if cancelled and cancelled():
        raise InterruptedError("диаризация отменена")
    segments = [{
        "start_ms": max(0, round(float(item.start) * 1000)),
        "end_ms": max(0, round(float(item.end) * 1000)),
        "speaker_id": f"SPEAKER_{int(item.speaker):02d}",
    } for item in result.sort_by_start_time()]
    payload = {
        "schema_version": 1,
        "created_at": dt.datetime.now().astimezone().isoformat(
            timespec="milliseconds"),
        "provider": "sherpa-onnx",
        "provider_version": getattr(sherpa_onnx, "__version__", "unknown"),
        "audio_file": audio_name,
        "sample_rate": engine.sample_rate,
        "requested_speakers": checked_speakers,
        "speaker_count_mode": "auto" if checked_speakers == 0 else "exact",
        "detected_speakers": int(result.num_speakers),
        "segmentation_model": SEGMENTATION_MODEL.name,
        "embedding_backend": embedding_key,
        "embedding_model": embedding_path.name,
        "segments": segments,
    }
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    os.replace(temporary, output)
    print(f"Готово: {output} ({len(segments)} отрезков, "
          f"{result.num_speakers} спикеров)", flush=True)
    return output


def _speaker_for(start_ms: int, end_ms: int, segments: list[dict]) -> str:
    overlaps = []
    midpoint = (start_ms + end_ms) / 2
    for item in segments:
        left = int(item["start_ms"])
        right = int(item["end_ms"])
        overlap = max(0, min(end_ms, right) - max(start_ms, left))
        distance = 0 if left <= midpoint <= right else min(
            abs(midpoint - left), abs(midpoint - right))
        overlaps.append((overlap, -distance, str(item["speaker_id"])))
    return max(overlaps)[2] if overlaps else "SPEAKER_UNKNOWN"


def _diarization_path(session: Path, name: str) -> Path:
    if (Path(name).name != name
            or not re.fullmatch(r"diarization(?:-[a-z0-9_-]+)?\.json",
                                name, re.IGNORECASE)):
        raise ValueError("недопустимое имя результата диаризации")
    return session / name


def _diarization_segments(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("в diarization.json нет сегментов")
    return segments


def _word_groups(event: dict, segments: list[dict]) -> list[list]:
    words = event.get("words") if isinstance(event.get("words"), list) else []
    groups: list[list] = []
    for word in words:
        speaker = _speaker_for(
            int(word["start_ms"]), int(word["end_ms"]), segments)
        if groups and groups[-1][0] == speaker:
            groups[-1][1].append(word)
        else:
            groups.append([speaker, [word]])
    if not groups:
        groups.append([_speaker_for(
            int(event["start_ms"]), int(event["end_ms"]), segments), []])
    return groups


def _derived_item(event: dict, speaker: str, words: list[dict]) -> dict:
    start_ms = int(words[0]["start_ms"]) if words else int(event["start_ms"])
    end_ms = int(words[-1]["end_ms"]) if words else int(event["end_ms"])
    text = (" ".join(str(word["text"]) for word in words)
            if words else str(event.get("text") or ""))
    return {
        "text": text, "start_ms": start_ms, "end_ms": end_ms,
        "speaker_id": speaker,
        "source": str(event.get("source") or "microphone"),
        "audio_file": event.get("audio_file"),
        "confidence": event.get("confidence"),
        "provider": event.get("provider", "local_whisper"),
        "words": words,
    }


def _derived_utterances(records: list[dict], segments: list[dict]) -> list[dict]:
    derived = []
    for event in records[1:]:
        if event.get("record_type") != "utterance":
            continue
        derived.extend(_derived_item(event, speaker, words)
                       for speaker, words in _word_groups(event, segments))
    return derived


def _can_coalesce(previous: dict | None, item: dict) -> bool:
    return bool(previous and previous["speaker_id"] == item["speaker_id"]
                and previous["source"] == item["source"]
                and item["start_ms"] - previous["end_ms"] <= 800)


def _merge_derived(previous: dict, item: dict) -> None:
    previous["text"] = f"{previous['text']} {item['text']}".strip()
    previous["end_ms"] = max(previous["end_ms"], item["end_ms"])
    previous["words"].extend(item["words"])
    confidences = [value for value in (
        previous.get("confidence"), item.get("confidence"))
        if isinstance(value, (int, float))]
    previous["confidence"] = (
        sum(confidences) / len(confidences) if confidences else None)


def _coalesce_utterances(derived: list[dict]) -> list[dict]:
    result = []
    for item in derived:
        previous = result[-1] if result else None
        if _can_coalesce(previous, item):
            _merge_derived(previous, item)
        else:
            result.append(item)
    return result


def _create_diarized_journal(path: Path, header: dict) -> None:
    transcript_events.create_journal(
        path, title=str(header.get("title") or "встреча"),
        provider=f"{header.get('provider', 'local_whisper')}+sherpa-onnx",
        segment=int(header.get("segment", 1)),
        audio_files=dict(header.get("audio_files") or {}),
        started_at=str(header["started_at"]))


def _append_diarized(path: Path, item: dict) -> None:
    transcript_events.append_event(
        path, REMOTE_ROLE, item["text"],
        provider=f"{item['provider']}+sherpa-onnx",
        metadata={
            "start_ms": item["start_ms"], "end_ms": item["end_ms"],
            "source": item["source"], "speaker_id": item["speaker_id"],
            "audio_file": item["audio_file"],
            "confidence": item["confidence"],
            "timing_source": "offline_word_alignment+diarization",
            "words": item["words"],
        })


def merge_transcript(session: Path, *,
                     transcript_name: str = "transcript.local.jsonl",
                     diarization_name: str = DIARIZATION_FILE,
                     output_name: str = DIARIZED_TRANSCRIPT_FILE) -> Path:
    """Разбить STT-реплики при смене speaker cluster на границе слова."""
    session = Path(session).resolve()
    transcript = _direct_file(session, transcript_name, _TRANSCRIPT_NAME)
    output = _direct_file(session, output_name, _TRANSCRIPT_NAME)
    diarization_path = _diarization_path(session, diarization_name)
    if output.exists():
        raise FileExistsError(f"результат уже существует: {output}")
    records = transcript_events.read_records(transcript)
    segments = _diarization_segments(diarization_path)
    temporary = session / f"{output_name}.tmp"
    temporary.unlink(missing_ok=True)
    _create_diarized_journal(temporary, records[0])
    try:
        derived = _derived_utterances(records, segments)
        for item in _coalesce_utterances(derived):
            _append_diarized(temporary, item)
        os.replace(temporary, output)
        return output
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _speaker_ids(session: Path, transcript_name: str) -> list[str]:
    transcript = _direct_file(session, transcript_name, _TRANSCRIPT_NAME)
    records = transcript_events.read_records(transcript)
    return sorted({str(item.get("speaker_id") or "") for item in records[1:]
                   if _SPEAKER_ID.fullmatch(str(item.get("speaker_id") or ""))})


def _clean_name(value: object) -> str:
    name = " ".join(str(value or "").split()).strip()
    if (len(name) > 80 or any(ord(char) < 32 for char in name)
            or any(char in "[]<>" for char in name)):
        raise ValueError(
            "имя должно содержать до 80 печатных символов без скобок")
    return name


def _speaker_boundaries(session: Path, transcript_name: str) -> set[tuple[str, int]]:
    records = transcript_events.read_records(
        _direct_file(session, transcript_name, _TRANSCRIPT_NAME))
    return {
        (str(item.get("speaker_id") or ""), int(item.get("start_ms", 0)))
        for item in records[1:] if item.get("record_type") == "utterance"
    }


def _speaker_split(item: object, base_ids: list[str], split_ids: set[str],
                   boundaries: set[tuple[str, int]]) -> dict:
    if not isinstance(item, dict):
        raise ValueError("правило разделения должно быть объектом")
    source = str(item.get("source") or "")
    target = str(item.get("speaker_id") or "")
    try:
        start_ms = int(item.get("start_ms"))
    except (TypeError, ValueError):
        raise ValueError("у разделения отсутствует корректное время") from None
    if source not in base_ids:
        raise ValueError(f"нельзя разделить отсутствующий кластер {source}")
    if not _SPEAKER_ID.fullmatch(target) or "_SPLIT_" not in target:
        raise ValueError(f"недопустимый идентификатор разделения: {target}")
    if target in base_ids or target in split_ids:
        raise ValueError(f"идентификатор разделения повторяется: {target}")
    if (source, start_ms) not in boundaries:
        raise ValueError("разделение должно начинаться с существующей реплики")
    return {"source": source, "start_ms": start_ms, "speaker_id": target}


def _speaker_splits(payload: object, base_ids: list[str],
                    boundaries: set[tuple[str, int]]) -> list[dict]:
    raw = payload.get("splits", []) if isinstance(payload, dict) else []
    if not isinstance(raw, list) or len(raw) > 100:
        raise ValueError("splits должен быть списком не более 100 правил")
    result = []
    split_ids: set[str] = set()
    for item in raw:
        split = _speaker_split(item, base_ids, split_ids, boundaries)
        split_ids.add(split["speaker_id"])
        result.append(split)
    return sorted(result, key=lambda item: (item["source"], item["start_ms"]))


def _speaker_setting(speaker_id: str, item: object,
                     speaker_ids: list[str]) -> dict:
    if not isinstance(item, dict):
        raise ValueError(f"настройка {speaker_id} должна быть объектом")
    role = str(item.get("role") or REMOTE_ROLE)
    if role not in _MAP_ROLES:
        raise ValueError(f"неизвестная роль для {speaker_id}: {role}")
    merge_into = str(item.get("merge_into") or speaker_id)
    if merge_into not in speaker_ids:
        raise ValueError(
            f"{speaker_id} нельзя объединить с отсутствующим {merge_into}")
    return {"name": _clean_name(item.get("name")), "role": role,
            "merge_into": merge_into}


def _speaker_settings(payload: object, speaker_ids: list[str]) -> dict[str, dict]:
    raw = payload.get("speakers") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        raise ValueError("ожидается объект speakers")
    unknown = set(map(str, raw)) - set(speaker_ids)
    if unknown:
        raise ValueError(f"неизвестные кластеры: {', '.join(sorted(unknown))}")
    return {speaker_id: _speaker_setting(
        speaker_id, raw.get(speaker_id, {}), speaker_ids)
            for speaker_id in speaker_ids}


def _speaker_root(speakers: dict[str, dict], start: str) -> str:
    seen = set()
    current = start
    while speakers[current]["merge_into"] != current:
        if current in seen:
            raise ValueError("объединения кластеров образуют цикл")
        seen.add(current)
        current = speakers[current]["merge_into"]
    return current


def normalize_speaker_map(session: Path, payload: object, *,
                          transcript_name: str =
                          DIARIZED_TRANSCRIPT_FILE) -> dict:
    """Проверить карту имён и объединений только для найденных кластеров."""
    session = Path(session).resolve()
    base_speaker_ids = _speaker_ids(session, transcript_name)
    if not base_speaker_ids:
        raise ValueError("в транскрипте нет анонимных кластеров SPEAKER_NN")
    splits = _speaker_splits(
        payload, base_speaker_ids,
        _speaker_boundaries(session, transcript_name))
    speaker_ids = sorted([*base_speaker_ids,
                          *(item["speaker_id"] for item in splits)])
    speakers = _speaker_settings(payload, speaker_ids)
    for speaker_id in speaker_ids:
        _speaker_root(speakers, speaker_id)
    roots = {_speaker_root(speakers, speaker_id) for speaker_id in speaker_ids}
    return {
        "schema_version": 2,
        "updated_at": dt.datetime.now().astimezone().isoformat(
            timespec="milliseconds"),
        "transcript": transcript_name,
        "reviewed": all(bool(speakers[speaker_id]["name"])
                        for speaker_id in roots),
        "speakers": speakers,
        "splits": splits,
    }


def load_speaker_map(session: Path, *,
                     transcript_name: str =
                     DIARIZED_TRANSCRIPT_FILE) -> dict:
    """Прочитать сохранённую карту или вернуть безопасные значения по умолчанию."""
    session = Path(session).resolve()
    path = session / "speaker-map.json"
    if path.is_file():
        value = json.loads(path.read_text(encoding="utf-8"))
        return normalize_speaker_map(
            session, value, transcript_name=transcript_name)
    defaults = {speaker_id: {} for speaker_id in _speaker_ids(
        session, transcript_name)}
    return normalize_speaker_map(
        session, {"speakers": defaults}, transcript_name=transcript_name)


def save_speaker_map(session: Path, payload: object, *,
                     transcript_name: str =
                     DIARIZED_TRANSCRIPT_FILE) -> dict:
    """Атомарно сохранить пользовательскую атрибуцию голосовых кластеров."""
    session = Path(session).resolve()
    normalized = normalize_speaker_map(
        session, payload, transcript_name=transcript_name)
    path = session / "speaker-map.json"
    temporary = session / "speaker-map.json.tmp"
    temporary.write_text(json.dumps(normalized, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    os.replace(temporary, path)
    return normalized


def add_speaker_split(session: Path, speaker_id: str, start_ms: int, *,
                      transcript_name: str =
                      DIARIZED_TRANSCRIPT_FILE) -> dict:
    """Создать новый ручной голос с указанной реплики, не меняя исходник."""
    session = Path(session).resolve()
    speaker_id = str(speaker_id)
    if speaker_id not in _speaker_ids(session, transcript_name):
        raise ValueError(f"неизвестный исходный кластер: {speaker_id}")
    start_ms = int(start_ms)
    mapping = load_speaker_map(session, transcript_name=transcript_name)
    for split in mapping.get("splits", []):
        if split["source"] == speaker_id and split["start_ms"] == start_ms:
            return mapping
    used = set(mapping["speakers"])
    index = 1
    while True:
        target = f"{speaker_id}_SPLIT_{index:02d}"
        if target not in used:
            break
        index += 1
    speakers = dict(mapping["speakers"])
    source = speakers[speaker_id]
    speakers[target] = {
        "name": "", "role": source["role"], "merge_into": target}
    splits = [*mapping.get("splits", []), {
        "source": speaker_id, "start_ms": start_ms, "speaker_id": target}]
    return save_speaker_map(
        session, {"speakers": speakers, "splits": splits},
        transcript_name=transcript_name)


def _resolved_speaker(speaker_id: str, speakers: dict) -> str:
    current = speaker_id
    for _unused in range(len(speakers) + 1):
        target = str(speakers[current]["merge_into"])
        if target == current:
            return current
        current = target
    raise ValueError("объединения кластеров образуют цикл")


def _split_speaker(speaker_id: str, start_ms: int, splits: list[dict]) -> str:
    candidates = [item for item in splits
                  if item["source"] == speaker_id
                  and int(item["start_ms"]) <= int(start_ms)]
    if not candidates:
        return speaker_id
    return str(max(candidates, key=lambda item: int(item["start_ms"]))[
        "speaker_id"])


def _render_refined_markdown(journal: Path, output: Path) -> None:
    records = transcript_events.read_records(journal)
    header = records[0]
    started = dt.datetime.fromisoformat(str(header["started_at"]))
    lines = [f"# Транскрипт: {header.get('title') or 'встреча'} — "
             f"{started:%Y-%m-%d %H:%M}", ""]
    for item in records[1:]:
        if (item.get("record_type") != "utterance"
                or item.get("status", "final") != "final"):
            continue
        captured = dt.datetime.fromisoformat(str(item["captured_at"]))
        role = str(item.get("speaker_role") or REMOTE_ROLE)
        name = str(item.get("speaker_name") or "").strip()
        label = f"{role} · {name}" if name else (
            f"{role} · {item.get('speaker_id') or 'неизвестный'}")
        text = " ".join(str(item.get("text") or "").split())
        lines.append(f"- {captured:%H:%M:%S} **[{label}]** {text}")
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    os.replace(temporary, output)


def apply_speaker_map(session: Path, *,
                      transcript_name: str =
                      DIARIZED_TRANSCRIPT_FILE) -> tuple[Path, Path]:
    """Пересобрать refined JSONL/Markdown без изменения исходного результата."""
    session = Path(session).resolve()
    source = _direct_file(session, transcript_name, _TRANSCRIPT_NAME)
    records = transcript_events.read_records(source)
    mapping = load_speaker_map(session, transcript_name=transcript_name)
    speakers = mapping["speakers"]
    splits = mapping.get("splits", [])
    output = session / "transcript.refined.jsonl"
    markdown = session / "transcript.refined.md"
    temporary = session / "transcript.refined.jsonl.tmp"
    temporary.unlink(missing_ok=True)
    header = records[0]
    transcript_events.create_journal(
        temporary, title=str(header.get("title") or "встреча"),
        provider=f"{header.get('provider', 'offline')}+manual-speaker-map",
        segment=int(header.get("segment", 1)),
        audio_files=dict(header.get("audio_files") or {}),
        started_at=str(header["started_at"]))
    try:
        for item in records[1:]:
            if item.get("record_type") != "utterance":
                continue
            speaker_id = str(item.get("speaker_id") or "")
            effective_id = _split_speaker(
                speaker_id, int(item.get("start_ms", 0)), splits)
            if effective_id not in speakers:
                continue
            target_id = _resolved_speaker(effective_id, speakers)
            target = speakers[target_id]
            transcript_events.append_event(
                temporary, target["role"], str(item.get("text") or ""),
                provider=f"{item.get('provider', 'offline')}+manual-speaker-map",
                metadata={
                    "start_ms": item.get("start_ms"),
                    "end_ms": item.get("end_ms"),
                    "source": item.get("source"),
                    "speaker_id": target_id,
                    "speaker_name": target["name"],
                    "audio_file": item.get("audio_file"),
                    "confidence": item.get("confidence"),
                    "status": item.get("status", "final"),
                    "timing_source": "offline_word_alignment+diarization+manual_map",
                    "words": item.get("words"),
                })
        os.replace(temporary, output)
        _render_refined_markdown(output, markdown)
        return output, markdown
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("install-models",
                   help="скачать локальные ONNX-модели с проверкой SHA-256")
    run = sub.add_parser("run", help="получить diarization.json из WAV")
    run.add_argument("session", type=Path)
    run.add_argument("--audio", default="audio-me.wav")
    run.add_argument("--output", default=DIARIZATION_FILE)
    run.add_argument("--speakers", type=int, default=2,
                     help="ожидаемое число голосов; 0 — авто (экспериментально)")
    run.add_argument("--threshold", type=float, default=0.5)
    run.add_argument("--embedding", choices=sorted(DIARIZATION_EMBEDDINGS),
                     default=DEFAULT_DIARIZATION_EMBEDDING)
    merge = sub.add_parser("merge", help="перенести кластеры в локальный JSONL")
    merge.add_argument("session", type=Path)
    merge.add_argument("--transcript", default="transcript.local.jsonl")
    merge.add_argument("--diarization", default=DIARIZATION_FILE)
    merge.add_argument("--output", default=DIARIZED_TRANSCRIPT_FILE)
    apply_map = sub.add_parser(
        "apply-map", help="пересобрать refined-транскрипт из speaker-map.json")
    apply_map.add_argument("session", type=Path)
    apply_map.add_argument(
        "--transcript", default=DIARIZED_TRANSCRIPT_FILE)
    args = parser.parse_args()
    if args.command == "install-models":
        install_models()
    elif args.command == "run":
        diarize(args.session, audio_name=args.audio, output_name=args.output,
                speakers=args.speakers, threshold=args.threshold,
                embedding_model=args.embedding)
    elif args.command == "merge":
        output = merge_transcript(
            args.session, transcript_name=args.transcript,
            diarization_name=args.diarization, output_name=args.output)
        print(f"Транскрипт с кластерами: {output}")
        page, entries = evidence.build(
            args.session, journal_name=output.name,
            output_name="evidence.diarized.html")
        if page:
            print(f"Проверка кластеров: {page} ({len(entries)} реплик)")
    else:
        journal, markdown = apply_speaker_map(
            args.session, transcript_name=args.transcript)
        print(f"Refined-транскрипт: {journal}")
        print(f"Для отчёта: {markdown}")


if __name__ == "__main__":
    main()
