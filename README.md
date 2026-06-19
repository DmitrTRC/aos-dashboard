<div align="center">

# aos · dashboard

**A local, read-first control plane for your projects** — one glance tells you which repos are healthy, dirty, stale, or on fire.

Built for the `kitty + zellij + nvim + claude` workflow, but it works on any folder of git repos.

[![CI](https://github.com/DmitrTRC/aos-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/DmitrTRC/aos-dashboard/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![Version](https://img.shields.io/badge/version-1.0.0-blueviolet)
![Dependencies](https://img.shields.io/badge/deps-PyYAML%20only-lightgrey)

</div>

---

```text
NAME           HEALTH   STAGE  BRANCH  GIT    GRAPH    PROG  SES
aos-dashboard  green    build  main    clean  fresh    100%  ●
brainme        unknown  idea   -       clean  missing  -     ·
junior-it      green    idea   main    clean  fresh    -     ·
research       yellow   idea   main    dirty  missing  -     ·
village-emrg   yellow   build  main    dirty  stale    40%   ·
```

`aos` discovers every project under `~/Projects`, reads its real state — git, progress,
deadlines, [graphify](https://github.com/) knowledge-graph freshness, test results, live
zellij sessions, running processes, and committed-secret risks — and renders one health
verdict per project. It ships three faces over the **same** snapshot: a CLI, an ANSI TUI
board, and an offline localhost web wall.

## Why

A directory full of repos hides its own state. Which ones have uncommitted work? Whose tests
are red? Where did a `.env` slip into git? Which graphify graph is stale? `aos` answers all of
that in one command — without you opening a single repo — and then lets you act
(`open` / `test` / `fetch` / `graphify`) through one safe, allow-listed layer.

## Features

- **Read-first by default** — `status`, `ls`, `show`, `dash` never mutate your repos.
- **One health verdict** per project — `green` / `yellow` / `red` / `unknown`, with reasons.
- **Sensors:** git (branch, dirty, ahead/behind, diffstat), progress (from superpowers plan
  checklists), deadlines, graphify freshness + commit-hook, test state, live zellij sessions
  (+ detected agents), project-bound processes, and a security-lite secret scan.
- **Three surfaces, one core:** terminal table (`aos status`), live TUI board (`aos dash --watch`),
  and an offline web wall (`aos serve` → `/wall`).
- **Safe actions:** a closed set of action kinds, per-project commands checked against an
  `exec_allowlist` and run with `shell=False`; the web server binds `127.0.0.1` and gates
  every action behind a per-run token.
- **Tiny footprint:** Python 3.11+ stdlib, a single dependency (PyYAML), no CDN, no telemetry.

## Install

```bash
git clone https://github.com/DmitrTRC/aos-dashboard.git
cd aos-dashboard
python -m pip install -e ".[dev]"   # editable + pytest
aos --version
```

## Quick start

```bash
aos status                 # health table of all projects in ~/Projects
aos dash --watch           # live ANSI board
aos serve                  # web wall at http://127.0.0.1:7777/wall
```

## Commands

### Read

| Command | What it does |
|---|---|
| `aos status` | Health table of all discovered projects |
| `aos status --json` | Machine-readable snapshot (pipe to `jq`) |
| `aos status --exit-code` | Exit `2` if any project is red — for statuslines / CI |
| `aos ls` | Discovered projects (registry + unregistered) |
| `aos show <project>` | Full snapshot: git, graphify, progress, deadlines, session, processes, security |
| `aos scan` | Discovery count (+ optional auto-scaffold) |
| `aos dash` / `aos dash --watch` | One-shot or live TUI board (`aos wall` is an alias) |
| `aos doctor` | Environment check (tools, config, roots) |

### Act

| Command | What it does |
|---|---|
| `aos open <project>` | Open the work session (new kitty window → project) |
| `aos test <project>` | Run the allow-listed test command, store the result |
| `aos fetch <project>` | `git fetch --prune` (the only network git action) |
| `aos graphify <project>` | `graphify update .` — refresh the knowledge graph (code-only) |
| `aos graphify <project> --hook-install` | Install the auto-rebuild commit hook |
| `aos graphify <project> --init [--yes]` | Full build (LLM: network + tokens; asks to confirm) |
| `aos init <project>` / `aos init --all` | Scaffold `.aos/project.yaml` |
| `aos serve [--port N] [--no-browser]` | Localhost web wall + token-guarded action API |

Global flags work before or after the subcommand: `--root <path>`, `--json`, `--no-color`.

## Configuration

Config lives at `~/.config/aos/config.yaml`. Everything has a sane default — see
[`configs/config.example.yaml`](configs/config.example.yaml). Highlights:

```yaml
roots: ["~/Projects"]          # where to discover projects
port: 7777                     # web wall port
refresh_interval_sec: 10       # TUI / wall refresh
auto_scaffold: false           # opt-in: write .aos/ stubs on scan/serve
tools:                         # absolute tool paths (checked by `aos doctor`)
  git: /usr/bin/git
  zellij: /opt/homebrew/bin/zellij
  kitty: /Applications/kitty.app/Contents/MacOS/kitty
  graphify: graphify
  ps: /bin/ps
exec_allowlist: [git, pnpm, npm, yarn, pytest, python, python3, node, make, just, bats, graphify, cargo, go]
health:
  deadline_warn_days: 7
  inactive_warn_days: 14
```

A registry at `~/.config/projects.conf` (`name | path | layout`, `#` comments) maps friendly
names to paths; anything else under `roots` is discovered as an unregistered project.

### Per-project file

Each project may carry an `.aos/project.yaml` describing itself (title, type, stage, deadlines,
test command, graphify policy, …) — see [`configs/project.example.yaml`](configs/project.example.yaml).
Create one with `aos init <name>`, or seed it at project-creation time
(see [`docs/integration-new-project.md`](docs/integration-new-project.md)). Runtime state lives
under `.aos/state/` and is git-ignored.

## Health model

| Verdict | Trigger |
|---|---|
| 🔴 `red` | failing tests · overdue deadline · required graphify missing · **a secret committed to git** |
| 🟡 `yellow` | uncommitted changes · stale graphify · deadline within the warn window |
| 🟢 `green` | clean working tree, nothing flagged |
| ⚪ `unknown` | not a git repo and no `.aos/project.yaml` |

## Safety model

`aos` is read-first; the only module that ever executes commands is `aos/actions.py`, and it is
deliberately small:

- **Closed action set** — every action is one of a fixed list of kinds (`open_session`,
  `run_tests`, `git_fetch`, `graphify_*`, `open_report`). No arbitrary command runs.
- **Allow-listed executables** — per-project commands are tokenised with `shlex` and the
  executable is checked against `exec_allowlist`. `shell=False`, sanitised env, timeout, and a
  cwd bound to the project — shell metacharacters in arguments are inert.
- **Confirmation gates** — `graphify --init` (network + LLM tokens) refuses without `--yes`.
- **Localhost-only web** — the server binds `127.0.0.1`, validates the `Host` header, and every
  POST action requires the per-run token stored in `~/.config/aos/token` (mode `600`).

## Architecture

```text
config ─┐
registry ├─► aggregator ──► collectors (git · progress · deadlines · graphify ·
model ──┘        │            tests · processes · sessions · security)  → Project snapshot
                 ├─► health (green/yellow/red/unknown + reasons)
                 └─► surfaces:  cli (table/json) · tui (ANSI board) · server (/wall + action API)
                                              actions.py  ← the single command-executing layer
```

Each collector is subprocess-bound, time-boxed, and **never raises** — a hung tool degrades one
field, not the whole snapshot. The aggregator runs collectors concurrently and computes the live
zellij-session set once per pass.

## Development

```bash
python -m pip install -e ".[dev]"
pytest                 # full suite (88 tests)
aos --root ~/Projects status
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the TDD workflow and conventions, and
[CHANGELOG.md](CHANGELOG.md) for the release history. The full design spec and the per-milestone
implementation plans + reports live under [`docs/`](docs/).

## License

[MIT](LICENSE) © 2026 Dmitry Morozov
