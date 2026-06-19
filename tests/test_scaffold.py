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
