"""Immutable training audio: persist original WAV before browser playback."""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import re
import threading
import uuid
import wave
from pathlib import Path

import numpy as np

from pcm_resampler import resample_pcm16_mono

_LOCK = threading.RLock()
_ROLES = {'interviewer', 'candidate'}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identity(run_id: str, speaker: str, turn_id: str, text: str, voice: str) -> str:
    if not re.fullmatch(r'[0-9a-f]{32}', run_id) or speaker not in _ROLES:
        raise ValueError('неверная роль или идентификатор записи тренировки')
    return _digest(json.dumps([run_id, speaker, turn_id, text, voice],
                             ensure_ascii=False).encode('utf-8'))[:24]


def _exclusive(path: Path, data: bytes) -> None:
    if path.is_symlink():
        raise ValueError('ссылки вместо файлов записи запрещены')
    try:
        with path.open('xb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError('сохраненная запись отличается; перезапись запрещена') from None


def _pcm(wav: bytes) -> tuple[bytes, int, int, int]:
    if len(wav) > 40_000_000:
        raise ValueError('слишком большая реплика для озвучки')
    try:
        with wave.open(io.BytesIO(wav), 'rb') as src:
            rate, channels, width = src.getframerate(), src.getnchannels(), src.getsampwidth()
            frames = src.getnframes()
            if not (8000 <= rate <= 96000 and channels in (1, 2) and width == 2
                    and 0 < frames <= rate * 180 and src.getcomptype() == 'NONE'):
                raise ValueError('ожидается непустой PCM16 WAV до трех минут')
            data = src.readframes(frames)
            if len(data) != frames * channels * width:
                raise ValueError('WAV содержит не все заявленные отсчеты')
            return data, rate, channels, frames
    except (wave.Error, EOFError) as exc:
        raise ValueError('неверный WAV реплики') from exc


def cached_clip(sdir: Path, *, run_id: str, speaker: str, turn_id: str,
                text: str, voice: str) -> tuple[bytes, dict] | None:
    key = _identity(run_id, speaker, turn_id, text, voice)
    path = Path(sdir) / f'audio-training-{run_id}-{key}.wav'
    meta = path.with_suffix('.json')
    with _LOCK:
        if not meta.exists():
            return None
        if meta.is_symlink() or path.is_symlink():
            raise ValueError('ссылки вместо файлов записи запрещены')
        info = json.loads(meta.read_text(encoding='utf-8'))
        wav = path.read_bytes()
        if _digest(wav) != info.get('wav_sha256') or info.get('name') != path.name:
            raise ValueError('контрольная сумма записи тренировки не совпала')
        _pcm(wav)
        return wav, info


def save_clip(sdir: Path, *, run_id: str, speaker: str, turn_id: str,
              text: str, voice: str, wav: bytes) -> dict:
    key = _identity(run_id, speaker, turn_id, text, voice)
    data, rate, channels, frames = _pcm(wav)
    path = Path(sdir) / f'audio-training-{run_id}-{key}.wav'
    info = {'name': path.name, 'run_id': run_id, 'speaker': speaker,
            'turn_id': turn_id, 'text': text, 'voice': voice,
            'source': 'synthetic', 'wav_sha256': _digest(wav),
            'wav_bytes': len(wav),
            'pcm_sha256': _digest(data), 'sample_rate': rate, 'channels': channels,
            'frames': frames, 'duration_ms': round(frames * 1000 / rate),
            'created_at': dt.datetime.now().astimezone().isoformat(timespec='milliseconds')}
    with _LOCK:
        existing = cached_clip(sdir, run_id=run_id, speaker=speaker,
                               turn_id=turn_id, text=text, voice=voice)
        if existing:
            if existing[0] != wav:
                raise ValueError('реплика уже записана другим звуком; перезапись запрещена')
            return existing[1]
        _exclusive(path, wav)
        _exclusive(path.with_suffix('.json'),
                   json.dumps(info, ensure_ascii=False, indent=2).encode('utf-8'))
    return info


def clip_catalog(sdir: Path, run_id: str, *, strict=False) -> dict:
    result, errors = [], []
    try:
        _identity(run_id, 'interviewer', '', '', '')
    except ValueError:
        if strict:
            raise
        return {'clips': [], 'errors': [{'code': 'invalid_run', 'file': ''}]}
    for path in sorted(Path(sdir).glob(f'audio-training-{run_id}-*.json')):
        # ASR cues and streaming sidecars share this prefix, but are not clip
        # metadata. Only the exact immutable clip identity belongs to this catalog.
        if not re.fullmatch(rf'audio-training-{run_id}-[0-9a-f]{{24}}\.json', path.name):
            continue
        try:
            if path.is_symlink() or path.stat().st_size > 128 * 1024:
                raise ValueError('недопустимое описание аудио')
            info = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(info, dict) or info.get('run_id') != run_id or not info.get('turn_id'):
                raise ValueError('неверное описание аудиофайла тренировки')
            expected = _identity(run_id, str(info.get('speaker')), str(info['turn_id']),
                                 str(info.get('text', '')), str(info.get('voice', '')))
            if path.name != f'audio-training-{run_id}-{expected}.json' or not isinstance(info.get('created_at'), str):
                raise ValueError('неверное описание аудиофайла тренировки')
            audio = path.with_suffix('.wav')
            if info.get('name') != audio.name or audio.is_symlink():
                raise ValueError('неверный путь аудиофайла тренировки')
            if audio.is_file():
                # Listing never rereads/hashes PCM. Cache/assembly verify the bytes.
                result.append(info)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            if strict:
                raise ValueError(f'не удалось прочитать описание аудио: {path.name}') from exc
            errors.append({'code': 'invalid_clip_metadata', 'file': path.name})
    return {'clips': sorted(result, key=lambda item: item['created_at']), 'errors': errors}


def clips(sdir: Path, run_id: str) -> list[dict]:
    return clip_catalog(sdir, run_id, strict=True)['clips']


def snapshot_scene(sdir: Path, state: dict) -> str | None:
    if not state.get('turns'):
        return None
    body = {'state': state}
    for key, name in [('transcript', 'ai-scene-transcript.md'),
                      ('transcript_jsonl', 'ai-scene-transcript.jsonl'),
                      ('review', 'ai-scene-review.md')]:
        path = Path(sdir)/name
        body[key] = path.read_bytes().decode('utf-8') if path.exists() else ''
    data = json.dumps(body, ensure_ascii=False, indent=2).encode('utf-8')
    name = f'ai-scene-history-{_digest(data)[:32]}.json'
    _exclusive(Path(sdir)/name, data)
    visible = body['transcript'] + ('\n\n' + body['review'] if body['review'] else '')
    _exclusive((Path(sdir)/name).with_suffix('.md'), visible.encode('utf-8'))
    return name


def assemble(sdir: Path, run_id: str, turns: list[dict]) -> dict:
    """Create a labelled turn-order montage, never pretend it is live capture."""
    by_turn = {}
    for item in clips(sdir, run_id):
        by_turn.setdefault(item['turn_id'], item)
    missing = [str(t['id']) for t in turns
               if t.get('source') != 'takeover' and t['id'] not in by_turn]
    ordered = [by_turn[t['id']] for t in turns if t['id'] in by_turn]
    result = {'missing': missing, 'clip_count': len(ordered),
              'contains_human': any(t.get('source') == 'takeover' for t in turns),
              'timing': 'turn_order_with_250ms_pauses', 'name': ''}
    if not ordered:
        return result
    key = _digest(json.dumps([(c['name'], c['wav_sha256']) for c in ordered]).encode())[:16]
    name = f'audio-training-{run_id}-dialogue-{key}.wav'
    target = Path(sdir)/name
    # Stream a potentially hour-long montage to disk, not one huge BytesIO.
    # The complete file is published exclusively; partial output is never served.
    temporary = Path(sdir)/f'.training-montage-{uuid.uuid4().hex}.tmp'
    try:
        with temporary.open('xb+') as stream:
            with wave.open(stream, 'wb') as out:
                out.setnchannels(2)
                out.setsampwidth(2)
                out.setframerate(48000)
                for index, item in enumerate(ordered):
                    wav = (Path(sdir)/item['name']).read_bytes()
                    if _digest(wav) != item['wav_sha256']:
                        raise ValueError('исходный WAV изменился; сборка остановлена')
                    pcm, rate, channels, _ = _pcm(wav)
                    if channels == 2:
                        pcm = np.frombuffer(pcm, '<i2').reshape(-1, 2).astype(np.int32).mean(
                            axis=1).astype('<i2').tobytes()
                    if rate != 48000:
                        pcm, _ = resample_pcm16_mono(pcm, rate, 48000)
                    mono = np.frombuffer(pcm, '<i2')
                    stereo = np.zeros((len(mono), 2), dtype='<i2')
                    stereo[:, 0 if item['speaker'] == 'interviewer' else 1] = mono
                    if index:
                        out.writeframes(b'\0' * (12000 * 4))
                    out.writeframes(stereo.tobytes())
            stream.flush()
            os.fsync(stream.fileno())
            stream.seek(0)
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        with _LOCK:
            if target.is_symlink():
                raise ValueError('ссылка вместо монтажа запрещена')
            try:
                try:
                    os.link(temporary, target)
                except FileExistsError:
                    raise
                except OSError:
                    if os.name != 'nt':
                        raise
                    # Windows rename is exclusive too; FAT/exFAT need no hard links.
                    os.rename(temporary, target)
            except FileExistsError:
                with target.open('rb') as existing:
                    if hashlib.file_digest(existing, 'sha256').hexdigest() != digest:
                        raise ValueError('монтаж уже существует с другим звуком; перезапись запрещена')
    finally:
        temporary.unlink(missing_ok=True)
    result['name'] = name
    result['wav_sha256'] = digest
    return result
