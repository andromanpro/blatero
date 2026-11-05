'use strict';
// Owned settings strings only. Never run this translator over input values,
// device names, meeting names, paths, prompts, reports or documents.
(() => {
  const entries = /* SETTINGS_ENTRIES */ {
  "settings.audit.changes": ["Перейти к изменениям", "Go to changes"],
  "settings.1": [
    "Настройки программы",
    "Application settings"
  ],
  "settings.2": [
    "Подключения, звук и оформление.",
    "Connections, audio and appearance."
  ],
  "settings.3": [
    "Вернуться к встрече ↗",
    "Back to meeting ↗"
  ],
  "settings.4": [
    "Закрыть настройки",
    "Close settings"
  ],
  "settings.5": [
    "Найти настройку",
    "Find a setting"
  ],
  "settings.6": [
    "Найти настройку…",
    "Find a setting…"
  ],
  "settings.7": [
    "Разделы настроек",
    "Settings sections"
  ],
  "settings.8": [
    "Раздел",
    "Section"
  ],
  "settings.9": [
    "На этом компьютере",
    "On this computer"
  ],
  "settings.10": [
    "Общие настройки Blatero.",
    "General Blatero settings."
  ],
  "settings.11": [
    "Параметры встречи →",
    "Meeting settings →"
  ],
  "settings.12": [
    "Помощь",
    "Help"
  ],
  "settings.13": [
    "Готовность к встрече",
    "Ready for the meeting"
  ],
  "settings.14": [
    "Проверьте звук, подключение ИИ и передачу данных.",
    "Check audio, the AI connection and data sharing."
  ],
  "settings.15": [
    "Звук",
    "Audio"
  ],
  "settings.16": [
    "Состояние загружается…",
    "Loading status…"
  ],
  "settings.17": [
    "Настроить звук →",
    "Set up audio →"
  ],
  "settings.18": [
    "ИИ",
    "AI"
  ],
  "settings.19": [
    "Состояние загружается…",
    "Loading status…"
  ],
  "settings.20": [
    "Открыть подключение →",
    "Open connection →"
  ],
  "settings.21": [
    "Данные",
    "Data"
  ],
  "settings.22": [
    "Состояние загружается…",
    "Loading status…"
  ],
  "settings.23": [
    "Передача данных →",
    "Data sharing →"
  ],
  "settings.24": [
    "Перед встречей",
    "Before a meeting"
  ],
  "settings.25": [
    "Проверка попросит произнести фразу и включить звук собеседников.",
    "The check will ask you to speak and play audio from the other participants."
  ],
  "settings.26": [
    "Проверить всё",
    "Check all"
  ],
  "settings.27": [
    "Звук и речь",
    "Audio and speech"
  ],
  "settings.28": [
    "Микрофон",
    "Microphone"
  ],
  "settings.29": [
    "Микрофон",
    "Microphone"
  ],
  "settings.30": [
    "Звук собеседников",
    "Other participants’ audio"
  ],
  "settings.31": [
    "Звук приложения встречи",
    "Meeting application audio"
  ],
  "settings.32": [
    "Распознавание речи",
    "Speech recognition"
  ],
  "settings.33": [
    "Движок распознавания речи",
    "Speech recognition engine"
  ],
  "settings.34": [
    "Применить распознавание",
    "Apply speech recognition"
  ],
  "settings.35": [
    "Проверить микрофон",
    "Check microphone"
  ],
  "settings.36": [
    "Все проверки звука",
    "All audio checks"
  ],
  "settings.37": [
    "Нажмите, когда будете готовы говорить. После отсчёта запишутся 12 секунд — пробу можно прослушать.",
    "Press when you are ready to speak. After the countdown, 12 seconds will be recorded for playback."
  ],
  "settings.38": [
    "Дополнительно: эхо и локальная модель",
    "Advanced: echo and local model"
  ],
  "settings.39": [
    "Локальная модель",
    "Local model"
  ],
  "settings.40": [
    "Локальная модель распознавания",
    "Local speech recognition model"
  ],
  "settings.41": [
    "Очистка эха",
    "Echo cancellation"
  ],
  "settings.42": [
    "Движок очистки эха",
    "Echo cancellation engine"
  ],
  "settings.43": [
    "Убирать акустическое эхо до распознавания",
    "Remove acoustic echo before recognition"
  ],
  "settings.44": [
    "Используется выбранный системный выход. Исходный WAV не меняется.",
    "Uses the selected system output. The original WAV is unchanged."
  ],
  "settings.45": [
    "Убирать текстовые дубли",
    "Remove duplicate text"
  ],
  "settings.46": [
    "Если фраза распознана в обоих каналах, остаётся системная копия. Настройки эха применятся со следующей записи.",
    "If a phrase is recognized in both channels, the system-audio copy is kept. Echo settings apply to the next recording."
  ],
  "settings.47": [
    "Калибровать эхо",
    "Calibrate echo"
  ],
  "settings.48": [
    "Установить WebRTC AEC3",
    "Install WebRTC AEC3"
  ],
  "settings.49": [
    "Проверяю WebRTC AEC3…",
    "Checking WebRTC AEC3…"
  ],
  "settings.50": [
    "Калибровка не запускалась.",
    "Calibration has not been run."
  ],
  "settings.51": [
    "Озвучка и голоса",
    "Speech synthesis and voices"
  ],
  "settings.52": [
    "Голос вопросов",
    "Question voice"
  ],
  "settings.53": [
    "Голос для вопросов",
    "Voice for questions"
  ],
  "settings.54": [
    "Голос эмуляции / резерв",
    "Simulation / backup voice"
  ],
  "settings.55": [
    "Голос эмуляции и резервный голос",
    "Simulation and backup voice"
  ],
  "settings.56": [
    "Проверить голос",
    "Test voice"
  ],
  "settings.57": [
    "Банк голосов",
    "Voice bank"
  ],
  "settings.58": [
    "Микрофон и системный звук разделяются по источнику. Имена из банка голосов применяются после проверки.",
    "Microphone and system audio are separated by source. Voice-bank names are applied after review."
  ],
  "settings.59": [
    "ИИ и подсказки",
    "AI and hints"
  ],
  "settings.60": [
    "Подключение",
    "Connection"
  ],
  "settings.61": [
    "Провайдер LLM",
    "LLM provider"
  ],
  "settings.62": [
    "Где получить доступ ↗",
    "Get access ↗"
  ],
  "settings.63": [
    "API-токен",
    "API token"
  ],
  "settings.64": [
    "API-токен LLM",
    "LLM API token"
  ],
  "settings.65": [
    "Новый токен",
    "New token"
  ],
  "settings.66": [
    "Показать",
    "Show"
  ],
  "settings.67": [
    "Адрес API",
    "API address"
  ],
  "settings.68": [
    "Сохранить подключение",
    "Save connection"
  ],
  "settings.69": [
    "Проверить соединение",
    "Check connection"
  ],
  "settings.70": [
    "Удалить токен",
    "Delete token"
  ],
  "settings.71": [
    "Подключение не проверено.",
    "Connection has not been checked."
  ],
  "settings.72": [
    "Проверка не отправляет материалы встречи.",
    "The check does not send meeting materials."
  ],
  "settings.73": [
    "Когда предлагать подсказки",
    "When to suggest hints"
  ],
  "settings.74": [
    "Автоподсказки",
    "Automatic hints"
  ],
  "settings.75": [
    "Подсказки ИИ-сценки",
    "AI role-play hints"
  ],
  "settings.76": [
    "Маршрут помощника сценки; оценка и остальные операции не переключаются",
    "Role-play assistant route; review and other operations remain unchanged"
  ],
  "settings.77": [
    "Основное подключение",
    "Main connection"
  ],
  "settings.78": [
    "DeepSeek Flash · OpenRouter · платный API",
    "DeepSeek Flash · OpenRouter · paid API"
  ],
  "settings.79": [
    "Дополнительно: модели, вопросы и инструкции",
    "Advanced: models, questions and instructions"
  ],
  "settings.80": [
    "Модель подсказок",
    "Hint model"
  ],
  "settings.81": [
    "Модель для подсказок",
    "Model for hints"
  ],
  "settings.82": [
    "Модель отчёта",
    "Report model"
  ],
  "settings.83": [
    "Модель для отчёта и анализа",
    "Model for reports and analysis"
  ],
  "settings.84": [
    "Стиль вопросов",
    "Question style"
  ],
  "settings.85": [
    "Стиль вопросов",
    "Question style"
  ],
  "settings.86": [
    "Стиль применяется при следующей генерации вопросов.",
    "The style applies to the next question generation."
  ],
  "settings.87": [
    "Системные инструкции",
    "System instructions"
  ],
  "settings.88": [
    "Отчёты",
    "Reports"
  ],
  "settings.89": [
    "Для новых отчётов. Сохранённые документы не меняются.",
    "Applies to new reports. Saved documents are unchanged."
  ],
  "settings.90": [
    "Показывать черновик перед DOCX",
    "Show draft before DOCX"
  ],
  "settings.91": [
    "Выводы можно исправить без повторного запроса к ИИ.",
    "Conclusions can be edited without another AI request."
  ],
  "settings.92": [
    "Добавлять таймкоды и ссылки",
    "Include timestamps and links"
  ],
  "settings.93": [
    "Переходы к моментам записи в evidence.html. По умолчанию выключены.",
    "Links to recording moments in evidence.html. Off by default."
  ],
  "settings.94": [
    "Данные и приватность",
    "Data and privacy"
  ],
  "settings.95": [
    "Текст для ИИ",
    "Text sent to AI"
  ],
  "settings.96": [
    "Режим обработки текста для LLM",
    "LLM text processing mode"
  ],
  "settings.97": [
    "Согласие на облачную обработку получено",
    "Consent for cloud processing has been obtained"
  ],
  "settings.98": [
    "Разрешение общее для программы. Перед новой встречей снимите галочку, если основания нет. Согласие не определяется по речи.",
    "This permission applies to the application. Clear it before a new meeting if consent does not apply. Consent is not inferred from speech."
  ],
  "settings.99": [
    "Локальный Whisper не отправляет аудио. SpeechKit отправляет звук в Яндекс. ИИ получает текст в выбранном режиме обработки.",
    "Local Whisper does not upload audio. SpeechKit sends audio to Yandex. AI receives text according to the selected processing mode."
  ],
  "settings.100": [
    "Хранение и удаление данных →",
    "Data retention and deletion →"
  ],
  "settings.101": [
    "Внешний вид",
    "Appearance"
  ],
  "settings.102": [
    "Предпросмотр применяется сразу. Вид панелей и тема сохраняются в этом браузере; размер текста — в настройках программы.",
    "Preview is immediate. Panel layout and theme are saved in this browser; text size is saved in application settings."
  ],
  "settings.103": [
    "Тема",
    "Theme"
  ],
  "settings.104": [
    "Анимация",
    "Animation"
  ],
  "settings.105": [
    "Размер текста",
    "Text size"
  ],
  "settings.106": [
    "Размер текста",
    "Text size"
  ],
  "settings.107": [
    "Рабочий вид",
    "Workspace layout"
  ],
  "settings.108": [
    "Рабочий вид",
    "Workspace layout"
  ],
  "settings.109": [
    "Текущая настройка",
    "Current layout"
  ],
  "settings.110": [
    "Обычный",
    "Standard"
  ],
  "settings.111": [
    "Только подсказки и звук",
    "Hints and audio only"
  ],
  "settings.112": [
    "Крупная история",
    "Expanded history"
  ],
  "settings.113": [
    "Компоновка панелей",
    "Panel layout"
  ],
  "settings.114": [
    "Ширина сценария",
    "Scenario width"
  ],
  "settings.115": [
    "Ширина сценария",
    "Scenario width"
  ],
  "settings.116": [
    "Видимость рабочих панелей",
    "Workspace panel visibility"
  ],
  "settings.117": [
    "Сценарий справа",
    "Scenario on the right"
  ],
  "settings.118": [
    "История транскрипта",
    "Transcript history"
  ],
  "settings.119": [
    "Крупная история",
    "Expanded history"
  ],
  "settings.120": [
    "Свернуть / показать сценарий",
    "Collapse / show scenario"
  ],
  "settings.121": [
    "Обычный вид",
    "Standard layout"
  ],
  "settings.122": [
    "Практика",
    "Practice"
  ],
  "settings.123": [
    "Выберите, кто спрашивает и отвечает. Новая попытка сохраняется отдельно от рабочих встреч.",
    "Choose who asks and answers. Each attempt is saved separately from work meetings."
  ],
  "settings.124": [
    "Я отвечаю",
    "I answer"
  ],
  "settings.125": [
    "ИИ задаёт вопросы, вы отвечаете в микрофон.",
    "AI asks questions; you answer into the microphone."
  ],
  "settings.126": [
    "Я спрашиваю",
    "I interview"
  ],
  "settings.127": [
    "Вы ведёте интервью, ИИ играет кандидата.",
    "You lead the interview; AI plays the candidate."
  ],
  "settings.128": [
    "Оба ИИ",
    "Both AI"
  ],
  "settings.129": [
    "Два ИИ ведут разговор. Вы разбираете запись.",
    "Two AI participants talk. You review the recording."
  ],
  "settings.130": [
    "Открыть текущую тренировку / мастер",
    "Open current practice / setup"
  ],
  "settings.131": [
    "Эмуляция текущей встречи",
    "Simulate the current meeting"
  ],
  "settings.132": [
    "Голосовой бот отвечает за второго участника в выбранной встрече.",
    "A voice bot responds as the other participant in the selected meeting."
  ],
  "settings.133": [
    "Включить эмуляцию",
    "Enable simulation"
  ],
  "settings.134": [
    "Изменить роль бота →",
    "Change bot role →"
  ],
  "settings.135": [
    "Обслуживание",
    "Maintenance"
  ],
  "settings.136": [
    "Компоненты",
    "Components"
  ],
  "settings.137": [
    "Модели речи, голоса и очистка эха",
    "Speech models, voices and echo cancellation"
  ],
  "settings.138": [
    "Локальные модели",
    "Local models"
  ],
  "settings.139": [
    "Установка и обновления",
    "Installation and updates"
  ],
  "settings.140": [
    "Версия, проверка пакета и откат",
    "Version, package verification and rollback"
  ],
  "settings.141": [
    "Открыть обновления",
    "Open updates"
  ],
  "settings.142": [
    "Диагностика",
    "Diagnostics"
  ],
  "settings.143": [
    "Каналы записи, говорящие и Replay Lab",
    "Recording channels, speakers and Replay Lab"
  ],
  "settings.144": [
    "Разобрать аудио",
    "Analyze audio"
  ],
  "settings.145": [
    "Восстановление и удаление данных",
    "Recovery and data deletion"
  ],
  "settings.146": [
    "Перед удалением показывается список файлов.",
    "A file list is shown before deletion."
  ],
  "settings.147": [
    "Восстановление",
    "Recovery"
  ],
  "settings.148": [
    "Данные встречи",
    "Meeting data"
  ],
  "settings.149": [
    "Очистить результат встречи",
    "Clear meeting results"
  ],
  "settings.150": [
    "Очистка удаляет аудио, транскрипт, подсказки и отчёт. Резюме, досье и сценарий сохраняются.",
    "Clears audio, transcript, hints and report. The résumé, dossier and scenario are kept."
  ],
  "settings.151": [
    "Команды · Ctrl+K",
    "Commands · Ctrl+K"
  ],
  "settings.152": [
    "Завершить Blatero",
    "Quit Blatero"
  ],
  "settings.153": [
    "Параметры встречи",
    "Meeting settings"
  ],
  "settings.154": [
    "Тема встречи",
    "Meeting topic"
  ],
  "settings.155": [
    "Тема встречи",
    "Meeting topic"
  ],
  "settings.156": [
    "Формат и роль",
    "Format and role"
  ],
  "settings.157": [
    "Формат и роль",
    "Format and role"
  ],
  "settings.158": [
    "Длительность, минут",
    "Duration, minutes"
  ],
  "settings.159": [
    "Длительность встречи",
    "Meeting duration"
  ],
  "settings.160": [
    "Без лимита",
    "No time limit"
  ],
  "settings.161": [
    "Клиент / компания",
    "Client / company"
  ],
  "settings.162": [
    "Клиент или компания",
    "Client or company"
  ],
  "settings.163": [
    "Материалы встречи",
    "Meeting materials"
  ],
  "settings.164": [
    "Название проекта",
    "Project name"
  ],
  "settings.165": [
    "Название проекта",
    "Project name"
  ],
  "settings.166": [
    "Рабочая папка",
    "Working folder"
  ],
  "settings.167": [
    "Рабочая папка",
    "Working folder"
  ],
  "settings.168": [
    "Путь к папке проекта",
    "Project folder path"
  ],
  "settings.169": [
    "Рабочая папка не указана.",
    "No working folder selected."
  ],
  "settings.170": [
    "Выбрать папку…",
    "Choose folder…"
  ],
  "settings.171": [
    "Проверить путь",
    "Check path"
  ],
  "settings.172": [
    "Подготовить контекст",
    "Prepare context"
  ],
  "settings.173": [
    "Перед ИИ-подготовкой откроется проверка передаваемых материалов.",
    "You will review the materials to be shared before AI preparation starts."
  ],
  "settings.174": [
    "Участники, эмуляция и контур данных",
    "Participants, simulation and data environment"
  ],
  "settings.175": [
    "Имя в микрофоне",
    "Microphone name"
  ],
  "settings.176": [
    "Подпись микрофона",
    "Microphone label"
  ],
  "settings.177": [
    "Я",
    "Me"
  ],
  "settings.178": [
    "Имя в системном звуке",
    "System-audio name"
  ],
  "settings.179": [
    "Подпись системного звука",
    "System-audio label"
  ],
  "settings.180": [
    "Собеседник",
    "Other participant"
  ],
  "settings.181": [
    "Роль бота",
    "Bot role"
  ],
  "settings.182": [
    "Роль бота в эмуляции",
    "Simulation bot role"
  ],
  "settings.183": [
    "Контур данных",
    "Data environment"
  ],
  "settings.184": [
    "Контур данных",
    "Data environment"
  ],
  "settings.185": [
    "Рабочий",
    "Work"
  ],
  "settings.186": [
    "Тестовый",
    "Test"
  ],
  "settings.187": [
    "Новая встреча",
    "New meeting"
  ],
  "settings.188": [
    "Импорт транскрипта",
    "Import transcript"
  ],
  "settings.189": [
    "Изменений нет",
    "No changes"
  ],
  "settings.190": [
    "Отменить изменения",
    "Discard changes"
  ],
  "settings.191": [
    "Сохранить изменения",
    "Save changes"
  ],
  "settings.dynamic.1": [
    "Обзор",
    "Overview"
  ],
  "settings.dynamic.2": [
    " (недоступно)",
    " (unavailable)"
  ],
  "settings.dynamic.3": [
    "Сохраняю…",
    "Saving…"
  ],
  "settings.dynamic.4": [
    "Несохранённых изменений: {count}",
    "Unsaved changes: {count}"
  ],
  "settings.dynamic.5": [
    "В других разделах есть изменения: {count}",
    "Changes in other sections: {count}"
  ],
  "settings.dynamic.6": [
    "Переключить движок",
    "Switch engine"
  ],
  "settings.dynamic.7": [
    "Применить модель",
    "Apply model"
  ],
  "settings.dynamic.8": [
    ", изменений: {count}",
    ", changes: {count}"
  ],
  "settings.dynamic.9": [
    "Для Codex API-токен не нужен. Для API выберите провайдера.",
    "Codex does not require an API token. Choose a provider to use an API."
  ],
  "settings.dynamic.10": [
    "Адрес сервера задаётся для подключения «Совместимый API».",
    "The server address is used for the Compatible API connection."
  ],
  "settings.dynamic.11": [
    "Успешная проверка сохраняет подключение.",
    "A successful check saves the connection."
  ],
  "settings.dynamic.12": [
    "Токен хранится в Windows Credential Manager. Проверка не отправляет материалы встречи.",
    "The token is stored in Windows Credential Manager. The check does not send meeting materials."
  ],
  "settings.dynamic.13": [
    "Аудио отправляется в Яндекс SpeechKit. Смена движка не прерывает запись.",
    "Audio is sent to Yandex SpeechKit. Switching engines does not interrupt recording."
  ],
  "settings.dynamic.14": [
    "Аудио распознаётся на этом компьютере. Смена движка не прерывает запись.",
    "Audio is recognized on this computer. Switching engines does not interrupt recording."
  ],
  "settings.dynamic.15": [
    "Изменения отменены",
    "Changes discarded"
  ],
  "settings.dynamic.16": [
    "Нет соединения с сервером. Черновик сохранён в этой вкладке.",
    "No server connection. Your draft is kept in this tab."
  ],
  "settings.dynamic.17": [
    "Передавать исходные имена, контакты и другие данные без обезличивания?",
    "Send original names, contact details and other data without redaction?"
  ],
  "settings.dynamic.18": [
    "Переместить встречу в {environment} контур?",
    "Move this meeting to the {environment} environment?"
  ],
  "settings.dynamic.19": [
    "тестовый",
    "test"
  ],
  "settings.dynamic.20": [
    "рабочий",
    "work"
  ],
  "settings.dynamic.21": [
    "Сервер не подтвердил сохранение. Черновик оставлен; проверьте соединение и повторите.",
    "The server has not confirmed the save. Your draft is kept; check the connection before trying again."
  ],
  "settings.dynamic.22": [
    "В настройках есть несохранённые изменения.",
    "Settings have unsaved changes."
  ],
  "settings.dynamic.23": [
    "Сохранить и закрыть",
    "Save and close"
  ],
  "settings.dynamic.24": [
    "Не сохранять",
    "Discard"
  ],
  "settings.dynamic.25": [
    "Продолжить настройку",
    "Keep editing"
  ],
  "settings.dynamic.26": [
    "Сохраните подключение отдельной кнопкой, затем закройте настройки.",
    "Save the connection with its own button, then close settings."
  ],
  "settings.dynamic.27": [
    "Дождитесь подтверждения сохранения.",
    "Wait for save confirmation."
  ],
  "settings.dynamic.28": [
    "Соединение потеряно до подтверждения. Черновик оставлен; после подключения проверьте настройки.",
    "Connection lost before confirmation. Your draft is kept; check the settings after reconnecting."
  ],
  "settings.dynamic.29": [
    "Сохранено сервером",
    "Saved by server"
  ],
  "settings.dynamic.30": [
    "Не сохранено: {message}",
    "Not saved: {message}"
  ],
  "settings.dynamic.31": [
    "SpeechKit · Яндекс",
    "SpeechKit · Yandex"
  ],
  "settings.dynamic.32": [
    "Whisper · локально",
    "Whisper · local"
  ],
  "settings.dynamic.33": [
    "Продолжить тренировку",
    "Continue practice"
  ],
  "settings.dynamic.34": [
    "Подробная настройка тренировки",
    "Advanced practice setup"
  ],
  "settings.dynamic.35": [
    "Имя участника",
    "Participant name"
  ],
  "settings.dynamic.36": [
    "Автовыбор",
    "Automatic selection"
  ],
  "settings.dynamic.37": [
    "Проверка пройдена",
    "Check passed"
  ],
  "settings.dynamic.38": [
    "Проверьте устройства перед встречей",
    "Check devices before the meeting"
  ],
  "settings.dynamic.39": [
    "Доступ не настроен",
    "Access is not configured"
  ],
  "settings.dynamic.40": [
    "Облако разрешено · обезличивание включено",
    "Cloud enabled · text redaction on"
  ],
  "settings.dynamic.41": [
    "Облако разрешено · исходный текст",
    "Cloud enabled · original text"
  ],
  "settings.dynamic.42": [
    "Облачные функции выключены",
    "Cloud features are off"
  ],
  "settings.dynamic.43": [
    "Настройка не найдена. Попробуйте «микрофон», «токен» или «тренировка».",
    "No matching setting. Try microphone, token or practice."
  ],
  "settings.dynamic.44": [
    "Сначала остановите текущую запись.",
    "Stop the current recording first."
  ],
  "settings.dynamic.45": [
    "Создаю тренировку…",
    "Creating practice…"
  ],
  "settings.dynamic.46": [
    "Сначала сохраните или отмените изменения этого раздела.",
    "Save or discard changes in this section first."
  ],
  "settings.dynamic.47": [
    "проверка звука",
    "audio checks"
  ],
  "settings.dynamic.48": [
    "локальные модели",
    "local models"
  ],
  "settings.dynamic.49": [
    "обновления",
    "updates"
  ],
  "settings.dynamic.50": [
    "настройки",
    "settings"
  ],
  "settings.dynamic.51": [
    "Включить эмуляцию",
    "Enable simulation"
  ],
  "settings.dynamic.52": [
    "Выключить эмуляцию",
    "Disable simulation"
  ],
  "settings.dynamic.53": [
    "Показать",
    "Show"
  ],
  "settings.dynamic.54": [
    "Скрыть",
    "Hide"
  ],
  "settings.dynamic.55": [
    "Codex / подписка ChatGPT",
    "Codex / ChatGPT subscription"
  ],
  "settings.dynamic.56": [
    "OpenRouter — единый API",
    "OpenRouter — unified API"
  ],
  "settings.dynamic.57": [
    "Ollama / совместимый API",
    "Ollama / compatible API"
  ],
  "settings.dynamic.58": [
    "Codex CLI найден; авторизация ещё не проверена",
    "Codex CLI found; sign-in has not been checked"
  ],
  "settings.dynamic.59": [
    "Codex CLI не найден",
    "Codex CLI was not found"
  ],
  "settings.dynamic.60": [
    "без токена",
    "without a token"
  ],
  "settings.dynamic.61": [
    "старый git config",
    "legacy git config"
  ],
  "settings.dynamic.62": [
    "модель: Codex по умолчанию",
    "model: Codex default"
  ],
  "settings.dynamic.63": [
    "API-токен (необязательно)",
    "API token (optional)"
  ],
  "settings.dynamic.64": [
    "необязательно для локального сервера",
    "optional for a local server"
  ],
  "settings.dynamic.65": [
    "вставьте новый токен или оставьте пустым",
    "enter a new token or leave blank"
  ],
  "settings.dynamic.66": [
    "API-токен не нужен. Выполните codex login и проверьте соединение.",
    "No API token is needed. Run codex login and check the connection."
  ],
  "settings.dynamic.67": [
    "Укажите доступ и проверьте соединение.",
    "Configure access and check the connection."
  ],
  "settings.dynamic.68": [
    "Провайдер выбран. Настройте доступ и выполните проверку.",
    "Provider selected. Configure access and run a check."
  ],
  "settings.dynamic.69": [
    "Доступ настроен: {source}. Нажмите «проверить соединение».",
    "Access configured: {source}. Press Check connection."
  ],
  "settings.dynamic.70": [
    "источник найден",
    "credential source found"
  ],
  "settings.dynamic.71": [
    "Доступ ещё не настроен. Введите токен и нажмите «проверить соединение».",
    "Access is not configured yet. Enter a token and press Check connection."
  ],
  "settings.dynamic.72": [
    "голоса",
    "voices"
  ],
  "settings.dynamic.73": [
    "локально",
    "local"
  ],
  "settings.dynamic.74": [
    "облако",
    "cloud"
  ],
  "settings.dynamic.75": [
    "локально → облако",
    "local → cloud"
  ],
  "settings.dynamic.76": [
    " · выключено",
    " · disabled"
  ],
  "settings.dynamic.77": [
    "контракт не загружен",
    "contract not loaded"
  ],
  "settings.dynamic.78": [
    "Создайте ключ в OpenRouter → Keys. Один ключ открывает модели разных компаний.",
    "Create a key in OpenRouter → Keys. One key provides access to models from different companies."
  ],
  "settings.dynamic.79": [
    "API-токен не нужен. Установите Codex CLI и один раз выполните codex login.",
    "No API token is needed. Install Codex CLI and run codex login once."
  ],
  "settings.dynamic.80": [
    "Создайте project API key в OpenAI Platform. Подписка ChatGPT не оплачивает API.",
    "Create a project API key in OpenAI Platform. A ChatGPT subscription does not cover API usage."
  ],
  "settings.dynamic.81": [
    "Создайте API key в Anthropic Console. Подписка Claude и API оплачиваются отдельно.",
    "Create an API key in Anthropic Console. Claude subscriptions and API usage are billed separately."
  ],
  "settings.dynamic.82": [
    "Создайте API key в DeepSeek Platform и пополните API-баланс.",
    "Create an API key in DeepSeek Platform and add API credit."
  ],
  "settings.dynamic.83": [
    "Укажите base URL OpenAI-совместимого сервера. Для Ollama обычно http://127.0.0.1:11434/v1; токен необязателен.",
    "Enter the base URL of an OpenAI-compatible server. For Ollama this is usually http://127.0.0.1:11434/v1; a token is optional."
  ],
  "settings.dynamic.84": [
    "авто (системный)",
    "automatic (system default)"
  ],
  "settings.dynamic.85": [
    "выкл",
    "off"
  ],
  "settings.dynamic.86": [
    "по паузам",
    "on pauses"
  ],
  "settings.dynamic.87": [
    "30с",
    "30 s"
  ],
  "settings.dynamic.88": [
    "60с",
    "60 s"
  ],
  "settings.dynamic.89": [
    "90с",
    "90 s"
  ],
  "settings.dynamic.90": [
    "кейсы",
    "cases"
  ],
  "settings.dynamic.91": [
    "классика",
    "classic"
  ],
  "settings.dynamic.92": [
    "микс",
    "mixed"
  ],
  "settings.dynamic.93": [
    "компактный",
    "compact"
  ],
  "settings.dynamic.94": [
    "обычный",
    "standard"
  ],
  "settings.dynamic.95": [
    "крупный",
    "large"
  ],
  "settings.dynamic.96": [
    "очень крупный",
    "extra large"
  ],
  "settings.dynamic.97": [
    "Whisper base — быстрее",
    "Whisper base — faster"
  ],
  "settings.dynamic.98": [
    "Whisper small — точнее",
    "Whisper small — more accurate"
  ],
  "settings.dynamic.99": [
    "Whisper medium — медленнее",
    "Whisper medium — slower"
  ],
  "settings.dynamic.100": [
    "обезличивать текст перед LLM",
    "redact text before sending to LLM"
  ],
  "settings.dynamic.101": [
    "передавать исходный текст",
    "send original text"
  ],
  "settings.dynamic.102": [
    "авто — WebRTC AEC3 → встроенный",
    "automatic — WebRTC AEC3 → built-in"
  ],
  "settings.dynamic.103": [
    "WebRTC AEC3 — с безопасным откатом",
    "WebRTC AEC3 — with safe fallback"
  ],
  "settings.dynamic.104": [
    "встроенный — без внешнего бинарника",
    "built-in — no external binary"
  ],
  "settings.dynamic.105": [
    "мой голос локально, без облака",
    "my voice locally, no cloud"
  ],
  "settings.dynamic.106": [
    "мой голос локально → Яндекс",
    "my voice locally → Yandex"
  ],
  "settings.dynamic.107": [
    "только Яндекс SpeechKit",
    "Yandex SpeechKit only"
  ],
  "settings.dynamic.108": [
    "авто (filipp)",
    "automatic (filipp)"
  ],
  "settings.dynamic.109": [
    "filipp — мужской",
    "filipp — male"
  ],
  "settings.dynamic.110": [
    "alena — женский",
    "alena — female"
  ],
  "settings.dynamic.111": [
    "jane — женский",
    "jane — female"
  ],
  "settings.dynamic.112": [
    "ermil — мужской",
    "ermil — male"
  ],
  "settings.dynamic.113": [
    "zahar — мужской",
    "zahar — male"
  ],
  "settings.dynamic.114": [
    "omazh — женский",
    "omazh — female"
  ],
  "settings.dynamic.115": [
    "Я интервьюирую",
    "I interview"
  ],
  "settings.dynamic.116": [
    "Я прохожу собеседование",
    "I am the candidate"
  ],
  "settings.dynamic.117": [
    "Тренировка собеседования",
    "Interview practice"
  ],
  "settings.dynamic.118": [
    "Консалтинг с клиентом",
    "Client consulting"
  ],
  "settings.dynamic.119": [
    "Другая встреча",
    "Other meeting"
  ],
  "settings.dynamic.120": [
    "Облачный маршрут выключен до согласия",
    "Cloud route is disabled until consent is recorded"
  ],
  "settings.dynamic.121": [
    "Неизвестный провайдер для {domain}",
    "Unknown provider for {domain}"
  ],
  "settings.dynamic.122": [
    "переменная {name}",
    "environment variable {name}"
  ],
  "settings.dynamic.123": [
    "Whisper локально — аудио не уходит",
    "Local Whisper — audio stays on this computer"
  ],
  "settings.dynamic.124": [
    "Yandex SpeechKit — облако",
    "Yandex SpeechKit — cloud"
  ],
  "settings.dynamic.125": [
    "Интеграции",
    "Connections"
  ]
};
  const aliases = /* SETTINGS_ALIASES */ {
  "Перейти к изменениям": "settings.audit.changes",
  "Go to changes": "settings.audit.changes",
  "Настройки программы": "settings.1",
  "Application settings": "settings.1",
  "Подключения, звук и оформление.": "settings.2",
  "Connections, audio and appearance.": "settings.2",
  "Вернуться к встрече ↗": "settings.3",
  "Back to meeting ↗": "settings.3",
  "Закрыть настройки": "settings.4",
  "Close settings": "settings.4",
  "Найти настройку": "settings.5",
  "Find a setting": "settings.5",
  "Найти настройку…": "settings.6",
  "Find a setting…": "settings.6",
  "Разделы настроек": "settings.7",
  "Settings sections": "settings.7",
  "Раздел": "settings.8",
  "Section": "settings.8",
  "На этом компьютере": "settings.9",
  "On this computer": "settings.9",
  "Общие настройки Blatero.": "settings.10",
  "General Blatero settings.": "settings.10",
  "Параметры встречи →": "settings.11",
  "Meeting settings →": "settings.11",
  "Помощь": "settings.12",
  "Help": "settings.12",
  "Готовность к встрече": "settings.13",
  "Ready for the meeting": "settings.13",
  "Проверьте звук, подключение ИИ и передачу данных.": "settings.14",
  "Check audio, the AI connection and data sharing.": "settings.14",
  "Звук": "settings.15",
  "Audio": "settings.15",
  "Состояние загружается…": "settings.22",
  "Loading status…": "settings.22",
  "Настроить звук →": "settings.17",
  "Set up audio →": "settings.17",
  "ИИ": "settings.18",
  "AI": "settings.18",
  "Открыть подключение →": "settings.20",
  "Open connection →": "settings.20",
  "Данные": "settings.21",
  "Data": "settings.21",
  "Передача данных →": "settings.23",
  "Data sharing →": "settings.23",
  "Перед встречей": "settings.24",
  "Before a meeting": "settings.24",
  "Проверка попросит произнести фразу и включить звук собеседников.": "settings.25",
  "The check will ask you to speak and play audio from the other participants.": "settings.25",
  "Проверить всё": "settings.26",
  "Check all": "settings.26",
  "Звук и речь": "settings.27",
  "Audio and speech": "settings.27",
  "Микрофон": "settings.29",
  "Microphone": "settings.29",
  "Звук собеседников": "settings.30",
  "Other participants’ audio": "settings.30",
  "Звук приложения встречи": "settings.31",
  "Meeting application audio": "settings.31",
  "Распознавание речи": "settings.32",
  "Speech recognition": "settings.32",
  "Движок распознавания речи": "settings.33",
  "Speech recognition engine": "settings.33",
  "Применить распознавание": "settings.34",
  "Apply speech recognition": "settings.34",
  "Проверить микрофон": "settings.35",
  "Check microphone": "settings.35",
  "Все проверки звука": "settings.36",
  "All audio checks": "settings.36",
  "Нажмите, когда будете готовы говорить. После отсчёта запишутся 12 секунд — пробу можно прослушать.": "settings.37",
  "Press when you are ready to speak. After the countdown, 12 seconds will be recorded for playback.": "settings.37",
  "Дополнительно: эхо и локальная модель": "settings.38",
  "Advanced: echo and local model": "settings.38",
  "Локальная модель": "settings.39",
  "Local model": "settings.39",
  "Локальная модель распознавания": "settings.40",
  "Local speech recognition model": "settings.40",
  "Очистка эха": "settings.41",
  "Echo cancellation": "settings.41",
  "Движок очистки эха": "settings.42",
  "Echo cancellation engine": "settings.42",
  "Убирать акустическое эхо до распознавания": "settings.43",
  "Remove acoustic echo before recognition": "settings.43",
  "Используется выбранный системный выход. Исходный WAV не меняется.": "settings.44",
  "Uses the selected system output. The original WAV is unchanged.": "settings.44",
  "Убирать текстовые дубли": "settings.45",
  "Remove duplicate text": "settings.45",
  "Если фраза распознана в обоих каналах, остаётся системная копия. Настройки эха применятся со следующей записи.": "settings.46",
  "If a phrase is recognized in both channels, the system-audio copy is kept. Echo settings apply to the next recording.": "settings.46",
  "Калибровать эхо": "settings.47",
  "Calibrate echo": "settings.47",
  "Установить WebRTC AEC3": "settings.48",
  "Install WebRTC AEC3": "settings.48",
  "Проверяю WebRTC AEC3…": "settings.49",
  "Checking WebRTC AEC3…": "settings.49",
  "Калибровка не запускалась.": "settings.50",
  "Calibration has not been run.": "settings.50",
  "Озвучка и голоса": "settings.51",
  "Speech synthesis and voices": "settings.51",
  "Голос вопросов": "settings.52",
  "Question voice": "settings.52",
  "Голос для вопросов": "settings.53",
  "Voice for questions": "settings.53",
  "Голос эмуляции / резерв": "settings.54",
  "Simulation / backup voice": "settings.54",
  "Голос эмуляции и резервный голос": "settings.55",
  "Simulation and backup voice": "settings.55",
  "Проверить голос": "settings.56",
  "Test voice": "settings.56",
  "Банк голосов": "settings.57",
  "Voice bank": "settings.57",
  "Микрофон и системный звук разделяются по источнику. Имена из банка голосов применяются после проверки.": "settings.58",
  "Microphone and system audio are separated by source. Voice-bank names are applied after review.": "settings.58",
  "ИИ и подсказки": "settings.59",
  "AI and hints": "settings.59",
  "Подключение": "settings.60",
  "Connection": "settings.60",
  "Провайдер LLM": "settings.61",
  "LLM provider": "settings.61",
  "Где получить доступ ↗": "settings.62",
  "Get access ↗": "settings.62",
  "API-токен": "settings.63",
  "API token": "settings.63",
  "API-токен LLM": "settings.64",
  "LLM API token": "settings.64",
  "Новый токен": "settings.65",
  "New token": "settings.65",
  "Показать": "settings.dynamic.53",
  "Show": "settings.dynamic.53",
  "Адрес API": "settings.67",
  "API address": "settings.67",
  "Сохранить подключение": "settings.68",
  "Save connection": "settings.68",
  "Проверить соединение": "settings.69",
  "Check connection": "settings.69",
  "Удалить токен": "settings.70",
  "Delete token": "settings.70",
  "Подключение не проверено.": "settings.71",
  "Connection has not been checked.": "settings.71",
  "Проверка не отправляет материалы встречи.": "settings.72",
  "The check does not send meeting materials.": "settings.72",
  "Когда предлагать подсказки": "settings.73",
  "When to suggest hints": "settings.73",
  "Автоподсказки": "settings.74",
  "Automatic hints": "settings.74",
  "Подсказки ИИ-сценки": "settings.75",
  "AI role-play hints": "settings.75",
  "Маршрут помощника сценки; оценка и остальные операции не переключаются": "settings.76",
  "Role-play assistant route; review and other operations remain unchanged": "settings.76",
  "Основное подключение": "settings.77",
  "Main connection": "settings.77",
  "DeepSeek Flash · OpenRouter · платный API": "settings.78",
  "DeepSeek Flash · OpenRouter · paid API": "settings.78",
  "Дополнительно: модели, вопросы и инструкции": "settings.79",
  "Advanced: models, questions and instructions": "settings.79",
  "Модель подсказок": "settings.80",
  "Hint model": "settings.80",
  "Модель для подсказок": "settings.81",
  "Model for hints": "settings.81",
  "Модель отчёта": "settings.82",
  "Report model": "settings.82",
  "Модель для отчёта и анализа": "settings.83",
  "Model for reports and analysis": "settings.83",
  "Стиль вопросов": "settings.85",
  "Question style": "settings.85",
  "Стиль применяется при следующей генерации вопросов.": "settings.86",
  "The style applies to the next question generation.": "settings.86",
  "Системные инструкции": "settings.87",
  "System instructions": "settings.87",
  "Отчёты": "settings.88",
  "Reports": "settings.88",
  "Для новых отчётов. Сохранённые документы не меняются.": "settings.89",
  "Applies to new reports. Saved documents are unchanged.": "settings.89",
  "Показывать черновик перед DOCX": "settings.90",
  "Show draft before DOCX": "settings.90",
  "Выводы можно исправить без повторного запроса к ИИ.": "settings.91",
  "Conclusions can be edited without another AI request.": "settings.91",
  "Добавлять таймкоды и ссылки": "settings.92",
  "Include timestamps and links": "settings.92",
  "Переходы к моментам записи в evidence.html. По умолчанию выключены.": "settings.93",
  "Links to recording moments in evidence.html. Off by default.": "settings.93",
  "Данные и приватность": "settings.94",
  "Data and privacy": "settings.94",
  "Текст для ИИ": "settings.95",
  "Text sent to AI": "settings.95",
  "Режим обработки текста для LLM": "settings.96",
  "LLM text processing mode": "settings.96",
  "Согласие на облачную обработку получено": "settings.97",
  "Consent for cloud processing has been obtained": "settings.97",
  "Разрешение общее для программы. Перед новой встречей снимите галочку, если основания нет. Согласие не определяется по речи.": "settings.98",
  "This permission applies to the application. Clear it before a new meeting if consent does not apply. Consent is not inferred from speech.": "settings.98",
  "Локальный Whisper не отправляет аудио. SpeechKit отправляет звук в Яндекс. ИИ получает текст в выбранном режиме обработки.": "settings.99",
  "Local Whisper does not upload audio. SpeechKit sends audio to Yandex. AI receives text according to the selected processing mode.": "settings.99",
  "Хранение и удаление данных →": "settings.100",
  "Data retention and deletion →": "settings.100",
  "Внешний вид": "settings.101",
  "Appearance": "settings.101",
  "Предпросмотр применяется сразу. Вид панелей и тема сохраняются в этом браузере; размер текста — в настройках программы.": "settings.102",
  "Preview is immediate. Panel layout and theme are saved in this browser; text size is saved in application settings.": "settings.102",
  "Тема": "settings.103",
  "Theme": "settings.103",
  "Анимация": "settings.104",
  "Animation": "settings.104",
  "Размер текста": "settings.106",
  "Text size": "settings.106",
  "Рабочий вид": "settings.108",
  "Workspace layout": "settings.108",
  "Текущая настройка": "settings.109",
  "Current layout": "settings.109",
  "Обычный": "settings.110",
  "Standard": "settings.110",
  "Только подсказки и звук": "settings.111",
  "Hints and audio only": "settings.111",
  "Крупная история": "settings.119",
  "Expanded history": "settings.119",
  "Компоновка панелей": "settings.113",
  "Panel layout": "settings.113",
  "Ширина сценария": "settings.115",
  "Scenario width": "settings.115",
  "Видимость рабочих панелей": "settings.116",
  "Workspace panel visibility": "settings.116",
  "Сценарий справа": "settings.117",
  "Scenario on the right": "settings.117",
  "История транскрипта": "settings.118",
  "Transcript history": "settings.118",
  "Свернуть / показать сценарий": "settings.120",
  "Collapse / show scenario": "settings.120",
  "Обычный вид": "settings.121",
  "Standard layout": "settings.121",
  "Практика": "settings.122",
  "Practice": "settings.122",
  "Выберите, кто спрашивает и отвечает. Новая попытка сохраняется отдельно от рабочих встреч.": "settings.123",
  "Choose who asks and answers. Each attempt is saved separately from work meetings.": "settings.123",
  "Я отвечаю": "settings.124",
  "I answer": "settings.124",
  "ИИ задаёт вопросы, вы отвечаете в микрофон.": "settings.125",
  "AI asks questions; you answer into the microphone.": "settings.125",
  "Я спрашиваю": "settings.126",
  "I interview": "settings.dynamic.115",
  "Вы ведёте интервью, ИИ играет кандидата.": "settings.127",
  "You lead the interview; AI plays the candidate.": "settings.127",
  "Оба ИИ": "settings.128",
  "Both AI": "settings.128",
  "Два ИИ ведут разговор. Вы разбираете запись.": "settings.129",
  "Two AI participants talk. You review the recording.": "settings.129",
  "Открыть текущую тренировку / мастер": "settings.130",
  "Open current practice / setup": "settings.130",
  "Эмуляция текущей встречи": "settings.131",
  "Simulate the current meeting": "settings.131",
  "Голосовой бот отвечает за второго участника в выбранной встрече.": "settings.132",
  "A voice bot responds as the other participant in the selected meeting.": "settings.132",
  "Включить эмуляцию": "settings.dynamic.51",
  "Enable simulation": "settings.dynamic.51",
  "Изменить роль бота →": "settings.134",
  "Change bot role →": "settings.134",
  "Обслуживание": "settings.135",
  "Maintenance": "settings.135",
  "Компоненты": "settings.136",
  "Components": "settings.136",
  "Модели речи, голоса и очистка эха": "settings.137",
  "Speech models, voices and echo cancellation": "settings.137",
  "Локальные модели": "settings.138",
  "Local models": "settings.138",
  "Установка и обновления": "settings.139",
  "Installation and updates": "settings.139",
  "Версия, проверка пакета и откат": "settings.140",
  "Version, package verification and rollback": "settings.140",
  "Открыть обновления": "settings.141",
  "Open updates": "settings.141",
  "Диагностика": "settings.142",
  "Diagnostics": "settings.142",
  "Каналы записи, говорящие и Replay Lab": "settings.143",
  "Recording channels, speakers and Replay Lab": "settings.143",
  "Разобрать аудио": "settings.144",
  "Analyze audio": "settings.144",
  "Восстановление и удаление данных": "settings.145",
  "Recovery and data deletion": "settings.145",
  "Перед удалением показывается список файлов.": "settings.146",
  "A file list is shown before deletion.": "settings.146",
  "Восстановление": "settings.147",
  "Recovery": "settings.147",
  "Данные встречи": "settings.148",
  "Meeting data": "settings.148",
  "Очистить результат встречи": "settings.149",
  "Clear meeting results": "settings.149",
  "Очистка удаляет аудио, транскрипт, подсказки и отчёт. Резюме, досье и сценарий сохраняются.": "settings.150",
  "Clears audio, transcript, hints and report. The résumé, dossier and scenario are kept.": "settings.150",
  "Команды · Ctrl+K": "settings.151",
  "Commands · Ctrl+K": "settings.151",
  "Завершить Blatero": "settings.152",
  "Quit Blatero": "settings.152",
  "Параметры встречи": "settings.153",
  "Meeting settings": "settings.153",
  "Тема встречи": "settings.155",
  "Meeting topic": "settings.155",
  "Формат и роль": "settings.157",
  "Format and role": "settings.157",
  "Длительность, минут": "settings.158",
  "Duration, minutes": "settings.158",
  "Длительность встречи": "settings.159",
  "Meeting duration": "settings.159",
  "Без лимита": "settings.160",
  "No time limit": "settings.160",
  "Клиент / компания": "settings.161",
  "Client / company": "settings.161",
  "Клиент или компания": "settings.162",
  "Client or company": "settings.162",
  "Материалы встречи": "settings.163",
  "Meeting materials": "settings.163",
  "Название проекта": "settings.165",
  "Project name": "settings.165",
  "Рабочая папка": "settings.167",
  "Working folder": "settings.167",
  "Путь к папке проекта": "settings.168",
  "Project folder path": "settings.168",
  "Рабочая папка не указана.": "settings.169",
  "No working folder selected.": "settings.169",
  "Выбрать папку…": "settings.170",
  "Choose folder…": "settings.170",
  "Проверить путь": "settings.171",
  "Check path": "settings.171",
  "Подготовить контекст": "settings.172",
  "Prepare context": "settings.172",
  "Перед ИИ-подготовкой откроется проверка передаваемых материалов.": "settings.173",
  "You will review the materials to be shared before AI preparation starts.": "settings.173",
  "Участники, эмуляция и контур данных": "settings.174",
  "Participants, simulation and data environment": "settings.174",
  "Имя в микрофоне": "settings.175",
  "Microphone name": "settings.175",
  "Подпись микрофона": "settings.176",
  "Microphone label": "settings.176",
  "Я": "settings.177",
  "Me": "settings.177",
  "Имя в системном звуке": "settings.178",
  "System-audio name": "settings.178",
  "Подпись системного звука": "settings.179",
  "System-audio label": "settings.179",
  "Собеседник": "settings.180",
  "Other participant": "settings.180",
  "Роль бота": "settings.181",
  "Bot role": "settings.181",
  "Роль бота в эмуляции": "settings.182",
  "Simulation bot role": "settings.182",
  "Контур данных": "settings.184",
  "Data environment": "settings.184",
  "Рабочий": "settings.185",
  "Work": "settings.185",
  "Тестовый": "settings.186",
  "Test": "settings.186",
  "Новая встреча": "settings.187",
  "New meeting": "settings.187",
  "Импорт транскрипта": "settings.188",
  "Import transcript": "settings.188",
  "Изменений нет": "settings.189",
  "No changes": "settings.189",
  "Отменить изменения": "settings.190",
  "Discard changes": "settings.190",
  "Сохранить изменения": "settings.191",
  "Save changes": "settings.191",
  "Обзор": "settings.dynamic.1",
  "Overview": "settings.dynamic.1",
  " (недоступно)": "settings.dynamic.2",
  " (unavailable)": "settings.dynamic.2",
  "Сохраняю…": "settings.dynamic.3",
  "Saving…": "settings.dynamic.3",
  "Несохранённых изменений: {count}": "settings.dynamic.4",
  "Unsaved changes: {count}": "settings.dynamic.4",
  "В других разделах есть изменения: {count}": "settings.dynamic.5",
  "Changes in other sections: {count}": "settings.dynamic.5",
  "Переключить движок": "settings.dynamic.6",
  "Switch engine": "settings.dynamic.6",
  "Применить модель": "settings.dynamic.7",
  "Apply model": "settings.dynamic.7",
  ", изменений: {count}": "settings.dynamic.8",
  ", changes: {count}": "settings.dynamic.8",
  "Для Codex API-токен не нужен. Для API выберите провайдера.": "settings.dynamic.9",
  "Codex does not require an API token. Choose a provider to use an API.": "settings.dynamic.9",
  "Адрес сервера задаётся для подключения «Совместимый API».": "settings.dynamic.10",
  "The server address is used for the Compatible API connection.": "settings.dynamic.10",
  "Успешная проверка сохраняет подключение.": "settings.dynamic.11",
  "A successful check saves the connection.": "settings.dynamic.11",
  "Токен хранится в Windows Credential Manager. Проверка не отправляет материалы встречи.": "settings.dynamic.12",
  "The token is stored in Windows Credential Manager. The check does not send meeting materials.": "settings.dynamic.12",
  "Аудио отправляется в Яндекс SpeechKit. Смена движка не прерывает запись.": "settings.dynamic.13",
  "Audio is sent to Yandex SpeechKit. Switching engines does not interrupt recording.": "settings.dynamic.13",
  "Аудио распознаётся на этом компьютере. Смена движка не прерывает запись.": "settings.dynamic.14",
  "Audio is recognized on this computer. Switching engines does not interrupt recording.": "settings.dynamic.14",
  "Изменения отменены": "settings.dynamic.15",
  "Changes discarded": "settings.dynamic.15",
  "Нет соединения с сервером. Черновик сохранён в этой вкладке.": "settings.dynamic.16",
  "No server connection. Your draft is kept in this tab.": "settings.dynamic.16",
  "Передавать исходные имена, контакты и другие данные без обезличивания?": "settings.dynamic.17",
  "Send original names, contact details and other data without redaction?": "settings.dynamic.17",
  "Переместить встречу в {environment} контур?": "settings.dynamic.18",
  "Move this meeting to the {environment} environment?": "settings.dynamic.18",
  "тестовый": "settings.dynamic.19",
  "test": "settings.dynamic.19",
  "рабочий": "settings.dynamic.20",
  "work": "settings.dynamic.20",
  "Сервер не подтвердил сохранение. Черновик оставлен; проверьте соединение и повторите.": "settings.dynamic.21",
  "The server has not confirmed the save. Your draft is kept; check the connection before trying again.": "settings.dynamic.21",
  "В настройках есть несохранённые изменения.": "settings.dynamic.22",
  "Settings have unsaved changes.": "settings.dynamic.22",
  "Сохранить и закрыть": "settings.dynamic.23",
  "Save and close": "settings.dynamic.23",
  "Не сохранять": "settings.dynamic.24",
  "Discard": "settings.dynamic.24",
  "Продолжить настройку": "settings.dynamic.25",
  "Keep editing": "settings.dynamic.25",
  "Сохраните подключение отдельной кнопкой, затем закройте настройки.": "settings.dynamic.26",
  "Save the connection with its own button, then close settings.": "settings.dynamic.26",
  "Дождитесь подтверждения сохранения.": "settings.dynamic.27",
  "Wait for save confirmation.": "settings.dynamic.27",
  "Соединение потеряно до подтверждения. Черновик оставлен; после подключения проверьте настройки.": "settings.dynamic.28",
  "Connection lost before confirmation. Your draft is kept; check the settings after reconnecting.": "settings.dynamic.28",
  "Сохранено сервером": "settings.dynamic.29",
  "Saved by server": "settings.dynamic.29",
  "Не сохранено: {message}": "settings.dynamic.30",
  "Not saved: {message}": "settings.dynamic.30",
  "SpeechKit · Яндекс": "settings.dynamic.31",
  "SpeechKit · Yandex": "settings.dynamic.31",
  "Whisper · локально": "settings.dynamic.32",
  "Whisper · local": "settings.dynamic.32",
  "Продолжить тренировку": "settings.dynamic.33",
  "Continue practice": "settings.dynamic.33",
  "Подробная настройка тренировки": "settings.dynamic.34",
  "Advanced practice setup": "settings.dynamic.34",
  "Имя участника": "settings.dynamic.35",
  "Participant name": "settings.dynamic.35",
  "Автовыбор": "settings.dynamic.36",
  "Automatic selection": "settings.dynamic.36",
  "Проверка пройдена": "settings.dynamic.37",
  "Check passed": "settings.dynamic.37",
  "Проверьте устройства перед встречей": "settings.dynamic.38",
  "Check devices before the meeting": "settings.dynamic.38",
  "Доступ не настроен": "settings.dynamic.39",
  "Access is not configured": "settings.dynamic.39",
  "Облако разрешено · обезличивание включено": "settings.dynamic.40",
  "Cloud enabled · text redaction on": "settings.dynamic.40",
  "Облако разрешено · исходный текст": "settings.dynamic.41",
  "Cloud enabled · original text": "settings.dynamic.41",
  "Облачные функции выключены": "settings.dynamic.42",
  "Cloud features are off": "settings.dynamic.42",
  "Настройка не найдена. Попробуйте «микрофон», «токен» или «тренировка».": "settings.dynamic.43",
  "No matching setting. Try microphone, token or practice.": "settings.dynamic.43",
  "Сначала остановите текущую запись.": "settings.dynamic.44",
  "Stop the current recording first.": "settings.dynamic.44",
  "Создаю тренировку…": "settings.dynamic.45",
  "Creating practice…": "settings.dynamic.45",
  "Сначала сохраните или отмените изменения этого раздела.": "settings.dynamic.46",
  "Save or discard changes in this section first.": "settings.dynamic.46",
  "проверка звука": "settings.dynamic.47",
  "audio checks": "settings.dynamic.47",
  "локальные модели": "settings.dynamic.48",
  "local models": "settings.dynamic.48",
  "обновления": "settings.dynamic.49",
  "updates": "settings.dynamic.49",
  "настройки": "settings.dynamic.50",
  "settings": "settings.dynamic.50",
  "Выключить эмуляцию": "settings.dynamic.52",
  "Disable simulation": "settings.dynamic.52",
  "Скрыть": "settings.dynamic.54",
  "Hide": "settings.dynamic.54",
  "Codex / подписка ChatGPT": "settings.dynamic.55",
  "Codex / ChatGPT subscription": "settings.dynamic.55",
  "OpenRouter — единый API": "settings.dynamic.56",
  "OpenRouter — unified API": "settings.dynamic.56",
  "Ollama / совместимый API": "settings.dynamic.57",
  "Ollama / compatible API": "settings.dynamic.57",
  "Codex CLI найден; авторизация ещё не проверена": "settings.dynamic.58",
  "Codex CLI found; sign-in has not been checked": "settings.dynamic.58",
  "Codex CLI не найден": "settings.dynamic.59",
  "Codex CLI was not found": "settings.dynamic.59",
  "без токена": "settings.dynamic.60",
  "without a token": "settings.dynamic.60",
  "старый git config": "settings.dynamic.61",
  "legacy git config": "settings.dynamic.61",
  "модель: Codex по умолчанию": "settings.dynamic.62",
  "model: Codex default": "settings.dynamic.62",
  "API-токен (необязательно)": "settings.dynamic.63",
  "API token (optional)": "settings.dynamic.63",
  "необязательно для локального сервера": "settings.dynamic.64",
  "optional for a local server": "settings.dynamic.64",
  "вставьте новый токен или оставьте пустым": "settings.dynamic.65",
  "enter a new token or leave blank": "settings.dynamic.65",
  "API-токен не нужен. Выполните codex login и проверьте соединение.": "settings.dynamic.66",
  "No API token is needed. Run codex login and check the connection.": "settings.dynamic.66",
  "Укажите доступ и проверьте соединение.": "settings.dynamic.67",
  "Configure access and check the connection.": "settings.dynamic.67",
  "Провайдер выбран. Настройте доступ и выполните проверку.": "settings.dynamic.68",
  "Provider selected. Configure access and run a check.": "settings.dynamic.68",
  "Доступ настроен: {source}. Нажмите «проверить соединение».": "settings.dynamic.69",
  "Access configured: {source}. Press Check connection.": "settings.dynamic.69",
  "источник найден": "settings.dynamic.70",
  "credential source found": "settings.dynamic.70",
  "Доступ ещё не настроен. Введите токен и нажмите «проверить соединение».": "settings.dynamic.71",
  "Access is not configured yet. Enter a token and press Check connection.": "settings.dynamic.71",
  "голоса": "settings.dynamic.72",
  "voices": "settings.dynamic.72",
  "локально": "settings.dynamic.73",
  "local": "settings.dynamic.73",
  "облако": "settings.dynamic.74",
  "cloud": "settings.dynamic.74",
  "локально → облако": "settings.dynamic.75",
  "local → cloud": "settings.dynamic.75",
  " · выключено": "settings.dynamic.76",
  " · disabled": "settings.dynamic.76",
  "контракт не загружен": "settings.dynamic.77",
  "contract not loaded": "settings.dynamic.77",
  "Создайте ключ в OpenRouter → Keys. Один ключ открывает модели разных компаний.": "settings.dynamic.78",
  "Create a key in OpenRouter → Keys. One key provides access to models from different companies.": "settings.dynamic.78",
  "API-токен не нужен. Установите Codex CLI и один раз выполните codex login.": "settings.dynamic.79",
  "No API token is needed. Install Codex CLI and run codex login once.": "settings.dynamic.79",
  "Создайте project API key в OpenAI Platform. Подписка ChatGPT не оплачивает API.": "settings.dynamic.80",
  "Create a project API key in OpenAI Platform. A ChatGPT subscription does not cover API usage.": "settings.dynamic.80",
  "Создайте API key в Anthropic Console. Подписка Claude и API оплачиваются отдельно.": "settings.dynamic.81",
  "Create an API key in Anthropic Console. Claude subscriptions and API usage are billed separately.": "settings.dynamic.81",
  "Создайте API key в DeepSeek Platform и пополните API-баланс.": "settings.dynamic.82",
  "Create an API key in DeepSeek Platform and add API credit.": "settings.dynamic.82",
  "Укажите base URL OpenAI-совместимого сервера. Для Ollama обычно http://127.0.0.1:11434/v1; токен необязателен.": "settings.dynamic.83",
  "Enter the base URL of an OpenAI-compatible server. For Ollama this is usually http://127.0.0.1:11434/v1; a token is optional.": "settings.dynamic.83",
  "авто (системный)": "settings.dynamic.84",
  "automatic (system default)": "settings.dynamic.84",
  "выкл": "settings.dynamic.85",
  "off": "settings.dynamic.85",
  "по паузам": "settings.dynamic.86",
  "on pauses": "settings.dynamic.86",
  "30с": "settings.dynamic.87",
  "30 s": "settings.dynamic.87",
  "60с": "settings.dynamic.88",
  "60 s": "settings.dynamic.88",
  "90с": "settings.dynamic.89",
  "90 s": "settings.dynamic.89",
  "кейсы": "settings.dynamic.90",
  "cases": "settings.dynamic.90",
  "классика": "settings.dynamic.91",
  "classic": "settings.dynamic.91",
  "микс": "settings.dynamic.92",
  "mixed": "settings.dynamic.92",
  "компактный": "settings.dynamic.93",
  "compact": "settings.dynamic.93",
  "обычный": "settings.dynamic.94",
  "standard": "settings.dynamic.94",
  "крупный": "settings.dynamic.95",
  "large": "settings.dynamic.95",
  "очень крупный": "settings.dynamic.96",
  "extra large": "settings.dynamic.96",
  "Whisper base — быстрее": "settings.dynamic.97",
  "Whisper base — faster": "settings.dynamic.97",
  "Whisper small — точнее": "settings.dynamic.98",
  "Whisper small — more accurate": "settings.dynamic.98",
  "Whisper medium — медленнее": "settings.dynamic.99",
  "Whisper medium — slower": "settings.dynamic.99",
  "обезличивать текст перед LLM": "settings.dynamic.100",
  "redact text before sending to LLM": "settings.dynamic.100",
  "передавать исходный текст": "settings.dynamic.101",
  "send original text": "settings.dynamic.101",
  "авто — WebRTC AEC3 → встроенный": "settings.dynamic.102",
  "automatic — WebRTC AEC3 → built-in": "settings.dynamic.102",
  "WebRTC AEC3 — с безопасным откатом": "settings.dynamic.103",
  "WebRTC AEC3 — with safe fallback": "settings.dynamic.103",
  "встроенный — без внешнего бинарника": "settings.dynamic.104",
  "built-in — no external binary": "settings.dynamic.104",
  "мой голос локально, без облака": "settings.dynamic.105",
  "my voice locally, no cloud": "settings.dynamic.105",
  "мой голос локально → Яндекс": "settings.dynamic.106",
  "my voice locally → Yandex": "settings.dynamic.106",
  "только Яндекс SpeechKit": "settings.dynamic.107",
  "Yandex SpeechKit only": "settings.dynamic.107",
  "авто (filipp)": "settings.dynamic.108",
  "automatic (filipp)": "settings.dynamic.108",
  "filipp — мужской": "settings.dynamic.109",
  "filipp — male": "settings.dynamic.109",
  "alena — женский": "settings.dynamic.110",
  "alena — female": "settings.dynamic.110",
  "jane — женский": "settings.dynamic.111",
  "jane — female": "settings.dynamic.111",
  "ermil — мужской": "settings.dynamic.112",
  "ermil — male": "settings.dynamic.112",
  "zahar — мужской": "settings.dynamic.113",
  "zahar — male": "settings.dynamic.113",
  "omazh — женский": "settings.dynamic.114",
  "omazh — female": "settings.dynamic.114",
  "Я интервьюирую": "settings.dynamic.115",
  "Я прохожу собеседование": "settings.dynamic.116",
  "I am the candidate": "settings.dynamic.116",
  "Тренировка собеседования": "settings.dynamic.117",
  "Interview practice": "settings.dynamic.117",
  "Консалтинг с клиентом": "settings.dynamic.118",
  "Client consulting": "settings.dynamic.118",
  "Другая встреча": "settings.dynamic.119",
  "Other meeting": "settings.dynamic.119",
  "Облачный маршрут выключен до согласия": "settings.dynamic.120",
  "Cloud route is disabled until consent is recorded": "settings.dynamic.120",
  "Неизвестный провайдер для {domain}": "settings.dynamic.121",
  "Unknown provider for {domain}": "settings.dynamic.121",
  "переменная {name}": "settings.dynamic.122",
  "environment variable {name}": "settings.dynamic.122",
  "Whisper локально — аудио не уходит": "settings.dynamic.123",
  "Local Whisper — audio stays on this computer": "settings.dynamic.123",
  "Yandex SpeechKit — облако": "settings.dynamic.124",
  "Yandex SpeechKit — cloud": "settings.dynamic.124",
  "Интеграции": "settings.dynamic.125",
  "Connections": "settings.dynamic.125"
};
  const ownedControls = /* SETTINGS_CONTROLS */ [
  "aecNativeInstall",
  "aecTestStart",
  "audioBtn",
  "clearResults",
  "commandSettings",
  "emuBtn",
  "importTranscript",
  "layoutReset",
  "llmDelete",
  "llmProviderHelp",
  "llmSave",
  "llmTest",
  "modelManagerSettings",
  "motionToggle",
  "newMeet",
  "promptEditorBtn",
  "settingsAnalysis",
  "settingsApply",
  "settingsApplySpeech",
  "settingsData",
  "settingsDiscard",
  "settingsGuide",
  "settingsHome",
  "settingsMicTest",
  "settingsPreflight",
  "settingsRecovery",
  "settingsShutdown",
  "sideToggleSettings",
  "speakerBankBtn",
  "themeToggle",
  "toggleLlmKey",
  "trainingBtn",
  "updateManagerSettings",
  "voiceTestBtn",
  "workspaceBrowse",
  "workspaceInit",
  "workspaceProbe"
];
  const i18n = window.BlateroI18n;
  if (!i18n) return;
  i18n.register(entries);
  function ui(text, params = {}) {
    const key = Object.hasOwn(aliases,text) ? aliases[text] : null;
    return key ? i18n.t(key, params) : String(text ?? '').replace(/\{([a-zA-Z_]\w*)\}/g,
      (match, name) => Object.hasOwn(params, name) ? String(params[name]) : match);
  }
  function applyOwned() {
    const host = document.getElementById('settingsOverlay');
    if (!host) return;
    host.lang = i18n.language;
    for (const id of ownedControls) {
      const element = document.getElementById(id);
      if (!element || !host.contains(element)) continue;
      const label = element.querySelector('.action-label') ||
        (element.childElementCount === 0 ? element : null);
      if (label && Object.hasOwn(aliases, label.textContent.trim())) {
        label.textContent = ui(label.textContent.trim());
        label.lang = i18n.language;
      }
    }
    for (const id of ['selMic','selOutput','selSpeech','selWhisper','selProvider',
      'selAuto','selStyle','selFont','selPrivacy','selAecBackend','selVoice',
      'selQuestionVoice','selMType','selDur']) {
      const select = document.getElementById(id);
      if (!select) continue;
      for (const option of select.options) {
        if (['selMic','selOutput'].includes(id) && option.value !== 'auto') continue;
        option.textContent = ui(option.textContent);
      }
    }
  }
  function searchTerms(text) {
    const key=Object.hasOwn(aliases,text)?aliases[text]:null;
    return key?entries[key].join(' '):text;
  }
  window.BlateroSettingsI18n = {ui, applyOwned, searchTerms};
  document.addEventListener('blatero:language', applyOwned);
  applyOwned();
})();
