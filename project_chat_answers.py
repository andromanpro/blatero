"""Explicit answer receipts. No model inference and no owner impersonation."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from project_store import Conflict, digest, identifier, now
from session_jsonl import message_span
from session_paths import codex_roots


def verify_message(source, quote, session_id):
    """Read a registered span in a connected Codex journal, never an arbitrary file."""
    if source['kind'] != 'source_span':
        raise ValueError('Нужен первичный фрагмент сообщения, не отчёт агента')
    filename, number = source['locator'].rsplit(':', 1)
    path, number = Path(filename).resolve(), int(number)
    if number < 1 or not any(path.is_relative_to((root/folder).resolve()) for root in codex_roots() for folder in ['sessions','archived_sessions']):
        raise ValueError('Сообщение вне подключённой истории Codex')
    if session_id not in path.name:
        raise ValueError('Источник принадлежит другому чату')
    raw, prefix_hash = message_span(path, number)
    event = json.loads(raw)
    if prefix_hash != source['snapshot_sha256']:
        raise ValueError('Исходное сообщение изменилось')
    payload = event.get('payload', {})
    if event.get('type') != 'response_item' or payload.get('type') != 'message' or payload.get('role') != 'user':
        raise ValueError('Источник должен быть сообщением пользователя')
    text = '\n'.join(b.get('text','') for b in payload.get('content',[]) if b.get('type') in {'input_text','text'})
    # UI question replies preserve the complete answer, including numbered mappings.
    if text.strip().startswith('<send_user_message_question_reply>'):
        packet = json.loads(text.split('>',1)[1].rsplit('</send_user_message_question_reply>',1)[0])
        answers = [item.get('answer') for item in packet]
    else:
        answers = [text.strip()]
    if quote not in answers:
        raise ValueError('Цитата не совпадает с полным ответом пользователя')
    return {'system':'codex','session_id':session_id,'locator':source['locator'],
            'reference_id':source['id'],'snapshot_sha256':source['snapshot_sha256'],
            'quote':quote,'message_at':event.get('timestamp')}


def record_answer(store, body, who, *, provenance=None):
    """CLI-only receipt: expensive source reads never happen in HTTP or hooks."""
    from project_provenance import context
    provenance = context(**provenance) if provenance is not None else None
    if who['role'] not in {'worker','owner'}:
        raise PermissionError('Запись ответа доступна рабочему агенту или владельцу')
    request_id = identifier(body.get('request_id'))
    identity = identifier(body.get('id'))
    task_id = identifier(body.get('work_item_id'))
    sid = identifier(body.get('session_id'))
    quote, answer = body.get('quote'), body.get('answer')
    for value in [quote, answer]:
        if not isinstance(value,str) or not value.strip() or len(value)>4000:
            raise ValueError('Нужен ответ и полная цитата: 1–4000 символов')
    key = 'daily.answer-request.' + request_id
    fingerprint = digest({'body':body,'actor_id':who['id']})
    with store.connect() as conn:
        prior = conn.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        source = conn.execute('SELECT * FROM sources WHERE id=? AND work_item_id=?',
                              (identifier(body.get('reference_id')),task_id)).fetchone()
    if prior:
        receipt = json.loads(prior[0])
        if receipt['fingerprint'] != fingerprint:
            raise Conflict('Идентификатор записи уже использован с другим содержимым',receipt['result'])
        return receipt['result']
    if not source:
        raise ValueError('Зарегистрируйте источник в этой карточке')
    origin = verify_message(dict(source), quote, sid)
    with store.transaction() as conn:
        # Another process may have delivered this exact request during source reading.
        prior = conn.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        if prior:
            receipt=json.loads(prior[0])
            if receipt['fingerprint']!=fingerprint:
                raise Conflict('Конфликт повторной записи',receipt['result'])
            return receipt['result']
        task = store.task(task_id,conn)
        if type(body.get('revision')) is not int or task['revision']!=body['revision'] or task['merged_into']:
            raise Conflict('Карточка изменилась; перечитайте контекст',task)
        row=conn.execute('SELECT * FROM daily_decisions WHERE id=? AND work_item_id=?',(identity,task_id)).fetchone()
        if not row:
            raise ValueError('Вопрос не найден в этой карточке')
        decision=dict(row)
        if type(body.get('decision_revision')) is not int or decision['revision']!=body['decision_revision'] or decision['state']!='open':
            raise Conflict('На вопрос уже ответили или он изменился',decision)
        if body.get('question')!=decision['question']:
            raise Conflict('Текст вопроса изменился',decision)
        if not origin['message_at'] or dt.datetime.fromisoformat(origin['message_at'].replace('Z','+00:00')) < dt.datetime.fromisoformat(decision['requested_at']):
            raise ValueError('Сообщение должно быть получено после вопроса')
        source_now=conn.execute('SELECT * FROM sources WHERE id=?',(source['id'],)).fetchone()
        if dict(source_now)!=dict(source):
            raise Conflict('Ссылка на источник изменилась',decision)
        stamp=now()
        result={**decision,'state':'answered','answer':answer.strip(),'resolved_at':stamp,'resolved_by':who['id'],'revision':decision['revision']+1}
        origin.update(recorded_by=who['id'],recorded_at=stamp,request_id=request_id)
        if provenance is not None:
            # The quoted user's session stays in origin.session_id. This is the
            # separate provenance of the agent recording that user's answer.
            origin['recording_provenance'] = provenance
        conn.execute("UPDATE daily_decisions SET state='answered',answer=?,resolved_at=?,resolved_by=?,revision=? WHERE id=?",
                     (result['answer'],stamp,who['id'],result['revision'],identity))
        conn.execute('UPDATE tasks SET revision=revision+1,updated_at=?,updated_by=? WHERE id=?',(stamp,who['id'],task_id))
        result['origin']=origin
        conn.execute('INSERT INTO settings VALUES (?,?)',('daily.answer.'+identity,json.dumps(origin,ensure_ascii=False)))
        conn.execute('INSERT INTO settings VALUES (?,?)',(key,json.dumps({'fingerprint':fingerprint,'result':result},ensure_ascii=False)))
        return result


def with_origins(conn, decisions):
    from project_provenance import read
    for decision in decisions:
        provenance = read(conn, "decision-request", decision['id'])
        if provenance is not None:
            decision['provenance'] = provenance
        row=conn.execute('SELECT value FROM settings WHERE key=?',('daily.answer.'+decision['id'],)).fetchone()
        if row:
            decision['origin']=json.loads(row[0])
    return decisions
