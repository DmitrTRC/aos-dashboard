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
