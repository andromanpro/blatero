"""Обезличенный диагностический снимок без аудио, транскриптов и секретов."""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path

import native_aec
import runtime_diagnostics


BASE = Path(__file__).resolve().parent
PACKAGES = ("fastapi", "uvicorn", "numpy", "pyaudiowpatch", "faster-whisper",
            "websockets", "grpcio", "requests", "sherpa-onnx")
SAFE_CONFIG = (
    "llm_provider", "pulse_model", "report_model", "question_voice_provider",
    "record_audio", "auto_pulse", "question_style", "font_scale",
    "speech_provider", "whisper_model", "text_privacy_mode",
    "cloud_processing_acknowledged", "cross_channel_echo_suppression",
    "pre_stt_echo_suppression", "pre_stt_echo_backend",
)
SAFE_LEVELS = (
    "rec", "healthy", "error", "stt", "echo_suppression",
    "echoes_suppressed", "aec_enabled", "aec_active",
    "aec_backend", "aec_requested_backend", "aec_capture_frames",
    "aec_processed_frames",
    "aec_delay_ms", "aec_correlation", "aec_reduction_db",
    "stt_queue_ms", "stt_queue_me_ms", "stt_queue_guest_ms", "stt_latency_ms",
    "stt_inflight_ms", "stt_buffered_ms", "stt_inference_ms", "stt_wait_ms", "stt_rtf",
    "stt_dropped_chunks", "wav_backlog_ms",
)


def _selection(value: object) -> str:
    text = str(value or "").strip()
    return "automatic" if not text or text == "auto" else "explicit"


def _versions() -> dict:
    result = {}
    for package in PACKAGES:
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = "not-installed"
    return result


def _error_file(path: Path) -> dict:
    try:
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        lines = [line for line in text.splitlines() if line.strip()]
        return {"exists": True, "bytes": len(data), "nonempty_lines": len(lines),
                "sha256": hashlib.sha256(data).hexdigest() if data else "",
                "updated_at": dt.datetime.fromtimestamp(
                    path.stat().st_mtime).astimezone().isoformat(timespec="seconds")}
    except OSError:
        return {"exists": False, "bytes": 0, "nonempty_lines": 0,
                "sha256": "", "updated_at": ""}


def _preflight(session: Path) -> dict:
    path = session / "preflight.json"
    if not path.is_file():
        return {"state": "not_run", "checks": []}
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "invalid", "checks": []}
    checks = []
    for item in source.get("checks", []):
        if isinstance(item, dict):
            checks.append({"key": str(item.get("key", ""))[:80],
                           "state": str(item.get("state", ""))[:20]})
    return {"state": source.get("state", "unknown"), "checks": checks}


def build(session: Path, settings: dict) -> Path:
    """Создать стабильный diagnostics.json только из разрешённых полей."""
    session = Path(session).resolve()
    native = native_aec.status()
    levels = {}
    levels_path = session / "levels.json"
    if levels_path.is_file():
        try:
            raw_levels = json.loads(levels_path.read_text(encoding="utf-8"))
            levels = {key: raw_levels.get(key) for key in SAFE_LEVELS}
            # Текст ошибки может содержать имя устройства — достаточно факта.
            levels["error"] = bool(levels.get("error"))
            guard = raw_levels.get("guard")
            if isinstance(guard, dict):
                issues = guard.get("issues") if isinstance(
                    guard.get("issues"), list) else []
                levels["guard"] = {
                    "state": str(guard.get("state") or "unknown")[:20],
                    "issue_codes": [str(item.get("code") or "")[:80]
                                    for item in issues if isinstance(item, dict)],
                }
            device = raw_levels.get("device_change")
            if isinstance(device, dict):
                roles = device.get("roles") if isinstance(
                    device.get("roles"), list) else []
                raw_event_id = device.get("event_id")
                event_id = (max(0, int(raw_event_id))
                            if isinstance(raw_event_id, (int, float))
                            and not isinstance(raw_event_id, bool) else 0)
                levels["device_change"] = {
                    "state": str(device.get("state") or "unknown")[:24],
                    "event_id": event_id,
                    "roles": [role for role in roles
                              if role in {"mic", "output"}],
                    "action_required": device.get("action_required") is True,
                    "mic_available": device.get("mic_available") is True,
                    "output_available": device.get("output_available") is True,
                }
        except (OSError, ValueError):
            levels = {"parse_error": True}
    payload = {
        "schema_version": 1,
        "created_at": dt.datetime.now().astimezone().isoformat(
            timespec="seconds"),
        "privacy": {
            "redacted": True,
            "excluded": ["audio", "transcripts", "meeting metadata", "tokens",
                         "absolute paths", "log content"],
        },
        "runtime": {
            "platform": platform.system(), "release": platform.release(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "executable_kind": "venv" if sys.prefix != sys.base_prefix else "system",
        },
        "packages": _versions(),
        "config": {key: settings.get(key) for key in SAFE_CONFIG},
        "devices": {
            "microphone": _selection(settings.get("mic_device")),
            "output": _selection(settings.get("output_device")),
        },
        "native_aec": {
            **{key: native.get(key) for key in (
                "supported", "installed", "valid", "version", "sha256")},
            # Текст исключения иногда содержит абсолютный путь к библиотеке.
            "error_present": bool(native.get("error")),
        },
        "preflight": _preflight(session),
        "last_levels": levels,
        "pipeline_summary": runtime_diagnostics.summary(session),
        "error_logs": {
            name: _error_file(BASE / name) for name in (
                "panel.err.log", "panel-runtime-error.log", "mcp-server.log")
        },
    }
    target = session / "diagnostics.json"
    temporary = session / "diagnostics.json.tmp"
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    os.replace(temporary, target)
    return target
