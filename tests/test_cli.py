import json
import subprocess
from pathlib import Path

import yaml

from aos.cli import main


def _setup(tmp_path: Path) -> Path:
    root = tmp_path / "Projects"
    repo = root / "demo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@e.st"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True, capture_output=True)
    (repo / "README.md").write_text("# demo\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
    return root


def test_status_json(tmp_path: Path, capsys):
    root = _setup(tmp_path)
    code = main(["status", "--json", "--root", str(root)])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert any(p["name"] == "demo" for p in data)


def test_init_command(tmp_path: Path, capsys):
    root = _setup(tmp_path)
    code = main(["init", "demo", "--root", str(root)])
    assert code == 0
    assert (root / "demo" / ".aos" / "project.yaml").exists()


def test_status_exit_code_flag_red(tmp_path: Path, capsys):
    root = _setup(tmp_path)
    repo = root / "demo"
    state = repo / ".aos" / "state"
    state.mkdir(parents=True)
    (state / "tests.json").write_text(json.dumps({"exit_code": 1}))
    (repo / ".aos" / "project.yaml").write_text(yaml.safe_dump({"name": "demo"}))
    code = main(["status", "--exit-code", "--root", str(root)])
    assert code == 2  # red present
