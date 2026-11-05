"""Инвентаризация и безопасное управление локальными моделями Blatero.

Менеджер удаляет только собственные зарегистрированные каталоги проекта.
Общий Hugging Face cache пользователя показывается read-only: его могут
использовать другие приложения, поэтому Blatero никогда не очищает его сам.
"""
from __future__ import annotations

import gc
import hashlib
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import app_paths
import native_aec
import speaker_diarization
import voice_clone


BASE = app_paths.APP_ROOT
MODELS_ROOT = app_paths.MODELS_ROOT
WHISPER_ROOT = MODELS_ROOT / "whisper"
TTS_ENV = BASE / ".venv-tts"
TTS_CACHE = voice_clone.MODEL_CACHE
CHATTERBOX_REPO = TTS_CACHE / "hub" / "models--ResembleAI--chatterbox"
REQUIREMENTS_CHATTERBOX = BASE / "requirements-chatterbox.txt"
TTS_ENV_ESTIMATE = 2500 * 1024**2

WHISPER_MODELS = {
    "whisper-base": {
        "name": "base", "label": "Whisper base", "estimate": 160 * 1024**2,
        "requirements": "CPU · 4 ГБ RAM · самый быстрый из доступных",
    },
    "whisper-small": {
        "name": "small", "label": "Whisper small", "estimate": 520 * 1024**2,
        "requirements": "CPU · 6 ГБ RAM · рекомендуемый баланс качества",
    },
    "whisper-medium": {
        "name": "medium", "label": "Whisper medium", "estimate": 1600 * 1024**2,
        "requirements": "CPU · 10 ГБ RAM · точнее, но заметно медленнее",
    },
}
Progress = Callable[[str], None]


def human_size(value: int) -> str:
    size = float(max(0, value))
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if size < 1024 or unit == "ТБ":
            digits = 0 if unit in {"Б", "КБ"} else 1
            return f"{size:.{digits}f} {unit}".replace(".0 ", " ")
        size /= 1024
    return "0 Б"


def _tree_size(*roots: Path) -> int:
    """Логический размер без повторного подсчёта hardlink/symlink целей."""
    total = 0
    seen: set[tuple[int, int]] = set()
    for root in roots:
        if not root.exists():
            continue
        pending = [root]
        while pending:
            path = pending.pop()
            try:
                if path.is_dir() and not path.is_symlink():
                    with os.scandir(path) as entries:
                        pending.extend(Path(entry.path) for entry in entries)
                    continue
                stat = path.stat()
                identity = (stat.st_dev, stat.st_ino)
                if identity in seen:
                    continue
                seen.add(identity)
                total += stat.st_size
            except OSError:
                continue
    return total


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _whisper_repo(name: str, root: Path | None = None) -> Path:
    root = WHISPER_ROOT if root is None else root
    return root / f"models--Systran--faster-whisper-{name}"


def _whisper_ready(name: str, root: Path | None = None) -> bool:
    root = WHISPER_ROOT if root is None else root
    repo = _whisper_repo(name, root)
    snapshots = repo / "snapshots"
    if not snapshots.is_dir():
        return False
    return any(
        (revision / "model.bin").is_file()
        and (revision / "config.json").is_file()
        and (revision / "tokenizer.json").is_file()
        for revision in snapshots.iterdir() if revision.is_dir()
    )


def whisper_ready(name: str) -> bool:
    if name not in {str(item["name"]) for item in WHISPER_MODELS.values()}:
        return False
    return _whisper_ready(name)


def _legacy_whisper_cache() -> dict:
    configured = os.environ.get("HF_HOME", "").strip()
    home = Path(configured).expanduser() if configured else Path.home() / ".cache" / "huggingface"
    hub = home / "hub"
    found = []
    size = 0
    for item in WHISPER_MODELS.values():
        name = str(item["name"])
        repo = _whisper_repo(name, hub)
        if _whisper_ready(name, hub):
            found.append(name)
            size += _tree_size(repo)
    return {
        "path": str(hub), "models": found, "size_bytes": size,
        "size": human_size(size), "managed": False,
        "note": ("Общий cache других приложений. Blatero показывает его, но не удаляет."
                 if found else "Общий cache Whisper не используется менеджером Blatero."),
    }


def _diarization_state() -> tuple[bool, bool, str]:
    files = (
        (speaker_diarization.SEGMENTATION_MODEL,
         speaker_diarization.SEGMENTATION_MODEL_SHA256),
        (speaker_diarization.EMBEDDING_MODEL,
         speaker_diarization.EMBEDDING_SHA256),
        (speaker_diarization.NEMO_EMBEDDING_MODEL,
         speaker_diarization.NEMO_EMBEDDING_SHA256),
    )
    present = [path.is_file() for path, _expected in files]
    if not any(present):
        return False, False, "не установлена"
    if not all(present):
        return False, False, "неполная установка"
    try:
        valid = all(_sha256(path) == expected for path, expected in files)
    except OSError:
        valid = False
    return valid, valid, "готова" if valid else "контрольная сумма не совпала"


def _chatterbox_model_ready() -> bool:
    blobs = CHATTERBOX_REPO / "blobs"
    if not blobs.is_dir():
        return False
    try:
        return sum(path.stat().st_size for path in blobs.iterdir() if path.is_file()) > 1024**3
    except OSError:
        return False


def _item(*, model_id: str, label: str, kind: str, installed: bool, valid: bool,
          size: int, estimate: int, requirements: str, license_name: str,
          location: Path, description: str, selected: bool = False,
          partial: bool = False, size_estimated: bool = False) -> dict:
    if valid:
        state, state_label = "ready", "готово"
    elif installed or partial:
        state, state_label = "partial", "требует восстановления"
    else:
        state, state_label = "missing", "не установлено"
    return {
        "id": model_id, "label": label, "kind": kind,
        "installed": installed, "valid": valid, "state": state,
        "state_label": state_label, "selected": selected,
        "size_bytes": size, "size": human_size(size),
        "size_estimated": size_estimated,
        "estimate_bytes": estimate, "estimate": human_size(estimate),
        "requirements": requirements, "license": license_name,
        "location": str(location), "description": description,
        "installable": True, "removable": bool(installed and not selected),
    }


def catalog(*, active_whisper: str = "small", busy: str = "") -> dict:
    items = []
    for model_id, definition in WHISPER_MODELS.items():
        name = str(definition["name"])
        repo = _whisper_repo(name)
        ready = _whisper_ready(name)
        size = _tree_size(repo)
        items.append(_item(
            model_id=model_id, label=str(definition["label"]), kind="STT",
            installed=repo.exists(), valid=ready, size=size,
            estimate=int(definition["estimate"]),
            requirements=str(definition["requirements"]), license_name="MIT",
            location=repo, selected=name == active_whisper,
            description="Локальное распознавание речи через faster-whisper.",
        ))

    native = native_aec.status()
    items.append(_item(
        model_id="aec3", label="WebRTC AEC3", kind="AUDIO",
        installed=bool(native["installed"]), valid=bool(native["valid"]),
        size=_tree_size(native_aec.INSTALL_DIR), estimate=1024**2,
        requirements="Windows x64 · CPU · подавление акустического эха",
        license_name="MIT", location=native_aec.INSTALL_DIR,
        description="Проверенный sidecar OpenWhispr для очистки микрофона.",
    ))

    diarization_ready, diarization_valid, _detail = _diarization_state()
    items.append(_item(
        model_id="diarization", label="Разделение голосов", kind="SPEAKER",
        installed=speaker_diarization.MODEL_ROOT.exists(), valid=diarization_valid,
        partial=speaker_diarization.MODEL_ROOT.exists() and not diarization_ready,
        size=_tree_size(speaker_diarization.MODEL_ROOT), estimate=78 * 1024**2,
        requirements="CPU · 4 ГБ RAM · постобработка записи",
        license_name="Apache-2.0 / MIT", location=speaker_diarization.MODEL_ROOT,
        description="ONNX-сегментация с NeMo TitaNet; 3D-Speaker сохранён для банка голосов.",
    ))

    chatterbox_status = voice_clone.status()
    chatterbox_model = _chatterbox_model_ready()
    chatterbox_installed = bool(chatterbox_status["installed"] or TTS_ENV.exists()
                                or TTS_CACHE.exists())
    tts_env_size = TTS_ENV_ESTIMATE if TTS_ENV.exists() else 0
    items.append(_item(
        model_id="chatterbox", label="Chatterbox Multilingual V3", kind="TTS",
        installed=chatterbox_installed,
        valid=bool(chatterbox_status["installed"] and chatterbox_model),
        partial=chatterbox_installed and not chatterbox_model,
        size=tts_env_size + _tree_size(TTS_CACHE), estimate=8 * 1024**3,
        size_estimated=TTS_ENV.exists(),
        requirements="CPU · 16 ГБ RAM · 8 ГБ диска · генерация не потоковая",
        license_name="MIT", location=TTS_CACHE,
        description="Локальный синтез и клонирование голоса; образец голоса удаляется отдельно.",
    ))

    usage = shutil.disk_usage(BASE)
    return {
        "type": "model_manager", "root": str(MODELS_ROOT),
        "busy": busy, "free_bytes": usage.free, "free": human_size(usage.free),
        "managed_bytes": sum(int(item["size_bytes"]) for item in items),
        "managed_size": human_size(sum(int(item["size_bytes"]) for item in items)),
        "legacy_whisper": _legacy_whisper_cache(), "items": items,
    }


def _run(command: list[str], *, timeout: int, env: dict | None = None) -> None:
    result = subprocess.run(
        command, cwd=BASE, env=env, text=True, encoding="utf-8",
        errors="replace", capture_output=True, timeout=timeout, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "неизвестная ошибка").strip()
        raise RuntimeError(detail[-1200:])


def _install_chatterbox(progress: Progress) -> None:
    if not REQUIREMENTS_CHATTERBOX.is_file():
        raise RuntimeError("requirements-chatterbox.txt не найден")
    if not (TTS_ENV / "Scripts" / "python.exe").is_file():
        progress("Создаю изолированное окружение Chatterbox…")
        executable = getattr(sys, "_base_executable", None) or sys.executable
        module = "virtualenv" if (app_paths.APP_ROOT / ".portable-runtime").is_file() \
            else "venv"
        _run([str(executable), "-m", module, str(TTS_ENV)], timeout=300)
    tts_python = TTS_ENV / "Scripts" / "python.exe"
    if not voice_clone.INSTALL_MARKER.is_file():
        progress("Устанавливаю закреплённые зависимости Chatterbox…")
        _run([str(tts_python), "-m", "pip", "install", "--disable-pip-version-check",
              "-r", str(REQUIREMENTS_CHATTERBOX)], timeout=1800)
        marker_tmp = voice_clone.INSTALL_MARKER.with_suffix(".ready.tmp")
        marker_tmp.write_text("requirements-chatterbox.txt\n", encoding="utf-8")
        os.replace(marker_tmp, voice_clone.INSTALL_MARKER)
    if not _chatterbox_model_ready():
        progress("Скачиваю Chatterbox Multilingual V3 в локальный cache на F…")
        TTS_CACHE.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["HF_HOME"] = str(TTS_CACHE)
        env["TOKENIZERS_PARALLELISM"] = "false"
        code = (
            "from chatterbox.mtl_tts import ChatterboxMultilingualTTS;"
            "ChatterboxMultilingualTTS.from_pretrained(device='cpu',t3_model='v3')"
        )
        _run([str(tts_python), "-c", code], timeout=1800, env=env)


def install(model_id: str, *, progress: Progress | None = None) -> dict:
    progress = progress or (lambda _message: None)
    if model_id in WHISPER_MODELS:
        name = str(WHISPER_MODELS[model_id]["name"])
        progress(f"Скачиваю Whisper {name} в {WHISPER_ROOT}…")
        WHISPER_ROOT.mkdir(parents=True, exist_ok=True)
        from faster_whisper.utils import download_model
        download_model(name, cache_dir=str(WHISPER_ROOT))
    elif model_id == "aec3":
        native_aec.install(progress=progress)
        native_aec.smoke()
    elif model_id == "diarization":
        progress("Скачиваю и проверяю модели разделения голосов…")
        speaker_diarization.install_models()
    elif model_id == "chatterbox":
        _install_chatterbox(progress)
    else:
        raise ValueError("неизвестная локальная модель")
    progress("Установка завершена; обновляю состояние…")
    return {"model_id": model_id, "action": "install"}


def _remove_registered(path: Path, expected: Path) -> int:
    """Удалить только точный путь из статического каталога менеджера."""
    path = Path(path)
    if path.absolute() != Path(expected).absolute():
        raise ValueError("отказ от удаления незарегистрированного пути")
    if path.name not in {
        ".venv-tts", "model-cache", "aec3", "speaker-diarization",
        "models--Systran--faster-whisper-base",
        "models--Systran--faster-whisper-small",
        "models--Systran--faster-whisper-medium",
    }:
        raise ValueError("отказ от удаления неожиданного каталога")
    size = _tree_size(path)
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)
    return size


def remove(model_id: str) -> dict:
    freed = 0
    if model_id in WHISPER_MODELS:
        name = str(WHISPER_MODELS[model_id]["name"])
        try:
            import local_whisper
            local_whisper.release_model(name)
        except (ImportError, AttributeError):
            gc.collect()
        freed += _remove_registered(_whisper_repo(name), _whisper_repo(name))
    elif model_id == "aec3":
        freed += _remove_registered(native_aec.INSTALL_DIR, native_aec.INSTALL_DIR)
    elif model_id == "diarization":
        freed += _remove_registered(
            speaker_diarization.MODEL_ROOT, speaker_diarization.MODEL_ROOT)
    elif model_id == "chatterbox":
        voice_clone.stop_worker()
        freed += _remove_registered(TTS_CACHE, TTS_CACHE)
        freed += _remove_registered(TTS_ENV, TTS_ENV)
    else:
        raise ValueError("неизвестная локальная модель")
    return {"model_id": model_id, "action": "remove",
            "freed_bytes": freed, "freed": human_size(freed)}
