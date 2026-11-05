"""Единый реестр редактируемых системных инструкций и шаблонов."""
from __future__ import annotations

CAT_HINTS = "Живые подсказки"
CAT_REPORTS = "Итоговые отчёты"
CAT_WORKSPACE = "Контекст проекта"
CAT_MEMORY = "Память проекта и клиента"
CAT_QUESTIONS = "Банк вопросов"
CAT_SPARRING = "Тренировка интервьюера"
CAT_CANDIDATE_TRAINING = "Тренировка кандидата"
CAT_AI_SCENE = "Тренировка · ИИ-сценка"


def _item(key: str, category: str, label: str, description: str, default: str,
          placeholders: tuple[str, ...] = (), required_literals: tuple[str, ...] = ()) -> dict:
    return {
        "key": key, "category": category, "label": label,
        "description": description, "default": default,
        "placeholders": list(placeholders), "required": list(placeholders),
        "required_literals": list(required_literals),
    }


def definitions() -> list[dict]:
    # Импорты отложены: panel.py запрашивает каталог уже после полной загрузки.
    import copilot
    import ai_scene
    import interview_training
    import speech_training
    import meeting_types
    import meeting_memory
    import panel
    import question_bank
    import report
    import sparring
    import workspace_context

    result = []
    for key, preset in meeting_types.TYPES.items():
        label = preset.get("label", key)
        result.extend([
            _item(f"meeting.{key}.pulse_system", CAT_HINTS,
                  f"{label} · системная инструкция",
                  "Роль ассистента и формат оперативной подсказки.",
                  preset["pulse_system"]),
            _item(f"meeting.{key}.report_system", CAT_REPORTS,
                  f"{label} · системная инструкция",
                  "Роль модели и правила итогового разбора встречи.",
                  preset["report_system"]),
            _item(f"meeting.{key}.report_structure", CAT_REPORTS,
                  f"{label} · структура отчёта",
                  "Заголовки и состав итогового документа.",
                  preset["report_structure"]),
        ])
    result.extend([
        _item("speech.coach.system", "Тренировка речи", "Разбор содержания · system",
              "Наблюдения по цитатам, одна задача для повтора; без выводов о голосе по тексту.",
              speech_training.COACH_SYSTEM),
        _item("speech.coach.template", "Тренировка речи", "Выступление и цель · template",
              "План и сегменты сохранённой попытки.", speech_training.COACH_TEMPLATE,
              ("plan", "segments")),
        _item("speech.compare.system", "Тренировка речи", "Сравнение по одной правке · system",
              "Две попытки и цитаты, без оценки голоса по тексту.", speech_training.COMPARE_SYSTEM),
        _item("speech.compare.template", "Тренировка речи", "Сравнение попыток · template",
              "Выбранная правка и исходные сегменты обеих попыток.", speech_training.COMPARE_TEMPLATE,
              ("focus", "plan", "before", "after")),
        _item("pulse.template.default", CAT_HINTS, "Подсказка интервьюеру / встрече",
              "Шаблон данных и JSON-ответа для обычных режимов.",
              copilot.PULSE_TEMPLATE_BASE,
              ("agenda_label", "roles", "tags_hint", "questions_hint", "flags_hint"),
              ("{{rubric}}", "{{tail}}", "{{prev}}")),
        _item("pulse.template.candidate", CAT_HINTS, "Быстрый ответ кандидату",
              "Шаблон быстрого ответа на последний вопрос интервьюера.",
              copilot.CANDIDATE_PULSE_TEMPLATE,
              ("agenda_label", "roles", "flags_hint"),
              ("{{rubric}}", "{{tail}}", "{{prev}}")),
        _item("report.template", CAT_REPORTS, "Общий шаблон отчёта",
              "Собирает повестку, транскрипт и выбранную структуру.",
              report.REPORT_TEMPLATE,
              ("agenda_label", "rubric", "roles", "transcript", "structure")),
        _item("emulation.system", "SIM · эмуляция", "Роль второго участника",
              "Инструкция боту, который говорит за кандидата, интервьюера или клиента.",
              panel.EMULATION_SYSTEM, ("role", "meeting_type")),
        _item("workspace.system", CAT_WORKSPACE, "Аналитик рабочей папки",
              "Системная роль для анализа локально отобранных файлов.",
              workspace_context.SYSTEM_PROMPT),
        _item("workspace.template", CAT_WORKSPACE, "Запрос анализа проекта",
              "Шаблон контекста встречи, фрагментов файлов и списка вопросов.",
              workspace_context.USER_PROMPT,
              ("meeting_label", "name", "duration", "brief", "content",
               "previous_context", "change_summary")),
        _item("memory.system", CAT_MEMORY, "Хранитель памяти · system",
              "Правила безопасного извлечения проверяемых сведений из отчёта.",
              meeting_memory.SYSTEM_PROMPT),
        _item("memory.template", CAT_MEMORY, "Черновик памяти из отчёта",
              "Выделяет решения, обещания, вопросы и факты для подтверждения.",
              meeting_memory.USER_PROMPT, ("scopes", "existing", "report")),
        _item("questions.system", CAT_QUESTIONS, "Технический интервьюер",
              "Общая системная роль для генерации и адаптации вопросов.",
              question_bank.INTERVIEWER_SYSTEM),
        _item("questions.generation", CAT_QUESTIONS, "Генерация общего банка",
              "Создание базового questions.md из рубрики.", question_bank.GEN_PROMPT,
              ("rubric", "style_block")),
        _item("questions.personal", CAT_QUESTIONS, "Персональные вопросы",
              "Вопросы по анкете, коду и рискам конкретного кандидата.",
              question_bank.PERSONAL_PROMPT, ("rubric", "name", "materials")),
        _item("questions.fit", CAT_QUESTIONS, "Боевой план по времени",
              "Сжатие полного банка под длительность встречи.", question_bank.FIT_PROMPT,
              ("minutes", "bank", "dossier", "style_note")),
        _item("dossier.system", CAT_QUESTIONS, "Ассистент досье",
              "Системная роль подготовки досье кандидата.", question_bank.DOSSIER_SYSTEM),
        _item("dossier.template", CAT_QUESTIONS, "Шаблон досье",
              "Структура внутренней шпаргалки по материалам кандидата.",
              question_bank.DOSSIER_PROMPT, ("name", "materials")),
        _item("questions.verify.system", CAT_QUESTIONS, "Проверяющий банка",
              "Системная роль независимой проверки фактической корректности.",
              question_bank.VERIFY_SYSTEM),
        _item("questions.verify.template", CAT_QUESTIONS, "Проверка корректности",
              "Критерии технической проверки банка вопросов.",
              question_bank.VERIFY_PROMPT, ("bank",)),
        _item("sparring.profile.system", CAT_SPARRING, "Генератор профиля · system",
              "Формат скрытого профиля учебного кандидата.", sparring.JSON_SYSTEM),
        _item("sparring.profile.template", CAT_SPARRING, "Генератор профиля · запрос",
              "Шаблон создания скрытого профиля по рубрике.", sparring.PROFILE_PROMPT,
              ("rubric",)),
        _item("sparring.candidate.system", CAT_SPARRING, "Учебный кандидат",
              "Поведение кандидата со скрытыми сильными и слабыми сторонами.",
              sparring.CANDIDATE_SYSTEM, ("profile",)),
        _item("sparring.score.system", CAT_SPARRING, "Экзаменатор · system",
              "Формат машинной оценки тренировки.", sparring.JSON_SYSTEM),
        _item("sparring.score.template", CAT_SPARRING, "Экзаменатор · запрос",
              "Критерии оценки действий интервьюера.", sparring.SCORECARD_PROMPT,
              ("profile", "transcript", "hints")),
        _item("sparring.debrief.system", CAT_SPARRING, "Тренер · system",
              "Тон и роль автора разбора тренировки.", sparring.DEBRIEF_SYSTEM),
        _item("sparring.debrief.template", CAT_SPARRING, "Тренер · разбор",
              "Структура обратной связи после тренировки.", sparring.DEBRIEF_PROMPT,
              ("profile", "transcript", "hints")),
        _item("training.plan.system", CAT_CANDIDATE_TRAINING,
              "План интервью · system",
              "Роль генератора универсального учебного интервью.",
              interview_training.PLAN_SYSTEM),
        _item("training.plan.template", CAT_CANDIDATE_TRAINING,
              "План интервью · запрос",
              "Генерация вопросов из роли, резюме, вакансии, ссылок и проекта.",
              interview_training.PLAN_PROMPT,
              ("role", "difficulty", "question_count", "context",
               "adaptive_history")),
        _item("training.evaluate.system", CAT_CANDIDATE_TRAINING,
              "Оценка ответа · system",
              "Роль работодателя, оценивающего один ответ кандидата.",
              interview_training.EVALUATE_SYSTEM),
        _item("training.evaluate.template", CAT_CANDIDATE_TRAINING,
              "Оценка ответа · запрос",
              "Критерии оценки, исправления и улучшенный вариант ответа.",
              interview_training.EVALUATE_PROMPT,
              ("role", "question", "why", "expected_points", "red_flags",
               "hints_used", "delivery", "answer")),
        _item("scene.cast.system", CAT_AI_SCENE, "Режиссёр сценки · system",
              "Создаёт независимые роли и скрытый профиль кандидата.",
              ai_scene.CAST_SYSTEM),
        _item("scene.cast.template", CAT_AI_SCENE, "Режиссёр сценки · запрос",
              "Задаёт вымышленный опыт и знания выбранного уровня; пробелы необязательны.",
              ai_scene.CAST_PROMPT,
              ("role", "difficulty", "style", "rounds", "context")),
        _item("scene.interviewer.system", CAT_AI_SCENE, "ИИ-интервьюер · system",
              "Правила независимого интервьюера без доступа к слабостям кандидата.",
              ai_scene.INTERVIEWER_SYSTEM),
        _item("scene.interviewer.template", CAT_AI_SCENE, "ИИ-интервьюер · ход",
              "Формирует один вопрос из публичного контекста и прошлого ответа.",
              ai_scene.INTERVIEWER_PROMPT,
              ("role", "difficulty", "round_number", "round_limit",
               "interviewer", "context", "history")),
        _item("scene.candidate.system", CAT_AI_SCENE, "ИИ-кандидат · system",
              "Разделяет знания роли, личный опыт и ограничения скрытого профиля.",
              ai_scene.CANDIDATE_SYSTEM),
        _item("scene.candidate.template", CAT_AI_SCENE, "ИИ-кандидат · ход",
              "Формирует ответ из профиля, материалов и разговора; уровень добавляется отдельно.",
              ai_scene.CANDIDATE_PROMPT,
              ("role", "profile", "context", "history")),
        _item("scene.review.system", CAT_AI_SCENE, "Тренер сценки · system",
              "Независимая оценка интервьюера, кандидата и реалистичности.",
              ai_scene.REVIEW_SYSTEM),
        _item("scene.review.template", CAT_AI_SCENE, "Тренер сценки · разбор",
              "Сопоставляет диалог со скрытым профилем после остановки.",
              ai_scene.REVIEW_PROMPT,
              ("role", "difficulty", "profile", "interviewer", "history")),
    ])
    category_order = {
        name: index for index, name in enumerate((
            CAT_HINTS, CAT_REPORTS, "SIM · эмуляция",
            CAT_WORKSPACE, CAT_MEMORY, CAT_QUESTIONS,
            CAT_CANDIDATE_TRAINING, CAT_AI_SCENE, CAT_SPARRING))
    }
    return sorted(result, key=lambda item: category_order.get(item["category"], 99))
