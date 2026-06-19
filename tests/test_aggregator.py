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
