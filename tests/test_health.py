from aos.config import DEFAULT_CONFIG
from aos.health import evaluate
from aos.model import Deadline, GitState, GraphifyState, Health, Project, TestState


def _proj(**kw) -> Project:
    p = Project(name="x", title="x", path="/x", has_yaml=True)
    p.git = GitState(is_repo=True)
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def test_unknown_when_no_repo_no_yaml():
    p = Project(name="x", title="x", path="/x")
    h, reasons = evaluate(p, DEFAULT_CONFIG)
    assert h == Health.UNKNOWN


def test_red_on_failing_tests():
    p = _proj(tests=TestState(status="fail"))
    h, reasons = evaluate(p, DEFAULT_CONFIG)
    assert h == Health.RED
    assert any("тест" in r.lower() for r in reasons)


def test_red_on_overdue_deadline():
    p = _proj(deadlines=[Deadline(title="d", due="2026-01-01", days_left=-5, overdue=True)])
    assert evaluate(p, DEFAULT_CONFIG)[0] == Health.RED


def test_yellow_on_dirty_tree():
    p = _proj(git=GitState(is_repo=True, untracked=2))
    assert evaluate(p, DEFAULT_CONFIG)[0] == Health.YELLOW


def test_green_when_clean():
    p = _proj()
    assert evaluate(p, DEFAULT_CONFIG)[0] == Health.GREEN
