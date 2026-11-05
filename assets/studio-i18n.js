'use strict';
// Owned studio copy only; never scan user or generated content.
(() => {
  const pairs = /* STUDIO_PHRASES */ [
  [
    "попытка",
    "attempt"
  ],
  [
    "содержание",
    "content"
  ],
  [
    "самостоятельность",
    "independence"
  ],
  [
    "следующий фокус",
    "next focus"
  ],
  [
    "появится после ответов",
    "available after your answers"
  ],
  [
    "профиль",
    "profile"
  ],
  [
    "общий между тренировками",
    "shared across practice sessions"
  ],
  [
    "эта сессия",
    "this session"
  ],
  [
    "повторить сейчас",
    "review now"
  ],
  [
    "закрепить",
    "practise"
  ],
  [
    "устойчиво",
    "consistent"
  ],
  [
    "поддерживать",
    "maintain"
  ],
  [
    "· дальше",
    "· next"
  ],
  [
    "· ответов",
    "· answers"
  ],
  [
    "Карта заполнится после завершённой попытки. Текущие ответы уже влияют на выбор следующего вопроса, но попадут в историю только после завершения.",
    "The map is saved when the attempt is completed. Your answers already inform the next question, but enter history only on completion."
  ],
  [
    "Тренировка собеседования",
    "Interview practice"
  ],
  [
    "оценок пока нет",
    "no scores yet"
  ],
  [
    "содержание {p0}/10 · самостоятельность {p1}",
    "content {p0}/10 · independence {p1}"
  ],
  [
    "Задайте роль и материалы — тренажёр подготовит вопросы.",
    "Set a role and add materials to prepare questions."
  ],
  [
    "План готов. Нажмите «начать тренировку» — запись включится перед первым вопросом.",
    "The plan is ready. Select Start practice; recording begins before the first question."
  ],
  [
    "Отвечайте голосом. Текстовое поле нужно только как запасной вариант.",
    "Answer aloud. Use the text field only as a fallback."
  ],
  [
    "Все вопросы пройдены. Завершите тренировку, чтобы получить отчёт.",
    "All questions are complete. Finish practice to create the report."
  ],
  [
    "Тренировка завершена. Можно открыть отчёт или повторить попытку.",
    "Practice complete. Open the report or try again."
  ],
  [
    "Настройте LLM и включите согласие в Настройки → Приватность: вопросы и оценки создаёт выбранный ИИ.",
    "Configure AI and allow cloud processing in Settings → Privacy. The selected AI creates questions and feedback."
  ],
  [
    "повторить тренировку",
    "try again"
  ],
  [
    "продолжить тренировку",
    "resume practice"
  ],
  [
    "начать тренировку",
    "start practice"
  ],
  [
    "Все вопросы пройдены — можно формировать итоговый разбор.",
    "All questions are complete. You can create the final review."
  ],
  [
    "вопрос",
    "question"
  ],
  [
    "готово",
    "done"
  ],
  [
    "проверяет: {p0}",
    "assesses: {p0}"
  ],
  [
    "маршрут: {p0}",
    "route: {p0}"
  ],
  [
    "Подсказка {p0}/3: {p1}",
    "Hint {p0}/3: {p1}"
  ],
  [
    "ещё подсказка ({p0}/3)",
    "another hint ({p0}/3)"
  ],
  [
    "подсказка",
    "hint"
  ],
  [
    "Последняя оценка ·",
    "Latest feedback ·"
  ],
  [
    "Содержание:",
    "Content:"
  ],
  [
    "/10 · самостоятельность:",
    "/10 · independence:"
  ],
  [
    "/10 · готовность:",
    "/10 · readiness:"
  ],
  [
    "/10 · подсказок:",
    "/10 · hints used:"
  ],
  [
    "Сильные стороны",
    "Strengths"
  ],
  [
    "Что улучшить",
    "Areas to improve"
  ],
  [
    "Исправления",
    "Corrections"
  ],
  [
    "Улучшенный ответ",
    "Improved answer"
  ],
  [
    "Что ещё спросит работодатель",
    "Possible follow-up question"
  ],
  [
    "быстрый ответ",
    "quick answer"
  ],
  [
    "подсказки",
    "hints"
  ],
  [
    "Готовый ответ на вопрос",
    "Answer to the current question"
  ],
  [
    "Подсказки наблюдателю сценки",
    "Hints for the scene observer"
  ],
  [
    "Завершите текущий разговор перед сменой состава участников.",
    "Finish the current conversation before changing participants."
  ],
  [
    "Настройте LLM и подтвердите облачную обработку в Настройки → Приватность.",
    "Configure AI and allow cloud processing in Settings → Privacy."
  ],
  [
    "разыграть заново",
    "play again"
  ],
  [
    "начать сценку",
    "start scene"
  ],
  [
    "готовлю подсказки…",
    "preparing hints…"
  ],
  [
    "обновить по диалогу",
    "update from dialogue"
  ],
  [
    "получить подсказки",
    "get hints"
  ],
  [
    "{p0} / {p1} раундов",
    "{p0} / {p1} rounds"
  ],
  [
    "Интервьюер ·",
    "Interviewer ·"
  ],
  [
    "Кандидат ·",
    "Candidate ·"
  ],
  [
    "отправить вопрос из микрофона",
    "send microphone question"
  ],
  [
    "сказать и продолжить",
    "send and continue"
  ],
  [
    "следующий ход",
    "next turn"
  ],
  [
    "Обычно оставьте пустым: вопрос берётся из микрофона. Можно исправить текст вручную.",
    "Usually leave this empty: the microphone provides your question. You can edit the text."
  ],
  [
    "Введите реплику — ИИ продолжит со второй стороны.",
    "Enter your line; AI will reply as the other participant."
  ],
  [
    "Запись · сохранено реплик ИИ:",
    "Recording · saved AI lines:"
  ],
  [
    "Открыть WAV",
    "Open WAV"
  ],
  [
    "озвучки ИИ",
    "of AI speech"
  ],
  [
    "диалога",
    "of the dialogue"
  ],
  [
    "· монтаж реплик с короткими паузами, оригиналы ниже",
    "· edited sequence with short pauses; originals below"
  ],
  [
    "Не озвучены",
    "Not voiced:"
  ],
  [
    "реплик: полной аудиозаписи ИИ пока нет. Текст сохранён.",
    "lines. The AI audio is incomplete; the text is saved."
  ],
  [
    "Ваш голос и реальная временная шкала — в исходных WAV микрофона в результатах встречи.",
    "Your voice and the original timeline are in the microphone WAVs under meeting results."
  ],
  [
    "Интервьюер",
    "Interviewer"
  ],
  [
    "Кандидат",
    "Candidate"
  ],
  [
    "с",
    "s"
  ],
  [
    "Предыдущая попытка",
    "Previous attempt"
  ],
  [
    "· диалог и разбор",
    "· dialogue and review"
  ],
  [
    "Сценка ИИ ↔ ИИ",
    "AI ↔ AI scene"
  ],
  [
    "Задайте роли и материалы — режиссёр подготовит независимых участников.",
    "Set roles and materials to prepare independent participants."
  ],
  [
    "Роли готовы. Выберите темп и запустите первый ход.",
    "Roles are ready. Choose a pace and start the first turn."
  ],
  [
    "Ваш ход: скажите вопрос, дождитесь распознавания и отправьте его.",
    "Your turn: ask a question, wait for recognition, then send it."
  ],
  [
    "Ваш ход: введите реплику за выбранную роль.",
    "Your turn: enter a line for your selected role."
  ],
  [
    "Сценка идёт. Наблюдайте или займите любую роль.",
    "The scene is running. Observe or take either role."
  ],
  [
    "Все раунды сыграны. Остановите сценку и получите независимый разбор.",
    "All rounds are complete. Finish the scene for an independent review."
  ],
  [
    "Сценка завершена. Разбор обоих участников готов.",
    "Scene complete. Feedback for both participants is ready."
  ],
  [
    "разбор готов",
    "review ready"
  ],
  [
    "ИИ-интервьюер ↔ ИИ-кандидат",
    "AI interviewer ↔ AI candidate"
  ],
  [
    "{p0}. Проверенная рубрика v{p1}; резюме и рабочие материалы остаются отдельным источником фактов.",
    "{p0}. Reviewed rubric v{p1}; the CV and project materials remain separate sources of facts."
  ],
  [
    "Свободная роль: система построит вопросы только по указанной роли и вашим материалам.",
    "Custom role: questions use only the role and materials you provide."
  ],
  [
    "Укажите целевую роль или профессию.",
    "Enter a target role or profession."
  ],
  [
    "Завершить тренировку, остановить запись и сформировать отчёт?",
    "Finish practice, stop recording and create the report?"
  ],
  [
    "Сбросить ответы и оценки этой попытки? Подготовленные вопросы и история завершённых попыток останутся.",
    "Reset answers and scores for this attempt? Prepared questions and completed attempts will remain."
  ],
  [
    "Удалить всю накопленную карту компетенций для этой роли? Текущая попытка и подготовленные вопросы останутся.",
    "Delete the saved skills map for this role? The current attempt and prepared questions will remain."
  ],
  [
    "Укажите целевую роль сценки.",
    "Enter the target role for the scene."
  ],
  [
    "Остановить сценку и попросить независимого тренера разобрать обе стороны?",
    "Stop the scene and ask an independent coach to review both participants?"
  ],
  [
    "Начать новую попытку? Предыдущие реплики, разбор и аудио сохранятся в истории; роли останутся.",
    "Start another attempt? Previous lines, feedback and audio will remain in history; roles will be retained."
  ],
  [
    "Нажмите ▶ в проигрывателе.",
    "Press ▶ in the player."
  ],
  [
    "Запись остановлена. Нажмите «Записать попытку», когда будете готовы.",
    "Recording stopped. Select Record attempt when you are ready."
  ],
  [
    "Скрыть параметры",
    "Hide settings"
  ],
  [
    "Тема и параметры",
    "Topic and settings"
  ],
  [
    "Записать повтор",
    "Record another attempt"
  ],
  [
    "Записать попытку",
    "Record attempt"
  ],
  [
    "Разбор сохранён",
    "Review saved"
  ],
  [
    "Разобрать эту попытку отдельно",
    "Review this attempt separately"
  ],
  [
    "Получить разбор",
    "Get feedback"
  ],
  [
    "Сравнение сохранено",
    "Comparison saved"
  ],
  [
    "Сравнить по выбранной правке",
    "Compare the selected change"
  ],
  [
    "{p0} · в модель уходит текст, не аудио.",
    "{p0} · the model receives text, not audio."
  ],
  [
    "ИИ не подключён",
    "AI is not connected"
  ],
  [
    "Запрос только по кнопке; API может быть платным.",
    "Requests run only when selected; API charges may apply."
  ],
  [
    "Настройте подключение и разрешение облака в настройках.",
    "Configure the connection and allow cloud processing in settings."
  ],
  [
    "Приготовьтесь…",
    "Get ready…"
  ],
  [
    "Говорите",
    "Speak now"
  ],
  [
    "Запись остановлена — сохраните попытку",
    "Recording stopped — save the attempt"
  ],
  [
    "Текстовый повтор: откройте поле ниже",
    "Text repeat: open the field below"
  ],
  [
    "Готовим запись…",
    "Preparing recording…"
  ],
  [
    "Повтор: та же тема, одна правка",
    "Repeat: same topic, one change"
  ],
  [
    "Попробуйте объяснить без готового текста",
    "Try explaining without a prepared script"
  ],
  [
    "Задача: {p0}",
    "Focus: {p0}"
  ],
  [
    "{p0} — ориентир, не ограничение. Запись завершаете вы.",
    "{p0} is a target, not a limit. You decide when to stop."
  ],
  [
    "Сравниваю две попытки…",
    "Comparing two attempts…"
  ],
  [
    "Разбираю содержание…",
    "Reviewing the content…"
  ],
  [
    "Завершаю запись и сохраняю последние слова…",
    "Finishing recording and saving the last words…"
  ],
  [
    "Готовлю упражнение…",
    "Preparing the exercise…"
  ],
  [
    "После отсчёта появится «Говорите».",
    "Speak now will appear after the countdown."
  ],
  [
    "Подтвердите начало записи в открывшемся окне.",
    "Confirm recording in the open dialog."
  ],
  [
    "Запись идёт. Когда закончите мысль, нажмите «Завершить и сохранить».",
    "Recording. When you finish, select Finish and save."
  ],
  [
    "Параметры изменились — подготовьте упражнение заново.",
    "Settings changed — prepare the exercise again."
  ],
  [
    "Попытка отменена. Исходная запись сохранена; подготовьте упражнение заново.",
    "Attempt cancelled. The original recording is retained; prepare the exercise again."
  ],
  [
    "Сравнение готово. Прослушайте фрагменты или выберите следующую правку.",
    "Comparison ready. Listen to the excerpts or choose your next change."
  ],
  [
    "Разбор готов. Выберите одну правку и подготовьте повтор.",
    "Feedback ready. Choose one change and prepare another attempt."
  ],
  [
    "Попытка сохранена. Получите разбор или выберите правку для повтора.",
    "Attempt saved. Get feedback or choose a change for your next attempt."
  ],
  [
    "Нажмите кнопку записи, когда будете готовы. Затем начнётся отсчёт.",
    "Select Record when you are ready. A countdown will follow."
  ],
  [
    "Укажите проект и подготовьте упражнение. Микрофон пока выключен.",
    "Enter a project and prepare the exercise. The microphone is off."
  ],
  [
    "Сравнение",
    "Compare"
  ],
  [
    "Разбор",
    "Review"
  ],
  [
    "Обработка",
    "Processing"
  ],
  [
    "Ждём последние слова распознавания.",
    "Waiting for the last recognized words."
  ],
  [
    "Результат появится здесь.",
    "The result will appear here."
  ],
  [
    "Представиться",
    "Introduce yourself"
  ],
  [
    "Ответить на возражение",
    "Respond to an objection"
  ],
  [
    "Объяснить проект за две минуты",
    "Explain a project in two minutes"
  ],
  [
    "Объяснить проект",
    "Explain a project"
  ],
  [
    "Кому он нужен, как работает на примере и что делать дальше.",
    "Who needs it, an example of how it works, and what to do next."
  ],
  [
    "{p0} · {p1} · {p2} · {p3} слов{p4}",
    "{p0} · {p1} · {p2} · {p3} words{p4}"
  ],
  [
    "текст",
    "text"
  ],
  [
    "микрофон",
    "microphone"
  ],
  [
    "· отменена",
    "· cancelled"
  ],
  [
    "Открыта",
    "Open"
  ],
  [
    "Открыть",
    "Open"
  ],
  [
    "Попробовать: {p0}",
    "Try: {p0}"
  ],
  [
    "Послушать фрагмент",
    "Play excerpt"
  ],
  [
    "Что изменилось в повторе",
    "What changed in the repeat"
  ],
  [
    "Повтор сохранён",
    "Repeat saved"
  ],
  [
    "Попытка отменена",
    "Attempt cancelled"
  ],
  [
    "Попытка сохранена",
    "Attempt saved"
  ],
  [
    "Попытка отменена ·",
    "Attempt cancelled ·"
  ],
  [
    "{p0} слов ·",
    "{p0} words ·"
  ],
  [
    "надёжной длительности речи нет",
    "reliable speech duration is unavailable"
  ],
  [
    "{p0} с между началом и концом распознанной речи · примерно {p1} слов/мин",
    "{p0} s between the first and last recognized words · about {p1} words/min"
  ],
  [
    "· слов и оборотов для прослушивания: {p0}",
    "· words and phrases to review: {p0}"
  ],
  [
    "Полнота записи и распознавания автоматически не подтверждена; аудиозапись доступна у фрагментов.",
    "Recording and recognition completeness is not automatically verified; audio is available with excerpts."
  ],
  [
    "Это текстовая попытка: звучание и длительность не оценивались.",
    "This is a text attempt: voice and duration were not assessed."
  ],
  [
    "Что понял слушатель",
    "What the listener understood"
  ],
  [
    "Остальные наблюдения",
    "Other observations"
  ],
  [
    "Что получилось",
    "What worked"
  ],
  [
    "Что поправить",
    "What to improve"
  ],
  [
    "Одна задача для повтора",
    "One focus for the repeat"
  ],
  [
    "Возможный вопрос слушателя",
    "A question the listener might ask"
  ],
  [
    "Правка сработала",
    "The change worked"
  ],
  [
    "Есть продвижение",
    "Some progress"
  ],
  [
    "Правка пока не видна",
    "The change is not evident yet"
  ],
  [
    "Изменение не удалось проверить",
    "The change could not be verified"
  ],
  [
    "Проверяли: {p0}. {p1}",
    "Checking: {p0}. {p1}"
  ],
  [
    "Первая попытка",
    "First attempt"
  ],
  [
    "Повтор",
    "Repeat"
  ],
  [
    "Сравнение по распознанному тексту, не оценка голоса или уверенности. Обе записи сохранены.",
    "This compares recognized text, not voice or confidence. Both recordings are retained."
  ],
  [
    "Предыдущая попытка сохранена. Сравните, удалось ли: {p0}.",
    "The previous attempt is retained. Check whether you managed to: {p0}."
  ],
  [
    "Послушать · {p0} с",
    "Play · {p0} s"
  ],
  [
    "Старт отменён. Готовую попытку это не меняет.",
    "Start cancelled. The saved attempt is unchanged."
  ],
  [
    "Нет временных отметок слов",
    "Word timestamps are unavailable"
  ],
  [
    "Слушаем и распознаём звук…",
    "Listening and recognizing speech…"
  ],
  [
    "Локальная расшифровка готовится…",
    "Preparing the local transcript…"
  ],
  [
    "раунд",
    "round"
  ],
  [
    "Первые мысли",
    "Initial thoughts"
  ],
  [
    "С подсказкой",
    "With a hint"
  ],
  [
    "Повторить реплику",
    "Replay line"
  ],
  [
    "↻ повторить",
    "↻ replay"
  ],
  [
    "Сначала — голос",
    "Listen first"
  ],
  [
    "Расшифровка появится по мере разговора.",
    "The transcript will appear as the conversation unfolds."
  ],
  [
    "Вопрос звучит",
    "Question playing"
  ],
  [
    "Кандидат отвечает",
    "Candidate speaking"
  ],
  [
    "Диалог прослушан",
    "Dialogue played"
  ],
  [
    "Пауза",
    "Paused"
  ],
  [
    "Готовы слушать",
    "Ready to listen"
  ],
  [
    "Подсказка кандидату",
    "Hint for the candidate"
  ],
  [
    "Помощь интервьюеру",
    "Help for the interviewer"
  ],
  [
    "Учебная постановка. Кандидат может использовать опору; это не самостоятельный ответ.",
    "Training scene. The candidate may use the hint; this is not an independent answer."
  ],
  [
    "Только по услышанному. Участники не получают подсказку.",
    "Based only on what was heard. Participants do not receive this hint."
  ],
  [
    "01 · Первые мысли",
    "01 · Initial thoughts"
  ],
  [
    "03 · Развивает ответ с подсказкой",
    "03 · Building on the hint"
  ],
  [
    "02 · Читает подсказку",
    "02 · Reading the hint"
  ],
  [
    "Опора готова",
    "Hint ready"
  ],
  [
    "Слушает вопрос",
    "Listening to the question"
  ],
  [
    "Готовлю по услышанному…",
    "Preparing from what was heard…"
  ],
  [
    "Обновить подсказки",
    "Refresh hints"
  ],
  [
    "Получить подсказки",
    "Get hints"
  ],
  [
    "Прочитал · ответить с подсказкой",
    "Ready · answer with the hint"
  ],
  [
    "Продолжить без подсказки",
    "Continue without a hint"
  ],
  [
    "Прочитал · продолжить ответ",
    "Ready · continue the answer"
  ],
  [
    "Сначала прослушайте вопрос.",
    "Listen to the question first."
  ],
  [
    "Затем появятся ориентиры для ответа.",
    "Then guidance for the answer will appear."
  ],
  [
    "Разбираю услышанный вопрос…",
    "Reviewing the question you heard…"
  ],
  [
    "Можно запросить подсказку по услышанному.",
    "You can request a hint based on what was heard."
  ],
  [
    "ИИ",
    "AI"
  ],
  [
    "· исходная подсказка",
    "· original hint"
  ],
  [
    "· за",
    "· in"
  ],
  [
    "Опора для ответа ·",
    "Answer guidance ·"
  ],
  [
    "· дополняю",
    "· updating"
  ],
  [
    "Суть ответа",
    "Key idea"
  ],
  [
    "Сейчас проверяем",
    "Current focus"
  ],
  [
    "Не забыть",
    "Remember"
  ],
  [
    "На что обратить внимание",
    "What to watch for"
  ],
  [
    "Проверка решения",
    "Check the solution"
  ],
  [
    "Можно уточнить",
    "Possible follow-up"
  ],
  [
    "■ Остановить",
    "■ Stop"
  ],
  [
    "▶ Прослушать диалог",
    "▶ Play dialogue"
  ],
  [
    "↻ Прослушать заново",
    "↻ Play again"
  ],
  [
    "Пауза для подсказки",
    "Paused for a hint"
  ],
  [
    "{p0} · {p1} · готовлю",
    "{p0} · {p1} · preparing"
  ],
  [
    "Неполный PCM-отсчёт",
    "Incomplete PCM sample"
  ],
  [
    "Подключаю голос…",
    "Connecting voice…"
  ],
  [
    "▶ Включить звук",
    "▶ Enable audio"
  ],
  [
    "Говорит {p0} · {p1} · старт за {p2} с",
    "Speaking: {p0} · {p1} · started in {p2} s"
  ],
  [
    "кандидат",
    "candidate"
  ],
  [
    "интервьюер",
    "interviewer"
  ],
  [
    "сохранённый WAV",
    "saved WAV"
  ],
  [
    "Неподдерживаемый поток голоса",
    "Unsupported voice stream"
  ],
  [
    "Поток прерван; полученный звук сохранён на сервере",
    "Stream interrupted; received audio is saved on the server"
  ],
  [
    "Озвучка прервана:",
    "Speech playback interrupted:"
  ],
  [
    "говорит",
    "speaking"
  ],
  [
    "пауза в реплике",
    "pause in speech"
  ],
  [
    "сигнал микрофона",
    "microphone signal"
  ],
  [
    "думает…",
    "thinking…"
  ],
  [
    "слушает",
    "listening"
  ],
  [
    "готов",
    "ready"
  ],
  [
    "вы · микрофон",
    "you · microphone"
  ],
  [
    "без оценки настроения",
    "no mood assessment"
  ],
  [
    "{value}",
    "{value}"
  ],
  [
    "роль",
    "role"
  ],
  [
    "Навык",
    "Skill"
  ],
  [
    "спокойный",
    "calm"
  ],
  [
    "доброжелательный",
    "friendly"
  ],
  [
    "вдумчивый",
    "thoughtful"
  ],
  [
    "напряжённый",
    "tense"
  ],
  [
    "мой голос / маршрут вопросов",
    "my voice / question voice settings"
  ],
  [
    "ТРЕНИРОВКА СОБЕСЕДОВАНИЯ",
    "INTERVIEW PRACTICE"
  ],
  [
    "Сценарий тренировки",
    "Practice mode"
  ],
  [
    "Я отвечаю",
    "I answer"
  ],
  [
    "ИИ задаёт вопросы",
    "AI asks questions"
  ],
  [
    "Я спрашиваю",
    "I interview"
  ],
  [
    "ИИ играет кандидата",
    "AI plays the candidate"
  ],
  [
    "Оба ИИ",
    "Both AI"
  ],
  [
    "наблюдать за сценкой",
    "observe a scene"
  ],
  [
    "Речь",
    "Speaking"
  ],
  [
    "выступить и повторить",
    "speak and try again"
  ],
  [
    "ПРАКТИКА РЕЧИ",
    "SPEAKING PRACTICE"
  ],
  [
    "Этапы упражнения",
    "Exercise stages"
  ],
  [
    "Запись",
    "Record"
  ],
  [
    "О каком проекте расскажете?",
    "Which project will you explain?"
  ],
  [
    "Название и назначение проекта",
    "Project name and purpose"
  ],
  [
    "Кто слушает",
    "Audience"
  ],
  [
    "Цель и другие упражнения",
    "Goal and other exercises"
  ],
  [
    "Упражнение",
    "Exercise"
  ],
  [
    "Ориентир, секунд",
    "Target, seconds"
  ],
  [
    "Что слушатель должен понять или сделать",
    "What the listener should understand or do"
  ],
  [
    "Одна задача для первой попытки",
    "One focus for the first attempt"
  ],
  [
    "Например, начать с результата",
    "For example, start with the outcome"
  ],
  [
    "Подготовить упражнение",
    "Prepare exercise"
  ],
  [
    "Сначала укажите тему",
    "Enter a topic first"
  ],
  [
    "Время выступления",
    "Speaking time"
  ],
  [
    "Время относительно ориентира",
    "Time against target"
  ],
  [
    "Завершить и сохранить",
    "Finish and save"
  ],
  [
    "Отменить попытку",
    "Cancel attempt"
  ],
  [
    "Отменить старт и остановить запись",
    "Cancel start and stop recording"
  ],
  [
    "Попробовать на тексте без микрофона",
    "Try with text, without a microphone"
  ],
  [
    "Текст выступления",
    "Speech text"
  ],
  [
    "Сохранить текстовую попытку",
    "Save text attempt"
  ],
  [
    "Одна правка для следующей попытки",
    "One change for the next attempt"
  ],
  [
    "Что попробуете сделать иначе?",
    "What will you try differently?"
  ],
  [
    "Подготовить повтор",
    "Prepare repeat"
  ],
  [
    "Транскрипт и прослушивание",
    "Transcript and playback"
  ],
  [
    "Наблюдения и ограничения",
    "Observations and limitations"
  ],
  [
    "Предыдущие попытки",
    "Previous attempts"
  ],
  [
    "Участники тренировочного разговора",
    "Practice participants"
  ],
  [
    "Вид и игровой характер персонажей",
    "Appearance and character style"
  ],
  [
    "Показывать звуковые аватары",
    "Show audio avatars"
  ],
  [
    "Интервьюер ИИ",
    "AI interviewer"
  ],
  [
    "напряжённый, без хамства",
    "tense, not rude"
  ],
  [
    "Кандидат ИИ",
    "AI candidate"
  ],
  [
    "волнуется",
    "nervous"
  ],
  [
    "Цвет — заданный стиль ИИ-персонажа. Настроение человека не определяется. В сценке стиль влияет на следующие реплики, но не на знания и факты профиля. Движение отключается общей настройкой интерфейса.",
    "Colour shows the AI character’s assigned style. Human mood is not inferred. Style affects subsequent lines, not the profile’s knowledge or facts. Use the shared interface setting to disable motion."
  ],
  [
    "Роль и материалы тренировки",
    "Practice role and materials"
  ],
  [
    "Профиль компетенций",
    "Skills profile"
  ],
  [
    "свободная роль — без готового профиля",
    "custom role — no preset profile"
  ],
  [
    "Целевая роль",
    "Target role"
  ],
  [
    "Product manager, архитектор, бухгалтер, разработчик…",
    "Product manager, architect, accountant, developer…"
  ],
  [
    "Уровень",
    "Level"
  ],
  [
    "смешанный",
    "mixed"
  ],
  [
    "Вопросов",
    "Questions"
  ],
  [
    "Резюме, вакансия, ссылки и любой контекст",
    "CV, job description, links and context"
  ],
  [
    "Вставьте текст резюме, описание вакансии, публичную HTTPS-ссылку или любые заметки. Рабочая папка из настроек тоже учитывается.",
    "Paste a CV, job description, public HTTPS link or notes. The project folder in settings is also used."
  ],
  [
    "Адаптивный маршрут",
    "Adaptive route"
  ],
  [
    "Слабые и давно не повторявшиеся темы идут раньше, а сложность растёт только после устойчивых ответов.",
    "Weaker and overdue topics come first. Difficulty increases only after consistent answers."
  ],
  [
    "подготовить вопросы",
    "prepare questions"
  ],
  [
    "сбросить попытку",
    "reset attempt"
  ],
  [
    "КАРТА НАВЫКОВ",
    "SKILLS MAP"
  ],
  [
    "Карта компетенций",
    "Skills map"
  ],
  [
    "сбросить историю",
    "reset history"
  ],
  [
    "повторить вопрос голосом",
    "replay the spoken question"
  ],
  [
    "Текст ответа (необязательно — только если речь не распозналась)",
    "Answer text (optional — only if speech was not recognized)"
  ],
  [
    "Обычно оставьте пустым: ответ берётся из микрофона.",
    "Usually leave this empty: your answer comes from the microphone."
  ],
  [
    "оценить и дальше",
    "evaluate and continue"
  ],
  [
    "завершить и сделать отчёт",
    "finish and create report"
  ],
  [
    "Роли, материалы и постановка",
    "Roles, materials and scene"
  ],
  [
    "Интервьюер не видит скрытый профиль кандидата. Кандидат не видит цели проверки. Полную картину получает только тренер после остановки.",
    "The interviewer cannot see the candidate’s hidden profile. The candidate cannot see the assessment goals. Only the coach gets the full picture after the scene stops."
  ],
  [
    "Архитектор, аналитик, руководитель проекта…",
    "Architect, analyst, project manager…"
  ],
  [
    "Раундов",
    "Rounds"
  ],
  [
    "Стиль интервьюера",
    "Interviewer style"
  ],
  [
    "деловой",
    "professional"
  ],
  [
    "поддерживающий",
    "supportive"
  ],
  [
    "через кейсы",
    "case-based"
  ],
  [
    "жёсткий, без хамства",
    "challenging, not rude"
  ],
  [
    "Голос интервьюера",
    "Interviewer voice"
  ],
  [
    "Голос кандидата",
    "Candidate voice"
  ],
  [
    "Подсказки для",
    "Hints for"
  ],
  [
    "кандидата · ответ с помощью",
    "candidate · assisted answer"
  ],
  [
    "интервьюера · независимые участники",
    "interviewer · independent participants"
  ],
  [
    "Резюме, вакансия, ссылки и контекст",
    "CV, vacancy, links and context"
  ],
  [
    "Можно использовать те же материалы, что и в личной тренировке.",
    "You can use the same materials as in personal practice."
  ],
  [
    "подготовить роли",
    "prepare roles"
  ],
  [
    "сбросить ходы",
    "reset turns"
  ],
  [
    "Темп",
    "Pace"
  ],
  [
    "по шагам",
    "step by step"
  ],
  [
    "автоматически",
    "automatic"
  ],
  [
    "Занять роль",
    "Take a role"
  ],
  [
    "наблюдатель",
    "observer"
  ],
  [
    "Живой разговор",
    "Live conversation"
  ],
  [
    "Расшифровка",
    "Transcript"
  ],
  [
    "Расшифровка диалога",
    "Dialogue transcript"
  ],
  [
    "Исходный текст реплик",
    "Original generated lines"
  ],
  [
    "Подсказки",
    "Hints"
  ],
  [
    "Только по услышанному.",
    "Based only on what was heard."
  ],
  [
    "Появятся после первого вопроса.",
    "Available after the first question."
  ],
  [
    "Продолжить ответ",
    "Continue answer"
  ],
  [
    "Ваша реплика за выбранную роль",
    "Your line for the selected role"
  ],
  [
    "повторить последнюю реплику голосом",
    "replay the last spoken line"
  ],
  [
    "▶ повторить",
    "▶ replay"
  ],
  [
    "остановить и разобрать",
    "stop and review"
  ],
  [
    "Gemini 3.8 · Kore · архивный", "Gemini 3.8 · Kore · archived"
  ],
  [
    "Gemini 3.8 · Charon · архивный", "Gemini 3.8 · Charon · archived"
  ],
  [
    "Gemini 3.8 · Kore · целая реплика", "Gemini 3.8 · Kore · full utterance"
  ],
  [
    "Gemini 3.8 · Charon · целая реплика", "Gemini 3.8 · Charon · full utterance"
  ],
  [
    "Gemini 3.8 · Kore · потоковые фразы", "Gemini 3.8 · Kore · streaming phrases"
  ],
  [
    "Gemini 3.8 · Charon · потоковые фразы", "Gemini 3.8 · Charon · streaming phrases"
  ],
  ["Черновик настроек сохранён в этой вкладке.","Setup draft saved in this tab."],
  ["Сбросить черновик","Discard draft"],
  ["Удалить несохранённый черновик?","Discard the unsaved draft?"]
];

  const i18n=window.BlateroI18n;
  if(!i18n)return;
  const entries=Object.fromEntries(pairs.map((pair,index)=>['studio.'+index,pair]));
  i18n.register(entries);
  const normal=value=>String(value??'').replace(/\s+/g,' ').trim();
  const aliases=new Map();
  for(const [key,pair]of Object.entries(entries))for(const phrase of pair)if(!aliases.has(normal(phrase)))aliases.set(normal(phrase),key);
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels=new Map(),attributes=new Map();
  const params=value=>typeof value==='function'?value():value;
  const resolve=(source,values)=>typeof source==='function'?source():{source,values:params(values)};
  const parse=value=>{try{return JSON.parse(value||'{}');}catch{return {};}};
  function ui(source,values={}){
    source=String(source??'');const key=aliases.get(normal(source));
    const rendered=key?i18n.t(key,values):source.replace(/\{([a-zA-Z_]\w*)\}/g,(match,name)=>Object.hasOwn(values,name)?String(values[name]):match);
    return key?source.match(/^\s*/)[0]+rendered+source.match(/\s*$/)[0]:rendered;
  }
  function bind(source,values={}){
    const key=aliases.get(normal(source));
    return key?'data-studio-key="'+key+'" data-studio-ru="'+escape(source)+'" data-studio-params="'+escape(JSON.stringify(values))+'" lang="'+i18n.language+'"':'';
  }
  function text(source,values={}){return '<span '+bind(source,values)+'>'+escape(ui(source,values))+'</span>';}
  function attrs(name,source,values={}){
    const key=aliases.get(normal(source));
    return name+'="'+escape(ui(source,values))+'"'+(key?' data-studio-'+name+'="'+key+'" data-studio-'+name+'-params="'+escape(JSON.stringify(values))+'"':'');
  }
  function forget(element){
    if(!element)return;labels.delete(element);
    for(const name of ['data-studio-key','data-studio-ru','data-studio-params','data-studio-source','data-studio-source-params'])element.removeAttribute(name);
  }
  function value(element,raw){if(!element)return;forget(element);const shown=String(raw??'');if(element.textContent!==shown)element.textContent=shown;}
  function label(element,source,values={}){
    if(!element)return;
    const resolved=resolve(source,values),shown=ui(resolved.source,resolved.values);
    let entry=labels.get(element);
    if(!entry||entry.node.parentNode!==element){
      forget(element);const node=document.createTextNode(shown);element.replaceChildren(node);entry={node};labels.set(element,entry);
    }else if(entry.node.textContent!==shown)entry.node.textContent=shown;
    Object.assign(entry,{source,values});element.lang=i18n.language;
    if(labels.size>256)for(const node of labels.keys())if(!node.isConnected)labels.delete(node);
  }
  function attr(element,name,source,values={}){
    if(!element)return;
    if(!attributes.has(element))attributes.set(element,new Map());
    attributes.get(element).set(name,{source,values});element.removeAttribute('data-studio-'+name);
    const entry=resolve(source,values);element.setAttribute(name,ui(entry.source,entry.values));
  }
  function apply(scope=document){
    const find=selector=>[...(scope.matches?.(selector)?[scope]:[]),...scope.querySelectorAll(selector)];
    for(const node of find('[data-studio-source]')){
      const key=aliases.get(normal(node.dataset.studioSource));
      if(!key)continue;
      node.dataset.studioKey=key;node.dataset.studioRu=node.dataset.studioSource;node.dataset.studioParams=node.dataset.studioSourceParams||'{}';
      node.removeAttribute('data-studio-source');node.removeAttribute('data-studio-source-params');
    }
    for(const name of ['title','aria-label','placeholder','data-tooltip','data-label'])for(const node of find('[data-studio-source-'+name+']')){
      const key=aliases.get(normal(node.getAttribute('data-studio-source-'+name)));
      if(!key)continue;
      node.setAttribute('data-studio-'+name,key);node.setAttribute('data-studio-'+name+'-params',node.getAttribute('data-studio-source-'+name+'-params')||'{}');
      node.removeAttribute('data-studio-source-'+name);node.removeAttribute('data-studio-source-'+name+'-params');
    }
    for(const element of find('[data-studio-key]')){
      const key=element.dataset.studioKey;if(!entries[key])continue;
      const shown=ui(element.dataset.studioRu??entries[key][0],parse(element.dataset.studioParams));
      if(element.textContent!==shown)element.textContent=shown;element.lang=i18n.language;
    }
    for(const name of ['title','aria-label','placeholder','data-tooltip','data-label'])for(const element of find('[data-studio-'+name+']')){
      const key=element.getAttribute('data-studio-'+name);if(entries[key])element.setAttribute(name,i18n.t(key,parse(element.getAttribute('data-studio-'+name+'-params'))));
    }
  }
  function refresh(){
    apply();
    for(const [element,entry]of labels){
      if(!element.isConnected||entry.node.parentNode!==element){labels.delete(element);continue;}
      const resolved=resolve(entry.source,entry.values),shown=ui(resolved.source,resolved.values);
      if(entry.node.textContent!==shown)entry.node.textContent=shown;element.lang=i18n.language;
    }
    for(const [element,values]of attributes){if(!element.isConnected){attributes.delete(element);continue;}for(const [name,entry]of values)attr(element,name,entry.source,entry.values);}
  }
  function register(namespace,pairs){
    if(!/^[a-z][a-z0-9]*$/.test(namespace))throw Error('Invalid feature namespace');
    const extra=Object.fromEntries(pairs.map((pair,index)=>[namespace+'.'+index,pair]));
    i18n.register(extra);
    for(const [key,pair]of Object.entries(extra)){
      entries[key]=pair;
      for(const phrase of pair)if(!aliases.has(normal(phrase)))aliases.set(normal(phrase),key);
    }
    refresh();
  }
  window.BlateroStudioI18n={ui,text,bind,attrs,label,attr,value,forget,refresh,register};
  const pending=window.__blateroStudioPending;
  if(pending){
    for(const [element,entry]of pending.labels)if(element.isConnected)label(element,entry.source,entry.values);
    for(const [element,values]of pending.attrs)if(element.isConnected)for(const [name,entry]of values)attr(element,name,entry.source,entry.values);
    delete window.__blateroStudioPending;
  }
  document.addEventListener('blatero:language',refresh);refresh();
})();
