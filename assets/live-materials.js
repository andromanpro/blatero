/* Meeting material inbox. No capture or cloud request starts automatically. */
(() => {
  const byId = id => document.getElementById(id);
  const dialog = document.createElement("dialog");
  dialog.id = "liveMaterialsDialog";
  dialog.className = "live-material-dialog";
  dialog.setAttribute("aria-labelledby", "liveMaterialsTitle");
  dialog.innerHTML = `
    <div class="live-material-head"><h2 id="liveMaterialsTitle">${studioText("Материалы по ходу встречи")}</h2>
      <button type="button" id="liveMaterialsClose" ${studioAttrs("aria-label","Закрыть материалы")}>${studioText("Закрыть")}</button></div>
    <p>${studioText("Добавление материалов не останавливает запись. Файлы сохраняются локально в этой встрече; отправка в ИИ — только после просмотра.")}</p>
    <div id="liveMaterialDrop" class="live-material-drop" tabindex="0" ${studioAttrs("aria-label","Добавить файлы или вставить картинку")}>
      <button type="button" id="liveMaterialChoose">${studioText("＋ Добавить файлы")}</button>
      <button type="button" id="liveMaterialCapture">${studioText("▣ Снимок области")}</button>
      <input id="liveMaterialFiles" type="file" multiple hidden>
      <p>${studioText("Перетащите сюда документы или вставьте картинку: Ctrl+V. До 10 МБ на файл, до 50 материалов на встречу.")}</p>
      <p>${studioText("В подсказки и отчёт включается выжимка последних 12 разобранных материалов, до 18 000 символов. Все результаты доступны ниже.")}</p>
    </div>
    <details><summary>${studioText("Горячие клавиши и новые файлы")}</summary>
      <label>${studioText("Снимок области в активной вкладке Blatero\n        ")}<select id="liveMaterialShortcut"><option value="KeyS">Ctrl+Shift+S</option><option value="KeyX">Ctrl+Shift+X</option><option value="off" ${studioBind('Выключено')}>${esc(studioUi('Выключено'))}</option></select></label>
      <label><input type="checkbox" id="liveMaterialPrint">${studioText(" Обрабатывать Print Screen в активной вкладке Blatero")}</label>
      <p>${studioText("Выключено по умолчанию. За пределами вкладки клавиша работает как обычно; браузер или Windows могут оставить за собой её системное действие.")}</p>
      <label><input type="checkbox" id="liveMaterialWatch">${studioText(" Замечать новые и изменённые файлы рабочей папки")}</label>
      <p>${studioText("Пока открыта вкладка. Проверяется размер и время изменения; новые файлы не отправляются автоматически. Первый опрос запоминает текущий состав папки.")}</p>
    </details>
    <p id="liveMaterialStatus" role="status" aria-live="polite"></p>
    <div id="liveMaterialChanges"></div>
    <section id="liveMaterialCrop" hidden>
      <h3>${studioText("Выделите область мышью или задайте координаты")}</h3>
      <canvas id="liveMaterialCanvas" ${studioAttrs("aria-label","Предпросмотр снимка")}></canvas>
      <div class="live-material-coordinates">
        <label>X, px<input id="liveCropX" type="number" min="0" value="0"></label>
        <label>Y, px<input id="liveCropY" type="number" min="0" value="0"></label>
        <label>${studioText("Ширина")}<input id="liveCropW" type="number" min="1" value="1"></label>
        <label>${studioText("Высота")}<input id="liveCropH" type="number" min="1" value="1"></label>
      </div>
      <button type="button" id="liveCropSave">${studioText("Добавить только выделенную область")}</button>
      <button type="button" id="liveCropCancel">${studioText("Отменить снимок")}</button>
      <p>${studioText("Полный снимок остаётся в памяти браузера. На локальный сервер попадёт только выбранная область. Закрасить лишнее можно при проверке материала.")}</p>
    </section>
    <div id="liveMaterialList"></div>`;
  document.body.append(dialog);
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.id = "liveMaterialsOpen";
  trigger.className = "icon-action";
  setIconAction(trigger, "plus", studioUi("материал"), studioUi("Добавить документ или снимок без остановки записи"));
  byId("preflightQuick")?.parentElement.append(trigger);
  let scope = null, uploading = false, busy = false, watching = false, watchPending = false;
  let imageCanvas = null, selection = null, dragStart = null, capturing = false;
  const currentScope = () => currentInit && ({session:currentInit.current_dir, generation:currentInit.session_generation});
  const same = (a,b) => a && b && a.session === b.session && a.generation === b.generation;
  const message = text => { studioValue(byId("liveMaterialStatus"),text); };
  const notice=(source,values={})=>studioLabel(byId("liveMaterialStatus"),source,values);
  const messageLabels={material_imported:'Файл добавлен локально; откройте проверку.',
    material_analysed:'Анализ готов. Следующие подсказки и отчёт учтут материал.',
    material_busy:'Дождитесь текущей проверки материала.',material_error:'Ошибка обработки материала: {detail}'};
  function resultNotice(result,element=byId('liveMaterialStatus')) {
    if(Object.hasOwn(messageLabels,result.message_code))studioLabel(element,messageLabels[result.message_code],result.message_params||{});
    else studioValue(element,result.text||'');
  }
  const settingsKey = "blatero.material-shortcuts.v1";
  try {
    const prefs = JSON.parse(localStorage.getItem(settingsKey) || "{}");
    byId("liveMaterialPrint").checked = prefs.print === true;
    if (["KeyS", "KeyX", "off"].includes(prefs.shortcut)) byId("liveMaterialShortcut").value = prefs.shortcut;
  } catch { /* Use opt-in defaults if local storage is unavailable. */ }
  function saveSettings() {
    try { localStorage.setItem(settingsKey, JSON.stringify({print:byId("liveMaterialPrint").checked,
      shortcut:byId("liveMaterialShortcut").value})); } catch { notice("Настройки действуют до закрытия вкладки: браузер не разрешил сохранение."); }
  }
  byId("liveMaterialPrint").onchange = saveSettings;
  byId("liveMaterialShortcut").onchange = saveSettings;
  function requireScope() {
    if (!same(scope, currentScope())) throw new Error(studioUi("Встреча сменилась. Откройте материалы заново."));
    return {...scope};
  }
  async function refresh() {
    const expected = requireScope();
    const response = await fetch(`/api/live-materials?${new URLSearchParams(expected)}`);
    if (!response.ok) throw new Error(await response.text());
    const result = await response.json();
    if (!same(expected, currentScope()) || !same(expected, scope)) return;
    const container = byId("liveMaterialList"); container.replaceChildren();
    if (!result.items.length) { studioLabel(container,"Пока нет дополнительных материалов."); return; }
    for (const item of result.items) {
      const card = document.createElement("article"); card.className = "live-material-card";
      const title = document.createElement("h3"); studioValue(title,item.name);
      const info = document.createElement("p");
      studioLabel(info,()=>({source:'{value}',values:{value:`${new Date(item.added_at).toLocaleString(window.BlateroI18n?.locale||"ru-RU")} · ${item.state === "ready" ? studioUi("анализ учтён в контексте") : studioUi("сохранён локально, ещё не проанализирован")}`}}));
      const button = document.createElement("button"); button.type = "button";
      studioLabel(button,()=>({source:"{value}",values:{value:item.state === "ready" ? studioUi("Повторно проверить и проанализировать") : studioUi("Проверить перед анализом")}}));
      button.onclick = () => {
        try { if (busy) throw new Error(studioUi("Дождитесь текущего анализа."));
          send({type:"live_material_prepare", ...requireScope(), batch:item.id});
          busy = true; notice("Локально читаю материал и проверяю данные…");
        } catch(error) { message(error.message); }
      };
      card.append(title, info, button);
      for (const [key, label] of [["new_facts",studioUi("Что нового")],["changed_conclusions",studioUi("Что перепроверить")],["questions",studioUi("Что уточнить сейчас")]]) {
        if (!item.analysis) continue;
        const heading = document.createElement("h4"); studioLabel(heading,label);
        const list = document.createElement("ul");
        for (const value of item.analysis[key] || []) { const li = document.createElement("li"); studioValue(li,value); list.append(li); }
        if (!list.childElementCount) { const li = document.createElement("li"); studioLabel(li,"Нет подтверждённых предложений."); list.append(li); }
        card.append(heading, list);
      }
      container.append(card);
    }
  }
  async function open() {
    if (!currentScope()) return;
    if (!same(scope, currentScope())) { scope = currentScope(); busy = false; watching = false; watchPending = false;
      byId("liveMaterialWatch").checked = false; byId("liveMaterialChanges").replaceChildren(); clearCrop(); }
    if (!dialog.open) dialog.showModal();
    try { await refresh(); } catch(error) { message(error.message); }
  }
  trigger.onclick = open;
  byId("liveMaterialsClose").onclick = () => dialog.close();
  dialog.addEventListener("close", clearCrop);
  byId("liveMaterialChoose").onclick = () => byId("liveMaterialFiles").click();
  async function upload(files) {
    if (uploading) { notice("Дождитесь текущей загрузки."); return; }
    let expected;
    try { expected = requireScope(); } catch(error) { message(error.message); return; }
    uploading = true;
    try {
      for (const file of Array.from(files).slice(0, 50)) {
        if (!same(expected, currentScope())) throw new Error(studioUi("Встреча сменилась. Загрузка остановлена."));
        if (file.size > 10 * 1024 * 1024) throw new Error(studioUi("{p0}: файл больше 10 МБ",{p0:file.name}));
        notice("Сохраняю локально: {p0}…",{p0:file.name});
        const response = await fetch(`/api/live-materials/upload?${new URLSearchParams({...expected, name:file.name})}`,
          {method:"POST", headers:{"Content-Type":"application/octet-stream"}, body:file});
        if (!response.ok) throw new Error(await response.text());
      }
      notice("Материалы сохранены локально. Нажмите «Проверить перед анализом» у нужного файла.");
      await refresh();
    } catch(error) { message(error.message); }
    finally { uploading = false; }
  }
  byId("liveMaterialFiles").onchange = event => { upload(event.target.files); event.target.value = ""; };
  const drop = byId("liveMaterialDrop");
  drop.ondragover = event => event.preventDefault();
  drop.ondrop = event => { event.preventDefault(); upload(event.dataTransfer.files); };
  dialog.addEventListener("paste", event => {
    if (event.target.closest("input,textarea,[contenteditable=true]")) return;
    const files = Array.from(event.clipboardData?.items || []).filter(x => x.kind === "file").map(x => x.getAsFile()).filter(Boolean);
    if (files.length) { event.preventDefault(); upload(files); }
  });
  function clearCrop() {
    if (imageCanvas) { imageCanvas.width = 0; imageCanvas.height = 0; }
    imageCanvas = null; selection = null; dragStart = null;
    const canvas = byId("liveMaterialCanvas"); canvas.width = 0; canvas.height = 0;
    byId("liveMaterialCrop").hidden = true;
  }
  function drawCrop() {
    if (!imageCanvas) return;
    const canvas = byId("liveMaterialCanvas"), ctx = canvas.getContext("2d");
    ctx.drawImage(imageCanvas, 0, 0);
    if (selection) { ctx.strokeStyle = "#00d9f5"; ctx.lineWidth = Math.max(2,canvas.width/500);
      ctx.strokeRect(selection.x, selection.y, selection.w, selection.h); }
  }
  async function capture() {
    if (capturing) return;
    capturing = true;
    let stream, video;
    try {
      if (!navigator.mediaDevices?.getDisplayMedia) throw new Error(studioUi("Захват недоступен в этом браузере. Сделайте снимок средствами Windows и вставьте Ctrl+V."));
      // Invoke during the click/key event, before any asynchronous work.
      const pending = navigator.mediaDevices.getDisplayMedia({video:true, audio:false});
      const expected = currentScope();
      open();
      clearCrop();
      stream = await pending;
      if (!same(expected, currentScope()) || !dialog.open) throw new Error(studioUi("Снимок отменён: окно закрыто или встреча сменилась."));
      video = document.createElement("video"); video.muted = true; video.srcObject = stream;
      await video.play();
      if (!same(expected, currentScope()) || !dialog.open) throw new Error(studioUi("Снимок отменён: встреча сменилась или окно закрыто."));
      if (!video.videoWidth || video.videoWidth * video.videoHeight > 20000000) throw new Error(studioUi("Слишком большой снимок. Выберите отдельное окно."));
      imageCanvas = document.createElement("canvas"); imageCanvas.width = video.videoWidth; imageCanvas.height = video.videoHeight;
      imageCanvas.getContext("2d").drawImage(video,0,0);
      const canvas = byId("liveMaterialCanvas"); canvas.width = imageCanvas.width; canvas.height = imageCanvas.height;
      selection = null; byId("liveCropSave").disabled = true;
      byId("liveMaterialCrop").hidden = false;
      drawCrop(); notice("Выделите область. На сервер пока ничего не отправлено.");
    } catch(error) { notice(()=>({source:"{value}",values:{value:error.name === "NotAllowedError" ? studioUi("Захват отменён или не разрешён. Можно вставить готовый снимок через Ctrl+V.") : error.message}})); }
    finally { stream?.getTracks().forEach(track => track.stop()); if (video) video.srcObject = null; capturing = false; }
  }
  const canvas = byId("liveMaterialCanvas");
  const point = event => { const rect = canvas.getBoundingClientRect(); return {
    x:Math.max(0,Math.min(canvas.width,Math.round((event.clientX-rect.left)*canvas.width/rect.width))),
    y:Math.max(0,Math.min(canvas.height,Math.round((event.clientY-rect.top)*canvas.height/rect.height)))}; };
  function updateCoordinates() {
    for (const [id,key] of [["X","x"],["Y","y"],["W","w"],["H","h"]]) byId(`liveCrop${id}`).value = selection[key];
    byId("liveCropSave").disabled = !selection.w || !selection.h; drawCrop();
  }
  canvas.onpointerdown = event => { if (!imageCanvas) return; dragStart = point(event); canvas.setPointerCapture(event.pointerId); };
  canvas.onpointermove = event => { if (!dragStart) return; const end = point(event);
    selection = {x:Math.min(dragStart.x,end.x), y:Math.min(dragStart.y,end.y),w:Math.abs(end.x-dragStart.x),h:Math.abs(end.y-dragStart.y)};
    updateCoordinates(); };
  canvas.onpointerup = canvas.onpointercancel = () => { dragStart = null; };
  for (const id of ["X","Y","W","H"]) byId(`liveCrop${id}`).oninput = () => {
    if (!imageCanvas) return;
    selection = {x:Number(byId("liveCropX").value),y:Number(byId("liveCropY").value),w:Number(byId("liveCropW").value),h:Number(byId("liveCropH").value)};
    byId("liveCropSave").disabled = !(Object.values(selection).every(Number.isInteger) && selection.x >= 0 && selection.y >= 0 && selection.w > 0 && selection.h > 0 && selection.x+selection.w <= canvas.width && selection.y+selection.h <= canvas.height);
    drawCrop();
  };
  byId("liveCropCancel").onclick = clearCrop;
  byId("liveCropSave").onclick = async () => {
    if (!selection || !imageCanvas || byId("liveCropSave").disabled) return;
    const expected = {...scope};
    const cropped = document.createElement("canvas"); cropped.width=selection.w; cropped.height=selection.h;
    cropped.getContext("2d").drawImage(imageCanvas,selection.x,selection.y,selection.w,selection.h,0,0,selection.w,selection.h);
    const blob = await new Promise(resolve => cropped.toBlob(resolve,"image/png"));
    cropped.width = cropped.height = 0; clearCrop();
    if (!same(expected, currentScope()) || !same(expected, scope)) { notice("Встреча сменилась; снимок не добавлен."); return; }
    if (blob) await upload([new File([blob], `screenshot-${Date.now()}.png`, {type:"image/png"})]);
  };
  byId("liveMaterialCapture").onclick = capture;
  document.addEventListener("keydown", event => {
    if (event.repeat || event.target.closest("input,textarea,select,[contenteditable=true]")) return;
    const selected = byId("liveMaterialShortcut").value;
    const matches = (event.ctrlKey && event.shiftKey && !event.altKey && event.code === selected)
      || (byId("liveMaterialPrint").checked && event.code === "PrintScreen" && !event.ctrlKey && !event.altKey && !event.metaKey);
    if (matches && currentScope()) { event.preventDefault(); event.stopImmediatePropagation(); capture(); }
  }, true);
  function pollFolder() {
    if (!watching || busy || watchPending || document.hidden) return;
    try { send({type:"live_material_watch", ...requireScope()}); watchPending = true; }
    catch(error) { watching = false; byId("liveMaterialWatch").checked = false; message(error.message); }
  }
  byId("liveMaterialWatch").onchange = event => { watching = event.target.checked; pollFolder(); };
  setInterval(pollFolder, 15000);
  window.addEventListener("blatero-material-review", () => { busy=false; if(dialog.open) dialog.close(); });
  window.addEventListener("blatero-material", async event => {
    const result = event.detail;
    if (!same(result, currentScope()) || !same(result, scope)) return;
    watchPending = false;
    if (result.type === "live_material_changes") {
      const container = byId("liveMaterialChanges"); container.replaceChildren();
      for (const item of result.changes) {
        const button = document.createElement("button"); button.type="button";
        studioLabel(button,()=>({source:"{value}",values:{value:studioUi("{p0}: {p1} — добавить",{p0:item.change === "new" ? studioUi("Новый") : studioUi("Изменён"),p1:item.path})}}));
        button.onclick = () => { send({type:"live_material_import",...requireScope(),path:item.path}); busy=true; };
        container.append(button);
      }
      notice(()=>({source:"{value}",values:{value:result.count ? studioUi("Новых или изменённых файлов: {p0}. Добавьте нужные для проверки.",{p0:result.count})
        : studioUi("Проверено файлов: {p0}. Новых изменений нет.{p1}",{p0:result.files,p1:result.limited ? studioUi(" Охват папки ограничен.") : ""})}}));
      setIconAction(trigger,'plus',studioUi("материал"),studioUi("Добавить документ или снимок без остановки записи"),result.count||'');
      return;
    }
    busy=false;
    resultNotice(result);
    if (result.type === "live_material_error" && workspacePrivacyReview?.live_batch) {
      resultNotice(result,byId('workspacePrivacyStatus'));
      byId("workspacePrivacyRecheck").disabled = false;
    }
    if (result.type === "live_material_done") {
      const reopen = dialog.open || (workspacePrivacyReview?.live_batch && byId("workspacePrivacyOverlay").classList.contains("show"));
      if (workspacePrivacyReview?.live_batch) { byId("workspacePrivacyOverlay").classList.remove("show"); workspacePrivacyReview=null; }
      if (reopen) await open();
      else setIconAction(trigger,'plus',studioUi("материал · готово"),studioUi("Добавить документ или снимок без остановки записи"));
      resultNotice(result);
    }
  });
})();
