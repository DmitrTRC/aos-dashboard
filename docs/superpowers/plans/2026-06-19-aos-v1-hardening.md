# AOS v1 Hardening Implementation Plan (Plan 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three real defects found during v1 smoke: (1) the security collector false-flags `.env.example`/template files as committed secrets (turned village-emrg falsely RED); (2) `GET /wall` 404s because the server only serves `/`; (3) `auto_scaffold: true` silently writes `.aos/` into every project on `scan`/`serve` — flip the default to opt-in.

**Architecture:** Three small, isolated fixes on top of Plans 1–3, each TDD. No new modules.

**Tech Stack:** Python 3.11+, stdlib, pytest. No new deps.

**Anchors (do not rename):** `aos.collectors.security.collect_security` / `_is_secret`; `aos.server` `_Handler.do_GET` + `make_server`; `aos.config.DEFAULT_CONFIG`.

---

### Task 1: Security collector — stop flagging `.env.example`/templates (`aos/collectors/security.py`)

**Files:**
- Modify: `aos/collectors/security.py`
- Test: `tests/test_security_examples.py`

- [ ] **Step 1: Write the failing test**

```python
import subprocess
from pathlib import Path

from aos.collectors.security import collect_security


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@e.st")
    _git(repo, "config", "user.name", "t")
    return repo


def test_env_example_is_not_a_secret(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / ".env.example").write_text("KEY=changeme\n")
    (repo / "web.env.template").write_text("X=1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "templates")
    s = collect_security(repo, git_bin="git")
    assert s.findings == []
    assert s.has_tracked_secret is False


def test_real_env_still_flagged_alongside_example(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / ".env").write_text("SECRET=1\n")
    (repo / ".env.example").write_text("SECRET=changeme\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "oops real env")
    s = collect_security(repo, git_bin="git")
    paths = {f.path for f in s.findings}
    assert ".env" in paths
    assert ".env.example" not in paths
    assert s.has_tracked_secret is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_security_examples.py -v`
Expected: FAIL — `.env.example` currently appears in findings and trips `has_tracked_secret`

- [ ] **Step 3: Modify `aos/collectors/security.py`**

Replace the `_SECRET_EXT` line and `_is_secret` function with:

```python
_SECRET_EXT = {".pem", ".key"}
_EXAMPLE_SUFFIXES = (".example", ".sample", ".template", ".dist", ".tmpl")


def _is_example(name: str) -> bool:
    return any(name.endswith(suf) for suf in _EXAMPLE_SUFFIXES)


def _is_secret(name: str) -> bool:
    if _is_example(name):
        return False
    return name == "env.bak" or name.startswith(".env") or Path(name).suffix in _SECRET_EXT
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_security_examples.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/collectors/security.py tests/test_security_examples.py
git commit -m "fix(security): do not flag .env.example/template files as secrets"
```

---

### Task 2: Server — serve the wall at `/wall` (`aos/server.py`)

**Files:**
- Modify: `aos/server.py`
- Test: `tests/test_server_wall.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server_wall.py -v`
Expected: FAIL — `/wall` returns 404

- [ ] **Step 3: Modify `aos/server.py`**

In `_Handler.do_GET`, replace the index condition:

```python
        if self.path == "/" or self.path.startswith("/index.html"):
```

with:

```python
        if self.path in ("/", "/wall", "/wall/") or self.path.startswith("/index.html"):
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server_wall.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add aos/server.py tests/test_server_wall.py
git commit -m "fix(server): serve the wall at /wall and /wall/ (doc↔code sync)"
```

---

### Task 3: Make `auto_scaffold` opt-in (default false) (`aos/config.py`)

**Files:**
- Modify: `aos/config.py`
- Modify: `README.md`
- Modify: `docs/integration-new-project.md`
- Test: `tests/test_config_autoscaffold_default.py`

- [ ] **Step 1: Write the failing test**

```python
from aos.config import load_config


def test_auto_scaffold_is_off_by_default(tmp_path):
    cfg = load_config(tmp_path / "missing.yaml")
    assert cfg["auto_scaffold"] is False


def test_auto_scaffold_can_be_enabled(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("auto_scaffold: true\n")
    assert load_config(p)["auto_scaffold"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_autoscaffold_default.py -v`
Expected: FAIL — default is currently `True`

- [ ] **Step 3: Modify `aos/config.py`**

Change the default:

```python
    "auto_scaffold": False,
```

- [ ] **Step 4: Update docs**

In `README.md`, change the Plan 3 sentence about auto-scaffold to:

```markdown
New projects get a stub `.aos/project.yaml` only when you opt in — set `auto_scaffold: true`
in `~/.config/aos/config.yaml` (then `aos scan`/`aos serve` seed missing stubs), or run
`aos init <name>` / `aos init --all` explicitly. Default is off, so read commands never write
into your repos.
```

In `docs/integration-new-project.md`, change the opening sentence to:

```markdown
`aos init <name>` / `aos init --all` scaffolds a stub `.aos/project.yaml`. If you set
`auto_scaffold: true`, `aos serve`/`aos scan` also seed missing stubs automatically
(off by default). To seed it at creation time instead, add this block to
`~/Projects/new-project.sh` just before the first commit:
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config_autoscaffold_default.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add aos/config.py README.md docs/integration-new-project.md tests/test_config_autoscaffold_default.py
git commit -m "fix(config): auto_scaffold off by default; docs clarify opt-in"
```

---

### Task 4: Repo housekeeping + full verification

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Ignore the build artifact**

Append to `.gitignore` (if not already present):

```gitignore
*.egg-info/
```

- [ ] **Step 2: Run the full suite**

Run: `pytest`
Expected: PASS — all Plans 1–4 tests green (no regressions).

- [ ] **Step 3: Re-verify the two fixes against the real workspace**

Run: `aos --root ~/Projects show village-emrg` — village-emrg is no longer RED solely due to `.env.example`.
Run: `aos serve --no-browser &` then `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7777/wall` — prints `200`. Kill the server afterwards.

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore *.egg-info build artifact"
```

---

## Self-Review

**Coverage of reported defects:**
- Security false-positive on `.env.example`/templates → Task 1 (`_is_example` guard) ✓ — village-emrg no longer falsely RED.
- `/wall` 404 (doc↔code from Plan 2) → Task 2 (route alias) ✓.
- `auto_scaffold` surprise writes → Task 3 (default false, docs clarified) ✓.
- Build-artifact hygiene → Task 4 (`*.egg-info/` ignored) ✓.

**Placeholder scan:** none — every step has complete code.

**Type consistency:** `_is_secret(name)`/`_is_example(name)` are module-private to `security.py`; `collect_security` return type unchanged. `do_GET` condition change does not alter the handler interface or `make_server(cfg, port, token, conf_path=)`. `DEFAULT_CONFIG["auto_scaffold"]` remains a bool consumed by `_cmd_scan`/`_cmd_serve` via `cfg.get("auto_scaffold", False)` (already defaulted safely at call sites).

**Note (out of code scope):** village-emrg's `.env.example` is a committed template by convention — do NOT `git rm --cached` it; Task 1 simply stops the collector mis-flagging it.
```
