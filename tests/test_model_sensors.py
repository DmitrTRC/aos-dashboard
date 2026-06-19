import json

from aos.model import (
    ProcessInfo, Project, SecurityFinding, SecurityFindings, SessionState,
)


def test_security_has_tracked_secret():
    s = SecurityFindings(findings=[
        SecurityFinding(path=".env", kind="env", tracked=True),
        SecurityFinding(path="env.bak", kind="env", tracked=False),
    ])
    assert s.has_tracked_secret is True
    assert SecurityFindings().has_tracked_secret is False


def test_project_to_dict_includes_new_sections():
    p = Project(name="x", title="x", path="/x")
    p.processes = [ProcessInfo(pid=42, command="node server.js", port=3000)]
    p.session = SessionState(active=True, session_name="x", agents=["claude"])
    p.security = SecurityFindings(findings=[SecurityFinding(path=".env", kind="env", tracked=True)])
    p.active = True
    d = p.to_dict()
    assert d["processes"][0]["pid"] == 42
    assert d["session"]["active"] is True
    assert d["security"]["has_tracked_secret"] is True
    assert d["active"] is True
    json.dumps(d)  # must not raise
