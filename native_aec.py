"""Проверяемый локальный WebRTC AEC3 sidecar для подавления акустического эха.

Бинарник не хранится в репозитории: пользователь явно устанавливает закреплённый
релиз OpenWhispr, после чего проверяются SHA-256 архива и самого EXE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import queue
import struct
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

import numpy as np
import requests

import app_paths


VERSION = "meeting-aec-helper-v1.0.0"
SAMPLE_RATE = 24000
FRAME_SAMPLES = SAMPLE_RATE // 100  # 10 мс — нативный размер кадра AEC3
ARCHIVE_URL = (
    "https://github.com/OpenWhispr/openwhispr/releases/download/"
    "meeting-aec-helper-v1.0.0/meeting-aec-helper-win32-x64.zip"
)
ARCHIVE_SHA256 = "576b04b2ff0fcb2562cc217b8f7cf71792b483a70bb8404e5523a26fed0ea9a3"
BINARY_SHA256 = "728802049292f3ae1f5cffdabfe42ff4adde299cec619a916fe1ce88c7570b76"
ARCHIVE_MEMBER = "meeting-aec-helper-win32-x64.exe"
SOURCE_URL = "https://github.com/OpenWhispr/openwhispr/tree/main/native/meeting-aec-helper"
RELEASE_URL = "https://github.com/OpenWhispr/openwhispr/releases/tag/meeting-aec-helper-v1.0.0"

BASE = app_paths.DATA_ROOT
INSTALL_DIR = BASE / ".models" / "aec3"
BINARY_PATH = INSTALL_DIR / ARCHIVE_MEMBER
MAX_ARCHIVE_BYTES = 5 * 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def supported_platform() -> bool:
    return (sys.platform == "win32"
            and platform.machine().lower() in {"amd64", "x86_64"})


def status() -> dict:
    supported = supported_platform()
    installed = BINARY_PATH.is_file()
    actual_hash = ""
    valid = False
    error = ""
    if installed:
        try:
            actual_hash = _sha256(BINARY_PATH)
            valid = actual_hash == BINARY_SHA256
            if not valid:
                error = "хеш установленного AEC3 не совпадает"
        except OSError as exc:
            error = f"AEC3 не прочитан: {exc}"
    elif supported:
        error = "WebRTC AEC3 ещё не установлен"
    else:
        error = "готовый WebRTC AEC3 доступен только для Windows x64"
    return {
        "supported": supported,
        "installed": installed,
        "valid": valid,
        "version": VERSION,
        "binary": str(BINARY_PATH),
        "sha256": actual_hash,
        "source": SOURCE_URL,
        "release": RELEASE_URL,
        "error": error,
    }


def install(*, progress=None) -> dict:
    """Скачать закреплённый архив и атомарно установить проверенный EXE."""
    if not supported_platform():
        raise RuntimeError("WebRTC AEC3 sidecar поддерживается только на Windows x64")
    current = status()
    if current["valid"]:
        return current
    progress = progress or (lambda _text: None)
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    archive_tmp = INSTALL_DIR / f"{VERSION}.zip.download"
    binary_tmp = INSTALL_DIR / f"{ARCHIVE_MEMBER}.download"
    for temporary in (archive_tmp, binary_tmp):
        temporary.unlink(missing_ok=True)
    try:
        progress("скачивание закреплённого WebRTC AEC3 (около 0,5 МБ)")
        size = 0
        with requests.get(ARCHIVE_URL, stream=True, timeout=(10, 60)) as response:
            response.raise_for_status()
            with archive_tmp.open("xb") as target:
                for chunk in response.iter_content(64 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > MAX_ARCHIVE_BYTES:
                        raise RuntimeError("архив AEC3 неожиданно велик")
                    target.write(chunk)
        progress("проверка SHA-256 архива")
        archive_hash = _sha256(archive_tmp)
        if archive_hash != ARCHIVE_SHA256:
            raise RuntimeError(
                f"SHA-256 архива AEC3 не совпал: {archive_hash}")
        with zipfile.ZipFile(archive_tmp) as archive:
            names = archive.namelist()
            if names != [ARCHIVE_MEMBER]:
                raise RuntimeError("неожиданный состав архива AEC3")
            info = archive.getinfo(ARCHIVE_MEMBER)
            if info.file_size <= 0 or info.file_size > MAX_ARCHIVE_BYTES:
                raise RuntimeError("неожиданный размер бинарника AEC3")
            with archive.open(info) as source, binary_tmp.open("xb") as target:
                while chunk := source.read(64 * 1024):
                    target.write(chunk)
        progress("проверка SHA-256 исполняемого файла")
        binary_hash = _sha256(binary_tmp)
        if binary_hash != BINARY_SHA256:
            raise RuntimeError(
                f"SHA-256 бинарника AEC3 не совпал: {binary_hash}")
        os.replace(binary_tmp, BINARY_PATH)
        progress("WebRTC AEC3 установлен")
        return status()
    finally:
        archive_tmp.unlink(missing_ok=True)
        binary_tmp.unlink(missing_ok=True)


def _resample(pcm: bytes, source_rate: int, target_rate: int,
              *, target_length: int | None = None) -> bytes:
    samples = np.frombuffer(pcm, dtype=np.int16)
    if target_length is None:
        target_length = max(
            1, round(len(samples) * target_rate / max(1, source_rate)))
    if not len(samples) or target_length == 0:
        return b""
    if source_rate == target_rate and len(samples) == target_length:
        return pcm
    if len(samples) == 1:
        result = np.full(target_length, samples[0], dtype=np.float32)
    else:
        result = np.interp(
            np.linspace(0, len(samples) - 1, target_length),
            np.arange(len(samples)), samples.astype(np.float32))
    return np.clip(np.rint(result), -32768, 32767).astype(np.int16).tobytes()


def _rms(pcm: bytes) -> float:
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float64)
    return float(np.sqrt(np.mean(np.square(samples)))) if len(samples) else 0.0


class WebRtcAec3:
    """Потокобезопасный PCM16-клиент sidecar с ограниченным ожиданием ответа."""

    def __init__(self, *, binary: Path | None = None, timeout: float = 2.0):
        self.binary = Path(binary or BINARY_PATH)
        self.timeout = max(0.2, float(timeout))
        if self.binary == BINARY_PATH:
            current = status()
            if not current["valid"]:
                raise RuntimeError(current["error"])
        elif not self.binary.is_file():
            raise RuntimeError(f"AEC3 sidecar не найден: {self.binary}")
        self._lock = threading.Lock()
        self._capture_lock = threading.Lock()
        self._responses: queue.Queue[bytes | BaseException] = queue.Queue()
        self._started: queue.Queue[dict | BaseException] = queue.Queue()
        self._closed = False
        self._capture_frames = 0
        self._processed_frames = 0
        self._failures = 0
        self._last_reduction_db = 0.0
        self._reduction_sum = 0.0
        self._last_processed_at = 0.0
        self._last_error = ""
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        self._process = subprocess.Popen(
            [str(self.binary), "--sample-rate", str(SAMPLE_RATE)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0, creationflags=flags)
        threading.Thread(target=self._stderr_loop, daemon=True,
                         name="aec3-stderr").start()
        threading.Thread(target=self._stdout_loop, daemon=True,
                         name="aec3-stdout").start()
        try:
            startup = self._started.get(timeout=3.0)
        except queue.Empty as exc:
            self.close()
            raise RuntimeError("AEC3 sidecar не подтвердил запуск за 3 секунды") from exc
        if isinstance(startup, BaseException):
            self.close()
            raise RuntimeError(str(startup))
        if (startup.get("type") != "start"
                or startup.get("backend") != "webrtc-apm-aec3"
                or startup.get("sampleRate") != SAMPLE_RATE):
            self.close()
            raise RuntimeError(f"AEC3 sidecar вернул неожиданный ответ: {startup}")

    @staticmethod
    def _read_exact(stream, length: int) -> bytes:
        result = bytearray()
        while len(result) < length:
            chunk = stream.read(length - len(result))
            if not chunk:
                raise EOFError("AEC3 sidecar закрыл канал вывода")
            result.extend(chunk)
        return bytes(result)

    def _stderr_loop(self) -> None:
        try:
            assert self._process.stderr is not None
            for raw in iter(self._process.stderr.readline, b""):
                try:
                    message = json.loads(raw.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                if message.get("type") == "start":
                    self._started.put(message)
                elif message.get("type") == "error":
                    error = RuntimeError(str(message.get("message") or message))
                    self._last_error = str(error)
                    if self._process.poll() is None and self._capture_frames == 0:
                        self._started.put(error)
        except Exception as exc:
            if not self._closed:
                self._started.put(exc)

    def _stdout_loop(self) -> None:
        try:
            assert self._process.stdout is not None
            while True:
                length = struct.unpack("<I", self._read_exact(
                    self._process.stdout, 4))[0]
                if length <= 0 or length > 4 * 1024 * 1024 or length % 2:
                    raise RuntimeError(f"AEC3 sidecar вернул неверную длину: {length}")
                self._responses.put(self._read_exact(self._process.stdout, length))
        except Exception as exc:
            if not self._closed:
                self._responses.put(exc)

    def _write(self, stream_type: int, pcm: bytes) -> None:
        if self._closed or self._process.poll() is not None:
            raise RuntimeError(self._last_error or "AEC3 sidecar остановлен")
        assert self._process.stdin is not None
        self._process.stdin.write(struct.pack("<BI", stream_type, len(pcm)))
        self._process.stdin.write(pcm)
        self._process.stdin.flush()

    @staticmethod
    def _prepare(pcm: bytes, rate: int) -> tuple[bytes, int]:
        converted = _resample(pcm, rate, SAMPLE_RATE)
        valid_samples = len(converted) // 2
        padded_samples = math.ceil(max(1, valid_samples) / FRAME_SAMPLES) * FRAME_SAMPLES
        if padded_samples > valid_samples:
            converted += b"\0\0" * (padded_samples - valid_samples)
        return converted, valid_samples

    def push_render(self, pcm: bytes, rate: int, _start_ms: int,
                    _end_ms: int) -> bytes:
        if not pcm:
            return pcm
        prepared, _valid = self._prepare(pcm, rate)
        with self._lock:
            self._write(1, prepared)
        return pcm

    def _request_capture(self, prepared: bytes):
        """Сопоставить один capture с одним ответом, не блокируя render-записи."""
        with self._capture_lock:
            with self._lock:
                self._capture_frames += 1
                self._write(2, prepared)
            try:
                return self._responses.get(timeout=self.timeout)
            except queue.Empty as exc:
                self._failures += 1
                raise RuntimeError("AEC3 sidecar не ответил вовремя") from exc

    def process_capture(self, pcm: bytes, rate: int, _start_ms: int,
                        _end_ms: int) -> bytes:
        if not pcm:
            return pcm
        prepared, valid_samples = self._prepare(pcm, rate)
        # Sidecar отвечает только на capture и сохраняет их порядок. Пока ждём,
        # render-поток должен продолжать передавать опорный звук, иначе AEC сам
        # ухудшает синхронизацию при краткой задержке ответа.
        response = self._request_capture(prepared)
        if isinstance(response, BaseException):
            self._failures += 1
            raise RuntimeError(str(response))
        expected = len(prepared)
        if len(response) != expected:
            self._failures += 1
            raise RuntimeError(
                f"AEC3 вернул {len(response)} байт вместо {expected}")
        cleaned_24k = response[:valid_samples * 2]
        cleaned = _resample(
            cleaned_24k, SAMPLE_RATE, rate, target_length=len(pcm) // 2)
        input_rms = _rms(pcm)
        output_rms = _rms(cleaned)
        reduction = 20 * math.log10(
            max(input_rms, 1.0) / max(output_rms, 1.0))
        self._processed_frames += 1
        self._last_reduction_db = round(max(0.0, reduction), 1)
        self._reduction_sum += max(0.0, reduction)
        self._last_processed_at = time.monotonic()
        return cleaned

    def reset(self) -> None:
        # AEC3 должен переобучиться после смены устройства. Проще и надёжнее
        # заменить процесс в фасаде, чем пытаться очищать внутреннее состояние.
        raise RuntimeError("AEC3 требует перезапуска")

    def snapshot(self) -> dict:
        return {
            "backend": "webrtc-aec3",
            "enabled": True,
            "active": bool(self._last_processed_at
                           and time.monotonic() - self._last_processed_at < 3),
            "capture_frames": self._capture_frames,
            "processed_frames": self._processed_frames,
            "failures": self._failures,
            "delay_ms": 0,
            "correlation": 0.0,
            "average_correlation": 0.0,
            "reduction_db": self._last_reduction_db,
            "average_reduction_db": round(
                self._reduction_sum / max(1, self._processed_frames), 1),
            "status": self._last_error or "WebRTC AEC3 активен",
        }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._process.stdin:
                self._process.stdin.close()
        except OSError:
            pass
        try:
            self._process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            try:
                self._process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=1.0)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def smoke() -> dict:
    with WebRtcAec3() as processor:
        silence = b"\0\0" * (SAMPLE_RATE // 10)
        processor.push_render(silence, SAMPLE_RATE, 0, 100)
        output = processor.process_capture(silence, SAMPLE_RATE, 0, 100)
        if len(output) != len(silence):
            raise RuntimeError("AEC3 smoke-test вернул PCM неверной длины")
        return processor.snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "install", "smoke"))
    args = parser.parse_args()
    if args.action == "install":
        result = install(progress=print)
    elif args.action == "smoke":
        result = smoke()
    else:
        result = status()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
