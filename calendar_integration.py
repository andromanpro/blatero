"""Локальная дневная/недельная лента и read-only интеграции календарей.

Google подключается через официальный OAuth Calendar API. Яндекс и Mail — через
официально поддерживаемый CalDAV. Пароли CalDAV и refresh-токены Google лежат в
Windows Credential Manager; старый файловый токен мигрируется при первом чтении.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

import app_paths

BASE = app_paths.DATA_ROOT
SOURCES_FILE = BASE / "calendar_sources.json"
CACHE_FILE = BASE / "calendar_cache.json"
TOKENS_DIR = BASE / ".calendar-tokens"
KEYRING_SERVICE = "blatero-calendar"
GOOGLE_TOKEN_PREFIX = "google-oauth:"
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
LOCAL_TZ = dt.datetime.now().astimezone().tzinfo
SOURCE_ID_PATTERN = r"[a-zA-Z0-9_-]{6,64}"
UNTITLED = "Без названия"

PROVIDERS = {
    "google": {"label": "Google Calendar", "url": ""},
    "yandex": {"label": "Яндекс Календарь", "url": "https://caldav.yandex.ru"},
    "mail": {"label": "Календарь Mail", "url": "https://calendar.mail.ru"},
    "caldav": {"label": "Другой CalDAV", "url": ""},
}


def _atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_sources() -> list[dict]:
    if not SOURCES_FILE.exists():
        return []
    try:
        raw = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    return [source for source in raw if isinstance(source, dict)
            and source.get("provider") in PROVIDERS
            and re.fullmatch(SOURCE_ID_PATTERN, str(source.get("id", "")))]


def public_sources() -> list[dict]:
    result = []
    for source in load_sources():
        result.append({key: source.get(key, "") for key in
                       ("id", "provider", "label", "username", "url", "credentials_file")})
        result[-1]["connected"] = source_connected(source)
    return result


def _source_id(value: str | None = None) -> str:
    if value and re.fullmatch(SOURCE_ID_PATTERN, value):
        return value
    return uuid.uuid4().hex[:12]


def _existing_source_id(value: str) -> str:
    if not re.fullmatch(SOURCE_ID_PATTERN, str(value)):
        raise ValueError("некорректный идентификатор календаря")
    return str(value)


def _validate_google_source(credentials_file: str) -> str:
    checked = credentials_file or str(BASE / "google-calendar-credentials.json")
    if Path(checked).expanduser().suffix.lower() != ".json":
        raise ValueError("Google credentials должны быть JSON-файлом")
    return checked


def _validate_caldav_source(username: str, url: str) -> None:
    if not username:
        raise ValueError("для CalDAV нужен логин")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("CalDAV требует HTTPS, чтобы не передавать пароль открытым текстом")


def _source_from_input(data: dict) -> dict:
    provider = str(data.get("provider", "")).strip().lower()
    if provider not in PROVIDERS:
        raise ValueError("неизвестный провайдер календаря")
    sid = _source_id(str(data.get("id", "")) or None)
    label = str(data.get("label", "")).strip()[:100] or PROVIDERS[provider]["label"]
    username = str(data.get("username", "")).strip()[:254]
    url = str(data.get("url", "")).strip()[:1000] or PROVIDERS[provider]["url"]
    credentials_file = str(data.get("credentials_file", "")).strip()[:1000]
    if provider == "google":
        credentials_file = _validate_google_source(credentials_file)
    else:
        _validate_caldav_source(username, url)
    return {"id": sid, "provider": provider, "label": label,
            "username": username, "url": url,
            "credentials_file": credentials_file}


def _upsert_source(sources: list[dict], source: dict) -> list[dict]:
    updated = [source if current.get("id") == source["id"] else current
               for current in sources]
    if not any(current.get("id") == source["id"] for current in sources):
        updated.append(source)
    return updated


def save_source(data: dict, password: str = "") -> dict:
    source = _source_from_input(data)
    sources = _upsert_source(load_sources(), source)
    _atomic_json(SOURCES_FILE, sources)
    if password:
        import keyring
        keyring.set_password(KEYRING_SERVICE, source["id"], password)
    return source


def delete_source(source_id: str) -> bool:
    source_id = _existing_source_id(source_id)
    sources = load_sources()
    kept = [source for source in sources if source.get("id") != source_id]
    if len(kept) == len(sources):
        return False
    import keyring
    for credential in (source_id, GOOGLE_TOKEN_PREFIX + source_id):
        try:
            keyring.delete_password(KEYRING_SERVICE, credential)
        except keyring.errors.PasswordDeleteError:
            pass
    token = TOKENS_DIR / f"{source_id}.json"
    token.unlink(missing_ok=True)
    # Источник исчезает из UI только после удаления известных credentials;
    # иначе повторить очистку оставшегося секрета было бы невозможно.
    _atomic_json(SOURCES_FILE, kept)
    return True


def _token_path(source: dict) -> Path:
    return TOKENS_DIR / f"{_existing_source_id(source['id'])}.json"


def _google_credential_name(source: dict) -> str:
    return GOOGLE_TOKEN_PREFIX + _existing_source_id(source["id"])


def _google_token_json(source: dict) -> str:
    """Получить OAuth JSON из keyring, один раз мигрировав legacy-файл."""
    import keyring
    credential = _google_credential_name(source)
    stored = keyring.get_password(KEYRING_SERVICE, credential)
    if stored:
        return stored
    legacy = _token_path(source)
    if not legacy.is_file():
        return ""
    if legacy.stat().st_size > 1_000_000:
        raise RuntimeError("старый Google OAuth-токен неожиданно большой")
    raw = legacy.read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError("старый Google OAuth-токен повреждён") from exc
    if not isinstance(value, dict):
        raise RuntimeError("старый Google OAuth-токен имеет неверный формат")
    keyring.set_password(KEYRING_SERVICE, credential, raw)
    legacy.unlink()
    return raw


def _save_google_token(source: dict, raw: str) -> None:
    import keyring
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Google OAuth вернул неверный формат токена")
    keyring.set_password(KEYRING_SERVICE, _google_credential_name(source), raw)
    _token_path(source).unlink(missing_ok=True)


def source_connected(source: dict) -> bool:
    if source.get("provider") == "google":
        try:
            return bool(_google_token_json(source))
        except Exception:
            return False
    import keyring
    return bool(keyring.get_password(KEYRING_SERVICE, str(source.get("id", ""))))


def connect_google(source_id: str) -> None:
    source_id = _existing_source_id(source_id)
    source = next((item for item in load_sources() if item.get("id") == source_id), None)
    if not source or source.get("provider") != "google":
        raise ValueError("источник Google не найден")
    credentials_file = Path(source["credentials_file"]).expanduser().resolve()
    if not credentials_file.is_file():
        raise FileNotFoundError(f"не найден OAuth-файл: {credentials_file}")
    if credentials_file.stat().st_size > 1_000_000:
        raise ValueError("OAuth-файл неожиданно большой")
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), GOOGLE_SCOPES)
    credentials = flow.run_local_server(port=0, open_browser=True,
                                        success_message="Google Calendar подключён. Окно можно закрыть.")
    _save_google_token(source, credentials.to_json())


def _iso(value: dt.date | dt.datetime) -> str:
    if isinstance(value, dt.datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=LOCAL_TZ)
    else:
        aware = dt.datetime.combine(value, dt.time.min, LOCAL_TZ)
    return aware.astimezone().isoformat()


def _normalized_event(*, event_id: str, source: dict, title: str,
                      start: dt.date | dt.datetime, end: dt.date | dt.datetime,
                      location: str = "", all_day: bool = False) -> dict:
    return {"id": event_id[:300], "source_id": source.get("id", "local"),
            "source": source.get("label", "Локальное расписание"),
            "provider": source.get("provider", "local"),
            "title": (title or UNTITLED).strip()[:500],
            "start": _iso(start), "end": _iso(end),
            "all_day": bool(all_day), "location": str(location or "").strip()[:500]}


def schedule_events(start: dt.datetime, end: dt.datetime) -> list[dict]:
    import meet
    source = {"id": "local", "label": "Blatero", "provider": "local"}
    events = []
    for number, meeting in enumerate(meet.load()):
        try:
            begin = dt.datetime.fromisoformat(f"{meeting['date']}T{meeting['time']}").replace(
                tzinfo=LOCAL_TZ)
            finish = begin + dt.timedelta(minutes=int(meeting.get("duration") or 30))
        except (KeyError, TypeError, ValueError):
            continue
        if finish <= start or begin >= end:
            continue
        title = str(meeting.get("name") or meeting.get("role") or "Встреча")
        role = str(meeting.get("role") or "").strip()
        if role and role.lower() not in title.lower():
            title += f" — {role}"
        events.append(_normalized_event(
            event_id=f"schedule-{number}-{meeting.get('date')}-{meeting.get('time')}",
            source=source, title=title, start=begin, end=finish,
            location=str(meeting.get("company") or "")))
    return events


def _google_credentials(source: dict):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    raw = _google_token_json(source)
    if not raw:
        raise RuntimeError("Google ещё не подключён — нажмите «OAuth Google»")
    try:
        token_info = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError("Google OAuth-токен повреждён") from exc
    credentials = Credentials.from_authorized_user_info(token_info, GOOGLE_SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        _save_google_token(source, credentials.to_json())
    if not credentials.valid:
        raise RuntimeError("токен Google недействителен — подключите OAuth заново")
    return credentials


def google_events(source: dict, start: dt.datetime, end: dt.datetime) -> list[dict]:
    from googleapiclient.discovery import build
    service = build("calendar", "v3", credentials=_google_credentials(source),
                    cache_discovery=False)
    page_token = None
    events = []
    while True:
        response = service.events().list(
            calendarId="primary", timeMin=start.astimezone(dt.timezone.utc).isoformat(),
            timeMax=end.astimezone(dt.timezone.utc).isoformat(), singleEvents=True,
            orderBy="startTime", maxResults=2500, pageToken=page_token).execute()
        for item in response.get("items", []):
            start_data, end_data = item.get("start", {}), item.get("end", {})
            all_day = "date" in start_data
            try:
                begin = (dt.date.fromisoformat(start_data["date"]) if all_day else
                         dt.datetime.fromisoformat(start_data["dateTime"].replace("Z", "+00:00")))
                finish = (dt.date.fromisoformat(end_data["date"]) if all_day else
                          dt.datetime.fromisoformat(end_data["dateTime"].replace("Z", "+00:00")))
            except (KeyError, ValueError):
                continue
            events.append(_normalized_event(
                event_id=f"google-{item.get('id', uuid.uuid4().hex)}", source=source,
                title=item.get("summary", UNTITLED), start=begin, end=finish,
                location=item.get("location", ""), all_day=all_day))
        page_token = response.get("nextPageToken")
        if not page_token:
            return events


def caldav_events(source: dict, start: dt.datetime, end: dt.datetime) -> list[dict]:
    import caldav
    import keyring
    password = keyring.get_password(KEYRING_SERVICE, source["id"])
    if not password:
        raise RuntimeError("пароль не найден в Windows Credential Manager")
    events = []
    with caldav.DAVClient(url=source["url"], username=source["username"],
                          password=password, timeout=30) as client:
        calendars = client.principal().calendars()
        for calendar in calendars:
            for resource in calendar.search(start=start, end=end, event=True,
                                            expand=True, split_expanded=True):
                try:
                    components = resource.icalendar_instance.walk("VEVENT")
                except Exception:
                    continue
                for component in components:
                    try:
                        begin = component.decoded("DTSTART")
                        finish = component.decoded("DTEND")
                    except (KeyError, ValueError):
                        continue
                    uid = str(component.get("UID", resource.url))
                    recurrence = str(component.get("RECURRENCE-ID", ""))
                    events.append(_normalized_event(
                        event_id=f"{source['id']}-{uid}-{recurrence}", source=source,
                        title=str(component.get("SUMMARY", UNTITLED)),
                        start=begin, end=finish,
                        location=str(component.get("LOCATION", "")),
                        all_day=not isinstance(begin, dt.datetime)))
    return events


def _load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {"events": [], "errors": {}, "last_sync": ""}
    try:
        raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {"events": [], "errors": {}, "last_sync": ""}
    except (OSError, ValueError):
        return {"events": [], "errors": {}, "last_sync": ""}


def sync(start: dt.datetime, end: dt.datetime) -> dict:
    events: list[dict] = []
    errors: dict[str, str] = {}
    for source in load_sources():
        try:
            provider = source.get("provider")
            fetched = (google_events(source, start, end) if provider == "google"
                       else caldav_events(source, start, end))
            events.extend(fetched)
        except Exception as exc:
            errors[str(source.get("id", "?"))] = str(exc)[:500]
    cache = {"range_start": start.isoformat(), "range_end": end.isoformat(),
             "events": events, "errors": errors,
             "last_sync": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    _atomic_json(CACHE_FILE, cache)
    return cache


def payload(anchor: str | None = None, view: str = "day", refresh: bool = False) -> dict:
    try:
        anchor_date = dt.date.fromisoformat(anchor or str(dt.date.today()))
    except ValueError:
        anchor_date = dt.date.today()
    if view not in ("day", "week"):
        view = "day"
    if view == "week":
        anchor_date -= dt.timedelta(days=anchor_date.weekday())
        days = 7
    else:
        days = 1
    start = dt.datetime.combine(anchor_date, dt.time.min, LOCAL_TZ)
    end = start + dt.timedelta(days=days)
    if refresh:
        # Кэшируем окно шире текущего экрана, чтобы листание не било API каждый раз.
        cache = sync(start - dt.timedelta(days=7), end + dt.timedelta(days=21))
    else:
        cache = _load_cache()
    external = []
    for event in cache.get("events", []):
        try:
            event_start = dt.datetime.fromisoformat(event["start"])
            event_end = dt.datetime.fromisoformat(event["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if event_end > start and event_start < end:
            external.append(event)
    events = schedule_events(start, end) + external
    events.sort(key=lambda item: (item["start"], item["title"]))
    return {"type": "calendar", "anchor": str(anchor_date), "view": view,
            "today": str(dt.date.today()), "events": events,
            "sources": public_sources(), "errors": cache.get("errors", {}),
            "last_sync": cache.get("last_sync", "")}
