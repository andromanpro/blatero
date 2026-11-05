let ws, outbox = [], currentBank = [], calendarState = null;
let currentMeetingType = "встреча", meetingTypeOptions = [], pendingStartMode = null;
let speakerLabels = {"Я":"Я", "Собеседник":"Собеседник"};
let emulationEnabled = false, emulationRole = "собеседник";
let setupStep = 1, setupMode = null, setupContour = "work";
let setupProbeResult = null, currentInit = null;
let setupProbeRequest = null;
let promptCatalog = [], selectedPromptKey = null, transcriptAdapters = [];
let calibrationBypassed = false;
let trainingState = null, trainingStartPending = false, trainingAutoQuestionId = null;
let sceneState = null, sceneAutoTurnId = null;
let sceneStartPending = false;
let competencyPacks = [];
let trainingView = ["scene", "speech"].includes(localStorage.getItem("blatero.trainingView"))
  ? localStorage.getItem("blatero.trainingView") : "personal";
let trainingStudioMode = localStorage.getItem("blatero.trainingMode") || (trainingView === "scene" ? "ai" : "personal");
if (!["personal", "interviewer", "ai", "speech"].includes(trainingStudioMode)) trainingStudioMode = "personal";
let archiveItems = [], replaySession = null, replayTimer = null;
let replayEpoch = 0, replayListTicket = 0, replayTimelineTicket = 0, replayCompareTicket = 0;
const memoryManualFields = ["memoryAddText","memoryAddOwner","memoryAddDue"];
const memoryManualDrafts = new Map();
let memoryManualPending = null;
let replaySelected = new Set(), replayCompareTimer = null;
let replayRunsState = [], replayTimelineData = null, replayTimelineActive = -1;
let currentContour = "work", feedExpanded = false;
let feedHistoryLines = [], feedHistorySession = "";
let lastAudioDeviceEventId = 0;
let currentReportReview = {state:"none",issues:[],requires_review:false};
let workspacePrivacyReview = null;
let workspaceVisualOptions = new Map();
let currentHasTranscript = false, currentPreflightState = "not_run";
let currentMeetingResult = {has_final:false, has_draft:false};
let reportDraftSaved = null, reportDraftLoading = false;
let transcriptEditorState = {utterances:[],total:0,shown:0,truncated:false};
let transcriptEditorFocusMs = null, transcriptEditorReturnToReview = false;
let transcriptEditorAudioTimer = null;
let qualityCatalog = {items:[]}, qualityReference = null, qualityAudioTimer = null;
let guardCalibrationState = null;
let memoryState = {configured:false,scopes:[],entries:[],draft:{entries:[]}};
let modelManagerState = {items:[],busy:""};
let updateManagerState = {busy:false}, selectedRelease = null;
let recoveryState = {state:"ready",items:[]}, recoveryPromptSignature = "";
let lifecycleState = {packages:[],retention_policy:{},retention:{items:[]}};
let lifecycleSession = "", lifecyclePurgePreview = null;
let pinnedHint = {text:"",label:""}, pinnedSession = "", latestAnswer = "";
let commandSelection = 0, visibleCommands = [];
let announcedFeedSession = "", announcedFeedTotal = 0;
let onboardingOffered = false;
let onboardingTimer = null;
// The old "seen" flag also changed on ordinary navigation, so it cannot
// represent an explicit opt-out and is deliberately not migrated.
const ONBOARDING_STORAGE_KEY = "blatero.onboardingShowOnStartup";
let onboardingShowOnStartup = readOnboardingPreference();
const $ = id => document.getElementById(id);
// A running server can still serve its old embedded HTML during a local update.
// Keep new asset handlers usable until the idle server is restarted.
if (!$('sceneCoachAudience') && $('sceneCandidateVoice')) {
  const label = document.createElement('label');label.textContent = 'Подсказки для';
  const select = document.createElement('select');select.id = 'sceneCoachAudience';
  select.innerHTML = '<option value="candidate">кандидата · ответ с помощью</option><option value="interviewer">интервьюера · независимые участники</option>';
  select.value = 'interviewer';
  label.append(select);$('sceneCandidateVoice').closest('label').after(label);
}
function clearSettingsHash() {
  if (String(location.hash || "").startsWith("#settings"))
    history.replaceState({}, "", location.pathname + location.search);
}
function closeSettingsOverlay() {
  if (window.BlateroSettings && !window.BlateroSettings.canClose()) return false;
  $("settingsOverlay").classList.remove("show");
  clearSettingsHash();
  return true;
}
document.querySelectorAll("[data-close-overlay]").forEach(button => {
  button.addEventListener("click", () => {
    const overlay = button.closest(".overlay");
    if (overlay?.id === "settingsOverlay" && !closeSettingsOverlay()) return;
    overlay?.classList.remove("show");
    if (overlay?.id === "settingsOverlay") clearSettingsHash();
    if (overlay?.id === "settingsOverlay" && $("setupOverlay").classList.contains("show")) {
      $("setupOverlay").inert = false;
      $("setupOverlay").setAttribute("aria-hidden", "false");
      requestAnimationFrame(renderSetupSummary);
    }
  });
});
// A still-running older server can load a missing or delayed studio catalog.
function studioUi(source, values = {}) {
  return window.BlateroStudioI18n?.ui(source,values) ?? String(source ?? '').replace(
    /\{([a-zA-Z_]\w*)\}/g,(match,name)=>Object.hasOwn(values,name)?String(values[name]):match);
}
function studioLabel(element, source, values = {}) {
  if(window.BlateroStudioI18n)return window.BlateroStudioI18n.label(element,source,values);
  if(!element)return;
  const pending=window.__blateroStudioPending ||= {labels:new Map(),attrs:new Map()};
  pending.labels.set(element,{source,values});
  const entry=typeof source==='function'?source():{source,values:typeof values==='function'?values():values};
  const shown=studioUi(entry.source,entry.values);if(element.textContent!==shown)element.textContent=shown;
}
function studioValue(element, value) {
  window.__blateroStudioPending?.labels.delete(element);
  if(window.BlateroStudioI18n)return window.BlateroStudioI18n.value(element,value);
  if(element&&element.textContent!==String(value??''))element.textContent=String(value??'');
}
function studioAttr(element, name, source, values = {}) {
  if(window.BlateroStudioI18n)return window.BlateroStudioI18n.attr(element,name,source,values);
  if(!element)return;
  const pending=window.__blateroStudioPending ||= {labels:new Map(),attrs:new Map()};
  if(!pending.attrs.has(element))pending.attrs.set(element,new Map());
  pending.attrs.get(element).set(name,{source,values});
  const entry=typeof source==='function'?source():{source,values:typeof values==='function'?values():values};
  element.setAttribute(name,studioUi(entry.source,entry.values));
}
function studioText(source, values = {}) {
  return window.BlateroStudioI18n?.text(source,values) ?? `<span data-studio-source="${esc(source)}" data-studio-source-params="${esc(JSON.stringify(values))}">${esc(studioUi(source,values))}</span>`;
}
function studioBind(source, values = {}) {
  return window.BlateroStudioI18n?.bind(source,values) ?? `data-studio-source="${esc(source)}" data-studio-source-params="${esc(JSON.stringify(values))}"`;
}
function studioAttrs(name, source, values = {}) {
  return window.BlateroStudioI18n?.attrs(name,source,values) ?? `${name}="${esc(studioUi(source,values))}" data-studio-source-${name}="${esc(source)}" data-studio-source-${name}-params="${esc(JSON.stringify(values))}"`;
}
function meetingUi(text, params = {}) {
  return window.BlateroMeetingI18n?.ui(text,params) ?? String(text ?? '').replace(
    /\{([a-zA-Z_]\w*)\}/g,(match,name)=>Object.hasOwn(params,name)?String(params[name]):match);
}
function meetingLabel(element, text, params = {}) {
  if(window.BlateroMeetingI18n)window.BlateroMeetingI18n.label(element,text,params);
  else if(element){
    const pending=window.__blateroMeetingPending ||= {labels:new Map(),attrs:new Map()};
    pending.labels.set(element,{text,params});element.textContent=meetingUi(text,typeof params==='function'?params():params);
  }
}
function meetingAttr(element, name, text, params = {}) {
  if(window.BlateroMeetingI18n)window.BlateroMeetingI18n.attr(element,name,text,params);
  else if(element){
    const pending=window.__blateroMeetingPending ||= {labels:new Map(),attrs:new Map()};
    if(!pending.attrs.has(element))pending.attrs.set(element,new Map());
    pending.attrs.get(element).set(name,{text,params});element.setAttribute(name,meetingUi(text,typeof params==='function'?params():params));
  }
}
function meetingText(text, params = {}) {
  return window.BlateroMeetingI18n?.text(text,params) ?? `<span data-meeting-source="${esc(text)}" data-meeting-source-params="${esc(JSON.stringify(params))}">${esc(meetingUi(text,params))}</span>`;
}
function meetingAttrs(name, text, params = {}) {
  return window.BlateroMeetingI18n?.attrs(name,text,params) ?? `${name}="${esc(meetingUi(text,params))}" data-meeting-source-${name}="${esc(text)}" data-meeting-source-${name}-params="${esc(JSON.stringify(params))}"`;
}
function setIconAction(element, icon, label, tooltip = label, badge = "", tooltipParams = {}) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "ui-icon");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#icon-${icon}`);
  svg.append(use);
  const hiddenLabel = document.createElement("span");
  hiddenLabel.className = "action-label";
  meetingLabel(hiddenLabel,label);
  element.replaceChildren(svg, hiddenLabel);
  if (badge) {
    const count = document.createElement("b");
    count.className = "tool-count";
    count.textContent = String(badge);
    element.append(count);
  }
  meetingAttr(element,'data-tooltip',tooltip,tooltipParams);
  meetingAttr(element,'aria-label',tooltip,tooltipParams);
  element.removeAttribute("title");
}
const localRecoveryControl = ["127.0.0.1", "localhost", "::1", "[::1]"].includes(
  location.hostname.toLocaleLowerCase());
if (new URLSearchParams(location.search).has("token"))
  history.replaceState({}, "", location.pathname + location.hash);

function connect() {
  ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => { outbox.forEach(m => ws.send(m)); outbox = []; };
  ws.onmessage = e => handle(JSON.parse(e.data));
  ws.onclose = () => {
    window.dispatchEvent(new CustomEvent("blatero:connection", {detail:{connected:false}}));
    $("status").textContent = "переподключение..."; setTimeout(connect, 2000);
  };
}
function send(o) {
  const memory = o.type.startsWith("memory_");
  const scene = o.type.startsWith("scene_");
  const stops = (o.type === "rec" && o.action === "stop" && !o.speech_rec_token)
    || ["scene_finish","training_finish"].includes(o.type);
  const scoped = memory || scene || ["rec","speech_start","speech_finish","speech_cancel","speech_text",
    "training_answer","training_finish"].includes(o.type) || !!o.speech_rec_token;
  if (scoped) {
    if (ws?.readyState !== WebSocket.OPEN || !currentInit?.server_epoch) {
      meetingLabel($("status"),"Переподключение…");
      return false;
    }
    o = {session:currentInit.current_dir, generation:currentInit.session_generation,
      server_epoch:currentInit.server_epoch, ...(memory ? {memory_revision:memoryState?.mutation_revision} : {}),
      ...(scene ? {run_id:sceneState?.run_id || null} : {}),
      ...(stops ? {recording_ref:recordingRef} : {}), ...o};
  }
  const m = JSON.stringify(o);
  if (ws && ws.readyState === 1) ws.send(m);
  else outbox.push(m);  // клик до коннекта не теряем
  return true;
}

function handle(m) {
  if (window.BlateroSettings?.beforeMessage(m) === false) return;
  if (m.type === "memory" && (m.session !== currentInit?.current_dir ||
      m.generation !== currentInit?.session_generation || m.server_epoch !== currentInit?.server_epoch)) return;
  window.dispatchEvent(new CustomEvent('blatero:brand-message', {detail:m}));
  if (m.type === 'init') document.dispatchEvent(new CustomEvent('blatero:meeting', {detail:m}));
  if (m.type === "init") {
    if (currentInit && (currentInit.current_dir !== m.current_dir ||
        currentInit.session_generation !== m.session_generation || currentInit.server_epoch !== m.server_epoch)) {
      sceneStartPending=false;trainingStartPending=false;
    }
    if (currentInit?.current_dir !== m.current_dir) {
      if (currentInit?.current_dir)
        memoryManualDrafts.set(currentInit.current_dir,memoryManualFields.map(id=>$(id).value));
      const draft=memoryManualDrafts.get(m.current_dir);
      memoryManualFields.forEach((id,index)=>{$(id).value=draft?.[index]||'';});
      memoryManualPending=null;
    }
    if (workspacePrivacyReview && workspacePrivacyReview.session !== m.current_dir) {
      workspacePrivacyReview = null;
      $("workspacePrivacyOverlay")?.classList.remove("show");
    }
    if (pinnedSession && pinnedSession !== m.session) clearPinnedHint();
    pinnedSession = m.session;
    currentInit = m;
    currentContour = m.contour === "test" ? "test" : "work";
    document.body.classList.toggle("test-contour", currentContour === "test");
    renderContourSwitches();
    currentReportReview = m.report_review || {state:"none",issues:[],requires_review:false};
    currentMeetingResult = m.report_result || {has_final:false,has_draft:false};
    renderRecovery(m.recovery || {state:"ready",items:[]}, true);
    applyFontScale(m.config.font_scale);
    currentMeetingType = (m.meta && m.meta.type) || "встреча";
    trainingState = m.training || {prepared:false,status:"not_prepared",total:0};
    sceneState = m.ai_scene || {prepared:false,status:"not_prepared",turns:[]};
    memoryState = m.memory || {configured:false,scopes:[],entries:[],draft:{entries:[]}};
    speakerLabels = m.speaker_labels || {"Я":"Я", "Собеседник":"Собеседник"};
    emulationEnabled = !!m.emulation_enabled;
    emulationRole = m.emulation_role || "собеседник";
    $("sess").textContent = m.session;
    renderFeed(m.lines || [], m.transcript || {});
    if (m.hints) renderHints(m.hints, m.hint_state);
    else {
      latestAnswer = "";
      $("answers").innerHTML = $("tags").innerHTML = $("questions").innerHTML = $("flags").innerHTML = $("uncovered").innerHTML = "";
      $("empty").style.display = "";
    }
    fillSelect("selSession", m.sessions.map(s => [s.dir, s.label]), m.current_dir);
    transcriptAdapters = m.transcript_adapters || [];
    const importAdapterValue = $("transcriptImportAdapter").value || "auto";
    fillSelect("transcriptImportAdapter",
      transcriptAdapters.map(item => [item.value, item.label]), importAdapterValue);
    for(const option of $("transcriptImportAdapter").options){
      const adapter=transcriptAdapters.find(item=>item.value===option.value);
      if(adapter)studioLabel(option,adapter.label);
    }
    updateTranscriptImportAdapter();
    const micPairs = m.mics.map(v => [v, v === "auto" ? "авто (системный)" : v.replace(/^Микрофон \(/, "").replace(/\)$/, "")]);
    fillSelect("selMic", micPairs, m.mic_current);
    fillSelect("testMic", micPairs, m.mic_current);
    const outputPairs = (m.outputs || ["auto"]).map(v =>
      [v, v === "auto" ? "авто (системный)" : v.replace(/^Динамики \(/, "").replace(/\)$/, "")]);
    fillSelect("selOutput", outputPairs, m.output_current || "auto");
    fillSelect("testOutput", outputPairs, m.output_current || "auto");
    fillSelect("selAecBackend", m.aec_backends || [],
      m.config.pre_stt_echo_backend || "auto");
    renderNativeAec(m.aec_native || {});
    renderPreflight(m.preflight || {});
    renderStartCalibration();
    $("reportFolderPath").value = m.report_folder || "";
    fillSelect("selAuto", m.autos, m.config.auto_pulse);
    fillSelect("selProvider", m.providers, m.config.llm_provider);
    if($("selSceneCoach"))$("selSceneCoach").value=m.config.scene_coach_route||'inherit';
    $("inpPulseModel").value = m.config.pulse_model || "";
    $("inpReportModel").value = m.config.report_model || "";
    updateModelSuggestions(m.config.llm_provider);
    updateProviderControls(m.config.llm_provider, m.llm_connection || null);
    fillSelect("selVoice", m.voices, m.config.voice);
    fillSelect("selQuestionVoice", m.question_voices, m.config.question_voice_provider);
    const sceneVoices = m.scene_voices || (m.voices || []).filter(item => item[0] !== "auto");
    fillSelect("sceneInterviewerVoice",
      [["question", "мой голос / маршрут вопросов"], ...sceneVoices],
      sceneState.interviewer_voice || m.scene_voice_defaults?.interviewer || "question");
    fillSelect("sceneCandidateVoice", sceneVoices,
      sceneState.candidate_voice || m.scene_voice_defaults?.candidate || "filipp");
    competencyPacks = Array.isArray(m.competency_packs) ? m.competency_packs : [];
    const competencyOptions = [["", "свободная роль — без готового профиля"],
      ...competencyPacks.map(item => [item.value, `${item.label} · v${item.version}`])];
    fillSelect("trainingPack", competencyOptions, trainingState.pack_id || "");
    fillSelect("scenePack", competencyOptions, sceneState.pack_id || "");
    applyCompetencyPack("trainingPack", "trainingRole", "trainingPackHint");
    applyCompetencyPack("scenePack", "sceneRole", "scenePackHint");
    renderVoiceProfile(m.voice_profile || {});
    fillSelect("selStyle", m.styles, m.config.question_style);
    fillSelect("selFont", m.font_scales, m.config.font_scale);
    $("reportTimestamps").checked = !!m.config.report_include_timestamps;
    $("reportReviewBeforeFinalize").checked = m.config.report_review_before_finalize !== false;
    fillSelect("selSpeech", m.speech_providers, m.config.speech_provider);
    fillSelect("selWhisper", m.whisper_models, m.config.whisper_model);
    fillSelect("selPrivacy", m.privacy_modes, m.config.text_privacy_mode);
    renderProviderContractStatus(m.provider_contracts || {});
    $("cloudAck").checked = !!m.config.cloud_ack;
    $("echoSuppression").checked = !!m.config.cross_channel_echo_suppression;
    $("acousticEchoSuppression").checked = !!m.config.pre_stt_echo_suppression;
    updateSpeechControls(m.config.speech_provider);
    meetingTypeOptions = m.type_options || m.types.map(t => ({value:t,label:t,description:""}));
    currentMeetingType = (m.meta && m.meta.type) || "встреча";
    fillSelect("selMType", meetingTypeOptions.map(t => [t.value, t.label]), currentMeetingType);
    $("selContour").value = currentContour;
    renderStartModes();
    applyMeetingMode(currentMeetingType);
    updateReportButton();
    $("selDur").value = (m.meta && m.meta.duration) ? String(m.meta.duration) : "";
    $("inpName").value = (m.meta && m.meta.name) || "";
    $("inpClient").value = (m.meta && m.meta.client_name) || "";
    $("inpProject").value = (m.meta && m.meta.project_name) || "";
    $("inpEmulationRole").value = (m.meta && m.meta.emulation_role) || "";
    $("inpEmulationRole").placeholder = `${emulationRole} — по типу встречи`;
    $("inpWorkspace").value = (m.meta && m.meta.workspace_path) || "";
    renderWorkspaceStatus("workspaceStatus", m.workspace || {});
    $("workspaceInit").disabled = !!(m.workspace && m.workspace.busy);
    $("workspaceProbe").disabled = false;
    $("workspaceBrowse").disabled = false;
    $("setupProbe").disabled = false;
    $("setupBrowse").disabled = false;
    $("inpSpeakerMe").value = speakerLabels["Я"] || "Я";
    $("inpSpeakerGuest").value = speakerLabels["Собеседник"] || "Собеседник";
    $("waveMeLabel").textContent = speakerLabels["Я"] || "Я";
    $("waveGuestLabel").textContent = speakerLabels["Собеседник"] || "Собеседник";
    renderMeetSummary();
    meetingDuration = m.duration || null;
    recLive = !!m.rec_running;
    recordingRef = m.recording_ref ?? null;
    renderRecordButton(recLive);
    if (!recLive) {
      $("recdot").className = "";
      $("rectext").style.color = "";
      meetingLabel($("rectext"),"запись не запущена · нажмите «Проверить всё» перед встречей");
    }
    renderWorkflowNext();
    renderTraining(trainingState);
    renderAiScene(sceneState);
    setTrainingView(trainingView, false);
    if (trainingStartPending && recLive && currentMeetingType === "тренировка") {
      trainingStartPending = false;
      send({type:"training_start"});
    }
    if (sceneStartPending && recLive && currentMeetingType === "тренировка") {
      const expectedRun = sceneStartPending;
      sceneStartPending = false;
      if (sceneState?.run_id === expectedRun) send({type:"scene_start",run_id:expectedRun});
    }
    currentBank = m.bank || [];
    renderBank(currentBank);
    if (m.calendar) renderCalendar(m.calendar);
    $("dossier").innerHTML = m.dossier ? mdLite(m.dossier)
      : '<span style="color:var(--dim);font-size:.8125rem">досье нет — появляется у кандидатов с материалами (meet.py --prepare)</span>';
    $("workspaceContext").innerHTML = m.workspace_context ? mdLite(m.workspace_context)
      : '<span style="color:var(--dim);font-size:.8125rem">контекст проекта ещё не подготовлен — откройте «Новая встреча» или настройки</span>';
    renderMemory(memoryState);
    maybeShowOnboarding();
    window.BlateroSettings?.afterInit(m);
    $("status").textContent = m.config.cloud_ack ? ""
      : (m.config.speech_provider === "local_whisper"
        ? "аудио локально · облачные функции LLM выключены до ручного подтверждения"
        : "облако выключено до ручного подтверждения в настройках приватности");
  } else if (m.type === "memory") { renderMemory(m);
    if (memoryManualPending && m.request_id === memoryManualPending.id) {
      memoryManualFields.forEach((id,index)=>{if($(id).value===memoryManualPending.values[index])$(id).value='';});
      memoryManualPending=null;
    }
  } else if (m.type === "model_manager") { renderModelManager(m);
  } else if (m.type === "update_manager") { renderUpdateManager(m);
  } else if (m.type === "recovery") { renderRecovery(m, false);
  } else if (m.type === "hints") { renderHints(m.hints, m.hint_state);
  } else if (m.type === "transcript") { renderFeed(m.lines, m);
  } else if (m.type === "levels") { renderLevels(m);
    window.dispatchEvent(new CustomEvent("blatero:training-levels", {detail:m}));
  } else if (m.type === "sessions") {
    fillSelect("selSession", m.sessions.map(s => [s.dir, s.label]), m.current_dir);
  } else if (m.type === "archive") { renderArchive(m.items);
  } else if (m.type === "session_lifecycle") { renderSessionLifecycle(m);
  } else if (m.type === "transcript_import") {
    const status = $("transcriptImportStatus");
    status.className = "workspace-status " + (m.state === "error" ? "error" : "ready");
    status.textContent = m.text || "Импорт завершён.";
    $("transcriptImportStart").disabled = m.state !== "error";
  } else if (m.type === "agenda") {
    $("agendaTitle").textContent = `Повестка: ${m.file} (из ${m.source})`;
    $("agendaTa").value = m.text;
    $("agendaOverlay").classList.add("show");
  } else if (m.type === "mic_test") {
    renderMicTest(m);
  } else if (m.type === "output_test") {
    renderOutputTest(m);
  } else if (m.type === "aec_test") {
    renderAecTest(m);
    if (m.calibration && currentInit) currentInit.audio_calibration = m.calibration;
    renderStartCalibration(m);
  } else if (m.type === "aec_install") {
    renderNativeAec({...((currentInit && currentInit.aec_native) || {}),
      ...(m.native || {}), state:m.state, text:m.text, busy:m.state === "started"});
  } else if (m.type === "preflight") {
    renderPreflight(m);
    if (m.calibration && currentInit) currentInit.audio_calibration = m.calibration;
    renderStartCalibration(m);
    studioLabel($("status"),()=>({source:preflightSummary(m)}));
  } else if (m.type === "diagnostics") {
    $("diagnosticsBuild").disabled = false;
    if (m.state === "done" && m.url) {
      const link = document.createElement("a"); link.href = m.url;
      link.download = "diagnostics.json"; document.body.appendChild(link);
      link.click(); link.remove();
      $("preflightStatus").textContent = m.text || "Диагностика готова.";
    } else if (m.text) {
      $("preflightStatus").className = "workspace-status error";
      $("preflightStatus").textContent = m.text;
    }
  } else if (m.type === "voice_profile") {
    renderVoiceProfile(m);
  } else if (m.type === "bank") {
    currentBank = m.bank || [];
    renderBank(currentBank);
  } else if (m.type === "calendar") {
    renderCalendar(m);
  } else if (m.type === "calendar_status") {
    $("calSync").disabled = !!m.busy;
    $("calStatus").textContent = m.text || "";
    $("calStatus").style.color = m.text && !m.busy && /не |ошиб/i.test(m.text)
      ? "var(--red)" : "var(--dim)";
  } else if (m.type === "workspace_browse") {
    const setupTarget = m.target === "setup";
    if (setupTarget && (!setupProbeRequest || (m.request_id && m.request_id !== setupProbeRequest.id))) return;
    const statusId = setupTarget ? "setupProbeStatus" : "workspaceStatus";
    const browseId = setupTarget ? "setupBrowse" : "workspaceBrowse";
    const probeId = setupTarget ? "setupProbe" : "workspaceProbe";
    const busy = m.state === "scanning";
    renderWorkspaceStatus(statusId, m);
    $(browseId).disabled = busy;
    $(probeId).disabled = busy;
  } else if (m.type === "workspace_probe") {
    if (m.target === 'setup') {
      if (!setupProbeRequest || (m.request_id && m.request_id !== setupProbeRequest.id)) return;
      if (setupProbeRequest.kind === 'probe' && !sameWorkspacePath(setupProbeRequest.path,$('setupWorkspace').value.trim())) return;
      setupProbeRequest = null;
    }
    setupProbeResult = m.target === "setup" ? m : setupProbeResult;
    if (m.path) $(m.target === "setup" ? "setupWorkspace" : "inpWorkspace").value = m.path;
    renderWorkspaceStatus(m.target === "setup" ? "setupProbeStatus" : "workspaceStatus", m);
    $(m.target === "setup" ? "setupProbe" : "workspaceProbe").disabled = false;
    $(m.target === "setup" ? "setupBrowse" : "workspaceBrowse").disabled = false;
    if (m.target === "settings") window.BlateroSettings?.workspaceProbe();
  } else if (m.type === "workspace_status") {
    renderWorkspaceStatus("workspaceStatus", m);
    $("workspaceInit").disabled = !!m.busy;
    if (workspacePrivacyReview && m.state === "ready" && !m.busy)
      $("workspacePrivacyOverlay")?.classList.remove("show");
  } else if (m.type === "workspace_privacy_review") {
    showWorkspacePrivacy(m);
  } else if (m.type === "workspace_privacy_error") {
    if ($("workspacePrivacyStatus")) $("workspacePrivacyStatus").textContent = m.text;
    if ($("workspacePrivacyRecheck")) $("workspacePrivacyRecheck").disabled = false;
  } else if (m.type.startsWith("live_material_")) {
    window.dispatchEvent(new CustomEvent("blatero-material", {detail:m}));
  } else if (m.type === "llm_connection_status") {
    if (currentInit && m.configured !== undefined)
      currentInit.llm_connection = {...(currentInit.llm_connection || {}), ...m};
    renderLlmConnection(m);
  } else if (m.type === "prompt_catalog") {
    receivePromptCatalog(m);
  } else if (m.type === "training") {
    trainingState = m;
    renderTraining(m);
    if (trainingView === "scene") renderAiScene(sceneState);
    if (m.auto_play && m.question && m.question.id !== trainingAutoQuestionId) {
      trainingAutoQuestionId = m.question.id;
      playQuestion(m.question.question, $("trainingSpeak"));
    }
  } else if (m.type === "ai_scene") {
    sceneState = m;
    renderAiScene(m);
    if (m.auto_play && m.turn && m.turn.id !== sceneAutoTurnId) {
      sceneAutoTurnId = m.turn.id;
      playSceneTurn(m.turn, true);
    }
  } else if (m.type === "report_review") {
    renderReportReview(m, m.open !== false);
  } else if (m.type === "report_draft_error") {
    reportDraftLoading = false;
    updateReportDraftState();
    $("reportDraftStatus").className = "dirty";
    meetingLabel($("reportDraftStatus"),'Не сохранено: {message}',{message:m.message||'ошибка'});
  } else if (m.type === "report_conclusion_error") {
    document.querySelectorAll(".report-conclusion-save").forEach(button => {
      button.disabled = false;
      meetingLabel(button,"сохранить вывод");
    });
    document.querySelectorAll(".report-conclusion-decision button").forEach(button => {
      button.disabled = currentReportReview.draft_editable === false;
    });
    meetingLabel($("reportConclusionMeta"),'Не сохранено: {message}',{message:m.message||'ошибка'});
  } else if (m.type === "status") {
    $("status").textContent = m.text;
    $("pulse").disabled = !!m.busy;
  }
}

function reportReviewPending(review = currentReportReview) {
  return ["needs_review", "stale", "blocked", "ready"].includes(review && review.state);
}

function meetingStage() {
  if (recLive) return "recording";
  if (currentMeetingType === "тренировка") return "training";
  if (reportReviewPending()) return currentMeetingResult.has_draft ? "draft" : "review";
  if (currentMeetingResult.has_final)
    return currentMeetingResult.stale === true ? "stale" : "done";
  if (currentHasTranscript) return "review";
  return ["ready", "ready_with_warnings"].includes(currentPreflightState) ? "ready" : "prepare";
}

function renderMeetSummary() {
  const m=currentInit;if(!m)return;
  const option=meetingTypeOptions.find(value=>value.value===currentMeetingType);
  const ready=m.workspace?.state==='ready'||m.dossier?.trim();
  const items=[
    {html:meetingText(option?.label||currentMeetingType),state:'info'},
    {html:m.meta?.duration?meetingText('{count} мин',{count:m.meta.duration}):meetingText('без лимита'),state:''},
    {html:meetingText(m.workspace?.state==='ready'?'контекст готов':m.dossier?.trim()?'досье загружено':'без контекста'),state:ready?'ready':'warn'},
    {html:esc(settingsUi(m.llm_connection?.label||m.config.llm_provider)),state:m.llm_connection?.configured?'ready':'warn'},
  ];
  $('meetSummary').innerHTML=items.map(item=>`<span class="summary-chip ${item.state}"><span>${item.html}</span></span>`).join('');
}
document.addEventListener('blatero:language',renderMeetSummary);

function renderWorkflowNext() {
  const box = $("workflowNext"), text = $("workflowNextText"), button = $("workflowNextAction");
  if (!box || !text || !button) return;
  // Studio modes already own their step/status controls. A meeting's saved
  // transcript is not the next action of a new scene or speaking exercise.
  box.hidden = currentMeetingType === 'тренировка';
  let state = "prepare", action = "setup", label = "подготовить встречу";
  let message = "Создайте встречу, укажите цель и добавьте рабочие материалы.";
  const phase = meetingStage();
  if (phase === "recording") {
    state = "recording"; action = "pulse";
    label = ["кандидат", "тренировка"].includes(currentMeetingType)
      ? "получить быстрый ответ" : "получить подсказку";
    message = "Запись идёт. Следите за уровнями звука; подсказку можно вызвать в любой момент.";
  } else if (phase === "done" || phase === "stale") {
    state = "done"; action = "results"; label = "читать отчёт";
    message = phase === "stale"
      ? "Сохранённый отчёт доступен, но исходные данные или настройки изменились."
      : "Отчёт сохранён. Прочитайте его здесь, скачайте DOCX или начните новую встречу.";
    const memoryReview = memoryState?.review;
    if (memoryReview && !["reviewed", "test", "no_report", "error"].includes(memoryReview.status)) {
      action = "memory_review"; label = "проверить договорённости";
      message = "Отчёт сохранён. Проверьте и сохраните договорённости — они подтянутся в следующую встречу проекта.";
    }
  } else if (reportReviewPending()) {
    state = "review"; action = "report"; label = "проверить отчёт";
    message = "Черновик готов. Проверьте говорящих, текст и выводы перед созданием DOCX.";
  } else if (currentHasTranscript) {
    state = "review"; action = "report";
    label = ["кандидат", "тренировка"].includes(currentMeetingType)
      ? "сформировать разбор" : "сформировать отчёт";
    message = "Запись сохранена. Проверьте транскрипт и сформируйте итоговый документ.";
  } else if (!["ready", "ready_with_warnings"].includes(currentPreflightState)) {
    state = "check"; action = "preflight"; label = "проверить всё";
    message = "Перед записью проверьте микрофон, звук встречи, распознавание речи и ИИ.";
  } else {
    state = "ready"; action = "record"; label = "начать запись";
    message = "Проверка пройдена. Можно начинать запись.";
  }
  box.dataset.state = state;
  meetingLabel(text,message);
  button.dataset.action = action;
  meetingLabel(button,label);
}

function updateReportButton() {
  const pending = reportReviewPending();
  const candidate = currentMeetingType === "кандидат";
  const training = currentMeetingType === "тренировка";
  if (!pending && currentMeetingResult.has_final) {
    setIconAction($("report"), "report", "открыть отчёт", "Читать сохранённый отчёт без нового запроса к ИИ");
  } else if (pending) {
    const count = (currentReportReview.issues || []).length;
    setIconAction($("report"), "review", "проверить отчёт",
      'Проверить сомнения перед итоговым DOCX{suffix}', count, {suffix:count ? ` — ${count}` : ''});
  } else {
    const label = candidate || training ? "разбор" : "отчёт";
    setIconAction($("report"), "report", label,
      candidate || training ? "Сформировать итоговый разбор" : "Сформировать итоговый отчёт");
  }
}

function reviewSampleText(issue) {
  const samples = issue && issue.evidence && Array.isArray(issue.evidence.samples)
    ? issue.evidence.samples : [];
  if (!samples.length) return "";
  return samples.slice(0, 6).map(item =>
    `${fmtSec(Math.round((Number(item.start_ms) || 0) / 1000))} · ${Math.round((Number(item.confidence) || 0) * 100)}%`).join(" · ");
}

function reviewSampleButtons(issue) {
  const samples = issue && issue.evidence && Array.isArray(issue.evidence.samples)
    ? issue.evidence.samples : [];
  if (!samples.length) return "";
  return samples.slice(0, 6).map(item => {
    const start = Math.max(0, Number(item.start_ms) || 0);
    const confidence = Math.round((Number(item.confidence) || 0) * 100);
    return `<button type="button" class="report-sample-link" data-start-ms="${start}"
      title="открыть реплику в локальном редакторе">${esc(formatTranscriptMs(start))} · ${confidence}%</button>`;
  }).join("");
}

function reportConclusionDirty() {
  return [...document.querySelectorAll(".report-conclusion-text")].some(
    textarea => textarea.value !== (textarea.dataset.saved || ""));
}

function reportCalibrationPct(value) {
  return typeof value === "number"
    ? `${(value * 100).toFixed(1).replace(".", ",")}%` : "—";
}

function renderReportCalibration(data) {
  const section = $("reportCalibration");
  if (!data || data.status === "unavailable") {
    section.hidden = true;
    return;
  }
  section.hidden = false;
  const requirements = data.requirements || {}, metrics = data.metrics || {};
  const labels = Number(data.labels) || 0;
  const target = Number(requirements.labels) || 40;
  $("reportCalibrationProgress").textContent =
    `${labels} / ${target} · ${Number(data.labeled_sessions) || 0} встреч`;
  const cards = [
    ["размечено", String(labels),
      `${Number(data.confirmed) || 0} подтверждено · ${Number(data.excluded) || 0} исключено`],
    ["точность допуска", reportCalibrationPct(metrics.keep_precision),
      `${Number(metrics.safe_keep) || 0} верных · ${Number(metrics.unsafe_keep) || 0} опасных`],
    ["верхняя граница 95%", reportCalibrationPct(metrics.unsafe_keep_wilson_upper_95),
      `цель не выше ${reportCalibrationPct(data.target_unsafe_keep_rate)}`],
    ["ручная проверка", reportCalibrationPct(metrics.manual_review_rate),
      `${Number(metrics.manual_review) || 0} выводов остановлено`],
  ];
  const notes=[
    meetingText('{confirmed} подтверждено · {excluded} исключено',{confirmed:Number(data.confirmed)||0,excluded:Number(data.excluded)||0}),
    meetingText('{safe} верных · {unsafe} опасных',{safe:Number(metrics.safe_keep)||0,unsafe:Number(metrics.unsafe_keep)||0}),
    meetingText('цель не выше {value}',{value:reportCalibrationPct(data.target_unsafe_keep_rate)}),
    meetingText('{count} выводов остановлено',{count:Number(metrics.manual_review)||0}),
  ];
  $("reportCalibrationMetrics").innerHTML = cards.map((item,index) =>
    `<article class="report-calibration-metric"><span>${meetingText(item[0])}</span>
      <b>${esc(item[1])}</b><small>${notes[index]}</small></article>`).join("");
  meetingLabel($("reportCalibrationProgress"),'{count} / {target} · встреч: {sessions}',{count:labels,target,sessions:Number(data.labeled_sessions)||0});
  const current = data.current_report || {};
  $("reportCalibrationCurrent").innerHTML = current.total
    ? meetingText('В текущем отчёте размечено выводов: {labeled} из {total}.',{labeled:Number(current.labeled)||0,total:Number(current.total)||0})+meetingText(current.complete?' Он полностью вошёл в корпус.':' Подтвердите или исключите остальные, если хотите использовать его как полный эталон.')
    : meetingText("В текущем отчёте пока нет размечаемых выводов.");
  const note = $("reportCalibrationNote");
  const blockers = Array.isArray(data.blockers) ? data.blockers : [];
  note.className = `report-calibration-note ${data.status === "passes" ? "ready" : data.status === "fails" ? "failed" : ""}`;
  if (data.status === "passes") {
    note.innerHTML = `<strong>${meetingText('Корпус достаточен: текущая граница допуска выдерживает целевой риск.')}</strong>
      <div>${meetingText('Это измерение, а не автоматическое разрешение кадрового решения.')} Fingerprint ${esc(String(data.fingerprint || "").slice(0,12))}.</div>`;
  } else if (data.status === "fails") {
    note.innerHTML = `<strong>${meetingText('Текущий автоматический допуск не выдерживает целевой риск.')}</strong>
      <div>${meetingText('До пересмотра правил все выводы следует проверять вручную.')}</div>`;
  } else {
    note.innerHTML = `<strong>${meetingText('Корпус пока мал — пороги и правила заблокированы.')}</strong>
      ${blockers.length ? `<ul>${blockers.map(item => `<li>${esc(String(item))}</li>`).join("")}</ul>` : ""}`;
  }
  const signalLabels = {
    no_evidence_reference:"нет ссылки на реплику",
    evidence_not_found:"реплика не найдена",
    low_confidence_evidence:"низкая уверенность STT",
    model_unsupported:"самоаудит: нет опоры",
    model_contradiction:"самоаудит: противоречие",
  };
  $("reportCalibrationSignals").innerHTML = (data.signals || []).slice(0, 6).map(item =>
    `<span class="report-calibration-signal">${meetingText(signalLabels[item.code] || String(item.code || "сигнал"))} · ${Number(item.total) || 0} · ${meetingText('исключено {value}',{value:reportCalibrationPct(item.exclusion_rate)})}</span>`).join("");
}

function renderReportConclusions(review) {
  const section = $("reportConclusions"), list = $("reportConclusionList");
  const conclusions = Array.isArray(review.conclusions) ? review.conclusions : [];
  if (!conclusions.length) {
    section.hidden = true;
    list.replaceChildren();
    return;
  }
  section.hidden = false;
  const summary = review.conclusion_summary || {};
  const unresolvedCount = Number(summary.unresolved) || 0;
  meetingLabel($("reportConclusionMeta"),'Подтверждено: {confirmed} · исключено: {excluded} · ждут решения: {pending}',
    {confirmed:Number(summary.confirmed)||0,excluded:Number(summary.excluded)||0,pending:unresolvedCount});
  const statusLabels = {
    supported:"опора найдена", needs_review:"проверить", unsupported:"нет опоры",
  };
  list.innerHTML = conclusions.map(item => {
    const evidenceButtons = (item.evidence || []).slice(0, 6).map(source =>
      `<button type="button" class="report-conclusion-evidence"
        data-start-ms="${Math.max(0, Number(source.start_ms) || 0)}"
        ${meetingAttrs('title','открыть реплику и прослушать аудио')}>${esc(String(source.clock || "реплика"))} · ${esc(String(source.speaker_name || source.speaker_role || "голос"))}</button>`).join("");
    const workspaceButtons = (item.workspace_sources || []).slice(0, 6).map(path =>
      `<button type="button" class="report-conclusion-source" data-path="${esc(String(path))}"
        ${meetingAttrs('title','показать локальный файл в Проводнике')}>⌁ ${esc(String(path))}</button>`).join("");
    const checks = (item.checks || []).map(check =>
      `<li>${esc(String(check.detail || check.code || "требуется проверка"))}</li>`).join("");
    const editable = review.draft_editable !== false;
    const decision = ["confirmed", "excluded"].includes(item.decision)
      ? item.decision : "pending";
    const decisionLabels = {
      pending:"на проверке", confirmed:"подтверждён", excluded:"исключён из DOCX",
    };
    const decisionButtons = [
      ["pending", "проверить"], ["confirmed", "подтвердить"], ["excluded", "исключить"],
    ].map(([value, label]) => `<button type="button" data-decision="${value}"
      class="${decision === value ? "active" : ""}" aria-pressed="${decision === value}"
      ${editable ? "" : "disabled"}>${meetingText(label)}</button>`).join("");
    return `<article class="report-conclusion ${esc(String(item.status || "needs_review"))} decision-${decision}"
      data-conclusion-id="${esc(String(item.id || ""))}">
      <div class="report-conclusion-head"><span>${item.section?esc(String(item.section)):meetingText('Вывод')}</span>
        <div><code>${meetingText(item.evidence_changed ? "опора изменилась" : (statusLabels[item.status] || "проверить"))}</code>
          <em>${meetingText(decisionLabels[decision])}</em></div></div>
      <textarea class="report-conclusion-text" maxlength="20000" spellcheck="true"
        ${meetingAttrs('aria-label','Вывод: {section}',{section:String(item.section||meetingUi('раздел'))})} ${editable ? "" : "disabled"}>${esc(String(item.text_markdown || item.text || ""))}</textarea>
      ${checks ? `<ul class="report-conclusion-checks">${checks}</ul>` : ""}
      ${(evidenceButtons || workspaceButtons) ? `<div class="report-conclusion-sources">${evidenceButtons}${workspaceButtons}</div>` : ""}
      <div class="report-conclusion-decision" role="group" ${meetingAttrs('aria-label','Решение по выводу')}>${decisionButtons}</div>
      <div class="report-conclusion-actions"><span>${meetingText('редакция {revision}',{revision:Number(item.revision)||0})}</span>
        <button type="button" class="primary report-conclusion-save" disabled>${meetingText('сохранить вывод')}</button></div>
    </article>`;
  }).join("");
  list.querySelectorAll(".report-conclusion-text").forEach(textarea => {
    textarea.dataset.saved = textarea.value;
  });
}

function renderReportReview(review, open = true) {
  currentReportReview = review || {state:"none",issues:[],requires_review:false};
  updateReportButton();
  renderWorkflowNext();
  if (currentReportReview.state === "finalized") {
    $("reportReviewOverlay").classList.remove("show");
    return;
  }
  const issues = currentReportReview.issues || [];
  const critical = issues.filter(item => item.severity === "critical").length;
  const warning = issues.filter(item => item.severity === "warning").length;
  $("reportReviewScore").innerHTML = `${issues.length}<small>${meetingText('сигналов · {critical} крит. · {warning} вним.',{critical,warning})}</small>`;
  const notice = $("reportReviewNotice");
  notice.className = "report-review-notice" + (!currentReportReview.requires_review ? " ready" : "");
  if (currentReportReview.stale) {
    meetingLabel(notice,"Исходные данные изменились после генерации. Старый черновик нельзя незаметно превратить в новый отчёт — его нужно пересобрать.");
  } else if (!issues.length) {
    meetingLabel(notice,"Технических сомнений не найдено. Blatero соберёт финальный документ без дополнительного запроса к модели.");
  } else if (!currentReportReview.draft_exists) {
    meetingLabel(notice,"Платный запрос к LLM не выполнялся: сначала нужен пригодный транскрипт.");
  } else {
    meetingLabel(notice,"Черновик уже готов. Исправьте данные, подтвердите выводы или явно создайте документ с перечисленными ограничениями.");
  }
  const unresolved = Number(currentReportReview.unresolved_conclusions) || 0;
  if (!currentReportReview.stale && currentReportReview.draft_exists && unresolved) {
    meetingLabel(notice,'Спорных выводов: {count}. Подтвердите их после проверки или исключите из итогового DOCX.',{count:unresolved});
  }
  $("reportReviewIssues").innerHTML = issues.map(issue => {
    const sample = reviewSampleText(issue);
    const sampleButtons = reviewSampleButtons(issue);
    return `<article class="report-review-issue ${esc(issue.severity || "warning")}">
      <div class="report-review-issue-head"><strong>${esc(issue.title || "Сигнал качества")}</strong>
        <code>${meetingText(({critical:'критично',warning:'внимание',notice:'замечание'})[issue.severity]||issue.severity||'внимание')}</code></div>
      <p>${esc(issue.detail || "")}</p>
      ${issue.action ? `<div class="review-action">→ ${esc(issue.action)}</div>` : ""}
      ${sampleButtons ? `<div class="report-review-samples">${sampleButtons}</div>`
        : sample ? `<div class="report-review-samples">${esc(sample)}</div>` : ""}
    </article>`;
  }).join("") || '<div class="report-review-notice ready">'+meetingText('Очередь пуста.')+'</div>';
  renderReportConclusions(currentReportReview);
  renderReportCalibration(currentReportReview.calibration);
  const canFinalize = !!currentReportReview.can_finalize;
  const hasDraftText = typeof currentReportReview.draft_markdown === "string";
  const editor = $("reportDraftEditor"), draftText = $("reportDraftText");
  if (hasDraftText) {
    reportDraftLoading = false;
    editor.hidden = false;
    draftText.disabled = false;
    draftText.value = currentReportReview.draft_markdown;
    draftText.dataset.revision = String(Number(currentReportReview.draft_revision) || 0);
    reportDraftSaved = draftText.value;
    meetingLabel($("reportDraftMeta"),'редакция {revision}',{revision:draftText.dataset.revision});
  } else if (!currentReportReview.draft_editable) {
    editor.hidden = true;
    reportDraftSaved = null;
  } else if (reportDraftSaved !== null
             && Number(draftText.dataset.revision || 0)
                === Number(currentReportReview.draft_revision || 0)) {
    editor.hidden = false;
    draftText.disabled = false;
  } else {
    editor.hidden = false;
    draftText.disabled = true;
    if (!reportDraftLoading) {
      reportDraftLoading = true;
      send({type:"report_review", action:"open"});
    }
  }
  updateReportDraftState();
  const draftDirty = (reportDraftSaved !== null && draftText.value !== reportDraftSaved)
    || reportConclusionDirty();
  $("reportReviewApprove").disabled = !currentReportReview.can_approve || draftDirty;
  $("reportReviewSkip").disabled = !canFinalize || draftDirty;
  $("reportReviewRegenerate").disabled = currentReportReview.state === "none";
  $("reportReviewTimeline").style.display = currentReportReview.evidence_url ? "" : "none";
  $("reportEvidenceExport").style.display = currentReportReview.evidence_export_url ? "" : "none";
  $("reportReviewSpeakers").style.display = currentReportReview.diarization_url ? "" : "none";
  meetingLabel($("reportReviewLead"),currentReportReview.audit_available
    ? "Локальные метрики, опоры выводов и самоаудит собраны в одну очередь."
    : "Локальные метрики собраны; модель не вернула структурированный самоаудит.");
  if (open) {
    $("reportReviewOverlay").classList.add("show");
    $("reportReviewTitle").focus();
  }
}

function formatTranscriptMs(value) {
  const seconds = Math.max(0, Math.floor((Number(value) || 0) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  return hours
    ? `${hours}:${String(minutes).padStart(2,"0")}:${String(rest).padStart(2,"0")}`
    : `${minutes}:${String(rest).padStart(2,"0")}`;
}

function transcriptItemKey(item) {
  return `${item.journal}:${item.event_id}`;
}

function transcriptEditorFilteredItems() {
  const query = $("transcriptEditorSearch").value.trim().toLocaleLowerCase("ru-RU");
  const items = transcriptEditorState.utterances || [];
  if (!query) return items;
  return items.filter(item => [item.text, item.speaker_name, item.speaker_role,
    item.speaker_id, item.source, item.journal].some(value =>
      String(value || "").toLocaleLowerCase("ru-RU").includes(query)));
}

function renderTranscriptEditor() {
  const items = transcriptEditorFilteredItems();
  const total = Number(transcriptEditorState.total) || 0;
  $("transcriptEditorCount").innerHTML = `${items.length}<small>${meetingText('показано · {total} всего',{total})}</small>`;
  if (!items.length) {
    $("transcriptEditorList").innerHTML = '<div class="transcript-editor-empty">'+meetingText('Реплики не найдены.')+'</div>';
    return;
  }
  let nearestKey = "", nearestDistance = Number.POSITIVE_INFINITY;
  if (transcriptEditorFocusMs !== null) {
    items.forEach(item => {
      const distance = Math.abs((Number(item.start_ms) || 0) - transcriptEditorFocusMs);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestKey = transcriptItemKey(item);
      }
    });
  }
  $("transcriptEditorList").innerHTML = items.map(item => {
    const key = transcriptItemKey(item);
    const speaker = item.speaker_name || item.speaker_role || meetingUi("Участник");
    const confidence = item.confidence == null ? meetingText("уверенность не измерялась")
      : meetingText('уверенность {value}%',{value:Math.round(Number(item.confidence)*100)});
    return `<article class="transcript-editor-item${key === nearestKey ? " focused" : ""}"
      data-key="${esc(key)}">
      <div class="transcript-editor-item-head">
        <button type="button" class="transcript-time" data-action="play"
          ${item.audio_file ? "" : "disabled"}
          ${meetingAttrs('title',item.audio_file ? "прослушать этот фрагмент" : "для реплики нет аудиодорожки")}>
          ${esc(formatTranscriptMs(item.start_ms))}</button>
        <strong>${esc(speaker)}</strong>
        <span>${esc(item.journal)} · ${confidence}</span>
        ${item.edited ? `<b ${meetingAttrs('title','ручная правка, редакция {revision}',{revision:Number(item.edit_revision)||1})}>${meetingText('исправлено')}</b>` : ""}
      </div>
      <textarea maxlength="12000" spellcheck="true"
        ${meetingAttrs('aria-label','Текст реплики {time}',{time:formatTranscriptMs(item.start_ms)})}>${esc(item.text || "")}</textarea>
      <div class="transcript-editor-item-actions">
        <span>${meetingText('{count} знаков',{count:(item.text||'').length})}</span>
        <button type="button" data-action="save" disabled>${meetingText('сохранить реплику')}</button>
      </div>
    </article>`;
  }).join("");
  $("transcriptEditorList").querySelectorAll(".transcript-editor-item").forEach(card => {
    const textarea = card.querySelector("textarea");
    const item = items.find(value => transcriptItemKey(value) === card.dataset.key);
    textarea.addEventListener("input", () => {
      const save = card.querySelector('[data-action="save"]');
      save.disabled = textarea.value === String(item.text || "");
      card.classList.toggle("dirty", !save.disabled);
      meetingLabel(card.querySelector(".transcript-editor-item-actions > span"),'{count} знаков',{count:textarea.value.length});
    });
  });
  if (nearestKey) {
    requestAnimationFrame(() => {
      const target = Array.from($("transcriptEditorList").children)
        .find(card => card.dataset.key === nearestKey);
      if (target) target.scrollIntoView({block:"center", behavior:"smooth"});
    });
    transcriptEditorFocusMs = null;
  }
}

async function loadTranscriptEditor() {
  const session = currentInit && currentInit.current_dir;
  if (!session) return;
  $("transcriptEditorStatus").className = "loading";
  meetingLabel($("transcriptEditorStatus"),"Загружаю канонический транскрипт…");
  try {
    const response = await fetch(
      `/api/sessions/${encodeURIComponent(session)}/transcript-editor`,
      {cache:"no-store"});
    if (!response.ok) throw new Error(await response.text());
    transcriptEditorState = await response.json();
    renderTranscriptEditor();
    $("transcriptEditorStatus").className = "saved";
    meetingLabel($("transcriptEditorStatus"),transcriptEditorState.truncated
      ? "Показана ограниченная часть длинной встречи."
      : "Все изменения сохраняются только локально.");
  } catch (error) {
    $("transcriptEditorStatus").className = "error";
    meetingLabel($("transcriptEditorStatus"),'{messages}',{messages:error.message||String(error)});
    $("transcriptEditorList").innerHTML = '<div class="transcript-editor-empty">'+meetingText('Транскрипт не загружен.')+'</div>';
  }
}

function openTranscriptEditor(startMs = null) {
  const draftDirty = reportDraftSaved !== null
    && $("reportDraftText").value !== reportDraftSaved;
  if (draftDirty) {
    alert(meetingUi("Сначала сохраните правки черновика отчёта."));
    return;
  }
  transcriptEditorFocusMs = startMs == null ? null : Math.max(0, Number(startMs) || 0);
  transcriptEditorReturnToReview = $("reportReviewOverlay").classList.contains("show");
  $("reportReviewOverlay").classList.remove("show");
  $("transcriptEditorOverlay").classList.add("show");
  $("transcriptEditorTitle").focus();
  loadTranscriptEditor();
}

async function saveTranscriptItem(card) {
  const session = currentInit && currentInit.current_dir;
  const item = (transcriptEditorState.utterances || []).find(
    value => transcriptItemKey(value) === card.dataset.key);
  if (!session || !item) return;
  const textarea = card.querySelector("textarea");
  const button = card.querySelector('[data-action="save"]');
  button.disabled = true;
  card.classList.add("saving");
  $("transcriptEditorStatus").className = "loading";
  meetingLabel($("transcriptEditorStatus"),"Сохраняю реплику и пересобираю Markdown…");
  try {
    const response = await fetch(
      `/api/sessions/${encodeURIComponent(session)}/transcript-editor`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({journal:item.journal, event_id:item.event_id,
          revision:item.revision, text:textarea.value})
      });
    if (!response.ok) throw new Error(await response.text());
    const result = await response.json();
    if (result.utterance) {
      const index = transcriptEditorState.utterances.findIndex(
        value => transcriptItemKey(value) === card.dataset.key);
      transcriptEditorState.utterances[index] = result.utterance;
    }
    renderTranscriptEditor();
    $("transcriptEditorStatus").className = "saved";
    meetingLabel($("transcriptEditorStatus"),result.changed === false
      ? "Текст не изменился."
      : "Реплика сохранена. Черновик отчёта помечен устаревшим до пересборки.");
  } catch (error) {
    button.disabled = false;
    card.classList.remove("saving");
    $("transcriptEditorStatus").className = "error";
    meetingLabel($("transcriptEditorStatus"),'{messages}',{messages:error.message||String(error)});
  }
}

function playTranscriptItem(item) {
  if (!item || !item.audio_file || !currentInit) return;
  const audio = $("transcriptEditorAudio");
  if (transcriptEditorAudioTimer) clearInterval(transcriptEditorAudioTimer);
  const src = `/files/${encodeURIComponent(currentInit.current_dir)}/${encodeURIComponent(item.audio_file)}`;
  const start = Math.max(0, Number(item.start_ms) || 0) / 1000;
  const end = Math.max(start + 0.8, Number(item.end_ms) / 1000 || start + 8);
  const begin = () => {
    audio.currentTime = start;
    audio.play().catch(error => {
      $("transcriptEditorStatus").className = "error";
      meetingLabel($("transcriptEditorStatus"),'Аудио не запущено: {message}',{message:error.message});
    });
    transcriptEditorAudioTimer = setInterval(() => {
      if (audio.currentTime >= end || audio.ended) {
        audio.pause();
        clearInterval(transcriptEditorAudioTimer);
        transcriptEditorAudioTimer = null;
      }
    }, 120);
  };
  audio.hidden = false;
  if (audio.getAttribute("src") !== src) {
    audio.src = src;
    audio.addEventListener("loadedmetadata", begin, {once:true});
    audio.load();
  } else begin();
}

function updateReportDraftState() {
  const textarea = $("reportDraftText"), status = $("reportDraftStatus");
  const ready = !$("reportDraftEditor").hidden && !textarea.disabled && reportDraftSaved !== null;
  const draftDirty = ready && textarea.value !== reportDraftSaved;
  const dirty = draftDirty || reportConclusionDirty();
  $("reportDraftSave").disabled = !draftDirty;
  status.className = draftDirty ? "dirty" : ready ? "saved" : "";
  if(!ready)meetingLabel(status,reportDraftLoading?'Загружаю локальный черновик…':'Черновик не загружен.');
  else meetingLabel(status,'{count} знаков · {state}',()=>({count:textarea.value.length,state:meetingUi(draftDirty?'есть несохранённые правки':'все правки сохранены')}));
  if (ready) {
    const canFinalize = !!currentReportReview.can_finalize;
    $("reportReviewApprove").disabled = !currentReportReview.can_approve || dirty;
    $("reportReviewSkip").disabled = !canFinalize || dirty;
  }
}

const fmtSec = s => s == null ? "?" : Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
const calDateKey = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
const calColors = {local:"#00D4FF", google:"#FFB300", yandex:"#FF2E63",
                   mail:"#A78BFA", caldav:"#64FFDA"};

function renderCalendar(data) {
  calendarState = data;
  const anchor = new Date(data.anchor + "T00:00:00");
  const count = data.view === "week" ? 7 : 1;
  const days = Array.from({length:count}, (_, i) => {
    const day = new Date(anchor); day.setDate(anchor.getDate() + i); return day;
  });
  const longFmt = new Intl.DateTimeFormat("ru-RU", {day:"numeric", month:"long", year:"numeric"});
  $("calRange").textContent = count === 1 ? longFmt.format(days[0])
    : `${days[0].toLocaleDateString("ru-RU", {day:"numeric",month:"short"})} — ${longFmt.format(days[6])}`;
  $("calDay").classList.toggle("primary", data.view === "day");
  $("calWeek").classList.toggle("primary", data.view === "week");
  const allDay = (data.events || []).filter(event => event.all_day);
  $("calAllDay").innerHTML = allDay.map(event =>
    `<div class="cal-all-pill" style="border-color:${calColors[event.provider] || calColors.caldav}" ` +
    `title="${esc(event.source || "")}">${esc(event.title)}</div>`).join("");

  const timed = (data.events || []).filter(event => !event.all_day);
  let startHour = 7, endHour = 22;
  timed.forEach(event => {
    const start = new Date(event.start), end = new Date(event.end);
    startHour = Math.max(0, Math.min(startHour, start.getHours()));
    endHour = Math.min(24, Math.max(endHour, end.getHours() + (end.getMinutes() ? 1 : 0)));
  });
  const hourHeight = 60, bodyHeight = (endHour - startHour) * hourHeight;
  const columns = days.map((day, index) =>
    `<div class="cal-col${calDateKey(day) === data.today ? " today" : ""}" data-day="${index}"></div>`).join("");
  const headers = days.map(day => `<div class="cal-head-day">${esc(day.toLocaleDateString("ru-RU", {weekday:"short",day:"numeric",month:"short"}))}</div>`).join("");
  const lines = Array.from({length:endHour-startHour}, (_, i) =>
    `<div class="cal-hour-line" style="top:${i*hourHeight}px"><span>${String(startHour+i).padStart(2,"0")}:00</span></div>`).join("");
  $("calTimeline").classList.toggle("cal-week", count === 7);
  $("calTimeline").closest(".cal-scroll")?.classList.toggle("cal-week-scroll", count === 7);
  $("calTimeline").innerHTML =
    `<div class="cal-head" style="grid-template-columns:repeat(${count},1fr)">${headers}</div>` +
    `<div class="cal-body" style="height:${bodyHeight}px;grid-template-columns:repeat(${count},1fr)">${columns}${lines}</div>`;
  const body = $("calTimeline").querySelector(".cal-body");
  timed.forEach(event => {
    const start = new Date(event.start), end = new Date(event.end);
    const dayIndex = days.findIndex(day => calDateKey(day) === calDateKey(start));
    if (dayIndex < 0) return;
    const topMinutes = Math.max(0, start.getHours()*60 + start.getMinutes() - startHour*60);
    const durationMinutes = Math.max(15, (end - start) / 60000);
    const el = document.createElement("div");
    const compact = durationMinutes < 45;
    el.className = "cal-event" + (compact ? " compact" : "");
    el.style.top = `${topMinutes / 60 * hourHeight}px`;
    el.style.height = `${Math.max(30, Math.min(durationMinutes, (endHour-startHour)*60-topMinutes) / 60 * hourHeight)}px`;
    el.style.borderColor = calColors[event.provider] || calColors.caldav;
    const timeText = `${start.toLocaleTimeString("ru-RU", {hour:"2-digit",minute:"2-digit"})}–${end.toLocaleTimeString("ru-RU", {hour:"2-digit",minute:"2-digit"})}`;
    el.title = [timeText, event.title, event.source, event.location].filter(Boolean).join(" · ");
    el.innerHTML = `<span class="cal-event-time">${timeText}</span>` +
      `<span class="cal-event-title">${esc(event.title)}</span>`;
    body.children[dayIndex].appendChild(el);
  });
  const now = new Date(), nowIndex = days.findIndex(day => calDateKey(day) === calDateKey(now));
  if (nowIndex >= 0 && now.getHours() >= startHour && now.getHours() < endHour) {
    const marker = document.createElement("div"); marker.className = "cal-now";
    marker.style.top = `${(now.getHours()*60 + now.getMinutes() - startHour*60) / 60 * hourHeight}px`;
    body.children[nowIndex].appendChild(marker);
  }
  renderCalendarSources(data.sources || [], data.errors || {});
  if (!$("calStatus").textContent && data.last_sync)
    studioLabel($("calStatus"),'последняя синхронизация: {date}',()=>({date:new Date(data.last_sync).toLocaleString(window.BlateroI18n?.locale||'ru-RU')}));
}

function wizardUi(text, params = {}) {
  return window.BlateroWizardI18n?.ui(text,params) ?? String(text ?? '').replace(
    /\{([a-zA-Z_]\w*)\}/g,(match,name)=>Object.hasOwn(params,name)?String(params[name]):match);
}

function renderWorkspaceStatus(id, data) {
  const el = $(id);
  if (!el) return;
  const stateName = String(data.state || "not_configured");
  el.className = `workspace-status ${stateName}`;
  window.BlateroWizardI18n?.remember(id,data);
  const message = window.BlateroWizardI18n?.message(data) || String(data.message || "Состояние рабочей папки неизвестно.");
  let details = "";
  if (data.used_files != null) {
    if (!/файл|files/i.test(message)) details = wizardUi(' · файлов: {count}',{count:data.used_files});
    if (data.chars != null && !/символ|characters/i.test(message))
      details += wizardUi(' · {count} символов',{count:Number(data.chars).toLocaleString(window.BlateroI18n?.locale || 'ru-RU')});
    if (data.secret_redactions) details += wizardUi(' · скрыто чувствительных фрагментов: {count}',{count:data.secret_redactions});
  }
  const diff = data.diff || {};
  if (diff && diff.baseline === false)
    details += ` · Δ +${(diff.added || []).length} ~${(diff.modified || []).length} −${(diff.deleted || []).length}`;
  el.textContent = message + details;
  if (data.limited) el.append(document.createTextNode(wizardUi(" · материал прочитан не полностью: достигнут лимит")));
  if (data.extraction_notice) {
    const notice = document.createElement("p");
    notice.textContent = wizardUi(data.extraction_notice);
    el.append(notice);
  }
  const read = Array.isArray(data.files) ? data.files : [];
  const skipped = Array.isArray(data.skipped_files) ? data.skipped_files : [];
  if (read.length || skipped.length) {
    const listDetails = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = wizardUi('Состав материалов: прочитано {read}, пропущено {skipped}',{read:read.length,skipped:skipped.length});
    listDetails.append(summary);
    const list = document.createElement("ul");
    for (const [items, accepted] of [[read, true], [skipped, false]]) {
      for (const item of items.slice(0, 100)) {
        const row = document.createElement("li");
        row.textContent = accepted
          ? wizardUi('{path} — {method}, {chars} символов{suffix}',{path:item.path,method:item.method || wizardUi('текст'),chars:item.chars,suffix:item.truncated ? wizardUi(', фрагмент') : ''})
          : wizardUi('{path} — пропущен: {reason}',{path:item.path,reason:item.message});
        list.append(row);
      }
      if (items.length > 100) {
        const more = document.createElement("li");
        more.textContent = wizardUi('Ещё {count} файлов; сузьте выбранную папку для подробного просмотра.',{count:items.length-100});
        list.append(more);
      }
    }
    listDetails.append(list);
    el.append(listDetails);
  }
}

function memoryKindLabel(kind) {
  return ({decision:'Решение',commitment:'Обещание',open_question:'Открытый вопрос',fact:'Проверенный факт'})[kind]||kind;
}
function memoryMetaUi(item) {
  return [item.owner?studioUi('ответственный: {p0}',{p0:item.owner}):'',item.due?studioUi('срок: {p0}',{p0:item.due}):'',item.scope_label||''].filter(Boolean).join(' · ');
}
function memoryDueUi(item) {
  return item.due_state==='overdue'?studioUi('просрочено'):item.due_state==='today'?studioUi('сегодня'):
    item.due_state==='soon'?studioUi('через {p0} дн.',{p0:Number(item.due_days)||0}):'';
}
function memoryStatusUi(data) {
  if(data.error)return String(data.message||'');
  const message=String(data.message||'Состояние памяти неизвестно.');
  const counts=message.match(/^В памяти (\d+) активных записей; областей: (\d+)\.(?: Требуют внимания: (\d+)\.)?$/);
  return counts?studioUi('Активных записей: {active} · областей: {scopes} · требуют внимания: {attention}',{active:counts[1],scopes:counts[2],attention:counts[3]||0}):studioUi(message);
}
function memoryKindOptions(selected) {
  return [["decision","Решение"],["commitment","Обещание"],
    ["open_question","Открытый вопрос"],["fact","Проверенный факт"]]
    .map(([value,label]) => `<option value="${value}"${value === selected ? " selected" : ""} ${studioBind(label)}>${esc(studioUi(label))}</option>`).join("");
}

function memoryHistory(item) {
  const history = Array.isArray(item.history) ? item.history : [];
  if (!history.length) return "";
  const action = {edit:"редактирование",status:"смена статуса",draft_merge:"обновление из отчёта"};
  return `<details class="memory-history"><summary>${studioText("история · ")}${history.length}</summary><ol>` +
    history.slice().reverse().map(value => `<li><b>v${Number(value.revision)||1} · ${studioText(action[value.action] || value.action || "изменение")}</b>` +
      `<span>${esc(String(value.text || ""))}</span>` +
      `<small>${value.owner?studioText('ответственный: {p0}',{p0:value.owner}):''} · ${value.due?studioText('срок: {p0}',{p0:value.due}):''} · ${esc(value.changed_at||'')}</small></li>`).join("") +
    `</ol></details>`;
}

function renderMemory(data) {
  memoryState = data || {configured:false,scopes:[],entries:[],draft:{entries:[]}};
  const status = $("memoryStatus");
  studioLabel(status,()=>({source:memoryStatusUi(memoryState)}));
  status.className = memoryState.error ? "error" : "";
  const scopes = memoryState.scopes || [];
  $("memoryScopes").innerHTML = scopes.map(scope =>
    `<span class="memory-scope"><b>${scope.scope === "client" ? studioText("клиент") : studioText("проект")}</b>` +
    `${esc(String(scope.label))}<small>${Number(scope.entries || 0)}${studioText(" записей")}</small>` +
    `<button data-memory-clear="${esc(String(scope.scope))}" ${studioAttrs("title","очистить только записи")} ${studioAttrs("aria-label","Очистить записи памяти {p1}",{p1:String(scope.label)})}>×</button>` +
    `<button data-memory-forget="${esc(String(scope.scope))}" ${studioAttrs("title","забыть область вместе со снимком")} ${studioAttrs("aria-label","Полностью забыть {p1}",{p1:String(scope.label)})}>⌫</button></span>`
  ).join("");
  $("memoryScopes").querySelectorAll("[data-memory-clear]").forEach(button => button.onclick = () => {
    const scope = button.dataset.memoryClear;
    const label = scopes.find(item => item.scope === scope)?.label || scope;
    if (confirm(studioUi("Удалить все подтверждённые записи памяти «{p0}»? Снимок файлов проекта сохранится.",{p0:label})))
      send({type:"memory_clear", scope});
  });
  $("memoryScopes").querySelectorAll("[data-memory-forget]").forEach(button => button.onclick = () => {
    const scope = button.dataset.memoryForget;
    const label = scopes.find(item => item.scope === scope)?.label || scope;
    if (confirm(studioUi("Полностью забыть «{p0}»? Будут удалены записи с историей, путь, снимок файлов и связи проекта. Отменить это нельзя.",{p0:label})))
      send({type:"memory_forget", scope});
  });
  fillSelect("memoryAddScope", scopes.map(scope => [scope.scope,
    `${scope.scope === "client" ? studioUi("клиент") : studioUi("проект")}: ${scope.label}`]),
    $("memoryAddScope").value || (scopes[0] && scopes[0].scope));
  const projectProfiles = Array.isArray(memoryState.project_profiles)
    ? memoryState.project_profiles : [];
  $("memoryLink").hidden = !projectProfiles.length;
  fillSelect("memoryLinkSource", projectProfiles.map(profile => [profile.id,
    studioUi("{p0} · {p1} записей{p2}",{p0:profile.label,p1:Number(profile.entries)||0,p2:profile.workspace_path ? ` · ${profile.workspace_path}` : ""})]),
    $("memoryLinkSource").value || (projectProfiles[0] && projectProfiles[0].id));

  const draftEntries = (memoryState.draft && memoryState.draft.entries) || [];
  $("memoryDraft").hidden = !draftEntries.length;
  $("memoryDraftEntries").innerHTML = draftEntries.map(item =>
    `<label class="memory-proposal"><input type="checkbox" data-memory-draft="${esc(String(item.id))}" checked>` +
    `<span><b>${studioText(memoryKindLabel(item.kind))} · ${studioText(item.scope==='client'?'клиент':'проект')}</b>` +
    `${esc(String(item.text || ""))}` +
    `${item.evidence ? `<small>${studioText("Основание: ")}${esc(String(item.evidence))}</small>` : ""}</span></label>`
  ).join("");

  const entries = memoryState.entries || [];
  $("memoryEntries").innerHTML = entries.length ? entries.map(item => {
    const resolved = item.status === "resolved";
    const meta = [item.owner ? studioUi("ответственный: {p0}",{p0:item.owner}) : "",
      item.due ? studioUi("срок: {p0}",{p0:item.due}) : "", item.scope_label || ""].filter(Boolean).join(" · ");
    const dueLabel = item.due_state === "overdue" ? studioUi("просрочено")
      : item.due_state === "today" ? studioUi("сегодня")
      : item.due_state === "soon" ? studioUi("через {p0} дн.",{p0:Number(item.due_days)||0}) : "";
    return `<article class="memory-entry${resolved ? " resolved" : ""}" data-memory-card="${esc(String(item.id))}">` +
      `<div class="memory-entry-head"><span>${studioText(memoryKindLabel(item.kind))}</span>` +
      `<small>${esc(String(item.scope_label || ""))}</small>${dueLabel ? `<b class="memory-due ${esc(String(item.due_state))}">${esc(dueLabel)}</b>` : ""}</div>` +
      `<p>${esc(String(item.text || ""))}</p>${meta ? `<div data-memory-meta>${esc(meta)}</div>` : ""}` +
      `${item.evidence ? `<details><summary>${studioText("основание")}</summary>${esc(String(item.evidence))}</details>` : ""}` +
      `${memoryHistory(item)}` +
      `<div class="memory-entry-actions"><button data-memory-status="${esc(String(item.id))}" data-next="${resolved ? "active" : "resolved"}">${resolved ? studioText("вернуть") : studioText("закрыть")}</button>` +
      `<button data-memory-edit="${esc(String(item.id))}">${studioText("изменить")}</button>` +
      `<button class="danger" data-memory-delete="${esc(String(item.id))}">${studioText("удалить")}</button></div>` +
      `<section class="memory-entry-edit" hidden><select data-memory-field="kind" ${studioAttrs("aria-label","Тип записи памяти")}>${memoryKindOptions(item.kind)}</select>` +
      `<textarea data-memory-field="text" maxlength="1200" ${studioAttrs("aria-label","Текст записи памяти")}>${esc(String(item.text || ""))}</textarea>` +
      `<input data-memory-field="owner" maxlength="160" ${studioAttrs("aria-label","Ответственный")} ${studioAttrs("placeholder","ответственный")} value="${esc(String(item.owner || ""))}">` +
      `<input data-memory-field="due" maxlength="160" ${studioAttrs("aria-label","Срок")} ${studioAttrs("placeholder","срок: 2026-08-15 или текст")} value="${esc(String(item.due || ""))}">` +
      `<div><button data-memory-cancel>${studioText("отмена")}</button><button class="primary" data-memory-save="${esc(String(item.id))}">${studioText("сохранить v")}${Number(item.revision)||1}</button></div></section></article>`;
  }).join("") : `<div class="memory-empty">${studioText("Подтверждённых решений и фактов пока нет.")}</div>`;
  for(const item of entries){
    const card=$("memoryEntries").querySelector('[data-memory-card="'+CSS.escape(String(item.id))+'"]');
    studioLabel(card?.querySelector('[data-memory-meta]'),()=>({source:memoryMetaUi(item)}));
    studioLabel(card?.querySelector('.memory-due'),()=>({source:memoryDueUi(item)}));
  }
  for(const option of $("memoryAddScope").options){
    const scope=scopes.find(x=>x.scope===option.value);
    if(scope)studioLabel(option,()=>({source:studioUi(scope.scope==='client'?'клиент':'проект')+': '+scope.label}));
  }
  for(const option of $("memoryLinkSource").options){
    const profile=projectProfiles.find(x=>x.id===option.value);
    if(profile)studioLabel(option,()=>({source:studioUi('{p0} · {p1} записей{p2}',{p0:profile.label,p1:Number(profile.entries)||0,p2:profile.workspace_path?' · '+profile.workspace_path:''})}));
  }
  $("memoryEntries").querySelectorAll("[data-memory-status]").forEach(button => button.onclick = () =>
    send({type:"memory_status", id:button.dataset.memoryStatus, status:button.dataset.next}));
  $("memoryEntries").querySelectorAll("[data-memory-delete]").forEach(button => button.onclick = () => {
    if (confirm(studioUi("Удалить эту запись из общей памяти?")))
      send({type:"memory_delete", id:button.dataset.memoryDelete});
  });
  $("memoryEntries").querySelectorAll("[data-memory-edit]").forEach(button => button.onclick = () => {
    const card = button.closest(".memory-entry");
    card.querySelector(".memory-entry-edit").hidden = false;
    card.querySelector('[data-memory-field="text"]').focus();
  });
  $("memoryEntries").querySelectorAll("[data-memory-cancel]").forEach(button => button.onclick = () => {
    button.closest(".memory-entry-edit").hidden = true;
  });
  $("memoryEntries").querySelectorAll("[data-memory-save]").forEach(button => button.onclick = () => {
    const id = button.dataset.memorySave, card = button.closest(".memory-entry");
    const item = entries.find(value => String(value.id) === id);
    const value = field => card.querySelector(`[data-memory-field="${field}"]`).value;
    if (!item || !value("text").trim()) return;
    button.disabled = true;
    send({type:"memory_update", id, revision:Number(item.revision)||1,
      kind:value("kind"), text:value("text"), owner:value("owner"), due:value("due")});
  });
  $("memoryExtract").disabled = !!memoryState.busy || !memoryState.configured || !memoryState.can_extract;
  studioAttr($("memoryExtract"),"title",()=>({source:"{value}",values:{value:!memoryState.configured ? studioUi("Сначала укажите клиента или проект")
    : (!memoryState.can_extract ? studioUi("Сначала сформируйте итоговый отчёт") : studioUi("Создать проверяемый черновик из отчёта"))}}));
  $("memoryAdd").disabled = !scopes.length || memoryState.writable === false;
  if(memoryState.writable === false){
    for(const id of ['memoryScopes','memoryEntries','memoryDraft','memoryLink'])
      $(id)?.querySelectorAll('button,input,select,textarea').forEach(node=>node.disabled=true);
  }
}

function modelSize(bytes,fallback='—') {
  if(typeof bytes!=='number'||!Number.isFinite(bytes)||bytes<0)return fallback;
  const en=window.BlateroI18n?.language==='en';
  const units=en?['B','KiB','MiB','GiB','TiB']:['Б','КБ','МБ','ГБ','ТБ'];
  let value=bytes,index=0;
  while(value>=1024&&index<units.length-1){value/=1024;index++;}
  return value.toLocaleString(window.BlateroI18n?.locale||'ru-RU',{maximumFractionDigits:index>1?1:0})+' '+units[index];
}
function modelStateLabel(item) {
  return ({ready:'готово к работе',partial:'нужно восстановить',missing:'не установлено'})[item.state]||item.state_label||item.state;
}
function serviceStatusText(data) {
  const messages={model_progress:'Операция модели: {detail}',model_failed:'Операция не завершена: {detail}',
    model_installed:'Модель установлена и проверена.',model_removed:'Компонент удалён; освобождено {freed}.',
    model_installing:'Начинаю установку…',model_removing:'Удаляю только управляемые файлы Blatero…',
    update_selection_cancelled:'Выбор файла отменён.',update_verified:'Подпись и контрольные суммы релиза проверены.',
    update_rejected:'Релиз не принят: {detail}',update_failed:'Обновление не подготовлено: {detail}',
    portable_full_required:'Portable обновляется полным пакетом в новой папке. Данные по умолчанию остаются в Документы/Blatero; для другого пути используйте BLATERO_DATA_DIR. Не копируйте новые файлы поверх старых.',
    update_staged:'Версия {version} подготовлена. Остановите Blatero и запустите ярлык снова — данные встреч не затрагиваются.',
    update_choosing:'Ожидаю выбор подписанного ZIP-релиза…',update_staging:'Повторно проверяю и копирую релиз…',
    update_cancelled:'Подготовленное обновление отменено.',update_rollback:'Откат к версии {version} подготовлен. Перезапустите Blatero.'};
  if(Object.hasOwn(messages,data.message_code)){
    const values={...(data.message_params||{})};
    if(data.message_code==='model_removed')values.freed=modelSize(values.freed_bytes,values.freed||'0 B');
    if(data.message_code==='update_rollback'&&!values.version)return studioUi('Откат к предыдущей версии подготовлен. Перезапустите Blatero.');
    return studioUi(messages[data.message_code],values);
  }
  return data.message?studioUi(data.message):'';
}
function renderModelManager(data) {
  modelManagerState = data.items ? data : {...modelManagerState,...data};
  const busy = String(modelManagerState.busy || "");
  const status = $("modelStatus");
  status.className = `workspace-status ${data.state === "error" ? "error" : (busy ? "scanning" : "ready")}`;
  studioLabel(status,()=>({source:"{value}",values:{value:serviceStatusText(data) || (busy
    ? studioUi("Операция выполняется. Не закрывайте сервер Blatero.")
    : studioUi("Состояние проверено. Установка и удаление доступны только на этом компьютере."))}}));
  $("modelRefresh").disabled = !!busy;
  if (!modelManagerState.items || !modelManagerState.items.length) return;
  $("modelSummary").innerHTML = [
    [studioUi("управляемые файлы"),modelSize(modelManagerState.managed_bytes,modelManagerState.managed_size || studioUi("0 Б"))],
    [studioUi("свободно на диске"),modelSize(modelManagerState.free_bytes,modelManagerState.free || "—")],
    [studioUi("корень моделей"),modelManagerState.root || "—"]
  ].map(item => `<div class="model-stat"><span>${studioText(item[0])}</span><strong>${esc(String(item[1]))}</strong></div>`).join("");
  $("modelList").innerHTML = modelManagerState.items.map(item => {
    const active = busy === item.id;
    const stateClass = active ? "busy" : item.state;
    const sizeLabel = item.installed
      ? `${item.size_estimated ? "≈ " : ""}${modelSize(item.size_bytes,item.size)}` : studioUi("загрузка ≈ {p0}",{p0:modelSize(item.estimate_bytes,item.estimate)});
    const install = item.valid ? "" : `<button class="primary model-install" data-model-id="${esc(item.id)}">${item.state === "partial" ? studioText("восстановить") : studioText("установить")}</button>`;
    const remove = item.removable ? `<button class="model-remove" data-model-id="${esc(item.id)}">${studioText("удалить")}</button>` : "";
    return `<article class="model-card ${stateClass}" data-model-card="${esc(item.id)}">` +
      `<div class="model-card-head"><div><span class="model-kind">${esc(item.kind)}</span>` +
      `<h4>${studioText(item.label)}</h4></div><span class="model-state">${active ? studioText("выполняется") : studioText(modelStateLabel(item))}</span></div>` +
      `<p class="model-description">${studioText(item.description)}</p>` +
      `<dl class="model-facts"><dt>${studioText("место")}</dt><dd>${esc(sizeLabel)}</dd>` +
      `<dt>${studioText("система")}</dt><dd>${studioText(item.requirements)}</dd>` +
      `<dt>${studioText("лицензия")}</dt><dd>${esc(item.license)}</dd></dl>` +
      `<div class="model-path">${esc(item.location)}</div>` +
      `<div class="model-actions">${item.selected ? `<span class="model-selected">${studioText("активная модель")}</span>` : ""}${install}${remove}</div></article>`;
  }).join("");
  $("modelList").querySelectorAll("button").forEach(button => button.disabled = !!busy);
  $("modelList").querySelectorAll(".model-install").forEach(button => button.onclick = () => {
    const item = modelManagerState.items.find(value => value.id === button.dataset.modelId);
    const estimate = item ? modelSize(item.estimate_bytes,item.estimate) : studioUi("неизвестно");
    if (confirm(studioUi("Установить «{p0}»?\n\nПотребуется примерно {p1}. Загрузка идёт только из закреплённого источника в локальный каталог Blatero.",{p0:item ? item.label : button.dataset.modelId,p1:estimate})))
      send({type:"models_install", model_id:button.dataset.modelId});
  });
  $("modelList").querySelectorAll(".model-remove").forEach(button => button.onclick = () => {
    const item = modelManagerState.items.find(value => value.id === button.dataset.modelId);
    if (confirm(studioUi("Удалить «{p0}» и освободить {p1}?\n\nУдаляются только управляемые файлы Blatero. Записи встреч и образец вашего голоса останутся.",{p0:item ? item.label : button.dataset.modelId,p1:item ? item.size : studioUi("место")})))
      send({type:"models_remove", model_id:button.dataset.modelId});
  });
  const legacy = modelManagerState.legacy_whisper || {};
  $("modelExternal").hidden = !(legacy.models || []).length;
  $("modelExternal").innerHTML = (legacy.models || []).length
    ? `<h4>${studioText("Обнаружен общий Whisper-cache: ")}${esc(modelSize(legacy.size_bytes,legacy.size || ""))}</h4><p>${studioText(legacy.note || "")}` +
      `${studioText(" Модели: ")}${legacy.models.map(esc).join(", ")}.</p><code>${esc(legacy.path || "")}</code>` : "";
}

function openModelManager() {
  $("modelOverlay").classList.add("show");
  $("modelStatus").className = "workspace-status scanning";
  studioLabel($("modelStatus"),"Считаю место и проверяю файлы моделей…");
  send({type:"models_status"});
  $("modelTitle").focus();
}

function renderUpdateManager(data) {
  updateManagerState = {...updateManagerState,...data};
  if (Object.prototype.hasOwnProperty.call(data,"selected")) selectedRelease = data.selected;
  const busy = !!updateManagerState.busy;
  const managed = !!updateManagerState.managed_install;
  const sourceUpdates = updateManagerState.source_updates_supported !== false;
  const pending = updateManagerState.pending || {};
  const pendingRollback = updateManagerState.pending_rollback || {};
  const status = $("updateStatus");
  status.className = `workspace-status ${data.state === "error" ? "error" : (busy ? "scanning" : "ready")}`;
  studioLabel(status,()=>({source:"{value}",values:{value:serviceStatusText(data) || (pending.version
    ? studioUi("Версия {p0} подготовлена — перезапустите Blatero.",{p0:pending.version})
    : (pendingRollback.to_version ? studioUi("Откат к {p0} подготовлен.",{p0:pendingRollback.to_version})
      : studioUi("Пакетных операций не ожидается.")))}}));
  $("updateSummary").innerHTML = [
    [studioUi("текущая версия"),updateManagerState.version || "dev"],
    [studioUi("программа"),updateManagerState.app_root || "—"],
    [studioUi("данные"),updateManagerState.data_root || "—"]
  ].map(item => `<div class="model-stat"><span>${studioText(item[0])}</span><strong>${esc(String(item[1]))}</strong></div>`).join("");
  $("updatePackage").innerHTML = selectedRelease
    ? `<strong>Blatero ${esc(selectedRelease.version)}</strong><span>${esc(modelSize(selectedRelease.size_bytes,String(selectedRelease.size || "")))} · ${esc(String(selectedRelease.file_count || 0))}${studioText(" файлов")}</span><code>SHA-256 ${esc(String(selectedRelease.sha256 || "").slice(0,24))}…</code>`
    : (pending.version ? `<strong>Blatero ${esc(pending.version)}</strong><span>${studioText("ожидает перезапуска")}</span>` : studioUi("Релиз ещё не выбран."));
  $("updateBrowse").disabled = busy;
  $("updateStage").disabled = busy || !managed || !sourceUpdates || !selectedRelease || !!pending.version;
  $("updateCancel").hidden = !pending.version && !pendingRollback.to_version;
  $("updateCancel").disabled = busy;
  $("updateRollback").disabled = busy || !managed || !updateManagerState.rollback_available || !!pending.version || !!pendingRollback.to_version;
  studioLabel($("updateRollbackText"),()=>({source:"{value}",values:{value:updateManagerState.rollback_available
    ? studioUi("Можно вернуться к версии {p0}. Откат также применяется при следующем запуске.",{p0:updateManagerState.rollback_version || studioUi("до последнего обновления")})
    : studioUi("После первого пакетного обновления здесь появится возврат к предыдущей версии.")}}));
  $("updateNote").className = `update-note${managed ? "" : " warning"}`;
  studioLabel($("updateNote"),()=>({source:"{value}",values:{value:!sourceUpdates
    ? studioUi("Portable обновляется полным пакетом в новой папке. Данные по умолчанию остаются в Документы/Blatero; для другого пути используйте BLATERO_DATA_DIR. Не копируйте новые файлы поверх старых.")
    : managed
    ? studioUi("Чтобы применить подготовленное действие: остановите сервер, затем снова запустите ярлык Blatero. При сбое зависимостей launcher автоматически восстановит предыдущие файлы.")
    : studioUi("Сейчас запущена рабочая Git-копия. Здесь можно проверить подпись релиза, но обновлять её пакетом нельзя — используйте Git. Пакетный режим включается установщиком.")}}));
}

function openUpdateManager() {
  $("updateOverlay").classList.add("show");
  $("updateStatus").className = "workspace-status scanning";
  studioLabel($("updateStatus"),"Проверяю ожидающие действия и резервную копию…");
  send({type:"update_status"});
  $("updateTitle").focus();
}

function renderCalendarSources(sources, errors) {
  $("calSources").innerHTML = sources.map(source => {
    const state = errors[source.id] ? studioUi("ошибка: {p0}",{p0:errors[source.id]})
      : (source.connected ? studioUi("подключён") : studioUi("нужна авторизация"));
    const google = source.provider === "google"
      ? `<button data-cal-action="google" data-id="${esc(source.id)}">OAuth Google</button>` : "";
    return `<div class="cal-source"><b>${esc(source.label)}</b><span class="source-state">${esc(state)}</span>` +
      `${google}<button data-cal-action="delete" data-id="${esc(source.id)}">${studioText("удалить")}</button></div>`;
  }).join("") || `<div class="privacy-note">${studioText("Внешние календари ещё не подключены. Локальное schedule.json уже показано.")}</div>`;
  studioValue($("calErrors"),Object.values(errors).join(" · "));
  $("calSources").querySelectorAll("[data-cal-action]").forEach(btn => btn.onclick = () => {
    if (btn.dataset.calAction === "google") {
      send({type:"calendar_google_connect", source_id:btn.dataset.id,
            anchor:calendarState.anchor, view:calendarState.view});
    } else if (confirm(studioUi("Удалить это подключение и локальный токен/пароль?"))) {
      send({type:"calendar_source_delete", source_id:btn.dataset.id,
            anchor:calendarState.anchor, view:calendarState.view});
    }
  });
}

function renderArchive(items) {
  archiveItems = items;
  $("archList").innerHTML = items.map(it => {
    const links = [
      `<a href="/?${new URLSearchParams({session:it.dir,panel:'tasks'})}">${studioText("задачи встречи ↗")}</a>`,
      it.transcript ? `<a target="_blank" href="/api/sessions/${encodeURIComponent(it.dir)}/transcript">${studioText("транскрипт целиком")}</a>` : "",
      it.report ? `<a target="_blank" href="/files/${encodeURIComponent(it.dir)}/report.md">${studioText("отчёт")}</a>` : "",
      it.evidence ? `<a target="_blank" href="/files/${encodeURIComponent(it.dir)}/evidence.html">${studioText("временная шкала")}</a>` : "",
      it.evidence_export ? `<a target="_blank" href="/files/${encodeURIComponent(it.dir)}/report.evidence.json">${studioText("опоры JSON")}</a>` : "",
      it.reference_evidence ? `<a target="_blank" href="/files/${encodeURIComponent(it.dir)}/evidence.reference.html">${studioText("проверка разметки")}</a>` : "",
      it.diarized_evidence ? `<a target="_blank" href="/files/${encodeURIComponent(it.dir)}/evidence.diarized.html">${studioText("кластеры голосов")}</a>` : "",
      it.docx ? `<a href="/files/${encodeURIComponent(it.dir)}/${encodeURIComponent(it.docx)}">docx</a>` : "",
    ].join("");
    const auds = it.audios.map(a =>
      `<div class="aud"><span>${a.name.includes("me") ? studioText("я") : studioText("собеседник")} · ${fmtSec(a.sec)} · ${a.mb}${studioText(" МБ")}</span>
       <audio controls preload="none" src="/files/${encodeURIComponent(it.dir)}/${encodeURIComponent(a.name)}"></audio>
       <button class="del-audio" data-session="${esc(it.dir)}" data-name="${esc(a.name)}">${studioText("удалить")}</button></div>`).join("");
    const removeAll = it.audios.length
      ? `<button class="danger del-all-audio" data-session="${esc(it.dir)}">${studioText("удалить всё аудио")}</button>` : "";
    const replay = it.audios.length && !it.live
      ? `<button class="open-replay" data-session="${esc(it.dir)}">${studioText("повторить")}${it.replay_count ? ` · ${it.replay_count}` : ""}</button>` : "";
    const lifecycle = it.live || it.replay_active ? "" :
      `<button class="session-export" data-session="${esc(it.dir)}">${studioText("зашифровать")}</button>
       <button class="session-purge" data-session="${esc(it.dir)}">${studioText("управлять данными")}</button>`;
    return `<div class="arch">
      <div class="ttl"><b>${esc(it.label)}</b>${it.live ? ` <span class="live">${studioText("● идёт запись")}</span>` : ""}</div>
      <div class="meta">${studioText(it.mtype)} · ${esc(it.date)} ${esc(it.time)} · ${esc(it.dir)}</div>
      ${auds}${links ? `<div>${links}</div>` : `<div class="meta">${studioText("файлов пока нет")}</div>`}
      ${(removeAll || replay || lifecycle) ? `<div class="arch-actions">${replay}${lifecycle}${removeAll}</div>` : ""}
    </div>`;
  }).join("") || `<span style="color:var(--dim)">${studioText("пусто")}</span>`;
  document.querySelectorAll(".del-audio").forEach(btn => btn.onclick = () => {
    if (confirm(studioUi("Безвозвратно удалить {p0}?",{p0:btn.dataset.name})))
      send({type:"delete_audio", session:btn.dataset.session, name:btn.dataset.name});
  });
  document.querySelectorAll(".del-all-audio").forEach(btn => btn.onclick = () => {
    if (confirm(studioUi("Безвозвратно удалить ВСЕ аудиофайлы этой встречи? Транскрипт и отчёт останутся.")))
      send({type:"delete_audio", session:btn.dataset.session});
  });
  document.querySelectorAll(".open-replay").forEach(btn => btn.onclick = () => {
    const item = archiveItems.find(value => value.dir === btn.dataset.session);
    if (item) openReplayLab(item);
  });
  document.querySelectorAll(".session-export").forEach(btn => btn.onclick = () =>
    openSessionLifecycle(btn.dataset.session, "export"));
  document.querySelectorAll(".session-purge").forEach(btn => btn.onclick = () =>
    openSessionLifecycle(btn.dataset.session, "purge"));
  renderAnalysisHub(items);
}

function lifecycleBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1).replace(".", ",")} КБ`;
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1).replace(".", ",")} МБ`;
  return `${(bytes / 1073741824).toFixed(2).replace(".", ",")} ГБ`;
}

function lifecycleSelectedLabel() {
  const item = archiveItems.find(value => value.dir === lifecycleSession);
  return item ? `${item.label} · ${item.dir}` : lifecycleSession || "—";
}

function openSessionLifecycle(session = "", focus = "") {
  lifecycleSession = session || lifecycleSession || $("selSession").value || "";
  lifecyclePurgePreview = null;
  $("lifecyclePurgeApply").disabled = true;
  studioLabel($("lifecyclePurgeResult"),"Ничего не рассчитано.");
  $("lifecycleSession").textContent = lifecycleSelectedLabel();
  $("archOverlay").classList.remove("show");
  $("lifecycleOverlay").classList.add("show");
  send({type:"lifecycle_status"});
  $("lifecycleTitle").focus();
  if (focus === "export") setTimeout(() => $("lifecyclePassword").focus(), 0);
  if (focus === "purge") setTimeout(() => $("lifecyclePurgeChecks").scrollIntoView(
    {behavior:"smooth",block:"center"}), 0);
}

function retentionValues() {
  return Object.fromEntries([...document.querySelectorAll("[data-retention]")].map(input =>
    [input.dataset.retention, Math.max(0, Math.min(36500, Number.parseInt(input.value || "0", 10) || 0))]));
}

function purgeCategories() {
  return [...$("lifecyclePurgeChecks").querySelectorAll("input:checked")].map(input => input.value);
}

function renderSessionLifecycle(data) {
  lifecycleState = data || lifecycleState;
  const status = $("lifecycleState");
  studioLabel(status,()=>({source:"{value}",values:{value:data.message || (data.busy ? studioUi("операция выполняется…") : studioUi("готово"))}}));
  status.className = `lifecycle-state ${data.error ? "error" : data.busy ? "" : "ready"}`;
  ["lifecycleExport","lifecycleImport","lifecyclePurgePreview","retentionSave"].forEach(id =>
    $(id).disabled = !!data.busy);
  studioValue($("lifecycleSession"),lifecycleSelectedLabel());
  const packages = Array.isArray(data.packages) ? data.packages : [];
  $("lifecyclePackages").innerHTML = packages.slice(0, 8).map(item =>
    `<div class="lifecycle-package"><span>${esc(item.name)} · ${lifecycleBytes(item.bytes)}</span>
      <a href="${esc(item.download_url)}">${studioText("скачать")}</a>
      <button class="danger" data-package-delete="${esc(item.name)}" ${studioAttrs("title","удалить пакет")} ${studioAttrs("aria-label","Удалить пакет {p4}",{p4:item.name})}>×</button></div>`).join("") ||
    `<span class="privacy-note">${studioText("Зашифрованных пакетов пока нет.")}</span>`;
  $("lifecyclePackages").querySelectorAll("[data-package-delete]").forEach(button => {
    button.onclick = () => {
      const name = button.dataset.packageDelete;
      if (confirm(studioUi("Безвозвратно удалить зашифрованный пакет {p0}? Скачанные ранее копии останутся вне Blatero.",{p0:name})))
        send({type:"session_package_delete", name, confirmation:`DELETE PACKAGE:${name}`});
    };
  });
  const inventory = data.privacy_inventory || {groups:[],files:0,bytes:0,external:[]};
  $("privacyInventory").innerHTML = `<strong>${Number(inventory.files)||0}${studioText(" файлов · ")}${lifecycleBytes(inventory.bytes)}</strong>` +
    (inventory.groups || []).map(group => `<div><span>${esc(String(group.label || group.key))}</span>` +
      `<b>${Number(group.files)||0} · ${lifecycleBytes(group.bytes)}</b></div>`).join("") +
    (inventory.external || []).map(item => `<small>${studioText("вне каталога: ")}${esc(String(item))}</small>`).join("");
  const policy = data.retention_policy || {};
  document.querySelectorAll("[data-retention]").forEach(input => {
    if (document.activeElement !== input) input.value = Number(policy[input.dataset.retention]) || 0;
  });
  const retention = data.retention || {items:[]};
  const retentionItems = Array.isArray(retention.items) ? retention.items : [];
  $("retentionPreview").innerHTML = retention.error ? esc(retention.error)
    : retention.files ? `<strong>${Number(retention.sessions) || 0}${studioText(" встреч · ")}${Number(retention.files) || 0}${studioText(" файлов · ")}${lifecycleBytes(retention.bytes)}</strong>
      <div>${retentionItems.slice(0,6).map(item => studioUi("{p0}: {p1} дн. · {p2}",{p0:esc(item.session),p1:Number(item.age_days)||0,p2:lifecycleBytes(item.bytes)})).join("<br>")}</div>`
    : studioUi("По сохранённым срокам очередь пуста.");
  $("retentionApply").disabled = !!data.busy || !retention.files;
  if (data.purge_preview) {
    lifecyclePurgePreview = data.purge_preview;
    $("lifecyclePurgeResult").innerHTML = data.purge_preview.files
      ? `<strong>${Number(data.purge_preview.files)}${studioText(" файлов · ")}${lifecycleBytes(data.purge_preview.bytes)}</strong>
        <div>${(data.purge_preview.sample || []).map(item => esc(item)).join("<br>")}</div>`
      : studioUi("Для выбранных категорий файлов нет.");
    $("lifecyclePurgeApply").disabled = !!data.busy || !data.purge_preview.files;
  }
  if (data.download_url) {
    const link = document.createElement("a");
    link.href = data.download_url;
    link.download = (data.exported && data.exported.name) || "";
    document.body.append(link); link.click(); link.remove();
    $("lifecyclePassword").value = "";
  } else if (!data.error && data.message && data.message.includes(studioUi("импортирована"))) {
    $("lifecyclePassword").value = "";
  }
}

function renderAnalysisHub(items) {
  const list = $("analysisSessionList");
  if (!list) return;
  const current = $("selSession").value;
  const ordered = [...items].sort((left, right) =>
    Number(right.dir === current) - Number(left.dir === current));
  if (!ordered.length) {
    list.innerHTML = '<div class="analysis-empty">'+meetingText('Записей пока нет. Создайте встречу и начните запись.')+'</div>';
    return;
  }
  list.innerHTML = ordered.map(item => {
    const audios = item.audios || [];
    const isCurrent = item.dir === current;
    const audioState = item.live ? meetingText("идёт запись")
      : audios.length ? meetingText('{count} аудиодор. · {time}',{count:audios.length,time:fmtSec(Math.max(...audios.map(audio=>Number(audio.sec)||0)))})
        : meetingText("аудио нет");
    const reviewUrl = item.diarized_evidence
      ? `/files/${encodeURIComponent(item.dir)}/evidence.diarized.html` : "";
    const replayButton = audios.length && !item.live
      ? `<button class="analysis-replay" data-session="${esc(item.dir)}"><svg class="ui-icon" aria-hidden="true"><use href="#icon-analysis"/></svg><span>${meetingText('разобрать запись{suffix}',{suffix:item.replay_count?` · ${item.replay_count}`:''})}</span></button>`
      : `<button disabled>${meetingText(item.live ? "дождитесь остановки" : "нет записи для разбора")}</button>`;
    const review = reviewUrl
      ? `<a class="analysis-review" target="_blank" rel="noopener" href="${reviewUrl}"><svg class="ui-icon" aria-hidden="true"><use href="#icon-edit"/></svg><span><strong>${meetingText('Переименовать говорящих')}</strong><small>${meetingText('для этой встречи · без банка голосов')}</small></span></a>`
      : '<span class="analysis-review-missing">'+meetingText('имена появятся после прогона с диаризацией')+'</span>';
    return `<article class="analysis-session${isCurrent ? " current" : ""}">
      <div class="analysis-session-copy"><div class="analysis-session-title"><strong>${esc(item.label)}</strong>${isCurrent ? '<span>'+meetingText('текущая')+'</span>' : ""}</div>
        <p>${esc(item.mtype)} · ${esc(item.date)} ${esc(item.time)} · ${audioState}</p></div>
      <div class="analysis-session-actions">${replayButton}${review}</div>
    </article>`;
  }).join("");
  list.querySelectorAll(".analysis-replay").forEach(button => button.onclick = () => {
    const item = archiveItems.find(value => value.dir === button.dataset.session);
    if (item) openReplayLab(item);
  });
}

function openAnalysisHub() {
  $("analysisSessionList").innerHTML = '<div class="analysis-empty">'+meetingText('Загружаю архив…')+'</div>';
  $("analysisOverlay").classList.add("show");
  send({type:"archive"});
}

function qualityPct(value) {
  return typeof value === "number" ? `${(value * 100).toLocaleString(window.BlateroI18n?.locale||'ru-RU',{minimumFractionDigits:1,maximumFractionDigits:1})}%` : "—";
}

function qualityStateLabel(value) {
  return ({missing:studioUi("нет эталона"), draft:studioUi("черновик"), reviewed:studioUi("подтверждён"),
           invalid:studioUi("повреждён")})[value] || value;
}

function qualityMetricCard(label, value, note) {
  return `<article class="quality-metric"><span>${studioText(label)}</span><strong>${qualityPct(value)}</strong><small>${studioText(note)}</small></article>`;
}

function renderQualityCatalog() {
  const reviewed = Number(qualityCatalog.reviewed) || 0;
  const target = Number(qualityCatalog.target_min) || 10;
  $("qualityProgress").innerHTML = `${reviewed} / ${target}<small>${studioText("подтверждено · минимум")}</small>`;
  const metrics = qualityCatalog.metrics;
  $("qualityMetrics").innerHTML = metrics
    ? qualityMetricCard("WER", metrics.wer, studioUi("ошибки слов · ниже лучше"))
      + qualityMetricCard("DER", metrics.der, studioUi("ошибки разделения голосов"))
      + qualityMetricCard("JER", metrics.jer, studioUi("пересечение голосовых кластеров"))
      + qualityMetricCard(studioUi("ошибка канала"), metrics.channel_error_rate, studioUi("микрофон ↔ звук встречи"))
      + qualityMetricCard(studioUi("ложное эхо"), metrics.false_suppression_rate, studioUi("потерянные содержательные реплики"))
    : `<article class="quality-metric"><span>${studioText("метрики")}</span><strong>—</strong><small>${studioText("Подтвердите первый эталон после сверки с аудио.")}</small></article>`;
  const filter = $("qualityFilter").value;
  const items = (qualityCatalog.items || []).filter(item => filter === "all" || item.state === filter);
  if (!items.length) {
    $("qualityList").innerHTML = `<div class="analysis-empty">${studioText("В этой группе записей пока нет.")}</div>`;
    return;
  }
  $("qualityList").innerHTML = items.map(item => {
    const metricLine = item.metrics
      ? `WER ${qualityPct(item.metrics.wer)} · DER ${qualityPct(item.metrics.der)} · JER ${qualityPct(item.metrics.jer)}`
      : (item.error || studioUi("метрики появятся после создания эталона"));
    const action = item.state === "missing"
      ? `<button data-action="create">${studioText("создать черновик")}</button>`
      : item.state === "invalid"
        ? `<button disabled>${studioText("нужна ручная проверка файла")}</button>`
        : `<button data-action="open">${item.state === "reviewed" ? studioText("просмотреть") : studioText("продолжить разметку")}</button>`;
    return `<article class="quality-item ${esc(item.state)}" data-session="${esc(item.session)}" data-journal="${esc(item.journal)}">
      <div><h4>${esc(item.label)}</h4><p>${esc(item.session)} · ${esc(item.journal)} · ${Number(item.utterances)||0}${studioText(" реплик · ")}${Number(item.audio)||0}${studioText(" аудиодор.")}</p>
        <p class="quality-item-metrics">${esc(metricLine)}</p></div>
      <div class="quality-item-actions"><span class="quality-state">${esc(qualityStateLabel(item.state))}</span>${action}</div>
    </article>`;
  }).join("");
  $("qualityList").querySelectorAll("[data-action]").forEach(button => button.onclick = async () => {
    const item = button.closest(".quality-item");
    button.disabled = true;
    if (button.dataset.action === "create") await createQualityReference(item.dataset.session, item.dataset.journal);
    else await openQualityReference(item.dataset.session, item.dataset.journal);
  });
}

async function loadQualityCatalog() {
  $("qualityStatus").className = "";
  studioLabel($("qualityStatus"),"Собираю локальные эталоны и метрики…");
  try {
    const response = await fetch("/api/quality-benchmark", {cache:"no-store"});
    if (!response.ok) throw new Error(await response.text());
    qualityCatalog = await response.json();
    renderQualityCatalog();
    $("qualityStatus").className = "saved";
    studioLabel($("qualityStatus"),()=>({source:"{value}",values:{value:studioUi("{p0} записей: {p1} черновиков, {p2} подтверждено.",{p0:Number(qualityCatalog.total)||0,p1:Number(qualityCatalog.draft)||0,p2:Number(qualityCatalog.reviewed)||0})}}));
  } catch (error) {
    $("qualityStatus").className = "error";
    studioValue($("qualityStatus"),error.message || String(error));
    $("qualityList").innerHTML = `<div class="analysis-empty">${studioText("Эталонный набор не загружен.")}</div>`;
  }
}

function openQualityLab() {
  if (closeQualityEditor() === false) return false;
  $("analysisOverlay").classList.remove("show");
  $("qualityOverlay").classList.add("show");
  $("qualityTitle").focus();
  return loadQualityCatalog();
}

function guardCalibrationValue(value, unit) {
  if (typeof value !== "number") return "—";
  if (unit === "ratio") return `${(value * 100).toFixed(value < .01 ? 2 : 1).replace(".",",")}%`;
  return value >= 1000
    ? studioUi("{p0} с",{p0:(value / 1000).toFixed(value % 1000 ? 1 : 0).replace(".",",")})
    : studioUi("{p0} мс",{p0:Math.round(value)});
}

function guardCalibrationRange(value, unit) {
  if (!value) return "—";
  return `${guardCalibrationValue(value.warning, unit)} / ${guardCalibrationValue(value.critical, unit)}`;
}

function guardMetricLabel(id,fallback='') {
  return ({stt_queue:'Очередь STT',stt_latency:'Задержка live STT',wav_backlog:'Отставание WAV',clipping:'Перегрузка сигнала'})[id]||fallback||id;
}
function guardBlockerLabel(detail) {
  if(detail.code==='more_reviewed')return studioUi('Подтвердите ещё {count} эталонных встреч.',{count:detail.count});
  if(detail.code==='more_telemetry')return studioUi('Нужны числовые срезы минимум из {count} встреч: {metrics}.',{
    count:detail.sessions,metrics:(detail.metrics||[]).map(id=>studioUi(guardMetricLabel(id))).join(', ')});
  if(detail.code==='profile_supported')return studioUi('Текущий профиль уже подтверждён собранными данными.');
  return detail.message||detail.code||'';
}
function renderGuardCalibration() {
  const data = guardCalibrationState || {};
  const corpus = data.corpus || {}, telemetry = data.telemetry || {};
  const ready = data.status === "ready";
  $("guardCalibrationReadiness").className = `guard-calibration-readiness ${ready ? "ready" : "waiting"}`;
  $("guardCalibrationReadiness").innerHTML = `${Number(corpus.reviewed)||0} / ${Number(corpus.required)||10}<small>${studioText("проверенных встреч")}</small>`;
  $("guardCalibrationSummary").innerHTML = [
    [studioUi("числовые срезы"), Number(telemetry.sample_records)||0, studioUi("{p0} встреч",{p0:Number(telemetry.sample_sessions)||0})],
    ["live STT", Number((data.metrics||[]).find(item => item.id === "stt_latency")?.samples)||0, studioUi("валидных задержек")],
    [studioUi("события"), Number(telemetry.opened_issues)||0, studioUi("{p0} встреч",{p0:Number(telemetry.issue_sessions)||0})],
  ].map(item => `<article><span>${studioText(item[0])}</span><strong>${item[1]}</strong><small>${esc(item[2])}</small></article>`).join("");
  $("guardCalibrationRows").innerHTML = (data.metrics || []).map(metric => {
    const observation = metric.samples
      ? `p50 ${guardCalibrationValue(metric.p50,metric.unit)} · p95 ${guardCalibrationValue(metric.p95,metric.unit)} · max ${guardCalibrationValue(metric.max,metric.unit)}<small>${Number(metric.samples)||0}${studioText(" замеров · ")}${Number(metric.sessions)||0}${studioText(" встреч")}</small>`
      : `${studioText("нет числовых срезов")}<small>${studioText("начнут собираться во время следующей записи")}</small>`;
    const verdict = metric.verdict === "tighten" ? studioUi("можно сделать чувствительнее")
      : metric.verdict === "keep" ? studioUi("оставить") : studioUi("данных недостаточно");
    return `<tr class="${esc(metric.verdict||"insufficient")}"><th>${studioText(guardMetricLabel(metric.id,metric.label))}</th>
      <td ${studioAttrs('data-label','наблюдение')}>${observation}</td><td ${studioAttrs('data-label','сейчас')}>${guardCalibrationRange(metric.current,metric.unit)}<small>${studioText("внимание / критично")}</small></td>
      <td ${studioAttrs('data-label','рекомендация')}>${guardCalibrationRange(metric.recommended,metric.unit)}</td><td ${studioAttrs('data-label','решение')}><span>${studioText(verdict)}</span></td></tr>`;
  }).join("") || `<tr><td colspan="5">${studioText("Измерения не найдены.")}</td></tr>`;
  const blockers = () => Array.isArray(data.blocker_details) ? data.blocker_details.map(guardBlockerLabel)
    : Array.isArray(data.blockers) ? data.blockers : [];
  studioLabel($("guardCalibrationBlockers"),()=>({source:'{value}',values:{value:ready
    ? studioUi('Профиль рассчитан.')+' '+(blockers().join(' · ')||studioUi('Он не изменится без вашего подтверждения.'))
    : studioUi('Пороги не меняются.')+' '+(blockers().join(' · ')||studioUi('Нужны реальные проверенные встречи.'))}}));
  if(data.privacy_code==='numeric_only')studioLabel($("guardCalibrationPrivacy"),"Только числа и коды событий; текст реплик, имена и названия аудиоустройств не записываются.");
  else studioValue($("guardCalibrationPrivacy"),data.privacy || "");
  $("guardCalibrationConfirmed").checked = false;
  $("guardCalibrationConfirmed").disabled = !data.can_apply;
  $("guardCalibrationApply").disabled = true;
  $("guardCalibrationStatus").className = ready ? "saved" : "";
  studioLabel($("guardCalibrationStatus"),()=>({source:"{value}",values:{value:data.can_apply
    ? studioUi("Есть доказательное изменение. Проверьте строки и подтвердите применение.")
    : (blockers()[0] || studioUi("Текущий профиль оставлен без изменений."))}}));
}

async function loadGuardCalibration() {
  $("guardCalibrationStatus").className = "";
  studioLabel($("guardCalibrationStatus"),"Считаю локальные измерения…");
  try {
    const response = await fetch("/api/audio-guard-calibration", {cache:"no-store"});
    if (!response.ok) throw new Error(await response.text());
    guardCalibrationState = await response.json();
    renderGuardCalibration();
  } catch (error) {
    $("guardCalibrationStatus").className = "error";
    studioValue($("guardCalibrationStatus"),error.message || String(error));
    $("guardCalibrationRows").innerHTML = `<tr><td colspan="5">${studioText("Калибровка не загружена.")}</td></tr>`;
  }
}

function openGuardCalibration() {
  $("analysisOverlay").classList.remove("show");
  $("guardCalibrationOverlay").classList.add("show");
  $("guardCalibrationTitle").focus();
  loadGuardCalibration();
}

async function applyGuardCalibration() {
  if (!guardCalibrationState || !guardCalibrationState.can_apply
      || !$("guardCalibrationConfirmed").checked) return;
  $("guardCalibrationApply").disabled = true;
  studioLabel($("guardCalibrationStatus"),"Сохраняю подтверждённый профиль…");
  try {
    const response = await fetch("/api/audio-guard-calibration/apply", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({fingerprint:guardCalibrationState.fingerprint, confirmed:true})});
    if (!response.ok) throw new Error(await response.text());
    guardCalibrationState = await response.json();
    renderGuardCalibration();
    $("guardCalibrationStatus").className = "saved";
    studioLabel($("guardCalibrationStatus"),"Профиль сохранён. Он действует со следующей записи.");
  } catch (error) {
    $("guardCalibrationStatus").className = "error";
    studioValue($("guardCalibrationStatus"),error.message || String(error));
    $("guardCalibrationApply").disabled = !$("guardCalibrationConfirmed").checked;
  }
}

async function createQualityReference(session, journal) {
  studioLabel($("qualityStatus"),"Создаю независимую копию транскрипта…");
  try {
    const response = await fetch(`/api/quality-benchmark/${encodeURIComponent(session)}/${encodeURIComponent(journal)}/create`, {
      method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"});
    if (!response.ok) throw new Error(await response.text());
    qualityReference = await response.json();
    await loadQualityCatalog();
    showQualityEditor();
  } catch (error) {
    $("qualityStatus").className = "error";
    studioLabel($("qualityStatus"),()=>({source:"{value}",values:{value:studioUi("Черновик не создан: {p0}",{p0:error.message})}}));
    renderQualityCatalog();
  }
}

async function openQualityReference(session, journal) {
  studioLabel($("qualityStatus"),"Загружаю реплики эталона…");
  try {
    const response = await fetch(`/api/quality-benchmark/${encodeURIComponent(session)}/${encodeURIComponent(journal)}`, {cache:"no-store"});
    if (!response.ok) throw new Error(await response.text());
    qualityReference = await response.json();
    showQualityEditor();
  } catch (error) {
    $("qualityStatus").className = "error";
    studioValue($("qualityStatus"),error.message || String(error));
  }
}

function showQualityEditor() {
  $("qualityList").hidden = true;
  $("qualityMetrics").hidden = true;
  $("qualityToolbar").hidden = true;
  $("qualityEditor").hidden = false;
  studioValue($("qualityEditorTitle"),qualityReference.label || qualityReference.session);
  studioLabel($("qualityEditorMeta"),()=>({source:"{value}",values:{value:studioUi("{p0} → {p1} · {p2} реплик",{p0:qualityReference.journal,p1:qualityReference.reference,p2:qualityReference.total})}}));
  $("qualityConfirmed").checked = false;
  $("qualitySearch").value = "";
  renderQualityReference();
}

function closeQualityEditor() {
  if (!$("qualityEditor")) return;
  const dirty = $("qualityUtterances").querySelector(".dirty,.quality-split-panel");
  if (dirty && !confirm(studioUi("Закрыть разметку и потерять несохранённую правку?"))) return false;
  if (qualityAudioTimer) clearInterval(qualityAudioTimer);
  qualityAudioTimer = null;
  $("qualityAudio").pause();
  $("qualityEditor").hidden = true;
  $("qualityList").hidden = false;
  $("qualityMetrics").hidden = false;
  $("qualityToolbar").hidden = false;
  qualityReference = null;
  return true;
}

function qualityFilteredUtterances() {
  const query = $("qualitySearch").value.trim().toLocaleLowerCase("ru-RU");
  const items = (qualityReference && qualityReference.utterances) || [];
  return query ? items.filter(item => [item.text,item.speaker_name,item.speaker_role,
    item.speaker_id,item.source].some(value => String(value||"").toLocaleLowerCase("ru-RU").includes(query))) : items;
}

function qualityOption(value, current, label) {
  return `<option value="${esc(value)}"${value === current ? " selected" : ""} ${studioBind(label)}>${esc(studioUi(label))}</option>`;
}

function qualityCardChanges(card, item) {
  const fields = {
    text:card.querySelector("textarea").value.trim(),
    start_ms:Math.round(Number(card.querySelector('[data-field="start"]').value) * 1000),
    end_ms:Math.round(Number(card.querySelector('[data-field="end"]').value) * 1000),
    speaker_role:card.querySelector('[data-field="role"]').value,
    source:card.querySelector('[data-field="source"]').value,
    status:card.querySelector('[data-field="status"]').value,
    speaker_name:card.querySelector('[data-field="name"]').value.trim(),
    speaker_id:card.querySelector('[data-field="speaker"]').value.trim()
  };
  const changes = {};
  Object.entries(fields).forEach(([key,value]) => {
    const previous = ["start_ms","end_ms"].includes(key) ? Number(item[key]) : String(item[key] ?? "");
    if (value !== previous) changes[key] = value;
  });
  return changes;
}

function renderQualityReference() {
  if (!qualityReference) return;
  const reviewed = qualityReference.state === "reviewed";
  $("qualityFinalize").hidden = reviewed;
  $("qualityFinalize").disabled = reviewed || !$("qualityConfirmed").checked;
  $("qualityReopen").hidden = !reviewed;
  $("qualityConfirmed").disabled = reviewed;
  const items = qualityFilteredUtterances();
  $("qualityUtterances").innerHTML = items.length ? items.map(item => {
    const speaker = item.speaker_name || item.speaker_role || item.speaker_id;
    return `<article class="quality-utterance ${item.status === "suppressed" ? "suppressed" : ""}" data-event="${esc(item.event_id)}">
      <div class="quality-utterance-head"><button class="quality-time" data-action="play" ${item.audio_file ? "" : "disabled"}>${esc(formatTranscriptMs(item.start_ms))}</button>
        <strong>${esc(speaker)}</strong><span>${esc(item.source)} · #${Number(item.sequence)||0}${item.audio_file ? ` · ${esc(item.audio_file)}` : studioText(" · аудио не найдено")}</span></div>
      <textarea maxlength="12000" spellcheck="true"
        ${studioAttrs("aria-label","Текст реплики {p8}, {p9}",{p8:formatTranscriptMs(item.start_ms),p9:speaker})}
        ${reviewed ? "disabled" : ""}>${esc(item.text)}</textarea>
      <div class="quality-fields">
        <label>${studioText("начало, сек")}<input data-field="start" type="number" min="0" step="0.1" value="${(Number(item.start_ms)/1000).toFixed(3)}" ${reviewed ? "disabled" : ""}></label>
        <label>${studioText("конец, сек")}<input data-field="end" type="number" min="0" step="0.1" value="${(Number(item.end_ms)/1000).toFixed(3)}" ${reviewed ? "disabled" : ""}></label>
        <label>${studioText("сторона")}<select data-field="role" ${reviewed ? "disabled" : ""}>${qualityOption("Я",item.speaker_role,studioUi("я / локальный"))}${qualityOption("Собеседник",item.speaker_role,studioUi("участник встречи"))}</select></label>
        <label>${studioText("канал")}<select data-field="source" ${reviewed ? "disabled" : ""}>${qualityOption("microphone",item.source,studioUi("микрофон"))}${qualityOption("loopback",item.source,studioUi("звук встречи"))}${qualityOption("import",item.source,studioUi("импорт"))}${qualityOption("manual",item.source,studioUi("ручной"))}${qualityOption("synthetic",item.source,studioUi("синтетический"))}</select></label>
        <label>${studioText("статус")}<select data-field="status" ${reviewed ? "disabled" : ""}>${qualityOption("final",item.status,studioUi("содержательная"))}${qualityOption("suppressed",item.status,studioUi("подавлена / эхо"))}</select></label>
        <label>${studioText("имя")}<input data-field="name" maxlength="160" value="${esc(item.speaker_name)}" ${reviewed ? "disabled" : ""}></label>
        <label>${studioText("ID голоса")}<input data-field="speaker" maxlength="200" value="${esc(item.speaker_id)}" ${reviewed ? "disabled" : ""}></label>
        ${reviewed ? "" : `<button class="quality-split" data-action="split">${studioText("разделить")}</button>`}
        <button class="quality-save" data-action="save" disabled>${studioText("сохранить")}</button>
      </div></article>`;
  }).join("") : `<div class="analysis-empty">${studioText("Реплики по фильтру не найдены.")}</div>`;
  $("qualityUtterances").querySelectorAll(".quality-utterance").forEach(card => {
    const item = items.find(value => value.event_id === card.dataset.event);
    card.querySelectorAll("textarea,input,select").forEach(control => control.addEventListener("input", () => {
      const dirty = Object.keys(qualityCardChanges(card,item)).length > 0;
      card.classList.toggle("dirty", dirty);
      card.querySelector('[data-action="save"]').disabled = !dirty;
    }));
  });
}

async function saveQualityUtterance(card) {
  const item = (qualityReference.utterances || []).find(value => value.event_id === card.dataset.event);
  if (!item) return;
  const changes = qualityCardChanges(card,item);
  if (!Object.keys(changes).length) return;
  const button = card.querySelector('[data-action="save"]');
  button.disabled = true; card.classList.add("saving");
  try {
    const response = await fetch(`/api/quality-benchmark/${encodeURIComponent(qualityReference.session)}/${encodeURIComponent(qualityReference.journal)}/utterances/${encodeURIComponent(item.event_id)}`, {
      method:"PATCH", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({revision:item.revision,changes})});
    if (!response.ok) throw new Error(await response.text());
    const result = await response.json();
    const index = qualityReference.utterances.findIndex(value => value.event_id === item.event_id);
    qualityReference.utterances[index] = result.utterance;
    renderQualityReference();
    $("qualityStatus").className = "saved";
    studioLabel($("qualityStatus"),"Правка сохранена только в эталонной копии.");
  } catch (error) {
    card.classList.remove("saving"); button.disabled = false;
    $("qualityStatus").className = "error";
    studioLabel($("qualityStatus"),()=>({source:"{value}",values:{value:studioUi("Не сохранено: {p0}",{p0:error.message})}}));
  }
}

function openQualitySplit(card, item) {
  $("qualityUtterances").querySelectorAll(".quality-split-panel").forEach(panel => panel.remove());
  const midpoint = (Number(item.start_ms) + Number(item.end_ms)) / 2000;
  card.insertAdjacentHTML("beforeend", `<section class="quality-split-panel">
    <div><strong>${studioText("Разделить склеенную реплику")}</strong><p>${studioText("Укажите границу по звуку и разнесите текст между двумя частями. Первая сохранит исходный ID, вторая получит новый.")}</p></div>
    <label>${studioText("граница, сек")}<input data-split="at" type="number" min="${(Number(item.start_ms)/1000+.2).toFixed(3)}" max="${(Number(item.end_ms)/1000-.2).toFixed(3)}" step="0.1" value="${midpoint.toFixed(3)}"></label>
    <label class="quality-split-text">${studioText("текст до границы")}<textarea data-split="left" maxlength="12000">${esc(item.text)}</textarea></label>
    <label class="quality-split-text">${studioText("текст после границы")}<textarea data-split="right" maxlength="12000" ${studioAttrs("placeholder","Перенесите сюда вторую реплику")}></textarea></label>
    <label>${studioText("сторона второй части")}<select data-split="role">${qualityOption("Я",item.speaker_role,studioUi("я / локальный"))}${qualityOption("Собеседник",item.speaker_role,studioUi("участник встречи"))}</select></label>
    <label>${studioText("канал второй части")}<select data-split="source">${qualityOption("microphone",item.source,studioUi("микрофон"))}${qualityOption("loopback",item.source,studioUi("звук встречи"))}${qualityOption("import",item.source,studioUi("импорт"))}${qualityOption("manual",item.source,studioUi("ручной"))}</select></label>
    <label>${studioText("имя второй части")}<input data-split="name" maxlength="160" value="${esc(item.speaker_name)}"></label>
    <label>${studioText("ID голоса второй части")}<input data-split="speaker" maxlength="200" value="${esc(item.speaker_id)}"></label>
    <div class="quality-split-actions"><button data-action="split-cancel">${studioText("отмена")}</button><button class="primary" data-action="split-confirm">${studioText("разделить и сохранить")}</button></div>
  </section>`);
  card.querySelector('[data-split="right"]').focus();
}

async function saveQualitySplit(card, item) {
  const panel = card.querySelector(".quality-split-panel");
  if (!panel) return;
  const button = panel.querySelector('[data-action="split-confirm"]');
  button.disabled = true;
  try {
    const response = await fetch(`/api/quality-benchmark/${encodeURIComponent(qualityReference.session)}/${encodeURIComponent(qualityReference.journal)}/utterances/${encodeURIComponent(item.event_id)}/split`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({revision:item.revision,
        at_ms:Math.round(Number(panel.querySelector('[data-split="at"]').value)*1000),
        left_text:panel.querySelector('[data-split="left"]').value,
        right_text:panel.querySelector('[data-split="right"]').value,
        right_changes:{speaker_role:panel.querySelector('[data-split="role"]').value,
          source:panel.querySelector('[data-split="source"]').value,
          speaker_name:panel.querySelector('[data-split="name"]').value.trim(),
          speaker_id:panel.querySelector('[data-split="speaker"]').value.trim()}})});
    if (!response.ok) throw new Error(await response.text());
    qualityReference = await response.json();
    renderQualityReference();
    $("qualityStatus").className = "saved";
    studioLabel($("qualityStatus"),"Склеенная реплика разделена в эталонной копии.");
  } catch (error) {
    button.disabled = false;
    $("qualityStatus").className = "error";
    studioLabel($("qualityStatus"),()=>({source:"{value}",values:{value:studioUi("Не разделено: {p0}",{p0:error.message})}}));
  }
}

function playQualityUtterance(item) {
  if (!item || !item.audio_file || !qualityReference) return;
  if (qualityAudioTimer) clearInterval(qualityAudioTimer);
  const audio = $("qualityAudio");
  const src = `/files/${encodeURIComponent(qualityReference.session)}/${encodeURIComponent(item.audio_file)}`;
  const start = Math.max(0,Number(item.start_ms)||0)/1000;
  const end = Math.max(start+.8,(Number(item.end_ms)||0)/1000);
  const begin = () => {
    audio.currentTime = start; audio.play().catch(error => {
      $("qualityStatus").className = "error"; studioLabel($("qualityStatus"),()=>({source:"{value}",values:{value:studioUi("Аудио не запущено: {p0}",{p0:error.message})}}));
    });
    qualityAudioTimer = setInterval(() => {
      if (audio.currentTime >= end || audio.ended) {
        audio.pause(); clearInterval(qualityAudioTimer); qualityAudioTimer = null;
      }
    },120);
  };
  audio.hidden = false;
  if (audio.getAttribute("src") !== src) {
    audio.src = src; audio.addEventListener("loadedmetadata",begin,{once:true}); audio.load();
  } else begin();
}

async function setQualityReviewed(reviewed) {
  if (!qualityReference) return;
  if (reviewed && $("qualityUtterances").querySelector(".dirty")) {
    alert(studioUi("Сначала сохраните текущую правку реплики.")); return;
  }
  if (reviewed && $("qualityUtterances").querySelector(".quality-split-panel")) {
    alert(studioUi("Сначала завершите или отмените разделение реплики.")); return;
  }
  $("qualityFinalize").disabled = true;
  try {
    const response = await fetch(`/api/quality-benchmark/${encodeURIComponent(qualityReference.session)}/${encodeURIComponent(qualityReference.journal)}/review`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({reviewed,confirmed:reviewed && $("qualityConfirmed").checked})});
    if (!response.ok) throw new Error(await response.text());
    qualityReference = await response.json();
    renderQualityReference();
    await loadQualityCatalog();
    $("qualityStatus").className = "saved";
    studioLabel($("qualityStatus"),()=>({source:"{value}",values:{value:reviewed
      ? studioUi("Эталон подтверждён и вошёл в общие метрики.")
      : studioUi("Эталон возвращён в черновик и исключён из общих метрик.")}}));
  } catch (error) {
    $("qualityStatus").className = "error";
    studioValue($("qualityStatus"),error.message || String(error));
  } finally { $("qualityFinalize").disabled = false; }
}

function replayFileUrl(run, name) {
  return `/api/sessions/${encodeURIComponent(replaySession.dir)}/replays/${encodeURIComponent(run.run_id)}/files/${encodeURIComponent(name)}`;
}
function replayPct(value) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "—";
}
function replayMetric(label, value, baseline, delta, lowerIsBetter=true) {
  const changed = typeof delta === "number" && Math.abs(delta) >= 0.00005;
  const cls = !changed ? "" : ((lowerIsBetter ? delta < 0 : delta > 0) ? "better" : "worse");
  const sign = typeof delta === "number" && delta > 0 ? "+" : "";
  return `<div class="replay-metric"><span>${studioText(label)}</span><b class="${cls}">${replayPct(value)}</b>` +
    (typeof baseline === "number" ? `<small>${studioText("было ")}${replayPct(baseline)} · Δ ${sign}${(delta * 100).toFixed(1)}${studioText(" п.п.")}</small>` : "") + `</div>`;
}
function replayStateLabel(state) {
  return ({queued:studioUi("очередь"),running:studioUi("выполняется"),completed:studioUi("готово"),error:studioUi("ошибка"),
           cancelled:studioUi("отменён"),interrupted:studioUi("прерван")})[state] || state;
}
function replayAecLabel(value) {
  return ({off:studioUi("выключен"),correlation:studioUi("корреляционный"),
           auto:studioUi("автовыбор"),native:studioUi("нативный → резерв")})[value] || value;
}
function replayEmbeddingLabel(value) {
  return ({nemo:"NeMo TitaNet","3dspeaker":"3D-Speaker",
           nemo_en_titanet_small:"NeMo TitaNet"})[value] || value || "3D-Speaker";
}
function replayWhen(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("ru-RU", {
    day:"2-digit", month:"2-digit", year:"numeric",
    hour:"2-digit", minute:"2-digit"});
}
function updateReplaySelection() {
  const known = new Set(replayRunsState.map(run => run.run_id));
  replaySelected = new Set([...replaySelected].filter(id => known.has(id)));
  const selectedRuns = replayRunsState.filter(run => replaySelected.has(run.run_id));
  const ready = selectedRuns.length >= 2 && selectedRuns.length <= 4
    && selectedRuns.every(run => run.state === "completed" && run.stt_current !== false);
  $("replayCompare").disabled = !ready;
  studioLabel($("replayCompareCount"),()=>({source:"{value}",values:{value:!selectedRuns.length
    ? studioUi("выберите 2–4 готовых варианта")
    : studioUi("{p0} выбрано{p1}",{p0:selectedRuns.length,p1:ready ? studioUi(" · можно сравнить") : studioUi(" · дождитесь готовности")})}}));
}
function renderReplayRuns(runs) {
  const owner = replayEpoch;
  replayRunsState = runs;
  const box = $("replayRuns");
  if (!runs.length) {
    box.innerHTML = `<div class="replay-empty">${studioText("Экспериментов ещё нет. Первый прогон создаст независимую точку сравнения.")}</div>`;
    updateReplaySelection();
    return;
  }
  box.innerHTML = runs.map(run => {
    const options = run.options || {}, comparison = run.comparison || {}, quality = comparison.quality || {};
    const batch = run.batch || {};
    const recommendation = run.recommendation || {};
    const replay = comparison.replay || {}, baseline = comparison.baseline || {}, delta = comparison.delta || {};
    const metrics = comparison.replay
      ? replayMetric("WER", replay.wer, baseline.wer, delta.wer) +
        replayMetric("DER", replay.der, baseline.der, delta.der) +
        replayMetric("JER", replay.jer, baseline.jer, delta.jer) +
        replayMetric(studioUi("raw уверенность модели"), quality.average_confidence, null, null, false)
      : `<div class="replay-metric"><span>${studioText("реплик")}</span><b>${Number(quality.utterances)||0}</b></div>` +
        `<div class="replay-metric"><span>${studioText("слов")}</span><b>${Number(quality.words)||0}</b></div>` +
        `<div class="replay-metric"><span>${studioText("голосов")}</span><b>${Number(quality.speakers)||0}</b></div>` +
        replayMetric(studioUi("raw уверенность модели"), quality.average_confidence, null, null, false);
    const outputs = run.outputs || [];
    const links = [
      outputs.includes("transcript.md") ? `<a target="_blank" href="${replayFileUrl(run,"transcript.md")}">${studioText("транскрипт")}</a>` : "",
      outputs.includes("transcript.diarized.md") ? `<a target="_blank" href="${replayFileUrl(run,"transcript.diarized.md")}">${studioText("с кластерами")}</a>` : "",
      outputs.includes("comparison.json") ? `<a target="_blank" href="${replayFileUrl(run,"comparison.json")}">${studioText("метрики JSON")}</a>` : "",
      outputs.includes("audio-clean.wav") ? `<a target="_blank" href="${replayFileUrl(run,"audio-clean.wav")}">AEC WAV</a>` : "",
      run.evidence_url ? `<a target="_blank" href="${esc(run.evidence_url)}">${studioText("голоса и имена")}</a>` : "",
    ].join("");
    const running = ["queued","running"].includes(run.state);
    const staleStt = run.stt_current === false;
    const balance = quality.speaker_balance || {};
    const speakerWarning = balance.needs_review
      ? `<div class="replay-message replay-hint-error">${studioText("Кластеры несбалансированы: крупнейший содержит ")}${Math.round((Number(balance.dominant_share)||0)*100)}${studioText("% размеченной речи")}${Number(balance.tiny_clusters) ? `${studioText(", коротких/сомнительных кластеров: ")}${Number(balance.tiny_clusters)}` : ""}${studioText(". Число голосов не подтверждено — проверьте примеры на слух.")}</div>` : "";
    const hint = run.hint_summary && run.hint_summary.first_question
      ? `<div class="replay-message">${studioText("Контрольный следующий ход: ")}${esc(run.hint_summary.first_question)}</div>`
      : run.hint_summary && run.hint_summary.error
        ? `<div class="replay-message replay-hint-error">${studioText("Подсказка не сформирована: ")}${esc(run.hint_summary.error)}</div>` : "";
    const ref = comparison.reference_state === "draft" ? studioUi(" · метрики по черновому эталону")
      : comparison.reference_state === "missing" ? studioUi(" · эталона нет")
        : comparison.reference_state === "incompatible" ? studioUi(" · эталон не размечает эту дорожку") : "";
    const recommended = recommendation.recommended
      ? `<div class="replay-recommendation">${studioText("Рекомендуемый вариант · ")}${esc(recommendation.reason||"")}</div>` : "";
    const sttWarning = staleStt
      ? `<div class="replay-message replay-hint-error">${studioText("Устаревшие параметры распознавания: результат оставлен для истории, но его нельзя применять или сравнивать. Запустите Replay заново.")}</div>` : "";
    return `<article class="replay-run ${esc(run.state||"error")}${recommendation.recommended ? " recommended" : ""}">
      <div class="replay-run-head"><label class="replay-select"><input type="checkbox" data-run="${esc(run.run_id)}" ${replaySelected.has(run.run_id) ? "checked" : ""} ${run.state === "completed" && !staleStt ? "" : "disabled"}><span><strong>${esc(batch.label || run.source && run.source.audio_name || run.run_id)}</strong>${batch.batch_id ? `<small>${studioText("матрица ")}${Number(batch.index)||"?"}/${Number(batch.total)||"?"}</small>` : ""}</span></label><span class="replay-state-wrap">${recommendation.recommended ? '<span class="replay-best">BEST</span>' : ""}<span class="replay-state">${esc(replayStateLabel(run.state||"error"))}</span></span></div>
      <div class="replay-config">${esc(replayWhen(run.created_at))} · ${esc(run.source && run.source.audio_name || "")} · Whisper ${esc(options.model||"—")}${studioText(" · язык русский · AEC ")}${esc(replayAecLabel(options.aec||"off"))} · ${options.diarization ? `${studioText("диаризация ")}${Number(options.speakers) ? Number(options.speakers)+studioText(" голосов") : studioText("авто")} · ${esc(replayEmbeddingLabel(options.diarization_embedding||run.diarization_embedding))}` : studioText("без диаризации")}${run.transcript_reused_from ? studioText(" · транскрипт готовый") : ""}${ref}</div>
      <div class="replay-progress"><span style="width:${Math.max(0,Math.min(100,Number(run.progress)||0))}%"></span></div>
      <div class="replay-message">${esc(run.message||"")}</div>
      ${sttWarning}${run.state === "completed" ? `${recommended}<div class="replay-metrics">${metrics}</div><div class="replay-metric-help">${studioText("WER — ошибки слов; DER/JER — ошибки разделения голосов. Для всех трёх ниже лучше. Raw уверенность — некалиброванная внутренняя метрика модели: она не является точностью и не сравнивается между движками.")}</div>${speakerWarning}` : ""}${hint}
      <div class="replay-run-actions">${links}${run.state === "completed" ? `<button class="replay-timeline" data-run="${esc(run.run_id)}">${studioText("▶ исходный темп и задержки")}</button>` : ""}${run.state === "completed" && !staleStt && options.diarization && !run.evidence_url ? `<button class="replay-apply" data-run="${esc(run.run_id)}">${studioText("переименовать говорящих")}</button>` : ""}${running ? `<button class="replay-cancel" data-run="${esc(run.run_id)}">${studioText("остановить")}</button>` : `<button class="danger replay-delete" data-run="${esc(run.run_id)}">${studioText("удалить результат")}</button>`}</div>
    </article>`;
  }).join("");
  box.querySelectorAll(".replay-cancel").forEach(button => button.onclick = () => { if(owner===replayEpoch) replayCancel(button.dataset.run); });
  box.querySelectorAll(".replay-delete").forEach(button => button.onclick = () => { if(owner===replayEpoch) replayDelete(button.dataset.run); });
  box.querySelectorAll(".replay-apply").forEach(button => button.onclick = () => { if(owner===replayEpoch) replayApply(button.dataset.run); });
  box.querySelectorAll(".replay-timeline").forEach(button => button.onclick = () => openReplayTimeline(button.dataset.run));
  box.querySelectorAll(".replay-select input").forEach(input => input.onchange = () => {
    if (input.checked && replaySelected.size >= 4) {
      input.checked = false;
      studioLabel($("replayStatus"),"Одновременно можно сравнить не более четырёх вариантов.");
      return;
    }
    if (input.checked) replaySelected.add(input.dataset.run);
    else replaySelected.delete(input.dataset.run);
    updateReplaySelection();
  });
  updateReplaySelection();
}
async function loadReplayRuns() {
  if (!replaySession) return;
  const owner = replayEpoch, ticket = ++replayListTicket, dir = replaySession.dir;
  const current = () => owner === replayEpoch && ticket === replayListTicket;
  clearTimeout(replayTimer); replayTimer = null;
  try {
    const response = await fetch(`/api/sessions/${encodeURIComponent(dir)}/replays`, {cache:"no-store"});
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json(), runs = data.runs || [];
    if (!current()) return;
    renderReplayRuns(runs);
    clearTimeout(replayTimer); replayTimer = null;
    if (runs.some(run => ["queued","running"].includes(run.state)))
      replayTimer = setTimeout(() => { if(current()) loadReplayRuns(); }, 1000);
  } catch (error) { if(current()) studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Не удалось загрузить прогоны: {p0}",{p0:error.message})}})); }
}
function replayTime(ms) {
  const sec = Math.max(0, Math.floor((Number(ms) || 0) / 1000));
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2,"0")}`;
}
function replayVariantAudio(variant, sourceAudio) {
  return variant.audio_kind === "cleaned"
    ? replayFileUrl({run_id:variant.run_id}, "audio-clean.wav")
    : `/files/${encodeURIComponent(replaySession.dir)}/${encodeURIComponent(sourceAudio)}`;
}
function stopReplayCompareAudio() {
  const audio = $("replayCompareAudio");
  audio.pause();
  if (replayCompareTimer) clearInterval(replayCompareTimer);
  replayCompareTimer = null;
  document.querySelectorAll(".replay-diff-play.playing").forEach(button => {
    button.classList.remove("playing"); studioValue(button,"▶");
  });
}
async function playReplayDifference(button, url, startMs, endMs) {
  stopReplayCompareAudio();
  const audio = $("replayCompareAudio");
  audio.src = url;
  const start = Math.max(0, Number(startMs) / 1000);
  const end = Math.max(start + .4, Number(endMs) / 1000);
  const seek = () => { audio.currentTime = Math.min(start, Number.isFinite(audio.duration) ? audio.duration : start); };
  if (audio.readyState >= 1) seek(); else audio.onloadedmetadata = seek;
  button.classList.add("playing"); studioValue(button,"■");
  try {
    await audio.play();
    replayCompareTimer = setInterval(() => {
      if (audio.ended || audio.currentTime >= end) stopReplayCompareAudio();
    }, 120);
  } catch (error) {
    stopReplayCompareAudio();
    studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Фрагмент не воспроизведён: {p0}",{p0:error.message})}}));
  }
}
function renderReplayComparison(data) {
  const variants = data.variants || [], rows = data.rows || [], summary = data.summary || {};
  const panel = $("replayComparePanel");
  panel.hidden = false;
  studioLabel($("replayCompareSummary"),()=>({source:"{value}",values:{value:rows.length
    ? studioUi("Найдено {p0} заметных расхождений из {p1} опорных реплик. Прослушивание использует исходный WAV, а после AEC — очищенный вариант.",{p0:rows.length,p1:Number(summary.anchor_utterances)||0})
    : studioUi("Заметных текстовых расхождений не найдено. Метрики вариантов всё равно остаются в карточках ниже.")}}));
  $("replayCompareVariants").style.setProperty("--replay-variants", variants.length);
  $("replayCompareVariants").innerHTML = variants.map((variant, index) => {
    const options = variant.options || {};
    return `<article><span>${String.fromCharCode(65 + index)}</span><div><strong>${esc(variant.label||variant.run_id)}</strong><small>Whisper ${esc(options.model||"—")} · AEC ${esc(replayAecLabel(options.aec||"off"))}${options.diarization ? ` · ${esc(replayEmbeddingLabel(options.diarization_embedding))} / ${Number(options.threshold).toFixed(2)}` : ""}</small></div>${variant.recommended ? '<b class="replay-best">BEST</b>' : ""}${options.diarization ? `<button class="replay-compare-apply" data-run="${esc(variant.run_id)}">${studioText("в проверку голосов")}</button>` : ""}</article>`;
  }).join("");
  $("replayCompareRows").style.setProperty("--replay-variants", variants.length);
  $("replayCompareRows").innerHTML = rows.length ? rows.map(row => {
    const byRun = new Map((row.cells || []).map(cell => [cell.run_id, cell]));
    const cells = variants.map(variant => {
      const cell = byRun.get(variant.run_id) || {};
      const confidence = typeof cell.confidence === "number" ? ` · raw ${Math.round(cell.confidence*100)}%` : "";
      return `<div class="replay-diff-cell"><div><span>${esc(cell.speaker||"голос не указан")}${confidence}</span><button class="replay-diff-play" data-run="${esc(variant.run_id)}" ${studioAttrs("title","прослушать этот вариант")}>▶</button></div><p>${esc(cell.text||"— нет текста —")}</p></div>`;
    }).join("");
    return `<article class="replay-diff-row" data-start="${Number(row.start_ms)||0}" data-end="${Number(row.end_ms)||0}"><header><b>${replayTime(row.start_ms)}</b><span>${studioText("различие ")}${Math.round((Number(row.difference)||0)*100)}%</span></header><div class="replay-diff-grid">${cells}</div></article>`;
  }).join("") : `<div class="replay-empty">${studioText("Тексты совпадают в пределах порога сравнения.")}</div>`;
  $("replayCompareVariants").querySelectorAll(".replay-compare-apply").forEach(button =>
    button.onclick = () => replayApply(button.dataset.run));
  $("replayCompareRows").querySelectorAll(".replay-diff-play").forEach(button => {
    button.onclick = () => {
      const row = button.closest(".replay-diff-row");
      const variant = variants.find(item => item.run_id === button.dataset.run);
      if (row && variant) playReplayDifference(
        button, replayVariantAudio(variant, data.source_audio),
        Number(row.dataset.start), Number(row.dataset.end));
    };
  });
  panel.scrollIntoView({behavior:"smooth",block:"start"});
}

function replayDelay(ms) {
  return Number.isFinite(Number(ms)) ? studioUi("{p0} с",{p0:(Number(ms)/1000).toFixed(1).replace(".0","")}) : "—";
}
function replayTimelineAudioUrl(data) {
  return data.audio_kind === "cleaned"
    ? replayFileUrl({run_id:data.run_id}, "audio-clean.wav")
    : `/files/${encodeURIComponent(replaySession.dir)}/${encodeURIComponent(data.source_audio)}`;
}
function stopReplayTimeline() {
  const audio = $("replayTimelineAudio");
  audio.pause(); replayTimelineActive = -1;
  document.querySelectorAll(".replay-timeline-utterance.active").forEach(item => item.classList.remove("active"));
}
function focusReplayTimelineAt(ms, play=false) {
  const audio = $("replayTimelineAudio");
  audio.currentTime = Math.max(0, Number(ms)||0) / 1000;
  if (play) audio.play().catch(error => {
    studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Запись не воспроизведена: {p0}",{p0:error.message})}}));
  });
  updateReplayTimelineCursor();
}
function updateReplayTimelineCursor() {
  if (!replayTimelineData) return;
  const now = $("replayTimelineAudio").currentTime * 1000;
  const events = replayTimelineData.utterances || [];
  let active = -1;
  for (let index=0; index<events.length; index++) {
    if (Number(events[index].start_ms) <= now) active = index;
    if (Number(events[index].start_ms) > now) break;
  }
  if (active === replayTimelineActive) return;
  replayTimelineActive = active;
  document.querySelectorAll(".replay-timeline-utterance.active").forEach(item => item.classList.remove("active"));
  const card = document.querySelector(`.replay-timeline-utterance[data-index="${active}"]`);
  if (card) {
    card.classList.add("active");
    if (!$("replayTimelineAudio").paused)
      card.scrollIntoView({behavior:"smooth",block:"nearest"});
  }
}
function replayTimelineWindows() {
  if (!replayTimelineData) return [];
  const events = replayTimelineData.utterances || [], defaults = replayTimelineData.simulation || {};
  const stt = Math.max(0, Number(defaults.stt_ms)||0);
  const llm = Math.max(200, Number($("replayTimelineLlm").value)*1000||6000);
  const silence = Math.max(500, Number($("replayTimelineSilence").value)*1000||4000);
  const cooldown = Math.max(0, Number(defaults.cooldown_ms)||0);
  const windows = []; let lastTrigger = -Infinity;
  for (let index=0; index<events.length; index++) {
    const event = events[index], next = events[index+1];
    const end = Number(event.end_ms)||0;
    const nextStart = next ? Number(next.start_ms)||0 : Number(replayTimelineData.duration_ms)||end;
    const trigger = end + stt + silence;
    if (next && nextStart-end < stt+silence) continue;
    if (trigger-lastTrigger < cooldown) continue;
    const ready = trigger+llm, remaining = nextStart-ready;
    windows.push({index, trigger, ready, nextStart, remaining,
      ontime:!next || remaining >= 0, final:!next});
    lastTrigger = trigger;
    if (windows.length >= 250) break;
  }
  return windows;
}
function renderReplayTimelineSimulation() {
  if (!replayTimelineData) return;
  const windows = replayTimelineWindows();
  const useful = windows.filter(item => item.ontime).length;
  const measured = (replayTimelineData.simulation||{}).basis === "measured";
  $("replayTimelineSimulation").innerHTML = windows.length
    ? `<strong>${useful}${studioText(" из ")}${windows.length}</strong>${studioText(" окон: подсказка успевает до следующей реплики. ")}${measured ? studioText("Время LLM взято из локальных замеров.") : studioText("Время LLM — оценка: измените его и проверьте сценарий.")}`
    : studioUi("При этих порогах достаточно длинных пауз для автоподсказки не найдено.");
  $("replayTimelineWindows").innerHTML = windows.length ? windows.map(item => {
    const state = item.final ? studioUi("последняя пауза") : item.ontime
      ? studioUi("запас {p0}",{p0:replayDelay(item.remaining)}) : studioUi("опоздание {p0}",{p0:replayDelay(-item.remaining)});
    return `<button class="replay-timeline-window ${item.ontime ? "ontime" : "late"}" data-ms="${item.trigger}"><b>${replayTime(item.trigger)}</b><span>${studioText("готово ")}${replayTime(item.ready)} · ${state}</span></button>`;
  }).join("") : `<div class="replay-empty">${studioText("Нет окон при выбранных параметрах.")}</div>`;
  $("replayTimelineWindows").querySelectorAll("[data-ms]").forEach(button =>
    button.onclick = () => focusReplayTimelineAt(button.dataset.ms, true));
}
function renderReplayTimeline(data) {
  replayTimelineData = data; replayTimelineActive = -1;
  const stt = data.stt_latency || {}, pulse = data.pulse_latency || {}, simulation = data.simulation || {};
  studioLabel($("replayTimelineSummary"),()=>({source:"{value}",values:{value:studioUi("{p0} · {p1} · {p2} реплик. Звук и подсветка идут по исходным меткам.",{p0:data.source_audio,p1:replayTime(data.duration_ms),p2:data.utterances.length})}}));
  $("replayTimelineMetrics").innerHTML = [
    ["STT p50",replayDelay(stt.p50_ms),stt.kind === "measured" ? studioUi("{p0} live-замеров",{p0:stt.samples}) : studioUi("оценка")],
    ["STT p95",replayDelay(stt.p95_ms),stt.kind === "measured" ? studioUi("хвост задержки") : studioUi("нет live-меток")],
    [studioUi("подсказка p50"),replayDelay(pulse.p50_ms),pulse.kind === "measured" ? studioUi("{p0} замеров",{p0:pulse.samples}) : studioUi("оценка")],
    [studioUi("без тайминга"),String(Number(pulse.legacy_without_timing)||0),studioUi("старые подсказки")],
  ].map(item => `<div><span>${item[0]}</span><b>${item[1]}</b><small>${item[2]}</small></div>`).join("");
  $("replayTimelineLlm").value = (Number(simulation.llm_ms||6000)/1000).toFixed(1);
  $("replayTimelineSilence").value = (Number(simulation.silence_ms||4000)/1000).toFixed(1);
  $("replayTimelineUtterances").innerHTML = data.utterances.map((item,index) =>
    `<button class="replay-timeline-utterance" data-index="${index}" data-ms="${Number(item.start_ms)||0}"><span>${replayTime(item.start_ms)}</span><b>${esc(item.speaker||"голос")}</b><p>${esc(item.text||"")}</p></button>`).join("");
  $("replayTimelineUtterances").querySelectorAll("[data-ms]").forEach(button =>
    button.onclick = () => focusReplayTimelineAt(button.dataset.ms, true));
  const audio = $("replayTimelineAudio");
  audio.src = replayTimelineAudioUrl(data);
  audio.playbackRate = Number($("replayTimelineSpeed").value)||1;
  renderReplayTimelineSimulation();
  $("replayTimelinePanel").hidden = false;
  $("replayTimelinePanel").scrollIntoView({behavior:"smooth",block:"start"});
}
async function openReplayTimeline(runId) {
  if (!replaySession) return;
  const owner = replayEpoch, ticket = ++replayTimelineTicket;
  stopReplayTimeline();
  $("replayTimelinePanel").hidden = false;
  studioLabel($("replayTimelineSummary"),"Собираю исходные метки и локальные замеры…");
  try {
    const response = await fetch(`/api/sessions/${encodeURIComponent(replaySession.dir)}/replays/${encodeURIComponent(runId)}/timeline`, {cache:"no-store"});
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    if (owner !== replayEpoch || ticket !== replayTimelineTicket) return;
    renderReplayTimeline(data);
    studioLabel($("replayStatus"),"Таймлайн готов. Симуляция не обращается к LLM.");
  } catch (error) {
    if (owner !== replayEpoch || ticket !== replayTimelineTicket) return;
    $("replayTimelinePanel").hidden = true;
    studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Таймлайн не открыт: {p0}",{p0:error.message})}}));
  }
}
async function compareReplaySelected() {
  if (!replaySession) return;
  const owner = replayEpoch, ticket = ++replayCompareTicket;
  const runIds = [...replaySelected];
  $("replayCompare").disabled = true;
  studioLabel($("replayStatus"),"Сопоставляю реплики по временной шкале…");
  try {
    const data = await replayMutation(
      `/api/sessions/${encodeURIComponent(replaySession.dir)}/replays/compare`,
      "POST", {run_ids:runIds});
    if (owner !== replayEpoch || ticket !== replayCompareTicket) return;
    renderReplayComparison(data);
    studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Сравнение готово: {p0} расхождений.",{p0:Number(data.summary && data.summary.difference_rows)||0})}}));
  } catch (error) {
    if (owner !== replayEpoch || ticket !== replayCompareTicket) return;
    studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Не удалось сравнить: {p0}",{p0:error.message})}}));
  } finally { if (owner === replayEpoch && ticket === replayCompareTicket) updateReplaySelection(); }
}
function updateReplayControls() {
  if (!replaySession) return;
  const audio = $("replayAudio").value, isMic = audio.startsWith("audio-me");
  const render = isMic ? `audio-guest${audio.slice("audio-me".length)}` : "";
  const hasRender = replaySession.audios.some(item => item.name === render);
  $("replayAec").disabled = !isMic || !hasRender;
  if ($("replayAec").disabled) $("replayAec").value = "off";
  $("replaySpeakers").disabled = $("replayThreshold").disabled =
    $("replayEmbedding").disabled = !$("replayDiarization").checked;
  $("replayMatrixStart").disabled = $("replayMatrix").value === "aec"
    && (!isMic || !hasRender);
  studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:!isMic ? studioUi("Системную дорожку можно распознать и разделить, AEC ей не нужен.")
    : !hasRender ? studioUi("Парной системной дорожки нет — сравнение AEC недоступно.")
    : studioUi("Готово к запуску. Исходные файлы останутся без изменений.")}}));
}
function replayOptions() {
  return {
    audio_name:$("replayAudio").value, model:$("replayModel").value,
    aec:$("replayAec").value, diarization:$("replayDiarization").checked,
    speakers:Number($("replaySpeakers").value), threshold:Number($("replayThreshold").value),
    diarization_embedding:$("replayEmbedding").value,
    generate_hint:$("replayHint").checked,
    reuse_transcript:$("replayReuse").checked,
    stt_beam:Number($("replayBeam").value),
  };
}
function openReplayLab(item) {
  replayEpoch++;
  replaySession = item;
  replaySelected = new Set(); replayRunsState = [];
  $("replayComparePanel").hidden = true;
  $("replayTimelinePanel").hidden = true;
  replayTimelineData = null; stopReplayTimeline();
  stopReplayCompareAudio();
  $("archOverlay").classList.remove("show");
  $("analysisOverlay").classList.remove("show");
  $("replayOverlay").classList.add("show");
  studioValue($("replaySessionLabel"),item.label);
  $("replayAudio").innerHTML = item.audios.map(audio =>
    `<option value="${esc(audio.name)}">${audio.name.includes("me")?studioText("микрофон"):studioText("системный звук")} · ${esc(audio.name)} · ${fmtSec(audio.sec)}</option>`).join("");
  $("replayModel").value = currentInit && currentInit.config.whisper_model || "small";
  updateReplayControls();
  $("replayRuns").innerHTML = `<div class="replay-empty">${studioText("Загружаю историю…")}</div>`;
  loadReplayRuns();
}
async function replayMutation(url, method="POST", body={}) {
  const response = await fetch(url, {method, headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
  if (!response.ok) { const error = new Error(await response.text()); error.status = response.status; throw error; }
  return response.json();
}
async function replayApply(runId) {
  if (!replaySession || !replayRunsState.some(run => run.run_id === runId)) return;
  const owner = replayEpoch;
  if (!confirm(studioUi("Перенести выбранный Replay-вариант в проверку голосов и имён? Исходный WAV и живой транскрипт не изменятся."))) return;
  const url = `/api/sessions/${encodeURIComponent(replaySession.dir)}/replays/${encodeURIComponent(runId)}/apply-diarization`;
  try {
    let result;
    try { result = await replayMutation(url); }
    catch (error) {
      if (owner !== replayEpoch) return;
      if (error.status !== 409 || !confirm(studioUi("У встречи уже есть производный разбор голосов. Заменить его результатом этого Replay run? Исходная запись и живой транскрипт сохранятся."))) throw error;
      result = await replayMutation(url, "POST", {replace:true});
    }
    if (owner !== replayEpoch) return;
    studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Разбор применён · голосов: {p0}. Проверьте имена на слух.",{p0:Number(result.speakers)||"—"})}}));
    await loadReplayRuns();
    if (owner === replayEpoch && result.evidence_url) window.open(result.evidence_url, "_blank", "noopener");
  } catch (error) { if(owner === replayEpoch) studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Разбор не применён: {p0}",{p0:error.message})}})); }
}
async function replayCancel(runId) {
  if (!replaySession || !replayRunsState.some(run => run.run_id === runId)) return;
  const owner = replayEpoch;
  try { await replayMutation(`/api/sessions/${encodeURIComponent(replaySession.dir)}/replays/${encodeURIComponent(runId)}/cancel`); if(owner===replayEpoch)await loadReplayRuns(); }
  catch (error) { if(owner===replayEpoch)studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Не остановлено: {p0}",{p0:error.message})}})); }
}
async function replayDelete(runId) {
  if (!replaySession || !replayRunsState.some(run => run.run_id === runId)) return;
  const owner = replayEpoch;
  if (!confirm(studioUi("Удалить только этот Replay run и все его производные файлы? Исходная встреча останется."))) return;
  try { await replayMutation(`/api/sessions/${encodeURIComponent(replaySession.dir)}/replays/${encodeURIComponent(runId)}`, "DELETE"); if(owner===replayEpoch)await loadReplayRuns(); }
  catch (error) { if(owner===replayEpoch)studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Не удалено: {p0}",{p0:error.message})}})); }
}

function renderBank(bank) {
  const el = $("bank");
  if (!bank.length) {
    el.innerHTML = '<span style="color:var(--dim);font-size:.8125rem">'+meetingText('questions.md ещё нет — генерирую…')+'</span>';
    return;
  }
  el.innerHTML = bank.map(sec =>
    `<h4>${esc(sec.section)}</h4>` + sec.questions.map(q => {
      let h = `<div class="qhead"><label class="bq${q.asked ? " asked" : ""}"><input type="checkbox"${q.asked ? " checked" : ""}> <span>${esc(q.text)}</span></label>` +
        `<button class="speak-q" data-text="${esc(q.text)}" ${meetingAttrs('title','задать вопрос голосом')}>▶</button></div>`;
      if (q.why) h += `<div class="qwhy"><b>${meetingText('Почему:')}</b> ${esc(q.why)}</div>`;
      if (q.context) h += `<div class="qcontext"><b>${meetingText('Факт и связь:')}</b> ${esc(q.context)}</div>`;
      if (q.answer) h += `<details class="qanswer"><summary>${meetingText('эталон ответа')}${q.answer_source ? ` · ${esc(q.answer_source)}` : ""}</summary><div>${esc(q.answer)}</div></details>`;
      if (q.branches && q.branches.length)
        h += `<details class="qbr"><summary>${meetingText('ветки ({count})',{count:q.branches.length})}</summary>` +
             q.branches.map(b => `<div>${esc(b)}</div>`).join("") + `</details>`;
      return h;
    }).join("")).join("");
  el.querySelectorAll(".bq").forEach(lab => {
    const inp = lab.querySelector("input");
    inp.onchange = () => {
      lab.classList.toggle("asked", inp.checked);
      send({type: "ask", text: lab.querySelector("span").textContent, asked: inp.checked});
    };
  });
  el.querySelectorAll(".speak-q").forEach(btn => btn.onclick = () =>
    playQuestion(btn.dataset.text, btn));
}

function trainingList(title, values) {
  if (!Array.isArray(values) || !values.length) return "";
  return `<h4>${studioText(title)}</h4><ul>${values.map(value =>
    `<li>${esc(String(value))}</li>`).join("")}</ul>`;
}

function renderTrainingAdaptation(data) {
  const adaptation = data.adaptation || {};
  const box = $("trainingAdaptation");
  box.hidden = !data.prepared;
  if (!data.prepared) return;
  const shown = value => value == null ? "—" : `${value}/10`;
  $("trainingAdaptationSummary").innerHTML = [
    ["попытка", esc(String(adaptation.attempt_number || 1))],
    ["содержание", esc(shown(adaptation.content_average))],
    ["самостоятельность", esc(shown(adaptation.independence_average))],
    ["следующий фокус", adaptation.next_focus ? esc(adaptation.next_focus) : studioText("появится после ответов")],
    ["профиль", studioText(adaptation.shared_across_sessions ? "общий между тренировками" : "эта сессия")],
  ].map(item => `<div class="training-adapt-stat"><span>${studioText(item[0])}</span>` +
    `<strong>${item[1]}</strong></div>`).join("");
  const competencies = adaptation.competencies || [];
  $("trainingCompetencies").innerHTML = competencies.map(item => {
    const mastery = Math.max(0, Math.min(100, Number(item.mastery) || 0));
    const status = item.due ? studioUi("повторить сейчас")
      : item.status === "weak" ? studioUi("закрепить")
      : item.status === "strong" ? studioUi("устойчиво") : studioUi("поддерживать");
    return `<article class="training-competency ${esc(String(item.status || "steady"))}">
      <div class="training-competency-head"><b>${esc(String(item.label || "Навык"))}</b>
        <span>${Math.round(mastery)}%</span></div>
      <div class="training-mastery"><i style="width:${mastery}%"></i></div>
      <small>${studioText(status)}${studioText(" · дальше ")}${esc(String(item.recommended_difficulty || "middle"))}${studioText(" · ответов ")}${esc(String(item.answers || 0))}</small>
    </article>`;
  }).join("") || `<div class="privacy-note">${studioText("Карта заполнится после завершённой попытки. Текущие ответы уже влияют на выбор следующего вопроса, но попадут в историю только после завершения.")}</div>`;
}

const studioDraftFields=['trainingRole','trainingSource','trainingDifficulty','trainingAdaptive','trainingCount','trainingPack',
  'sceneRole','sceneSource','sceneDifficulty','scenePack','sceneStyle','sceneRounds','sceneInterviewerVoice','sceneCandidateVoice','sceneCoachAudience'];
let studioDraftSession='',studioDraftValues={};
function studioDraftKey(){return 'blatero.studioDraft.'+studioDraftSession;}
function studioDraftStore(){try{sessionStorage.setItem(studioDraftKey(),JSON.stringify(studioDraftValues));}catch{}}
function studioDraftSessionSync(){
  const session=currentInit?.current_dir||'';if(session===studioDraftSession)return;
  if(studioDraftSession)studioDraftStore();studioDraftSession=session;
  try{studioDraftValues=JSON.parse(sessionStorage.getItem(studioDraftKey())||'{}');}catch{studioDraftValues={};}
  for(const id of studioDraftFields){const node=$(id);if(!node)continue;
    if(node.type==='checkbox')node.checked=node.defaultChecked;
    else if(node.tagName==='SELECT'){const selected=[...node.options].find(o=>o.defaultSelected);node.value=selected?.value||node.options[0]?.value||'';}
    else node.value=node.defaultValue;
  }
}
function studioDraftRestore(){
  for(const [id,value]of Object.entries(studioDraftValues)){if(!studioDraftFields.includes(id))continue;const node=$(id);if(node)node.type==='checkbox'?node.checked=!!value:node.value=value;}
  for(const id of ['trainingSetup','sceneSetup']){
    const setup=$(id);if(!setup)continue;let note=setup.querySelector('[data-studio-draft]');
    if(!Object.keys(studioDraftValues).length){note?.remove();continue;}
    if(!note){note=document.createElement('p');note.dataset.studioDraft='';note.className='privacy-note';const label=document.createElement('span');studioLabel(label,'Черновик настроек сохранён в этой вкладке.');const reset=document.createElement('button');reset.type='button';studioLabel(reset,'Сбросить черновик');reset.onclick=()=>{if(!confirm(studioUi('Удалить несохранённый черновик?')))return;studioDraftValues={};studioDraftStore();studioDraftSession='';studioDraftSessionSync();renderTraining(trainingState);renderAiScene(sceneState);};note.append(label,' ',reset);setup.append(note);}
  }
}
for(const event of ['input','change'])document.addEventListener(event,e=>{if(!studioDraftFields.includes(e.target.id))return;studioDraftSessionSync();const node=e.target;studioDraftValues[node.id]=node.type==='checkbox'?node.checked:node.value;studioDraftStore();});
const studioSubmissions=new Map();
function studioSubmissionKey(kind,run,turn){return JSON.stringify([currentInit?.current_dir,kind,run||'',turn||'']);}
function studioSubmissionField(id,key,receipts) {
  const node=$(id), previous=node.dataset.draftOwner;
  for(const [owner,draft] of studioSubmissions)if(receipts.includes(draft.request_id)){
    studioSubmissions.delete(owner);if(previous===owner&&node.value===draft.value)node.value='';
  }
  if(previous!==key){node.dataset.draftOwner=key;node.value=studioSubmissions.get(key)?.value||'';}
}
function studioSubmission(id) {
  const node=$(id),key=node.dataset.draftOwner;
  const old=studioSubmissions.get(key);
  if(old?.value===node.value)return old.request_id;
  const draft={value:node.value,request_id:crypto.randomUUID()};studioSubmissions.set(key,draft);
  return draft.request_id;
}
for(const id of ['trainingAnswer','sceneTakeoverText'])$(id).addEventListener('input',()=>studioSubmission(id));
function renderTraining(data){studioDraftSessionSync();renderTrainingCore(data);studioDraftRestore();
  studioSubmissionField('trainingAnswer',studioSubmissionKey('training',data?.attempt_id,data?.question?.id),data?.accepted_requests||[]);
}
function renderTrainingCore(data) {
  if (!data) return;
  const role = $("trainingRole"), source = $("trainingSource");
  if (!role.value && (data.role || (currentInit && currentInit.meta && currentInit.meta.name)))
    role.value = data.role || currentInit.meta.name;
  if (!source.value && data.source) source.value = data.source;
  if (data.difficulty) $("trainingDifficulty").value = data.difficulty;
  if (data.prepared && !data.busy) {
    $("trainingPack").value = data.pack_id || "";
    applyCompetencyPack("trainingPack", "trainingRole", "trainingPackHint");
  }
  $("trainingAdaptive").checked = data.adaptive_enabled !== false;
  const currentNumber = data.total
    ? Math.min((data.question ? (data.question_position || 0) + 1 : data.total), data.total) : 0;
  studioLabel($("trainingTitle"),()=>({source:"{value}",values:{value:data.title || studioUi("Тренировка собеседования")}}));
  studioValue($("trainingProgress"),`${currentNumber} / ${data.total || 0}`);
  $("trainingRing").style.setProperty("--training-progress",
    `${data.total ? Math.round(currentNumber / data.total * 100) : 0}%`);
  const independence = data.adaptation && data.adaptation.independence_average;
  studioLabel($("trainingScore"),()=>({source:"{value}",values:{value:data.average_score == null
    ? studioUi("оценок пока нет")
    : studioUi("содержание {p0}/10 · самостоятельность {p1}",{p0:data.average_score,p1:independence == null ? "—" : independence + "/10"})}}));
  const statusText = data.error || data.message || ({
    not_prepared:studioUi("Задайте роль и материалы — тренажёр подготовит вопросы."),
    prepared:studioUi("План готов. Нажмите «начать тренировку» — запись включится перед первым вопросом."),
    active:studioUi("Отвечайте голосом. Текстовое поле нужно только как запасной вариант."),
    ready_to_finish:studioUi("Все вопросы пройдены. Завершите тренировку, чтобы получить отчёт."),
    completed:studioUi("Тренировка завершена. Можно открыть отчёт или повторить попытку.")
  }[data.status] || "");
  if(data.error || data.message)studioValue($("trainingStatus"),statusText);
  else studioLabel($("trainingStatus"),statusText);
  $("trainingStatus").style.color = data.error ? "var(--red)"
    : data.busy ? "var(--yellow)" : "var(--dim)";
  const aiReady = !!(currentInit && currentInit.config && currentInit.config.cloud_ack
    && currentInit.llm_connection && currentInit.llm_connection.configured);
  const warnings = [...(data.warnings || [])];
  $("trainingWarnings").innerHTML = warnings.map(value =>
    `<div>⚠ ${esc(String(value))}</div>`).join("") + (!aiReady && data.status !== "completed"
      ? `<div>⚠ ${studioText("Настройте LLM и включите согласие в Настройки → Приватность: вопросы и оценки создаёт выбранный ИИ.")}</div>` : "");
  const inProgress = ["active", "ready_to_finish"].includes(data.status);
  $("trainingSetup").open = !inProgress;
  $("trainingPrepare").disabled = !!data.busy || recLive || !aiReady;
  $("trainingStart").disabled = !!data.busy || !data.prepared || !aiReady
    || data.status === "ready_to_finish" || (data.status === "active" && recLive);
  studioLabel($("trainingStart"),()=>({source:"{value}",values:{value:data.status === "completed"
    ? studioUi("повторить тренировку")
    : data.status === "active" && !recLive ? studioUi("продолжить тренировку") : studioUi("начать тренировку")}}));
  $("trainingReset").disabled = !!data.busy || recLive || !data.prepared;
  $("trainingProgressReset").disabled = !!data.busy || recLive
    || !(data.adaptation && data.adaptation.attempts);
  renderTrainingAdaptation(data);

  const card = $("trainingQuestionCard"), question = data.question;
  card.hidden = !inProgress;
  studioLabel($("trainingQuestion"),()=>({source:"{value}",values:{value:question
    ? question.question : studioUi("Все вопросы пройдены — можно формировать итоговый разбор.")}}));
  studioLabel($("trainingCategory"),()=>({source:"{value}",values:{value:question
    ? `${question.category || studioUi("вопрос")} · ${question.difficulty || ""}` : studioUi("готово")}}));
  studioLabel($("trainingWhy"),()=>({source:"{value}",values:{value:question && question.why ? studioUi("проверяет: {p0}",{p0:question.why}) : ""}}));
  studioLabel($("trainingAdaptiveReason"),()=>({source:"{value}",values:{value:question && data.adaptation
    && data.adaptation.question_reason ? studioUi("маршрут: {p0}",{p0:data.adaptation.question_reason}) : ""}}));
  $("trainingSpeak").hidden = !question;
  $("trainingHintBtn").hidden = !question;
  $("trainingAnswerBtn").hidden = !question;
  $("trainingAnswer").parentElement.hidden = !question;
  $("trainingHint").hidden = !data.hint;
  studioLabel($("trainingHint"),()=>({source:"{value}",values:{value:data.hint
    ? studioUi("Подсказка {p0}/3: {p1}",{p0:data.hint_level,p1:data.hint}) : ""}}));
  $("trainingHintBtn").disabled = !!data.busy || data.hint_level >= 3;
  studioLabel($("trainingHintBtn"),()=>({source:"{value}",values:{value:data.hint_level
    ? studioUi("ещё подсказка ({p0}/3)",{p0:data.hint_level}) : studioUi("подсказка")}}));
  $("trainingAnswerBtn").disabled = !!data.busy || !aiReady;
  $("trainingFinish").disabled = !!data.busy || !aiReady
    || !(data.evaluations > 0 || question);

  const evaluation = data.last_evaluation, box = $("trainingEvaluation");
  box.hidden = !evaluation;
  if (evaluation) {
    box.innerHTML = `<h3>${studioText("Последняя оценка · ")}<span class="training-score">${esc(String(evaluation.content_score == null ? evaluation.score : evaluation.content_score))}/10</span></h3>` +
      `<div class="training-verdict">${esc(String(evaluation.verdict || ""))}</div>` +
      `<div class="training-meta">${studioText("Содержание: ")}${esc(String(evaluation.content_score == null ? evaluation.score : evaluation.content_score))}${studioText("/10 · самостоятельность: ")}${esc(String(evaluation.independence_score == null ? 10 : evaluation.independence_score))}${studioText("/10 · готовность: ")}${esc(String(evaluation.readiness_score == null ? evaluation.score : evaluation.readiness_score))}${studioText("/10 · подсказок: ")}${esc(String(evaluation.hints_used || 0))}</div>` +
      trainingList(studioUi("Сильные стороны"), evaluation.strengths) +
      trainingList(studioUi("Что улучшить"), evaluation.gaps) +
      trainingList(studioUi("Исправления"), evaluation.corrections) +
      (evaluation.better_answer ? `<h4>${studioText("Улучшенный ответ")}</h4><div class="better-answer">${esc(String(evaluation.better_answer))}</div>` : "") +
      (evaluation.follow_up ? `<h4>${studioText("Что ещё спросит работодатель")}</h4><div>${esc(String(evaluation.follow_up))}</div>` : "");
  }
  notifyTrainingStudio();
}

function setTrainingView(view, persist = true) {
  trainingView = ["scene", "speech"].includes(view) ? view : "personal";
  if (trainingView === "personal") trainingStudioMode = "personal";
  else if (trainingView === "speech") trainingStudioMode = "speech";
  else if (!["interviewer", "ai"].includes(trainingStudioMode)) trainingStudioMode = "ai";
  document.body.classList.toggle("speech-training-view", trainingView === "speech" && currentMeetingType === "тренировка");
  document.body.classList.toggle(
    "scene-training-view", trainingView === "scene" && currentMeetingType === "тренировка");
  $("personalTraining").hidden = trainingView !== "personal";
  $("sceneTraining").hidden = trainingView !== "scene";
  $("speechTraining").hidden = trainingView !== "speech";
  for (const [id, active] of [["trainingPersonalTab", trainingStudioMode === "personal"],
                              ["trainingInterviewerTab", trainingStudioMode === "interviewer"],
                              ["trainingSceneTab", trainingStudioMode === "ai"],
                              ["trainingSpeechTab", trainingStudioMode === "speech"]]) {
    $(id).classList.toggle("active", active);
    $(id).setAttribute("aria-selected", String(active));
    $(id).tabIndex = active ? 0 : -1;
  }
  if (trainingView === "scene") {
    if (!$("sceneRole").value) $("sceneRole").value = $("trainingRole").value;
    if (!$("sceneSource").value) $("sceneSource").value = $("trainingSource").value;
    if (!$("scenePack").value && $("trainingPack").value) {
      $("scenePack").value = $("trainingPack").value;
      applyCompetencyPack("scenePack", "sceneRole", "scenePackHint");
    }
    renderAiScene(sceneState || {prepared:false,status:"not_prepared",turns:[]});
  } else if (trainingView === "personal") {
    if (!$("trainingRole").value) $("trainingRole").value = $("sceneRole").value;
    if (!$("trainingSource").value) $("trainingSource").value = $("sceneSource").value;
    if (!$("trainingPack").value && $("scenePack").value) {
      $("trainingPack").value = $("scenePack").value;
      applyCompetencyPack("trainingPack", "trainingRole", "trainingPackHint");
    }
    renderTraining(trainingState || {prepared:false,status:"not_prepared",total:0});
  }
  if (persist) localStorage.setItem("blatero.trainingView", trainingView);
  if (persist) localStorage.setItem("blatero.trainingMode", trainingStudioMode);
  notifyTrainingStudio();
}

function notifyTrainingStudio() {
  if (currentMeetingType === 'тренировка') {
    const label=trainingStudioMode === 'personal' ? "быстрый ответ" : "ещё подсказку";
    const tip=trainingStudioMode === 'personal' ? "Готовый ответ на вопрос" : "Подсказки наблюдателю сценки";
    setIconAction($("pulse"), "spark", label, tip);
    studioLabel($("pulse").querySelector('.action-label'),label);
    studioAttr($("pulse"),'aria-label',tip);studioAttr($("pulse"),'data-tooltip',tip);
  }
  window.dispatchEvent(new CustomEvent("blatero:training-state", {detail:{
    mode:trainingStudioMode, scene:sceneState, training:trainingState,
    recLive, meetingType:currentMeetingType}}));
}

function selectTrainingMode(mode) {
  if (recLive || window.BlateroSpeechTraining?.active()
      || (mode === "speech" && trainingState?.status === "active")
      || (sceneState && sceneState.status === "active")) {
    studioLabel($("trainingStatus"),"Завершите текущий разговор перед сменой состава участников.");
    return;
  }
  stopQuestionAudio();
  trainingStudioMode = mode;
  setTrainingView(mode === "speech" ? "speech" : mode === "personal" ? "personal" : "scene");
  if (mode === "speech") return;
  if (mode === "personal") $("trainingSetup").open = true;
  else $("sceneSetup").open = true;
  if (mode !== "personal" && sceneState && sceneState.prepared) {
    $("sceneTakeover").value = mode === "interviewer" ? "interviewer" : "observer";
    saveSceneControl();
  }
}

function sceneVoice(turn) {
  return turn && turn.speaker === "interviewer"
    ? (sceneState.interviewer_voice || "question")
    : (sceneState.candidate_voice || "filipp");
}

function playSceneTurn(turn, autoAdvance = false) {
  if (!turn || turn.source === "takeover") return;
  const button = $("sceneSpeak");
  playQuestion(turn.text, button, {
    sceneTurnId: turn.id, sceneRunId: sceneState.run_id, sceneSpeaker:turn.speaker, voice: sceneVoice(turn),
    onDone: autoAdvance ? () => {
      const current = sceneState && sceneState.turn;
      if (sceneState && sceneState.control === "auto" && sceneState.status === "active"
          && !sceneState.needs_takeover && current && current.id === turn.id)
        {const runId=sceneState.run_id, next=()=>send({type:"scene_next", run_id:runId, after_turn_id:turn.id, text:""});
          window.BlateroSceneLive.afterTurn(turn,next);}
    } : null
  });
}

function renderAiScene(data){studioDraftSessionSync();renderAiSceneCore(data);studioDraftRestore();
  studioSubmissionField('sceneTakeoverText',studioSubmissionKey('scene',data?.run_id,data?.turn?.id),(data?.turns||[]).map(turn=>turn.request_id).filter(Boolean));
}
function renderAiSceneCore(data) {
  if (!data) return;
  sceneState = data;
  const role = $("sceneRole"), source = $("sceneSource");
  if (!role.value && (data.role || (trainingState && trainingState.role)))
    role.value = data.role || trainingState.role;
  if (!source.value && trainingState && trainingState.source)
    source.value = trainingState.source;
  if (data.difficulty) $("sceneDifficulty").value = data.difficulty;
  if (data.prepared && !data.busy) {
    $("scenePack").value = data.pack_id || "";
    applyCompetencyPack("scenePack", "sceneRole", "scenePackHint");
  }
  if (data.style) $("sceneStyle").value = data.style;
  if (data.round_limit) $("sceneRounds").value = String(data.round_limit);
  if (data.interviewer_voice) $("sceneInterviewerVoice").value = data.interviewer_voice;
  if (data.candidate_voice) $("sceneCandidateVoice").value = data.candidate_voice;
  if (data.control) $("sceneControl").value = data.control;
  if (data.takeover) $("sceneTakeover").value = data.takeover;
  if (data.coach_audience) $("sceneCoachAudience").value = data.coach_audience;
  $("sceneCoachAudience").disabled = !!data.busy || data.status === 'active';

  const active = data.status === "active";
  const turns = Array.isArray(data.turns) ? data.turns : [];
  if (!turns.length && data.status === "prepared") sceneAutoTurnId = null;
  const aiReady = !!(currentInit && currentInit.config && currentInit.config.cloud_ack
    && currentInit.llm_connection && currentInit.llm_connection.configured);
  const warnings = [...(data.warnings || [])];
  $("sceneWarnings").innerHTML = warnings.map(value =>
    `<div>⚠ ${esc(String(value))}</div>`).join("") + (!aiReady && data.status !== "completed"
      ? `<div>⚠ ${studioText("Настройте LLM и подтвердите облачную обработку в Настройки → Приватность.")}</div>` : "");

  // После первого хода постановка освобождает место самому разговору и разбору.
  const setup = $("sceneSetup");
  if (setup.dataset.run !== String(data.run_id || '') || (turns.length && setup.dataset.hasTurns !== '1'))
    setup.open = !turns.length;
  setup.dataset.run = String(data.run_id || '');
  setup.dataset.hasTurns = turns.length ? '1' : '0';
  $("scenePrepare").disabled = !!data.busy || recLive || !aiReady;
  const humanInterviewer = data.takeover === "interviewer";
  $("sceneStart").disabled = !!data.busy || !data.prepared || (recLive && !humanInterviewer) || !aiReady || active;
  studioLabel($("sceneStart"),()=>({source:"{value}",values:{value:data.status === "completed"
    ? studioUi("разыграть заново")
    : studioUi("начать сценку")}}));
  $("sceneReset").disabled = !!data.busy || !data.prepared || recLive;
  $("sceneControls").hidden = !data.prepared;
  $("sceneActions").hidden = !active && data.status !== "ready_to_review";
  $("sceneNext").hidden = !active;
  $("sceneNext").disabled = !!data.busy || !aiReady;
  $("sceneFinish").disabled = !!data.busy || !aiReady || turns.length < 2
    || data.status === "completed";
  $("sceneSpeak").disabled = !!data.busy || !data.turn || data.turn.source === "takeover";
  $("sceneCoach").disabled = !!data.busy || !turns.length || !aiReady;
  studioLabel($("sceneCoach"),()=>({source:"{value}",values:{value:data.busy && data.operation === 'scene_hint'
    ? studioUi("готовлю подсказки…") : data.coach?.focus ? studioUi("обновить по диалогу") : studioUi("получить подсказки")}}));
  studioLabel($("sceneCounter"),()=>({source:"{value}",values:{value:studioUi("{p0} / {p1} раундов",{p0:data.completed_rounds || 0,p1:data.round_limit || 0})}}));

  const cast = $("sceneCast");
  cast.hidden = !data.prepared;
  cast.innerHTML = data.prepared ? `<article><h3>${studioText("Интервьюер · ")}${esc(String((data.interviewer || {}).role || "роль"))}</h3>
      <p>${esc(String((data.interviewer || {}).goal || "Цель появится после подготовки."))}</p></article>
    <article class="candidate"><h3>${studioText("Кандидат · ")}${esc(String((data.candidate || {}).name || "кандидат"))}</h3>
      <p>${esc(String((data.candidate || {}).legend || "Легенда скрыта до подготовки."))}</p></article>` : "";

  // The live transcript controller renders only actually heard audio, not these generated turns.

  $("sceneTakeoverBox").hidden = !data.needs_takeover;
  studioLabel($("sceneNext"),()=>({source:"{value}",values:{value:data.needs_takeover
    ? (humanInterviewer ? studioUi("отправить вопрос из микрофона") : studioUi("сказать и продолжить"))
    : studioUi("следующий ход")}}));
  studioAttr($("sceneTakeoverText"),"placeholder",()=>({source:"{value}",values:{value:humanInterviewer
    ? studioUi("Обычно оставьте пустым: вопрос берётся из микрофона. Можно исправить текст вручную.")
    : studioUi("Введите реплику — ИИ продолжит со второй стороны.")}}));
  const audioList = Array.isArray(data.audio_clips) ? data.audio_clips : [];
  const pastRuns = Array.isArray(data.history_files) ? data.history_files : [];
  const savedAudio = data.audio_recording || {};
  const fileHref = name => `/files/${encodeURIComponent($("selSession").value)}/${encodeURIComponent(name)}`;
  $("sceneSavedAudio").hidden = !audioList.length && !savedAudio.missing?.length && !pastRuns.length;
  $("sceneSavedAudio").innerHTML = `<summary>${studioText("Запись · сохранено реплик ИИ: ")}${audioList.length}</summary>`
    + (savedAudio.name ? `<p><a href="${fileHref(savedAudio.name)}" target="_blank">${studioText("Открыть WAV ")}${savedAudio.contains_human ? studioText("озвучки ИИ") : studioText("диалога")}</a>${studioText(" · монтаж реплик с короткими паузами, оригиналы ниже")}</p>` : "")
    + (savedAudio.missing?.length ? `<p class="training-warnings">${studioText("Не озвучены ")}${savedAudio.missing.length}${studioText(" реплик: полной аудиозаписи ИИ пока нет. Текст сохранён.")}</p>` : "")
    + (humanInterviewer ? `<p>${studioText("Ваш голос и реальная временная шкала — в исходных WAV микрофона в результатах встречи.")}</p>` : "")
    + audioList.map(item => `<p><a href="${fileHref(item.name)}" target="_blank">${item.speaker === "interviewer" ? studioText("Интервьюер") : studioText("Кандидат")} · ${esc(item.turn_id)} · ${(item.duration_ms / 1000).toFixed(1)}${studioText(" с")}</a></p>`).join("")
    + pastRuns.map((name,index) => `<p><a href="${fileHref(name)}" target="_blank">${studioText("Предыдущая попытка ")}${index + 1}${studioText(" · диалог и разбор")}</a></p>`).join("");
  const review = $("sceneReview");
  review.hidden = !data.review;
  review.innerHTML = data.review ? mdLite(data.review) : "";

  if (trainingView === "scene") {
    studioLabel($("trainingTitle"),()=>({source:"{value}",values:{value:data.title || studioUi("Сценка ИИ ↔ ИИ")}}));
    const statusText = data.error || data.message || ({
      not_prepared:studioUi("Задайте роли и материалы — режиссёр подготовит независимых участников."),
      prepared:studioUi("Роли готовы. Выберите темп и запустите первый ход."),
      active:data.needs_takeover ? (humanInterviewer ? studioUi("Ваш ход: скажите вопрос, дождитесь распознавания и отправьте его.") : studioUi("Ваш ход: введите реплику за выбранную роль."))
        : studioUi("Сценка идёт. Наблюдайте или займите любую роль."),
      ready_to_review:studioUi("Все раунды сыграны. Остановите сценку и получите независимый разбор."),
      completed:studioUi("Сценка завершена. Разбор обоих участников готов.")
    }[data.status] || "");
    if(data.error || data.message)studioValue($("trainingStatus"),statusText);
    else studioLabel($("trainingStatus"),statusText);
    $("trainingStatus").style.color = data.error ? "var(--red)"
      : data.busy ? "var(--yellow)" : "var(--dim)";
    studioValue($("trainingProgress"),`${data.completed_rounds || 0} / ${data.round_limit || 0}`);
    $("trainingRing").style.setProperty("--training-progress",
      `${data.round_limit ? Math.round((data.completed_rounds || 0) / data.round_limit * 100) : 0}%`);
    studioLabel($("trainingScore"),()=>({source:"{value}",values:{value:data.status === "completed"
      ? studioUi("разбор готов") : studioUi("ИИ-интервьюер ↔ ИИ-кандидат")}}));
  }
  notifyTrainingStudio();
  window.BlateroSceneLive?.render(data);
}

function mdLite(md) {
  const lines = String(md || "").split(/\r?\n/);
  const inline = value => esc(value).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
  const cells = line => {
    const result = []; let cell = "", code = false;
    const text = line.trim().replace(/^\|/, "").replace(/(?<!\\)\|$/, "");
    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      if (char === "\\" && text[i + 1] === "|") { cell += "|"; i++; }
      else if (char === "`") { code = !code; cell += char; }
      else if (char === "|" && !code) { result.push(cell.trim()); cell = ""; }
      else cell += char;
    }
    result.push(cell.trim()); return result;
  };
  const out = [];
  for (let i = 0; i < lines.length; i++) {
    let l = lines[i];
    const header = cells(l), divider = cells(lines[i + 1] || "");
    if (header.length > 1 && header.length === divider.length && divider.every(c => /^:?-{3,}:?$/.test(c))) {
      const align = divider.map(c => c.startsWith(":") && c.endsWith(":") ? "center" : c.endsWith(":") ? "right" : "left");
      let html = '<div class="dossier-table-wrap" role="region" aria-label="Таблица досье" tabindex="0"><table><thead><tr>';
      html += header.map((c, n) => `<th scope="col" style="text-align:${align[n]}">${inline(c)}</th>`).join("") + "</tr></thead><tbody>";
      i++;
      while (i + 1 < lines.length && lines[i + 1].trim() && cells(lines[i + 1]).length > 1) {
        const row = cells(lines[++i]);
        html += "<tr>" + header.map((_, n) => `<td style="text-align:${align[n]}">${inline(row[n] || "")}</td>`).join("") + "</tr>";
      }
      out.push(html + "</tbody></table></div>"); continue;
    }
    l = l.trim();
    if (!l) continue;
    if (l.startsWith("> "))
      out.push(`<blockquote>${inline(l.slice(2))}</blockquote>`);
    else if (l.startsWith("# ")) out.push(`<h3>${inline(l.slice(2))}</h3>`);
    else if (l.startsWith("## ")) out.push(`<h4>${inline(l.slice(3))}</h4>`);
    else if (l.startsWith("- ")) out.push(`<div class="dossier-bullet">• ${inline(l.slice(2))}</div>`);
    else out.push(`<div>${inline(l)}</div>`);
  }
  return out.join("");
}

let waveMe = [], waveGuest = [], meetingDuration = null, recLive = false;
let recordingRef = null;
function renderVoiceProfile(m) {
  const meter = $("voiceMeter"), status = $("localVoiceStatus");
  const level = Math.round(Math.max(0, Math.min(100, (m.level || 0) * 100)));
  meter.style.width = `${level}%`;
  meter.setAttribute("aria-valuenow", String(level));
  let text = "";
  if (m.busy) text = studioUi("идёт запись образца · осталось {p0} с",{p0:Math.ceil(m.remaining || 0)});
  else if (!m.installed) text = studioUi("локальный движок Chatterbox не установлен");
  else if (!m.sample) text = studioUi("движок установлен · запишите образец своего голоса");
  else if (m.quality === "failed") text = studioUi("клон отклонён · {reason} · проверьте выбранный маршрут озвучки",{reason:m.quality_message || studioUi("речь не совпала с текстом")});
  else if (m.quality === "passed") text = studioUi("речь проверена · {p0} · образец {p1} с",{p0:m.engine || "Chatterbox",p1:m.seconds || 0});
  else text = studioUi("образец {p0} с записан · проверьте голос перед подготовкой вопросов",{p0:m.seconds || 0});
  if (m.cache_progress) text += ` · ${m.cache_progress}`;
  if (m.message) text = m.message;
  if (m.error) text = m.error;
  studioValue(status,text);
  status.style.color = m.error || m.quality === "failed" ? "var(--red)"
    : (m.quality === "passed" && !m.busy ? "var(--green)"
      : (m.busy ? "var(--acc)" : "var(--yellow)"));
  $("voiceRecord").disabled = !!m.busy || !!m.cache_busy;
  $("localVoiceTest").disabled = !m.ready || !!m.busy || !!m.cache_busy;
  $("voiceCache").disabled = !m.ready || !!m.busy || !!m.cache_busy;
  $("voiceDelete").disabled = !m.sample || !!m.busy || !!m.cache_busy;
}

let micTestRequest = null, micTestTimer = null, micTestUrl = null, micTestPhase = '';

function micPreviewControls(busy) {
  $("micTestStart").disabled = busy;
  $("micTestCancel").hidden = !busy;
  $("testMic").disabled = busy;
  $("refreshMics").disabled = busy;
}

function clearMicPreview(cancel = true) {
  clearInterval(micTestTimer); micTestTimer = null;
  if (cancel && micTestRequest && ['countdown','opening','recording'].includes(micTestPhase)
      && ws?.readyState === WebSocket.OPEN && micTestPhase !== 'countdown')
    send({type:'mic_test_cancel',request_id:micTestRequest});
  micTestRequest = null; micTestPhase = '';
  const audio = $("micTestPlayback");
  if (!audio) return; // An old HTML tab can briefly load updated static assets during upgrade.
  audio.pause(); audio.removeAttribute('src'); audio.load();
  if (micTestUrl) URL.revokeObjectURL(micTestUrl);
  micTestUrl = null;
  $("micTestPreview").hidden = true;
  $("micTestCountdown").hidden = true;
  $("micTestTime").textContent = '';
  $("micMeter").style.width = '0%'; $("micMeter").setAttribute('aria-valuenow','0');
  micPreviewControls(false);
}

function startMicPreview() {
  if (!$("micTestPlayback")) {
    studioLabel($("micTestStatus"),"Обновите страницу, чтобы открыть новую проверку с прослушиванием.");
    return;
  }
  if (['countdown','opening','recording'].includes(micTestPhase)) return;
  if (recLive) {
    studioLabel($("micTestStatus"),"Во время записи используйте индикаторы внизу. Проверка доступна после остановки.");
    return;
  }
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    studioLabel($("micTestStatus"),"Нет подключения к серверу. Подождите и нажмите кнопку снова.");
    return; // Never queue a microphone start for an unexpected later reconnect.
  }
  clearMicPreview(false);
  micTestRequest = crypto.randomUUID(); micTestPhase = 'countdown';
  micPreviewControls(true);
  const counter = $("micTestCountdown"), status = $("micTestStatus");
  let remaining = 3;
  counter.hidden = false; studioValue(counter,remaining);
  status.style.color = 'var(--acc)';
  studioLabel(status,"Приготовьтесь говорить. Начало через 3 секунды.");
  micTestTimer = setInterval(() => {
    remaining -= 1;
    if (remaining > 0) {
      studioValue(counter,remaining);
      studioLabel(status,()=>({source:"{value}",values:{value:studioUi("Начало через {p0}…",{p0:remaining})}}));
      return;
    }
    clearInterval(micTestTimer); micTestTimer = null; counter.hidden = true;
    if (!ws || ws.readyState !== WebSocket.OPEN || recLive) {
      clearMicPreview(false);
      studioLabel(status,"Проверка не началась: нет подключения или уже идёт запись. Нажмите кнопку снова.");
      return;
    }
    micTestPhase = 'opening'; studioLabel(status,"Открываю выбранный микрофон…");
    send({type:'mic_test',request_id:micTestRequest});
  },1000);
}

function renderMicTest(m) {
  if (!micTestRequest || m.request_id !== micTestRequest) return;
  const bar = $("micMeter"), status = $("micTestStatus"), start = $("micTestStart");
  if (m.level != null) {
    const level = Math.round(Math.max(0, Math.min(100, m.level * 100)));
    bar.style.width = `${level}%`; bar.setAttribute("aria-valuenow", String(level));
  }
  if (m.state === 'opening' || m.state === "started") {
    micTestPhase = m.state === 'opening' ? 'opening' : 'recording';
    micPreviewControls(true); status.style.color = "var(--acc)"; studioValue(status,m.text);
    if (m.state === 'started') studioLabel($("micTestTime"),"Идёт запись · 12 с");
  } else if (m.state === "level") {
    // No live-region chatter on every audio buffer.
    studioLabel($("micTestTime"),()=>({source:"{value}",values:{value:studioUi("Идёт запись · осталось {p0} с",{p0:Math.ceil(Number(m.remaining)||0)})}}));
  } else {
    micTestPhase = 'done'; micPreviewControls(false); studioLabel(start,"Повторить проверку");
    studioValue($("micTestTime"),'');
    status.style.color = m.state === "done" && m.signal ? "var(--green)"
      : (m.state === "error" ? "var(--red)" : "var(--yellow)");
    studioLabel(status,()=>({source:"{value}",values:{value:m.text || studioUi("проверка завершена")}}));
    if (m.state === 'done' && m.wav_base64) {
      try {
        if (m.wav_base64.length > 600000) throw new Error(studioUi("проба слишком велика"));
        const bytes = Uint8Array.from(atob(m.wav_base64), x=>x.charCodeAt(0));
        if (micTestUrl) URL.revokeObjectURL(micTestUrl);
        micTestUrl = URL.createObjectURL(new Blob([bytes],{type:'audio/wav'}));
        $("micTestPlayback").src = micTestUrl; $("micTestPreview").hidden = false;
      } catch (error) { status.textContent += studioUi(" Не удалось открыть пробу: {p0}",{p0:error.message}); }
    }
  }
}

window.addEventListener('blatero:connection', event => {
  if (!event.detail.connected && ['countdown','opening','recording'].includes(micTestPhase)) {
    clearMicPreview(false);
    studioLabel($("micTestStatus"),'Связь с сервером прервалась. Нажмите кнопку для новой проверки.');
  }
});
window.addEventListener('pagehide', () => clearMicPreview());

function renderOutputTest(m) {
  const bar = $("outputMeter"), status = $("outputTestStatus"), start = $("outputTestStart");
  if (m.level != null) {
    const level = Math.round(Math.max(0, Math.min(100, m.level * 100)));
    bar.style.width = `${level}%`; bar.setAttribute("aria-valuenow", String(level));
  }
  if (m.state === "started") {
    start.disabled = true; status.style.color = "var(--acc)"; studioValue(status,m.text);
  } else if (m.state !== "level") {
    start.disabled = false;
    status.style.color = m.state === "done" && m.signal ? "var(--green)"
      : (m.state === "error" || m.signal === false ? "var(--red)" : "var(--dim)");
    studioLabel(status,()=>({source:"{value}",values:{value:m.text || studioUi("проверка завершена")}}));
  }
}

function renderAecTest(m) {
  const status = $("aecTestStatus"), start = $("aecTestStart");
  const busy = m.state === "started" || m.state === "progress";
  start.disabled = busy;
  status.className = "workspace-status " + (m.state === "error" ? "error"
    : m.state === "done" ? "ready" : busy ? "scanning" : "");
  studioLabel(status,()=>({source:"{value}",values:{value:m.text || studioUi("проверяю маршрут…")}}));
  if (m.state === "done" && m.route_signal) {
    const metrics = [studioUi("loopback {p0} дБFS",{p0:Number(m.loopback_dbfs).toFixed(1)})];
    if (m.echo_detected) {
      metrics.push(studioUi("эхо {p0} дБFS",{p0:Number(m.echo_dbfs).toFixed(1)}));
      metrics.push(studioUi("задержка {p0} мс",{p0:m.delay_ms}));
    }
    status.textContent += ` · ${metrics.join(" · ")}`;
  }
}

function renderNativeAec(m) {
  const status = $("aecNativeStatus"), install = $("aecNativeInstall");
  const busy = !!m.busy || m.state === "started";
  install.disabled = busy || !m.supported || (!!m.valid && m.state !== "error");
  status.className = "workspace-status " + (m.state === "error" ? "error"
    : m.valid || m.state === "done" ? "ready" : busy ? "scanning" : "");
  if (m.text) studioValue(status,m.text);
  else if (m.valid) studioLabel(status,()=>({source:"{value}",values:{value:studioUi("WebRTC AEC3 {p0} установлен · SHA-256 проверен",{p0:m.version})}}));
  else studioLabel(status,()=>({source:"{value}",values:{value:m.error || studioUi("WebRTC AEC3 не установлен; используется встроенный фильтр.")}}));
  studioLabel(install,()=>({source:"{value}",values:{value:m.valid ? studioUi("WebRTC AEC3 установлен") : studioUi("установить WebRTC AEC3")}}));
}

function preflightSummary(m) {
  const checks=m.checks||[], failures=checks.filter(x=>x.state==='fail').length,
        warnings=checks.filter(x=>x.state==='warn').length;
  if(m.state==='blocked')return studioUi('не готово: ошибок {failures}, предупреждений {warnings}',{failures,warnings});
  if(m.state==='ready_with_warnings')return studioUi('готово с предупреждениями: {warnings}',{warnings});
  if(m.state==='ready')return studioUi('готово к встрече');
  if(m.state==='incomplete')return studioUi('Проверка голоса не завершена. Остальные результаты — ниже. Повторите проверку, произнеся фразу после отсчёта.');
  return studioUi(m.text||m.summary||'Проверка ещё не запускалась.');
}
function preflightCheckLabel(item) {
  return studioUi(({microphone:'Проверка голоса',audio_route:'Системный звук встречи',capture:'Совместный захват звука',
    aec:'Подавление акустического эха',stt:'Распознавание речи',llm:'Подсказки и отчёт',storage:'Запись результатов'})[item.key]||item.label||item.key);
}
function preflightCheckMessage(item) {
  const d=item.details||{};
  if(item.key==='microphone'&&item.state==='pass')return studioUi('сигнал найден: {device}',{device:d.device||'—'});
  if(item.key==='microphone'&&item.state==='incomplete')return studioUi('Микрофон открылся ({device}), но речь не подтверждена. Повторите проверку после отсчёта; проверьте mute и уровень входа.',{device:d.device||'—'});
  if(item.key==='stt'&&d.ok)return studioUi('Тестовая фраза распознана: «{text}»',{text:d.text||''});
  if(item.key==='llm'&&typeof d.configured==='boolean'&&item.state!=='fail')return studioUi(d.configured?'Доступ настроен: {provider}':'Доступ не подтверждён: {provider}',{provider:d.provider||'LLM'});
  if(item.key==='aec'&&item.state==='pass')return d.backend==='webrtc-aec3'
    ?studioUi('WebRTC AEC3 {version} отвечает; SHA-256 проверен',{version:d.version||'—'})
    :studioUi(item.message||'');
  return studioUi(item.message||'');
}
function renderPreflightChecks(list,checks) {
  const icons={pass:'OK',warn:'!',fail:'×',incomplete:'…'};
  list.replaceChildren();
  for(const check of checks){
    const row=document.createElement('div'), title=document.createElement('b'), text=document.createElement('span');
    row.className='preflight-item '+(['pass','warn','fail','incomplete'].includes(check.state)?check.state:'');
    studioLabel(title,()=>({source:(icons[check.state]||'·')+' · '+preflightCheckLabel(check)}));
    studioLabel(text,()=>({source:preflightCheckMessage(check)}));
    row.append(title,text);list.append(row);
  }
}
function renderPreflight(m) {
  const status = $("preflightStatus"), start = $("preflightStart"),
        quick = $("preflightQuick");
  const busy = !!m.busy || m.state === "started" || m.state === "progress";
  currentPreflightState = m.state || "not_run";
  start.disabled = busy;
  const success = m.state === "ready" || m.state === "ready_with_warnings";
  quick.disabled = busy;
  quick.classList.toggle("mode-on", success);
  setIconAction(quick, "check", busy ? "проверяю" : "проверить всё",
    preflightSummary(m));
  status.className = "workspace-status " + (m.state === "blocked" || m.state === "error"
    ? "error" : success ? "ready" : busy ? "scanning" : "");
  studioLabel(status,()=>({source:preflightSummary(m)}));
  renderPreflightChecks($("preflightChecks"),m.checks||[]);
  renderWorkflowNext();
}

function audioGuardActionLabel(kind) {
  return studioUi(({open_audio:"настройки звука",open_stt:"настройки STT",
           open_results:"открыть папку"})[kind] || "открыть настройки");
}
function audioGuardSeverityLabel(severity) {
  return studioUi(({notice:"рекомендация",warning:"внимание",
           critical:"критично"})[severity] || "событие");
}
function audioGuardEventCount(count) {
  if(window.BlateroI18n?.language==='en')return `${count} ${count===1?'event':'events'}`;
  const lastTwo = count % 100, last = count % 10;
  const word = lastTwo >= 11 && lastTwo <= 14 ? "событий"
    : last === 1 ? "событие" : last >= 2 && last <= 4 ? "события" : "событий";
  return `${count} ${word}`;
}
function runAudioGuardAction(kind) {
  if (kind === "open_audio") {
    $("audioOverlay").classList.add("show");
  } else if (kind === "open_stt") {
    openSettingsOverlay(document.activeElement);
    window.BlateroSettings?.reveal("selSpeech");
  } else if (kind === "open_results") {
    send({type:"open_report_folder"});
  }
}
function renderAudioGuard(guard, live) {
  const box = $("audioGuard"), issues = guard && Array.isArray(guard.issues)
    ? guard.issues : [];
  if (!live) {
    box.className = "audio-guard off"; box.open = false;
    return;
  }
  const state = ["ok","notice","warning","critical"].includes(guard && guard.state)
    ? guard.state : "ok";
  box.className = `audio-guard ${state}`;
  const ownedCodes = new Set(['transcript_write_error','device_change_gap','audio_filter_disabled']);
  const label = (issue, field) => ownedCodes.has(issue.code) ? studioUi(issue[field]||'') : (issue[field]||'');
  const first = issues[0];
  $("audioGuardSummary").textContent = first && ownedCodes.has(first.code)
    ? label(first,'title') + (issues.length > 1 ? studioUi(' · ещё {count}',{count:issues.length-1}) : '')
    : guard && guard.summary || "Звук в порядке";
  $("audioGuardCount").textContent = issues.length
    ? audioGuardEventCount(issues.length) : studioUi("автопроверка записи");
  $("audioGuardIssues").innerHTML = issues.map(issue =>
    `<article class="audio-issue ${esc(issue.severity||"notice")}">
      <div class="audio-issue-head"><strong>${esc(label(issue,'title')||"Аудиособытие")}</strong><span>${esc(audioGuardSeverityLabel(issue.severity))}</span></div>
      <p>${esc(label(issue,'detail'))}</p>
      <p class="audio-action"><b>${studioText('Что сделать:')}</b> ${esc(label(issue,'action'))}</p>
      <p class="audio-verify"><b>${studioText('Как проверить:')}</b> ${esc(label(issue,'verify'))}</p>
      <button data-audio-action="${esc(issue.action_kind||"open_audio")}">${esc(audioGuardActionLabel(issue.action_kind))}</button>
    </article>`).join("");
  $("audioGuardIssues").querySelectorAll("[data-audio-action]").forEach(button =>
    button.onclick = () => runAudioGuardAction(button.dataset.audioAction));
  // Status updates must not expand the footer or override the user's choice.
  // The compact severity/summary remains visible even for critical issues.
}

function formatRecordingLine(m) {
  const mins=Math.floor(m.sec/60);
  let time=mins+':'+String(m.sec%60).padStart(2,'0');
  if(meetingDuration){time+=' / '+meetingUi('{count} мин',{count:meetingDuration});if(mins>=meetingDuration-5)time+=' ⚠';}
  let text=m.rec?`REC ${m.files} · ${time}`:meetingUi('звук идёт · {time} · {files}',{time,files:m.files});
  if(m.mic)text+=meetingUi(' · мик: {device}',{device:m.mic});
  if(m.output)text+=meetingUi(' · встреча: {device}',{device:m.output});
  if(m.stt)text+=' · '+m.stt;
  if(m.echo_suppression&&m.echoes_suppressed)text+=meetingUi(' · текстовых дублей: {count}',{count:m.echoes_suppressed});
  if(m.aec_enabled){
    const backend=m.aec_backend==='webrtc-aec3'?'AEC3':'AEC fallback';
    text+=' · '+(m.aec_active?backend+' '+meetingUi('{value} дБ',{value:Number(m.aec_reduction_db||0).toFixed(1)})+(m.aec_delay_ms?meetingUi(' · {value} мс',{value:m.aec_delay_ms}):''):backend+': '+(m.aec_status||meetingUi('ожидание опоры')));
  }
  if(m.warning&&!(m.guard?.issues?.length))text+=meetingUi(' · ВНИМАНИЕ: {message}',{message:m.warning});
  return text;
}

function renderLevels(m) {
  if (m.session && (m.session !== currentInit?.current_dir ||
      m.generation !== currentInit?.session_generation)) return;
  if (m.session) recordingRef = m.recording_ref ?? null;
  const dot = $("recdot"), txt = $("rectext");
  const recordingChanged = recLive !== !!m.live;
  recLive = m.live;
  if (recordingChanged) notifyTrainingStudio();
  renderRecordButton(m.live);
  renderWorkflowNext();
  renderAudioGuard(m.guard || {}, m.live);
  const deviceEvent = m.device_change && typeof m.device_change === "object"
    ? m.device_change : {};
  const deviceEventId = Number(deviceEvent.event_id || 0);
  if (deviceEventId && deviceEventId !== lastAudioDeviceEventId && currentInit) {
    lastAudioDeviceEventId = deviceEventId;
    const selectedMic = currentInit.mic_current || "auto";
    const selectedOutput = currentInit.output_current || "auto";
    const mics = Array.isArray(deviceEvent.mics) ? [...deviceEvent.mics] : [];
    const outputs = Array.isArray(deviceEvent.outputs) ? [...deviceEvent.outputs] : [];
    if (!mics.includes(selectedMic)) mics.push(selectedMic);
    if (!outputs.includes(selectedOutput)) outputs.push(selectedOutput);
    const micPairs = mics.map(value => [value, value === "auto"
      ? "авто (системный)" : value.replace(/^Микрофон \(/, "").replace(/\)$/, "")]);
    const outputPairs = outputs.map(value => [value, value === "auto"
      ? "авто (системный)" : value.replace(/^Динамики \(/, "").replace(/\)$/, "")]);
    fillSelect("selMic", micPairs, selectedMic);
    fillSelect("testMic", micPairs, selectedMic);
    fillSelect("selOutput", outputPairs, selectedOutput);
    fillSelect("testOutput", outputPairs, selectedOutput);
  }
  if (!m.live) {
    dot.className = "";
    txt.style.color = "";
    meetingLabel(txt,"запись не запущена · микрофон можно проверить кнопкой «проверка звука»");
    return;
  }
  if (m.healthy === false || m.error) {
    dot.className = "";
    meetingLabel(txt,'ОШИБКА ЗАПИСИ: {message}',()=>({message:m.error||meetingUi('аудиоканал недоступен')}));
    txt.style.color = "var(--red)";
    return;
  }
  txt.style.color = "";
  dot.className = m.rec ? "on" : "";
  meetingLabel(txt,'{messages}',()=>({messages:formatRecordingLine(m)}));
  if (m.warning && !(m.guard && m.guard.issues && m.guard.issues.length)) {
    txt.style.color = "var(--yellow)";
  }
  waveMe.push(m.me || 0); waveGuest.push(m.guest || 0);
  const c = $("wave"), W = c.width = c.clientWidth, H = c.height;
  const maxN = Math.floor(W / 2);
  if (waveMe.length > maxN) { waveMe = waveMe.slice(-maxN); waveGuest = waveGuest.slice(-maxN); }
  const ctx = c.getContext("2d");
  ctx.clearRect(0, 0, W, H);
  const mid = H / 2;
  ctx.fillStyle = "rgba(0,212,255,.12)"; ctx.fillRect(0, mid - 0.5, W, 1);
  ctx.fillStyle = "#00D4FF";
  waveMe.forEach((v, i) => { const h = Math.max(1, v * (mid - 2)); ctx.fillRect(i * 2, mid - h, 1.5, h); });
  ctx.fillStyle = "#64FFDA";
  waveGuest.forEach((v, i) => { const h = Math.max(1, v * (mid - 2)); ctx.fillRect(i * 2, mid, 1.5, h); });
}

function fillSelect(id, pairs, current) {
  const el = $(id);
  el.innerHTML = pairs.map(([v, l]) => {
    const studioVoice = ['sceneInterviewerVoice','sceneCandidateVoice'].includes(id)
      && ['gemini38:kore:ru1','gemini38:kore:ru2','gemini38:kore:ru3','gemini38:charon:ru1','gemini38:charon:ru2','gemini38:charon:ru3'].includes(v);
    const owned = studioVoice || (['trainingPack','scenePack'].includes(id) && v === '') || (id === 'sceneInterviewerVoice' && v === 'question');
    return `<option value="${esc(v)}"${v === current ? " selected" : ""} ${owned?studioBind(l):''}>${esc(owned?studioUi(l):l)}</option>`;
  }).join("");
}

function applyCompetencyPack(selectId, roleId, hintId) {
  const select = $(selectId), role = $(roleId), hint = $(hintId);
  const pack = competencyPacks.find(item => item.value === select.value);
  const previousSuggestedRole = role.dataset.packRole || "";
  if (pack && (!role.value.trim() || role.value.trim() === previousSuggestedRole))
    role.value = pack.role;
  role.dataset.packRole = pack ? pack.role : "";
  hint.classList.toggle("ready", !!pack);
  studioLabel(hint,()=>({source:"{value}",values:{value:pack
    ? studioUi("{p0}. Проверенная рубрика v{p1}; резюме и рабочие материалы остаются отдельным источником фактов.",{p0:pack.description,p1:pack.version})
    : studioUi("Свободная роль: система построит вопросы только по указанной роли и вашим материалам.")}}));
}

const modeIcons = {"собеседование":"ASK", "кандидат":"ANS", "тренировка":"TRN",
                   "консалтинг":"ADV", "встреча":"MTG"};

function renderRecordButton(live) {
  document.body.classList.toggle("meeting-recording", !!live);
  window.BlateroRecording?.audioState(live);
  let panels = $("meetingPanelsToggle");
  if (!panels) {
    panels = document.createElement("button");
    panels.id = "meetingPanelsToggle"; panels.type = "button";
    panels.className = "icon-action";
    $("recbtn").parentElement.append(panels);
  }
  panels.onclick = () => {
    const expanded = document.body.classList.toggle("meeting-controls-expanded");
    panels.setAttribute("aria-expanded", String(expanded));
    meetingLabel(panels,expanded ? "свернуть панели" : "все панели");
  };
  panels.hidden = !live;
  meetingLabel(panels,document.body.classList.contains("meeting-controls-expanded") ? "свернуть панели" : "все панели");
  panels.setAttribute("aria-expanded", String(document.body.classList.contains("meeting-controls-expanded")));
  setIconAction($("recbtn"), live ? "stop" : "record",
    live ? "стоп" : "запись",
    live ? "Остановить и сохранить запись" : "Начать запись встречи");
}

function calibrationIsReady() {
  return !!(currentInit && currentInit.audio_calibration
    && currentInit.audio_calibration.ready);
}

function renderStartCalibration(event = null) {
  const box = $("startCalibration"), title = $("startCalibrationTitle");
  const text = $("startCalibrationText"), calibrate = $("startCalibrate");
  const bypass = $("startWithoutCalibration");
  const busy = event && event.type === "aec_test"
    && ["started", "progress"].includes(event.state);
  box.className = "start-calibration" + (calibrationIsReady() ? " ready" : busy ? " scanning" : "");
  calibrate.disabled = !!busy;
  if (calibrationIsReady()) {
    const calibration = currentInit.audio_calibration;
    meetingLabel(title,"Калибровка выполнена");
    meetingLabel(text,calibration.message || "Аудиомаршрут готов к записи.");
    calibrate.style.display = "none";
    bypass.style.display = "none";
  } else if (busy) {
    meetingLabel(title,"Идёт калибровка");
    meetingLabel(text,event.text || "Не говорите, пока звучит тестовый сигнал.");
    calibrate.style.display = "";
    bypass.style.display = "none";
  } else if (calibrationBypassed) {
    meetingLabel(title,"Калибровка пропущена для этой записи");
    meetingLabel(text,"Можно начинать, но звук встречи может повторно попасть в ваш микрофон.");
    calibrate.style.display = "";
    bypass.style.display = "none";
  } else {
    const calibration = currentInit && currentInit.audio_calibration;
    meetingLabel(title,"Перед записью рекомендуется калибровка");
    meetingLabel(text,(event && event.state === "error" ? event.text : null)
      || (calibration && calibration.message)
      || "Она проверит выход встречи и акустическое эхо; аудио никуда не отправляется.");
    calibrate.style.display = "";
    bypass.style.display = "";
  }
}

function renderStartModes(focusMode = "") {
  $("startModes").innerHTML = meetingTypeOptions.map(option =>
    `<button class="mode-choice${pendingStartMode === option.value ? " sel" : ""}" ` +
    `data-mode="${esc(option.value)}" aria-pressed="${pendingStartMode === option.value}"><span class="mode-icon">${modeIcons[option.value] || "MODE"}</span>` +
    `<span><b>${meetingText(option.label)}</b><span>${meetingText(option.description || "")}</span></span></button>`
  ).join("");
  $("startModes").querySelectorAll(".mode-choice").forEach(button => button.onclick = () => {
    pendingStartMode = button.dataset.mode;
    updateStartConfirmState();
    const option = meetingTypeOptions.find(item => item.value === pendingStartMode);
    meetingLabel($("startModeHint"),option ? option.description : "");
    if (option) $("startMeetingSummary").textContent = `${currentInit?.meta?.name || "Текущая встреча"} · ${option.label}`;
    renderStartModes(pendingStartMode);
  });
  if (focusMode) requestAnimationFrame(() =>
    $("startModes").querySelector(`[data-mode="${CSS.escape(focusMode)}"]`)?.focus());
}

function updateStartConfirmState() {
  const acknowledgement = $("startRecordingAck");
  const required = currentContour === "work";
  $("startRecordingAckWrap").hidden = !required;
  $("startConfirm").disabled = !pendingStartMode || (required && !acknowledgement.checked);
}

function workspaceHintForMode(mode) {
  if (mode === "собеседование") return wizardUi("Папка присланного тестового задания или репозитория кандидата.");
  if (mode === "кандидат") return wizardUi("Папка вашего проекта: ИИ подготовит вероятные вопросы о коде и корректные ответы.");
  if (mode === "тренировка") return wizardUi("Необязательно: папка вашего проекта или портфолио добавит вопросы по реальным материалам.");
  if (mode === "консалтинг") return wizardUi("Папка проекта или системы клиента: ИИ подготовит discovery-вопросы и карту пробелов.");
  return wizardUi("Папка с материалами и кодом, относящимися к встрече.");
}

function renderSetupModes(focusMode = "") {
  $("setupModes").innerHTML = meetingTypeOptions.map(option =>
    `<button class="mode-choice${setupMode === option.value ? " sel" : ""}" data-mode="${esc(option.value)}" aria-pressed="${setupMode === option.value}">` +
    `<span class="mode-icon">${modeIcons[option.value] || "MODE"}</span>` +
    `<span><b>${esc(wizardUi(option.label))}</b><span>${esc(wizardUi(option.description || ""))}</span></span></button>`
  ).join("");
  $("setupModes").querySelectorAll(".mode-choice").forEach(button => button.onclick = () => {
    setupMode = button.dataset.mode;
    const option = meetingTypeOptions.find(item => item.value === setupMode);
    $("setupModeStatus").className = "workspace-status ready";
    renderWorkspaceStatus('setupModeStatus',{state:'ready',message:option ? option.description : setupMode});
    $("setupWorkspaceHint").textContent = workspaceHintForMode(setupMode);
    renderSetupCopy();
    renderSetupModes(setupMode);
  });
  if (focusMode) queueMicrotask(() =>
    $("setupModes").querySelector(`[data-mode="${CSS.escape(focusMode)}"]`)?.focus());
}

function renderSetupCopy() {
  const training = setupMode === "тренировка";
  $("setupGoalHint").textContent = training
    ? wizardUi("Укажите профессию или должность. В поле материалов можно вставить резюме, вакансию, публичную HTTPS-ссылку и любые заметки.")
    : wizardUi("Для интервью укажите кандидата и фокус проверки; для консалтинга — клиента, проблему и ожидаемый результат разговора.");
  $("setupNameLabel").textContent = training ? wizardUi("Название / целевая роль") : wizardUi("Название / участник");
  $("setupName").placeholder = training ? "Senior product manager" : wizardUi("Александр · разработчик 1С");
  $("setupBriefLabel").textContent = training
    ? wizardUi("Резюме, вакансия, ссылки и любой контекст") : wizardUi("Цель, роль и темы");
  $("setupBrief").placeholder = training
    ? wizardUi("Вставьте текст резюме, описание вакансии, HTTPS-ссылку или любые заметки.")
    : wizardUi("Что нужно выяснить, проверить или решить? Какие темы обязательны?");
}

function renderContourSwitches() {
  document.querySelectorAll("#contourSwitch [data-contour]").forEach(button => {
    const active = button.dataset.contour === currentContour;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  document.querySelectorAll("#setupContourSwitch [data-contour]").forEach(button => {
    const active = button.dataset.contour === setupContour;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  if ($("setupContourHint")) {
    $("setupContourHint").textContent = setupContour === "test"
      ? wizardUi("Тестовый прогон не появится среди рабочих интервью и отчётов.")
      : wizardUi("Рабочая встреча хранится отдельно от тренировочных прогонов.");
  }
}

function sameWorkspacePath(left, right) {
  const slash = String.fromCharCode(92);
  return String(left || "").split(slash).join("/").replace(/[/]$/, "").toLowerCase()
    === String(right || "").split(slash).join("/").replace(/[/]$/, "").toLowerCase();
}

function renderSetupSummary() {
  const option = meetingTypeOptions.find(item => item.value === setupMode);
  const path = $("setupWorkspace").value.trim();
  const initialize = !!path && $("setupInitialize").checked;
  const provider = currentInit && currentInit.llm_connection
    ? currentInit.llm_connection.label : wizardUi("LLM не выбран");
  const mic = currentInit ? currentInit.mic_current : "?";
  const output = currentInit ? currentInit.output_current : "?";
  $("setupSummary").innerHTML = [
    [wizardUi("Контур"), setupContour === "test" ? wizardUi("Тестовый · изолированный") : wizardUi("Рабочий")],
    [wizardUi("Формат"), option ? wizardUi(option.label) : wizardUi("не выбран")],
    [wizardUi("Название"), $("setupName").value.trim() || wizardUi("не задано")],
    [wizardUi("Память"), [$("setupClient").value.trim(), $("setupProject").value.trim()]
      .filter(Boolean).join(" · ") || (path ? wizardUi("проект по рабочей папке") : wizardUi("не привязана"))],
    [wizardUi("Тайминг"), $("setupDuration").value ? wizardUi('{count} минут',{count:$("setupDuration").value}) : wizardUi("без лимита")],
    [wizardUi("Контекст проекта"), path ? `${path} · ${initialize ? wizardUi("ИИ-анализ") : wizardUi("только привязать")}` : wizardUi("без папки")],
    [wizardUi("ИИ"), settingsUi(provider)],
    [wizardUi("Звук"), wizardUi('микрофон: {mic}; встреча: {output}',{mic,output})],
  ].map(([label, value]) => `<div><b>${esc(label)}</b>${esc(String(value))}</div>`).join("");

  const ready = $("setupReadyStatus");
  let stateName = "ready", text = wizardUi("Можно создавать сессию. После подготовки проверьте звук и нажмите «начать запись».");
  let blocked = !setupMode || !$("setupName").value.trim();
  let needsAi = false, needsPrivacy = false;
  if (path && (!setupProbeResult || !sameWorkspacePath(path, setupProbeResult.path))) {
    stateName = "error"; text = wizardUi("Папка изменилась после проверки — вернитесь на шаг 3 и проверьте её снова."); blocked = true;
  } else if (initialize && setupProbeResult && setupProbeResult.state === "ready"
             && !(currentInit && currentInit.llm_connection && currentInit.llm_connection.configured)) {
    stateName = "error"; text = wizardUi("Для ИИ-подготовки настройте подключение к ИИ и проверьте соединение. Можно также создать встречу без ИИ-подготовки."); blocked = true; needsAi = true;
  } else if (initialize && setupProbeResult && setupProbeResult.state === "ready"
             && !(currentInit && currentInit.config.cloud_ack)) {
    stateName = "error"; text = wizardUi("Для ИИ-подготовки подтвердите основание облачной обработки. Можно также создать встречу без ИИ-подготовки."); blocked = true; needsPrivacy = true;
  } else if (initialize && setupProbeResult && ["empty", "insufficient"].includes(setupProbeResult.state)) {
    stateName = setupProbeResult.state;
    text = wizardUi('{message} Сессия создастся без ИИ-вопросов — добавьте материалы или заполните повестку вручную.',
      {message:window.BlateroWizardI18n?.message(setupProbeResult) || setupProbeResult.message});
  } else if (!path) {
    stateName = "insufficient";
    text = wizardUi("Рабочая папка не указана. Будет использована только цель встречи и общий сценарий.");
  }
  ready.className = `workspace-status ${stateName}`;
  ready.textContent = text;
  $("setupCreate").disabled = blocked;
  $("setupRemediation").hidden = !(needsAi || needsPrivacy);
  $("setupConfigureAi").hidden = !needsAi;
  $("setupConfigurePrivacy").hidden = !needsPrivacy;
}

function renderSetupStep(moveFocus = false, preserveScroll = false) {
  document.querySelectorAll(".wizard-step").forEach(step => {
    const active = Number(step.dataset.step) === setupStep;
    step.classList.toggle("active", active);
    step.setAttribute("aria-hidden", String(!active));
  });
  $("setupProgress").querySelectorAll("span").forEach(item => {
    const number = Number(item.dataset.step);
    item.classList.toggle("active", number === setupStep);
    item.classList.toggle("done", number < setupStep);
    if (number === setupStep) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  });
  $("setupBack").style.visibility = setupStep === 1 ? "hidden" : "visible";
  $("setupNext").style.display = setupStep === 4 ? "none" : "";
  $("setupCreate").style.display = setupStep === 4 ? "" : "none";
  $("setupActionStatus").textContent = wizardUi('Шаг {step} из {total}',{step:setupStep,total:4});
  $("setupNext").textContent = ({1:wizardUi("дальше: цель"), 2:wizardUi("дальше: материалы"),
                                  3:wizardUi("дальше: проверка")})[setupStep] || wizardUi("продолжить");
  if (setupStep === 4) {
    renderSetupSummary();
    const withPreparation = !!$("setupWorkspace").value.trim() && $("setupInitialize").checked;
    $("setupCreate").textContent = withPreparation
      ? wizardUi("создать и подготовить")
      : wizardUi("создать встречу");
  }
  if (!preserveScroll) $("setupOverlay").scrollTop = 0;
  if (moveFocus) queueMicrotask(() => $("setupStepTitle" + setupStep)?.focus());
}

function setupStepValid() {
  if (setupStep === 1 && !setupMode) {
    renderWorkspaceStatus("setupModeStatus", {state:"error", message:wizardUi("Сначала выберите формат встречи.")});
    return false;
  }
  if (setupStep === 2 && !$("setupName").value.trim()) {
    $("status").textContent = wizardUi("укажите название встречи или участника");
    $("setupName").focus(); return false;
  }
  if (setupStep === 3) {
    const path = $("setupWorkspace").value.trim();
    if (path && (!setupProbeResult || !sameWorkspacePath(path, setupProbeResult.path))) {
      renderWorkspaceStatus("setupProbeStatus", {state:"error", message:wizardUi("Нажмите «проверить папку локально» перед продолжением.")});
      return false;
    }
  }
  return true;
}

function openSetupWizard(preferredMode = null) {
  setupStep = 1; setupMode = preferredMode; setupContour = currentContour;
  setupProbeResult = null;
  setupProbeRequest = null;
  $("setupName").value = "";
  $("setupDuration").value = (currentInit && currentInit.meta && currentInit.meta.duration)
    ? String(currentInit.meta.duration) : "30";
  $("setupBrief").value = "";
  $("setupClient").value = "";
  $("setupProject").value = "";
  $("setupWorkspace").value = "";
  $("setupInitialize").checked = true;
  const option = meetingTypeOptions.find(item => item.value === setupMode);
  renderWorkspaceStatus("setupModeStatus", {state:option ? "ready" : "not_configured",
    message:option ? option.description : wizardUi("Выберите формат встречи.")});
  renderWorkspaceStatus("setupProbeStatus", {state:"not_configured", message:wizardUi("Папка ещё не проверена. Её можно оставить пустой и подготовить встречу вручную.")});
  $("setupWorkspaceHint").textContent = workspaceHintForMode(setupMode);
  renderSetupCopy(); renderSetupModes(); renderContourSwitches(); renderSetupStep();
  $("setupOverlay").classList.add("show");
  $("setupTitle").focus();
}

function syncEmptyLayout() {
  const empty = $("empty");
  const hasHints = ["answers", "tags", "questions", "flags", "uncovered"]
    .some(id => $(id).childElementCount > 0 || $(id).textContent.trim());
  const visible = empty.style.display !== "none";
  document.body.classList.toggle("empty-state",
    visible && !hasHints && !document.body.classList.contains("training-mode"));
}

function applyMeetingMode(mtype) {
  const candidate = mtype === "кандидат";
  const training = mtype === "тренировка";
  document.body.classList.toggle("candidate-mode", candidate);
  document.body.classList.toggle("training-mode", training);
  syncEmptyLayout();
  $("trainingPanel").hidden = !training;
  setIconAction($("pulse"), "spark", candidate || training ? "быстрый ответ" : "ещё подсказку",
    candidate || training ? "Готовый ответ на последний вопрос интервьюера"
      : "Следующий вопрос и точки для уточнения");
  updateReportButton();
  setIconAction($("agendaBtn"), "agenda", candidate || training ? "темы и вакансия" : "повестка",
    candidate || training ? "Темы, вакансия и материалы" : "Повестка и материалы встречи");
  renderEmulationMode(mtype);
}

function renderEmulationMode(mtype = currentMeetingType) {
  const button = $("emuBtn");
  button.style.display = mtype === "тренировка" ? "none" : "";
  button.classList.toggle("mode-on", emulationEnabled);
  setIconAction(button, "emulation", "эмуляция",
    emulationEnabled ? `Выключить роль «${emulationRole}»`
      : `Включить эмуляцию роли «${emulationRole}»`);
}

let speechStartRequest = null;
function openStartOverlay(preferredMode = null, recordingVideo = null, speechToken = null) {
  speechStartRequest = {...(speechToken ? {speech_rec_token:speechToken} : {}),
    session:currentInit?.current_dir, generation:currentInit?.session_generation, server_epoch:currentInit?.server_epoch};
  window.BlateroRecording?.onStartOverlay(recordingVideo);
  const savedMode = preferredMode || currentInit?.meta?.type || currentMeetingType;
  pendingStartMode = meetingTypeOptions.some(item => item.value === savedMode) ? savedMode : null;
  calibrationBypassed = false;
  $("startRecordingAck").checked = false;
  updateStartConfirmState();
  const option = meetingTypeOptions.find(item => item.value === pendingStartMode);
  meetingLabel($("startTitle"),pendingStartMode ? "Начать запись текущей встречи?" : "В какой роли вы участвуете?");
  $("startMeetingSummary").textContent = pendingStartMode
    ? `${currentInit?.meta?.name || "Текущая встреча"} · ${option.label}` : "Выберите формат встречи.";
  $("startModes").hidden = !!pendingStartMode;
  $("startChangeMode").hidden = !pendingStartMode;
  $("startModeHint").textContent = option ? option.description : "Выберите один вариант.";
  renderStartModes();
  renderStartCalibration();
  $("startOverlay").classList.add("show");
  $("startTitle").focus();
}

$("startChangeMode").onclick = () => {
  $("startModes").hidden = false;
  $("startChangeMode").hidden = true;
  renderStartModes(pendingStartMode);
};

function applyFontScale(value) {
  const scale = Number.parseFloat(value);
  document.documentElement.style.fontSize = `${16 * (Number.isFinite(scale) ? scale : 1.15)}px`;
}

function updateModelSuggestions(provider, discovered = null) {
  const configured = currentInit && currentInit.models_by_provider
    ? (currentInit.models_by_provider[provider] || []) : [];
  const values = discovered && discovered.length
    ? discovered.map(value => [value, value]) : configured;
  $("llmModelSuggestions").innerHTML = values.map(([value, label]) =>
    `<option value="${esc(value)}">${esc(label || value)}</option>`).join("");
}

// Translate only catalogued program labels, never credentials or meeting content.
function settingsUi(text, params = {}) {
  return window.BlateroSettingsI18n?.ui(text, params) ?? String(text ?? '').replace(
    /\{([a-zA-Z_]\w*)\}/g, (match, name) => Object.hasOwn(params, name) ? String(params[name]) : match);
}

function renderLlmConnection(data) {
  const provider = $("selProvider").value;
  if (data.provider && data.provider !== provider) return;
  const el = $("llmConnectionStatus");
  const stateName = data.state || (data.configured ? "selected" : "not_configured");
  el.className = `workspace-status ${stateName}`;
  el.textContent = data.message ? settingsUi(data.message) : (data.configured
    ? settingsUi('Доступ настроен: {source}. Нажмите «проверить соединение».',
      {source: settingsUi(data.source || 'источник найден')})
    : settingsUi('Доступ ещё не настроен. Введите токен и нажмите «проверить соединение».'));
  el.lang = /[а-яё]/i.test(el.textContent) ? 'ru' : (window.BlateroI18n?.language || 'ru');
  const busy = stateName === "scanning";
  $("llmSave").disabled = busy;
  $("llmTest").disabled = busy;
  $("llmDelete").disabled = busy;
  $("llmDelete").style.display = data.can_delete ? "" : "none";
  if (data.models && data.models.length) updateModelSuggestions(provider, data.models);
  if (stateName === "ready" || /сохранен|сохранён/i.test(data.message || ""))
    $("inpLlmApiKey").value = "";
}

function updateProviderControls(provider, connection = null) {
  const codex = provider === "codex";
  const compatible = provider === "compatible";
  $("pulseModelCtl").style.display = codex ? "none" : "";
  $("reportModelCtl").style.display = codex ? "none" : "";
  $("providerHint").style.display = codex ? "" : "none";
  $("providerHint").textContent = codex ? settingsUi("модель: Codex по умолчанию") : "";
  $("llmKeyRow").style.display = codex ? "none" : "";
  $("llmBaseUrlRow").style.display = compatible ? "" : "none";
  $("llmSave").style.display = codex ? "none" : "";
  $("llmKeyRow").querySelector("label, span").textContent = settingsUi(compatible
    ? "API-токен (необязательно)" : "API-токен");
  $("inpLlmApiKey").placeholder = settingsUi(compatible
    ? "необязательно для локального сервера" : "вставьте новый токен или оставьте пустым");
  updateModelSuggestions(provider);
  if (connection && connection.provider === provider) {
    $("llmProviderGuide").textContent = settingsUi(connection.help_text || "");
    $("llmProviderHelp").href = connection.help_url || "#";
    $("llmProviderHelp").hidden = !connection.help_url;
    $("inpLlmBaseUrl").value = compatible ? (connection.base_url || "") : "";
    renderLlmConnection(connection);
  } else {
    const guide = currentInit?.llm_provider_help?.[provider];
    $("llmProviderGuide").textContent = settingsUi(guide?.text || (codex
      ? "API-токен не нужен. Выполните codex login и проверьте соединение."
      : "Укажите доступ и проверьте соединение."));
    $("llmProviderHelp").href = guide?.url || "#";
    $("llmProviderHelp").hidden = !guide?.url;
    $("llmDelete").style.display = "none";
    renderLlmConnection({provider, state:"selected", message:"Провайдер выбран. Настройте доступ и выполните проверку."});
  }
}

function updateSpeechControls(provider) {
  $("whisperModelCtl").style.display = provider === "local_whisper" ? "" : "none";
}

function renderProviderContractStatus(contract) {
  const target = $("providerContractStatus");
  if (!target) return;
  const routes = contract.selection || {};
  const domainLabels = {llm:"LLM",stt:"STT",tts:"TTS",diarization:"голоса"};
  const executionLabels = {local:"локально",cloud:"облако",hybrid:"локально → облако"};
  const chips = Object.entries(routes).map(([domain, route]) =>
    `<span class="provider-route ${route.blocked ? "blocked" : route.execution}">` +
    `<b>${esc(settingsUi(domainLabels[domain] || domain))}</b> ${esc(settingsUi(executionLabels[route.execution] || route.execution))}` +
    `${route.blocked ? settingsUi(" · выключено") : ""}</span>`).join("");
  const issues = (contract.issues || []).map(item => {
    // Known codes have stable UI wording. Unknown diagnostics retain their detail.
    const message = item.code === 'cloud_ack_required'
      ? settingsUi(routes[item.domain]?.label || item.domain) + ': ' + settingsUi('Облачный маршрут выключен до согласия')
      : item.code === 'unknown_provider'
        ? settingsUi('Неизвестный провайдер для {domain}', {domain:item.domain}) + ': ' + (item.message || item.code)
        : item.message || item.code;
    return `<div class="provider-contract-issue">${esc(message)}</div>`;
  }).join("");
  target.innerHTML = `<div class="provider-contract-head"><strong>${esc(settingsUi('Контур данных'))}</strong>` +
    `<span>${esc(contract.schema || settingsUi("контракт не загружен"))}</span></div>` +
    `<div class="provider-contract-routes">${chips}</div>${issues}`;
}

function selectedPrompt() {
  return promptCatalog.find(item => item.key === selectedPromptKey) || null;
}

function renderPromptList() {
  let category = "", html = "";
  promptCatalog.forEach(item => {
    if (item.category !== category) {
      category = item.category;
      html += `<div class="prompt-category">${esc(category)}</div>`;
    }
    html += `<button class="prompt-item${item.key === selectedPromptKey ? " sel" : ""}` +
      `${item.customized ? " modified" : ""}" data-key="${esc(item.key)}">${esc(item.label)}</button>`;
  });
  $("promptList").innerHTML = html || studioUi("Редактируемые промпты не найдены.");
  $("promptList").querySelectorAll(".prompt-item").forEach(button =>
    button.onclick = () => showPrompt(button.dataset.key));
}

function showPrompt(key) {
  const item = promptCatalog.find(value => value.key === key);
  if (!item) return;
  if (selectedPromptKey && selectedPromptKey !== key && promptHasDraft()
      && !confirm(studioUi("Перейти к другому промпту и потерять несохранённые изменения?"))) return;
  selectedPromptKey = item.key;
  renderPromptList();
  studioValue($("promptLabel"),item.label);
  studioValue($("promptDescription"),item.description || "");
  studioValue($("promptKey"),item.key);
  $("promptText").disabled = false;
  $("promptText").value = item.text;
  studioValue($("promptDefault"),item.default);
  $("promptDefaultBox").open = false;
  const markers = (item.placeholders || []).map(value => `{${value}}`)
    .concat(item.required_literals || []);
  $("promptPlaceholders").innerHTML = markers.length
    ? studioUi("Обязательные служебные маркеры: ") + markers.map(value => `<code>${esc(value)}</code>`).join(" · ")
    : studioUi("Служебных подстановок нет — текст можно менять свободно.");
  $("promptSave").disabled = true;
  $("promptReset").disabled = !item.customized;
  $("promptStatus").style.color = item.validation_error ? "var(--red)" : item.customized ? "var(--yellow)" : "var(--dim)";
  studioLabel($("promptStatus"),()=>({source:"{value}",values:{value:item.validation_error
    ? studioUi("Локальный шаблон не применяется; используется заводской. ") + item.validation_error
    : item.customized ? studioUi("используется локальная версия") : studioUi("заводской вариант")}}));
}

function receivePromptCatalog(message) {
  const draft = $("promptText").value;
  const previousKey = selectedPromptKey;
  promptCatalog = message.items || [];
  selectedPromptKey = promptCatalog.some(item => item.key === previousKey)
    ? previousKey : (promptCatalog[0] && promptCatalog[0].key);
  renderPromptList();
  if (selectedPromptKey) showPrompt(selectedPromptKey);
  if (message.error) {
    $("promptText").value = draft;
    $("promptSave").disabled = false;
    $("promptStatus").style.color = "var(--red)";
    $("promptStatus").textContent = message.error;
  } else if (message.message) {
    $("promptStatus").style.color = "var(--green)";
    studioLabel($("promptStatus"),message.message);
  }
}

function promptHasDraft() {
  const item = selectedPrompt();
  return !!item && $("promptText").value !== item.text;
}

function uiPreference(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(`blatero.${key}`);
    localStorage.setItem(`blatero.${key}`, String(value));
  } catch (_) { return null; }
  return value;
}

function markCustomLayout() {
  uiPreference("layoutPreset", "custom");
  if ($("layoutPreset")) $("layoutPreset").value = "custom";
}

function applySideWidth(value, persist = true) {
  const width = Math.max(320, Math.min(900, Number(value) || 620));
  document.documentElement.style.setProperty("--side-width", `${width}px`);
  $("sideWidth").value = String(width);
  $("sideWidthValue").textContent = `${width} px`;
  $("sideResize").setAttribute("aria-valuenow", String(width));
  if (persist) uiPreference("sideWidth", width);
}

function setSideVisible(visible, persist = true, custom = true) {
  document.body.classList.toggle("side-collapsed", !visible);
  if (["кандидат", "тренировка"].includes(currentMeetingType))
    document.body.classList.toggle("memory-open", visible);
  $("layoutSideVisible").checked = visible;
  if (persist) uiPreference("sideCollapsed", visible ? "0" : "1");
  if (persist && custom) markCustomLayout();
}

function toggleSide() {
  setSideVisible(getComputedStyle($("side")).display === "none");
}

function setTranscriptVisible(visible, persist = true, custom = true) {
  document.body.classList.toggle("feed-collapsed", !visible);
  $("layoutFeedVisible").checked = visible;
  $("feedVisibility").setAttribute("aria-pressed", String(visible));
  meetingLabel($("feedVisibility"),visible ? "скрыть историю" : "показать историю");
  if (persist) uiPreference("feedVisible", visible ? "1" : "0");
  if (persist && custom) markCustomLayout();
}

function setTranscriptTall(tall, persist = true, custom = true) {
  document.querySelector("footer").classList.toggle("feed-expanded", tall);
  $("layoutFeedTall").checked = tall;
  meetingLabel($("feedExpand"),tall ? "свернуть" : "развернуть");
  if (persist) uiPreference("feedTall", tall ? "1" : "0");
  if (persist && custom) markCustomLayout();
}

function applyLayoutPreset(name, persist = true) {
  const preset = ["standard","focus","review"].includes(name) ? name : "custom";
  if (preset === "standard") {
    setSideVisible(true, persist, false);
    setTranscriptVisible(true, persist, false);
    setTranscriptTall(false, persist, false);
  } else if (preset === "focus") {
    setSideVisible(false, persist, false);
    setTranscriptVisible(false, persist, false);
    setTranscriptTall(false, persist, false);
  } else if (preset === "review") {
    setSideVisible(true, persist, false);
    setTranscriptVisible(true, persist, false);
    setTranscriptTall(true, persist, false);
  }
  $("layoutPreset").value = preset;
  if (persist) uiPreference("layoutPreset", preset);
}

function resetLayout() {
  applySideWidth(620);
  applyLayoutPreset("standard");
}

async function copyUiText(text) {
  if (!text) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(text); return;
  }
  const field = document.createElement("textarea");
  field.value = text; field.style.position = "fixed"; field.style.opacity = "0";
  document.body.appendChild(field); field.select(); document.execCommand("copy"); field.remove();
}

function clearPinnedHint() {
  pinnedHint = {text:"",label:""};
  $("pinnedHint").hidden = true;
  $("pinnedHintText").textContent = "";
}

function setPinnedHint(text, label = "Закреплено") {
  if (!text) return;
  pinnedHint = {text,label};
  $("pinnedHintLabel").textContent = label;
  $("pinnedHintText").textContent = text;
  $("pinnedHint").hidden = false;
  $("hintzone").scrollTo({top:0,behavior:"smooth"});
}

function openFocusAnswer(text = pinnedHint.text || latestAnswer) {
  if (!text) return;
  $("focusAnswerText").textContent = text;
  $("focusAnswerOverlay").classList.add("show");
  $("focusAnswerClose").focus();
}

function commandDefinitions() {
  return [
    {label:studioUi("Получить подсказку"),detail:studioUi("Сильный следующий ход по текущей встрече"),keys:"P",search:studioUi("ответ совет"),run:() => send({type:"pulse"})},
    {label:recLive ? studioUi("Остановить запись") : studioUi("Начать запись"),detail:studioUi("Управление записью текущей встречи"),keys:"",search:studioUi("старт стоп микрофон"),run:() => $("recbtn").click()},
    {label:studioUi("Новая встреча"),detail:studioUi("Пошаговая подготовка встречи или тренировки"),keys:"",search:studioUi("создать интервью консалтинг"),run:() => $("setupBtn").click()},
    {label:studioUi("Проверить всё"),detail:studioUi("Микрофон, системный звук, эхо, распознавание речи и ИИ"),keys:"",search:studioUi("диагностика звук"),run:() => $("preflightQuick").click()},
    {label:studioUi("Свернуть / показать сценарий"),detail:studioUi("Освободить место для подсказок"),keys:"Ctrl+B",search:studioUi("боковая колонка фокус"),run:toggleSide},
    {label:studioUi("Показать / скрыть историю"),detail:studioUi("Транскрипт без скрытия Аудиосторожа"),keys:"Ctrl+J",search:studioUi("лента реплики история"),run:() => setTranscriptVisible(document.body.classList.contains("feed-collapsed"))},
    ...(latestAnswer ? [{label:studioUi("Показать последний ответ крупно"),detail:studioUi("Режим чтения без отвлечений"),keys:"",search:studioUi("подсказка экран"),run:() => openFocusAnswer()}] : []),
    {label:studioUi("Повестка"),detail:studioUi("Открыть контекст текущей встречи"),keys:"",search:"agenda",run:() => $("agendaBtn").click()},
    {label:studioUi("Календарь"),detail:studioUi("Расписание дня и недели"),keys:"",search:studioUi("встречи события"),run:() => $("calendarBtn").click()},
    {label:studioUi("Тренировка собеседования"),detail:studioUi("Вопросы, голос и оценка ответа"),keys:"",search:studioUi("mock интервью обучение"),run:() => $("trainingBtn").click()},
    {label:studioUi("Память клиента и проекта"),detail:studioUi("Решения, обещания и открытые вопросы"),keys:"",search:studioUi("контекст история"),run:() => $("memoryBtn").click()},
    {label:studioUi("Сформировать отчёт"),detail:studioUi("Контроль качества и DOCX"),keys:"",search:studioUi("документ результат"),run:() => $("report").click()},
    {label:studioUi("Настройки"),detail:studioUi("Встреча, ИИ, звук, приватность и интерфейс"),keys:"",search:studioUi("конфигурация"),run:() => $("settingsBtn").click()},
    {label:studioUi("Аудио и говорящие"),detail:studioUi("Записи, Replay Lab, голоса, имена и проверка каналов"),keys:"",search:studioUi("aec chatterbox яндекс диаризация"),run:openAnalysisHub},
    {label:studioUi("Локальные модели"),detail:studioUi("Whisper, Chatterbox, AEC и разделение голосов"),keys:"",search:studioUi("установить удалить место диск"),run:openModelManager},
    {label:studioUi("Установка и обновления"),detail:studioUi("Проверка подписи, обновление и откат"),keys:"",search:studioUi("версия релиз rollback"),run:openUpdateManager},
    {label:studioUi("Восстановление записей"),detail:studioUi("Незавершённые встречи после сбоя"),keys:"",search:studioUi("авария wav jsonl"),run:openRecovery},
    {label:studioUi("Системные промпты"),detail:studioUi("Просмотр и локальное редактирование"),keys:"",search:studioUi("инструкции llm"),run:() => $("promptEditorBtn").click()},
    {label:studioUi("Открыть папку результатов"),detail:studioUi("Текущая встреча в Проводнике"),keys:"",search:studioUi("отчет файлы"),run:() => $("openReportFolder").click()}
  ];
}

function recoveryDuration(seconds) {
  const value = Math.max(0, Math.round(Number(seconds) || 0));
  const minutes = Math.floor(value / 60), tail = value % 60;
  return minutes ? studioUi("{p0} мин {p1} с",{p0:minutes,p1:tail}) : studioUi("{p0} с",{p0:tail});
}

function recoveryBytes(bytes) {
  return modelSize(Math.max(0,Number(bytes)||0));
}

function openRecovery() {
  renderRecovery(recoveryState, false);
  $("recoveryOverlay").classList.add("show");
  $("recoveryTitle").focus();
}

function renderRecovery(value, autoOpen = false) {
  recoveryState = value || {state:"ready",items:[]};
  const items = recoveryState.items || [];
  const jobs = recoveryState.jobs || [];
  const schemas = recoveryState.schemas || [];
  const total = Number(recoveryState.count) || items.length + jobs.length + schemas.length;
  studioValue($("recoveryCount"),total ? String(total) : "");
  $("recoveryCount").hidden = !total;
  $("recoveryEmpty").hidden = !!total;
  $("recoveryList").innerHTML = items.map(item => {
    const issues = (item.issues || []).map(issue => `<li>${esc(String(issue))}</li>`).join("");
    const audio = (item.audio || []).map(file =>
      `<span class="recovery-chip ${file.valid ? "ready" : "warn"}">${esc(file.name)} · ${file.valid ? studioText("цел") : studioText("нужна проверка")}</span>`).join("");
    const date = item.last_activity ? new Date(item.last_activity).toLocaleString(window.BlateroI18n?.locale||"ru-RU") : studioUi("время неизвестно");
    const space = item.space || {};
    const ready = item.repairable && item.recovery_ready !== false;
    const spaceChip = space.checked === false
      ? `<span class="recovery-chip warn">${studioText("место не проверено")}</span>`
      : (space.required_bytes
        ? `<span class="recovery-chip ${space.sufficient === false ? "warn" : "ready"}">${studioText("нужно ")}${recoveryBytes(space.required_bytes)}${studioText(" · свободно ")}${recoveryBytes(space.free_bytes)}</span>`
        : "");
    const stateLabel = !item.repairable ? studioUi("нужна проверка") :
      (ready ? studioUi("можно восстановить") : studioUi("освободите место"));
    return `<article class="recovery-card" data-session="${esc(item.session)}">
      <div class="recovery-card-head"><div><span class="model-kind">${studioText("ПРЕРВАННАЯ ЗАПИСЬ · ")}${esc(item.source || "lifecycle")}</span>
        <h4>${esc(item.label || item.session)}</h4><p>${esc(date)} · ${recoveryDuration(item.duration_seconds)}${studioText(" · реплик: ")}${Number(item.turns) || 0}</p></div>
        <span class="recovery-state">${studioText(stateLabel)}</span></div>
      <div class="recovery-audio">${audio || `<span class="recovery-chip">${studioText("WAV не записывался")}</span>`}${spaceChip}</div>
      <ul>${issues}</ul>
      <div class="recovery-actions">
        <button class="primary" data-recovery="recover" ${ready && localRecoveryControl ? "" : "disabled"}>${studioText("восстановить и открыть")}</button>
        <button data-recovery="finalize" ${localRecoveryControl ? "" : "disabled"}>${studioText("завершить как прерванную")}</button>
        <button data-recovery="cleanup" ${localRecoveryControl ? "" : "disabled"}>${studioText("очистить временные хвосты")}</button>
      </div></article>`;
  }).join("");
  $("recoveryList").querySelectorAll("[data-recovery]").forEach(button => {
    button.onclick = () => {
      const card = button.closest("[data-session]");
      const action = button.dataset.recovery;
      if (action === "finalize" && !confirm(studioUi("Оставить аудио и транскрипт без изменений и больше не предлагать восстановление?"))) return;
      card.querySelectorAll("button").forEach(item => item.disabled = true);
      send({type:"recovery", action, session:card.dataset.session});
    };
  });
  $("recoveryJobs").innerHTML = jobs.map(item => {
    const date = item.last_activity ? new Date(item.last_activity).toLocaleString(window.BlateroI18n?.locale||"ru-RU") : studioUi("время неизвестно");
    const mode = item.recovery_mode === "saved_draft" ? studioUi("контрольная точка") :
      (item.recovery_mode === "local_finalize" ? studioUi("локальное продолжение") : studioUi("нужен повтор"));
    const cost = item.new_llm_request
      ? `<span class="recovery-chip warn">${studioText("новый LLM-запрос")}</span>`
      : `<span class="recovery-chip ready">${studioText("без нового LLM-запроса")}</span>`;
    return `<article class="recovery-card recovery-job" data-job-session="${esc(item.session)}" data-job-kind="${esc(item.kind)}">
      <div class="recovery-card-head"><div><span class="model-kind">${studioText("ФОНОВАЯ ЗАДАЧА · ")}${esc((item.kind || "job").toUpperCase())}</span>
        <h4>${esc(item.label || item.kind)}</h4><p>${esc(item.session_label || item.session)} · ${esc(date)}</p></div>
        <span class="recovery-state">${studioText(mode)}</span></div>
      <p class="recovery-job-message">${item.message?esc(item.message):studioText("Задача была прервана.")}</p>
      ${item.error ? `<div class="recovery-job-error">${esc(item.error)}</div>` : ""}
      <div class="recovery-audio">${cost}<span class="recovery-chip">${studioText("этап: ")}${esc(item.stage || "неизвестен")}</span></div>
      <div class="recovery-actions">
        <button class="primary" data-job-recovery="job_retry" ${localRecoveryControl ? "" : "disabled"}>${item.new_llm_request ? studioText("повторить после подтверждения") : studioText("продолжить")}</button>
        <button data-job-recovery="job_dismiss" ${localRecoveryControl ? "" : "disabled"}>${studioText("не возобновлять")}</button>
        <button data-job-recovery="job_cleanup" ${localRecoveryControl ? "" : "disabled"}>${studioText("очистить временные файлы")}</button>
      </div></article>`;
  }).join("");
  $("recoveryJobs").querySelectorAll("[data-job-recovery]").forEach(button => {
    button.onclick = () => {
      const card = button.closest("[data-job-session]");
      const action = button.dataset.jobRecovery;
      const item = jobs.find(candidate => candidate.session === card.dataset.jobSession
        && candidate.kind === card.dataset.jobKind);
      let confirmedNewLlm = false;
      if (action === "job_retry" && item && item.new_llm_request
          && !confirm(studioUi("Сохранённого ответа LLM нет. Повторить задачу с новым запросом к выбранному провайдеру?"))) return;
      if (action === "job_retry" && item && item.new_llm_request) confirmedNewLlm = true;
      if (action === "job_dismiss"
          && !confirm(studioUi("Не возобновлять эту задачу? Уже сохранённые файлы встречи останутся."))) return;
      card.querySelectorAll("button").forEach(control => control.disabled = true);
      send({type:"recovery", action, session:card.dataset.jobSession,
            kind:card.dataset.jobKind, confirm_new_llm:confirmedNewLlm});
    };
  });
  $("recoverySchemas").innerHTML = schemas.map(item => {
    const version = item.version === null || item.version === undefined
      ? studioUi("версия неизвестна") : `v${Number(item.version)} → v${Number(item.current_version)}`;
    const stateLabel = item.can_migrate ? studioUi("можно завершить") :
      (item.state === "future" ? studioUi("нужна новая версия") : studioUi("заблокировано"));
    return `<article class="recovery-card recovery-schema" data-schema-session="${esc(item.session)}">
      <div class="recovery-card-head"><div><span class="model-kind">${studioText("ФОРМАТ ДАННЫХ")}</span>
        <h4>${esc(item.label || item.session)}</h4><p>${esc(version)}</p></div>
        <span class="recovery-state">${studioText(stateLabel)}</span></div>
      <p class="recovery-job-message">${item.message?esc(item.message):studioText("Схема сессии требует проверки.")}</p>
      <div class="recovery-actions">
        ${item.can_migrate ? `<button class="primary" data-schema-recovery="schema_migrate" ${localRecoveryControl ? "" : "disabled"}>${studioText("обновить схему")}</button>` : ""}
      </div></article>`;
  }).join("");
  $("recoverySchemas").querySelectorAll("[data-schema-recovery]").forEach(button => {
    button.onclick = () => {
      const card = button.closest("[data-schema-session]");
      if (!confirm(studioUi("Завершить локальную миграцию с резервной копией meta.json?"))) return;
      button.disabled = true;
      send({type:"recovery", action:"schema_migrate",
            session:card.dataset.schemaSession});
    };
  });
  const signature = [
    ...items.map(item => `rec:${item.session}:${item.last_activity}`),
    ...jobs.map(item => `job:${item.session}:${item.kind}:${item.last_activity}`),
    ...schemas.map(item => `schema:${item.session}:${item.state}:${item.version}`)
  ].join("|");
  if (autoOpen && localRecoveryControl && signature
      && signature !== recoveryPromptSignature) {
    recoveryPromptSignature = signature;
    openRecovery();
  }
  if (!total) $("recoveryOverlay").classList.remove("show");
}

function renderCommands(query = "") {
  const words = query.toLocaleLowerCase("ru-RU").trim().split(/\s+/).filter(Boolean);
  visibleCommands = commandDefinitions().filter(command => {
    const haystack = `${command.label} ${command.detail} ${command.search || ""}`.toLocaleLowerCase("ru-RU");
    return words.every(word => haystack.includes(word));
  });
  commandSelection = Math.min(commandSelection, Math.max(0, visibleCommands.length - 1));
  $("commandList").innerHTML = visibleCommands.length ? visibleCommands.map((command,index) =>
    `<button id="commandOption${index}" class="command-item${index === commandSelection ? " selected" : ""}" role="option" aria-selected="${index === commandSelection}" tabindex="-1" data-index="${index}"><strong>${studioText(command.label)}</strong><small>${studioText(command.detail)}</small>${command.keys ? `<kbd>${esc(command.keys)}</kbd>` : ""}</button>`).join("")
    : `<div class="command-empty">${studioText("Ничего не найдено. Попробуйте «звук», «отчёт» или «сценарий».")}</div>`;
  $("commandList").querySelectorAll(".command-item").forEach(button => {
    button.onmouseenter = () => {
      commandSelection = Number(button.dataset.index);
      $("commandList").querySelectorAll(".command-item").forEach(item => {
        const selected = item === button;
        item.classList.toggle("selected", selected);
        item.setAttribute("aria-selected", String(selected));
      });
    };
    button.onclick = () => runSelectedCommand(Number(button.dataset.index));
  });
  const selected = $("commandList").querySelector(".selected");
  if (selected) {
    selected.scrollIntoView({block:"nearest"});
    $("commandSearch").setAttribute("aria-activedescendant", selected.id);
  } else $("commandSearch").removeAttribute("aria-activedescendant");
}

function openCommandPalette() {
  commandSelection = 0;
  $("commandSearch").value = "";
  $("commandSearch").setAttribute("aria-expanded", "true");
  $("commandOverlay").classList.add("show");
  renderCommands();
  requestAnimationFrame(() => $("commandSearch").focus());
}

function closeCommandPalette() {
  $("commandOverlay").classList.remove("show");
  $("commandSearch").setAttribute("aria-expanded", "false");
  $("commandSearch").removeAttribute("aria-activedescendant");
}

function runSelectedCommand(index = commandSelection) {
  const command = visibleCommands[index];
  if (!command) return;
  closeCommandPalette();
  command.run();
}

function renderHints(h) {
  $("empty").style.display = "none";
  syncEmptyLayout();
  const first = (h.answers || [])[0];
  latestAnswer = first == null ? "" : (typeof first === "object" ? (first.answer || "") : String(first));
  $("answers").innerHTML = (h.answers || []).map(a => {
    const value = typeof a === "object" && a !== null ? (a.answer || "") : String(a);
    const why = typeof a === "object" && a !== null ? (a.why || "") : "";
    return `<div class="answer-card">${esc(value)}${why ? `<span class="answer-why">Опора: ${esc(why)}</span>` : ""}<span class="hint-actions"><button class="hint-pin" data-text="${esc(value)}" data-label="Ответ" title="закрепить сверху" aria-label="Закрепить ответ сверху"><svg class="ui-icon" aria-hidden="true"><use href="#icon-pin"/></svg></button><button class="hint-focus" data-text="${esc(value)}" title="показать крупно" aria-label="Показать ответ крупно"><svg class="ui-icon" aria-hidden="true"><use href="#icon-expand"/></svg></button></span></div>`;
  }).join("");
  $("tags").innerHTML = "";
  (h.tags || []).forEach(t => {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "tag"; el.textContent = t;
    el.setAttribute("aria-pressed", "false");
    el.onclick = () => {
      el.classList.toggle("sel");
      el.setAttribute("aria-pressed", String(el.classList.contains("sel")));
      send({type: "tag", tag: t});
    };
    $("tags").appendChild(el);
  });
  $("questions").innerHTML = (h.questions || []).map(q => {
    const text = typeof q === "object" && q !== null ? (q.q || "") : String(q);
    const why = typeof q === "object" && q !== null ? (q.why || "") : "";
    const play = currentMeetingType === "кандидат" ? ""
      : `<button class="speak-q hint-speak" data-text="${esc(text)}" title="задать вопрос голосом" aria-label="Задать вопрос голосом"><svg class="ui-icon" aria-hidden="true"><use href="#icon-play"/></svg></button>`;
    return `<div class="q">${esc(text)}${why ? `<span class="qw">— ${esc(why)}</span>` : ""}<span class="hint-actions">${play}<button class="hint-pin" data-text="${esc(text)}" data-label="Вопрос" title="закрепить сверху" aria-label="Закрепить вопрос сверху"><svg class="ui-icon" aria-hidden="true"><use href="#icon-pin"/></svg></button></span></div>`;
  }).join("");
  document.querySelectorAll(".hint-speak").forEach(btn => btn.onclick = () =>
    playQuestion(btn.dataset.text, btn));
  document.querySelectorAll(".hint-pin").forEach(btn => btn.onclick = () =>
    setPinnedHint(btn.dataset.text, btn.dataset.label));
  document.querySelectorAll(".hint-focus").forEach(btn => btn.onclick = () =>
    openFocusAnswer(btn.dataset.text));
  $("flags").innerHTML = (h.flags || []).map(f =>
    `<div class="f"><span class="nav-code">RISK</span> ${esc(f)}</div>`).join("");
  $("uncovered").innerHTML = (h.uncovered || []).length
    ? "Уточнить: " + h.uncovered.slice(0, 3).map(esc).join(" · ")
      + (h.uncovered.length > 3 ? `<details class="hint-more"><summary>ещё ${h.uncovered.length - 3}</summary>${h.uncovered.slice(3).map(esc).join(" · ")}</details>` : "") : "";
}

function mergeFeedHistory(previous, incoming) {
  const max = Math.min(previous.length, incoming.length);
  let overlap = max;
  while (overlap > 0) {
    if (previous.slice(-overlap).every((line, index) => line === incoming[index])) break;
    overlap--;
  }
  return previous.concat(incoming.slice(overlap)).slice(-2000);
}

function feedEntries(lines) {
  const entries = [];
  (Array.isArray(lines) ? lines : []).forEach(line => {
    const match = line.match(/^- (\d\d:\d\d:\d\d) \*\*\[(.+?)\]\*\* (.*)$/);
    if (!match) return;
    const previous = entries.at(-1);
    if (previous && previous.speaker === match[2]) {
      previous.text += ` ${match[3]}`;
      previous.fragments += 1;
      previous.lastTime = match[1];
      return;
    }
    entries.push({
      time: match[1], lastTime: match[1], speaker: match[2],
      text: match[3], fragments: 1,
    });
  });
  return entries;
}

function ruCount(value, one, few, many) {
  const number = Math.abs(Number(value)) % 100;
  const last = number % 10;
  if (number > 10 && number < 20) return many;
  if (last > 1 && last < 5) return few;
  return last === 1 ? one : many;
}

function renderFeed(lines, info = {}) {
  const session = String(info.session || $("selSession").value || "");
  if (feedHistorySession !== session) {
    feedHistorySession = session; feedHistoryLines = []; feedExpanded = false;
    announcedFeedSession = session; announcedFeedTotal = Number(info.total || 0);
  }
  const incoming = Array.isArray(lines) ? lines : [];
  feedHistoryLines = feedExpanded && feedHistoryLines.length > incoming.length
    ? mergeFeedHistory(feedHistoryLines, incoming) : incoming;
  $("feed").innerHTML = feedEntries(feedHistoryLines).map(entry => {
    const cls = entry.speaker === "Я" ? "me" : "them";
    const label = speakerLabels[entry.speaker] || entry.speaker;
    const source = entry.speaker === "Я" ? "канал микрофона" : "канал системного звука";
    const tooltip=entry.fragments>1?source+' · фрагментов STT: {count}':source;
    const interval = entry.lastTime !== entry.time ? `–${entry.lastTime}` : "";
    return `<div class="line"><span class="t" ${meetingAttrs('title',tooltip,{count:entry.fragments})}>${entry.time}${interval}</span><b class="${cls}" ${meetingAttrs('title',tooltip,{count:entry.fragments})}>[${esc(label)}]</b> ${esc(entry.text)}</div>`;
  }).join("");
  const total = Number(info.total ?? feedHistoryLines.length);
  const shown = feedHistoryLines.length;
  currentHasTranscript = total > 0;
  if(!total)meetingLabel($("feedCount"),'История · реплик пока нет');
  else meetingLabel($("feedCount"),'{messages}',()=>({messages:meetingUi('История · ')+total+' '+
    (window.BlateroI18n?.language==='en'?meetingUi(total===1?'реплика':'реплики'):ruCount(total,'реплика','реплики','реплик'))+
    (shown<total?meetingUi(' · показано {count}',{count:shown}):'')}));
  $("feedMore").hidden = !info.truncated || feedExpanded;
  $("feedFull").hidden = !session || !total;
  $("feedFull").href = session
    ? `/api/sessions/${encodeURIComponent(session)}/transcript` : "";
  $("feed").scrollTop = $("feed").scrollHeight;
  if (announcedFeedSession === session && total > announcedFeedTotal && feedHistoryLines.length) {
    const latest = feedEntries(feedHistoryLines).at(-1);
    const label = speakerLabels[latest.speaker] || latest.speaker;
    $("transcriptAnnouncement").textContent = `${label}: ${latest.text}`;
  }
  announcedFeedSession = session;
  announcedFeedTotal = total;
  renderWorkflowNext();
}

const esc = s => s.replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

$("selSession").onchange = e => send({type: "session", dir: e.target.value});
document.querySelectorAll("#contourSwitch [data-contour]").forEach(button => {
  button.onclick = () => {
    if (button.dataset.contour !== currentContour)
      send({type:"contour", value:button.dataset.contour});
  };
});
document.querySelectorAll("#setupContourSwitch [data-contour]").forEach(button => {
  button.onclick = () => {
    setupContour = button.dataset.contour;
    renderContourSwitches();
  };
});
$("feedMore").onclick = () => {
  feedExpanded = true;
  $("feedMore").hidden = true;
  $("feedCount").textContent += " · загружаю…";
  send({type:"transcript_history"});
};
$("feedExpand").onclick = () => {
  setTranscriptTall(!document.querySelector("footer").classList.contains("feed-expanded"));
};
$("feedVisibility").onclick = () =>
  setTranscriptVisible(document.body.classList.contains("feed-collapsed"));
$("selMType").onchange = e => send({type: "meta", key: "type", value: e.target.value});
$("selContour").onchange = e => {
  const target = e.target.value;
  const label = target === "test" ? "тестовый" : "рабочий";
  if (!confirm(`Переместить текущую встречу в ${label} контур? Она исчезнет из текущего списка и появится в другом.`)) {
    e.target.value = currentContour; return;
  }
  send({type:"meta", key:"contour", value:target});
};
$("selDur").onchange = e => send({type: "meta", key: "duration",
                                  value: e.target.value ? parseInt(e.target.value) : ""});
$("inpName").onchange = e => send({type: "meta", key: "name", value: e.target.value.trim()});
$("inpClient").onchange = e => send({type: "meta", key: "client_name", value: e.target.value.trim()});
$("inpProject").onchange = e => send({type: "meta", key: "project_name", value: e.target.value.trim()});
$("inpEmulationRole").onchange = e => send({type: "meta", key: "emulation_role", value: e.target.value.trim()});
$("inpSpeakerMe").onchange = e => send({type: "meta", key: "speaker_me", value: e.target.value.trim()});
$("inpSpeakerGuest").onchange = e => send({type: "meta", key: "speaker_guest", value: e.target.value.trim()});
$("inpWorkspace").onchange = e => send({type:"meta", key:"workspace_path", value:e.target.value.trim()});
$("newMeet").onclick = () => { if (closeSettingsOverlay()) openSetupWizard(); };
let transcriptImportContent = "";
function updateTranscriptImportAdapter() {
  const selected = transcriptAdapters.find(
    item => item.value === $("transcriptImportAdapter").value);
  if (!selected) return;
  studioLabel($("transcriptImportHelp"),selected.help);
  $("transcriptImportFile").accept = (selected.extensions || []).join(",");
}
$("transcriptImportAdapter").onchange = () => {
  updateTranscriptImportAdapter();
  $("transcriptImportFile").value = "";
  transcriptImportContent = "";
  $("transcriptImportStatus").className = "workspace-status";
  studioLabel($("transcriptImportStatus"),"Выберите файл для этого источника.");
  $("transcriptImportStart").disabled = true;
};
$("importTranscript").onclick = () => {
  if (!closeSettingsOverlay()) return;
  $("importOverlay").classList.add("show");
};
$("transcriptImportFile").onchange = async event => {
  const file = event.target.files && event.target.files[0];
  transcriptImportContent = "";
  if (!file) {
    studioLabel($("transcriptImportStatus"),"Файл ещё не выбран.");
    $("transcriptImportStart").disabled = true; return;
  }
  if (file.size > 2 * 1024 * 1024) {
    $("transcriptImportStatus").className = "workspace-status error";
    studioLabel($("transcriptImportStatus"),"Файл больше 2 МБ.");
    $("transcriptImportStart").disabled = true; return;
  }
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 32768)
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
  transcriptImportContent = btoa(binary);
  $("transcriptImportStatus").className = "workspace-status ready";
  studioLabel($("transcriptImportStatus"),()=>({source:"{value}",values:{value:studioUi("{p0} · {p1} КБ",{p0:file.name,p1:(file.size / 1024).toFixed(1)})}}));
  $("transcriptImportStart").disabled = !transcriptImportContent;
};
$("transcriptImportStart").onclick = () => {
  const file = $("transcriptImportFile").files[0];
  if (!file || !transcriptImportContent) return;
  $("transcriptImportStart").disabled = true;
  $("transcriptImportStatus").className = "workspace-status scanning";
  studioLabel($("transcriptImportStatus"),"Проверяю и добавляю новый сегмент…");
  send({type:"transcript_import", name:file.name, content:transcriptImportContent,
        encoding:"base64", adapter:$("transcriptImportAdapter").value,
        my_speaker:$("transcriptMySpeaker").value.trim()});
};
$("setupBtn").onclick = () => openSetupWizard();
$("trainingBtn").onclick = () => {
  if (!closeSettingsOverlay()) return;
  if (currentMeetingType === "тренировка") {
    $("trainingPanel").scrollIntoView({behavior:"smooth", block:"start"});
    return;
  }
  openSetupWizard("тренировка");
};
$("trainingPersonalTab").onclick = () => selectTrainingMode("personal");
$("trainingInterviewerTab").onclick = () => selectTrainingMode("interviewer");
$("trainingSceneTab").onclick = () => selectTrainingMode("ai");
$("trainingSpeechTab").onclick = () => selectTrainingMode("speech");
[$("trainingPersonalTab"), $("trainingInterviewerTab"), $("trainingSceneTab"), $("trainingSpeechTab")].forEach((tab, index, tabs) => {
  tab.onkeydown = event => {
    let target = null;
    if (["ArrowLeft", "ArrowUp"].includes(event.key)) target = tabs[(index - 1 + tabs.length) % tabs.length];
    else if (["ArrowRight", "ArrowDown"].includes(event.key)) target = tabs[(index + 1) % tabs.length];
    else if (event.key === "Home") target = tabs[0];
    else if (event.key === "End") target = tabs.at(-1);
    if (!target) return;
    event.preventDefault(); target.click(); target.focus();
  };
});
$("trainingPack").onchange = () => applyCompetencyPack(
  "trainingPack", "trainingRole", "trainingPackHint");
$("scenePack").onchange = () => applyCompetencyPack(
  "scenePack", "sceneRole", "scenePackHint");
$("trainingPrepare").onclick = () => {
  const role = $("trainingRole").value.trim();
  const packId = $("trainingPack").value;
  if (!role && !packId) {
    studioLabel($("trainingStatus"),"Укажите целевую роль или профессию.");
    $("trainingStatus").style.color = "var(--red)";
    $("trainingRole").focus(); return;
  }
  send({type:"training_prepare", role, source:$("trainingSource").value.trim(),
        question_count:parseInt($("trainingCount").value),
        difficulty:$("trainingDifficulty").value,
        adaptive:$("trainingAdaptive").checked, pack_id:packId});
};
$("trainingStart").onclick = () => {
  if (recLive) { send({type:"training_start"}); return; }
  trainingStartPending = true;
  openStartOverlay("тренировка");
};
$("trainingSpeak").onclick = () => {
  if (trainingState && trainingState.question)
    playQuestion(trainingState.question.question, $("trainingSpeak"));
};
$("trainingHintBtn").onclick = () => send({type:"training_hint"});
$("trainingAnswerBtn").onclick = () => {
  send({type:"training_answer", answer:$("trainingAnswer").value.trim(),
    attempt_id:trainingState.attempt_id,question_id:trainingState.question?.id,request_id:studioSubmission('trainingAnswer')});
};
$("trainingFinish").onclick = () => {
  if (!confirm(studioUi("Завершить тренировку, остановить запись и сформировать отчёт?"))) return;
  send({type:"training_finish", answer:$("trainingAnswer").value.trim(),
    attempt_id:trainingState.attempt_id,question_id:trainingState.question?.id,request_id:studioSubmission('trainingAnswer')});
};
$("trainingReset").onclick = () => {
  if (confirm(studioUi("Сбросить ответы и оценки этой попытки? Подготовленные вопросы и история завершённых попыток останутся.")))
    send({type:"training_reset"});
};
$("trainingProgressReset").onclick = () => {
  if (confirm(studioUi("Удалить всю накопленную карту компетенций для этой роли? Текущая попытка и подготовленные вопросы останутся.")))
    send({type:"training_progress_reset"});
};
$("scenePrepare").onclick = () => {
  const role = $("sceneRole").value.trim();
  const packId = $("scenePack").value;
  if (!role && !packId) {
    studioLabel($("trainingStatus"),"Укажите целевую роль сценки.");
    $("trainingStatus").style.color = "var(--red)";
    $("sceneRole").focus(); return;
  }
  send({type:"scene_prepare", role, source:$("sceneSource").value.trim(),
        rounds:parseInt($("sceneRounds").value),
        difficulty:$("sceneDifficulty").value, style:$("sceneStyle").value,
        interviewer_voice:$("sceneInterviewerVoice").value,
        candidate_voice:$("sceneCandidateVoice").value, pack_id:packId,
        coach_audience:$("sceneCoachAudience").value,
        takeover:trainingStudioMode === "interviewer" ? "interviewer" : "observer",
        moods:window.BlateroTrainingAvatars?.moods() || {}});
};
$("sceneStart").onclick = () => {
  if (sceneState && sceneState.takeover === "interviewer" && !recLive) {
    sceneStartPending = sceneState.run_id || false;
    openStartOverlay("тренировка");
    return;
  }
  send({type:"scene_start"});
};
function saveSceneControl() {
  send({type:"scene_control", control:$("sceneControl").value,
        coach_audience:$("sceneCoachAudience").value,
        takeover:$("sceneTakeover").value, moods:window.BlateroTrainingAvatars?.moods() || {}});
}
$("sceneControl").onchange = saveSceneControl;
$("sceneTakeover").onchange = saveSceneControl;
$("sceneCoachAudience").onchange = () => {if(sceneState?.prepared)saveSceneControl();};
$("sceneNext").onclick = () => {
  const turn = sceneState && sceneState.turn;
  send({type:"scene_next", run_id:sceneState?.run_id, after_turn_id:turn ? turn.id : "",
        request_id:sceneState?.needs_takeover?studioSubmission('sceneTakeoverText'):undefined,
        text:sceneState && sceneState.needs_takeover
          ? $("sceneTakeoverText").value.trim() : ""});
};
$("sceneSpeak").onclick = () => {
  if (sceneState && sceneState.turn) playSceneTurn(sceneState.turn, false);
};
$("sceneCoach").onclick = () => send({type:'scene_hint'});
$("sceneFinish").onclick = () => {
  if (confirm(studioUi("Остановить сценку и попросить независимого тренера разобрать обе стороны?"))) {
    stopQuestionAudio();
    send({type:"scene_finish"});
  }
};
$("sceneReset").onclick = () => {
  if (confirm(studioUi("Начать новую попытку? Предыдущие реплики, разбор и аудио сохранятся в истории; роли останутся."))) {
    stopQuestionAudio();
    send({type:"scene_reset"});
  }
};
$("memoryExtract").onclick = () => send({type:"memory_extract"});
$("memoryAccept").onclick = () => {
  const ids = [...document.querySelectorAll("[data-memory-draft]:checked")]
    .map(input => input.dataset.memoryDraft);
  if (!ids.length) { studioLabel($("memoryStatus"),"Выберите хотя бы один пункт."); return; }
  send({type:"memory_accept", ids, review_context:{...memoryState.review,request_id:crypto.randomUUID()}});
};
$("memoryDiscard").onclick = () => {
  if (confirm(studioUi("Отклонить весь черновик? Подтверждённая память не изменится.")))
    send({type:"memory_discard"});
};
$("memoryAdd").onclick = () => {
  const text = $("memoryAddText").value.trim();
  if (!text) { studioLabel($("memoryStatus"),"Введите текст записи."); return; }
  const values=memoryManualFields.map(id=>$(id).value);
  const scope=$("memoryAddScope").value, kind=$("memoryAddKind").value;
  const signature=JSON.stringify([scope,kind,values]);
  const id=memoryManualPending?.signature===signature?memoryManualPending.id:crypto.randomUUID();
  if (send({type:"memory_add", request_id:id, scope, kind, text,
        owner:$("memoryAddOwner").value.trim(), due:$("memoryAddDue").value.trim()}))
    memoryManualPending={id,values,signature};
};
$("memoryLinkApply").onclick = () => {
  const sourceId = $("memoryLinkSource").value;
  const selected = (memoryState.project_profiles || []).find(item => item.id === sourceId);
  if (!selected) return;
  if (confirm(studioUi('Связать текущую папку с памятью проекта «{label}»?',{label:selected.label})))
    send({type:"memory_link_project", source_id:sourceId});
};
$("setupClose").onclick = () => $("setupOverlay").classList.remove("show");
$("setupBack").onclick = () => { if (setupStep > 1) { setupStep--; renderSetupStep(true); } };
$("setupNext").onclick = () => {
  if (!setupStepValid()) return;
  setupStep = Math.min(4, setupStep + 1); renderSetupStep(true);
};
function openSetupSettings(sectionId) {
  $("setupOverlay").inert = true;
  $("setupOverlay").setAttribute("aria-hidden", "true");
  openSettingsOverlay(document.activeElement);
  window.BlateroSettings?.select(sectionId);
}
$("setupConfigureAi").onclick = () => openSetupSettings("settingsAi");
$("setupConfigurePrivacy").onclick = () => openSetupSettings("settingsPrivacy");
$("setupWithoutAi").onclick = () => {
  $("setupInitialize").checked = false;
  renderSetupStep(false,true);
  $("setupCreate").focus();
};
function browseWorkspace(target) {
  const setupTarget = target === "setup";
  const path = $(setupTarget ? "setupWorkspace" : "inpWorkspace").value.trim();
  const statusId = setupTarget ? "setupProbeStatus" : "workspaceStatus";
  const browseId = setupTarget ? "setupBrowse" : "workspaceBrowse";
  const probeId = setupTarget ? "setupProbe" : "workspaceProbe";
  $(browseId).disabled = true;
  $(probeId).disabled = true;
  renderWorkspaceStatus(statusId, {state:"scanning", message:wizardUi("Открываю системный диалог выбора папки…")});
  if (setupTarget) setupProbeRequest = {id:crypto.randomUUID(),path,kind:'browse'};
  send({type:"workspace_browse", target, path,...(setupTarget ? {request_id:setupProbeRequest.id} : {})});
}
$("setupBrowse").onclick = () => browseWorkspace("setup");
$("setupProbe").onclick = () => {
  const path = $("setupWorkspace").value.trim();
  if (!path) {
    setupProbeResult = null;
    renderWorkspaceStatus("setupProbeStatus", {state:"insufficient", message:wizardUi("Папка не указана — ИИ использует только цель встречи и общий сценарий.")});
    return;
  }
  $("setupProbe").disabled = true;
  setupProbeRequest = {id:crypto.randomUUID(),path,kind:'probe'};
  renderWorkspaceStatus("setupProbeStatus", {state:"scanning", message:wizardUi("Локально проверяю состав папки…")});
  send({type:"workspace_probe", path:path, target:"setup", request_id:setupProbeRequest.id});
};
$("setupWorkspace").oninput = () => {
  setupProbeResult = null; setupProbeRequest = null;
  $('setupProbe').disabled = false; $('setupBrowse').disabled = false;
  renderWorkspaceStatus('setupProbeStatus',{state:'not_configured',message:'Путь изменён. Проверьте папку снова.'});
};
$("setupCreate").onclick = () => {
  renderSetupSummary();
  if ($("setupCreate").disabled) return;
  const path = $("setupWorkspace").value.trim();
  send({type:"new_meeting", name:$("setupName").value.trim(), mtype:setupMode,
        contour:setupContour,
        duration:$("setupDuration").value || null, brief:$("setupBrief").value.trim(),
        client_name:$("setupClient").value.trim(), project_name:$("setupProject").value.trim(),
        workspace_path:path, initialize_workspace:!!path && $("setupInitialize").checked});
  $("setupOverlay").classList.remove("show");
};
$("workspaceBrowse").onclick = () => browseWorkspace("settings");
$("workspaceProbe").onclick = () => {
  const path = $("inpWorkspace").value.trim();
  if (!path) { renderWorkspaceStatus("workspaceStatus", {state:"error", message:"Укажите абсолютный путь к рабочей папке."}); return; }
  $("workspaceProbe").disabled = true;
  renderWorkspaceStatus("workspaceStatus", {state:"scanning", message:wizardUi("Локально проверяю состав папки…")});
  send({type:"workspace_probe", path:path, target:"settings",
    session:currentInit.current_dir,generation:currentInit.session_generation});
};
$("workspaceInit").onclick = () => {
  const path = $("inpWorkspace").value.trim();
  if (!path) { renderWorkspaceStatus("workspaceStatus", {state:"error", message:"Сначала укажите рабочую папку проекта."}); return; }
  send({type:"meta", key:"workspace_path", value:path});
  send({type:"workspace_init"});
};
function workspacePrivacyMessage(type) {
  if (workspacePrivacyReview.live_batch) type = type.replace("workspace_review_", "live_material_");
  return {type, session:workspacePrivacyReview.session, generation:workspacePrivacyReview.generation,
    batch:workspacePrivacyReview.live_batch,
    id:workspacePrivacyReview.review.id};
}
function privacyPreviewDirty() {
  if ($("workspaceImagesAck")) $("workspaceImagesAck").checked = false;
  if (workspacePrivacyReview) workspacePrivacyReview.dirty = true;
  $("workspacePrivacyApprove").disabled = true;
  studioLabel($("workspacePrivacyStatus"),"Выбор изменён. Нажмите «Перепроверить локально» и просмотрите новый текст.");
}
function showWorkspacePrivacy(message) {
  if (currentInit && message.session !== currentInit.current_dir) return;
  if (message.live_batch) window.dispatchEvent(new CustomEvent("blatero-material-review"));
  const overlay = $("workspacePrivacyOverlay");
  if (!overlay) { alert(studioUi("Для просмотра проверки ПД перезапустите Blatero и обновите страницу.")); return; }
  workspacePrivacyReview = message;
  const review = message.review;
  if(review.message_code==='local_review_complete')studioLabel($("workspacePrivacyStatus"),'Проверка выполнена локально. Автоматическое обнаружение может ошибаться. Просмотрите отправляемый текст.');
  else studioValue($("workspacePrivacyStatus"),review.message);
  studioLabel($("workspacePrivacyDestination"),()=>({source:"{value}",values:{value:studioUi("Получатель: {p0} · модель: {p1} · {p2}",{p0:review.destination,p1:review.destination==='Codex'?studioUi('определяется Codex CLI'):review.model,p2:studioUi(review.detector)})}}));
  $("workspacePrivacyFiles").replaceChildren();
  for (const item of review.files) {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = !review.excluded.includes(item.path);
    checkbox.dataset.path = item.path;
    checkbox.onchange = privacyPreviewDirty;
    label.append(checkbox, document.createTextNode(item.path));
    $("workspacePrivacyFiles").append(label);
  }
  $("workspacePrivacyCustom").value = review.custom.join("\n");
  $("workspacePrivacyCustom").oninput = privacyPreviewDirty;
  studioLabel($("workspacePrivacyCount"),()=>({source:"{value}",values:{value:studioUi("Подозрительных фрагментов: {p0}. Они скрыты в отправляемом тексте.",{p0:review.findings.length})}}));
  const chars = Array.from(review.source);
  let cursor = 0, highlighted = "";
  for (const item of review.findings) {
    highlighted += esc(chars.slice(cursor, item.start).join(""));
    highlighted += `<mark title="${esc(item.replacement)}">${esc(chars.slice(item.start, item.end).join(""))}</mark>`;
    cursor = item.end;
  }
  $("workspacePrivacySource").innerHTML = highlighted + esc(chars.slice(cursor).join(""));
  studioValue($("workspacePrivacySystem"),review.system);
  studioValue($("workspacePrivacyUser"),review.user);
  showWorkspaceVisuals(review);
  updateWorkspacePrivacyApproval();
  $("workspacePrivacyRecheck").disabled = false;
  overlay.classList.add("show");
  $("workspacePrivacyTitle").focus();
}
if ($("workspacePrivacyRecheck")) $("workspacePrivacyRecheck").onclick = () => {
  if (!workspacePrivacyReview) return;
  const excluded = [...$("workspacePrivacyFiles").querySelectorAll("input:not(:checked)")].map(x => x.dataset.path);
  const custom = $("workspacePrivacyCustom").value.split("\n").map(x => x.trim()).filter(Boolean);
  const visual_selection = [...workspaceVisualOptions.values()].filter(x => x.selected)
    .map(({path, masks}) => ({path, masks}));
  send({...workspacePrivacyMessage("workspace_review_update"), excluded, custom, visual_selection});
  $("workspacePrivacyRecheck").disabled = true;
  $("workspacePrivacyApprove").disabled = true;
  studioLabel($("workspacePrivacyStatus"),"Повторная локальная проверка… Ничего не отправляется в облако.");
};
if ($("workspacePrivacyApprove")) $("workspacePrivacyApprove").onclick = () => {
  if (!workspacePrivacyReview) return;
  send({...workspacePrivacyMessage("workspace_review_approve"), images_ack:$("workspaceImagesAck")?.checked === true});
  $("workspacePrivacyApprove").disabled = true;
  $("workspacePrivacyRecheck").disabled = true;
  studioLabel($("workspacePrivacyStatus"),"Проверяю, что материалы не изменились; затем отправлю подтверждённый текст…");
};
if ($("workspacePrivacyClose")) $("workspacePrivacyClose").onclick = () => {
  if (workspacePrivacyReview) send(workspacePrivacyMessage("workspace_review_cancel"));
  workspacePrivacyReview = null;
  $("workspacePrivacyOverlay").classList.remove("show");
};

function updateWorkspacePrivacyApproval() {
  if (!workspacePrivacyReview) return;
  const selected = (workspacePrivacyReview.review.visuals || []).some(x => x.selected);
  studioLabel($("workspacePrivacyApprove"),()=>({source:"{value}",values:{value:selected
    ? studioUi("подтверждаю текст и картинки — отправить и подготовить")
    : studioUi("подтверждаю текст — отправить и подготовить")}}));
  $("workspacePrivacyApprove").disabled = !!workspacePrivacyReview.dirty ||
    workspacePrivacyReview.review.can_approve === false || (selected && !$("workspaceImagesAck")?.checked);
}
function showWorkspaceVisuals(review) {
  const section = $("workspaceVisualSection"), container = $("workspaceVisuals");
  if (!section || !container) return;
  workspaceVisualOptions = new Map();
  container.replaceChildren();
  section.hidden = !(review.visuals || []).length;
  $("workspaceImagesAck").checked = false;
  $("workspaceImagesAck").onchange = updateWorkspacePrivacyApproval;
  studioLabel($("workspaceVisualNotice"),()=>({source:"{value}",values:{value:review.vision_supported
    ? studioUi("Для анализа нужна модель с поддержкой изображений. Используется модель подготовки, указанная выше. Изображения могут увеличить стоимость запроса.")
    : studioUi("Текущий провайдер здесь принимает только текст. Для картинок выберите в настройках Codex, OpenRouter, OpenAI, Anthropic или совместимый API и модель со зрением. Текст и структура схем доступны и без этого.")}}));
  for (const row of review.visuals || []) {
    const card = document.createElement("article"); card.className = "privacy-visual-card";
    const choice = document.createElement("label"), box = document.createElement("input");
    box.type = "checkbox"; box.checked = !!row.selected; box.disabled = !review.vision_supported || !!row.error;
    box.dataset.path = row.path;
    choice.append(box, document.createTextNode(studioUi(" Отправить картинку: ") + row.path)); card.append(choice);
    const option = {path:row.path, selected:!!row.selected, masks:structuredClone(row.masks || [])};
    workspaceVisualOptions.set(row.path, option);
    box.onchange = () => { option.selected = box.checked; privacyPreviewDirty(); };
    if (row.error) {
      const error = document.createElement("p"); studioValue(error,row.error); card.append(error);
    } else {
      const details = document.createElement("details"), summary = document.createElement("summary");
      studioLabel(summary,"Просмотреть и скрыть области"); details.open = !!row.selected; details.append(summary);
      const canvas = document.createElement("canvas"); canvas.setAttribute("aria-label", studioUi("Изображение ") + row.path);
      const image = new Image(); const ctx = canvas.getContext("2d");
      image.onload = () => { canvas.width = image.naturalWidth; canvas.height = image.naturalHeight; ctx.drawImage(image, 0, 0); };
      // Only server-generated PNG data URLs; never render source SVG/HTML.
      if (row.data_url.startsWith("data:image/png;base64,")) image.src = row.data_url;
      let start = null;
      const point = event => { const r = canvas.getBoundingClientRect(); return [
        Math.max(0, Math.min(1, (event.clientX-r.left)/r.width)),
        Math.max(0, Math.min(1, (event.clientY-r.top)/r.height))]; };
      const addMask = mask => {
        if (option.masks.length >= 40) { alert(studioUi("Можно скрыть до 40 областей на изображении.")); return; }
        option.masks.push(mask); ctx.fillStyle = "black";
        ctx.fillRect(mask[0]*canvas.width, mask[1]*canvas.height, mask[2]*canvas.width, mask[3]*canvas.height);
        privacyPreviewDirty();
      };
      canvas.onpointerdown = event => { start = point(event); canvas.setPointerCapture(event.pointerId); };
      canvas.onpointerup = event => {
        if (!start) return;
        const end = point(event), mask = [Math.min(start[0],end[0]), Math.min(start[1],end[1]), Math.abs(end[0]-start[0]), Math.abs(end[1]-start[1])];
        start = null;
        if (mask[2] > 0.001 && mask[3] > 0.001) addMask(mask);
      };
      canvas.onpointercancel = () => { start = null; };
      details.append(canvas);
      const reset = document.createElement("button"); studioLabel(reset,"сбросить области и перепроверить");
      reset.onclick = () => { option.masks = []; privacyPreviewDirty(); $("workspacePrivacyRecheck").click(); };
      const manual = document.createElement("details"), manualTitle = document.createElement("summary");
      studioLabel(manualTitle,"Задать область с клавиатуры (проценты)"); manual.append(manualTitle);
      const inputs = [studioUi("Слева"), studioUi("Сверху"), studioUi("Ширина"), studioUi("Высота")].map((title, i) => {
        const label = document.createElement("label"), input = document.createElement("input");
        input.type = "number"; input.min = "0"; input.max = "100"; input.value = i < 2 ? "0" : "20";
        label.append(document.createTextNode(title + " "), input); manual.append(label); return input;
      });
      const add = document.createElement("button"); studioLabel(add,"закрасить область");
      add.onclick = () => { const m = inputs.map(x => Number(x.value)/100);
        if (m.some(x => !Number.isFinite(x) || x < 0 || x > 1) || m[2] <= 0 || m[3] <= 0 || m[0]+m[2]>1 || m[1]+m[3]>1) {
          alert(studioUi("Область должна находиться внутри картинки.")); return;
        } addMask(m);
      };
      manual.append(add); details.append(reset, manual); card.append(details);
    }
    container.append(card);
  }
}
$("clearResults").onclick = () => {
  const label = $("sess").textContent || "текущей встречи";
  const contour = currentContour === "test" ? "тестовой" : "рабочей";
  if (!confirm(`Очистить результат ${contour} встречи «${label}»?

Будут безвозвратно удалены транскрипт, аудио, подсказки, отчёт и отметки заданных вопросов. Резюме, досье и сценарий останутся.`)) return;
  send({type:"clear_results"});
  closeSettingsOverlay();
};
$("archiveBtn").onclick = () => { send({type: "archive"}); $("archOverlay").classList.add("show"); };
$("lifecycleOpen").onclick = () => openSessionLifecycle($("selSession").value || "");
$("lifecycleClose").onclick = () => $("lifecycleOverlay").classList.remove("show");
$("lifecycleExport").onclick = () => {
  const password = $("lifecyclePassword").value;
  if (!lifecycleSession) { studioLabel($("lifecycleState"),"Выберите встречу в архиве."); return; }
  if (password.length < 10) { studioLabel($("lifecycleState"),"Парольная фраза короче 10 символов."); $("lifecyclePassword").focus(); return; }
  send({type:"session_export",session:lifecycleSession,password});
};
$("lifecycleImport").onclick = () => {
  const password = $("lifecyclePassword").value;
  if (password.length < 10) { studioLabel($("lifecycleState"),"Введите парольную фразу пакета."); $("lifecyclePassword").focus(); return; }
  send({type:"session_import",password});
};
$("lifecycleOpenFolder").onclick = () => send({type:"lifecycle_open_packages"});
$("lifecyclePurgeChecks").onchange = event => {
  const all = $("lifecyclePurgeChecks").querySelector('input[value="all"]');
  if (event.target === all && all.checked)
    $("lifecyclePurgeChecks").querySelectorAll('input:not([value="all"])').forEach(input => input.checked = false);
  else if (event.target !== all && event.target.checked) all.checked = false;
  lifecyclePurgePreview = null;
  $("lifecyclePurgeApply").disabled = true;
  studioLabel($("lifecyclePurgeResult"),"Состав изменён — рассчитайте заново.");
};
$("lifecyclePurgePreview").onclick = () => {
  const categories = purgeCategories();
  if (!lifecycleSession || !categories.length) {
    studioLabel($("lifecyclePurgeResult"),"Выберите встречу и хотя бы одну категорию."); return;
  }
  send({type:"session_purge_preview",session:lifecycleSession,categories});
};
$("lifecyclePurgeApply").onclick = () => {
  if (!lifecyclePurgePreview || !lifecyclePurgePreview.files) return;
  const typed = prompt(studioUi('Будут безвозвратно удалены {count} файлов ({size}).\n\nВведите имя папки сессии для подтверждения:\n{session}',{count:lifecyclePurgePreview.files,size:modelSize(lifecyclePurgePreview.bytes),session:lifecycleSession}));
  if (typed !== lifecycleSession) { studioLabel($("lifecyclePurgeResult"),"Удаление отменено: имя не совпало."); return; }
  send({type:"session_purge_apply",session:lifecycleSession,
        categories:lifecyclePurgePreview.categories,confirmation:`DELETE:${lifecycleSession}`});
  lifecyclePurgePreview = null; $("lifecyclePurgeApply").disabled = true;
};
$("retentionSave").onclick = () => send({type:"retention_save",policies:retentionValues()});
$("retentionApply").onclick = () => {
  const retention = lifecycleState.retention || {};
  const typed = prompt(`Очередь: ${Number(retention.sessions)||0} встреч, ${Number(retention.files)||0} файлов, ${lifecycleBytes(retention.bytes)}.\n\nДля применения введите: APPLY RETENTION`);
  if (typed !== "APPLY RETENTION") return;
  send({type:"retention_apply",confirmation:typed});
};
$("analysisBtn").onclick = openAnalysisHub;
$("analysisClose").onclick = () => $("analysisOverlay").classList.remove("show");
$("analysisRefresh").onclick = () => send({type:"archive"});
$("analysisAudio").onclick = () => {
  $("analysisOverlay").classList.remove("show");
  $("audioOverlay").classList.add("show");
};
$("analysisImport").onclick = () => {
  $("analysisOverlay").classList.remove("show");
  $("importTranscript").click();
};
$("analysisSpeakerBank").onclick = () => {
  $("analysisOverlay").classList.remove("show");
  openSpeakerBank();
};
$("analysisReport").onclick = () => {
  $("analysisOverlay").classList.remove("show");
  $("report").click();
};
$("analysisBenchmark").onclick = openQualityLab;
$("analysisGuardCalibration").onclick = openGuardCalibration;
$("analysisArchive").onclick = () => {
  $("analysisOverlay").classList.remove("show");
  $("archiveBtn").click();
};
$("qualityRefresh").onclick = loadQualityCatalog;
$("qualityFilter").onchange = renderQualityCatalog;
$("qualityEditorBack").onclick = () => {
  if (closeQualityEditor()) loadQualityCatalog();
};
$("qualitySearch").oninput = renderQualityReference;
$("qualityConfirmed").onchange = () => {
  if (qualityReference && qualityReference.state !== "reviewed")
    $("qualityFinalize").disabled = !$("qualityConfirmed").checked;
};
$("qualityFinalize").onclick = () => setQualityReviewed(true);
$("qualityReopen").onclick = () => setQualityReviewed(false);
$("qualityUtterances").addEventListener("click", event => {
  const button = event.target.closest("button[data-action]");
  const card = event.target.closest(".quality-utterance");
  if (!button || !card || !qualityReference) return;
  const item = (qualityReference.utterances || []).find(
    value => value.event_id === card.dataset.event);
  if (button.dataset.action === "play") playQualityUtterance(item);
  else if (button.dataset.action === "save") saveQualityUtterance(card);
  else if (button.dataset.action === "split") openQualitySplit(card,item);
  else if (button.dataset.action === "split-cancel") button.closest(".quality-split-panel").remove();
  else if (button.dataset.action === "split-confirm") saveQualitySplit(card,item);
});
$("qualityClose").onclick = () => {
  if (!closeQualityEditor()) return;
  $("qualityOverlay").classList.remove("show");
};
$("guardCalibrationClose").onclick = () => $("guardCalibrationOverlay").classList.remove("show");
$("guardCalibrationRefresh").onclick = loadGuardCalibration;
$("guardCalibrationConfirmed").onchange = () => {
  $("guardCalibrationApply").disabled = !(guardCalibrationState?.can_apply
    && $("guardCalibrationConfirmed").checked);
};
$("guardCalibrationApply").onclick = applyGuardCalibration;
$("memoryBtn").onclick = () => {
  closeSettingsOverlay();
  const focused = document.body.classList.contains("memory-open");
  document.body.classList.remove("side-collapsed");
  uiPreference("sideCollapsed", "0");
  document.body.classList.toggle("memory-open", !focused);
  if (!focused || !["кандидат", "тренировка"].includes(currentMeetingType)) {
    document.querySelector('[data-t="memoryPanel"]').click();
    $("side").scrollIntoView({behavior:"smooth", block:"start"});
  }
};
$("replayClose").onclick = () => {
  replayEpoch++;
  $("replayOverlay").classList.remove("show"); replaySession = null;
  clearTimeout(replayTimer); replayTimer = null;
  stopReplayCompareAudio(); stopReplayTimeline(); replayTimelineData = null;
  replaySelected = new Set(); replayRunsState = [];
};
$("replayRefresh").onclick = loadReplayRuns;
$("replayCompare").onclick = compareReplaySelected;
$("replayCompareClose").onclick = () => {
  stopReplayCompareAudio(); $("replayComparePanel").hidden = true;
};
$("replayTimelineClose").onclick = () => {
  stopReplayTimeline(); $("replayTimelinePanel").hidden = true;
};
$("replayTimelineSpeed").onchange = event => {
  $("replayTimelineAudio").playbackRate = Number(event.target.value)||1;
};
$("replayTimelineLlm").oninput = renderReplayTimelineSimulation;
$("replayTimelineSilence").oninput = renderReplayTimelineSimulation;
$("replayTimelineAudio").ontimeupdate = updateReplayTimelineCursor;
$("replayAudio").onchange = updateReplayControls;
$("replayDiarization").onchange = updateReplayControls;
$("replayMatrix").onchange = updateReplayControls;
$("replayStart").onclick = async () => {
  if (!replaySession) return;
  const button = $("replayStart"); button.disabled = true;
  studioLabel($("replayStatus"),"Создаю изолированный прогон…");
  try {
    const response = await fetch(`/api/sessions/${encodeURIComponent(replaySession.dir)}/replays`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify(replayOptions())});
    if (!response.ok) throw new Error(await response.text());
    const run = await response.json();
    studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Запущен {p0}. Можно закрыть окно — обработка продолжится.",{p0:run.run_id})}}));
    await loadReplayRuns();
  } catch (error) { studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Не запущено: {p0}",{p0:error.message})}})); }
  finally { button.disabled = false; }
};
$("replayMatrixStart").onclick = async () => {
  if (!replaySession) return;
  if ($("replayHint").checked) {
    studioLabel($("replayStatus"),"Для матрицы отключите платную контрольную LLM-подсказку.");
    return;
  }
  const button = $("replayMatrixStart"); button.disabled = true;
  studioLabel($("replayStatus"),"Готовлю независимые варианты матрицы…");
  try {
    const body = {...replayOptions(), preset:$("replayMatrix").value,
                  generate_hint:false};
    const response = await fetch(
      `/api/sessions/${encodeURIComponent(replaySession.dir)}/replays/matrix`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify(body)});
    if (!response.ok) throw new Error(await response.text());
    const matrix = await response.json();
    replaySelected = new Set((matrix.runs || []).map(run => run.run_id));
    $("replayComparePanel").hidden = true;
    studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Матрица {p0} вариантов запущена последовательно. Сравнение станет доступно после завершения.",{p0:matrix.count})}}));
    await loadReplayRuns();
  } catch (error) {
    studioLabel($("replayStatus"),()=>({source:"{value}",values:{value:studioUi("Матрица не запущена: {p0}",{p0:error.message})}}));
  } finally { button.disabled = false; updateReplayControls(); }
};
$("settingsBtn").onclick = event => openSettingsOverlay(event.currentTarget);
$("settingsGuide").onclick = () => {
  openHelp();
};
if ($("settingsHome")) {
  $("settingsHome").onclick = () => {
    if (!closeSettingsOverlay()) return;
    $("settingsBtn").focus();
  };
}
$("modelsBtn").onclick = openModelManager;
$("modelManagerSettings").onclick = openModelManager;
$("modelClose").onclick = () => $("modelOverlay").classList.remove("show");
$("modelRefresh").onclick = () => {
  $("modelStatus").className = "workspace-status scanning";
  studioLabel($("modelStatus"),"Обновляю размеры и контрольные суммы…");
  send({type:"models_status"});
};
$("updatesBtn").onclick = openUpdateManager;
$("updateManagerSettings").onclick = openUpdateManager;
$("updateClose").onclick = () => $("updateOverlay").classList.remove("show");
$("updateRefresh").onclick = () => send({type:"update_status"});
$("updateBrowse").onclick = () => send({
  type:"update_browse", path:selectedRelease ? selectedRelease.package : ""});
$("updateStage").onclick = () => {
  if (!selectedRelease) return;
  if (confirm(`Подготовить обновление Blatero ${selectedRelease.version}?\n\nТекущий сервер не изменится. Пакет будет применён только при следующем запуске.`))
    send({type:"update_stage", package:selectedRelease.package});
};
$("updateCancel").onclick = () => {
  if (confirm(studioUi("Отменить подготовленное обновление или откат?"))) send({type:"update_cancel"});
};
$("updateRollback").onclick = () => {
  if (confirm(studioUi("Подготовить возврат к предыдущей версии?\n\nДанные встреч и модели не изменятся.")))
    send({type:"update_rollback"});
};
$("commandBtn").onclick = openCommandPalette;
$("commandClose").onclick = closeCommandPalette;
$("commandSettings").onclick = () => {
  openCommandPalette();
};
$("sideToggleSettings").onclick = toggleSide;
$("sideCollapse").onclick = () => setSideVisible(false);
$("sideRestore").onclick = () => setSideVisible(true);
$("sideWidth").oninput = event => applySideWidth(event.target.value);
$("layoutPreset").onchange = event => applyLayoutPreset(event.target.value);
$("layoutSideVisible").onchange = event => setSideVisible(event.target.checked);
$("layoutFeedVisible").onchange = event => setTranscriptVisible(event.target.checked);
$("layoutFeedTall").onchange = event => setTranscriptTall(event.target.checked);
$("layoutReset").onclick = resetLayout;
$("pinnedHintClear").onclick = clearPinnedHint;
$("pinnedHintFocus").onclick = () => openFocusAnswer(pinnedHint.text);
$("pinnedHintCopy").onclick = () => copyUiText(pinnedHint.text).catch(() => {});
$("focusAnswerClose").onclick = () => $("focusAnswerOverlay").classList.remove("show");
$("focusAnswerCopy").onclick = () => copyUiText($("focusAnswerText").textContent).catch(() => {});
$("focusAnswerUnpin").onclick = clearPinnedHint;
$("commandSearch").oninput = event => { commandSelection = 0; renderCommands(event.target.value); };
let sideResizeRight = 0;
$("sideResize").onpointerdown = event => {
  if (window.innerWidth <= 700) return;
  sideResizeRight = $("side").getBoundingClientRect().right;
  document.body.classList.add("side-resizing");
  $("sideResize").setPointerCapture(event.pointerId);
  event.preventDefault();
};
$("sideResize").onpointermove = event => {
  if (!document.body.classList.contains("side-resizing")) return;
  applySideWidth(Math.round((sideResizeRight - event.clientX) / 20) * 20);
};
$("sideResize").onpointerup = event => {
  document.body.classList.remove("side-resizing");
  if ($("sideResize").hasPointerCapture(event.pointerId))
    $("sideResize").releasePointerCapture(event.pointerId);
};
$("sideResize").onpointercancel = $("sideResize").onpointerup;
$("sideResize").onkeydown = event => {
  const current = Number($("sideResize").getAttribute("aria-valuenow")) || 620;
  let next = null;
  if (["ArrowLeft", "ArrowDown"].includes(event.key)) next = current - 20;
  else if (["ArrowRight", "ArrowUp"].includes(event.key)) next = current + 20;
  else if (event.key === "Home") next = 320;
  else if (event.key === "End") next = 900;
  if (next == null) return;
  event.preventDefault(); applySideWidth(next);
};
$("promptEditorBtn").onclick = () => {
  $("promptOverlay").classList.add("show");
  studioLabel($("promptList"),"Загружаю реестр…");
  $("promptStatus").textContent = "";
  send({type:"prompt_catalog"});
  $("promptTitle").focus();
};
function closePromptEditor() {
  if (promptHasDraft() && !confirm(studioUi("Закрыть редактор и потерять несохранённые изменения?"))) return;
  $("promptOverlay").classList.remove("show");
}
$("promptClose").onclick = closePromptEditor;
$("promptText").oninput = () => {
  const item = selectedPrompt();
  const dirty = !!item && $("promptText").value !== item.text;
  $("promptSave").disabled = !dirty;
  $("promptStatus").style.color = dirty ? "var(--yellow)" : "var(--dim)";
  studioLabel($("promptStatus"),dirty
    ? "есть несохранённые изменения"
    : (item && item.customized ? "используется локальная версия" : "заводской вариант"));
};
$("promptSave").onclick = () => {
  if (!selectedPromptKey) return;
  $("promptSave").disabled = true;
  $("promptStatus").style.color = "var(--yellow)";
  studioLabel($("promptStatus"),"проверяю и сохраняю…");
  send({type:"prompt_save", key:selectedPromptKey, text:$("promptText").value});
};
$("promptReset").onclick = () => {
  const item = selectedPrompt();
  if (!item || !confirm(studioUi("Сбросить «{label}» к заводскому варианту?",{label:item.label}))) return;
  send({type:"prompt_reset", key:item.key});
};
$("emuBtn").onclick = () => send({type:"emulation_toggle", enabled:!emulationEnabled});
$("calendarBtn").onclick = () => {
  $("calendarOverlay").classList.add("show");
  if (calendarState) send({type:"calendar_get", anchor:calendarState.anchor, view:calendarState.view});
};
$("audioBtn").onclick = () => $("audioOverlay").classList.add("show");
function speakerProfileSource(value) {
  return ({chatterbox_sample:studioUi("мой образец Chatterbox"),
           session_cluster:studioUi("реплики встречи"),
           calibrated_sessions:studioUi("калибровка по архиву")})[value] || studioUi("локальный образец");
}
function speakerCalibrationLabel(item) {
  const value = item && item.calibration;
  if (!value) return "";
  const accepted = Number(value.accepted_sessions) || 0;
  const rejected = Number(value.rejected_sessions) || 0;
  const falseAccepts = Number(value.false_accepts) || 0;
  const negatives = Number(value.negative_tests) || 0;
  return studioUi(" · архив: {p0} принято, {p1} исключено · ложных совпадений {p2}/{p3}",{p0:accepted,p1:rejected,p2:falseAccepts,p3:negatives});
}
function speakerAction(icon, label, css, profile) {
  return `<button class="speaker-profile-action ${css}" data-profile="${esc(profile)}" ${studioAttrs('title',label)}><svg class="ui-icon" aria-hidden="true"><use href="#icon-${icon}"/></svg><span>${studioText(label)}</span></button>`;
}
function speakerAlternativesText(items) {
  const alternatives = (items || []).slice(0, 3);
  return alternatives.length
    ? studioUi(" Ближайшие: {p0}.",{p0:alternatives.map(item => `${item.name} ${Math.round(Number(item.similarity||0)*100)}%`).join("; ")})
    : "";
}
function speakerVerificationText(result) {
  const usable = result.state === "high" || result.state === "review";
  let lead;
  if (result.matched_expected && usable) {
    lead = result.state === "high"
      ? studioUi("Запись похожа на «{p0}».",{p0:result.expected_name})
      : studioUi("«{p0}» — первый вариант, но требуется проверка на слух.",{p0:result.expected_name});
  } else if (result.matched_expected) {
    lead = studioUi("Запись пока недостаточно похожа на «{p0}».",{p0:result.expected_name});
  } else {
    const best = (result.alternatives || [])[0];
    lead = best
      ? studioUi("Запись больше похожа на «{p0}», а не на «{p1}».",{p0:best.name,p1:result.expected_name})
      : studioUi("Профиль «{p0}» не подтверждён.",{p0:result.expected_name});
  }
  return `${lead} ${result.reason || ""}${speakerAlternativesText(result.alternatives)}`.trim();
}
function renderSpeakerProfiles(data) {
  const list = $("speakerProfileList"), profiles = data.profiles || [];
  if (!data.model_ready) {
    list.innerHTML = `<div class="speaker-profile-empty">${studioText("Модель Speaker ID не установлена.")}</div><button type="button" data-model-install>${studioText("Открыть установку моделей")}</button>`;
    list.querySelector("[data-model-install]").onclick = openModelManager;
  } else if (!profiles.length) {
    list.innerHTML = `<div class="speaker-profile-empty">${studioText("Банк пуст. Добавьте свой образец здесь или участника из экрана проверки диаризации.")}</div>`;
  } else {
    list.innerHTML = profiles.map(item => item.state === "error"
      ? `<article class="speaker-profile"><div class="speaker-profile-copy"><strong>${esc(item.name)}</strong><small>${studioText("профиль повреждён")}</small></div><div class="speaker-profile-actions">${speakerAction("trash", studioUi("удалить"), "danger speaker-profile-delete", item.profile_id)}</div></article>`
      : `<article class="speaker-profile"><div class="speaker-profile-copy"><strong>${esc(item.name)}</strong><small>${esc(speakerProfileSource(item.source_kind))}${studioText(" · образцов: ")}${Number(item.embedding_count)||0}${esc(speakerCalibrationLabel(item))}</small></div><div class="speaker-profile-actions">${speakerAction("mic", studioUi("проверить голос"), "speaker-profile-verify", item.profile_id)}${speakerAction("edit", studioUi("переименовать"), "speaker-profile-rename", item.profile_id)}${speakerAction("trash", studioUi("удалить"), "danger speaker-profile-delete", item.profile_id)}</div></article>`).join("");
  }
  list.querySelectorAll(".speaker-profile-rename").forEach(button => button.onclick = async () => {
    const card = button.closest(".speaker-profile"), current = card.querySelector("strong").textContent;
    const name = prompt(studioUi("Новое имя голосового профиля"), current);
    if (name === null || name.trim() === current) return;
    button.disabled = true; studioLabel($("speakerBankStatus"),"Переименовываю профиль…");
    try {
      const response = await fetch(`/api/speaker-profiles/${encodeURIComponent(button.dataset.profile)}`, {
        method:"PATCH", headers:{"Content-Type":"application/json"}, body:JSON.stringify({name:name.trim()})});
      if (!response.ok) throw new Error(await response.text());
      await loadSpeakerProfiles();
      studioLabel($("speakerBankStatus"),()=>({source:"{value}",values:{value:studioUi("Профиль переименован в «{p0}».",{p0:name.trim()})}}));
    } catch (error) {
      studioLabel($("speakerBankStatus"),()=>({source:"{value}",values:{value:studioUi("Не переименовано: {p0}",{p0:error.message})}})); button.disabled = false;
    }
  });
  list.querySelectorAll(".speaker-profile-verify").forEach(button => button.onclick = async () => {
    const card = button.closest(".speaker-profile"), name = card.querySelector("strong").textContent;
    const actions = [...list.querySelectorAll(".speaker-profile-action")];
    actions.forEach(action => { action.disabled = true; });
    let remaining = 15;
    studioLabel($("speakerBankStatus"),()=>({source:"{value}",values:{value:studioUi("Говорите обычным голосом {p0} секунд. Проверочная запись будет удалена сразу после сравнения.",{p0:remaining})}}));
    const ticker = setInterval(() => {
      remaining = Math.max(1, remaining - 1);
      studioLabel($("speakerBankStatus"),()=>({source:"{value}",values:{value:studioUi("Говорите обычным голосом: осталось около {p0} с. Проверяю профиль «{p1}»…",{p0:remaining,p1:name})}}));
    }, 1000);
    try {
      const response = await fetch(`/api/speaker-profiles/${encodeURIComponent(button.dataset.profile)}/verify`, {
        method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"});
      if (!response.ok) throw new Error(await response.text());
      studioValue($("speakerBankStatus"),speakerVerificationText(await response.json()));
    } catch (error) {
      studioLabel($("speakerBankStatus"),()=>({source:"{value}",values:{value:studioUi("Проверка не выполнена: {p0}",{p0:error.message})}}));
    } finally {
      clearInterval(ticker); actions.forEach(action => { action.disabled = false; });
    }
  });
  list.querySelectorAll(".speaker-profile-delete").forEach(button => button.onclick = async () => {
    const card = button.closest(".speaker-profile"), name = card.querySelector("strong").textContent;
    if (!confirm(studioUi("Полностью удалить голосовой профиль «{p0}»? Восстановить отпечаток будет нельзя.",{p0:name}))) return;
    button.disabled = true; studioLabel($("speakerBankStatus"),"Удаляю профиль…");
    try {
      const response = await fetch(`/api/speaker-profiles/${encodeURIComponent(button.dataset.profile)}`, {
        method:"DELETE", headers:{"Content-Type":"application/json"}, body:"{}"});
      if (!response.ok) throw new Error(await response.text());
      await loadSpeakerProfiles();
      studioLabel($("speakerBankStatus"),"Профиль и его отпечатки полностью удалены.");
    } catch (error) {
      studioLabel($("speakerBankStatus"),()=>({source:"{value}",values:{value:studioUi("Не удалено: {p0}",{p0:error.message})}})); button.disabled = false;
    }
  });
}
async function loadSpeakerProfiles() {
  $("speakerProfileList").innerHTML = `<div class="speaker-profile-empty">${studioText("Загружаю…")}</div>`;
  try {
    const response = await fetch("/api/speaker-profiles", {cache:"no-store"});
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json(); renderSpeakerProfiles(data);
    studioLabel($("speakerBankStatus"),()=>({source:"{value}",values:{value:!data.model_ready
      ? studioUi("Модель голосов не установлена · профилей: {p0}.",{p0:Number(data.count) || 0})
      : data.count
      ? studioUi("Локально сохранено профилей: {p0}.",{p0:data.count})
      : studioUi("Банк готов, сохранённых профилей пока нет.")}}));
  } catch (error) {
    $("speakerProfileList").innerHTML = `<div class="speaker-profile-empty">${studioText("Банк недоступен.")}</div>`;
    studioLabel($("speakerBankStatus"),()=>({source:"{value}",values:{value:studioUi("Не удалось открыть банк: {p0}",{p0:error.message})}}));
  }
}
function openSpeakerBank() {
  $("speakerBankOverlay").classList.add("show");
  loadSpeakerProfiles();
  $("speakerProfileName").focus();
}
$("speakerBankBtn").onclick = openSpeakerBank;
$("speakerBankClose").onclick = () => $("speakerBankOverlay").classList.remove("show");
$("speakerBankRefresh").onclick = loadSpeakerProfiles;
$("speakerOpenAudio").onclick = () => {
  $("speakerBankOverlay").classList.remove("show"); $("audioOverlay").classList.add("show");
};
async function createMySpeakerProfile(button, url, progress, completed) {
  const name = $("speakerProfileName").value.trim();
  if (!name) { studioLabel($("speakerBankStatus"),"Укажите имя профиля."); $("speakerProfileName").focus(); return; }
  if (!$("speakerProfileConsent").checked) { studioLabel($("speakerBankStatus"),"Сначала подтвердите создание и хранение локального отпечатка."); return; }
  button.disabled = true; studioValue($("speakerBankStatus"),progress);
  try {
    const response = await fetch(url, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({name, consent:true})});
    if (!response.ok) throw new Error(await response.text());
    $("speakerProfileName").value = ""; $("speakerProfileConsent").checked = false;
    await loadSpeakerProfiles();
    studioValue($("speakerBankStatus"),completed);
  } catch (error) {
    studioLabel($("speakerBankStatus"),()=>({source:"{value}",values:{value:studioUi("Профиль не создан: {p0}",{p0:error.message})}}));
  } finally { button.disabled = false; }
}
$("speakerCalibrateMyVoice").onclick = () => createMySpeakerProfile(
  $("speakerCalibrateMyVoice"), "/api/speaker-profiles/calibrate-my-voice",
  studioUi("Сравниваю локальные микрофонные дорожки и отбраковываю эхо…"),
  studioUi("Профиль откалиброван по согласованным архивным встречам. Исходное аудио не копировалось."));
$("speakerEnrollMyVoice").onclick = () => createMySpeakerProfile(
  $("speakerEnrollMyVoice"), "/api/speaker-profiles/enroll-my-voice",
  studioUi("Анализирую отдельный образец локально…"),
  studioUi("Профиль создан из отдельного образца. Исходная запись в банк не копировалась."));
$("micTestStart").onclick = startMicPreview;
if ($("settingsMicTest")) $("settingsMicTest").onclick = () => {
  $("audioOverlay").classList.add('show');
  requestAnimationFrame(() => {
    $("micTestPanel").scrollIntoView({block:'center'});
    $("micTestStart").focus({preventScroll:true});
  });
  startMicPreview();
};
if ($("micTestCancel")) $("micTestCancel").onclick = () => {
  clearMicPreview(); studioLabel($("micTestStatus"),"Проверка отменена. Нажмите кнопку, когда будете готовы.");
};
if ($("micTestClear")) $("micTestClear").onclick = () => {
  clearMicPreview(); studioLabel($("micTestStatus"),"Проба удалена из памяти вкладки.");
};
$("outputTestStart").onclick = () => {
  $("outputMeter").style.width = "0";
  $("outputMeter").setAttribute("aria-valuenow", "0");
  send({type:"output_test"});
};
$("aecTestStart").onclick = () => {
  $("aecTestStart").disabled = true;
  studioLabel($("aecTestStatus"),"подготовка калибровки…");
  $("aecTestStatus").className = "workspace-status scanning";
  send({type:"aec_test"});
};
$("startCalibrate").onclick = () => {
  calibrationBypassed = false;
  renderStartCalibration({type:"aec_test", state:"started",
    text:studioUi("Сейчас прозвучит тихий тест. Не говорите около четырёх секунд.")});
  send({type:"aec_test"});
};
$("startWithoutCalibration").onclick = () => {
  calibrationBypassed = true;
  renderStartCalibration();
};
function startPreflight() {
  openPreflightGuide();
}
$("preflightStart").onclick = startPreflight;
$("preflightQuick").onclick = startPreflight;
$("diagnosticsBuild").onclick = () => {
  $("diagnosticsBuild").disabled = true;
  studioLabel($("preflightStatus"),"Собираю обезличенную диагностику…");
  send({type:"diagnostics_build"});
};
$("aecNativeInstall").onclick = () => {
  $("aecNativeInstall").disabled = true;
  renderNativeAec({supported:true, busy:true, state:"started",
    text:"Скачиваю и проверяю WebRTC AEC3…"});
  send({type:"aec_install"});
};
$("refreshMics").onclick = () => send({type:"refresh_audio"});
$("testMic").onchange = e => {
  $("selMic").value = e.target.value;
  send({type:"config", key:"mic_device", value:e.target.value});
};
$("testOutput").onchange = e => {
  $("selOutput").value = e.target.value;
  send({type:"config", key:"output_device", value:e.target.value});
};
$("agendaBtn").onclick = () => send({type: "get_agenda"});
$("openReportFolder").onclick = () => send({type:"open_report_folder"});
$("agendaSave").onclick = () => {
  send({type: "save_agenda", text: $("agendaTa").value});
  $("agendaOverlay").classList.remove("show");
};
$("recbtn").onclick = () => {
  if (recLive) send({type:"rec", action:"stop"});
  else if(window.BlateroRecording)window.BlateroRecording.choose();
  else openStartOverlay();
};
$("startConfirm").onclick = () => {
  if (!pendingStartMode) return;
  if (currentContour === "work" && !$("startRecordingAck").checked) {
    $("startRecordingAck").focus();
    return;
  }
  if (!calibrationIsReady() && !calibrationBypassed) {
    studioLabel($("startCalibrationTitle"),"Сначала калибровка или явный пропуск");
    studioLabel($("startCalibrationText"),"Выберите один из двух вариантов выше.");
    $("startCalibrate").focus();
    return;
  }
  let capturePayload;
  try { capturePayload=window.BlateroRecording?.startPayload() || {}; }
  catch(error) { $("startModeHint").textContent=error.message; return; }
  send({type:"rec", action:"start", mtype:pendingStartMode,
    calibration_bypassed:calibrationBypassed,
    recording_acknowledged:$("startRecordingAck").checked,
    ...capturePayload, ...speechStartRequest});
  speechStartRequest = null;
  window.BlateroRecording?.submitted();
  $("startOverlay").classList.remove("show");
};
$("startRecordingAck").onchange = updateStartConfirmState;
$("startClose").onclick = $("startCancel").onclick = () => {
  speechStartRequest = null;
  window.BlateroRecording?.cancelPending();
  trainingStartPending = false;
  sceneStartPending = false;
  $("startOverlay").classList.remove("show");
};
const sideTabs = [...document.querySelectorAll(".stab")];
function activateSideTab(tab, focus = false) {
  if (!tab) return;
  const targetId = tab.dataset.t;
  if (targetId !== "memoryPanel" && ["кандидат", "тренировка"].includes(currentMeetingType))
    document.body.classList.remove("memory-open");
  sideTabs.forEach(item => {
    const active = item === tab;
    item.classList.toggle("sel", active);
    item.setAttribute("aria-selected", String(active));
    item.tabIndex = active ? 0 : -1;
  });
  ["bank", "dossier", "workspaceContext", "memoryPanel"].forEach(id => {
    $(id).hidden = targetId !== id;
  });
  if (focus) tab.focus();
}
sideTabs.forEach((tab, index) => {
  tab.onclick = () => activateSideTab(tab);
  tab.onkeydown = event => {
    let target = null;
    if (["ArrowLeft", "ArrowUp"].includes(event.key)) target = sideTabs[(index - 1 + sideTabs.length) % sideTabs.length];
    else if (["ArrowRight", "ArrowDown"].includes(event.key)) target = sideTabs[(index + 1) % sideTabs.length];
    else if (event.key === "Home") target = sideTabs[0];
    else if (event.key === "End") target = sideTabs.at(-1);
    if (!target) return;
    event.preventDefault(); activateSideTab(target, true);
  };
});
$("selMic").onchange = e => {
  $("testMic").value = e.target.value;
  send({type: "config", key: "mic_device", value: e.target.value});
};
$("selOutput").onchange = e => {
  $("testOutput").value = e.target.value;
  send({type: "config", key: "output_device", value: e.target.value});
};
$("selAecBackend").onchange = e => send({
  type:"config", key:"pre_stt_echo_backend", value:e.target.value});
$("selAuto").onchange = e => send({type: "config", key: "auto_pulse", value: e.target.value});
$("selProvider").onchange = e => {
  $("inpLlmApiKey").value = "";
  updateProviderControls(e.target.value, null);
  send({type: "config", key: "llm_provider", value: e.target.value});
};
$("inpPulseModel").onchange = e => send({type: "config", key: "pulse_model", value: e.target.value.trim()});
$("inpReportModel").onchange = e => send({type: "config", key: "report_model", value: e.target.value.trim()});
$("toggleLlmKey").onclick = () => {
  const input = $("inpLlmApiKey");
  input.type = input.type === "password" ? "text" : "password";
  $("toggleLlmKey").textContent = settingsUi(input.type === "password" ? "Показать" : "Скрыть");
};
function llmConnectionPayload(type) {
  return {type, provider:$("selProvider").value,
          api_key:$("inpLlmApiKey").value.trim(),
          base_url:$("inpLlmBaseUrl").value.trim()};
}
$("llmSave").onclick = () => send(llmConnectionPayload("llm_connection_save"));
$("llmTest").onclick = () => {
  renderLlmConnection({provider:$("selProvider").value, state:"scanning",
                       message:"Проверяю авторизацию без отправки данных встречи…"});
  send(llmConnectionPayload("llm_connection_test"));
};
$("llmDelete").onclick = () => {
  if (confirm(studioUi("Удалить API-токен выбранного провайдера из Windows Credential Manager?")))
    send({type:"llm_connection_delete", provider:$("selProvider").value});
};
$("selVoice").onchange = e => send({type: "config", key: "voice", value: e.target.value});
$("selQuestionVoice").onchange = e => send({type: "config", key: "question_voice_provider", value: e.target.value});
$("selStyle").onchange = e => send({type: "config", key: "question_style", value: e.target.value});
$("selFont").onchange = e => {
  applyFontScale(e.target.value);
  send({type: "config", key: "font_scale", value: e.target.value});
};
$("reportTimestamps").onchange = e => send({
  type:"config", key:"report_include_timestamps", value:e.target.checked
});
$("reportReviewBeforeFinalize").onchange = e => send({
  type:"config", key:"report_review_before_finalize", value:e.target.checked
});
$("selSpeech").onchange = e => {
  updateSpeechControls(e.target.value);
  send({type:"config", key:"speech_provider", value:e.target.value});
};
$("selWhisper").onchange = e => send({type:"config", key:"whisper_model", value:e.target.value});
$("selPrivacy").onchange = e => {
  if (e.target.value === "raw" && !confirm(studioUi("Передавать в LLM исходные ФИО, контакты и другие данные без обезличивания?"))) {
    e.target.value = "redact"; return;
  }
  send({type:"config", key:"text_privacy_mode", value:e.target.value,
        raw_acknowledged:e.target.value === "raw"});
};
$("cloudAck").onchange = e => {
  if (currentInit) currentInit.config.cloud_ack = e.target.checked;
  send({type:"config", key:"cloud_processing_acknowledged", value:e.target.checked});
};
$("echoSuppression").onchange = e => send({type:"config", key:"cross_channel_echo_suppression", value:e.target.checked});
$("acousticEchoSuppression").onchange = e => send({type:"config", key:"pre_stt_echo_suppression", value:e.target.checked});

function calendarRequest(anchor, view) {
  send({type:"calendar_get", anchor, view});
}
function calendarMove(direction) {
  if (!calendarState) return;
  const anchor = new Date(calendarState.anchor + "T00:00:00");
  anchor.setDate(anchor.getDate() + direction * (calendarState.view === "week" ? 7 : 1));
  calendarRequest(calDateKey(anchor), calendarState.view);
}
$("calPrev").onclick = () => calendarMove(-1);
$("calNext").onclick = () => calendarMove(1);
$("calToday").onclick = () => calendarRequest(calDateKey(new Date()), calendarState ? calendarState.view : "day");
$("calDay").onclick = () => calendarRequest(calendarState ? calendarState.anchor : calDateKey(new Date()), "day");
$("calWeek").onclick = () => calendarRequest(calendarState ? calendarState.anchor : calDateKey(new Date()), "week");
$("calSync").onclick = () => {
  if (calendarState) send({type:"calendar_sync", anchor:calendarState.anchor, view:calendarState.view});
};
function updateCalendarProviderForm() {
  const provider = $("calProvider").value;
  document.querySelectorAll(".cal-google").forEach(x => x.style.display = provider === "google" ? "" : "none");
  document.querySelectorAll(".cal-caldav").forEach(x => x.style.display = provider === "google" ? "none" : "");
  if (provider === "yandex") $("calUrl").value = "https://caldav.yandex.ru";
  else if (provider === "mail") $("calUrl").value = "https://calendar.mail.ru";
  else if (provider === "caldav" && /(?:yandex|mail)\.ru/.test($("calUrl").value)) $("calUrl").value = "";
}
$("calProvider").onchange = updateCalendarProviderForm;
$("calAddSource").onclick = () => {
  if (!calendarState) return;
  send({type:"calendar_source_save", source:{provider:$("calProvider").value,
    label:$("calLabel").value.trim(), username:$("calUsername").value.trim(),
    url:$("calUrl").value.trim(), credentials_file:$("calCredentials").value.trim()},
    password:$("calPassword").value, anchor:calendarState.anchor, view:calendarState.view});
  $("calPassword").value = "";
};
updateCalendarProviderForm();
$("pulse").onclick = () => send({type: currentMeetingType === 'тренировка'
  && trainingStudioMode !== 'personal' ? 'scene_hint' : 'pulse'});
function readOnboardingPreference() {
  try { return localStorage.getItem(ONBOARDING_STORAGE_KEY) !== "0"; }
  catch { return true; }
}
function openHelp(automatic = false) {
  onboardingOffered = true;
  clearTimeout(onboardingTimer);
  if ($("helpShowOnStartup")) $("helpShowOnStartup").checked = onboardingShowOnStartup;
  $("helpOverlay").classList.add("show");
  document.dispatchEvent(new CustomEvent("blatero:help-opened", {detail:{automatic:automatic === true}}));
  requestAnimationFrame(() => $("helpTitle").focus());
}
function maybeShowOnboarding() {
  if (onboardingOffered || !onboardingShowOnStartup || recLive) return;
  clearTimeout(onboardingTimer);
  onboardingTimer = setTimeout(() => {
    if (recLive || onboardingOffered || !onboardingShowOnStartup) return;
    if (document.querySelector(".overlay.show, dialog[open]")) {
      maybeShowOnboarding();
      return;
    }
    openHelp(true);
  }, 350);
}
// A running pre-update server may still serve the old HTML until restart.
if ($("helpShowOnStartup")) $("helpShowOnStartup").onchange = event => {
  onboardingShowOnStartup = event.target.checked;
  try {
    localStorage.setItem(ONBOARDING_STORAGE_KEY, onboardingShowOnStartup ? "1" : "0");
    studioLabel($("helpPreferenceStatus"),"Сохранено в этом браузере.");
  } catch {
    studioLabel($("helpPreferenceStatus"),"Браузер запретил сохранение. Выбор действует только в этой вкладке.");
  }
};
$("help").onclick = () => openHelp();
$("helpClose").onclick = () => {
  $("helpOverlay").classList.remove("show");
};
$("helpSetup").onclick = () => {
  $("helpOverlay").classList.remove("show");
  $("setupBtn").click();
};
$("helpQuickSettings").onclick = () => {
  $("helpOverlay").classList.remove("show");
  openSettingsOverlay($("helpQuickSettings"));
  $("settingsOverlay").scrollTop = 0;
  $("settingsTitle").focus();
};
$("helpDone").onclick = () => {
  $("helpOverlay").classList.remove("show");
};
async function shutdownApplication() {
  if (recLive) {
    alert(studioUi("Сначала остановите запись, чтобы сохранить последние реплики."));
    return;
  }
  if (!confirm(studioUi("Завершить работу Blatero и остановить локальный сервер?"))) return;
  const buttons = [$("shutdownBtn")];
  buttons.forEach(button => { button.disabled = true; });
  try {
    const response = await fetch("/api/shutdown", {
      method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"
    });
    if (!response.ok) throw new Error(await response.text());
    document.querySelectorAll(".overlay.show").forEach(overlay => overlay.classList.remove("show"));
    $("shutdownOverlay").classList.add("show");
    $("shutdownTitle").focus();
  } catch (error) {
    alert(studioUi("Не удалось завершить Blatero: {p0}",{p0:error.message}));
    buttons.forEach(button => { button.disabled = false; });
  }
}
$("shutdownBtn").onclick = shutdownApplication;
document.querySelectorAll(".empty-step").forEach(button => {
  button.onclick = () => ({
    setup:$("setupBtn"), check:$("audioBtn"), record:$("recbtn"), analysis:$("analysisBtn")
  }[button.dataset.action]).click();
});
$("workflowNextAction").onclick = event => {
  const action = event.currentTarget.dataset.action;
  if (action === "setup") $("setupBtn").click();
  else if (action === "preflight") $("preflightQuick").click();
  else if (action === "memory_review") { openMeetingResult(); if (typeof openReportMemoryReview === "function") openReportMemoryReview(); }
  else if (action === "record") $("recbtn").click();
  else if (action === "pulse") send({type:"pulse"});
  else if (action === "report") $("report").click();
  else if (action === "results") {
    if (typeof openMeetingResult === "function") openMeetingResult();
    else send({type:"open_report_folder"});
  }
};
document.querySelectorAll(".header-more-menu button").forEach(button => {
  button.addEventListener("click", () => button.closest("details").removeAttribute("open"));
});
document.addEventListener("click", event => {
  document.querySelectorAll(".header-more[open], .output-tools[open]").forEach(details => {
    if (!details.contains(event.target)) details.removeAttribute("open");
  });
});
const modalStack = [];
const modalOrigins = new WeakMap();
let lastDialogTrigger = null;

function modalFocusable(overlay) {
  return [...overlay.querySelectorAll(
    'a[href],button,input,select,textarea,summary,audio[controls],video[controls],[tabindex]:not([tabindex="-1"])')]
    .filter(element => !element.disabled && element.tabIndex >= 0
      && !element.hidden && element.getClientRects().length
      && getComputedStyle(element).visibility !== "hidden"
      && !element.closest('[inert], [hidden]')
      && !hiddenByClosedDetails(element, overlay));
}

function hiddenByClosedDetails(element, boundary) {
  // Firefox can expose rects for controls in a closed disclosure. Only its
  // direct summary participates in Tab order; nested disclosures obey each ancestor.
  for (let parent = element.parentElement; parent && parent !== boundary;
       parent = parent.parentElement) {
    if (parent.tagName === "DETAILS" && !parent.open
        && !parent.querySelector(":scope > summary")?.contains(element)) return true;
  }
  return false;
}

function topVisibleModal() {
  for (let index = modalStack.length - 1; index >= 0; index -= 1) {
    if (modalStack[index].classList.contains("show")) return modalStack[index];
  }
  return [...document.querySelectorAll(".overlay.show")].at(-1) || null;
}

function modalReturnTarget(origin) {
  if (!(origin instanceof HTMLElement) || !origin.isConnected) return null;
  const disclosure = origin.closest("details");
  const summary = disclosure?.querySelector(":scope > summary");
  if (disclosure && !disclosure.open)
    return summary instanceof HTMLElement && summary.getClientRects().length ? summary : null;
  if (origin.getClientRects().length) return origin;
  return summary instanceof HTMLElement && summary.getClientRects().length ? summary : null;
}

function openSettingsOverlay(origin = document.activeElement) {
  const overlay = $("settingsOverlay");
  if (origin instanceof HTMLElement) modalOrigins.set(overlay, origin);
  window.BlateroSettings?.select("overview");
  overlay.classList.add("show");
  overlay.scrollTop = 0;
}

function setSettingsMode(mode) {
  // Older diagnostic links still work; details now belong to their section.
  if (mode === "advanced")
    $("settingsOverlay").querySelectorAll("details").forEach(item => { item.open = true; });
}

function syncModalLayers() {
  const top = topVisibleModal();
  document.querySelectorAll(".overlay").forEach(item => {
    const active = item.classList.contains("show") && item === top;
    item.setAttribute("aria-hidden", String(!active));
    item.inert = !active;
  });
}

function syncAccessibleModal(overlay) {
  const visible = overlay.classList.contains("show");
  if (overlay.id === 'audioOverlay' && !visible) clearMicPreview();
  overlay.setAttribute("aria-hidden", String(!visible));
  overlay.inert = !visible;
  const index = modalStack.indexOf(overlay);
  if (visible) {
    if (index >= 0) modalStack.splice(index, 1);
    modalStack.push(overlay);
    if (!modalOrigins.has(overlay)) {
      const active = document.activeElement;
      modalOrigins.set(overlay, lastDialogTrigger instanceof HTMLElement
        ? lastDialogTrigger : (active instanceof HTMLElement ? active : null));
    }
    lastDialogTrigger = null;
    syncModalLayers();
    const heading = overlay.querySelector('[tabindex="-1"], h3');
    if (heading && !heading.hasAttribute("tabindex")) heading.setAttribute("tabindex", "-1");
    requestAnimationFrame(() => {
      if (!overlay.contains(document.activeElement))
        (heading || modalFocusable(overlay)[0])?.focus({preventScroll:true});
    });
    return;
  }
  if (index >= 0) modalStack.splice(index, 1);
  syncModalLayers();
  const origin = modalOrigins.get(overlay);
  modalOrigins.delete(overlay);
  requestAnimationFrame(() => {
    // Между закрытием одного окна и кадром могло открыться другое. Не возвращать
    // фокус старой кнопке поверх уже активного диалога.
    const upper = topVisibleModal();
    const target = modalReturnTarget(origin);
    const active = document.activeElement;
    const upperHasFocus = upper && active instanceof HTMLElement && upper.contains(active);
    if (target && (!upper || upper.contains(target) || !upperHasFocus))
      target.focus({preventScroll:true});
  });
}

function trapModalTab(event) {
  const overlay = topVisibleModal();
  if (!overlay) return false;
  const focusable = modalFocusable(overlay);
  if (!focusable.length) {
    event.preventDefault();
    overlay.querySelector('[tabindex="-1"], h3')?.focus({preventScroll:true});
    return true;
  }
  const active = document.activeElement;
  const first = focusable[0], last = focusable.at(-1);
  if (event.shiftKey && (active === first || !overlay.contains(active))) {
    event.preventDefault(); last.focus();
  } else if (!event.shiftKey && (active === last || !overlay.contains(active))) {
    event.preventDefault(); first.focus();
  }
  return true;
}

document.addEventListener("click", event => {
  const trigger = event.target.closest("button,a[href],input[type=button],input[type=submit]");
  if (!(trigger instanceof HTMLElement)) return;
  lastDialogTrigger = trigger;
  setTimeout(() => { if (lastDialogTrigger === trigger) lastDialogTrigger = null; }, 0);
}, true);
document.addEventListener("click", event => {
  const trigger = event.target.closest("button,a[href],input[type=button],input[type=submit]");
  if (!(trigger instanceof HTMLElement)) return;
  document.querySelectorAll(".overlay.show").forEach(overlay => {
    if (!modalOrigins.has(overlay)) modalOrigins.set(overlay, trigger);
  });
});
const dialogFocusObserver = new MutationObserver(changes =>
  changes.forEach(change => syncAccessibleModal(change.target)));
document.querySelectorAll(".overlay").forEach(overlay => {
  syncAccessibleModal(overlay);
  dialogFocusObserver.observe(overlay, {attributes:true, attributeFilter:["class"]});
});
$("report").onclick = () => {
  if (currentMeetingResult.has_final && !reportReviewPending() && typeof openMeetingResult === "function") openMeetingResult();
  else if (reportReviewPending()) send({type:"report_review", action:"open"});
  else if (confirm(studioUi("Сформировать проверяемый черновик отчёта?"))) send({type:"report"});
};
$("recoveryBtn").onclick = openRecovery;
$("recoveryClose").onclick = $("recoveryLater").onclick = () =>
  $("recoveryOverlay").classList.remove("show");
$("reportReviewClose").onclick = () => {
  if (((reportDraftSaved !== null && $("reportDraftText").value !== reportDraftSaved)
       || reportConclusionDirty())
      && !confirm(studioUi("Закрыть без сохранения правок черновика?"))) return;
  $("reportReviewOverlay").classList.remove("show");
};
$("reportDraftText").oninput = updateReportDraftState;
$("reportDraftSave").onclick = () => {
  const textarea = $("reportDraftText");
  $("reportDraftSave").disabled = true;
  $("reportDraftStatus").className = "";
  meetingLabel($("reportDraftStatus"),"Сохраняю локально…");
  send({type:"report_review", action:"save_draft", markdown:textarea.value,
        draft_revision:Number(textarea.dataset.revision || 0)});
};
$("reportReviewTimeline").onclick = () => {
  if (currentReportReview.evidence_url)
    window.open(currentReportReview.evidence_url, "_blank", "noopener");
};
$("reportEvidenceExport").onclick = () => {
  if (currentReportReview.evidence_export_url)
    window.open(currentReportReview.evidence_export_url, "_blank", "noopener");
};
$("reportConclusionList").addEventListener("input", event => {
  const textarea = event.target.closest(".report-conclusion-text");
  if (!textarea) return;
  const card = textarea.closest(".report-conclusion");
  const button = card.querySelector(".report-conclusion-save");
  button.disabled = textarea.value === (textarea.dataset.saved || "");
  updateReportDraftState();
});
$("reportConclusionList").addEventListener("click", event => {
  const evidenceButton = event.target.closest(".report-conclusion-evidence");
  if (evidenceButton) {
    openTranscriptEditor(Number(evidenceButton.dataset.startMs) || 0);
    return;
  }
  const sourceButton = event.target.closest(".report-conclusion-source");
  if (sourceButton) {
    send({type:"report_review", action:"open_workspace_source",
          path:sourceButton.dataset.path || ""});
    return;
  }
  const decisionButton = event.target.closest(
    ".report-conclusion-decision button[data-decision]");
  if (decisionButton) {
    const card = decisionButton.closest(".report-conclusion");
    const textarea = card.querySelector(".report-conclusion-text");
    if (textarea.value !== (textarea.dataset.saved || "")) {
      meetingLabel($("reportConclusionMeta"),"Сначала сохраните изменённый текст, затем примите решение.");
      textarea.focus();
      return;
    }
    card.querySelectorAll(".report-conclusion-decision button").forEach(button => {
      button.disabled = true;
    });
    send({type:"report_review", action:"set_conclusion_decision",
          conclusion_id:card.dataset.conclusionId,
          decision:decisionButton.dataset.decision,
          draft_revision:Number(currentReportReview.draft_revision || 0),
          decision_revision:Number(currentReportReview.decision_revision || 0)});
    return;
  }
  const saveButton = event.target.closest(".report-conclusion-save");
  if (!saveButton) return;
  const card = saveButton.closest(".report-conclusion");
  const textarea = card.querySelector(".report-conclusion-text");
  saveButton.disabled = true;
  meetingLabel(saveButton,"сохраняю…");
  send({type:"report_review", action:"save_conclusion",
        conclusion_id:card.dataset.conclusionId, markdown:textarea.value,
        draft_revision:Number(currentReportReview.draft_revision || 0)});
});
$("reportReviewSpeakers").onclick = () => {
  if (currentReportReview.diarization_url)
    window.open(currentReportReview.diarization_url, "_blank", "noopener");
};
$("reportReviewTranscript").onclick = () => openTranscriptEditor();
$("reportReviewIssues").addEventListener("click", event => {
  const sample = event.target.closest(".report-sample-link");
  if (sample) openTranscriptEditor(Number(sample.dataset.startMs) || 0);
});
$("transcriptEditorSearch").oninput = renderTranscriptEditor;
$("transcriptEditorReload").onclick = loadTranscriptEditor;
$("transcriptEditorList").addEventListener("click", event => {
  const action = event.target.closest("[data-action]");
  const card = event.target.closest(".transcript-editor-item");
  if (!action || !card) return;
  const item = (transcriptEditorState.utterances || []).find(
    value => transcriptItemKey(value) === card.dataset.key);
  if (action.dataset.action === "save") saveTranscriptItem(card);
  else if (action.dataset.action === "play") playTranscriptItem(item);
});
$("transcriptEditorClose").onclick = () => {
  const dirty = $("transcriptEditorList").querySelector(".transcript-editor-item.dirty");
  if (dirty && !confirm(studioUi("Закрыть редактор без сохранения изменённой реплики?"))) return;
  const audio = $("transcriptEditorAudio");
  audio.pause();
  if (transcriptEditorAudioTimer) clearInterval(transcriptEditorAudioTimer);
  transcriptEditorAudioTimer = null;
  $("transcriptEditorOverlay").classList.remove("show");
  if (transcriptEditorReturnToReview) {
    transcriptEditorReturnToReview = false;
    send({type:"report_review", action:"open"});
  }
};
$("reportReviewRegenerate").onclick = () => {
  if (confirm(studioUi("Пересобрать черновик по текущему транскрипту? Это выполнит новый запрос к выбранной LLM."))) {
    $("reportReviewOverlay").classList.remove("show");
    send({type:"report_review", action:"regenerate"});
  }
};
$("reportReviewApprove").onclick = () => {
  $("reportReviewOverlay").classList.remove("show");
  send({type:"report_review", action:"approve"});
};
$("reportReviewSkip").onclick = () => {
  if (confirm(studioUi("Создать отчёт, явно указав в нём оставшиеся ограничения?"))) {
    $("reportReviewOverlay").classList.remove("show");
    send({type:"report_review", action:"skip"});
  }
};
let voiceAudioUrl = null;
let activeQuestionAudio = null;
let pendingQuestionAudio = null, questionAudioEpoch = 0;
function restoreQuestionButton(button, label) {
  if(button?.closest('#trainingPanel'))studioLabel(button,label || "▶");
  else if(button)button.textContent=label || "▶";
}
function stopQuestionAudio() {
  questionAudioEpoch++;
  if (pendingQuestionAudio) {
    pendingQuestionAudio.controller.abort();
    pendingQuestionAudio.button.classList.remove("loading");
    restoreQuestionButton(pendingQuestionAudio.button,pendingQuestionAudio.originalLabel);
    pendingQuestionAudio = null;
  }
  if (!activeQuestionAudio) return;
  activeQuestionAudio.audio.pause();
  send({type:"tts_playback", phase:"end", text:activeQuestionAudio.text,
        session:activeQuestionAudio.session,
        scene_turn_id:activeQuestionAudio.sceneTurnId || "",
        voice:activeQuestionAudio.voice || ""});
  URL.revokeObjectURL(activeQuestionAudio.url);
  activeQuestionAudio.button.classList.remove("loading");
  restoreQuestionButton(activeQuestionAudio.button,activeQuestionAudio.originalLabel);
  activeQuestionAudio = null;
}
async function playQuestion(text, button, options = {}) {
  if(options.sceneTurnId&&String(options.voice||'').startsWith('gemini38:')&&window.BlateroSceneAudio&&(window.AudioContext||window.webkitAudioContext))
    return window.BlateroSceneAudio.play(text,button,options);
  if (!text || (pendingQuestionAudio?.text === text && pendingQuestionAudio.button === button)) return;
  stopQuestionAudio();
  const epoch = questionAudioEpoch;
  const controller = new AbortController();
  const originalLabel = button.textContent;
  pendingQuestionAudio = {controller, button, text, originalLabel};
  button.classList.add("loading"); restoreQuestionButton(button,"…");
  const session = $("selSession").value;
  try {
    const response = await fetch("/question-audio", {
      method:"POST", headers:{"Content-Type":"application/json"},
      signal:controller.signal,
      body:JSON.stringify({text, scene_turn_id:options.sceneTurnId || "", scene_run_id:options.sceneRunId || "",
                           voice:options.voice || ""})
    });
    if (!response.ok) throw new Error(await response.text());
    const provider = response.headers.get("X-TTS-Provider") || "голос";
    const fallback = response.headers.get("X-TTS-Fallback") === "1";
    const blob = await response.blob();
    if (epoch !== questionAudioEpoch) return;
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    const savedName = response.headers.get("X-Training-Audio");
    if (savedName && options.sceneTurnId && sceneState?.run_id === options.sceneRunId) {
      const clips = Array.isArray(sceneState.audio_clips) ? sceneState.audio_clips : [];
      if (!clips.some(item => item.name === savedName)) {
        clips.push({name:savedName, speaker:options.sceneSpeaker || "interviewer",
          turn_id:options.sceneTurnId, duration_ms:Number(response.headers.get("X-Training-Duration")) || 0});
        sceneState.audio_clips = clips;
        renderAiScene(sceneState);
      }
    }
    window.BlateroTrainingAvatars?.attach(audio, blob, options.sceneSpeaker || "interviewer");
    if (savedName && options.sceneTurnId) window.BlateroSceneLive?.attach(audio, {
      turnId:options.sceneTurnId,runId:options.sceneRunId,name:savedName,voice:options.voice});
    activeQuestionAudio = {audio, url, text, button, session, originalLabel,
                           sceneTurnId:options.sceneTurnId || "", voice:options.voice || ""};
    pendingQuestionAudio = null;
    audio.onended = () => {
      const isCurrent = activeQuestionAudio && activeQuestionAudio.audio === audio;
      if (isCurrent) send({type:"tts_playback", phase:"end", text, session,
                           scene_turn_id:options.sceneTurnId || "", voice:options.voice || ""});
      URL.revokeObjectURL(url);
      if (isCurrent) activeQuestionAudio = null;
      button.classList.remove("loading"); restoreQuestionButton(button,originalLabel);
      if (isCurrent && typeof options.onDone === "function") options.onDone();
    };
    audio.onerror = () => {
      const isCurrent = activeQuestionAudio && activeQuestionAudio.audio === audio;
      if (isCurrent) send({type:"tts_playback", phase:"end", text, session,
                           scene_turn_id:options.sceneTurnId || "", voice:options.voice || ""});
      URL.revokeObjectURL(url);
      if (isCurrent) activeQuestionAudio = null;
      button.classList.remove("loading"); restoreQuestionButton(button,originalLabel);
    };
    await audio.play();
    send({type:"tts_playback", phase:"start", text, session,
          scene_turn_id:options.sceneTurnId || "", voice:options.voice || ""});
    let lastHeartbeat = performance.now();
    audio.ontimeupdate = () => {
      if (activeQuestionAudio?.audio !== audio || audio.paused || audio.ended ||
          performance.now() - lastHeartbeat < 2000) return;
      lastHeartbeat = performance.now();
      send({type:"tts_playback", phase:"heartbeat", text, session,
            scene_turn_id:options.sceneTurnId || "", voice:options.voice || ""});
    };
    const speakerLabel = options.sceneSpeaker === 'candidate' ? 'говорит кандидат'
      : options.sceneSpeaker === 'interviewer' ? 'говорит интервьюер' : 'вопрос звучит';
    const providerLabel = provider === 'saved scene voice' ? 'сохранённая озвучка' : provider;
    $("status").textContent = `${speakerLabel} · ${providerLabel}${fallback ? " · локальный WAV ещё не готов, использован Яндекс" : ""}`;
  } catch (e) {
    if (epoch !== questionAudioEpoch) return;
    if (activeQuestionAudio && activeQuestionAudio.text === text) {
      activeQuestionAudio.audio.pause();
      URL.revokeObjectURL(activeQuestionAudio.url);
      activeQuestionAudio = null;
      send({type:"tts_playback", phase:"end", text, session,
            scene_turn_id:options.sceneTurnId || "", voice:options.voice || ""});
    }
    button.classList.remove("loading"); restoreQuestionButton(button,originalLabel);
    $("status").textContent = `вопрос не озвучен: ${e.message}`;
  } finally {
    if (pendingQuestionAudio?.controller === controller) pendingQuestionAudio = null;
  }
}

async function playPreview(url, loadingText, successText, status) {
  status.style.color = "var(--acc)"; status.textContent = loadingText;
  const response = await fetch(url, {method:"POST", cache:"no-store",
    headers:{"Content-Type":"application/json"}, body:"{}"});
  if (!response.ok) throw new Error(await response.text());
  if (voiceAudioUrl) URL.revokeObjectURL(voiceAudioUrl);
  voiceAudioUrl = URL.createObjectURL(await response.blob());
  await new Audio(voiceAudioUrl).play();
  status.style.color = "var(--green)"; status.textContent = successText;
}

async function previewYandex() {
  const voice = $("selVoice").value, status = $("voiceTestStatus");
  if (voice === "auto") {
    status.style.color = "var(--yellow)";
    studioLabel(status,"Сначала выберите конкретный голос вместо «auto».");
    $("audioOverlay").classList.add("show");
    return;
  }
  $("voiceTestBtn").disabled = $("voiceTestModal").disabled = true;
  try {
    await playPreview(`/voice-preview/${encodeURIComponent(voice)}`,
      studioUi("загружаю голос {p0} из SpeechKit…",{p0:voice}), studioUi("воспроизводится голос {p0}",{p0:voice}), status);
  } catch (e) {
    status.style.color = "var(--red)"; studioLabel(status,()=>({source:"{value}",values:{value:studioUi("голос не проверен: {p0}",{p0:e.message})}}));
    $("audioOverlay").classList.add("show");
  } finally {
    $("voiceTestBtn").disabled = $("voiceTestModal").disabled = false;
  }
}
async function previewLocal() {
  const status = $("localVoiceStatus");
  $("localVoiceTest").disabled = true;
  try {
    await playPreview("/local-voice-preview", studioUi("локальный голос загружается…"),
      studioUi("воспроизводится мой локальный голос"), status);
  } catch (e) {
    status.style.color = "var(--red)"; studioLabel(status,()=>({source:"{value}",values:{value:studioUi("голос не проверен: {p0}",{p0:e.message})}}));
  } finally { $("localVoiceTest").disabled = false; }
}
async function previewQuestionVoice() {
  if ($("selQuestionVoice").value === "yandex") await previewYandex();
  else { $("audioOverlay").classList.add("show"); await previewLocal(); }
}
$("voiceRecord").onclick = () => send({type:"voice_record", seconds:parseInt($("voiceSeconds").value)});
$("voiceCache").onclick = () => send({type:"voice_cache"});
$("voiceDelete").onclick = () => {
  if (confirm(studioUi("Удалить локальный образец вашего голоса и все подготовленные фразы?")))
    send({type:"voice_delete"});
};
$("localVoiceTest").onclick = previewLocal;
$("voiceTestBtn").onclick = previewQuestionVoice;
$("voiceTestModal").onclick = previewYandex;
document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.code === "KeyK") {
    e.preventDefault();
    if ($("commandOverlay").classList.contains("show")) closeCommandPalette();
    else openCommandPalette();
    return;
  }
  if (e.ctrlKey && e.code === "KeyB" && !e.repeat) {
    e.preventDefault(); toggleSide(); return;
  }
  if (e.ctrlKey && e.code === "KeyJ" && !e.repeat) {
    e.preventDefault();
    setTranscriptVisible(document.body.classList.contains("feed-collapsed"));
    return;
  }
  if (e.key === "Tab" && topVisibleModal()) {
    trapModalTab(e); return;
  }
  if ($("commandOverlay").classList.contains("show")) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const delta = e.key === "ArrowDown" ? 1 : -1;
      commandSelection = visibleCommands.length
        ? (commandSelection + delta + visibleCommands.length) % visibleCommands.length : 0;
      renderCommands($("commandSearch").value);
    } else if (e.key === "Enter") {
      e.preventDefault(); runSelectedCommand();
    } else if (e.key === "Escape") {
      e.preventDefault(); closeCommandPalette();
    }
    return;
  }
  if (e.code === "KeyP" && !e.repeat && !/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) {
    e.preventDefault(); send({type: "pulse"});
  }
  if (e.key === "Escape") {
    const overlay = topVisibleModal();
    if (!overlay) return;
    e.preventDefault();
    const close = overlay.querySelector(".ovclose");
    if (close) close.click();
    else overlay.classList.remove("show");
  }
});
function syncMobileFooterSpace() {
  const footer = document.querySelector("footer");
  if (window.innerWidth <= 700 && footer)
    document.documentElement.style.setProperty("--mobile-footer-height", `${Math.ceil(footer.getBoundingClientRect().height)}px`);
  else document.documentElement.style.removeProperty("--mobile-footer-height");
}
const footerResizeObserver = new ResizeObserver(syncMobileFooterSpace);
footerResizeObserver.observe(document.querySelector("footer"));
window.addEventListener("resize", syncMobileFooterSpace);
syncMobileFooterSpace();
applySideWidth(uiPreference("sideWidth") || 620, false);
const initialSideVisible = uiPreference("sideCollapsed") !== "1";
document.body.classList.toggle("side-collapsed", !initialSideVisible);
$("layoutSideVisible").checked = initialSideVisible;
setTranscriptVisible(uiPreference("feedVisible") === null
  ? !matchMedia('(max-width:700px)').matches : uiPreference("feedVisible") !== "0", false, false);
setTranscriptTall(uiPreference("feedTall") === "1", false, false);
$("layoutPreset").value = uiPreference("layoutPreset") || "custom";
connect();
