"""Локальное распознавание двух WASAPI-каналов через faster-whisper.

Аудио обрабатывается в памяти текущего компьютера. При первом запуске библиотека
скачивает выбранную модель, после чего использует локальный кэш Hugging Face.
"""
from __future__ import annotations

import array
import gc
import os
from pathlib import Path
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np
import pyaudiowpatch as pyaudio

import app_paths
import runtime_diagnostics as diagnostics

CHUNK_MS = 100
SILENCE_CHUNKS = 8
MIN_UTTERANCE_SECONDS = 0.9
MAX_UTTERANCE_SECONDS = 6.0
VOICE_PEAK = 380
PREWARM_BUFFER_SECONDS = 180
BASE = app_paths.DATA_ROOT
MODEL_ROOT = BASE / ".models" / "whisper"

_models: dict[str, object] = {}
_model_load_lock = threading.Lock()
_inference_slots = threading.BoundedSemaphore(2)
_QUEUE_TIMEOUT = object()


def transcription_prompt(context: object = None) -> str | None:
    """Only vocabulary belongs in an ASR prompt; language is a separate option."""
    cleaned = " ".join(str(context or "").split())[:200]
    return cleaned or None


@dataclass
class _Utterance:
    pre_roll: deque[tuple[bytes, int, int]] = field(
        default_factory=lambda: deque(maxlen=3))
    audio: bytearray = field(default_factory=bytearray)
    speaking: bool = False
    silence: int = 0
    rate: int = 16000
    start_ms: int = 0
    end_ms: int = 0


def get_model(name: str, *, local_only: bool = False):
    with _model_load_lock:
        if name not in _models:
            from faster_whisper import WhisperModel
            print(f"Whisper: загружаю модель {name}…",
                  flush=True)
            MODEL_ROOT.mkdir(parents=True, exist_ok=True)
            _models[name] = WhisperModel(
                name, device="cpu", compute_type="int8",
                cpu_threads=max(1, min(8, (os.cpu_count() or 2) // 2)),
                num_workers=2,
                download_root=str(MODEL_ROOT), local_files_only=local_only)
            print(f"Whisper: модель {name} готова", flush=True)
        return _models[name]


def release_model(name: str) -> bool:
    """Освободить модель перед удалением её управляемого cache."""
    with _model_load_lock:
        removed = _models.pop(name, None) is not None
    if removed:
        gc.collect()
    return removed


class LocalWhisperRecognizer:
    """Совместимый со StreamingRecognizer интерфейс start/stop."""

    def __init__(self, device_index: int, label: str, on_segment, tap=None,
                 model_name: str = "small", on_timed_segment=None,
                 timeline_origin: float | None = None, audio_processor=None,
                 diagnostic_session: Path | None = None, recording_id: str = ""):
        self.device_index = device_index
        self.label = label
        self.on_segment = on_segment
        self.on_timed_segment = on_timed_segment
        self.tap = tap
        self.model_name = model_name
        self.timeline_origin = timeline_origin
        self.audio_processor = audio_processor
        self.diagnostic_session = diagnostic_session
        self.recording_id = recording_id
        # Модель грузится только после открытия capture. Пока идёт prewarm,
        # сырые чанки уже уходят в WAV и накапливаются для распознавания.
        self.model = None
        self.model_error = None
        self._model_ready = threading.Event()
        self._audio_q: queue.Queue[
            tuple[bytes, int, int, int] | None] = queue.Queue(
                maxsize=PREWARM_BUFFER_SECONDS * 1000 // CHUNK_MS)
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self.capture_error = None
        self.dropped_chunks = 0
        self.audio_chunk_ms = CHUNK_MS
        self.inflight_audio_ms = 0
        self.buffered_audio_ms = 0
        self.last_inference_ms = 0
        self.last_wait_ms = 0
        self.last_rtf = 0.0

    def _process_audio(self, data: bytes, rate: int, start_ms: int,
                       end_ms: int) -> bytes:
        """Apply an optional filter without allowing it to stop capture."""
        processor = self.audio_processor
        if processor is None:
            return data
        try:
            processed = processor(data, rate, start_ms, end_ms)
            if not isinstance(processed, (bytes, bytearray)):
                raise TypeError("фильтр вернул не PCM-буфер")
            if len(processed) != len(data):
                raise ValueError("фильтр изменил длину PCM-буфера")
            return bytes(processed)
        except Exception as exc:
            # Распознавание важнее фильтра: при любой ошибке продолжаем сырым
            # звуком и отключаем неисправный процессор до следующего запуска.
            self.audio_processor = None
            self.on_segment(
                "error", f"аудиофильтр отключён, используется исходный звук: {exc}")
            return data

    @staticmethod
    def _downmix(data: bytes, channels: int) -> bytes:
        samples = array.array("h", data)
        if channels == 2:
            return array.array("h", ((samples[i] + samples[i + 1]) // 2
                                      for i in range(0, len(samples), 2))).tobytes()
        if channels > 2:
            return array.array("h", samples[::channels]).tobytes()
        return data

    def _open_capture(self, audio):
        info = audio.get_device_info_by_index(self.device_index)
        channels = max(1, int(info["maxInputChannels"]))
        rate = int(info["defaultSampleRate"])
        frames = int(rate * CHUNK_MS / 1000)
        stream = audio.open(
            format=pyaudio.paInt16, channels=channels, rate=rate,
            input=True, input_device_index=self.device_index,
            frames_per_buffer=frames)
        return stream, channels, rate, frames

    def _queue_audio(self, item: tuple[bytes, int, int, int]) -> None:
        if getattr(self, "model_error", None):
            return
        try:
            self._audio_q.put_nowait(item)
            return
        except queue.Full:
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                pass
        self._audio_q.put_nowait(item)
        self.dropped_chunks += 1
        if self.dropped_chunks == 1 or self.dropped_chunks % 100 == 0:
            self.on_segment(
                "error", "локальный Whisper не успевает: потеряно "
                f"аудиоблоков — {self.dropped_chunks}")

    def _capture_chunk(self, stream, channels: int, rate: int,
                       frames: int) -> None:
        data = self._downmix(
            stream.read(frames, exception_on_overflow=False), channels)
        end_ms = max(0, round((time.monotonic() - self.timeline_origin) * 1000))
        duration_ms = round(len(data) / 2 / max(1, rate) * 1000)
        start_ms = max(0, end_ms - duration_ms)
        if self.tap:
            self.tap(data, rate, start_ms, end_ms)
        processed = self._process_audio(data, rate, start_ms, end_ms)
        self._queue_audio((processed, rate, start_ms, end_ms))

    @staticmethod
    def _close_capture(audio, stream) -> None:
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        audio.terminate()

    def _capture_loop(self):
        audio = pyaudio.PyAudio()
        stream = None
        try:
            stream, channels, rate, frames = self._open_capture(audio)
            self._capture_ready.set()
            while not self._stop.is_set():
                self._capture_chunk(stream, channels, rate, frames)
        except Exception as exc:
            self.capture_error = str(exc)
            if not self._stop.is_set():
                self.on_segment("capture_error", f"канал «{self.label}» оборван: {exc}")
        finally:
            self._close_capture(audio, stream)
            self._capture_ready.set()
            try:
                self._audio_q.put_nowait(None)
            except queue.Full:
                pass

    def _transcribe(self, pcm: bytes, rate: int, start_ms: int = 0,
                    end_ms: int | None = None):
        if not pcm:
            return
        if end_ms is None:
            end_ms = start_ms + round(len(pcm) / 2 / max(1, rate) * 1000)
        source = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        if rate != 16000 and len(source) > 1:
            target_length = max(1, round(len(source) * 16000 / rate))
            source = np.interp(
                np.linspace(0, len(source) - 1, target_length),
                np.arange(len(source)), source).astype(np.float32)
        samples = source / 32768.0
        self.inflight_audio_ms = round(len(pcm) / 2 / max(1,rate) * 1000)
        started = time.monotonic()
        wait_ms = 0
        result_chars = 0
        code = "ok"
        inference_ms = 0
        try:
            with _inference_slots:
                wait_ms = round((time.monotonic() - started) * 1000)
                inference_started = time.monotonic()
                segments, _info = self.model.transcribe(
                    samples, language="ru", task="transcribe", beam_size=1,
                    best_of=1, temperature=0,
                    vad_filter=True, condition_on_previous_text=False,
                    initial_prompt=transcription_prompt())
                recognized = list(segments)
                inference_ms = round((time.monotonic() - inference_started) * 1000)
                text = " ".join(
                    segment.text.strip() for segment in recognized).strip()
                result_chars = len(text)
            if text:
                speech_start = start_ms
                speech_end = end_ms
                if recognized:
                    starts = [float(getattr(segment, "start", 0.0))
                              for segment in recognized]
                    ends = [float(getattr(segment, "end",
                                          (end_ms - start_ms) / 1000))
                            for segment in recognized]
                    speech_start = min(end_ms, start_ms + round(min(starts) * 1000))
                    speech_end = start_ms + round(max(ends) * 1000)
                    speech_end = min(max(speech_start, speech_end), end_ms)
                metadata = {
                    "start_ms": speech_start,
                    "end_ms": speech_end,
                    "confidence": None,
                    "provider": "local_whisper",
                    "timing_source": "audio_chunk",
                }
                if getattr(self, "on_timed_segment", None):
                    self.on_timed_segment("refined", text, metadata)
                else:
                    self.on_segment("refined", text)
        except Exception as exc:
            code = diagnostics.error_code(exc)
            if not self._stop.is_set():
                self.on_segment("error", f"локальный Whisper: {exc}")
        finally:
            audio_ms = max(1, round(len(pcm) / 2 / max(1, rate) * 1000))
            self.inflight_audio_ms = 0
            self.last_wait_ms = wait_ms
            self.last_inference_ms = inference_ms
            self.last_rtf = inference_ms / audio_ms
            diagnostics.record(getattr(self, "diagnostic_session", None), "stt.inference",
                component="stt", provider="local_whisper", model=getattr(self,"model_name","unknown"),
                recording_id=getattr(self,"recording_id",""), role=getattr(self,"label",""),
                start_ms=start_ms, end_ms=end_ms, audio_ms=audio_ms, wait_ms=wait_ms,
                inference_ms=inference_ms, duration_ms=round((time.monotonic()-started)*1000),
                rtf=inference_ms/audio_ms, result_chars=result_chars, code=code, beam_size=1)

    def _next_audio(self):
        try:
            return self._audio_q.get(timeout=0.3)
        except queue.Empty:
            return None if self._stop.is_set() else _QUEUE_TIMEOUT

    @staticmethod
    def _begin_utterance(state: _Utterance) -> None:
        buffered = list(state.pre_roll)
        state.audio.extend(b"".join(part[0] for part in buffered))
        state.start_ms = buffered[0][1]
        state.end_ms = buffered[-1][2]
        state.pre_roll.clear()
        state.speaking = True
        state.silence = 0

    def _finish_utterance(self, state: _Utterance) -> None:
        self.buffered_audio_ms = 0
        self._transcribe(
            bytes(state.audio), state.rate, state.start_ms, state.end_ms)
        state.audio.clear()
        state.speaking = False
        state.silence = 0

    def _consume_audio(self, state: _Utterance,
                       item: tuple[bytes, int, int, int]) -> None:
        data, rate, chunk_start_ms, chunk_end_ms = item
        if state.rate != rate:
            if state.audio:
                self._finish_utterance(state)
            state.pre_roll.clear()
        state.rate = rate
        peak = max((abs(sample) for sample in array.array("h", data)), default=0)
        if not state.speaking:
            state.pre_roll.append((data, chunk_start_ms, chunk_end_ms))
            if peak >= VOICE_PEAK:
                self._begin_utterance(state)
            return
        state.audio.extend(data)
        self.buffered_audio_ms = round(len(state.audio) / 2 / max(1,state.rate)*1000)
        state.end_ms = chunk_end_ms
        state.silence = state.silence + 1 if peak < VOICE_PEAK else 0
        seconds = len(state.audio) / 2 / state.rate
        complete = ((state.silence >= SILENCE_CHUNKS
                     and seconds >= MIN_UTTERANCE_SECONDS)
                    or seconds >= MAX_UTTERANCE_SECONDS)
        if complete:
            self._finish_utterance(state)

    def _recognize_loop(self):
        state = _Utterance()
        while True:
            item = self._next_audio()
            if item is _QUEUE_TIMEOUT:
                continue
            if item is None:
                break
            self._consume_audio(state, item)
        if state.audio:
            self._finish_utterance(state)

    def _recognize_worker(self) -> None:
        try:
            self.model = get_model(self.model_name)
        except Exception as exc:
            self.model_error = str(exc)
            if not self._stop.is_set():
                self.on_segment(
                    "error", f"локальный Whisper не загрузился; WAV продолжается: {exc}")
            return
        finally:
            self._model_ready.set()
        self._recognize_loop()

    def start_capture(self) -> None:
        if self.timeline_origin is None:
            self.timeline_origin = time.monotonic()
        self._capture_ready = threading.Event()
        capture = threading.Thread(
            target=self._capture_loop, daemon=True, name=f"local-cap-{self.label}")
        capture.start()
        self._threads = [capture]
        if not self._capture_ready.wait(timeout=5):
            self._stop.set()
            raise RuntimeError(f"канал «{self.label}» не открылся за 5 секунд")
        if self.capture_error:
            self._stop.set()
            capture.join(timeout=1)
            raise RuntimeError(f"канал «{self.label}» не открылся: {self.capture_error}")

    def start_recognition(self) -> None:
        recognize = threading.Thread(
            target=self._recognize_worker, daemon=True, name=f"local-stt-{self.label}")
        recognize.start()
        self._threads.append(recognize)

    def start_external(self) -> None:
        """Recognition only; a persistent AudioCapture owns WASAPI and WAV."""
        self._threads = [None]
        self.start_recognition()

    def feed_audio(self, data: bytes, rate: int, start_ms: int, end_ms: int):
        if not self._stop.is_set():
            self._queue_audio((data, rate, start_ms, end_ms))

    def start(self):
        self.start_capture()
        self.start_recognition()

    def request_stop(self) -> None:
        self._stop.set()

    def wait_capture(self) -> None:
        if self._threads and self._threads[0] is not None:
            self._threads[0].join(timeout=5)

    def finish_recognition(self) -> None:
        # STT дочитывает очередь уже после освобождения обоих устройств. На
        # медленном CPU хвост важнее мгновенного завершения процесса.
        if len(self._threads) > 1:
            self._threads[1].join(timeout=40)
            if self._threads[1].is_alive():
                message = ("локальный Whisper не успел дописать хвост "
                           "за 40 секунд; требуется дораспознавание исходного WAV")
                self.on_segment("error", message)
                raise TimeoutError(message)

    def stop(self, wait: bool = False):
        self.request_stop()
        if wait:
            self.wait_capture()
            self.finish_recognition()
