"""Потоковое распознавание SpeechKit v3 с WASAPI-устройства (мик или loopback).

Каждый экземпляр StreamingRecognizer держит один аудиоканал:
захват → очередь → gRPC-сессия SpeechKit. Сессии переоткрываются каждые
SESSION_SECONDS (лимит длительности на стороне Яндекса); очередь при этом
не останавливается. Очередь сохраняет времена исходного PCM; переполнение
и отказ распознавания учитываются отдельно от сохранности сырого WAV.
"""
import queue
import threading
import time
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from pathlib import Path

import grpc
import pyaudiowpatch as pyaudio
import runtime_diagnostics as diagnostics
from yandex.cloud.ai.stt.v3 import stt_pb2, stt_service_pb2_grpc

ENDPOINT = "stt.api.cloud.yandex.net:443"
KEY_PATH = Path.home() / ".yc-speechkit-key"
CHUNK_MS = 100
SESSION_SECONDS = 230  # переоткрываем сессию заранее, до серверного лимита


@dataclass(frozen=True)
class AudioChunk:
    data: bytes
    start_ms: float
    end_ms: float


class RpcTimeline:
    """Map provider stream offsets to the original capture clock, including gaps."""
    def __init__(self, origin_ms: float):
        self.origin_ms = origin_ms
        self._lock = threading.Lock()
        self._spans: list[tuple[float, float, float, float]] = []
        self._ends: list[float] = []
        self._sent_ms = 0.0

    def append(self, chunk: AudioChunk, sample_rate: int) -> None:
        duration = len(chunk.data) / 2 / sample_rate * 1000
        if duration <= 0:
            return
        with self._lock:
            end = self._sent_ms + duration
            self._spans.append((self._sent_ms, end, chunk.start_ms, chunk.end_ms))
            self._ends.append(end)
            self._sent_ms = end

    def capture_ms(self, relative: float, *, end: bool = False) -> int:
        relative = max(0, relative)
        with self._lock:
            if not self._spans:
                return round(self.origin_ms + relative)
            # At a discontinuity an ending word belongs to the preceding span;
            # a starting word belongs to the next one, not to the device gap.
            search = bisect_left if end else bisect_right
            index = min(search(self._ends, relative), len(self._spans) - 1)
            start, stop, capture_start, capture_end = self._spans[index]
            fraction = (relative - start) / (stop - start)
            return max(0, round(capture_start + fraction * (capture_end - capture_start)))


def read_api_key(require_cloud_ack: bool = True) -> str:
    import config as cfg
    if require_cloud_ack:
        cfg.require_cloud_processing()
    try:
        key = KEY_PATH.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        raise RuntimeError(
            f"нет ключа SpeechKit — положи API-ключ (AQVN...) в {KEY_PATH}") from None
    if not key:
        raise RuntimeError(f"файл ключа {KEY_PATH} пуст")
    return key


def _session_options(sample_rate: int) -> stt_pb2.StreamingRequest:
    return stt_pb2.StreamingRequest(
        session_options=stt_pb2.StreamingOptions(
            recognition_model=stt_pb2.RecognitionModelOptions(
                audio_format=stt_pb2.AudioFormatOptions(
                    raw_audio=stt_pb2.RawAudio(
                        audio_encoding=stt_pb2.RawAudio.LINEAR16_PCM,
                        sample_rate_hertz=sample_rate,
                        audio_channel_count=1,
                    )
                ),
                text_normalization=stt_pb2.TextNormalizationOptions(
                    text_normalization=stt_pb2.TextNormalizationOptions.TEXT_NORMALIZATION_ENABLED,
                    profanity_filter=False,
                ),
                language_restriction=stt_pb2.LanguageRestrictionOptions(
                    restriction_type=stt_pb2.LanguageRestrictionOptions.WHITELIST,
                    language_code=["ru-RU"],
                ),
                audio_processing_type=stt_pb2.RecognitionModelOptions.REAL_TIME,
            )
        )
    )


class StreamingRecognizer:
    """Потоковый STT; финальная реплика может включать временные метаданные."""

    def __init__(self, device_index: int, label: str, on_segment, tap=None,
                 on_timed_segment=None, timeline_origin: float | None = None,
                 audio_processor=None, diagnostic_session: Path | None = None,
                 recording_id: str = ""):
        self.device_index = device_index
        self.label = label
        self.on_segment = on_segment
        self.on_timed_segment = on_timed_segment
        # tap(data, rate, start_ms, end_ms): сырой mono PCM до AEC/STT.
        self.tap = tap
        self.timeline_origin = timeline_origin
        self.audio_processor = audio_processor
        self.diagnostic_session = diagnostic_session
        self.recording_id = recording_id
        # лимит ~60с звука: если gRPC завис — сбрасываем старое, не жрём память
        self._audio_q: queue.Queue = queue.Queue(maxsize=600)
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._active_call = None  # текущий gRPC-вызов, чтобы отменить при остановке
        self._api_key = read_api_key()
        self.capture_error = None
        self.recognition_error = ""
        self._recognition_failure = ""
        self._recognition_completed = False
        self.recognition_session_id = ""
        self.recognition_request_id = ""
        self.dropped_chunks = 0
        self.audio_chunk_ms = CHUNK_MS

    def _process_audio(self, data: bytes, rate: int, start_ms: int,
                       end_ms: int) -> bytes:
        """Apply an optional filter and fall back to raw PCM on failure."""
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
            self.audio_processor = None
            self.on_segment(
                "error", f"аудиофильтр отключён, используется исходный звук: {exc}")
            return data

    @staticmethod
    def _alternative_metadata(alternative, session_start_ms: int | RpcTimeline) -> dict:
        """Перевести относительные времена SpeechKit в шкалу всей записи."""
        def convert(value, *, end=False):
            value = max(0, int(value))
            if isinstance(session_start_ms, RpcTimeline):
                return session_start_ms.capture_ms(value, end=end)
            return session_start_ms + value
        start_ms = convert(alternative.start_time_ms)
        end_ms = max(start_ms, convert(alternative.end_time_ms, end=True))
        words = []
        for word in alternative.words:
            word_start = convert(word.start_time_ms)
            words.append({
                "text": word.text,
                "start_ms": word_start,
                "end_ms": max(word_start, convert(word.end_time_ms, end=True)),
            })
        metadata = {
            "start_ms": start_ms,
            "end_ms": end_ms,
            "provider": "yandex",
            "timing_source": "provider",
            "words": words,
        }
        # SpeechKit v3 документирует Alternative.confidence как пока не
        # используемое поле: protobuf возвращает 0, хотя это не оценка качества.
        confidence = float(alternative.confidence)
        if 0.0 < confidence <= 1.0:
            metadata["confidence"] = confidence
        return metadata

    # --- захват ---------------------------------------------------------
    def _open_capture(self, audio):
        info = audio.get_device_info_by_index(self.device_index)
        channels = max(1, int(info["maxInputChannels"]))
        rate = int(info["defaultSampleRate"])
        frames = int(rate * CHUNK_MS / 1000)
        self.sample_rate = rate
        stream = audio.open(
            format=pyaudio.paInt16, channels=channels, rate=rate, input=True,
            input_device_index=self.device_index, frames_per_buffer=frames)
        return stream, channels, rate, frames

    def _mono_chunk(self, data: bytes, channels: int) -> bytes:
        if channels == 2:
            return self._downmix(data)
        if channels > 2:
            return self._first_channel(data, channels)
        return data

    def _queue_audio(self, data: bytes, start_ms: float | None = None,
                     end_ms: float | None = None) -> None:
        if not data:
            return
        chunk = (AudioChunk(data, float(start_ms), float(end_ms))
                 if start_ms is not None and end_ms is not None else data)
        try:
            self._audio_q.put_nowait(chunk)
            return
        except queue.Full:
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                pass
        self._audio_q.put_nowait(chunk)
        self.dropped_chunks += 1
        if self.dropped_chunks == 1 or self.dropped_chunks % 100 == 0:
            self.on_segment(
                "error", "SpeechKit не успевает: потеряно "
                f"аудиоблоков — {self.dropped_chunks}")

    def _capture_chunk(self, stream, channels: int, rate: int,
                       frames: int) -> None:
        data = self._mono_chunk(
            stream.read(frames, exception_on_overflow=False), channels)
        end_ms = max(0, round((time.monotonic() - self.timeline_origin) * 1000))
        duration_ms = round(len(data) / 2 / max(1, rate) * 1000)
        start_ms = max(0, end_ms - duration_ms)
        if self.tap:
            self.tap(data, rate, start_ms, end_ms)
        self._queue_audio(self._process_audio(data, rate, start_ms, end_ms), start_ms, end_ms)

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
            # устройство отвалилось/занято → фиксируем, чтобы не изображать запись
            self.capture_error = str(exc)
            if not self._stop.is_set():
                self.on_segment(
                    "capture_error", f"канал «{self.label}» оборван: {exc}")
        finally:
            self._capture_ready.set()
            self._close_capture(audio, stream)

    @staticmethod
    def _downmix(stereo: bytes) -> bytes:
        import array
        samples = array.array("h", stereo)
        mono = array.array("h", ((samples[i] + samples[i + 1]) // 2
                                 for i in range(0, len(samples), 2)))
        return mono.tobytes()

    @staticmethod
    def _first_channel(interleaved: bytes, channels: int) -> bytes:
        import array
        s = array.array("h", interleaved)
        return array.array("h", s[::channels]).tobytes()

    # --- gRPC-сессии ----------------------------------------------------
    def _request_gen(self, deadline: float, timeline: RpcTimeline | None = None):
        yield _session_options(self.sample_rate)
        # WASAPI loopback не отдаёт кадров, пока в колонках тишина — подкачиваем
        # нулевые чанки, иначе SpeechKit не увидит конца фразы и уморит сессию.
        # Таймлайн SpeechKit должен идти с той же скоростью, что WAV/wall-clock:
        # ожидание очереди длится 300 мс, значит и заполнитель равен 300 мс.
        silence = b"\x00\x00" * int(self.sample_rate * 0.3)
        while (not self._stop.is_set() or not self._audio_q.empty()) and time.monotonic() < deadline:
            try:
                item = self._audio_q.get(timeout=0.3)
            except queue.Empty:
                if self._stop.is_set():
                    break
                item = silence
            if isinstance(item, AudioChunk):
                chunk = item
            else:
                duration = len(item) / 2 / self.sample_rate * 1000
                origin = getattr(self, "timeline_origin", None)
                end = ((time.monotonic() - origin) * 1000 if origin is not None
                       else (timeline.origin_ms + duration if timeline else duration))
                chunk = AudioChunk(item, max(0, end - duration), max(duration, end))
            if timeline is not None:
                timeline.append(chunk, self.sample_rate)
            yield stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=chunk.data))

    def _handle_response(self, response, session_start_ms: int | RpcTimeline) -> None:
        # session_uuid is a sibling of the Event oneof, not one of its variants.
        session = getattr(response, "session_uuid", None)
        if session is not None:
            if session.uuid:
                self.recognition_session_id = session.uuid[:100]
            if session.user_request_id:
                self.recognition_request_id = session.user_request_id[:100]
        kind = response.WhichOneof("Event")
        if kind == "partial" and response.partial.alternatives:
            self.on_segment("partial", response.partial.alternatives[0].text)
            return
        if kind == "final" and response.final.alternatives:
            self.on_segment("final", response.final.alternatives[0].text)
            return
        if kind != "final_refinement":
            return
        alternatives = response.final_refinement.normalized_text.alternatives
        if not alternatives:
            return
        self.recognition_error = ""
        alternative = alternatives[0]
        detail = self._alternative_metadata(alternative, session_start_ms)
        if self.on_timed_segment:
            self.on_timed_segment("refined", alternative.text, detail)
        else:
            self.on_segment("refined", alternative.text)

    def _handle_rpc_error(self, error: grpc.RpcError) -> None:
        expected = error.code() in (
            grpc.StatusCode.CANCELLED, grpc.StatusCode.DEADLINE_EXCEEDED)
        if self._stop.is_set() or expected:
            return
        self.recognition_error = error.code().name
        diagnostics.record(getattr(self,"diagnostic_session",None), "stt.rpc_error",
            component="stt", provider="yandex", role=getattr(self,"label",""),
            recording_id=getattr(self,"recording_id",""), code=self.recognition_error,
            session_id=getattr(self,"recognition_session_id",""),
            request_id=getattr(self,"recognition_request_id",""))
        detail = str(error.details() or "")
        if getattr(self, "_api_key", ""):
            detail = detail.replace(self._api_key, "[KEY]")
        reference = ", ".join(value for value in (
            getattr(self, "recognition_session_id", ""),
            getattr(self, "recognition_request_id", "")) if value)
        if reference:
            detail += f" [SpeechKit session/request: {reference}]"
        self.on_segment("error", f"{error.code()}: {detail}")
        time.sleep(1)

    def _run_recognition_session(self, credentials, metadata) -> None:
        self.recognition_session_id = ""
        self.recognition_request_id = ""
        channel = grpc.secure_channel(ENDPOINT, credentials)
        started = time.monotonic()
        diagnostics.record(getattr(self,"diagnostic_session",None), "stt.rpc_started",
            component="stt", provider="yandex", role=getattr(self,"label",""),
            recording_id=getattr(self,"recording_id",""))
        call = None
        try:
            stub = stt_service_pb2_grpc.RecognizerStub(channel)
            deadline = time.monotonic() + SESSION_SECONDS
            session_start_ms = max(0, round(
                (time.monotonic() - self.timeline_origin) * 1000))
            timeline = RpcTimeline(session_start_ms)
            call = stub.RecognizeStreaming(
                self._request_gen(deadline, timeline), metadata=metadata,
                timeout=SESSION_SECONDS + 30)
            self._active_call = call
            for response in call:
                self._handle_response(response, timeline)
        except grpc.RpcError as error:
            self._handle_rpc_error(error)
        except Exception as error:
            self._recognition_failed(error)
            raise
        finally:
            self._active_call = None
            if call is not None:
                try:
                    call.cancel()
                except Exception:
                    pass
            channel.close()
            diagnostics.record(getattr(self,"diagnostic_session",None), "stt.rpc_finished",
                component="stt", provider="yandex", role=getattr(self,"label",""),
                recording_id=getattr(self,"recording_id",""),
                duration_ms=round((time.monotonic()-started)*1000),
                code=getattr(self,"recognition_error","") or "ok",
                session_id=getattr(self,"recognition_session_id",""),
                request_id=getattr(self,"recognition_request_id",""))

    def _recognize_loop(self):
        try:
            credentials = grpc.ssl_channel_credentials()
            metadata = (("authorization", f"Api-Key {self._api_key}"),)
            while not self._stop.is_set() or not self._audio_q.empty():
                self._run_recognition_session(credentials, metadata)
            self._recognition_completed = True
        except Exception as error:
            self._recognition_failed(error)

    def _recognition_failed(self, error: Exception) -> None:
        if getattr(self, "_recognition_failure", ""):
            return
        self._recognition_failure = diagnostics.error_code(error)
        self.recognition_error = self._recognition_failure
        diagnostics.record(getattr(self, "diagnostic_session", None), "stt.rpc_error",
            component="stt", provider="yandex", role=getattr(self, "label", ""),
            recording_id=getattr(self, "recording_id", ""), code=self.recognition_error)
        try:
            self.on_segment("error", "SpeechKit прервал распознавание; "
                            "WAV сохраняется, требуется дораспознавание")
        except Exception:
            pass  # Publication may itself be the failed component.

    # --- управление -----------------------------------------------------
    def start(self):
        if self.timeline_origin is None:
            self.timeline_origin = time.monotonic()
        self._capture_ready = threading.Event()
        cap = threading.Thread(target=self._capture_loop, daemon=True,
                               name=f"cap-{self.label}")
        cap.start()
        if not self._capture_ready.wait(timeout=5):
            self._stop.set()
            raise RuntimeError(f"канал «{self.label}» не открылся за 5 секунд")
        if self.capture_error:
            self._stop.set()
            cap.join(timeout=1)
            raise RuntimeError(f"канал «{self.label}» не открылся: {self.capture_error}")
        rec = threading.Thread(target=self._recognize_loop, daemon=True,
                               name=f"rec-{self.label}")
        rec.start()
        self._threads = [cap, rec]

    def request_stop(self) -> None:
        # _stop.set() завершает генератор аудио → серверу уходит half-close, и он
        # успевает вернуть последний final_refinement (единственное, что пишется в
        # транскрипт).
        self._stop.set()

    def start_external(self) -> None:
        """Consume PCM without opening/closing any audio device."""
        self.sample_rate = 16000
        self._external_resampler = None
        self._external_rate = None
        rec = threading.Thread(target=self._recognize_loop, daemon=True,
                               name=f"stt-{self.label}")
        self._threads = [None, rec]
        rec.start()

    def feed_audio(self, data: bytes, rate: int, start_ms: int, end_ms: int):
        if self._stop.is_set() or getattr(self, "_recognition_failure", ""):
            return
        from pcm_resampler import resample_pcm16_mono
        if rate != self._external_rate:
            self._external_resampler = None
            self._external_rate = rate
        data, self._external_resampler = resample_pcm16_mono(
            data, rate, self.sample_rate, self._external_resampler)
        self._queue_audio(data, start_ms, end_ms)

    def wait_capture(self) -> None:
        if self._threads and self._threads[0] is not None:
            self._threads[0].join(timeout=3)

    def finish_recognition(self) -> None:
        rec = self._threads[1] if len(self._threads) > 1 else None
        if rec is not None:
            rec.join(timeout=3)  # штатный half-close + последний refinement
        incomplete = rec is not None and rec.is_alive()
        call = self._active_call
        if call is not None and incomplete:  # только зависший сервер — аварийный cancel
            try:
                call.cancel()
            except Exception:
                pass
        if incomplete:
            rec.join(timeout=3)
            raise TimeoutError("SpeechKit не подтвердил завершение хвоста; "
                               "требуется дораспознавание исходного WAV")
        if (getattr(self, "_recognition_failure", "")
                or (rec is not None and not getattr(self, "_recognition_completed", False))):
            raise RuntimeError("SpeechKit прервал распознавание; "
                               "требуется дораспознавание исходного WAV")

    def stop(self, wait: bool = False):
        self.request_stop()
        if wait:
            self.wait_capture()
        self.finish_recognition()
