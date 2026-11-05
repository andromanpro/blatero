"""Provider-independent WASAPI capture. STT never owns this lifetime."""
import array
import math
import queue
import sys
import threading
import time

import pyaudiowpatch as pyaudio


class AudioCapture:
    def __init__(self, device_index, label, *, timeline_origin, tap, sink,
                 on_error, audio_processor=None):
        self.device_index = device_index
        self.label = label
        self.timeline_origin = timeline_origin
        self.tap = tap
        self.sink = sink
        self.on_error = on_error
        self.audio_processor = audio_processor
        self.capture_error = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread = None
        self._delivery_thread = None
        self._audio_q = queue.Queue(maxsize=300)
        self.dropped_chunks = 0
        self._sink_failed = False
        self._clock_offset = None
        self._next_frame = None
        self._rate = None
        self._channels = None
        self._timing_warning = False
        self.timing_warning = ""
        self.processing_warning = ""

    def _capture_pcm(self, data, time_info):
        """Place unique device samples by ADC time, not Python delivery time."""
        rate, channels = self._rate, self._channels
        if not data:
            return
        if len(data) % (2 * channels):
            raise ValueError("неполный PCM-кадр устройства")
        if channels > 1:
            samples = array.array("h", data)
            data = (array.array("h", ((samples[i] + samples[i+1]) // 2
                    for i in range(0, len(samples), 2))).tobytes()
                    if channels == 2 else array.array("h", samples[::channels]).tobytes())
        sample_count = len(data) // 2
        try:
            adc = float(time_info["input_buffer_adc_time"])
            current = float(time_info["current_time"])
            if (not math.isfinite(adc) or not math.isfinite(current)
                    or current <= 0 or adc <= 0 or adc > current + 1):
                raise ValueError("invalid device clock")
        except (KeyError, TypeError, ValueError):
            # If a driver supplies no clock, preserve every sample. Do not
            # fabricate overlap/pause from scheduling jitter. Make the loss of
            # precise cross-channel timing visible instead of silently guessing.
            if not self._timing_warning:
                self._timing_warning = True
                self.timing_warning = ("Устройство не сообщает время аудиобуфера; "
                                       "PCM сохраняется, точность выравнивания каналов снижена")
                self._notify("error", self.timing_warning)
            start_frame = self._next_frame
            if start_frame is None:
                start_frame = max(0, round((time.monotonic() - self.timeline_origin)
                                         * rate) - sample_count)
        else:
            if self._clock_offset is None:
                self._clock_offset = time.monotonic() - current
            start_frame = max(0, round((adc + self._clock_offset
                                       - self.timeline_origin) * rate))
        if self._next_frame is not None:
            start_frame = max(start_frame, self._next_frame)
        self._next_frame = start_frame + sample_count
        # Keep sub-ms precision until the recorder converts back to frames.
        # Rounding each small buffer to integer ms would add/drop 44.1-kHz PCM.
        start = start_frame * 1000 / rate
        end = self._next_frame * 1000 / rate
        self.tap(data, rate, start, end)
        try:
            self._audio_q.put_nowait((data, rate, start, end))
        except queue.Full:
            self.dropped_chunks += 1  # only STT work, never raw PCM

    def _callback(self, data, _frames, time_info, status_flags):
        try:
            if status_flags & pyaudio.paInputOverflow:
                self.capture_error = "устройство сообщило потерю входных аудиобуферов"
                self._notify("capture_error", self.capture_error)
            self._capture_pcm(data, time_info)
        except Exception as exc:
            self.capture_error = str(exc)
            self._notify("capture_error", f"канал «{self.label}» оборван: {exc}")
            self._stop.set()
            return None, pyaudio.paAbort
        return None, pyaudio.paComplete if self._stop.is_set() else pyaudio.paContinue

    def _notify(self, kind, text):
        try:
            self.on_error(kind, text)
        except Exception:
            pass

    def _deliver(self):
        while (not self._stop.is_set() or not self._audio_q.empty()
               or (self._thread and self._thread.is_alive())):
            try:
                data, rate, start, end = self._audio_q.get(timeout=0.1)
            except queue.Empty:
                continue
            processed = data
            if self.audio_processor:
                try:
                    processed = self.audio_processor(data, rate, start, end)
                    if not isinstance(processed, bytes) or len(processed) != len(data):
                        raise ValueError("invalid PCM")
                except Exception:
                    self.audio_processor = None
                    processed = data
                    self.processing_warning = "аудиофильтр отключён; STT получает исходный PCM"
                    self._notify("error", self.processing_warning)
            try:
                self.sink(processed, rate, start, end)
                self._sink_failed = False
            except Exception:
                if not self._sink_failed:
                    self._notify("error", "STT не принимает аудио; WAV продолжает записываться")
                self._sink_failed = True

    def _run(self):
        audio, stream, com = None, None, None
        try:
            if sys.platform == "win32":
                import ctypes
                apartment = ctypes.OleDLL("ole32")
                try:
                    apartment.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED
                    com = apartment  # S_OK and S_FALSE both own one COM reference.
                except OSError as exc:
                    if getattr(exc, "winerror", None) not in (-2147417850, 2147549446):
                        raise
                    # RPC_E_CHANGED_MODE: the calling thread already owns an
                    # apartment. Do not uninitialize somebody else's reference.
            audio = pyaudio.PyAudio()
            info = audio.get_device_info_by_index(self.device_index)
            rate = int(info["defaultSampleRate"])
            channels = max(1, int(info["maxInputChannels"]))
            self._rate, self._channels = rate, channels
            frames = rate // 10
            stream = audio.open(format=pyaudio.paInt16, channels=channels, rate=rate,
                                input=True, input_device_index=self.device_index,
                                frames_per_buffer=frames, start=False,
                                stream_callback=self._callback)
            if self._stop.is_set():
                return  # A late driver open must not start after the readiness deadline.
            stream.start_stream()
            self._ready.set()
            while not self._stop.wait(0.25):
                if not stream.is_active():
                    self.capture_error = "аудиопоток устройства неожиданно остановился"
                    self._notify("capture_error", self.capture_error)
                    self._stop.set()
        except Exception as exc:
            self.capture_error = str(exc)
            if not self._stop.is_set():
                self._notify("capture_error", f"канал «{self.label}» оборван: {exc}")
        finally:
            self._ready.set()
            if stream is not None:
                try:
                    stream.stop_stream()
                except Exception as exc:
                    self.capture_error = f"остановка аудиопотока: {exc}"
                    self._notify("capture_error", self.capture_error)
                try:
                    stream.close()
                except Exception as exc:
                    self.capture_error = f"закрытие аудиопотока: {exc}"
                    self._notify("capture_error", self.capture_error)
            try:
                if audio is not None:
                    try:
                        audio.terminate()
                    except Exception as exc:
                        self.capture_error = f"завершение аудиодрайвера: {exc}"
                        self._notify("capture_error", self.capture_error)
            finally:
                if com is not None:
                    com.CoUninitialize()

    def start(self):
        if self._thread is not None or self._stop.is_set():
            raise RuntimeError("повторный запуск одного аудиозахвата запрещён")
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"capture-{self.label}")
        self._thread.start()
        self._delivery_thread = threading.Thread(target=self._deliver, daemon=True,
                                                 name=f"pcm-{self.label}")
        self._delivery_thread.start()
        ready = self._ready.wait(5)
        if not ready and not self.capture_error:
            self.capture_error = "таймаут подключения аудиоустройства"
            self._notify("capture_error", f"канал «{self.label}» не открылся: {self.capture_error}")
        if not ready or self.capture_error:
            self.request_stop()
            self.wait_capture()
            raise RuntimeError(f"канал «{self.label}» не открылся: {self.capture_error or 'таймаут'}")

    def request_stop(self):
        self._stop.set()

    def wait_capture(self):
        if self._thread:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise TimeoutError("аудиозахват не завершился; WAV может быть неполным")
        if self._delivery_thread:
            self._delivery_thread.join(timeout=5)
            if self._delivery_thread.is_alive():
                raise TimeoutError("передача PCM в STT не завершилась; требуется дораспознавание")

    def stop(self, wait=True):
        self.request_stop()
        if wait:
            self.wait_capture()
