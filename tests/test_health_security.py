from aos.config import DEFAULT_CONFIG
from aos.health import evaluate
from aos.model import GitState, Health, Project, SecurityFinding, SecurityFindings


def _proj():
    p = Project(name="x", title="x", path="/x", has_yaml=True)
    p.git = GitState(is_repo=True)
    return p


def test_tracked_secret_makes_red():
    p = _proj()
    p.security = SecurityFindings(findings=[SecurityFinding(path=".env", kind="env", tracked=True)])
    h, reasons = evaluate(p, DEFAULT_CONFIG)
    assert h == Health.RED
    assert any("секрет" in r for r in reasons)


def test_untracked_secret_not_red():
    p = _proj()
    p.security = SecurityFindings(findings=[SecurityFinding(path="env.bak", kind="env", tracked=False)])
    assert evaluate(p, DEFAULT_CONFIG)[0] == Health.GREEN
