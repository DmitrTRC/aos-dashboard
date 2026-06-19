from aos.model import GitState, GraphifyState, Health, Project, ProgressState, SessionState
from aos.tui import render_dash


def _proj(name, health):
    p = Project(name=name, title=name, path="/x", stage="build")
    p.git = GitState(is_repo=True, branch="main")
    p.graphify = GraphifyState(status="fresh")
    p.progress = ProgressState(percent=50)
    p.session = SessionState(active=True)
    p.health = health
    return p


def test_render_dash_has_header_and_rows():
    out = render_dash([_proj("village", Health.YELLOW), _proj("demo", Health.GREEN)], color=False)
    lines = out.splitlines()
    assert "NAME" in lines[0] and "SES" in lines[0]
    assert "village" in out and "demo" in out
    assert "50%" in out
