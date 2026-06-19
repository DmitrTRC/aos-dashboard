from __future__ import annotations

import json
from pathlib import Path

from aos.model import TestState


def collect_tests(path: Path) -> TestState:
    f = Path(path) / ".aos" / "state" / "tests.json"
    if not f.exists():
        return TestState(status="unknown")
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return TestState(status="unknown")
    status = "pass" if d.get("exit_code") == 0 else "fail"
    return TestState(
        status=status,
        last_run=d.get("time"),
        duration_sec=d.get("duration_sec"),
    )
