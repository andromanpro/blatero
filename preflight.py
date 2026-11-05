"""Единая локальная проверка готовности Blatero перед встречей."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import hashlib
import os
import uuid
from pathlib import Path

import llm
import model_manager
import native_aec
import stt_probe

STT_LABEL = "Распознавание речи"
LLM_LABEL = "Подсказки и отчёт"
AEC_LABEL = "Подавление акустического эха"
CHECK_REVISION = 4
_SETTINGS_KEYS = ("speech_provider", "whisper_model", "mic_device", "output_device",
                  "pre_stt_echo_suppression", "pre_stt_echo_backend", "llm_provider",
                  "pulse_model", "cloud_processing_acknowledged")


def settings_stamp(settings: dict) -> str:
    # Never hash credentials: this is an identity of the tested configuration.
    public = {key:settings.get(key) for key in _SETTINGS_KEYS}
    return hashlib.sha256(json.dumps(public,sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest()


def result_is_current(result: dict, settings: dict) -> bool:
    return (result.get("check_revision") == CHECK_REVISION
            and result.get("settings_stamp") == settings_stamp(settings))


def _check(key: str, label: str, state: str, message: str,
           details: dict | None = None) -> dict:
    return {"key": key, "label": label, "state": state,
            "message": message, "details": details or {}}


def _stt_check(settings: dict) -> dict:
    provider = settings.get("speech_provider", "local_whisper")
    if provider not in {"local_whisper", "yandex"}:
        return _check("stt", STT_LABEL, "fail", "неизвестный движок распознавания",
                      {"provider": provider})
    if provider == "local_whisper":
        available = importlib.util.find_spec("faster_whisper") is not None
        model = str(settings.get("whisper_model", "small"))
        ready = available and model_manager.whisper_ready(model)
        state = "pass" if ready else ("warn" if available else "fail")
        if ready:
            probe = stt_probe.run(provider, model)
            return _check("stt", STT_LABEL, "pass" if probe["ok"] else "fail",
                          (f"Whisper {model}: тестовая фраза распознана — «{probe['text']}»"
                           if probe["ok"] else probe["message"]), probe)
        elif available:
            message = (f"Whisper {model} ещё не подготовлен на этом диске; "
                       "откройте MOD локальные модели до встречи")
        else:
            message = "пакет faster-whisper не установлен"
        return _check(
            "stt", STT_LABEL, state, message,
            {"provider": provider, "model": model, "model_ready": ready})
    try:
        if not settings.get("cloud_processing_acknowledged", False):
            raise RuntimeError("не включено ручное согласие на облачную обработку")
        from speechkit_stream import read_api_key
        read_api_key(require_cloud_ack=False)
        probe = stt_probe.run(provider)
        return _check(
            "stt", STT_LABEL, "pass" if probe["ok"] else "fail",
            (f"SpeechKit: тестовая фраза распознана — «{probe['text']}»"
             if probe["ok"] else probe["message"]), probe)
    except Exception as exc:
        return _check("stt", STT_LABEL, "fail", str(exc),
                      {"provider": provider})


def _llm_check(settings: dict) -> dict:
    provider = settings.get("llm_provider", "openrouter")
    current = llm.connection_status(provider, settings)
    configured = bool(current.get("configured"))
    if provider == "codex" and configured:
        try:
            result = llm.test_connection("codex")
        except Exception as exc:
            return _check(
                "llm", LLM_LABEL, "fail", str(exc),
                {"provider": provider, "configured": False,
                 "source": current.get("source", "")})
        return _check(
            "llm", LLM_LABEL, "pass", result["message"],
            {"provider": provider, "configured": True,
             "source": current.get("source", "")})
    return _check(
        "llm", LLM_LABEL, "pass" if configured else "warn",
        (f"{current.get('label', 'LLM')}: доступ настроен"
         if configured else
         f"{current.get('label', 'LLM')}: доступ ещё не подтверждён"),
        {"provider": current.get("provider"),
         "configured": configured, "source": current.get("source", "")})


def _aec_check(settings: dict) -> dict:
    if not settings.get("pre_stt_echo_suppression", True):
        return _check("aec", AEC_LABEL, "warn",
                      "подавление до STT выключено")
    requested = settings.get("pre_stt_echo_backend", "auto")
    if requested == "correlation":
        return _check("aec", AEC_LABEL, "pass",
                      "выбран встроенный корреляционный фильтр",
                      {"backend": requested})
    current = native_aec.status()
    if current["valid"]:
        smoke = native_aec.smoke()
        return _check(
            "aec", AEC_LABEL, "pass",
            f"WebRTC AEC3 {current['version']} отвечает; SHA-256 проверен",
            {"backend": "webrtc-aec3", "version": current["version"],
             "smoke_frames": smoke["processed_frames"]})
    state = "fail" if requested == "native" else "warn"
    return _check(
        "aec", AEC_LABEL, state,
        f"{current['error']}; будет использован встроенный фильтр",
        {"backend": "correlation", "requested": requested})


def _write_check(session: Path) -> dict:
    probe = session / f".preflight-write-{uuid.uuid4().hex}.tmp"
    created = False
    try:
        with probe.open("xb") as output:
            created = True
            output.write(b"blatero-preflight")
            output.flush()
            os.fsync(output.fileno())
        probe.unlink()
        return _check("storage", "Запись результатов", "pass",
                      "папка встречи доступна для записи")
    except OSError as exc:
        if created:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass
        return _check("storage", "Запись результатов", "fail", str(exc))


def _render_markdown(payload: dict) -> str:
    icon = {"pass": "OK", "warn": "ВНИМАНИЕ", "fail": "ОШИБКА", "incomplete": "НЕ ЗАВЕРШЕНО"}
    lines = ["# Проверка готовности к встрече", "",
             f"Дата: {payload['created_at']}",
             f"Итог: {payload['summary']}", ""]
    for item in payload["checks"]:
        lines.append(
            f"- **{icon[item['state']]} · {item['label']}** — {item['message']}")
    lines.extend([
        "", "Звук проверки микрофона и аудиомаршрута не отправляется в облако.",
        "Для STT используется отдельная встроенная синтетическая фраза; при выборе",
        "SpeechKit только эта фраза отправляется в Яндекс. Речь участников не используется.", ""])
    return "\n".join(lines)


def run(session: Path, settings: dict, *, probe_microphone, calibrate,
        on_stage=None, probe_capture=None, on_level=None) -> dict:
    """Выполнить проверки последовательно и атомарно сохранить локальный отчёт."""
    session = Path(session).resolve()
    session.mkdir(parents=True, exist_ok=True)
    checks = []

    def stage(text: str) -> None:
        if on_stage:
            on_stage(text)

    stage("Говорите сейчас: «Проверяю микрофон перед встречей». Проверка длится 8 секунд.")
    try:
        args = (settings.get("mic_device", "auto"), 8.0)
        mic = (probe_microphone(*args, on_level=on_level) if on_level
               else probe_microphone(*args))
        checks.append(_check(
            "microphone", "Проверка голоса", "pass" if mic.get("signal") else "incomplete",
            (f"сигнал найден: {mic.get('device')}"
             if mic.get("signal") else
             f"Микрофон открылся ({mic.get('device')}), но достаточно громкая речь не обнаружена. "
             "Это не доказывает неисправность. Повторите проверку и произнесите фразу после отсчёта; "
             "если говорили — проверьте выбранный микрофон, mute и уровень входа."),
            {"device": mic.get("device"), "peak": mic.get("peak")}))
    except Exception as exc:
        checks.append(_check("microphone", "Микрофон", "fail", str(exc)))

    stage("не говорите — проверяю выход, loopback и акустическую утечку")
    try:
        route = calibrate(settings.get("mic_device", "auto"),
                          settings.get("output_device", "auto"))
        checks.append(_check(
            "audio_route", "Системный звук встречи",
            "pass" if route.get("route_signal") else "fail",
            route.get("recommendation", "маршрут проверен"),
            {key: route.get(key) for key in (
                "mic", "output", "playback", "diagnosis", "route_signal",
                "echo_detected", "delay_ms", "correlation", "loopback_dbfs",
                "mic_dbfs", "echo_dbfs")}))
    except Exception as exc:
        checks.append(_check(
            "audio_route", "Системный звук встречи", "fail", str(exc)))

    stage("проверяю одновременный запуск каналов настоящего контура записи")
    try:
        if probe_capture is None:
            from panel_audio import probe_recording_route
            probe_capture = probe_recording_route
        capture = probe_capture(settings.get("mic_device", "auto"),
                                settings.get("output_device", "auto"))
        checks.append(_check("capture", "Совместный захват звука", "pass",
            "оба канала открыты как при записи; микрофон передаёт PCM", capture))
    except Exception as exc:
        checks.append(_check("capture", "Совместный захват звука", "fail", str(exc)))

    stage("проверяю AEC и реальное распознавание встроенной тестовой фразы")
    for factory in (_aec_check, _stt_check, _llm_check):
        try:
            checks.append(factory(settings))
        except Exception as exc:
            checks.append(_check(factory.__name__, factory.__name__, "fail", str(exc)))
    checks.append(_write_check(session))

    failures = sum(item["state"] == "fail" for item in checks)
    warnings = sum(item["state"] == "warn" for item in checks)
    incomplete = sum(item["state"] == "incomplete" for item in checks)
    if failures:
        state = "blocked"
        summary = f"не готово: ошибок {failures}, предупреждений {warnings}"
    elif incomplete:
        state = "incomplete"
        summary = "Проверка голоса не завершена. Остальные результаты — ниже. Повторите проверку, произнеся фразу после отсчёта."
    elif warnings:
        state = "ready_with_warnings"
        summary = f"готово с предупреждениями: {warnings}"
    else:
        state = "ready"
        summary = "готово к встрече"
    payload = {
        "schema_version": 1,
        "check_revision": CHECK_REVISION,
        "settings_stamp": settings_stamp(settings),
        "created_at": dt.datetime.now().astimezone().isoformat(
            timespec="seconds"),
        "state": state,
        "summary": summary,
        "checks": checks,
    }
    json_tmp = session / "preflight.json.tmp"
    md_tmp = session / "preflight.md.tmp"
    json_tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    md_tmp.write_text(_render_markdown(payload), encoding="utf-8")
    os.replace(json_tmp, session / "preflight.json")
    os.replace(md_tmp, session / "preflight.md")
    stage(summary)
    return payload
