"""Локальная калибровка проверки выводов по человеческим решениям."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


SCHEMA_VERSION = 1
DECISION_JOURNAL_FILE = "report-conclusion-decisions.jsonl"
MAX_JOURNAL_BYTES = 2_000_000
MAX_RECORDS_PER_SESSION = 20_000
MIN_LABELS = 40
MIN_SESSIONS = 10
MIN_PER_CLASS = 10
MIN_AUTO_KEEP = 20
TARGET_UNSAFE_KEEP_RATE = 0.05
_DECISIONS = {"pending", "confirmed", "excluded"}
_PREDICTIONS = {"supported", "needs_review", "unsupported"}
_HASH = re.compile(r"[0-9a-f]{64}", re.IGNORECASE)


def session_contour(session: Path) -> str:
    try:
        meta = json.loads((session / "meta.json").read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            meta = {}
    except (OSError, TypeError, ValueError):
        meta = {}
    explicit = str(meta.get("contour") or "").strip().lower()
    if explicit in {"work", "test"}:
        return explicit
    marker = f"{session.name} {meta.get('name', '')}".casefold()
    if (session.name.casefold().startswith(("test_", "sparring_", "ui-audit"))
            or session.name.casefold() == "constest"
            or "тестовая встреча" in marker):
        return "test"
    return "work"


def _records(session: Path) -> tuple[list[dict], int, int]:
    path = session / DECISION_JOURNAL_FILE
    if not path.exists():
        return [], 0, 0
    if path.is_symlink() or not path.is_file():
        return [], 1, 0
    try:
        if path.stat().st_size > MAX_JOURNAL_BYTES:
            return [], 1, 0
        lines = path.read_bytes().splitlines()
    except OSError:
        return [], 1, 0
    result = []
    invalid = 0
    legacy = 0
    for raw in lines[:MAX_RECORDS_PER_SESSION]:
        try:
            item = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError):
            invalid += 1
            continue
        if (not isinstance(item, dict)
                or item.get("schema_version") != 1
                or item.get("record_type") != "conclusion_decision"
                or item.get("decision") not in _DECISIONS):
            invalid += 1
            continue
        prediction = str(item.get("prediction_status") or "")
        if prediction not in _PREDICTIONS:
            legacy += 1
            continue
        claim_hash = str(item.get("claim_sha256") or "")
        if not _HASH.fullmatch(claim_hash):
            invalid += 1
            continue
        result.append(item)
    if len(lines) > MAX_RECORDS_PER_SESSION:
        invalid += len(lines) - MAX_RECORDS_PER_SESSION
    return result, invalid, legacy


def _label_key(item: dict) -> tuple[str, int, str, str]:
    try:
        revision = int(item.get("draft_revision") or 0)
    except (TypeError, ValueError):
        revision = -1
    return (
        str(item.get("source_hash") or ""), revision,
        str(item.get("conclusion_id") or ""),
        str(item.get("claim_sha256") or "").lower(),
    )


def _labels(session: Path) -> tuple[list[dict], int, int]:
    records, invalid, legacy = _records(session)
    latest: dict[tuple[str, int, str, str], dict] = {}
    for item in records:
        latest[_label_key(item)] = item
    labels = [item for item in latest.values()
              if item.get("decision") in {"confirmed", "excluded"}]
    return labels, invalid, legacy


def _ratio(part: int, total: int) -> float | None:
    return round(part / total, 6) if total else None


def _wilson_upper(errors: int, total: int, z: float = 1.96) -> float | None:
    if total <= 0:
        return None
    observed = errors / total
    denominator = 1 + z * z / total
    center = observed + z * z / (2 * total)
    margin = z * math.sqrt(
        observed * (1 - observed) / total + z * z / (4 * total * total))
    return round(min(1.0, (center + margin) / denominator), 6)


def _fingerprint(samples: list[tuple]) -> str:
    raw = json.dumps(sorted(samples), ensure_ascii=False,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def catalog(sessions_root: Path, *, contour: str = "work") -> dict:
    """Собрать обезличенную матрицу ошибок по последним явным решениям."""
    root = Path(sessions_root).resolve(strict=True)
    checked_contour = str(contour or "work").strip().lower()
    if checked_contour not in {"work", "test"}:
        raise ValueError("неизвестный контур корпуса")
    labels = []
    samples = []
    labeled_sessions = 0
    scanned_sessions = 0
    invalid_records = 0
    legacy_records = 0
    for session in sorted(root.iterdir(), key=lambda item: item.name):
        if (not session.is_dir() or session.is_symlink()
                or session_contour(session) != checked_contour):
            continue
        scanned_sessions += 1
        session_labels, invalid, legacy = _labels(session)
        invalid_records += invalid
        legacy_records += legacy
        if session_labels:
            labeled_sessions += 1
        for item in session_labels:
            label = str(item["decision"])
            prediction = str(item["prediction_status"])
            codes = sorted({str(code)[:80] for code in item.get("check_codes", [])
                            if isinstance(code, str) and code})[:24]
            labels.append({"label": label, "prediction": prediction,
                           "codes": codes})
            samples.append((
                hashlib.sha256(session.name.encode("utf-8")).hexdigest(),
                *_label_key(item), label, prediction, tuple(codes)))

    confirmed = sum(item["label"] == "confirmed" for item in labels)
    excluded = sum(item["label"] == "excluded" for item in labels)
    supported = [item for item in labels if item["prediction"] == "supported"]
    unsupported = [item for item in labels if item["prediction"] == "unsupported"]
    review = [item for item in labels if item["prediction"] == "needs_review"]
    safe_keep = sum(item["label"] == "confirmed" for item in supported)
    unsafe_keep = sum(item["label"] == "excluded" for item in supported)
    correct_reject = sum(item["label"] == "excluded" for item in unsupported)
    false_reject = sum(item["label"] == "confirmed" for item in unsupported)
    review_confirmed = sum(item["label"] == "confirmed" for item in review)
    review_excluded = sum(item["label"] == "excluded" for item in review)

    signal_counts: dict[str, dict[str, int]] = {}
    for item in labels:
        for code in item["codes"]:
            bucket = signal_counts.setdefault(
                code, {"total": 0, "confirmed": 0, "excluded": 0})
            bucket["total"] += 1
            bucket[item["label"]] += 1
    signals = [
        {"code": code, **counts,
         "exclusion_rate": _ratio(counts["excluded"], counts["total"])}
        for code, counts in sorted(
            signal_counts.items(), key=lambda pair: (-pair[1]["total"], pair[0]))
    ][:12]

    blockers = []
    if len(labels) < MIN_LABELS:
        blockers.append(f"нужно не менее {MIN_LABELS} размеченных выводов")
    if labeled_sessions < MIN_SESSIONS:
        blockers.append(f"нужно не менее {MIN_SESSIONS} реальных встреч")
    if confirmed < MIN_PER_CLASS:
        blockers.append(f"нужно не менее {MIN_PER_CLASS} подтверждённых выводов")
    if excluded < MIN_PER_CLASS:
        blockers.append(f"нужно не менее {MIN_PER_CLASS} исключённых выводов")
    if len(supported) < MIN_AUTO_KEEP:
        blockers.append(
            f"нужно не менее {MIN_AUTO_KEEP} выводов со статусом «опора найдена»")
    corpus_ready = not blockers
    unsafe_upper = _wilson_upper(unsafe_keep, len(supported))
    passes_target = bool(
        corpus_ready and unsafe_upper is not None
        and unsafe_upper <= TARGET_UNSAFE_KEEP_RATE)
    if not corpus_ready:
        status = "collecting"
        recommendation = "collect_more_labels"
    elif passes_target:
        status = "passes"
        recommendation = "keep_current_gate"
    else:
        status = "fails"
        recommendation = "manual_review_all"
    return {
        "schema_version": SCHEMA_VERSION,
        "contour": checked_contour,
        "status": status,
        "corpus_ready": corpus_ready,
        "recommendation": recommendation,
        "fingerprint": _fingerprint(samples),
        "scanned_sessions": scanned_sessions,
        "labeled_sessions": labeled_sessions,
        "labels": len(labels),
        "confirmed": confirmed,
        "excluded": excluded,
        "legacy_records": legacy_records,
        "invalid_records": invalid_records,
        "requirements": {
            "labels": MIN_LABELS, "sessions": MIN_SESSIONS,
            "per_class": MIN_PER_CLASS, "auto_keep": MIN_AUTO_KEEP,
        },
        "metrics": {
            "automatic_keep": len(supported),
            "safe_keep": safe_keep,
            "unsafe_keep": unsafe_keep,
            "keep_precision": _ratio(safe_keep, len(supported)),
            "unsafe_keep_rate": _ratio(unsafe_keep, len(supported)),
            "unsafe_keep_wilson_upper_95": unsafe_upper,
            "automatic_reject": len(unsupported),
            "correct_reject": correct_reject,
            "false_reject": false_reject,
            "reject_precision": _ratio(correct_reject, len(unsupported)),
            "manual_review": len(review),
            "manual_review_rate": _ratio(len(review), len(labels)),
            "review_confirmed": review_confirmed,
            "review_excluded": review_excluded,
        },
        "target_unsafe_keep_rate": TARGET_UNSAFE_KEEP_RATE,
        "blockers": blockers,
        "signals": signals,
        "methodology": {
            "label": "explicit_local_human_decision",
            "prediction": "status_at_decision_time",
            "privacy": "claim text and participant identity are not aggregated",
            "limitation": (
                "Решение человека служит эталонной меткой, но не заменяет "
                "независимую экспертную перепроверку содержания."),
        },
    }
