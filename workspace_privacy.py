"""Одноразовые разрешения на точный текст подготовки папки, только в памяти."""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from pathlib import Path

import privacy_inspector

TTL_SECONDS = 15 * 60
_LOCK = threading.Lock()
_REVIEWS: dict[str, dict] = {}


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def clear(sdir: Path | None = None) -> None:
    with _LOCK:
        if sdir is None:
            _REVIEWS.clear()
        else:
            _REVIEWS.pop(str(sdir.resolve()), None)


def load(sdir: Path, review_id: str, *, consume: bool = False) -> dict:
    key = str(sdir.resolve())
    with _LOCK:
        record = _REVIEWS.get(key)
        if record and time.monotonic() - record["created"] > TTL_SECONDS:
            _REVIEWS.pop(key, None)
            record = None
        if not record or not secrets.compare_digest(record["id"], str(review_id)):
            raise ValueError("проверка устарела или отменена; запустите проверку папки заново")
        if consume:
            _REVIEWS.pop(key, None)
        return dict(record)


def prepare(sdir: Path, *, source: dict, system: str, user: str, files: list[dict],
            excluded: list[str], custom: list[str], model: str,
            visuals: list[dict] | None = None, can_approve: bool = True) -> dict:
    import llm
    import workspace_visuals
    visuals = visuals or []
    images = workspace_visuals.selected_png(visuals)
    # Inspect together so identical names get identical replacements in both messages.
    separator = "\n===BLATERO_MESSAGE_SEPARATOR===\n"
    if separator in system or separator in user:
        raise ValueError("служебный разделитель в материалах; удалите его перед проверкой")
    original = system + separator + user
    inspection = privacy_inspector.inspect(original, custom, source.get("filenames", []))
    safe_system, safe_user = inspection["text"].split(separator)
    final_system, final_user, digest, destination = llm.preview_messages(model, safe_system, safe_user, images)
    record = {"id": secrets.token_urlsafe(24), "created": time.monotonic(),
              "source_hash": fingerprint(source), "system": safe_system, "user": safe_user,
              "digest": digest, "excluded": excluded, "custom": custom,
              "file_aliases": {item["replacement"]: item["value"] for item in inspection["findings"]
                               if item["kind"] == "FILE"},
              "model": model, "images": images,
              "visual_selection": [{"path": x["path"], "masks": x["masks"]} for x in visuals if x.get("selected")]}
    with _LOCK:
        # Keep a single preview per session and at most four sessions in RAM.
        key = str(sdir.resolve())
        now = time.monotonic()
        for expired in [k for k, v in _REVIEWS.items() if now - v["created"] > TTL_SECONDS]:
            _REVIEWS.pop(expired)
        if key not in _REVIEWS and len(_REVIEWS) >= 4:
            _REVIEWS.pop(min(_REVIEWS, key=lambda key: _REVIEWS[key]["created"]))
        _REVIEWS[key] = record
    return {"id": record["id"], "source": original, "system": final_system,
            "user": final_user, "findings": inspection["findings"],
            "counts": inspection["counts"], "detector": inspection["detector"],
            "files": files, "excluded": excluded, "custom": custom,
            "model": "определяется Codex CLI" if destination == "Codex" else model,
            "destination": destination,
            "visuals": visuals, "can_approve": can_approve,
            "vision_supported": source.get("settings", {}).get("llm_provider", "openrouter") in workspace_visuals.PROVIDERS,
            "message_code": "local_review_complete",
            "message": "Проверка выполнена локально. Автоматическое обнаружение может ошибаться. Просмотрите отправляемый текст."}


def authorize(sdir: Path, review_id: str, source: dict) -> dict:
    record = load(sdir, review_id, consume=True)
    if record["source_hash"] != fingerprint(source):
        raise ValueError("материалы, настройки или контекст изменились; проверьте новую версию перед отправкой")
    # Fail closed if the detector becomes unavailable between preview and send.
    checked = privacy_inspector.inspect(record["system"] + "\n" + record["user"], record["custom"])
    if checked["findings"]:
        raise ValueError("повторная проверка нашла подозрительные данные; сформируйте новый просмотр")
    return record
