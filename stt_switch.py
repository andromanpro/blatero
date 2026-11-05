"""Local request/ack protocol, bound to one recording and one request ID."""
import json
import os
import uuid

REQUEST = ".stt-switch.json"
RESULT = ".stt-switch-result.json"


def read(path):
    try:
        if path.stat().st_size > 16384:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write(path, value):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
