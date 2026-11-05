'use strict';
(() => {
  const i18n = window.BlateroI18n;
  const host = document.querySelector('#settingsInterface') || document.querySelector('.space-appearance-controls');
  const connectionHost = document.querySelector('#settingsConnections') || host;
  if (!host || !i18n) return;
  const section = document.createElement('section');
  section.className = 'workspace-preferences';
  section.innerHTML = `<h4 data-i18n="language"></h4><label><select id="uiLanguage" aria-label="Interface language"><option value="ru">Русский</option><option value="en">English (preview)</option></select></label>
    <p class="quiet" data-i18n="localeNote"></p><p class="quiet" data-i18n="preview"></p>`;
  host.append(section);
  const connectionSection = document.createElement('section');
  connectionSection.className = 'workspace-preferences';
  connectionSection.innerHTML = `<h4 data-i18n="connections"></h4><p data-i18n="independent"></p>
    <form id="optionalConnections"><label><input name="neon" type="checkbox" disabled> <span data-i18n="neon"></span></label>
    <label><input name="granka" type="checkbox" disabled> <span data-i18n="granka"></span></label>
    <p class="quiet" data-i18n="connectionScope"></p><button type="submit" data-i18n="save" disabled></button>
    <span class="quiet" id="connectionStatus" role="status" aria-live="polite"></span></form>`;
  connectionHost.append(connectionSection);
  const selector = section.querySelector('#uiLanguage');
  selector.value = i18n.language;
  selector.onchange = () => i18n.setLanguage(selector.value);
  document.addEventListener('blatero:language', () => {
    selector.value = i18n.language; section.lang = connectionSection.lang = i18n.language; i18n.apply(section);
  });
  section.lang = connectionSection.lang = i18n.language;
  i18n.apply(section);
  i18n.apply(connectionSection);
  const form = connectionSection.querySelector('form'), status = connectionSection.querySelector('#connectionStatus');
  let revision;
  async function load() {
    try {
      const response = await fetch('/api/projects/connections', {cache:'no-store'});
      if (!response.ok) throw Error();
      const data = await response.json(); revision = data.revision;
      for (const key of ['neon','granka']) { form.elements[key].checked = data.enabled[key]; form.elements[key].disabled = false; }
      form.querySelector('button').disabled = false; status.textContent = '';
    } catch { status.textContent = i18n.t('loadFailed'); }
  }
  form.onsubmit = async event => {
    event.preventDefault();
    form.querySelector('button').disabled = true; status.textContent = i18n.t('loading');
    for(const input of form.querySelectorAll('input')) input.disabled = true;
    try {
      const response = await fetch('/api/projects/connections', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({revision,enabled:{neon:form.elements.neon.checked,granka:form.elements.granka.checked}})});
      if (!response.ok) throw Error();
      const data = await response.json(); revision = data.revision;
      status.textContent = i18n.t('saved');
    } catch { await load(); status.textContent = i18n.t('failed'); }
    finally {
      form.querySelector('button').disabled = revision === undefined;
      for(const input of form.querySelectorAll('input')) input.disabled = revision === undefined;
    }
  };
  load();
})();
