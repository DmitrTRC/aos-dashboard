import json

from aos.model import (
    Deadline, GitState, GraphifyState, Health, Project, ProgressState, TestState,
)


def test_gitstate_dirty():
    assert GitState(is_repo=True, untracked=2).dirty is True
    assert GitState(is_repo=True).dirty is False


def test_project_to_dict_is_json_serialisable():
    p = Project(name="village", title="Village", path="/x/village")
    p.health = Health.GREEN
    p.git = GitState(is_repo=True, branch="main", untracked=1)
    p.deadlines = [Deadline(title="MVP", due="2026-07-01", days_left=12)]
    d = p.to_dict()
    assert d["health"] == "green"
    assert d["git"]["branch"] == "main"
    assert d["deadlines"][0]["title"] == "MVP"
    json.dumps(d)  # must not raise
