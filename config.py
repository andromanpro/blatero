"""Настройки blatero: config.json в каталоге данных, дефолты здесь.

Меняются из панели (селекторы) или руками в config.json.
"""
import ipaddress
import json
import sys
import warnings
from urllib.parse import urlparse

import app_paths
import provider_contracts
from audio_watchdog import normalize_thresholds

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE = app_paths.DATA_ROOT
CONFIG_FILE = BASE / "config.json"
DEEPSEEK_FLASH = "deepseek/deepseek-v4-flash"
DEEPSEEK_PRO = "deepseek/deepseek-v4-pro"
OLLAMA_EXAMPLE_MODEL = "llama3.2"

DEFAULTS = {
    # Explicit opt-in: user-initiated loopback browser navigation can sign in.
    "local_browser_auto_login": False,
    "call_auto_telemost": False,
    "call_auto_talk": False,
    "call_auto_record_acknowledged": False,
    "llm_provider": "openrouter",  # OpenRouter/Codex/direct API/compatible endpoint
    "scene_coach_route": "inherit",
    # Используется только для OpenAI-совместимого провайдера (Ollama/vLLM/LM Studio).
    "llm_base_url": "http://127.0.0.1:11434/v1",
    "pulse_model": DEEPSEEK_FLASH,
    "report_model": DEEPSEEK_PRO,
    "voice": "auto",          # auto = по полу кандидата; либо имя голоса SpeechKit
    # Озвучивание вопросов: свой локальный голос, при сбое — выбранный voice Yandex.
    "question_voice_provider": "chatterbox_yandex",
    "record_audio": True,     # писать WAV обоих каналов в папку сессии
    "auto_pulse": "smart",    # off | smart (по паузам) | 30 | 60 | 90 (секунды)
    "mic_device": "auto",     # auto = системный дефолт; либо точное имя устройства
    # Выход приложения встречи, который читается через WASAPI loopback.
    "output_device": "auto",  # auto = системный дефолт; либо точное имя выхода
    # Удалять одну реплику, одновременно распознанную в микрофоне и loopback.
    "cross_channel_echo_suppression": True,
    # До STT вычитать из микрофона только уверенно совпавший опорный loopback.
    "pre_stt_echo_suppression": True,
    # auto: WebRTC AEC3 при наличии, иначе встроенный корреляционный фильтр.
    "pre_stt_echo_backend": "auto",
    "candidates_dir": str(app_paths.DATA_ROOT / "candidates"),  # optional surname folders
    "question_style": "classic",  # cases (кейсы) | classic (прямые) | mix
    "font_scale": "1.15",       # масштаб текста панели: 0.9 | 1.0 | 1.15 | 1.3
    # Доказательные таймкоды полезны при аудите, но перегружают обычный отчёт.
    "report_include_timestamps": False,
    # Человек видит и при необходимости правит локальный черновик до DOCX.
    "report_review_before_finalize": True,
    # local_whisper не передаёт аудио наружу; yandex оставлен как быстрый вариант.
    "speech_provider": "local_whisper",
    "whisper_model": "small",
    # По умолчанию LLM получает текст после локального удаления структурированных ПД.
    "text_privacy_mode": "redact",
    # Отдельное подтверждение для raw: browser confirm не является security boundary.
    "raw_text_acknowledged": False,
    # Ручное подтверждение оператора, а не автоматическое «распознавание согласия».
    "cloud_processing_acknowledged": False,
    # Профиль меняется только из локальной калибровки после ручного подтверждения.
    "audio_guard_thresholds": normalize_thresholds(),
}

# что показываем в селекторах панели: (значение, подпись)
PROVIDER_CHOICES = provider_contracts.choice_items("llm")
MODEL_CHOICES = [
    (DEEPSEEK_FLASH, "flash — быстро и дёшево"),
    ("anthropic/claude-haiku-4.5", "haiku — быстро, умнее"),
    (DEEPSEEK_PRO, "v4-pro — глубоко, медленно"),
    ("anthropic/claude-sonnet-5", "sonnet — умно, дороже"),
]
PROVIDER_MODEL_CHOICES = {
    "openrouter": MODEL_CHOICES,
    "codex": [],
    "openai": [
        ("gpt-5-mini", "GPT-5 mini — быстро"),
        ("gpt-5.2", "GPT-5.2 — глубоко"),
    ],
    "anthropic": [
        ("claude-haiku-4-5", "Claude Haiku 4.5 — быстро"),
        ("claude-sonnet-4-6", "Claude Sonnet 4.6 — глубоко"),
    ],
    "deepseek": [
        ("deepseek-v4-flash", "DeepSeek V4 Flash — быстро"),
        ("deepseek-v4-pro", "DeepSeek V4 Pro — глубоко"),
    ],
    "compatible": [
        (OLLAMA_EXAMPLE_MODEL, "llama3.2 — пример Ollama"),
        ("gpt-oss:20b", "gpt-oss:20b — пример Ollama"),
    ],
}
PROVIDER_DEFAULT_MODELS = {
    "openrouter": (DEEPSEEK_FLASH, DEEPSEEK_PRO),
    "openai": ("gpt-5-mini", "gpt-5.2"),
    "anthropic": ("claude-haiku-4-5", "claude-sonnet-4-6"),
    "deepseek": ("deepseek-v4-flash", "deepseek-v4-pro"),
    "compatible": (OLLAMA_EXAMPLE_MODEL, OLLAMA_EXAMPLE_MODEL),
}
VOICE_CHOICES = ["auto", "filipp", "alena", "jane", "ermil", "zahar", "omazh"]
VOICE_OPTIONS = [
    ("auto", "авто (filipp)"),
    ("filipp", "filipp — мужской"),
    ("alena", "alena — женский"),
    ("jane", "jane — женский"),
    ("ermil", "ermil — мужской"),
    ("zahar", "zahar — мужской"),
    ("omazh", "omazh — женский"),
]
QUESTION_VOICE_CHOICES = provider_contracts.choice_items("tts")
AUTO_CHOICES = [("off", "авто: выкл"), ("smart", "авто: по паузам"),
                ("30", "авто: 30с"), ("60", "авто: 60с"), ("90", "авто: 90с")]
STYLE_CHOICES = [("cases", "вопросы: кейсы"), ("classic", "вопросы: классика"),
                 ("mix", "вопросы: микс")]
FONT_SCALE_CHOICES = [
    ("0.9", "шрифт: компактный"),
    ("1.0", "шрифт: обычный"),
    ("1.15", "шрифт: крупный"),
    ("1.3", "шрифт: очень крупный"),
]
SPEECH_CHOICES = provider_contracts.choice_items("stt")
WHISPER_MODEL_CHOICES = [
    ("base", "Whisper base — быстрее"),
    ("small", "Whisper small — точнее"),
    ("medium", "Whisper medium — медленнее"),
]
PRIVACY_CHOICES = [
    ("redact", "обезличивать текст перед LLM"),
    ("raw", "передавать исходный текст"),
]
AEC_BACKEND_CHOICES = [
    ("auto", "авто — WebRTC AEC3 → встроенный"),
    ("native", "WebRTC AEC3 — с безопасным откатом"),
    ("correlation", "встроенный — без внешнего бинарника"),
]

# цепочка фолбэков пульса достраивается за выбранной моделью
PULSE_FALLBACKS = ["anthropic/claude-haiku-4.5", DEEPSEEK_PRO]


CHOICE_VALIDATORS = {
    "scene_coach_route": (("inherit", "openrouter_flash"), "неизвестный маршрут подсказок студии", False),
    "llm_provider": (PROVIDER_CHOICES, "неизвестный LLM-провайдер", False),
    "voice": (VOICE_CHOICES, "неизвестный голос", False),
    "question_voice_provider": (
        QUESTION_VOICE_CHOICES, "неизвестный голос вопросов", False),
    "auto_pulse": (AUTO_CHOICES, "неизвестный режим автопульса", True),
    "question_style": (STYLE_CHOICES, "неизвестный стиль вопросов", False),
    "font_scale": (FONT_SCALE_CHOICES, "неизвестный масштаб текста", True),
    "speech_provider": (SPEECH_CHOICES, "неизвестный распознаватель речи", False),
    "whisper_model": (WHISPER_MODEL_CHOICES, "неизвестная модель Whisper", False),
    "text_privacy_mode": (PRIVACY_CHOICES, "неизвестный режим приватности", False),
    "pre_stt_echo_backend": (AEC_BACKEND_CHOICES, "неизвестный AEC backend", False),
}
BOOLEAN_SETTINGS = frozenset({
    "local_browser_auto_login",
    "call_auto_telemost", "call_auto_talk", "call_auto_record_acknowledged",
    "record_audio", "cloud_processing_acknowledged",
    "raw_text_acknowledged",
    "cross_channel_echo_suppression", "pre_stt_echo_suppression",
    "report_include_timestamps", "report_review_before_finalize",
})
PATH_SETTINGS = frozenset({"mic_device", "output_device", "candidates_dir"})
MODEL_SETTINGS = frozenset({"pulse_model", "report_model"})


def _choice_values(choices) -> set:
    return {item[0] if isinstance(item, tuple) else item for item in choices}


def _validated_choice(key: str, value):
    choices, error, stringify = CHOICE_VALIDATORS[key]
    checked = str(value) if stringify else value
    if checked not in _choice_values(choices):
        raise ValueError(f"{error}: {checked}")
    return checked


def validate_llm_base_url(value) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 1000:
        raise ValueError("llm_base_url: ожидается URL до 1000 символов")
    checked = value.strip().rstrip("/")
    parsed = urlparse(checked)
    if (parsed.scheme not in {"http", "https"} or not parsed.netloc
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError(
            "llm_base_url: нужен HTTP(S)-адрес без логина, query и fragment")
    hostname = (parsed.hostname or "").rstrip(".").casefold()
    try:
        loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        loopback = hostname == "localhost"
    if parsed.scheme == "http" and not loopback:
        raise ValueError(
            "llm_base_url: HTTP разрешён только для localhost/loopback; "
            "для внешнего адреса нужен HTTPS")
    return checked


def _validated_model(key: str, value) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 150:
        raise ValueError(f"{key}: ожидается строка модели до 150 символов")
    return value


def _validated_bool(key: str, value) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{key}: ожидается true/false")
    return value


def _validated_path(key: str, value) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 500:
        raise ValueError(f"{key}: ожидается непустая строка до 500 символов")
    return value


def _validated(key: str, value):
    if key in CHOICE_VALIDATORS:
        return _validated_choice(key, value)
    if key == "llm_base_url":
        return validate_llm_base_url(value)
    if key in MODEL_SETTINGS:
        return _validated_model(key, value)
    if key in BOOLEAN_SETTINGS:
        return _validated_bool(key, value)
    if key in PATH_SETTINGS:
        return _validated_path(key, value)
    if key == "audio_guard_thresholds":
        return normalize_thresholds(value)
    return value


def load() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("корень config.json должен быть объектом")
            for key, value in raw.items():
                if key in DEFAULTS:
                    try:
                        cfg[key] = _validated(key, value)
                    except ValueError as exc:
                        warnings.warn(f"config.json: {exc}; используется значение по умолчанию")
        except (OSError, ValueError) as exc:
            warnings.warn(f"config.json не прочитан: {exc}; используются значения по умолчанию")
    # До 0.28.1 raw подтверждался только браузерным confirm и отдельного
    # server-side признака не существовало. Не переносить такой legacy-режим
    # молча и не блокировать из-за него сохранение других настроек.
    if (cfg.get("text_privacy_mode") == "raw"
            and cfg.get("raw_text_acknowledged") is not True):
        cfg["text_privacy_mode"] = "redact"
        cfg["raw_text_acknowledged"] = False
    return cfg


def save(updates: dict):
    cfg = load()
    checked = {k: _validated(k, v) for k, v in updates.items() if k in DEFAULTS}
    cfg.update(checked)
    # Отзыв облачного разрешения не должен оставлять «спящий» raw, который
    # включится при следующей единственной галочке без нового подтверждения.
    if checked.get("cloud_processing_acknowledged") is False:
        cfg["text_privacy_mode"] = "redact"
        cfg["raw_text_acknowledged"] = False
    if checked.get("text_privacy_mode") == "redact":
        cfg["raw_text_acknowledged"] = False
    if (cfg.get("text_privacy_mode") == "raw"
            and cfg.get("raw_text_acknowledged") is not True):
        raise ValueError(
            "режим raw требует отдельного подтверждения передачи исходного текста")
    # атомарно: live.py читает config.json на лету, нельзя ловить полузапись
    import os
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, CONFIG_FILE)
    return cfg


def pulse_chain() -> list[str]:
    current = load()
    if current["llm_provider"] == "codex":
        # Выбор провайдера строгий: не откатываться на платный OpenRouter молча.
        return ["codex-chatgpt"]
    primary = current["pulse_model"]
    if current["llm_provider"] != "openrouter":
        # Не подменять выбранный прямой API моделями другого провайдера.
        return [primary]
    chain = [primary] + [m for m in PULSE_FALLBACKS if m != primary]
    return chain


def llm_label(model: str | None = None) -> str:
    current = load()
    if current["llm_provider"] == "codex":
        return "Codex · подписка ChatGPT"
    label = dict(PROVIDER_CHOICES).get(current["llm_provider"], current["llm_provider"])
    return f"{label} · {model or current['report_model']}"


def default_models(provider: str) -> tuple[str, str]:
    return PROVIDER_DEFAULT_MODELS.get(
        provider, (DEFAULTS["pulse_model"], DEFAULTS["report_model"]))


def require_cloud_processing(purpose: str = "тексты") -> None:
    current = load()
    if not current.get("cloud_processing_acknowledged", False):
        text_destination = {
            "codex": "OpenAI Codex", "openrouter": "OpenRouter",
            "openai": "OpenAI API", "anthropic": "Anthropic API",
            "deepseek": "DeepSeek API", "compatible": "настроенный LLM endpoint",
        }.get(current["llm_provider"], "LLM")
        raise RuntimeError(
            f"облачная обработка ({purpose}) выключена: выбран {text_destination}. "
            "Приложение не умеет распознавать согласие автоматически — оператор "
            "фиксирует его переключателем в настройках или командой "
            "python config.py --ack-cloud"
        )


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Настройки blatero")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--ack-cloud", action="store_true",
                       help="зафиксировать ручное разрешение оператора на облачные функции")
    group.add_argument("--revoke-cloud", action="store_true",
                       help="отозвать подтверждение и блокировать облачные вызовы")
    args = ap.parse_args()
    value = bool(args.ack_cloud)
    save({"cloud_processing_acknowledged": value})
    print("облачная обработка: " + ("разрешена оператором" if value else "заблокирована"))
