"""Спарринг: ИИ играет кандидата со скрытым профилем, ты тренируешься копать.

    python sparring.py           — вопросы голосом (мик), ответы озвучкой SAPI
    python sparring.py --text    — вопросы текстом, без озвучки (смоук-тест)

Цикл: задаёшь вопрос → кандидат отвечает в границах своего учебного профиля
→ панель подсказок обновляется → копаешь дальше. q — закончить и получить разбор.
"""
import argparse
import datetime as dt
import json
import sys
import threading
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from llm import PULSE_MODEL, REPORT_MODEL, chat, extract_json
import copilot
from copilot import render
from meeting_types import preset
from session_utils import unique_session_dir
import transcript_events
import app_paths
import session_schema

APP_ROOT = app_paths.APP_ROOT
BASE = APP_ROOT


def _runtime_data_root() -> Path:
    """Keep legacy BASE patching in tests/CLI while installed data stays separate."""
    return BASE if BASE != APP_ROOT else app_paths.DATA_ROOT
JSON_SYSTEM = "Отвечай только валидным JSON."
DEBRIEF_SYSTEM = "Ты — тренер интервьюеров. Честный, конкретный."

PROFILE_PROMPT = """Рубрика позиции:
{rubric}

Сгенерируй скрытый профиль кандидата для тренировочного собеседования. JSON:
{{
  "имя": "реалистичное русское имя",
  "пол": "м или ж; используется только для выбора синтетического голоса",
  "легенда": "2 предложения: опыт, текущее место",
  "сильные": ["2 области из рубрики, где кандидат реально хорош"],
  "ограничения": ["2 области, где опыта или знаний пока недостаточно"],
  "неопределённость": "одно утверждение, которое кандидат честно уточнит вопросами"
}}"""

CANDIDATE_SYSTEM = """Ты играешь кандидата на собеседовании. Скрытый профиль:
{profile}

Правила игры:
- отвечай устно-разговорно, 2-5 предложений, как живой человек, без списков
- в сильных областях — уверенно, с конкретикой и цифрами
- в незнакомой области честно обозначай границу опыта и объясняй известный подход
- на уточнения отвечай по существу; не скрывай пробелы и не выдумывай достижения
- неопределённое утверждение сначала уточняй, не выдавай допущение за факт
- из роли не выходи никогда"""

SCORECARD_PROMPT = """Скрытый профиль кандидата:
{profile}

Транскрипт тренировки:
{transcript}

Подсказки панели:
{hints}

Оцени РАБОТУ ИНТЕРВЬЮЕРА (не кандидата). Конкретно и уважительно. JSON:
{{
  "качество_уточнений": <1-10, уточнял ли ответы без давления и подсказки>,
  "работа_с_фактами": <1-10, отделял ли факты, допущения и противоречия>,
  "покрытие_рубрики": <1-10, сколько тем рубрики затронул>,
  "использование_подсказок": <1-10, шёл ли по тегам/вопросам панели>,
  "прояснено_пробелов": <0-2, сколько ограничений опыта корректно прояснил>,
  "проверено_неподтвержденных_утверждений": <true/false>,
  "очки": <0-100, интегральная оценка сессии>,
  "вердикт": "одно конструктивное предложение"
}}
Короткая сессия (1-2 вопроса) не может стоить больше 25 очков."""

LEVELS = [(0, "Стажёр интервьюера"), (150, "Интервьюер"),
          (400, "Технический интервьюер"), (800, "Ведущий интервьюер"),
          (1500, "Наставник"), (3000, "Мастер интервью")]


def level_for(xp: int) -> tuple[str, int | None]:
    name = LEVELS[0][1]
    nxt = None
    for threshold, title in LEVELS:
        if xp >= threshold:
            name = title
        elif nxt is None:
            nxt = threshold
    return name, nxt


def _score_card(profile: dict, tpath: Path, prev_hints: list) -> dict | None:
    import prompt_store
    try:
        raw = chat(REPORT_MODEL,
                   prompt_store.resolve("sparring.score.system", JSON_SYSTEM),
                   prompt_store.resolve("sparring.score.template", SCORECARD_PROMPT).format(
                       profile=json.dumps(profile, ensure_ascii=False),
                       transcript=tpath.read_text(encoding="utf-8"),
                       hints=json.dumps(prev_hints, ensure_ascii=False)[:4000]),
                   json_mode=True, max_tokens=1000, temperature=0.2)
        return extract_json(raw)
    except Exception as exc:
        print(f"!! оценка не удалась: {exc}")
        return None


def _stats_history(stats_file: Path) -> list[dict]:
    if not stats_file.exists():
        return []
    return [json.loads(line) for line in
            stats_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def _score_delta(history: list[dict], key: str, value: object) -> str:
    if not history:
        return ""
    previous = history[-1].get(key)
    if not (isinstance(previous, (int, float))
            and isinstance(value, (int, float))):
        return ""
    delta = value - previous
    return f" ({'+' if delta >= 0 else ''}{delta} к прошлой)"


def _render_score(card: dict, history: list[dict]) -> None:
    xp_previous = sum(int(item.get("очки", 0)) for item in history)
    xp = xp_previous + int(card.get("очки", 0))
    level, next_level = level_for(xp)
    previous_level, _ = level_for(xp_previous)
    cyan, green, yellow, reset = "\033[96m", "\033[92m", "\033[93m", "\033[0m"
    print(f"\n{cyan}═══ ОЦЕНКА СЕССИИ ═══{reset}")
    for key in ("качество_уточнений", "работа_с_фактами", "покрытие_рубрики",
                "использование_подсказок"):
        value = card.get(key, "?")
        print(f"  {key.replace('_', ' ')}: {value}/10"
              f"{_score_delta(history, key, value)}")
    checked = "да" if card.get(
        "проверено_неподтвержденных_утверждений") else "нет"
    print(f"  прояснено пробелов: {card.get('прояснено_пробелов', '?')}/2, "
          f"проверены неподтверждённые утверждения: {checked}")
    print(f"  {yellow}{card.get('вердикт', '')}{reset}")
    next_note = (f" (до следующего {next_level - xp} XP)"
                 if next_level else " — потолок")
    print(f"\n{green}+{card.get('очки', 0)} XP → всего {xp}. Уровень: "
          f"{level}{next_note}{reset}")
    if level != previous_level:
        print(f"{cyan}▲▲▲ НОВЫЙ УРОВЕНЬ: {level} ▲▲▲{reset}")
    print(f"  сессий сыграно: {len(history) + 1}")


def score_and_stats(profile: dict, tpath: Path, prev_hints: list) -> None:
    stats_file = _runtime_data_root() / "stats.jsonl"
    card = _score_card(profile, tpath, prev_hints)
    if card is None:
        return

    history = _stats_history(stats_file)
    entry = {"дата": f"{dt.datetime.now():%Y-%m-%d %H:%M}", **card}
    with stats_file.open("a", encoding="utf-8") as output:
        output.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _render_score(card, history)


DEBRIEF_PROMPT = """Скрытый профиль кандидата был:
{profile}

Транскрипт тренировки:
{transcript}

Подсказки, которые панель показывала интервьюеру:
{hints}

Разбор тренировки (markdown, кратко и честно):
## Что корректно прояснил
(какие ограничения опыта и неподтверждённые утверждения проверил без давления)
## Что пропустил
## Работа с подсказками
(какими воспользовался, какие проигнорировал зря)
## Качество и безопасность разговора
(были ли вопросы ясными, уважительными и не подсказывали ли ответ)
## 3 совета на завтра"""


from tts import speak as tts_speak


def _sparring_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", action="store_true",
                        help="вопросы текстом, без озвучки")
    parser.add_argument("--rounds", type=int, default=0,
                        help="автостоп после N вопросов")
    return parser.parse_args()


def _create_sparring_session() -> tuple[Path, Path, str]:
    rubric_file = BASE / "rubric.md"
    rubric = (rubric_file.read_text(encoding="utf-8")
              if rubric_file.exists() else "1С-разработчик")
    started = dt.datetime.now().astimezone()
    sdir = unique_session_dir(
        _runtime_data_root() / "sessions", f"sparring_{started:%Y-%m-%d_%H%M}")
    transcript = sdir / "transcript.md"
    title = "Спарринг с ИИ-кандидатом"
    session_schema.initialize(sdir, {
        "date": f"{started:%Y-%m-%d}", "time": f"{started:%H:%M}",
        "name": title, "type": "собеседование", "emulation_enabled": True,
    })
    transcript.write_text(
        f"# Транскрипт: {title} — {started:%Y-%m-%d %H:%M}\n\n",
        encoding="utf-8")
    transcript_events.create_journal(
        transcript_events.journal_path(transcript), title=title,
        provider="interactive_sparring", segment=1,
        started_at=started.isoformat(timespec="milliseconds"))
    return sdir, transcript, rubric


def _candidate_profile(rubric: str) -> dict:
    import prompt_store
    print("Генерирую кандидата...")
    return extract_json(chat(
        REPORT_MODEL, prompt_store.resolve("sparring.profile.system", JSON_SYSTEM),
        prompt_store.resolve("sparring.profile.template", PROFILE_PROMPT).format(
            rubric=rubric),
        json_mode=True, max_tokens=1000, temperature=0.9))


def _candidate_voice(profile: dict) -> str:
    import config as cfg
    configured = cfg.load()["voice"]
    if configured != "auto":
        return configured
    female = profile.get("пол", "м").strip().lower().startswith("ж")
    return "alena" if female else "filipp"


def _candidate_system(profile: dict) -> str:
    import prompt_store
    return prompt_store.resolve(
        "sparring.candidate.system", CANDIDATE_SYSTEM).format(
        profile=json.dumps(profile, ensure_ascii=False, indent=2))


def _start_voice_input():
    import pyaudiowpatch as pyaudio
    from speechkit_stream import StreamingRecognizer
    voice_buffer: list[str] = []
    mute = threading.Event()
    with pyaudio.PyAudio() as audio:
        mic = audio.get_host_api_info_by_type(
            pyaudio.paWASAPI)["defaultInputDevice"]
    recognizer = StreamingRecognizer(
        mic, "Я", lambda kind, text: (
            kind == "refined" and not mute.is_set() and voice_buffer.append(text)))
    recognizer.start()
    print("Мик слушает. Говори вопрос и жми Enter "
          "(пустой Enter без речи = q).\n")
    return voice_buffer, mute, recognizer


def _next_question(text_mode: bool, voice_buffer: list[str]) -> str:
    if text_mode:
        return input("Твой вопрос (q — разбор): ").strip()
    input("— говори, затем Enter —")
    spoken = voice_buffer[:]
    del voice_buffer[:len(spoken)]
    return " ".join(spoken).strip()


def _candidate_answer(system: str, history: str, question: str) -> str:
    return chat(
        REPORT_MODEL, system,
        f"История разговора:\n{history or '(начало)'}\n\n"
        f"Интервьюер спрашивает: {question}\n\nТвой устный ответ:",
        max_tokens=800, temperature=0.8)


def _sparring_hints(rubric: str, transcript: Path,
                    previous: list[dict]) -> dict:
    pulse_preset = preset("собеседование")
    pulse_template = copilot._pulse_template(pulse_preset)
    raw = chat(
        PULSE_MODEL, pulse_preset["pulse_system"], pulse_template.format(
            rubric=rubric, tail=transcript.read_text(encoding="utf-8")[-7000:],
            prev=json.dumps(previous[-2:], ensure_ascii=False)),
        json_mode=True, max_tokens=1200)
    return extract_json(raw)


def _run_sparring(args, transcript: Path, rubric: str, profile: dict,
                  voice: str, system: str, voice_buffer: list[str],
                  mute: threading.Event) -> list[dict]:
    history = ""
    previous_hints: list[dict] = []
    rounds = 0
    while True:
        question = _next_question(args.text, voice_buffer)
        if question.lower() in ("q", ""):
            break
        provider = "manual" if args.text else "yandex"
        source = "manual" if args.text else "microphone"
        transcript_events.append_transcript_turn(
            transcript, "Я", question, provider=provider,
            metadata={"source": source})
        answer = _candidate_answer(system, history, question)
        history += f"\nИнтервьюер: {question}\nКандидат: {answer}"
        transcript_events.append_transcript_turn(
            transcript, "Собеседник", answer, provider="llm",
            metadata={"source": "synthetic", "speaker_id": "ai_candidate"})
        print(f"\n{profile['имя']}: {answer}\n")
        if not args.text:
            mute.set()
            tts_speak(answer, voice)
            mute.clear()
        try:
            hints = _sparring_hints(rubric, transcript, previous_hints)
            previous_hints.append(hints)
            render(hints)
        except Exception as exc:
            print(f"!! пульс не удался: {exc}")
        rounds += 1
        if args.rounds and rounds >= args.rounds:
            break
    return previous_hints


def _debrief(profile: dict, transcript: Path, previous_hints: list[dict]) -> str:
    import prompt_store
    return chat(
        REPORT_MODEL,
        prompt_store.resolve("sparring.debrief.system", DEBRIEF_SYSTEM),
        prompt_store.resolve("sparring.debrief.template", DEBRIEF_PROMPT).format(
            profile=json.dumps(profile, ensure_ascii=False),
            transcript=transcript.read_text(encoding="utf-8"),
            hints=json.dumps(previous_hints, ensure_ascii=False)[:4000]),
        max_tokens=2500, temperature=0.3)


def main():
    args = _sparring_args()
    sdir, tpath, rubric = _create_sparring_session()
    profile = _candidate_profile(rubric)
    print(f"Кандидат: {profile['имя']} — {profile['легенда']}")
    print("(его сильные/слабые стороны узнаешь в разборе)\n")
    voice = _candidate_voice(profile)
    candidate_system = _candidate_system(profile)
    voice_buf: list[str] = []
    mute = threading.Event()
    recognizer = None
    if not args.text:
        voice_buf, mute, recognizer = _start_voice_input()
    try:
        prev_hints = _run_sparring(
            args, tpath, rubric, profile, voice, candidate_system, voice_buf, mute)
    finally:
        # мик слушает только во время диалога — не течёт в SpeechKit на разборе
        if recognizer is not None:
            recognizer.stop(wait=True)

    print("\nРазбор полёта...")
    debrief = _debrief(profile, tpath, prev_hints)
    (sdir / "debrief.md").write_text(debrief, encoding="utf-8")
    print("\n" + debrief)
    score_and_stats(profile, tpath, prev_hints)
    print(f"\nАртефакты: {sdir}")


if __name__ == "__main__":
    main()
