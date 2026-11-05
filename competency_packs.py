"""Versioned, trusted competency profiles for interview training.

Free-form roles remain the default. A selected pack adds a curated rubric to
the model context; it never replaces candidate materials or supplies a hidden
verdict about a person.
"""
from __future__ import annotations

import copy
import re


SCHEMA = "blatero.competency-packs/v1"
PACK_VERSION = 1
LEVELS = ("junior", "middle", "senior")
_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


_PACKS = {
    "one-c-developer": {
        "label": "1С-разработчик",
        "role": "Разработчик 1С",
        "description": "Платформа, данные, проведение, производительность и инженерная практика",
        "interview_focus": (
            "Проверяй понимание причин и компромиссов, а не знание названий. "
            "После базового ответа проси применить подход к небольшой рабочей ситуации."
        ),
        "competencies": [
            {
                "id": "platform-context",
                "name": "Контекст платформы и общая логика",
                "levels": {
                    "junior": "различает клиент, сервер, модули объекта/менеджера и общие модули",
                    "middle": "выбирает место логики по ответственности, повторному использованию и контексту вызова",
                    "senior": "задаёт границы подсистемы и объясняет влияние решения на сопровождение и расширения",
                },
                "evidence": ["сам предлагает место кода и объясняет почему", "учитывает клиент-серверный вызов"],
            },
            {
                "id": "data-and-queries",
                "name": "Данные, запросы и регистры",
                "levels": {
                    "junior": "понимает выборку, соединения, NULL и отличие отсутствия значения от нуля",
                    "middle": "работает с виртуальными таблицами, периодами, итогами и временными таблицами",
                    "senior": "проектирует модель хранения под чтение, запись, историю и конкурентную нагрузку",
                },
                "evidence": ["строит минимальный корректный запрос", "называет граничные случаи данных"],
            },
            {
                "id": "posting-and-consistency",
                "name": "Проведение, транзакции и блокировки",
                "levels": {
                    "junior": "понимает движения документа и атомарность изменения данных",
                    "middle": "объясняет оперативное/неоперативное проведение, контроль остатков и управляемые блокировки",
                    "senior": "разбирает взаимоблокировки, повторный запуск и согласованность нескольких регистров",
                },
                "evidence": ["видит границу транзакции", "различает бизнес-проверку и техническую блокировку"],
            },
            {
                "id": "performance",
                "name": "Производительность",
                "levels": {
                    "junior": "не выполняет запрос или обращение к базе в очевидном цикле без причины",
                    "middle": "ищет узкое место измерением, использует пакетные операции и подходящие индексы",
                    "senior": "связывает план запроса, блокировки, объём данных и архитектурный компромисс",
                },
                "evidence": ["сначала предлагает измерить", "оценивает объём и частоту операции"],
            },
            {
                "id": "integration",
                "name": "Интеграции и обмен",
                "levels": {
                    "junior": "читает JSON/XML, вызывает HTTP и обрабатывает явную ошибку",
                    "middle": "продумывает контракт, идемпотентность, повторы, таймаут и журналирование",
                    "senior": "выбирает синхронный/асинхронный маршрут и стратегию согласованности данных",
                },
                "evidence": ["описывает безопасный повтор", "не теряет диагностический контекст ошибки"],
            },
            {
                "id": "engineering-practice",
                "name": "Инженерная практика",
                "levels": {
                    "junior": "читает существующий код, делает малое изменение и проверяет результат",
                    "middle": "использует Git, автоматические тесты, логирование и декомпозицию",
                    "senior": "управляет техническим долгом, совместимостью и проверяемой поставкой изменений",
                },
                "evidence": ["называет способ проверить изменение", "разделяет симптом, причину и исправление"],
            },
        ],
    },
    "integration-engineer": {
        "label": "Инженер интеграций",
        "role": "Инженер интеграций",
        "description": "Контракты, повторяемость, очереди, согласованность и наблюдаемость",
        "interview_focus": (
            "Давай отказоустойчивые кейсы: таймаут после принятой операции, дубль, "
            "нарушение порядка и частичная недоступность. Требуй конкретную схему восстановления."
        ),
        "competencies": [
            {
                "id": "contracts",
                "name": "Контракты и совместимость",
                "levels": {
                    "junior": "понимает request/response, коды ошибок и обязательные поля",
                    "middle": "версионирует контракт и отличает совместимое изменение от ломающего",
                    "senior": "проектирует эволюцию нескольких потребителей и миграцию без единого окна",
                },
                "evidence": ["фиксирует семантику ошибки", "не связывает потребителей скрытыми полями"],
            },
            {
                "id": "delivery-semantics",
                "name": "Идемпотентность и доставка",
                "levels": {
                    "junior": "понимает, почему повтор запроса возможен после таймаута",
                    "middle": "использует idempotency key, дедупликацию и ограниченный retry с backoff",
                    "senior": "объясняет at-least-once, порядок, outbox/inbox и границы exactly-once",
                },
                "evidence": ["различает повтор отправки и повтор эффекта", "описывает ключ дедупликации"],
            },
            {
                "id": "consistency",
                "name": "Согласованность данных",
                "levels": {
                    "junior": "видит частичный успех двух последовательных операций",
                    "middle": "выбирает компенсацию, сверку и источник истины",
                    "senior": "проектирует сагу, reconciliation и допустимую eventual consistency",
                },
                "evidence": ["называет инвариант", "имеет путь восстановления после частичного сбоя"],
            },
            {
                "id": "async-processing",
                "name": "Очереди и асинхронная обработка",
                "levels": {
                    "junior": "понимает consumer, acknowledgement и dead-letter queue",
                    "middle": "управляет повтором, порядком, poison message и backpressure",
                    "senior": "выбирает партиционирование и гарантии под бизнес-инварианты",
                },
                "evidence": ["не подтверждает сообщение до эффекта", "описывает судьбу неисправимого сообщения"],
            },
            {
                "id": "security-observability",
                "name": "Безопасность и наблюдаемость",
                "levels": {
                    "junior": "не пишет секреты в лог и различает аутентификацию/авторизацию",
                    "middle": "использует correlation ID, метрики, трассировку и ротацию секретов",
                    "senior": "задаёт SLO, threat boundary и диагностику сквозной деградации",
                },
                "evidence": ["может найти один запрос между системами", "лог не раскрывает payload без основания"],
            },
        ],
    },
    "solution-architect": {
        "label": "Архитектор решений",
        "role": "Архитектор решений",
        "description": "Требования, границы, данные, надёжность, безопасность и эволюция",
        "interview_focus": (
            "Оценивай качество вопросов и решений при неполных требованиях. Хороший ответ "
            "обозначает допущения, альтернативы и проверяемый риск, а не рисует единственную схему."
        ),
        "competencies": [
            {
                "id": "requirements-tradeoffs",
                "name": "Требования и компромиссы",
                "levels": {
                    "junior": "уточняет пользователей, сценарий и ограничения",
                    "middle": "разделяет функциональные требования, качества и допущения",
                    "senior": "связывает решение с SLO, стоимостью, риском и обратимостью",
                },
                "evidence": ["задаёт уточняющие вопросы до схемы", "фиксирует критерий выбора"],
            },
            {
                "id": "boundaries",
                "name": "Границы компонентов",
                "levels": {
                    "junior": "разделяет интерфейс, бизнес-логику и хранение",
                    "middle": "выбирает границы по ответственности, данным и темпу изменений",
                    "senior": "управляет связностью, владением и организационными границами",
                },
                "evidence": ["объясняет владельца данных", "не дробит систему без причины"],
            },
            {
                "id": "data-consistency",
                "name": "Данные и согласованность",
                "levels": {
                    "junior": "задаёт сущности, связи и источник истины",
                    "middle": "выбирает транзакционные границы, кэш и модель чтения",
                    "senior": "обосновывает распределённую согласованность, миграцию и lineage",
                },
                "evidence": ["называет инварианты", "описывает восстановление и сверку"],
            },
            {
                "id": "reliability-scale",
                "name": "Надёжность и масштабирование",
                "levels": {
                    "junior": "видит single point of failure и необходимость backup",
                    "middle": "задаёт timeout, retry, circuit breaker, capacity и деградацию",
                    "senior": "проектирует multi-region/DR исходя из RTO/RPO и бюджета",
                },
                "evidence": ["описывает отказ компонента", "не обещает бесконечную масштабируемость"],
            },
            {
                "id": "security-evolution",
                "name": "Безопасность и эволюция",
                "levels": {
                    "junior": "учитывает доступ, секреты и персональные данные",
                    "middle": "задаёт trust boundaries, аудит, версионирование и rollout",
                    "senior": "планирует threat model, совместимую миграцию и архитектурные fitness-функции",
                },
                "evidence": ["предлагает поэтапную поставку", "имеет план отката и измерения"],
            },
        ],
    },
    "consulting": {
        "label": "ИТ-консалтинг",
        "role": "ИТ-консультант",
        "description": "Диагностика запроса, требования, стейкхолдеры, скоуп и внедрение",
        "interview_focus": (
            "Проверяй способность превратить расплывчатый запрос в проверяемую проблему и "
            "договорённость. Не считай уверенную презентацию заменой фактам и ограничениям."
        ),
        "competencies": [
            {
                "id": "discovery",
                "name": "Диагностика запроса",
                "levels": {
                    "junior": "задаёт открытые вопросы и фиксирует текущую боль",
                    "middle": "отделяет симптом, причину, ограничение и ожидаемый эффект",
                    "senior": "строит гипотезы, план проверки и экономику проблемы",
                },
                "evidence": ["переформулирует проблему и сверяет понимание", "не продаёт решение до диагностики"],
            },
            {
                "id": "requirements",
                "name": "Требования и критерии приёмки",
                "levels": {
                    "junior": "фиксирует сценарий, роль и ожидаемый результат",
                    "middle": "задаёт границы, исключения, приоритет и критерии приёмки",
                    "senior": "управляет конфликтом требований и трассировкой до бизнес-эффекта",
                },
                "evidence": ["формулирует проверяемый критерий", "отделяет must-have от гипотезы"],
            },
            {
                "id": "stakeholders",
                "name": "Стейкхолдеры и коммуникация",
                "levels": {
                    "junior": "понимает роли заказчика, пользователя и исполнителя",
                    "middle": "выявляет ЛПР, конфликт интересов и план коммуникаций",
                    "senior": "ведёт сложное решение через несогласие и организационные ограничения",
                },
                "evidence": ["проверяет, кто принимает решение", "фиксирует разногласие, а не маскирует его"],
            },
            {
                "id": "scope-risk",
                "name": "Скоуп, оценка и риски",
                "levels": {
                    "junior": "видит явные зависимости и неопределённость",
                    "middle": "декомпозирует этапы, допущения, риски и точки пересмотра",
                    "senior": "управляет портфелем рисков, коммерческими границами и change control",
                },
                "evidence": ["не выдаёт точную оценку без входных данных", "предлагает малый проверяемый этап"],
            },
            {
                "id": "adoption-value",
                "name": "Внедрение и ценность",
                "levels": {
                    "junior": "учитывает обучение и поддержку пользователя",
                    "middle": "задаёт план внедрения, владельца изменения и метрику эффекта",
                    "senior": "связывает продукт, процесс, данные и устойчивое изменение поведения",
                },
                "evidence": ["называет метрику до запуска", "планирует обратную связь после внедрения"],
            },
        ],
    },
}


def _validate_registry() -> None:
    if len(_PACKS) != len(set(_PACKS)):
        raise RuntimeError("duplicate competency pack id")
    for pack_id, pack in _PACKS.items():
        if not _ID.fullmatch(pack_id):
            raise RuntimeError(f"invalid competency pack id: {pack_id}")
        for field in ("label", "role", "description", "interview_focus"):
            if not isinstance(pack.get(field), str) or not pack[field].strip():
                raise RuntimeError(f"competency pack {pack_id} has no {field}")
        competencies = pack.get("competencies")
        if not isinstance(competencies, list) or not 4 <= len(competencies) <= 12:
            raise RuntimeError(f"competency pack {pack_id} has invalid competencies")
        ids = set()
        for competency in competencies:
            competency_id = str(competency.get("id") or "")
            if not _ID.fullmatch(competency_id) or competency_id in ids:
                raise RuntimeError(f"competency pack {pack_id} has invalid competency id")
            ids.add(competency_id)
            if set(competency.get("levels") or {}) != set(LEVELS):
                raise RuntimeError(f"competency pack {pack_id}/{competency_id} has invalid levels")
            if not all(str(item).strip() for item in competency["levels"].values()):
                raise RuntimeError(f"competency pack {pack_id}/{competency_id} has empty level")
            evidence = competency.get("evidence")
            if not isinstance(evidence, list) or not 1 <= len(evidence) <= 6:
                raise RuntimeError(f"competency pack {pack_id}/{competency_id} has invalid evidence")


_validate_registry()


def options() -> list[dict]:
    return [
        {
            "value": pack_id,
            "label": pack["label"],
            "role": pack["role"],
            "description": pack["description"],
            "version": PACK_VERSION,
        }
        for pack_id, pack in _PACKS.items()
    ]


def get(pack_id: object) -> dict | None:
    normalized = str(pack_id or "").strip()
    if not normalized:
        return None
    if normalized not in _PACKS:
        raise ValueError("неизвестный профиль компетенций")
    return {
        "schema": SCHEMA,
        "version": PACK_VERSION,
        "id": normalized,
        **copy.deepcopy(_PACKS[normalized]),
    }


def prompt_context(pack_id: object, difficulty: str) -> str:
    pack = get(pack_id)
    if pack is None:
        return ""
    selected_level = difficulty if difficulty in LEVELS else "mixed"
    lines = [
        f"Проверенный профиль компетенций: {pack['label']}",
        f"Версия профиля: {pack['version']}",
        f"Рекомендуемая роль: {pack['role']}",
        f"Фокус интервью: {pack['interview_focus']}",
        "Компетенции:",
    ]
    for item in pack["competencies"]:
        levels = item["levels"]
        if selected_level == "mixed":
            expectation = "; ".join(f"{level}: {levels[level]}" for level in LEVELS)
        else:
            expectation = levels[selected_level]
        lines.append(
            f"- {item['name']} [{item['id']}]: {expectation}. "
            f"Наблюдаемые признаки: {'; '.join(item['evidence'])}."
        )
    lines.append(
        "Используй профиль как рубрику покрытия, но не приписывай кандидату опыт "
        "и не превращай все вопросы в проверку терминов. Для вопроса из рубрики "
        "записывай в поле competency точное название компетенции из профиля — "
        "это сохраняет единую карту прогресса между попытками."
    )
    return "\n".join(lines)
