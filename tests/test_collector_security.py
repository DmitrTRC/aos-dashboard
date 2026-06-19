import subprocess
from pathlib import Path

from aos.collectors.security import collect_security


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True)


def test_flags_tracked_vs_untracked(tmp_path: Path):
    repo = tmp_path / "demo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@e.st")
    _git(repo, "config", "user.name", "t")
    (repo / ".env").write_text("SECRET=1\n")
    (repo / "SECURITY.md").write_text("# sec\n")
    _git(repo, "add", ".env", "SECURITY.md")
    _git(repo, "commit", "-m", "oops committed env")
    (repo / "env.bak").write_text("OLD=1\n")  # untracked

    s = collect_security(repo, git_bin="git")
    by = {f.path: f for f in s.findings}
    assert by[".env"].tracked is True
    assert by["env.bak"].tracked is False
    assert s.has_tracked_secret is True
    assert s.has_security_md is True


def test_clean_project_no_findings(tmp_path: Path):
    s = collect_security(tmp_path, git_bin="git")
    assert s.findings == []
    assert s.has_tracked_secret is False
