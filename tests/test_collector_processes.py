from pathlib import Path

from aos.collectors.processes import collect_processes


class _Runner:
    def __init__(self, out):
        self.out = out

    def __call__(self, argv, **kw):
        class _CP:
            pass
        cp = _CP()
        cp.returncode = 0
        cp.stdout = self.out
        cp.stderr = ""
        return cp


def test_matches_processes_under_project_path(tmp_path: Path):
    proj = tmp_path / "demo"
    out = (
        f"  101 node {proj}/packages/web/server.js\n"
        f"  202 /bin/zsh -il\n"
        f"  303 python3 {proj}/run.py\n"
    )
    procs = collect_processes(proj, runner=_Runner(out))
    pids = sorted(p.pid for p in procs)
    assert pids == [101, 303]


def test_runner_failure_is_empty(tmp_path: Path):
    def boom(*a, **k):
        raise FileNotFoundError("no ps")
    assert collect_processes(tmp_path, runner=boom) == []
