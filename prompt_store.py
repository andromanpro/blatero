"""Локальные переопределения промптов, отделённые от исходного кода.

Файл ``prompt_overrides.json`` намеренно не хранится в Git. Перед сохранением
шаблоны проверяются: обязательные подстановки нельзя удалить или переименовать,
а неизвестные поля и повреждённые фигурные скобки отклоняются. Инструкции без
подстановок передаются буквально, включая фигурные скобки примеров JSON.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from string import Formatter

import app_paths

BASE = app_paths.DATA_ROOT
OVERRIDES_FILE = BASE / "prompt_overrides.json"
MAX_PROMPT_CHARS = 50_000
_LOCK = threading.RLock()
_INVALID_REPORTED = set()
_FORMATTED_KEYS = {"questions.generation", "questions.personal", "questions.fit",
                   "sparring.candidate.system", "emulation.system"}


def _definitions_by_key(definitions: list[dict]) -> dict[str, dict]:
    return {str(item["key"]): item for item in definitions}


def _read() -> dict[str, str]:
    try:
        raw = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): value for key, value in raw.items()
            if isinstance(key, str) and isinstance(value, str)}


def _write(values: dict[str, str]) -> None:
    OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OVERRIDES_FILE.with_name(OVERRIDES_FILE.name + ".tmp")
    tmp.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, OVERRIDES_FILE)


def resolve(key: str, default: str) -> str:
    """Вернуть локальную версию, если она существует, иначе заводскую."""
    with _LOCK:
        value = _read().get(key)
    if not isinstance(value, str) or not value.strip():
        return default
    # Infer the runtime contract from the canonical template, without importing
    # the UI catalog (which imports callers and is unsafe during module startup).
    formatted = "template" in key.split(".") or key in _FORMATTED_KEYS
    fields = _fields(default) if formatted else set()
    definition = {"placeholders": fields,
                  "required_literals": re.findall(r"\{\{\w+\}\}", default) if formatted else []}
    try:
        valid = validate(definition, value)
    except ValueError:
        if key not in _INVALID_REPORTED:
            logging.getLogger(__name__).warning("Invalid local prompt %s; factory version used", key)
            _INVALID_REPORTED.add(key)
        return default
    _INVALID_REPORTED.discard(key)
    return valid


def _fields(text: str) -> set[str]:
    fields = set()
    try:
        parsed = Formatter().parse(text)
        for _literal, field, _spec, _conversion in parsed:
            if field is None:
                continue
            if _spec or _conversion:
                raise ValueError("форматы и преобразования подстановок не поддерживаются")
            if not field or any(char in field for char in ".[]"):
                raise ValueError(f"недопустимая подстановка {{{field}}}")
            fields.add(field)
    except ValueError as exc:
        raise ValueError(f"повреждены фигурные скобки шаблона: {exc}") from exc
    return fields


def validate(definition: dict, text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("промпт должен быть текстом")
    text = text.strip()
    if not text:
        raise ValueError("промпт не может быть пустым")
    if len(text) > MAX_PROMPT_CHARS:
        raise ValueError(f"промпт длиннее {MAX_PROMPT_CHARS} символов")
    if "\x00" in text:
        raise ValueError("промпт содержит недопустимый нулевой символ")

    allowed = set(definition.get("placeholders", []))
    # Only format templates are interpolated by callers. A literal system
    # instruction can contain nested JSON examples; parsing them as fields would
    # reject valid instructions (or force double braces into the model's input).
    actual = _fields(text) if allowed else set()
    unknown = sorted(actual - allowed)
    missing = sorted(set(definition.get("required", allowed)) - actual)
    if unknown:
        raise ValueError("неизвестные подстановки: " + ", ".join(
            "{" + item + "}" for item in unknown))
    if missing:
        raise ValueError("нельзя удалить обязательные подстановки: " + ", ".join(
            "{" + item + "}" for item in missing))
    missing_literals = [item for item in definition.get("required_literals", [])
                        if item not in text]
    if missing_literals:
        raise ValueError("нельзя удалить служебные маркеры: " + ", ".join(
            missing_literals))
    return text


def save(key: str, text: str, definitions: list[dict]) -> dict:
    known = _definitions_by_key(definitions)
    if key not in known:
        raise ValueError("неизвестный системный промпт")
    value = validate(known[key], text)
    with _LOCK:
        values = _read()
        if value == known[key]["default"].strip():
            values.pop(key, None)
        else:
            values[key] = value
        _write(values)
    return public_item(known[key], values)


def reset(key: str, definitions: list[dict]) -> dict:
    known = _definitions_by_key(definitions)
    if key not in known:
        raise ValueError("неизвестный системный промпт")
    with _LOCK:
        values = _read()
        values.pop(key, None)
        _write(values)
    return public_item(known[key], values)


def public_item(definition: dict, values: dict[str, str] | None = None) -> dict:
    values = _read() if values is None else values
    key = str(definition["key"])
    default = str(definition["default"]).strip()
    customized = key in values and bool(values[key].strip())
    validation_error = ""
    if customized:
        try:
            validate(definition, values[key])
        except ValueError as exc:
            validation_error = str(exc)
    return {
        "key": key,
        "category": str(definition["category"]),
        "label": str(definition["label"]),
        "description": str(definition.get("description", "")),
        "default": default,
        "text": values[key].strip() if customized else default,
        "customized": customized,
        "validation_error": validation_error,
        "placeholders": list(definition.get("placeholders", [])),
        "required_literals": list(definition.get("required_literals", [])),
    }


def catalog(definitions: list[dict]) -> dict:
    with _LOCK:
        values = _read()
    return {
        "type": "prompt_catalog",
        "items": [public_item(item, values) for item in definitions],
        "storage": str(OVERRIDES_FILE),
        "protected": (
            "Защита недоверенных данных, обезличивание и технические правила "
            "провайдера не редактируются и добавляются программой отдельно."),
    }
