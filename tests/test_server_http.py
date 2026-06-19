import http.client
import json
import subprocess
import threading
from pathlib import Path

import pytest

from aos.config import DEFAULT_CONFIG
from aos.server import make_server


def _repo(root: Path, name="demo") -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@e.st"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True, capture_output=True)
    (repo / "README.md").write_text("# d\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "i"], check=True, capture_output=True)
    return repo


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "Projects"
    _repo(root)
    cfg = dict(DEFAULT_CONFIG, roots=[str(root)],
               tools=dict(DEFAULT_CONFIG["tools"], git="git"))
    srv = make_server(cfg, port=0, token="testtoken", conf_path=tmp_path / "none.conf")
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield port
    srv.shutdown()


def test_get_projects(server):
    conn = http.client.HTTPConnection("127.0.0.1", server)
    conn.request("GET", "/api/projects")
    resp = conn.getresponse()
    assert resp.status == 200
    data = json.loads(resp.read())
    assert any(p["name"] == "demo" for p in data)


def test_post_action_requires_token(server):
    conn = http.client.HTTPConnection("127.0.0.1", server)
    conn.request("POST", "/api/projects/demo/actions/git_fetch", body="{}")
    assert conn.getresponse().status == 403


def test_post_action_with_token(server):
    conn = http.client.HTTPConnection("127.0.0.1", server)
    conn.request("POST", "/api/projects/demo/actions/git_fetch",
                 body="{}", headers={"X-AOS-Token": "testtoken"})
    resp = conn.getresponse()
    assert resp.status == 200
    assert json.loads(resp.read())["kind"] == "git_fetch"


def test_post_unknown_kind_is_400(server):
    conn = http.client.HTTPConnection("127.0.0.1", server)
    conn.request("POST", "/api/projects/demo/actions/nuke",
                 body="{}", headers={"X-AOS-Token": "testtoken"})
    assert conn.getresponse().status == 400
