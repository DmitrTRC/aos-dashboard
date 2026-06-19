import subprocess
from pathlib import Path

from aos.collectors.security import collect_security


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@e.st")
    _git(repo, "config", "user.name", "t")
    return repo


def test_env_example_is_not_a_secret(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / ".env.example").write_text("KEY=changeme\n")
    (repo / "web.env.template").write_text("X=1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "templates")
    s = collect_security(repo, git_bin="git")
    assert s.findings == []
    assert s.has_tracked_secret is False


def test_real_env_still_flagged_alongside_example(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / ".env").write_text("SECRET=1\n")
    (repo / ".env.example").write_text("SECRET=changeme\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "oops real env")
    s = collect_security(repo, git_bin="git")
    paths = {f.path for f in s.findings}
    assert ".env" in paths
    assert ".env.example" not in paths
    assert s.has_tracked_secret is True
