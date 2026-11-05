"""Полностью локальное перераспознавание архивного WAV через faster-whisper."""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path

import local_whisper
import transcript_events


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


_AUDIO_NAME = re.compile(r"audio-(?:me|guest)(?:-\d+)?\.wav", re.IGNORECASE)
_OUTPUT_NAME = re.compile(
    r"transcript(?:-\d+)?\.local\.jsonl", re.IGNORECASE)
TRANSCRIPTION_RECIPE = "ru-meeting-v3"


def recipe_metadata() -> dict[str, object]:
    """Версия параметров STT для аудита и отбраковки старых Replay run."""
    return {
        "recipe": TRANSCRIPTION_RECIPE,
        "language": "ru",
        "task": "transcribe",
        "condition_on_previous_text": False,
    }


def _source_header(session: Path) -> dict:
    journal = session / "transcript.jsonl"
    if journal.is_file():
        records = transcript_events.read_records(journal)
        if records and records[0].get("record_type") == "recording":
            return records[0]
    raise ValueError(
        "сначала создайте transcript.jsonl или импортируйте старый Markdown")


def _backfill_paths(session: Path, audio_name: str,
                    output_name: str) -> tuple[Path, Path, Path]:
    if Path(audio_name).name != audio_name or not _AUDIO_NAME.fullmatch(audio_name):
        raise ValueError("разрешён только WAV-канал audio-me/audio-guest")
    if (Path(output_name).name != output_name
            or not _OUTPUT_NAME.fullmatch(output_name)):
        raise ValueError("имя результата должно быть transcript*.local.jsonl")
    audio = session / audio_name
    output = session / output_name
    if not audio.is_file():
        raise FileNotFoundError(f"аудиофайл не найден: {audio}")
    if output.exists():
        raise FileExistsError(f"результат уже существует: {output}")
    return audio, output, session / f"{output_name}.tmp"


def _backfill_channel(audio_name: str) -> tuple[str, str, str]:
    role = "Я" if audio_name.startswith("audio-me") else "Собеседник"
    if role == "Я":
        return role, "microphone", "mixed_capture"
    return role, "loopback", "remote_mix"


def _word_timestamp(word: object, start_ms: int) -> tuple[dict | None, float | None]:
    text = str(getattr(word, "word", "")).strip()
    if not text:
        return None, None
    word_start = max(start_ms, round(float(word.start) * 1000))
    word_end = max(word_start, round(float(word.end) * 1000))
    probability = getattr(word, "probability", None)
    confidence = float(probability) if isinstance(probability, (int, float)) else None
    return {"text": text, "start_ms": word_start, "end_ms": word_end}, confidence


def _segment_metadata(segment: object, *, source: str, speaker_id: str,
                      audio_name: str) -> tuple[str, dict] | None:
    text = str(getattr(segment, "text", "")).strip()
    if not text:
        return None
    start_ms = max(0, round(float(segment.start) * 1000))
    end_ms = max(start_ms, round(float(segment.end) * 1000))
    parsed_words = [_word_timestamp(word, start_ms)
                    for word in (getattr(segment, "words", None) or [])]
    words = [word for word, _ in parsed_words if word]
    probabilities = [value for _, value in parsed_words if value is not None]
    confidence = (sum(probabilities) / len(probabilities)
                  if probabilities else None)
    return text, {
        "start_ms": start_ms, "end_ms": end_ms, "source": source,
        "speaker_id": speaker_id, "audio_file": audio_name,
        "confidence": confidence, "timing_source": "offline_word_alignment",
        "words": words,
    }


def _append_segments(path: Path, segments, *, role: str, provider: str,
                     source: str, speaker_id: str, audio_name: str,
                     duration_ms: int = 0,
                     progress: Callable[[int, int, str], None] | None = None,
                     cancelled: Callable[[], bool] | None = None) -> int:
    count = 0
    for segment in segments:
        if cancelled and cancelled():
            raise InterruptedError("перераспознавание отменено")
        parsed = _segment_metadata(
            segment, source=source, speaker_id=speaker_id,
            audio_name=audio_name)
        if not parsed:
            continue
        text, metadata = parsed
        transcript_events.append_event(
            path, role, text, provider=provider, metadata=metadata)
        count += 1
        if progress:
            progress(int(metadata["end_ms"]), int(duration_ms), text)
        print(f"{count:04d} {metadata['start_ms'] / 1000:8.1f}s  {text[:100]}",
              flush=True)
    return count


def transcribe_audio(audio: Path, output: Path, header: dict, *,
                     audio_name: str, model_name: str = "small",
                     beam_size: int = 3,
                     progress: Callable[[int, int, str], None] | None = None,
                     cancelled: Callable[[], bool] | None = None) -> Path:
    """Распознать явно заданный WAV в новый журнал, не меняя источник."""
    audio = Path(audio).resolve()
    output = Path(output).resolve()
    if not audio.is_file():
        raise FileNotFoundError(f"аудиофайл не найден: {audio}")
    if (Path(audio_name).name != audio_name
            or not _AUDIO_NAME.fullmatch(audio_name)):
        raise ValueError("разрешён только WAV-канал audio-me/audio-guest")
    if not _OUTPUT_NAME.fullmatch(output.name):
        raise ValueError("имя результата должно быть transcript*.local.jsonl")
    if output.exists():
        raise FileExistsError(f"результат уже существует: {output}")
    if model_name not in {"tiny", "base", "small", "medium", "large-v3"}:
        raise ValueError("неизвестная модель Whisper")
    if not isinstance(beam_size, int) or not 1 <= beam_size <= 5:
        raise ValueError("beam_size должен быть целым от 1 до 5")
    if not isinstance(header, dict) or not header.get("started_at"):
        raise ValueError("в исходной сессии нет времени начала записи")
    temporary = output.with_name(output.name + ".tmp")
    temporary.unlink(missing_ok=True)
    role, source, speaker_id = _backfill_channel(audio_name)
    provider = f"local_whisper_{model_name}_offline"
    created = False
    try:
        transcript_events.create_journal(
            temporary, title=str(header.get("title") or "встреча"),
            provider=provider, segment=int(header.get("segment", 1)),
            audio_files={role: audio_name},
            started_at=str(header["started_at"]))
        created = True
        if cancelled and cancelled():
            raise InterruptedError("перераспознавание отменено")
        model = local_whisper.get_model(model_name)
        segments, info = model.transcribe(
            str(audio), language="ru", task="transcribe", beam_size=beam_size,
            vad_filter=True, word_timestamps=True,
            # Ошибка в первой короткой реплике не должна становиться контекстом
            # для следующих сегментов и каскадом менять язык всего вступления.
            condition_on_previous_text=False,
            initial_prompt=local_whisper.transcription_prompt(
                header.get("title")))
        duration = getattr(info, "duration", None)
        duration_ms = max(0, round(float(duration or 0) * 1000))
        count = _append_segments(
            temporary, segments, role=role, provider=provider,
            source=source, speaker_id=speaker_id, audio_name=audio_name,
            duration_ms=duration_ms, progress=progress, cancelled=cancelled)
        if not count:
            raise RuntimeError("Whisper не нашёл речи в аудиофайле")
        os.replace(temporary, output)
        suffix = f", длительность {float(duration):.1f} с" if duration else ""
        print(f"Готово: {output} ({count} сегментов{suffix})", flush=True)
        return output
    except Exception:
        if created:
            temporary.unlink(missing_ok=True)
        raise


def backfill(session: Path, *, audio_name: str = "audio-me.wav",
             output_name: str = "transcript.local.jsonl",
             model_name: str = "small") -> Path:
    """Создать новый журнал с точными локальными сегментами и словами."""
    session = Path(session).resolve()
    audio, output, _temporary = _backfill_paths(
        session, audio_name, output_name)
    header = _source_header(session)
    return transcribe_audio(
        audio, output, header, audio_name=audio_name, model_name=model_name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--audio", default="audio-me.wav")
    parser.add_argument("--output", default="transcript.local.jsonl")
    parser.add_argument("--model", default="small", choices=(
        "tiny", "base", "small", "medium", "large-v3"))
    args = parser.parse_args()
    backfill(args.session, audio_name=args.audio, output_name=args.output,
             model_name=args.model)


if __name__ == "__main__":
    main()
