"""Локальная калибровка маршрута выход → loopback → микрофон.

В выбранный выход воспроизводится тихий детерминированный сигнал. Одновременно
измеряются выбранный WASAPI-loopback и микрофон. Аудио остаётся в памяти и после
расчёта отбрасывается: тест не использует STT, LLM или облачные API.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

import numpy as np
import pyaudiowpatch as pyaudio


ANALYSIS_RATE = 16000
CAPTURE_FRAME_MS = 20
TEST_SECONDS = 3.2


@dataclass
class _Capture:
    samples: np.ndarray
    rate: int
    started_at: float


def _mono(data: bytes, channels: int) -> np.ndarray:
    samples = np.frombuffer(data, dtype=np.int16)
    if channels > 1 and len(samples) >= channels:
        usable = len(samples) - len(samples) % channels
        samples = samples[:usable].reshape(-1, channels).astype(np.float32)
        samples = np.mean(samples, axis=1)
    return samples.astype(np.float32) / 32768.0


def _resample(samples: np.ndarray, source_rate: int,
              target_rate: int = ANALYSIS_RATE) -> np.ndarray:
    if not len(samples) or source_rate == target_rate:
        return samples.astype(np.float32, copy=False)
    length = max(1, round(len(samples) * target_rate / max(1, source_rate)))
    return np.interp(
        np.linspace(0, len(samples) - 1, length),
        np.arange(len(samples)), samples).astype(np.float32)


def _rms(samples: np.ndarray) -> float:
    return (float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
            if len(samples) else 0.0)


def _dbfs(value: float) -> float:
    return 20 * math.log10(max(float(value), 1e-9))


def _timeline(signal: _Capture, origin: float, length: int) -> np.ndarray:
    samples = _resample(signal.samples, signal.rate)
    result = np.zeros(length, dtype=np.float32)
    offset = max(0, round((signal.started_at - origin) * ANALYSIS_RATE))
    count = min(len(samples), length - offset)
    if count > 0:
        result[offset:offset + count] = samples[:count]
    return result


def _aligned_calibration_signals(
        mic_samples: np.ndarray, mic_rate: int, mic_started_at: float,
        render_samples: np.ndarray, render_rate: int,
        render_started_at: float) -> tuple[np.ndarray, np.ndarray]:
    mic_length = round(len(mic_samples) * ANALYSIS_RATE / max(1, mic_rate))
    render_length = round(
        len(render_samples) * ANALYSIS_RATE / max(1, render_rate))
    origin = min(mic_started_at, render_started_at)
    length = max(
        round((mic_started_at - origin) * ANALYSIS_RATE) + mic_length,
        round((render_started_at - origin) * ANALYSIS_RATE) + render_length,
        1,
    )
    mic = _timeline(_Capture(mic_samples, mic_rate, mic_started_at), origin, length)
    render = _timeline(
        _Capture(render_samples, render_rate, render_started_at), origin, length)
    mic -= float(np.mean(mic))
    render -= float(np.mean(render))
    return mic, render


def _best_echo_match(mic: np.ndarray, render: np.ndarray,
                     max_delay_ms: int) -> tuple[float, int, float]:
    length = len(mic)
    best = (0.0, 0, 0.0)
    for delay_ms in range(0, max_delay_ms + 1, 5):
        delay = round(delay_ms * ANALYSIS_RATE / 1000)
        if delay >= length - ANALYSIS_RATE // 2:
            break
        reference = render[:length - delay]
        capture = mic[delay:]
        denominator = (float(np.linalg.norm(reference))
                       * float(np.linalg.norm(capture)))
        if denominator < 1e-8:
            continue
        dot = float(np.dot(reference, capture))
        correlation = abs(dot / denominator)
        if correlation > best[0]:
            gain = dot / max(float(np.dot(reference, reference)), 1e-9)
            best = (correlation, delay_ms, gain)
    return best


def _calibration_diagnosis(route_signal: bool, echo_detected: bool,
                           delay_ms: int) -> tuple[str, str]:
    if not route_signal:
        return (
            "output_missing",
            "Тестовый звук не появился в системном канале. Проверьте выбранный "
            "выход и укажите тот же выход в приложении встречи.")
    if echo_detected:
        return (
            "echo_detected",
            f"Маршрут работает; в микрофоне найдено эхо с задержкой {delay_ms} мс. "
            "Оставьте подавление до STT включённым.")
    return (
        "good",
        "Маршрут работает, заметного проникновения в микрофон нет. "
        "В приложении встречи выберите этот же выход.")


def analyze_calibration(mic_samples: np.ndarray, mic_rate: int,
                        mic_started_at: float, render_samples: np.ndarray,
                        render_rate: int, render_started_at: float,
                        *, max_delay_ms: int = 500) -> dict:
    """Оценить маршрут и коррелирующую эхо-составляющую двух дорожек."""
    mic, render = _aligned_calibration_signals(
        mic_samples, mic_rate, mic_started_at,
        render_samples, render_rate, render_started_at)
    mic_rms = _rms(mic)
    render_rms = _rms(render)
    route_signal = render_rms >= 0.002
    best = (_best_echo_match(mic, render, max_delay_ms)
            if route_signal and mic_rms >= 0.0002 else (0.0, 0, 0.0))

    correlation, delay_ms, gain = best
    echo_rms = abs(gain) * render_rms
    echo_detected = bool(
        route_signal and correlation >= 0.35 and echo_rms >= 0.001)
    state, recommendation = _calibration_diagnosis(
        route_signal, echo_detected, delay_ms)
    return {
        "diagnosis": state,
        "route_signal": route_signal,
        "echo_detected": echo_detected,
        "delay_ms": int(delay_ms if echo_detected else 0),
        "correlation": round(float(correlation), 3),
        "leakage_db": round(20 * math.log10(max(abs(gain), 1e-9)), 1),
        "loopback_dbfs": round(_dbfs(render_rms), 1),
        "mic_dbfs": round(_dbfs(mic_rms), 1),
        "echo_dbfs": round(_dbfs(echo_rms), 1),
        "recommendation": recommendation,
    }


def _calibration_signal(rate: int, seconds: float = TEST_SECONDS) -> np.ndarray:
    count = max(1, round(rate * seconds))
    t = np.arange(count, dtype=np.float64) / rate
    # Два плавных чирпа дают узнаваемый, но негромкий сигнал с хорошей
    # автокорреляцией. Огибающая исключает щелчки в начале и конце.
    frequency = 420 + 2100 * (t / max(seconds, 0.1))
    phase = 2 * np.pi * np.cumsum(frequency) / rate
    signal = np.sin(phase) + 0.35 * np.sin(phase * 1.73 + 0.4)
    fade = max(1, round(rate * 0.12))
    envelope = np.ones(count, dtype=np.float64)
    envelope[:fade] = np.linspace(0, 1, fade)
    envelope[-fade:] = np.linspace(1, 0, fade)
    return (signal * envelope * 0.055).astype(np.float32)


def _output_device(pa: pyaudio.PyAudio, selector: str) -> tuple[int, str]:
    wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    if not selector or selector == "auto":
        index = int(wasapi["defaultOutputDevice"])
        return index, str(pa.get_device_info_by_index(index)["name"])
    for index in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(index)
        if (info["hostApi"] == wasapi["index"]
                and info["maxOutputChannels"] > 0
                and str(info["name"]) == selector):
            return int(info["index"]), str(info["name"])
    raise RuntimeError(f"выход воспроизведения «{selector}» не найден")


def _capture(stream, rate: int, channels: int, stop: threading.Event,
             result: dict, key: str, errors: list[Exception]) -> None:
    frames = max(1, round(rate * CAPTURE_FRAME_MS / 1000))
    chunks: list[np.ndarray] = []
    started_at = 0.0
    try:
        while not stop.is_set():
            data = stream.read(frames, exception_on_overflow=False)
            ended_at = time.monotonic()
            if not started_at:
                started_at = ended_at - frames / max(1, rate)
            chunks.append(_mono(data, channels))
    except Exception as exc:
        errors.append(exc)
        stop.set()
    finally:
        result[key] = _Capture(
            np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32),
            rate, started_at or time.monotonic())


def calibrate(mic_selector: str, output_selector: str, on_stage=None) -> dict:
    """Воспроизвести локальный тест и вернуть диагностику без записи на диск."""
    from live import _output_name, pick_loopback, resolve_mic

    mic_index, mic_name = resolve_mic(mic_selector)
    loop_index, loop_name = pick_loopback(output_selector)
    pa = pyaudio.PyAudio()
    streams = []
    stop = threading.Event()
    errors: list[Exception] = []
    captured: dict[str, _Capture] = {}
    threads = []
    try:
        output_index, output_name = _output_device(pa, output_selector)
        mic_info = pa.get_device_info_by_index(mic_index)
        loop_info = pa.get_device_info_by_index(loop_index)
        output_info = pa.get_device_info_by_index(output_index)
        mic_channels = max(1, int(mic_info["maxInputChannels"]))
        loop_channels = max(1, int(loop_info["maxInputChannels"]))
        output_channels = min(2, max(1, int(output_info["maxOutputChannels"])))
        mic_rate = int(mic_info["defaultSampleRate"])
        loop_rate = int(loop_info["defaultSampleRate"])
        output_rate = int(output_info["defaultSampleRate"])
        mic_stream = pa.open(
            format=pyaudio.paInt16, channels=mic_channels, rate=mic_rate,
            input=True, input_device_index=mic_index,
            frames_per_buffer=max(1, round(mic_rate * CAPTURE_FRAME_MS / 1000)))
        loop_stream = pa.open(
            format=pyaudio.paInt16, channels=loop_channels, rate=loop_rate,
            input=True, input_device_index=loop_index,
            frames_per_buffer=max(1, round(loop_rate * CAPTURE_FRAME_MS / 1000)))
        output_stream = pa.open(
            format=pyaudio.paInt16, channels=output_channels, rate=output_rate,
            output=True, output_device_index=output_index,
            frames_per_buffer=max(1, round(output_rate * CAPTURE_FRAME_MS / 1000)))
        streams = [mic_stream, loop_stream, output_stream]
        for key, stream, rate, channels in (
                ("mic", mic_stream, mic_rate, mic_channels),
                ("render", loop_stream, loop_rate, loop_channels)):
            thread = threading.Thread(
                target=_capture,
                args=(stream, rate, channels, stop, captured, key, errors),
                daemon=True, name=f"aec-calibration-{key}")
            thread.start()
            threads.append(thread)
        if on_stage:
            on_stage("подготовка каналов")
        time.sleep(0.45)
        if on_stage:
            on_stage("воспроизвожу тестовый сигнал — не говорите")
        signal = _calibration_signal(output_rate)
        pcm = np.clip(np.rint(signal * 32767), -32768, 32767).astype(np.int16)
        if output_channels > 1:
            pcm = np.repeat(pcm[:, None], output_channels, axis=1).reshape(-1)
        block = max(1, round(output_rate * CAPTURE_FRAME_MS / 1000))
        block_bytes = block * output_channels * 2
        data = pcm.tobytes()
        for offset in range(0, len(data), block_bytes):
            output_stream.write(data[offset:offset + block_bytes])
        time.sleep(0.55)
        stop.set()
        for thread in threads:
            thread.join(timeout=2)
        if errors:
            raise RuntimeError(str(errors[0]))
        if "mic" not in captured or "render" not in captured:
            raise RuntimeError("аудиоканалы не вернули данные")
        if on_stage:
            on_stage("оцениваю задержку и проникновение")
        result = analyze_calibration(
            captured["mic"].samples, captured["mic"].rate,
            captured["mic"].started_at, captured["render"].samples,
            captured["render"].rate, captured["render"].started_at)
        result.update({
            "mic": mic_name,
            "output": _output_name(loop_name),
            "playback": output_name,
            "stored": False,
        })
        return result
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=0.5)
        for stream in streams:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        pa.terminate()
