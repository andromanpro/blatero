"""Conservative extraction of explicitly stated methods from historic prose."""
from __future__ import annotations

import re

METHOD = re.compile(r'(?i)(?:\b(?:подход|способ|метод решения)\s*[:—-]|'
                    r'\b(?:выбрали|выбран[аоы]?|выбираем|используем|будем использовать|решили использовать)\b)')
FORMAT = re.compile(r'(?i)(межстрочн|колонтитул|перенос.*абзац|верстк|вёрстк|оформлен|\bword\b|\bdocx\b)')
DOCUMENT_TASK = re.compile(r'(?i)(документ|инструкци|отч[её]т|word|docx|презентац|стать[яюьи]|редактур|верстк|вёрстк)')
CHOICE_REASON = re.compile(r'(?i)(причина выбора|выбра[лн].*(?:потому|чтобы)|потому что|так как)')


def explicit_method(text: str, purpose: str = '') -> str:
    candidates = []
    for line in re.split(r'\n+|(?<=[.!?])\s+', text):
        line = line.strip(' #*')
        if not METHOD.search(line):
            continue
        if FORMAT.search(line) and not DOCUMENT_TASK.search(purpose):
            continue
        if len(line) < 20 or line.endswith(':'):
            continue
        candidates.append(line)
    return '\n'.join(candidates[:3])[:1000]


def explicit_rationale(text: str) -> str:
    candidates = [line.strip(' #*') for line in re.split(r'\n+|(?<=[.!?])\s+', text)
                  if CHOICE_REASON.search(line) and len(line.strip()) > 25]
    return '\n'.join(candidates[:2])[:700]
