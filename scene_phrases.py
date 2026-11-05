"""Sentence pipeline for an upstream that buffers Gemini speech until synthesis ends."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import threading

import training_media
import tts


def phrases(text):
    remaining=' '.join(text.split())
    result=[]
    while remaining:
        limit=125 if not result else 350
        if len(remaining)<=limit:
            result.append(remaining)
            break
        candidates=[m.end() for m in re.finditer(r'[.!?;:]\s+',remaining[:limit+1]) if m.end()>=40]
        if not candidates:
            candidates=[m.end() for m in re.finditer(r',\s+',remaining[:limit+1]) if m.end()>=40]
        end=candidates[-1] if candidates else remaining.rfind(' ',0,limit)
        if end<1:
            end=limit
        result.append(remaining[:end].strip())
        remaining=remaining[end:].strip()
    return result


def synthesize(sdir, args, on_pcm, cancelled, on_words=None):
    key=training_media._identity(**args)
    folder=Path(sdir)/'.scene-audio-parts'/key
    if (folder.is_symlink() or folder.parent.is_symlink()
            or folder.parent.resolve().parent!=Path(sdir).resolve()):
        raise ValueError('ссылка вместо частей озвучки')
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/'manifest.json'
    if target.is_symlink():
        raise ValueError('ссылка вместо описания озвучки')
    texts=phrases(args['text'])
    manifest=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {
        'schema':'scene-phrases/v1','parts':{},'clip_name':f"audio-training-{args['run_id']}-{key}.wav"}
    guard=threading.Lock()
    def save():
        temporary=folder/'manifest.tmp'
        if temporary.is_symlink():
            raise ValueError('ссылка вместо временного описания')
        temporary.write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
        os.replace(temporary,target)
    def part(index):
        text=texts[index]
        path=folder/f'part-{index:03d}.wav'
        text_hash=hashlib.sha256(text.encode()).hexdigest()
        with guard:
            known=manifest['parts'].get(str(index))
        if known:
            if path.is_symlink() or known['text_sha256']!=text_hash:
                raise ValueError('часть озвучки изменилась')
            wav=path.read_bytes()
            if hashlib.sha256(wav).hexdigest()!=known['wav_sha256']:
                raise ValueError('контрольная сумма части озвучки не совпала')
            return wav,False
        streamed=index==0
        if cancelled():
            raise ValueError('прослушивание остановлено до запроса следующей части')
        wav=tts.gemini_scene_audio(text,args['voice'],Path(sdir)/'.tts-generations',
                                  on_pcm=on_pcm if streamed else lambda _data:None)
        training_media._exclusive(path,wav)
        with guard:
            manifest['parts'][str(index)]={'text_sha256':text_hash,'wav_sha256':hashlib.sha256(wav).hexdigest()}
            save()
        return wav,streamed
    raw=[]
    all_words=[]
    asr_enabled=on_words is not None
    seconds=0
    def recognize(index,wav,pcm,rate,offset):
        nonlocal asr_enabled
        if not asr_enabled:
            return
        try:
            import scene_transcription
            cue_file=folder/f'part-{index:03d}.asr.json'
            if cue_file.is_symlink():
                raise ValueError('ссылка вместо расшифровки')
            if cue_file.exists():
                saved=json.loads(cue_file.read_text(encoding='utf-8'))
                if saved.get('wav_sha256')!=hashlib.sha256(wav).hexdigest():
                    raise ValueError('расшифровка относится к другой части')
                local=saved['words']
            else:
                local=scene_transcription.pcm_cues(pcm,rate)
                training_media._exclusive(cue_file,json.dumps({'words':local,
                    'wav_sha256':hashlib.sha256(wav).hexdigest()},ensure_ascii=False).encode())
            words=[{**word,'start':round(word['start']+offset,3),
                           'end':round(word['end']+offset,3)} for word in local]
            all_words.extend(words)
            on_words(words)
        except Exception as exc:
            with guard:
                manifest['asr_error']=type(exc).__name__
            asr_enabled=False  # No hidden model download/cloud fallback.
    try:
        with ThreadPoolExecutor(max_workers=2,thread_name_prefix='scene-phrase') as pool, \
             ThreadPoolExecutor(max_workers=1,thread_name_prefix='scene-asr') as asr:
            futures={i:pool.submit(part,i) for i in range(min(2,len(texts)))}
            for index in range(len(texts)):
                wav,streamed=futures[index].result()
                pcm,rate,channels,_=training_media._pcm(wav)
                if rate!=24000 or channels!=1:
                    raise ValueError('неверный PCM части озвучки')
                raw.append(pcm)
                if not streamed:
                    for offset in range(0,len(pcm),8192):
                        on_pcm(pcm[offset:offset+8192])
                if cancelled():
                    raise ValueError('прослушивание остановлено; готовые части сохранены')
                following=index+2
                if following<len(texts):
                    futures[following]=pool.submit(part,following)
                if asr_enabled:
                    asr.submit(recognize,index,wav,pcm,rate,seconds)
                seconds+=len(pcm)/(rate*2)
        wav=tts.pcm_to_wav(b''.join(raw),24000)
        training_media._pcm(wav)
        manifest.update(status='complete',wav_sha256=hashlib.sha256(wav).hexdigest())
        if asr_enabled and all_words:
            cue=Path(sdir)/Path(manifest['clip_name']).with_suffix('.asr.json')
            value={'schema':'scene-asr/v1','wav_sha256':manifest['wav_sha256'],'words':all_words,
                   'source':'local-whisper-small-phrases','audio':manifest['clip_name']}
            training_media._exclusive(cue,json.dumps(value,ensure_ascii=False).encode())
        save()
        return wav
    except Exception:
        manifest['status']='partial'
        save()
        raise


def delete_parts(sdir, clip_name=None):
    root=Path(sdir)/'.scene-audio-parts'
    if not root.exists():
        return []
    if root.is_symlink() or root.resolve().parent!=Path(sdir).resolve():
        raise ValueError('ссылка вместо частей озвучки')
    selected=[]
    for folder in root.iterdir():
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r'[0-9a-f]{24}',folder.name):
            raise ValueError('неверная папка частей озвучки')
        manifest_path=folder/'manifest.json'
        if manifest_path.is_symlink():
            raise ValueError('ссылка вместо описания частей')
        manifest=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
        if clip_name and manifest.get('clip_name')!=clip_name:
            continue
        children=list(folder.iterdir())
        if any(p.is_symlink() or not p.is_file() or not (
                p.name in {'manifest.json','manifest.tmp'} or re.fullmatch(r'part-[0-9]{3}(?:\.wav|\.asr\.json)',p.name)) for p in children):
            raise ValueError('неожиданные файлы частей озвучки')
        selected.append((folder,manifest,children))
    removed=[]
    for folder,manifest,children in selected:
        for info in manifest.get('parts',{}).values():
            removed+=tts.delete_scene_receipts(sdir,info['wav_sha256'])
        for path in children:
            path.unlink()
            removed.append(path.relative_to(sdir).as_posix())
        folder.rmdir()
    if not any(root.iterdir()):
        root.rmdir()
    return removed
