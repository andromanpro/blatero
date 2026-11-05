"""Безопасный локальный импорт транскриптов из сервисов видеовстреч."""
from __future__ import annotations

import base64
import datetime as dt
import io
import json
import os
import re
import uuid
import zipfile
from pathlib import Path

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

import transcript_events


MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_UTTERANCES = 10_000
MAX_DOCX_MEMBERS = 2_500
MAX_DOCX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 200
MAX_EXTRACTED_TEXT_CHARS = 4 * 1024 * 1024
JSON_SUFFIX = ".json"
DOCX_SUFFIX = ".docx"
TOO_LARGE_MESSAGE = "файл транскрипта больше 2 МБ"

ADAPTERS = {
    "auto": {
        "label": "определить автоматически",
        "extensions": (".srt", ".vtt", JSON_SUFFIX, ".txt", DOCX_SUFFIX, ".pdf"),
        "help": "Teams, Zoom, Телемост, Контур.Толк и универсальные файлы",
    },
    "teams": {
        "label": "Microsoft Teams",
        "extensions": (".vtt", DOCX_SUFFIX),
        "help": "скачанный из Teams транскрипт VTT или DOCX",
    },
    "zoom": {
        "label": "Zoom",
        "extensions": (".vtt",),
        "help": "аудиотранскрипт облачной записи Zoom в формате VTT",
    },
    "telemost": {
        "label": "Яндекс Телемост",
        "extensions": (".txt", DOCX_SUFFIX, ".pdf"),
        "help": "полная расшифровка из письма; при необходимости сохраните текст как TXT",
    },
    "kontur_talk": {
        "label": "Контур.Толк",
        "extensions": (".txt",),
        "help": "TXT из раздела «Расшифровка» с авторами и таймкодами",
    },
    "universal": {
        "label": "другой источник",
        "extensions": (".srt", ".vtt", JSON_SUFFIX, ".txt", DOCX_SUFFIX, ".pdf"),
        "help": "SRT, VTT, JSON или текст с таймкодами и именами участников",
    },
}
ADAPTER_PAYLOAD = [
    {"value": key, "label": value["label"],
     "extensions": list(value["extensions"]), "help": value["help"]}
    for key, value in ADAPTERS.items()
]

_TXT_TIME_VALUE = r"(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[,.]\d{1,3})?"
_TXT_TIME = re.compile(
    rf"^\[?(?P<time>{_TXT_TIME_VALUE})\]?"
    r"(?:\s+|\s*[—–-]\s*)?(?P<body>.*)$")
_TIME_ONLY = re.compile(rf"^\[?(?P<time>{_TXT_TIME_VALUE})\]?$")
_TRAILING_TIME = re.compile(
    rf"^(?P<body>.+?)\s+\[?(?P<time>{_TXT_TIME_VALUE})\]?$")
_TELEMOST_MARKERS = ("телемост", "telemost", "яндекс", "yandex", "алиса pro")
_TALK_MARKERS = ("контур.толк", "контур толк", "kontur", "ktalk", "толк")


def adapter_payload() -> list[dict]:
    """Вернуть описание адаптеров для интерфейса без изменяемых общих объектов."""
    return [{**item, "extensions": list(item["extensions"])}
            for item in ADAPTER_PAYLOAD]


def decode_upload(content: str, encoding: str = "text") -> str | bytes:
    """Декодировать браузерную загрузку и ограничить размер уже после base64."""
    if not isinstance(content, str):
        raise ValueError("не получено содержимое импортируемого файла")
    if encoding == "base64":
        max_encoded = ((MAX_IMPORT_BYTES + 2) // 3) * 4
        if len(content) > max_encoded:
            raise ValueError(TOO_LARGE_MESSAGE)
        try:
            raw = base64.b64decode(content, validate=True)
        except ValueError as exc:
            raise ValueError("повреждено содержимое импортируемого файла") from exc
        if len(raw) > MAX_IMPORT_BYTES:
            raise ValueError(TOO_LARGE_MESSAGE)
        return raw
    if encoding not in ("", "text", None):
        raise ValueError("неизвестная кодировка импортируемого файла")
    if len(content.encode("utf-8")) > MAX_IMPORT_BYTES:
        raise ValueError(TOO_LARGE_MESSAGE)
    return content


def _milliseconds(value: object, *, seconds_default: bool = False) -> int:
    if isinstance(value, bool):
        raise ValueError("время не может быть true/false")
    if isinstance(value, (int, float)):
        number = float(value)
        return max(0, round(number * 1000 if seconds_default else number))
    text = str(value or "").strip()
    whole, separator, milliseconds = text.replace(",", ".").partition(".")
    parts = whole.split(":")
    if (separator != "." or len(milliseconds) != 3
            or not milliseconds.isdigit() or len(parts) not in (2, 3)
            or any(not part.isdigit() for part in parts)):
        raise ValueError(f"неизвестный формат времени: {text[:40]}")
    if len(parts) == 2:
        hours = 0
        minutes, seconds = map(int, parts)
    else:
        hours, minutes, seconds = map(int, parts)
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + int(milliseconds)


def _voice_tag(text: str) -> tuple[str, str] | None:
    """Разобрать WebVTT voice-tag без регулярного выражения с backtracking."""
    if text[:2].casefold() != "<v":
        return None
    close = text.find(">", 2)
    if close < 0:
        return None
    header = text[2:close]
    if not header or not (header[0].isspace() or header[0] == "."):
        return None
    if header.startswith("."):
        _, separator, header = header.partition(" ")
        if not separator:
            return None
    name = header.strip()
    if not name:
        return None
    return name, text[close + 1:].strip()


def _speaker_prefix(text: str) -> tuple[str, str] | None:
    """Разобрать `[Имя] текст` или `Имя: текст` за линейное время."""
    if text.startswith("["):
        close = text.find("]", 1)
        if close > 1:
            name = text[1:close].strip()
            body = text[close + 1:].strip()
            if name and body:
                return name, body
    colon = text.find(":")
    if 0 < colon <= 80:
        name = text[:colon].strip()
        body = text[colon + 1:].strip()
        if name and body:
            return name, body
    return None


def _speaker_text(text: str, speaker: object = "") -> tuple[str, str]:
    cleaned = " ".join(str(text or "").replace("\ufeff", "").split()).strip()
    name = " ".join(str(speaker or "").split()).strip()
    voice = _voice_tag(cleaned)
    if voice:
        name, cleaned = voice
    elif not name:
        prefix = _speaker_prefix(cleaned)
        if prefix:
            name, cleaned = prefix
    if len(name) > 80:
        raise ValueError("имя участника длиннее 80 символов")
    if not cleaned:
        raise ValueError("пустая реплика")
    return name, cleaned


def _cue_lines(block: str, *, webvtt: bool) -> list[str]:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if webvtt and lines and lines[0].upper().startswith("WEBVTT"):
        return lines[1:]
    return lines


def _cue_from_lines(lines: list[str], *, webvtt: bool) -> dict | None:
    arrow_index = next((index for index, line in enumerate(lines)
                        if "-->" in line), -1)
    if arrow_index < 0:
        return None
    start_part, separator, end_part = lines[arrow_index].partition("-->")
    start_values = start_part.split()
    end_values = end_part.split()
    if not separator or not start_values or not end_values:
        return None
    speaker, text = _speaker_text(" ".join(lines[arrow_index + 1:]))
    if webvtt:
        text = re.sub(r"</?[^>]+>", "", text).strip()
        if not text:
            return None
    start_ms = _milliseconds(start_values[-1])
    end_ms = _milliseconds(end_values[0])
    return {"start_ms": start_ms, "end_ms": max(start_ms, end_ms),
            "speaker": speaker, "text": text}


def _parse_cues(content: str, *, webvtt: bool) -> list[dict]:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalized.strip())
    result = []
    for block in blocks:
        lines = _cue_lines(block, webvtt=webvtt)
        cue = _cue_from_lines(lines, webvtt=webvtt) if lines else None
        if cue:
            result.append(cue)
    return result


def _first(item: dict, *keys: str):
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def _json_items(content: str) -> list:
    value = json.loads(content)
    if isinstance(value, dict):
        value = next((value[key] for key in
                      ("utterances", "segments", "transcript", "messages", "items")
                      if isinstance(value.get(key), list)), value)
    if not isinstance(value, list):
        raise ValueError("JSON должен быть массивом реплик или содержать utterances/segments")
    if len(value) > MAX_UTTERANCES:
        raise ValueError(f"в JSON больше {MAX_UTTERANCES} реплик")
    return value


def _json_text_and_speaker(raw: dict) -> tuple[str, str] | None:
    text = _first(raw, "text", "transcript", "content", "message")
    if isinstance(text, dict):
        text = _first(text, "text", "content", "value")
    if not str(text or "").strip():
        return None
    speaker = _first(raw, "speaker_name", "speaker", "participant",
                     "author", "user_name", "name")
    if isinstance(speaker, dict):
        speaker = _first(speaker, "name", "display_name", "title", "id")
    return _speaker_text(str(text), speaker)


def _json_time(raw: dict, milliseconds_key: str, keys: tuple[str, ...],
               default: int) -> int:
    if milliseconds_key in raw:
        return _milliseconds(raw[milliseconds_key])
    value = _first(raw, *keys)
    return (_milliseconds(value, seconds_default=True)
            if value is not None else default)


def _json_utterance(raw: object, cursor: int) -> dict | None:
    if not isinstance(raw, dict):
        return None
    parsed = _json_text_and_speaker(raw)
    if not parsed:
        return None
    speaker, text = parsed
    start_ms = _json_time(raw, "start_ms", ("start", "start_time", "from"), cursor)
    duration = max(800, min(30_000, len(text.split()) * 420))
    end_ms = _json_time(raw, "end_ms", ("end", "end_time", "to"),
                        start_ms + duration)
    return {"start_ms": start_ms, "end_ms": max(start_ms, end_ms),
            "speaker": speaker, "text": text}


def _parse_json(content: str) -> list[dict]:
    result = []
    cursor = 0
    for raw in _json_items(content):
        utterance = _json_utterance(raw, cursor)
        if utterance:
            result.append(utterance)
            cursor = utterance["end_ms"] + 100
    return result


def _txt_milliseconds(value: str) -> int:
    """Разобрать таймкод TXT, где доли секунды обычно отсутствуют."""
    normalized = value.replace(",", ".")
    whole, dot, fraction = normalized.partition(".")
    parts = [int(part) for part in whole.split(":")]
    if len(parts) == 2:
        hours, minutes, seconds = 0, *parts
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(f"неизвестный формат времени: {value[:40]}")
    milliseconds = int((fraction + "000")[:3]) if dot else 0
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


def _prepare_timed_lines(content: str) -> list[str]:
    lines = [" ".join(line.replace("\ufeff", "").split()).strip()
             for line in content.replace("\r\n", "\n").replace("\r", "\n").splitlines()]
    lines = [line for line in lines if line]
    prepared: list[str] = []
    for line in lines:
        trailing = _TRAILING_TIME.match(line)
        if trailing and not _TXT_TIME.match(line):
            prepared.append(f"{trailing.group('time')} {trailing.group('body')}")
            continue
        time_only = _TIME_ONLY.match(line)
        if time_only and prepared and len(prepared[-1]) <= 80 \
                and not _TXT_TIME.match(prepared[-1]):
            speaker = prepared.pop()
            prepared.append(f"{time_only.group('time')} {speaker}")
            continue
        prepared.append(line)
    return prepared


def _timed_cues(content: str) -> list[dict]:
    cues: list[dict] = []
    current: dict | None = None
    for line in _prepare_timed_lines(content):
        match = _TXT_TIME.match(line)
        if match:
            if current:
                cues.append(current)
            current = {"start_ms": _txt_milliseconds(match.group("time")),
                       "lines": [], "body": match.group("body").strip()}
        elif current:
            current["lines"].append(line)
    if current:
        cues.append(current)
    return cues


def _timed_text(cue: dict) -> tuple[str, str]:
    body = str(cue["body"] or "").strip()
    lines = list(cue["lines"])
    if body:
        prefixed = _speaker_prefix(body)
        if prefixed:
            speaker, first_line = prefixed
            return speaker, " ".join([first_line, *lines]).strip()
        if lines and len(body) <= 80:
            return body, " ".join(lines).strip()
        return "", " ".join([body, *lines]).strip()
    if len(lines) >= 2 and len(lines[0]) <= 80:
        return lines[0], " ".join(lines[1:]).strip()
    return "", " ".join(lines).strip()


def _timed_utterance(cues: list[dict], index: int) -> dict | None:
    cue = cues[index]
    speaker, text = _timed_text(cue)
    try:
        speaker, text = _speaker_text(text, speaker)
    except ValueError:
        return None
    start_ms = int(cue["start_ms"])
    if index + 1 < len(cues):
        end_ms = max(start_ms, int(cues[index + 1]["start_ms"]) - 1)
    else:
        end_ms = start_ms + max(800, min(30_000, len(text.split()) * 420))
    return {"start_ms": start_ms, "end_ms": end_ms,
            "speaker": speaker, "text": text}


def _parse_timed_text(content: str) -> list[dict]:
    """Разобрать TXT/DOCX/PDF с таймкодом до или после имени участника."""
    cues = _timed_cues(content)
    result = []
    for index in range(len(cues)):
        utterance = _timed_utterance(cues, index)
        if utterance:
            result.append(utterance)
    return result


def _parse_speaker_lines(content: str) -> list[dict]:
    """Последний локальный fallback для строк вида «Имя: реплика» без времени."""
    result = []
    cursor = 0
    for source_line in content.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = " ".join(source_line.replace("\ufeff", "").split()).strip()
        prefixed = _speaker_prefix(line)
        if not prefixed:
            continue
        speaker, text = prefixed
        if not speaker or not text:
            continue
        duration = max(800, min(30_000, len(text.split()) * 420))
        result.append({"start_ms": cursor, "end_ms": cursor + duration,
                       "speaker": speaker, "text": text})
        cursor += duration + 100
    return result if len(result) >= 2 else []


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("текст файла не удалось прочитать как UTF-8, UTF-16 или Windows-1251")


def docx_text(raw: bytes) -> str:
    """Локально извлечь абзацы и таблицы DOCX с ограничениями ZIP/XML."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            if len(members) > MAX_DOCX_MEMBERS:
                raise ValueError("в DOCX слишком много внутренних файлов")
            if sum(item.file_size for item in members) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise ValueError("распакованный DOCX слишком велик")
            if "word/document.xml" not in archive.namelist():
                raise ValueError("в DOCX отсутствует основной документ")
            xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError) as exc:
        raise ValueError("DOCX повреждён или имеет неверный формат") from exc
    if len(xml) > MAX_DOCX_UNCOMPRESSED_BYTES:
        raise ValueError("основной документ DOCX слишком велик")
    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise ValueError("DOCX содержит запрещённые XML-сущности")
    try:
        root = ElementTree.fromstring(xml)
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        raise ValueError("не удалось разобрать содержимое DOCX") from exc
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(namespace + "p"):
        text = "".join(node.text or "" for node in paragraph.iter(namespace + "t"))
        if text.strip():
            paragraphs.append(text.strip())
    result = "\n".join(paragraphs)
    if len(result) > MAX_EXTRACTED_TEXT_CHARS:
        raise ValueError("извлечённый текст DOCX слишком велик")
    return result


def _docx_text(raw: bytes) -> str:
    return docx_text(raw)


def pdf_text(raw: bytes, *, max_pages: int = MAX_PDF_PAGES,
             max_chars: int = MAX_EXTRACTED_TEXT_CHARS) -> str:
    """Извлечь текст PDF с явными пределами страниц и результата."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise ValueError("PDF защищён паролем")
        if len(reader.pages) > max_pages:
            raise ValueError(f"в PDF больше {max_pages} страниц")
        pages = []
        text_size = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            text_size += len(text)
            if text_size > max_chars:
                raise ValueError("извлечённый текст PDF слишком велик")
            pages.append(text)
        return "\n".join(pages)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF повреждён или не содержит доступного текста") from exc


def _pdf_text(raw: bytes) -> str:
    return pdf_text(raw)


def _parse_document_text(content: str) -> list[dict]:
    if "-->" in content:
        cues = _parse_cues(content, webvtt="WEBVTT" in content[:100].upper())
        if cues:
            return cues
    cues = _parse_timed_text(content)
    return cues or _parse_speaker_lines(content)


def _ensure_size(payload: str | bytes) -> None:
    size = len(payload if isinstance(payload, bytes) else payload.encode("utf-8"))
    if size > MAX_IMPORT_BYTES:
        raise ValueError(TOO_LARGE_MESSAGE)


def _extract(name: str, payload: str | bytes) -> tuple[str, str]:
    suffix = Path(str(name)).suffix.lower()
    if suffix in (DOCX_SUFFIX, ".pdf"):
        if not isinstance(payload, bytes):
            raise ValueError(f"{suffix.upper()[1:]} должен быть загружен как бинарный файл")
        return suffix, _docx_text(payload) if suffix == DOCX_SUFFIX else _pdf_text(payload)
    if isinstance(payload, bytes):
        return suffix, _decode_text(payload)
    return suffix, payload


def _detect_adapter(name: str, suffix: str, content: str) -> str:
    haystack = f"{name}\n{content[:5000]}".casefold()
    if suffix == ".vtt":
        lowered = content.casefold()
        has_voice_tag = "<v." in lowered or "<v " in lowered or "<v\t" in lowered
        return "teams" if has_voice_tag else "zoom"
    if suffix == DOCX_SUFFIX:
        return "telemost" if any(word in haystack for word in _TELEMOST_MARKERS) else "teams"
    if suffix == ".pdf":
        return "telemost"
    if suffix == ".txt":
        if any(word in haystack for word in _TELEMOST_MARKERS):
            return "telemost"
        if any(word in haystack for word in _TALK_MARKERS) or _parse_timed_text(content):
            return "kontur_talk"
    return "universal"


def parse_adapter(name: str, payload: str | bytes, adapter: str = "auto") -> dict:
    """Разобрать файл выбранным адаптером или определить источник автоматически."""
    _ensure_size(payload)
    if adapter not in ADAPTERS:
        raise ValueError("неизвестный источник транскрипта")
    suffix, content = _extract(name, payload)
    if not content.strip():
        raise ValueError("файл транскрипта пуст или не содержит доступного текста")
    selected = _detect_adapter(name, suffix, content) if adapter == "auto" else adapter
    allowed = ADAPTERS[selected]["extensions"]
    if suffix not in allowed:
        readable = ", ".join(ext.upper().lstrip(".") for ext in allowed)
        raise ValueError(f"для «{ADAPTERS[selected]['label']}» нужен файл {readable}")

    if suffix == ".srt":
        format_name, utterances = "srt", _parse_cues(content, webvtt=False)
    elif suffix == ".vtt":
        format_name, utterances = "vtt", _parse_cues(content, webvtt=True)
    elif suffix == JSON_SUFFIX:
        format_name, utterances = "json", _parse_json(content)
    else:
        format_name, utterances = suffix.lstrip("."), _parse_document_text(content)
    if not utterances:
        raise ValueError("в файле не найдено реплик с именами участников и/или временем")
    if len(utterances) > MAX_UTTERANCES:
        raise ValueError(f"в файле больше {MAX_UTTERANCES} реплик")
    utterances.sort(key=lambda item: (item["start_ms"], item["end_ms"]))
    return {"adapter": selected, "adapter_label": ADAPTERS[selected]["label"],
            "format": format_name, "utterances": utterances}


def parse(name: str, content: str) -> tuple[str, list[dict]]:
    """Обратная совместимость универсального текстового импорта."""
    result = parse_adapter(name, content, "universal")
    format_name = {"vtt": "webvtt", "txt": "ktalk-txt"}.get(
        result["format"], result["format"])
    return format_name, result["utterances"]


def _next_segment(session: Path) -> tuple[int, Path, Path]:
    segment = 1
    while True:
        suffix = "" if segment == 1 else f"-{segment}"
        markdown = session / f"transcript{suffix}.md"
        journal = session / f"transcript{suffix}.jsonl"
        if not markdown.exists() and not journal.exists():
            return segment, markdown, journal
        segment += 1


def _reserve_segment(session: Path) -> tuple[int, Path, Path, str]:
    """Эксклюзивно занять номер сегмента и для импорта, и для live.py."""
    segment = 1
    while True:
        suffix = "" if segment == 1 else f"-{segment}"
        markdown = session / f"transcript{suffix}.md"
        journal = session / f"transcript{suffix}.jsonl"
        if markdown.exists():
            segment += 1
            continue
        marker = f"BLATERO_IMPORT_RESERVATION:{uuid.uuid4().hex}\n"
        try:
            with journal.open("x", encoding="ascii", newline="") as reservation:
                reservation.write(marker)
        except FileExistsError:
            segment += 1
            continue
        # live.py создаёт Markdown первым. Если он успел между проверками,
        # уступаем номер; удаляем только собственный маркер, не чужой журнал.
        if markdown.exists():
            try:
                if journal.read_text(encoding="ascii") == marker:
                    journal.unlink()
            except (OSError, UnicodeError):
                pass
            segment += 1
            continue
        return segment, markdown, journal, marker


def _import_title(session: Path) -> str:
    meta_path = session / "meta.json"
    meta = (json.loads(meta_path.read_text(encoding="utf-8"))
            if meta_path.is_file() else {})
    return " ".join(f"{meta.get('type', '')} {meta.get('name', '')}".split())


def _import_paths(session: Path) -> tuple[int, Path, Path, Path, Path, str]:
    segment, markdown, journal, marker = _reserve_segment(session)
    nonce = uuid.uuid4().hex
    journal_tmp = journal.with_name(f".{journal.name}.{nonce}.tmp")
    markdown_tmp = markdown.with_name(f".{markdown.name}.{nonce}.tmp")
    return segment, markdown, journal, markdown_tmp, journal_tmp, marker


def _import_speaker(item: dict, my_key: str,
                    speaker_ids: dict[str, str]) -> tuple[str, str, str]:
    speaker_name = str(item.get("speaker") or "").strip()
    speaker_match = " ".join(speaker_name.casefold().split())
    role = "Я" if my_key and speaker_match == my_key else "Собеседник"
    speaker_key = speaker_name or "неизвестный участник"
    speaker_ids.setdefault(speaker_key, f"IMPORT_{len(speaker_ids) + 1:02d}")
    return speaker_name, role, speaker_ids[speaker_key]


def _write_import_journal(path: Path, utterances: list[dict], *, title: str,
                          provider: str, segment: int, my_key: str) -> dict[str, str]:
    transcript_events.create_journal(
        path, title=title or "импортированная встреча", provider=provider,
        segment=segment, started_at=dt.datetime.now().astimezone().isoformat(
            timespec="milliseconds"))
    speaker_ids: dict[str, str] = {}
    for item in utterances:
        speaker_name, role, speaker_id = _import_speaker(item, my_key, speaker_ids)
        transcript_events.append_event(
            path, role, item["text"], provider=provider,
            metadata={"start_ms": item["start_ms"], "end_ms": item["end_ms"],
                      "source": "import", "speaker_id": speaker_id,
                      "speaker_name": speaker_name or None,
                      "timing_source": provider})
    return speaker_ids


def _clear_import_files(journal_tmp: Path, markdown_tmp: Path, journal: Path,
                        marker: str, journal_committed: bool) -> None:
    journal_tmp.unlink(missing_ok=True)
    markdown_tmp.unlink(missing_ok=True)
    if journal_committed:
        return
    try:
        if journal.read_text(encoding="ascii") == marker:
            journal.unlink()
    except (OSError, UnicodeError):
        pass


def import_transcript(session: Path, name: str, content: str | bytes, *,
                      my_speaker: str = "", adapter: str = "auto") -> dict:
    """Импортировать файл новым сегментом, не перезаписывая результаты встречи."""
    session = Path(session).resolve()
    parsed = parse_adapter(name, content, adapter)
    format_name = f"{parsed['adapter'].replace('_', '-')}-{parsed['format']}"
    utterances = parsed["utterances"]
    provider = f"import:{format_name}"
    paths = _import_paths(session)
    segment, markdown, journal, markdown_tmp, journal_tmp, marker = paths
    my_key = " ".join(str(my_speaker or "").casefold().split())
    journal_committed = False
    try:
        speaker_ids = _write_import_journal(
            journal_tmp, utterances, title=_import_title(session),
            provider=provider, segment=segment, my_key=my_key)
        transcript_events.render_markdown(journal_tmp, markdown_tmp)
        os.replace(journal_tmp, journal)
        journal_committed = True
        os.replace(markdown_tmp, markdown)
    except Exception:
        _clear_import_files(journal_tmp, markdown_tmp, journal, marker,
                            journal_committed)
        raise
    return {"format": parsed["format"], "adapter": parsed["adapter"],
            "adapter_label": parsed["adapter_label"],
            "utterances": len(utterances), "speakers": list(speaker_ids),
            "segment": segment, "markdown": markdown.name, "journal": journal.name}
