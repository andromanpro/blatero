"""Локальный профиль голоса и клиент изолированного Chatterbox worker."""
from __future__ import annotations

import array
import difflib
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
import wave
from pathlib import Path

import app_paths

BASE = app_paths.APP_ROOT
PROFILE_DIR = app_paths.DATA_ROOT / ".voice-profile"
SAMPLE_PATH = PROFILE_DIR / "my-voice.wav"
CONDITIONED_SAMPLE_PATH = PROFILE_DIR / "my-voice-conditioned.wav"
CACHE_DIR = PROFILE_DIR / "audio-cache"
MODEL_CACHE = PROFILE_DIR / "model-cache"
TTS_PYTHON = BASE / ".venv-tts" / "Scripts" / "python.exe"
WORKER = BASE / "chatterbox_worker.py"
INSTALL_MARKER = BASE / ".venv-tts" / ".blatero-chatterbox-ready"
WORKER_LOG = PROFILE_DIR / "chatterbox-worker.log"
QUALITY_FILE = PROFILE_DIR / "quality.json"
MODEL_MARKER = "multilingual-v3@65b1843-ru-stable1"
CONDITIONING_MARKER = "trim-12s-24khz-peak085-v1"
_VALIDATION_MODEL = None
_VALIDATION_LOCK = threading.Lock()


def _wav_info(path: Path) -> tuple[float, int]:
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / max(1, audio.getframerate()), audio.getframerate()


def _condition_reference(source: Path = SAMPLE_PATH,
                         target: Path = CONDITIONED_SAMPLE_PATH) -> Path:
    """Подготовить чистый 24 кГц эталон для чувствительного voice encoder."""
    import numpy as np

    with wave.open(str(source), "rb") as audio:
        channels = audio.getnchannels()
        width = audio.getsampwidth()
        rate = audio.getframerate()
        raw = audio.readframes(audio.getnframes())
    if width != 2 or rate < 8000 or not raw:
        raise RuntimeError("образец должен быть непустым PCM16 WAV")
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if channels > 1:
        samples = samples[:len(samples) - len(samples) % channels]
        samples = samples.reshape(-1, channels).mean(axis=1)
    samples /= 32768.0

    frame = max(1, rate // 50)  # 20 мс
    usable = samples[:len(samples) - len(samples) % frame]
    if not len(usable):
        raise RuntimeError("образец слишком короткий")
    levels = np.sqrt(np.mean(usable.reshape(-1, frame) ** 2, axis=1))
    threshold = max(0.004, min(0.02, float(np.percentile(levels, 70)) * 0.35))
    active = np.flatnonzero(levels >= threshold)
    if not len(active):
        raise RuntimeError("в образце не найдена речь")
    margin = rate // 10
    start = max(0, int(active[0]) * frame - margin)
    end = min(len(samples), (int(active[-1]) + 1) * frame + margin)
    samples = samples[start:min(end, start + rate * 12)]
    if len(samples) < rate * 3:
        raise RuntimeError("для клонирования нужно хотя бы 3 секунды речи")

    if rate != 24000:
        duration = len(samples) / rate
        old_axis = np.linspace(0.0, duration, num=len(samples), endpoint=False)
        new_count = max(1, round(duration * 24000))
        new_axis = np.linspace(0.0, duration, num=new_count, endpoint=False)
        samples = np.interp(new_axis, old_axis, samples).astype(np.float32)
    samples -= float(np.mean(samples))
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(samples ** 2)))
    if peak < 0.01 or rms < 0.002:
        raise RuntimeError("образец записан слишком тихо")
    gain = min(10.0, 0.85 / peak, 0.1 / rms)
    pcm = np.clip(samples * gain, -1.0, 1.0)
    pcm = (pcm * 32767).astype(np.int16)

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".wav.tmp")
    try:
        with wave.open(str(tmp), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(24000)
            audio.writeframes(pcm.tobytes())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return target


def conditioned_reference() -> Path:
    if (not CONDITIONED_SAMPLE_PATH.is_file()
            or CONDITIONED_SAMPLE_PATH.stat().st_mtime_ns
            < SAMPLE_PATH.stat().st_mtime_ns):
        _condition_reference()
    return CONDITIONED_SAMPLE_PATH


def status() -> dict:
    sample = SAMPLE_PATH.is_file()
    seconds = 0.0
    sample_rate = 0
    if sample:
        try:
            seconds, sample_rate = _wav_info(SAMPLE_PATH)
        except (OSError, wave.Error):
            sample = False
    installed = TTS_PYTHON.is_file() and INSTALL_MARKER.is_file()
    quality = "unverified"
    quality_message = "локальный голос ещё не прошёл проверку речи"
    if sample:
        try:
            saved = json.loads(QUALITY_FILE.read_text(encoding="utf-8"))
            stat = SAMPLE_PATH.stat()
            if (saved.get("model") == MODEL_MARKER
                    and saved.get("sample_mtime_ns") == stat.st_mtime_ns):
                quality = str(saved.get("status", "unverified"))
                quality_message = str(saved.get("message", quality_message))
        except (OSError, ValueError):
            pass
    return {
        "installed": installed,
        "sample": sample,
        "seconds": round(seconds, 1),
        "sample_rate": sample_rate,
        "ready": bool(installed and sample and quality != "failed"),
        "engine": "Chatterbox Multilingual V3 · CPU",
        "quality": quality,
        "quality_message": quality_message,
    }


def _save_quality(state: str, message: str) -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    stat = SAMPLE_PATH.stat()
    payload = {"status": state, "message": message, "model": MODEL_MARKER,
               "sample_mtime_ns": stat.st_mtime_ns, "checked_at": time.time()}
    tmp = QUALITY_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, QUALITY_FILE)


def _normalized_words(text: str) -> list[str]:
    return re.findall(r"[a-zа-яё0-9]+", str(text).casefold())


def _texts_match(expected: str, recognized: str) -> tuple[bool, float, float]:
    expected_words = _normalized_words(expected)
    recognized_words = _normalized_words(recognized)
    expected_norm = " ".join(expected_words)
    recognized_norm = " ".join(recognized_words)
    ratio = difflib.SequenceMatcher(None, expected_norm, recognized_norm).ratio()
    meaningful = {word for word in expected_words if len(word) >= 3}
    recognized_set = set(recognized_words)
    coverage = len(meaningful & recognized_set) / max(1, len(meaningful))
    cyrillic_expected = [word for word in expected_words
                         if re.search(r"[а-яё]", word)]
    cyrillic_recognized = [word for word in recognized_words
                           if re.search(r"[а-яё]", word)]
    language_ok = (len(cyrillic_expected) < 4
                   or len(cyrillic_recognized) >= max(2, len(cyrillic_expected) // 3))
    return bool(language_ok and (ratio >= 0.52 or coverage >= 0.45)), ratio, coverage


def _validate_generated(text: str, output: Path) -> tuple[bool, str]:
    seconds, _rate = _wav_info(output)
    # Быстрый предохранитель от ухода T3 к лимиту 1000 токенов.
    max_seconds = max(8.0, len(text.strip()) / 4.0 + 4.0)
    if seconds > max_seconds:
        return False, (f"аномальная длительность {seconds:.1f} с для короткого "
                       "текста — вероятна галлюцинация Chatterbox")
    global _VALIDATION_MODEL
    with _VALIDATION_LOCK:
        if _VALIDATION_MODEL is None:
            from local_whisper import get_model
            _VALIDATION_MODEL = get_model("base")
        segments, _info = _VALIDATION_MODEL.transcribe(
            str(output), language="ru", beam_size=3, vad_filter=True,
            condition_on_previous_text=False)
        recognized = " ".join(segment.text.strip() for segment in segments).strip()
    matches, ratio, coverage = _texts_match(text, recognized)
    if not matches:
        preview = recognized[:120] or "речь не распознана"
        return False, (f"проверка речи не совпала с текстом "
                       f"({ratio:.0%}/{coverage:.0%}): {preview}")
    return True, f"русская речь проверена локально ({ratio:.0%}/{coverage:.0%})"


def _record_mono_wav(selector: str, target: Path, seconds: int,
                     on_level=None) -> dict:
    """Атомарно записать локальный mono PCM16 WAV в явно заданный файл."""
    if seconds not in {15, 30, 60}:
        raise ValueError("длительность образца должна быть 15, 30 или 60 секунд")
    import pyaudiowpatch as pyaudio
    from live import resolve_mic

    mic_idx, mic_name = resolve_mic(selector)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    pa = pyaudio.PyAudio()
    stream = None
    frames: list[bytes] = []
    try:
        info = pa.get_device_info_by_index(mic_idx)
        channels = max(1, int(info["maxInputChannels"]))
        rate = int(info["defaultSampleRate"])
        chunk = max(1, int(rate * 0.1))
        stream = pa.open(format=pyaudio.paInt16, channels=channels, rate=rate,
                         input=True, input_device_index=mic_idx,
                         frames_per_buffer=chunk)
        deadline = time.monotonic() + seconds
        peak_seen = 0.0
        while time.monotonic() < deadline:
            data = stream.read(chunk, exception_on_overflow=False)
            samples = array.array("h", data)
            if channels > 1:
                mono = array.array("h", (
                    sum(samples[i:i + channels]) // channels
                    for i in range(0, len(samples) - channels + 1, channels)))
                data = mono.tobytes()
                samples = mono
            peak = max((abs(sample) for sample in samples), default=0) / 32768
            peak_seen = max(peak_seen, peak)
            frames.append(data)
            if on_level:
                on_level(min(1.0, peak * 2.5),
                         max(0.0, deadline - time.monotonic()))
        if peak_seen < 0.012:
            raise RuntimeError("в образце нет уверенного сигнала микрофона")
        with wave.open(str(tmp), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(rate)
            audio.writeframes(b"".join(frames))
        os.replace(tmp, target)
        duration, sample_rate = _wav_info(target)
        return {
            "path": str(target), "seconds": round(duration, 1),
            "sample_rate": sample_rate, "device": mic_name,
            "peak": round(peak_seen, 3),
        }
    finally:
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        pa.terminate()
        tmp.unlink(missing_ok=True)


def record_temporary_sample(selector: str, target: Path, seconds: int = 15,
                            on_level=None) -> dict:
    """Записать проверочный WAV без изменения профиля синтеза голоса."""
    return _record_mono_wav(selector, target, seconds, on_level)


def record_sample(selector: str, seconds: int = 30, on_level=None) -> dict:
    """Записать mono PCM16 WAV с выбранного микрофона, полностью локально."""
    captured = _record_mono_wav(selector, SAMPLE_PATH, seconds, on_level)
    QUALITY_FILE.unlink(missing_ok=True)
    _condition_reference()
    clear_cache()
    return {**status(), "device": captured["device"], "peak": captured["peak"]}


def clear_cache() -> int:
    stop_worker()
    if not CACHE_DIR.exists():
        return 0
    count = sum(1 for p in CACHE_DIR.glob("*.wav") if p.is_file())
    shutil.rmtree(CACHE_DIR)
    return count


def delete_profile() -> int:
    """Удалить эталон и синтезированные фразы; модели/venv оставить."""
    stop_worker()
    removed = int(SAMPLE_PATH.exists())
    SAMPLE_PATH.unlink(missing_ok=True)
    removed += int(CONDITIONED_SAMPLE_PATH.exists())
    CONDITIONED_SAMPLE_PATH.unlink(missing_ok=True)
    removed += int(QUALITY_FILE.exists())
    QUALITY_FILE.unlink(missing_ok=True)
    removed += clear_cache()
    return removed


class _WorkerClient:
    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.messages: queue.Queue[dict] = queue.Queue()
        self.lock = threading.Lock()
        self.reader: threading.Thread | None = None

    def _read_stdout(self) -> None:
        assert self.process and self.process.stdout
        for line in self.process.stdout:
            marker = "BLATERO_JSON "
            if marker not in line:
                continue
            try:
                self.messages.put(json.loads(line.split(marker, 1)[1]))
            except json.JSONDecodeError:
                continue

    def start(self, timeout: float = 300) -> None:
        if self.process and self.process.poll() is None:
            return
        current = status()
        if not current["installed"]:
            raise RuntimeError("Chatterbox ещё не установлен: запустите настройку движка")
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        MODEL_CACHE.mkdir(parents=True, exist_ok=True)
        log = WORKER_LOG.open("a", encoding="utf-8")
        env = os.environ.copy()
        env["HF_HOME"] = str(MODEL_CACHE)
        env["TOKENIZERS_PARALLELISM"] = "false"
        try:
            self.process = subprocess.Popen(
                [str(TTS_PYTHON), "-u", str(WORKER)], cwd=BASE,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        finally:
            log.close()
        self.messages = queue.Queue()
        self.reader = threading.Thread(target=self._read_stdout, daemon=True,
                                       name="chatterbox-output")
        self.reader.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"Chatterbox завершился при загрузке; см. {WORKER_LOG.name}")
            try:
                message = self.messages.get(timeout=min(1, deadline - time.monotonic()))
            except queue.Empty:
                continue
            if message.get("type") == "ready":
                return
        self.stop()
        raise TimeoutError("Chatterbox не загрузился за 5 минут")

    def generate(self, text: str, reference: Path, output: Path,
                 timeout: float = 300) -> None:
        with self.lock:
            self.start()
            assert self.process and self.process.stdin
            request_id = uuid.uuid4().hex
            request = {"id": request_id, "text": text,
                       "reference": str(reference), "output": str(output)}
            try:
                self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
                self.process.stdin.flush()
            except OSError as exc:
                self.stop()
                raise RuntimeError("локальный движок голоса остановился") from exc
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    message = self.messages.get(
                        timeout=min(1, deadline - time.monotonic()))
                except queue.Empty:
                    if self.process.poll() is not None:
                        raise RuntimeError(
                            f"Chatterbox завершился; см. {WORKER_LOG.name}")
                    continue
                if message.get("type") != "result" or message.get("id") != request_id:
                    continue
                if not message.get("ok"):
                    raise RuntimeError(message.get("error") or "ошибка Chatterbox")
                return
            self.stop()
            raise TimeoutError("Chatterbox ушёл в долгую генерацию и был остановлен")

    def stop(self) -> None:
        process, self.process = self.process, None
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                process.kill()


_WORKER = _WorkerClient()


def stop_worker() -> None:
    _WORKER.stop()


def _cache_key(text: str) -> str:
    stat = SAMPLE_PATH.stat()
    material = (f"{MODEL_MARKER}|{CONDITIONING_MARKER}|{stat.st_size}|"
                f"{stat.st_mtime_ns}|{text.strip()}")
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def cached_audio(text: str) -> bytes | None:
    """Вернуть подготовленный WAV без запуска модели."""
    text = str(text).strip()
    if not text or not SAMPLE_PATH.is_file():
        return None
    try:
        target = CACHE_DIR / f"{_cache_key(text)}.wav"
        if target.is_file() and target.stat().st_size > 44:
            return target.read_bytes()
    except OSError:
        pass
    return None


def synthesize(text: str) -> bytes:
    text = str(text).strip()
    if not text or len(text) > 4000:
        raise ValueError("текст для озвучивания должен содержать от 1 до 4000 символов")
    current = status()
    if not current["sample"]:
        raise RuntimeError("сначала запишите образец своего голоса")
    if not current["installed"]:
        raise RuntimeError("локальный движок Chatterbox ещё не установлен")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = CACHE_DIR / f"{_cache_key(text)}.wav"
    cached = cached_audio(text)
    if cached is not None:
        return cached
    tmp = target.with_suffix(f".{uuid.uuid4().hex}.tmp.wav")
    try:
        generation_timeout = min(300.0, max(90.0, len(text) * 2.5))
        _WORKER.generate(text, conditioned_reference(), tmp,
                         timeout=generation_timeout)
        if not tmp.is_file() or tmp.stat().st_size <= 44:
            raise RuntimeError("Chatterbox не создал аудиофайл")
        valid, message = _validate_generated(text, tmp)
        if not valid:
            _save_quality("failed", message)
            raise RuntimeError(f"локальный голос не прошёл проверку: {message}")
        _save_quality("passed", message)
        os.replace(tmp, target)
        return target.read_bytes()
    finally:
        tmp.unlink(missing_ok=True)


def cache_questions(questions: list[str], on_progress=None) -> dict:
    unique = list(dict.fromkeys(q.strip() for q in questions if q.strip()))
    completed = 0
    for index, text in enumerate(unique, 1):
        synthesize(text)
        completed = index
        if on_progress:
            on_progress(index, len(unique), text)
    return {"completed": completed, "total": len(unique)}
