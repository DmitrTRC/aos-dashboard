from __future__ import annotations

import re
from pathlib import Path

from aos.model import ProgressState

_CHECK = re.compile(r"^\s*[-*]\s+\[( |x|X)\]")


def count_checkboxes(text: str) -> tuple[int, int]:
    done = total = 0
    for line in text.splitlines():
        m = _CHECK.match(line)
        if not m:
            continue
        total += 1
        if m.group(1) in ("x", "X"):
            done += 1
    return done, total


def _latest_plan(plans_dir: Path) -> Path | None:
    if not plans_dir.is_dir():
        return None
    plans = sorted(p for p in plans_dir.glob("*.md") if p.is_file())
    return plans[-1] if plans else None


def collect_progress(
    path: Path,
    mode: str = "auto",
    percent: int | None = None,
    plan_override: str | None = None,
) -> ProgressState:
    path = Path(path)
    if mode == "manual":
        return ProgressState(mode="manual", percent=percent)

    plan = (path / plan_override) if plan_override else _latest_plan(path / "docs" / "superpowers" / "plans")
    if not plan or not plan.exists():
        return ProgressState(mode="auto", percent=None, done=0, total=0)

    done, total = count_checkboxes(plan.read_text(encoding="utf-8", errors="ignore"))
    pct = round(100 * done / total) if total else None
    rel = str(plan.relative_to(path)) if str(plan).startswith(str(path)) else str(plan)
    return ProgressState(mode="auto", percent=pct, done=done, total=total, plan=rel)
