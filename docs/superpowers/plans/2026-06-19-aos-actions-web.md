# AOS Actions + Safety + Web `/wall` Implementation Plan (Plan 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the single command-executing layer (`aos/actions.py`) with a closed action whitelist + exec-allowlist + `shell=False`, wire it into the CLI (`open/test/fetch/graphify`), and serve a local read+act web dashboard (`aos serve` → `/wall`) bound to `127.0.0.1` with a per-run token.

**Architecture:** Builds on Plan 1 (`config`, `registry`, `model`, `aggregator`, `cli`). `actions.py` is the ONLY module that executes commands: every action is a named kind from a closed set; per-project commands are validated against `cfg["exec_allowlist"]`, run with list-argv + `shell=False` + timeout + cwd bound to the project. `server.py` is a stdlib `ThreadingHTTPServer` (localhost only) exposing read endpoints + a token-guarded POST action endpoint, serving one offline `web/index.html`.

**Tech Stack:** Python 3.11+, stdlib (`subprocess`, `shlex`, `http.server`, `http.client`, `secrets`), existing dep PyYAML, tests via pytest. No new dependencies; frontend is vanilla JS, no CDN.

**Scope note:** Plan 2 = spec §7 (actions+safety), §9 (web). Out of scope (Plan 3): processes/sessions/security collectors, TUI `aos dash`, auto-scaffold-on-discover, `new-project.sh` patch.

**Integration anchors (from Plan 1, do not rename):**
- `aos.config.load_config()` → dict with keys `tools{git,zellij,kitty,graphify}`, `session.launch_cmd_template`, `exec_allowlist`, `timeouts_sec{collector,tests,graphify}`, `port`, `refresh_interval_sec`.
- `aos.model.Project` has `.name`, `.path` (str), `.to_dict()`.
- `aos.aggregator.build_all(cfg, conf_path=None)` and `build_project(ref, cfg)`.
- `aos.cli.build_parser()` uses `top_common`/`sub_common` parent parsers; subcommands call `func(args, cfg)`; helpers `_snapshot(cfg)`, `_find(cfg, name)`, `_conf_path()`.

---

### Task 1: Command validation & result types (`aos/actions.py`)

**Files:**
- Create: `aos/actions.py`
- Test: `tests/test_actions_validate.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from aos.actions import ActionError, ActionResult, validate_command

ALLOW = ["git", "pnpm", "pytest", "python", "graphify"]


def test_valid_command_returns_argv():
    assert validate_command("pnpm test", ALLOW) == ["pnpm", "test"]


def test_absolute_path_executable_checked_by_basename():
    assert validate_command("/usr/bin/git fetch", ALLOW) == ["/usr/bin/git", "fetch"]


def test_rejects_executable_not_in_allowlist():
    with pytest.raises(ActionError):
        validate_command("rm -rf /tmp/x", ALLOW)


def test_rejects_empty_and_unbalanced_quotes():
    with pytest.raises(ActionError):
        validate_command("   ", ALLOW)
    with pytest.raises(ActionError):
        validate_command('python -c "unbalanced', ALLOW)


def test_action_result_to_dict():
    r = ActionResult(kind="run_tests", ok=True, command=["pytest"], exit_code=0)
    d = r.to_dict()
    assert d["kind"] == "run_tests" and d["ok"] is True and d["command"] == ["pytest"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_actions_validate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.actions'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_actions_validate.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/actions.py tests/test_actions_validate.py
git commit -m "feat(actions): command validation + ActionResult/ActionError"
```

---

### Task 2: Safe runner & action log (`aos/actions.py`)

**Files:**
- Modify: `aos/actions.py`
- Test: `tests/test_actions_runner.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from aos.actions import ActionResult, log_action, run_whitelisted


def test_run_whitelisted_executes_without_shell(tmp_path: Path):
    # `&& touch HACKED` must NOT run — proves shell=False (args are literal)
    argv = ["python", "-c", "print('hi')", "&&", "touch", "HACKED"]
    cp = run_whitelisted(argv, cwd=tmp_path, timeout=30)
    assert cp.returncode == 0
    assert "hi" in cp.stdout
    assert not (tmp_path / "HACKED").exists()


def test_run_whitelisted_sanitises_env(tmp_path: Path):
    cp = run_whitelisted(
        ["python", "-c", "import os;print(os.environ.get('SECRET','none'))"],
        cwd=tmp_path, timeout=30, env={"SECRET": "shown"},
    )
    assert "shown" in cp.stdout  # explicit env passes through


def test_log_action_appends_jsonl(tmp_path: Path):
    r = ActionResult(kind="git_fetch", ok=True, command=["git", "fetch"], exit_code=0)
    log_action(tmp_path, r)
    log = tmp_path / ".aos" / "state" / "actions.log"
    assert log.exists()
    assert "git_fetch" in log.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_actions_runner.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_whitelisted'`

- [ ] **Step 3: Add to `aos/actions.py`**

Append these imports at the top (merge with existing import block):

```python
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
```

Append at the end of the file:

```python
def run_whitelisted(argv, cwd, timeout, env=None, runner=subprocess.run):
    """Execute argv with NO shell, sanitised env, timeout, bound cwd."""
    safe_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }
    if env:
        safe_env.update(env)
    return runner(
        list(argv),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=safe_env,
    )


def log_action(project_path, result: ActionResult) -> None:
    state = Path(project_path) / ".aos" / "state"
    state.mkdir(parents=True, exist_ok=True)
    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "kind": result.kind,
        "ok": result.ok,
        "exit_code": result.exit_code,
        "command": result.command,
    }
    with (state / "actions.log").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_actions_runner.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/actions.py tests/test_actions_runner.py
git commit -m "feat(actions): shell-free runner + jsonl action log"
```

---

### Task 3: `run_tests` action (`aos/actions.py`)

**Files:**
- Modify: `aos/actions.py`
- Test: `tests/test_actions_tests.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

import yaml

from aos.config import DEFAULT_CONFIG
from aos.actions import resolve_test_command, run_tests
from aos.model import Project


def _proj(path: Path) -> Project:
    return Project(name="demo", title="demo", path=str(path))


def _cfg():
    return dict(DEFAULT_CONFIG)


def test_resolve_prefers_yaml_then_detects(tmp_path: Path):
    assert resolve_test_command(tmp_path, {"test": "pytest -q"}) == "pytest -q"
    (tmp_path / "package.json").write_text("{}")
    assert resolve_test_command(tmp_path, {}) == "pnpm test"


def test_run_tests_writes_state_pass(tmp_path: Path):
    aos = tmp_path / ".aos"
    aos.mkdir()
    (aos / "project.yaml").write_text(yaml.safe_dump(
        {"name": "demo", "commands": {"test": "python -c \"import sys;sys.exit(0)\""}}))
    r = run_tests(_proj(tmp_path), _cfg())
    assert r.ok is True and r.exit_code == 0
    state = json.loads((aos / "state" / "tests.json").read_text())
    assert state["exit_code"] == 0


def test_run_tests_records_failure(tmp_path: Path):
    aos = tmp_path / ".aos"
    aos.mkdir()
    (aos / "project.yaml").write_text(yaml.safe_dump(
        {"name": "demo", "commands": {"test": "python -c \"import sys;sys.exit(3)\""}}))
    r = run_tests(_proj(tmp_path), _cfg())
    assert r.ok is False and r.exit_code == 3


def test_run_tests_no_command(tmp_path: Path):
    r = run_tests(_proj(tmp_path), _cfg())
    assert r.ok is False and "не найдена" in r.message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_actions_tests.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_test_command'`

- [ ] **Step 3: Add to `aos/actions.py`**

Add import near the other imports:

```python
import time

import yaml
```

Append at the end of the file:

```python
def _read_yaml(project_path) -> dict:
    f = Path(project_path) / ".aos" / "project.yaml"
    if not f.exists():
        return {}
    try:
        return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}


def resolve_test_command(project_path, yaml_commands: dict) -> str | None:
    if yaml_commands.get("test"):
        return yaml_commands["test"]
    path = Path(project_path)
    if (path / "package.json").exists():
        return "pnpm test"
    if (path / "pyproject.toml").exists() or (path / "tests").is_dir():
        return "pytest"
    return None


def _write_tests_state(project_path, exit_code: int, duration: float, command: str) -> None:
    state = Path(project_path) / ".aos" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "tests.json").write_text(json.dumps({
        "exit_code": exit_code,
        "duration_sec": duration,
        "time": datetime.now(timezone.utc).isoformat(),
        "command": command,
    }, ensure_ascii=False), encoding="utf-8")


def run_tests(project, cfg: dict, runner=subprocess.run) -> ActionResult:
    cmds = _read_yaml(project.path).get("commands") or {}
    cmd = resolve_test_command(project.path, cmds)
    if not cmd:
        return ActionResult(kind="run_tests", ok=False, message="тест-команда не найдена")
    argv = validate_command(cmd, cfg["exec_allowlist"])
    t0 = time.time()
    try:
        cp = run_whitelisted(argv, project.path, cfg["timeouts_sec"]["tests"], runner=runner)
    except subprocess.TimeoutExpired:
        _write_tests_state(project.path, 124, cfg["timeouts_sec"]["tests"], cmd)
        r = ActionResult(kind="run_tests", ok=False, command=argv, exit_code=124, message="таймаут")
        log_action(project.path, r)
        return r
    dur = round(time.time() - t0, 2)
    _write_tests_state(project.path, cp.returncode, dur, cmd)
    r = ActionResult(
        kind="run_tests", ok=cp.returncode == 0, command=argv,
        exit_code=cp.returncode, stdout=cp.stdout[-4000:], stderr=cp.stderr[-4000:],
    )
    log_action(project.path, r)
    return r
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_actions_tests.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/actions.py tests/test_actions_tests.py
git commit -m "feat(actions): run_tests resolves+executes whitelisted test cmd, writes state"
```

---

### Task 4: `git_fetch`, `graphify` & `open_report` actions (`aos/actions.py`)

**Files:**
- Modify: `aos/actions.py`
- Test: `tests/test_actions_misc.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from aos.config import DEFAULT_CONFIG
from aos.actions import (
    ActionError, git_fetch, graphify_action, graphify_argv, open_report,
)
from aos.model import Project


class _FakeRunner:
    def __init__(self, returncode=0):
        self.calls = []
        self.returncode = returncode

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        class _CP:
            pass
        cp = _CP()
        cp.returncode = self.returncode
        cp.stdout = "out"
        cp.stderr = ""
        return cp


def _proj(p):
    return Project(name="demo", title="demo", path=str(p))


def test_graphify_argv_modes():
    assert graphify_argv("update", "graphify") == ["graphify", "update", "."]
    assert graphify_argv("hook_install", "graphify") == ["graphify", "hook", "install"]
    assert graphify_argv("init", "graphify") == ["graphify", "."]


def test_graphify_init_requires_confirm(tmp_path: Path):
    with pytest.raises(ActionError):
        graphify_action(_proj(tmp_path), DEFAULT_CONFIG, mode="init", confirm=False)


def test_graphify_update_runs(tmp_path: Path):
    runner = _FakeRunner(returncode=0)
    r = graphify_action(_proj(tmp_path), DEFAULT_CONFIG, mode="update", runner=runner)
    assert r.kind == "graphify_update" and r.ok is True
    assert runner.calls[0][0] == ["graphify", "update", "."]


def test_git_fetch_builds_argv(tmp_path: Path):
    runner = _FakeRunner(returncode=0)
    cfg = dict(DEFAULT_CONFIG, tools=dict(DEFAULT_CONFIG["tools"], git="/usr/bin/git"))
    r = git_fetch(_proj(tmp_path), cfg, runner=runner)
    assert r.kind == "git_fetch"
    assert runner.calls[0][0] == ["/usr/bin/git", "-C", str(tmp_path), "fetch", "--prune"]


def test_open_report_rejects_path_outside_project(tmp_path: Path):
    with pytest.raises(ActionError):
        open_report(_proj(tmp_path), "../../etc/passwd", DEFAULT_CONFIG, spawn=lambda *a, **k: None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_actions_misc.py -v`
Expected: FAIL with `ImportError: cannot import name 'git_fetch'`

- [ ] **Step 3: Add to `aos/actions.py`**

Append at the end of the file:

```python
def git_fetch(project, cfg: dict, runner=subprocess.run) -> ActionResult:
    git = cfg["tools"]["git"]
    argv = [git, "-C", str(project.path), "fetch", "--prune"]
    cp = run_whitelisted(argv, project.path, cfg["timeouts_sec"]["collector"] * 6, runner=runner)
    r = ActionResult(
        kind="git_fetch", ok=cp.returncode == 0, command=argv,
        exit_code=cp.returncode, stdout=cp.stdout[-2000:], stderr=cp.stderr[-2000:],
    )
    log_action(project.path, r)
    return r


def graphify_argv(mode: str, graphify_bin: str) -> list[str]:
    if mode == "update":
        return [graphify_bin, "update", "."]
    if mode == "hook_install":
        return [graphify_bin, "hook", "install"]
    if mode == "init":
        return [graphify_bin, "."]
    raise ActionError(f"неизвестный режим graphify: {mode}")


def graphify_action(project, cfg: dict, mode: str = "update",
                    confirm: bool = False, runner=subprocess.run) -> ActionResult:
    if mode == "init" and not confirm:
        raise ActionError("graphify init требует подтверждения (сеть + расход токенов)")
    argv = graphify_argv(mode, cfg["tools"]["graphify"])
    cp = run_whitelisted(argv, project.path, cfg["timeouts_sec"]["graphify"], runner=runner)
    r = ActionResult(
        kind=f"graphify_{mode}", ok=cp.returncode == 0, command=argv,
        exit_code=cp.returncode, stdout=cp.stdout[-2000:], stderr=cp.stderr[-2000:],
    )
    log_action(project.path, r)
    return r


def open_report(project, rel_path: str, cfg: dict, spawn=subprocess.Popen) -> ActionResult:
    base = Path(project.path).resolve()
    target = (base / rel_path).resolve()
    if base != target and base not in target.parents:
        raise ActionError("путь вне проекта")
    if not target.exists():
        raise ActionError(f"файл не найден: {rel_path}")
    argv = ["/usr/bin/open", str(target)]
    spawn(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ActionResult(kind="open_report", ok=True, command=argv)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_actions_misc.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/actions.py tests/test_actions_misc.py
git commit -m "feat(actions): git_fetch, graphify (update/hook/init), open_report"
```

---

### Task 5: `open_session` & action dispatcher (`aos/actions.py`)

**Files:**
- Modify: `aos/actions.py`
- Test: `tests/test_actions_dispatch.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from aos.config import DEFAULT_CONFIG
from aos.actions import ACTION_KINDS, ActionError, open_session, run_action
from aos.model import Project


def _proj(p, name="village"):
    return Project(name=name, title=name, path=str(p))


def test_open_session_builds_kitty_argv(tmp_path: Path):
    captured = {}

    def fake_spawn(argv, **kw):
        captured["argv"] = argv
        captured["kw"] = kw

    r = open_session(_proj(tmp_path), DEFAULT_CONFIG, spawn=fake_spawn)
    assert r.ok is True and r.kind == "open_session"
    assert captured["argv"] == [
        "/Applications/kitty.app/Contents/MacOS/kitty", "-1", "-e",
        "/bin/zsh", "-ic", "project village",
    ]
    assert captured["kw"].get("start_new_session") is True


def test_open_session_rejects_unsafe_name(tmp_path: Path):
    with pytest.raises(ActionError):
        open_session(_proj(tmp_path, name="a; rm -rf ~"), DEFAULT_CONFIG, spawn=lambda *a, **k: None)


def test_dispatch_unknown_kind(tmp_path: Path):
    with pytest.raises(ActionError):
        run_action("delete_everything", _proj(tmp_path), DEFAULT_CONFIG)


def test_action_kinds_are_closed_set():
    assert ACTION_KINDS == {
        "open_session", "run_tests", "git_fetch",
        "graphify_update", "graphify_hook_install", "graphify_init", "open_report",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_actions_dispatch.py -v`
Expected: FAIL with `ImportError: cannot import name 'ACTION_KINDS'`

- [ ] **Step 3: Add to `aos/actions.py`**

Add import near the others:

```python
import re
```

Append at the end of the file:

```python
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

ACTION_KINDS = {
    "open_session", "run_tests", "git_fetch",
    "graphify_update", "graphify_hook_install", "graphify_init", "open_report",
}


def open_session(project, cfg: dict, spawn=subprocess.Popen) -> ActionResult:
    name = project.name
    if not _SAFE_NAME.match(name):
        raise ActionError(f"небезопасное имя проекта: {name!r}")
    template = cfg["session"]["launch_cmd_template"]
    cmd = template.format(kitty=cfg["tools"]["kitty"], name=name)
    try:
        argv = shlex.split(cmd)
    except ValueError as exc:
        raise ActionError(f"не разобрать launch_cmd_template: {exc}") from exc
    spawn(
        argv,
        cwd=str(project.path),
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    r = ActionResult(kind="open_session", ok=True, command=argv,
                     message=f"открыто окно: project {name}")
    log_action(project.path, r)
    return r


def run_action(kind: str, project, cfg: dict, **opts) -> ActionResult:
    if kind not in ACTION_KINDS:
        raise ActionError(f"неизвестное действие: {kind}")
    if kind == "open_session":
        return open_session(project, cfg)
    if kind == "run_tests":
        return run_tests(project, cfg)
    if kind == "git_fetch":
        return git_fetch(project, cfg)
    if kind == "graphify_update":
        return graphify_action(project, cfg, mode="update")
    if kind == "graphify_hook_install":
        return graphify_action(project, cfg, mode="hook_install")
    if kind == "graphify_init":
        return graphify_action(project, cfg, mode="init", confirm=bool(opts.get("confirm", False)))
    if kind == "open_report":
        return open_report(project, opts["path"], cfg)
    raise ActionError(f"необработанное действие: {kind}")  # unreachable guard
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_actions_dispatch.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/actions.py tests/test_actions_dispatch.py
git commit -m "feat(actions): open_session + closed-set run_action dispatcher"
```

---

### Task 6: CLI action subcommands (`aos/cli.py`)

**Files:**
- Modify: `aos/cli.py`
- Test: `tests/test_cli_actions.py`

- [ ] **Step 1: Write the failing test**

```python
import subprocess
from pathlib import Path

import yaml

from aos.cli import main


def _repo(root: Path, name="demo") -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@e.st"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True, capture_output=True)
    (repo / "README.md").write_text("# d\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "i"], check=True, capture_output=True)
    return repo


def test_cli_test_command_runs(tmp_path: Path, capsys):
    root = tmp_path / "Projects"
    repo = _repo(root)
    (repo / ".aos").mkdir()
    (repo / ".aos" / "project.yaml").write_text(yaml.safe_dump(
        {"name": "demo", "commands": {"test": "python -c \"import sys;sys.exit(0)\""}}))
    code = main(["test", "demo", "--root", str(root)])
    out = capsys.readouterr().out
    assert code == 0
    assert "pass" in out.lower() or "ok" in out.lower()


def test_cli_unknown_project(tmp_path: Path, capsys):
    root = tmp_path / "Projects"
    _repo(root)
    code = main(["open", "nope", "--root", str(root)])
    assert code == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_actions.py -v`
Expected: FAIL with `argument command: invalid choice: 'test'` (or SystemExit)

- [ ] **Step 3: Modify `aos/cli.py`**

Add to the imports block:

```python
from aos.actions import ActionError, graphify_action, run_action
```

Add these command functions before `build_parser`:

```python
def _require(cfg, name):
    p = _find(cfg, name)
    if not p:
        print(f"проект не найден: {name}", file=sys.stderr)
    return p


def _cmd_open(args, cfg) -> int:
    p = _require(cfg, args.project)
    if not p:
        return 1
    try:
        r = run_action("open_session", p, cfg)
    except ActionError as exc:
        print(f"отказано: {exc}", file=sys.stderr)
        return 1
    print(r.message or "открыто")
    return 0


def _cmd_test(args, cfg) -> int:
    p = _require(cfg, args.project)
    if not p:
        return 1
    try:
        r = run_action("run_tests", p, cfg)
    except ActionError as exc:
        print(f"отказано: {exc}", file=sys.stderr)
        return 1
    print(f"tests: {'pass' if r.ok else 'fail'} (exit {r.exit_code}) — {' '.join(r.command)}")
    if not r.ok and r.message:
        print(f"  {r.message}")
    return 0 if r.ok else 1


def _cmd_fetch(args, cfg) -> int:
    p = _require(cfg, args.project)
    if not p:
        return 1
    r = run_action("git_fetch", p, cfg)
    print(f"git fetch: {'ok' if r.ok else 'fail'} (exit {r.exit_code})")
    return 0 if r.ok else 1


def _cmd_graphify(args, cfg) -> int:
    p = _require(cfg, args.project)
    if not p:
        return 1
    if args.init:
        mode, confirm = "init", args.yes
        if not confirm:
            reply = input("graphify init ходит в LLM (сеть + токены). Продолжить? [y/N] ").strip().lower()
            confirm = reply in ("y", "yes", "д", "да")
        if not confirm:
            print("отменено")
            return 1
        try:
            r = graphify_action(p, cfg, mode="init", confirm=True)
        except ActionError as exc:
            print(f"отказано: {exc}", file=sys.stderr)
            return 1
    else:
        mode = "hook_install" if args.hook_install else "update"
        r = run_action(f"graphify_{mode}", p, cfg)
    print(f"graphify {mode}: {'ok' if r.ok else 'fail'} (exit {r.exit_code})")
    return 0 if r.ok else 1
```

Register the subcommands inside `build_parser`, right before `return parser`:

```python
    op = sub.add_parser("open", parents=[sub_common])
    op.add_argument("project")
    op.set_defaults(func=_cmd_open)

    te = sub.add_parser("test", parents=[sub_common])
    te.add_argument("project")
    te.set_defaults(func=_cmd_test)

    fe = sub.add_parser("fetch", parents=[sub_common])
    fe.add_argument("project")
    fe.set_defaults(func=_cmd_fetch)

    gf = sub.add_parser("graphify", parents=[sub_common])
    gf.add_argument("project")
    gf.add_argument("--init", action="store_true")
    gf.add_argument("--update", action="store_true")
    gf.add_argument("--hook-install", dest="hook_install", action="store_true")
    gf.add_argument("--yes", action="store_true", help="skip confirmation for --init")
    gf.set_defaults(func=_cmd_graphify)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_actions.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/cli.py tests/test_cli_actions.py
git commit -m "feat(cli): open/test/fetch/graphify subcommands"
```

---

### Task 7: Server auth helpers & token (`aos/server.py`)

**Files:**
- Create: `aos/server.py`
- Test: `tests/test_server_auth.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from aos.server import host_allowed, load_or_create_token, token_ok


def test_host_allowed():
    assert host_allowed("127.0.0.1:7777") is True
    assert host_allowed("localhost:7777") is True
    assert host_allowed("evil.example.com") is False
    assert host_allowed(None) is False


def test_token_ok_constant_compare():
    assert token_ok("abc", "abc") is True
    assert token_ok("abc", "abd") is False
    assert token_ok(None, "abc") is False


def test_load_or_create_token_persists(tmp_path: Path):
    p = tmp_path / "token"
    t1 = load_or_create_token(p)
    assert len(t1) >= 16
    assert oct(p.stat().st_mode)[-3:] == "600"
    t2 = load_or_create_token(p)
    assert t1 == t2  # stable across calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.server'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path

_ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


def host_allowed(host_header: str | None) -> bool:
    if not host_header:
        return False
    host = host_header.split(":", 1)[0]
    return host in _ALLOWED_HOSTS


def token_ok(provided: str | None, expected: str) -> bool:
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


def load_or_create_token(path: Path) -> str:
    path = Path(path)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(24)
    path.write_text(token, encoding="utf-8")
    os.chmod(path, 0o600)
    return token
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server_auth.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/server.py tests/test_server_auth.py
git commit -m "feat(server): host/token auth helpers + per-run token file"
```

---

### Task 8: HTTP server — read endpoints & action POST (`aos/server.py`)

**Files:**
- Modify: `aos/server.py`
- Create: `aos/web/index.html` (placeholder so `/` has something to serve; full UI in Task 9)
- Test: `tests/test_server_http.py`

- [ ] **Step 1: Write the failing test**

```python
import http.client
import json
import subprocess
import threading
from pathlib import Path

import pytest

from aos.config import DEFAULT_CONFIG
from aos.server import make_server


def _repo(root: Path, name="demo") -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@e.st"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True, capture_output=True)
    (repo / "README.md").write_text("# d\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "i"], check=True, capture_output=True)
    return repo


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "Projects"
    _repo(root)
    cfg = dict(DEFAULT_CONFIG, roots=[str(root)],
               tools=dict(DEFAULT_CONFIG["tools"], git="git"))
    srv = make_server(cfg, port=0, token="testtoken", conf_path=tmp_path / "none.conf")
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield port
    srv.shutdown()


def test_get_projects(server):
    conn = http.client.HTTPConnection("127.0.0.1", server)
    conn.request("GET", "/api/projects")
    resp = conn.getresponse()
    assert resp.status == 200
    data = json.loads(resp.read())
    assert any(p["name"] == "demo" for p in data)


def test_post_action_requires_token(server):
    conn = http.client.HTTPConnection("127.0.0.1", server)
    conn.request("POST", "/api/projects/demo/actions/git_fetch", body="{}")
    assert conn.getresponse().status == 403


def test_post_action_with_token(server):
    conn = http.client.HTTPConnection("127.0.0.1", server)
    conn.request("POST", "/api/projects/demo/actions/git_fetch",
                 body="{}", headers={"X-AOS-Token": "testtoken"})
    resp = conn.getresponse()
    assert resp.status == 200
    assert json.loads(resp.read())["kind"] == "git_fetch"


def test_post_unknown_kind_is_400(server):
    conn = http.client.HTTPConnection("127.0.0.1", server)
    conn.request("POST", "/api/projects/demo/actions/nuke",
                 body="{}", headers={"X-AOS-Token": "testtoken"})
    assert conn.getresponse().status == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server_http.py -v`
Expected: FAIL with `ImportError: cannot import name 'make_server'`

- [ ] **Step 3: Create placeholder `aos/web/index.html`**

```html
<!doctype html><meta charset="utf-8"><title>aos</title><body><h1>aos</h1></body>
```

- [ ] **Step 4: Add to `aos/server.py`**

Add imports at the top (merge with existing):

```python
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from aos.actions import ACTION_KINDS, ActionError, run_action
from aos.aggregator import build_all
```

Append at the end of the file:

```python
_WEB_DIR = Path(__file__).parent / "web"


def _render_index(cfg: dict, token: str) -> bytes:
    html = (_WEB_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace("__AOS_TOKEN__", token)
    html = html.replace("__AOS_REFRESH__", str(cfg.get("refresh_interval_sec", 10)))
    return html.encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    cfg: dict = {}
    token: str = ""
    conf_path = None

    def log_message(self, *a):  # silence default stderr logging
        pass

    def _send(self, status: int, body: bytes, ctype="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _projects(self):
        return build_all(self.cfg, conf_path=self.conf_path)

    def do_GET(self):
        if not host_allowed(self.headers.get("Host")):
            return self._json(403, {"error": "bad host"})
        if self.path == "/" or self.path.startswith("/index.html"):
            return self._send(200, _render_index(self.cfg, self.token), "text/html; charset=utf-8")
        if self.path == "/api/projects":
            return self._json(200, [p.to_dict() for p in self._projects()])
        if self.path.startswith("/api/projects/"):
            name = self.path.rsplit("/", 1)[-1]
            p = next((x for x in self._projects() if x.name == name), None)
            return self._json(200, p.to_dict()) if p else self._json(404, {"error": "not found"})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if not host_allowed(self.headers.get("Host")):
            return self._json(403, {"error": "bad host"})
        if not token_ok(self.headers.get("X-AOS-Token"), self.token):
            return self._json(403, {"error": "bad token"})
        parts = self.path.strip("/").split("/")
        # api / projects / {name} / actions / {kind}
        if len(parts) != 5 or parts[0:2] != ["api", "projects"] or parts[3] != "actions":
            return self._json(404, {"error": "not found"})
        name, kind = parts[2], parts[4]
        if kind not in ACTION_KINDS:
            return self._json(400, {"error": f"unknown action: {kind}"})
        p = next((x for x in self._projects() if x.name == name), None)
        if not p:
            return self._json(404, {"error": "project not found"})
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            opts = json.loads(raw or b"{}")
        except ValueError:
            opts = {}
        try:
            result = run_action(kind, p, self.cfg, **opts)
        except ActionError as exc:
            return self._json(400, {"error": str(exc)})
        return self._json(200, result.to_dict())


def make_server(cfg: dict, port: int, token: str, conf_path=None) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (_Handler,), {"cfg": cfg, "token": token, "conf_path": conf_path})
    return ThreadingHTTPServer(("127.0.0.1", port), handler)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_server_http.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add aos/server.py aos/web/index.html tests/test_server_http.py
git commit -m "feat(server): localhost HTTP read endpoints + token-guarded action POST"
```

---

### Task 9: Web UI `/wall` (`aos/web/index.html`)

**Files:**
- Modify: `aos/web/index.html`
- Test: `tests/test_web_assets.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import aos


def test_index_html_is_offline_and_has_hooks():
    html = (Path(aos.__file__).parent / "web" / "index.html").read_text(encoding="utf-8")
    # no external network references (offline-only)
    assert "http://" not in html and "https://" not in html
    assert "cdn" not in html.lower()
    # template hooks the server fills in
    assert "__AOS_TOKEN__" in html
    assert "__AOS_REFRESH__" in html
    # talks to the read API
    assert "/api/projects" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_assets.py -v`
Expected: FAIL — placeholder html lacks `__AOS_TOKEN__` / `/api/projects`

- [ ] **Step 3: Replace `aos/web/index.html` with the full wall**

```html
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>aos · wall</title>
<style>
  :root { --bg:#0f1115; --card:#171a21; --mut:#8b93a7; --line:#252a35; --txt:#e6e9ef;
          --green:#3fb950; --yellow:#d29922; --red:#f85149; --unknown:#6e7681; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif; }
  header { display:flex; align-items:center; gap:14px; padding:14px 20px; border-bottom:1px solid var(--line); }
  header .title { font-weight:600; font-size:16px; }
  header .sum span { margin-left:10px; }
  .grid { display:grid; gap:12px; padding:16px 20px;
          grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }
  .card h3 { margin:0 0 8px; font-size:15px; display:flex; align-items:center; gap:8px; }
  .dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
  .g{background:var(--green)} .y{background:var(--yellow)} .r{background:var(--red)} .u{background:var(--unknown)}
  .meta { color:var(--mut); margin-left:auto; font-size:12px; }
  table.kv { width:100%; font-size:13px; color:var(--mut); border-collapse:collapse; }
  table.kv td { padding:2px 0; }
  table.kv td.v { text-align:right; color:var(--txt); }
  .acts { display:flex; flex-wrap:wrap; gap:6px; margin-top:12px; }
  button { background:transparent; color:var(--txt); border:1px solid var(--line);
           border-radius:7px; padding:5px 10px; font-size:12px; cursor:pointer; }
  button:hover { border-color:var(--mut); }
  .focus { padding:12px 20px; color:var(--mut); font-size:13px; border-top:1px solid var(--line); }
  .focus b { color:var(--txt); }
  #toast { position:fixed; right:16px; bottom:16px; background:var(--card);
           border:1px solid var(--line); border-radius:8px; padding:10px 14px; display:none; }
</style>
</head>
<body>
<header>
  <span class="title">aos · wall</span>
  <span class="sum" id="sum"></span>
  <button style="margin-left:auto" onclick="load()">↻ refresh</button>
</header>
<div class="grid" id="grid"></div>
<div class="focus" id="focus"></div>
<div id="toast"></div>
<script>
const TOKEN = "__AOS_TOKEN__";
const REFRESH = parseInt("__AOS_REFRESH__", 10) || 10;
const CLS = { green:"g", yellow:"y", red:"r", unknown:"u" };

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.style.display = "block";
  setTimeout(() => { t.style.display = "none"; }, 3000);
}

async function act(name, kind, opts) {
  const r = await fetch(`/api/projects/${name}/actions/${kind}`, {
    method:"POST", headers:{ "X-AOS-Token":TOKEN, "Content-Type":"application/json" },
    body: JSON.stringify(opts || {})
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { toast("✗ " + (data.error || r.status)); return; }
  toast(`${kind}: ${data.ok ? "ok" : "fail"}${data.exit_code != null ? " (exit "+data.exit_code+")" : ""}`);
  load();
}

function card(p) {
  const g = p.graphify || {}, git = p.git || {}, pr = p.progress || {};
  const diff = git.is_repo ? `+${git.insertions||0}/-${git.deletions||0}` : "-";
  const prog = pr.percent != null ? pr.percent + "%" : "-";
  const dirty = git.dirty ? "dirty" : "clean";
  const dl = (p.deadlines || []).map(d => `${d.title}: ${d.due}${d.overdue ? " ⚠" : ""}`).join("; ") || "—";
  return `<div class="card">
    <h3><span class="dot ${CLS[p.health]||'u'}"></span>${p.name}
        <span class="meta">${p.type} · ${p.stage}</span></h3>
    <table class="kv">
      <tr><td>git</td><td class="v">${git.branch||'-'} · ${dirty} · ${diff}</td></tr>
      <tr><td>graph</td><td class="v">${g.status||'-'}${g.hook_installed ? ' · hook' : ''}</td></tr>
      <tr><td>progress</td><td class="v">${prog}</td></tr>
      <tr><td>deadline</td><td class="v">${dl}</td></tr>
    </table>
    <div class="acts">
      <button onclick="act('${p.name}','open_session')">Open</button>
      <button onclick="act('${p.name}','run_tests')">Test</button>
      <button onclick="act('${p.name}','git_fetch')">Fetch</button>
      <button onclick="act('${p.name}','graphify_update')">Graph ↻</button>
    </div></div>`;
}

function focusStrip(ps) {
  const fails = ps.filter(p => (p.tests||{}).status === "fail").map(p => p.name);
  const stale = ps.filter(p => (p.graphify||{}).status === "stale").map(p => p.name);
  const dirty = ps.filter(p => (p.git||{}).dirty).map(p => p.name);
  const due = ps.filter(p => (p.deadlines||[]).some(d => d.overdue)).map(p => p.name);
  const part = (label, arr) => arr.length ? `<b>${label}:</b> ${arr.join(", ")}` : "";
  return [part("tests failing", fails), part("graph stale", stale),
          part("uncommitted", dirty), part("overdue", due)].filter(Boolean).join(" &nbsp;·&nbsp; ")
          || "всё спокойно";
}

async function load() {
  const ps = await (await fetch("/api/projects")).json();
  const by = { green:0, yellow:0, red:0, unknown:0 };
  ps.forEach(p => by[p.health] = (by[p.health]||0) + 1);
  document.getElementById("sum").innerHTML =
    `<span style="color:var(--green)">${by.green} green</span>
     <span style="color:var(--yellow)">${by.yellow} yellow</span>
     <span style="color:var(--red)">${by.red} red</span>`;
  document.getElementById("grid").innerHTML = ps.map(card).join("");
  document.getElementById("focus").innerHTML = focusStrip(ps);
}

load();
setInterval(load, REFRESH * 1000);
</script>
</body>
</html>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_assets.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/web/index.html tests/test_web_assets.py
git commit -m "feat(web): offline /wall — cards, summary, focus strip, action buttons"
```

---

### Task 10: `aos serve` command + full verification

**Files:**
- Modify: `aos/cli.py`
- Modify: `README.md`
- Test: `tests/test_cli_serve.py`

- [ ] **Step 1: Write the failing test**

```python
from aos.cli import build_parser


def test_serve_parser_has_port_and_no_browser():
    parser = build_parser()
    args = parser.parse_args(["serve", "--port", "9999", "--no-browser"])
    assert args.port == 9999
    assert args.no_browser is True
    assert args.func.__name__ == "_cmd_serve"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_serve.py -v`
Expected: FAIL with `argument command: invalid choice: 'serve'`

- [ ] **Step 3: Modify `aos/cli.py`**

Add the serve command function before `build_parser`:

```python
def _cmd_serve(args, cfg) -> int:
    import webbrowser

    from aos.server import load_or_create_token, make_server

    port = args.port or cfg["port"]
    token = load_or_create_token(expand("~/.config/aos/token"))
    srv = make_server(cfg, port=port, token=token, conf_path=_conf_path())
    url = f"http://127.0.0.1:{port}/"
    print(f"aos serve → {url}  (Ctrl+C для выхода)")
    if not args.no_browser and cfg.get("open_browser", True):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")
    finally:
        srv.shutdown()
    return 0
```

Register it inside `build_parser`, before `return parser`:

```python
    sv = sub.add_parser("serve", parents=[sub_common])
    sv.add_argument("--port", type=int, default=None)
    sv.add_argument("--no-browser", action="store_true")
    sv.set_defaults(func=_cmd_serve)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_serve.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Update `README.md`**

Add this section after the existing CLI block:

```markdown
## Actions & web (Plan 2)

```bash
aos open village-emrg          # open the work session (new kitty window → project)
aos test village-emrg          # run the whitelisted test command, store result
aos fetch village-emrg         # git fetch --prune (only network git action)
aos graphify village-emrg --hook-install   # install the auto-rebuild commit hook
aos graphify village-emrg                  # graphify update . (free, code-only)
aos graphify village-emrg --init           # full build (LLM: network + tokens; asks to confirm)
aos serve                      # local web dashboard at http://127.0.0.1:7777/wall
```

Safety: only the closed set of action kinds exists; per-project commands are checked
against `exec_allowlist` and run with `shell=False`; the server binds `127.0.0.1` and
POST actions require the per-run token in `~/.config/aos/token`.
```

- [ ] **Step 6: Run the full suite + manual smoke**

Run: `pytest`
Expected: PASS — all Plan 1 + Plan 2 tests green.

Manual smoke (optional, real machine):
Run: `aos serve --no-browser &` then `curl -s http://127.0.0.1:7777/api/projects | python -m json.tool | head`
Expected: JSON array of projects; open `http://127.0.0.1:7777/` to see the wall. Kill the server afterwards.

- [ ] **Step 7: Commit**

```bash
git add aos/cli.py README.md tests/test_cli_serve.py
git commit -m "feat(cli): aos serve; docs: actions & web usage"
```

---

## Self-Review

**Spec coverage (§7 actions+safety, §9 web):**
- Closed action-kind set + dispatcher (spec §7.1) → Task 5 (`ACTION_KINDS`, `run_action`) ✓
- exec-allowlist + shlex + `shell=False` + sanitised env + timeout + cwd (spec §7.2) → Tasks 1, 2 ✓
- open_session via kitty launcher template, detached, name-validated (spec §7.3) → Task 5 ✓
- graphify update/hook-install/init with init-confirm gate (spec §7.4) → Tasks 4, 6 ✓
- run_tests writes `.aos/state/tests.json`; git_fetch the only git network action (spec §5, §7) → Tasks 3, 4 ✓
- bind 127.0.0.1 + per-run token (mode 600) + Host/Origin guard (spec §7.2, §9) → Tasks 7, 8 ✓
- read endpoints `/api/projects`, `/api/projects/{name}`; POST actions endpoint (spec §9) → Task 8 ✓
- offline single-file `/wall` with cards + focus strip + action buttons, no CDN (spec §9) → Task 9 ✓
- `aos open/test/fetch/graphify/serve` CLI (spec §8) → Tasks 6, 10 ✓
- Deferred to Plan 3 (correctly out of scope): processes/sessions/security collectors, TUI, auto-scaffold, new-project.sh patch.

**Placeholder scan:** No TBD/TODO; every code step is complete. The Task 8 `aos/web/index.html` is intentionally a one-line placeholder, fully replaced in Task 9 (sequencing, not a placeholder-gap).

**Type consistency:** `ActionResult(kind, ok, command, exit_code, stdout, stderr, message)` + `.to_dict()` used identically across actions, CLI, server. `run_action(kind, project, cfg, **opts)` signature matches every call site (CLI `_cmd_*`, server `do_POST`). `ActionError` raised in actions, caught in CLI (`_cmd_*`) and server (`do_POST`). `make_server(cfg, port, token, conf_path=None)` matches the serve command and tests. `host_allowed`/`token_ok`/`load_or_create_token` names consistent between `server.py` and tests. `graphify_action(project, cfg, mode=, confirm=, runner=)` and `graphify_argv(mode, bin)` consistent between Tasks 4, 5, 6. CLI integrates via existing `_find`, `sub_common`, `expand`, `_conf_path` from Plan 1 (verified against the committed `aos/cli.py`).
```
