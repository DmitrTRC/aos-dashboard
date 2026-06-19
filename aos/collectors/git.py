from __future__ import annotations

import subprocess
from pathlib import Path

from aos.model import GitState


def _run(git: str, path: Path, args: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        [git, "-C", str(path), "--no-optional-locks", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def collect_git(path: Path, git: str = "/usr/bin/git", timeout: int = 5) -> GitState:
    path = Path(path)
    if not (path / ".git").exists():
        return GitState(is_repo=False)
    st = GitState(is_repo=True)
    try:
        r = _run(git, path, ["rev-parse", "--abbrev-ref", "HEAD"], timeout)
        st.branch = r.stdout.strip() or None
        r = _run(git, path, ["rev-parse", "HEAD"], timeout)
        st.head = r.stdout.strip() or None

        r = _run(git, path, ["status", "--porcelain"], timeout)
        for line in r.stdout.splitlines():
            if not line:
                continue
            x, y = line[0], line[1]
            if line.startswith("??"):
                st.untracked += 1
                continue
            if x not in (" ", "?"):
                st.staged += 1
            if y not in (" ", "?"):
                st.unstaged += 1

        r = _run(git, path, ["rev-list", "--left-right", "--count", "@{u}...HEAD"], timeout)
        if r.returncode == 0 and r.stdout.strip():
            behind, ahead = r.stdout.split()
            st.behind, st.ahead = int(behind), int(ahead)

        r = _run(git, path, ["diff", "--numstat", "HEAD"], timeout)
        for line in r.stdout.splitlines():
            cols = line.split("\t")
            if len(cols) >= 2 and cols[0].isdigit() and cols[1].isdigit():
                st.insertions += int(cols[0])
                st.deletions += int(cols[1])

        r = _run(git, path, ["log", "-1", "--pretty=%h %s"], timeout)
        st.last_commit = r.stdout.strip() or None
    except Exception as exc:  # subprocess error / timeout — never crash the aggregator
        st.error = str(exc)
    return st
