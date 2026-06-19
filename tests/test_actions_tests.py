import json
from pathlib import Path

import yaml

from aos.config import DEFAULT_CONFIG
from aos.actions import resolve_test_command, run_tests
from aos.model import Project


def _proj(path: Path) -> Project:
    return Project(name="demo", title="demo", path=str(path))


def _cfg():
    return dict(DEFAULT_CONFIG)


def test_resolve_prefers_yaml_then_detects(tmp_path: Path):
    assert resolve_test_command(tmp_path, {"test": "pytest -q"}) == "pytest -q"
    (tmp_path / "package.json").write_text("{}")
    assert resolve_test_command(tmp_path, {}) == "pnpm test"


def test_run_tests_writes_state_pass(tmp_path: Path):
    aos = tmp_path / ".aos"
    aos.mkdir()
    (aos / "project.yaml").write_text(yaml.safe_dump(
        {"name": "demo", "commands": {"test": "python -c \"import sys;sys.exit(0)\""}}))
    r = run_tests(_proj(tmp_path), _cfg())
    assert r.ok is True and r.exit_code == 0
    state = json.loads((aos / "state" / "tests.json").read_text())
    assert state["exit_code"] == 0


def test_run_tests_records_failure(tmp_path: Path):
    aos = tmp_path / ".aos"
    aos.mkdir()
    (aos / "project.yaml").write_text(yaml.safe_dump(
        {"name": "demo", "commands": {"test": "python -c \"import sys;sys.exit(3)\""}}))
    r = run_tests(_proj(tmp_path), _cfg())
    assert r.ok is False and r.exit_code == 3


def test_run_tests_no_command(tmp_path: Path):
    r = run_tests(_proj(tmp_path), _cfg())
    assert r.ok is False and "не найдена" in r.message
