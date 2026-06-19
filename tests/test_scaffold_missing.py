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
