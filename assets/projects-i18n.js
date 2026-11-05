'use strict';
// Owned tracker UI only. Never bind a populated task, source or quoted answer.
(() => {
  const pairs = /* PROJECT_PHRASES */ [
  [
    "Исходные документы еще не привязаны.",
    "No source documents are linked yet."
  ],
  [
    "Открыть карточку",
    "Open task"
  ],
  [
    "Документы проекта",
    "Project documents"
  ],
  [
    "Исторические сессии ·",
    "Past sessions ·"
  ],
  [
    "Технические запуски сохранены как источники. Показаны 100 последних; полный каталог доступен агентам локально.",
    "Technical runs are retained as sources. The latest 100 are shown; agents can access the full local catalog."
  ],
  [
    "Цель:",
    "Goal:"
  ],
  [
    "Метод:",
    "Method:"
  ],
  [
    "Почему:",
    "Rationale:"
  ],
  [
    "Оцените собственное воспроизведение. Это пробное расписание возвращений.",
    "Rate your recall. This is a trial review schedule."
  ],
  [
    "Не вспомнил · завтра",
    "Did not recall · tomorrow"
  ],
  [
    "Частично · через 3 дня",
    "Partly · in 3 days"
  ],
  [
    "Помню · через 7 дней",
    "Recalled · in 7 days"
  ],
  [
    "Без подсказки ответьте своими словами:",
    "Answer in your own words without a hint:"
  ],
  [
    "Что нужно получить?",
    "What is the intended outcome?"
  ],
  [
    "Как решаем задачу?",
    "How are we approaching the task?"
  ],
  [
    "Почему выбрали этот метод?",
    "Why did we choose this method?"
  ],
  [
    "Мой пересказ",
    "My explanation"
  ],
  [
    "Можно проговорить вслух или записать здесь. Текст не оценивается моделью и не сохраняется.",
    "Say it aloud or write it here. The text is not assessed by AI or saved."
  ],
  [
    "Показать карточку и сверить",
    "Show task and compare"
  ],
  [
    "Записей пока нет. Метод и причина выбора уже доступны выше.",
    "No entries yet. The method and rationale are available above."
  ],
  [
    "Подтвердить содержание",
    "Confirm content"
  ],
  [
    "Основания:",
    "Evidence:"
  ],
  [
    "Проверки пока не записаны.",
    "No checks have been recorded yet."
  ],
  [
    "Первоначальное заполнение по",
    "Initially populated from"
  ],
  [
    "историческим сессиям. Поля восстановлены из сообщений; приемка результата и актуальность требуют сверки.",
    "past sessions. Fields were recovered from messages; acceptance and current relevance need review."
  ],
  [
    "Содержание изменения",
    "Change details"
  ],
  [
    "Источники и прежнее решение",
    "Sources and earlier decision"
  ],
  [
    "Связанная история",
    "Related history"
  ],
  [
    "Здесь сохранены исходные карточки: их поля, источники и знания доступны отдельно. Связь не означает приёмку результата.",
    "Original tasks are retained here, with their fields, sources and knowledge available separately. Linking is not acceptance."
  ],
  [
    "Следующее возвращение:",
    "Next review:"
  ],
  [
    "· самооценка редакции",
    "· self-assessed revision"
  ],
  [
    "Без проекта",
    "No project"
  ],
  [
    "Самостоятельная задача",
    "Standalone task"
  ],
  [
    "Решение",
    "Decision"
  ],
  [
    "Факт",
    "Fact"
  ],
  [
    "Ограничение",
    "Constraint"
  ],
  [
    "Открытый вопрос",
    "Open question"
  ],
  [
    "Выберите источник ниже",
    "Choose a source below"
  ],
  [
    "Артефакт",
    "Artifact"
  ],
  [
    "Обсуждение",
    "Discussion"
  ],
  [
    "Проверка",
    "Check"
  ],
  [
    "· редакция",
    "· revision"
  ],
  [
    "· обновлено",
    "· updated"
  ],
  [
    "Статус",
    "Status"
  ],
  [
    "Проект",
    "Project"
  ],
  [
    "Название",
    "Title"
  ],
  [
    "Что решаем",
    "Goal"
  ],
  [
    "Выбранный метод",
    "Chosen method"
  ],
  [
    "Почему подходит",
    "Rationale"
  ],
  [
    "Следующий шаг",
    "Next step"
  ],
  [
    "Приоритет",
    "Priority"
  ],
  [
    "Срок",
    "Due date"
  ],
  [
    "Родительская задача",
    "Parent task"
  ],
  [
    "Сохранить карточку",
    "Save task"
  ],
  [
    "Знания и решения",
    "Knowledge and decisions"
  ],
  [
    "Решение или факт",
    "Decision or fact"
  ],
  [
    "Тип",
    "Type"
  ],
  [
    "Основание",
    "Source"
  ],
  [
    "Сохранить предложение",
    "Save proposal"
  ],
  [
    "Источники и результаты",
    "Sources and results"
  ],
  [
    "Что подтверждает источник",
    "What the source supports"
  ],
  [
    "Ссылка или путь",
    "Link or path"
  ],
  [
    "Добавить источник",
    "Add source"
  ],
  [
    "Проверки",
    "Checks"
  ],
  [
    "Сессии и история",
    "Sessions and history"
  ],
  [
    "Закрепление",
    "Recall practice"
  ],
  [
    "Вспомнить суть и метод",
    "Recall goal and method"
  ],
  [
    "Предложение из истории",
    "Proposal from history"
  ],
  [
    "Историческая карточка связана с текущей работой. Исходные данные сохранены.",
    "This past task is linked to current work. Original data is retained."
  ],
  [
    "Открыть актуальную карточку",
    "Open current task"
  ],
  [
    "Без проекта — разобрать позже",
    "No project — sort out later"
  ],
  [
    "Все проекты",
    "All projects"
  ],
  [
    "Разобрать привязку",
    "Review project assignment"
  ],
  [
    "Принятые задачи",
    "Accepted tasks"
  ],
  [
    "С подтвержденной приемкой",
    "With confirmed acceptance"
  ],
  [
    "Связанные сессии",
    "Linked sessions"
  ],
  [
    "В журнале Neon найдены:",
    "Found in the Neon log:"
  ],
  [
    "Эквивалент API, USD",
    "API-equivalent cost, USD"
  ],
  [
    "Задача",
    "Task"
  ],
  [
    "Приемка",
    "Acceptance"
  ],
  [
    "Сессии / покрытие",
    "Sessions / coverage"
  ],
  [
    "Загружаю связь с Neon Legion…",
    "Loading Neon Legion links…"
  ],
  [
    "Сначала определить проект",
    "Choose the project first"
  ],
  [
    "Исторические связи этих задач не подтверждены. Выберите проект карточки, чтобы сравнивать расходы.",
    "These historical project assignments are unconfirmed. Assign a project before comparing costs."
  ],
  [
    "Попробовать вспомнить",
    "Try to recall"
  ],
  [
    "Цель → метод → причина",
    "Goal → method → rationale"
  ],
  [
    "Выберите задачу и перескажите эти три пункта до открытия карточки.",
    "Choose a task and explain these three points before opening it."
  ],
  [
    "Это добровольная самооценка. Она не влияет на статус работы.",
    "This is an optional self-assessment. It does not affect task status."
  ],
  [
    "Далее:",
    "Next:"
  ],
  [
    "Проверить, что помню",
    "Check my recall"
  ],
  [
    "Сначала суть и метод. Предложения агентов подтверждаются отдельно и сохраняют ссылки на основания.",
    "Start with the goal and method. Agent proposals require separate confirmation and retain source references."
  ],
  [
    "Начнем с одной задачи",
    "Start with one task"
  ],
  [
    "Создайте проект и задачу. Агенты смогут сохранять решения и двигать карточки.",
    "Create a project and a task. Agents can record decisions and move tasks."
  ],
  [
    "Добавить задачу",
    "Add task"
  ],
  [
    "Высокий приоритет",
    "High priority"
  ],
  [
    "Подзадача",
    "Subtask"
  ],
  [
    "Из истории",
    "From history"
  ],
  [
    "До",
    "Due"
  ],
  [
    "Статус задачи {p0}",
    "Status of task {p0}"
  ],
  [
    "Карточек в этом представлении",
    "Tasks in this view"
  ],
  [
    "восстановлены из истории",
    "recovered from history"
  ],
  [
    "Новых незавершенных задач",
    "New unfinished tasks"
  ],
  [
    "Остальные статусы требуют сверки",
    "Other statuses need review"
  ],
  [
    "Показать ещё",
    "Show more"
  ],
  [
    "показано",
    "showing"
  ],
  [
    "из",
    "of"
  ],
  [
    "Здесь пока нет задач",
    "No tasks here yet"
  ],
  [
    "Нет новых доступных исходников. Добавьте статью в библиотеку Гранки и обновите источники во вкладке «Материалы».",
    "No new sources are available. Add an article to Granka and refresh sources in Materials."
  ],
  [
    "Выберите статью",
    "Choose an article"
  ],
  [
    "Статья в Гранке",
    "Article in Granka"
  ],
  [
    "Связать статью",
    "Link article"
  ],
  [
    "Связать статью с задачей",
    "Link an article to this task"
  ],
  [
    "Источник изменился. Первоначальное основание сохранено.",
    "The source changed. The original evidence is retained."
  ],
  [
    "Источник сейчас недоступен.",
    "The source is currently unavailable."
  ],
  [
    "Содержание источника",
    "Source contents"
  ],
  [
    "Снять связь",
    "Unlink"
  ],
  [
    "Встречи и статьи",
    "Meetings and articles"
  ],
  [
    "Статьи задачи",
    "Task articles"
  ],
  [
    "Место в плане",
    "Schedule"
  ],
  [
    "Начало работы",
    "Start time"
  ],
  [
    "Длительность, минут",
    "Duration, minutes"
  ],
  [
    "Время ввода — часовой пояс вашего компьютера. Пустое начало снимает задачу с расписания.",
    "Enter time in your computer’s time zone. Clear the start time to remove the task from the schedule."
  ],
  [
    "Сохранить план",
    "Save schedule"
  ],
  [
    "Читаю связи…",
    "Loading links…"
  ],
  [
    "Пересечения в плане:",
    "Schedule conflicts:"
  ],
  [
    "Есть место в плане",
    "Time available"
  ],
  [
    "К встрече ↗",
    "Open meeting ↗"
  ],
  [
    "Предыдущая неделя",
    "Previous week"
  ],
  [
    "Неделя",
    "Week"
  ],
  [
    "Следующая неделя",
    "Next week"
  ],
  [
    "Сегодня",
    "Today"
  ],
  [
    "Время: Москва · встречи и задачи",
    "Moscow time · meetings and tasks"
  ],
  [
    "Назначьте начало и длительность в карточке. Срок задачи и дата публикации показаны отдельно. Внешние календари читаются из последнего снимка Blatero.",
    "Set start time and duration in the task. Due dates and publication dates are shown separately. External calendars use Blatero’s latest snapshot."
  ],
  [
    "Назначить время",
    "Schedule tasks"
  ],
  [
    "Готовность в Гранке:",
    "Readiness in Granka:"
  ],
  [
    "Источник больше не найден. Снимок и связи сохранены.",
    "The source is no longer available. Its snapshot and links are retained."
  ],
  [
    "Подключение выключено. Снимок и связи сохранены.",
    "The connection is disabled. Its snapshot and links are retained."
  ],
  [
    "Источник обновился после привязки. Сверьте новое содержание.",
    "The source changed after linking. Review its updated contents."
  ],
  [
    "Выберите карточку",
    "Choose a task"
  ],
  [
    "Создать задачу в проекте",
    "Create a task in project"
  ],
  [
    "Создать карточку",
    "Create task"
  ],
  [
    "Или связать с задачей",
    "Or link to a task"
  ],
  [
    "Связать с карточкой",
    "Link to task"
  ],
  [
    "Материалов в этом представлении нет",
    "No materials in this view"
  ],
  [
    "Обновите источники или выберите все проекты. Привязанные материалы появятся в своём проекте.",
    "Refresh sources or select all projects. Linked materials appear under their project."
  ],
  [
    "Показаны первые 200. Используйте поиск или фильтр вида.",
    "Showing the first 200. Use search or filter by kind."
  ],
  [
    "Все материалы",
    "All materials"
  ],
  [
    "Обновить источники",
    "Refresh sources"
  ],
  [
    "Вид",
    "Kind"
  ],
  [
    "материалов ·",
    "materials ·"
  ],
  [
    "Встречи, договорённости и статьи остаются в своих приложениях. Связь сохраняет снимок источника; обновление не меняет ваши решения и статус карточки.",
    "Meetings, agreements and articles remain in their applications. A link retains a source snapshot; refreshing does not change your decisions or task status."
  ],
  [
    "Выберите проект",
    "Choose a project"
  ],
  [
    "В плане:",
    "Scheduled:"
  ],
  [
    "мин",
    "min"
  ],
  [
    "Загружаю локальный план…",
    "Loading the local schedule…"
  ],
  [
    "Здесь собраны общие и личные вопросы",
    "General and personal items"
  ],
  [
    "Откройте доску или список, чтобы прочитать историю. Для планирования рабочих задач выберите проект.",
    "Open the board or list to read their history. Select a project to schedule work."
  ],
  [
    "Общие и личные вопросы",
    "General and personal items"
  ],
  [
    "Читать публикацию ↗",
    "Read publication ↗"
  ],
  [
    "Редактировать в Гранке ↗",
    "Edit in Granka ↗"
  ],
  [
    "Открыть встречу ↗",
    "Open meeting ↗"
  ],
  [
    "Для ежедневного закрепления заполните суть, метод и причину выбора.",
    "Enter the goal, method and rationale to enable daily recall practice."
  ],
  [
    "Запросить решение",
    "Request a decision"
  ],
  [
    "Вопрос пользователю",
    "Question for the user"
  ],
  [
    "Рекомендация и причина",
    "Recommendation and rationale"
  ],
  [
    "Добавить в очередь внимания",
    "Add to attention queue"
  ],
  [
    "Сверьте текущие суть, метод и следующий шаг перед ответом.",
    "Review the current goal, method and next step before answering."
  ],
  [
    "Рекомендация:",
    "Recommendation:"
  ],
  [
    "Нужен твой ответ",
    "Your answer is needed"
  ],
  [
    "Моё решение",
    "My decision"
  ],
  [
    "Сохранить решение",
    "Save decision"
  ],
  [
    "Ответ сохраняется в истории. Статус и метод агент обновит отдельно.",
    "The answer is saved in history. The agent updates status and method separately."
  ],
  [
    "Сегодня: фокус и решения",
    "Today: focus and decisions"
  ],
  [
    "Сделать текущей задачей",
    "Set as current task"
  ],
  [
    "СЛЕДУЮЩИЙ ШАГ",
    "NEXT STEP"
  ],
  [
    "Продолжить задачу ↗",
    "Continue task ↗"
  ],
  [
    "Вспомнить метод",
    "Recall the method"
  ],
  [
    "Метод и причина выбора",
    "Method and rationale"
  ],
  [
    "Снять фокус",
    "Clear focus"
  ],
  [
    "Открытых вопросов нет.",
    "No open questions."
  ],
  [
    "Агент может оставить вопрос и рекомендацию в карточке.",
    "An agent can leave a question and recommendation in the task."
  ],
  [
    "Рекомендация агента",
    "Agent recommendation"
  ],
  [
    "Контекст изменился после вопроса. Сверьте актуальную карточку.",
    "The context changed after the question. Review the current task."
  ],
  [
    "Ответить в карточке ↗",
    "Answer in task ↗"
  ],
  [
    "Показаны 3 из",
    "Showing 3 of"
  ],
  [
    ". После ответа появится следующий вопрос.",
    ". The next question appears after you answer."
  ],
  [
    "Все вопросы",
    "All questions"
  ],
  [
    "Новых результатов на проверке нет.",
    "No new results awaiting review."
  ],
  [
    "Открыть список задач",
    "Open task list"
  ],
  [
    "Ближайшее время свободно. Назначьте начало работы в карточке или добавьте встречу.",
    "No upcoming events. Schedule a task or add a meeting."
  ],
  [
    "Пересечения в ближайшем плане:",
    "Upcoming schedule conflicts:"
  ],
  [
    ". Проверьте расписание.",
    ". Review the schedule."
  ],
  [
    "Сейчас 2 темы из",
    "Showing 2 topics of"
  ],
  [
    ". После самооценки очередь обновится.",
    ". The queue updates after self-assessment."
  ],
  [
    "У",
    "For"
  ],
  [
    "отмеченных задач не хватает сути, метода или причины. Дополните карточки.",
    "marked tasks, the goal, method or rationale is missing. Complete those fields."
  ],
  [
    "Выберите задачу",
    "Choose a task"
  ],
  [
    "/ МСК",
    "/ MSK"
  ],
  [
    "КОНТЕКСТ НА СВЯЗИ",
    "CONTEXT CONNECTED"
  ],
  [
    "01 / ФОКУС",
    "01 / FOCUS"
  ],
  [
    "ОДНА ЗАДАЧА",
    "ONE TASK"
  ],
  [
    "Текущая задача",
    "Current task"
  ],
  [
    "Сохранить фокус",
    "Save focus"
  ],
  [
    "Новая задача",
    "New task"
  ],
  [
    "Фокус общий для всего пространства. Выбор сохраняется в базе и не меняет статус карточки.",
    "Focus is shared across the workspace. Your choice is saved without changing task status."
  ],
  [
    "02 / ТВОЁ РЕШЕНИЕ",
    "02 / YOUR DECISION"
  ],
  [
    "Ждут твоего ответа",
    "Awaiting your answer"
  ],
  [
    "Результаты на проверке ·",
    "Results awaiting review ·"
  ],
  [
    "Это готовность к проверке. Приёмка результата — отдельное действие.",
    "These results are ready for review. Acceptance is a separate action."
  ],
  [
    "03 / БЛИЖАЙШЕЕ",
    "03 / UPCOMING"
  ],
  [
    "7 ДНЕЙ",
    "7 DAYS"
  ],
  [
    "Место для важного",
    "Time for what matters"
  ],
  [
    "Открыть весь план ↗",
    "Open full schedule ↗"
  ],
  [
    "Календари — из последнего снимка.",
    "Calendars use the latest snapshot."
  ],
  [
    "04 / ЗАКРЕПИТЬ",
    "04 / RECALL"
  ],
  [
    "ДО 5 МИНУТ",
    "UP TO 5 MINUTES"
  ],
  [
    "Сначала вспомни сам",
    "Recall it first"
  ],
  [
    "Суть → метод → почему. Затем сверься с карточкой.",
    "Goal → method → rationale. Then check the task."
  ],
  [
    "Самооценка назначает возвращение через 1, 3 или 7 дней. Пересказ не сохраняется; уведомлений нет.",
    "Self-assessment schedules a review in 1, 3 or 7 days. Your explanation is not saved; there are no notifications."
  ],
  [
    "Выбрать другую задачу ↗",
    "Choose another task ↗"
  ],
  [
    "Фокус — во всём пространстве; вопросы, проверка, план и закрепление — в выбранном проекте. Поиск и период истории здесь не применяются.",
    "Focus spans the workspace; questions, review, schedule and recall use the selected project. Search and history period do not apply here."
  ],
  [
    "Отвеченных вопросов пока нет.",
    "No answered questions yet."
  ],
  [
    "Источник ответа",
    "Answer source"
  ],
  [
    "Исходная цитата:",
    "Original quote:"
  ],
  [
    "Чат Codex ·",
    "Codex chat ·"
  ],
  [
    "Вопрос:",
    "Question:"
  ],
  [
    "Ответ:",
    "Answer:"
  ],
  [
    "Отвеченные ·",
    "Answered ·"
  ],
  [
    "Собираю сегодняшний день…",
    "Loading today’s workspace…"
  ],
  [
    "· ранее:",
    "· previously:"
  ],
  [
    "Если задача больше не актуальна, укажите причину закрытия. Результат не будет автоматически принят.",
    "If the task is no longer relevant, record why it is being closed. Its result is not automatically accepted."
  ],
  [
    "Закрыть задачу",
    "Close task"
  ],
  [
    "Чтобы изменить поля или план, восстановите карточку. Добавлять источники и предложения можно без восстановления.",
    "Reopen the task to edit its fields or schedule. You can add sources and proposals while it is closed."
  ],
  [
    "Восстановить во входящие",
    "Reopen in inbox"
  ],
  [
    "Восстановить в работу",
    "Reopen in progress"
  ],
  [
    "Закрытых карточек пока нет",
    "No closed tasks yet"
  ],
  [
    "Их можно вернуть во входящие или в работу в любой момент.",
    "You can reopen them in the inbox or in progress at any time."
  ],
  [
    "Закрытие сохраняет историю и материалы. Оно не означает приёмку результата. Здесь показаны закрытые карточки за всё время; поиск и фильтр проекта работают.",
    "Closing retains history and materials. It is not acceptance. Closed tasks from all time are shown here; search and project filters still apply."
  ],
  [
    "ЗАКРЫТО",
    "CLOSED"
  ],
  [
    "Причина:",
    "Reason:"
  ],
  [
    "Во входящие",
    "To inbox"
  ],
  [
    "В работу",
    "Start work"
  ],
  [
    "Длинные поля сокращены до 4000 знаков. Полный текст — в карточке.",
    "Long fields are limited to 4,000 characters here. Open the task for the full text."
  ],
  [
    "Редакция",
    "Revision"
  ],
  [
    "Поля совпадают. Это не доказывает одинаковый результат.",
    "The fields match. This does not prove the outcomes are identical."
  ],
  [
    "Зарегистрированных источников нет.",
    "No registered sources."
  ],
  [
    "Карточка",
    "Task"
  ],
  [
    "Текущий снимок обеих карточек",
    "Current snapshot of both tasks"
  ],
  [
    "Отличающиеся поля ·",
    "Different fields ·"
  ],
  [
    "История и зависимости",
    "History and dependencies"
  ],
  [
    "Общих записей источников:",
    "Shared source entries:"
  ],
  [
    "; уникальных:",
    "; unique:"
  ],
  [
    ". Общих привязанных сессий:",
    ". Shared linked sessions:"
  ],
  [
    "Подзадач:",
    "Subtasks:"
  ],
  [
    "; связей с материалами:",
    "; material links:"
  ],
  [
    "Источники обеих карточек",
    "Sources from both tasks"
  ],
  [
    "Отпечаток снимка:",
    "Snapshot fingerprint:"
  ],
  [
    "Объединение недоступно в этом просмотре.",
    "Merging is not available in this view."
  ],
  [
    "Совпадений много: показаны первые 200 новых пар. Уточните проект.",
    "Many matches found: showing the first 200 new pairs. Select a project to narrow the results."
  ],
  [
    "В этой выборке пар нет.",
    "No pairs in this selection."
  ],
  [
    "· ред.",
    "· rev."
  ],
  [
    "Карточка изменилась после снимка оснований. Нужна повторная сверка.",
    "The task changed after the evidence snapshot. Review it again."
  ],
  [
    "Сравнить поля и связи",
    "Compare fields and links"
  ],
  [
    "Основания и ограничения",
    "Evidence and limitations"
  ],
  [
    "СРАВНЕНИЕ / БЕЗ ИЗМЕНЕНИЙ",
    "COMPARE / READ ONLY"
  ],
  [
    "Возможные слияния",
    "Possible merges"
  ],
  [
    "Пока ничего не объединяем. Сходство — повод проверить цель, результат и границы работы.",
    "No tasks are merged here. Similarity is a reason to review goals, outcomes and scope."
  ],
  [
    "Обновить карточки",
    "Refresh tasks"
  ],
  [
    "Условных дублей:",
    "Possible import duplicates:"
  ],
  [
    "Неопределённых пар:",
    "Uncertain pairs:"
  ],
  [
    "Совпадений названий без разбора:",
    "Unreviewed title matches:"
  ],
  [
    "Исторический разбор:",
    "Historical review:"
  ],
  [
    ". Поля ниже прочитаны сейчас. Поиск и период истории не применяются; используется фильтр проекта.",
    ". Fields below were read just now. Search and history period do not apply; the project filter does."
  ],
  [
    "Что показать",
    "Show"
  ],
  [
    "Все пары ·",
    "All pairs ·"
  ],
  [
    "Первичные источники ещё не разобраны.",
    "Primary sources have not been reviewed yet."
  ],
  [
    "Сопоставляю карточки…",
    "Comparing tasks…"
  ],
  [
    "Закрыть проект",
    "Close project"
  ],
  [
    "Закрыть",
    "Close"
  ],
  [
    "Проект уйдёт из основного списка в группу «Закрытые проекты». Задачи, материалы и знания сохранятся. Проект можно восстановить.",
    "The project moves to Closed projects. Tasks, materials and knowledge are retained. You can reopen the project."
  ],
  [
    "Причина",
    "Reason"
  ],
  [
    "(необязательно)",
    "(optional)"
  ],
  [
    "Например, работа завершена или проект отложен",
    "For example, work is complete or the project is postponed"
  ],
  [
    "Отмена",
    "Cancel"
  ],
  [
    "Нет совпадений с поиском.",
    "No search matches."
  ],
  [
    "Закрытые проекты",
    "Closed projects"
  ],
  [
    "Вся работа.",
    "All your work."
  ],
  [
    "В поле зрения.",
    "In view."
  ],
  [
    "Без локальной рабочей папки",
    "No local project folder"
  ],
  [
    "Задачи, решения и следующий шаг — в одном месте.",
    "Tasks, decisions and next steps in one place."
  ],
  [
    "Сохранено",
    "Saved"
  ],
  [
    "Возвращение записано:",
    "Review scheduled:"
  ],
  [
    "Еще не записана",
    "Not recorded yet"
  ],
  [
    "Еще не выбран",
    "Not chosen yet"
  ],
  [
    "Причина еще не записана",
    "Rationale not recorded yet"
  ],
  [
    "Добавлено карточек: {p0}",
    "Tasks added: {p0}"
  ],
  [
    "Подтверждено пользователем",
    "Confirmed by the user"
  ],
  [
    "Предложение агента",
    "Agent proposal"
  ],
  [
    "открыта",
    "open"
  ],
  [
    "остановлена",
    "stopped"
  ],
  [
    "Сначала выберите проект задачи",
    "Choose the task’s project first"
  ],
  [
    "Изменения сохранены локально",
    "Changes saved locally"
  ],
  [
    "Отклоненных событий в журнале: {p0}",
    "Rejected events in log: {p0}"
  ],
  [
    "В очереди: {p0}, обрабатываются: {p1}",
    "Queued: {p0}, processing: {p1}"
  ],
  [
    "Нет данных",
    "No data"
  ],
  [
    "Нужно определить",
    "Not defined yet"
  ],
  [
    "Локальная карточка",
    "Local task"
  ],
  [
    "{p0} сессий",
    "Sessions: {p0}"
  ],
  [
    "Восстановлено по {p0} локальным сессиям. Исторические статусы предварительные; сведения агентов сохранены как предложения. Неясная привязка: {p1} карточек.",
    "Recovered from {p0} local sessions. Historical statuses are provisional; agent information is retained as proposals. Uncertain project assignments: {p1} tasks."
  ],
  [
    "Проектов в пространстве",
    "Projects in workspace"
  ],
  [
    "Сессий в каталоге",
    "Sessions in catalog"
  ],
  [
    "Суть → метод → следующий шаг",
    "Goal → method → next step"
  ],
  [
    "Источники и связи сохранены",
    "Sources and links retained"
  ],
  [
    "Не удалось выполнить действие",
    "Could not complete the action"
  ],
  [
    "Сервер недоступен или требуется вход в Blatero",
    "The server is unavailable or you need to sign in to Blatero"
  ],
  [
    "Высокий",
    "High"
  ],
  [
    "Обычный",
    "Normal"
  ],
  [
    "Низкий",
    "Low"
  ],
  [
    "Закрыто",
    "Closed"
  ],
  [
    "Завершено",
    "Done"
  ],
  [
    "На проверке",
    "Review"
  ],
  [
    "Ожидает",
    "Waiting"
  ],
  [
    "В работе",
    "In progress"
  ],
  [
    "Входящие",
    "Inbox"
  ],
  [
    "Выберите проект новой карточки",
    "Choose a project for the new task"
  ],
  [
    "Сначала сохраните изменения карточки, затем свяжите статью",
    "Save task changes before linking an article"
  ],
  [
    "Нужен дополнительный контекст",
    "More context is needed"
  ],
  [
    "Общий или личный вопрос",
    "General or personal item"
  ],
  [
    "Календарь",
    "Calendar"
  ],
  [
    "Срок ещё не задан",
    "No due date set"
  ],
  [
    "Срок:",
    "Due:"
  ],
  [
    "На этот день",
    "On this day"
  ],
  [
    "Срок задачи",
    "Task due date"
  ],
  [
    "источники ещё не прочитаны",
    "sources have not been loaded yet"
  ],
  [
    "обновлено",
    "updated"
  ],
  [
    "Дата",
    "Date"
  ],
  [
    "Публикация",
    "Publication"
  ],
  [
    "Содержание",
    "Contents"
  ],
  [
    "Протокол",
    "Meeting report"
  ],
  [
    "Открыть связанную задачу",
    "Open linked task"
  ],
  [
    "Восстановлено по {p0} локальным сессиям. Исторические статусы предварительные. Нужно уточнить проект: {p1}; общих и личных вопросов: {p2}.",
    "Recovered from {p0} local sessions. Historical statuses are provisional. Project assignment needs review: {p1}; general and personal items: {p2}."
  ],
  [
    "Разовые и личные вопросы из истории. Источники сохранены; рабочий проект им не приписан.",
    "One-off and personal items from history. Sources are retained; no work project is assigned."
  ],
  [
    "Идея",
    "Idea"
  ],
  [
    "Опубликована",
    "Published"
  ],
  [
    "Готова",
    "Ready"
  ],
  [
    "Черновик",
    "Draft"
  ],
  [
    "Закрыта в источнике",
    "Closed in source"
  ],
  [
    "Открыта",
    "Open"
  ],
  [
    "Есть протокол",
    "Report available"
  ],
  [
    "Есть запись",
    "Recording available"
  ],
  [
    "Запланирована",
    "Scheduled"
  ],
  [
    "Статья",
    "Article"
  ],
  [
    "Договорённость",
    "Agreement"
  ],
  [
    "Встреча",
    "Meeting"
  ],
  [
    "Решение сохранено в истории карточки",
    "Decision saved in task history"
  ],
  [
    "Вопрос добавлен в очередь внимания",
    "Question added to the attention queue"
  ],
  [
    "Настройка закрепления сохранена",
    "Recall preference saved"
  ],
  [
    "Текущая задача сохранена",
    "Current task saved"
  ],
  [
    "Закреплять важное решение",
    "Add to daily recall"
  ],
  [
    "Убрать из ежедневного закрепления",
    "Remove from daily recall"
  ],
  [
    "Фокус снят",
    "Focus cleared"
  ],
  [
    "Фокус сохранён",
    "Focus saved"
  ],
  [
    "Совпадений нет",
    "No matches"
  ],
  [
    "Название, суть или метод",
    "Title, goal or method"
  ],
  [
    "Найти задачу для фокуса",
    "Find a task to focus on"
  ],
  [
    "Выбери, с чего продолжить",
    "Choose where to continue"
  ],
  [
    "Один явный выбор поможет вернуться к сути после переключения.",
    "Choose one task to make it easier to resume after switching context."
  ],
  [
    "Предыдущая задача завершена или связана с другой карточкой. Выберите новый фокус.",
    "The previous task is done or merged into another task. Choose a new focus."
  ],
  [
    "Суть ещё не записана. Дополните карточку.",
    "The goal is not recorded yet. Add it to the task."
  ],
  [
    "Определите следующий шаг в карточке.",
    "Define the next step in the task."
  ],
  [
    "Ещё не выбран",
    "Not chosen yet"
  ],
  [
    "Ещё не записано",
    "Not recorded yet"
  ],
  [
    "Выбрать текущую задачу",
    "Choose current task"
  ],
  [
    "Сменить текущую задачу",
    "Change current task"
  ],
  [
    "Личный календарь",
    "Personal calendar"
  ],
  [
    "Гранка пока не подключена.",
    "Granka is not connected yet."
  ],
  [
    "Показаны 6 из {p0}.",
    "Showing 6 of {p0}."
  ],
  [
    "Отметь важную задачу для закрепления в её карточке.",
    "Enable daily recall in a task you want to revisit."
  ],
  [
    "На сегодня возвращений нет.",
    "No reviews scheduled for today."
  ],
  [
    "Сохранён в интерфейсе",
    "Saved in the interface"
  ],
  [
    "Записан агентом из чата",
    "Recorded by an agent from chat"
  ],
  [
    "· из истории, требует сверки",
    "· from history, needs review"
  ],
  [
    "Карточка закрыта. Она доступна в разделе «Закрытые».",
    "Task closed. It is available under Closed."
  ],
  [
    "Укажите причину закрытия",
    "Enter a reason for closing"
  ],
  [
    "Закрытие задачи",
    "Close this task"
  ],
  [
    "Карточка закрыта",
    "Task is closed"
  ],
  [
    "Последнее закрытие",
    "Last closure"
  ],
  [
    "Причина закрытия",
    "Closure reason"
  ],
  [
    "Смотрите историю карточки",
    "See task history"
  ],
  [
    "Карточка восстановлена:",
    "Task reopened:"
  ],
  [
    "Не задано",
    "Not set"
  ],
  [
    "основания самооценок",
    "self-assessment evidence"
  ],
  [
    "подзадачи",
    "subtasks"
  ],
  [
    "связанная история",
    "related history"
  ],
  [
    "материалы",
    "materials"
  ],
  [
    "пометки разбора",
    "review notes"
  ],
  [
    "темы закрепления",
    "recall topics"
  ],
  [
    "вопросы",
    "questions"
  ],
  [
    "импортированные сессии",
    "imported sessions"
  ],
  [
    "рабочие сессии",
    "work sessions"
  ],
  [
    "события",
    "events"
  ],
  [
    "самооценки",
    "self-assessments"
  ],
  [
    "проверки",
    "checks"
  ],
  [
    "подтверждения",
    "confirmations"
  ],
  [
    "записи знаний",
    "knowledge entries"
  ],
  [
    "источники",
    "sources"
  ],
  [
    "нет",
    "none"
  ],
  [
    "Не перепроверено",
    "Not rechecked"
  ],
  [
    "Источник изменился",
    "Source changed"
  ],
  [
    "Хеш сверён при разборе",
    "Hash verified during review"
  ],
  [
    "· поле карточки",
    "· task field"
  ],
  [
    "Оценка времени",
    "Estimated duration"
  ],
  [
    "Начало",
    "Start"
  ],
  [
    "Родитель",
    "Parent"
  ],
  [
    "Почему выбран",
    "Rationale"
  ],
  [
    "Метод",
    "Method"
  ],
  [
    "Суть",
    "Goal"
  ],
  [
    "Разные задачи",
    "Unrelated tasks"
  ],
  [
    "Связанные работы",
    "Related work"
  ],
  [
    "Продолжение",
    "Continuation"
  ],
  [
    "Совпадение названий",
    "Matching titles"
  ],
  [
    "Нужен разбор результата",
    "Outcome review needed"
  ],
  [
    "Условный дубль импорта",
    "Possible import duplicate"
  ],
  [
    "Проект перемещён в «Закрытые проекты»",
    "Project moved to Closed projects"
  ],
  [
    "Проект восстановлен",
    "Project reopened"
  ],
  [
    "Все текущие статусы задач сохранятся.",
    "All current task statuses are retained."
  ],
  [
    "В проекте {p0} незавершённых задач. Их статусы не изменятся.",
    "Unfinished tasks in this project: {p0}. Their statuses are unchanged."
  ],
  [
    "Восстановить проект",
    "Reopen project"
  ],
  [
    "привязок нужно уточнить",
    "assignments need review"
  ],
  [
    "{p0} сессий в памяти{p1}",
    "Sessions retained: {p0}{p1}"
  ],
  [
    "Причина закрытия · сохранённая история · ручное восстановление",
    "Closure reason · retained history · manual reopening"
  ],
  [
    "Можно вернуться к любой задаче",
    "Return to any task"
  ],
  [
    "Приёмка и связанные сессии Neon Legion",
    "Acceptance and linked Neon Legion sessions"
  ],
  [
    "Результат и затраты",
    "Outcome and cost"
  ],
  [
    "Сначала свой ответ, затем подсказка",
    "Your answer first, then the reference"
  ],
  [
    "Вспомнить. Закрепить. Продолжить.",
    "Recall. Review. Continue."
  ],
  [
    "Документы · задачи · решения · история обсуждений",
    "Documents · tasks · decisions · discussion history"
  ],
  [
    "Библиотека общего контекста",
    "Shared context library"
  ],
  [
    "Статус, срок и следующий шаг",
    "Status, due date and next step"
  ],
  [
    "Весь объём перед глазами",
    "All tasks in view"
  ],
  [
    "Встречи · договорённости · статьи",
    "Meetings · agreements · articles"
  ],
  [
    "У каждой задачи есть основание",
    "Sources behind every task"
  ],
  [
    "Встречи, работа и публикации в одном плане",
    "Meetings, work and publications in one schedule"
  ],
  [
    "Время для важного",
    "Time for what matters"
  ],
  [
    "Перетаскивайте карточки между колонками",
    "Drag tasks between columns"
  ],
  [
    "От замысла к результату",
    "From idea to outcome"
  ],
  [
    "Один фокус · решения · ближайший план · память",
    "One focus · decisions · upcoming plans · recall"
  ],
  [
    "С чего продолжим сегодня",
    "Where to continue today"
  ],
  [
    "Проекты · Blatero",
    "Projects · Blatero"
  ],
  [
    "ЛОКАЛЬНОЕ ПРОСТРАНСТВО",
    "LOCAL WORKSPACE"
  ],
  [
    "Время в Москве",
    "Moscow time"
  ],
  [
    "Включить или выключить анимации",
    "Turn animations on or off"
  ],
  [
    "Движение",
    "Animation"
  ],
  [
    "Переключить тему",
    "Switch theme"
  ],
  [
    "Тема",
    "Theme"
  ],
  [
    "+ Проект",
    "+ Project"
  ],
  [
    "Проекты",
    "Projects"
  ],
  [
    "ПРОЕКТЫ",
    "PROJECTS"
  ],
  [
    "Найти проект",
    "Find a project"
  ],
  [
    "Поиск по пространству",
    "Search workspace"
  ],
  [
    "Выбор проекта",
    "Select a project"
  ],
  [
    "ПАМЯТЬ НА СВЯЗИ",
    "SHARED CONTEXT"
  ],
  [
    "Люди + агенты. Общий контекст.",
    "People + agents. Shared context."
  ],
  [
    "РАБОТА × ПАМЯТЬ",
    "WORK × MEMORY"
  ],
  [
    "О проекте",
    "About project"
  ],
  [
    "Понимать сейчас.",
    "Understand now."
  ],
  [
    "Помнить потом.",
    "Remember later."
  ],
  [
    "КОНТУР РАБОТЫ / 01",
    "WORKFLOW / 01"
  ],
  [
    "01 / СУТЬ",
    "01 / GOAL"
  ],
  [
    "02 / МЕТОД",
    "02 / METHOD"
  ],
  [
    "03 / РЕЗУЛЬТАТ",
    "03 / OUTCOME"
  ],
  [
    "Обзор рабочего пространства",
    "Workspace overview"
  ],
  [
    "История рабочего пространства",
    "Workspace history"
  ],
  [
    "Подробнее +",
    "More +"
  ],
  [
    "Поиск задач",
    "Find tasks"
  ],
  [
    "Найти задачу, метод или решение",
    "Find a task, method or decision"
  ],
  [
    "Период истории",
    "History period"
  ],
  [
    "Последние 30 дней",
    "Last 30 days"
  ],
  [
    "Вся история",
    "All history"
  ],
  [
    "Только новые задачи",
    "New tasks only"
  ],
  [
    "Представление проектов",
    "Project view"
  ],
  [
    "Доска",
    "Board"
  ],
  [
    "План",
    "Schedule"
  ],
  [
    "Материалы",
    "Materials"
  ],
  [
    "Список",
    "List"
  ],
  [
    "Библиотека",
    "Library"
  ],
  [
    "Вспомнить",
    "Recall"
  ],
  [
    "Эффективность",
    "AI usage"
  ],
  [
    "Сравнение",
    "Compare"
  ],
  [
    "Закрытые",
    "Closed"
  ],
  [
    "Новый проект",
    "New project"
  ],
  [
    "Общее описание",
    "Description"
  ],
  [
    "Рабочая папка",
    "Project folder"
  ],
  [
    "Например, C:/Projects/blatero",
    "For example, C:/Projects/example"
  ],
  [
    "Папка помогает агенту выбрать проект. Для общей рабочей папки привязку выбираем явно.",
    "The folder helps an agent identify the project. For a shared workspace, choose the project explicitly."
  ],
  [
    "Создать проект",
    "Create project"
  ],
  [
    "Что должно получиться",
    "Expected outcome"
  ],
  [
    "Создать и открыть",
    "Create and open"
  ],
  [
    "Принять результат",
    "Accept result"
  ],
  [
    "Карточка перейдет в «Завершено». Приемка сохранится в истории.",
    "The task moves to Done. Acceptance is recorded in history."
  ],
  [
    "Какой результат проверен и принят",
    "What result was checked and accepted"
  ],
  [
    "Принять и завершить",
    "Accept and finish"
  ],
  [
    "Карточка уйдёт из текущей доски. История и материалы сохранятся; восстановление доступно в разделе «Закрытые». Закрытие не означает приёмку результата.",
    "The task leaves the current board. History and materials are retained; reopen it under Closed. Closing is not acceptance."
  ],
  [
    "Почему задача больше не актуальна",
    "Why this task is no longer relevant"
  ],
  [
    "Завершён разовый аудит; задача отменена или заменена; служебная запись",
    "One-off audit completed; task cancelled or replaced; administrative entry"
  ],
  [
    "Вспомнить без подсказки",
    "Recall without a hint"
  ],
  [
    "Восстановить проект {name}",
    "Reopen project {name}"
  ],
  [
    "Закрыть проект {name}",
    "Close project {name}"
  ],
  [
    "Карточка восстановлена: {status}",
    "Task reopened: {status}"
  ],
  [
    "Возвращение записано: {date}",
    "Review scheduled: {date}"
  ],
  [
    "{time} / МСК",
    "{time} / MSK"
  ],
  [
    "Blatero — рабочее пространство",
    "Blatero — workspace"
  ],
  [
    "Рабочее пространство",
    "Workspace"
  ],
  [
    "Все задачи проекта",
    "All project tasks"
  ],
  [
    "Показать закрытые",
    "Show closed tasks"
  ],
  [
    "Снимает поиск и ограничение истории. Закрытие не удаляет карточку.",
    "Clears search and history limits. Closing does not delete a task."
  ],
  [
    "Обсудить на новой встрече ↗",
    "Discuss in a new meeting ↗"
  ],
  [
    "Эта карточка закрыта и скрыта на обычной доске.",
    "This task is closed and hidden from the regular board."
  ],
  [
    "Карточка не видна из-за выбранного проекта, поиска или фильтра истории.",
    "This task is hidden by the project, search or history filter."
  ],
  [
    "Показать в закрытых",
    "Show under Closed"
  ],
  [
    "Показать в списке задач",
    "Show in task list"
  ],
  [
    "Показаны только карточки выбранной встречи. Фильтр снимается выбором проекта.",
    "Only tasks linked to the selected meeting are shown. Select a project to clear this filter."
  ],
  [
    "Анимации отключены настройкой системы",
    "Animations are disabled by a system preference"
  ],
  [
    "Выключить анимации",
    "Turn animations off"
  ],
  [
    "Включить анимации",
    "Turn animations on"
  ],
  [
    "Учитывается системная настройка уменьшения движения",
    "The system reduced-motion preference is respected"
  ],
  [
    "Все пары · {count}",
    "All pairs · {count}"
  ],
  [
    "Условный дубль импорта · {count}",
    "Possible import duplicates · {count}"
  ],
  [
    "Нужен разбор результата · {count}",
    "Outcome review needed · {count}"
  ],
  [
    "Совпадение названий · {count}",
    "Matching titles · {count}"
  ],
  [
    "Продолжение · {count}",
    "Continuations · {count}"
  ],
  [
    "Связанные работы · {count}",
    "Related work · {count}"
  ],
  [
    "Разные задачи · {count}",
    "Unrelated tasks · {count}"
  ],
  [
    "Отмеченных задач без сути, метода или причины: {count}. Дополните карточки.",
    "Marked tasks missing a goal, method or rationale: {count}. Complete those fields."
  ],
  [
    "Материалов: {count} ·",
    "Materials: {count} ·"
  ],
  [
    "Ещё",
    "More"
  ],
  ["Не удалось сохранить черновик в этой вкладке","Could not save the draft in this tab"],
  ["Восстановлен черновик. Карточка изменилась; проверьте поля перед сохранением.","Draft restored. The task has changed; review the fields before saving."],
  ["Восстановлен черновик из этой вкладки.","Draft restored from this tab."],
  ["Сбросить черновик","Discard draft"],
  ["Удалить несохранённый черновик?","Discard the unsaved draft?"],
  ["Вся история карточки","Full task history"],
  ["Раздел истории","History section"],
  ["Повторения","Recalls"],
  ["Показать ещё","Show more"],
  ["Показано {count} из {total}","Showing {count} of {total}"],
  ["Паспорт проекта","Project overview"],
  ["Файлы и записи не перемещаются. Меняется путь проекта; его ID, задачи и история сохраняются.","Files and recordings are not moved. The project path changes; its ID, tasks and history are preserved."],
  ["Проверить и сохранить проект","Review and save project"],
  ["Отменить изменения проекта?","Discard project changes?"],
  ["Задач: {tasks} · документов: {documents}. Файлы не перемещаются.","Tasks: {tasks} · documents: {documents}. Files are not moved."],
  ["Сохранить изменения проекта?","Save project changes?"],
  ["Проект сохранён","Project saved"],
  ["Изменения проекта","Project changes"]
];
  const i18n=window.BlateroI18n;
  if(!i18n)return;
  const entries=Object.fromEntries(pairs.map((pair,index)=>['project.'+index,pair]));
  i18n.register(entries);
  const normal=value=>String(value??'').replace(/\s+/g,' ').trim();
  const aliases=new Map();
  for(const [key,pair] of Object.entries(entries))for(const phrase of pair)if(!aliases.has(normal(phrase)))aliases.set(normal(phrase),key);
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels=new Map(),attributes=new Map();
  const params=value=>typeof value==='function'?value():value;
  const resolve=(source,values)=>typeof source==='function'?source():{source,values:params(values)};
  const parse=value=>{try{return JSON.parse(value||'{}');}catch{return {};}};
  function ui(source,values={}){
    source=String(source??'');const key=aliases.get(normal(source));
    const translated=key?i18n.t(key,values):source.replace(/\{([a-zA-Z_]\w*)\}/g,
      (match,name)=>Object.hasOwn(values,name)?String(values[name]):match);
    return key?source.match(/^\s*/)[0]+translated+source.match(/\s*$/)[0]:translated;
  }
  function bind(source,values={}){
    const key=aliases.get(normal(source));
    return key?'data-project-key="'+key+'" data-project-params="'+escape(JSON.stringify(values))+'" lang="'+i18n.language+'"':'';
  }
  function text(source,values={}){
    return '<span '+bind(source,values)+'>'+escape(ui(source,values))+'</span>';
  }
  function attrs(name,source,values={}){
    const key=aliases.get(normal(source));
    return name+'="'+escape(ui(source,values))+'"'+(key?' data-project-'+name+'="'+key+'" data-project-'+name+'-params="'+escape(JSON.stringify(values))+'"':'');
  }
  function forget(element){
    if(!element)return;labels.delete(element);element.removeAttribute('data-project-key');element.removeAttribute('data-project-params');
  }
  function value(element,raw){if(!element)return;forget(element);element.textContent=String(raw??'');}
  function label(element,source,values={}){
    if(!element)return;forget(element);const resolved=resolve(source,values);
    const node=document.createTextNode(ui(resolved.source,resolved.values));element.replaceChildren(node);
    labels.set(element,{source,values,node});element.lang=i18n.language;
    if(labels.size>256)for(const node of labels.keys())if(!node.isConnected)labels.delete(node);
  }
  function attr(element,name,source,values={}){
    if(!element)return;
    if(!attributes.has(element))attributes.set(element,new Map());
    attributes.get(element).set(name,{source,values});element.removeAttribute('data-project-'+name);
    element.setAttribute(name,ui(source,params(values)));
  }
  function time(source,options={}){
    if(!source)return '';
    const timestamp=source instanceof Date?source.toISOString():String(source);
    return '<time datetime="'+escape(timestamp)+'" data-project-date="'+escape(timestamp)+'" data-project-date-options="'+escape(JSON.stringify(options))+'">'+escape(formatTime(timestamp,options))+'</time>';
  }
  function formatTime(source,options){return new Date(source).toLocaleString(i18n.locale,options);}
  function apply(scope=document){
    const find=selector=>[...(scope.matches?.(selector)?[scope]:[]),...scope.querySelectorAll(selector)];
    for(const element of find('[data-project-key]')){
      const key=element.dataset.projectKey;if(!entries[key])continue;
      element.textContent=i18n.t(key,parse(element.dataset.projectParams));element.lang=i18n.language;
    }
    for(const name of ['title','aria-label','placeholder','data-tooltip'])for(const element of find('[data-project-'+name+']')){
      const key=element.getAttribute('data-project-'+name);if(entries[key])element.setAttribute(name,i18n.t(key,parse(element.getAttribute('data-project-'+name+'-params'))));
    }
    for(const element of find('[data-project-date]'))element.textContent=formatTime(element.dataset.projectDate,parse(element.dataset.projectDateOptions));
  }
  function bindStatic(scope){
    // Call only on source-authored fragments before user values are attached.
    const walker=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT),nodes=[];
    while(walker.nextNode())nodes.push(walker.currentNode);
    for(const node of nodes){
      if(node.parentElement.closest('textarea,script,style,pre,code'))continue;
      const key=aliases.get(normal(node.textContent));if(!key)continue;
      if(['OPTION','TITLE'].includes(node.parentElement.tagName)){node.parentElement.dataset.projectKey=key;continue;}
      const span=document.createElement('span');span.dataset.projectKey=key;span.textContent=node.textContent;node.replaceWith(span);
    }
    for(const element of scope.querySelectorAll('[title],[aria-label],[placeholder],[data-tooltip]'))for(const name of ['title','aria-label','placeholder','data-tooltip']){
      const key=aliases.get(normal(element.getAttribute(name)));if(key)element.setAttribute('data-project-'+name,key);
    }
    apply(scope);
  }
  function refresh(){
    apply();
    for(const [element,entry] of labels){
      if(!element.isConnected||entry.node.parentNode!==element){labels.delete(element);continue;}
      const resolved=resolve(entry.source,entry.values);entry.node.textContent=ui(resolved.source,resolved.values);element.lang=i18n.language;
    }
    for(const [element,values] of attributes){if(!element.isConnected){attributes.delete(element);continue;}for(const [name,entry] of values)attr(element,name,entry.source,entry.values);}
  }
  window.BlateroProjectsI18n={ui,text,bind,attrs,label,attr,value,forget,time,bindStatic,refresh};
  document.addEventListener('blatero:language',refresh);
  bindStatic(document);
})();
