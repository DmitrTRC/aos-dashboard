# AOS Core + CLI (read-only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the headless `aos` control-plane core and a read-only terminal CLI (`aos status/ls/show/scan/init/doctor`) that discovers projects in `~/Projects`, reads their state (git, progress, deadlines, graphify, tests) and renders health.

**Architecture:** A small Python package. A pure discovery+model layer (`config`, `registry`, `model`), independent read-only `collectors/` (each subprocess-bound with a timeout, never raises), a `health` evaluator, an `aggregator` that runs collectors concurrently into a `Project` snapshot, and a `cli` that renders a table or `--json`. No web/actions in this plan — those are follow-up plans.

**Tech Stack:** Python 3.11+, stdlib (`argparse`, `subprocess`, `concurrent.futures`, `http`/later), single external dependency **PyYAML**, tests via **pytest**.

**Scope note:** This plan = spec Milestones 1–2 (read-only). Follow-up plans: (2) actions + safety + web `/wall`; (3) sensors (processes/sessions/security) + TUI + polish.

---

### Task 0: Project skeleton & packaging

**Files:**
- Create: `pyproject.toml`
- Create: `aos/__init__.py`
- Create: `aos/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "aos-dashboard"
version = "0.1.0"
description = "Local project dashboard / control plane (aos)"
requires-python = ">=3.11"
dependencies = ["PyYAML>=6"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
aos = "aos.cli:main"

[tool.setuptools.packages.find]
include = ["aos*"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
```

- [ ] **Step 2: Create package init files**

`aos/__init__.py`:

```python
__version__ = "0.1.0"
```

`aos/__main__.py`:

```python
from aos.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

`tests/__init__.py`: empty file.

- [ ] **Step 3: Create `tests/conftest.py` with shared fixtures**

```python
import subprocess
from pathlib import Path

import pytest


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@e.st")
    _git(repo, "config", "user.name", "test")
    (repo / "README.md").write_text("# demo\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo
```

- [ ] **Step 4: Verify the package imports and pytest runs**

Run: `python -m pip install -e ".[dev]" && python -c "import aos; print(aos.__version__)" && pytest`
Expected: prints `0.1.0`; pytest reports "no tests ran" (exit 5) or 0 collected — no error.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml aos/ tests/
git commit -m "chore: package skeleton + pytest setup"
```

---

### Task 1: Config loading (`aos/config.py`)

**Files:**
- Create: `aos/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from aos.config import DEFAULT_CONFIG, load_config


def test_defaults_when_no_file(tmp_path: Path):
    cfg = load_config(tmp_path / "missing.yaml")
    assert cfg["port"] == 7777
    assert cfg["roots"] == ["~/Projects"]
    assert "git" in cfg["exec_allowlist"]


def test_user_file_overrides_deep(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text("port: 9000\ntools:\n  git: /custom/git\n")
    cfg = load_config(p)
    assert cfg["port"] == 9000
    assert cfg["tools"]["git"] == "/custom/git"
    # untouched defaults survive the deep-merge
    assert cfg["tools"]["zellij"] == "/opt/homebrew/bin/zellij"
    assert cfg["refresh_interval_sec"] == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.config'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml

DEFAULT_CONFIG: dict = {
    "roots": ["~/Projects"],
    "port": 7777,
    "refresh_interval_sec": 10,
    "open_browser": True,
    "tools": {
        "git": "/usr/bin/git",
        "zellij": "/opt/homebrew/bin/zellij",
        "kitty": "/Applications/kitty.app/Contents/MacOS/kitty",
        "graphify": "graphify",
    },
    "session": {
        "launch_cmd_template": "{kitty} -1 -e /bin/zsh -ic 'project {name}'",
    },
    "exec_allowlist": [
        "git", "pnpm", "npm", "yarn", "pytest", "python",
        "node", "make", "just", "bats", "graphify", "cargo", "go",
    ],
    "exclude_dirs": [
        "node_modules", ".git", "dist", "build", "target",
        ".venv", "venv", "__pycache__",
    ],
    "timeouts_sec": {"collector": 5, "tests": 120, "graphify": 300},
    "health": {"deadline_warn_days": 7, "inactive_warn_days": 14},
}


def config_path() -> Path:
    return Path(os.path.expanduser("~/.config/aos/config.yaml"))


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: Path | None = None) -> dict:
    path = path or config_path()
    if path.exists():
        user = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        user = {}
    return _deep_merge(DEFAULT_CONFIG, user)


def expand(p: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(p)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/config.py tests/test_config.py
git commit -m "feat(config): load_config with deep-merge over defaults"
```

---

### Task 2: Data model (`aos/model.py`)

**Files:**
- Create: `aos/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing test**

```python
import json

from aos.model import (
    Deadline, GitState, GraphifyState, Health, Project, ProgressState, TestState,
)


def test_gitstate_dirty():
    assert GitState(is_repo=True, untracked=2).dirty is True
    assert GitState(is_repo=True).dirty is False


def test_project_to_dict_is_json_serialisable():
    p = Project(name="village", title="Village", path="/x/village")
    p.health = Health.GREEN
    p.git = GitState(is_repo=True, branch="main", untracked=1)
    p.deadlines = [Deadline(title="MVP", due="2026-07-01", days_left=12)]
    d = p.to_dict()
    assert d["health"] == "green"
    assert d["git"]["branch"] == "main"
    assert d["deadlines"][0]["title"] == "MVP"
    json.dumps(d)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.model'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


class Health(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNKNOWN = "unknown"


@dataclass
class GitState:
    is_repo: bool = False
    branch: Optional[str] = None
    ahead: int = 0
    behind: int = 0
    staged: int = 0
    unstaged: int = 0
    untracked: int = 0
    insertions: int = 0
    deletions: int = 0
    last_commit: Optional[str] = None
    head: Optional[str] = None
    error: Optional[str] = None

    @property
    def dirty(self) -> bool:
        return (self.staged + self.unstaged + self.untracked) > 0


@dataclass
class GraphifyState:
    status: str = "missing"  # fresh|stale|missing|disabled|error
    hook_installed: bool = False
    built_commit: Optional[str] = None
    last_update: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ProgressState:
    mode: str = "auto"
    percent: Optional[int] = None
    done: int = 0
    total: int = 0
    plan: Optional[str] = None


@dataclass
class Deadline:
    title: str
    due: str
    days_left: Optional[int] = None
    overdue: bool = False


@dataclass
class TestState:
    status: str = "unknown"  # pass|fail|unknown
    last_run: Optional[str] = None
    duration_sec: Optional[float] = None


@dataclass
class Project:
    name: str
    title: str
    path: str
    layout: str = ""
    type: str = "unknown"
    stage: str = "idea"
    priority: str = "medium"
    registered: bool = True
    has_yaml: bool = False
    graphify_required: bool = False
    git: GitState = field(default_factory=GitState)
    graphify: GraphifyState = field(default_factory=GraphifyState)
    progress: ProgressState = field(default_factory=ProgressState)
    deadlines: list[Deadline] = field(default_factory=list)
    tests: TestState = field(default_factory=TestState)
    health: Health = Health.UNKNOWN
    health_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["health"] = self.health.value
        d["git"]["dirty"] = self.git.dirty
        return d
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_model.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/model.py tests/test_model.py
git commit -m "feat(model): dataclasses + JSON-serialisable Project"
```

---

### Task 3: Registry & discovery (`aos/registry.py`)

**Files:**
- Create: `aos/registry.py`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from aos.registry import ProjectRef, discover, expand_path, parse_projects_conf


def test_parse_skips_comments_and_trims():
    text = "# comment\n\nvillage | $HOME/Projects/village-emrg | dev\nresearch|~/Projects/research|research\n"
    entries = parse_projects_conf(text)
    assert entries[0] == ("village", "$HOME/Projects/village-emrg", "dev")
    assert entries[1] == ("research", "~/Projects/research", "research")


def test_discover_reconciles_registry_name_vs_dirname(tmp_path: Path, monkeypatch):
    root = tmp_path / "Projects"
    (root / "village-emrg" / ".git").mkdir(parents=True)
    (root / "loose" / ".git").mkdir(parents=True)  # not in registry
    conf = tmp_path / "projects.conf"
    conf.write_text(f"village | {root}/village-emrg | dev\n")

    refs = discover(roots=[str(root)], conf_path=conf, exclude_dirs=["node_modules"])
    by_path = {Path(r.path).name: r for r in refs}
    assert by_path["village-emrg"].name == "village"      # registry name wins
    assert by_path["village-emrg"].registered is True
    assert by_path["loose"].name == "loose"               # falls back to dirname
    assert by_path["loose"].registered is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.registry'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProjectRef:
    name: str
    path: str
    layout: str = ""
    registered: bool = True


def expand_path(raw: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def parse_projects_conf(text: str) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split("|")]
        if len(parts) < 2:
            continue
        name, path = parts[0], parts[1]
        layout = parts[2] if len(parts) > 2 else ""
        entries.append((name, path, layout))
    return entries


def _is_project_dir(d: Path) -> bool:
    return (d / ".git").exists() or (d / ".aos" / "project.yaml").exists()


def discover(
    roots: list[str],
    conf_path: Path | None = None,
    exclude_dirs: list[str] | None = None,
) -> list[ProjectRef]:
    exclude = set(exclude_dirs or [])
    refs: dict[str, ProjectRef] = {}  # keyed by resolved path

    if conf_path and Path(conf_path).exists():
        for name, raw, layout in parse_projects_conf(Path(conf_path).read_text(encoding="utf-8")):
            p = expand_path(raw)
            refs[str(p)] = ProjectRef(name=name, path=str(p), layout=layout, registered=True)

    for root in roots:
        rp = expand_path(root)
        if not rp.is_dir():
            continue
        for child in sorted(rp.iterdir()):
            if not child.is_dir() or child.name in exclude or child.name.startswith("."):
                continue
            key = str(child.resolve())
            if key in refs:
                continue
            if _is_project_dir(child):
                refs[key] = ProjectRef(name=child.name, path=key, layout="", registered=False)

    return list(refs.values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_registry.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/registry.py tests/test_registry.py
git commit -m "feat(registry): projects.conf parse + roots discovery with reconcile"
```

---

### Task 4: Git collector (`aos/collectors/git.py`)

**Files:**
- Create: `aos/collectors/__init__.py` (empty)
- Create: `aos/collectors/git.py`
- Test: `tests/test_collector_git.py`

- [ ] **Step 1: Write the failing test**

```python
import subprocess
from pathlib import Path

from aos.collectors.git import collect_git


def test_clean_repo(git_repo: Path):
    st = collect_git(git_repo, git="git")
    assert st.is_repo is True
    assert st.branch == "main"
    assert st.dirty is False
    assert st.head and len(st.head) >= 7
    assert st.last_commit and "init" in st.last_commit


def test_dirty_counts(git_repo: Path):
    (git_repo / "new.txt").write_text("x\n")           # untracked
    (git_repo / "README.md").write_text("# changed\n")  # unstaged
    st = collect_git(git_repo, git="git")
    assert st.untracked == 1
    assert st.unstaged == 1
    assert st.dirty is True


def test_not_a_repo(tmp_path: Path):
    assert collect_git(tmp_path, git="git").is_repo is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_collector_git.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.collectors'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_collector_git.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/collectors/__init__.py aos/collectors/git.py tests/test_collector_git.py
git commit -m "feat(collectors): read-only git collector"
```

---

### Task 5: Progress collector (`aos/collectors/progress.py`)

**Files:**
- Create: `aos/collectors/progress.py`
- Test: `tests/test_collector_progress.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from aos.collectors.progress import collect_progress, count_checkboxes


def test_count_checkboxes():
    md = "- [ ] a\n- [x] b\n- [X] c\nnot a box\n  - [ ] nested d\n"
    assert count_checkboxes(md) == (2, 4)


def test_collect_progress_picks_latest_plan(tmp_path: Path):
    plans = tmp_path / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-06-01-old.md").write_text("- [x] done\n- [ ] todo\n")
    (plans / "2026-06-15-new.md").write_text("- [x] a\n- [x] b\n- [ ] c\n- [ ] d\n")
    ps = collect_progress(tmp_path)
    assert ps.plan.endswith("2026-06-15-new.md")
    assert (ps.done, ps.total) == (2, 4)
    assert ps.percent == 50


def test_manual_mode(tmp_path: Path):
    ps = collect_progress(tmp_path, mode="manual", percent=80)
    assert ps.mode == "manual"
    assert ps.percent == 80
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_collector_progress.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.collectors.progress'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_collector_progress.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/collectors/progress.py tests/test_collector_progress.py
git commit -m "feat(collectors): progress from superpowers plan checklists"
```

---

### Task 6: Deadlines collector (`aos/collectors/deadlines.py`)

**Files:**
- Create: `aos/collectors/deadlines.py`
- Test: `tests/test_collector_deadlines.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

from aos.collectors.deadlines import compute_deadlines


def test_days_left_and_overdue():
    items = [
        {"title": "soon", "due": "2026-06-25"},
        {"title": "past", "due": "2026-06-10"},
        {"title": "bad", "due": "not-a-date"},
    ]
    out = compute_deadlines(items, today=date(2026, 6, 19))
    assert out[0].days_left == 6 and out[0].overdue is False
    assert out[1].days_left == -9 and out[1].overdue is True
    assert out[2].days_left is None and out[2].overdue is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_collector_deadlines.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.collectors.deadlines'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from datetime import date

from aos.model import Deadline


def compute_deadlines(items: list[dict] | None, today: date | None = None) -> list[Deadline]:
    today = today or date.today()
    out: list[Deadline] = []
    for it in items or []:
        due = str(it.get("due", ""))
        d = Deadline(title=str(it.get("title", "")), due=due)
        try:
            dd = date.fromisoformat(due)
            d.days_left = (dd - today).days
            d.overdue = d.days_left < 0
        except ValueError:
            pass
        out.append(d)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_collector_deadlines.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/collectors/deadlines.py tests/test_collector_deadlines.py
git commit -m "feat(collectors): deadline days-left / overdue"
```

---

### Task 7: Graphify collector (`aos/collectors/graphify.py`)

**Files:**
- Create: `aos/collectors/graphify.py`
- Test: `tests/test_collector_graphify.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from aos.collectors.graphify import collect_graphify


def test_missing(tmp_path: Path):
    st = collect_graphify(tmp_path)
    assert st.status == "missing"
    assert st.hook_installed is False


def test_disabled(tmp_path: Path):
    assert collect_graphify(tmp_path, disabled=True).status == "disabled"


def test_fresh_vs_stale_by_commit(tmp_path: Path):
    out = tmp_path / "graphify-out"
    out.mkdir()
    (out / "manifest.json").write_text("{}")
    (out / "GRAPH_REPORT.md").write_text("Built from commit: `abc1234`\n")
    assert collect_graphify(tmp_path, git_head="abc1234def").status == "fresh"
    assert collect_graphify(tmp_path, git_head="9999999").status == "stale"


def test_hook_detected(tmp_path: Path):
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "post-commit").write_text("#!/bin/sh\n# graphify-hook-start\n")
    (tmp_path / "graphify-out").mkdir()
    st = collect_graphify(tmp_path, git_head=None)
    assert st.hook_installed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_collector_graphify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.collectors.graphify'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_collector_graphify.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/collectors/graphify.py tests/test_collector_graphify.py
git commit -m "feat(collectors): graphify freshness by built-commit + hook sensor"
```

---

### Task 8: Tests-state collector (`aos/collectors/tests.py`)

**Files:**
- Create: `aos/collectors/tests.py`
- Test: `tests/test_collector_tests.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

from aos.collectors.tests import collect_tests


def test_unknown_when_no_state(tmp_path: Path):
    assert collect_tests(tmp_path).status == "unknown"


def test_pass_and_fail(tmp_path: Path):
    state = tmp_path / ".aos" / "state"
    state.mkdir(parents=True)
    (state / "tests.json").write_text(json.dumps(
        {"exit_code": 0, "time": "2026-06-19T10:00:00+00:00", "duration_sec": 4.2}
    ))
    ts = collect_tests(tmp_path)
    assert ts.status == "pass"
    assert ts.duration_sec == 4.2

    (state / "tests.json").write_text(json.dumps({"exit_code": 1}))
    assert collect_tests(tmp_path).status == "fail"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_collector_tests.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.collectors.tests'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_collector_tests.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/collectors/tests.py tests/test_collector_tests.py
git commit -m "feat(collectors): tests state from .aos/state/tests.json"
```

---

### Task 9: Health evaluator (`aos/health.py`)

**Files:**
- Create: `aos/health.py`
- Test: `tests/test_health.py`

- [ ] **Step 1: Write the failing test**

```python
from aos.config import DEFAULT_CONFIG
from aos.health import evaluate
from aos.model import Deadline, GitState, GraphifyState, Health, Project, TestState


def _proj(**kw) -> Project:
    p = Project(name="x", title="x", path="/x", has_yaml=True)
    p.git = GitState(is_repo=True)
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def test_unknown_when_no_repo_no_yaml():
    p = Project(name="x", title="x", path="/x")
    h, reasons = evaluate(p, DEFAULT_CONFIG)
    assert h == Health.UNKNOWN


def test_red_on_failing_tests():
    p = _proj(tests=TestState(status="fail"))
    h, reasons = evaluate(p, DEFAULT_CONFIG)
    assert h == Health.RED
    assert any("тест" in r.lower() for r in reasons)


def test_red_on_overdue_deadline():
    p = _proj(deadlines=[Deadline(title="d", due="2026-01-01", days_left=-5, overdue=True)])
    assert evaluate(p, DEFAULT_CONFIG)[0] == Health.RED


def test_yellow_on_dirty_tree():
    p = _proj(git=GitState(is_repo=True, untracked=2))
    assert evaluate(p, DEFAULT_CONFIG)[0] == Health.YELLOW


def test_green_when_clean():
    p = _proj()
    assert evaluate(p, DEFAULT_CONFIG)[0] == Health.GREEN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.health'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from aos.model import Health, Project


def evaluate(p: Project, cfg: dict) -> tuple[Health, list[str]]:
    if not p.git.is_repo and not p.has_yaml:
        return Health.UNKNOWN, ["не git-репозиторий, нет .aos/project.yaml"]

    red: list[str] = []
    yellow: list[str] = []

    if p.tests.status == "fail":
        red.append("тесты упали")
    if any(d.overdue for d in p.deadlines):
        red.append("дедлайн просрочен")
    if p.graphify.status == "missing" and p.graphify_required:
        red.append("Graphify отсутствует (required)")

    if p.git.is_repo and (p.git.staged + p.git.unstaged + p.git.untracked) > 0:
        yellow.append("незакоммиченные изменения")
    if p.graphify.status == "stale":
        yellow.append("Graphify устарел")

    warn = cfg["health"]["deadline_warn_days"]
    for d in p.deadlines:
        if d.days_left is not None and 0 <= d.days_left <= warn:
            yellow.append(f"дедлайн через {d.days_left} дн")

    if red:
        return Health.RED, red + yellow
    if yellow:
        return Health.YELLOW, yellow
    return Health.GREEN, ["всё чисто"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/health.py tests/test_health.py
git commit -m "feat(health): green/yellow/red/unknown evaluator with reasons"
```

---

### Task 10: Aggregator (`aos/aggregator.py`)

**Files:**
- Create: `aos/aggregator.py`
- Test: `tests/test_aggregator.py`

- [ ] **Step 1: Write the failing test**

```python
import subprocess
from pathlib import Path

import yaml

from aos.aggregator import build_all, build_project
from aos.config import DEFAULT_CONFIG
from aos.model import Health
from aos.registry import ProjectRef


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True)


def test_build_project_reads_yaml_and_runs_collectors(git_repo: Path):
    aos_dir = git_repo / ".aos"
    aos_dir.mkdir()
    (aos_dir / "project.yaml").write_text(yaml.safe_dump({
        "name": "demo", "title": "Demo", "type": "app", "stage": "build",
        "deadlines": [{"title": "MVP", "due": "2099-01-01"}],
    }))
    ref = ProjectRef(name="demo", path=str(git_repo), layout="dev", registered=True)
    cfg = dict(DEFAULT_CONFIG, tools=dict(DEFAULT_CONFIG["tools"], git="git"))
    p = build_project(ref, cfg)
    assert p.title == "Demo"
    assert p.stage == "build"
    assert p.git.branch == "main"
    assert p.health in (Health.GREEN, Health.YELLOW)
    assert p.deadlines[0].title == "MVP"


def test_build_all_discovers(tmp_path: Path, git_repo: Path):
    root = git_repo.parent
    cfg = dict(DEFAULT_CONFIG, roots=[str(root)], tools=dict(DEFAULT_CONFIG["tools"], git="git"))
    projects = build_all(cfg, conf_path=tmp_path / "none.conf")
    assert any(p.path == str(git_repo.resolve()) for p in projects)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_aggregator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.aggregator'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_aggregator.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/aggregator.py tests/test_aggregator.py
git commit -m "feat(aggregator): build Project snapshots concurrently"
```

---

### Task 11: Scaffold `aos init` (`aos/scaffold.py`)

**Files:**
- Create: `aos/scaffold.py`
- Test: `tests/test_scaffold.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import yaml

from aos.scaffold import init_project


def test_init_creates_stub_and_gitignore(tmp_path: Path):
    created = init_project(tmp_path, name="village")
    assert created is True
    y = yaml.safe_load((tmp_path / ".aos" / "project.yaml").read_text())
    assert y["name"] == "village"
    assert y["progress"]["mode"] == "auto"
    assert (tmp_path / ".aos" / "state").is_dir()
    assert ".aos/state/" in (tmp_path / ".gitignore").read_text()


def test_init_is_idempotent(tmp_path: Path):
    assert init_project(tmp_path, name="x") is True
    assert init_project(tmp_path, name="x") is False  # already exists, not overwritten
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scaffold.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.scaffold'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from pathlib import Path

import yaml

_STUB = {
    "name": None,
    "title": None,
    "type": "unknown",
    "stage": "idea",
    "priority": "medium",
    "tags": [],
    "deadlines": [],
    "progress": {"mode": "auto", "percent": None, "plan": None},
    "graphify": {"required": False, "disabled": False},
    "commands": {},
    "session": {"launch": None},
    "dashboard": {"show_on_wall": True},
}


def _ensure_gitignore(path: Path) -> None:
    gi = path / ".gitignore"
    line = ".aos/state/"
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if line not in existing.splitlines():
        with gi.open("a", encoding="utf-8") as fh:
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            fh.write(line + "\n")


def init_project(path: Path, name: str) -> bool:
    path = Path(path)
    aos_dir = path / ".aos"
    (aos_dir / "state").mkdir(parents=True, exist_ok=True)
    _ensure_gitignore(path)

    yaml_file = aos_dir / "project.yaml"
    if yaml_file.exists():
        return False
    stub = dict(_STUB)
    stub["name"] = name
    stub["title"] = name
    yaml_file.write_text(yaml.safe_dump(stub, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scaffold.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/scaffold.py tests/test_scaffold.py
git commit -m "feat(scaffold): aos init writes .aos/project.yaml stub + gitignore"
```

---

### Task 12: Table formatter (`aos/tablefmt.py`)

**Files:**
- Create: `aos/tablefmt.py`
- Test: `tests/test_tablefmt.py`

- [ ] **Step 1: Write the failing test**

```python
from aos.tablefmt import render_table


def test_render_table_aligns_and_includes_values():
    rows = [["village", "green", "main"], ["research", "yellow", "main"]]
    out = render_table(["NAME", "HEALTH", "BRANCH"], rows, color=False)
    lines = out.splitlines()
    assert "NAME" in lines[0] and "HEALTH" in lines[0]
    assert "village" in out and "research" in out
    # column is wide enough to fit the longest value
    assert lines[0].index("HEALTH") >= len("research") + 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tablefmt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.tablefmt'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

_COLORS = {
    "green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m",
    "unknown": "\033[90m",
}
_RESET = "\033[0m"


def colorize(text: str, health: str, color: bool = True) -> str:
    if not color or health not in _COLORS:
        return text
    return f"{_COLORS[health]}{text}{_RESET}"


def render_table(headers: list[str], rows: list[list[str]], color: bool = True) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    out = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    for row in rows:
        out.append("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))
    return "\n".join(out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tablefmt.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/tablefmt.py tests/test_tablefmt.py
git commit -m "feat(tablefmt): minimal ANSI table renderer"
```

---

### Task 13: CLI (`aos/cli.py`) — status/ls/show/scan/init/doctor

**Files:**
- Create: `aos/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import subprocess
from pathlib import Path

import yaml

from aos.cli import main


def _setup(tmp_path: Path) -> Path:
    root = tmp_path / "Projects"
    repo = root / "demo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@e.st"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True, capture_output=True)
    (repo / "README.md").write_text("# demo\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
    return root


def test_status_json(tmp_path: Path, capsys):
    root = _setup(tmp_path)
    code = main(["status", "--json", "--root", str(root)])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert any(p["name"] == "demo" for p in data)


def test_init_command(tmp_path: Path, capsys):
    root = _setup(tmp_path)
    code = main(["init", "demo", "--root", str(root)])
    assert code == 0
    assert (root / "demo" / ".aos" / "project.yaml").exists()


def test_status_exit_code_flag_red(tmp_path: Path, capsys):
    root = _setup(tmp_path)
    repo = root / "demo"
    state = repo / ".aos" / "state"
    state.mkdir(parents=True)
    (state / "tests.json").write_text(json.dumps({"exit_code": 1}))
    (repo / ".aos" / "project.yaml").write_text(yaml.safe_dump({"name": "demo"}))
    code = main(["status", "--exit-code", "--root", str(root)])
    assert code == 2  # red present
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.cli'` (or AttributeError on `main`)

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aos import __version__
from aos.aggregator import build_all, build_project
from aos.config import expand, load_config
from aos.model import Health, Project
from aos.registry import ProjectRef, discover
from aos.scaffold import init_project
from aos.tablefmt import colorize, render_table


def _apply_root_override(cfg: dict, root: str | None) -> dict:
    if root:
        cfg = dict(cfg, roots=[root])
    return cfg


def _conf_path() -> Path:
    return expand("~/.config/projects.conf")


def _snapshot(cfg: dict) -> list[Project]:
    return build_all(cfg, conf_path=_conf_path())


def _cmd_status(args, cfg) -> int:
    projects = _snapshot(cfg)
    if args.json:
        print(json.dumps([p.to_dict() for p in projects], ensure_ascii=False, indent=2))
    else:
        rows = []
        for p in projects:
            diff = f"+{p.git.insertions}/-{p.git.deletions}" if p.git.is_repo else "-"
            pct = f"{p.progress.percent}%" if p.progress.percent is not None else "-"
            rows.append([
                colorize(p.name, p.health.value, args.color),
                p.health.value, p.stage, p.git.branch or "-",
                "dirty" if p.git.dirty else "clean", p.graphify.status, pct,
            ])
        print(render_table(
            ["NAME", "HEALTH", "STAGE", "BRANCH", "GIT", "GRAPH", "PROG"], rows, color=args.color))
    if getattr(args, "exit_code", False) and any(p.health == Health.RED for p in projects):
        return 2
    return 0


def _cmd_ls(args, cfg) -> int:
    refs = discover(roots=cfg["roots"], conf_path=_conf_path(), exclude_dirs=cfg["exclude_dirs"])
    if args.json:
        print(json.dumps([r.__dict__ for r in refs], ensure_ascii=False, indent=2))
    else:
        rows = [[r.name, "reg" if r.registered else "new", r.layout or "-", r.path] for r in refs]
        print(render_table(["NAME", "REG", "LAYOUT", "PATH"], rows, color=False))
    return 0


def _find(cfg: dict, name: str) -> Project | None:
    for p in _snapshot(cfg):
        if p.name == name:
            return p
    return None


def _cmd_show(args, cfg) -> int:
    p = _find(cfg, args.project)
    if not p:
        print(f"проект не найден: {args.project}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(p.to_dict(), ensure_ascii=False, indent=2))
        return 0
    print(f"{p.name}  [{p.health.value}]  {p.type}/{p.stage}")
    print(f"  path:     {p.path}")
    print(f"  git:      {p.git.branch or '-'}  "
          f"{'dirty' if p.git.dirty else 'clean'}  +{p.git.insertions}/-{p.git.deletions}")
    print(f"  graphify: {p.graphify.status}  hook={'yes' if p.graphify.hook_installed else 'no'}")
    if p.progress.percent is not None:
        print(f"  progress: {p.progress.percent}% ({p.progress.done}/{p.progress.total})")
    for d in p.deadlines:
        print(f"  deadline: {d.title} {d.due} ({d.days_left} дн)")
    for r in p.health_reasons:
        print(f"  · {r}")
    return 0


def _cmd_scan(args, cfg) -> int:
    n = len(_snapshot(cfg))
    print(f"обнаружено проектов: {n}")
    return 0


def _cmd_init(args, cfg) -> int:
    if args.all:
        refs = discover(roots=cfg["roots"], conf_path=_conf_path(), exclude_dirs=cfg["exclude_dirs"])
        for r in refs:
            created = init_project(Path(r.path), name=r.name)
            print(f"{'создан' if created else 'есть'}: {r.name}")
        return 0
    if not args.project:
        print("укажите <project> или --all", file=sys.stderr)
        return 1
    ref = next((r for r in discover(roots=cfg["roots"], conf_path=_conf_path(),
                                    exclude_dirs=cfg["exclude_dirs"]) if r.name == args.project), None)
    target = Path(ref.path) if ref else (expand(cfg["roots"][0]) / args.project)
    created = init_project(target, name=args.project)
    print(f"{'создан' if created else 'уже есть'}: {target}/.aos/project.yaml")
    return 0


def _cmd_doctor(args, cfg) -> int:
    import shutil

    ok = True
    for label, tool in cfg["tools"].items():
        found = Path(tool).exists() or shutil.which(tool) is not None
        ok = ok and found
        print(f"  [{'ok' if found else 'MISS'}] {label}: {tool}")
    conf = _conf_path()
    print(f"  [{'ok' if conf.exists() else 'MISS'}] projects.conf: {conf}")
    for root in cfg["roots"]:
        rp = expand(root)
        print(f"  [{'ok' if rp.is_dir() else 'MISS'}] root: {rp}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aos", description="Local project dashboard")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--root", help="override roots with a single path")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--no-color", dest="color", action="store_false", help="disable ANSI color")
    parser.set_defaults(color=True, func=_cmd_status, exit_code=False)

    sub = parser.add_subparsers(dest="command")

    s = sub.add_parser("status")
    s.add_argument("--exit-code", action="store_true")
    s.set_defaults(func=_cmd_status)

    sub.add_parser("ls").set_defaults(func=_cmd_ls)
    sub.add_parser("list").set_defaults(func=_cmd_ls)

    sh = sub.add_parser("show")
    sh.add_argument("project")
    sh.set_defaults(func=_cmd_show)

    sub.add_parser("scan").set_defaults(func=_cmd_scan)

    it = sub.add_parser("init")
    it.add_argument("project", nargs="?")
    it.add_argument("--all", action="store_true")
    it.set_defaults(func=_cmd_init)

    sub.add_parser("doctor").set_defaults(func=_cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = _apply_root_override(load_config(), args.root)
    return args.func(args, cfg)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/cli.py tests/test_cli.py
git commit -m "feat(cli): status/ls/show/scan/init/doctor (table + --json)"
```

---

### Task 14: Full-suite verification, example config & README

**Files:**
- Create: `configs/config.example.yaml`
- Create: `configs/project.example.yaml`
- Modify: `README.md`

- [ ] **Step 1: Write the example config files**

`configs/config.example.yaml`:

```yaml
roots: ["~/Projects"]
port: 7777
refresh_interval_sec: 10
open_browser: true
tools:
  git: /usr/bin/git
  zellij: /opt/homebrew/bin/zellij
  kitty: /Applications/kitty.app/Contents/MacOS/kitty
  graphify: graphify
session:
  launch_cmd_template: "{kitty} -1 -e /bin/zsh -ic 'project {name}'"
exec_allowlist: [git, pnpm, npm, yarn, pytest, python, node, make, just, bats, graphify, cargo, go]
exclude_dirs: [node_modules, .git, dist, build, target, .venv, venv, __pycache__]
timeouts_sec: { collector: 5, tests: 120, graphify: 300 }
health:
  deadline_warn_days: 7
  inactive_warn_days: 14
```

`configs/project.example.yaml`:

```yaml
name: village
title: "Village EMRG"
type: app
stage: build
priority: high
tags: []
deadlines:
  - { title: "MVP deploy", due: 2026-07-01 }
progress:
  mode: auto
  percent: null
  plan: null
graphify:
  required: false
  disabled: false
commands:
  test: pnpm test
session:
  launch: null
dashboard:
  show_on_wall: true
```

- [ ] **Step 2: Write `README.md`**

```markdown
# aos-dashboard

Local project dashboard / control plane over the `kitty + zellij + nvim + claude` workflow.

## Install (editable)

```bash
python -m pip install -e ".[dev]"
```

## CLI (read-only, this milestone)

```bash
aos status                 # health table of all projects in ~/Projects
aos status --json | jq .    # machine-readable
aos status --exit-code      # exit 2 if any project is red (for statuslines/CI)
aos ls                     # discovered projects (registry + unregistered)
aos show village-emrg      # detailed snapshot
aos init village-emrg      # scaffold .aos/project.yaml
aos doctor                 # environment check
```

Config lives at `~/.config/aos/config.yaml` (see `configs/config.example.yaml`).
```

- [ ] **Step 3: Run the full test suite**

Run: `pytest`
Expected: PASS — all tests across tasks 1–13 green.

- [ ] **Step 4: Smoke-test the CLI against the real workspace**

Run: `aos --root ~/Projects status && aos --root ~/Projects ls && aos doctor`
Expected: a table listing `Junior_IT`, `research`, `village-emrg` (and `aos-dashboard`) with health/branch/graphify columns; `doctor` prints tool checks. (Tool MISS lines are acceptable if a path differs — fix paths in config.)

- [ ] **Step 5: Commit**

```bash
git add configs/ README.md
git commit -m "docs: example configs + README; verify full suite"
```

---

## Self-Review

**Spec coverage (Milestones 1–2):**
- Discovery + registry reconcile (spec §2.2, §4.3) → Task 3 ✓
- `.aos/project.yaml` schema read + scaffold (spec §4.1, §4.2) → Tasks 10, 11 ✓
- git / progress / deadlines / graphify / tests collectors (spec §5) → Tasks 4–8 ✓
- graphify freshness by built-commit + hook sensor (spec §2.4, §5) → Task 7 ✓
- health model green/yellow/red/unknown (spec §6) → Task 9 ✓
- CLI status/ls/show/scan/init/doctor + `--json`/`--exit-code`/`--root`/`--no-color` (spec §8) → Tasks 12, 13 ✓
- single dependency PyYAML, stdlib only (spec §3) → Task 0 ✓
- Deferred to later plans (correctly out of scope here): actions+safety+`serve`+`/wall` (Plan 2), processes/sessions/security collectors + TUI (Plan 3). Spec §7, §9, §10 intentionally not in this plan.

**Placeholder scan:** No TBD/TODO; every code step contains complete code.

**Type consistency:** `collect_git/collect_progress/compute_deadlines/collect_graphify/collect_tests` signatures match their calls in `aggregator.build_project`; `Project`/`GitState`/`GraphifyState`/`ProgressState`/`Deadline`/`TestState`/`Health` fields used in CLI and health match `model.py`; `ProjectRef(name,path,layout,registered)` consistent across `registry`, `aggregator`, `cli`; `evaluate()` returns `(Health, list[str])` as consumed in `aggregator` and `cli`.
