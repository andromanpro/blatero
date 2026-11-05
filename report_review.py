"""Локальный контроль качества между черновиком отчёта и финальным DOCX."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import re
import wave
from pathlib import Path

import copilot
import report
import report_calibration
import transcript_events


SCHEMA_VERSION = 3
REVIEW_FILE = "report-review.json"
DRAFT_FILE = "report.draft.md"
DRAFT_UNDO_FILE = "report.draft.undo.md"
EVIDENCE_EXPORT_FILE = "report.evidence.json"
EVIDENCE_SCHEMA_VERSION = 2
DECISION_JOURNAL_FILE = "report-conclusion-decisions.jsonl"
DECISION_SCHEMA_VERSION = 1
LOW_CONFIDENCE = 0.55
MAX_DRAFT_BYTES = 1_000_000
MAX_CONCLUSION_BYTES = 20_000
MAX_DECISION_REASON_BYTES = 2_000
_DECISIONS = {"pending", "confirmed", "excluded"}
_PRIMARY_JOURNAL = re.compile(r"transcript(?:-\d+)?\.jsonl", re.IGNORECASE)
_TURN = re.compile(
    r"(?m)^-\s+\d\d:\d\d:\d\d\s+\*\*\[(Я|Собеседник)(?:\s+·[^\]]+)?\]\*\*")
_TIME_ANCHOR = re.compile(r"\[\d\d:\d\d:\d\d\]")
_TIME_VALUE = re.compile(r"\[(\d\d:\d\d:\d\d)(?:\s*[-–—]\s*\d\d:\d\d:\d\d)?\]")
_HEADING = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")
_LIST_ITEM = re.compile(r"^(\s*(?:[-*+]\s+|\d+[.)]\s+))(.*)$")
_MARKDOWN_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_INLINE_MARKUP = re.compile(r"[`*_~]+")
_HTML_TAG = re.compile(r"<[^>]+>")
_WORD = re.compile(r"[\w-]{3,}", re.UNICODE)
_SEVERITY_RANK = {"notice": 1, "warning": 2, "critical": 3}
_EVIDENCE_SECTIONS = {"доказательства", "источники", "приложения"}
_CLAIM_STOP_WORDS = {
    "без", "был", "была", "были", "для", "его", "или", "как", "надо",
    "нет", "при", "так", "что", "это", "этот", "эта", "есть", "они",
    "the", "and", "with", "from", "that", "this",
}


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _atomic_text(path: Path, value: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _append_jsonl(path: Path, payload: dict) -> None:
    """Append one durable record; a torn final line is ignored by the reader."""
    if path.is_symlink():
        raise ValueError("журнал решений не должен быть символической ссылкой")
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
               + "\n").encode("utf-8")
    separator = b""
    if path.exists():
        try:
            with path.open("rb") as stream:
                stream.seek(0, os.SEEK_END)
                if stream.tell():
                    stream.seek(-1, os.SEEK_END)
                    if stream.read(1) not in {b"\n", b"\r"}:
                        separator = b"\n"
        except OSError as exc:
            raise ValueError("журнал решений не открывается для записи") from exc
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, separator + encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _issue(code: str, severity: str, title: str, detail: str, *,
           action: str = "", action_kind: str = "", evidence: dict | None = None,
           source: str = "local") -> dict:
    return {
        "code": code,
        "severity": severity if severity in _SEVERITY_RANK else "warning",
        "title": str(title)[:200],
        "detail": str(detail)[:1000],
        "action": str(action)[:300],
        "action_kind": str(action_kind)[:40],
        "evidence": evidence if isinstance(evidence, dict) else {},
        "source": source,
    }


def _primary_utterances(session: Path) -> list[dict]:
    result = []
    journals = sorted(
        (path for path in session.glob("transcript*.jsonl")
         if _PRIMARY_JOURNAL.fullmatch(path.name)),
        key=lambda path: transcript_events.segment_number(path.with_suffix(".md")))
    for journal in journals:
        try:
            records = transcript_events.read_records(journal)
        except (OSError, ValueError):
            continue
        for item in records:
            if (item.get("record_type") != "utterance"
                    or item.get("status", "final") != "final"
                    or not str(item.get("text") or "").strip()):
                continue
            result.append({**item, "_journal": journal.name})
    return result


def _transcript_stats(session: Path, transcript: str) -> dict:
    utterances = _primary_utterances(session)
    if utterances:
        roles = {"Я": 0, "Собеседник": 0}
        sources: dict[str, int] = {}
        low = []
        confidence_count = 0
        for item in utterances:
            role = str(item.get("speaker_role") or "")
            if role in roles:
                roles[role] += 1
            source = str(item.get("source") or "unknown")
            sources[source] = sources.get(source, 0) + 1
            confidence = transcript_events.event_confidence(item)
            if confidence is not None:
                confidence_count += 1
                if confidence < LOW_CONFIDENCE:
                    low.append({
                        "start_ms": max(0, int(item.get("start_ms", 0))),
                        "confidence": round(confidence, 3),
                        "speaker": str(item.get("speaker_name")
                                       or item.get("speaker_role") or "голос")[:80],
                    })
        return {
            "utterances": len(utterances), "roles": roles, "sources": sources,
            "confidence_count": confidence_count, "low_confidence": low,
            "characters": sum(len(str(item.get("text") or "")) for item in utterances),
        }
    roles = {"Я": 0, "Собеседник": 0}
    for match in _TURN.finditer(transcript):
        roles[match.group(1)] += 1
    return {
        "utterances": sum(roles.values()), "roles": roles, "sources": {},
        "confidence_count": 0, "low_confidence": [],
        "characters": len(transcript.strip()),
    }


def _speaker_issue(session: Path) -> dict | None:
    diarized = session / "transcript.local.diarized.jsonl"
    if not diarized.is_file():
        return None
    mapping_file = session / "speaker-map.json"
    try:
        mapping = json.loads(mapping_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        mapping = {}
    if mapping.get("reviewed") is True:
        return None
    speakers = mapping.get("speakers") if isinstance(mapping.get("speakers"), dict) else {}
    unnamed = sum(
        1 for key, value in speakers.items()
        if isinstance(value, dict)
        and str(value.get("merge_into") or key) == str(key)
        and not str(value.get("name") or "").strip())
    detail = (f"Не подписано голосовых кластеров: {unnamed}." if unnamed else
              "Диаризация есть, но имена и роли голосов ещё не подтверждены.")
    return _issue(
        "speakers_unreviewed", "warning", "Говорящие не подтверждены", detail,
        action="Откройте разметку, назовите голоса и сохраните уточнённый транскрипт.",
        action_kind="open_diarization")


def _audio_watch_issues(session: Path) -> list[dict]:
    active: dict[str, dict] = {}
    for journal in sorted(session.glob("audio-watch*.jsonl")):
        local_active: dict[str, dict] = {}
        try:
            lines = journal.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        for line in lines:
            try:
                item = json.loads(line)
            except (TypeError, ValueError):
                continue
            if item.get("record_type") == "audio_issue":
                code = str(item.get("code") or "")
                if item.get("state") == "resolved":
                    local_active.pop(code, None)
                elif code:
                    local_active[code] = item
            elif item.get("record_type") == "audio_watch_stop":
                codes = {str(code) for code in item.get("active_codes", [])}
                local_active = {code: value for code, value in local_active.items()
                                if code in codes}
        active.update(local_active)
    severe = [item for item in active.values()
              if item.get("severity") in {"warning", "critical"}]
    if not severe:
        return []
    titles = [str(item.get("title") or item.get("code") or "сбой") for item in severe]
    severity = "critical" if any(
        item.get("severity") == "critical" for item in severe) else "warning"
    return [_issue(
        "audio_incomplete", severity, "Во время записи остались аудиосбои",
        "; ".join(titles[:6]),
        action=("Сверьте эти места с WAV и временной шкалой. При пропусках "
                "перезапустите запись через Replay Lab."),
        action_kind="open_evidence",
        evidence={"codes": [str(item.get("code") or "") for item in severe[:12]]})]


def inspect_inputs(session: Path) -> dict:
    """Дешёвая локальная проверка до платного обращения к LLM."""
    session = Path(session).resolve()
    transcript = copilot.all_transcripts(session)
    meeting_type = copilot.session_type(session)
    stats = _transcript_stats(session, transcript)
    issues = []
    total = stats["utterances"]
    if not transcript.strip() or total == 0:
        issues.append(_issue(
            "transcript_empty", "critical", "Транскрипт пуст",
            "В отчёте нечего проверять: распознанных реплик нет.",
            action="Импортируйте транскрипт или запишите встречу, затем повторите.",
            action_kind="open_evidence"))
    elif total <= 2 or stats["characters"] < 80:
        issues.append(_issue(
            "transcript_tiny", "critical", "Слишком мало распознанной речи",
            f"Найдено реплик: {total}. Итоговые оценки будут ненадёжны.",
            action="Сверьте запись и при необходимости восстановите текст через Replay Lab.",
            action_kind="open_evidence"))

    roles = stats["roles"]
    if total >= 6 and min(roles.values()) == 0:
        missing = "собеседников" if roles["Собеседник"] == 0 else "ваш голос"
        issues.append(_issue(
            "single_channel", "critical", "В транскрипте только одна сторона",
            f"Не найден {missing}; роли и выводы о диалоге нельзя считать подтверждёнными.",
            action="Сверьте системный звук, микрофон и временную шкалу.",
            action_kind="open_evidence", evidence={"roles": roles}))

    low = stats["low_confidence"]
    confidence_count = stats["confidence_count"]
    low_limit = max(2, math.ceil(confidence_count * 0.15))
    if low and (len(low) >= low_limit
                or min(item["confidence"] for item in low) < 0.30):
        percent = round(len(low) / confidence_count * 100) if confidence_count else 0
        issues.append(_issue(
            "low_stt_confidence", "warning", "Есть сомнительно распознанные реплики",
            f"Ниже уверенности {LOW_CONFIDENCE:.0%}: {len(low)} из "
            f"{confidence_count} ({percent}%).",
            action="Прослушайте отмеченные места перед подтверждением выводов.",
            action_kind="open_evidence", evidence={"samples": low[:8]}))

    warning = report.attribution_warning(transcript, meeting_type, session)
    if warning and not any(item["code"] == "single_channel" for item in issues):
        issues.append(_issue(
            "speaker_attribution", "warning", "Атрибуция реплик сомнительна",
            re.sub(r"^Техническое предупреждение:\s*", "", warning),
            action="Сверьте голоса и вероятные межканальные дубли.",
            action_kind="open_evidence"))

    speaker_issue = _speaker_issue(session)
    if speaker_issue:
        issues.append(speaker_issue)
    issues.extend(_recognition_integrity_issues(session))
    issues.extend(_audio_watch_issues(session))
    return {
        "stats": stats,
        "issues": issues,
        "can_generate": not any(item["code"] == "transcript_empty" for item in issues),
    }


def _recognition_integrity_issues(session: Path) -> list[dict]:
    """Flag likely ASR prompt leakage and audio-only segments, never rewrite data."""
    utterances = _primary_utterances(session)
    leaked = [row for row in utterances if row.get("provider") == "local_whisper"
              and "встреча на русском языке" in str(row.get("text", "")).casefold()]
    issues=[]
    if len(leaked) >= 3:
        issues.append(_issue("asr_prompt_leak", "warning", "В тексте повторяется служебная фраза распознавания",
            f"В {len(leaked)} репликах обнаружена фраза языковой подсказки Whisper. Это может быть ошибкой распознавания.",
            action="Сверьте отмеченные места с WAV и исправьте текст перед подтверждением отчёта.",
            action_kind="open_evidence", evidence={"samples":[{"start_ms":row.get("start_ms",0),
                "journal":row.get("_journal", "")} for row in leaked[:8]]}))
    populated={row.get("_journal") for row in utterances}
    empty=[]
    for journal in session.glob("transcript*.jsonl"):
        if not _PRIMARY_JOURNAL.fullmatch(journal.name) or journal.name in populated or journal.is_symlink():
            continue
        try:
            rows=transcript_events.read_records(journal)
            if not rows:
                continue
            audio_files=rows[0].get("audio_files") or {}
            durations=[]
            for name in audio_files.values():
                audio=session / str(name)
                if audio.parent != session or audio.is_symlink() or not audio.is_file():
                    continue
                with wave.open(str(audio),"rb") as wav:
                    durations.append(wav.getnframes()/max(1,wav.getframerate()))
            if max(durations,default=0) >= 10:
                empty.append({"journal":journal.name,"audio_seconds":round(max(durations),1)})
        except (OSError,ValueError,TypeError,AttributeError,wave.Error,EOFError):
            continue
    if empty:
        issues.append(_issue("audio_without_transcript", "warning", "Есть аудиосегменты без распознанных реплик",
            f"Сегментов с WAV длиннее 10 секунд, но без финального текста: {len(empty)}. Это может быть тишина или сбой STT.",
            action="Прослушайте эти сегменты; при наличии речи выполните повторное распознавание, сохранив исходники.",
            action_kind="open_evidence",evidence={"segments":empty[:8]}))
    return issues


def _model_issues(audit: object) -> list[dict]:
    if not isinstance(audit, dict):
        return []
    result = []
    unsupported = audit.get("unsupported_claims")
    if isinstance(unsupported, list):
        for index, item in enumerate(unsupported[:8], 1):
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if claim or reason:
                result.append(_issue(
                    f"unsupported_claim_{index}", "warning",
                    "Вывод без достаточного подтверждения",
                    claim or reason, action=reason or "Сверьте вывод с транскриптом.",
                    action_kind="open_evidence", source="model_self_audit"))
    contradictions = audit.get("contradictions")
    if isinstance(contradictions, list):
        for index, item in enumerate(contradictions[:8], 1):
            if not isinstance(item, dict):
                continue
            left = str(item.get("left") or "").strip()
            right = str(item.get("right") or "").strip()
            reason = str(item.get("reason") or "").strip()
            detail = " ↔ ".join(value for value in (left, right) if value)
            if reason:
                detail = f"{detail}. {reason}" if detail else reason
            if detail:
                result.append(_issue(
                    f"contradiction_{index}", "warning",
                    "В выводах есть противоречие", detail,
                    action="Сверьте обе реплики и выберите подтверждённую трактовку.",
                    action_kind="open_evidence", source="model_self_audit"))
    return result


def _plain_markdown(value: str) -> str:
    text = _MARKDOWN_LINK.sub(r"\1", value)
    text = _HTML_TAG.sub(" ", text)
    text = _INLINE_MARKUP.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _section_is_evidence(section: str) -> bool:
    normalized = _plain_markdown(section).casefold().strip(" .:—-")
    return any(normalized.startswith(value) for value in _EVIDENCE_SECTIONS)


def _report_blocks(markdown: str) -> list[dict]:
    """Выделить редактируемые смысловые блоки, сохранив точные смещения."""
    lines = markdown.splitlines(keepends=True)
    result: list[dict] = []
    section = "Итог"
    ordinals: dict[str, int] = {}
    paragraph: list[tuple[int, int, str]] = []
    list_item: dict | None = None
    offset = 0
    fenced = False

    def append_block(start: int, end: int, raw: str, prefix: str = "", *,
                     remove_start: int | None = None,
                     remove_end: int | None = None) -> None:
        plain = _plain_markdown(raw)
        if len(plain) < 20 or _section_is_evidence(section):
            return
        key = _plain_markdown(section).casefold() or "итог"
        ordinals[key] = ordinals.get(key, 0) + 1
        stable = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
        result.append({
            "id": f"claim-{stable}-{ordinals[key]}",
            "section": _plain_markdown(section) or "Итог",
            "text": plain,
            "text_markdown": raw.strip(),
            "_start": start,
            "_end": end,
            "_prefix": prefix,
            "_remove_start": start if remove_start is None else remove_start,
            "_remove_end": end if remove_end is None else remove_end,
        })

    def flush_paragraph() -> None:
        if not paragraph:
            return
        start = paragraph[0][0]
        end = paragraph[-1][1]
        raw = markdown[start:end].rstrip("\r\n")
        append_block(start, start + len(raw), raw,
                     remove_start=start, remove_end=end)
        paragraph.clear()

    def flush_list_item() -> None:
        nonlocal list_item
        if list_item is None:
            return
        raw = markdown[list_item["body_start"]:list_item["end"]].rstrip("\r\n")
        append_block(
            list_item["body_start"], list_item["body_start"] + len(raw), raw,
            list_item["prefix"], remove_start=list_item["start"],
            remove_end=list_item["end"])
        list_item = None

    for line in lines:
        start = offset
        offset += len(line)
        content = line.rstrip("\r\n")
        stripped = content.strip()
        structural = (
            not stripped or stripped.startswith("```")
            or _HEADING.match(content) is not None
            or _LIST_ITEM.match(content) is not None
            or stripped.startswith("|") or stripped.startswith("<!--"))
        if list_item is not None:
            if not structural and not fenced:
                list_item["end"] = offset
                continue
            flush_list_item()
        if stripped.startswith("```"):
            flush_paragraph()
            fenced = not fenced
            continue
        if fenced:
            continue
        heading = _HEADING.match(content)
        if heading:
            flush_paragraph()
            if len(heading.group(1)) >= 2:
                section = heading.group(2)
            continue
        if not stripped:
            flush_paragraph()
            continue
        if stripped.startswith("|") or stripped.startswith("<!--"):
            flush_paragraph()
            continue
        listed = _LIST_ITEM.match(content)
        if listed:
            flush_paragraph()
            body_start = start + listed.start(2)
            list_item = {
                "start": start, "body_start": body_start,
                "end": offset, "prefix": listed.group(1),
            }
            continue
        paragraph.append((start, offset, content))
    flush_list_item()
    flush_paragraph()
    return result


def _claim_words(value: str) -> set[str]:
    return {word.casefold() for word in _WORD.findall(_plain_markdown(value))
            if word.casefold() not in _CLAIM_STOP_WORDS}


def _claims_overlap(left: str, right: str) -> bool:
    a, b = _claim_words(left), _claim_words(right)
    if not a or not b:
        return False
    return len(a & b) / max(1, min(len(a), len(b))) >= 0.45


def _audit_flags(audit: dict, text: str) -> list[dict]:
    flags = []
    unsupported = audit.get("unsupported_claims")
    if isinstance(unsupported, list):
        for item in unsupported:
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim") or "")
            if claim and _claims_overlap(claim, text):
                flags.append({
                    "code": "model_unsupported",
                    "detail": str(item.get("reason") or
                                  "Самоаудит модели не нашёл достаточной опоры."),
                })
                break
    contradictions = audit.get("contradictions")
    if isinstance(contradictions, list):
        for item in contradictions:
            if not isinstance(item, dict):
                continue
            if any(_claims_overlap(str(item.get(key) or ""), text)
                   for key in ("left", "right")):
                flags.append({
                    "code": "model_contradiction",
                    "detail": str(item.get("reason") or
                                  "Самоаудит модели отметил противоречие."),
                })
                break
    return flags


def _clock(item: dict) -> str:
    try:
        return dt.datetime.fromisoformat(str(item["captured_at"])).strftime("%H:%M:%S")
    except (KeyError, TypeError, ValueError):
        start = max(0, int(item.get("start_ms", 0))) // 1000
        return f"{start // 3600:02d}:{start // 60 % 60:02d}:{start % 60:02d}"


def _safe_audio_url(session: Path, item: dict) -> str:
    name = str(item.get("audio_file") or "")
    if not name or Path(name).name != name:
        return ""
    path = session / name
    try:
        if path.is_symlink() or not path.is_file() or path.resolve().parent != session:
            return ""
    except OSError:
        return ""
    return f"/files/{session.name}/{name}"


def _transcript_evidence(session: Path) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for item in _primary_utterances(session):
        clock = _clock(item)
        confidence = transcript_events.event_confidence(item)
        sequence = int(item.get("sequence", 0))
        segment = int(item.get("segment", 1))
        evidence_item = {
            "event_id": str(item.get("event_id") or f"{segment}:{sequence}"),
            "journal": str(item.get("_journal") or ""),
            "clock": clock,
            "start_ms": max(0, int(item.get("start_ms", 0))),
            "end_ms": max(0, int(item.get("end_ms", 0))),
            "speaker_role": str(item.get("speaker_role") or ""),
            "speaker_name": str(item.get("speaker_name") or ""),
            "text": str(item.get("text") or ""),
            "source": str(item.get("source") or "unknown"),
            "confidence": (round(float(confidence), 4)
                           if isinstance(confidence, (int, float)) else None),
            "timeline_url": (
                f"/files/{session.name}/evidence.html#"
                f"t-{clock.replace(':', '')}-{segment}-{sequence}"),
            "audio_url": _safe_audio_url(session, item),
        }
        result.setdefault(clock, []).append(evidence_item)
    return result


def _workspace_sources(session: Path, text: str) -> list[str]:
    status_path = session / "workspace-status.json"
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return []
    files = status.get("files") if isinstance(status, dict) else []
    paths = [str(item.get("path") or "") for item in files
             if isinstance(item, dict) and str(item.get("path") or "")]
    basename_counts: dict[str, int] = {}
    for value in paths:
        name = Path(value).name.casefold()
        basename_counts[name] = basename_counts.get(name, 0) + 1
    normalized = text.casefold().replace("\\", "/")
    matched = []
    for value in sorted(paths, key=len, reverse=True):
        relative = value.replace("\\", "/")
        basename = Path(relative).name.casefold()
        if (relative.casefold() in normalized
                or (basename_counts.get(basename) == 1
                    and re.search(rf"(?<![\w.-]){re.escape(basename)}(?![\w.-])",
                                  normalized))):
            matched.append(relative)
    return matched[:12]


def _load_audit(session: Path) -> dict:
    try:
        value = json.loads((session / report.REPORT_DRAFT_META_FILE).read_text(
            encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return {}
    audit = value.get("audit") if isinstance(value, dict) else {}
    return audit if isinstance(audit, dict) else {}


def _claim_sha256(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def _decision_records(session: Path) -> list[dict]:
    """Read the append-only journal, tolerating only a torn/corrupt record."""
    path = Path(session).resolve() / DECISION_JOURNAL_FILE
    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file():
        raise ValueError("журнал решений имеет небезопасный тип")
    try:
        lines = path.read_bytes().splitlines()
    except OSError as exc:
        raise ValueError("журнал решений не читается") from exc
    result = []
    for line in lines:
        try:
            item = json.loads(line.decode("utf-8"))
            revision = int(item.get("revision"))
        except (AttributeError, TypeError, ValueError):
            continue
        if (not isinstance(item, dict)
                or item.get("schema_version") != DECISION_SCHEMA_VERSION
                or item.get("record_type") != "conclusion_decision"
                or item.get("decision") not in _DECISIONS
                or revision < 1):
            continue
        result.append({**item, "revision": revision})
    return result


def _apply_decisions(session: Path, manifest: dict,
                     conclusions: list[dict]) -> tuple[list[dict], int]:
    records = _decision_records(session)
    decision_revision = max(
        [int(manifest.get("decision_revision") or 0),
         *(int(item["revision"]) for item in records)], default=0)
    source_hash = str(manifest.get("source_hash") or "")
    draft_revision = int(manifest.get("draft_revision") or 0)
    current = {(str(item.get("id") or ""),
                _claim_sha256(str(item.get("text_markdown") or ""))): item
               for item in conclusions}
    selected: dict[tuple[str, str], dict] = {}
    for record in records:
        key = (str(record.get("conclusion_id") or ""),
               str(record.get("claim_sha256") or ""))
        if (record.get("source_hash") != source_hash
                or int(record.get("draft_revision", -1)) != draft_revision
                or key not in current):
            continue
        selected[key] = record
    for item in conclusions:
        key = (str(item.get("id") or ""),
               _claim_sha256(str(item.get("text_markdown") or "")))
        record = selected.get(key, {})
        decision = str(record.get("decision") or "pending")
        item.update({
            "decision": decision if decision in _DECISIONS else "pending",
            "decision_reason": str(record.get("reason") or ""),
            "decided_at": str(record.get("timestamp") or ""),
            "decision_revision": int(record.get("revision") or 0),
            "decision_required": item.get("status") != "supported",
        })
    return conclusions, decision_revision


def build_conclusions(session: Path, markdown: str, *, audit: dict | None = None,
                      revision: int = 0) -> list[dict]:
    """Локально проверить наличие опор; это не семантическая проверка истины."""
    session = Path(session).resolve()
    evidence_by_clock = _transcript_evidence(session)
    checked_audit = audit if isinstance(audit, dict) else _load_audit(session)
    conclusions = []
    for block in _report_blocks(markdown):
        clocks = list(dict.fromkeys(_TIME_VALUE.findall(block["text_markdown"])))
        anchors = [item for clock in clocks for item in evidence_by_clock.get(clock, [])]
        missing = [clock for clock in clocks if clock not in evidence_by_clock]
        flags = _audit_flags(checked_audit, block["text"])
        if not clocks:
            flags.append({
                "code": "no_evidence_reference",
                "detail": "В выводе нет ссылки на подтверждающую реплику.",
            })
        if missing:
            flags.append({
                "code": "evidence_not_found",
                "detail": "Не найдены реплики для времени: " + ", ".join(missing),
            })
        low = [item for item in anchors
               if isinstance(item.get("confidence"), (int, float))
               and item["confidence"] < LOW_CONFIDENCE]
        if low:
            flags.append({
                "code": "low_confidence_evidence",
                "detail": "Опора содержит реплику с низкой уверенностью STT.",
            })
        codes = {item["code"] for item in flags}
        if "model_unsupported" in codes or "evidence_not_found" in codes:
            status = "unsupported"
        elif flags:
            status = "needs_review"
        else:
            status = "supported"
        conclusions.append({
            **block,
            "revision": int(revision),
            "status": status,
            "checks": flags,
            "evidence": anchors,
            "workspace_sources": _workspace_sources(session, block["text"]),
        })
    return conclusions


def _public_conclusion(item: dict) -> dict:
    return {key: value for key, value in item.items() if not key.startswith("_")}


def _conclusion_summary(conclusions: list[dict]) -> dict:
    counts = {"supported": 0, "needs_review": 0, "unsupported": 0}
    decisions = {"pending": 0, "confirmed": 0, "excluded": 0}
    unresolved = 0
    for item in conclusions:
        status = str(item.get("status") or "needs_review")
        counts[status if status in counts else "needs_review"] += 1
        decision = str(item.get("decision") or "pending")
        decisions[decision if decision in decisions else "pending"] += 1
        if item.get("decision_required") and decision == "pending":
            unresolved += 1
    return {"total": len(conclusions), **counts, **decisions,
            "unresolved": unresolved}


def refresh_evidence_export(session: Path, *, manifest: dict | None = None,
                            markdown: str | None = None) -> dict:
    """Атомарно сохранить переносимый JSON без абсолютных локальных путей."""
    session = Path(session).resolve()
    current = manifest if isinstance(manifest, dict) else load(session)
    if markdown is None:
        draft_path = session / DRAFT_FILE
        if draft_path.is_symlink() or not draft_path.is_file():
            raise ValueError("черновик отчёта не найден или небезопасен")
        markdown = draft_path.read_text(encoding="utf-8")
    revision = int(current.get("draft_revision") or 0)
    conclusions = build_conclusions(session, markdown, revision=revision)
    conclusions, decision_revision = _apply_decisions(
        session, current, conclusions)
    draft_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    previous_path = session / EVIDENCE_EXPORT_FILE
    try:
        previous = (json.loads(previous_path.read_text(encoding="utf-8"))
                    if not previous_path.is_symlink() else {})
    except (OSError, ValueError):
        previous = {}
    same_draft = (isinstance(previous, dict)
                  and previous.get("draft_sha256") == draft_hash
                  and previous.get("draft_revision") == revision
                  and previous.get("source_hash") == current.get("source_hash"))
    old = {item["id"]: item for item in previous.get("conclusions", [])
           if isinstance(item, dict) and "id" in item} if same_draft else {}
    for item in conclusions:
        # Exclude confidence, URLs and rendering details: track meaning and speaker.
        dependencies = [{key: anchor.get(key) for key in (
            "event_id", "journal", "text", "speaker_role", "speaker_name")}
            for anchor in item["evidence"]]
        baseline = old.get(item["id"], {}).get("dependency_baseline", dependencies)
        item["dependency_baseline"] = baseline
        item["evidence_changed"] = baseline != dependencies
        if item["evidence_changed"]:
            item["checks"].append({"code": "evidence_changed", "detail":
                "После подготовки вывода изменились текст, говорящий или состав опор. Пересоберите черновик."})
            item.update(status="needs_review", decision="pending", decision_required=True,
                        decision_reason="", decided_at="")
    exported = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "generated_at": _now(),
        "session": session.name,
        "source_hash": str(current.get("source_hash") or ""),
        "draft_sha256": draft_hash,
        "draft_revision": revision,
        "decision_revision": decision_revision,
        "review_state": str(current.get("state") or "none"),
        "decision": current.get("decision"),
        "methodology": {
            "kind": "local_evidence_presence_check",
            "limitation": (
                "Проверяется существование привязанной реплики и качество STT; "
                "истинность и полнота вывода автоматически не гарантируются."),
        },
        "summary": _conclusion_summary(conclusions),
        "conclusions": [_public_conclusion(item) for item in conclusions],
    }
    _atomic_json(session / EVIDENCE_EXPORT_FILE, exported)
    return exported


def _manifest(session: Path, *, state: str, source_hash: str, issues: list[dict],
              stats: dict, draft_exists: bool, audit_available: bool) -> dict:
    required = any(_SEVERITY_RANK.get(item.get("severity", "warning"), 2) >= 2
                   for item in issues)
    return {
        "schema_version": SCHEMA_VERSION, "state": state,
        "updated_at": _now(), "source_hash": source_hash,
        "draft_file": DRAFT_FILE if draft_exists else "",
        "draft_exists": draft_exists, "requires_review": required,
        "issues": issues, "stats": stats,
        "audit_available": bool(audit_available),
        "decision": None, "decision_issues": [],
        "draft_revision": 0, "draft_edited_at": "", "draft_sha256": "",
        "decision_revision": 0,
        "evidence_export_file": "", "conclusion_summary": {},
    }


def save_blocked(session: Path, inspection: dict) -> dict:
    session = Path(session).resolve()
    manifest = _manifest(
        session, state="blocked", source_hash="",
        issues=list(inspection.get("issues") or []),
        stats=dict(inspection.get("stats") or {}), draft_exists=False,
        audit_available=False)
    _atomic_json(session / REVIEW_FILE, manifest)
    return manifest


def create(session: Path, draft: dict, inspection: dict) -> dict:
    """Объединить локальные сигналы и самоаудит модели, сохранить очередь."""
    session = Path(session).resolve()
    issues = list(inspection.get("issues") or [])
    issues.extend(_model_issues(draft.get("audit")))
    stats = dict(inspection.get("stats") or {})
    if stats.get("utterances", 0) >= 6 and not draft.get("audit_available"):
        issues.append(_issue(
            "model_audit_missing", "warning", "Самопроверка черновика не завершилась",
            "Модель не вернула структурированный список спорных выводов и противоречий.",
            action="Сверьте ключевые выводы с временной шкалой перед подтверждением.",
            action_kind="open_evidence"))
    if (stats.get("utterances", 0) >= 6
            and not _TIME_ANCHOR.search(str(draft.get("markdown") or ""))):
        issues.append(_issue(
            "evidence_missing", "warning", "Выводы не привязаны к репликам",
            "В черновике нет ни одной временной опоры на транскрипт.",
            action="Сверьте фактические выводы с временной шкалой.",
            action_kind="open_evidence"))
    requires_review = any(
        _SEVERITY_RANK.get(item.get("severity", "warning"), 2) >= 2
        for item in issues)
    manifest = _manifest(
        session, state="needs_review" if requires_review else "ready",
        source_hash=str(draft.get("source_hash") or ""), issues=issues,
        stats=stats, draft_exists=(session / DRAFT_FILE).is_file(),
        audit_available=bool(draft.get("audit_available")))
    _atomic_json(session / REVIEW_FILE, manifest)
    if manifest["draft_exists"]:
        try:
            exported = refresh_evidence_export(
                session, manifest=manifest, markdown=str(draft.get("markdown") or ""))
            manifest.update({
                "evidence_export_file": EVIDENCE_EXPORT_FILE,
                "conclusion_summary": dict(exported.get("summary") or {}),
            })
            _atomic_json(session / REVIEW_FILE, manifest)
        except (OSError, TypeError, ValueError):
            pass
    return manifest


def load(session: Path) -> dict:
    path = Path(session).resolve() / REVIEW_FILE
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def payload(session: Path, *, current_source_hash: str | None = None,
            include_draft: bool = False) -> dict:
    """Безопасный для UI снимок очереди с локальными ссылками на проверку."""
    session = Path(session).resolve()
    manifest = load(session)
    if not manifest:
        return {"state": "none", "issues": [], "requires_review": False}
    value = dict(manifest)
    value["issues"] = [dict(item) for item in manifest.get("issues", [])
                       if isinstance(item, dict)]
    stale = bool(
        current_source_hash is not None and manifest.get("source_hash")
        and current_source_hash != manifest.get("source_hash"))
    value["stale"] = stale
    value["can_finalize"] = bool(
        manifest.get("draft_exists") and not stale
        and (session / DRAFT_FILE).is_file())
    value["draft_editable"] = bool(
        value["can_finalize"] and manifest.get("state") != "finalized")
    try:
        journal_revision = max(
            (int(item["revision"]) for item in _decision_records(session)),
            default=0)
    except ValueError:
        journal_revision = int(manifest.get("decision_revision") or 0)
    value["decision_revision"] = max(
        int(manifest.get("decision_revision") or 0), journal_revision)
    draft = ""
    if include_draft and (value["draft_editable"] or stale):
        try:
            draft_path = session / DRAFT_FILE
            draft = (draft_path.read_text(encoding="utf-8")
                     if not draft_path.is_symlink() else "")
        except OSError:
            draft = ""
        if len(draft.encode("utf-8")) <= MAX_DRAFT_BYTES:
            if value["draft_editable"]:
                value["draft_markdown"] = draft
            try:
                exported = refresh_evidence_export(
                    session, manifest=manifest, markdown=draft)
            except (OSError, TypeError, ValueError):
                exported = {}
            conclusions = exported.get("conclusions")
            if isinstance(conclusions, list):
                value["conclusions"] = conclusions
                value["conclusion_summary"] = dict(
                    exported.get("summary") or {})
                value["decision_revision"] = int(
                    exported.get("decision_revision") or value["decision_revision"])
    export_path = session / EVIDENCE_EXPORT_FILE
    if export_path.is_file() and not export_path.is_symlink():
        value["evidence_export_url"] = (
            f"/files/{session.name}/{EVIDENCE_EXPORT_FILE}")
    else:
        value["evidence_export_url"] = ""
    evidence_file = session / "evidence.html"
    diarized_file = session / "evidence.diarized.html"
    value["evidence_url"] = (
        f"/files/{session.name}/{evidence_file.name}" if evidence_file.is_file() else "")
    value["diarization_url"] = (
        f"/files/{session.name}/{diarized_file.name}" if diarized_file.is_file() else "")
    if stale:
        value["issues"] = [_issue(
            "draft_stale", "warning", "После черновика изменились исходные данные",
            "Транскрипт, роли, контекст или настройки отчёта были изменены.",
            action="Пересоберите черновик, чтобы изменения попали в DOCX.",
            action_kind="regenerate"), *value["issues"]]
        value["requires_review"] = True
        value["state"] = "stale"
    summary = value.get("conclusion_summary")
    unresolved = (int(summary.get("unresolved") or 0)
                  if isinstance(summary, dict) else 0)
    value["unresolved_conclusions"] = unresolved
    value["can_approve"] = bool(value["can_finalize"] and unresolved == 0)
    if include_draft:
        try:
            calibration = report_calibration.catalog(
                session.parent,
                contour=report_calibration.session_contour(session))
            current_summary = value.get("conclusion_summary")
            if isinstance(current_summary, dict):
                current_total = int(current_summary.get("total") or 0)
                current_labeled = (
                    int(current_summary.get("confirmed") or 0)
                    + int(current_summary.get("excluded") or 0))
            else:
                current_total = current_labeled = 0
            calibration["current_report"] = {
                "total": current_total,
                "labeled": current_labeled,
                "complete": bool(current_total and current_labeled == current_total),
            }
            value["calibration"] = calibration
        except (OSError, TypeError, ValueError):
            value["calibration"] = {"status": "unavailable"}
    return value


def save_draft(session: Path, markdown: object, *, expected_revision: object,
               current_source_hash: str) -> dict:
    """Atomically save a local human edit without another model request."""
    session = Path(session).resolve()
    manifest = load(session)
    draft_path = session / DRAFT_FILE
    if (not manifest.get("draft_exists") or not draft_path.is_file()
            or draft_path.is_symlink()):
        raise ValueError("черновик отчёта не найден")
    if manifest.get("state") == "finalized":
        raise ValueError("итоговый отчёт уже создан")
    if (manifest.get("source_hash") and current_source_hash
            and manifest.get("source_hash") != current_source_hash):
        raise ValueError("исходные данные изменились — сначала пересоберите черновик")
    try:
        revision = int(expected_revision)
    except (TypeError, ValueError) as exc:
        raise ValueError("не указана редакция черновика") from exc
    current_revision = int(manifest.get("draft_revision") or 0)
    if revision != current_revision:
        raise ValueError("черновик уже изменён в другом окне — откройте его заново")
    if not isinstance(markdown, str):
        raise ValueError("текст черновика должен быть строкой")
    checked = markdown.replace("\r\n", "\n").replace("\r", "\n")
    if "\0" in checked:
        raise ValueError("черновик содержит недопустимый нулевой символ")
    if len(checked.encode("utf-8")) > MAX_DRAFT_BYTES:
        raise ValueError("черновик превышает 1 МБ")
    if len(checked.strip()) < 20:
        raise ValueError("черновик слишком короткий для итогового отчёта")
    checked = checked.rstrip() + "\n"
    current = draft_path.read_text(encoding="utf-8")
    checkpoint_path = session / report.REPORT_DRAFT_META_FILE
    try:
        checkpoint_text = checkpoint_path.read_text(encoding="utf-8")
        checkpoint = json.loads(checkpoint_text)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(
            "контрольная точка черновика отсутствует или повреждена") from exc
    current_digest = hashlib.sha256(current.encode("utf-8")).hexdigest()
    if (not isinstance(checkpoint, dict)
            or checkpoint.get("source_hash") != manifest.get("source_hash")
            or checkpoint.get("draft_sha256") != current_digest):
        raise ValueError(
            "целостность черновика не подтверждена — сначала пересоберите его")
    edited_at = _now()
    edited_digest = hashlib.sha256(checked.encode("utf-8")).hexdigest()
    updated_checkpoint = dict(checkpoint)
    updated_checkpoint.update({
        "draft_sha256": edited_digest,
        "human_edited": True,
        "edited_at": edited_at,
    })
    undo_path = session / DRAFT_UNDO_FILE
    _atomic_text(undo_path, current)
    _atomic_text(draft_path, checked)
    updated = dict(manifest)
    updated.update({
        "updated_at": _now(),
        "draft_revision": current_revision + 1,
        "draft_edited_at": edited_at,
        "draft_sha256": edited_digest,
        "decision": None,
    })
    try:
        _atomic_json(checkpoint_path, updated_checkpoint)
        _atomic_json(session / REVIEW_FILE, updated)
    except Exception:
        _atomic_text(draft_path, current)
        _atomic_text(checkpoint_path, checkpoint_text)
        raise
    try:
        exported = refresh_evidence_export(
            session, manifest=updated, markdown=checked)
        updated.update({
            "evidence_export_file": EVIDENCE_EXPORT_FILE,
            "conclusion_summary": dict(exported.get("summary") or {}),
        })
        _atomic_json(session / REVIEW_FILE, updated)
    except (OSError, TypeError, ValueError):
        pass
    return updated


def save_conclusion(session: Path, conclusion_id: object, markdown: object, *,
                    expected_revision: object, current_source_hash: str) -> dict:
    """Изменить один смысловой блок с той же optimistic-lock, что и весь черновик."""
    session = Path(session).resolve()
    draft_path = session / DRAFT_FILE
    if draft_path.is_symlink() or not draft_path.is_file():
        raise ValueError("черновик отчёта не найден")
    current = draft_path.read_text(encoding="utf-8")
    manifest = load(session)
    blocks = build_conclusions(
        session, current, revision=int(manifest.get("draft_revision") or 0))
    selected = next(
        (item for item in blocks if item.get("id") == str(conclusion_id or "")), None)
    if selected is None:
        raise ValueError("вывод уже изменился — откройте контроль отчёта заново")
    if not isinstance(markdown, str):
        raise ValueError("текст вывода должен быть строкой")
    checked = markdown.replace("\r\n", "\n").replace("\r", "\n").strip()
    if "\0" in checked:
        raise ValueError("вывод содержит недопустимый нулевой символ")
    if len(checked.encode("utf-8")) > MAX_CONCLUSION_BYTES:
        raise ValueError("вывод превышает 20 КБ")
    if len(_plain_markdown(checked)) < 3:
        raise ValueError("вывод слишком короткий")
    start, end = int(selected["_start"]), int(selected["_end"])
    changed = current[:start] + checked + current[end:]
    updated = save_draft(
        session, changed, expected_revision=expected_revision,
        current_source_hash=current_source_hash)
    try:
        exported = refresh_evidence_export(
            session, manifest=updated, markdown=changed)
        updated.update({
            "evidence_export_file": EVIDENCE_EXPORT_FILE,
            "conclusion_summary": dict(exported.get("summary") or {}),
        })
        _atomic_json(session / REVIEW_FILE, updated)
    except (OSError, TypeError, ValueError):
        pass
    return updated


def save_conclusion_decision(
        session: Path, conclusion_id: object, decision: object, *,
        expected_draft_revision: object, expected_decision_revision: object,
        current_source_hash: str, reason: object = "") -> dict:
    """Append a human decision bound to exact source, draft and claim bytes."""
    session = Path(session).resolve()
    manifest = load(session)
    draft_path = session / DRAFT_FILE
    if (not manifest.get("draft_exists") or not draft_path.is_file()
            or draft_path.is_symlink()):
        raise ValueError("черновик отчёта не найден")
    if manifest.get("state") == "finalized":
        raise ValueError("итоговый отчёт уже создан")
    if (manifest.get("source_hash") and current_source_hash
            and manifest.get("source_hash") != current_source_hash):
        raise ValueError("исходные данные изменились — сначала пересоберите черновик")
    try:
        draft_revision = int(expected_draft_revision)
        decision_revision = int(expected_decision_revision)
    except (TypeError, ValueError) as exc:
        raise ValueError("не указана редакция решения") from exc
    current_draft_revision = int(manifest.get("draft_revision") or 0)
    if draft_revision != current_draft_revision:
        raise ValueError("черновик уже изменён в другом окне — откройте его заново")
    records = _decision_records(session)
    current_decision_revision = max(
        [int(manifest.get("decision_revision") or 0),
         *(int(item["revision"]) for item in records)], default=0)
    if decision_revision != current_decision_revision:
        raise ValueError("решения уже изменены в другом окне — откройте отчёт заново")
    checked_decision = str(decision or "")
    if checked_decision not in _DECISIONS:
        raise ValueError("неизвестный статус вывода")
    if not isinstance(reason, str):
        raise ValueError("комментарий к решению должен быть строкой")
    if "\0" in reason:
        raise ValueError("комментарий к решению содержит недопустимый символ")
    checked_reason = reason.strip()
    if len(checked_reason.encode("utf-8")) > MAX_DECISION_REASON_BYTES:
        raise ValueError("комментарий к решению превышает 2 КБ")
    markdown = draft_path.read_text(encoding="utf-8")
    conclusions = build_conclusions(
        session, markdown, revision=current_draft_revision)
    selected = next(
        (item for item in conclusions
         if item.get("id") == str(conclusion_id or "")), None)
    if selected is None:
        raise ValueError("вывод уже изменился — откройте контроль отчёта заново")
    next_revision = current_decision_revision + 1
    _append_jsonl(session / DECISION_JOURNAL_FILE, {
        "schema_version": DECISION_SCHEMA_VERSION,
        "record_type": "conclusion_decision",
        "revision": next_revision,
        "timestamp": _now(),
        "source_hash": str(manifest.get("source_hash") or ""),
        "draft_revision": current_draft_revision,
        "conclusion_id": str(selected["id"]),
        "claim_sha256": _claim_sha256(str(selected["text_markdown"])),
        "prediction_status": str(selected.get("status") or "needs_review"),
        "check_codes": sorted({
            str(item.get("code") or "") for item in selected.get("checks", [])
            if isinstance(item, dict) and item.get("code")
        })[:24],
        "evidence_count": len(selected.get("evidence") or []),
        "decision": checked_decision,
        "reason": checked_reason,
        "actor": "local_user",
    })
    updated = dict(manifest)
    updated.update({
        "updated_at": _now(), "decision_revision": next_revision,
        "decision": None,
    })
    _atomic_json(session / REVIEW_FILE, updated)
    exported = refresh_evidence_export(
        session, manifest=updated, markdown=markdown)
    updated["conclusion_summary"] = dict(exported.get("summary") or {})
    _atomic_json(session / REVIEW_FILE, updated)
    return updated


def materialize_final_markdown(session: Path) -> str:
    """Return the current draft with explicitly excluded conclusions removed."""
    session = Path(session).resolve()
    manifest = load(session)
    draft_path = session / DRAFT_FILE
    if draft_path.is_symlink() or not draft_path.is_file():
        raise ValueError("черновик отчёта не найден или небезопасен")
    markdown = draft_path.read_text(encoding="utf-8")
    checkpoint = report.load_draft_checkpoint(session)
    if (not checkpoint or checkpoint.get("markdown") != markdown
            or checkpoint.get("source_hash") != manifest.get("source_hash")):
        raise ValueError("целостность черновика не подтверждена — пересоберите его")
    conclusions = build_conclusions(
        session, markdown, revision=int(manifest.get("draft_revision") or 0))
    conclusions, _ = _apply_decisions(session, manifest, conclusions)
    excluded = [item for item in conclusions if item.get("decision") == "excluded"]
    for item in sorted(excluded, key=lambda value: int(value["_remove_start"]),
                       reverse=True):
        start = int(item["_remove_start"])
        end = int(item["_remove_end"])
        markdown = markdown[:start] + markdown[end:]
    return re.sub(r"\n{3,}", "\n\n", markdown).rstrip() + "\n"


def mark_finalized(session: Path, decision: str, issues: list[dict]) -> dict:
    session = Path(session).resolve()
    manifest = load(session)
    manifest.update({
        "state": "finalized", "updated_at": _now(), "requires_review": False,
        "decision": decision,
        "decision_issues": [str(item.get("code") or "") for item in issues[:50]],
    })
    _atomic_json(session / REVIEW_FILE, manifest)
    try:
        refresh_evidence_export(session, manifest=manifest)
    except (OSError, TypeError, ValueError):
        pass
    return manifest
