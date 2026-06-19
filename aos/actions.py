from __future__ import annotations

import os
import shlex
from dataclasses import asdict, dataclass, field


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
