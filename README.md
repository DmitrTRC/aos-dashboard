# aos-dashboard

Local project dashboard / control plane over the `kitty + zellij + nvim + claude` workflow.

## Install (editable)

```bash
python -m pip install -e ".[dev]"
```

## CLI (read-only, this milestone)

```bash
aos status                 # health table of all projects in ~/Projects
aos status --json | jq .    # machine-readable
aos status --exit-code      # exit 2 if any project is red (for statuslines/CI)
aos ls                     # discovered projects (registry + unregistered)
aos show village-emrg      # detailed snapshot
aos init village-emrg      # scaffold .aos/project.yaml
aos doctor                 # environment check
```

Config lives at `~/.config/aos/config.yaml` (see `configs/config.example.yaml`).

## Actions & web (Plan 2)

```bash
aos open village-emrg          # open the work session (new kitty window → project)
aos test village-emrg          # run the whitelisted test command, store result
aos fetch village-emrg         # git fetch --prune (only network git action)
aos graphify village-emrg --hook-install   # install the auto-rebuild commit hook
aos graphify village-emrg                  # graphify update . (free, code-only)
aos graphify village-emrg --init           # full build (LLM: network + tokens; asks to confirm)
aos serve                      # local web dashboard at http://127.0.0.1:7777/wall
```

Safety: only the closed set of action kinds exists; per-project commands are checked
against `exec_allowlist` and run with `shell=False`; the server binds `127.0.0.1` and
POST actions require the per-run token in `~/.config/aos/token`.

## Sensors & TUI (Plan 3)

```bash
aos dash            # one-shot ANSI board (health, git, graph, progress, session)
aos dash --watch    # live board, refreshes every refresh_interval_sec
aos wall            # alias for dash
```

The `/wall` web cards and `aos show` now include: live zellij **session** (+ detected
agents), running **processes** bound to the project, and **security** findings
(secret-like files; a secret committed to git turns the project red). New projects get a
stub `.aos/project.yaml` only when you opt in — set `auto_scaffold: true`
in `~/.config/aos/config.yaml` (then `aos scan`/`aos serve` seed missing stubs), or run
`aos init <name>` / `aos init --all` explicitly. Default is off, so read commands never write
into your repos.
