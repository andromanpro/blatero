"""Низкоуровневое обнаружение и проверка WASAPI-аудиоустройств."""

import array
import base64
import io
import time
import wave


def list_mics() -> list[str]:
    try:
        from live import device_options, list_input_devices
        return ["auto"] + device_options(list_input_devices())
    except Exception:
        return ["auto"]


def list_outputs() -> list[str]:
    try:
        from live import device_options, list_output_devices
        return ["auto"] + device_options(list_output_devices())
    except Exception:
        return ["auto"]


def _probe_input(device_idx: int, device_name: str, seconds: float,
                 threshold: float, on_level=None, *, preview=False, on_ready=None,
                 cancel=None) -> dict:
    import pyaudiowpatch as pyaudio

    if cancel and cancel.is_set():
        return {"device":device_name, "peak":0.0, "signal":False}
    pa = pyaudio.PyAudio()
    stream = None
    peak_seen = 0.0
    chunks = []
    try:
        info = pa.get_device_info_by_index(device_idx)
        channels = max(1, int(info["maxInputChannels"]))
        rate = int(info["defaultSampleRate"])
        frames = max(1, int(rate * 0.1))
        stream = pa.open(format=pyaudio.paInt16, channels=channels, rate=rate,
                         input=True, input_device_index=device_idx,
                         frames_per_buffer=frames)
        if on_ready:
            on_ready(device_name)
        deadline = time.monotonic() + seconds
        remaining = round(rate * seconds)
        while time.monotonic() < deadline and remaining > 0 and not (cancel and cancel.is_set()):
            data = stream.read(frames, exception_on_overflow=False)
            samples = array.array("h", data)
            peak = max((abs(sample) for sample in samples), default=0) / 32768
            peak_seen = max(peak_seen, peak)
            if on_level:
                on_level(min(1.0, peak * 2.5))
            count = min(len(samples) // channels, remaining)
            if preview:
                # Browser preview is bounded and independent of meeting files.
                mono = array.array('h', (sum(samples[i:i+channels]) // channels
                    for i in range(0, count * channels, channels)))
                chunks.append(mono.tobytes())
            remaining -= count
        result = {
            "device": device_name,
            "peak": round(peak_seen, 3),
            "signal": peak_seen >= threshold,
        }
        if preview and not (cancel and cancel.is_set()):
            from pcm_resampler import resample_pcm16_mono
            pcm, _ = resample_pcm16_mono(b''.join(chunks), rate, 16000)
            output = io.BytesIO()
            with wave.open(output, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(pcm)
            result.update(wav_base64=base64.b64encode(output.getvalue()).decode('ascii'),
                          seconds=len(pcm) / 32000)
        return result
    finally:
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        pa.terminate()


def probe_microphone(selector: str, seconds: float = 8.0, on_level=None) -> dict:
    """Локально измерить сигнал выбранного WASAPI-микрофона, ничего не сохраняя."""
    from live import resolve_mic

    mic_idx, mic_name = resolve_mic(selector)
    return _probe_input(mic_idx, mic_name, seconds, 0.012, on_level)


def preview_microphone(selector: str, seconds: float = 12.0, on_level=None,
                       on_ready=None, cancel=None) -> dict:
    """Local in-memory WAV for the requesting browser, never a voice-bank sample."""
    from live import resolve_mic
    mic_idx, mic_name = resolve_mic(selector)
    return _probe_input(mic_idx, mic_name, max(1, min(12, seconds)), .012,
        on_level, preview=True, on_ready=on_ready, cancel=cancel)


def probe_output(selector: str, seconds: float = 8.0, on_level=None) -> dict:
    """Измерить сигнал выбранного WASAPI loopback без записи на диск."""
    from live import _output_name, pick_loopback

    device_idx, loopback_name = pick_loopback(selector)
    return _probe_input(
        device_idx, _output_name(loopback_name), seconds, 0.006, on_level)


def probe_recording_route(microphone: str, output: str, seconds: float = 0.5) -> dict:
    """Open the actual pair of callback capture workers; retain no audio."""
    from audio_capture import AudioCapture
    from live import pick_loopback, resolve_mic

    mic_index, mic_name = resolve_mic(microphone)
    loop_index, loop_name = pick_loopback(output)
    counts = {"microphone": 0, "loopback": 0}
    owners = []
    origin = time.monotonic()
    try:
        # Match live.py: system audio first, then microphone, both remain open.
        for key, index in (("loopback", loop_index), ("microphone", mic_index)):
            def tap(pcm, *_args, channel=key):
                counts[channel] += len(pcm)
            owner = AudioCapture(index, key, timeline_origin=origin,
                tap=tap, sink=lambda *_: None, on_error=lambda *_: None)
            owners.append(owner)
            owner.start()
        time.sleep(max(0.1, min(2.0, seconds)))
        for owner in owners:
            if owner.capture_error:
                raise RuntimeError(owner.capture_error)
        if not counts["microphone"]:
            raise RuntimeError("микрофон открылся, но не передал PCM в контур записи")
    finally:
        for owner in owners:
            owner.request_stop()
        errors = []
        for owner in owners:
            try:
                owner.wait_capture()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError("; ".join(errors))
    # Loopback may be silent when the meeting application plays no sound.
    return {"microphone": mic_name, "loopback": loop_name,
            "simultaneous_open": True, "capture_callback": True,
            "mic_pcm_bytes": counts["microphone"],
            "loopback_pcm_bytes": counts["loopback"]}
