"""Build and verify source and portable release artifacts.

The private Ed25519 key must live outside Git. Use ``--init-key`` once to create
it and refresh ``release_public_key.pem`` in the repository.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path

from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ci import build_release, build_windows_portable  # noqa: E402
import release_manager  # noqa: E402


def _version() -> str:
    return str(tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])


def _public_from_private(private_key: Path) -> bytes:
    private = serialization.load_pem_private_key(private_key.read_bytes(), password=None)
    return private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _ensure_key(signing_key: Path, *, init_key: bool) -> None:
    public_key = ROOT / "release_public_key.pem"
    if init_key:
        if signing_key.exists():
            raise SystemExit(f"signing key already exists: {signing_key}")
        subprocess.run([
            sys.executable, str(ROOT / "ci" / "generate_release_key.py"),
            str(signing_key), "--public-key", str(public_key),
        ], cwd=ROOT, check=True)
    if not signing_key.is_file():
        raise SystemExit(
            f"signing key not found: {signing_key}. "
            "Run with --init-key once or pass --signing-key.")
    actual = _public_from_private(signing_key)
    expected = public_key.read_bytes()
    if actual != expected:
        raise SystemExit(
            "signing key does not match release_public_key.pem; refusing to build.")


def _require_clean_tracked_tree() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE)
    missing = [name for name in result.stdout.decode("utf-8").split("\0")
               if name and build_release._runtime_file(name)]
    if missing:
        raise SystemExit("untracked application files would be omitted: " + ", ".join(missing))
    for args, message in (
            (["git", "diff", "--quiet"], "working tree has unstaged changes"),
            (["git", "diff", "--cached", "--quiet"], "index has staged changes")):
        result = subprocess.run(args, cwd=ROOT)
        if result.returncode != 0:
            raise SystemExit(f"{message}; commit or revert tracked changes before release.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--signing-key",
        default=str(ROOT / ".release" / "release-signing-key.pem"),
        help="private Ed25519 key outside Git")
    parser.add_argument("--init-key", action="store_true")
    parser.add_argument("--version")
    parser.add_argument("--skip-portable", action="store_true")
    args = parser.parse_args()

    version = args.version or _version()
    signing_key = Path(args.signing_key).expanduser().resolve()
    _ensure_key(signing_key, init_key=args.init_key)
    if not args.init_key:
        _require_clean_tracked_tree()

    source = ROOT / "dist" / f"blatero-{version}.zip"
    source_result = build_release.build(source, signing_key, version)
    source_verify = release_manager.verify_package(
        source, ROOT / "release_public_key.pem")
    results = {"source": source_result, "source_verify": {
        "version": source_verify["version"],
        "files": len(source_verify["files"]),
        "package": source_verify["package"],
        "sha256": source_verify["package_sha256"],
        "size": source_verify["package_size"],
    }}

    if not args.skip_portable:
        portable = ROOT / "dist" / f"blatero-portable-{version}-win-x64.zip"
        portable_result = build_windows_portable.build(
            portable,
            cache=ROOT / ".tmp" / "portable-cache",
            wheelhouse=ROOT / ".tmp" / "portable-wheels",
            private_key_path=signing_key,
            version=version,
        )
        verify_result = build_windows_portable.verify(
            portable, ROOT / "release_public_key.pem")
        results["portable"] = portable_result
        results["portable_verify"] = verify_result

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
