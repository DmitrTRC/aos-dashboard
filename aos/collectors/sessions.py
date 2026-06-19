from __future__ import annotations

import subprocess

from aos.model import ProcessInfo, SessionState

_AGENTS = ("claude", "opencode", "codex")


def live_sessions(zellij_bin: str, timeout: int = 5, runner=subprocess.run) -> set[str]:
    """Names of live (non-EXITED) zellij sessions. Never raises."""
    try:
        cp = runner([zellij_bin, "list-sessions", "-n"], capture_output=True, text=True, timeout=timeout)
    except Exception:
        return set()
    names: set[str] = set()
    for line in (cp.stdout or "").splitlines():
        if not line.strip() or "EXITED" in line:
            continue
        names.add(line.split()[0])
    return names


def collect_session(project_name: str, live: set[str], processes: list[ProcessInfo]) -> SessionState:
    active = project_name in live
    agents = sorted({
        a for p in processes for a in _AGENTS if a in p.command.lower()
    })
    return SessionState(
        active=active,
        session_name=project_name if active else None,
        agents=agents,
    )
