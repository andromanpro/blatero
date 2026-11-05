"""Apply a reviewed initial-import manifest with provenance and durable identities.

Only adds initial cards/evidence. Never overwrites subsequent human or agent edits.
Session history is evidence, not an artificial native session start or acceptance.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import sqlite3
import sys
import uuid
from pathlib import Path

from project_contract import canonical
from project_store import Store, digest, make_event, now


def stable_id(scope: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'blatero:initial-import:' + scope))


def validate_manifest(manifest: dict) -> None:
    if manifest.get('schema_version') != 1:
        raise ValueError('неверная версия импорта')
    projects = {p['key']: p for p in manifest['projects']}
    tasks = {t['key']: t for t in manifest['tasks']}
    if len(projects) != len(manifest['projects']) or len(tasks) != len(manifest['tasks']):
        raise ValueError('повторный ключ проекта/задачи')
    for p in projects.values():
        if not isinstance(p['name'], str) or not p['name'].strip() or len(p['name']) > 160:
            raise ValueError('неверное имя проекта')
        if p.get('workspace') and not Path(p['workspace']).is_dir():
            raise ValueError('рабочая папка не найдена: ' + p['workspace'])
    for t in tasks.values():
        if t.get('project_key') and t['project_key'] not in projects:
            raise ValueError('неизвестный проект задачи')
        if not t['title'].strip() or len(t['title']) > 240 or not t.get('sources'):
            raise ValueError('задаче нужны название и источник')
        if t.get('status', 'inbox') not in {'inbox', 'active', 'waiting', 'review'}:
            raise ValueError('импорт не может принимать результат за пользователя')
        for source in t['sources']:
            if len(source['snapshot_sha256']) != 64 or any(c not in '0123456789abcdef' for c in source['snapshot_sha256']):
                raise ValueError('неверная сумма источника')
        for key in ('goal', 'method', 'rationale', 'next_step'):
            limit = 4000 if key == 'goal' else 2000
            if not isinstance(t.get(key, ''), str) or len(t.get(key, '')) > limit:
                raise ValueError('слишком длинное поле: ' + key)
    seen = set()
    for s in manifest['sessions']:
        key = (s['system'], s['id'])
        if key in seen:
            raise ValueError('повтор сессии в импорте')
        seen.add(key)
        if s.get('task_key') and s['task_key'] not in tasks:
            raise ValueError('неизвестная задача сессии')
        if s.get('project_key') and s['project_key'] not in projects:
            raise ValueError('неизвестный проект сессии')
        if dt.datetime.fromisoformat(s['activity_at'].replace('Z', '+00:00')).tzinfo is None:
            raise ValueError('нет часового пояса')


def backup(store: Store) -> Path:
    folder = store.root / 'backups'
    folder.mkdir(exist_ok=True)
    path = folder / ('before-initial-import-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8] + '.sqlite3')
    with store.connect() as source, contextlib.closing(sqlite3.connect(path)) as target:
        source.backup(target)
    return path


def apply_manifest(store: Store, manifest: dict) -> dict:
    validate_manifest(manifest)
    snapshot = backup(store)
    actor, _ = store.local_agent('initial-import')
    stamp = now()
    projects, tasks = {}, {}
    result = {'added_tasks': 0, 'existing_tasks': 0, 'sources': 0, 'knowledge': 0,
              'linked_sessions': 0, 'unbound_sessions': 0, 'backup': str(snapshot)}
    for project in manifest['projects']:
        previous = [p for p in store.projects() if not project.get('workspace') and p['name'] == project['name'] and not p['workspace']]
        if len(previous) > 1:
            raise ValueError('неоднозначное имя проекта без рабочей папки')
        projects[project['key']] = previous[0] if previous else store.create_project(project['name'], project.get('workspace', ''), project.get('description', ''))
        with store.transaction() as conn:
            for doc in project.get('sources', []):
                conn.execute('INSERT INTO project_documents VALUES (?,?,?,?) ON CONFLICT(project_id,locator) DO NOTHING',
                             (projects[project['key']]['id'], doc['path'], Path(doc['path']).name, doc['sha256']))
    for entry in manifest['tasks']:
        task_id = entry.get('existing_id') or stable_id(entry['key'])
        try:
            task = store.task(task_id)
            fresh = False
            result['existing_tasks'] += 1
        except ValueError:
            task = {'id': task_id, 'project_id': projects[entry['project_key']]['id'] if entry.get('project_key') else None}
            event = make_event(task, actor, 'task.created', {'title': entry['title'], 'goal': entry.get('goal', ''), 'initial_status': 'inbox'},
                               system='initial-import', session_id=entry['key'][:160], event_id='import:create:' + task_id)
            applied = store.apply(event, actor)
            if applied['state'] != 'applied':
                raise ValueError(applied)
            task = applied['task']
            fresh = True
            result['added_tasks'] += 1
            patch = {k: entry[k] for k in ('method', 'rationale', 'next_step') if entry.get(k)}
            if patch:
                applied = store.apply(make_event(task, actor, 'task.updated', {'patch': patch}, system='initial-import',
                                                 session_id=entry['key'][:160], event_id='import:context:' + task_id), actor)
                if applied['state'] != 'applied':
                    raise ValueError(applied)
                task = applied['task']
            if entry.get('status', 'inbox') != 'inbox':
                task = store.apply(make_event(task, actor, 'task.status_changed', {
                    'from': 'inbox', 'to': entry['status'], 'reason': entry.get('status_reason', 'Предварительное состояние по исторической сессии; требует сверки.')},
                    system='initial-import', session_id=entry['key'][:160], event_id='import:status:' + task_id), actor)['task']
        tasks[entry['key']] = task
        existing = store.detail(task_id)['sources']
        for source in entry['sources']:
            found = next((s for s in existing if s['locator'] == source['locator'] and s['snapshot_sha256'] == source['snapshot_sha256']), None)
            if found is None:
                found = store.add_source(task_id, source.get('kind', 'source_span'), source['label'], source['locator'], source['snapshot_sha256'],
                                         allow_missing_journal=True)
                existing.append(found)
                result['sources'] += 1
            # Imported excerpts always remain proposals and clearly name their origin.
            for proposal in source.get('knowledge', []) if fresh else []:
                event = make_event(task, actor, 'knowledge.proposed', {'kind': proposal.get('kind', 'decision'),
                                   'text': proposal['text'], 'state': 'draft'}, system='initial-import', session_id=entry['key'][:160],
                                   references=[store.source_reference(found)], event_id='import:knowledge:' + digest({'task': task_id, 'source': found['id'], 'proposal': proposal}))
                applied = store.apply(event, actor)
                if applied['state'] != 'applied':
                    raise ValueError(applied)
                result['knowledge'] += 1
    with store.transaction() as conn:
        for session in manifest['sessions']:
            task = tasks.get(session.get('task_key'))
            project = projects.get(session.get('project_key'))
            conn.execute('INSERT INTO imported_sessions(system,session_id,work_item_id,project_id,source,snapshot_sha256,activity_at,classification,imported_at,title) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(system,session_id) DO NOTHING',
                         (session['system'], session['id'], task['id'] if task else None, project['id'] if project else None,
                          session['source'], session['snapshot_sha256'], session['activity_at'], session['classification'], stamp, session.get('title', '')))
            result['linked_sessions' if task else 'unbound_sessions'] += 1
        summary = manifest.get('coverage', {}) | {'imported_at': stamp, 'projects': len(projects), 'tasks': len(tasks),
                                               'linked_sessions': result['linked_sessions'], 'unbound_sessions': result['unbound_sessions']}
        conn.execute("INSERT INTO settings VALUES ('initial-import-summary',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (canonical(summary),))
    result['history_links'] = store.reconcile_history()
    return result


def main():
    parser = argparse.ArgumentParser(description='Первоначальный импорт сессий и проектов Blatero')
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    validate_manifest(manifest)
    if args.dry_run:
        print(json.dumps({'projects': len(manifest['projects']), 'tasks': len(manifest['tasks']), 'sessions': len(manifest['sessions'])}, ensure_ascii=False))
        return
    print(json.dumps(apply_manifest(Store(args.data_root), manifest), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
