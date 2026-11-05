"""Финальный отчёт: полный транскрипт + рубрика → report.md (+ docx, если есть node)."""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from llm import chat
import prompt_store
import evidence
import transcript_events

BASE = Path(__file__).parent
TYPE_INTERVIEW = "собеседование"
TYPE_CANDIDATE = "кандидат"
TYPE_TRAINING = "тренировка"
TYPE_MEETING = "встреча"


def docx_runtime() -> tuple[str, Path, str] | None:
    """Найти Node и конвертер без привязки к диску или имени пользователя."""
    override = os.environ.get("BLATERO_MD2DOCX", "").strip()
    candidates = ([Path(override)] if override else []) + [
        BASE / "tools" / "scripts" / "md-to-docx.js",
        BASE.parent / "tools" / "scripts" / "md-to-docx.js",
    ]
    script = next((path.resolve() for path in candidates if path.is_file()), None)
    node = shutil.which("node")
    if not script or not node:
        return None
    node_path = os.environ.get("NODE_PATH", "").strip()
    if not node_path:
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if npm:
            try:
                result = subprocess.run(
                    [npm, "root", "-g"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=10, check=True)
                node_path = result.stdout.strip()
            except (OSError, subprocess.SubprocessError):
                pass
    return node, script, node_path

REPORT_TEMPLATE = """{agenda_label}:
<agenda_data>
{rubric}
</agenda_data>

Полный транскрипт ({roles}):
<transcript_data>
{transcript}
</transcript_data>

Структура отчёта:
{structure}"""

REPORT_EVIDENCE_RULE = """Для каждого фактического вывода укажи точное время
подтверждающей реплики в формате [ЧЧ:ММ:СС], взяв его из транскрипта. Не
придумывай время."""
REPORT_PLAIN_RULE = """Не добавляй таймкоды, ссылки на временную шкалу или
служебные идентификаторы реплик. Отчёт должен читаться как самостоятельный
документ."""
REPORT_INTERNAL_DELIBERATION_RULE = """
Служебное обсуждение интервьюеров после того, как кандидат попрощался или
покинул разговор, не является материалом оценки. Не цитируй и не пересказывай
его и не используй согласование решения интервьюерами как доказательство
вердикта. Обосновывай вердикт только ответами кандидата и наблюдаемыми фактами
самой части интервью."""
REPORT_HIRING_FAIRNESS_RULE = """
Не используй возраст, пол, семейное положение, инвалидность, национальность,
религию и другие защищённые характеристики как риск или основание кадрового
решения. Вердикт основывай только на требованиях роли, наблюдаемых ответах и
проверяемых фактах профессионального опыта."""
REPORT_REVIEW_SYSTEM = """
После основного Markdown добавь ровно один служебный HTML-комментарий:
<!-- BLATERO_REVIEW
{"unsupported_claims": [{"claim": "вывод", "reason": "чего не хватает"}],
 "contradictions": [{"left": "утверждение 1", "right": "утверждение 2",
 "reason": "почему они конфликтуют"}]}
-->
В unsupported_claims перечисляй только фактические выводы отчёта, для которых
нет достаточной опоры в транскрипте. В contradictions — только реальные
логические конфликты. Если проблем нет, верни пустые массивы. Этот комментарий
не является частью отчёта и не заменяет честные пометки «не проверялось»."""
REPORT_DRAFT_FILE = "report.draft.md"
REPORT_DRAFT_META_FILE = "report.draft.json"
_REVIEW_MARKER = re.compile(
    r"<!--\s*BLATERO_REVIEW\s*(\{.*?\})\s*-->", re.IGNORECASE | re.DOTALL)
_INTERNAL_DELIBERATION_PATTERN = re.compile(
    r"внутренн\w*\s+обсуждени\w*|интервьюер\w*\s+(?:также\s+)?склонил\w*|"
    r"если\s+отказ\s*,?\s+то\s+отказ",
    re.IGNORECASE)
_MARKDOWN_IMAGE = re.compile(
    r"!\[(?P<alt>[^\]\n]{0,500})\]\((?P<target>[^)\n]{1,2000})\)")
_MARKDOWN_LINK = re.compile(
    r"(?<!!)\[(?P<label>[^\]\n]{0,1000})\]\((?P<target>[^)\n]{1,2000})\)")
_SAFE_EVIDENCE_LINK = re.compile(
    r"evidence\.html#t-\d{6}-\d+-\d+", re.IGNORECASE)

REPORT_FILE_TITLES = {
    TYPE_INTERVIEW: "Отчёт по собеседованию",
    TYPE_CANDIDATE: "Разбор собеседования",
    TYPE_TRAINING: "Разбор тренировки",
    "консалтинг": "Протокол консультации",
    TYPE_MEETING: "Протокол встречи",
}


def _filename_part(value: object, fallback: str, max_length: int = 80) -> str:
    """Читаемый и безопасный компонент имени файла Windows."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip(" .")
    return (text[:max_length].rstrip(" .") or fallback)


def report_docx_name(sdir: Path) -> str:
    """Читаемое имя DOCX с типом встречи, участником и датой."""
    meta = {}
    try:
        value = json.loads((sdir / "meta.json").read_text(encoding="utf-8"))
        if isinstance(value, dict):
            meta = value
    except (OSError, ValueError):
        pass
    meeting_type = str(meta.get("type") or TYPE_MEETING).strip().lower()
    title = REPORT_FILE_TITLES.get(meeting_type, REPORT_FILE_TITLES[TYPE_MEETING])
    subject = _filename_part(meta.get("name"), "без названия")
    date_text = str(meta.get("date") or "").strip()
    try:
        date_text = dt.date.fromisoformat(date_text).isoformat()
    except ValueError:
        match = re.match(r"(\d{4}-\d{2}-\d{2})", sdir.name)
        date_text = match.group(1) if match else f"{dt.date.today():%Y-%m-%d}"
    return f"{title} — {subject} — {date_text}.docx"


def find_report_docx(sdir: Path) -> Path | None:
    """Найти новое, legacy или вручную переименованное итоговое DOCX."""
    preferred = sdir / report_docx_name(sdir)
    legacy = sdir / "report.docx"
    for candidate in (preferred, legacy):
        if candidate.is_file():
            return candidate
    prefixes = ("report ", "отчёт ", "отчет ", "разбор ", "протокол ")
    manual = [path for path in sdir.glob("*.docx")
              if path.name.casefold().startswith(prefixes)
              and not path.name.casefold().startswith("report.previous-")]
    return max(manual, key=lambda path: path.stat().st_mtime) if manual else None


def _cross_channel_duplicate_count(sdir: Path) -> int:
    """Сосчитать вероятные неснятые дубли микрофона и системного канала."""
    import channel_echo
    journals = sorted(path for path in Path(sdir).glob("transcript*.jsonl")
                      if re.fullmatch(r"transcript(?:-\d+)?\.jsonl", path.name))
    duplicates = 0
    for journal in journals:
        try:
            records = transcript_events.read_records(journal)
        except (OSError, ValueError):
            continue
        utterances = [item for item in records
                      if item.get("record_type") == "utterance"
                      and item.get("status", "final") == "final"]
        microphones = [item for item in utterances
                       if item.get("source") == "microphone"]
        loopbacks = [item for item in utterances
                     if item.get("source") == "loopback"]
        for microphone in microphones:
            for loopback in loopbacks:
                separated = (max(int(microphone.get("start_ms", 0)),
                                 int(loopback.get("start_ms", 0)))
                             - min(int(microphone.get("end_ms", 0)),
                                   int(loopback.get("end_ms", 0))))
                if separated > 1500:
                    continue
                if channel_echo.echo_similarity(
                        str(microphone.get("text") or ""),
                        str(loopback.get("text") or "")) >= 0.8:
                    duplicates += 1
                    break
    return duplicates


def attribution_warning(transcript: str, meeting_type: str,
                        sdir: Path | None = None) -> str:
    """Предупредить о невозможной для диалога одноканальной атрибуции."""
    if meeting_type not in {
            TYPE_INTERVIEW, TYPE_CANDIDATE, TYPE_TRAINING, "консалтинг", TYPE_MEETING}:
        return ""
    import re
    me = len(re.findall(
        r"(?m)^- \d\d:\d\d:\d\d \*\*\[Я(?: · [^\]]+)?\]\*\*",
        transcript))
    guest = len(re.findall(
        r"(?m)^- \d\d:\d\d:\d\d \*\*\[Собеседник(?: · [^\]]+)?\]\*\*",
        transcript))
    if me + guest >= 6 and min(me, guest) == 0:
        missing = "системного звука" if guest == 0 else "микрофона"
        return (
            f"Техническое предупреждение: в транскрипте нет реплик канала {missing}. "
            "Роли говорящих не подтверждены; не приписывай спорные высказывания "
            "конкретному человеку без смысловой проверки и явно укажи ограничение "
            "атрибуции в отчёте.")
    duplicates = _cross_channel_duplicate_count(sdir) if sdir is not None else 0
    if duplicates >= 3:
        return (
            f"Техническое предупреждение: после фильтрации осталось не менее "
            f"{duplicates} вероятных межканальных дублей. Часть речи могла быть "
            "приписана обеим сторонам; оценки, цитаты и выводы о конкретном "
            "человеке требуют сверки с аудио.")
    return ""


def add_local_warning(md: str, warning: str) -> str:
    if not warning:
        return md
    lines = md.splitlines()
    message = re.sub(r"^Техническое предупреждение:\s*", "", warning).strip()
    note = f"> ⚠️ **Ограничение атрибуции.** {message}"
    if lines and lines[0].startswith("# "):
        lines[1:1] = ["", note]
    else:
        lines[:0] = [note, ""]
    return "\n".join(lines).rstrip() + "\n"


def add_review_limitations(md: str, issues: list[dict]) -> str:
    """Явно отметить ручной пропуск контроля, не раскрывая служебные детали."""
    titles = []
    for item in issues[:8]:
        title = str(item.get("title") or "").strip()
        if title and title not in titles:
            titles.append(title)
    detail = "; ".join(titles) or "остались непроверенные сигналы качества"
    note = (
        "> ⚠️ **Отчёт создан с ограничениями.** Контроль перед отчётом был "
        f"явно пропущен; {detail}. Выводы требуют сверки с исходной записью.")
    lines = md.splitlines()
    if lines and lines[0].startswith("# "):
        lines[1:1] = ["", note]
    else:
        lines[:0] = [note, ""]
    return "\n".join(lines).rstrip() + "\n"


def localize_heading(md: str, sdir: Path, meeting_type: str) -> str:
    """Вернуть имя в локальный заголовок после обезличенного облачного вызова.

    В облако имя не уходит. Для интервью мы строим первую строку из локального
    meta.json, поэтому технический псевдоним вида [IDENTITY_1] не остаётся в
    отчёте и при этом не приходится восстанавливать прочие скрытые ПД.
    """
    if meeting_type not in {TYPE_INTERVIEW, TYPE_TRAINING}:
        return md
    meta_file = sdir / "meta.json"
    if not meta_file.exists():
        return md
    try:
        import json
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return md
    name = str(meta.get("name", "")).strip()
    date = str(meta.get("date", "")).strip() or f"{dt.date.today():%Y-%m-%d}"
    if (not name or len(name) > 200
            or any(ord(char) < 32 for char in name + date)):
        return md
    lines = md.splitlines()
    prefix = ("Разбор тренировки собеседования"
              if meeting_type == TYPE_TRAINING else "Отчёт по собеседованию")
    heading = f"# {prefix} — {name} — {date}"
    if lines and lines[0].startswith("# "):
        lines[0] = heading
    else:
        lines = [heading, "", *lines]
    return "\n".join(lines).rstrip() + "\n"


def _report_evidence(sdir: Path) -> list[dict]:
    try:
        _evidence_path, entries = evidence.build(sdir)
    except (OSError, ValueError, KeyError):
        return []
    return entries


def _report_prompt(sdir: Path, preset_data: dict, transcript: str,
                   quality_warning: str, *, include_timestamps: bool = False) -> str:
    from copilot import meeting_context
    from meeting_types import agenda_text
    prompt = prompt_store.resolve("report.template", REPORT_TEMPLATE).format(
        agenda_label=preset_data["agenda_label"],
        rubric=agenda_text(sdir, preset_data), roles=preset_data["roles"],
        transcript=transcript, structure=preset_data["report_structure"])
    prompt += "\n\n" + (
        REPORT_EVIDENCE_RULE if include_timestamps else REPORT_PLAIN_RULE)
    if quality_warning:
        prompt = quality_warning + "\n\n" + prompt
    # Conclusions saved from this report are outputs, not new input to itself.
    ctx = meeting_context(sdir, exclude_memory_source_session=Path(sdir).name)
    if ctx:
        if preset_data.get("mode") == "training":
            context_rule = (
                "Материалы тренировки — только контекст подготовки. Опыт считается "
                "подтверждённым лишь тогда, когда кандидат сам раскрыл его в ответе.")
        elif preset_data.get("mode") == "candidate":
            context_rule = (
                "Используй резюме/анкету только для контекста подготовки. Не считай "
                "несказанный опыт фактом и не придумывай его.")
        else:
            context_rule = "Сверяй сказанное с резюме/анкетой: расхождения — в риски."
        prompt = ctx + "\n\n" + context_rule + "\n\n" + prompt
    return prompt


def _draft_materials(sdir: Path) -> dict:
    """Все входы staged-отчёта; одна функция защищает fingerprint от рассинхрона."""
    from copilot import all_transcripts, session_type, UNTRUSTED_DATA_RULE
    from meeting_types import preset
    import config as cfg

    meeting_type = session_type(sdir)
    preset_data = preset(meeting_type)
    transcript = all_transcripts(sdir) or "(транскрипт пуст)"
    quality_warning = attribution_warning(transcript, meeting_type, sdir)
    settings = cfg.load()
    prompt = _report_prompt(
        sdir, preset_data, transcript, quality_warning, include_timestamps=True)
    deliberation_rule = (
        REPORT_INTERNAL_DELIBERATION_RULE
        if meeting_type == TYPE_INTERVIEW else "")
    fairness_rule = (
        REPORT_HIRING_FAIRNESS_RULE if meeting_type == TYPE_INTERVIEW else "")
    system = (preset_data["report_system"] + UNTRUSTED_DATA_RULE
              + deliberation_rule + fairness_rule + REPORT_REVIEW_SYSTEM)
    model = settings["report_model"]
    fingerprint_data = json.dumps({
        "meeting_type": meeting_type, "model": model, "system": system,
        "prompt": prompt,
    }, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "meeting_type": meeting_type, "preset": preset_data,
        "transcript": transcript, "quality_warning": quality_warning,
        "settings": settings, "prompt": prompt, "system": system, "model": model,
        "source_hash": hashlib.sha256(fingerprint_data).hexdigest(),
    }


def source_fingerprint(sdir: Path) -> str:
    """Отпечаток именно тех данных, по которым строится проверяемый черновик."""
    return str(_draft_materials(Path(sdir))["source_hash"])


def _extract_review_marker(markdown: str) -> tuple[str, dict, bool]:
    match = _REVIEW_MARKER.search(markdown)
    if not match:
        return markdown.rstrip() + "\n", {}, False
    cleaned = _REVIEW_MARKER.sub("", markdown).rstrip() + "\n"
    try:
        value = json.loads(match.group(1))
    except (TypeError, ValueError):
        return cleaned, {}, False
    return cleaned, value if isinstance(value, dict) else {}, isinstance(value, dict)


def remove_internal_deliberation(markdown: str, meeting_type: str) -> str:
    """Не допустить служебное обсуждение интервьюеров в итоговый отчёт."""
    if meeting_type != TYPE_INTERVIEW:
        return markdown
    cleaned_lines: list[str] = []
    for line in markdown.splitlines():
        sentences = re.split(r"(?<=[.!?])\s+", line)
        kept = []
        for sentence in sentences:
            normalized = sentence.casefold().replace("ё", "е")
            after_candidate = (
                "после завершения разговора" in normalized
                or "после ухода кандидата" in normalized)
            decision_terms = any(term in normalized for term in (
                "интервьюер", "решени", "вердикт", "отказ", "соглас"))
            if (_INTERNAL_DELIBERATION_PATTERN.search(normalized)
                    or (after_candidate and decision_terms)):
                continue
            kept.append(sentence)
        cleaned_lines.append(" ".join(kept).rstrip())
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.rstrip() + "\n"


def sanitize_generated_markdown(markdown: str) -> str:
    """Не дать LLM заставить DOCX-конвертер читать файлы или создавать phishing links."""
    def image_replacement(match: re.Match[str]) -> str:
        alt = match.group("alt").strip()
        return f"[Изображение исключено: {alt}]" if alt else "[Изображение исключено]"

    def link_replacement(match: re.Match[str]) -> str:
        target = match.group("target").strip()
        return (match.group(0) if _SAFE_EVIDENCE_LINK.fullmatch(target)
                else match.group("label"))

    cleaned = _MARKDOWN_IMAGE.sub(image_replacement, str(markdown))
    return _MARKDOWN_LINK.sub(link_replacement, cleaned)


def prepare_draft(sdir: Path) -> dict:
    """Один LLM-вызов: сохранить черновик и локальные данные самоаудита."""
    import config as cfg

    sdir = Path(sdir).resolve()
    data = _draft_materials(sdir)
    print(f"Генерирую проверяемый черновик ({cfg.llm_label(data['model'])}, "
          f"тип «{data['meeting_type']}», может думать минуту-две)...")
    entries = _report_evidence(sdir)
    raw = chat(data["model"], data["system"], data["prompt"],
               max_tokens=6000, temperature=0.2)
    md, audit, audit_available = _extract_review_marker(raw)
    md = remove_internal_deliberation(md, data["meeting_type"])
    md = sanitize_generated_markdown(md)
    md = localize_heading(md, sdir, data["meeting_type"])
    md = add_local_warning(md, data["quality_warning"])
    md = evidence.link_report_timestamps(md, entries)
    output = sdir / REPORT_DRAFT_FILE
    checkpoint = {
        "schema_version": 1,
        "source_hash": data["source_hash"],
        "draft_sha256": hashlib.sha256(md.encode("utf-8")).hexdigest(),
        "audit": audit,
        "audit_available": audit_available,
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="milliseconds"),
    }
    checkpoint_path = sdir / REPORT_DRAFT_META_FILE
    checkpoint_tmp = checkpoint_path.with_name(checkpoint_path.name + ".tmp")
    checkpoint_tmp.write_text(
        json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(checkpoint_tmp, checkpoint_path)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(md, encoding="utf-8")
    os.replace(temporary, output)
    return {
        "markdown": md, "draft": output.name, "audit": audit,
        "audit_available": audit_available, "source_hash": data["source_hash"],
    }


def load_draft_checkpoint(sdir: Path) -> dict:
    """Return a draft only when its persisted provenance matches its bytes."""
    sdir = Path(sdir).resolve()
    draft_path = sdir / REPORT_DRAFT_FILE
    checkpoint_path = sdir / REPORT_DRAFT_META_FILE
    if not draft_path.is_file() or not checkpoint_path.is_file():
        return {}
    try:
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        markdown = draft_path.read_text(encoding="utf-8")
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(checkpoint, dict):
        return {}
    digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    if checkpoint.get("draft_sha256") != digest:
        return {}
    return {
        "markdown": markdown,
        "draft": draft_path.name,
        "audit": (checkpoint.get("audit")
                  if isinstance(checkpoint.get("audit"), dict) else {}),
        "audit_available": bool(checkpoint.get("audit_available")),
        "source_hash": str(checkpoint.get("source_hash") or ""),
    }


def finalize_draft(sdir: Path, *, decision: str = "approved",
                   issues: list[dict] | None = None,
                   markdown_override: str | None = None) -> dict:
    """Без LLM-вызова превратить проверенный черновик в итоговый MD/DOCX."""
    from copilot import session_type
    import config as cfg

    sdir = Path(sdir).resolve()
    draft = sdir / REPORT_DRAFT_FILE
    if not draft.is_file():
        raise FileNotFoundError("проверяемый черновик отчёта не найден")
    meeting_type = session_type(sdir)
    settings = cfg.load()
    include_timestamps = bool(settings.get("report_include_timestamps", False))
    if markdown_override is not None and not isinstance(markdown_override, str):
        raise ValueError("проверенный текст отчёта должен быть строкой")
    md = (markdown_override if markdown_override is not None
          else draft.read_text(encoding="utf-8"))
    md = remove_internal_deliberation(md, meeting_type)
    md = sanitize_generated_markdown(md)
    if decision == "skipped":
        md = add_review_limitations(md, issues or [])
    md = (md if include_timestamps else evidence.remove_report_timestamps(md))
    out = sdir / "report.md"
    docx = sdir / report_docx_name(sdir)
    _archive_reports(sdir, (out, docx, sdir / "report.docx"))
    temporary = sdir / "report.md.tmp"
    temporary.write_text(md, encoding="utf-8")
    os.replace(temporary, out)
    print(f"Отчёт: {out}")
    _build_docx(sdir, out, docx, meeting_type)
    return {"markdown": out.name, "docx": docx.name if docx.exists() else ""}


def _archive_reports(sdir: Path, outputs: tuple[Path, ...]) -> None:
    stamp = f"{dt.datetime.now():%Y%m%d-%H%M%S}"
    for existing in dict.fromkeys(outputs):
        if not existing.exists():
            continue
        archived = sdir / f"report.previous-{stamp}{existing.suffix}"
        number = 2
        while archived.exists():
            archived = sdir / f"report.previous-{stamp}-{number}{existing.suffix}"
            number += 1
        os.replace(existing, archived)


def _report_header(meeting_type: str) -> str:
    if meeting_type == TYPE_TRAINING:
        return "Разбор тренировки собеседования"
    if meeting_type == TYPE_CANDIDATE:
        return "Разбор моего собеседования"
    if meeting_type == TYPE_INTERVIEW:
        return "Отчёт по собеседованию"
    return "Протокол встречи"


def _build_docx(sdir: Path, markdown: Path, docx: Path,
                meeting_type: str) -> None:
    runtime = docx_runtime()
    if not runtime:
        from docx_export import build as export_docx
        temporary = sdir / "report.tmp.docx"
        try:
            export_docx(markdown.read_text(encoding="utf-8"), temporary,
                        header=_report_header(meeting_type))
            os.replace(temporary, docx)
            print(f"DOCX:  {docx}")
        finally:
            temporary.unlink(missing_ok=True)
        return
    node, md2docx, node_path = runtime
    temporary = sdir / "report.tmp.docx"
    try:
        subprocess.run(
            [node, str(md2docx), str(markdown), str(temporary),
             "--header", _report_header(meeting_type)],
            env={**os.environ, **({"NODE_PATH": node_path} if node_path else {})},
            check=True, capture_output=True, timeout=120)
        os.replace(temporary, docx)
        print(f"DOCX:  {docx}")
    except (OSError, subprocess.SubprocessError) as exc:
        temporary.unlink(missing_ok=True)
        print(f"Внешний конвертер недоступен ({type(exc).__name__}); используется встроенный экспорт.")
        from docx_export import build as export_docx
        try:
            export_docx(markdown.read_text(encoding="utf-8"), temporary,
                        header=_report_header(meeting_type))
            os.replace(temporary, docx)
        finally:
            temporary.unlink(missing_ok=True)


def build(sdir: Path):
    from copilot import all_transcripts, session_type
    from meeting_types import preset
    meeting_type = session_type(sdir)
    preset_data = preset(meeting_type)
    transcript = all_transcripts(sdir) or "(транскрипт пуст)"
    quality_warning = attribution_warning(transcript, meeting_type, sdir)
    import config as cfg
    settings = cfg.load()
    include_timestamps = bool(settings.get("report_include_timestamps", False))
    evidence_entries = _report_evidence(sdir) if include_timestamps else []
    prompt = _report_prompt(
        sdir, preset_data, transcript, quality_warning,
        include_timestamps=include_timestamps)
    model = settings["report_model"]
    print(f"Генерирую отчёт ({cfg.llm_label(model)}, тип «{meeting_type}», "
          "может думать минуту-две)...")
    from copilot import UNTRUSTED_DATA_RULE
    deliberation_rule = (
        REPORT_INTERNAL_DELIBERATION_RULE
        if meeting_type == TYPE_INTERVIEW else "")
    fairness_rule = (
        REPORT_HIRING_FAIRNESS_RULE if meeting_type == TYPE_INTERVIEW else "")
    md = chat(model, preset_data["report_system"] + UNTRUSTED_DATA_RULE
              + deliberation_rule + fairness_rule,
              prompt, max_tokens=6000, temperature=0.2)
    md = remove_internal_deliberation(md, meeting_type)
    md = sanitize_generated_markdown(md)
    md = localize_heading(md, sdir, meeting_type)
    md = add_local_warning(md, quality_warning)
    md = (evidence.link_report_timestamps(md, evidence_entries)
          if include_timestamps else evidence.remove_report_timestamps(md))
    out = sdir / "report.md"
    docx = sdir / report_docx_name(sdir)
    _archive_reports(sdir, (out, docx, sdir / "report.docx"))
    tmp_md = sdir / "report.md.tmp"
    tmp_md.write_text(md, encoding="utf-8")
    os.replace(tmp_md, out)
    print(f"Отчёт: {out}")
    _build_docx(sdir, out, docx, meeting_type)
    return {"markdown": out.name, "docx": docx.name if docx.exists() else ""}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None)
    args = ap.parse_args()
    if args.session:
        sdir = Path(args.session)
    else:
        from copilot import latest_session
        sdir = latest_session()
    build(sdir)
