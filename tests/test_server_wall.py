import http.client
import threading

import pytest

from aos.config import DEFAULT_CONFIG
from aos.server import make_server


@pytest.fixture
def server(tmp_path):
    cfg = dict(DEFAULT_CONFIG, roots=[str(tmp_path)])
    srv = make_server(cfg, port=0, token="t", conf_path=tmp_path / "none.conf")
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield port
    srv.shutdown()


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port)
    conn.request("GET", path)
    r = conn.getresponse()
    return r.status, r.read().decode("utf-8")


def test_wall_path_serves_html(server):
    for path in ("/", "/wall", "/wall/"):
        status, body = _get(server, path)
        assert status == 200, path
        assert "<html" in body.lower() or "aos" in body.lower()
