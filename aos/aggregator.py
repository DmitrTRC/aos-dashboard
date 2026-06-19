from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from aos.collectors.deadlines import compute_deadlines
from aos.collectors.git import collect_git
from aos.collectors.graphify import collect_graphify
from aos.collectors.progress import collect_progress
from aos.collectors.tests import collect_tests
from aos.config import expand
from aos.health import evaluate
from aos.model import Project
from aos.registry import ProjectRef, discover


def _load_yaml(path: Path) -> dict:
    f = path / ".aos" / "project.yaml"
    if not f.exists():
        return {}
    try:
        return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}


def build_project(ref: ProjectRef, cfg: dict) -> Project:
    path = Path(ref.path)
    y = _load_yaml(path)
    git_bin = cfg["tools"]["git"]
    timeout = cfg["timeouts_sec"]["collector"]
    gph = y.get("graphify", {}) or {}
    prog = y.get("progress", {}) or {}

    p = Project(
        name=y.get("name") or ref.name,
        title=y.get("title") or ref.name,
        path=str(path),
        layout=ref.layout,
        type=y.get("type", "unknown"),
        stage=y.get("stage", "idea"),
        priority=y.get("priority", "medium"),
        registered=ref.registered,
        has_yaml=bool(y),
        graphify_required=bool(gph.get("required", False)),
    )
    p.git = collect_git(path, git=git_bin, timeout=timeout)
    p.progress = collect_progress(
        path, mode=prog.get("mode", "auto"),
        percent=prog.get("percent"), plan_override=prog.get("plan"),
    )
    p.deadlines = compute_deadlines(y.get("deadlines"))
    p.graphify = collect_graphify(
        path, git_head=p.git.head,
        required=p.graphify_required, disabled=bool(gph.get("disabled", False)),
    )
    p.tests = collect_tests(path)
    p.health, p.health_reasons = evaluate(p, cfg)
    return p


def build_all(cfg: dict, conf_path: Path | None = None) -> list[Project]:
    if conf_path is None:
        conf_path = expand("~/.config/projects.conf")
    refs = discover(roots=cfg["roots"], conf_path=conf_path, exclude_dirs=cfg["exclude_dirs"])
    with ThreadPoolExecutor(max_workers=8) as pool:
        projects = list(pool.map(lambda r: build_project(r, cfg), refs))
    return sorted(projects, key=lambda p: p.name.lower())
