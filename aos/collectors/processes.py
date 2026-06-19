from __future__ import annotations

import subprocess
from pathlib import Path

from aos.model import ProcessInfo


def collect_processes(path, ps_bin: str = "/bin/ps", timeout: int = 5, runner=subprocess.run) -> list[ProcessInfo]:
    """Processes whose command line references the project path. Read-only, never raises."""
    try:
        cp = runner([ps_bin, "-axo", "pid=,command="], capture_output=True, text=True, timeout=timeout)
    except Exception:
        return []
    needle = str(Path(path))
    out: list[ProcessInfo] = []
    for line in (cp.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        pid_str, _, cmd = line.partition(" ")
        if not pid_str.isdigit() or needle not in cmd:
            continue
        out.append(ProcessInfo(pid=int(pid_str), command=cmd[:200]))
    return out
