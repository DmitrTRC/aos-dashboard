import pytest

from aos.actions import ActionError, ActionResult, validate_command

ALLOW = ["git", "pnpm", "pytest", "python", "graphify"]


def test_valid_command_returns_argv():
    assert validate_command("pnpm test", ALLOW) == ["pnpm", "test"]


def test_absolute_path_executable_checked_by_basename():
    assert validate_command("/usr/bin/git fetch", ALLOW) == ["/usr/bin/git", "fetch"]


def test_rejects_executable_not_in_allowlist():
    with pytest.raises(ActionError):
        validate_command("rm -rf /tmp/x", ALLOW)


def test_rejects_empty_and_unbalanced_quotes():
    with pytest.raises(ActionError):
        validate_command("   ", ALLOW)
    with pytest.raises(ActionError):
        validate_command('python -c "unbalanced', ALLOW)


def test_action_result_to_dict():
    r = ActionResult(kind="run_tests", ok=True, command=["pytest"], exit_code=0)
    d = r.to_dict()
    assert d["kind"] == "run_tests" and d["ok"] is True and d["command"] == ["pytest"]
