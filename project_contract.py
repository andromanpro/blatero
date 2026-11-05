"""Small, dependency-free validator for the versioned agent event contract."""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import uuid
from pathlib import Path

MAX_EVENT_BYTES = 64 * 1024
SCHEMA_FILE = Path(__file__).with_name("project-agent-event.schema.json")


class InvalidEvent(ValueError):
    pass


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def _kind(value: object, name: str) -> bool:
    return {"object": isinstance(value, dict), "array": isinstance(value, list),
            "string": isinstance(value, str), "null": value is None,
            "boolean": isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool)
            and (isinstance(value, int) or math.isfinite(value))}.get(name, False)


def _format(value: str, name: str) -> bool:
    try:
        if name == "uuid":
            return str(uuid.UUID(value)) == value.lower()
        if name == "date":
            return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                        and dt.date.fromisoformat(value))
        if name == "date-time":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}"
                                r"(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", value):
                return False
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00")
                                              .replace("z", "+00:00")).tzinfo is not None
    except (ValueError, OverflowError):
        return False
    raise InvalidEvent(f"неподдерживаемый формат схемы: {name}")


def _check(value: object, rule: dict, root: dict, location: str) -> list[str]:
    errors = []
    if "$ref" in rule:
        ref = rule["$ref"]
        if not ref.startswith("#/"):
            raise InvalidEvent("внешние ссылки схемы запрещены")
        resolved = root
        for part in ref[2:].split("/"):
            resolved = resolved[part.replace("~1", "/").replace("~0", "~")]
        errors.extend(_check(value, resolved, root, location))
    kinds = rule.get("type")
    if kinds and not any(_kind(value, name) for name in
                         (kinds if isinstance(kinds, list) else [kinds])):
        return [f"{location}: неверный тип"]
    if "const" in rule and canonical(value) != canonical(rule["const"]):
        errors.append(f"{location}: неверное постоянное значение")
    if "enum" in rule and canonical(value) not in [canonical(v) for v in rule["enum"]]:
        errors.append(f"{location}: недопустимое значение")
    if isinstance(value, dict):
        for key in rule.get("required", []):
            if key not in value:
                errors.append(f"{location}.{key}: обязательное поле")
        properties = rule.get("properties", {})
        if rule.get("additionalProperties") is False:
            errors.extend(f"{location}.{key}: неизвестное поле"
                          for key in value if key not in properties)
        if len(value) < rule.get("minProperties", 0):
            errors.append(f"{location}: пустое изменение")
        for key, child in properties.items():
            if key in value:
                errors.extend(_check(value[key], child, root, f"{location}.{key}"))
    if isinstance(value, list):
        if len(value) < rule.get("minItems", 0) or len(value) > rule.get("maxItems", math.inf):
            errors.append(f"{location}: неверное число элементов")
        for index, child in enumerate(value):
            if "items" in rule:
                errors.extend(_check(child, rule["items"], root, f"{location}[{index}]"))
    if isinstance(value, str):
        if len(value) < rule.get("minLength", 0) or len(value) > rule.get("maxLength", math.inf):
            errors.append(f"{location}: неверная длина")
        if "pattern" in rule and not re.search(rule["pattern"], value):
            errors.append(f"{location}: неверный формат")
        if "format" in rule and not _format(value, rule["format"]):
            errors.append(f"{location}: неверный {rule['format']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < rule.get("minimum", -math.inf):
            errors.append(f"{location}: слишком малое значение")
        if value > rule.get("maximum", math.inf):
            errors.append(f"{location}: слишком большое значение")
    for child in rule.get("allOf", []):
        errors.extend(_check(value, child, root, location))
    if "if" in rule:
        selected = "else" if _check(value, rule["if"], root, location) else "then"
        if selected in rule:
            errors.extend(_check(value, rule[selected], root, location))
    return errors


def validate(event: object) -> dict:
    try:
        encoded = canonical(event).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InvalidEvent("ожидается конечный JSON без NaN") from exc
    if len(encoded) > MAX_EVENT_BYTES:
        raise InvalidEvent("событие превышает 64 КБ")
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    errors = _check(event, schema, schema, "event")
    if errors:
        raise InvalidEvent("; ".join(errors[:8]))
    return event
