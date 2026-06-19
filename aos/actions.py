from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


class ActionError(Exception):
    """Raised when an action is rejected before/without execution."""


@dataclass
class ActionResult:
    kind: str
    ok: bool
    command: list[str] = field(default_factory=list)
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def validate_command(cmd: str, allowlist: list[str]) -> list[str]:
    """Parse a command string into argv and verify argv[0] is allowlisted.

    Safety model: we never use a shell. shlex.split tokenizes respecting quotes,
    so metacharacters in arguments are literal and harmless. We only gate the
    executable (argv[0] basename) against the allowlist.
    """
    try:
        argv = shlex.split(cmd)
    except ValueError as exc:
        raise ActionError(f"не разобрать команду: {exc}") from exc
    if not argv:
        raise ActionError("пустая команда")
    exe = os.path.basename(argv[0])
    if exe not in allowlist:
        raise ActionError(f"исполняемый '{exe}' не в exec_allowlist")
    return argv


def run_whitelisted(argv, cwd, timeout, env=None, runner=subprocess.run):
    """Execute argv with NO shell, sanitised env, timeout, bound cwd."""
    safe_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }
    if env:
        safe_env.update(env)
    return runner(
        list(argv),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=safe_env,
    )


def log_action(project_path, result: ActionResult) -> None:
    state = Path(project_path) / ".aos" / "state"
    state.mkdir(parents=True, exist_ok=True)
    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "kind": result.kind,
        "ok": result.ok,
        "exit_code": result.exit_code,
        "command": result.command,
    }
    with (state / "actions.log").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
