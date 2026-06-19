from aos.collectors.sessions import collect_session, live_sessions
from aos.model import ProcessInfo


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


def test_live_sessions_skips_exited():
    out = "village [Created 1h ago]\nold [Created 2d ago] (EXITED - 1h ago)\nresearch [Created]\n"
    live = live_sessions("zellij", runner=_Runner(out))
    assert live == {"village", "research"}


def test_live_sessions_runner_failure_is_empty():
    def boom(*a, **k):
        raise FileNotFoundError("no zellij")
    assert live_sessions("zellij", runner=boom) == set()


def test_collect_session_active_and_agents():
    procs = [ProcessInfo(pid=1, command="/bin/claude --foo"), ProcessInfo(pid=2, command="node x")]
    s = collect_session("village", {"village"}, procs)
    assert s.active is True and s.session_name == "village"
    assert "claude" in s.agents


def test_collect_session_inactive():
    s = collect_session("village", set(), [])
    assert s.active is False and s.session_name is None
