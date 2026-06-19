from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from aos.model import GraphifyState

_COMMIT = re.compile(r"Built from commit:\s*`?([0-9a-fA-F]{7,40})`?")


def _hook_installed(path: Path) -> bool:
    hook = path / ".git" / "hooks" / "post-commit"
    if not hook.exists():
        return False
    return "graphify-hook-start" in hook.read_text(encoding="utf-8", errors="ignore")


def _iso_mtime(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()


def collect_graphify(
    path: Path,
    git_head: str | None = None,
    required: bool = False,
    disabled: bool = False,
) -> GraphifyState:
    path = Path(path)
    hook = _hook_installed(path)
    if disabled:
        return GraphifyState(status="disabled", hook_installed=hook)

    out = path / "graphify-out"
    if not out.is_dir():
        return GraphifyState(status="missing", hook_installed=hook)

    st = GraphifyState(status="fresh", hook_installed=hook)
    manifest = out / "manifest.json"
    if manifest.exists():
        st.last_update = _iso_mtime(manifest)

    report = out / "GRAPH_REPORT.md"
    if report.exists():
        m = _COMMIT.search(report.read_text(encoding="utf-8", errors="ignore"))
        if m:
            st.built_commit = m.group(1)

    if st.built_commit and git_head:
        short = st.built_commit
        st.status = "fresh" if git_head.startswith(short) or short.startswith(git_head) else "stale"
    return st
