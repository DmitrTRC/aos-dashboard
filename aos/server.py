from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path

_ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


def host_allowed(host_header: str | None) -> bool:
    if not host_header:
        return False
    host = host_header.split(":", 1)[0]
    return host in _ALLOWED_HOSTS


def token_ok(provided: str | None, expected: str) -> bool:
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


def load_or_create_token(path: Path) -> str:
    path = Path(path)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(24)
    path.write_text(token, encoding="utf-8")
    os.chmod(path, 0o600)
    return token
