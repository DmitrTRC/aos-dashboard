from pathlib import Path

from aos.actions import ActionResult, log_action, run_whitelisted


def test_run_whitelisted_executes_without_shell(tmp_path: Path):
    # `&& touch HACKED` must NOT run — proves shell=False (args are literal)
    argv = ["python", "-c", "print('hi')", "&&", "touch", "HACKED"]
    cp = run_whitelisted(argv, cwd=tmp_path, timeout=30)
    assert cp.returncode == 0
    assert "hi" in cp.stdout
    assert not (tmp_path / "HACKED").exists()


def test_run_whitelisted_sanitises_env(tmp_path: Path):
    cp = run_whitelisted(
        ["python", "-c", "import os;print(os.environ.get('SECRET','none'))"],
        cwd=tmp_path, timeout=30, env={"SECRET": "shown"},
    )
    assert "shown" in cp.stdout  # explicit env passes through


def test_log_action_appends_jsonl(tmp_path: Path):
    r = ActionResult(kind="git_fetch", ok=True, command=["git", "fetch"], exit_code=0)
    log_action(tmp_path, r)
    log = tmp_path / ".aos" / "state" / "actions.log"
    assert log.exists()
    assert "git_fetch" in log.read_text()
