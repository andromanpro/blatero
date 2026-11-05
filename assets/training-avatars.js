'use strict';
// Analyse the saved PCM at audio.currentTime. Never reroute, mute or delay playback.
(() => {
  function readWave(buffer) {
    const view = new DataView(buffer);
    const tag = at => String.fromCharCode(...new Uint8Array(buffer, at, 4));
    if (view.byteLength < 44 || tag(0) !== 'RIFF' || tag(8) !== 'WAVE') return null;
    let channels = 0, rate = 0, width = 0, format = 0, start = 0, size = 0;
    for (let at = 12; at + 8 <= view.byteLength;) {
      const kind = tag(at), count = view.getUint32(at + 4, true), data = at + 8;
      if (count > view.byteLength - data) return null;
      if (kind === 'fmt ' && count >= 16) {
        format = view.getUint16(data, true); channels = view.getUint16(data + 2, true);
        rate = view.getUint32(data + 4, true); width = view.getUint16(data + 14, true);
      }
      if (kind === 'data') { start = data; size = count; }
      at = data + count + (count % 2);
    }
    if (format !== 1 || ![1, 2].includes(channels) || width !== 16
        || rate < 8000 || rate > 96000 || !start || size % (channels * 2)) return null;
    return {view, start, channels, rate, frames:size / (channels * 2)};
  }
  function samplesAt(wave, seconds, count = 80) {
    const bins = new Float32Array(count);
    if (!wave || !Number.isFinite(seconds) || seconds < 0) return {bins, level:0};
    const first = Math.floor(seconds * wave.rate), step = Math.max(1, Math.floor(wave.rate * .03 / count));
    let sum = 0;
    for (let i = 0; i < count; i++) {
      const frame = first + i * step;
      if (frame >= wave.frames) break;
      let sample = 0;
      for (let ch = 0; ch < wave.channels; ch++) {
        sample += Math.abs(wave.view.getInt16(wave.start + (frame * wave.channels + ch) * 2, true)) / 32768;
      }
      bins[i] = sample / wave.channels;
      sum += bins[i] * bins[i];
    }
    return {bins, level:Math.min(1, Math.sqrt(sum / count) * 3)};
  }
  globalThis.BlateroTrainingWave = {readWave, samplesAt};
  if (typeof document === 'undefined') return;
  const stage = document.getElementById('trainingStage');
  if (!stage) return;
  const $ = id => document.getElementById(id);
  const labels = {calm:'спокойный', friendly:'доброжелательный', cautious:'вдумчивый', tense:'напряжённый'};
  const colors = {calm:'#45c9eb', friendly:'#b8ed67', cautious:'#bda5ff', tense:'#ffc17b'};
  const actors = [...stage.querySelectorAll('.training-avatar')].map(el => ({
    el, role:el.dataset.speaker, canvas:el.querySelector('canvas'),
    state:el.querySelector('[data-avatar-state]'), source:el.querySelector('[data-avatar-source]'),
    mood:el.querySelector('[data-avatar-mood]'), level:0, human:false,
  }));
  const controls = {interviewer:$('studioInterviewerMood'), candidate:$('studioCandidateMood')};
  let detail = {}, playback = null, humanLevel = 0, humanLevelAt = 0, frame = null;
  let enabled = localStorage.getItem('blatero.trainingAvatars') !== 'off';
  const visible = () => enabled && detail.meetingType === 'тренировка' && !document.hidden;
  const motion = () => document.documentElement.dataset.motion !== 'off'
    && !matchMedia('(prefers-reduced-motion: reduce)').matches;
  const moods = () => Object.fromEntries(Object.entries(controls).map(([role, el]) => [role, el.value]));
  for (const [role, control] of Object.entries(controls)) {
    const remembered = localStorage.getItem('blatero.trainingMood.' + role);
    if (labels[remembered]) control.value = remembered;
    control.onchange = () => {
      localStorage.setItem('blatero.trainingMood.' + role, control.value);
      if (typeof trainingView !== 'undefined' && trainingView === 'scene'
          && detail.scene?.prepared && !detail.scene.busy) saveSceneControl();
      refresh();
    };
  }
  $('studioShowAvatars').checked = enabled;
  $('studioShowAvatars').onchange = () => {
    enabled = $('studioShowAvatars').checked;
    localStorage.setItem('blatero.trainingAvatars', enabled ? 'on' : 'off'); refresh();
  };
  function draw(actor, now) {
    const canvas = actor.canvas, box = canvas.getBoundingClientRect();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(80, box.width), h = Math.max(50, box.height);
    if (canvas.width !== Math.round(w*dpr) || canvas.height !== Math.round(h*dpr)) {
      canvas.width = Math.round(w*dpr); canvas.height = Math.round(h*dpr);
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
    const moving = motion(), t = moving ? now / 1700 : 0;
    let signal = {bins:new Float32Array(80),level:0};
    const playing = playback && playback.role === actor.role && !playback.audio.paused && !playback.audio.ended;
    if (playing) signal = playback.sampleAt?playback.sampleAt(playback.audio.currentTime):samplesAt(playback.wave, playback.audio.currentTime);
    if (actor.human && detail.recLive && now - humanLevelAt < 1100) signal.level = humanLevel;
    if (playing && (playback.audio.muted || playback.audio.volume === 0)) signal.level = 0;
    actor.level = signal.level;
    actor.el.dataset.level = signal.level.toFixed(3);
    const busy = detail.mode === 'personal' ? !!detail.training?.busy
      : !!detail.scene?.busy && !['scene_hint','scene_finish','scene_control','scene_reset'].includes(detail.scene?.operation);
    const thinking = !actor.human && busy && (detail.mode === 'personal'
      || (detail.scene?.next_speaker || 'interviewer') === actor.role);
    const state = playing ? (signal.level > .005 ? studioUi("говорит") : studioUi("пауза в реплике"))
      : actor.human && signal.level > .015 ? studioUi("сигнал микрофона")
      : thinking ? studioUi("думает…") : detail.recLive || detail.scene?.status === 'active' ? studioUi("слушает") : studioUi("готов");
    if (actor.state.textContent !== state) studioLabel(actor.state,state);
    actor.el.dataset.state = playing ? 'speaking' : thinking ? 'thinking' : 'listening';
    const mood = actor.human ? 'calm' : controls[actor.role].value;
    const fill = actor.human ? (actor.role === 'candidate' ? '#cced59' : '#79ccff') : colors[mood];
    const edge = actor.role === 'interviewer' ? '#79ccff' : '#cced59';
    const radius = Math.min(w*.32,h*.3), cx=w/2, cy=h/2;
    const gradient = ctx.createRadialGradient(cx-radius*.2,cy-radius*.2,2,cx,cy,radius*1.7);
    gradient.addColorStop(0,fill+'ce');gradient.addColorStop(.6,fill+'68');gradient.addColorStop(1,fill+'05');
    ctx.beginPath();
    for (let i=0;i<=160;i++) {
      const a=i/160*Math.PI*2;
      const base = 1+.095*Math.sin(a*3+t)+.065*Math.cos(a*5-t*.8);
      const sample = signal.bins[i%80] || signal.level*.45;
      const spike = moving ? (i%2===0 ? 1 : -.3)*Math.min(.42,sample*1.2+signal.level*.2) : 0;
      const r=radius*(base+spike), x=cx+Math.cos(a)*r, y=cy+Math.sin(a)*r;
      if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
    }
    ctx.closePath();ctx.fillStyle=gradient;ctx.shadowColor=fill;ctx.shadowBlur=18;ctx.fill();
    ctx.shadowBlur=0;ctx.strokeStyle=edge;ctx.lineWidth=1.4;ctx.stroke();
    if (thinking) {
      ctx.beginPath();ctx.arc(cx,cy,radius*1.5,t,t+Math.PI*.7);ctx.strokeStyle=fill;ctx.lineWidth=2;ctx.stroke();
    }
  }
  function tick(now) {
    frame=null;
    if(!visible())return;
    actors.forEach(actor=>draw(actor,now));
    if(motion())frame=requestAnimationFrame(tick);
  }
  function refresh() {
    stage.hidden=!enabled;
    const active = detail.meetingType === 'тренировка'
      && (detail.recLive || (detail.mode !== 'personal' && detail.scene?.status === 'active')
        || (playback && !playback.audio.paused && !playback.audio.ended));
    document.body.classList.toggle('training-live', !!active);
    stage.style.setProperty('--studio-top', Math.ceil(document.querySelector('.hint-toolbar')?.getBoundingClientRect().height || 0) + 'px');
    actors.forEach(actor=>{
      actor.human=detail.mode==='interviewer' ? actor.role==='interviewer'
        : detail.mode==='personal' ? actor.role==='candidate' : false;
      const voice = detail.scene?.[actor.role+'_voice'] || '';
      const voiceName = voice.includes(':kore:')?'Kore':voice.includes(':charon:')?'Charon':'';
      studioLabel(actor.source,()=>({source:"{value}",values:{value:actor.human?studioUi("вы · микрофон"):studioUi("ИИ")+(voiceName?' · '+voiceName:'')}}));
      studioLabel(actor.mood,()=>({source:"{value}",values:{value:actor.human?studioUi("без оценки настроения"):studioUi(labels[controls[actor.role].value])}}));
      controls[actor.role].disabled=actor.human || !!(detail.mode==='personal' ? detail.training?.busy : detail.scene?.busy);
    });
    if(frame!=null){cancelAnimationFrame(frame);frame=null;}
    tick(performance.now());
  }
  window.addEventListener('blatero:training-state', event=>{
    detail=event.detail;
    if(detail.mode!=='personal' && detail.scene?.moods) {
      for(const role of Object.keys(controls)) {
        const value=detail.scene.moods[role];if(labels[value])controls[role].value=value;
      }
    }
    refresh();
  });
  window.addEventListener('blatero:training-levels',event=>{
    humanLevel=Math.min(1,Math.max(0,Number(event.detail.me)||0));humanLevelAt=performance.now();
    if(!motion())refresh();
  });
  document.addEventListener('workspace:motion',refresh);
  document.addEventListener('visibilitychange',refresh);
  window.addEventListener('resize',refresh);
  function attachPCM(audio,sampleAt,role){
    const entry={audio,role,sampleAt};
    audio.addEventListener('playing',()=>{playback=entry;refresh();});
    const end=()=>{if(playback===entry){playback=null;refresh();}};
    for(const kind of ['pause','ended','error'])audio.addEventListener(kind,end);
  }
  window.BlateroTrainingAvatars={moods,attachPCM,attach(audio,blob,role){
    if(!['interviewer','candidate'].includes(role))return;
    const entry={audio,role,wave:null};
    blob.arrayBuffer().then(buffer=>{entry.wave=readWave(buffer);}).catch(()=>{});
    audio.addEventListener('playing',()=>{playback=entry;refresh();});
    const end=()=>{if(playback===entry){playback=null;refresh();}};
    audio.addEventListener('pause',end);audio.addEventListener('ended',end);audio.addEventListener('error',end);
  }};
  if(typeof notifyTrainingStudio==='function')notifyTrainingStudio();else refresh();
})();
