import subprocess
from pathlib import Path

from aos.collectors.git import collect_git


def test_clean_repo(git_repo: Path):
    st = collect_git(git_repo, git="git")
    assert st.is_repo is True
    assert st.branch == "main"
    assert st.dirty is False
    assert st.head and len(st.head) >= 7
    assert st.last_commit and "init" in st.last_commit


def test_dirty_counts(git_repo: Path):
    (git_repo / "new.txt").write_text("x\n")           # untracked
    (git_repo / "README.md").write_text("# changed\n")  # unstaged
    st = collect_git(git_repo, git="git")
    assert st.untracked == 1
    assert st.unstaged == 1
    assert st.dirty is True


def test_not_a_repo(tmp_path: Path):
    assert collect_git(tmp_path, git="git").is_repo is False
