"""Озвучка: Chatterbox/Яндекс для вопросов, отдельный Gemini для ИИ-сценок.

    python tts.py "Фраза для проверки" [голос]
"""
import subprocess
import sys
import io
import wave
import hashlib
import json
import os
import time
import uuid
import re
from pathlib import Path

import requests

from speechkit_stream import read_api_key

SAMPLE_RATE = 48000
DEFAULT_VOICE = "filipp"
SCENE_GEMINI_MODEL = "google/gemini-3.8-flash-tts"
# Keys encode provider/model/style as well as voice: immutable WAV cache identity.
SCENE_GEMINI_VOICES = {"gemini38:kore:ru1": "Kore", "gemini38:charon:ru1": "Charon",
                       "gemini38:kore:ru2": "Kore", "gemini38:charon:ru2": "Charon",
                       "gemini38:kore:ru3": "Kore", "gemini38:charon:ru3": "Charon"}
SCENE_INTERVIEWER_VOICE = "gemini38:kore:ru3"
SCENE_CANDIDATE_VOICE = "gemini38:charon:ru3"
SCENE_GEMINI_STYLE = (
    "Естественная русская разговорная речь, не диктор и не реклама. "
    "Говори спокойно, с живой интонацией и короткими естественными паузами. "
    "Произноси только переданный текст, не добавляй реплик и не читай инструкции."
)


def scene_voice_options() -> list[list[str]]:
    import config as cfg
    return [[key, f"Gemini 3.8 · {name}" + (" · архивный" if key.endswith(':ru1')
             else " · целая реплика" if key.endswith(':ru2') else " · потоковые фразы")]
            for key, name in SCENE_GEMINI_VOICES.items()] + [
        [key, f"Яндекс · {label}"] for key, label in cfg.VOICE_OPTIONS if key != "auto"]


def _receipt(path: Path, value: dict) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def delete_scene_receipts(sdir: Path, wav_sha256: str | None = None) -> list[str]:
    """Remove only owned speech receipts on explicit audio/results deletion."""
    root = Path(sdir) / ".tts-generations"
    if not root.exists():
        return []
    if root.is_symlink() or root.resolve().parent != Path(sdir).resolve():
        raise ValueError("ссылка вместо каталога озвучки")
    selected = []
    for folder in root.iterdir():
        if not re.fullmatch(r"[0-9a-f]{32}", folder.name):
            continue
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("неверный каталог квитанции")
        if wav_sha256 is not None:
            try:
                info = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if info.get("wav_sha256") != wav_sha256:
                continue
        children = list(folder.iterdir())
        if any(p.name not in {"receipt.json", "receipt.tmp", "raw-response.bin", "partial.wav",
                              "generation.json", "generation-response.json"}
               or p.is_symlink() or not p.is_file() for p in children):
            raise ValueError("неожиданные файлы вместо квитанции озвучки")
        selected.append((folder, children))
    removed = []
    for folder, children in selected:
        for path in children:
            path.unlink()
            removed.append(path.relative_to(sdir).as_posix())
        folder.rmdir()
    if not any(root.iterdir()):
        root.rmdir()
    return removed


def gemini_scene_audio(text: str, voice: str, receipt_dir: Path, on_pcm=None) -> bytes:
    """Persist raw response/ID before validation; no retry or voice fallback."""
    import config as cfg
    from llm import openrouter_key
    from privacy import for_cloud

    cfg.require_cloud_processing("озвучка учебной сценки Gemini через OpenRouter")
    cloud_text = for_cloud(text)
    if voice.endswith((':ru2',':ru3')):
        from tts_pronunciation import for_speech
        cloud_text = for_speech(cloud_text)
    key = openrouter_key()
    folder = Path(receipt_dir) / uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    record = {"model": SCENE_GEMINI_MODEL, "voice": SCENE_GEMINI_VOICES[voice],
              "voice_key": voice, "style": SCENE_GEMINI_STYLE,
              "input_sha256": hashlib.sha256(cloud_text.encode("utf-8")).hexdigest(),
              "input_chars": len(cloud_text), "status": "started", "cost": None}
    target = folder / "receipt.json"
    _receipt(target, record)
    started = time.monotonic()
    valid_stream=False
    try:
        with requests.post(
            "https://openrouter.ai/api/v1/audio/speech",
            headers={"Authorization": f"Bearer {key}", "X-OpenRouter-Title": "Blatero studio"},
            json={"model": SCENE_GEMINI_MODEL, "voice": record["voice"],
                  "input": cloud_text, "instructions": SCENE_GEMINI_STYLE,
                  "response_format": "pcm"}, timeout=(15, 120), stream=True,
        ) as response:
            record.update(http_status=response.status_code,
                          generation_id=response.headers.get("X-Generation-Id"),
                          content_type=response.headers.get("Content-Type", ""))
            _receipt(target, record)  # ID survives a later interrupted stream.
            mime, *parameters = str(record['content_type']).lower().split(';')
            params=dict(p.strip().split('=',1) for p in parameters if '=' in p)
            valid_stream=(response.status_code==200 and mime.strip()=='audio/pcm'
                          and params.get('rate','24000')=='24000' and params.get('channels','1')=='1')
            raw_path = folder / "raw-response.bin"
            size = 0
            carry=b''
            with raw_path.open("xb") as stream:
                for chunk in response.iter_content(8192):
                    if chunk:
                        stream.write(chunk)
                        stream.flush()
                        os.fsync(stream.fileno())
                        size += len(chunk)
                        if size > 40_000_000:
                            raise ValueError("ответ озвучки превысил допустимый размер")
                        if valid_stream and size>24000*2*180:
                            raise ValueError('озвучка превысила три минуты')
                        record.setdefault('first_pcm_seconds',round(time.monotonic()-started,3))
                        if on_pcm and valid_stream:
                            aligned=carry+chunk
                            length=len(aligned)//2*2
                            carry=aligned[length:]
                            if length:
                                on_pcm(aligned[:length])  # Durable raw PCM precedes playback.
                stream.flush()
                os.fsync(stream.fileno())
            raw = raw_path.read_bytes()
        record.update(raw_saved=True, raw_bytes=len(raw),
                      raw_sha256=hashlib.sha256(raw).hexdigest(), status="response_saved",
                      response_seconds=round(time.monotonic() - started, 3))
        _receipt(target, record)
        if record["http_status"] != 200:
            raise ValueError(f"Gemini TTS: HTTP {record['http_status']}; ответ сохранён")
        mime, *parameters = str(record["content_type"]).lower().split(";")
        params = dict(part.strip().split("=", 1) for part in parameters if "=" in part)
        rate, channels = int(params.get("rate", "24000")), int(params.get("channels", "1"))
        if (mime.strip() != "audio/pcm" or channels != 1 or rate != 24000
                or not raw or len(raw) % 2 or len(raw) > rate * 2 * 180):
            raise ValueError("Gemini TTS вернул неподдерживаемый или неполный PCM16")
        if not any(raw):
            raise ValueError("Gemini TTS вернул тишину")
        wav = pcm_to_wav(raw, rate)
        record.update(status="validated", wav_sha256=hashlib.sha256(wav).hexdigest())
        _receipt(target, record)
        return wav
    except Exception as exc:
        raw_path=folder/'raw-response.bin'
        if raw_path.exists():
            partial=raw_path.read_bytes()
            record.update(raw_bytes=len(partial),raw_sha256=hashlib.sha256(partial).hexdigest())
            if on_pcm and valid_stream and partial:
                aligned=partial[:min(len(partial)//2*2,24000*2*180)]
                if aligned:
                    with (folder/'partial.wav').open('xb') as out:
                        out.write(pcm_to_wav(aligned,24000))
                        out.flush()
                        os.fsync(out.fileno())
        record.update(status="failed", error_type=type(exc).__name__,
                      response_seconds=round(time.monotonic() - started, 3))
        _receipt(target, record)
        raise


def synthesize(text: str, voice: str = DEFAULT_VOICE, speed: float = 1.0,
               require_cloud_ack: bool = True) -> bytes:
    resp = requests.post(
        "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize",
        headers={"Authorization":
                 f"Api-Key {read_api_key(require_cloud_ack=require_cloud_ack)}"},
        data={"text": text, "voice": voice, "speed": str(speed),
              "format": "lpcm", "sampleRateHertz": str(SAMPLE_RATE)},
        timeout=60)
    resp.raise_for_status()
    return resp.content


def pcm_to_wav(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Обернуть сырой mono PCM16 SpeechKit в WAV для браузера."""
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return output.getvalue()


def preview(voice: str) -> bytes:
    """Безопасная фиксированная реплика для проверки голоса в настройках."""
    phrase = ("Здравствуйте! Это проверка голоса Яндекс Спичкит. "
              "Если вы меня слышите, воспроизведение настроено правильно.")
    # В облако уходит только константа выше, без данных встречи или пользователя.
    return pcm_to_wav(synthesize(phrase, voice, require_cloud_ack=False))


LOCAL_PREVIEW_PHRASE = (
    "Здравствуйте. Это проверка моего локального голоса."
)


def local_preview() -> bytes:
    """Тест Chatterbox; текст и эталон не покидают компьютер."""
    import voice_clone
    return voice_clone.synthesize(LOCAL_PREVIEW_PHRASE)


def question_audio(text: str) -> tuple[bytes, str, str | None]:
    """Озвучить вопрос выбранным маршрутом.

    Возвращает (WAV, фактический провайдер, причина фолбэка). Произвольный текст
    в Yandex отправляется только при действующем ручном разрешении облака.
    """
    import config as cfg
    import voice_clone

    settings = cfg.load()
    provider = settings.get("question_voice_provider", "chatterbox_yandex")
    if provider == "chatterbox":
        return voice_clone.synthesize(text), "chatterbox", None
    local_error = None
    if provider == "chatterbox_yandex":
        cached = voice_clone.cached_audio(text)
        if cached is not None:
            return cached, "chatterbox", None
        current = voice_clone.status()
        local_error = ("локальный вопрос ещё не подготовлен"
                       if current["ready"] else
                       "локальный профиль голоса ещё не готов")
    if provider in {"yandex", "chatterbox_yandex"}:
        try:
            cfg.require_cloud_processing("текст вопроса в Yandex SpeechKit")
            voice = settings.get("voice", DEFAULT_VOICE)
            if voice == "auto":
                voice = DEFAULT_VOICE
            wav = pcm_to_wav(synthesize(text, voice, require_cloud_ack=True))
            return wav, "yandex", local_error
        except Exception as cloud_exc:
            # В гибридном режиме сохранить работоспособность без облака, пусть и
            # с ожидаемой CPU-задержкой. В режиме «только Яндекс» ошибку вернуть.
            if provider == "chatterbox_yandex" and voice_clone.status()["ready"]:
                wav = voice_clone.synthesize(text)
                return wav, "chatterbox", f"Yandex недоступен: {cloud_exc}"
            raise
    raise RuntimeError(f"неизвестный провайдер голоса вопросов: {provider}")


def scene_audio(text: str, voice: str, *,
                receipt_dir: Path | None = None) -> tuple[bytes, str, str | None]:
    """Озвучить сохранённую реплику ИИ-сценки назначенным голосом.

    ``question`` сохраняет обычный маршрут вопросов. Новые gemini38-голоса
    используют отдельный TTS OpenRouter, прежние именованные — SpeechKit.
    Облако требует ручного разрешения; WAV уже озвученных реплик не меняются.
    """
    if voice == "question":
        return question_audio(text)
    if voice in SCENE_GEMINI_VOICES:
        if receipt_dir is None:
            raise ValueError("для Gemini требуется каталог квитанций озвучки")
        return (gemini_scene_audio(text, voice, receipt_dir),
                f"OpenRouter Gemini 3.8 / {SCENE_GEMINI_VOICES[voice]}", None)
    import config as cfg

    if voice == "auto" or voice not in cfg.VOICE_CHOICES:
        raise ValueError("неизвестный голос сценки")
    cfg.require_cloud_processing("реплика учебной ИИ-сценки в Yandex SpeechKit")
    wav = pcm_to_wav(synthesize(text, voice, require_cloud_ack=True))
    return wav, f"yandex {voice}", None


def play_pcm(pcm: bytes):
    import config as cfg
    from audio_calibration import _output_device
    import pyaudiowpatch as pyaudio
    pa = pyaudio.PyAudio()
    try:
        output_index, _output_name = _output_device(
            pa, cfg.load().get("output_device", "auto"))
        stream = pa.open(format=pyaudio.paInt16, channels=1,
                         rate=SAMPLE_RATE, output=True,
                         output_device_index=output_index)
        stream.write(pcm)
        stream.stop_stream()
        stream.close()
    finally:
        pa.terminate()


# текст идёт через stdin, а не в строку команды → инъекция невозможна в принципе
SAPI_SCRIPT = (
    "Add-Type -AssemblyName System.Speech; "
    "$t = [Console]::In.ReadToEnd(); "
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "try { $s.SelectVoice('Microsoft Irina Desktop') } catch {}; "
    "$s.Speak($t)")


def sapi_speak(text: str):
    subprocess.run(["powershell", "-NoProfile", "-Command", SAPI_SCRIPT],
                   input=text, text=True, encoding="utf-8", timeout=120)


def speak(text: str, voice: str = DEFAULT_VOICE):
    try:
        play_pcm(synthesize(text, voice))
    except Exception as e:
        print(f"!! Yandex TTS отвалился ({e}) — фолбэк на SAPI", flush=True)
        sapi_speak(text)


def speak_participant(text: str) -> str:
    """Произнести реплику эмулируемого участника через системный выход."""
    import config as cfg

    settings = cfg.load()
    voice = settings.get("voice", DEFAULT_VOICE)
    if voice == "auto":
        voice = DEFAULT_VOICE
    try:
        cfg.require_cloud_processing("текст реплики SIM-участника в Yandex SpeechKit")
        play_pcm(synthesize(text, voice, require_cloud_ack=True))
        return f"Yandex {voice}"
    except Exception as exc:
        print(f"!! голос SIM-участника через Yandex недоступен ({exc}) — SAPI", flush=True)
        sapi_speak(text)
        return "SAPI Irina"


# Совместимость со старыми внешними вызовами; новый код использует общее имя.
speak_candidate = speak_participant


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    phrase = sys.argv[1] if len(sys.argv) > 1 else "Проверка нейросетевого голоса."
    speak(phrase, sys.argv[2] if len(sys.argv) > 2 else DEFAULT_VOICE)
