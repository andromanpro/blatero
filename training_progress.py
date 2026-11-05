"""Локальная карта компетенций и адаптивный маршрут mock-интервью."""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path


SCHEMA_VERSION = 2
PROGRESS_FILE = "training-progress.json"
PORTABLE_PROFILE_FILE = "training-profiles.json"
DIFFICULTY_RANK = {"junior": 0, "middle": 1, "senior": 2}
INDEPENDENCE_BY_HINTS = {0: 10.0, 1: 7.0, 2: 4.0, 3: 1.0}


def _now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def _iso(value: dt.datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="seconds")


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def role_key(role: object) -> str:
    normalized = " ".join(str(role or "").casefold().split()) or "общая роль"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def competency_label(question: dict) -> str:
    return " ".join(str(
        question.get("competency") or question.get("category") or "общий"
    ).split()).strip()[:100] or "общий"


def competency_key(question: dict) -> str:
    label = competency_label(question).casefold()
    return re.sub(r"[^\w]+", "_", label, flags=re.UNICODE).strip("_")[:80] or "general"


def _empty_store() -> dict:
    return {"schema_version": SCHEMA_VERSION, "profiles": {}}


def store_path(session: Path) -> Path:
    """Общий профиль для стандартных sessions; локальный fallback для embedding."""
    target = Path(session).resolve()
    if target.parent.name.casefold() == "sessions":
        return target.parent.parent / PORTABLE_PROFILE_FILE
    return target / PROGRESS_FILE


def portable_store(session: Path) -> bool:
    return store_path(session) != Path(session).resolve() / PROGRESS_FILE


def _merge_legacy_profiles(profiles: list[dict]) -> dict:
    if not profiles:
        return {}
    result = copy.deepcopy(profiles[0])
    result.setdefault("attempts", [])
    result.setdefault("competencies", {})
    result.setdefault("totals", _empty_profile(result.get("role", ""))["totals"])
    for incoming in profiles[1:]:
        known_attempts = {str(item.get("id")) for item in result["attempts"]
                          if isinstance(item, dict) and item.get("id")}
        for attempt in incoming.get("attempts", []):
            if (isinstance(attempt, dict)
                    and str(attempt.get("id")) not in known_attempts):
                result["attempts"].append(copy.deepcopy(attempt))
                known_attempts.add(str(attempt.get("id")))
        for name in ("answers", "content_sum", "independence_sum",
                     "readiness_sum", "hints"):
            result["totals"][name] = round(
                float(result["totals"].get(name, 0))
                + float(incoming.get("totals", {}).get(name, 0)), 2)
        for key, item in incoming.get("competencies", {}).items():
            if not isinstance(item, dict):
                continue
            current = result["competencies"].get(key)
            if not isinstance(current, dict):
                result["competencies"][key] = copy.deepcopy(item)
                continue
            current_answers = max(0, int(current.get("answers", 0)))
            incoming_answers = max(0, int(item.get("answers", 0)))
            answers = current_answers + incoming_answers
            if answers:
                mastery = round((float(current.get("mastery", 0)) * current_answers
                                 + float(item.get("mastery", 0)) * incoming_answers)
                                / answers, 1)
            else:
                mastery = 0.0
            latest = max((current, item), key=lambda value: str(
                value.get("last_seen_at") or ""))
            history = [entry for entry in (
                list(current.get("history", [])) + list(item.get("history", [])))
                       if isinstance(entry, dict)]
            history.sort(key=lambda entry: str(entry.get("at") or ""))
            result["competencies"][key] = {
                **copy.deepcopy(latest), "answers": answers, "mastery": mastery,
                "recommended_difficulty": recommended_difficulty(mastery),
                "history": history[-12:],
            }
        result["attempts"] = sorted(
            result["attempts"], key=lambda item: str(item.get("completed_at") or "")
            if isinstance(item, dict) else "")[-30:]
        result["updated_at"] = max(
            str(result.get("updated_at") or ""),
            str(incoming.get("updated_at") or "")) or None
    return result


def _legacy_store(session: Path) -> dict:
    target = Path(session).resolve()
    if target.parent.name.casefold() != "sessions":
        return _empty_store()
    grouped: dict[str, list[dict]] = {}
    for path in sorted(target.parent.glob(f"*/{PROGRESS_FILE}")):
        if path.is_symlink() or not path.is_file():
            continue
        value = _read_json(path)
        profiles = value.get("profiles") if isinstance(value.get("profiles"), dict) else {}
        for key, profile in profiles.items():
            if isinstance(profile, dict):
                grouped.setdefault(str(key), []).append(profile)
    return {
        "schema_version": SCHEMA_VERSION,
        "profiles": {key: _merge_legacy_profiles(values)
                     for key, values in grouped.items()},
    }


def load_store(session: Path) -> dict:
    path = store_path(session)
    value = _read_json(path)
    if not value and portable_store(session):
        value = _legacy_store(session)
    profiles = value.get("profiles") if isinstance(value.get("profiles"), dict) else {}
    return {"schema_version": SCHEMA_VERSION, "profiles": profiles}


def _empty_profile(role: str) -> dict:
    return {
        "role": role, "updated_at": None, "attempts": [],
        "competencies": {},
        "totals": {
            "answers": 0, "content_sum": 0.0, "independence_sum": 0.0,
            "readiness_sum": 0.0, "hints": 0,
        },
    }


def load_profile(session: Path, role: str) -> dict:
    store = load_store(session)
    value = store["profiles"].get(role_key(role))
    if not isinstance(value, dict):
        return _empty_profile(role)
    result = copy.deepcopy(value)
    result["role"] = str(result.get("role") or role)
    result["attempts"] = (
        result.get("attempts") if isinstance(result.get("attempts"), list) else [])
    result["competencies"] = (
        result.get("competencies")
        if isinstance(result.get("competencies"), dict) else {})
    if not isinstance(result.get("totals"), dict):
        result["totals"] = _empty_profile(role)["totals"]
    return result


def evaluation_metrics(score: object, hints_used: object,
                       difficulty: object) -> dict:
    """Развести содержание ответа, самостоятельность и итоговую готовность."""
    try:
        content = min(10.0, max(0.0, float(score)))
    except (TypeError, ValueError):
        content = 0.0
    try:
        hints = min(3, max(0, int(hints_used)))
    except (TypeError, ValueError):
        hints = 0
    independence = INDEPENDENCE_BY_HINTS[hints]
    difficulty_name = str(difficulty or "middle")
    difficulty_bonus = {"junior": -0.5, "middle": 0.0, "senior": 0.5}.get(
        difficulty_name, 0.0)
    readiness = min(10.0, max(
        0.0, round(content * 0.7 + independence * 0.3 + difficulty_bonus, 1)))
    return {
        "content_score": round(content, 1),
        "independence_score": round(independence, 1),
        "readiness_score": readiness,
        "hints_used": hints,
    }


def recommended_difficulty(mastery: object) -> str:
    try:
        value = float(mastery)
    except (TypeError, ValueError):
        value = 50.0
    if value < 45:
        return "junior"
    if value < 75:
        return "middle"
    return "senior"


def _review_days(readiness: float, streak: int) -> int:
    if readiness < 4:
        return 1
    if readiness < 6:
        return 3
    if readiness < 8:
        return 7
    return 30 if streak >= 2 else 21


def _evaluation_question(evaluation: dict) -> dict:
    return {
        "competency": evaluation.get("competency"),
        "category": evaluation.get("category"),
    }


def _apply_evaluation(profile: dict, evaluation: dict, *, at: dt.datetime) -> None:
    question = _evaluation_question(evaluation)
    key = competency_key(question)
    label = competency_label(question)
    metrics = evaluation_metrics(
        evaluation.get("score"), evaluation.get("hints_used"),
        evaluation.get("difficulty"))
    competencies = profile.setdefault("competencies", {})
    previous = competencies.get(key) if isinstance(competencies.get(key), dict) else {}
    answers = max(0, int(previous.get("answers", 0))) + 1
    old_mastery = float(previous.get("mastery", metrics["readiness_score"] * 10))
    mastery = (metrics["readiness_score"] * 10 if answers == 1 else
               round(old_mastery * 0.65 + metrics["readiness_score"] * 10 * 0.35, 1))
    streak = int(previous.get("streak", 0)) + 1 \
        if metrics["readiness_score"] >= 7 else 0
    next_review = at + dt.timedelta(
        days=_review_days(metrics["readiness_score"], streak))
    history = previous.get("history") if isinstance(previous.get("history"), list) else []
    history = [*history, {
        "at": _iso(at), "question": str(evaluation.get("question") or "")[:1000],
        "difficulty": str(evaluation.get("difficulty") or "middle"),
        **metrics,
    }][-12:]
    competencies[key] = {
        "key": key, "label": label, "mastery": round(mastery, 1),
        "answers": answers, "last_seen_at": _iso(at),
        "next_review_at": _iso(next_review), "streak": streak,
        "last_score": metrics["content_score"],
        "last_independence": metrics["independence_score"],
        "last_readiness": metrics["readiness_score"],
        "recommended_difficulty": recommended_difficulty(mastery),
        "history": history,
    }
    totals = profile.setdefault("totals", _empty_profile(profile.get("role", ""))["totals"])
    totals["answers"] = int(totals.get("answers", 0)) + 1
    totals["content_sum"] = round(
        float(totals.get("content_sum", 0)) + metrics["content_score"], 2)
    totals["independence_sum"] = round(
        float(totals.get("independence_sum", 0)) + metrics["independence_score"], 2)
    totals["readiness_sum"] = round(
        float(totals.get("readiness_sum", 0)) + metrics["readiness_score"], 2)
    totals["hints"] = int(totals.get("hints", 0)) + metrics["hints_used"]


def projected_profile(session: Path, role: str,
                      current_evaluations: list[dict] | None = None) -> dict:
    profile = load_profile(session, role)
    at = _now()
    for evaluation in current_evaluations or []:
        if isinstance(evaluation, dict):
            _apply_evaluation(profile, evaluation, at=at)
    return profile


def _parse_time(value: object) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.astimezone()


def profile_payload(profile: dict) -> dict:
    now = _now()
    rows = []
    competencies = profile.get("competencies")
    for key, item in (competencies.items() if isinstance(competencies, dict) else []):
        if not isinstance(item, dict):
            continue
        mastery = round(min(100.0, max(0.0, float(item.get("mastery", 0)))), 1)
        next_review = _parse_time(item.get("next_review_at"))
        due = bool(next_review and next_review <= now)
        status = "due" if due else "weak" if mastery < 65 else "strong" if mastery >= 80 else "steady"
        rows.append({
            "key": str(item.get("key") or key),
            "label": str(item.get("label") or key)[:100],
            "mastery": mastery, "answers": int(item.get("answers", 0)),
            "last_score": item.get("last_score"),
            "last_independence": item.get("last_independence"),
            "last_readiness": item.get("last_readiness"),
            "next_review_at": str(item.get("next_review_at") or ""),
            "recommended_difficulty": str(
                item.get("recommended_difficulty")
                or recommended_difficulty(mastery)),
            "status": status, "due": due,
        })
    rows.sort(key=lambda item: (
        0 if item["due"] else 1, item["mastery"], item["label"].casefold()))
    totals = profile.get("totals") if isinstance(profile.get("totals"), dict) else {}
    answers = max(0, int(totals.get("answers", 0)))

    def average(name: str) -> float | None:
        return round(float(totals.get(name, 0)) / answers, 1) if answers else None

    overall = round(sum(item["mastery"] for item in rows) / len(rows), 1) if rows else None
    return {
        "attempts": len(profile.get("attempts", [])), "answers": answers,
        "mastery": overall, "content_average": average("content_sum"),
        "independence_average": average("independence_sum"),
        "readiness_average": average("readiness_sum"),
        "hints_total": int(totals.get("hints", 0)),
        "recommended_difficulty": recommended_difficulty(overall),
        "next_focus": rows[0]["label"] if rows else "",
        "competencies": rows[:12],
    }


def _question_priority(question: dict, profile: dict, last_key: str,
                       index: int) -> tuple:
    key = competency_key(question)
    item = profile.get("competencies", {}).get(key, {})
    mastery = float(item.get("mastery", 50.0)) if isinstance(item, dict) else 50.0
    next_review = _parse_time(item.get("next_review_at")) if isinstance(item, dict) else None
    due = bool(next_review and next_review <= _now())
    target = recommended_difficulty(mastery)
    difficulty = str(question.get("difficulty") or "middle")
    distance = abs(DIFFICULTY_RANK.get(difficulty, 1) - DIFFICULTY_RANK[target])
    repeated = key == last_key
    unseen = not bool(item)
    return (
        0 if due or mastery < 65 else 1,
        1 if repeated else 0,
        round(mastery, 1),
        0 if unseen else 1,
        distance, index,
    )


def select_question(plan: dict, state: dict, profile: dict) -> dict | None:
    questions = plan.get("questions") if isinstance(plan.get("questions"), list) else []
    evaluated = {
        str(item.get("question_id")) for item in state.get("evaluations", [])
        if isinstance(item, dict) and item.get("question_id")
    }
    candidates = [(index, item) for index, item in enumerate(questions)
                  if isinstance(item, dict) and str(item.get("id")) not in evaluated]
    if not candidates:
        return None
    if not plan.get("adaptive_enabled", True):
        return candidates[0][1]
    last = next((item for item in reversed(state.get("evaluations", []))
                 if isinstance(item, dict)), {})
    parent_id = str(last.get("question_id") or "")
    immediate = [pair for pair in candidates
                 if pair[1].get("generated_follow_up")
                 and str(pair[1].get("parent_question_id") or "") == parent_id]
    if immediate:
        return immediate[0][1]
    last_key = competency_key(_evaluation_question(last)) if last else ""
    return min(candidates, key=lambda pair: _question_priority(
        pair[1], profile, last_key, pair[0]))[1]


def selection_reason(question: dict | None, profile: dict) -> str:
    if not question:
        return ""
    key = competency_key(question)
    item = profile.get("competencies", {}).get(key, {})
    if not isinstance(item, dict) or not item:
        return "новая компетенция · проверяем базовый уровень"
    mastery = float(item.get("mastery", 0))
    next_review = _parse_time(item.get("next_review_at"))
    if next_review and next_review <= _now():
        return "интервальное повторение · тему пора освежить"
    if mastery < 65:
        return "слабая тема · закрепляем до уверенного ответа"
    if str(question.get("difficulty")) == "senior" and mastery >= 75:
        return "уровень растёт · усложняем задачу"
    return "поддерживаем навык · проверяем устойчивость"


def history_context(session: Path, role: str) -> str:
    profile = load_profile(session, role)
    public = profile_payload(profile)
    if not public["answers"]:
        return "Истории завершённых попыток ещё нет."
    weak = public["competencies"][:6]
    recent_questions = []
    for attempt in reversed(profile.get("attempts", [])):
        if not isinstance(attempt, dict):
            continue
        recent_questions.extend(
            str(item)[:500] for item in attempt.get("questions", []) if str(item).strip())
        if len(recent_questions) >= 12:
            break
    lines = [
        f"Завершённых попыток: {public['attempts']}",
        f"Общая готовность: {public['mastery']}",
        f"Рекомендуемая сложность: {public['recommended_difficulty']}",
        "Компетенции для приоритета:",
        *[f"- {item['label']}: освоение {item['mastery']}, "
          f"следующий уровень {item['recommended_difficulty']}"
          for item in weak],
    ]
    if recent_questions:
        lines.extend(["Недавние вопросы — не повторяй дословно:",
                      *[f"- {value}" for value in recent_questions[:12]]])
    return "\n".join(lines)[:12_000]


def record_attempt(session: Path, role: str, plan: dict, state: dict) -> dict:
    session = Path(session)
    store = load_store(session)
    key = role_key(role)
    profile = load_profile(session, role)
    attempt_id = str(state.get("attempt_id") or "")
    attempts = profile.get("attempts")
    if attempt_id and any(
            isinstance(item, dict) and item.get("id") == attempt_id for item in attempts):
        return profile_payload(profile)
    completed_at = _now()
    evaluations = [item for item in state.get("evaluations", []) if isinstance(item, dict)]
    for evaluation in evaluations:
        _apply_evaluation(profile, evaluation, at=completed_at)
    metrics = [evaluation_metrics(
        item.get("score"), item.get("hints_used"), item.get("difficulty"))
        for item in evaluations]

    def avg(name: str) -> float | None:
        return round(sum(item[name] for item in metrics) / len(metrics), 1) if metrics else None

    attempts.append({
        "id": attempt_id or hashlib.sha256(_iso(completed_at).encode()).hexdigest()[:16],
        "started_at": state.get("started_at"), "completed_at": _iso(completed_at),
        "questions_count": len(evaluations),
        "content_average": avg("content_score"),
        "independence_average": avg("independence_score"),
        "readiness_average": avg("readiness_score"),
        "questions": [str(item.get("question") or "")[:1000] for item in evaluations],
    })
    profile["attempts"] = attempts[-30:]
    profile["role"] = role
    profile["updated_at"] = _iso(completed_at)
    store["profiles"][key] = profile
    _atomic_json(store_path(session), store)
    return profile_payload(profile)


def reset_history(session: Path, role: str | None = None) -> None:
    session = Path(session)
    path = store_path(session)
    if not role:
        if portable_store(session):
            _atomic_json(path, _empty_store())
        else:
            path.unlink(missing_ok=True)
            path.with_name(path.name + ".tmp").unlink(missing_ok=True)
        return
    store = load_store(session)
    store["profiles"].pop(role_key(role), None)
    if store["profiles"]:
        _atomic_json(path, store)
    elif portable_store(session):
        _atomic_json(path, _empty_store())
    else:
        path.unlink(missing_ok=True)
