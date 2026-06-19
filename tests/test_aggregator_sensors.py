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
