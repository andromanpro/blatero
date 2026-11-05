"""Локальное подавление коррелирующего loopback-эха перед STT.

Это консервативный Windows fallback, а не замена полноценному WebRTC AEC3.
Исходный микрофонный WAV сохраняется до обработки; фильтр получает опорный
loopback, оценивает задержку и вычитает только хорошо коррелирующую составляющую.
"""
from __future__ import annotations

import argparse
import math
import os
import threading
import time
import wave
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np


INTERNAL_RATE = 16000
MIN_CORRELATION = 0.62
MIN_SIGNAL_RMS = 0.002


@dataclass
class _Frame:
    start_ms: int
    end_ms: int
    samples: np.ndarray


def _float_samples(pcm: bytes, rate: int) -> np.ndarray:
    source = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if not len(source) or rate == INTERNAL_RATE:
        return source
    target_length = max(1, round(len(source) * INTERNAL_RATE / max(1, rate)))
    return np.interp(
        np.linspace(0, len(source) - 1, target_length),
        np.arange(len(source)), source).astype(np.float32)


def _pcm_samples(samples: np.ndarray, length: int) -> bytes:
    if len(samples) != length and len(samples) > 1:
        samples = np.interp(
            np.linspace(0, len(samples) - 1, length),
            np.arange(len(samples)), samples).astype(np.float32)
    elif len(samples) == 1 and length != 1:
        samples = np.full(length, samples[0], dtype=np.float32)
    clipped = np.clip(np.rint(samples * 32768.0), -32768, 32767)
    return clipped.astype(np.int16).tobytes()


def _rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(samples, dtype=np.float64)))) \
        if len(samples) else 0.0


class AdaptiveEchoSuppressor:
    """Синхронизировать render/capture по timeline и подавлять уверенное эхо."""

    def __init__(self, *, max_delay_ms: int = 500,
                 min_correlation: float = MIN_CORRELATION):
        self.max_delay_ms = max(100, min(1000, int(max_delay_ms)))
        self.min_correlation = min(0.95, max(0.4, float(min_correlation)))
        self._render: deque[_Frame] = deque(maxlen=80)
        self._lock = threading.Lock()
        self._capture_frames = 0
        self._processed_frames = 0
        self._failures = 0
        self._correlation_sum = 0.0
        self._reduction_sum = 0.0
        self._best_delay_ms = 0
        self._last_correlation = 0.0
        self._last_reduction_db = 0.0
        self._last_processed_at = 0.0
        self._last_reason = "нет опорного сигнала"

    def reset(self) -> None:
        with self._lock:
            self._render.clear()
            self._best_delay_ms = 0
            self._last_correlation = 0.0
            self._last_reduction_db = 0.0
            self._last_processed_at = 0.0
            self._last_reason = "ожидание нового опорного сигнала"

    def push_render(self, pcm: bytes, rate: int, start_ms: int,
                    end_ms: int) -> bytes:
        """Сохранить системный звук как render reference."""
        samples = _float_samples(pcm, rate)
        if not len(samples):
            return pcm
        frame = _Frame(int(start_ms), int(end_ms), samples)
        with self._lock:
            self._render.append(frame)
            cutoff = int(end_ms) - self.max_delay_ms - 1500
            while self._render and self._render[0].end_ms < cutoff:
                self._render.popleft()
        return pcm

    def _reference_grid(self, start_ms: int, end_ms: int,
                        frames: list[_Frame]) -> tuple[np.ndarray, int]:
        grid_start = start_ms - self.max_delay_ms - 120
        length = max(1, round((end_ms - grid_start) * INTERNAL_RATE / 1000))
        grid = np.zeros(length, dtype=np.float32)
        for frame in frames:
            offset = round((frame.start_ms - grid_start) * INTERNAL_RATE / 1000)
            left = max(0, offset)
            source_left = max(0, -offset)
            count = min(len(frame.samples) - source_left, length - left)
            if count > 0:
                grid[left:left + count] = frame.samples[
                    source_left:source_left + count]
        return grid, grid_start

    def _pass(self, reason: str, pcm: bytes) -> bytes:
        self._last_reason = reason
        self._last_correlation = 0.0
        self._last_reduction_db = 0.0
        return pcm

    def _best_reference(self, centered_capture: np.ndarray, capture_norm: float,
                        grid: np.ndarray, grid_start: int,
                        start_ms: int) -> tuple | None:
        best = None
        for delay_ms in range(0, self.max_delay_ms + 1, 10):
            ref_start = round(
                (start_ms - delay_ms - grid_start) * INTERNAL_RATE / 1000)
            reference = grid[ref_start:ref_start + len(centered_capture)]
            if len(reference) != len(centered_capture):
                continue
            centered_reference = reference - float(np.mean(reference))
            if _rms(centered_reference) < MIN_SIGNAL_RMS:
                continue
            denominator = capture_norm * float(np.linalg.norm(centered_reference))
            if denominator < 1e-9:
                continue
            dot = float(np.dot(centered_capture, centered_reference))
            correlation = abs(dot / denominator)
            if best is None or correlation > best[0]:
                gain = dot / max(
                    float(np.dot(centered_reference, centered_reference)), 1e-9)
                best = (correlation, delay_ms, gain, centered_reference)
        return best

    def _record_suppression(self, correlation: float, delay_ms: int,
                            reduction_db: float) -> None:
        self._processed_frames += 1
        self._correlation_sum += correlation
        self._reduction_sum += max(0.0, reduction_db)
        self._best_delay_ms = int(delay_ms)
        self._last_correlation = float(correlation)
        self._last_reduction_db = max(0.0, float(reduction_db))
        self._last_processed_at = time.monotonic()
        self._last_reason = "активен"

    @staticmethod
    def _resize_removed_echo(removed: np.ndarray, length: int) -> np.ndarray:
        if len(removed) == length:
            return removed
        return np.interp(
            np.linspace(0, len(removed) - 1, length),
            np.arange(len(removed)), removed).astype(np.float32)

    def _apply_best_reference(self, pcm: bytes, original: np.ndarray,
                              original_length: int, capture: np.ndarray,
                              capture_rms: float, best: tuple) -> bytes:
        correlation, delay_ms, gain, reference = best
        gain = max(-2.5, min(2.5, float(gain)))
        echo_rms = abs(gain) * _rms(reference)
        if echo_rms / max(capture_rms, 1e-9) < 0.08:
            return self._pass("оценённое эхо слишком тихое", pcm)
        confidence = min(
            1.0, max(0.0, (correlation - self.min_correlation)
                     / max(0.01, 0.95 - self.min_correlation)))
        strength = 0.35 + confidence * 0.60
        cleaned = capture - strength * gain * reference
        output_rms = _rms(cleaned)
        if output_rms > capture_rms * 1.05:
            return self._pass("фильтр увеличил энергию", pcm)
        if correlation >= 0.96 and output_rms < 0.0015:
            cleaned.fill(0)
            output_rms = 0.0
        reduction_db = 20 * math.log10(
            max(capture_rms, 1e-9) / max(output_rms, 1e-9))
        self._record_suppression(correlation, delay_ms, reduction_db)
        removed_echo = self._resize_removed_echo(
            capture - cleaned, original_length)
        return _pcm_samples(original - removed_echo, original_length)

    def _process_with_reference(self, pcm: bytes, rate: int, start_ms: int,
                                end_ms: int, frames: list[_Frame]) -> bytes:
        original_length = len(pcm) // 2
        original = np.frombuffer(pcm, dtype=np.int16).astype(
            np.float32) / 32768.0
        capture = _float_samples(pcm, rate)
        capture_rms = _rms(capture)
        if capture_rms < MIN_SIGNAL_RMS:
            return self._pass("микрофон почти молчит", pcm)
        grid, grid_start = self._reference_grid(start_ms, end_ms, frames)
        centered_capture = capture - float(np.mean(capture))
        capture_norm = float(np.linalg.norm(centered_capture))
        if capture_norm < 1e-6:
            return self._pass("микрофонный блок постоянный", pcm)
        best = self._best_reference(
            centered_capture, capture_norm, grid, grid_start, start_ms)
        if best is None:
            return self._pass("опорный сигнал не похож на микрофон", pcm)
        if best[0] < self.min_correlation:
            return self._pass(f"корреляция {best[0]:.2f} ниже порога", pcm)
        return self._apply_best_reference(
            pcm, original, original_length, capture, capture_rms, best)

    def process_capture(self, pcm: bytes, rate: int, start_ms: int,
                        end_ms: int) -> bytes:
        """Вернуть очищенный PCM либо исходник, если опора/оценка ненадёжна."""
        with self._lock:
            self._capture_frames += 1
            frames = list(self._render)
            if not frames:
                return self._pass("нет опорного loopback", pcm)
            try:
                return self._process_with_reference(
                    pcm, rate, int(start_ms), int(end_ms), frames)
            except Exception:
                self._failures += 1
                return self._pass("ошибка фильтра — исходный звук сохранён", pcm)

    def snapshot(self) -> dict:
        with self._lock:
            processed = self._processed_frames
            active = bool(self._last_processed_at
                          and time.monotonic() - self._last_processed_at < 3)
            return {
                "enabled": True,
                "active": active,
                "capture_frames": self._capture_frames,
                "processed_frames": processed,
                "failures": self._failures,
                "delay_ms": self._best_delay_ms,
                "correlation": round(self._last_correlation, 3),
                "average_correlation": round(
                    self._correlation_sum / max(1, processed), 3),
                "reduction_db": round(self._last_reduction_db, 1),
                "average_reduction_db": round(
                    self._reduction_sum / max(1, processed), 1),
                "status": self._last_reason,
            }


class EchoSuppressionPipeline:
    """Выбрать WebRTC AEC3 и безопасно откатиться на встроенный фильтр."""

    def __init__(self, backend: str = "auto", *, native_factory=None):
        if backend not in {"auto", "native", "correlation"}:
            raise ValueError(f"неизвестный AEC backend: {backend}")
        self.requested_backend = backend
        self._fallback = AdaptiveEchoSuppressor()
        self._native_factory = native_factory
        self._native = None
        self._native_available = False
        self._native_error = ""
        self._native_lock = threading.RLock()
        if backend != "correlation":
            self._start_native()

    def _start_native(self) -> None:
        try:
            if self._native_factory is None:
                import native_aec
                current = native_aec.status()
                self._native_available = bool(current["valid"])
                if not current["valid"]:
                    self._native_error = str(current["error"])
                    return
                factory = native_aec.WebRtcAec3
            else:
                self._native_available = True
                factory = self._native_factory
            self._native = factory()
            self._native_error = ""
        except Exception as exc:
            self._native = None
            self._native_error = str(exc)

    def _disable_native(self, exc: BaseException) -> None:
        self._native_error = f"AEC3 отключён: {exc}"
        native = self._native
        self._native = None
        if native is not None:
            try:
                native.close()
            except Exception:
                pass

    def push_render(self, pcm: bytes, rate: int, start_ms: int,
                    end_ms: int) -> bytes:
        # Fallback всегда получает опору, чтобы подхватить следующий mic-чанк
        # без периода повторного обучения при аварии sidecar.
        self._fallback.push_render(pcm, rate, start_ms, end_ms)
        with self._native_lock:
            if self._native is not None:
                try:
                    self._native.push_render(pcm, rate, start_ms, end_ms)
                except Exception as exc:
                    self._disable_native(exc)
        # Оба распознавателя используют единый контракт аудиопроцессора:
        # результат должен быть PCM того же размера. Render не очищается, но
        # обязан пройти дальше в STT; None отключал подачу опоры AEC после
        # первого блока системного звука.
        return pcm

    def process_capture(self, pcm: bytes, rate: int, start_ms: int,
                        end_ms: int) -> bytes:
        with self._native_lock:
            if self._native is not None:
                try:
                    return self._native.process_capture(
                        pcm, rate, start_ms, end_ms)
                except Exception as exc:
                    self._disable_native(exc)
        return self._fallback.process_capture(pcm, rate, start_ms, end_ms)

    def reset(self) -> None:
        self._fallback.reset()
        with self._native_lock:
            native = self._native
            self._native = None
            if native is not None:
                try:
                    native.close()
                except Exception:
                    pass
            if self.requested_backend != "correlation":
                self._start_native()

    def snapshot(self) -> dict:
        with self._native_lock:
            if self._native is not None:
                result = self._native.snapshot()
                result.update({
                    "requested_backend": self.requested_backend,
                    "native_available": True,
                    "native_error": "",
                })
                return result
        result = self._fallback.snapshot()
        result.update({
            "backend": "correlation",
            "requested_backend": self.requested_backend,
            "native_available": self._native_available,
            "native_error": self._native_error,
        })
        if self._native_error and self.requested_backend != "correlation":
            result["status"] = f"встроенный фильтр · {self._native_error}"
        return result

    def close(self) -> None:
        with self._native_lock:
            native = self._native
            self._native = None
            if native is not None:
                try:
                    native.close()
                except Exception:
                    pass


def create_echo_processor(backend: str = "auto") -> EchoSuppressionPipeline:
    return EchoSuppressionPipeline(backend)


def _read_mono(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as source:
        if source.getsampwidth() != 2:
            raise ValueError(f"поддерживается только PCM16 WAV: {path}")
        rate = source.getframerate()
        channels = source.getnchannels()
        data = source.readframes(source.getnframes())
    if channels == 1:
        return data, rate
    samples = np.frombuffer(data, dtype=np.int16).reshape(-1, channels)
    mono = np.rint(np.mean(samples.astype(np.float32), axis=1))
    return np.clip(mono, -32768, 32767).astype(np.int16).tobytes(), rate


def process_wav(capture_path: Path, render_path: Path, output_path: Path, *,
                backend: str = "correlation",
                progress: Callable[[int, int], None] | None = None,
                cancelled: Callable[[], bool] | None = None) -> dict:
    """Офлайн-smoke тем же 100-мс процессором; исходные WAV не изменяются."""
    capture, capture_rate = _read_mono(capture_path)
    render, render_rate = _read_mono(render_path)
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(f"результат уже существует: {output_path}")
    processor = create_echo_processor(backend)
    capture_size = int(capture_rate * 0.1) * 2
    render_size = int(render_rate * 0.1) * 2
    output = bytearray()
    capture_blocks = math.ceil(len(capture) / max(1, capture_size))
    try:
        for index in range(capture_blocks):
            if cancelled and cancelled():
                raise InterruptedError("AEC-прогон отменён")
            start_ms = index * 100
            end_ms = start_ms + 100
            render_chunk = render[
                index * render_size:(index + 1) * render_size]
            if render_chunk:
                processor.push_render(
                    render_chunk, render_rate, start_ms, end_ms)
            capture_chunk = capture[
                index * capture_size:(index + 1) * capture_size]
            if not capture_chunk:
                break
            output.extend(processor.process_capture(
                capture_chunk, capture_rate, start_ms, end_ms))
            if progress:
                progress(index + 1, capture_blocks)
        snapshot = processor.snapshot()
    finally:
        processor.close()
    temporary = output_path.with_name(output_path.name + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with wave.open(str(temporary), "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(capture_rate)
            target.writeframes(output)
        os.replace(temporary, output_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="сырой микрофонный PCM16 WAV")
    parser.add_argument("render", type=Path, help="опорный loopback PCM16 WAV")
    parser.add_argument("output", type=Path, help="новый очищенный WAV")
    args = parser.parse_args()
    result = process_wav(args.capture, args.render, args.output)
    print(f"Очищенный WAV: {args.output}")
    print(f"Диагностика: {result}")


if __name__ == "__main__":
    main()
