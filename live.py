"""Живая запись: мик + системный звук → STT → JSONL и Markdown-транскрипт.

Запуск:  python live.py            — до Ctrl+C
         python live.py --seconds 20 --say "фраза"   — автотест с озвучкой SAPI
Каналы:  [Я] = микрофон по умолчанию, [Собеседник] = loopback дефолтных колонок.
"""
import argparse
import array
import datetime as dt
import json
import os
import signal
import sys
import threading
import time
import runtime_diagnostics as diagnostics
from collections import deque
from dataclasses import dataclass
from contextlib import nullcontext
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import pyaudiowpatch as pyaudio

import app_paths
import config as cfg
import session_recovery
import session_schema
import transcript_events
import stt_switch
from audio_watchdog import AudioWatchdog
from audio_device_monitor import AudioDeviceMonitor
from audio_echo import create_echo_processor
from channel_echo import CrossChannelEchoFilter
from session_utils import direct_child

BASE = app_paths.DATA_ROOT
SESSIONS = app_paths.SESSIONS_ROOT
REMOTE_ROLE = "Собеседник"
LOCAL_ROLE = "Я"
LEVELS_FILE = "levels.json"
DEVICE_SELECTOR_MARK = " · устройство #"


@dataclass(frozen=True)
class AudioRoute:
    mic_index: int
    mic_name: str
    mic_selector: str | int
    loop_index: int
    loop_name: str
    output_selector: str


def list_input_devices() -> list[tuple[int, str]]:
    """WASAPI-микрофоны (без loopback-устройств)."""
    with pyaudio.PyAudio() as audio:
        wasapi_idx = audio.get_host_api_info_by_type(pyaudio.paWASAPI)["index"]
        result = []
        for index in range(audio.get_device_count()):
            device = audio.get_device_info_by_index(index)
            if (device["hostApi"] == wasapi_idx and device["maxInputChannels"] > 0
                    and not device.get("isLoopbackDevice")):
                result.append((int(device["index"]), device["name"]))
        return result


def device_options(devices: list[tuple[int, str]]) -> list[str]:
    """Make duplicate display names selectable without silently taking first."""
    counts: dict[str, int] = {}
    for _, name in devices:
        counts[name] = counts.get(name, 0) + 1
    return [
        (f"{name}{DEVICE_SELECTOR_MARK}{index}" if counts[name] > 1 else name)
        for index, name in devices
    ]


def _indexed_selector(selector: object) -> tuple[str, int | None]:
    value = str(selector or "")
    name, marker, raw_index = value.rpartition(DEVICE_SELECTOR_MARK)
    if marker and raw_index.isdigit():
        return name, int(raw_index)
    return value, None


def resolve_mic(selector) -> tuple[int, str]:
    """Разрешить индекс, ``auto`` или точное имя микрофона."""
    if isinstance(selector, int):
        with pyaudio.PyAudio() as audio:
            return selector, audio.get_device_info_by_index(selector)["name"]
    if selector and selector != "auto":
        selected_name, selected_index = _indexed_selector(selector)
        matches = [(index, name) for index, name in list_input_devices()
                   if name == selected_name]
        if selected_index is not None:
            exact = [item for item in matches if item[0] == selected_index]
            if len(exact) == 1:
                return exact[0]
        elif len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            raise RuntimeError(
                f"микрофон «{selector}» неоднозначен; выберите вариант с номером")
        raise RuntimeError(f"микрофон «{selector}» не найден среди устройств")
    with pyaudio.PyAudio() as audio:
        index = audio.get_host_api_info_by_type(
            pyaudio.paWASAPI)["defaultInputDevice"]
        return index, audio.get_device_info_by_index(index)["name"]


def _output_name(loopback_name: str) -> str:
    suffix = " [Loopback]"
    return loopback_name[:-len(suffix)] if loopback_name.endswith(suffix) else loopback_name


def list_output_devices() -> list[tuple[int, str]]:
    """Физические WASAPI-выходы, у которых PyAudioWPatch нашёл loopback."""
    with pyaudio.PyAudio() as audio:
        return [(int(device["index"]), _output_name(str(device["name"])))
                for device in audio.get_loopback_device_info_generator()]


def pick_loopback(selector: str = "auto") -> tuple[int, str]:
    with pyaudio.PyAudio() as audio:
        wasapi = audio.get_host_api_info_by_type(pyaudio.paWASAPI)
        devices = list(audio.get_loopback_device_info_generator())
        loop = None
        if selector and selector != "auto":
            selected_name, selected_index = _indexed_selector(selector)
            exact = [device for device in devices
                     if _output_name(str(device["name"])) == selected_name
                     and (selected_index is None
                          or int(device["index"]) == selected_index)]
            if len(exact) == 1:
                loop = exact[0]
            elif len(exact) > 1:
                raise RuntimeError(
                    f"выход «{selector}» неоднозначен; выберите вариант с номером")
            if loop is None:
                available = ", ".join(
                    _output_name(str(device["name"])) for device in devices)
                raise RuntimeError(
                    f"выход «{selector}» не найден; доступны: {available or 'нет'}")
        else:
            output = audio.get_device_info_by_index(wasapi["defaultOutputDevice"])
            output_name = str(output["name"])
            loop = next((device for device in devices
                         if output_name in device["name"]), None)
        if loop is None:
            selected = selector if selector and selector != "auto" else output_name
            raise RuntimeError(f"нет loopback для выхода «{selected}»")
        return int(loop["index"]), str(loop["name"])


def read_audio_inventory() -> dict:
    """Один локальный снимок входов, loopback-выходов и системных defaults."""
    with pyaudio.PyAudio() as audio:
        wasapi = audio.get_host_api_info_by_type(pyaudio.paWASAPI)
        inputs = []
        for index in range(audio.get_device_count()):
            device = audio.get_device_info_by_index(index)
            if (device["hostApi"] == wasapi["index"]
                    and device["maxInputChannels"] > 0
                    and not device.get("isLoopbackDevice")):
                inputs.append(str(device["name"]))
        outputs = [_output_name(str(device["name"]))
                   for device in audio.get_loopback_device_info_generator()]
        default_mic = ""
        default_output = ""
        try:
            default_mic = str(audio.get_device_info_by_index(
                wasapi["defaultInputDevice"])["name"])
        except (KeyError, OSError):
            pass
        try:
            physical = str(audio.get_device_info_by_index(
                wasapi["defaultOutputDevice"])["name"])
            default_output = next(
                (name for name in outputs if name == physical), physical)
        except (KeyError, OSError):
            pass
        return {
            "mics": inputs, "outputs": outputs,
            "default_mic": default_mic, "default_output": default_output,
        }


class TranscriptWriter:
    def __init__(self, path: Path, title: str = "", *, suppress_echo: bool = True,
                 provider: str = "unknown", segment: int = 1,
                 audio_files: dict[str, str] | None = None,
                 speaker_names: dict[str, str] | None = None):
        self.path = path
        self.journal_path = transcript_events.journal_path(path)
        self._lock = threading.Lock()
        self._last_capture_ms = 0
        started = dt.datetime.now().astimezone()
        with self.path.open("x", encoding="utf-8") as output:
            output.write(f"# Транскрипт: {title or 'встреча'} — "
                         f"{started:%Y-%m-%d %H:%M}\n\n")
        try:
            self.header = transcript_events.create_journal(
                self.journal_path, title=title or "встреча", provider=provider,
                segment=segment, audio_files=audio_files,
                speaker_names=speaker_names,
                started_at=started.isoformat(timespec="milliseconds"))
        except Exception:
            self.path.unlink(missing_ok=True)
            raise
        self._echo_filter = CrossChannelEchoFilter(
            self._write, enabled=suppress_echo,
            on_suppressed=self._write_suppressed)

    def add(self, speaker: str, text: str, metadata: dict | None = None):
        self._echo_filter.add(speaker, text, metadata)

    def add_suppressed(self, speaker: str, text: str, metadata: dict | None,
                       reason: str) -> None:
        self._echo_filter.add_suppressed(speaker, text, metadata, reason)

    @property
    def echoes_suppressed(self) -> int:
        return self._echo_filter.suppressed

    @property
    def publication_error(self) -> str:
        return self._echo_filter.publication_error

    def close(self):
        self._echo_filter.close()
        # Во время записи Markdown дописывается по мере прихода результатов от
        # двух распознавателей. После сброса хвоста восстанавливаем читаемую
        # хронологию из канонического JSONL.
        try:
            transcript_events.render_markdown(self.journal_path, self.path)
        except (OSError, ValueError) as exc:
            # Ошибка производного Markdown не должна мешать закрыть WAV и
            # распознаватели; канонический JSONL остаётся для восстановления.
            print(f"!! транскрипт не отсортирован: {exc}", flush=True)

    def _write(self, speaker: str, text: str, metadata: dict | None = None):
        text = text.strip()
        if not text:
            return
        with self._lock:
            event = transcript_events.append_transcript_turn(
                self.path, speaker, text, metadata=metadata)
            capture_ms = int(event.get("start_ms", 0) or 0)
            if capture_ms < self._last_capture_ms:
                # A retired backend may finish after a newer live result.
                transcript_events.render_markdown(self.journal_path, self.path)
            self._last_capture_ms = max(self._last_capture_ms, capture_ms)
        stamp = dt.datetime.fromisoformat(event["captured_at"]).strftime("%H:%M:%S")
        print(f"[{stamp}][{speaker}] {text}", flush=True)

    def _write_suppressed(self, speaker: str, text: str,
                          metadata: dict | None = None):
        with self._lock:
            transcript_events.append_event(
                self.journal_path, speaker, text, metadata=metadata)


def install_break_handler() -> None:
    if hasattr(signal, "SIGBREAK"):
        def graceful_break(_signal, _frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGBREAK, graceful_break)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mic", type=int, default=None,
                        help="индекс устройства микрофона")
    parser.add_argument("--seconds", type=int, default=0,
                        help="автостоп (0 = до Ctrl+C)")
    parser.add_argument("--say", default=None,
                        help="автотест: озвучить фразу через SAPI")
    parser.add_argument("--session", default=None,
                        help="имя сессии (по умолчанию дата-время)")
    parser.add_argument("--no-record", action="store_true",
                        help="не писать WAV разговора")
    return parser.parse_args()


def recognizer_backend(settings: dict):
    provider = settings.get("speech_provider", "local_whisper")
    if provider == "yandex":
        cfg.require_cloud_processing("аудио в Yandex SpeechKit")
        from speechkit_stream import StreamingRecognizer
        return provider, StreamingRecognizer
    from local_whisper import LocalWhisperRecognizer
    return provider, LocalWhisperRecognizer


def session_metadata(session_name: str | None) -> tuple[Path, Path, dict, str]:
    name = session_name or f"{dt.datetime.now():%Y-%m-%d_%H%M%S}"
    SESSIONS.mkdir(parents=True, exist_ok=True)
    session = direct_child(SESSIONS, name)
    session.mkdir(parents=True, exist_ok=True)
    stop_request = session / ".stop-request"
    stop_request.unlink(missing_ok=True)
    meta = {}
    meta_file = session / "meta.json"
    if meta_file.exists() or (session / session_schema.MANIFEST_FILE).exists():
        session_schema.ensure(session)
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    else:
        now = dt.datetime.now().astimezone()
        session_schema.initialize(session, {
            "date": f"{now:%Y-%m-%d}", "time": f"{now:%H:%M}",
            "name": name, "type": "встреча",
        })
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    title = (f"{meta.get('type', '')} {meta.get('name', '')} "
             f"({meta.get('role', '')})").strip()
    if title:
        print(f"Встреча:     {title}")
    return session, stop_request, meta, title


def create_transcript_writer(session: Path, title: str, meta: dict,
                             settings: dict, provider: str,
                             record_audio: bool) -> tuple[TranscriptWriter, int, str, Path]:
    segment = 1
    for path in session.iterdir():
        if path.suffix not in {".md", ".jsonl", ".wav"}:
            continue
        for prefix in ("transcript", "audio-me", "audio-guest"):
            if path.stem == prefix:
                segment = max(segment, 2)
            elif path.stem.startswith(prefix + "-"):
                number = path.stem[len(prefix) + 1:]
                if number.isdecimal() and len(number) < 10 and str(int(number)) == number:
                    segment = max(segment, int(number) + 1)
    while True:
        suffix = "" if segment == 1 else f"-{segment}"
        transcript = session / f"transcript{suffix}.md"
        if any((session / name).exists() for name in (
                transcript.name, f"transcript{suffix}.jsonl",
                f"audio-me{suffix}.wav", f"audio-guest{suffix}.wav")):
            segment += 1
            continue
        audio_files = ({
            LOCAL_ROLE: f"audio-me{suffix}.wav",
            REMOTE_ROLE: f"audio-guest{suffix}.wav",
        } if record_audio else {})
        speaker_names = {
            role: str(meta.get(key, "")).strip()
            for role, key in ((LOCAL_ROLE, "speaker_me"),
                              (REMOTE_ROLE, "speaker_guest"))
            if str(meta.get(key, "")).strip()
        }
        try:
            writer = TranscriptWriter(
                transcript, title,
                suppress_echo=settings.get("cross_channel_echo_suppression", True),
                provider=provider, segment=segment, audio_files=audio_files,
                speaker_names=speaker_names)
            return writer, segment, suffix, transcript
        except FileExistsError:
            segment += 1


def create_recorders(session: Path, suffix: str, mic_index: int,
                     loop_index: int, enabled: bool) -> tuple[list, dict]:
    feeds = {LOCAL_ROLE: None, REMOTE_ROLE: None}
    if not enabled:
        return [], feeds
    from recorder import ChannelRecorder
    with pyaudio.PyAudio() as audio:
        mic_rate = int(audio.get_device_info_by_index(mic_index)["defaultSampleRate"])
        loop_rate = int(audio.get_device_info_by_index(loop_index)["defaultSampleRate"])
    microphone = ChannelRecorder(session / f"audio-me{suffix}.wav", mic_rate)
    try:
        guest = ChannelRecorder(session / f"audio-guest{suffix}.wav", loop_rate)
    except Exception:
        microphone.close()
        raise
    print("Запись WAV:  audio-me.wav + audio-guest.wav")
    def sequential_feed(recorder):
        def feed(data, rate, start_ms=None, end_ms=None):
            recorder.feed(data, rate, start_ms, end_ms, sequential=True)
        return feed
    return [microphone, guest], {
        LOCAL_ROLE: sequential_feed(microphone), REMOTE_ROLE: sequential_feed(guest)}


class LiveAudioRuntime:
    def __init__(self, *, recognizer_class, provider: str, settings: dict,
                 session: Path, writer: TranscriptWriter, recorders: list,
                 feeds: dict, route: AudioRoute, timeline_origin: float,
                 suffix: str, recording_id: str = "unknown"):
        self.recognizer_class = recognizer_class
        self.provider = provider
        self.settings = settings
        self.session = session
        self.writer = writer
        self.recorders = recorders
        self.feeds = feeds
        self.mic_index = route.mic_index
        self.mic_name = route.mic_name
        self.mic_selector = route.mic_selector
        self.loop_index = route.loop_index
        self.loop_name = route.loop_name
        self.output_selector = route.output_selector
        self.timeline_origin = timeline_origin
        self.suffix = suffix
        self.recording_id = recording_id
        self.levels = {LOCAL_ROLE: 0.0, REMOTE_ROLE: 0.0}
        self.activity = {LOCAL_ROLE: 0.0, REMOTE_ROLE: 0.0}
        self.capture_errors = {LOCAL_ROLE: "", REMOTE_ROLE: ""}
        self._capture_faults = {}
        self._device_gaps = []
        self._capture_retry_at = {}
        self.recognizers = []
        self.captures = []
        self._stt_lock = threading.RLock()
        self._switch_thread = None
        self._retired = []
        self._retired_errors = []
        self._last_speech_request = ""
        self._speech_result = {}
        self._accept_callbacks = True
        self._signal_lock = threading.Lock()
        self._signal_windows = {LOCAL_ROLE: deque(), REMOTE_ROLE: deque()}
        self._stt_latency_ms = {LOCAL_ROLE: 0, REMOTE_ROLE: 0}
        self._stt_result_at = {LOCAL_ROLE: 0.0, REMOTE_ROLE: 0.0}
        self._stt_end_ms = {LOCAL_ROLE: -1, REMOTE_ROLE: -1}
        self._levels_stop = threading.Event()
        self._levels_thread: threading.Thread | None = None
        self._closed = False
        self._recovery_heartbeat_at = 0.0
        self._last_device_reconnect_event = 0
        self.audio_watch = AudioWatchdog(
            session / f"audio-watch{suffix}.jsonl",
            settings.get("audio_guard_thresholds"))
        self.device_monitor = AudioDeviceMonitor(
            read_audio_inventory,
            mic_selector=self.mic_selector,
            output_selector=self.output_selector,
            active_mic=self.mic_name,
            active_output=_output_name(self.loop_name),
        )
        aec_enabled = bool(settings.get("pre_stt_echo_suppression", True))
        self.acoustic_echo = (create_echo_processor(
            settings.get("pre_stt_echo_backend", "auto")) if aec_enabled else None)
        if self.acoustic_echo:
            snapshot = self.acoustic_echo.snapshot()
            print(f"AEC до STT:  {snapshot['backend']} "
                  "(сырой WAV сохраняется без изменений)")

    def _handle_segment(self, speaker: str, kind: str, text: str,
                        metadata: dict | None = None) -> None:
        if kind == "refined":
            end_ms = (metadata or {}).get("end_ms")
            if isinstance(end_ms, (int, float)) and hasattr(self, "timeline_origin"):
                elapsed_ms = max(
                    0, round((time.monotonic() - self.timeline_origin) * 1000))
                latency = max(0, elapsed_ms - int(end_ms))
                ends = getattr(self, "_stt_end_ms", {})
                if end_ms >= ends.get(speaker, -1):
                    self._stt_latency_ms[speaker] = latency
                    self._stt_result_at[speaker] = time.monotonic()
                    ends[speaker] = end_ms
                    self._stt_end_ms = ends
                diagnostics.record(self.session, "stt.final",
                    component="stt", provider=(metadata or {}).get("provider", self.provider), role=speaker,
                    recording_id=getattr(self,"recording_id",""),
                    start_ms=(metadata or {}).get("start_ms",0), end_ms=end_ms,
                    latency_ms=latency, result_chars=len(text))
            if speaker == REMOTE_ROLE:
                from tts_events import should_suppress_guest
                if should_suppress_guest(self.session, text):
                    self.writer.add_suppressed(speaker, text, metadata, "tts_playback_echo")
                    print("[TTS] совпавшая реплика сохранена как подавленная", flush=True)
                    return
            self.writer.add(speaker, text, metadata)
        elif kind == "capture_error":
            self._remember_capture_failure(speaker, text)
            print(f"!! [{speaker}] {text}", flush=True)
        elif kind == "error":
            print(f"!! [{speaker}] {text}", flush=True)

    def segment_handler(self, speaker: str, provider: str | None = None):
        def on_segment(kind, text, metadata=None):
            if not getattr(self, "_accept_callbacks", True):
                return
            if provider:
                metadata = {**(metadata or {}), "provider": provider}
            self._handle_segment(speaker, kind, text, metadata)
        return on_segment

    def _remember_capture_failure(self, speaker, text):
        self.capture_errors[speaker] = text
        faults = getattr(self, "_capture_faults", {})
        faults.setdefault(speaker, text)
        self._capture_faults = faults

    def make_tap(self, speaker: str):
        feed = self.feeds[speaker]

        def tap(data: bytes, rate: int, start_ms: int | None = None,
                end_ms: int | None = None) -> None:
            samples = array.array("h", data)
            peak = max((abs(sample) for sample in samples), default=0)
            self.levels[speaker] = min(1.0, peak / 32768 * 2.5)
            self._remember_signal(speaker, samples)
            if peak / 32768 >= 0.004:
                self.activity[speaker] += len(samples) / max(1, rate)
            if feed:
                if start_ms is None and end_ms is None:
                    feed(data, rate)
                else:
                    feed(data, rate, start_ms, end_ms)
        return tap

    def _remember_signal(self, speaker: str, samples: array.array) -> None:
        windows = getattr(self, "_signal_windows", None)
        lock = getattr(self, "_signal_lock", None)
        if windows is None or lock is None:
            return
        now = time.monotonic()
        clipped = sum(abs(sample) >= 32700 for sample in samples)
        with lock:
            window = windows[speaker]
            window.append((now, clipped, len(samples)))
            while window and now - window[0][0] > 5:
                window.popleft()

    def _signal_health(self) -> dict:
        result = {"me_clipping_ratio": 0.0, "guest_clipping_ratio": 0.0}
        windows = getattr(self, "_signal_windows", None)
        lock = getattr(self, "_signal_lock", None)
        if windows is None or lock is None:
            return result
        now = time.monotonic()
        with lock:
            for speaker, key in ((LOCAL_ROLE, "me_clipping_ratio"),
                                 (REMOTE_ROLE, "guest_clipping_ratio")):
                window = windows[speaker]
                while window and now - window[0][0] > 5:
                    window.popleft()
                clipped = sum(item[1] for item in window)
                total = sum(item[2] for item in window)
                result[key] = round(clipped / max(1, total), 6)
        return result

    def _stt_health(self) -> dict:
        queue_by_role = {LOCAL_ROLE: 0, REMOTE_ROLE: 0}
        dropped_by_role = {LOCAL_ROLE: 0, REMOTE_ROLE: 0}
        for position, speaker in enumerate((LOCAL_ROLE, REMOTE_ROLE)):
            if position >= len(self.recognizers):
                continue
            recognizer = self.recognizers[position]
            audio_queue = getattr(recognizer, "_audio_q", None)
            try:
                queue_by_role[speaker] = max(
                    0, int(audio_queue.qsize())
                    * int(getattr(recognizer, "audio_chunk_ms", 100)))
            except (AttributeError, TypeError, ValueError):
                queue_by_role[speaker] = 0
            dropped_by_role[speaker] = max(
                0, int(getattr(recognizer, "dropped_chunks", 0) or 0))
            captures = getattr(self, "captures", [])
            if position < len(captures):
                dropped_by_role[speaker] += captures[position].dropped_chunks
                pending = getattr(captures[position], "_audio_q", None)
                if pending is not None:
                    queue_by_role[speaker] += pending.qsize() * 100
        result_times = getattr(self, "_stt_result_at", {})
        latencies = getattr(self, "_stt_latency_ms", {})
        latest_at = max((float(value or 0) for value in result_times.values()),
                        default=0.0)
        latest_role = max(result_times, key=result_times.get) if latest_at else None
        return {
            **{f"stt_{key}":max((float(getattr(r, attribute, 0) or 0) for r in self.recognizers),default=0)
               for key,attribute in (("inflight_ms","inflight_audio_ms"),
                   ("buffered_ms","buffered_audio_ms"),("inference_ms","last_inference_ms"),
                   ("wait_ms","last_wait_ms"),("rtf","last_rtf"))},
            "stt_queue_ms": max(queue_by_role.values(), default=0),
            "stt_queue_me_ms": queue_by_role[LOCAL_ROLE],
            "stt_queue_guest_ms": queue_by_role[REMOTE_ROLE],
            "stt_dropped_me": dropped_by_role[LOCAL_ROLE],
            "stt_dropped_guest": dropped_by_role[REMOTE_ROLE],
            "stt_dropped_chunks": sum(dropped_by_role.values()),
            "stt_latency_ms": int(latencies.get(latest_role, 0) or 0),
            "stt_result_age_ms": (max(0, round((time.monotonic() - latest_at) * 1000))
                                  if latest_at else 999_999),
        }

    def _recorder_health(self) -> dict:
        errors = [str(getattr(recorder, "write_error", "") or "")
                  for recorder in self.recorders]
        return {
            "wav_backlog_ms": max(
                (int(getattr(recorder, "backlog_ms", 0) or 0)
                 for recorder in self.recorders), default=0),
            "wav_write_error": "; ".join(error for error in errors if error),
        }

    def make_recognizer(self, device_index: int, speaker: str, *,
                        provider=None, settings=None, recognizer_class=None):
        provider = provider or self.provider
        settings = settings or self.settings
        callback = self.segment_handler(speaker, provider)
        processor = None
        if self.acoustic_echo:
            processor = (self.acoustic_echo.process_capture
                         if speaker == LOCAL_ROLE else self.acoustic_echo.push_render)
        kwargs = {
            "tap": self.make_tap(speaker),
            "on_timed_segment": callback,
            "timeline_origin": self.timeline_origin,
            "audio_processor": processor,
            "diagnostic_session": self.session,
            "recording_id": getattr(self, "recording_id", ""),
        }
        if provider == "local_whisper":
            kwargs["model_name"] = settings.get("whisper_model", "small")
        return (recognizer_class or self.recognizer_class)(device_index, speaker, callback, **kwargs)

    def _deliver_audio(self, position, data, rate, start, end):
        with self._stt_lock:
            self.recognizers[position].feed_audio(data, rate, start, end)

    def make_capture(self, position, device_index, speaker):
        from audio_capture import AudioCapture
        processor = None
        if self.acoustic_echo:
            processor = (self.acoustic_echo.process_capture if speaker == LOCAL_ROLE
                         else self.acoustic_echo.push_render)
        return AudioCapture(device_index, speaker, timeline_origin=self.timeline_origin,
            tap=self.make_tap(speaker),
            sink=lambda *args: self._deliver_audio(position, *args),
            on_error=self.segment_handler(speaker), audio_processor=processor)

    def _speech_ack(self, request, state, code="ok"):
        result = {"id": request.get("id"), "recording_id": self.recording_id,
                  "state": state, "code": code}
        self._speech_result = result
        try:
            stt_switch.write(self.session / stt_switch.RESULT, result)
        except OSError:
            pass  # The levels heartbeat also carries the acknowledgement.
        diagnostics.record(self.session, "stt.switch." + state, component="stt",
            provider=self.provider, recording_id=self.recording_id,
            request_id=request.get("id", ""), code=code)

    def _request_current(self, request):
        current = stt_switch.read(self.session / stt_switch.REQUEST)
        try:
            expires = float(request.get("expires_at", 0))
        except (ValueError, TypeError):
            return False
        return (not self._closed and current.get("id") == request.get("id")
                and not current.get("cancelled") and expires > time.time())

    def _apply_speech_request(self, request):
        replacements = []
        committed = False
        try:
            key, value = request.get("key"), request.get("value")
            choices = {"speech_provider": cfg.SPEECH_CHOICES,
                       "whisper_model": cfg.WHISPER_MODEL_CHOICES}
            if key not in choices or value not in {item[0] for item in choices[key]}:
                raise ValueError("invalid STT setting")
            settings = {**cfg.load(), key: value}
            provider, backend = recognizer_backend(settings)
            if provider == "local_whisper":
                from local_whisper import get_model
                from model_manager import whisper_ready
                if not whisper_ready(settings.get("whisper_model", "small")):
                    raise RuntimeError("Whisper model is not installed")
                get_model(settings.get("whisper_model", "small"))
            # Keep both old recognizers and BOTH capture devices running during
            # imports, model prewarm, authentication and replacement startup.
            for index, speaker in ((self.mic_index, LOCAL_ROLE), (self.loop_index, REMOTE_ROLE)):
                item = self.make_recognizer(index, speaker, provider=provider,
                    settings=settings, recognizer_class=backend)
                replacements.append(item)
                item.start_external()
            with self._stt_lock:
                if not self._request_current(request):
                    raise TimeoutError("STT request expired/cancelled")
                if provider == "yandex":
                    cfg.require_cloud_processing("аудио в Yandex SpeechKit")
                cfg.save({key: value})
                previous = self.recognizers
                self.recognizers = replacements
                self.provider, self.recognizer_class, self.settings = provider, backend, settings
                committed = True
            for item in previous:
                try:
                    item.request_stop()
                except Exception:
                    pass
            # Never hold the capture routing lock while draining an old backend.
            def drain():
                for item in previous:
                    try:
                        item.finish_recognition()
                    except Exception as exc:
                        with self._stt_lock:
                            if not hasattr(self, "_retired_errors"):
                                self._retired_errors = []
                            self._retired_errors.append(exc)
            tail = threading.Thread(target=drain, daemon=True, name="stt-tail")
            with self._stt_lock:
                self._retired.append((previous, tail))
                tail.start()
            self._speech_ack(request, "applied")
        except Exception as exc:
            if committed:
                # Cleanup failure cannot undo the already active replacement.
                self._speech_ack(request, "applied", diagnostics.error_code(exc))
                return
            if not committed:
                for item in replacements:
                    try:
                        item.request_stop()
                    except Exception:
                        pass
                for item in replacements:
                    try:
                        item.finish_recognition()
                    except Exception:
                        pass  # no PCM was routed to this uncommitted backend
            self._speech_ack(request, "failed", diagnostics.error_code(exc))

    def poll_speech_switch(self):
        request = stt_switch.read(self.session / stt_switch.REQUEST)
        identity = request.get("id")
        if not identity or identity == self._last_speech_request:
            return
        self._last_speech_request = identity
        if (request.get("recording_id") != self.recording_id
                or not self.captures or not self._request_current(request)):
            return
        with self._stt_lock:
            self._retired = [(items, thread) for items, thread in self._retired if thread.is_alive()]
            if ((self._switch_thread and self._switch_thread.is_alive()) or len(self._retired) >= 4):
                self._speech_ack(request, "failed", "runtime_error")
                return
            self._switch_thread = threading.Thread(target=self._apply_speech_request,
                args=(request,), daemon=True, name="stt-switch")
            diagnostics.record(self.session, "stt.switch.requested", component="stt",
                recording_id=self.recording_id, request_id=identity, provider=self.provider)
            self._switch_thread.start()

    def _aec_snapshot(self) -> dict:
        if self.acoustic_echo:
            return self.acoustic_echo.snapshot()
        return {
            "enabled": False, "active": False, "status": "выключен",
            "backend": "off", "requested_backend": "off",
            "capture_frames": 0, "processed_frames": 0, "delay_ms": 0,
            "correlation": 0.0, "reduction_db": 0.0,
        }

    def _route_warning(self, elapsed: float, dropped_chunks: int) -> str:
        warning = ""
        if elapsed >= 30 and self.activity[REMOTE_ROLE] < 0.5:
            warning = ("канал системного звука молчит — проверьте, что в "
                       "Blatero выбран тот же выход, что в приложении встречи")
        elif (elapsed >= 120 and self.activity[LOCAL_ROLE] >= 15
              and self.activity[REMOTE_ROLE]
              / max(self.activity[LOCAL_ROLE], 0.1) < 0.02):
            warning = ("в системном канале почти нет звука — реплики встречи "
                       "могут ошибочно попадать в канал микрофона")
        if dropped_chunks:
            warning = (f"распознавание не успевает: потеряно аудиоблоков — "
                       f"{dropped_chunks}; WAV продолжает записываться")
        publication_error = getattr(getattr(self, "writer", None), "publication_error", "")
        if isinstance(publication_error, str) and publication_error:
            warning = "сохранение транскрипта прервано; WAV пишется, требуется восстановление текста"
        timing = [item.timing_warning for item in getattr(self, "captures", [])
                  if isinstance(getattr(item, "timing_warning", None), str)
                  and item.timing_warning]
        processing = [item.processing_warning for item in getattr(self, "captures", [])
                      if isinstance(getattr(item, "processing_warning", None), str)
                      and item.processing_warning]
        return "; ".join(filter(None, [warning, *dict.fromkeys(timing + processing)]))

    def _stt_label(self) -> str:
        if self.provider != "local_whisper":
            errors = [str(getattr(item, "recognition_error", "")) for item in self.recognizers
                      if getattr(item, "recognition_error", "")]
            if errors:
                return f"SpeechKit: ошибка {errors[0]} · WAV пишется"
            return "Yandex SpeechKit"
        model_name = self.settings.get("whisper_model", "small")
        model_errors = [
            str(getattr(recognizer, "model_error", "") or "")
            for recognizer in self.recognizers
            if getattr(recognizer, "model_error", None)
        ]
        if model_errors:
            return f"Whisper не загрузился · WAV пишется: {model_errors[0]}"
        readiness = [
            getattr(recognizer, "_model_ready", None)
            for recognizer in self.recognizers
        ]
        if any(event is not None and not event.is_set() for event in readiness):
            return f"Whisper {model_name} загружается · WAV уже пишется"
        return f"Whisper {model_name} локально"

    def levels_payload(self) -> dict:
        elapsed = time.monotonic() - self.timeline_origin
        aec = self._aec_snapshot()
        stt_health = self._stt_health()
        recorder_health = self._recorder_health()
        publication_error = getattr(getattr(self, "writer", None), "publication_error", "")
        if not isinstance(publication_error, str):
            publication_error = ""
        payload = {
            "ts": time.time(),
            "me": round(self.levels[LOCAL_ROLE], 3),
            "guest": round(self.levels[REMOTE_ROLE], 3),
            "rec": (bool(self.recorders) and not any(self.capture_errors.values())
                    and not recorder_health["wav_write_error"]),
            "healthy": (not any(self.capture_errors.values())
                        and not getattr(self, "_capture_faults", {})
                        and not recorder_health["wav_write_error"]),
            "error": "; ".join(dict.fromkeys(
                [error for error in self.capture_errors.values() if error] +
                ["В записи был разрыв: " + text for text in getattr(self, "_capture_faults", {}).values()])),
            "recording_has_gaps": bool(getattr(self, "_capture_faults", {})
                                       or getattr(self, "_device_gaps", [])),
            "device_gaps": list(getattr(self, "_device_gaps", [])),
            "audio_processor_failed": any(
                bool(getattr(item, "processing_warning", ""))
                for item in getattr(self, "captures", [])),
            "transcript_write_error": publication_error,
            "capture_issues": dict(getattr(self, "_capture_faults", {})),
            "pid": os.getpid(),
            "recording_id": getattr(self, "recording_id", ""),
            "stt_hot_switch": bool(getattr(self, "captures", [])),
            "speech_switch_result": getattr(self, "_speech_result", {}),
            "sec": int(self.recorders[0].seconds if self.recorders else elapsed),
            "stt": self._stt_label(),
            **stt_health,
            **recorder_health,
            **self._signal_health(),
            "echo_suppression": self.settings.get(
                "cross_channel_echo_suppression", True),
            "echoes_suppressed": self.writer.echoes_suppressed,
            "aec_enabled": aec["enabled"], "aec_active": aec["active"],
            "aec_status": aec["status"],
            "aec_backend": aec.get("backend", "correlation"),
            "aec_requested_backend": aec.get("requested_backend", "auto"),
            "aec_capture_frames": aec.get("capture_frames", 0),
            "aec_processed_frames": aec["processed_frames"],
            "aec_delay_ms": aec["delay_ms"],
            "aec_correlation": aec["correlation"],
            "aec_reduction_db": aec["reduction_db"],
            "mic": self.mic_name.replace("Микрофон (", "").rstrip(")"),
            "output": _output_name(self.loop_name),
            "me_activity": round(self.activity[LOCAL_ROLE], 1),
            "guest_activity": round(self.activity[REMOTE_ROLE], 1),
            "warning": self._route_warning(
                elapsed, stt_health["stt_dropped_chunks"]),
            "device_change": (
                self.device_monitor.snapshot()
                if getattr(self, "device_monitor", None) else {
                    "state": "ok", "event_id": 0, "roles": [],
                    "message": "Аудиоустройства без изменений",
                }),
            "elapsed_seconds": round(elapsed, 1),
            "files": (f"audio-me{self.suffix}.wav + audio-guest{self.suffix}.wav"
                      if self.recorders else "WAV выключен (--no-record)"),
        }
        watch = getattr(self, "audio_watch", None)
        payload["guard"] = (watch.observe(payload) if watch else {
            "state": "ok", "summary": "Звук под контролем", "issues": [],
            "active_count": 0,
        })
        return payload

    def _write_levels(self) -> None:
        temporary = self.session / f"{LEVELS_FILE}.tmp"
        target = self.session / LEVELS_FILE
        while not self._levels_stop.is_set():
            try:
                payload = self.levels_payload()
                temporary.write_text(json.dumps(payload), encoding="utf-8")
                os.replace(temporary, target)
                now = time.monotonic()
                if now - self._recovery_heartbeat_at >= 5:
                    session_recovery.heartbeat(
                        self.session, self.recording_id,
                        float(payload.get("elapsed_seconds", 0)))
                    self._recovery_heartbeat_at = now
            except OSError:
                pass
            for speaker in self.levels:
                self.levels[speaker] *= 0.5
            self._levels_stop.wait(0.2)

    def start_levels(self) -> None:
        self._levels_thread = threading.Thread(
            target=self._write_levels, daemon=True, name="levels")
        self._levels_thread.start()

    def start_recognizers(self) -> None:
        self.recognizers = [
            self.make_recognizer(self.mic_index, LOCAL_ROLE),
            self.make_recognizer(self.loop_index, REMOTE_ROLE),
        ]
        ordered = [self.recognizers[1], self.recognizers[0]]
        started = []
        try:
            if all(hasattr(item, "start_external") for item in ordered):
                for item in ordered:
                    item.start_external()
                    started.append(item)
                self.captures = [self.make_capture(0, self.mic_index, LOCAL_ROLE),
                                 self.make_capture(1, self.loop_index, REMOTE_ROLE)]
                self.captures[1].start()
                self.captures[0].start()
                return
            capture_first = all(
                hasattr(recognizer, "start_capture")
                and hasattr(recognizer, "start_recognition")
                for recognizer in ordered)
            if capture_first:
                # Оба WASAPI-канала уже пишут сырой WAV до prewarm Whisper.
                for recognizer in ordered:
                    recognizer.start_capture()
                    started.append(recognizer)
                for recognizer in ordered:
                    recognizer.start_recognition()
            else:
                for recognizer in ordered:
                    recognizer.start()
                    started.append(recognizer)
        except Exception as exc:
            self.capture_errors[LOCAL_ROLE] = str(exc)
            for capture in getattr(self, "captures", []):
                capture.request_stop()
            for capture in getattr(self, "captures", []):
                capture.wait_capture()
            time.sleep(0.35)
            for active in started:
                active.stop(wait=True)
            raise

    def speak_test_phrase(self, phrase: str | None) -> None:
        if not phrase:
            return
        time.sleep(1.5)
        from tts import sapi_speak
        threading.Thread(
            target=sapi_speak, args=(phrase,), daemon=True,
            name="roundtrip-test-speech").start()

    def _swap_recognizer(self, position: int, new_index: int, speaker: str,
                         channel_name: str) -> None:
        if getattr(self, "captures", []):
            # Changing a physical endpoint can reopen capture; changing STT cannot.
            current = self.captures[position]
            gap_start = time.monotonic()
            try:
                current.stop(wait=True)
            except Exception as exc:
                self._remember_capture_failure(speaker, f"{channel_name} не остановлен: {exc}")
                raise
            replacement = None
            try:
                if self.acoustic_echo:
                    self.acoustic_echo.reset()
                replacement = self.make_capture(position, new_index, speaker)
                self.captures[position] = replacement
                replacement.start()
            except Exception as switch_error:
                self._remember_capture_failure(speaker, f"{channel_name}: {switch_error}")
                # Never open a second endpoint until the failed one has stopped.
                # Keep the handle in captures if cleanup times out, so close() owns it.
                if replacement is not None:
                    try:
                        replacement.stop(wait=True)
                    except Exception as cleanup_error:
                        self._remember_capture_failure(speaker,
                            f"{channel_name} не завершён после отказа: {cleanup_error}")
                        raise RuntimeError(self.capture_errors[speaker]) from cleanup_error
                try:
                    rollback = self.make_capture(position, current.device_index, speaker)
                    self.captures[position] = rollback
                    rollback.start()
                except Exception as rollback_error:
                    self._remember_capture_failure(speaker,
                        f"{channel_name} не восстановлен: {rollback_error}")
                    raise RuntimeError(
                        f"новое устройство не открылось ({switch_error}); прежнее "
                        f"тоже не восстановилось ({rollback_error})") from rollback_error
                self.capture_errors[speaker] = ""
                raise RuntimeError(
                    f"новое устройство не открылось ({switch_error}); прежнее восстановлено") from switch_error
            gap_end = time.monotonic()
            origin = getattr(self, "timeline_origin", gap_start)
            gaps = getattr(self, "_device_gaps", [])
            gap = {"role": speaker,
                   "start_ms": max(0, round((gap_start - origin) * 1000)),
                   "end_ms": max(0, round((gap_end - origin) * 1000))}
            gaps.append(gap)
            self._device_gaps = gaps[-128:]
            diagnostics.record(getattr(self, "session", None), "capture.device_changed",
                component="capture", role=speaker, start_ms=gap["start_ms"],
                end_ms=gap["end_ms"], recording_id=getattr(self, "recording_id", ""))
            return
        current = self.recognizers[position]
        old_index = self.mic_index if position == 0 else self.loop_index
        try:
            current.stop(wait=True)
        except Exception as exc:
            self._remember_capture_failure(speaker, f"{channel_name} не остановлен: {exc}")
            raise
        replacement = None
        try:
            if self.acoustic_echo:
                self.acoustic_echo.reset()
            replacement = self.make_recognizer(new_index, speaker)
            self.recognizers[position] = replacement
            replacement.start()
        except Exception as switch_error:
            self._remember_capture_failure(speaker, f"{channel_name}: {switch_error}")
            if replacement is not None:
                try:
                    replacement.stop(wait=True)
                except Exception as cleanup_error:
                    self._remember_capture_failure(speaker,
                        f"{channel_name} не завершён после отказа: {cleanup_error}")
                    raise RuntimeError(self.capture_errors[speaker]) from cleanup_error
            try:
                rollback = self.make_recognizer(old_index, speaker)
                self.recognizers[position] = rollback
                rollback.start()
            except Exception as rollback_error:
                self._remember_capture_failure(speaker,
                    f"{channel_name} не восстановлен: {rollback_error}")
                raise RuntimeError(
                    f"новое устройство не открылось ({switch_error}); прежнее "
                    f"тоже не восстановилось ({rollback_error})") from rollback_error
            self.recognizers[position] = rollback
            self.capture_errors[speaker] = ""
            raise RuntimeError(
                f"новое устройство не открылось ({switch_error}); "
                "прежнее восстановлено") from switch_error
        self.recognizers[position] = replacement

    def refresh_microphone(self, selector, *, force: bool = False) -> bool:
        if selector == self.mic_selector and not force:
            if not self.capture_errors.get(LOCAL_ROLE):
                return True
            if time.monotonic() < getattr(self, "_capture_retry_at", {}).get(LOCAL_ROLE, 0):
                return False
        old_selector = self.mic_selector
        try:
            new_index, new_name = resolve_mic(selector)
            self._swap_recognizer(0, new_index, LOCAL_ROLE, "микрофон")
            self.mic_index = new_index
            self.mic_name = new_name
            self.mic_selector = selector
            self.capture_errors[LOCAL_ROLE] = ""
            print(f"Микрофон переключён: {new_name}", flush=True)
            return True
        except Exception as exc:
            retries = getattr(self, "_capture_retry_at", {})
            retries[LOCAL_ROLE] = time.monotonic() + 5
            self._capture_retry_at = retries
            try:
                cfg.save({"mic_device": old_selector})
            except Exception:
                pass
            print(f"!! смена микрофона не удалась: {exc}", flush=True)
            return False

    def refresh_output(self, selector, *, force: bool = False) -> bool:
        if selector == self.output_selector and not force:
            if not self.capture_errors.get(REMOTE_ROLE):
                return True
            if time.monotonic() < getattr(self, "_capture_retry_at", {}).get(REMOTE_ROLE, 0):
                return False
        try:
            new_index, new_name = pick_loopback(selector)
            self._swap_recognizer(1, new_index, REMOTE_ROLE, "системный канал")
            self.loop_index = new_index
            self.loop_name = new_name
            self.output_selector = selector
            self.capture_errors[REMOTE_ROLE] = ""
            print(f"Канал собеседника переключён: {new_name}", flush=True)
            return True
        except Exception as exc:
            retries = getattr(self, "_capture_retry_at", {})
            retries[REMOTE_ROLE] = time.monotonic() + 5
            self._capture_retry_at = retries
            if selector != self.output_selector:
                try:
                    cfg.save({"output_device": self.output_selector})
                except Exception:
                    pass
            print(f"!! смена системного выхода не удалась: {exc}", flush=True)
            return False

    def wait(self, seconds: int, stop_request: Path) -> None:
        deadline = time.monotonic() + seconds if seconds else None
        while True:
            if stop_request.exists():
                try:
                    command = stop_request.read_text(encoding="ascii").strip()
                    if json.loads(command).get("recording_id") == self.recording_id:
                        raise KeyboardInterrupt
                except (OSError, ValueError, AttributeError):
                    pass
            current = cfg.load()
            self.poll_speech_switch()
            self.refresh_microphone(current["mic_device"])
            self.refresh_output(current.get("output_device", "auto"))
            monitor = getattr(self, "device_monitor", None)
            if monitor:
                device_event = monitor.poll(
                    mic_selector=self.mic_selector,
                    output_selector=self.output_selector,
                    active_mic=self.mic_name,
                    active_output=_output_name(self.loop_name),
                )
                event_id = int(device_event.get("event_id", 0) or 0)
                if (device_event.get("state") == "returned"
                        and event_id > getattr(
                            self, "_last_device_reconnect_event", 0)):
                    roles = set(device_event.get("roles") or [])
                    reconnected = True
                    if "mic" in roles:
                        reconnected = self.refresh_microphone(
                            self.mic_selector, force=True) and reconnected
                    if "output" in roles:
                        reconnected = self.refresh_output(
                            self.output_selector, force=True) and reconnected
                    if reconnected:
                        self._last_device_reconnect_event = event_id
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                time.sleep(min(1.0, remaining))
            else:
                time.sleep(1)

    def close(self) -> None:
        with getattr(self, "_stt_lock", None) or nullcontext():
            if self._closed:
                return
            self._closed = True
        close_errors = []
        for capture in getattr(self, "captures", []):
            try:
                capture.request_stop()
            except Exception as exc:
                close_errors.append(exc)
        for capture in getattr(self, "captures", []):
            try:
                capture.wait_capture()
                error = getattr(capture, "capture_error", None)
                if isinstance(error, str) and error:
                    close_errors.append(RuntimeError(f"аудиозахват неполон: {error}"))
            except Exception as exc:
                close_errors.append(exc)
        diagnostics.record(getattr(self, "session", None), "capture.stopped", component="capture",
            recording_id=getattr(self, "recording_id", ""),
            end_ms=max(0, round((time.monotonic() - self.timeline_origin) * 1000)))
        self._levels_stop.set()
        if self._levels_thread:
            self._levels_thread.join(timeout=1)
        phased_stop = bool(self.recognizers) and all(
            hasattr(recognizer, method)
            for recognizer in self.recognizers
            for method in ("request_stop", "wait_capture", "finish_recognition")
        )
        if phased_stop:
            for recognizer in self.recognizers:
                try:
                    recognizer.request_stop()
                except Exception as exc:
                    close_errors.append(exc)
            for recognizer in self.recognizers:
                try:
                    recognizer.wait_capture()
                except Exception as exc:
                    close_errors.append(exc)
            capture_end_ms = max(
                0, round((time.monotonic() - self.timeline_origin) * 1000))
        else:
            for recognizer in self.recognizers:
                try:
                    recognizer.stop(wait=True)
                except Exception as exc:
                    close_errors.append(exc)
            capture_end_ms = max(
                0, round((time.monotonic() - self.timeline_origin) * 1000))
        # Сначала финализировать сырой WAV: даже если STT-хвост зависнет или
        # процесс затем аварийно завершат, заголовок и общая длина уже сохранены.
        for recorder in self.recorders:
            try:
                recorder.close(end_ms=capture_end_ms)
            except Exception as exc:
                close_errors.append(exc)
            error = getattr(recorder, "write_error", None)
            if isinstance(error, str) and error:
                close_errors.append(OSError(f"WAV сохранён не полностью: {error}"))
        if phased_stop:
            for recognizer in self.recognizers:
                try:
                    recognizer.finish_recognition()
                except Exception as exc:
                    close_errors.append(exc)
        watch = getattr(self, "audio_watch", None)
        if watch:
            # Recorder.close() above is the first point where a delayed write or
            # WAV header failure is guaranteed to be visible to the watchdog.
            try:
                self.levels_payload()
            except Exception as exc:
                close_errors.append(exc)
            try:
                watch.close()
            except Exception as exc:
                close_errors.append(exc)
        if self.acoustic_echo:
            try:
                self.acoustic_echo.close()
            except Exception as exc:
                close_errors.append(exc)
        for _items, thread in getattr(self, "_retired", []):
            thread.join(timeout=40)
            if thread.is_alive():
                close_errors.append(TimeoutError("старый STT-хвост не завершён; требуется дораспознавание WAV"))
        close_errors.extend(getattr(self, "_retired_errors", []))
        close_errors.extend(RuntimeError(f"аудиозахват был прерван: {text}")
                            for text in getattr(self, "_capture_faults", {}).values())
        self._accept_callbacks = False
        try:
            self.writer.close()
        except Exception as exc:
            close_errors.append(exc)
        if close_errors:
            raise close_errors[0]


def main() -> None:
    install_break_handler()
    args = parse_args()
    settings = cfg.load()
    provider, recognizer_class = recognizer_backend(settings)
    mic_selector = args.mic if args.mic is not None else settings["mic_device"]
    mic_index, mic_name = resolve_mic(mic_selector)
    output_selector = settings.get("output_device", "auto")
    loop_index, loop_name = pick_loopback(output_selector)
    session, stop_request, meta, title = session_metadata(args.session)
    record_audio = bool(settings.get("record_audio", True)) and not args.no_record
    timeline_origin = time.monotonic()
    writer, segment, suffix, transcript = create_transcript_writer(
        session, title, meta, settings, provider, record_audio)
    recorders = []
    runtime = None
    recording_id = str(writer.header["recording_id"])
    lifecycle_started = False
    failure = None
    try:
        recorders, feeds = create_recorders(
            session, suffix, mic_index, loop_index, record_audio)
        session_recovery.begin(
            session, recording_id=recording_id, segment=segment,
            transcript_file=transcript.name,
            journal_file=writer.journal_path.name,
            audio_files=[recorder.path.name for recorder in recorders],
            provider=provider)
        lifecycle_started = True
        runtime = LiveAudioRuntime(
            recognizer_class=recognizer_class, provider=provider, settings=settings,
            session=session, writer=writer, recorders=recorders, feeds=feeds,
            route=AudioRoute(
                mic_index, mic_name, mic_selector,
                loop_index, loop_name, output_selector),
            timeline_origin=timeline_origin, suffix=suffix,
            recording_id=recording_id)
        if segment > 1:
            print(f"Сегмент:     #{segment} (прошлые записи этой встречи сохранены)")
        print(f"Сессия:      {session}")
        print(f"{LOCAL_ROLE}:           [{mic_index}] {mic_name}")
        print(f"{REMOTE_ROLE}:  [{loop_index}] {loop_name}")
        print("Пишу. Ctrl+C — стоп.\n")
        runtime.start_levels()
        runtime.start_recognizers()
        diagnostics.record(session, "capture.started", component="capture",
            recording_id=recording_id, segment=segment, provider=provider)
        runtime.speak_test_phrase(args.say)
        runtime.wait(args.seconds, stop_request)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        failure = exc
    finally:
        stop_request.unlink(missing_ok=True)
        elapsed = max(0, time.monotonic() - timeline_origin)
        if lifecycle_started and failure is None:
            session_recovery.mark_finalizing(session, recording_id, elapsed)
        try:
            if runtime is not None:
                runtime.close()
            else:
                writer.close()
                for recorder in recorders:
                    recorder.close()
        except Exception as close_error:
            if failure is None:
                failure = close_error
        elapsed = max(0, time.monotonic() - timeline_origin)
        if lifecycle_started:
            if failure is None:
                session_recovery.complete(session, recording_id, elapsed)
            else:
                session_recovery.mark_interrupted(
                    session, recording_id, elapsed,
                    f"{type(failure).__name__}: {failure}")
        print(f"\nТранскрипт: {transcript}")
        if recorders:
            print(f"Аудио: {recorders[0].path.name} ({recorders[0].seconds:.0f}с) + "
                  f"{recorders[1].path.name} ({recorders[1].seconds:.0f}с) в {session}")
    if failure is not None:
        raise failure


if __name__ == "__main__":
    main()
