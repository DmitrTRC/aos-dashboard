import json
from pathlib import Path

from aos.collectors.tests import collect_tests


def test_unknown_when_no_state(tmp_path: Path):
    assert collect_tests(tmp_path).status == "unknown"


def test_pass_and_fail(tmp_path: Path):
    state = tmp_path / ".aos" / "state"
    state.mkdir(parents=True)
    (state / "tests.json").write_text(json.dumps(
        {"exit_code": 0, "time": "2026-06-19T10:00:00+00:00", "duration_sec": 4.2}
    ))
    ts = collect_tests(tmp_path)
    assert ts.status == "pass"
    assert ts.duration_sec == 4.2

    (state / "tests.json").write_text(json.dumps({"exit_code": 1}))
    assert collect_tests(tmp_path).status == "fail"
