"""Isolated, bounded conversion of legacy Office/Visio copies with LibreOffice."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading

TARGETS = {".doc": ".docx", ".rtf": ".docx", ".xls": ".xlsx", ".ppt": ".pptx", ".vsd": ".fodg"}
_LOCK = threading.Lock()
MAX_OUTPUT = 20 * 1024 * 1024
PROFILE = '''<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="DisableActiveContent" oor:op="fuse"><value>true</value></prop><prop oor:name="BlockUntrustedRefererLinks" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>1</value></prop></item>
</oor:items>'''


def run_converter(command: list[str]) -> int:
    try:
        process = subprocess.Popen(  # nosec B603
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), start_new_session=os.name != "nt")
    except OSError as exc:
        raise ValueError("не удалось запустить LibreOffice") from exc
    try:
        return process.wait(timeout=45)
    except subprocess.TimeoutExpired as exc:
        # Terminate only this converter and its children, never the user's office.
        if os.name == "nt":
            subprocess.run(  # nosec B603
                [str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/taskkill.exe"),
                 "/PID", str(process.pid), "/T", "/F"], timeout=10,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
        raise ValueError("LibreOffice не завершил преобразование за 45 секунд") from exc


def executable() -> str:
    candidates = [Path(__file__).parent / "tools/LibreOffice/program/soffice.com"]
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        if os.environ.get(env):
            candidates.append(Path(os.environ[env]) / "LibreOffice/program/soffice.com")
    candidates.append(Path("F:/Program Files/LibreOffice/program/soffice.com"))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    found = shutil.which("soffice")
    if found:
        return found
    raise ValueError("для DOC/XLS/PPT/RTF и старого VSD нужен LibreOffice; установите его или сохраните файл в современном формате")


def convert(raw: bytes, suffix: str) -> tuple[bytes, str]:
    if suffix not in TARGETS:
        raise ValueError("неподдерживаемый старый формат")
    # Only real compound Office files / RTF, never HTML disguised as .doc.
    if not (raw.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1") or
            suffix in {".rtf", ".doc"} and raw.lstrip().startswith(b"{\\rtf")):
        raise ValueError("файл не соответствует старому формату Office")
    # Conservative guard: converter must not resolve document-supplied resources.
    # False positives are intentional; modern XML readers can read such docs safely.
    lowered = raw.lower().replace(b"\x00", b"")
    if any(marker in lowered for marker in (b"://", b"\\\\", b"file:", b"ddeauto", b"includepicture", b"includetext")):
        raise ValueError("старый документ содержит возможные внешние ссылки; пересохраните локально в современный формат перед импортом")
    command = executable()
    with _LOCK, tempfile.TemporaryDirectory(prefix="blatero-convert-") as tmp:
        folder = Path(tmp)
        profile = folder / "profile"
        (profile / "user").mkdir(parents=True)
        (profile / "user/registrymodifications.xcu").write_text(PROFILE, encoding="utf-8")
        source = folder / ("input" + suffix)
        source.write_bytes(raw)
        output = folder / "output"
        output.mkdir()
        returncode = run_converter(
                [command, "-env:UserInstallation=" + profile.as_uri(), "--headless",
                 "--norestore", "--nodefault", "--nofirststartwizard", "--convert-to",
                 TARGETS[suffix][1:], "--outdir", str(output), str(source)])
        target = output / ("input" + TARGETS[suffix])
        if returncode or not target.is_file():
            raise ValueError("LibreOffice не прочитал файл: он повреждён, защищён паролем или не поддерживается")
        if target.stat().st_size > MAX_OUTPUT:
            raise ValueError("преобразованный документ слишком велик")
        return target.read_bytes(), TARGETS[suffix]
