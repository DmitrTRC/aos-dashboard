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
