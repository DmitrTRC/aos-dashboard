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
