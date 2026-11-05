"""Bounded end-to-end STT check using only the bundled synthetic phrase.

No microphone, playback, meeting files or provider switch. Heavy inference and
gRPC run in a separate process so the deadline also bounds model loading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import wave

import app_paths

PHRASE = "Проверка распознавания речи. Запись работает правильно."
PROBE_FILE = app_paths.APP_ROOT / "assets" / "stt-probe.wav"
TIMEOUT_SECONDS = 25
_STEMS = ("проверк", "распознаван", "реч", "запис", "работ", "правильн")
PCM_SHA256 = "1084a1624d403aa5ba99431abab540366c6a346c6c5de365b01827d15c748054"


def matches(text: str) -> bool:
    words = re.findall(r"[а-яё]+", str(text).casefold())
    found = {stem for stem in _STEMS if any(word.startswith(stem) for word in words)}
    return "распознаван" in found and len(found) >= 3


def load_audio() -> tuple[bytes, int, dict]:
    if PROBE_FILE.is_symlink() or PROBE_FILE.stat().st_size > 512000:
        raise ValueError("повреждён тестовый аудиофайл; восстановите файлы приложения")
    with wave.open(str(PROBE_FILE), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1, 2, 16000, "NONE"):
            raise ValueError("неверный формат тестового аудиофайла")
        pcm = source.readframes(source.getnframes())
    seconds = len(pcm) / 32000
    if not 1 <= seconds <= 10 or hashlib.sha256(pcm).hexdigest() != PCM_SHA256:
        raise ValueError("тестовая фраза пуста или повреждена")
    return pcm, 16000, {"sample_rate": 16000, "audio_seconds": round(seconds, 3),
                        "audio_sha256": hashlib.sha256(pcm).hexdigest(),
                        "audio_source": "bundled_synthetic_phrase"}


def rpc_error_message(code: str) -> str:
    return {
        "UNAUTHENTICATED": "SpeechKit отклонил ключ. Проверьте срок действия и тип API-ключа.",
        "PERMISSION_DENIED": "SpeechKit отказал в доступе. Проверьте права сервисного аккаунта.",
        "RESOURCE_EXHAUSTED": "SpeechKit: исчерпана квота или лимит запросов.",
        "UNAVAILABLE": "SpeechKit недоступен по сети. Проверьте соединение и прокси.",
        "DEADLINE_EXCEEDED": "SpeechKit не распознал тестовую фразу за отведённое время.",
        "INTERNAL": "SpeechKit вернул внутреннюю ошибку при реальном распознавании. Ключ найден, но сервис сейчас не прошёл проверку.",
        "INVALID_ARGUMENT": "SpeechKit отклонил параметры тестового аудио.",
    }.get(code, f"SpeechKit: проверка распознавания завершилась ошибкой {code}.")


def recognize_yandex(pcm: bytes, rate: int, key: str, *, timeout: float = 18) -> dict:
    import grpc
    from speechkit_stream import ENDPOINT, _session_options
    from yandex.cloud.ai.stt.v3 import stt_pb2, stt_service_pb2_grpc

    channel = grpc.secure_channel(ENDPOINT, grpc.ssl_channel_credentials())
    call = None
    final_text = ""
    def requests():
        yield _session_options(rate)  # Same options as the live recognizer.
        chunk_bytes = rate // 5  # 100 ms, PCM16 mono.
        data = pcm + b"\0" * rate * 4  # Two seconds of silence finish the phrase.
        for pos in range(0, len(data), chunk_bytes):
            yield stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=data[pos:pos + chunk_bytes]))
            time.sleep(.1)
    try:
        call = stt_service_pb2_grpc.RecognizerStub(channel).RecognizeStreaming(
            requests(), metadata=(("authorization", "Api-Key " + key),), timeout=timeout)
        for response in call:
            kind = response.WhichOneof("Event")
            if kind == "final":
                final_text = " ".join(x.text for x in response.final.alternatives)
            if kind != "final_refinement":
                continue
            text = " ".join(x.text for x in response.final_refinement.normalized_text.alternatives)
            if matches(text):
                return {"ok": True, "text": text, "event": "final_refinement"}
        return {"ok": False, "code": "NO_MATCH", "message": (
            "SpeechKit не вернул ожидаемый финальный текст тестовой фразы."
            if not final_text else "SpeechKit вернул черновой итог, но не подтвердил финальную фразу.")}
    except grpc.RpcError as error:
        code = error.code().name
        # Provider details can echo credentials; keep only a stable, useful code.
        return {"ok": False, "code": code, "message": rpc_error_message(code)}
    finally:
        if call is not None:
            call.cancel()
        channel.close()


def recognize_local(model_name: str) -> dict:
    from concurrent.futures import ThreadPoolExecutor
    # Use exactly the managed live model/profile, not a faster test-only setup.
    from local_whisper import get_model

    model = get_model(model_name)
    def recognize(_):
        segments, _info = model.transcribe(str(PROBE_FILE), language="ru", task="transcribe",
            beam_size=1, best_of=1, temperature=0, vad_filter=True,
            condition_on_previous_text=False, initial_prompt=None)
        return " ".join(segment.text.strip() for segment in segments).strip()
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as pool:
        texts = list(pool.map(recognize, (0, 1)))
    elapsed = time.monotonic() - started
    _pcm, _rate, metadata = load_audio()
    rtf = elapsed / metadata["audio_seconds"]
    matched = all(matches(text) for text in texts)
    ready = matched and rtf < 1
    return {"ok":ready, "text":texts[0], "channels_tested":2,
            "two_channel_rtf":round(rtf,3), "two_channel_ms":round(elapsed*1000),
            "code":"OK" if ready else ("LOCAL_TOO_SLOW" if matched else "NO_MATCH"),
            "message":("Whisper распознал тестовую фразу в обоих каналах быстрее реального времени."
                       if ready else ("Whisper не успевает обрабатывать два канала в реальном времени; выберите меньшую модель или другой STT."
                       if matched else "Whisper не распознал ожидаемую тестовую фразу."))}


def run(provider: str, model: str = "small", *, timeout: float = TIMEOUT_SECONDS) -> dict:
    if provider not in {"yandex", "local_whisper"}:
        return {"ok": False, "code": "UNKNOWN_PROVIDER", "message": "неизвестный движок распознавания"}
    if model not in {"base", "small", "medium"}:
        return {"ok": False, "code": "UNKNOWN_MODEL", "message": "неизвестная локальная модель"}
    started = time.monotonic()
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", provider, "--model", model],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                env={**os.environ, "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1"})
        if result.returncode or len(result.stdout) > 64000:
            raise ValueError("процесс проверки распознавания завершился с ошибкой")
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict) or type(payload.get("ok")) is not bool:
            raise ValueError("неверный ответ процесса проверки")
        # Even an erroneously successful worker cannot pass without actual words.
        if payload["ok"] and not matches(payload.get("text", "")):
            payload = {"ok": False, "code": "NO_MATCH", "message": "тестовая фраза не распознана"}
        if not payload["ok"]:
            payload.setdefault("message", "тестовая фраза не распознана")
    except subprocess.TimeoutExpired:
        payload = {"ok": False, "code": "PROBE_TIMEOUT", "message": "истекло время проверки реального распознавания"}
    except (OSError, ValueError):
        payload = {"ok": False, "code": "PROBE_FAILED", "message": "не удалось выполнить тест распознавания; проверьте файлы приложения и зависимости"}
    return {**payload, "provider": provider, "latency_ms": round((time.monotonic() - started) * 1000),
            "audio_source": "bundled_synthetic_phrase"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=("yandex", "local_whisper"), required=True)
    parser.add_argument("--model", choices=("base", "small", "medium"), default="small")
    args = parser.parse_args()
    try:
        pcm, rate, metadata = load_audio()
        if args.worker == "yandex":
            from speechkit_stream import read_api_key
            result = recognize_yandex(pcm, rate, read_api_key(require_cloud_ack=False))
        else:
            import contextlib
            # get_model prints progress; stdout must remain the single JSON reply.
            with contextlib.redirect_stdout(sys.stderr):
                result = recognize_local(args.model)
        result.update(metadata)
    except Exception:
        result = {"ok": False, "code": "PROBE_FAILED", "message": "ошибка загрузки тестовой фразы, ключа или локальной модели"}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
