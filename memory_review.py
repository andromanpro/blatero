"""Explicit post-report review. Local suggestions, shared memory store, no LLM calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import uuid

from markdown_it import MarkdownIt

import meeting_memory as memory

MAX_REPORT_BYTES = 2_000_000


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _report(sdir):
    path = Path(sdir) / 'report.md'
    if not path.is_file():
        return '', ''
    if path.is_symlink() or path.resolve().parent != Path(sdir).resolve():
        raise ValueError('Отчёт не может быть ссылкой за пределы встречи')
    with path.open('rb') as source:
        raw = source.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError('Отчёт слишком большой для разбора памяти')
    return raw.decode('utf-8-sig'), _digest(raw)


def _draft(sdir):
    path = Path(sdir) / memory.DRAFT_FILE
    if not path.exists():
        return {}, ''
    if path.is_symlink() or path.resolve().parent != Path(sdir).resolve():
        raise ValueError('Черновик памяти не может быть ссылкой')
    with path.open('rb') as source:
        raw = source.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Черновик памяти слишком большой')
    value = json.loads(raw)
    if not isinstance(value, dict) or not isinstance(value.get('entries', []), list):
        raise ValueError('Черновик памяти повреждён; он не перезаписан')
    return value, _digest(raw)


def _scope_stamp(sdir):
    store = memory._read_store()
    refs = [memory._resolved_ref(store, ref) for ref in memory.references(sdir)]
    return _digest(json.dumps([(r['scope'], r['key']) for r in refs], sort_keys=True).encode())


def summary(sdir):
    text, source_hash = _report(sdir)
    draft, revision = _draft(sdir)
    entries = draft.get('entries', [])
    receipt = draft.get('review', {})
    source_changed = bool(draft.get('report_sha256') and draft['report_sha256'] != source_hash)
    scope_changed = bool(draft.get('scope_stamp') and draft['scope_stamp'] != _scope_stamp(sdir))
    status = ('test' if memory._meta(sdir).get('contour', 'work') != 'work'
              else 'no_report' if not text else 'needs_scope' if not memory.references(sdir)
              else 'stale' if source_changed or scope_changed
              else 'pending' if entries
              else 'reviewed' if receipt.get('report_sha256') == source_hash
              else 'empty' if draft.get('report_sha256') == source_hash
              else 'not_prepared')
    return {'status':status, 'pending_count':len(entries), 'saved_count':receipt.get('saved_count', 0),
            'duplicates':receipt.get('duplicates',0),
            'report_sha256':source_hash, 'draft_revision':revision, 'scope_stamp':_scope_stamp(sdir),
            'legacy_draft':bool(entries and not draft.get('report_sha256')),
            'can_confirm':status == 'pending', 'local_only':True}


def payload(sdir):
    return {**memory.payload(sdir), 'review':summary(sdir), 'session':Path(sdir).name}


def _plain(token):
    return ''.join(child.content for child in (token.children or [])
                   if child.type in {'text','code_inline','softbreak','hardbreak'}).strip() or token.content


def _kind(heading):
    if re.search(r'открыт.*вопрос|уточнен|уточнён|неопредел', heading, re.I):
        return 'open_question'
    if re.search(r'действи|следующ|поручени|дальнейш', heading, re.I):
        return 'commitment'
    if re.search(r'решени|договор', heading, re.I):
        return 'decision'
    return ''


def local_proposals(markdown, refs):
    """Extract only explicit action/decision/question sections, retaining evidence."""
    tokens = MarkdownIt('commonmark', {'html':False}).enable('table').parse(markdown)
    scope = 'project' if any(r['scope'] == 'project' for r in refs) else 'client'
    proposals = []
    section_kind = ''
    section_depth = 0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type == 'heading_open':
            depth = int(token.tag[1:])
            kind = _kind(tokens[index + 1].content)
            if kind:
                section_kind, section_depth = kind, depth
            elif depth <= section_depth:
                section_kind = ''
        elif section_kind and token.type == 'table_open':
            rows, cells = [], []
            index += 1
            while index < len(tokens) and tokens[index].type != 'table_close':
                part = tokens[index]
                if part.type == 'tr_open':
                    cells = []
                elif part.type == 'inline':
                    cells.append(_plain(part))
                elif part.type == 'tr_close':
                    rows.append(cells)
                index += 1
            if rows:
                headers = rows[0]
                def column(pattern):
                    return next((i for i,h in enumerate(headers) if re.search(pattern, h, re.I)), None)
                text_col = column(r'действ|решени|договор|вопрос|задач|что.*сделать|шаг')
                owner_col, due_col = column(r'ответствен|владелец|исполнител'), column(r'срок|услови|когда')
                if text_col is not None:
                    for row in rows[1:]:
                        cell = lambda col: row[col] if col is not None and col < len(row) else ''  # noqa: E731
                        owner, due = cell(owner_col), cell(due_col)
                        if re.search(r'не назван|не определ|не установлен|не указан', owner, re.I):
                            owner = ''
                        if re.fullmatch(r'(?:срок\s+)?не (?:назван|определ[её]н|указан)|без срока|[—-]', due, re.I):
                            due = ''
                        proposals.append({'scope':scope,'kind':section_kind,'text':cell(text_col),
                                          'owner':owner,'due':due,'evidence':' | '.join(f'{h}: {v}' for h,v in zip(headers,row))})
        elif section_kind and token.type == 'paragraph_open' and index + 1 < len(tokens):
            inline = tokens[index + 1]
            if inline.type == 'inline':
                text = _plain(inline)
                proposals.append({'scope':scope,'kind':section_kind,'text':text,'evidence':text})
        index += 1
    return memory._normalize_proposals({'entries':proposals}, {r['scope'] for r in refs})


def prepare(sdir):
    with memory._LOCK:
        _recover_review(sdir)
        info = summary(sdir)
        if info['status'] in {'test','no_report','needs_scope'}:
            raise ValueError('Нужны рабочая встреча, итоговый отчёт и выбранный проект/клиент')
        draft, _ = _draft(sdir)
        # Never overwrite a legacy, edited, stale or already reviewed draft.
        if draft.get('entries') or info['status'] in {'reviewed','empty','stale'}:
            return payload(sdir)
        text, source_hash = _report(sdir)
        value = {'schema_version':2, 'created_at':memory._now(), 'source_session':Path(sdir).name,
                 'report_sha256':source_hash, 'scope_stamp':_scope_stamp(sdir), 'extractor':'local_sections',
                 'entries':local_proposals(text, memory.references(sdir))}
        memory._atomic_json(Path(sdir) / memory.DRAFT_FILE, value)
        return payload(sdir)


def _validate(sdir, body, draft, *, allow_empty=False):
    info = summary(sdir)
    if info['status'] in {'test','no_report','needs_scope','stale'}:
        raise ValueError('Отчёт или проект изменились. Проверьте источники и обновите предложения.')
    for key in ('draft_revision','report_sha256','scope_stamp'):
        if not body.get(key) or body[key] != info[key]:
            raise ValueError('Данные изменились в другой вкладке. Откройте проверку заново; память не изменена.')
    if not draft.get('entries') and not (allow_empty and info['status'] == 'empty'):
        raise ValueError('Нет предложений для подтверждения')


def _finish_review(sdir, draft, request_id, saved):
    draft['report_sha256'] = saved['report_sha256']
    draft['scope_stamp'] = saved['scope_stamp']
    draft['entries'] = [e for e in draft['entries'] if e['id'] not in saved['proposal_ids']]
    receipt = draft.get('review', {})
    draft['review'] = {'report_sha256':saved['report_sha256'], 'saved_at':memory._now(),
                       'saved_count':int(receipt.get('saved_count',0)) + saved['added'],
                       'duplicates':int(receipt.get('duplicates',0)) + saved['duplicates']}
    draft.setdefault('receipts', {})[request_id] = saved['hash']
    draft['receipts'] = dict(list(draft['receipts'].items())[-30:])
    memory._atomic_json(Path(sdir) / memory.DRAFT_FILE, draft)


def _recover_review(sdir):
    store = memory._read_store()
    for identity, saved in list(store["pending_reviews"].items()):
        if saved["session"] != str(Path(sdir).resolve()):
            continue
        draft, revision = _draft(sdir)
        previous = draft.get('receipts', {}).get(identity)
        if previous != saved['hash']:
            if revision != saved['draft_revision']:
                raise ValueError('Память уже сохранена, но черновик изменился. Нужна проверка сохранённой операции.')
            _finish_review(sdir, draft, identity, saved)
        store["pending_reviews"].pop(identity)
        try:
            memory._write_store(store)
        except OSError:
            pass  # A matching draft receipt makes housekeeping safe to retry.


def confirm(sdir, body):
    with memory._LOCK:
        request_id = str(uuid.UUID(str(body.get('request_id', ''))))
        command_hash = _digest(json.dumps(body, sort_keys=True, ensure_ascii=False).encode())
        pending = memory._read_store()["pending_reviews"].get(request_id)
        if pending and (pending["hash"] != command_hash or pending["session"] != str(Path(sdir).resolve())):
            raise ValueError('Этот запрос уже использован с другими данными')
        _recover_review(sdir)
        draft, _ = _draft(sdir)
        previous = draft.get('receipts', {}).get(request_id)
        if previous:
            if previous != command_hash:
                raise ValueError('Этот запрос уже использован с другими данными')
            return payload(sdir)
        _validate(sdir, body, draft)
        edits = body.get('entries')
        if not isinstance(edits, list) or not 1 <= len(edits) <= 20:
            raise ValueError('Выберите от 1 до 20 пунктов для подтверждения')
        available = {e['id']:e for e in draft['entries']}
        seen, proposals = set(), []
        for edit in edits:
            if not isinstance(edit, dict) or edit.get('id') not in available or edit['id'] in seen:
                raise ValueError('Пункт отсутствует в текущем черновике')
            seen.add(edit['id'])
            source = available[edit['id']]
            proposals.append({**source, **{k:edit.get(k, source.get(k,'')) for k in ('scope','kind','text','owner','due')}})
        operation = {**{key:body[key] for key in ('report_sha256','scope_stamp','draft_revision')},
                     'hash':command_hash, 'proposal_ids':sorted(seen)}
        memory.accept_proposals(sdir, proposals, receipt=(request_id, operation))
        _recover_review(sdir)
        return payload(sdir)


def reject(sdir, body):
    with memory._LOCK:
        _recover_review(sdir)
        draft, _ = _draft(sdir)
        _validate(sdir, body, draft, allow_empty=True)
        draft['entries'] = []
        draft['review'] = {**draft.get('review',{}), 'report_sha256':body['report_sha256'],
                           'rejected_at':memory._now(), 'saved_count':draft.get('review',{}).get('saved_count',0)}
        memory._atomic_json(Path(sdir) / memory.DRAFT_FILE, draft)
        return payload(sdir)


def rebuild(sdir, body):
    """Explicit replacement, preserving the complete old draft as a backup."""
    with memory._LOCK:
        _recover_review(sdir)
        info = summary(sdir)
        if info['status'] in {'test','no_report','needs_scope'}:
            raise ValueError('Нужны рабочая встреча, итоговый отчёт и проект')
        if any(body.get(k) != info[k] for k in ('draft_revision','report_sha256','scope_stamp')):
            raise ValueError('Источники изменились. Обновите проверку перед пересборкой.')
        path = Path(sdir) / memory.DRAFT_FILE
        old, _ = _draft(sdir)
        if old:
            with path.with_name('memory-draft.previous-' + uuid.uuid4().hex + '.json').open('xb') as backup:
                backup.write(path.read_bytes())
        text, source_hash = _report(sdir)
        memory._atomic_json(path, {'schema_version':2,'source_session':Path(sdir).name,
            'created_at':memory._now(), 'report_sha256':source_hash,'scope_stamp':_scope_stamp(sdir),
            'extractor':'local_sections','entries':local_proposals(text,memory.references(sdir))})
        return payload(sdir)
