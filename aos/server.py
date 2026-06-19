from __future__ import annotations

import hmac
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from aos.actions import ACTION_KINDS, ActionError, run_action
from aos.aggregator import build_all

_ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


def host_allowed(host_header: str | None) -> bool:
    if not host_header:
        return False
    host = host_header.split(":", 1)[0]
    return host in _ALLOWED_HOSTS


def token_ok(provided: str | None, expected: str) -> bool:
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


def load_or_create_token(path: Path) -> str:
    path = Path(path)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(24)
    path.write_text(token, encoding="utf-8")
    os.chmod(path, 0o600)
    return token


_WEB_DIR = Path(__file__).parent / "web"


def _render_index(cfg: dict, token: str) -> bytes:
    html = (_WEB_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace("__AOS_TOKEN__", token)
    html = html.replace("__AOS_REFRESH__", str(cfg.get("refresh_interval_sec", 10)))
    return html.encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    cfg: dict = {}
    token: str = ""
    conf_path = None

    def log_message(self, *a):  # silence default stderr logging
        pass

    def _send(self, status: int, body: bytes, ctype="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _projects(self):
        return build_all(self.cfg, conf_path=self.conf_path)

    def do_GET(self):
        if not host_allowed(self.headers.get("Host")):
            return self._json(403, {"error": "bad host"})
        if self.path == "/" or self.path.startswith("/index.html"):
            return self._send(200, _render_index(self.cfg, self.token), "text/html; charset=utf-8")
        if self.path == "/api/projects":
            return self._json(200, [p.to_dict() for p in self._projects()])
        if self.path.startswith("/api/projects/"):
            name = self.path.rsplit("/", 1)[-1]
            p = next((x for x in self._projects() if x.name == name), None)
            return self._json(200, p.to_dict()) if p else self._json(404, {"error": "not found"})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if not host_allowed(self.headers.get("Host")):
            return self._json(403, {"error": "bad host"})
        if not token_ok(self.headers.get("X-AOS-Token"), self.token):
            return self._json(403, {"error": "bad token"})
        parts = self.path.strip("/").split("/")
        # api / projects / {name} / actions / {kind}
        if len(parts) != 5 or parts[0:2] != ["api", "projects"] or parts[3] != "actions":
            return self._json(404, {"error": "not found"})
        name, kind = parts[2], parts[4]
        if kind not in ACTION_KINDS:
            return self._json(400, {"error": f"unknown action: {kind}"})
        p = next((x for x in self._projects() if x.name == name), None)
        if not p:
            return self._json(404, {"error": "project not found"})
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            opts = json.loads(raw or b"{}")
        except ValueError:
            opts = {}
        try:
            result = run_action(kind, p, self.cfg, **opts)
        except ActionError as exc:
            return self._json(400, {"error": str(exc)})
        return self._json(200, result.to_dict())


def make_server(cfg: dict, port: int, token: str, conf_path=None) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (_Handler,), {"cfg": cfg, "token": token, "conf_path": conf_path})
    return ThreadingHTTPServer(("127.0.0.1", port), handler)
