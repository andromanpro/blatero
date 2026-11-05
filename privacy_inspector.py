"""Локальное обнаружение ПД в подготовке материалов. Никаких сетевых вызовов."""
from __future__ import annotations

from collections import Counter
import re
import threading
import time

import privacy

MAX_CHARS = 240_000
MAX_FINDINGS = 4000
_NER_LOCK = threading.Lock()
_NER = None
_PLACEHOLDER = re.compile(r"\[[A-Z_]+(?:_\d+)?\]")
_EMAIL = re.compile(r"[\w.+-]{1,128}@[\w-]{1,100}(?:\.[\w-]{1,60}){1,5}")
_STREET = re.compile(
    r"(?i)\b(?:улиц[аыеу]|ул\.|проспект|пр-т|переулок|пер\.)[ \t]+"
    r"[^\n;.!?]{2,100}?(?:дом|д\.)[ \t]*\d+[а-яa-z]?(?:[ /-]\d+)?"
    r"(?:[, \t]+(?:квартира|кв\.)[ \t]*\d+)?")


def _ner_spans(text: str):
    global _NER
    # Model + embeddings are packaged in the installed wheel, not downloaded
    # while inspecting user documents. MorphVocab/pymorphy2 is not needed.
    with _NER_LOCK:
        try:
            from natasha import Doc, NewsEmbedding, NewsNERTagger, Segmenter
            if _NER is None:
                _NER = (Segmenter(), NewsNERTagger(NewsEmbedding()))
            segmenter, tagger = _NER
            deadline = time.monotonic() + 45
            for offset in range(0, len(text), 5500):
                if time.monotonic() > deadline:
                    raise ValueError("локальная проверка ПД не уложилась в лимит; уменьшите объём материалов")
                doc = Doc(text[offset:offset + 6000])
                doc.segment(segmenter)
                doc.tag_ner(tagger)
                for span in doc.spans:
                    kind = {"PER": "PERSON", "LOC": "LOCATION", "ORG": "ORGANIZATION"}.get(span.type)
                    if kind:
                        yield offset + span.start, offset + span.stop, kind
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("локальный детектор ПД недоступен; восстановите зависимости Blatero. Отправка заблокирована") from exc


def inspect(text: str, custom: list[str] | None = None,
            filenames: list[str] | None = None) -> dict:
    """Спаны/замены предназначены только для локального экрана проверки."""
    if not isinstance(text, str) or len(text) > MAX_CHARS:
        raise ValueError("слишком большой текст для проверки ПД")
    custom = list(custom or [])
    if len(custom) > 100 or any(not isinstance(x, str) or not 2 <= len(x) <= 300 for x in custom):
        raise ValueError("укажите до 100 скрываемых фрагментов, от 2 до 300 символов каждый")
    spans = list(_ner_spans(text))
    import workspace_context
    spans.extend((m.start("value"), m.end("value"), "SECRET")
                 for m in workspace_context.SECRET_ASSIGNMENT_RE.finditer(text))
    for pattern in (workspace_context.TOKEN_RE, *workspace_context.RAW_SECRET_PATTERNS):
        spans.extend((m.start(), m.end(), "SECRET") for m in pattern.finditer(text))
    spans.extend((m.start(), m.end(), "LOCAL_PATH")
                 for m in workspace_context.LOCAL_PATH_RE.finditer(text))
    for kind, pattern in privacy._PATTERNS:
        spans.extend((m.start(), m.end(), kind) for m in pattern.finditer(text))
    for kind, pattern in (("IDENTITY", privacy._LABELLED), ("PERSON", privacy._MEETING_NAME),
                          ("ADDRESS", privacy._ADDRESS)):
        spans.extend((m.start("value"), m.end("value"), kind) for m in pattern.finditer(text))
    for kind, pattern in (("EMAIL", _EMAIL), ("ADDRESS", _STREET)):
        spans.extend((m.start(), m.end(), kind) for m in pattern.finditer(text))
    for value in custom:
        spans.extend((m.start(), m.end(), "CUSTOM")
                     for m in re.finditer(re.escape(value), text, flags=re.I))
    # A name embedded in Ivan_Petrov.docx may not be recognized as a person.
    # Replace file references regardless of the NER decision.
    for value in set(filenames or []):
        if value:
            spans.extend((m.start(), m.end(), "FILE")
                         for m in re.finditer(re.escape(value), text, flags=re.I))
    placeholders = [(m.start(), m.end()) for m in _PLACEHOLDER.finditer(text)]
    # Do not reinterpret existing pseudonyms as names or labelled identities.
    spans = sorted(set((a, b, k) for a, b, k in spans
                       if not any(start <= a and b <= stop for start, stop in placeholders)))
    if len(spans) > MAX_FINDINGS:
        raise ValueError("слишком много подозрительных фрагментов; уменьшите объём материалов")
    merged = []
    for start, stop, kind in spans:
        if merged and start < merged[-1][1]:
            old_start, old_stop, old_kind = merged[-1]
            merged[-1] = (old_start, max(stop, old_stop), old_kind if old_stop >= stop else kind)
        else:
            merged.append((start, stop, kind))
    aliases, counts, findings, chunks = {}, Counter(), [], []
    cursor = 0
    for start, stop, kind in merged:
        value = text[start:stop]
        key = (kind, value.casefold())
        if key not in aliases:
            counts[kind] += 1
            aliases[key] = f"[{kind}_{counts[kind]}]"
        alias = aliases[key]
        chunks.extend((text[cursor:start], alias))
        findings.append({"start": start, "end": stop, "kind": kind,
                         "value": value, "replacement": alias})
        cursor = stop
    chunks.append(text[cursor:])
    return {"text": "".join(chunks), "findings": findings,
            "counts": dict(Counter(item["kind"] for item in findings)),
            "detector": "Natasha (русский) + правила", "complete": True}
