"""Read-only local session inventory for initial import. No model/network calls.

Every available conversation message is parsed; compact excerpts retain line IDs.
Technical runs are catalogued as supporting work, not automatically separate tasks.
Never collect tool arguments/results, reasoning, model config or authentication data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from session_paths import codex_roots

ROOT = Path(__file__).parent
WORKAI = ROOT.parent
SECRET = re.compile(r'(?i)(?:\b(?:sk-|ghp_|github_pat_|gitea_|xox[baprs]-)[A-Za-z0-9_\-]{15,}|'
                    r'\b(?:api[_ -]?key|access[_ -]?token|authorization|password|пароль|токен)\s*[:=]\s*["\']?[^\s"\',;]{8,})')
INJECTED = ('# AGENTS.md instructions', '<external_codex_apps_open_page>', '<environment_context>', '<recommended_plugins>',
            '<user_instructions>', '<INSTRUCTIONS>', '<turn_aborted>', '<system-reminder>',
            '<local-command-caveat>', '<local-command-stdout>', '<command-name>', 'This session is being continued from')
TERMS = re.compile(r'(?i)(метод|выбра[лн]|потому|причин|решени|подход|провер|следующ|готов|сдела|исправ|не реализ|жд[её]м|блокир|дальше|остал|результат|поставка|deploy|decision|implemented|verified|next step|test)')


def redact(text: str) -> str:
    return SECRET.sub('[секрет скрыт]', text)


def clean(text: str) -> str:
    text = re.sub(r'<in-app-browser-context\b[^>]*>.*?</in-app-browser-context>', '', text, flags=re.S).strip()
    text = re.sub(r'^## My request:\s*', '', text)
    return text


def excerpt(text: str, limit: int = 1200) -> str:
    text = redact(text)
    if len(text) <= limit:
        return text
    # Head + distinct useful sentences: a compact preview, not a semantic summary.
    sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
    selected = text[:limit // 2]
    for sentence in sentences:
        if TERMS.search(sentence) and sentence[:80] not in selected:
            selected += '\n' + sentence[:300]
            if len(selected) >= limit:
                break
    return selected[:limit] + ' […]'


def text_content(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return '\n'.join(v.get('text', '') for v in value if isinstance(v, dict)
                         and v.get('type') in {'text', 'input_text', 'output_text'} and isinstance(v.get('text'), str))
    return ''


def ro(path: Path):
    conn = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def add_message(record: dict, role: str, text: str, location: str, stamp=None):
    text = clean(text)
    if not text or (role == 'user' and text.startswith(INJECTED)):
        return
    record['message_count'][role] += 1
    record['text_chars'] += len(text)
    entry = {'role': role, 'location': location, 'timestamp': stamp, 'excerpt': excerpt(text)}
    # Retain all human prompts and final assistant text as bounded previews.
    record['messages'].append(entry)
    record['tickets'].update(re.findall(r'\b(?:ITWMS|ITWMST|BHK|WMS)-\d{2,6}\b', text, re.I))
    record['paths'].update(re.findall(r'(?i)(?:F:|F\\:)[/\\]WorkAI[/\\]([^\s/\\"\'<>;,]+)', text))


def codex_catalog(home: Path, output: Path, conversations_only=False):
    import contextlib
    from session_jsonl import canonical, session_files
    with contextlib.closing(ro(home / 'state_5.sqlite')) as conn:
        rows = [dict(row) for row in conn.execute('SELECT id,rollout_path,created_at,updated_at,source,cwd,title,archived,agent_role,thread_source FROM threads')]
        parents = {row['child_thread_id']: row['parent_thread_id'] for row in conn.execute('SELECT * FROM thread_spawn_edges')}
    lookup = {}
    for folder in (home / 'sessions', home / 'archived_sessions'):
        for path in session_files(folder):
            match = re.search(r'([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\.jsonl$', canonical(path).name, re.I)
            if match:
                if match[1] not in lookup or path.suffix == '.jsonl':
                    lookup[match[1]] = path
    seen = set()
    registered = {row['id'] for row in rows}
    for index, row in enumerate(rows, 1):
        path = Path(row['rollout_path'].removeprefix('\\\\?\\'))
        if canonical(path).is_file():
            path = canonical(path)
        if not path.is_file():
            path = lookup.get(row['id'], path)
        seen.add(path.resolve())
        record = new_record('codex', row['id'], str(path), row['cwd'], row['title'])
        record.update({'created_at': row['created_at'], 'updated_at': row['updated_at'], 'archived': bool(row['archived']),
                       'parent_id': parents.get(row['id']), 'technical': row['source'] not in {'vscode', 'cli', 'desktop'}})
        if conversations_only and record['technical']:
            continue
        read_codex(path, record)
        write_record(output, record)
        if index % 100 == 0:
            print(f'Codex {index}/{len(rows)}', flush=True)
    for sid, path in lookup.items():
        if path.resolve() in seen or sid in registered:
            continue
        record = new_record('codex', sid, str(path), '', '')
        read_codex(path, record)
        write_record(output, record)


def new_record(system, sid, source, cwd='', title=''):
    return {'system': system, 'id': sid, 'source': source, 'cwd': cwd or '', 'title': title or '',
            'technical': False, 'parent_id': None, 'message_count': Counter(), 'text_chars': 0,
            'messages': [], 'tickets': set(), 'paths': set(), 'errors': [], 'sha256': '', 'stable': True}


def read_codex(path: Path, record: dict):
    from session_jsonl import open_jsonl
    try:
        before = path.stat()
        sha = hashlib.sha256()
        with open_jsonl(path) as stream:
            for number, raw in enumerate(stream, 1):
                sha.update(raw)
                # Filter accounting/tool blobs before decoding JSON; still hash every byte.
                if b'"role"' not in raw and b'"session_meta"' not in raw:
                    continue
                try:
                    event = json.loads(raw)
                    payload = event.get('payload', {})
                    if event.get('type') == 'session_meta':
                        record['cwd'] = record['cwd'] or payload.get('cwd', '')
                        record['technical'] = record['technical'] or payload.get('source') == 'exec' or isinstance(payload.get('source'), dict)
                    if event.get('type') != 'response_item' or payload.get('type') != 'message':
                        continue
                    role = payload.get('role')
                    if role not in {'user', 'assistant'} or (role == 'assistant' and payload.get('channel') == 'analysis'):
                        continue
                    add_message(record, role, text_content(payload.get('content')), f'{path}:{number}', event.get('timestamp'))
                except (ValueError, TypeError):
                    record['errors'].append(f'line {number}: invalid JSON')
        record['sha256'] = sha.hexdigest()
        after = path.stat()
        record['stable'] = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
        record['bytes'] = before.st_size
    except (OSError, ValueError) as exc:
        record['errors'].append(str(exc))
        record['stable'] = False


def claude_catalog(home: Path, output: Path, conversations_only=False):
    from session_jsonl import canonical, session_files, open_jsonl
    paths = session_files(home)
    support = []
    for index, path in enumerate(paths, 1):
        record = new_record('claude-code', canonical(path).stem, str(path))
        record['technical'] = 'subagents' in path.parts or canonical(path).stem.startswith('agent-')
        if canonical(path).name == 'journal.jsonl' and 'workflows' in path.parts:
            support.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'kind': 'workflow_journal'})
            continue
        if conversations_only and record['technical']:
            continue
        if 'subagents' in path.parts:
            record['parent_id'] = path.parent.parent.name
        try:
            before = path.stat()
            sha = hashlib.sha256()
            with open_jsonl(path) as stream:
                for number, raw in enumerate(stream, 1):
                    sha.update(raw)
                    try:
                        event = json.loads(raw)
                        record['cwd'] = record['cwd'] or event.get('cwd', '')
                        if event.get('type') == 'summary' and not record['title']:
                            record['title'] = event.get('summary', '')
                        if event.get('isCompactSummary'):
                            continue
                        if event.get('type') not in {'user', 'assistant'}:
                            continue
                        message = event.get('message', {})
                        add_message(record, event['type'], text_content(message.get('content')), f'{path}:{number}', event.get('timestamp'))
                    except (ValueError, TypeError):
                        record['errors'].append(f'line {number}: invalid JSON')
            record['sha256'] = sha.hexdigest()
            after = path.stat()
            record.update({'stable': (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
                           'bytes': before.st_size, 'updated_at': before.st_mtime})
        except (OSError, ValueError) as exc:
            record['errors'].append(str(exc))
            record['stable'] = False
        write_record(output, record)
        if index % 50 == 0:
            print(f'Claude {index}/{len(paths)}', flush=True)
    (output / 'support-files.json').write_text(json.dumps(support, ensure_ascii=False, indent=2), encoding='utf-8')
    journal = output / 'sessions/claude-code' / (hashlib.sha256(b'journal').hexdigest()[:24] + '.json')
    journal.unlink(missing_ok=True)


def sqlite_catalog(path: Path, system: str, output: Path):
    if not path.exists():
        return
    with ro(path) as conn:
        if system == 'hermes':
            rows = conn.execute('SELECT id,title,source,cwd,parent_session_id,started_at,last_activity_at,archived FROM sessions').fetchall()
        else:
            rows = conn.execute('SELECT id,title,directory,parent_id,time_created,time_updated,time_archived FROM session').fetchall()
        for row in rows:
            record = new_record(system, row['id'], str(path), row['cwd'] if system == 'hermes' else row['directory'], row['title'])
            record['parent_id'] = row['parent_session_id'] if system == 'hermes' else row['parent_id']
            record['technical'] = bool(record['parent_id']) or (system == 'hermes' and row['source'] == 'tool')
            record['created_at'] = row['started_at'] if system == 'hermes' else row['time_created'] / 1000
            record['updated_at'] = row['last_activity_at'] if system == 'hermes' else row['time_updated'] / 1000
            record['archived'] = bool(row['archived'] if system == 'hermes' else row['time_archived'])
            sha = hashlib.sha256()
            if system == 'hermes':
                messages = conn.execute("SELECT id,role,content,timestamp FROM messages WHERE session_id=? AND role IN ('user','assistant') ORDER BY id", (row['id'],))
                for m in messages:
                    text = m['content'] or ''
                    sha.update(json.dumps(dict(m), ensure_ascii=False, sort_keys=True).encode())
                    add_message(record, m['role'], text, f'{path}#messages/{m["id"]}', m['timestamp'])
            else:
                messages = conn.execute('SELECT m.id,m.data,p.data AS part FROM message m LEFT JOIN part p ON p.message_id=m.id WHERE m.session_id=? ORDER BY m.time_created,p.time_created', (row['id'],))
                for m in messages:
                    try:
                        meta = json.loads(m['data'])
                        part = json.loads(m['part']) if m['part'] else {}
                        sha.update(json.dumps(dict(m), ensure_ascii=False, sort_keys=True).encode())
                        if part.get('type') != 'text' or meta.get('role') not in {'user', 'assistant'}:
                            continue
                        add_message(record, meta['role'], part.get('text', ''), f'{path}#message/{m["id"]}', meta.get('time', {}).get('created'))
                    except (ValueError, TypeError):
                        record['errors'].append('invalid message JSON')
            record['sha256'] = sha.hexdigest()
            write_record(output, record)


def write_record(output: Path, record: dict):
    record['tickets'] = sorted(record['tickets'])
    record['paths'] = sorted(record['paths'])
    record['message_count'] = dict(record['message_count'])
    if not record['title']:
        prompts = [m['excerpt'] for m in record['messages'] if m['role'] == 'user']
        record['title'] = prompts[0].splitlines()[0][:180] if prompts else 'Без содержательных сообщений'
    record['title'] = redact(record['title'])[:240]
    folder = output / 'sessions' / record['system']
    folder.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(record['id'].encode()).hexdigest()[:24]
    path = folder / (key + '.json')
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')


def project_catalog(output: Path):
    records = []
    skip = re.compile(r'^(?:[._$]|tmp|temp$|backups$|outputs$|logs$|kernels$|apk-|.*-workspace$)', re.I)
    for folder in WORKAI.iterdir():
        if not folder.is_dir() or skip.search(folder.name):
            continue
        docs = []
        for name in ('AGENTS.md', 'CLAUDE.md', 'README.md', 'СТАРТЕР.md'):
            path = folder / name
            if path.is_file():
                text = path.read_text(encoding='utf-8-sig', errors='replace')
                docs.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                             'excerpt': excerpt(text, 2400), 'headings': re.findall(r'^#{1,3}\s+(.+)$', text, re.M)[:30]})
        records.append({'name': folder.name, 'workspace': str(folder), 'git': (folder / '.git').exists(), 'documents': docs})
    (output / 'projects.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--conversations-only', action='store_true', help='перечитать человеческие сессии, сохранив каталог технических запусков')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    projects = project_catalog(output)
    codex_root = next((r for r in codex_roots() if r.is_dir()), codex_roots()[0])
    codex_catalog(codex_root, output, args.conversations_only)
    home = Path.home()
    claude_catalog(home / '.claude' / 'projects', output, args.conversations_only)
    sqlite_catalog(home / '.hermes' / 'state.db', 'hermes', output)
    sqlite_catalog(home / '.local' / 'share' / 'opencode' / 'opencode.db', 'opencode', output)
    records = [json.loads(path.read_text(encoding='utf-8')) for path in (output / 'sessions').rglob('*.json')]
    report = {'session_count': len(records), 'systems': dict(Counter(r['system'] for r in records)),
              'technical_sessions': sum(r['technical'] for r in records),
              'conversation_sessions': sum(not r['technical'] and r['message_count'].get('user', 0) > 0 for r in records),
              'messages': sum(sum(r['message_count'].values()) for r in records),
              'text_chars': sum(r['text_chars'] for r in records), 'projects': len(projects),
              'errors': [{'system': r['system'], 'id': r['id'], 'errors': r['errors']} for r in records if r['errors']],
              'changing_sources': [r['id'] for r in records if not r['stable']]}
    (output / 'coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'errors'}, ensure_ascii=False, indent=2), flush=True)
    print('Sources with errors:', len(report['errors']), flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
