'use strict';
// Owned laboratory labels; source text and names remain data.
(() => {
  window.BlateroStudioI18n?.register('readiness', [
    ['Natasha (русский) + правила','Natasha (Russian) + rules'],
    ['Во время записи проверка оборудования недоступна. Сначала завершите запись.','Hardware checks are unavailable during recording. Stop recording first.'],
    ['Проверим звук перед встречей','Check audio before the meeting'],
    ['Наденьте наушники и убедитесь, что микрофон не выключен.','Check that your microphone is not muted. Headphones help reduce echo.'],
    ['Нажмите «Я готов, начать». После отсчёта скажите обычным голосом:','Click “Ready, start”. After the countdown, say the displayed phrase in your normal voice:'],
    ['На речь будет 8 секунд. Затем замолчите: программа воспроизведёт тестовый сигнал и проверит остальные компоненты.','You have 8 seconds to speak. Then stay quiet while the app plays a test signal and checks the other components.'],
    ['Голос этой проверки не сохраняется и не отправляется в облако. Для проверки распознавания используется отдельная встроенная фраза; SpeechKit отправляет только её в Яндекс.','Your microphone speech is not saved or sent to the cloud. Recognition uses a separate built-in phrase; SpeechKit sends only that fixture to Yandex.'],
    ['Проверка ещё не началась.','The check has not started.'], ['Уровень микрофона','Microphone level'],
    ['Я готов, начать','Ready, start'],
    ['Проверка ещё не началась. Нажмите кнопку, когда будете готовы говорить.','The check has not started. Click when you are ready to speak.'],
    ['Нет подключения к серверу. Проверка не началась.','No server connection. The check did not start.'],
    ['Приготовьтесь говорить. Начало через {seconds}…','Get ready to speak. Starting in {seconds}…'],
    ['Начало через {seconds}…','Starting in {seconds}…'], ['Проверяем…','Checking…'], ['Повторить проверку','Repeat check'],
    ['Говорите сейчас: «Проверяю микрофон перед встречей». 8 секунд.','Speak now for 8 seconds: say the displayed phrase.'],
    ['Говорите сейчас: «Проверяю микрофон перед встречей». Проверка длится 8 секунд.','Speak now for 8 seconds: say the displayed phrase.'],
    ['не говорите — проверяю выход, loopback и акустическую утечку','Stay quiet — checking output, loopback and acoustic leakage'],
    ['проверяю одновременный запуск каналов настоящего контура записи','Checking simultaneous capture using the recording audio route'],
    ['проверяю AEC и реальное распознавание встроенной тестовой фразы','Checking AEC and real recognition of the built-in test phrase'],
    ['не готово: ошибок {failures}, предупреждений {warnings}','Not ready · errors: {failures} · warnings: {warnings}'],
    ['готово с предупреждениями: {warnings}','Ready with {warnings} warnings'], ['готово к встрече','Ready for the meeting'],
    ['Проверка голоса не завершена. Остальные результаты — ниже. Повторите проверку, произнеся фразу после отсчёта.','Voice check incomplete. Review the other results below, then repeat and speak after the countdown.'],
    ['Проверка голоса','Voice check'], ['Микрофон','Microphone'], ['Системный звук встречи','Meeting audio'],
    ['Совместный захват звука','Simultaneous audio capture'], ['Подавление акустического эха','Acoustic echo cancellation'],
    ['Распознавание речи','Speech recognition'], ['Подсказки и отчёт','Hints and report'], ['Запись результатов','Saving results'],
    ['сигнал найден: {device}','Signal detected: {device}'],
    ['Микрофон открылся ({device}), но речь не подтверждена. Повторите проверку после отсчёта; проверьте mute и уровень входа.','Microphone opened ({device}), but speech was not confirmed. Repeat after the countdown; check mute and input level.'],
    ['папка встречи доступна для записи','Meeting folder is writable'],
    ['оба канала открыты как при записи; микрофон передаёт PCM','Both channels opened using the recording route; microphone supplies PCM'],
    ['Тестовая фраза распознана: «{text}»','Test phrase recognized: “{text}”'],
    ['Доступ настроен: {provider}','Access configured: {provider}'], ['Доступ не подтверждён: {provider}','Access not confirmed: {provider}'],
    ['WebRTC AEC3 {version} отвечает; SHA-256 проверен','WebRTC AEC3 {version} responds; SHA-256 verified'],
    ['выбран встроенный корреляционный фильтр','Built-in correlation filter selected'], ['Проверка ещё не запускалась.','No check has run yet.']
  ]);
  const pairs = /* TOOL_PHRASES */ [
  [
    "операция выполняется…",
    "operation in progress…"
  ],
  [
    "готово",
    "done"
  ],
  [
    "скачать",
    "download"
  ],
  [
    "удалить пакет",
    "delete package"
  ],
  [
    "Удалить пакет {p4}",
    "Delete package {p4}"
  ],
  [
    "Зашифрованных пакетов пока нет.",
    "No encrypted packages yet."
  ],
  [
    "Безвозвратно удалить зашифрованный пакет {p0}? Скачанные ранее копии останутся вне Blatero.",
    "Permanently delete encrypted package {p0}? Previously downloaded copies remain outside Blatero."
  ],
  [
    "файлов ·",
    "files ·"
  ],
  [
    "вне каталога:",
    "outside the catalog:"
  ],
  [
    "встреч ·",
    "meetings ·"
  ],
  [
    "{p0}: {p1} дн. · {p2}",
    "{p0}: {p1} days · {p2}"
  ],
  [
    "По сохранённым срокам очередь пуста.",
    "No items are due under the saved retention rules."
  ],
  [
    "Для выбранных категорий файлов нет.",
    "No files in the selected categories."
  ],
  [
    "импортирована",
    "imported"
  ],
  [
    "нет эталона",
    "no reference"
  ],
  [
    "черновик",
    "draft"
  ],
  [
    "подтверждён",
    "confirmed"
  ],
  [
    "повреждён",
    "invalid"
  ],
  [
    "подтверждено · минимум",
    "reviewed · minimum"
  ],
  [
    "ошибки слов · ниже лучше",
    "word errors · lower is better"
  ],
  [
    "ошибки разделения голосов",
    "speaker separation errors"
  ],
  [
    "пересечение голосовых кластеров",
    "voice cluster overlap"
  ],
  [
    "ошибка канала",
    "channel error"
  ],
  [
    "микрофон ↔ звук встречи",
    "microphone ↔ meeting audio"
  ],
  [
    "ложное эхо",
    "false echo suppression"
  ],
  [
    "потерянные содержательные реплики",
    "meaningful utterances removed"
  ],
  [
    "метрики",
    "metrics"
  ],
  [
    "Подтвердите первый эталон после сверки с аудио.",
    "Review the first reference against the audio, then confirm it."
  ],
  [
    "В этой группе записей пока нет.",
    "No recordings in this group yet."
  ],
  [
    "метрики появятся после создания эталона",
    "metrics appear after a reference is created"
  ],
  [
    "создать черновик",
    "create draft"
  ],
  [
    "нужна ручная проверка файла",
    "file needs manual review"
  ],
  [
    "просмотреть",
    "view"
  ],
  [
    "продолжить разметку",
    "continue annotation"
  ],
  [
    "реплик ·",
    "utterances ·"
  ],
  [
    "аудиодор.",
    "audio tracks"
  ],
  [
    "Собираю локальные эталоны и метрики…",
    "Loading local references and metrics…"
  ],
  [
    "{p0} записей: {p1} черновиков, {p2} подтверждено.",
    "{p0} recordings: {p1} drafts, {p2} reviewed."
  ],
  [
    "Эталонный набор не загружен.",
    "Could not load the reference set."
  ],
  [
    "{p0} с",
    "{p0} s"
  ],
  [
    "{p0} мс",
    "{p0} ms"
  ],
  [
    "проверенных встреч",
    "reviewed meetings"
  ],
  [
    "числовые срезы",
    "numeric snapshots"
  ],
  [
    "{p0} встреч",
    "{p0} meetings"
  ],
  [
    "валидных задержек",
    "valid latency samples"
  ],
  [
    "события",
    "events"
  ],
  [
    "замеров ·",
    "samples ·"
  ],
  [
    "встреч",
    "meetings"
  ],
  [
    "нет числовых срезов",
    "no numeric snapshots"
  ],
  [
    "начнут собираться во время следующей записи",
    "collection starts with the next recording"
  ],
  [
    "можно сделать чувствительнее",
    "sensitivity can be increased"
  ],
  [
    "оставить",
    "keep"
  ],
  [
    "данных недостаточно",
    "insufficient data"
  ],
  [
    "внимание / критично",
    "warning / critical"
  ],
  [
    "Измерения не найдены.",
    "No measurements found."
  ],
  [
    "Профиль рассчитан.",
    "Profile calculated."
  ],
  [
    "Он не изменится без вашего подтверждения.",
    "It will not change without your confirmation."
  ],
  [
    "Пороги не меняются.",
    "Thresholds are unchanged."
  ],
  [
    "Есть доказательное изменение. Проверьте строки и подтвердите применение.",
    "The evidence supports a change. Review the rows and confirm before applying."
  ],
  [
    "Текущий профиль оставлен без изменений.",
    "The current profile is unchanged."
  ],
  [
    "Считаю локальные измерения…",
    "Calculating local measurements…"
  ],
  [
    "Калибровка не загружена.",
    "Could not load calibration."
  ],
  [
    "Сохраняю подтверждённый профиль…",
    "Saving the confirmed profile…"
  ],
  [
    "Профиль сохранён. Он действует со следующей записи.",
    "Profile saved. It takes effect with the next recording."
  ],
  [
    "Создаю независимую копию транскрипта…",
    "Creating a separate transcript copy…"
  ],
  [
    "Черновик не создан: {p0}",
    "Could not create draft: {p0}"
  ],
  [
    "Загружаю реплики эталона…",
    "Loading reference utterances…"
  ],
  [
    "{p0} → {p1} · {p2} реплик",
    "{p0} → {p1} · {p2} utterances"
  ],
  [
    "Закрыть разметку и потерять несохранённую правку?",
    "Close annotation and discard the unsaved edit?"
  ],
  [
    "· аудио не найдено",
    "· audio not found"
  ],
  [
    "Текст реплики {p8}, {p9}",
    "Utterance text {p8}, {p9}"
  ],
  [
    "начало, сек",
    "start, seconds"
  ],
  [
    "конец, сек",
    "end, seconds"
  ],
  [
    "сторона",
    "speaker role"
  ],
  [
    "я / локальный",
    "me / local"
  ],
  [
    "участник встречи",
    "meeting participant"
  ],
  [
    "канал",
    "channel"
  ],
  [
    "микрофон",
    "microphone"
  ],
  [
    "звук встречи",
    "meeting audio"
  ],
  [
    "импорт",
    "import"
  ],
  [
    "ручной",
    "manual"
  ],
  [
    "синтетический",
    "synthetic"
  ],
  [
    "статус",
    "status"
  ],
  [
    "содержательная",
    "meaningful"
  ],
  [
    "подавлена / эхо",
    "suppressed / echo"
  ],
  [
    "имя",
    "name"
  ],
  [
    "ID голоса",
    "voice ID"
  ],
  [
    "разделить",
    "split"
  ],
  [
    "сохранить",
    "save"
  ],
  [
    "Реплики по фильтру не найдены.",
    "No utterances match the filter."
  ],
  [
    "Правка сохранена только в эталонной копии.",
    "Edit saved in the reference copy only."
  ],
  [
    "Не сохранено: {p0}",
    "Not saved: {p0}"
  ],
  [
    "Разделить склеенную реплику",
    "Split a merged utterance"
  ],
  [
    "Укажите границу по звуку и разнесите текст между двумя частями. Первая сохранит исходный ID, вторая получит новый.",
    "Locate the split in the audio and divide the text between the two parts. The first keeps the original ID; the second gets a new one."
  ],
  [
    "граница, сек",
    "split, seconds"
  ],
  [
    "текст до границы",
    "text before the split"
  ],
  [
    "текст после границы",
    "text after the split"
  ],
  [
    "Перенесите сюда вторую реплику",
    "Move the second utterance here"
  ],
  [
    "сторона второй части",
    "speaker role of the second part"
  ],
  [
    "канал второй части",
    "audio channel of the second part"
  ],
  [
    "имя второй части",
    "name in the second part"
  ],
  [
    "ID голоса второй части",
    "voice ID in the second part"
  ],
  [
    "отмена",
    "cancel"
  ],
  [
    "разделить и сохранить",
    "split and save"
  ],
  [
    "Склеенная реплика разделена в эталонной копии.",
    "Merged utterance split in the reference copy."
  ],
  [
    "Не разделено: {p0}",
    "Could not split: {p0}"
  ],
  [
    "Аудио не запущено: {p0}",
    "Could not play audio: {p0}"
  ],
  [
    "Сначала сохраните текущую правку реплики.",
    "Save the current utterance edit first."
  ],
  [
    "Сначала завершите или отмените разделение реплики.",
    "Complete or cancel the utterance split first."
  ],
  [
    "Эталон подтверждён и вошёл в общие метрики.",
    "Reference reviewed and included in aggregate metrics."
  ],
  [
    "Эталон возвращён в черновик и исключён из общих метрик.",
    "Reference reopened as a draft and excluded from aggregate metrics."
  ],
  [
    "было",
    "previously"
  ],
  [
    "п.п.",
    "pp"
  ],
  [
    "очередь",
    "queued"
  ],
  [
    "выполняется",
    "running"
  ],
  [
    "ошибка",
    "error"
  ],
  [
    "отменён",
    "cancelled"
  ],
  [
    "прерван",
    "interrupted"
  ],
  [
    "выключен",
    "off"
  ],
  [
    "корреляционный",
    "correlation"
  ],
  [
    "автовыбор",
    "automatic"
  ],
  [
    "нативный → резерв",
    "native → fallback"
  ],
  [
    "выберите 2–4 готовых варианта",
    "select 2–4 completed runs"
  ],
  [
    "{p0} выбрано{p1}",
    "{p0} selected{p1}"
  ],
  [
    "· можно сравнить",
    "· ready to compare"
  ],
  [
    "· дождитесь готовности",
    "· wait for completion"
  ],
  [
    "Экспериментов ещё нет. Первый прогон создаст независимую точку сравнения.",
    "No experiments yet. The first run creates a separate comparison point."
  ],
  [
    "raw уверенность модели",
    "raw model confidence"
  ],
  [
    "реплик",
    "utterances"
  ],
  [
    "слов",
    "words"
  ],
  [
    "голосов",
    "voices"
  ],
  [
    "транскрипт",
    "transcript"
  ],
  [
    "с кластерами",
    "with clusters"
  ],
  [
    "метрики JSON",
    "metrics JSON"
  ],
  [
    "голоса и имена",
    "voices and names"
  ],
  [
    "Кластеры несбалансированы: крупнейший содержит",
    "Unbalanced clusters: the largest contains"
  ],
  [
    "% размеченной речи",
    "% of annotated speech"
  ],
  [
    ", коротких/сомнительных кластеров:",
    ", short or uncertain clusters:"
  ],
  [
    ". Число голосов не подтверждено — проверьте примеры на слух.",
    ". Voice count is not confirmed — listen to the samples."
  ],
  [
    "Контрольный следующий ход:",
    "Test next step:"
  ],
  [
    "Подсказка не сформирована:",
    "Hint not generated:"
  ],
  [
    "· метрики по черновому эталону",
    "· metrics use a draft reference"
  ],
  [
    "· эталона нет",
    "· no reference"
  ],
  [
    "· эталон не размечает эту дорожку",
    "· reference does not cover this track"
  ],
  [
    "Рекомендуемый вариант ·",
    "Recommended run ·"
  ],
  [
    "Устаревшие параметры распознавания: результат оставлен для истории, но его нельзя применять или сравнивать. Запустите Replay заново.",
    "Recognition settings are outdated. The result is retained for history but cannot be applied or compared. Create a new Replay run."
  ],
  [
    "матрица",
    "matrix"
  ],
  [
    "· язык русский · AEC",
    "· Russian language · AEC"
  ],
  [
    "диаризация",
    "diarization"
  ],
  [
    "авто",
    "auto"
  ],
  [
    "без диаризации",
    "no diarization"
  ],
  [
    "WER — ошибки слов; DER/JER — ошибки разделения голосов. Для всех трёх ниже лучше. Raw уверенность — некалиброванная внутренняя метрика модели: она не является точностью и не сравнивается между движками.",
    "WER measures word errors; DER/JER measure speaker separation errors. Lower is better for all three. Raw confidence is an uncalibrated internal model score, not accuracy, and cannot be compared across engines."
  ],
  [
    "▶ исходный темп и задержки",
    "▶ original timing and latency"
  ],
  [
    "переименовать говорящих",
    "rename speakers"
  ],
  [
    "остановить",
    "stop"
  ],
  [
    "удалить результат",
    "delete result"
  ],
  [
    "Одновременно можно сравнить не более четырёх вариантов.",
    "You can compare up to four runs at a time."
  ],
  [
    "Не удалось загрузить прогоны: {p0}",
    "Could not load runs: {p0}"
  ],
  [
    "Фрагмент не воспроизведён: {p0}",
    "Could not play excerpt: {p0}"
  ],
  [
    "Найдено {p0} заметных расхождений из {p1} опорных реплик. Прослушивание использует исходный WAV, а после AEC — очищенный вариант.",
    "Found {p0} significant differences across {p1} reference utterances. Playback uses the original WAV, or the cleaned version after AEC."
  ],
  [
    "Заметных текстовых расхождений не найдено. Метрики вариантов всё равно остаются в карточках ниже.",
    "No significant text differences found. Run metrics remain in the cards below."
  ],
  [
    "в проверку голосов",
    "review voices"
  ],
  [
    "прослушать этот вариант",
    "listen to this run"
  ],
  [
    "различие",
    "difference"
  ],
  [
    "Тексты совпадают в пределах порога сравнения.",
    "Texts match within the comparison threshold."
  ],
  [
    "Запись не воспроизведена: {p0}",
    "Could not play recording: {p0}"
  ],
  [
    "из",
    "of"
  ],
  [
    "окон: подсказка успевает до следующей реплики.",
    "windows: the hint arrives before the next utterance."
  ],
  [
    "Время LLM взято из локальных замеров.",
    "AI latency comes from local measurements."
  ],
  [
    "Время LLM — оценка: измените его и проверьте сценарий.",
    "AI latency is an estimate: adjust it to test the scenario."
  ],
  [
    "При этих порогах достаточно длинных пауз для автоподсказки не найдено.",
    "No pauses are long enough for automatic hints at these thresholds."
  ],
  [
    "последняя пауза",
    "final pause"
  ],
  [
    "запас {p0}",
    "margin {p0}"
  ],
  [
    "опоздание {p0}",
    "late by {p0}"
  ],
  [
    "Нет окон при выбранных параметрах.",
    "No hint windows at these settings."
  ],
  [
    "{p0} · {p1} · {p2} реплик. Звук и подсветка идут по исходным меткам.",
    "{p0} · {p1} · {p2} utterances. Audio and highlighting follow the original timestamps."
  ],
  [
    "{p0} live-замеров",
    "{p0} live samples"
  ],
  [
    "оценка",
    "estimate"
  ],
  [
    "хвост задержки",
    "latency tail"
  ],
  [
    "нет live-меток",
    "no live timestamps"
  ],
  [
    "подсказка p50",
    "hint p50"
  ],
  [
    "{p0} замеров",
    "{p0} samples"
  ],
  [
    "без тайминга",
    "no timing data"
  ],
  [
    "старые подсказки",
    "past hints"
  ],
  [
    "Собираю исходные метки и локальные замеры…",
    "Loading original timestamps and local measurements…"
  ],
  [
    "Таймлайн готов. Симуляция не обращается к LLM.",
    "Timeline ready. The simulation does not call AI."
  ],
  [
    "Таймлайн не открыт: {p0}",
    "Could not open timeline: {p0}"
  ],
  [
    "Сопоставляю реплики по временной шкале…",
    "Aligning utterances by timestamp…"
  ],
  [
    "Сравнение готово: {p0} расхождений.",
    "Comparison ready: {p0} differences."
  ],
  [
    "Не удалось сравнить: {p0}",
    "Could not compare: {p0}"
  ],
  [
    "Системную дорожку можно распознать и разделить, AEC ей не нужен.",
    "The system track supports transcription and diarization; it does not need AEC."
  ],
  [
    "Парной системной дорожки нет — сравнение AEC недоступно.",
    "There is no paired system track, so AEC comparison is unavailable."
  ],
  [
    "Готово к запуску. Исходные файлы останутся без изменений.",
    "Ready to run. Original files will remain unchanged."
  ],
  [
    "системный звук",
    "system audio"
  ],
  [
    "Загружаю историю…",
    "Loading history…"
  ],
  [
    "Перенести выбранный Replay-вариант в проверку голосов и имён? Исходный WAV и живой транскрипт не изменятся.",
    "Use the selected Replay run for voice and name review? The original WAV and live transcript will remain unchanged."
  ],
  [
    "У встречи уже есть производный разбор голосов. Заменить его результатом этого Replay run? Исходная запись и живой транскрипт сохранятся.",
    "This meeting already has a derived voice analysis. Replace it with this Replay run? The original recording and live transcript will remain unchanged."
  ],
  [
    "Разбор применён · голосов: {p0}. Проверьте имена на слух.",
    "Analysis applied · voices: {p0}. Listen to verify the names."
  ],
  [
    "Разбор не применён: {p0}",
    "Analysis not applied: {p0}"
  ],
  [
    "Не остановлено: {p0}",
    "Could not stop: {p0}"
  ],
  [
    "Удалить только этот Replay run и все его производные файлы? Исходная встреча останется.",
    "Delete this Replay run and its derived files only? The original meeting will remain."
  ],
  [
    "Не удалено: {p0}",
    "Not deleted: {p0}"
  ],
  [
    "Выберите файл для этого источника.",
    "Choose a file for this source."
  ],
  [
    "Файл ещё не выбран.",
    "No file selected yet."
  ],
  [
    "Файл больше 2 МБ.",
    "The file is larger than 2 MB."
  ],
  [
    "{p0} · {p1} КБ",
    "{p0} · {p1} KB"
  ],
  [
    "Проверяю и добавляю новый сегмент…",
    "Checking and adding a new segment…"
  ],
  [
    "Создаю изолированный прогон…",
    "Creating a separate run…"
  ],
  [
    "Запущен {p0}. Можно закрыть окно — обработка продолжится.",
    "Started {p0}. You can close this window; processing will continue."
  ],
  [
    "Не запущено: {p0}",
    "Could not start: {p0}"
  ],
  [
    "Для матрицы отключите платную контрольную LLM-подсказку.",
    "Disable the paid test AI hint before running a matrix."
  ],
  [
    "Готовлю независимые варианты матрицы…",
    "Preparing separate matrix runs…"
  ],
  [
    "Матрица {p0} вариантов запущена последовательно. Сравнение станет доступно после завершения.",
    "Started {p0} matrix runs in sequence. Comparison will be available when they finish."
  ],
  [
    "Матрица не запущена: {p0}",
    "Could not start matrix: {p0}"
  ],
  [
    "мой образец Chatterbox",
    "my Chatterbox sample"
  ],
  [
    "реплики встречи",
    "meeting utterances"
  ],
  [
    "калибровка по архиву",
    "archive calibration"
  ],
  [
    "локальный образец",
    "local sample"
  ],
  [
    "· архив: {p0} принято, {p1} исключено · ложных совпадений {p2}/{p3}",
    "· archive: {p0} included, {p1} excluded · false matches {p2}/{p3}"
  ],
  [
    "Ближайшие: {p0}.",
    "Closest matches: {p0}."
  ],
  [
    "Запись похожа на «{p0}».",
    "The recording is similar to “{p0}”."
  ],
  [
    "«{p0}» — первый вариант, но требуется проверка на слух.",
    "“{p0}” is the first suggestion, but you must verify it by listening."
  ],
  [
    "Запись пока недостаточно похожа на «{p0}».",
    "The recording is not similar enough to “{p0}” yet."
  ],
  [
    "Запись больше похожа на «{p0}», а не на «{p1}».",
    "The recording is more similar to “{p0}” than “{p1}”."
  ],
  [
    "Профиль «{p0}» не подтверждён.",
    "Profile “{p0}” is not confirmed."
  ],
  [
    "Модель Speaker ID не установлена.",
    "The Speaker ID model is not installed."
  ],
  [
    "Открыть установку моделей",
    "Open model installation"
  ],
  [
    "Банк пуст. Добавьте свой образец здесь или участника из экрана проверки диаризации.",
    "The voice bank is empty. Add your sample here, or add a participant from diarization review."
  ],
  [
    "профиль повреждён",
    "invalid profile"
  ],
  [
    "удалить",
    "delete"
  ],
  [
    "· образцов:",
    "· samples:"
  ],
  [
    "проверить",
    "review"
  ],
  [
    "переименовать",
    "rename"
  ],
  [
    "Новое имя голосового профиля",
    "New voice profile name"
  ],
  [
    "Переименовываю профиль…",
    "Renaming profile…"
  ],
  [
    "Профиль переименован в «{p0}».",
    "Profile renamed to “{p0}”."
  ],
  [
    "Не переименовано: {p0}",
    "Could not rename: {p0}"
  ],
  [
    "Говорите обычным голосом {p0} секунд. Проверочная запись будет удалена сразу после сравнения.",
    "Speak normally for {p0} seconds. The test recording is deleted immediately after comparison."
  ],
  [
    "Говорите обычным голосом: осталось около {p0} с. Проверяю профиль «{p1}»…",
    "Speak normally: about {p0} s remaining. Checking profile “{p1}”…"
  ],
  [
    "Проверка не выполнена: {p0}",
    "Check failed: {p0}"
  ],
  [
    "Полностью удалить голосовой профиль «{p0}»? Восстановить отпечаток будет нельзя.",
    "Permanently delete voice profile “{p0}”? The voiceprint cannot be recovered."
  ],
  [
    "Удаляю профиль…",
    "Deleting profile…"
  ],
  [
    "Профиль и его отпечатки полностью удалены.",
    "The profile and its voiceprints have been deleted."
  ],
  [
    "Загружаю…",
    "Loading…"
  ],
  [
    "Модель голосов не установлена · профилей: {p0}.",
    "The voice model is not installed · profiles: {p0}."
  ],
  [
    "Локально сохранено профилей: {p0}.",
    "Profiles saved locally: {p0}."
  ],
  [
    "Банк готов, сохранённых профилей пока нет.",
    "Voice bank ready; no profiles saved yet."
  ],
  [
    "Банк недоступен.",
    "Voice bank unavailable."
  ],
  [
    "Не удалось открыть банк: {p0}",
    "Could not open voice bank: {p0}"
  ],
  [
    "Укажите имя профиля.",
    "Enter a profile name."
  ],
  [
    "Сначала подтвердите создание и хранение локального отпечатка.",
    "Confirm local voiceprint creation and storage first."
  ],
  [
    "Профиль не создан: {p0}",
    "Could not create profile: {p0}"
  ],
  [
    "Сравниваю локальные микрофонные дорожки и отбраковываю эхо…",
    "Comparing local microphone tracks and excluding echo…"
  ],
  [
    "Профиль откалиброван по согласованным архивным встречам. Исходное аудио не копировалось.",
    "Profile calibrated against consistent archived meetings. Original audio was not copied."
  ],
  [
    "Анализирую отдельный образец локально…",
    "Analysing the separate sample locally…"
  ],
  [
    "Профиль создан из отдельного образца. Исходная запись в банк не копировалась.",
    "Profile created from a separate sample. The original recording was not copied to the voice bank."
  ],
  [
    "Проверка отменена. Нажмите кнопку, когда будете готовы.",
    "Check cancelled. Press the button when you are ready."
  ],
  [
    "Проба удалена из памяти вкладки.",
    "Test sample removed from tab memory."
  ],
  [
    "подготовка калибровки…",
    "preparing calibration…"
  ],
  [
    "Сейчас прозвучит тихий тест. Не говорите около четырёх секунд.",
    "A quiet test sound will play. Remain silent for about four seconds."
  ],
  [
    "закрыть",
    "close"
  ],
  [
    "ЛОКАЛЬНАЯ ПРОВЕРКА ЗВУКА",
    "LOCAL AUDIO CHECK"
  ],
  [
    "Калибровка Аудиосторожа",
    "Audio Guard calibration"
  ],
  [
    "Blatero сравнивает текущие пороги с обезличенными числовыми срезами реальных записей. Никаких автоматических изменений: применение появится только после достаточной ручной выборки и подтверждения.",
    "Blatero compares the current thresholds with anonymised numeric snapshots from real recordings. No changes are automatic: applying a profile requires enough manually reviewed samples and your confirmation."
  ],
  [
    "сигнал",
    "signal"
  ],
  [
    "наблюдение",
    "observation"
  ],
  [
    "сейчас",
    "current"
  ],
  [
    "рекомендация",
    "recommendation"
  ],
  [
    "решение",
    "decision"
  ],
  [
    "пересчитать локально",
    "recalculate locally"
  ],
  [
    "Применить только показанный профиль",
    "Apply only the displayed profile"
  ],
  [
    "При изменении архива потребуется новый расчёт.",
    "If the archive changes, calculate a new profile."
  ],
  [
    "применить рекомендации",
    "apply recommendations"
  ],
  [
    "Загружаю локальные измерения…",
    "Loading local measurements…"
  ],
  [
    "ЭТАЛОН КАЧЕСТВА",
    "QUALITY REFERENCE"
  ],
  [
    "Эталон качества",
    "Quality reference"
  ],
  [
    "Сверяйте архивный транскрипт с исходным звуком. Черновик хранится отдельно и не меняет запись, рабочий транскрипт или отчёт.",
    "Check the archived transcript against the original audio. The draft is separate and does not change the recording, working transcript or report."
  ],
  [
    "показать",
    "show"
  ],
  [
    "все записи",
    "all recordings"
  ],
  [
    "черновики",
    "drafts"
  ],
  [
    "подтверждённые",
    "reviewed"
  ],
  [
    "без эталона",
    "no reference"
  ],
  [
    "обновить",
    "refresh"
  ],
  [
    "Загружаю локальный набор…",
    "Loading the local set…"
  ],
  [
    "ПРОСЛУШАТЬ · ИСПРАВИТЬ · СОХРАНИТЬ",
    "LISTEN · EDIT · SAVE"
  ],
  [
    "Разметка",
    "Annotation"
  ],
  [
    "к списку",
    "back to list"
  ],
  [
    "поиск",
    "search"
  ],
  [
    "текст, имя, роль",
    "text, name, role"
  ],
  [
    "Я прослушал спорные места и сверил текст, роль и канал",
    "I listened to uncertain passages and checked the text, role and channel"
  ],
  [
    "подтвердить эталон",
    "confirm reference"
  ],
  [
    "вернуть в черновик",
    "reopen draft"
  ],
  [
    "Корпус и метрики находятся только в локальном архиве. В общую статистику входят лишь вручную подтверждённые эталоны. Цель первого измеримого релиза — 10–20 реальных встреч.",
    "The corpus and metrics remain in the local archive. Only manually reviewed references contribute to aggregate statistics. Quality calibration targets 10–20 real meetings."
  ],
  [
    "Повторный локальный прогон архивной записи через выбранные распознавание речи, очистку эха и разделение голосов. Исходные аудио, транскрипт и отчёт не изменяются; каждый эксперимент сохраняется отдельно и удаляется целиком.",
    "Reprocess an archived recording locally with the selected recognition, echo cancellation and diarization settings. Original audio, transcript and report remain unchanged. Each experiment is saved separately and can be deleted as a unit."
  ],
  [
    "архивная встреча",
    "archived meeting"
  ],
  [
    "Дорожка",
    "Track"
  ],
  [
    "tiny · быстро",
    "tiny · fast"
  ],
  [
    "small · баланс",
    "small · balanced"
  ],
  [
    "medium · точнее",
    "medium · more accurate"
  ],
  [
    "large-v3 · медленно",
    "large-v3 · slow"
  ],
  [
    "встроенный корреляционный",
    "built-in correlation"
  ],
  [
    "только WebRTC AEC3 → fallback при сбое",
    "WebRTC AEC3 only → fallback on failure"
  ],
  [
    "Ожидается голосов",
    "Expected voices"
  ],
  [
    "0 — авто; на шумных звонках лучше указать число",
    "0 means auto; specify a count for noisy calls"
  ],
  [
    "Признаки голоса",
    "Voice embeddings"
  ],
  [
    "NeMo TitaNet · рекомендуется",
    "NeMo TitaNet · recommended"
  ],
  [
    "3D-Speaker · прежний",
    "3D-Speaker · legacy"
  ],
  [
    "Порог кластеризации",
    "Clustering threshold"
  ],
  [
    "0,40 · разделять чаще",
    "0.40 · split more often"
  ],
  [
    "0,50 · базовый",
    "0.50 · default"
  ],
  [
    "0,60 · объединять чаще",
    "0.60 · merge more often"
  ],
  [
    "Разделить голосовые кластеры",
    "Separate voice clusters"
  ],
  [
    "Локальная CPU-диаризация после Whisper.",
    "Local CPU diarization after Whisper."
  ],
  [
    "Контрольная подсказка после прогона",
    "Test hint after the run"
  ],
  [
    "Не симуляция тайминга: один финальный pulse. Может использовать выбранный LLM и требует облачного согласия.",
    "One final hint request, not a timing simulation. It may use the selected AI service and requires cloud acknowledgement."
  ],
  [
    "запустить один вариант",
    "start one run"
  ],
  [
    "Что сравнить",
    "Compare"
  ],
  [
    "AEC · выкл / корреляция / WebRTC",
    "AEC · off / correlation / WebRTC"
  ],
  [
    "Голоса · 4 варианта кластеризации",
    "Voices · 4 clustering settings"
  ],
  [
    "запустить несколько и сравнить",
    "run several and compare"
  ],
  [
    "Выберите настройки варианта.",
    "Choose the run settings."
  ],
  [
    "Прогоны и сравнение",
    "Runs and comparison"
  ],
  [
    "сравнить расхождения",
    "compare differences"
  ],
  [
    "СРАВНЕНИЕ И ПРОСЛУШИВАНИЕ",
    "COMPARE AND LISTEN"
  ],
  [
    "Где варианты услышали разное",
    "Where the runs disagree"
  ],
  [
    "свернуть сравнение",
    "collapse comparison"
  ],
  [
    "свернуть",
    "collapse"
  ],
  [
    "ТАЙМЛАЙН И ЗАДЕРЖКИ",
    "TIMELINE AND LATENCY"
  ],
  [
    "Встреча в исходном темпе",
    "Meeting at its original pace"
  ],
  [
    "закрыть таймлайн",
    "close timeline"
  ],
  [
    "скорость",
    "speed"
  ],
  [
    "ответ LLM, сек",
    "AI response, seconds"
  ],
  [
    "тишина до запроса, сек",
    "silence before request, seconds"
  ],
  [
    "Реплики",
    "Utterances"
  ],
  [
    "Окна для подсказки",
    "Hint windows"
  ],
  [
    "Повестка",
    "Agenda"
  ],
  [
    "Сохранить",
    "Save"
  ],
  [
    "Импорт транскрипта",
    "Import transcript"
  ],
  [
    "Адаптеры понимают выгрузки Microsoft Teams, Zoom, Яндекс Телемоста и Контур.Толка. Файл обрабатывается на этом компьютере и добавляется новым сегментом — существующая запись не перезаписывается.",
    "Import Microsoft Teams, Zoom, Yandex Telemost and Kontur.Talk exports. The file is processed on this computer and added as a new segment; existing recordings are not overwritten."
  ],
  [
    "Источник",
    "Source"
  ],
  [
    "Выберите источник или оставьте автоопределение.",
    "Choose the source or leave automatic detection enabled."
  ],
  [
    "Файл до 2 МБ",
    "File up to 2 MB"
  ],
  [
    "Как в файле подписан мой голос",
    "My speaker label in the file"
  ],
  [
    "например, Роман; можно оставить пустым",
    "for example, Alex; optional"
  ],
  [
    "добавить в текущую встречу",
    "add to the current meeting"
  ],
  [
    "Локальный банк голосов",
    "Local voice bank"
  ],
  [
    "Blatero хранит только числовые голосовые отпечатки и имя профиля. Исходная запись в банк не копируется, данные не отправляются в облако, а найденное имя всегда требует ручного подтверждения.",
    "Blatero stores only numeric voiceprints and a profile name. The original recording is not copied to the bank, data is not sent to the cloud, and suggested names always need your confirmation."
  ],
  [
    "Добавить мой голос",
    "Add my voice"
  ],
  [
    "Рекомендуется калибровка по нескольким архивным встречам: она отбракует дорожки с эхом и несогласованные фрагменты. Отдельный образец для синтеза голоса доступен как запасной вариант.",
    "Calibration across several archived meetings excludes echo tracks and inconsistent fragments. A separate voice synthesis sample is available as a fallback."
  ],
  [
    "Имя профиля",
    "Profile name"
  ],
  [
    "например, Роман",
    "for example, Alex"
  ],
  [
    "Создать локальный голосовой отпечаток",
    "Create a local voiceprint"
  ],
  [
    "Подтверждаю, что это мой голос и согласен хранить его отпечаток на этом компьютере до ручного удаления.",
    "I confirm this is my voice and agree to store its voiceprint on this computer until I delete it."
  ],
  [
    "калибровать по архиву",
    "calibrate from archive"
  ],
  [
    "использовать образец голоса",
    "use a voice sample"
  ],
  [
    "записать образец…",
    "record a sample…"
  ],
  [
    "Загружаю банк…",
    "Loading voice bank…"
  ],
  [
    "Сохранённые профили",
    "Saved profiles"
  ],
  [
    "У каждого профиля можно изменить только подпись, либо записать отдельные 15 секунд для проверки. Проверочная запись удаляется сразу; автоматическое назначение имён отключено.",
    "Rename a profile or record a separate 15-second sample to test it. The test recording is deleted immediately; automatic name assignment is disabled."
  ],
  ["проверить голос","test voice"],
  ["Очередь STT","STT queue"],
  ["Задержка live STT","Live STT latency"],
  ["Отставание WAV","WAV backlog"],
  ["Перегрузка сигнала","Signal clipping"],
  ["Подтвердите ещё {count} эталонных встреч.","Review {count} more reference meetings."],
  ["Нужны числовые срезы минимум из {count} встреч: {metrics}.","Numeric snapshots from at least {count} meetings are required: {metrics}."],
  ["Текущий профиль уже подтверждён собранными данными.","The collected data already supports the current profile."],
  ["Только числа и коды событий; текст реплик, имена и названия аудиоустройств не записываются.","Only numbers and event codes are recorded, not utterance text, names or audio device names."],
  ["Использовать готовый транскрипт","Reuse the existing transcript"],
  ["Если такой же прогон уже распознан, Whisper не запускается повторно.","If an identical run was already transcribed, Whisper is not repeated."],
  ["Точность распознавания","Recognition accuracy"],
  ["1 · быстрее","1 · faster"],
  ["3 · точнее","3 · more accurate"],
  [" · транскрипт готовый"," · reused transcript"]
];
  window.BlateroStudioI18n?.register('tool',pairs);
  const materials = /* MATERIAL_PHRASES */ [
  [
    "Материалы по ходу встречи",
    "Materials during the meeting"
  ],
  [
    "Закрыть материалы",
    "Close materials"
  ],
  [
    "Закрыть",
    "Close"
  ],
  [
    "Добавление материалов не останавливает запись. Файлы сохраняются локально в этой встрече; отправка в ИИ — только после просмотра.",
    "Adding materials does not stop recording. Files are saved locally in this meeting; they are sent to AI only after review."
  ],
  [
    "Добавить файлы или вставить картинку",
    "Add files or paste an image"
  ],
  [
    "＋ Добавить файлы",
    "＋ Add files"
  ],
  [
    "▣ Снимок области",
    "▣ Capture a region"
  ],
  [
    "Перетащите сюда документы или вставьте картинку: Ctrl+V. До 10 МБ на файл, до 50 материалов на встречу.",
    "Drop documents here or paste an image with Ctrl+V. Up to 10 MB per file and 50 materials per meeting."
  ],
  [
    "В подсказки и отчёт включается выжимка последних 12 разобранных материалов, до 18 000 символов. Все результаты доступны ниже.",
    "Hints and reports use a summary of the latest 12 analysed materials, up to 18,000 characters. All results remain available below."
  ],
  [
    "Горячие клавиши и новые файлы",
    "Shortcuts and new files"
  ],
  [
    "Снимок области в активной вкладке Blatero",
    "Region capture in the active Blatero tab"
  ],
  [
    "Выключено",
    "Off"
  ],
  [
    "Обрабатывать Print Screen в активной вкладке Blatero",
    "Handle Print Screen in the active Blatero tab"
  ],
  [
    "Выключено по умолчанию. За пределами вкладки клавиша работает как обычно; браузер или Windows могут оставить за собой её системное действие.",
    "Off by default. Outside this tab the key works as usual; the browser or Windows may retain its system action."
  ],
  [
    "Замечать новые и изменённые файлы рабочей папки",
    "Detect new and changed files in the working folder"
  ],
  [
    "Пока открыта вкладка. Проверяется размер и время изменения; новые файлы не отправляются автоматически. Первый опрос запоминает текущий состав папки.",
    "Runs while this tab is open. Checks size and modification time; new files are not sent automatically. The first check records the current folder contents."
  ],
  [
    "Выделите область мышью или задайте координаты",
    "Select a region with the mouse or enter coordinates"
  ],
  [
    "Предпросмотр снимка",
    "Capture preview"
  ],
  [
    "Ширина",
    "Width"
  ],
  [
    "Высота",
    "Height"
  ],
  [
    "Добавить только выделенную область",
    "Add the selected region only"
  ],
  [
    "Отменить снимок",
    "Cancel capture"
  ],
  [
    "Полный снимок остаётся в памяти браузера. На локальный сервер попадёт только выбранная область. Закрасить лишнее можно при проверке материала.",
    "The full capture stays in browser memory. Only the selected region is sent to the local server. Cover sensitive areas during material review."
  ],
  [
    "материал",
    "material"
  ],
  [
    "Добавить документ или снимок без остановки записи",
    "Add a document or capture without stopping recording"
  ],
  [
    "Настройки действуют до закрытия вкладки: браузер не разрешил сохранение.",
    "These preferences last until the tab closes: the browser blocked local storage."
  ],
  [
    "Встреча сменилась. Откройте материалы заново.",
    "The meeting changed. Open materials again."
  ],
  [
    "Пока нет дополнительных материалов.",
    "No additional materials yet."
  ],
  [
    "анализ учтён в контексте",
    "analysis included in context"
  ],
  [
    "сохранён локально, ещё не проанализирован",
    "saved locally, not analysed yet"
  ],
  [
    "Повторно проверить и проанализировать",
    "Review and analyse again"
  ],
  [
    "Проверить перед анализом",
    "Review before analysis"
  ],
  [
    "Дождитесь текущего анализа.",
    "Wait for the current analysis to finish."
  ],
  [
    "Локально читаю материал и проверяю данные…",
    "Reading the material locally and checking data…"
  ],
  [
    "Что нового",
    "New facts"
  ],
  [
    "Что перепроверить",
    "Conclusions to review"
  ],
  [
    "Что уточнить сейчас",
    "Questions to clarify now"
  ],
  [
    "Нет подтверждённых предложений.",
    "No supported suggestions."
  ],
  [
    "Дождитесь текущей загрузки.",
    "Wait for the current upload to finish."
  ],
  [
    "Встреча сменилась. Загрузка остановлена.",
    "The meeting changed. Upload stopped."
  ],
  [
    "{p0}: файл больше 10 МБ",
    "{p0}: file exceeds 10 MB"
  ],
  [
    "Сохраняю локально: {p0}…",
    "Saving locally: {p0}…"
  ],
  [
    "Материалы сохранены локально. Нажмите «Проверить перед анализом» у нужного файла.",
    "Materials saved locally. Choose Review before analysis next to a file."
  ],
  [
    "Захват недоступен в этом браузере. Сделайте снимок средствами Windows и вставьте Ctrl+V.",
    "Capture is unavailable in this browser. Use Windows capture and paste with Ctrl+V."
  ],
  [
    "Снимок отменён: окно закрыто или встреча сменилась.",
    "Capture cancelled: the dialog closed or the meeting changed."
  ],
  [
    "Снимок отменён: встреча сменилась или окно закрыто.",
    "Capture cancelled: the meeting changed or the dialog closed."
  ],
  [
    "Слишком большой снимок. Выберите отдельное окно.",
    "Capture is too large. Choose a single window."
  ],
  [
    "Выделите область. На сервер пока ничего не отправлено.",
    "Select a region. Nothing has been sent to the server yet."
  ],
  [
    "Захват отменён или не разрешён. Можно вставить готовый снимок через Ctrl+V.",
    "Capture was cancelled or denied. You can paste an existing image with Ctrl+V."
  ],
  [
    "Встреча сменилась; снимок не добавлен.",
    "The meeting changed; capture was not added."
  ],
  [
    "{p0}: {p1} — добавить",
    "{p0}: {p1} — add"
  ],
  [
    "Новый",
    "New"
  ],
  [
    "Изменён",
    "Changed"
  ],
  [
    "Новых или изменённых файлов: {p0}. Добавьте нужные для проверки.",
    "New or changed files: {p0}. Add the ones you want to review."
  ],
  [
    "Проверено файлов: {p0}. Новых изменений нет.{p1}",
    "Files checked: {p0}. No new changes.{p1}"
  ],
  [
    "Охват папки ограничен.",
    "Folder scan coverage is limited."
  ],
  [
    "материал · готово",
    "material · ready"
  ],
  ["Файл добавлен локально; откройте проверку.","File added locally; open review."],
  ["Анализ готов. Следующие подсказки и отчёт учтут материал.","Analysis ready. The next hints and report will include this material."],
  ["Дождитесь текущей проверки материала.","Wait for the current material review to finish."],
  ["Ошибка обработки материала: {detail}","Material processing failed: {detail}"]
];
  window.BlateroStudioI18n?.register('material',materials);
  const services = /* SERVICE_PHRASES */ [
  [
    "Операция выполняется. Не закрывайте сервер Blatero.",
    "Operation in progress. Keep the Blatero server running."
  ],
  [
    "Состояние проверено. Установка и удаление доступны только на этом компьютере.",
    "Status checked. Installation and removal are available on this computer only."
  ],
  [
    "управляемые файлы",
    "managed files"
  ],
  [
    "0 Б",
    "0 B"
  ],
  [
    "свободно на диске",
    "free disk space"
  ],
  [
    "корень моделей",
    "model directory"
  ],
  [
    "загрузка ≈ {p0}",
    "download ≈ {p0}"
  ],
  [
    "восстановить",
    "repair"
  ],
  [
    "установить",
    "install"
  ],
  [
    "удалить",
    "delete"
  ],
  [
    "выполняется",
    "running"
  ],
  [
    "место",
    "disk space"
  ],
  [
    "система",
    "system"
  ],
  [
    "лицензия",
    "license"
  ],
  [
    "активная модель",
    "active model"
  ],
  [
    "неизвестно",
    "unknown"
  ],
  [
    "Установить «{p0}»? Потребуется примерно {p1}. Загрузка идёт только из закреплённого источника в локальный каталог Blatero.",
    "Install “{p0}”? About {p1} is required. Downloads use the pinned source and the local Blatero directory."
  ],
  [
    "Удалить «{p0}» и освободить {p1}? Удаляются только управляемые файлы Blatero. Записи встреч и образец вашего голоса останутся.",
    "Remove “{p0}” and free {p1}? Only files managed by Blatero are removed. Meeting recordings and your voice sample remain."
  ],
  [
    "Обнаружен общий Whisper-cache:",
    "Shared Whisper cache found:"
  ],
  [
    "Модели:",
    "Models:"
  ],
  [
    "Считаю место и проверяю файлы моделей…",
    "Checking model files and disk usage…"
  ],
  [
    "Версия {p0} подготовлена — перезапустите Blatero.",
    "Version {p0} is staged — restart Blatero."
  ],
  [
    "Откат к {p0} подготовлен.",
    "Rollback to {p0} is staged."
  ],
  [
    "Пакетных операций не ожидается.",
    "No package operations are pending."
  ],
  [
    "текущая версия",
    "current version"
  ],
  [
    "программа",
    "application"
  ],
  [
    "данные",
    "data"
  ],
  [
    "файлов",
    "files"
  ],
  [
    "ожидает перезапуска",
    "waiting for restart"
  ],
  [
    "Релиз ещё не выбран.",
    "No release selected yet."
  ],
  [
    "Можно вернуться к версии {p0}. Откат также применяется при следующем запуске.",
    "You can return to version {p0}. Rollback also takes effect on the next launch."
  ],
  [
    "до последнего обновления",
    "before the last update"
  ],
  [
    "После первого пакетного обновления здесь появится возврат к предыдущей версии.",
    "After the first package update, the previous version will be available here."
  ],
  [
    "Чтобы применить подготовленное действие: остановите сервер, затем снова запустите ярлык Blatero. При сбое зависимостей launcher автоматически восстановит предыдущие файлы.",
    "To apply the staged action, stop the server and launch Blatero again. If dependency setup fails, the launcher restores the previous files."
  ],
  [
    "Сейчас запущена рабочая Git-копия. Здесь можно проверить подпись релиза, но обновлять её пакетом нельзя — используйте Git. Пакетный режим включается установщиком.",
    "This is a Git checkout. You can verify a release signature here, but use Git to update this copy. Package updates are enabled by the installer."
  ],
  [
    "Проверяю ожидающие действия и резервную копию…",
    "Checking pending actions and the backup…"
  ],
  [
    "ошибка: {p0}",
    "error: {p0}"
  ],
  [
    "подключён",
    "connected"
  ],
  [
    "нужна авторизация",
    "sign-in required"
  ],
  [
    "Внешние календари ещё не подключены. Локальное schedule.json уже показано.",
    "No external calendars are connected. The local schedule.json is already shown."
  ],
  [
    "Удалить это подключение и локальный токен/пароль?",
    "Delete this connection and its local token/password?"
  ],
  [
    "Для просмотра проверки ПД перезапустите Blatero и обновите страницу.",
    "Restart Blatero and reload the page to open personal-data review."
  ],
  [
    "Получатель: {p0} · модель: {p1} · {p2}",
    "Recipient: {p0} · model: {p1} · {p2}"
  ],
  [
    "Подозрительных фрагментов: {p0}. Они скрыты в отправляемом тексте.",
    "Potentially sensitive fragments: {p0}. They are hidden in the outgoing text."
  ],
  [
    "подтверждаю текст и картинки — отправить и подготовить",
    "approve text and images — send and prepare"
  ],
  [
    "подтверждаю текст — отправить и подготовить",
    "approve text — send and prepare"
  ],
  [
    "Для анализа нужна модель с поддержкой изображений. Используется модель подготовки, указанная выше. Изображения могут увеличить стоимость запроса.",
    "Image analysis requires a vision-capable model. It uses the preparation model shown above. Images may increase request cost."
  ],
  [
    "Текущий провайдер здесь принимает только текст. Для картинок выберите в настройках Codex, OpenRouter, OpenAI, Anthropic или совместимый API и модель со зрением. Текст и структура схем доступны и без этого.",
    "This provider currently accepts text only here. For images, choose Codex, OpenRouter, OpenAI, Anthropic or a compatible API with a vision model. Text and diagram structure remain available without it."
  ],
  [
    "Отправить картинку:",
    "Send image:"
  ],
  [
    "Просмотреть и скрыть области",
    "Review and mask regions"
  ],
  [
    "Изображение",
    "Image"
  ],
  [
    "Можно скрыть до 40 областей на изображении.",
    "You can mask up to 40 regions per image."
  ],
  [
    "сбросить области и перепроверить",
    "reset masks and recheck"
  ],
  [
    "Задать область с клавиатуры (проценты)",
    "Enter a region using the keyboard (percent)"
  ],
  [
    "Слева",
    "Left"
  ],
  [
    "Сверху",
    "Top"
  ],
  [
    "Ширина",
    "Width"
  ],
  [
    "Высота",
    "Height"
  ],
  [
    "закрасить область",
    "mask region"
  ],
  [
    "Область должна находиться внутри картинки.",
    "The region must be inside the image."
  ],
  [
    "CPU · 4 ГБ RAM · самый быстрый из доступных",
    "CPU · 4 GB RAM · fastest available option"
  ],
  [
    "CPU · 6 ГБ RAM · рекомендуемый баланс качества",
    "CPU · 6 GB RAM · recommended balance"
  ],
  [
    "CPU · 10 ГБ RAM · точнее, но заметно медленнее",
    "CPU · 10 GB RAM · more accurate, but noticeably slower"
  ],
  [
    "Windows x64 · CPU · подавление акустического эха",
    "Windows x64 · CPU · acoustic echo cancellation"
  ],
  [
    "Проверенный sidecar OpenWhispr для очистки микрофона.",
    "Verified OpenWhispr sidecar for microphone echo cancellation."
  ],
  [
    "Разделение голосов",
    "Speaker separation"
  ],
  [
    "CPU · 4 ГБ RAM · постобработка записи",
    "CPU · 4 GB RAM · recording post-processing"
  ],
  [
    "ONNX-сегментация с NeMo TitaNet; 3D-Speaker сохранён для банка голосов.",
    "ONNX segmentation with NeMo TitaNet; 3D-Speaker is retained for the voice bank."
  ],
  [
    "CPU · 16 ГБ RAM · 8 ГБ диска · генерация не потоковая",
    "CPU · 16 GB RAM · 8 GB disk · non-streaming generation"
  ],
  [
    "Локальный синтез и клонирование голоса; образец голоса удаляется отдельно.",
    "Local speech synthesis and voice cloning; delete the voice sample separately."
  ],
  [
    "Локальное распознавание речи через faster-whisper.",
    "Local speech recognition using faster-whisper."
  ],
  [
    "отменить отправку",
    "cancel sending"
  ],
  [
    "Что уйдёт в облако",
    "What will be sent to the cloud"
  ],
  [
    "Оригиналы остаются на компьютере. Проверка может пропустить данные, особенно после OCR. Это не гарантия анонимности: проверьте текст справа. Согласие на облачную обработку настраивается отдельно.",
    "Originals stay on this computer. The check can miss data, especially after OCR. It does not guarantee anonymity: review the text on the right. Cloud acknowledgement is configured separately."
  ],
  [
    "Включённые файлы",
    "Included files"
  ],
  [
    "Снимите галочку, чтобы исключить файл. При исключениях прежний анализ проекта не используется.",
    "Clear a checkbox to exclude a file. When exclusions change, the previous project analysis is not reused."
  ],
  [
    "Дополнительно скрыть — каждый фрагмент с новой строки",
    "Hide additional text — one fragment per line"
  ],
  [
    "Имя, адрес, название клиента или другой фрагмент",
    "Name, address, client name or another fragment"
  ],
  [
    "Исходный запрос с подсветкой — только локально",
    "Highlighted source request — local only"
  ],
  [
    "Точный текст отправки",
    "Exact outgoing text"
  ],
  [
    "Системная инструкция",
    "System instruction"
  ],
  [
    "Визуальный анализ картинок — отдельно от текста",
    "Image analysis is separate from text"
  ],
  [
    "Картинки не обезличиваются автоматически. Выберите нужные, закрасьте личные данные прямоугольником на картинке и нажмите «Перепроверить локально». В ИИ уйдут только выбранные изображения в показанном виде, без исходных метаданных.",
    "Images are not anonymised automatically. Select the images, cover personal data with rectangles and choose Recheck locally. Only selected images in the displayed form are sent to AI, without original metadata."
  ],
  [
    "Для выбранных картинок исходный OCR и прежний анализ проекта не используются, чтобы скрытые сведения не вернулись через текст.",
    "Original OCR and previous project analysis are not used for selected images, so masked information does not reappear through text."
  ],
  [
    "Я проверил выбранные картинки и разрешаю отправить именно эти изображения.",
    "I reviewed the selected images and approve sending these exact images."
  ],
  [
    "перепроверить локально",
    "recheck locally"
  ],
  [
    "закрыть",
    "close"
  ],
  [
    "ЛОКАЛЬНЫЕ МОДЕЛИ",
    "LOCAL MODELS"
  ],
  [
    "Локальные модели",
    "Local models"
  ],
  [
    "Установка, требования и место на диске. Удаляются только каталоги, которыми управляет Blatero; образец вашего голоса сохраняется отдельно.",
    "Installation, requirements and disk usage. Only directories managed by Blatero are removed; your voice sample is stored separately."
  ],
  [
    "обновить",
    "refresh"
  ],
  [
    "Проверяю локальные компоненты…",
    "Checking local components…"
  ],
  [
    "ПОДПИСЬ И ОТКАТ",
    "SIGNATURE AND ROLLBACK"
  ],
  [
    "Установка и обновления",
    "Installation and updates"
  ],
  [
    "Blatero проверяет подпись Ed25519 и контрольную сумму каждого файла. Обновление применяется только после остановки сервера; записи, модели, токены, память и голосовой профиль находятся в отдельном каталоге данных.",
    "Blatero checks the Ed25519 signature and every file checksum. Updates apply only after the server stops. Recordings, models, tokens, memory and the voice profile are stored in a separate data directory."
  ],
  [
    "Проверяю состояние установки…",
    "Checking installation status…"
  ],
  [
    "Подготовить обновление",
    "Stage an update"
  ],
  [
    "Выберите локальный ZIP-релиз. Файл будет дважды проверен и скопирован в защищённую очередь; текущий процесс не меняется.",
    "Choose a local release ZIP. It is verified twice and copied to the staging queue; the running process is not changed."
  ],
  [
    "выбрать и проверить ZIP",
    "choose and verify ZIP"
  ],
  [
    "подготовить",
    "stage"
  ],
  [
    "отменить",
    "cancel"
  ],
  [
    "Откат",
    "Rollback"
  ],
  [
    "подготовить откат",
    "stage rollback"
  ]
];
  services.push(
    ['Откат к предыдущей версии подготовлен. Перезапустите Blatero.','Rollback to the previous version is staged. Restart Blatero.'],
    ['Операция модели: {detail}','Model operation: {detail}'],
    ['Операция не завершена: {detail}','Operation did not complete: {detail}'],
    ['Модель установлена и проверена.','Model installed and verified.'],
    ['Компонент удалён; освобождено {freed}.','Component removed; freed {freed}.'],
    ['Начинаю установку…','Starting installation…'],
    ['Удаляю только управляемые файлы Blatero…','Removing files managed by Blatero only…'],
    ['Выбор файла отменён.','File selection cancelled.'],
    ['Релиз не принят: {detail}','Release rejected: {detail}'],
    ['Обновление не подготовлено: {detail}','Update not staged: {detail}'],
    ['Версия {version} подготовлена. Остановите Blatero и запустите ярлык снова — данные встреч не затрагиваются.','Version {version} is staged. Stop Blatero and launch it again; meeting data is not affected.'],
    ['Ожидаю выбор подписанного ZIP-релиза…','Waiting for a signed release ZIP…'],
    ['Повторно проверяю и копирую релиз…','Verifying and copying the release again…'],
    ['Подготовленное обновление отменено.','Staged update cancelled.'],
    ['Откат к версии {version} подготовлен. Перезапустите Blatero.','Rollback to version {version} is staged. Restart Blatero.'],
    ['предыдущей','the previous version'],
    ['Проверка выполнена локально. Автоматическое обнаружение может ошибаться. Просмотрите отправляемый текст.','The check ran locally. Automatic detection can be wrong. Review the outgoing text.'],
    ['определяется Codex CLI','assigned by Codex CLI'],
    ['Состояние проверено.','Status checked.'],
    ['Подпись и контрольные суммы релиза проверены.','Release signature and checksums verified.'],
    ['определить автоматически','detect automatically'],
    ['Teams, Zoom, Телемост, Контур.Толк и универсальные файлы','Teams, Zoom, Telemost, Kontur.Talk and universal files'],
    ['скачанный из Teams транскрипт VTT или DOCX','transcript downloaded from Teams as VTT or DOCX'],
    ['аудиотранскрипт облачной записи Zoom в формате VTT','audio transcript of a Zoom cloud recording in VTT format'],
    ['Яндекс Телемост','Yandex Telemost'],
    ['полная расшифровка из письма; при необходимости сохраните текст как TXT','full transcript from the email; save as TXT if needed'],
    ['Контур.Толк','Kontur.Talk'],
    ['TXT из раздела «Расшифровка» с авторами и таймкодами','TXT from the Transcript section with speakers and timestamps'],
    ['другой источник','another source'],
    ['SRT, VTT, JSON или текст с таймкодами и именами участников','SRT, VTT, JSON or text with timestamps and speaker names'],
    ['готово к работе','ready'],['нужно восстановить','needs repair'],['не установлено','not installed'],
    ['Общий cache других приложений. Blatero показывает его, но не удаляет.','Shared cache used by other applications. Blatero displays it but does not remove it.'],
    ['Общий cache Whisper не используется менеджером Blatero.','The shared Whisper cache is not managed by Blatero.'],
    ['Выбор изменён. Нажмите «Перепроверить локально» и просмотрите новый текст.','Selection changed. Choose Recheck locally and review the new text.'],
    ['Повторная локальная проверка… Ничего не отправляется в облако.','Rechecking locally… Nothing is sent to the cloud.'],
    ['Проверяю, что материалы не изменились; затем отправлю подтверждённый текст…','Checking that materials have not changed, then sending the approved text…']);
  window.BlateroStudioI18n?.register('service',services);
const remaining = /* REMAINING_PHRASES */ [
  [
    "решить позже",
    "Decide later"
  ],
  [
    "ВОССТАНОВЛЕНИЕ",
    "RECOVERY"
  ],
  [
    "Найдены незавершённые операции",
    "Unfinished operations found"
  ],
  [
    "Blatero отличает оборванную запись, фоновую задачу и схему данных. Аудио чинится только после резервной копии. Отчёт продолжится из проверенной контрольной точки, а неизвестный формат сессии не открывается наугад.",
    "Audio, background jobs and session schemas have separate recovery paths. Audio repair first creates a backup. A report resumes from a verified checkpoint; an unknown session format is blocked."
  ],
  [
    "Незавершённых операций нет.",
    "No unfinished operations."
  ],
  [
    "Действия на этом экране не удаляют запись встречи или готовые результаты.",
    "These actions do not delete meeting recordings or completed results."
  ],
  [
    "закрыть",
    "close"
  ],
  [
    "Системные промпты",
    "System prompts"
  ],
  [
    "Здесь собраны системные инструкции и шаблоны запросов, которые определяют подсказки, отчёты, вопросы и режим эмуляции. Изменения хранятся только на этом компьютере и применяются к следующему запросу модели. Защитные правила остаются включены независимо от текста ниже.",
    "Instructions and templates for hints, reports, questions and simulation. Changes stay on this computer and apply to the next model request. Safety guards remain enabled regardless of this text."
  ],
  [
    "Список промптов",
    "Prompt list"
  ],
  [
    "Загружаю реестр…",
    "Loading catalog…"
  ],
  [
    "Выберите промпт слева",
    "Choose a prompt on the left"
  ],
  [
    "Текст выбранного системного промпта",
    "Selected system prompt text"
  ],
  [
    "посмотреть заводской вариант",
    "view default"
  ],
  [
    "сохранить локальную версию",
    "save local version"
  ],
  [
    "сбросить к заводскому",
    "reset to default"
  ],
  [
    "Проверка и настройка звука",
    "Audio checks and setup"
  ],
  [
    "Закрыть проверку звука",
    "Close audio checks"
  ],
  [
    "Готовность к встрече",
    "Ready for the meeting"
  ],
  [
    "Одна проверка микрофона, звука приложения встречи, очистки эха, распознавания речи и записи. Сначала говорите, затем замолчите для тестового сигнала. Для STT используется отдельная встроенная фраза: Whisper проверяется локально в двух каналах, при выбранном SpeechKit эта фраза отправляется в Яндекс. Речь из проверки микрофона не отправляется.",
    "Check microphone, meeting audio, echo cancellation, recognition and recording. Speak first, then stay quiet for the test signal. STT uses a separate built-in phrase: Whisper runs locally in two channels; SpeechKit sends only the fixture to Yandex, not your microphone test speech."
  ],
  [
    "проверить всё",
    "check all"
  ],
  [
    "скачать диагностику",
    "download diagnostics"
  ],
  [
    "Проверка ещё не запускалась.",
    "No check has run yet."
  ],
  [
    "Микрофон",
    "Microphone"
  ],
  [
    "После отсчёта скажите: «Проверяю микрофон перед встречей. Меня хорошо слышно».",
    "After the countdown, speak in your normal voice for the microphone sample."
  ],
  [
    "Уровень микрофона",
    "Microphone level"
  ],
  [
    "Нажмите кнопку, когда будете готовы говорить. Проба остаётся в памяти этой вкладки; в облако и папку встречи не попадает.",
    "Click when ready to speak. The sample stays in this tab's memory, not the cloud or meeting folder."
  ],
  [
    "Начать проверку микрофона",
    "Start microphone check"
  ],
  [
    "Отменить",
    "Cancel"
  ],
  [
    "обновить список устройств",
    "refresh devices"
  ],
  [
    "Ваша проба",
    "Your sample"
  ],
  [
    "Прослушать проверочную запись микрофона",
    "Play microphone test sample"
  ],
  [
    "Удалить пробу",
    "Delete sample"
  ],
  [
    "Системный звук встречи",
    "Meeting audio"
  ],
  [
    "Уровень системного звука",
    "System audio level"
  ],
  [
    "Выберите тот же выход, который указан в приложении встречи. Во время проверки включите тестовый звук или видео.",
    "Select the output used by the meeting app. Play test audio or video during the check."
  ],
  [
    "проверить 8 секунд",
    "test for 8 seconds"
  ],
  [
    "Мой голос · Chatterbox локально",
    "My voice · local Chatterbox"
  ],
  [
    "Прочитайте спокойным естественным голосом текст ниже, без длинных пауз и постороннего шума.",
    "Read the text below in your normal voice, without long pauses or background noise."
  ],
  [
    "длительность",
    "duration"
  ],
  [
    "15 с · рекомендуется",
    "15 s · recommended"
  ],
  [
    "30 с",
    "30 s"
  ],
  [
    "60 с",
    "60 s"
  ],
  [
    "Сегодня я говорю спокойно и уверенно. Мне важно, чтобы каждое слово звучало ясно и естественно. Я делаю небольшие паузы между предложениями, сохраняю ровный темп и обычную интонацию. Этот образец поможет программе воспроизвести особенности моего голоса.",
    "Today I am speaking calmly and clearly. I want every word to sound natural. I take short pauses between sentences, keep a steady pace and use my normal intonation. This sample will help the program reproduce the characteristics of my voice."
  ],
  [
    "Уровень записи образца голоса",
    "Voice sample recording level"
  ],
  [
    "Проверяю локальный движок и образец…",
    "Checking local engine and sample…"
  ],
  [
    "записать образец",
    "record sample"
  ],
  [
    "проверить мой голос",
    "test my voice"
  ],
  [
    "подготовить вопросы встречи",
    "prepare meeting questions"
  ],
  [
    "удалить мой голос",
    "delete my voice"
  ],
  [
    "Локально:",
    "Local:"
  ],
  [
    "образец, модель и готовые WAV находятся только в папке Blatero. Если вопрос ещё не подготовлен или движок ошибся, Яндекс используется лишь в режиме «мой голос → Яндекс» и при включённом согласии.",
    "The sample, model and saved WAVs stay in the Blatero data folder. Yandex is used only for the local-to-Yandex route when audio is unavailable and cloud processing is enabled."
  ],
  [
    "Резервный голос Яндекс SpeechKit",
    "Yandex SpeechKit fallback voice"
  ],
  [
    "Для проверки выберите конкретный голос в настройках.",
    "Choose a specific voice in settings to test it."
  ],
  [
    "В SpeechKit уйдёт только фиксированная тестовая фраза, без данных встречи.",
    "Only a fixed test phrase goes to SpeechKit, without meeting data."
  ],
  [
    "прослушать выбранный голос",
    "play selected voice"
  ],
  [
    "Быстрое действие",
    "Quick action"
  ],
  [
    "Закрыть палитру",
    "Close command palette"
  ],
  [
    "Поиск команды",
    "Find a command"
  ],
  [
    "Начните вводить: запись, отчёт, звук, настройки…",
    "Type: record, report, audio, settings…"
  ],
  [
    "Доступные команды",
    "Available commands"
  ],
  [
    "↑ ↓ — выбрать · Enter — выполнить · можно искать по русским словам",
    "↑ ↓ select · Enter run · search by command name"
  ],
  [
    "{p0} / {p1} · {p2} встреч",
    "{p0} / {p1} · meetings: {p2}"
  ],
  [
    "размечено",
    "labeled"
  ],
  [
    "{p0} подтверждено · {p1} исключено",
    "confirmed: {p0} · excluded: {p1}"
  ],
  [
    "точность допуска",
    "acceptance precision"
  ],
  [
    "{p0} верных · {p1} опасных",
    "correct: {p0} · unsafe: {p1}"
  ],
  [
    "верхняя граница 95%",
    "95% upper bound"
  ],
  [
    "цель не выше {p0}",
    "target at most {p0}"
  ],
  [
    "ручная проверка",
    "manual review"
  ],
  [
    "{p0} выводов остановлено",
    "conclusions blocked: {p0}"
  ],
  [
    "{confirmed} подтверждено · {excluded} исключено",
    "{confirmed} confirmed · {excluded} excluded"
  ],
  [
    "{safe} верных · {unsafe} опасных",
    "{safe} correct · {unsafe} unsafe"
  ],
  [
    "цель не выше {value}",
    "target at most {value}"
  ],
  [
    "{count} выводов остановлено",
    "{count} conclusions held for review"
  ],
  [
    "{count} / {target} · встреч: {sessions}",
    "{count} / {target} · meetings: {sessions}"
  ],
  [
    "В текущем отчёте размечено выводов: {labeled} из {total}.",
    "Conclusions labeled in this report: {labeled} of {total}."
  ],
  [
    "Он полностью вошёл в корпус.",
    " The full report is included in the corpus."
  ],
  [
    "Подтвердите или исключите остальные, если хотите использовать его как полный эталон.",
    " Confirm or exclude the remaining conclusions to use it as a complete reference."
  ],
  [
    "В текущем отчёте пока нет размечаемых выводов.",
    "This report has no conclusions to label yet."
  ],
  [
    "нет ссылки на реплику",
    "no utterance reference"
  ],
  [
    "реплика не найдена",
    "utterance not found"
  ],
  [
    "низкая уверенность STT",
    "low STT confidence"
  ],
  [
    "самоаудит: нет опоры",
    "self-review: no evidence"
  ],
  [
    "самоаудит: противоречие",
    "self-review: contradiction"
  ],
  [
    "Подтверждено: {confirmed} · исключено: {excluded} · ждут решения: {pending}",
    "Confirmed: {confirmed} · excluded: {excluded} · awaiting a decision: {pending}"
  ],
  [
    "опора найдена",
    "evidence found"
  ],
  [
    "проверить",
    "review"
  ],
  [
    "нет опоры",
    "no evidence"
  ],
  [
    "на проверке",
    "pending review"
  ],
  [
    "подтверждён",
    "confirmed"
  ],
  [
    "исключён из DOCX",
    "excluded from DOCX"
  ],
  [
    "подтвердить",
    "confirm"
  ],
  [
    "исключить",
    "exclude"
  ],
  [
    "редактирование",
    "edit"
  ],
  [
    "смена статуса",
    "status change"
  ],
  [
    "обновление из отчёта",
    "report update"
  ],
  [
    "история ·",
    "history ·"
  ],
  [
    "Состояние памяти неизвестно.",
    "Memory status is unknown."
  ],
  [
    "клиент",
    "client"
  ],
  [
    "проект",
    "project"
  ],
  [
    "записей",
    "items"
  ],
  [
    "очистить только записи",
    "clear items only"
  ],
  [
    "Очистить записи памяти {p1}",
    "Clear memory items: {p1}"
  ],
  [
    "забыть область вместе со снимком",
    "forget scope and snapshot"
  ],
  [
    "Полностью забыть {p1}",
    "Completely forget {p1}"
  ],
  [
    "Удалить все подтверждённые записи памяти «{p0}»? Снимок файлов проекта сохранится.",
    "Delete all confirmed memory items for “{p0}”? The project file snapshot stays."
  ],
  [
    "Полностью забыть «{p0}»? Будут удалены записи с историей, путь, снимок файлов и связи проекта. Отменить это нельзя.",
    "Completely forget “{p0}”? This deletes items, history, path, file snapshot and project aliases. This cannot be undone."
  ],
  [
    "{p0} · {p1} записей{p2}",
    "{p0} · items: {p1}{p2}"
  ],
  [
    "Основание:",
    "Basis:"
  ],
  [
    "ответственный: {p0}",
    "owner: {p0}"
  ],
  [
    "срок: {p0}",
    "due: {p0}"
  ],
  [
    "просрочено",
    "overdue"
  ],
  [
    "сегодня",
    "today"
  ],
  [
    "через {p0} дн.",
    "in {p0} days"
  ],
  [
    "основание",
    "basis"
  ],
  [
    "вернуть",
    "restore"
  ],
  [
    "изменить",
    "edit"
  ],
  [
    "удалить",
    "delete"
  ],
  [
    "Тип записи памяти",
    "Memory item type"
  ],
  [
    "Текст записи памяти",
    "Memory item text"
  ],
  [
    "Ответственный",
    "Owner"
  ],
  [
    "ответственный",
    "owner"
  ],
  [
    "Срок",
    "Due date"
  ],
  [
    "срок: 2026-08-15 или текст",
    "due: YYYY-MM-DD or note"
  ],
  [
    "отмена",
    "cancel"
  ],
  [
    "сохранить v",
    "save v"
  ],
  [
    "Подтверждённых решений и фактов пока нет.",
    "No confirmed decisions or facts yet."
  ],
  [
    "Удалить эту запись из общей памяти?",
    "Delete this shared memory item?"
  ],
  [
    "Сначала укажите клиента или проект",
    "Set a client or project first"
  ],
  [
    "Сначала сформируйте итоговый отчёт",
    "Create the final report first"
  ],
  [
    "Создать проверяемый черновик из отчёта",
    "Create a reviewable draft from the report"
  ],
  [
    "задачи встречи ↗",
    "meeting tasks ↗"
  ],
  [
    "транскрипт целиком",
    "full transcript"
  ],
  [
    "отчёт",
    "report"
  ],
  [
    "временная шкала",
    "timeline"
  ],
  [
    "опоры JSON",
    "evidence JSON"
  ],
  [
    "проверка разметки",
    "annotation review"
  ],
  [
    "кластеры голосов",
    "voice clusters"
  ],
  [
    "я",
    "me"
  ],
  [
    "собеседник",
    "other participant"
  ],
  [
    "МБ",
    "MiB"
  ],
  [
    "удалить всё аудио",
    "delete all audio"
  ],
  [
    "повторить",
    "repeat"
  ],
  [
    "зашифровать",
    "encrypt"
  ],
  [
    "управлять данными",
    "manage data"
  ],
  [
    "● идёт запись",
    "● recording"
  ],
  [
    "файлов пока нет",
    "no files yet"
  ],
  [
    "пусто",
    "empty"
  ],
  [
    "Безвозвратно удалить {p0}?",
    "Permanently delete {p0}?"
  ],
  [
    "Безвозвратно удалить ВСЕ аудиофайлы этой встречи? Транскрипт и отчёт останутся.",
    "Permanently delete ALL audio for this meeting? Transcript and report stay."
  ],
  [
    "идёт запись образца · осталось {p0} с",
    "recording sample · {p0} s left"
  ],
  [
    "локальный движок Chatterbox не установлен",
    "Local Chatterbox engine is not installed"
  ],
  [
    "движок установлен · запишите образец своего голоса",
    "Engine installed · record your voice sample"
  ],
  [
    "клон отклонён · {p0} · пока используется Яндекс",
    "clone rejected · {p0} · Yandex is used for now"
  ],
  [
    "речь не совпала с текстом",
    "speech did not match the text"
  ],
  [
    "речь проверена · {p0} · образец {p1} с",
    "speech checked · {p0} · {p1} s sample"
  ],
  [
    "образец {p0} с записан · проверьте голос перед подготовкой вопросов",
    "{p0} s sample recorded · test the voice before preparing questions"
  ],
  [
    "Обновите страницу, чтобы открыть новую проверку с прослушиванием.",
    "Reload to open the new check with sample playback."
  ],
  [
    "Во время записи используйте индикаторы внизу. Проверка доступна после остановки.",
    "Use the meters during recording. This test is available after Stop."
  ],
  [
    "Нет подключения к серверу. Подождите и нажмите кнопку снова.",
    "No server connection. Wait and click again."
  ],
  [
    "Приготовьтесь говорить. Начало через 3 секунды.",
    "Get ready to speak. Starting in 3 seconds."
  ],
  [
    "Начало через {p0}…",
    "Starting in {p0}…"
  ],
  [
    "Проверка не началась: нет подключения или уже идёт запись. Нажмите кнопку снова.",
    "Check did not start: disconnected or already recording. Click again when ready."
  ],
  [
    "Открываю выбранный микрофон…",
    "Opening selected microphone…"
  ],
  [
    "Идёт запись · 12 с",
    "Recording · 12 s"
  ],
  [
    "Идёт запись · осталось {p0} с",
    "Recording · {p0} s left"
  ],
  [
    "Повторить проверку",
    "Repeat check"
  ],
  [
    "проверка завершена",
    "check completed"
  ],
  [
    "проба слишком велика",
    "sample is too large"
  ],
  [
    "Не удалось открыть пробу: {p0}",
    "Could not open sample: {p0}"
  ],
  [
    "проверяю маршрут…",
    "checking audio route…"
  ],
  [
    "loopback {p0} дБFS",
    "loopback {p0} dBFS"
  ],
  [
    "эхо {p0} дБFS",
    "echo {p0} dBFS"
  ],
  [
    "задержка {p0} мс",
    "delay {p0} ms"
  ],
  [
    "WebRTC AEC3 {p0} установлен · SHA-256 проверен",
    "WebRTC AEC3 {p0} installed · SHA-256 verified"
  ],
  [
    "WebRTC AEC3 не установлен; используется встроенный фильтр.",
    "WebRTC AEC3 is not installed; using the built-in filter."
  ],
  [
    "WebRTC AEC3 установлен",
    "WebRTC AEC3 installed"
  ],
  [
    "установить WebRTC AEC3",
    "install WebRTC AEC3"
  ],
  [
    "Редактируемые промпты не найдены.",
    "No editable prompts found."
  ],
  [
    "Перейти к другому промпту и потерять несохранённые изменения?",
    "Switch prompts and discard unsaved changes?"
  ],
  [
    "Обязательные служебные маркеры:",
    "Required template markers:"
  ],
  [
    "Служебных подстановок нет — текст можно менять свободно.",
    "No required placeholders; the text can be edited freely."
  ],
  [
    "Локальный шаблон не применяется; используется заводской.",
    "Local template is invalid; using the default."
  ],
  [
    "используется локальная версия",
    "using local version"
  ],
  [
    "заводской вариант",
    "default version"
  ],
  [
    "Получить подсказку",
    "Get a hint"
  ],
  [
    "Сильный следующий ход по текущей встрече",
    "Next question or clarification for this meeting"
  ],
  [
    "ответ совет",
    "answer advice"
  ],
  [
    "Остановить запись",
    "Stop recording"
  ],
  [
    "Начать запись",
    "Start recording"
  ],
  [
    "Управление записью текущей встречи",
    "Control this meeting's recording"
  ],
  [
    "старт стоп микрофон",
    "start stop microphone"
  ],
  [
    "Новая встреча",
    "New meeting"
  ],
  [
    "Пошаговая подготовка встречи или тренировки",
    "Prepare a meeting or training step by step"
  ],
  [
    "создать интервью консалтинг",
    "create interview consulting"
  ],
  [
    "Проверить всё",
    "Check all"
  ],
  [
    "Микрофон, системный звук, эхо, распознавание речи и ИИ",
    "Microphone, system audio, echo, speech recognition and AI"
  ],
  [
    "диагностика звук",
    "diagnostics audio"
  ],
  [
    "Свернуть / показать сценарий",
    "Collapse / show scenario"
  ],
  [
    "Освободить место для подсказок",
    "Make room for hints"
  ],
  [
    "боковая колонка фокус",
    "sidebar focus"
  ],
  [
    "Показать / скрыть историю",
    "Show / hide history"
  ],
  [
    "Транскрипт без скрытия Аудиосторожа",
    "Transcript without hiding Audio Guard"
  ],
  [
    "лента реплики история",
    "feed transcript history"
  ],
  [
    "Показать последний ответ крупно",
    "Enlarge last answer"
  ],
  [
    "Режим чтения без отвлечений",
    "Focused reading view"
  ],
  [
    "подсказка экран",
    "hint screen"
  ],
  [
    "Повестка",
    "Agenda"
  ],
  [
    "Открыть контекст текущей встречи",
    "Open this meeting's context"
  ],
  [
    "Календарь",
    "Calendar"
  ],
  [
    "Расписание дня и недели",
    "Day and week schedule"
  ],
  [
    "встречи события",
    "meetings events"
  ],
  [
    "Тренировка собеседования",
    "Interview practice"
  ],
  [
    "Вопросы, голос и оценка ответа",
    "Questions, voice and answer review"
  ],
  [
    "mock интервью обучение",
    "mock interview training"
  ],
  [
    "Память клиента и проекта",
    "Client and project memory"
  ],
  [
    "Решения, обещания и открытые вопросы",
    "Decisions, commitments and open questions"
  ],
  [
    "контекст история",
    "context history"
  ],
  [
    "Сформировать отчёт",
    "Create report"
  ],
  [
    "Контроль качества и DOCX",
    "Review and DOCX export"
  ],
  [
    "документ результат",
    "document result"
  ],
  [
    "Настройки",
    "Settings"
  ],
  [
    "Встреча, ИИ, звук, приватность и интерфейс",
    "Meeting, AI, audio, privacy and appearance"
  ],
  [
    "конфигурация",
    "configuration"
  ],
  [
    "Аудио и говорящие",
    "Audio and speakers"
  ],
  [
    "Записи, Replay Lab, голоса, имена и проверка каналов",
    "Recordings, Replay, voices, names and channel checks"
  ],
  [
    "aec chatterbox яндекс диаризация",
    "aec chatterbox yandex diarization"
  ],
  [
    "Локальные модели",
    "Local models"
  ],
  [
    "Whisper, Chatterbox, AEC и разделение голосов",
    "Whisper, Chatterbox, AEC and speaker separation"
  ],
  [
    "установить удалить место диск",
    "install remove space disk"
  ],
  [
    "Установка и обновления",
    "Installation and updates"
  ],
  [
    "Проверка подписи, обновление и откат",
    "Signature verification, update and rollback"
  ],
  [
    "версия релиз rollback",
    "version release rollback"
  ],
  [
    "Восстановление записей",
    "Recording recovery"
  ],
  [
    "Незавершённые встречи после сбоя",
    "Interrupted meetings after a crash"
  ],
  [
    "авария wav jsonl",
    "crash wav jsonl"
  ],
  [
    "Просмотр и локальное редактирование",
    "View and edit locally"
  ],
  [
    "инструкции llm",
    "instructions llm"
  ],
  [
    "Открыть папку результатов",
    "Open results folder"
  ],
  [
    "Текущая встреча в Проводнике",
    "Current meeting in File Explorer"
  ],
  [
    "отчет файлы",
    "report files"
  ],
  [
    "{p0} мин {p1} с",
    "{p0} min {p1} s"
  ],
  [
    "{p0} с",
    "{p0} s"
  ],
  [
    "цел",
    "intact"
  ],
  [
    "нужна проверка",
    "needs review"
  ],
  [
    "время неизвестно",
    "time unknown"
  ],
  [
    "место не проверено",
    "disk space not checked"
  ],
  [
    "нужно",
    "required"
  ],
  [
    "· свободно",
    "· free"
  ],
  [
    "можно восстановить",
    "can be recovered"
  ],
  [
    "освободите место",
    "free disk space"
  ],
  [
    "ПРЕРВАННАЯ ЗАПИСЬ ·",
    "INTERRUPTED RECORDING ·"
  ],
  [
    "· реплик:",
    "· utterances:"
  ],
  [
    "WAV не записывался",
    "No WAV was recorded"
  ],
  [
    "восстановить и открыть",
    "recover and open"
  ],
  [
    "завершить как прерванную",
    "mark interrupted"
  ],
  [
    "очистить временные хвосты",
    "clean temporary tails"
  ],
  [
    "Оставить аудио и транскрипт без изменений и больше не предлагать восстановление?",
    "Leave audio/transcript unchanged and stop offering recovery?"
  ],
  [
    "контрольная точка",
    "checkpoint"
  ],
  [
    "локальное продолжение",
    "local continuation"
  ],
  [
    "нужен повтор",
    "retry needed"
  ],
  [
    "новый LLM-запрос",
    "new AI request"
  ],
  [
    "без нового LLM-запроса",
    "no new AI request"
  ],
  [
    "ФОНОВАЯ ЗАДАЧА ·",
    "BACKGROUND JOB ·"
  ],
  [
    "этап:",
    "stage:"
  ],
  [
    "повторить после подтверждения",
    "retry after confirmation"
  ],
  [
    "продолжить",
    "continue"
  ],
  [
    "не возобновлять",
    "do not resume"
  ],
  [
    "очистить временные файлы",
    "clean temporary files"
  ],
  [
    "Сохранённого ответа LLM нет. Повторить задачу с новым запросом к выбранному провайдеру?",
    "No saved model response. Retry with a new request to the selected provider?"
  ],
  [
    "Не возобновлять эту задачу? Уже сохранённые файлы встречи останутся.",
    "Do not resume this job? Saved meeting files will remain."
  ],
  [
    "версия неизвестна",
    "version unknown"
  ],
  [
    "можно завершить",
    "can be completed"
  ],
  [
    "нужна новая версия",
    "newer version required"
  ],
  [
    "заблокировано",
    "blocked"
  ],
  [
    "ФОРМАТ ДАННЫХ",
    "DATA FORMAT"
  ],
  [
    "обновить схему",
    "update schema"
  ],
  [
    "Завершить локальную миграцию с резервной копией meta.json?",
    "Complete the local migration with a meta.json backup?"
  ],
  [
    "Ничего не найдено. Попробуйте «звук», «отчёт» или «сценарий».",
    "Nothing found. Try audio, report or scenario."
  ],
  [
    "Закрыть редактор и потерять несохранённые изменения?",
    "Close editor and discard unsaved changes?"
  ],
  [
    "Сначала остановите запись, чтобы сохранить последние реплики.",
    "Stop recording first to preserve the last utterances."
  ],
  [
    "Завершить работу Blatero и остановить локальный сервер?",
    "Exit Blatero and stop the local server?"
  ],
  [
    "Не удалось завершить Blatero: {p0}",
    "Could not shut down Blatero: {p0}"
  ],
  [
    "Сначала выберите конкретный голос вместо «auto».",
    "Choose a specific voice instead of auto first."
  ],
  [
    "загружаю голос {p0} из SpeechKit…",
    "loading voice {p0} from SpeechKit…"
  ],
  [
    "воспроизводится голос {p0}",
    "playing voice {p0}"
  ],
  [
    "голос не проверен: {p0}",
    "voice not verified: {p0}"
  ],
  [
    "локальный голос загружается…",
    "loading local voice…"
  ],
  [
    "воспроизводится мой локальный голос",
    "playing my local voice"
  ]
];
const remainingExtra = /* REMAINING_EXTRA */ [
  ["последняя синхронизация: {date}","last sync: {date}"],
  ["Ничего не рассчитано.","No estimate yet."],
  ["Связь с сервером прервалась. Нажмите кнопку для новой проверки.","Server connection lost. Press the button to start a new check."],
  ["Выберите встречу в архиве.","Select a meeting in the archive."],
  ["Парольная фраза короче 10 символов.","The passphrase is shorter than 10 characters."],
  ["Введите парольную фразу пакета.","Enter the package passphrase."],
  ["Состав изменён — рассчитайте заново.","Selection changed — calculate again."],
  ["Выберите встречу и хотя бы одну категорию.","Select a meeting and at least one category."],
  ["Удаление отменено: имя не совпало.","Deletion cancelled: the name did not match."],
  ["Будут безвозвратно удалены {count} файлов ({size}).\n\nВведите имя папки сессии для подтверждения:\n{session}","Permanently delete {count} files ({size}).\n\nEnter the session folder name to confirm:\n{session}"],
  ["Обновляю размеры и контрольные суммы…","Refreshing sizes and checksums…"],
  ["Отменить подготовленное обновление или откат?","Cancel the staged update or rollback?"],
  ["Подготовить возврат к предыдущей версии?\n\nДанные встреч и модели не изменятся.","Stage a rollback to the previous version?\n\nMeeting data and models will not change."],
  ["Удалить API-токен выбранного провайдера из Windows Credential Manager?","Delete the selected provider's API token from Windows Credential Manager?"],
  ["Передавать в LLM исходные ФИО, контакты и другие данные без обезличивания?","Send original names, contacts and other data to AI without anonymisation?"],
  ["Сохранено в этом браузере.","Saved in this browser."],
  ["Браузер запретил сохранение. Выбор действует только в этой вкладке.","Browser storage is blocked. The choice applies only in this tab."],
  ["Сформировать проверяемый черновик отчёта?","Create a report draft for review?"],
  ["Закрыть без сохранения правок черновика?","Close without saving draft changes?"],
  ["Закрыть редактор без сохранения изменённой реплики?","Close the editor without saving the edited utterance?"],
  ["Пересобрать черновик по текущему транскрипту? Это выполнит новый запрос к выбранной LLM.","Rebuild the draft from the current transcript? This sends a new request to the selected AI provider."],
  ["Создать отчёт, явно указав в нём оставшиеся ограничения?","Create the report with the remaining limitations explicitly included?"],
  ["Загружаю реестр…","Loading registry…"],
  ["есть несохранённые изменения","unsaved changes"],
  ["проверяю и сохраняю…","validating and saving…"],
  ["Локальная версия сохранена и применится к следующему запросу.","Local version saved; it will apply to the next request."],
  ["Восстановлен заводской вариант.","Default version restored."],
  ["Сбросить «{label}» к заводскому варианту?","Reset “{label}” to its default version?"],
  ["Собираю обезличенную диагностику…","Building anonymised diagnostics…"],
  ["Сначала калибровка или явный пропуск","Calibrate or explicitly skip first"],
  ["Выберите один из двух вариантов выше.","Choose one of the two options above."],
  ["Удалить локальный образец вашего голоса и все подготовленные фразы?","Delete your local voice sample and all prepared phrases?"],
  ["Решение","Decision"],["Обещание","Commitment"],["Открытый вопрос","Open question"],["Проверенный факт","Verified fact"],
  ["изменение","change"],
  ["Активных записей: {active} · областей: {scopes} · требуют внимания: {attention}","Active items: {active} · scopes: {scopes} · need attention: {attention}"],
  ["Укажите клиента или проект, чтобы включить память между встречами.","Set a client or project to enable memory between meetings."],
  ["Области связаны, но подтверждённых записей пока нет.","Scopes linked; no confirmed items yet."],
  ["Черновик памяти уже формируется…","Memory draft is already being prepared…"],
  ["ИИ выделяет предложения; память ещё не изменяется…","AI is preparing proposals; confirmed memory is unchanged…"],
  ["Черновик готов. Проверьте пункты перед сохранением.","Draft ready. Review items before saving."],
  ["Отклонить весь черновик? Подтверждённая память не изменится.","Discard the entire draft? Confirmed memory stays unchanged."],
  ["Введите текст записи.","Enter item text."],["Выберите хотя бы один пункт.","Select at least one item."],
  ["Связать текущую папку с памятью проекта «{label}»?","Link the current folder to project memory “{label}”?"],
  ["клон отклонён · {reason} · проверьте выбранный маршрут озвучки","clone rejected · {reason} · check the selected voice route"],
  ["Задача была прервана.","The job was interrupted."],["Схема сессии требует проверки.","The session schema needs review."],
  ["неизвестен","unknown"],
  ["собеседование","interview"],["кандидат","candidate"],["консалтинг","consulting"],["встреча","meeting"],["тренировка","training"]
];
remainingExtra.push(
  ["Portable обновляется полным пакетом в новой папке. Данные по умолчанию остаются в Документы/Blatero; для другого пути используйте BLATERO_DATA_DIR. Не копируйте новые файлы поверх старых.","Update portable using a complete package in a new folder. Default data stays in Documents/Blatero; use BLATERO_DATA_DIR for a custom path. Do not copy new files over old ones."],
  ["Сохранение транскрипта прервано","Transcript saving interrupted"],
  ["Не все распознанные реплики сохранены. Исходный WAV записывается отдельно.","Not all recognised turns were saved. The original WAV is recorded separately."],
  ["После встречи восстановите транскрипт из WAV в разделе разбора аудио.","After the meeting, recover the transcript from WAV in Audio review."],
  ["Проверьте восстановленный текст перед созданием отчёта.","Review the recovered text before creating a report."],
  ["В записи была смена аудиоустройства","Audio device changed during recording"],
  ["При переключении физического устройства был перерыв захвата.","Capture was interrupted while switching the physical device."],
  ["При разборе встречи проверьте участок смены устройства.","Review the part of the meeting where the device changed."],
  ["Времена переключений сохранены в диагностике встречи.","Device change times are saved in the meeting diagnostics."],
  ["Аудиофильтр отключён после ошибки","Audio filter disabled after an error"],
  ["Распознавание получает исходный PCM без этого фильтра. WAV не изменяется.","Recognition receives the original PCM without this filter. WAV is unchanged."],
  ["Проверьте звук и состояние очистки эха после встречи.","Check audio and echo cancellation after the meeting."],
  ["При следующей записи фильтр должен снова обрабатывать микрофон.","The filter should process the microphone again in the next recording."],
  [" · ещё {count}"," · {count} more"],
  ["Что сделать:","What to do:"],["Как проверить:","How to verify:"]
);
remainingExtra.push(
  ["настройки звука","audio settings"],["настройки STT","STT settings"],
  ["открыть папку","open folder"],["открыть настройки","open settings"],
  ["рекомендация","notice"],["внимание","warning"],["критично","critical"],
  ["событие","event"],["автопроверка записи","automatic recording check"]
);
remaining.push(...remainingExtra);
window.BlateroStudioI18n?.register("remaining",remaining);
})();
