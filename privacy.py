"""Локальное обезличивание текстов перед передачей внешнему LLM.

Фильтр намеренно консервативен: он удаляет структурированные идентификаторы и
имена/организации из явно подписанных полей. Это дополнительный барьер, а не
юридическая гарантия полной анонимизации произвольной речи.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RedactionResult:
    text: str
    counts: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.counts.values())


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PHONE", re.compile(
        r"(?<!\d)(?:\+?7|8)[\s()\-]*\d{3}[\s()\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)")),
    ("SNILS", re.compile(r"(?<!\d)\d{3}-?\d{3}-?\d{3}[ -]?\d{2}(?!\d)")),
    ("PASSPORT", re.compile(
        r"(?i)(?:паспорт|серия(?:[ \t]{1,10}и[ \t]{1,10}номер)?)"
        r"[ \t]{0,10}[:№-]?[ \t]{0,10}\d{2}[ \t]{0,10}"
        r"\d{2}[ \t]{0,10}\d{6}")),
    ("INN", re.compile(
        r"(?i)(?:\bинн|tax[ _-]?id)\s*[:№-]?\s*\d(?:[ -]?\d){9,11}\b")),
    ("BIRTH_DATE", re.compile(
        r"(?i)(?:дата\s+рождения|родил(?:ся|ась)|date\s+of\s+birth|dob)"
        r"\s*[:—-]?\s*(?:[0-3]?\d[./-][01]?\d[./-](?:19|20)?\d{2}|"
        r"(?:19|20)\d{2}-[01]\d-[0-3]\d)")),
    ("BANK_CARD", re.compile(
        r"(?i)(?:карта|номер\s+карты|card(?:\s+number)?)\s*[:№-]?\s*"
        r"\d(?:[ -]?\d){12,18}\b")),
    ("URL", re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>]+")),
    ("HANDLE", re.compile(r"(?<![\w@])@[^\W\d_]\w{4,}(?!\w)")),
)


def _email_local_char(char: str) -> bool:
    return char.isalnum() or char in "_.+-"


def _email_domain_char(char: str) -> bool:
    return char.isalnum() or char in "_-"


def _redact_emails(text: str) -> tuple[str, int]:
    """Линейно скрыть email без регулярного выражения с backtracking."""
    output: list[str] = []
    copied_until = 0
    search_from = 0
    count = 0
    while (at := text.find("@", search_from)) >= 0:
        start = at
        while start > copied_until and _email_local_char(text[start - 1]):
            start -= 1
        end = at + 1
        while end < len(text) and (
                _email_domain_char(text[end]) or text[end] == "."):
            end += 1
        domain = text[at + 1:end].rstrip(".")
        end = at + 1 + len(domain)
        labels = domain.split(".")
        valid = (start < at and len(labels) >= 2
                 and all(label and all(_email_domain_char(char)
                                       for char in label)
                         for label in labels))
        if valid:
            count += 1
            output.extend((text[copied_until:start], f"[EMAIL_{count}]"))
            copied_until = end
            search_from = end
        else:
            search_from = at + 1
    output.append(text[copied_until:])
    return "".join(output), count

# Из этих полей сначала извлекаем значение, затем заменяем все его повторы в
# промпте. Так ФИО не останется в резюме после удаления только заголовка.
_LABELLED = re.compile(
    r"(?im)(?P<label>\b(?:фио|имя|кандидат|собеседник|работодатель|компания|организация|клиент|проект)"
    r"\s*[:—-]\s*)(?P<value>[^\n,;()]{2,120})"
)
_MEETING_NAME = re.compile(
    r"(?im)(?P<label>^Встреча:[^\n—]{0,80}—\s*)(?P<value>[^,\n()]{2,120})"
)
_ADDRESS = re.compile(
    r"(?im)(?P<label>\b(?:адрес|место жительства|регистрация)\s*[:—-]\s*)"
    r"(?P<value>[^\n]{4,180})"
)


def _replace_labelled(text: str, pattern: re.Pattern[str], kind: str,
                      aliases: dict[str, str], counts: dict[str, int]) -> str:
    values: list[str] = []

    def labelled(match: re.Match[str]) -> str:
        value = match.group("value").strip()
        if re.fullmatch(r"\[[A-Z_]+(?:_\d+)?\]", value):
            return match.group(0)
        if value not in aliases:
            aliases[value] = f"[{kind}_{len([x for x in aliases.values() if x.startswith('[' + kind)]) + 1}]"
        values.append(value)
        counts[kind] = counts.get(kind, 0) + 1
        return match.group("label") + aliases[value]

    text = pattern.sub(labelled, text)
    # Длинные значения заменяем первыми, не трогаем регистр.
    for value in sorted(set(values), key=len, reverse=True):
        alias = aliases[value]
        text, n = re.subn(re.escape(value), alias, text, flags=re.I)
        counts[kind] = counts.get(kind, 0) + n
    return text


def redact_text(text: str) -> RedactionResult:
    """Вернуть обезличенный текст и счётчики замен без сохранения исходных ПД."""
    if not isinstance(text, str):
        raise TypeError("redact_text ожидает строку")
    counts: dict[str, int] = {}
    aliases: dict[str, str] = {}
    result = _replace_labelled(text, _MEETING_NAME, "PERSON", aliases, counts)
    result = _replace_labelled(result, _LABELLED, "IDENTITY", aliases, counts)
    result = _replace_labelled(result, _ADDRESS, "ADDRESS", aliases, counts)
    result, email_count = _redact_emails(result)
    if email_count:
        counts["EMAIL"] = email_count

    for kind, pattern in _PATTERNS:
        number = 0

        def replace(_match: re.Match[str], label: str = kind) -> str:
            nonlocal number
            number += 1
            return f"[{label}_{number}]"

        result, count = pattern.subn(replace, result)
        if count:
            counts[kind] = counts.get(kind, 0) + count
    return RedactionResult(result, counts)


def for_cloud(text: str) -> str:
    """Применить выбранный режим: raw разрешается только явной настройкой."""
    import config as cfg
    settings = cfg.load()
    if (settings.get("text_privacy_mode", "redact") == "raw"
            and settings.get("raw_text_acknowledged") is True):
        return text
    return redact_text(text).text
