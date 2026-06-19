from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml


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
