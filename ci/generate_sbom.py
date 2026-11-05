"""Generate a deterministic CycloneDX SBOM from the pinned runtime lock."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements.lock"
PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;]+)$")


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def build(lock: Path = LOCK, *, version: str = "") -> dict:
    lock = Path(lock).resolve()
    base = lock.parent
    pins, sources, active = {}, {}, set()

    def read(file: Path) -> None:
        if file.is_symlink() or not file.resolve().is_relative_to(base):
            raise ValueError("SBOM include must remain inside its lock directory")
        file = file.resolve()
        if file in active:
            raise ValueError("SBOM include cycle")
        if file in sources:
            return
        active.add(file)
        raw = file.read_bytes()
        sources[file] = hashlib.sha256(raw).hexdigest()
        for number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            if value.startswith("-r "):
                include = Path(value[3:].strip())
                if include.is_absolute() or ".." in include.parts:
                    raise ValueError("SBOM include must be a relative file inside the lock directory")
                read(file.parent / include)
                continue
            match = PIN_RE.fullmatch(value)
            if not match:
                raise ValueError(f"{file.name}:{number}: SBOM требует точную фиксацию name==version")
            name, pinned = match.groups()
            canonical = _canonical(name)
            if canonical in pins and pins[canonical][1] != pinned:
                raise ValueError(f"SBOM conflicting pins: {name}")
            pins[canonical] = (name, pinned)
        active.remove(file)

    read(lock)
    components = []
    for canonical, (name, pinned) in pins.items():
        components.append({
            "type": "library",
            "bom-ref": f"pkg:pypi/{canonical}@{pinned}",
            "name": name,
            "version": pinned,
            "purl": f"pkg:pypi/{canonical}@{pinned}",
        })
    components.sort(key=lambda item: item["purl"])
    digest = sources[lock]
    combined = digest if len(sources) == 1 else json.dumps(
        {file.relative_to(base).as_posix(): value for file, value in sources.items()}, sort_keys=True)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, combined)}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application", "name": "Blatero",
                "version": version or "dev",
                "bom-ref": f"pkg:generic/blatero@{version or 'dev'}",
            },
            "properties": [
                {"name": "blatero:requirements-lock:sha256", "value": digest},
            ] + [{"name": "blatero:included-lock:" + file.relative_to(base).as_posix(), "value": value}
                 for file, value in sorted(sources.items()) if file != lock],
        },
        "components": components,
    }


def encoded(lock: Path = LOCK, *, version: str = "") -> bytes:
    return (json.dumps(build(lock, version=version), ensure_ascii=False,
                       sort_keys=True, indent=2) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=LOCK)
    parser.add_argument("--version", default="")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = encoded(args.lock, version=args.version)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(data)
    else:
        print(data.decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
