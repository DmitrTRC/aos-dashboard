import subprocess
from pathlib import Path

from aos.cli import build_parser, main


def _repo(root: Path, name="demo"):
    repo = root / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@e.st"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True, capture_output=True)
    (repo / "README.md").write_text("# d\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "i"], check=True, capture_output=True)


def test_dash_parser_watch():
    parser = build_parser()
    args = parser.parse_args(["dash", "--watch"])
    assert args.watch is True and args.func.__name__ == "_cmd_dash"


def test_dash_prints_board(tmp_path: Path, capsys):
    root = tmp_path / "Projects"
    _repo(root)
    code = main(["dash", "--root", str(root)])
    out = capsys.readouterr().out
    assert code == 0 and "NAME" in out and "demo" in out
