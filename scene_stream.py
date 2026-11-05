"""A bounded playback queue, independent of durable paid synthesis."""
import asyncio
import base64
import json
import queue
import threading

import training_media
import tts


class SceneStream:
    def __init__(self, sdir, clip_args):
        self.sdir=sdir
        self.args=clip_args
        self.queue=queue.Queue(maxsize=256)
        self.disconnected=threading.Event()
        self.finished=threading.Event()
        self.result=None
        self.error=None

    def emit(self, value):
        if self.disconnected.is_set():
            return
        try:
            self.queue.put_nowait(value)
        except queue.Full:
            self.disconnected.set()  # Never block capture or lose the paid response.

    def produce(self):
        try:
            cached=training_media.cached_clip(self.sdir,**self.args)
            def pcm(data):
                self.emit({'type':'pcm','data':base64.b64encode(data).decode('ascii')})
            if cached:
                wav,info=cached
                raw,rate,_,_=training_media._pcm(wav)
                self.emit({'type':'format','rate':rate,'channels':1,'cached':True,'name':info['name']})
                for index in range(0,len(raw),8192):
                    value={'type':'pcm','data':base64.b64encode(raw[index:index+8192]).decode('ascii')}
                    while not self.disconnected.is_set():
                        try:
                            self.queue.put(value,timeout=.05)
                            break
                        except queue.Full:
                            pass
                    if self.disconnected.is_set():
                        return
            else:
                key=training_media._identity(**self.args)
                self.emit({'type':'format','rate':24000,'channels':1,'cached':False,
                           'name':f"audio-training-{self.args['run_id']}-{key}.wav"})
                if self.args['voice'].endswith(':ru3'):
                    import scene_phrases
                    import scene_transcription
                    def warm():
                        try:
                            scene_transcription.prewarm()
                        except Exception:
                            pass  # Local ASR errors must never stop durable audio capture.
                    threading.Thread(target=warm,daemon=True,name='scene-asr-warm').start()
                    wav=scene_phrases.synthesize(self.sdir,self.args,pcm,self.disconnected.is_set,
                        on_words=lambda words:self.emit({'type':'words','name':f"audio-training-{self.args['run_id']}-{key}.wav",'words':words}))
                else:
                    wav=tts.gemini_scene_audio(self.args['text'],self.args['voice'],
                        self.sdir/'.tts-generations',on_pcm=pcm)
                info=training_media.save_clip(self.sdir,wav=wav,**self.args)
            self.result={'type':'complete','clip':info}
        except Exception as exc:
            self.error={'type':'error','message':str(exc)}
        finally:
            self.finished.set()

    async def events(self):
        try:
            while not self.finished.is_set() or not self.queue.empty():
                if self.disconnected.is_set():
                    yield json.dumps({'type':'error','message':'клиент не успевает получать звук; запись сохраняется'})+'\n'
                    return
                try:
                    event=self.queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(.015)
                    continue
                yield json.dumps(event,ensure_ascii=False)+'\n'
            yield json.dumps(self.error or self.result,ensure_ascii=False)+'\n'
        finally:
            self.disconnected.set()
