"""Расписание встреч и рабочие папки: schedule.json → sessions/<дата_время_имя>/.

    python meet.py                        — встречи на сегодня
    python meet.py --date 2026-07-21      — на дату (или --date все)
    python meet.py --prepare              — создать папки встреч (класть туда резюме)
    python meet.py --start                — запись ближайшей встречи (или --start 15:30)

В папке встречи: meta.json (кто/когда/роль), резюме.* (md/txt/pdf — подхватят
пульс и отчёт), после записи — transcript.md, hints.jsonl, report.md и DOCX с
именем участника и датой.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import app_paths
import session_schema

BASE = app_paths.APP_ROOT
SCHEDULE = app_paths.DATA_ROOT / "schedule.json"
SESSIONS = app_paths.SESSIONS_ROOT
QUESTIONS_FILE = "questions.md"

from session_utils import (direct_child, safe_component, schedule_slug,
                           transcript_segments)


def load() -> list[dict]:
    if not SCHEDULE.exists():
        return []
    raw = json.loads(SCHEDULE.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("schedule.json должен содержать массив встреч")
    seen = set()
    for number, meeting in enumerate(raw, 1):
        if not isinstance(meeting, dict):
            raise ValueError(f"встреча #{number}: ожидается объект")
        session_slug = schedule_slug(meeting)
        if session_slug in seen:
            raise ValueError(f"дублирующая встреча в schedule.json: {session_slug}")
        seen.add(session_slug)
        if "duration" in meeting and not 1 <= int(meeting["duration"]) <= 1440:
            raise ValueError(f"встреча #{number}: длительность должна быть 1–1440 минут")
    return raw


def slug(m: dict) -> str:
    return schedule_slug(m)


def sdir(m: dict) -> Path:
    return direct_child(SESSIONS, slug(m))


def _copy_candidate_resume(candidate_dir: Path, session: Path, quiet: bool) -> Path:
    import question_bank as qb
    description = candidate_dir / "Описание.txt"
    has_resume = any(session.glob("резюме*")) or any(session.glob("resume*"))
    if description.exists() and not has_resume:
        (session / "резюме.txt").write_text(
            qb._read_smart(description), encoding="utf-8")
        if not quiet:
            print("    анкета -> резюме.txt")
    return description


def _candidate_materials(candidate_dir: Path, description: Path,
                         candidate_name: str) -> list[str]:
    import question_bank as qb
    materials = []
    if description.exists():
        materials.append(f"### Анкета\n{qb._read_smart(description)[:4000]}")
    for review in sorted(candidate_dir.glob("Ревью*.md")):
        materials.append(f"### {review.name}\n{qb._read_smart(review)[:6000]}")
    summary = qb.svodka_section(
        candidate_dir.parent / "Сводка_по_кандидатам_1С.md", candidate_name)
    if summary:
        materials.append(f"### Из общей сводки\n{summary}")
    return materials


def _prepare_candidate_questions(meeting: dict, session: Path,
                                 materials: list[str], quiet: bool) -> None:
    import question_bank as qb
    if not materials:
        return
    if not (session / "dossier.md").exists():
        if not quiet:
            print("    собираю досье...")
        qb.make_dossier(session, meeting["name"], materials)
    if not (session / QUESTIONS_FILE).exists():
        if not quiet:
            print(f"    генерирую персональные вопросы ({len(materials)} источника)...")
        qb.personalize(session, meeting["name"], materials)
        if not quiet:
            print("    questions.md готов (персональный блок + общий банк)")


def _fit_candidate_plan(meeting: dict, session: Path, quiet: bool) -> None:
    import question_bank as qb
    should_fit = (meeting.get("duration") and (session / QUESTIONS_FILE).exists()
                  and not (session / "questions-full.md").exists())
    if not should_fit:
        return
    if not quiet:
        print(f"    сжимаю план под {meeting['duration']} минут...")
    qb.fit(session, int(meeting["duration"]))
    if not quiet:
        print("    боевой план готов (полная версия в questions-full.md)")


def _verify_candidate_questions(session: Path, quiet: bool) -> None:
    import question_bank as qb
    if not (session / QUESTIONS_FILE).exists() or (session / "verify.txt").exists():
        return
    try:
        found = qb.verify(session)
        (session / "verify.txt").write_text(
            "\n".join(f"[{i+1}] {item.get('вопрос','')}"
                      f"\n  ПРОБЛЕМА: {item.get('проблема','')}"
                      f"\n  ФИКС: {item.get('исправление','')}"
                      for i, item in enumerate(found)) or "ошибок не найдено",
            encoding="utf-8")
        if not quiet:
            print("    техпроверка вопросов: " + (
                f"⚠ {len(found)} замечаний в verify.txt — глянь"
                if found else "чисто"))
    except Exception as exc:
        print(f"    !! техпроверка не удалась: {exc}")


def enrich_from_candidates(m: dict, d: Path, quiet: bool):
    """Материалы из candidates_dir/<Фамилия>: анкета, досье и вопросы."""
    import config as cfg
    configured_root = str(cfg.load().get("candidates_dir") or "").strip()
    if not configured_root:
        return
    surname = m["name"].split()[0]
    candidates_root = Path(configured_root)
    cdir = direct_child(candidates_root, safe_component(surname))
    if not cdir.is_dir():
        return
    opis = _copy_candidate_resume(cdir, d, quiet)
    materials = _candidate_materials(cdir, opis, m["name"])
    _prepare_candidate_questions(m, d, materials, quiet)
    _fit_candidate_plan(m, d, quiet)
    _verify_candidate_questions(d, quiet)


def prepare(meetings: list[dict], quiet: bool = False):
    for m in meetings:
        d = sdir(m)
        d.mkdir(parents=True, exist_ok=True)
        if (d / session_schema.MANIFEST_FILE).exists() or (d / "meta.json").exists():
            session_schema.write_meta(d, m)
        else:
            session_schema.initialize(d, m)
        if not quiet:
            has_cv = any(d.glob("резюме*")) or any(d.glob("resume*"))
            print(f"  {d.name}" + ("  [резюме на месте]" if has_cv else "  [резюме нет]"))
        try:
            enrich_from_candidates(m, d, quiet)
        except Exception as e:
            print(f"    !! материалы кандидата не подтянулись: {e}")
    if not quiet:
        print("Резюме клади в папку кандидата файлом резюме.pdf/md/txt — пульс и отчёт подхватят.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="ГГГГ-ММ-ДД, по умолчанию сегодня; «все»")
    ap.add_argument("--prepare", action="store_true", help="создать папки встреч")
    ap.add_argument("--start", nargs="?", const="next", default=None,
                    help="запустить запись: без значения = ближайшая, либо ЧЧ:ММ")
    args = ap.parse_args()

    date = args.date or f"{dt.date.today():%Y-%m-%d}"
    todays = [m for m in load() if args.date == "все" or m["date"] == date]
    if not todays:
        print(f"На {date} встреч в schedule.json нет.")
        return
    todays.sort(key=lambda m: m["time"])

    print(f"Встречи на {date}:")
    for i, m in enumerate(todays, 1):
        done = "✓" if transcript_segments(sdir(m)) else "·"
        print(f"  {i}. {done} {m['time']}  {m['name']}  — {m.get('role', '')} ({m.get('type', 'встреча')})")

    if args.prepare:
        print()
        prepare(todays)
        import question_bank
        question_bank.ensure()  # банк вопросов: создаётся один раз, если нет

    if args.start:
        now = f"{dt.datetime.now():%H:%M}"
        if args.start == "next":
            pick = next((m for m in todays if m["time"] >= now), todays[-1])
        else:
            pick = next((m for m in todays if m["time"] == args.start), None)
            if pick is None:
                print(f"Встречи в {args.start} нет.")
                return
        prepare([pick], quiet=True)
        print(f"\n▶ Запись: {pick['name']}, {pick['time']} — Ctrl+C по окончании, потом жми r в панели или запусти report.py")
        subprocess.run([sys.executable, str(BASE / "live.py"), "--session", slug(pick)])


if __name__ == "__main__":
    main()
