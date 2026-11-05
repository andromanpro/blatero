"""Запись mono PCM в WAV по timestamp шкалы встречи.

WASAPI loopback не отдаёт чанки во время тишины, а callback устройства может
задержаться из-за нагрузки. Поэтому wall-clock тикер здесь недопустим: он успеет
записать тишину, после чего запоздавший реальный чанк удлинит дорожку. Каждый
чанк размещается в позиции ``start_ms``; разрыв заполняется тишиной, а уже
занятое пересечение отбрасывается. При закрытии обе дорожки дополняются до общей
границы встречи.
"""
import queue
import os
import threading
import time
import wave
from pathlib import Path

from pcm_resampler import PCM16ResampleState, resample_pcm16_mono


_STOP = object()
MAX_QUEUE_CHUNKS = 600
DEFAULT_CLOSE_TIMEOUT_SECONDS = 15.0


class ChannelRecorder:
    def __init__(self, path: Path, rate: int | None = None, *,
                 max_queue_chunks: int = MAX_QUEUE_CHUNKS,
                 close_timeout_seconds: float = DEFAULT_CLOSE_TIMEOUT_SECONDS):
        self.path = path
        self._q: queue.Queue = queue.Queue(maxsize=max(1, int(max_queue_chunks)))
        self._wav = None
        self._file = None
        self._rate = None
        self._written = 0
        self._submitted_end = 0
        self._thread = None
        self._feed_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._source_rate = None
        self._resample_state: PCM16ResampleState | None = None
        self._closed = False
        self._accepting = True
        self._stop_enqueued = False
        self._discard_queued = False
        self._fatal = False
        self._close_timeout_seconds = max(0.05, float(close_timeout_seconds))
        self.write_error = ""
        if rate:
            self._open(rate)

    def feed(self, data: bytes, rate: int, start_ms: int | None = None,
             end_ms: int | None = None, *, sequential: bool = False) -> None:
        if not data or not self._accepting:
            return
        with self._feed_lock:
            if not self._accepting:
                return
            if self._wav is None:
                self._open(rate)
            if rate != self._rate:
                # Горячая смена устройства часто меняет 44.1/48 кГц. Приводим
                # поток к уже зафиксированной частоте WAV, сохраняя timestamp.
                if self._source_rate != rate:
                    self._source_rate = rate
                    self._resample_state = None
                data, self._resample_state = resample_pcm16_mono(
                    data, rate, self._rate, self._resample_state)
            else:
                self._source_rate = rate
                self._resample_state = None

            frames = len(data) // 2
            if start_ms is None and end_ms is not None:
                duration_ms = round(frames / max(1, self._rate) * 1000)
                start_ms = max(0, int(end_ms) - duration_ms)
            if start_ms is None:
                start_frame = self._submitted_end
            else:
                start_frame = max(0, round(float(start_ms) * self._rate / 1000))
            if sequential:
                # The capture stream supplies unique PCM, never redeliveries.
                # Millisecond rounding/device changes must not discard samples.
                start_frame = max(start_frame, self._submitted_end)
            try:
                self._q.put_nowait((start_frame, data))
            except queue.Full:
                self._fatal = True
                self._accepting = False
                self.write_error = (
                    "RecorderBackpressure: диск не успевает сохранять WAV; "
                    "очередь записи переполнена")
            else:
                self._submitted_end = max(
                    self._submitted_end, start_frame + frames)

    def _open(self, rate: int) -> None:
        # Exclusive creation also protects against a collision after segment
        # selection. wave.open(path, 'wb') would silently truncate an old take.
        output = self.path.open("xb")
        self._rate = rate
        try:
            self._wav = wave.open(output, "wb")
            self._wav.setnchannels(1)
            self._wav.setsampwidth(2)
            self._wav.setframerate(rate)
        except Exception:
            output.close()
            raise
        self._file = output
        self._thread = threading.Thread(
            target=self._writer_loop, daemon=True, name=f"rec-{self.path.stem}")
        self._thread.start()

    def _writer_loop(self) -> None:
        while True:
            item = self._q.get()
            if item is _STOP:
                return
            if self._discard_queued:
                continue
            start_frame, data = item
            try:
                self._place(start_frame, data)
            except Exception as exc:
                # Продолжаем освобождать очередь, чтобы ошибка диска не съела RAM.
                self._fatal = True
                self._accepting = False
                self._discard_queued = True
                self.write_error = f"{type(exc).__name__}: {exc}"[:300]

    def _place(self, start_frame: int, data: bytes) -> None:
        if start_frame > self._written:
            self._write_silence(start_frame - self._written)
        elif start_frame < self._written:
            overlap = self._written - start_frame
            frames = len(data) // 2
            if overlap >= frames:
                return
            data = data[overlap * 2:]
        self._write(data)

    def _write_silence(self, frames: int) -> None:
        # Не выделять многомегабайтный bytes при долгой тишине loopback.
        block_frames = max(1, min(self._rate, frames))
        block = b"\x00\x00" * block_frames
        remaining = frames
        while remaining:
            current = min(block_frames, remaining)
            self._write(block[:current * 2])
            remaining -= current

    def _write(self, data: bytes) -> None:
        if not data:
            return
        self._wav.writeframesraw(data)
        self._written += len(data) // 2

    def close(self, end_ms: int | None = None) -> None:
        if not self._close_lock.acquire(timeout=self._close_timeout_seconds):
            raise TimeoutError("RecorderCloseTimeout: остановка WAV уже выполняется")
        try:
            self._finish_close(end_ms)
        finally:
            self._close_lock.release()

    def _finish_close(self, end_ms: int | None) -> None:
        if self._closed:
            return
        deadline = time.monotonic() + self._close_timeout_seconds
        if not self._feed_lock.acquire(timeout=self._close_timeout_seconds):
            self._fatal = True
            self._accepting = False
            self.write_error = "RecorderCloseTimeout: подача PCM не завершилась"
            raise TimeoutError(self.write_error)
        try:
            self._accepting = False
            if self._thread and not self._stop_enqueued:
                try:
                    self._q.put(_STOP, timeout=max(0.0, deadline - time.monotonic()))
                    self._stop_enqueued = True
                except queue.Full:
                    self._fatal = True
                    self.write_error = (
                        "RecorderCloseTimeout: очередь WAV не освободилась при остановке")
                    raise TimeoutError(self.write_error)
        finally:
            self._feed_lock.release()
        if self._thread:
            self._thread.join(timeout=max(0.0, deadline - time.monotonic()))
            if self._thread.is_alive():
                self._fatal = True
                self.write_error = (
                    "RecorderCloseTimeout: WAV не завершён за отведённое время")
                raise TimeoutError(self.write_error)
        if self._wav:
            if end_ms is not None and not self.write_error:
                target = max(0, round(int(end_ms) * self._rate / 1000))
                if target > self._written:
                    try:
                        self._write_silence(target - self._written)
                    except Exception as exc:
                        self.write_error = f"{type(exc).__name__}: {exc}"[:300]
            try:
                self._wav.close()
            except Exception as exc:
                if not self.write_error:
                    self.write_error = f"{type(exc).__name__}: {exc}"[:300]
            try:
                if self._file:
                    self._file.flush()
                    os.fsync(self._file.fileno())
            except Exception as exc:
                self._fatal = True
                self.write_error = self.write_error or f"{type(exc).__name__}: {exc}"[:300]
            finally:
                if self._file:
                    try:
                        self._file.close()
                    except Exception as exc:
                        self.write_error = self.write_error or f"{type(exc).__name__}: {exc}"[:300]
        if self.write_error:
            self._fatal = True
        self._closed = True

    @property
    def seconds(self) -> float:
        frames = max(self._written, self._submitted_end)
        return frames / self._rate if self._rate else 0.0

    @property
    def backlog_ms(self) -> int:
        if not self._rate:
            return 0
        frames = max(0, self._submitted_end - self._written)
        return round(frames * 1000 / self._rate)

    @property
    def fatal(self) -> bool:
        return self._fatal
