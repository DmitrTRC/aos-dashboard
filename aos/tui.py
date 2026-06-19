from __future__ import annotations

import sys
import time

from aos.aggregator import build_all
from aos.model import Project
from aos.tablefmt import colorize, render_table


def render_dash(projects: list[Project], color: bool = True) -> str:
    rows = []
    for p in projects:
        pct = f"{p.progress.percent}%" if p.progress.percent is not None else "-"
        rows.append([
            colorize(p.name, p.health.value, color),
            p.health.value,
            p.stage,
            p.git.branch or "-",
            "dirty" if p.git.dirty else "clean",
            p.graphify.status,
            pct,
            "●" if p.session.active else "·",
        ])
    return render_table(
        ["NAME", "HEALTH", "STAGE", "BRANCH", "GIT", "GRAPH", "PROG", "SES"], rows, color=color)


def dash_once(cfg: dict, conf_path=None, color: bool = True) -> str:
    return render_dash(build_all(cfg, conf_path=conf_path), color=color)


def dash_loop(cfg, conf_path=None, color=True, interval=5, out=sys.stdout, clock=time, iterations=None):
    n = 0
    while iterations is None or n < iterations:
        out.write("\033[2J\033[H" if color else "")
        out.write(dash_once(cfg, conf_path=conf_path, color=color) + "\n")
        out.flush()
        n += 1
        if iterations is not None and n >= iterations:
            break
        clock.sleep(interval)
