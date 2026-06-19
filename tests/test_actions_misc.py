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
