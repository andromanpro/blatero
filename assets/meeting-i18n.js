'use strict';
// Explicitly owned interface copy. Never scan reports, transcripts or hint text.
(() => {
  // Append only: template data-meeting-key values are positional.
  const phrases = /* MEETING_PHRASES */ [
    ["Blatero — продукт Androman.pro", "Blatero — by Androman.pro"],
    ["Подсказки — следующий вопрос", "Hints — next question"],
    ["ещё подсказку", "another hint"], ["Начать запись", "Start recording"], ["запись", "record"],
    ["все панели", "all panels"], ["Режимы работы", "Workspace modes"],
    ["Проекты и задачи", "Projects and tasks"], ["проекты", "projects"],
    ["Календарь — день и неделя", "Calendar — day and week"], ["календарь", "calendar"],
    ["Инструменты", "Tools"], ["инструменты", "tools"], ["настройки", "settings"],
    ["аудио и говорящие", "audio and speakers"], ["архив", "archive"],
    ["память клиента и проекта", "client and project memory"], ["локальные модели", "local models"],
    ["обновления", "updates"], ["восстановление", "recovery"], ["команды · Ctrl+K", "commands · Ctrl+K"],
    ["помощь", "help"], ["завершить работу", "shut down"], ["Встреча", "Meeting"],
    ["Контур встреч", "Meeting environment"], ["рабочий", "work"], ["тестовый", "test"],
    ["Проверить звук, распознавание и ИИ", "Check audio, speech recognition and AI"],
    ["проверить всё", "check all"], ["Новая встреча", "New meeting"], ["новая встреча", "new meeting"],
    ["Повестка и материалы встречи", "Meeting agenda and materials"], ["повестка", "agenda"],
    ["Проверить транскрипт и сформировать DOCX", "Review the transcript and create a DOCX"],
    ["отчёт", "report"], ["Результаты и папка отчёта", "Results and report folder"],
    ["результаты", "results"], ["Папка отчёта", "Report folder"],
    ["Папка сохранения отчёта", "Report destination folder"],
    ["открыть папку текущей встречи в Проводнике", "open this meeting’s folder in File Explorer"],
    ["открыть папку", "open folder"], ["Следующий шаг", "Next step"],
    ["Подготовьте встречу и проверьте оборудование.", "Prepare the meeting and check your equipment."],
    ["подготовить встречу", "prepare meeting"], ["отмена", "cancel"],
    ["Начать запись текущей встречи?", "Start recording this meeting?"],
    ["Используется формат выбранной встречи.", "Uses the selected meeting’s format."],
    ["изменить формат", "change format"], ["Роль в текущей записи", "Your role in this recording"],
    ["Выберите один вариант.", "Choose one option."], ["Проверяю калибровку…", "Checking calibration…"],
    ["калибровать сейчас", "calibrate now"], ["продолжить без калибровки", "continue without calibration"],
    ["Запись рабочего разговора", "Recording a work conversation"],
    ["Подтверждаю: участники уведомлены о записи или есть иное применимое основание. Это не юридическое согласие и не заменяет проверку применимых правил.", "I confirm that participants have been informed of the recording, or another applicable basis exists. This checkbox is not legal consent or a substitute for checking the applicable rules."],
    ["начать запись", "start recording"], ["закрыть", "close"],
    ["АУДИО И ГОВОРЯЩИЕ", "AUDIO AND SPEAKERS"], ["Аудио и говорящие", "Audio and speakers"],
    ["Единое место для проверки каналов, повторного распознавания, разделения голосов и назначения участникам имён.", "Check channels, transcribe again, separate voices and name participants."],
    ["Порядок разбора записи", "Recording review steps"], ["выбрать запись", "choose recording"],
    ["разделить голоса", "separate voices"], ["прослушать и назвать", "listen and name"],
    ["проверить отчёт", "review report"], ["Проверить каналы", "Check channels"],
    ["микрофон, звук встречи, эхо и распознавание", "microphone, meeting audio, echo and recognition"],
    ["Импортировать транскрипт", "Import a transcript"],
    ["Teams, Zoom, Телемост или Контур.Толк", "Teams, Zoom, Telemost or Kontur.Talk"],
    ["Открыть банк голосов", "Open the voice bank"], ["локальные отпечатки для подсказки имён", "local voiceprints for name suggestions"],
    ["Проверить отчёт", "Review report"], ["контроль спорных мест и создание DOCX", "review uncertain passages and create a DOCX"],
    ["Эталон качества", "Quality reference"], ["проверка ошибок текста и разделения голосов по исходному аудио", "check transcription and speaker errors against the original audio"],
    ["Калибровка Аудиосторожа", "Audio Guard calibration"], ["пороги задержки, диска и перегрузки по реальным встречам", "latency, disk and overload thresholds based on real meetings"],
    ["Открыть весь архив", "Open the full archive"], ["транскрипты, записи и отчёты встреч", "meeting transcripts, recordings and reports"],
    ["Записи для разбора", "Recordings to review"], ["Выберите встречу. Replay Lab создаёт отдельный результат и не меняет исходник.", "Choose a meeting. Replay Lab creates a separate result without changing the original."],
    ["обновить", "refresh"], ["Загружаю архив…", "Loading archive…"],
    ["Чтобы назвать говорящих, банк голосов не нужен.", "You do not need the voice bank to name speakers."],
    ["Сначала Replay Lab делит запись на голосовые кластеры. Затем нажмите «Переименовать говорящих», прослушайте примеры, укажите имена и сохраните. После этого нажмите «Проверить отчёт»: Blatero покажет спорные места перед созданием DOCX. Банк голосов — отдельный необязательный шаг: он помогает предлагать эти имена в будущих встречах, но никогда не применяет их без вашего подтверждения.", "First, Replay Lab groups the recording by voice. Then choose Rename speakers, listen to samples, enter names and save. Choose Review report to inspect uncertainties before creating a DOCX. The voice bank is optional: it suggests names in future meetings but never applies them without your confirmation."],
    ["ПРОВЕРКА ОТЧЁТА", "REPORT REVIEW"], ["Контроль перед отчётом", "Review before export"],
    ["Проверяю транскрипт, голоса и доказательность выводов.", "Checking the transcript, speakers and evidence for conclusions."],
    ["Выводы и их опоры", "Conclusions and evidence"],
    ["Локальная проверка находит связанную реплику и уверенность распознавания, но не подменяет содержательную проверку человеком.", "Local checks locate supporting utterances and recognition confidence. A person must still review the substance."],
    ["Калибровка проверки выводов", "Conclusion review calibration"],
    ["Сравнение автоматического статуса с вашими решениями", "Compare automatic status with your decisions"],
    ["Черновик итогового отчёта", "Final report draft"], ["Правки сохраняются локально и не вызывают LLM.", "Edits are saved locally without an AI request."],
    ["Черновик не загружен.", "Draft not loaded."], ["сохранить правки", "save edits"],
    ["1 · проверить исходные данные", "1 · review source data"], ["прослушать спорные места", "listen to uncertain passages"],
    ["переименовать говорящих", "rename speakers"], ["исправить текст", "edit transcript"],
    ["2 · обновить выводы", "2 · update conclusions"], ["обновить после исправлений", "rebuild after edits"],
    ["3 · создать документ", "3 · create document"], ["DOCX с предупреждениями", "DOCX with warnings"],
    ["создать проверенный DOCX", "create reviewed DOCX"], ["дополнительно", "more"],
    ["экспорт доказательств JSON", "export evidence as JSON"],
    ["Черновик и очередь сомнений хранятся локально. Повторный запрос к LLM выполняется только по кнопке «пересобрать»; подтверждение собирает DOCX без нового обращения к модели.", "The draft and review queue are stored locally. Only rebuilding makes another AI request. Confirming creates the DOCX without calling the model again."],
    ["ЛОКАЛЬНЫЙ ТРАНСКРИПТ", "LOCAL TRANSCRIPT"], ["Исправление реплик", "Edit utterances"],
    ["Правится канонический JSONL, а читаемый Markdown пересобирается автоматически. Исходная версия и журнал изменений остаются локально.", "Edits update the canonical JSONL and rebuild the readable Markdown. The original version and change history remain local."],
    ["поиск", "search"], ["текст, имя или роль", "text, name or role"], ["Редактор не загружен.", "Editor not loaded."],
    ["Редактирование доступно после остановки записи и только на этом компьютере. Если реплика успела измениться в другом окне, Blatero потребует перезагрузить данные.", "Editing is available on this computer after recording stops. If an utterance changes in another window, Blatero requires you to reload it."],
    ["КРУПНАЯ ПОДСКАЗКА", "LARGE HINT"], ["Ответ крупно", "Large answer"], ["скопировать", "copy"],
    ["открепить", "unpin"], ["ГОТОВ К ВСТРЕЧЕ", "READY FOR A MEETING"],
    ["Меньше заметок — больше разговора", "Fewer notes. More conversation."],
    ["Blatero записывает звук, расшифровывает речь и помогает собрать проверяемый отчёт.", "Blatero records audio, transcribes speech and helps create a report you can verify."],
    ["Подготовить", "Prepare"], ["роль, цель, материалы и вопросы", "role, goal, materials and questions"],
    ["Проверить", "Check"], ["микрофон, звук встречи и ИИ", "microphone, meeting audio and AI"],
    ["Записать", "Record"], ["запись, подсказки и транскрипт", "recording, hints and transcript"],
    ["Разобрать", "Review"], ["говорящие, спорные места и DOCX", "speakers, uncertainties and DOCX"],
    ["после подготовки вопросы появятся справа", "prepared questions appear on the right"],
    ["подсказку можно вызвать кнопкой сверху или клавишей P", "request a hint with the top button or the P key"],
    ["отчёт собирается после проверки говорящих", "create the report after reviewing speakers"],
    ["Изменить ширину сценария", "Resize the question plan"], ["Рабочие материалы", "Meeting materials"],
    ["сценарий", "plan"], ["досье", "dossier"], ["проект", "project"], ["память", "memory"],
    ["свернуть сценарий · Ctrl+B", "collapse question plan · Ctrl+B"], ["Свернуть сценарий", "Collapse question plan"],
    ["Память между встречами", "Memory between meetings"], ["Не настроена.", "Not configured."],
    ["из отчёта", "from report"], ["Черновик · ещё не сохранён", "Draft · not saved yet"],
    ["принять выбранное", "accept selected"], ["отклонить", "reject"], ["+ добавить вручную", "+ add manually"],
    ["Область новой записи памяти", "New memory entry scope"], ["Тип новой записи памяти", "New memory entry type"],
    ["решение", "decision"], ["обещание", "commitment"], ["открытый вопрос", "open question"],
    ["проверенный факт", "verified fact"], ["Текст новой записи памяти", "New memory entry text"],
    ["Короткая самостоятельная формулировка", "A short, self-contained statement"],
    ["Ответственный по новой записи", "Owner of the new entry"], ["ответственный · необязательно", "owner · optional"],
    ["Срок новой записи", "New entry due date"], ["срок · необязательно", "due date · optional"],
    ["сохранить", "save"], ["Папка проекта изменилась?", "Has the project folder changed?"],
    ["Свяжите новую рабочую папку с прежней памятью. Записи не копируются: обе папки продолжат видеть одну историю проекта.", "Link the new folder to the existing project memory. Entries are not copied; both folders share the same project history."],
    ["Прежняя память проекта", "Existing project memory"], ["связать память", "link memory"],
    ["запись не запущена · нажмите «Проверить всё» перед встречей", "not recording · run Check all before the meeting"],
    ["Звук в порядке", "Audio is OK"], ["История · реплик пока нет", "History · no utterances yet"],
    ["скрыть историю", "hide history"], ["развернуть", "expand"], ["показать всю историю", "show full history"],
    ["открыть полный транскрипт", "open full transcript"], ["История транскрипта", "Transcript history"],
    ["Разделы встречи", "Meeting sections"], ["Отчёт", "Report"], ["Транскрипт", "Transcript"], ["Материалы", "Materials"],
    ["Скачать DOCX", "Download DOCX"], ["Проверить черновик", "Review draft"], ["Ещё", "More"],
    ["Открыть папку результатов", "Open results folder"], ["Продолжить запись…", "Resume recording…"],
    ["Сформировать заново…", "Rebuild report…"], ["Печать", "Print"], ["Повторить загрузку", "Retry loading"],
    ["Разделы отчёта", "Report sections"], ["Размер текста документа", "Document text size"],
    ["Уменьшить текст документа", "Decrease document text size"], ["Обычный размер", "Default size"],
    ["Увеличить текст документа", "Increase document text size"], ["Запись сохранена", "Recording saved"],
    ["Проверьте говорящих и текст, затем подготовьте итог. Подсказки можно открыть отдельно.", "Review speakers and text, then prepare the result. You can open hints separately."],
    ["Читать транскрипт", "Read transcript"], ["Подготовить отчёт", "Prepare report"],
    ["Черновик — ещё не итоговый документ. Проверьте текст и выводы перед созданием DOCX.", "This is a draft, not the final document. Review the text and conclusions before creating a DOCX."],
    ["Сохранённый отчёт. Данные о прохождении контроля отсутствуют; подтверждённым он не помечается.", "Saved report. Review status is unavailable, so it is not marked as confirmed."],
    ["После создания отчёта исходные данные или настройки изменились. Здесь показана сохранённая версия; автоматической пересборки нет.", "Source data or settings have changed since the report was created. This is the saved version; it is not rebuilt automatically."],
    ["Актуальность относительно исходных данных не подтверждена.", "It has not been confirmed against the current source data."],
    ["Файл DOCX не найден; сохранённый текст отчёта доступен ниже.", "The DOCX file was not found. The saved report text is available below."],
    ["ЧЕРНОВИК", "DRAFT"], ["СОХРАНЁННЫЙ ОТЧЁТ", "SAVED REPORT"], ["МАТЕРИАЛЫ", "MATERIALS"],
    ["Материалы этой встречи. Исходные файлы и настройки обработки не меняются при просмотре.", "Materials for this meeting. Viewing does not change original files or processing settings."],
    ["Досье", "Dossier"], ["Досье пока не подготовлено.", "No dossier has been prepared yet."],
    ["Контекст проекта", "Project context"], ["Рабочая папка и контекст не указаны.", "No project folder or context is set."],
    ["Память проекта", "Project memory"], ["Сохранённых записей памяти пока нет.", "No saved memory entries yet."],
    ["Открыть память проекта", "Open project memory"], ["Повестка и сценарий", "Agenda and question plan"],
    ["Добавить материалы", "Add materials"], ["Загружаю сохранённые данные…", "Loading saved data…"],
    ["Не удалось загрузить сохранённые данные", "Could not load saved data"], ["ПОЛНЫЙ ТРАНСКРИПТ", "FULL TRANSCRIPT"],
    ["Все сохранённые сегменты встречи. Для исправления текста или говорящих откройте «Ещё → Аудио и говорящие».", "All saved meeting segments. To edit text or speakers, open More → Participants and voice bank, or the detailed audio review."],
    ["Разбор", "Review"], ["Подсказки", "Hints"], ["Подготовка", "Preparation"],
    ["Запись сохранена · исходные аудиофайлы доступны в результатах", "Recording saved · original audio files are available in results"],
    ["продолжить запись", "resume recording"], ["Продолжить эту встречу новым аудиосегментом", "Resume this meeting in a new audio segment"],
    ["Скрыть вспомогательные панели, оставить команды и подсказки", "Hide extra panels; keep commands and hints"],
    ["↗ Обычный вид", "↗ Full view"], ["↙ Только главное", "↙ Essentials"],
    ["Размер текста подсказок", "Hint text size"], ["Уменьшить текст подсказок", "Decrease hint text size"],
    ["Вернуть обычный размер", "Restore default size"], ["Увеличить текст подсказок", "Increase hint text size"],
    ["ИИ · ожидание запроса", "AI · waiting for a request"], ["Модель ИИ · уточняется", "AI model · not confirmed yet"],
    ["Модель подсказок. Для Codex она подтверждается заголовком ответа CLI.", "Hint model. For Codex, it is confirmed by the CLI response header."],
    ["Codex выбирает модель автоматически. Показана модель из заголовка последнего запуска; усилие рассуждения low.", "Codex selects the model automatically. This is the model reported by the last run; reasoning effort is low."],
    ["Подсказки студии · DeepSeek V4 Flash · OpenRouter", "Studio hints · DeepSeek V4 Flash · OpenRouter"],
    ["Отдельный быстрый маршрут студии. Основная модель и голоса не меняются.", "A separate fast studio route. The main model and voices are unchanged."],
    ["Размер подсказок {count}%. Сбросить до 100%", "Hint size {count}%. Reset to 100%"],
    ["Запрос принят · ИИ работает ", "Request received · AI is working "],
    ["Связь потеряна · запрос отправлен ", "Connection lost · request was sent "],
    ["ИИ · результат запроса неизвестен после ", "AI · request outcome unknown after "],
    ["ИИ · готово за ", "AI · completed in "], ["ИИ · ошибка через ", "AI · error after "],
    ["ИИ · ожидание прервано после ", "AI · waiting interrupted after "],
    ["Создайте встречу, укажите цель и добавьте рабочие материалы.", "Create a meeting, enter its goal and add materials."],
    ["получить быстрый ответ", "get a quick answer"], ["получить подсказку", "get a hint"],
    ["Запись идёт. Следите за уровнями звука; подсказку можно вызвать в любой момент.", "Recording is in progress. Watch the audio levels; request a hint at any time."],
    ["читать отчёт", "read report"], ["Сохранённый отчёт доступен, но исходные данные или настройки изменились.", "The saved report is available, but source data or settings have changed."],
    ["Отчёт сохранён. Прочитайте его здесь, скачайте DOCX или начните новую встречу.", "Report saved. Read it here, download the DOCX or start a new meeting."],
    ["проверить договорённости", "review agreements"],
    ["Отчёт сохранён. Проверьте и сохраните договорённости — они подтянутся в следующую встречу проекта.", "Report saved. Review and save agreements to include them in the project’s next meeting."],
    ["Черновик готов. Проверьте говорящих, текст и выводы перед созданием DOCX.", "Draft ready. Review speakers, text and conclusions before creating a DOCX."],
    ["сформировать разбор", "create review"], ["сформировать отчёт", "create report"],
    ["Запись сохранена. Проверьте транскрипт и сформируйте итоговый документ.", "Recording saved. Review the transcript and create the final document."],
    ["Перед записью проверьте микрофон, звук встречи, распознавание речи и ИИ.", "Before recording, check the microphone, meeting audio, speech recognition and AI."],
    ["Проверка пройдена. Можно начинать запись.", "Checks passed. You can start recording."],
    ["открыть отчёт", "open report"], ["Читать сохранённый отчёт без нового запроса к ИИ", "Read the saved report without a new AI request"],
    ["разбор", "review"], ["Сформировать итоговый разбор", "Create the final review"], ["Сформировать итоговый отчёт", "Create the final report"],
    ["Проверить сомнения перед итоговым DOCX{suffix}", "Review uncertainties before the final DOCX{suffix}"],
    ["быстрый ответ", "quick answer"], ["Готовый ответ на последний вопрос интервьюера", "An answer to the interviewer’s last question"],
    ["Следующий вопрос и точки для уточнения", "Next question and points to clarify"], ["темы и вакансия", "topics and job description"],
    ["Темы, вакансия и материалы", "Topics, job description and materials"],
    ["Закреплённые подсказки", "Pinned hints"], ["История подсказок и рисков", "Hint and risk history"],
    ["Действие не сохранено", "Action was not saved"], ["Закрепить", "Pin"], ["Открепить", "Unpin"],
    ["Крупно", "Enlarge"], ["Решён", "Resolved"], ["Отвечен", "Answered"],
    ["Убрать неудачную подсказку", "Dismiss this hint"], ["Убрать подсказку", "Dismiss hint"],
    ["Неактуально", "Irrelevant"], ["Бесполезный вопрос", "Unhelpful question"], ["Повтор", "Duplicate"],
    ["Ранее показанные · не отмечены решёнными", "Previously shown · not marked resolved"],
    ["Незакрытые риски вне основного экрана", "Open risks outside the main view"], ["Решённые риски", "Resolved risks"],
    ["Решённые вопросы и ответы", "Resolved questions and answers"], ["Отклонённые подсказки", "Dismissed hints"],
    ["Риск: ", "Risk: "], ["Вернуть", "Restore"], ["Показать новые · {count}", "Show new · {count}"],
    ["Незакрытых рисков: {count}", "Open risks: {count}"], ["Незакрытые риски · {count}", "Open risks · {count}"],
    ["{message} · исходные ответы и записи сохранены", "{message} · original answers and recordings are retained"],
    ["Новые показаны. Старые незакреплённые уйдут в историю через 45 секунд; наведите курсор, чтобы задержать.", "New hints are shown. Older unpinned hints move to history after 45 seconds; hover to keep them visible."],
    ["Риски находятся на экране или ожидают за кнопкой «Показать новые».", "Risks are visible on screen or waiting behind Show new."],
    ["Уточнить: {text}", "Clarify: {text}"],
    ["Подготовим итог автоматически. Уточнить потребуется только спорные имена и выводы.", "We will prepare the result automatically. Only uncertain names and conclusions need your review."],
    ["Завершить и создать отчёт", "Finish and create report"], ["Участники и банк голосов", "Participants and voice bank"],
    ["Дополнительно", "More"], ["Подробный разбор фраз и аудио", "Detailed transcript and audio review"], ["Продолжить запись", "Resume recording"],
    ["Подготовка отчёта", "Report preparation"], ["Готовим отчёт", "Preparing report"],
    ["Проверка записи и материалов", "Check recording and materials"], ["Черновик и контроль выводов", "Draft and conclusion review"],
    ["Итоговый документ", "Final document"], ["Открыть черновик", "Open draft"],
    ["Запускаем подготовку", "Starting preparation"], ["Проверяем транскрипт и материалы", "Checking transcript and materials"],
    ["ИИ анализирует встречу и пишет черновик", "AI is analyzing the meeting and writing a draft"],
    ["Проверяем выводы и качество данных", "Checking conclusions and data quality"],
    ["Проверяем сохранённый черновик", "Checking the saved draft"], ["Собираем итоговый DOCX", "Building the final DOCX"],
    ["Сохраняем результаты", "Saving results"], ["Прошло {time}", "Elapsed {time}"],
    ["Результат запроса неизвестен", "Request outcome unknown"], ["Не удалось подготовить отчёт", "Could not prepare report"],
    ["Подготовка прервана", "Preparation interrupted"], ["Этап завершён", "Stage completed"],
    ["Запрос отправлен. Ожидаем начало обработки…", "Request sent. Waiting for processing to start…"],
    ["Проверяем состояние задачи", "Checking operation status"],
    ["Локальная сборка без нового обращения к ИИ. Точное время заранее неизвестно.", "Local assembly without another AI request. The exact duration is not known in advance."],
    ["Ориентир для черновика — 1–3 минуты, не гарантия. Модель не сообщает процент готовности.", "A draft usually takes around 1–3 minutes, but this is not guaranteed. The model does not report a completion percentage."],
    [" Запрос выполняется дольше ориентира.", " The request is taking longer than the estimate."],
    ["Открыть отчёт", "Open report"], ["Проверить готовый черновик", "Review completed draft"],
    ["Отчёт сохранён. Можно проверить и сохранить договорённости.", "Report saved. You can review and save agreements."],
    ["Черновик сохранён. Проверьте только отмеченные сомнения перед DOCX.", "Draft saved. Review the flagged uncertainties before creating a DOCX."],
    ["Проверка завершена. Для продолжения откройте замечания к данным встречи.", "Check complete. Open the meeting data issues to continue."],
    ["Откройте восстановление в настройках и проверьте сохранённый результат перед повтором. Запрос мог завершиться у провайдера; повтор может потребовать оплаты.", "Open Recovery in settings and check the saved result before retrying. The provider may have completed the request; retrying may incur a charge."],
    ["Исходные записи сохранены. Откройте восстановление в настройках перед повтором.", "Original recordings are retained. Open Recovery in settings before retrying."],
    ["Нет связи с сервером", "No server connection"], ["{message} · повторяем проверку состояния", "{message} · checking status again"],
    ["Обновить отчёт после продолжения встречи", "Update report after resuming the meeting"], ["Открыть готовый отчёт", "Open completed report"],
    ["Отчёт готовится автоматически. Если имя участника неизвестно, можно назвать голос и сохранить его в банк; подробный разбор фраз необязателен.", "The report is prepared automatically. If a participant is unknown, name their voice and optionally save it to the bank. Detailed utterance review is optional."],
    ["{text} · {count}", "{text} · {count}"],
    ["{prefix}{text}", "{prefix}{text}"],
    ["{messages}", "{messages}"], ["{text} · {time}", "{text} · {time}"],
    ["свернуть панели", "collapse panels"], ["стоп", "stop"],
    ["Остановить и сохранить запись", "Stop and save recording"], ["Начать запись встречи", "Start meeting recording"],
    ["показать историю", "show history"], ["свернуть", "collapse"],
    ["{count} мин", "{count} min"], ["без лимита", "no time limit"],
    ["контекст готов", "context ready"], ["досье загружено", "dossier loaded"], ["без контекста", "no context"],
    ["Я интервьюирую", "I interview"], ["Я прохожу собеседование", "I am the candidate"],
    ["Тренировка собеседования", "Interview practice"], ["Консалтинг с клиентом", "Client consulting"], ["Другая встреча", "Other meeting"],
    ["запись не запущена · микрофон можно проверить кнопкой «проверка звука»", "not recording · use the audio check to test your microphone"],
    ["ОШИБКА ЗАПИСИ: {message}", "RECORDING ERROR: {message}"], ["аудиоканал недоступен", "audio channel unavailable"],
    ["звук идёт · {time} · {files}", "audio active · {time} · {files}"], [" · мик: {device}", " · mic: {device}"],
    [" · встреча: {device}", " · meeting: {device}"], [" · текстовых дублей: {count}", " · duplicate utterances: {count}"],
    ["{value} дБ", "{value} dB"], [" · {value} мс", " · {value} ms"], ["ожидание опоры", "waiting for reference"],
    [" · ВНИМАНИЕ: {message}", " · WARNING: {message}"],
    ["История · ", "History · "], ["реплика", "utterance"], ["реплики", "utterances"], [" · показано {count}", " · showing {count}"],
    ["канал микрофона", "microphone channel"], ["канал системного звука", "system audio channel"],
    ["канал микрофона · фрагментов STT: {count}", "microphone channel · STT fragments: {count}"],
    ["канал системного звука · фрагментов STT: {count}", "system audio channel · STT fragments: {count}"],
    ["Codex · авто · последняя: {model}", "Codex · auto · last: {model}"],
    ["Codex · авто · модель уточняется", "Codex · auto · model not confirmed yet"],
    ["сигналов · {critical} крит. · {warning} вним.", "signals · {critical} critical · {warning} warnings"],
    ["Исходные данные изменились после генерации. Старый черновик нельзя незаметно превратить в новый отчёт — его нужно пересобрать.", "Source data changed after generation. Rebuild the draft before using it as a new report."],
    ["Технических сомнений не найдено. Blatero соберёт финальный документ без дополнительного запроса к модели.", "No technical uncertainties found. Blatero can build the final document without another model request."],
    ["Платный запрос к LLM не выполнялся: сначала нужен пригодный транскрипт.", "No paid AI request was made. A usable transcript is required first."],
    ["Черновик уже готов. Исправьте данные, подтвердите выводы или явно создайте документ с перечисленными ограничениями.", "Draft ready. Correct the data, confirm conclusions or explicitly create a document with the listed limitations."],
    ["Спорных выводов: {count}. Подтвердите их после проверки или исключите из итогового DOCX.", "Conclusions needing a decision: {count}. Confirm them after review or exclude them from the final DOCX."],
    ["Сигнал качества", "Quality signal"], ["Очередь пуста.", "The queue is empty."],
    ["критично", "critical"], ["внимание", "warning"], ["замечание", "notice"],
    ["редакция {revision}", "revision {revision}"],
    ["Локальные метрики, опоры выводов и самоаудит собраны в одну очередь.", "Local metrics, supporting evidence and self-review are collected in one queue."],
    ["Локальные метрики собраны; модель не вернула структурированный самоаудит.", "Local metrics are available; the model did not return a structured self-review."],
    ["Подтверждено: {confirmed} · исключено: {excluded} · ждут решения: {pending}", "Confirmed: {confirmed} · excluded: {excluded} · awaiting a decision: {pending}"],
    ["опора найдена", "evidence found"], ["проверить", "review"], ["нет опоры", "no evidence"],
    ["на проверке", "pending review"], ["подтверждён", "confirmed"], ["исключён из DOCX", "excluded from DOCX"],
    ["подтвердить", "confirm"], ["исключить", "exclude"], ["опора изменилась", "evidence changed"],
    ["открыть реплику и прослушать аудио", "open the utterance and listen to its audio"],
    ["показать локальный файл в Проводнике", "show the local file in File Explorer"],
    ["Вывод", "Conclusion"], ["Вывод: {section}", "Conclusion: {section}"], ["раздел", "section"],
    ["Решение по выводу", "Conclusion decision"], ["сохранить вывод", "save conclusion"],
    ["открыть реплику в локальном редакторе", "open the utterance in the local editor"],
    ["Загружаю локальный черновик…", "Loading the local draft…"], ["есть несохранённые правки", "unsaved edits"],
    ["все правки сохранены", "all edits saved"], ["{count} знаков · {state}", "{count} characters · {state}"],
    ["показано · {total} всего", "shown · {total} total"], ["Реплики не найдены.", "No utterances found."],
    ["Участник", "Participant"], ["уверенность не измерялась", "confidence not measured"],
    ["уверенность {value}%", "confidence {value}%"], ["прослушать этот фрагмент", "listen to this segment"],
    ["для реплики нет аудиодорожки", "no audio track for this utterance"],
    ["ручная правка, редакция {revision}", "manual edit, revision {revision}"], ["исправлено", "edited"],
    ["Текст реплики {time}", "Utterance text {time}"], ["{count} знаков", "{count} characters"],
    ["сохранить реплику", "save utterance"], ["Загружаю канонический транскрипт…", "Loading the canonical transcript…"],
    ["Показана ограниченная часть длинной встречи.", "Only part of this long meeting is shown."],
    ["Все изменения сохраняются только локально.", "All edits are saved locally only."], ["Транскрипт не загружен.", "Transcript not loaded."],
    ["Сначала сохраните правки черновика отчёта.", "Save the report draft edits first."],
    ["Сохраняю реплику и пересобираю Markdown…", "Saving the utterance and rebuilding Markdown…"],
    ["Текст не изменился.", "The text has not changed."],
    ["Реплика сохранена. Черновик отчёта помечен устаревшим до пересборки.", "Utterance saved. The report draft is marked stale until rebuilt."],
    ["Аудио не запущено: {message}", "Audio did not start: {message}"],
    ["Не сохранено: {message}", "Not saved: {message}"], ["Сохраняю локально…", "Saving locally…"],
    ["Сначала сохраните изменённый текст, затем примите решение.", "Save the edited text before making a decision."],
    ["сохраняю…", "saving…"],
    ["Записей пока нет. Создайте встречу и начните запись.", "No recordings yet. Create a meeting and start recording."],
    ["идёт запись", "recording"], ["{count} аудиодор. · {time}", "{count} audio tracks · {time}"],
    ["аудио нет", "no audio"], ["разобрать запись{suffix}", "review recording{suffix}"],
    ["дождитесь остановки", "wait for recording to stop"], ["нет записи для разбора", "no recording to review"],
    ["Переименовать говорящих", "Rename speakers"], ["для этой встречи · без банка голосов", "for this meeting · no voice bank required"],
    ["имена появятся после прогона с диаризацией", "speaker names become available after diarization"], ["текущая", "current"],
    ["Калибровка выполнена", "Calibration complete"], ["Аудиомаршрут готов к записи.", "The audio route is ready for recording."],
    ["Идёт калибровка", "Calibration in progress"], ["Не говорите, пока звучит тестовый сигнал.", "Do not speak while the test signal is playing."],
    ["Калибровка пропущена для этой записи", "Calibration skipped for this recording"],
    ["Можно начинать, но звук встречи может повторно попасть в ваш микрофон.", "You can start, but meeting audio may leak back into your microphone."],
    ["Перед записью рекомендуется калибровка", "Calibration is recommended before recording"],
    ["Она проверит выход встречи и акустическое эхо; аудио никуда не отправляется.", "It checks the meeting output and acoustic echo without sending audio anywhere."],
    ["В какой роли вы участвуете?", "What is your role?"],
    ["Я задаю вопросы и оцениваю кандидата", "I ask questions and assess the candidate"],
    ["Меня спрашивают — нужен быстрый и корректный ответ", "I answer questions and need quick, accurate help"],
    ["ИИ спрашивает, подсказывает и оценивает как работодатель", "AI asks questions, provides hints and assesses me as an employer"],
    ["Выяснять запрос, риски и договорённости", "Clarify needs, risks and agreements"],
    ["Нейтральные подсказки и протокол", "Neutral hints and meeting notes"],
    ["Кто участвовал во встрече?", "Who took part in the meeting?"],
    ["Технический разбор выполняется локально. Вам — только узнать неизвестный голос.", "Technical analysis runs locally. You only need to identify unknown voices."],
    ["Готово", "Done"], ["Автоматически найти голоса", "Find voices automatically"],
    ["Что происходит с данными?", "What happens to the data?"],
    ["Все дорожки звука встречи обрабатываются локально. Исходные WAV и транскрипты не изменяются. Совпадение с банком — предположение, которое может быть ошибочным. Имя сохраняется в этом разборе; само по себе оно не переименовывает реплики и не пересобирает уже готовый отчёт. Голосовой отпечаток хранится в банке только по отдельному согласию. Удалить его можно в настройках банка голосов.", "All meeting audio tracks are processed locally. Original WAV files and transcripts are unchanged. A voice-bank match is a suggestion and may be wrong. A name is saved in this review; this alone does not rename utterances or rebuild an existing report. A voiceprint is stored in the bank only with separate consent and can be deleted in voice-bank settings."],
    ["Предположения банка и уже названные голоса", "Bank suggestions and named voices"],
    ["Неизвестный участник", "Unknown participant"], ["Предположение банка · {reason}", "Bank suggestion · {reason}"],
    ["проверьте на слух", "check by listening"], ["Имя подтверждено вами", "Name confirmed by you"],
    ["Назовите участника по короткому образцу", "Name the participant from a short sample"],
    ["▶ Послушать голос", "▶ Listen to voice"], ["Не удалось воспроизвести: {message}", "Playback failed: {message}"],
    ["Имя участника", "Participant name"], ["Голос уже сохранён в банке", "Voice already saved in the bank"],
    ["Есть согласие участника: сохранить голосовой отпечаток в банке для следующих встреч", "Participant consent obtained: save a voiceprint for future meetings"],
    ["Сохранить имя", "Save name"], ["Сохранить имя и голос в банк", "Save name and voice to bank"],
    ["Ищем голоса во всех дорожках; это может занять несколько минут…", "Finding voices in all tracks; this may take a few minutes…"],
    ["Сохраняем локально…", "Saving locally…"], ["Ищем голоса локально", "Finding voices locally"],
    ["Предыдущий разбор прерван. Можно повторить; исходные записи сохранены.", "The previous review was interrupted. You can retry; original recordings are retained."],
    ["После разбора появились новые дорожки. Обработаем их, сохранив уже указанные имена.", "New tracks were added after the review. We will process them while keeping existing names."],
    ["Локально найдём голоса во всех дорожках встречи. Аудио никуда не отправляется.", "Find voices locally in all meeting tracks. No audio is sent anywhere."],
    ["Проверьте только неизвестные голоса. Совпадения с банком — предположения, не доказательство личности. Транскрипты не менялись.", "Review unknown voices only. Bank matches are suggestions, not proof of identity. Transcripts are unchanged."],
    ["Разбор не завершён. Исходные записи сохранены; можно повторить локальную подготовку.", "Review did not complete. Original recordings are retained; you can retry local preparation."],
    ["размечено", "labeled"], ["точность допуска", "acceptance precision"], ["верхняя граница 95%", "95% upper bound"],
    ["ручная проверка", "manual review"], ["{confirmed} подтверждено · {excluded} исключено", "{confirmed} confirmed · {excluded} excluded"],
    ["{safe} верных · {unsafe} опасных", "{safe} correct · {unsafe} unsafe"], ["цель не выше {value}", "target at most {value}"],
    ["{count} выводов остановлено", "{count} conclusions held for review"], ["{count} / {target} · встреч: {sessions}", "{count} / {target} · meetings: {sessions}"],
    ["В текущем отчёте размечено выводов: {labeled} из {total}.", "Conclusions labeled in this report: {labeled} of {total}."],
    [" Он полностью вошёл в корпус.", " The full report is included in the corpus."],
    [" Подтвердите или исключите остальные, если хотите использовать его как полный эталон.", " Confirm or exclude the remaining conclusions to use it as a complete reference."],
    ["В текущем отчёте пока нет размечаемых выводов.", "This report has no conclusions to label yet."],
    ["Корпус достаточен: текущая граница допуска выдерживает целевой риск.", "The corpus is sufficient: the current acceptance bound meets the target risk."],
    ["Это измерение, а не автоматическое разрешение кадрового решения.", "This is a measurement, not automatic authorization for a hiring decision."],
    ["Текущий автоматический допуск не выдерживает целевой риск.", "The current automatic acceptance rule does not meet the target risk."],
    ["До пересмотра правил все выводы следует проверять вручную.", "Review every conclusion manually until the rules are revised."],
    ["Корпус пока мал — пороги и правила заблокированы.", "The corpus is still too small; thresholds and rules are locked."],
    ["нет ссылки на реплику", "no utterance reference"], ["реплика не найдена", "utterance not found"],
    ["низкая уверенность STT", "low STT confidence"], ["самоаудит: нет опоры", "self-review: no evidence"],
    ["самоаудит: противоречие", "self-review: contradiction"], ["сигнал", "signal"], ["исключено {value}", "excluded {value}"],
    ["questions.md ещё нет — генерирую…", "questions.md is not available yet — preparing…"],
    ["задать вопрос голосом", "read question aloud"], ["Почему:", "Why:"], ["Факт и связь:", "Source and relevance:"],
    ["эталон ответа", "reference answer"], ["ветки ({count})", "follow-ups ({count})"],
    ["материал", "material"], ["материал · готово", "material · ready"],
    ["Добавить документ или снимок без остановки записи", "Add a document or screenshot without stopping recording"],
    ["ВСТРЕЧА → РАБОТА", "MEETING → WORK"], ["Задачи встречи", "Meeting tasks"],
    ["Связать встречу с проектом", "Link meeting to a project"], ["Задачи встречи · {count}", "Meeting tasks · {count}"],
    ["по связанным задачам", "from linked tasks"], ["предложение по рабочей папке", "suggested by project folder"],
    ["предложение по названию", "suggested by name"], ["Контекст задач недоступен", "Task context unavailable"],
    ["Проверить договорённости", "Review agreements"], ["Что запомнить к следующей встрече", "What to remember for the next meeting"],
    ["Закрыть проверку договорённостей", "Close agreement review"],
    ["Проверьте формулировки, ответственных и сроки. В память попадут только отмеченные пункты после нажатия «Подтвердить и сохранить». Неотмеченные останутся на потом. Статусы задач не меняются.", "Review the wording, owners and due dates. Only checked items are added to memory when you choose Confirm and save. Unchecked items remain for later. Task statuses are unchanged."],
    ["Позже", "Later"], ["Добавить вручную", "Add manually"], ["Новый черновик из отчёта", "New draft from report"],
    ["Отклонить оставшееся", "Reject remaining"], ["Подтвердить и сохранить", "Confirm and save"],
    ["пункт", "item"], ["пункта", "items"], ["пунктов", "items"],
    ["Договорённости проверены", "Agreements reviewed"], ["Следующий шаг — память проекта", "Next step — project memory"],
    ["Добавлено в память: {count}. Подтверждённые пункты подтянутся при подготовке следующей встречи этого проекта.", "Added to memory: {count}. Confirmed items will be included when preparing this project’s next meeting."],
    ["В черновике {points}. Они ещё не в памяти: проверьте их и сохраните выбранные.", "The draft contains {points}. They are not in memory yet; review them and save your selection."],
    ["После подготовки пунктов изменился отчёт или проект. Обновите черновик перед сохранением.", "The report or project changed after the items were prepared. Update the draft before saving."],
    ["Укажите проект или рабочую папку встречи: без этого договорённости не с чем связать.", "Set the meeting’s project or folder so agreements can be linked to it."],
    ["Отчёт сам по себе не пополняет память. Подготовьте предложения, проверьте их и сохраните нужные для следующей встречи.", "A report does not populate memory by itself. Prepare suggestions, review them and save those needed for the next meeting."],
    ["Указать проект", "Set project"], ["Посмотреть память", "View memory"], ["Проверить {points}", "Review {points}"],
    ["Не удалось обновить память", "Could not update memory"],
    ["Отчёт или проект изменились. Старые пункты сохранены, но подтверждение заблокировано. Создайте новый черновик по текущему отчёту; предыдущий останется в резервной копии.", "The report or project changed. Existing items are retained, but confirmation is blocked. Create a draft from the current report; the previous draft remains in a backup."],
    ["Это ранее созданный черновик без контрольной суммы отчёта. Пункты не пересоздавались. Сверьте основания перед подтверждением.", "This is an older draft without a report checksum. Its items were not recreated. Review their sources before confirming."],
    ["Решение", "Decision"], ["Действие / обещание", "Action / commitment"], ["Открытый вопрос", "Open question"], ["Подтверждённый факт", "Confirmed fact"],
    ["Формулировка", "Wording"], ["Куда сохранить", "Save to"], ["Тип записи", "Entry type"],
    ["Проект", "Project"], ["Клиент", "Client"], ["{scope}: {label}", "{scope}: {label}"],
    ["Ответственный · если известен", "Owner · if known"], ["Срок или условие · если названы", "Due date or condition · if stated"],
    ["Основание в отчёте", "Evidence in report"],
    ["Проверка завершена. Добавлено в память: {count}. Для следующей встречи будут использоваться подтверждённые записи.", "Review complete. Added to memory: {count}. The next meeting will use confirmed entries."],
    ["В явных разделах отчёта не найдены пункты для переноса. Можно добавить договорённость вручную; программа ничего не додумывала.", "No items were found in the report’s explicit sections. You can add an agreement manually; the application did not infer missing items."],
    ["Подтвердить: сохранять нечего", "Confirm: nothing to save"], ["Подтвердить и сохранить ({count})", "Confirm and save ({count})"],
    ["Сначала завершите запись.", "Stop recording first."], ["Читаю итоговый отчёт и сохранённый черновик…", "Reading the final report and saved draft…"],
    ["Пока это предложения. Память изменится только после вашего подтверждения.", "These are suggestions. Memory changes only after your confirmation."],
    ["Заполните формулировку выбранного пункта.", "Enter the wording for the selected item."], ["Выберите хотя бы один пункт.", "Choose at least one item."],
    ["Сохраняю выбранные пункты в локальную память…", "Saving selected items to local memory…"],
    ["Сохранено в память: {saved}. Осталось проверить: {pending}.", "Saved to memory: {saved}. Remaining for review: {pending}."],
    ["{message} Несохранённые правки оставлены в форме.", "{message} Unsaved edits are retained in the form."],
    ["Отклонить все оставшиеся предложения? Отчёт и уже сохранённая память останутся.", "Reject all remaining suggestions? The report and saved memory will remain."],
    ["Создать новый черновик по текущему отчёту? Предыдущий сохранится в резервной копии.", "Create a draft from the current report? The previous draft will be kept in a backup."],
    ["Оставшиеся предложения отклонены.", "Remaining suggestions rejected."], ["Новый черновик подготовлен локально.", "New draft prepared locally."],
    ["Встреча изменилась.", "The meeting changed."],
    ["Сведения о встрече", "Meeting details"],
    ["Читаем банк голосов", "Loading voice bank"], ["Разделяем голоса", "Separating voices"],
    ["Читаем аудио", "Loading audio"], ["Вычисляем голосовые признаки", "Extracting voice features"],
    ["Сравниваем с банком", "Matching against voice bank"], ["Готовим образцы", "Preparing samples"],
    ["{stage} · дорожка {track} из {total}", "{stage} · track {track} of {total}"],
    ["Прогресс текущего этапа", "Current stage progress"],
    ["Обработано: {done} из {total}", "Processed: {done} of {total}"], ["Скрыть", "Hide"],
    ["Прошло {time} · общее время заранее неизвестно", "Elapsed {time} · total duration is not yet known"],
    ["Время разбора: {time}", "Review duration: {time}"], ["Время по этапам", "Stage timings"],
    ["{stage}: {seconds} с", "{stage}: {seconds} s"],
    ["Дорожка {track}: найдено {count} голосовых кластеров. Это не число участников; возможна избыточная разбивка.", "Track {track}: {count} voice clusters found. This is not a participant count; the audio may be over-segmented."],
    ["Дорожки или банк голосов обновились. Повторите разбор; подтверждённые имена для неизменённых дорожек сохранятся.", "Audio tracks or the voice bank have changed. Run the review again; confirmed names for unchanged tracks will be kept."],
    ["Операция не завершена", "Operation did not complete"],
    ["Повторите сравнение с банком голосов", "Run voice bank matching again"],
    ["Результат разделения голосов изменился. Повторите разбор; предыдущая версия сохранена.", "The voice separation result has changed. Run the review again; the previous version has been kept."]
  ];
  const i18n=window.BlateroI18n;
  if(!i18n)return;
  const entries=Object.fromEntries(phrases.map((pair,index)=>['meeting.'+index,pair]));
  i18n.register(entries);
  const normal=value=>String(value??'').replace(/\s+/g,' ').trim();
  const aliases=new Map();
  for(const [key,pair] of Object.entries(entries))for(const phrase of pair)aliases.set(normal(phrase),key);
  const labels=new Map(),attributes=new Map();
  const escape=value=>String(value??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  function ui(source,params={}){
    const key=aliases.get(normal(source));
    return key?i18n.t(key,params):String(source??'').replace(/\{([a-zA-Z_]\w*)\}/g,
      (match,name)=>Object.hasOwn(params,name)?String(params[name]):match);
  }
  function label(element,source,params={}){
    if(!element)return;
    labels.set(element,{source,params});element.removeAttribute('data-meeting-key');
    element.textContent=ui(source,typeof params==='function'?params():params);
    element.lang=aliases.has(normal(source))?i18n.language:/[а-яё]/i.test(source)?'ru':i18n.language;
  }
  function attr(element,name,source,params={}){
    if(!element)return;
    if(!attributes.has(element))attributes.set(element,new Map());
    attributes.get(element).set(name,{source,params});
    element.removeAttribute('data-meeting-'+name);
    element.setAttribute(name,ui(source,typeof params==='function'?params():params));
  }
  function text(source,params={}){
    const key=aliases.get(normal(source));
    return key?'<span data-meeting-key="'+key+'" data-meeting-params="'+escape(JSON.stringify(params))+'" lang="'+i18n.language+'">'+escape(ui(source,params))+'</span>':escape(ui(source,params));
  }
  function attrs(name,source,params={}){
    const key=aliases.get(normal(source));
    return name+'="'+escape(ui(source,params))+'"'+(key?' data-meeting-'+name+'="'+key+'" data-meeting-'+name+'-params="'+escape(JSON.stringify(params))+'"':'');
  }
  function apply(scope=document){
    const find=selector=>[...(scope.matches?.(selector)?[scope]:[]),...scope.querySelectorAll(selector)];
    for(const node of find('[data-meeting-source]')){
      const key=aliases.get(normal(node.dataset.meetingSource));
      if(key){node.dataset.meetingKey=key;node.dataset.meetingParams=node.dataset.meetingSourceParams||'{}';}
      node.removeAttribute('data-meeting-source');node.removeAttribute('data-meeting-source-params');
    }
    for(const name of ['title','aria-label','placeholder','data-tooltip'])
      for(const node of find('[data-meeting-source-'+name+']')){
        const key=aliases.get(normal(node.getAttribute('data-meeting-source-'+name)));
        if(key){node.setAttribute('data-meeting-'+name,key);node.setAttribute('data-meeting-'+name+'-params',node.getAttribute('data-meeting-source-'+name+'-params')||'{}');}
        node.removeAttribute('data-meeting-source-'+name);node.removeAttribute('data-meeting-source-'+name+'-params');
      }
    for(const node of find('[data-meeting-key]')){
      const key=node.dataset.meetingKey;if(!entries[key])continue;
      node.textContent=i18n.t(key,JSON.parse(node.dataset.meetingParams||'{}'));node.lang=i18n.language;
    }
    for(const name of ['title','aria-label','placeholder','data-tooltip'])
      for(const node of find('[data-meeting-'+name+']')){
        const key=node.getAttribute('data-meeting-'+name);if(entries[key])
          node.setAttribute(name,i18n.t(key,JSON.parse(node.getAttribute('data-meeting-'+name+'-params')||'{}')));
      }
  }
  function bindStatic(scope){
    // Only freshly created interface fragments, before attaching user data.
    const walker=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT),nodes=[];
    while(walker.nextNode())nodes.push(walker.currentNode);
    for(const node of nodes){
      if(node.parentElement.closest('textarea,script,style,pre,code'))continue;
      const key=aliases.get(normal(node.textContent));if(!key)continue;
      if(node.parentElement.tagName==='OPTION'){node.parentElement.dataset.meetingKey=key;continue;}
      const span=document.createElement('span');span.dataset.meetingKey=key;span.textContent=node.textContent;node.replaceWith(span);
    }
    for(const element of [scope,...scope.querySelectorAll('[title],[aria-label],[placeholder],[data-tooltip]')])
      for(const name of ['title','aria-label','placeholder','data-tooltip']){
        const key=aliases.get(normal(element.getAttribute(name)));if(key)element.setAttribute('data-meeting-'+name,key);
      }
    apply(scope);
  }
  function refresh(){
    apply();
    for(const [element,value] of labels){if(!element.isConnected){labels.delete(element);continue;}label(element,value.source,value.params);}
    for(const [element,values] of attributes){if(!element.isConnected){attributes.delete(element);continue;}for(const [name,value] of values)attr(element,name,value.source,value.params);}
  }
  function forget(element){labels.delete(element);element?.removeAttribute('data-meeting-key');}
  window.BlateroMeetingI18n={ui,label,attr,text,attrs,bindStatic,refresh,forget};
  const pending=window.__blateroMeetingPending;
  if(pending){
    for(const [element,value] of pending.labels)if(element.isConnected)label(element,value.text,value.params);
    for(const [element,values] of pending.attrs)if(element.isConnected)for(const [name,value] of values)attr(element,name,value.text,value.params);
    delete window.__blateroMeetingPending;
  }
  document.addEventListener('blatero:language',refresh);refresh();
  if(typeof renderMeetSummary==='function')renderMeetSummary();
})();
