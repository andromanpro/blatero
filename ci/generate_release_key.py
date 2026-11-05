"""Create an Ed25519 release key outside the repository and print its public key."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("private_key")
    parser.add_argument("--public-key")
    args = parser.parse_args()
    private_path = Path(args.private_key).expanduser().resolve()
    if private_path.exists():
        raise SystemExit(f"ключ уже существует: {private_path}")
    private_path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    private_bytes = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    temporary = private_path.with_name(private_path.name + ".tmp")
    temporary.write_bytes(private_bytes)
    os.replace(temporary, private_path)
    public_bytes = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if args.public_key:
        public_path = Path(args.public_key).expanduser().resolve()
        public_path.parent.mkdir(parents=True, exist_ok=True)
        public_path.write_bytes(public_bytes)
        print(public_path)
    else:
        print(public_bytes.decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
