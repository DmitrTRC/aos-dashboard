# AOS Sensors + TUI + Auto-scaffold Implementation Plan (Plan 3, final)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close v1 — add the processes/sessions/security sensors, an `active` signal, a TUI board (`aos dash --watch`), auto-scaffold of `.aos/project.yaml` on discovery, and a documented `new-project.sh` integration.

**Architecture:** Extends Plan 1+2. Three new read-only collectors (`processes`, `sessions`, `security`) feed new `Project` fields; `aggregator` computes the live zellij-session set once and derives `active`; `health` gains one red trigger (a git-tracked secret); a `tui` module renders the same snapshots as an ANSI board; `scaffold.scaffold_missing` lights up new projects on `scan`/`serve`.

**Tech Stack:** Python 3.11+, stdlib (`subprocess`), existing dep PyYAML, pytest. No new deps.

**Scope note:** Plan 3 = spec §5 (processes/sessions/security collectors), §6 (security red + active), §10 (TUI), §4.1 (auto-scaffold). Completes v1 Definition of Done.

**Integration anchors (from Plans 1–2, do not rename):**
- `aos.model`: `Project`, `Health`, `GitState`, `GraphifyState`, `ProgressState`, `Deadline`, `TestState`; `Project.to_dict()` special-cases `health` and `git.dirty`.
- `aos.health.evaluate(p, cfg) -> (Health, list[str])`.
- `aos.aggregator.build_project(ref, cfg)`, `build_all(cfg, conf_path=None)`.
- `aos.config.DEFAULT_CONFIG` with `tools{git,zellij,kitty,graphify}`, `exec_allowlist`, `timeouts_sec`, `health`.
- `aos.tablefmt.render_table(headers, rows, color=True)`, `colorize(text, health, color=True)`.
- `aos.scaffold.init_project(path, name) -> bool`.
- `aos.cli.build_parser()` (parents `top_common`/`sub_common`), `_snapshot(cfg)`, `_find(cfg, name)`, `_conf_path()`, `expand`.

---

### Task 1: Model — processes/sessions/security + `active` (`aos/model.py`)

**Files:**
- Modify: `aos/model.py`
- Test: `tests/test_model_sensors.py`

- [ ] **Step 1: Write the failing test**

```python
import json

from aos.model import (
    ProcessInfo, Project, SecurityFinding, SecurityFindings, SessionState,
)


def test_security_has_tracked_secret():
    s = SecurityFindings(findings=[
        SecurityFinding(path=".env", kind="env", tracked=True),
        SecurityFinding(path="env.bak", kind="env", tracked=False),
    ])
    assert s.has_tracked_secret is True
    assert SecurityFindings().has_tracked_secret is False


def test_project_to_dict_includes_new_sections():
    p = Project(name="x", title="x", path="/x")
    p.processes = [ProcessInfo(pid=42, command="node server.js", port=3000)]
    p.session = SessionState(active=True, session_name="x", agents=["claude"])
    p.security = SecurityFindings(findings=[SecurityFinding(path=".env", kind="env", tracked=True)])
    p.active = True
    d = p.to_dict()
    assert d["processes"][0]["pid"] == 42
    assert d["session"]["active"] is True
    assert d["security"]["has_tracked_secret"] is True
    assert d["active"] is True
    json.dumps(d)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model_sensors.py -v`
Expected: FAIL with `ImportError: cannot import name 'ProcessInfo'`

- [ ] **Step 3: Modify `aos/model.py`**

Add these dataclasses after `TestState` (before `Project`):

```python
@dataclass
class ProcessInfo:
    pid: int
    command: str
    port: Optional[int] = None


@dataclass
class SessionState:
    active: bool = False
    session_name: Optional[str] = None
    agents: list[str] = field(default_factory=list)


@dataclass
class SecurityFinding:
    path: str
    kind: str  # env|key|secret
    tracked: bool = False


@dataclass
class SecurityFindings:
    findings: list[SecurityFinding] = field(default_factory=list)
    has_security_md: bool = False

    @property
    def has_tracked_secret(self) -> bool:
        return any(f.tracked for f in self.findings)
```

Add these fields to `Project` (after `tests: TestState = ...`, before `health: Health = ...`):

```python
    processes: list[ProcessInfo] = field(default_factory=list)
    session: SessionState = field(default_factory=SessionState)
    security: SecurityFindings = field(default_factory=SecurityFindings)
    active: bool = False
```

Replace `Project.to_dict` with:

```python
    def to_dict(self) -> dict:
        d = asdict(self)
        d["health"] = self.health.value
        d["git"]["dirty"] = self.git.dirty
        d["security"]["has_tracked_secret"] = self.security.has_tracked_secret
        return d
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_model_sensors.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/model.py tests/test_model_sensors.py
git commit -m "feat(model): ProcessInfo/SessionState/SecurityFindings + active"
```

---

### Task 2: Config — `ps` tool, `python3`, `auto_scaffold` (`aos/config.py`)

**Files:**
- Modify: `aos/config.py`
- Test: `tests/test_config_v3.py`

- [ ] **Step 1: Write the failing test**

```python
from aos.config import DEFAULT_CONFIG, load_config


def test_new_defaults_present(tmp_path):
    cfg = load_config(tmp_path / "missing.yaml")
    assert cfg["tools"]["ps"] == "/bin/ps"
    assert "python3" in cfg["exec_allowlist"]
    assert cfg["auto_scaffold"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_v3.py -v`
Expected: FAIL with `KeyError: 'ps'`

- [ ] **Step 3: Modify `aos/config.py`**

In `DEFAULT_CONFIG`, add `"ps": "/bin/ps"` to the `tools` dict:

```python
    "tools": {
        "git": "/usr/bin/git",
        "zellij": "/opt/homebrew/bin/zellij",
        "kitty": "/Applications/kitty.app/Contents/MacOS/kitty",
        "graphify": "graphify",
        "ps": "/bin/ps",
    },
```

Add `"python3"` to `exec_allowlist`:

```python
    "exec_allowlist": [
        "git", "pnpm", "npm", "yarn", "pytest", "python", "python3",
        "node", "make", "just", "bats", "graphify", "cargo", "go",
    ],
```

Add a top-level `"auto_scaffold": True,` key (e.g. right after `"open_browser": True,`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_v3.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/config.py tests/test_config_v3.py
git commit -m "feat(config): ps tool, python3 allowlisted, auto_scaffold flag"
```

---

### Task 3: Sessions collector (`aos/collectors/sessions.py`)

**Files:**
- Create: `aos/collectors/sessions.py`
- Test: `tests/test_collector_sessions.py`

- [ ] **Step 1: Write the failing test**

```python
from aos.collectors.sessions import collect_session, live_sessions
from aos.model import ProcessInfo


class _Runner:
    def __init__(self, out):
        self.out = out

    def __call__(self, argv, **kw):
        class _CP:
            pass
        cp = _CP()
        cp.returncode = 0
        cp.stdout = self.out
        cp.stderr = ""
        return cp


def test_live_sessions_skips_exited():
    out = "village [Created 1h ago]\nold [Created 2d ago] (EXITED - 1h ago)\nresearch [Created]\n"
    live = live_sessions("zellij", runner=_Runner(out))
    assert live == {"village", "research"}


def test_live_sessions_runner_failure_is_empty():
    def boom(*a, **k):
        raise FileNotFoundError("no zellij")
    assert live_sessions("zellij", runner=boom) == set()


def test_collect_session_active_and_agents():
    procs = [ProcessInfo(pid=1, command="/bin/claude --foo"), ProcessInfo(pid=2, command="node x")]
    s = collect_session("village", {"village"}, procs)
    assert s.active is True and s.session_name == "village"
    assert "claude" in s.agents


def test_collect_session_inactive():
    s = collect_session("village", set(), [])
    assert s.active is False and s.session_name is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_collector_sessions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.collectors.sessions'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_collector_sessions.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/collectors/sessions.py tests/test_collector_sessions.py
git commit -m "feat(collectors): zellij live-session sensor + agent detection"
```

---

### Task 4: Processes collector (`aos/collectors/processes.py`)

**Files:**
- Create: `aos/collectors/processes.py`
- Test: `tests/test_collector_processes.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from aos.collectors.processes import collect_processes


class _Runner:
    def __init__(self, out):
        self.out = out

    def __call__(self, argv, **kw):
        class _CP:
            pass
        cp = _CP()
        cp.returncode = 0
        cp.stdout = self.out
        cp.stderr = ""
        return cp


def test_matches_processes_under_project_path(tmp_path: Path):
    proj = tmp_path / "demo"
    out = (
        f"  101 node {proj}/packages/web/server.js\n"
        f"  202 /bin/zsh -il\n"
        f"  303 python3 {proj}/run.py\n"
    )
    procs = collect_processes(proj, runner=_Runner(out))
    pids = sorted(p.pid for p in procs)
    assert pids == [101, 303]


def test_runner_failure_is_empty(tmp_path: Path):
    def boom(*a, **k):
        raise FileNotFoundError("no ps")
    assert collect_processes(tmp_path, runner=boom) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_collector_processes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.collectors.processes'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_collector_processes.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/collectors/processes.py tests/test_collector_processes.py
git commit -m "feat(collectors): project-bound process sensor (read-only)"
```

---

### Task 5: Security collector (`aos/collectors/security.py`)

**Files:**
- Create: `aos/collectors/security.py`
- Test: `tests/test_collector_security.py`

- [ ] **Step 1: Write the failing test**

```python
import subprocess
from pathlib import Path

from aos.collectors.security import collect_security


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True)


def test_flags_tracked_vs_untracked(tmp_path: Path):
    repo = tmp_path / "demo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@e.st")
    _git(repo, "config", "user.name", "t")
    (repo / ".env").write_text("SECRET=1\n")
    (repo / "SECURITY.md").write_text("# sec\n")
    _git(repo, "add", ".env", "SECURITY.md")
    _git(repo, "commit", "-m", "oops committed env")
    (repo / "env.bak").write_text("OLD=1\n")  # untracked

    s = collect_security(repo, git_bin="git")
    by = {f.path: f for f in s.findings}
    assert by[".env"].tracked is True
    assert by["env.bak"].tracked is False
    assert s.has_tracked_secret is True
    assert s.has_security_md is True


def test_clean_project_no_findings(tmp_path: Path):
    s = collect_security(tmp_path, git_bin="git")
    assert s.findings == []
    assert s.has_tracked_secret is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_collector_security.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.collectors.security'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from aos.model import SecurityFinding, SecurityFindings

_SECRET_EXT = {".pem", ".key"}


def _is_secret(name: str) -> bool:
    return name == "env.bak" or name.startswith(".env") or Path(name).suffix in _SECRET_EXT


def _kind(name: str) -> str:
    if "env" in name:
        return "env"
    if Path(name).suffix in _SECRET_EXT:
        return "key"
    return "secret"


def collect_security(path, git_bin: str = "/usr/bin/git", timeout: int = 5, runner=subprocess.run) -> SecurityFindings:
    """Shallow (top-level) scan for secret-like files + git-tracked status. Read-only."""
    path = Path(path)
    candidates = [f for f in path.iterdir() if f.is_file() and _is_secret(f.name)] if path.is_dir() else []
    tracked: set[str] = set()
    if candidates and (path / ".git").exists():
        rels = [f.name for f in candidates]
        try:
            cp = runner([git_bin, "-C", str(path), "ls-files", "--", *rels],
                        capture_output=True, text=True, timeout=timeout)
            tracked = {ln.strip() for ln in (cp.stdout or "").splitlines() if ln.strip()}
        except Exception:
            tracked = set()
    findings = [
        SecurityFinding(path=f.name, kind=_kind(f.name), tracked=f.name in tracked)
        for f in sorted(candidates)
    ]
    return SecurityFindings(findings=findings, has_security_md=(path / "SECURITY.md").exists())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_collector_security.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/collectors/security.py tests/test_collector_security.py
git commit -m "feat(collectors): security-lite secret scan + tracked detection"
```

---

### Task 6: Health — tracked-secret red (`aos/health.py`)

**Files:**
- Modify: `aos/health.py`
- Test: `tests/test_health_security.py`

- [ ] **Step 1: Write the failing test**

```python
from aos.config import DEFAULT_CONFIG
from aos.health import evaluate
from aos.model import GitState, Health, Project, SecurityFinding, SecurityFindings


def _proj():
    p = Project(name="x", title="x", path="/x", has_yaml=True)
    p.git = GitState(is_repo=True)
    return p


def test_tracked_secret_makes_red():
    p = _proj()
    p.security = SecurityFindings(findings=[SecurityFinding(path=".env", kind="env", tracked=True)])
    h, reasons = evaluate(p, DEFAULT_CONFIG)
    assert h == Health.RED
    assert any("секрет" in r for r in reasons)


def test_untracked_secret_not_red():
    p = _proj()
    p.security = SecurityFindings(findings=[SecurityFinding(path="env.bak", kind="env", tracked=False)])
    assert evaluate(p, DEFAULT_CONFIG)[0] == Health.GREEN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_health_security.py -v`
Expected: FAIL — currently returns GREEN for the tracked-secret case

- [ ] **Step 3: Modify `aos/health.py`**

Add this red check in `evaluate`, right after the `graphify required` red check (before the yellow block):

```python
    if p.security.has_tracked_secret:
        red.append("в git закоммичен секрет")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health_security.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/health.py tests/test_health_security.py
git commit -m "feat(health): red when a secret is git-tracked"
```

---

### Task 7: Aggregator — wire sensors + `active` (`aos/aggregator.py`)

**Files:**
- Modify: `aos/aggregator.py`
- Test: `tests/test_aggregator_sensors.py`

- [ ] **Step 1: Write the failing test**

```python
import subprocess
from pathlib import Path

import yaml

from aos.aggregator import build_project
from aos.config import DEFAULT_CONFIG
from aos.registry import ProjectRef


def _repo(path: Path):
    path.mkdir(parents=True)
    subprocess.run(["git", "-C", str(path), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@e.st"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True, capture_output=True)
    (path / "README.md").write_text("# d\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "i"], check=True, capture_output=True)


def test_build_project_populates_sensors_and_active(tmp_path: Path):
    repo = tmp_path / "demo"
    _repo(repo)
    (repo / ".aos").mkdir()
    (repo / ".aos" / "project.yaml").write_text(yaml.safe_dump({"name": "demo"}))
    cfg = dict(DEFAULT_CONFIG, tools=dict(DEFAULT_CONFIG["tools"], git="git"))
    ref = ProjectRef(name="demo", path=str(repo), layout="dev", registered=True)
    # inject a live session for this project name
    p = build_project(ref, cfg, live=set(["demo"]))
    assert p.session.active is True
    assert p.active is True
    assert isinstance(p.security.findings, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_aggregator_sensors.py -v`
Expected: FAIL with `TypeError: build_project() got an unexpected keyword argument 'live'`

- [ ] **Step 3: Modify `aos/aggregator.py`**

Add to the collector imports:

```python
from aos.collectors.processes import collect_processes
from aos.collectors.security import collect_security
from aos.collectors.sessions import collect_session, live_sessions
```

Change `build_project` signature and add the sensor wiring (insert after `p.tests = collect_tests(path)`, before `p.health, p.health_reasons = evaluate(p, cfg)`):

```python
def build_project(ref: ProjectRef, cfg: dict, live: set[str] | None = None) -> Project:
```

```python
    p.processes = collect_processes(path, ps_bin=cfg["tools"].get("ps", "/bin/ps"), timeout=timeout)
    if live is None:
        live = live_sessions(cfg["tools"]["zellij"], timeout=timeout)
    p.session = collect_session(p.name, live, p.processes)
    p.security = collect_security(path, git_bin=git_bin, timeout=timeout)
    p.active = p.session.active or bool(p.processes)
```

Change `build_all` to compute the live set once and pass it down:

```python
def build_all(cfg: dict, conf_path: Path | None = None) -> list[Project]:
    if conf_path is None:
        conf_path = expand("~/.config/projects.conf")
    refs = discover(roots=cfg["roots"], conf_path=conf_path, exclude_dirs=cfg["exclude_dirs"])
    live = live_sessions(cfg["tools"]["zellij"], timeout=cfg["timeouts_sec"]["collector"])
    with ThreadPoolExecutor(max_workers=8) as pool:
        projects = list(pool.map(lambda r: build_project(r, cfg, live=live), refs))
    return sorted(projects, key=lambda p: p.name.lower())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_aggregator_sensors.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/aggregator.py tests/test_aggregator_sensors.py
git commit -m "feat(aggregator): wire processes/sessions/security + active; live set once"
```

---

### Task 8: Auto-scaffold on discovery (`aos/scaffold.py` + `aos/cli.py`)

**Files:**
- Modify: `aos/scaffold.py`
- Modify: `aos/cli.py`
- Test: `tests/test_scaffold_missing.py`

- [ ] **Step 1: Write the failing test**

```python
import subprocess
from pathlib import Path

from aos.config import DEFAULT_CONFIG
from aos.scaffold import scaffold_missing


def _repo(path: Path):
    path.mkdir(parents=True)
    subprocess.run(["git", "-C", str(path), "init", "-b", "main"], check=True, capture_output=True)


def test_scaffold_missing_creates_for_projects_without_yaml(tmp_path: Path):
    root = tmp_path / "Projects"
    _repo(root / "a")
    _repo(root / "b")
    (root / "b" / ".aos").mkdir()
    (root / "b" / ".aos" / "project.yaml").write_text("name: b\n")  # already has yaml
    cfg = dict(DEFAULT_CONFIG, roots=[str(root)])
    created = scaffold_missing(cfg, conf_path=tmp_path / "none.conf")
    assert created == ["a"]
    assert (root / "a" / ".aos" / "project.yaml").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scaffold_missing.py -v`
Expected: FAIL with `ImportError: cannot import name 'scaffold_missing'`

- [ ] **Step 3: Modify `aos/scaffold.py`**

Add imports at the top:

```python
from aos.registry import discover
```

Append at the end:

```python
def scaffold_missing(cfg: dict, conf_path=None) -> list[str]:
    """Create a stub .aos/project.yaml for every discovered project lacking one."""
    refs = discover(roots=cfg["roots"], conf_path=conf_path, exclude_dirs=cfg["exclude_dirs"])
    created: list[str] = []
    for r in refs:
        if not (Path(r.path) / ".aos" / "project.yaml").exists():
            if init_project(Path(r.path), name=r.name):
                created.append(r.name)
    return sorted(created)
```

- [ ] **Step 4: Modify `aos/cli.py`**

In `_cmd_scan`, scaffold first when enabled. Replace the body of `_cmd_scan` with:

```python
def _cmd_scan(args, cfg) -> int:
    if cfg.get("auto_scaffold", False):
        from aos.scaffold import scaffold_missing
        created = scaffold_missing(cfg, conf_path=_conf_path())
        if created:
            print(f"скаффолд .aos/project.yaml: {', '.join(created)}")
    n = len(_snapshot(cfg))
    print(f"обнаружено проектов: {n}")
    return 0
```

In `_cmd_serve` (added in Plan 2), add a scaffold step right after computing `port` and before `make_server`:

```python
    if cfg.get("auto_scaffold", False):
        from aos.scaffold import scaffold_missing
        scaffold_missing(cfg, conf_path=_conf_path())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_scaffold_missing.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add aos/scaffold.py aos/cli.py tests/test_scaffold_missing.py
git commit -m "feat(scaffold): scaffold_missing on scan/serve when auto_scaffold"
```

---

### Task 9: TUI board (`aos/tui.py`)

**Files:**
- Create: `aos/tui.py`
- Test: `tests/test_tui.py`

- [ ] **Step 1: Write the failing test**

```python
from aos.model import GitState, GraphifyState, Health, Project, ProgressState, SessionState
from aos.tui import render_dash


def _proj(name, health):
    p = Project(name=name, title=name, path="/x", stage="build")
    p.git = GitState(is_repo=True, branch="main")
    p.graphify = GraphifyState(status="fresh")
    p.progress = ProgressState(percent=50)
    p.session = SessionState(active=True)
    p.health = health
    return p


def test_render_dash_has_header_and_rows():
    out = render_dash([_proj("village", Health.YELLOW), _proj("demo", Health.GREEN)], color=False)
    lines = out.splitlines()
    assert "NAME" in lines[0] and "SES" in lines[0]
    assert "village" in out and "demo" in out
    assert "50%" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.tui'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/tui.py tests/test_tui.py
git commit -m "feat(tui): render_dash board + watch loop"
```

---

### Task 10: CLI `dash` / `wall` (`aos/cli.py`)

**Files:**
- Modify: `aos/cli.py`
- Test: `tests/test_cli_dash.py`

- [ ] **Step 1: Write the failing test**

```python
import subprocess
from pathlib import Path

from aos.cli import build_parser, main


def _repo(root: Path, name="demo"):
    repo = root / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@e.st"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True, capture_output=True)
    (repo / "README.md").write_text("# d\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "i"], check=True, capture_output=True)


def test_dash_parser_watch():
    parser = build_parser()
    args = parser.parse_args(["dash", "--watch"])
    assert args.watch is True and args.func.__name__ == "_cmd_dash"


def test_dash_prints_board(tmp_path: Path, capsys):
    root = tmp_path / "Projects"
    _repo(root)
    code = main(["dash", "--root", str(root)])
    out = capsys.readouterr().out
    assert code == 0 and "NAME" in out and "demo" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_dash.py -v`
Expected: FAIL with `argument command: invalid choice: 'dash'`

- [ ] **Step 3: Modify `aos/cli.py`**

Add the command function before `build_parser`:

```python
def _cmd_dash(args, cfg) -> int:
    from aos.tui import dash_loop, dash_once

    if args.watch:
        interval = cfg.get("refresh_interval_sec", 5)
        try:
            dash_loop(cfg, conf_path=_conf_path(), color=args.color, interval=interval)
        except KeyboardInterrupt:
            print("\nостановлено")
        return 0
    print(dash_once(cfg, conf_path=_conf_path(), color=args.color))
    return 0
```

Register the subcommands inside `build_parser`, before `return parser`:

```python
    da = sub.add_parser("dash", parents=[sub_common])
    da.add_argument("--watch", action="store_true")
    da.set_defaults(func=_cmd_dash)

    wa = sub.add_parser("wall", parents=[sub_common])
    wa.add_argument("--watch", action="store_true")
    wa.set_defaults(func=_cmd_dash)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_dash.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/cli.py tests/test_cli_dash.py
git commit -m "feat(cli): dash/wall TUI board (+ --watch)"
```

---

### Task 11: Web — session & security on cards (`aos/web/index.html`)

**Files:**
- Modify: `aos/web/index.html`
- Test: `tests/test_web_sensors.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import aos


def test_index_shows_session_and_security():
    html = (Path(aos.__file__).parent / "web" / "index.html").read_text(encoding="utf-8")
    assert "session" in html
    assert "has_tracked_secret" in html
    # still offline
    assert "http://" not in html and "https://" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_sensors.py -v`
Expected: FAIL — current card markup has no `session`/`has_tracked_secret`

- [ ] **Step 3: Modify `aos/web/index.html`**

In the `card(p)` function, add a `session` row and a `secret` warning. Replace the `<table class="kv">…</table>` block inside `card` with:

```javascript
    const sess = (p.session && p.session.active)
      ? "● active" + (p.session.agents && p.session.agents.length ? " ("+p.session.agents.join(",")+")" : "")
      : "idle";
    const secret = (p.security && p.security.has_tracked_secret) ? " ⚠ secret in git" : "";
    const body = `<table class="kv">
      <tr><td>git</td><td class="v">${git.branch||'-'} · ${dirty} · ${diff}${secret}</td></tr>
      <tr><td>graph</td><td class="v">${g.status||'-'}${g.hook_installed ? ' · hook' : ''}</td></tr>
      <tr><td>progress</td><td class="v">${prog}</td></tr>
      <tr><td>session</td><td class="v">${sess}</td></tr>
      <tr><td>deadline</td><td class="v">${dl}</td></tr>
    </table>`;
```

Then change the card's returned template to use `${body}` in place of the previous inline `<table…>` markup (the rest of the card — `<h3>` and `.acts` — stays the same):

```javascript
  return `<div class="card">
    <h3><span class="dot ${CLS[p.health]||'u'}"></span>${p.name}
        <span class="meta">${p.type} · ${p.stage}</span></h3>
    ${body}
    <div class="acts">
      <button onclick="act('${p.name}','open_session')">Open</button>
      <button onclick="act('${p.name}','run_tests')">Test</button>
      <button onclick="act('${p.name}','git_fetch')">Fetch</button>
      <button onclick="act('${p.name}','graphify_update')">Graph ↻</button>
    </div></div>`;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_sensors.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/web/index.html tests/test_web_sensors.py
git commit -m "feat(web): show session/agents + secret-in-git warning on cards"
```

---

### Task 12: `new-project.sh` integration doc + full v1 verification

**Files:**
- Create: `docs/integration-new-project.md`
- Modify: `README.md`

- [ ] **Step 1: Write `docs/integration-new-project.md`**

```markdown
# Integration: seed `.aos/project.yaml` in new projects

`aos serve` and `aos scan` already auto-scaffold a stub `.aos/project.yaml` for any
discovered project (when `auto_scaffold: true`). To seed it at creation time instead,
add this block to `~/Projects/new-project.sh` just before the first commit
(after the `docs/` skeleton step):

```bash
# ── .aos/ (project dashboard contract) ─────────────────────────
mkdir -p .aos/state
cat > .aos/project.yaml <<EOF
name: ${NAME}
title: ${NAME}
type: unknown
stage: idea
priority: medium
tags: []
deadlines: []
progress: { mode: auto, percent: null, plan: null }
graphify: { required: false, disabled: false }
commands: {}
session: { launch: null }
dashboard: { show_on_wall: true }
EOF
grep -qxF '.aos/state/' .gitignore 2>/dev/null || printf '\n.aos/state/\n' >> .gitignore
```

This is optional — the dashboard works without it via auto-scaffold. Equivalent one-shot
for existing projects: `aos init <name>` or `aos init --all`.
```

- [ ] **Step 2: Update `README.md`**

Add after the actions/web section:

```markdown
## Sensors & TUI (Plan 3)

```bash
aos dash            # one-shot ANSI board (health, git, graph, progress, session)
aos dash --watch    # live board, refreshes every refresh_interval_sec
aos wall            # alias for dash
```

The `/wall` web cards and `aos show` now include: live zellij **session** (+ detected
agents), running **processes** bound to the project, and **security** findings
(secret-like files; a secret committed to git turns the project red). New projects get a
stub `.aos/project.yaml` automatically on `aos scan`/`aos serve` (`auto_scaffold: true`),
or seed it at creation — see `docs/integration-new-project.md`.
```

- [ ] **Step 3: Run the full suite**

Run: `pytest`
Expected: PASS — all Plan 1 + 2 + 3 tests green.

- [ ] **Step 4: Smoke-test the new surfaces**

Run: `aos --root ~/Projects dash && aos --root ~/Projects scan && aos --root ~/Projects show village-emrg`
Expected: `dash` prints a board with a `SES` column; `scan` reports discovery (and any scaffolded yamls); `show village-emrg` prints session/processes/security lines.

- [ ] **Step 5: Commit**

```bash
git add docs/integration-new-project.md README.md
git commit -m "docs: new-project integration + sensors/TUI usage; verify v1"
```

---

## Self-Review

**Spec coverage (Plan 3 portion):**
- processes collector (spec §5) → Task 4 ✓
- sessions collector via `zellij list-sessions -n | grep -v EXITED` + agent detect (spec §2.3, §5) → Task 3 ✓
- security-lite secret scan + tracked detection (spec §5, §22-equivalent) → Task 5 ✓
- `active` project signal (spec §6) → Task 7 ✓
- security red on committed secret (spec §6) → Task 6 ✓
- TUI `aos dash`/`wall` + `--watch` (spec §10) → Tasks 9, 10 ✓
- auto-scaffold `.aos/project.yaml` on discovery (spec §4.1) → Task 8 ✓
- `new-project.sh` integration (spec §14 milestone 6) → Task 12 ✓
- web/show surface the new sensors (spec §9) → Task 11 ✓
- After this plan, spec Definition of Done (§15) is fully covered across Plans 1–3.

**Placeholder scan:** No TBD/TODO; every code step is complete.

**Type consistency:** New model types `ProcessInfo(pid,command,port)`, `SessionState(active,session_name,agents)`, `SecurityFinding(path,kind,tracked)`, `SecurityFindings(findings,has_security_md,+has_tracked_secret)` used identically in collectors, aggregator, health, tui, web-dict. `collect_session(name, live, processes)`, `live_sessions(zellij_bin,...)`, `collect_processes(path, ps_bin=, timeout=, runner=)`, `collect_security(path, git_bin=, timeout=, runner=)` signatures match their aggregator call sites. `build_project(ref, cfg, live=None)` is backward-compatible (Plan 1/2 callers pass two args; `build_all` now passes `live=`). `render_dash(projects, color=True)` consumes the existing `tablefmt.render_table`/`colorize`. `scaffold_missing(cfg, conf_path=None)` reuses Plan 1 `init_project` + `discover`. CLI additions reuse `_snapshot`/`_find`/`_conf_path`/`sub_common` verified against the committed `aos/cli.py`.
```
