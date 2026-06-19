# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-19

First stable release. Delivered across four implementation milestones (Plans 1–4),
each built test-first.

### Added

**Core + read-only CLI (Plan 1)**
- Project discovery over `roots` + a `~/.config/projects.conf` registry with name/dir reconcile.
- `Project` data model with JSON-serialisable snapshots.
- Read-only collectors: git, progress (superpowers plan checklists), deadlines,
  graphify freshness (+ commit-hook sensor), test state.
- Health evaluator: `green` / `yellow` / `red` / `unknown` with reasons.
- Concurrent aggregator building per-project snapshots.
- CLI: `status`, `ls`, `show`, `scan`, `init`, `doctor` — table or `--json`,
  `--exit-code`, `--root`, `--no-color`.

**Actions + safety + web (Plan 2)**
- Single command-executing layer (`actions.py`): closed action set, `exec_allowlist`,
  `shlex` tokenisation, `shell=False`, sanitised env, timeouts, project-bound cwd.
- Actions: `run_tests`, `git_fetch`, `graphify` (update / hook-install / init),
  `open_session`, `open_report` — with an init confirmation gate and a JSONL action log.
- CLI: `open`, `test`, `fetch`, `graphify`.
- Localhost web server (`aos serve`): read endpoints + token-guarded action POST,
  bound to `127.0.0.1`, per-run token (mode `600`); offline single-file `/wall` UI.

**Sensors + TUI + auto-scaffold (Plan 3)**
- Sensors: project-bound processes, live zellij sessions (+ agent detection),
  security-lite secret scan with git-tracked detection.
- `active` project signal; health turns red on a git-tracked secret.
- TUI board: `aos dash` / `aos wall` (+ `--watch`).
- Opt-in `scaffold_missing` on `scan` / `serve`; web cards surface session + secret status.

### Fixed (Plan 4 — v1 hardening)
- Security collector no longer flags `.env.example` / `*.template` / `*.sample` /
  `*.dist` / `*.tmpl` files as secrets (false-positive red removed).
- Web server serves the wall at `/wall` and `/wall/` (doc↔code sync), not only `/`.
- `auto_scaffold` now defaults to **off** — read commands never write into your repos
  unless you opt in.

### Notes
- Python 3.11+ ; single runtime dependency: PyYAML.
- 88 tests, all green.

[1.0.0]: https://github.com/DmitrTRC/aos-dashboard/releases/tag/v1.0.0
