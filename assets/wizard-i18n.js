'use strict';
// Owned interface copy only. User names, paths, goals and file contents stay intact.
(() => {
  const entries = /* WIZARD_ENTRIES */ {
    "wizard.title": ["Подготовка новой встречи", "Prepare a new meeting"],
    "wizard.close": ["закрыть", "close"],
    "wizard.lead": ["Мастер создаст отдельную сессию, сохранит цель встречи, проверит локальную папку проекта и — по вашему выбору — подготовит контекст и вопросы. Запись начнётся только после отдельной кнопки «начать запись».", "Create a separate session with a meeting goal and project folder. AI preparation is optional. Recording starts only when you press Start recording."],
    "wizard.environment": ["Контур данных", "Data environment"],
    "wizard.environmentHint": ["Рабочие встречи и тестовые прогоны показываются отдельно.", "Work meetings and test runs are shown separately."],
    "wizard.environmentAria": ["Контур новой встречи", "New meeting environment"],
    "wizard.work": ["рабочий", "work"],
    "wizard.test": ["тестовый", "test"],
    "wizard.progress": ["Этапы подготовки встречи", "Meeting preparation steps"],
    "wizard.step1": ["1 · формат", "1 · format"],
    "wizard.step2": ["2 · цель", "2 · goal"],
    "wizard.step3": ["3 · материалы", "3 · materials"],
    "wizard.step4": ["4 · проверка", "4 · review"],
    "wizard.roleTitle": ["Как вы участвуете?", "What is your role?"],
    "wizard.roleHelp": ["Формат определяет роль подсказок, сценарий вопросов, режим эмуляции и структуру отчёта.", "The format determines the hints, question plan, simulation role and report structure."],
    "wizard.roleAria": ["Формат новой встречи", "New meeting format"],
    "wizard.chooseRole": ["Выберите формат встречи.", "Choose a meeting format."],
    "wizard.goalTitle": ["Кого или что готовим?", "Who or what is this meeting about?"],
    "wizard.goalHelp": ["Для интервью укажите кандидата и фокус проверки; для консалтинга — клиента, проблему и ожидаемый результат разговора.", "For an interview, enter the candidate and assessment focus. For consulting, enter the client, problem and expected outcome."],
    "wizard.name": ["Название / участник", "Title / participant"],
    "wizard.nameExample": ["Александр · разработчик 1С", "Alex · 1C developer"],
    "wizard.duration": ["Длительность", "Duration"],
    "wizard.unlimited": ["без лимита", "no time limit"],
    "wizard.minutes30": ["30 минут", "30 minutes"],
    "wizard.minutes45": ["45 минут", "45 minutes"],
    "wizard.minutes60": ["60 минут", "60 minutes"],
    "wizard.minutes90": ["90 минут", "90 minutes"],
    "wizard.client": ["Клиент / компания", "Client / company"],
    "wizard.optional": ["необязательно", "optional"],
    "wizard.project": ["Название проекта", "Project name"],
    "wizard.projectExample": ["необязательно · иначе имя папки", "optional · otherwise the folder name"],
    "wizard.brief": ["Цель, роль и темы", "Goal, role and topics"],
    "wizard.briefExample": ["Что нужно выяснить, проверить или решить? Какие темы обязательны?", "What should be clarified, checked or decided? Which topics must be covered?"],
    "wizard.folderTitle": ["Рабочая папка проекта", "Project folder"],
    "wizard.folderHelp": ["Укажите абсолютный путь к локальной папке с кодом и материалами.", "Enter the absolute path to a local folder containing code and materials."],
    "wizard.path": ["Путь", "Path"],
    "wizard.aiPrepare": ["После создания запустить ИИ-подготовку", "Run AI preparation after creating the meeting"],
    "wizard.aiScope": ["Сначала выполняется локальный отбор. В LLM уйдут только ограниченные текстовые фрагменты без файлов секретов; при пустой папке вызова LLM не будет.", "Files are selected locally first. Only limited text excerpts are sent to the model; secret files are excluded. An empty folder does not trigger an AI request."],
    "wizard.browse": ["выбрать папку…", "choose folder…"],
    "wizard.checkPath": ["проверить введённый путь", "check this path"],
    "wizard.folderUnchecked": ["Папка ещё не проверена. Её можно оставить пустой и подготовить встречу вручную.", "The folder has not been checked. You can leave it blank and prepare the meeting manually."],
    "wizard.reviewTitle": ["Проверка перед созданием", "Review before creating"],
    "wizard.reviewHelp": ["После создания откроется новая сессия. Проверьте звук отдельно, затем нажмите «начать запись».", "A new session will open. Check the audio separately, then press Start recording."],
    "wizard.configureAi": ["настроить подключение к ИИ", "configure AI access"],
    "wizard.configurePrivacy": ["проверить согласие и приватность", "review consent and privacy"],
    "wizard.withoutAi": ["создать без ИИ-подготовки", "create without AI preparation"],
    "wizard.back": ["назад", "back"],
    "wizard.stepStatus": ["Шаг {step} из {total}", "Step {step} of {total}"],
    "wizard.next": ["продолжить", "continue"],
    "wizard.nextGoal": ["дальше: цель", "next: goal"],
    "wizard.nextMaterials": ["дальше: материалы", "next: materials"],
    "wizard.nextReview": ["дальше: проверка", "next: review"],
    "wizard.createPrepare": ["создать и подготовить", "create and prepare"],
    "wizard.create": ["создать встречу", "create meeting"],
    "wizard.trainingHelp": ["Укажите профессию или должность. В поле материалов можно вставить резюме, вакансию, публичную HTTPS-ссылку и любые заметки.", "Enter a profession or job title. Add a CV, job description, public HTTPS link or notes to the materials field."],
    "wizard.trainingName": ["Название / целевая роль", "Title / target role"],
    "wizard.trainingBrief": ["Резюме, вакансия, ссылки и любой контекст", "CV, job description, links and context"],
    "wizard.trainingExample": ["Вставьте текст резюме, описание вакансии, HTTPS-ссылку или любые заметки.", "Paste a CV, job description, HTTPS link or notes."],
    "wizard.testHint": ["Тестовый прогон не появится среди рабочих интервью и отчётов.", "The test run will not appear among work interviews and reports."],
    "wizard.workHint": ["Рабочая встреча хранится отдельно от тренировочных прогонов.", "Work meetings are stored separately from practice runs."],
    "wizard.folderInterview": ["Папка присланного тестового задания или репозитория кандидата.", "Folder containing the candidate’s assignment or repository."],
    "wizard.folderCandidate": ["Папка вашего проекта: ИИ подготовит вероятные вопросы о коде и корректные ответы.", "Your project folder: AI will prepare likely code questions and correct answers."],
    "wizard.folderTraining": ["Необязательно: папка вашего проекта или портфолио добавит вопросы по реальным материалам.", "Optional: add your project or portfolio folder for questions based on those materials."],
    "wizard.folderConsulting": ["Папка проекта или системы клиента: ИИ подготовит discovery-вопросы и карту пробелов.", "Client project or system folder: AI will prepare discovery questions and identify gaps."],
    "wizard.folderMeeting": ["Папка с материалами и кодом, относящимися к встрече.", "Folder containing materials and code relevant to the meeting."],
    "wizard.roleInterviewer": ["Я интервьюирую", "I interview"],
    "wizard.roleCandidate": ["Я прохожу собеседование", "I am the candidate"],
    "wizard.roleTraining": ["Тренировка собеседования", "Interview practice"],
    "wizard.roleConsulting": ["Консалтинг с клиентом", "Client consulting"],
    "wizard.roleMeeting": ["Другая встреча", "Other meeting"],
    "wizard.descInterviewer": ["Я задаю вопросы и оцениваю кандидата", "I ask questions and assess the candidate"],
    "wizard.descCandidate": ["Меня спрашивают — нужен быстрый и корректный ответ", "I answer questions and need quick, accurate help"],
    "wizard.descTraining": ["ИИ спрашивает, подсказывает и оценивает как работодатель", "AI asks questions, provides hints and assesses me as an employer"],
    "wizard.descConsulting": ["Выяснять запрос, риски и договорённости", "Clarify needs, risks and agreements"],
    "wizard.descMeeting": ["Нейтральные подсказки и протокол", "Neutral hints and meeting notes"],
    "wizard.summaryEnvironment": ["Контур", "Environment"],
    "wizard.summaryTest": ["Тестовый · изолированный", "Test · isolated"],
    "wizard.summaryWork": ["Рабочий", "Work"],
    "wizard.format": ["Формат", "Format"],
    "wizard.notChosen": ["не выбран", "not selected"],
    "wizard.titleLabel": ["Название", "Title"],
    "wizard.notSet": ["не задано", "not set"],
    "wizard.memory": ["Память", "Memory"],
    "wizard.folderMemory": ["проект по рабочей папке", "project identified by folder"],
    "wizard.noMemory": ["не привязана", "not linked"],
    "wizard.timing": ["Тайминг", "Timing"],
    "wizard.minutes": ["{count} минут", "{count} minutes"],
    "wizard.projectContext": ["Контекст проекта", "Project context"],
    "wizard.aiAnalysis": ["ИИ-анализ", "AI analysis"],
    "wizard.linkOnly": ["только привязать", "link only"],
    "wizard.noFolder": ["без папки", "no folder"],
    "wizard.ai": ["ИИ", "AI"],
    "wizard.noLlm": ["LLM не выбран", "No AI provider selected"],
    "wizard.audio": ["Звук", "Audio"],
    "wizard.audioSummary": ["микрофон: {mic}; встреча: {output}", "microphone: {mic}; meeting: {output}"],
    "wizard.ready": ["Можно создавать сессию. После подготовки проверьте звук и нажмите «начать запись».", "The session can be created. Check the audio after preparation, then press Start recording."],
    "wizard.folderChanged": ["Папка изменилась после проверки — вернитесь на шаг 3 и проверьте её снова.", "The folder changed after the check. Return to step 3 and check it again."],
    "wizard.aiRequired": ["Для ИИ-подготовки настройте подключение к ИИ и проверьте соединение. Можно также создать встречу без ИИ-подготовки.", "Configure and check AI access before AI preparation, or create the meeting without it."],
    "wizard.privacyRequired": ["Для ИИ-подготовки подтвердите основание облачной обработки. Можно также создать встречу без ИИ-подготовки.", "Confirm the basis for cloud processing before AI preparation, or create the meeting without it."],
    "wizard.noAiQuestions": ["{message} Сессия создастся без ИИ-вопросов — добавьте материалы или заполните повестку вручную.", "{message} The session will be created without AI questions. Add materials or write the agenda manually."],
    "wizard.emptyPath": ["Рабочая папка не указана. Будет использована только цель встречи и общий сценарий.", "No project folder is selected. Only the meeting goal and general question plan will be used."],
    "wizard.chooseFirst": ["Сначала выберите формат встречи.", "Choose a meeting format first."],
    "wizard.nameRequired": ["укажите название встречи или участника", "enter a meeting title or participant"],
    "wizard.checkFirst": ["Нажмите «проверить папку локально» перед продолжением.", "Check the folder locally before continuing."],
    "wizard.pathChanged": ["Путь изменён. Проверьте папку снова.", "The path changed. Check the folder again."],
    "wizard.browsing": ["Открываю системный диалог выбора папки…", "Opening the system folder picker…"],
    "wizard.picker": ["Выберите папку в системном окне…", "Choose a folder in the system dialog…"],
    "wizard.pickerOpen": ["Диалог выбора папки уже открыт.", "The folder picker is already open."],
    "wizard.pickerCancelled": ["Выбор папки отменён.", "Folder selection cancelled."],
    "wizard.noPath": ["Папка не указана — ИИ использует только цель встречи и общий сценарий.", "No folder selected. AI will use only the meeting goal and general question plan."],
    "wizard.scanning": ["Локально проверяю состав папки…", "Checking the folder locally…"],
    "wizard.scanFailed": ["Не удалось проверить папку: {detail}", "Could not check the folder: {detail}"],
    "wizard.scan.ready": ["Готово к анализу: {files} файлов, {chars} символов контекста.", "Ready for analysis: {files} files, {chars} characters of context."],
    "wizard.scan.insufficient": ["Файлы найдены, но читаемого контекста недостаточно для надёжного анализа и вопросов.", "Files were found, but there is not enough readable context for reliable analysis and questions."],
    "wizard.scan.empty": ["Не найдено файлов доступных форматов. Поддерживаются DOCX, PDF, XLSX, PPTX, ODT, старые Office через LibreOffice, Draw.io/BPMN/Visio/SVG, PNG/JPEG/BMP/TIFF, тексты и исходный код. Причины пропуска — в списке файлов.", "No supported files found. Supported: DOCX, PDF, XLSX, PPTX, ODT, legacy Office via LibreOffice, Draw.io/BPMN/Visio/SVG, PNG/JPEG/BMP/TIFF, text and source code. See the file list for skipped-file reasons."],
    "wizard.scan.skipped": ["Исключено при отборе: {count}.", "Excluded during selection: {count}."],
    "wizard.scan.readErrors": ["Не прочитано файлов: {count}. {detail}", "Files not read: {count}. {detail}"],
    "wizard.fileCount": [" · файлов: {count}", " · files: {count}"],
    "wizard.charCount": [" · {count} символов", " · {count} characters"],
    "wizard.redactions": [" · скрыто чувствительных фрагментов: {count}", " · sensitive fragments redacted: {count}"],
    "wizard.limited": [" · материал прочитан не полностью: достигнут лимит", " · material partially read: size limit reached"],
    "wizard.materialCount": ["Состав материалов: прочитано {read}, пропущено {skipped}", "Materials: {read} read, {skipped} skipped"],
    "wizard.fileDetails": ["{path} — {method}, {chars} символов{suffix}", "{path} — {method}, {chars} characters{suffix}"],
    "wizard.fragment": [", фрагмент", ", excerpt"],
    "wizard.text": ["текст", "text"],
    "wizard.skippedFile": ["{path} — пропущен: {reason}", "{path} — skipped: {reason}"],
    "wizard.moreFiles": ["Ещё {count} файлов; сузьте выбранную папку для подробного просмотра.", "{count} more files. Choose a smaller folder to inspect them."],
    "wizard.unknownFolder": ["Состояние рабочей папки неизвестно.", "Project folder status is unknown."],
    "wizard.extraction": ["Из документов извлекается текст, из схем — доступная структура; из отдельных изображений — надписи через локальный OCR. Встроенные картинки не анализируются. Визуально проверить смысл схем и фотографий можно отдельно перед отправкой. PDF-сканы без текстового слоя нужно сохранить как отдельные изображения.", "Text is extracted from documents, available structure from diagrams, and text from separate images using local OCR. Embedded images are not analyzed. You can review diagrams and photos visually before sending. Save scanned PDF pages without text as separate images."],
    "quick.title": ["Подготовить встречу", "Prepare a meeting"],
    "quick.oldTitle": ["Новая встреча за один шаг", "New meeting in one step"],
    "quick.close": ["Закрыть", "Close"],
    "quick.topic": ["Тема встречи", "Meeting topic"],
    "quick.topicExample": ["Например: запуск печати этикеток", "For example: launching label printing"],
    "quick.workFormat": ["Рабочая встреча", "Work meeting"],
    "quick.consulting": ["Консультация", "Consultation"],
    "quick.interview": ["Я провожу интервью", "I conduct the interview"],
    "quick.goal": ["Что обсудить · необязательно", "Topics to discuss · optional"],
    "quick.linkTask": ["Связать встречу с выбранной задачей", "Link the meeting to the selected task"],
    "quick.oldIntro": ["Создаётся рабочая встреча. Запись и ИИ-подготовка не запускаются. Папку и материалы можно добавить позже.", "Creates a work meeting without recording or AI preparation. Add a folder and materials later."],
    "quick.intro": ["Подготовка локальная: нет записи, вызова ИИ или приглашений во внешний календарь. Для встречи по проекту сначала проверьте найденные источники.", "Preparation is local: no recording, AI request or external calendar invitation. Review the sources found for a project meeting before creating it."],
    "quick.wizard": ["Подробный мастер", "Detailed wizard"],
    "quick.retryLink": ["Повторить только привязку", "Retry linking only"],
    "quick.create": ["Создать и открыть", "Create and open"],
    "quick.project": ["Проект · необязательно", "Project · optional"],
    "quick.noProject": ["Без проекта — только тема", "No project — topic only"],
    "quick.projectHint": ["Выберите проект: подтянем задачи доски, реестр из рабочей папки, материалы и прошлые договорённости. Без проекта доступен простой ввод темы.", "Choose a project to load board tasks, the folder’s task register, materials and previous agreements. Without a project, just enter a topic."],
    "quick.date": ["Дата", "Date"],
    "quick.time": ["Время · по Москве", "Time · Moscow"],
    "quick.minutes": ["Минут", "Minutes"],
    "quick.searchTask": ["Найти задачу", "Find a task"],
    "quick.taskExample": ["Номер или название", "Number or title"],
    "quick.history": ["Показать историю и завершённые задачи", "Show history and completed tasks"],
    "quick.tasks": ["Задачи проекта", "Project tasks"],
    "quick.prepare": ["Подтянуть контекст", "Load context"],
    "quick.context": ["Найденный контекст", "Available context"],
    "quick.more": ["Формат и дополнительная цель · необязательно", "Format and additional goal · optional"],
    "quick.closed": [" · закрыта", " · closed"],
    "quick.done": [" · завершена", " · completed"],
    "quick.selected": ["Выбрано задач: {count}. Подтяните контекст перед созданием.", "Tasks selected: {count}. Load context before creating the meeting."],
    "quick.noTasks": ["Подходящих задач нет. Измените поиск или включите историю. Создать задачу можно в разделе «Проекты».", "No matching tasks. Change the search or include history. Create tasks in Projects."],
    "quick.loadingTasks": ["Читаю задачи проекта…", "Loading project tasks…"],
    "quick.chooseTasks": ["Выберите задачи, дату и время, затем нажмите «Подтянуть контекст».", "Choose tasks, date and time, then press Load context."],
    "quick.needTask": ["Выберите хотя бы одну задачу.", "Choose at least one task."],
    "quick.collecting": ["Локально собираю источники. Исходные файлы не изменяются…", "Collecting sources locally. Original files are not changed…"],
    "quick.preview": ["Подготовлено: задач {tasks}, документов {files}, подтверждённых записей памяти {agreements}, прошлых отчётов {reports}. Папка: {path}", "Prepared context · tasks: {tasks}; documents: {files}; confirmed memory entries: {agreements}; previous reports: {reports}. Folder: {path}"],
    "quick.noPath": ["не задана", "not set"],
    "quick.register": ["Реестр · ", "Task register · "],
    "quick.excerpt": [" · выдержка", " · excerpt"],
    "quick.agreement": ["Договорённость: {text}", "Agreement: {text}"],
    "quick.report": ["Прошлый отчёт: {date} · {title}", "Previous report: {date} · {title}"],
    "quick.review": ["Проверьте подборку. Снимите галочки с лишних или устаревших источников. Создание сохранит повестку, досье и встречу в локальном календаре.", "Review the selection. Uncheck unnecessary or outdated sources. Creating saves the agenda, dossier and meeting in the local calendar."],
    "quick.stopFirst": ["Сначала завершите текущую запись. Новая встреча не переключается во время REC.", "Finish the current recording first. You cannot switch to a new meeting during recording."],
    "quick.button": ["+ новая встреча", "+ new meeting"],
    "quick.buttonHelp": ["Создать по теме или перейти в подробный мастер", "Create by topic or open the detailed wizard"],
    "quick.wizardHelp": ["Пошаговый мастер с материалами и ИИ-подготовкой", "Step-by-step wizard with materials and AI preparation"],
    "quick.linkError": ["Не удалось связать встречу с задачей", "Could not link the meeting to the task"],
    "quick.savedWarning": ["Встреча сохранена. {message}", "Meeting saved. {message}"],
    "quick.linkPending": ["Встреча сохранена, связь пока не восстановлена: {message}", "Meeting saved, but the link has not been restored: {message}"],
    "quick.sourceUnavailable": ["Встреча создана, но её источник пока недоступен", "Meeting created, but its source is not available yet"],
    "quick.createdNotLinked": ["Встреча уже создана и открыта. Привязка не выполнена: {message}", "The meeting is already created and open. Linking failed: {message}"],
    "quick.createdWarning": ["Встреча создана. {message}", "Meeting created. {message}"],
    "quick.createUnknown": ["Создание не подтверждено: {message}. Повторное нажатие безопасно: используется тот же запрос. При изменении источников заново подтяните контекст.", "Creation is not confirmed: {message}. Pressing again reuses the same request. Reload context if the sources have changed."],
    "quick.creating": ["Создаю локально…", "Creating locally…"],
    "quick.timeout": ["Ответ не получен. Проверьте список встреч перед повторным созданием; автоматического повтора нет.", "No response received. Check the meeting list before creating again; there is no automatic retry."],
    "quick.created": ["Встреча создана.", "Meeting created."],
    "quick.topicRequired": ["Укажите тему встречи.", "Enter a meeting topic."],
    "quick.recording": ["Запись идёт. Сначала завершите её.", "Recording is in progress. Stop it first."],
    "quick.disconnected": ["Нет подключения к серверу. Создание не отправлено.", "No server connection. Creation was not sent."],
    "quick.prepareFirst": ["Сначала нажмите «Подтянуть контекст».", "Press Load context first."],
    "quick.saving": ["Сохраняю встречу, повестку и досье…", "Saving the meeting, agenda and dossier…"],
    "quick.loadingTask": ["Читаю задачу…", "Loading task…"],
    "quick.retiredTask": ["Исходная карточка закрыта или объединена. Можно создать встречу по её теме, но связи и статус этой карточки меняться не будут.", "The original task is closed or merged. You can create a meeting about it, but its links and status will not change."],
    "quick.fromTask": ["Тема и цель взяты из задачи. Можно изменить перед созданием.", "The topic and goal come from the task. You can edit them before creating the meeting."]
  };
  const i18n = window.BlateroI18n;
  if (!i18n) return;
  i18n.register(entries);
  const aliases = new Map();
  for (const [key,pair] of Object.entries(entries)) for (const phrase of pair) aliases.set(phrase,key);
  const statuses = new Map();
  const labels = new Map();
  function ui(text,params={}) {
    const key=aliases.get(String(text));
    return key ? i18n.t(key,params) : String(text ?? '').replace(/\{([a-zA-Z_]\w*)\}/g,
      (match,name)=>Object.hasOwn(params,name)?String(params[name]):match);
  }
  function message(data) {
    if(data.error_code==='workspace_scan_failed')return i18n.t('wizard.scanFailed',{detail:data.message});
    const key='wizard.scan.'+data.message_code;
    if (!Object.hasOwn(entries,key)) return ui(data.message || 'Состояние рабочей папки неизвестно.');
    const params=data.message_params || {};
    let text=i18n.t(key,{files:params.files,chars:Number(params.chars || 0).toLocaleString(i18n.locale)});
    if(params.skipped)text+=' '+i18n.t('wizard.scan.skipped',{count:params.skipped});
    if(data.read_errors?.length)text+=' '+i18n.t('wizard.scan.readErrors',{
      count:data.read_errors.length,detail:data.read_errors.map(row=>row.path+': '+row.message).join('; ')});
    return text;
  }
  function remember(id,data) { if(id.startsWith('setup'))statuses.set(id,data); }
  function label(element,text,params={}) {
    labels.set(element,{text,params});
    element.textContent=ui(text,typeof params==='function'?params():params);
    element.lang=!aliases.has(text)&&/[а-яё]/i.test(text)?'ru':i18n.language;
  }
  function bindQuick(host) {
    // Called once, before projects or user values are loaded. Later updates use
    // explicit bindings and never walk task titles, meeting text or input values.
    const walker=document.createTreeWalker(host,NodeFilter.SHOW_TEXT),nodes=[];
    while(walker.nextNode())nodes.push(walker.currentNode);
    for(const node of nodes) {
      const key=aliases.get(node.textContent.trim());
      if(!key)continue;
      if(node.parentElement.tagName==='OPTION') {
        node.parentElement.dataset.i18n=key;
      } else {
        const span=document.createElement('span');span.dataset.i18n=key;
        span.textContent=node.textContent;node.replaceWith(span);
      }
    }
    for(const element of host.querySelectorAll('[title],[aria-label],[placeholder]'))
      for(const [name,target] of [['title','i18nTitle'],['aria-label','i18nAria'],['placeholder','i18nPlaceholder']]) {
        const key=aliases.get(element.getAttribute(name));
        if(key)element.dataset[target]=key;
      }
    host.lang=i18n.language;i18n.apply(host);
  }
  function refresh() {
    const quick=document.getElementById('quickMeetingDialog');if(quick)quick.lang=i18n.language;
    for(const [element,value] of labels) {
      if(!element.isConnected){labels.delete(element);continue;}
      label(element,value.text,value.params);
    }
    const host=document.getElementById('setupOverlay');
    if(!host)return;
    host.lang=i18n.language;
    if(typeof renderSetupCopy !== 'function')return;
    const focused=document.activeElement?.dataset?.mode;
    renderSetupCopy();renderSetupModes();renderContourSwitches();renderSetupStep(false,true);
    for(const [id,data] of statuses)renderWorkspaceStatus(id,data);
    if(focused)queueMicrotask(()=>host.querySelector('[data-mode="'+CSS.escape(focused)+'"]')?.focus());
  }
  window.BlateroWizardI18n={ui,message,remember,label,bindQuick,refresh};
  document.addEventListener('blatero:language',refresh);
  refresh();
})();
