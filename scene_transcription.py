"""Local ASR cues for saved synthetic audio; not an estimated typing animation."""
import hashlib
import json
from pathlib import Path
import threading

import training_media

_LOCK = threading.Lock()


def prewarm():
    """Only a locally installed model, while the speech provider is still preparing PCM."""
    import local_whisper
    snapshots=list((local_whisper.MODEL_ROOT/'models--Systran--faster-whisper-small'/'snapshots').glob('*/model.bin'))
    if snapshots:
        local_whisper.get_model('small',local_only=True)


def pcm_cues(pcm: bytes, rate: int) -> list[dict]:
    """Recognize a completed spoken phrase locally while later TTS is still running."""
    import numpy as np
    import local_whisper
    from pcm_resampler import resample_pcm16_mono
    with _LOCK:
        snapshots=list((local_whisper.MODEL_ROOT/'models--Systran--faster-whisper-small'/'snapshots').glob('*/model.bin'))
        if not snapshots:
            raise ValueError('для расшифровки установите Whisper small')
        if rate!=16000:
            pcm,_=resample_pcm16_mono(pcm,rate,16000)
        model=local_whisper.get_model('small',local_only=True)
        audio=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
        segments,_=model.transcribe(audio,language='ru',word_timestamps=True,
            condition_on_previous_text=False,beam_size=3)
        return [{'start':round(max(0,w.start),3),'end':round(max(w.start,w.end),3),'text':w.word}
                for segment in segments for w in (segment.words or []) if w.word.strip()]


def cue_path(audio: Path) -> Path:
    return audio.with_suffix('.asr.json')


def transcribe(audio: Path) -> dict:
    audio = Path(audio)
    if audio.is_symlink() or not audio.name.startswith('audio-training-'):
        raise ValueError('ожидается сохранённая запись тренировки')
    with _LOCK:
        raw = audio.read_bytes()
        training_media._pcm(raw)
        digest = hashlib.sha256(raw).hexdigest()
        target = cue_path(audio)
        if target.is_symlink():
            raise ValueError('ссылка вместо расшифровки')
        if target.exists():
            saved = json.loads(target.read_text(encoding='utf-8'))
            if saved.get('wav_sha256') == digest and saved.get('schema') == 'scene-asr/v1':
                return saved
        import local_whisper
        # Do not silently download a model or upload audio as a fallback.
        snapshots = list((local_whisper.MODEL_ROOT / 'models--Systran--faster-whisper-small'
                          / 'snapshots').glob('*/model.bin'))
        if not snapshots:
            raise ValueError('Для живого текста установите локальную модель Whisper small в настройках моделей.')
        model = local_whisper.get_model('small', local_only=True)
        segments, _ = model.transcribe(str(audio), language='ru', word_timestamps=True,
                                        condition_on_previous_text=False, beam_size=3)
        words = []
        for segment in segments:
            for word in segment.words or []:
                if word.word.strip():
                    words.append({'start':round(max(0,word.start),3),
                                  'end':round(max(word.start,word.end),3), 'text':word.word})
        if not words:
            raise ValueError('Локальное распознавание не выделило слова; исходный WAV сохранён.')
        if hashlib.sha256(audio.read_bytes()).hexdigest() != digest:
            raise ValueError('Аудио изменилось во время распознавания')
        value = {'schema':'scene-asr/v1','wav_sha256':digest,'words':words,
                 'source':'local-whisper-small','audio':audio.name}
        training_media._exclusive(target, json.dumps(value,ensure_ascii=False).encode('utf-8'))
        return value
