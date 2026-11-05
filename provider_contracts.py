"""Версионированные контракты реализованных LLM/STT/TTS-провайдеров.

Каталог описывает не маркетинговые возможности внешних сервисов, а ровно тот
маршрут, который поддерживает текущая версия Blatero. Поэтому UI и preflight
могут заранее показать, какие данные покинут компьютер и что будет заблокировано
без ручного разрешения облачной обработки.
"""

from __future__ import annotations

import copy
import ipaddress
from urllib.parse import urlparse


SCHEMA = "blatero.provider-contracts/v1"
CONTRACT_VERSION = 1


_CATALOG = {
    "llm": {
        "openrouter": {
            "label": "OpenRouter — единый API",
            "execution": "cloud",
            "credential": "api_key",
            "capabilities": {
                "hints": True, "reports": True, "model_selection": True,
                "connection_test": True, "custom_endpoint": False,
                "agent_tools": False,
            },
        },
        "codex": {
            "label": "Codex / подписка ChatGPT",
            "execution": "cloud",
            "credential": "subscription_login",
            "capabilities": {
                "hints": True, "reports": True, "model_selection": False,
                "connection_test": True, "custom_endpoint": False,
                "agent_tools": False,
            },
        },
        "openai": {
            "label": "OpenAI — API",
            "execution": "cloud",
            "credential": "api_key",
            "capabilities": {
                "hints": True, "reports": True, "model_selection": True,
                "connection_test": True, "custom_endpoint": False,
                "agent_tools": False,
            },
        },
        "anthropic": {
            "label": "Anthropic Claude — API",
            "execution": "cloud",
            "credential": "api_key",
            "capabilities": {
                "hints": True, "reports": True, "model_selection": True,
                "connection_test": True, "custom_endpoint": False,
                "agent_tools": False,
            },
        },
        "deepseek": {
            "label": "DeepSeek — API",
            "execution": "cloud",
            "credential": "api_key",
            "capabilities": {
                "hints": True, "reports": True, "model_selection": True,
                "connection_test": True, "custom_endpoint": False,
                "agent_tools": False,
            },
        },
        "compatible": {
            "label": "Ollama / совместимый API",
            "execution": "endpoint",
            "credential": "optional_api_key",
            "capabilities": {
                "hints": True, "reports": True, "model_selection": True,
                "connection_test": True, "custom_endpoint": True,
                "agent_tools": False,
            },
        },
    },
    "stt": {
        "local_whisper": {
            "label": "Whisper локально — аудио не уходит",
            "execution": "local",
            "credential": "none",
            "capabilities": {
                "live_transcription": True, "two_source_capture": True,
                "switch_during_recording": True, "timestamps": True,
                "offline_replay": True,
            },
        },
        "yandex": {
            "label": "Yandex SpeechKit — облако",
            "execution": "cloud",
            "credential": "api_key",
            "capabilities": {
                "live_transcription": True, "two_source_capture": True,
                "switch_during_recording": True, "timestamps": True,
                "offline_replay": False,
            },
        },
    },
    "tts": {
        "chatterbox": {
            "label": "мой голос локально, без облака",
            "execution": "local",
            "credential": "voice_profile",
            "capabilities": {
                "preview": True, "questions": True, "scene": True,
                "voice_clone": True, "cloud_fallback": False,
            },
        },
        "chatterbox_yandex": {
            "label": "мой голос локально → Яндекс",
            "execution": "hybrid",
            "credential": "voice_profile_or_api_key",
            "capabilities": {
                "preview": True, "questions": True, "scene": True,
                "voice_clone": True, "cloud_fallback": True,
            },
        },
        "yandex": {
            "label": "только Яндекс SpeechKit",
            "execution": "cloud",
            "credential": "api_key",
            "capabilities": {
                "preview": True, "questions": True, "scene": True,
                "voice_clone": False, "cloud_fallback": False,
            },
        },
    },
    "diarization": {
        "sherpa_onnx": {
            "label": "Sherpa-ONNX локально",
            "execution": "local",
            "credential": "model_files",
            "capabilities": {
                "offline": True, "multiple_speakers": True,
                "speaker_bank_suggestions": True, "live": False,
            },
        },
    },
}


def catalog() -> dict:
    """Вернуть JSON-safe копию каталога, которую вызывающий не может испортить."""
    return {
        "schema": SCHEMA,
        "contract_version": CONTRACT_VERSION,
        "domains": copy.deepcopy(_CATALOG),
    }


def choice_items(domain: str) -> list[tuple[str, str]]:
    """Селектор UI из того же реестра, что и runtime-контракт."""
    if domain not in _CATALOG:
        raise ValueError(f"неизвестный домен провайдера: {domain}")
    return [(provider, spec["label"])
            for provider, spec in _CATALOG[domain].items()]


def _compatible_execution(base_url: object) -> str:
    try:
        parsed = urlparse(str(base_url or ""))
        hostname = (parsed.hostname or "").rstrip(".").casefold()
        try:
            loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            loopback = hostname == "localhost"
        return "local" if loopback else "cloud"
    except (TypeError, ValueError):
        return "cloud"


def _selection(domain: str, provider: str, settings: dict) -> dict:
    spec = copy.deepcopy(_CATALOG[domain][provider])
    execution = spec["execution"]
    if domain == "llm" and provider == "compatible":
        execution = _compatible_execution(settings.get("llm_base_url"))
    cloud_possible = execution in {"cloud", "hybrid"}
    cloud_ack = bool(settings.get("cloud_processing_acknowledged"))
    return {
        "domain": domain,
        "provider": provider,
        "label": spec["label"],
        "execution": execution,
        "cloud_possible": cloud_possible,
        "requires_cloud_ack": cloud_possible,
        "blocked": bool(cloud_possible and not cloud_ack),
        "credential": spec["credential"],
        "capabilities": spec["capabilities"],
    }


def validate_settings(settings: dict) -> list[dict]:
    """Найти несовместимые или сознательно заблокированные маршруты."""
    selected = {
        "llm": str(settings.get("llm_provider") or ""),
        "stt": str(settings.get("speech_provider") or ""),
        "tts": str(settings.get("question_voice_provider") or ""),
        "diarization": "sherpa_onnx",
    }
    issues = []
    for domain, provider in selected.items():
        if provider not in _CATALOG[domain]:
            issues.append({
                "severity": "error", "domain": domain,
                "code": "unknown_provider",
                "message": f"неизвестный провайдер {domain}: {provider or 'не выбран'}",
            })
            continue
        route = _selection(domain, provider, settings)
        if route["blocked"]:
            issues.append({
                "severity": "warning", "domain": domain,
                "code": "cloud_ack_required",
                "message": f"{route['label']}: облачный маршрут выключен до согласия",
            })
    return issues


def runtime_payload(settings: dict) -> dict:
    """Контракт и фактически выбранные маршруты для UI и диагностики."""
    selected_ids = {
        "llm": str(settings.get("llm_provider") or ""),
        "stt": str(settings.get("speech_provider") or ""),
        "tts": str(settings.get("question_voice_provider") or ""),
        "diarization": "sherpa_onnx",
    }
    selection = {}
    for domain, provider in selected_ids.items():
        if provider in _CATALOG[domain]:
            selection[domain] = _selection(domain, provider, settings)
    return {
        **catalog(),
        "selection": selection,
        "issues": validate_settings(settings),
    }
