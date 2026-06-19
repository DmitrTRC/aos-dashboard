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
