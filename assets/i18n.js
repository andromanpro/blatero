'use strict';
// Translate owned UI labels only. Meeting text, paths, names and reports are never translated.
(() => {
  const catalog = {
    today: ['Сегодня', 'Today'], meetings: ['Встречи', 'Meetings'], projects: ['Проекты', 'Projects'],
    planning: ['План', 'Plan'], materials: ['Материалы', 'Materials'], library: ['Библиотека', 'Library'],
    archive: ['Архив', 'Archive'], help: ['Помощь', 'Help'], close: ['Закрыть', 'Close'],
    navPrevious: ['Предыдущие разделы', 'Previous sections'], navNext: ['Следующие разделы', 'More sections'],
    cloudPermissionScope: ['Снятие разрешения блокирует новые облачные операции, но не отменяет уже отправленные запросы и активный поток SpeechKit. Для прекращения этого потока остановите запись или переключитесь на локальное распознавание; дождитесь завершения хвоста.',
      'Withdrawing permission blocks new cloud operations, but does not cancel requests already sent or an active SpeechKit stream. To end that stream, stop recording or switch to local recognition, then wait for pending audio to finish.'],
    appearance: ['Настройки', 'Settings'], theme: ['Тема', 'Theme'],
    motion: ['Анимация', 'Animation'], language: ['Язык интерфейса', 'Interface language'],
    localeNote: ['Язык интерфейса не меняет язык встречи, распознавания или подсказок.',
      'Interface language does not change the meeting, transcription or AI response language.'],
    preview: ['RU/EN меняет подписи интерфейса и справку. Документы и ответы ИИ не переводятся; технические ошибки могут остаться на исходном языке.',
      'RU/EN changes interface labels and help. Documents and AI responses are not translated; technical errors may retain their original language.'],
    connections: ['Интеграции', 'Connections'],
    independent: ['Blatero работает самостоятельно. Подключения выключены, пока вы их не включите.',
      'Blatero works on its own. Connections stay off until you enable them.'],
    neon: ['Neon Legion — расходы ИИ', 'Neon Legion — AI usage'],
    granka: ['Гранка — статьи и план публикаций', 'Granka — articles and publishing plan'],
    connectionScope: ['Только локальное чтение. Источники не изменяются. Отключение сохраняет прежние связи и снимки.',
      'Read-only local access. Sources are not modified. Disabling keeps existing links and snapshots.'],
    save: ['Сохранить', 'Save'], loading: ['Загрузка…', 'Loading…'], saved: ['Сохранено', 'Saved'],
    failed: ['Не удалось сохранить. Обновите раздел и повторите.', 'Could not save. Reload this section and try again.'],
    loadFailed: ['Не удалось прочитать настройки подключений.', 'Could not load connection settings.'],
    noConnection: ['Отключено', 'Disabled'], onConnection: ['Включено', 'Enabled'],
    otherApps: ['Другие приложения', 'Other apps'],
    appsTitle: ['Можно использовать вместе', 'Works well alongside'],
    appsNote: ['Это отдельные приложения, не обязательные компоненты Blatero. Открытие ссылки не включает интеграцию.',
      'These are separate apps, not required Blatero components. Opening a link does not enable a connection.'],
    neonAbout: ['Neon Legion собирает локальные журналы использования ИИ. В Blatero можно сопоставить их со связанными задачами. Оценка API не равна оплате подписки.',
      'Neon Legion reads local AI usage logs. Blatero can match them to linked tasks. API-equivalent cost is not your subscription bill.'],
    grankaAbout: ['Гранка — локальный редактор статей с замечаниями ИИ, версиями и публикацией. Blatero может читать её материалы и даты публикаций; редактор остаётся в Гранке.',
      'Granka is a local article editor with AI feedback, versions and publishing. Blatero can read its materials and publishing dates; editing stays in Granka.'],
    motiveliumAbout: ['Мотивелиум — отдельный инструмент для работы с роликами. Прямого обмена с Blatero пока нет; устанавливать его для встреч не нужно.',
      'Motivelium is a separate tool for video work. There is no direct Blatero connector yet; meetings do not require it.'],
    learn: ['О проекте ↗', 'Learn more ↗'], setup: ['Настройки → Интеграции. Подключение включается отдельно от установки приложения.',
      'Settings → Connections. Installing an app does not enable its connection.'],
    guideMeetings: ['Провести встречу', 'Run a meeting'], guideProjects: ['Вести задачи', 'Manage tasks'],
    guideMemory: ['План и закрепление', 'Plan and recall'],
    guideAbout: ['О программе', 'About'],
    guideAuthor: ['Автор', 'By'],
    guideCodeLicense: ['Код Blatero — MIT.', 'Blatero code is MIT-licensed.'],
    guideTitle: ['Как пользоваться Blatero', 'Getting started with Blatero'],
    guideIntro: ['Выберите короткий маршрут. Задачи и знания доступны без записи встречи.',
      'Choose a quick guide. Tasks and knowledge work without recording a meeting.'],
    guideKicker: ['РАБОЧЕЕ ПРОСТРАНСТВО', 'WORKSPACE'],
    tourInvite: ['Впервые здесь? За пять шагов найдите основные кнопки встречи.',
      'New here? Find the main meeting controls in five steps.'],
    tourStart: ['Показать на экране', 'Show me around'],
    tourBusy: ['Тур доступен после остановки записи.', 'The tour is available after you stop recording.'],
    tourExit: ['Выйти из тура', 'Exit tour'], tourBack: ['Назад', 'Back'],
    guideMeetTitle: ['Встреча: от подготовки до отчёта', 'Meeting: preparation to report'],
    guideMeet1: ['Создайте встречу: выберите проект, задачи, тему и время. Материалы добавляйте по необходимости.',
      'Create a meeting: choose a project, tasks, topic and time. Add materials if needed.'],
    guideMeet2: ['Откройте проверку звука, нажмите старт и говорите после сигнала. Проверьте микрофон и звук встречи.',
      'Open the audio check, press Start and speak after the cue. Check both the microphone and meeting audio.'],
    guideMeet3: ['Начните запись. Подсказки можно запросить вручную; закреплённые карточки остаются на экране.',
      'Start recording. Request a hint when needed; pinned cards stay on screen.'],
    guideMeet4: ['Остановите запись и создайте отчёт. Проверьте выводы перед сохранением договорённостей в память.',
      'Stop recording and create a report. Review conclusions before saving agreements to memory.'],
    guideTasksTitle: ['Задачи и решения', 'Tasks and decisions'],
    guideTasksText: ['Создайте проект и задачу. Запишите цель, метод, причину и следующий шаг. Статус «На проверке» не означает приёмку: завершение подтверждает владелец.',
      'Create a project and task. Record the goal, method, rationale and next step. Review is not acceptance: the owner confirms completion.'],
    guidePlanTitle: ['План и библиотека', 'Plan and library'],
    guidePlanText: ['В плане объединены встречи и сроки задач. Библиотека сохраняет источники и основания решений. Предложения требуют подтверждения; изменившийся источник требует перепроверки.',
      'The plan combines meetings and task deadlines. The library keeps sources and decision rationale. Proposals need confirmation; changed sources need rechecking.'],
    board: ['Доска', 'Board'], list: ['Список', 'List'], recall: ['Вспомнить', 'Recall'],
    efficiency: ['Эффективность', 'AI usage'], merge: ['Сравнение', 'Compare'], closed: ['Закрытые', 'Closed'],
    inbox: ['Входящие', 'Inbox'], active: ['В работе', 'In progress'], waiting: ['Ожидает', 'Waiting'],
    review: ['На проверке', 'Review'], done: ['Завершено', 'Done'], newProject: ['Новый проект', 'New project']
  };
  let language = 'ru';
  try { language = localStorage.getItem('blatero.ui.language') === 'en' ? 'en' : 'ru'; } catch {}
  function t(key, params={}) {
    const value=catalog[key]?.[language === 'en' ? 1 : 0] ?? catalog[key]?.[0] ?? key;
    return String(value).replace(/\{([a-zA-Z_]\w*)\}/g,
      (match,name)=>Object.hasOwn(params,name)?String(params[name]):match);
  }
  function register(entries) {
    for(const [key,pair] of Object.entries(entries)) {
      if(!/^[a-z][a-zA-Z0-9._-]+$/.test(key)||!Array.isArray(pair)||pair.length!==2||pair.some(v=>typeof v!=='string'))
        throw Error('Invalid interface catalog entry');
      if(Object.hasOwn(catalog,key)&&JSON.stringify(catalog[key])!==JSON.stringify(pair))
        throw Error('Conflicting interface catalog entry: '+key);
      catalog[key]=pair;
    }
    apply();
  }
  function apply(scope=document) {
    document.documentElement.lang = language;
    // Preview keeps untranslated Russian screens labelled correctly for screen readers.
    if (document.body) document.body.lang = 'ru';
    // A still-running older page can load newer assets. Keep its fallback text
    // until the feature catalog is available; never display an untranslated key.
    scope.querySelectorAll('[data-i18n]').forEach(el => {
      if (Object.hasOwn(catalog,el.dataset.i18n)) { el.textContent = t(el.dataset.i18n); el.lang = language; }
    });
    scope.querySelectorAll('[data-i18n-title]').forEach(el => {
      if (Object.hasOwn(catalog,el.dataset.i18nTitle)) el.title = t(el.dataset.i18nTitle);
    });
    scope.querySelectorAll('[data-i18n-aria]').forEach(el => {
      if (Object.hasOwn(catalog,el.dataset.i18nAria)) el.setAttribute('aria-label', t(el.dataset.i18nAria));
    });
    scope.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      if (Object.hasOwn(catalog,el.dataset.i18nPlaceholder)) el.placeholder = t(el.dataset.i18nPlaceholder);
    });
  }
  function setLanguage(value) {
    language = value === 'en' ? 'en' : 'ru';
    try { localStorage.setItem('blatero.ui.language', language); } catch {}
    apply();
    document.dispatchEvent(new CustomEvent('blatero:language', {detail: {language}}));
  }
  window.BlateroI18n = {t, apply, register, setLanguage, get language() { return language; },
    get locale() { return language === 'en' ? 'en-GB' : 'ru-RU'; }};
  window.addEventListener('storage', e => { if (e.key === 'blatero.ui.language') setLanguage(e.newValue); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => apply()); else apply();
})();
