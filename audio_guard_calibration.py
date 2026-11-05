"""Локальная доказательная калибровка порогов Аудиосторожа."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import threading
from collections import Counter
from pathlib import Path

import config
import quality_benchmark
import transcript_events
from audio_watchdog import DEFAULT_THRESHOLDS, normalize_thresholds


SCHEMA_VERSION = 1
MIN_REVIEWED_SESSIONS = 10
MIN_TELEMETRY_SESSIONS = 3
_WATCH = re.compile(r"audio-watch(?:-[1-9]\d*)?\.jsonl", re.IGNORECASE)
_METRICS = (
    ("stt_queue", "Очередь STT", "ms", "stt_queue_ms", "sample"),
    ("stt_latency", "Задержка live STT", "ms", "stt_latency_ms", "mixed"),
    ("wav_backlog", "Отставание WAV", "ms", "wav_backlog_ms", "sample"),
    ("clipping", "Перегрузка сигнала", "ratio", "clipping_ratio", "sample"),
)
_PROFILE = {
    "stt_queue": ("stt_queue_warning_ms", "stt_queue_critical_ms", 500, 1_000),
    "stt_latency": ("stt_latency_warning_ms", "stt_latency_critical_ms", 500, 1_000),
    "wav_backlog": ("wav_backlog_warning_ms", "wav_backlog_critical_ms", 250, 500),
    "clipping": ("clipping_warning_ratio", "clipping_critical_ratio", 0.0005, 0.001),
}
_LOCK = threading.Lock()


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _parse_time(value: object) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1,
                max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def _rounded(value: float | None, unit: str) -> int | float | None:
    if value is None:
        return None
    return round(value, 6) if unit == "ratio" else int(round(value))


def _watch_records(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 32_000_000:
        return
    try:
        with path.open("r", encoding="utf-8", errors="replace") as source:
            for index, line in enumerate(source):
                if index >= 100_000 or len(line) > 1_000_000:
                    break
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    yield value
    except OSError:
        return


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def _live_latencies(journal: Path) -> list[float]:
    if journal.is_symlink() or not journal.is_file():
        return []
    try:
        records = transcript_events.read_records(journal)
    except (OSError, TypeError, ValueError):
        return []
    if not records:
        return []
    started = _parse_time(records[0].get("started_at"))
    if started is None:
        return []
    values = []
    for item in records[1:]:
        if (item.get("record_type") != "utterance"
                or item.get("status", "final") != "final"
                or str(item.get("timing_source") or "").startswith("offline")):
            continue
        received = _parse_time(item.get("received_at"))
        try:
            end_ms = int(item.get("end_ms", 0))
        except (TypeError, ValueError):
            continue
        if received is None:
            continue
        latency = round((received - started).total_seconds() * 1000) - end_ms
        if -1_000 <= latency <= 120_000:
            values.append(float(max(0, latency)))
    return values


def _round_up(value: float, step: float, unit: str) -> int | float:
    result = math.ceil(value / step) * step
    return round(result, 6) if unit == "ratio" else int(result)


def _recommend(metric: str, unit: str, values: list[float], sessions: int,
               current: dict, evidence_ready: bool) -> tuple[int | float, int | float]:
    warning_key, critical_key, warning_floor, critical_step = _PROFILE[metric]
    warning = current[warning_key]
    critical = current[critical_key]
    if not evidence_ready or sessions < MIN_TELEMETRY_SESSIONS or not values:
        return warning, critical
    p95 = _percentile(values, 0.95) or 0
    p99 = _percentile(values, 0.99) or 0
    # Калибровка может только постепенно повысить чувствительность. Плохой
    # архив не должен автоматически поднять пороги и спрятать проблему.
    candidate_warning = _round_up(max(warning_floor, p95 * 1.5),
                                  warning_floor, unit)
    proposed_warning = min(
        warning, max(DEFAULT_THRESHOLDS[warning_key] * 0.8, candidate_warning))
    candidate_critical = _round_up(
        max(proposed_warning + critical_step, p99 * 2), critical_step, unit)
    proposed_critical = min(
        critical, max(DEFAULT_THRESHOLDS[critical_key] * 0.8,
                      candidate_critical))
    if proposed_critical <= proposed_warning:
        proposed_critical = critical
    return (_rounded(float(proposed_warning), unit),
            _rounded(float(proposed_critical), unit))


def analyze(sessions_root: Path, thresholds: object = None) -> dict:
    """Build a local calibration report without changing the active profile."""
    root = Path(sessions_root).resolve(strict=True)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("архив встреч должен быть обычной локальной папкой")
    current = normalize_thresholds(
        config.load().get("audio_guard_thresholds") if thresholds is None
        else thresholds)
    benchmark = quality_benchmark.catalog(root)
    values = {name: [] for name, *_ in _METRICS}
    sessions = {name: set() for name, *_ in _METRICS}
    issue_counts: Counter[str] = Counter()
    issue_sessions: set[str] = set()
    sample_records = 0
    sample_sessions: set[str] = set()

    for session in sorted(root.iterdir(), key=lambda item: item.name):
        if not session.is_dir() or session.is_symlink():
            continue
        for watch in sorted(session.glob("audio-watch*.jsonl")):
            if not _WATCH.fullmatch(watch.name):
                continue
            for record in _watch_records(watch):
                kind = record.get("record_type")
                if kind == "audio_issue" and record.get("state") == "opened":
                    code = str(record.get("code") or "unknown")[:80]
                    issue_counts[code] += 1
                    issue_sessions.add(session.name)
                if kind != "audio_sample":
                    continue
                sample_records += 1
                sample_sessions.add(session.name)
                for metric, _label, _unit, field, _source in _METRICS:
                    if metric == "stt_latency":
                        result_age = _number(record.get("stt_result_age_ms"))
                        if result_age is None or result_age > 15_000:
                            continue
                    raw_values = ([record.get("me_clipping_ratio"),
                                   record.get("guest_clipping_ratio")]
                                  if metric == "clipping" else [record.get(field)])
                    accepted = [number for value in raw_values
                                if (number := _number(value)) is not None]
                    if accepted:
                        values[metric].extend(accepted)
                        sessions[metric].add(session.name)

    primary_items = benchmark.get("items") if isinstance(benchmark, dict) else []
    for item in primary_items if isinstance(primary_items, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("session") or "")
        journal_name = str(item.get("journal") or "")
        if not name or Path(name).name != name or not journal_name:
            continue
        session = root / name
        journal = session / journal_name
        if (session.is_symlink() or journal.is_symlink()
                or journal.resolve(strict=False).parent != session.resolve()):
            continue
        latency = _live_latencies(journal)
        if latency:
            values["stt_latency"].extend(latency)
            sessions["stt_latency"].add(name)

    reviewed_names = {
        str(item.get("session") or "")
        for item in primary_items if isinstance(item, dict)
        and item.get("state") == "reviewed" and item.get("session")
    }
    all_names = {
        str(item.get("session") or "")
        for item in primary_items if isinstance(item, dict) and item.get("session")
    }
    reviewed = len(reviewed_names)
    corpus_ready = reviewed >= MIN_REVIEWED_SESSIONS
    blockers = []
    blocker_details = []
    if not corpus_ready:
        blocker_details.append({"code": "more_reviewed", "count": MIN_REVIEWED_SESSIONS - reviewed})
        blockers.append(
            f"подтвердите ещё {MIN_REVIEWED_SESSIONS - reviewed} эталонных встреч")
    missing_metrics = [label for name, label, *_ in _METRICS
                       if len(sessions[name]) < MIN_TELEMETRY_SESSIONS]
    if missing_metrics:
        blocker_details.append({"code": "more_telemetry", "sessions": MIN_TELEMETRY_SESSIONS,
                                "metrics": [name for name, *_ in _METRICS
                                            if len(sessions[name]) < MIN_TELEMETRY_SESSIONS]})
        blockers.append(
            "нужны числовые срезы минимум из 3 встреч: " + ", ".join(missing_metrics))
    evidence_ready = corpus_ready and not missing_metrics
    proposal = dict(current)
    metrics = []
    for name, label, unit, _field, source in _METRICS:
        warning_key, critical_key, _floor, _step = _PROFILE[name]
        recommended = _recommend(name, unit, values[name], len(sessions[name]),
                                 current, evidence_ready)
        proposal[warning_key], proposal[critical_key] = recommended
        metrics.append({
            "id": name, "label": label, "unit": unit,
            "samples": len(values[name]), "sessions": len(sessions[name]),
            "p50": _rounded(_percentile(values[name], 0.5), unit),
            "p95": _rounded(_percentile(values[name], 0.95), unit),
            "max": _rounded(max(values[name]) if values[name] else None, unit),
            "current": {"warning": current[warning_key],
                        "critical": current[critical_key]},
            "recommended": {"warning": recommended[0],
                            "critical": recommended[1]},
            "source": source,
            "verdict": ("insufficient" if not evidence_ready else
                        "tighten" if recommended != (
                            current[warning_key], current[critical_key]) else "keep"),
        })
    proposal = normalize_thresholds(proposal)
    changed = proposal != current
    if evidence_ready and not changed:
        blocker_details.append({"code": "profile_supported"})
        blockers.append("текущий профиль уже подтверждён собранными данными")
    fingerprint_payload = {
        "current": current, "proposal": proposal, "reviewed": reviewed,
        "metrics": [{key: item[key] for key in (
            "id", "samples", "sessions", "p50", "p95", "max")}
                    for item in metrics],
    }
    fingerprint = hashlib.sha256(json.dumps(
        fingerprint_payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION, "generated_at": _now(),
        "status": "ready" if evidence_ready else "insufficient",
        "can_apply": bool(evidence_ready and changed),
        "fingerprint": fingerprint,
        "corpus": {
            "reviewed": reviewed, "required": MIN_REVIEWED_SESSIONS,
            "total": len(all_names),
            "reviewed_segments": max(0, int(benchmark.get("reviewed") or 0)),
        },
        "telemetry": {
            "sample_records": sample_records,
            "sample_sessions": len(sample_sessions),
            "issue_sessions": len(issue_sessions),
            "opened_issues": sum(issue_counts.values()),
            "issue_codes": dict(issue_counts.most_common(12)),
        },
        "metrics": metrics, "current": current, "proposal": proposal,
        "blockers": blockers, "blocker_details": blocker_details,
        "privacy_code": "numeric_only",
        "privacy": ("Только числа и коды событий; текст реплик, имена и названия "
                    "аудиоустройств не записываются."),
    }


def apply(sessions_root: Path, fingerprint: object, *, confirmed: bool) -> dict:
    """Apply the current evidence-bound proposal after explicit confirmation."""
    if confirmed is not True:
        raise ValueError("подтвердите применение рекомендованного профиля")
    with _LOCK:
        report = analyze(sessions_root)
        if str(fingerprint or "") != report["fingerprint"]:
            raise ValueError("данные калибровки изменились; пересчитайте рекомендации")
        if not report["can_apply"]:
            raise ValueError("профиль нельзя применить: " + "; ".join(report["blockers"]))
        config.save({"audio_guard_thresholds": report["proposal"]})
    updated = analyze(sessions_root)
    updated["applied"] = True
    return updated
