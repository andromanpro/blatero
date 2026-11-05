'use strict';
// PCM packets are played only after the server has flushed them to durable storage.
(() => {
  class PCMPlayer extends EventTarget {
    constructor(){
      super();const Context=window.AudioContext||window.webkitAudioContext;
      this.ctx=new Context();this.gain=this.ctx.createGain();this.gain.connect(this.ctx.destination);
      this.paused=false;this.ended=false;this.muted=false;this.volume=1;this.duration=Infinity;
      this.parts=[];this.nodes=[];this.frames=0;this.rate=24000;this.eof=false;this.started=false;
      this.timer=setInterval(()=>{if(this.started&&!this.paused){this.emit('timeupdate');this.checkEnd();}},100);
      this.ctx.addEventListener('statechange',()=>this.markStarted());
      this.ctx.resume().catch(()=>{this.needGesture=true;});
    }
    emit(type){const event=new Event(type);this.dispatchEvent(event);this['on'+type]?.(event);}
    get currentTime(){
      if(!this.parts.length)return 0;
      const now=this.ctx.currentTime;
      for(let i=this.parts.length-1;i>=0;i--){const p=this.parts[i];
        if(now>=p.at)return p.offset+Math.min(p.samples.length/this.rate,now-p.at);
      }return 0;
    }
    async play(){await this.ctx.resume();}
    markStarted(){if(!this.started&&this.parts.length&&!this.paused&&this.ctx.state==='running'){
      this.needGesture=false;this.started=true;this.emit('playing');}}
    push(raw){
      if(this.paused)return;
      if(raw.byteLength%2)throw new Error(studioUi("Неполный PCM-отсчёт"));
      const samples=new Int16Array(raw),buffer=this.ctx.createBuffer(1,samples.length,this.rate);
      const channel=buffer.getChannelData(0);for(let i=0;i<samples.length;i++)channel[i]=samples[i]/32768;
      const last=this.parts.at(-1),at=Math.max(this.ctx.currentTime+.06,last?last.at+last.samples.length/this.rate:0);
      const node=this.ctx.createBufferSource();node.buffer=buffer;node.connect(this.gain);
      this.parts.push({samples,at,offset:this.frames/this.rate});this.frames+=samples.length;
      this.nodes.push(node);node.onended=()=>this.checkEnd();node.start(at);
      this.markStarted();
      if(!this.started){this.needGesture=true;this.onblocked?.();}
    }
    complete(info){this.eof=true;this.duration=info.duration_ms/1000;this.emit('clipready');this.checkEnd();}
    checkEnd(){
      const last=this.parts.at(-1);
      if(this.eof&&!this.paused&&!this.ended&&last&&this.ctx.currentTime>=last.at+last.samples.length/this.rate){
        this.ended=true;this.paused=true;clearInterval(this.timer);this.emit('timeupdate');this.emit('ended');
        this.ctx.close();
      }
    }
    pause(){if(this.paused)return;this.paused=true;clearInterval(this.timer);
      this.nodes.forEach(n=>{try{n.stop();}catch{}});this.emit('pause');this.ctx.close();this.abort?.();}
    fail(error){this.failure=error;this.emit('error');this.pause();}
    signal(seconds,count=80){
      const bins=new Float32Array(count),first=Math.floor(seconds*this.rate),step=Math.max(1,Math.floor(this.rate*.03/count));let sum=0;
      for(let i=0;i<count;i++){const index=first+i*step;
        const part=this.parts.find(p=>index>=p.offset*this.rate&&index<p.offset*this.rate+p.samples.length);
        const sample=part?Math.abs(part.samples[index-Math.round(part.offset*this.rate)])/32768:0;
        bins[i]=sample;sum+=sample*sample;
      }return {bins,level:Math.min(1,Math.sqrt(sum/count)*3)};
    }
  }
  async function play(text,button,options){
    stopQuestionAudio();const epoch=questionAudioEpoch,session=currentInit.current_dir;
    const originalLabel=button.textContent,controller=new AbortController(),audio=new PCMPlayer();
    audio.abort=()=>controller.abort();pendingQuestionAudio={controller,button,text,originalLabel};
    studioLabel(button,"Подключаю голос…");button.classList.add('loading');
    activeQuestionAudio={audio,url:'',text,button,session,originalLabel,sceneTurnId:options.sceneTurnId,voice:options.voice};
    const sentAt=performance.now();
    const unlock=event=>{if(audio.needGesture&&audio.ctx.state!=='running'){
      event.preventDefault();event.stopImmediatePropagation();audio.play().catch(error=>audio.fail(error));}};
    button.addEventListener('click',unlock,true);
    audio.onblocked=()=>{studioLabel(button,"▶ Включить звук");button.classList.remove('loading');};
    audio.addEventListener('pause',()=>button.removeEventListener('click',unlock,true));
    const restore=()=>{button.classList.remove('loading');studioLabel(button,originalLabel);
      button.removeEventListener('click',unlock,true);
      if(activeQuestionAudio?.audio===audio)activeQuestionAudio=null;
      if(pendingQuestionAudio?.controller===controller)pendingQuestionAudio=null;};
    audio.onended=()=>{send({type:'tts_playback',phase:'end',session,text,scene_turn_id:options.sceneTurnId,voice:options.voice});
      restore();options.onDone?.();};
    audio.addEventListener('playing',()=>{studioLabel(button,"■ Остановить");button.classList.remove('loading');
      studioLabel(document.getElementById('status'),()=>({source:"{value}",values:{value:studioUi("Говорит {p0} · {p1} · старт за {p2} с",{p0:options.sceneSpeaker==='candidate'?studioUi("кандидат"):studioUi("интервьюер"),p1:audio.cached?studioUi("сохранённый WAV"):'Gemini',p2:((performance.now()-sentAt)/1000).toFixed(1)})}}));
      send({type:'tts_playback',phase:'start',session,text,scene_turn_id:options.sceneTurnId,voice:options.voice});});
    try{
      const response=await fetch('/scene-audio-stream',{method:'POST',headers:{'Content-Type':'application/json'},
        signal:controller.signal,body:JSON.stringify({text,voice:options.voice,scene_turn_id:options.sceneTurnId,scene_run_id:options.sceneRunId})});
      if(!response.ok)throw new Error(await response.text());
      const reader=response.body.getReader(),decoder=new TextDecoder();let pending='',completed=false;
      while(true){const {value,done}=await reader.read();if(done)break;
        if(epoch!==questionAudioEpoch){controller.abort();return;}
        pending+=decoder.decode(value,{stream:true});
        while(pending.includes('\n')){const end=pending.indexOf('\n'),line=pending.slice(0,end);pending=pending.slice(end+1);if(!line)continue;
          const packet=JSON.parse(line);
          if(packet.type==='error')throw new Error(packet.message);
          if(packet.type==='format'){
            audio.cached=!!packet.cached;
            if(packet.rate!==24000||packet.channels!==1)throw new Error(studioUi("Неподдерживаемый поток голоса"));
            window.BlateroSceneLive?.attach(audio,{turnId:options.sceneTurnId,runId:options.sceneRunId,name:packet.name,voice:options.voice,streaming:true});
            window.BlateroTrainingAvatars?.attachPCM(audio,t=>audio.signal(t),options.sceneSpeaker);
          }else if(packet.type==='pcm'){
            const binary=atob(packet.data),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
            audio.push(bytes.buffer);
          }else if(packet.type==='words'){
            window.BlateroSceneLive?.words(packet.name,packet.words);
          }else if(packet.type==='complete'){
            completed=true;audio.complete(packet.clip);
            if(sceneState?.run_id===options.sceneRunId){
              sceneState.audio_clips=[...(sceneState.audio_clips||[]).filter(c=>c.name!==packet.clip.name),packet.clip];renderAiScene(sceneState);
            }
          }
        }
      }
      if(!completed)throw new Error(studioUi("Поток прерван; полученный звук сохранён на сервере"));
    }catch(error){
      if(epoch!==questionAudioEpoch||error.name==='AbortError')return;
      audio.fail(error);restore();studioLabel(document.getElementById('status'),()=>({source:"{value}",values:{value:studioUi("Озвучка прервана: ")+error.message}}));
      send({type:'tts_playback',phase:'end',session,text,scene_turn_id:options.sceneTurnId,voice:options.voice});
    }
  }
  window.BlateroSceneAudio={play,PCMPlayer};
})();
