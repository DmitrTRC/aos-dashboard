from pathlib import Path

from aos.server import host_allowed, load_or_create_token, token_ok


def test_host_allowed():
    assert host_allowed("127.0.0.1:7777") is True
    assert host_allowed("localhost:7777") is True
    assert host_allowed("evil.example.com") is False
    assert host_allowed(None) is False


def test_token_ok_constant_compare():
    assert token_ok("abc", "abc") is True
    assert token_ok("abc", "abd") is False
    assert token_ok(None, "abc") is False


def test_load_or_create_token_persists(tmp_path: Path):
    p = tmp_path / "token"
    t1 = load_or_create_token(p)
    assert len(t1) >= 16
    assert oct(p.stat().st_mode)[-3:] == "600"
    t2 = load_or_create_token(p)
    assert t1 == t2  # stable across calls
