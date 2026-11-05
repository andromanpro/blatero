"""Build a reproducible, Ed25519-signed source release ZIP."""
from __future__ import annotations

import argparse
import ast
import base64
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

try:  # module import in tests and direct ``python ci/build_release.py``
    from ci import generate_sbom
except ModuleNotFoundError:  # pragma: no cover - direct script path
    import generate_sbom

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT_FILES = {
    "README.md", "README.en.md", "DEVLOG.md", "LICENSE", "PRIVACY.md", "THIRD_PARTY_NOTICES.md", "TRANSCRIPT_FORMAT.md",
    "DIARIZATION_MODELS.md", "questions.md", "rubric.md", "pyproject.toml",
    "requirements.lock", "requirements-portable.txt", "requirements-chatterbox.txt", "requirements-video.txt",
    "start_blatero.cmd", "install_blatero.cmd", "release_public_key.pem",
    "project-agent-event.schema.json",
}
RUNTIME_PREFIXES = (
    "assets/",
    "templates/",
    "ci/__init__.py",
    "ci/build_release.py",
    "ci/build_windows_portable.py",
    "ci/generate_sbom.py",
    "ci/offline_help.py",
    "ci/generate_release_key.py",
    "ci/portable_launcher/",
    "ci/release_step.py",
    "docs/legal/",
    "docs/wiki/",
)
DEVELOPMENT_ONLY = {"test_roundtrip.py", "debug_two_channels.py", "devices_check.py"}


def _tracked_files() -> list[str]:
    result = subprocess.run(
        # Релиз строится только из зафиксированного снимка. Иначе случайный
        # неигнорируемый secret.py из рабочей копии может попасть в архив.
        ["git", "ls-files", "-z", "--cached"],
        cwd=ROOT, check=True,
        stdout=subprocess.PIPE)
    names = result.stdout.decode("utf-8").split("\0")
    if (ROOT / "release_public_key.pem").is_file():
        names.append("release_public_key.pem")
    return sorted(set(filter(None, names)))


def _runtime_file(name: str) -> bool:
    path = PurePosixPath(name)
    return name not in DEVELOPMENT_ONLY and (
        len(path.parts) == 1 and (name.endswith(".py") or name in RUNTIME_ROOT_FILES)
        or any(name.startswith(prefix) for prefix in RUNTIME_PREFIXES)
    )


def validate_runtime_inventory(names: list[str], *, root: Path | None = None) -> list[str]:
    """Fail closed when tracked runtime code depends on an omitted local file.

    Never add untracked files automatically. Both source and portable builders use
    this check, including direct invocations which bypass release_step.
    """
    root = root or ROOT
    runtime = {name for name in names if _runtime_file(name)}
    missing = set()
    for name in sorted(runtime):
        file = root / name
        if not file.is_file() or file.is_symlink():
            missing.add(name)
            continue
        if file.suffix not in {'.py', '.js', '.css', '.html'}:
            continue
        text = file.read_text(encoding='utf-8-sig')
        candidates = set(re.findall(r'/(?:projects/)?assets/([A-Za-z0-9_./-]+\.(?:js|css|png|svg|ico|ttf|wav))', text))
        if file.suffix == '.py':
            tree = ast.parse(text, filename=name)
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    modules = [node.module] + [node.module + '.' + alias.name for alias in node.names if alias.name != '*']
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if re.fullmatch(r'templates/[A-Za-z0-9_./-]+\.html', node.value) and node.value not in runtime:
                        missing.add(node.value)
                    if re.fullmatch(r'[A-Za-z0-9_./-]+\.(?:js|css|png|svg|ico|ttf|wav)', node.value):
                        if (root / 'assets' / node.value).is_file():
                            candidates.add(node.value)
                for module in modules:
                    for relative in (module.replace('.', '/') + '.py', module.replace('.', '/') + '/__init__.py'):
                        if (root / relative).is_file() and relative not in runtime:
                            missing.add(relative)
        missing.update('assets/' + asset for asset in candidates if 'assets/' + asset not in runtime)
    if missing:
        raise ValueError('Runtime files missing from tracked inventory: ' + ', '.join(sorted(missing)))
    return sorted(runtime)


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def _created_at() -> str:
    epoch = os.getenv("SOURCE_DATE_EPOCH", "").strip()
    if epoch:
        return dt.datetime.fromtimestamp(
            int(epoch), tz=dt.timezone.utc).isoformat(timespec="seconds")
    result = subprocess.run(
        ["git", "log", "-1", "--format=%cI"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE)
    return result.stdout.strip()


def build(output: Path, private_key_path: Path, version: str | None = None) -> dict:
    private = serialization.load_pem_private_key(
        private_key_path.read_bytes(), password=None)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError("ключ релиза должен быть Ed25519")
    if version is None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        version = str(project["project"]["version"])
    payload: dict[str, bytes] = {}
    files: dict[str, dict] = {}
    for name in validate_runtime_inventory(_tracked_files()):
        data = (ROOT / Path(*PurePosixPath(name).parts)).read_bytes()
        payload[name] = data
        files[name] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    sbom_name = "SBOM.cdx.json"
    sbom = generate_sbom.encoded(ROOT / "requirements.lock", version=version)
    payload[sbom_name] = sbom
    files[sbom_name] = {
        "sha256": hashlib.sha256(sbom).hexdigest(), "size": len(sbom)}
    if "release_public_key.pem" not in payload:
        raise ValueError("release_public_key.pem отсутствует")
    manifest = {
        "schema_version": 1,
        "product": "blatero",
        "version": version,
        "created_at": _created_at(),
        "files": files,
    }
    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    signature = base64.b64encode(private.sign(manifest_bytes))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", compresslevel=9) as archive:
        for name, data in payload.items():
            archive.writestr(_zip_info(name), data)
        archive.writestr(_zip_info("release-manifest.json"), manifest_bytes)
        archive.writestr(_zip_info("release-manifest.sig"), signature)
    temporary.replace(output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="ascii")
    return {"version": version, "files": len(files), "output": str(output),
            "sha256": digest, "size": output.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signing-key", required=True)
    parser.add_argument("--output")
    parser.add_argument("--version")
    args = parser.parse_args()
    version = args.version or tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    output = Path(args.output) if args.output else ROOT / "dist" / f"blatero-{version}.zip"
    result = build(output.resolve(), Path(args.signing_key).resolve(), args.version)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
