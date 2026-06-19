# Contributing to aos-dashboard

Thanks for taking a look. This is a small, dependency-light tool — contributions that keep it
that way are the most welcome.

## Ground rules

- **Read-first.** New read paths must never mutate a user's repos. Anything that executes a
  command goes through `aos/actions.py` and the `exec_allowlist` — no exceptions, no `shell=True`.
- **Stdlib + PyYAML only.** Adding a runtime dependency needs a strong reason.
- **Collectors never raise.** A failing/hung tool degrades one field, not the snapshot — wrap
  subprocess calls and return a sane default.
- **Test-first.** Every non-trivial change starts with a failing test.

## Development setup

```bash
python -m pip install -e ".[dev]"
pytest
```

> macOS ships only `python3`. Some tests invoke `python`; if `pytest` can't find it, add a shim:
> `ln -sf "$(command -v python3)" ~/.local/bin/python` (or run on a machine where `python` resolves).

## TDD workflow

1. Write a failing test under `tests/`.
2. Run it — confirm it fails for the right reason.
3. Write the minimal implementation.
4. Run it — confirm green.
5. Run the full suite (`pytest`) to check for regressions.
6. Commit with a conventional message (see below).

## Commit messages

Conventional Commits, present tense, no emoji:

```
feat(collectors): add docker-container sensor
fix(server): reject non-loopback Host headers
docs: clarify auto_scaffold opt-in
chore: bump dev tooling
```

Refactors go in their own commit (ideally their own branch). Keep changes minimally invasive —
match the style of the file you're editing.

## Pull requests

- Keep PRs focused; one concern per PR.
- Include tests and make sure `pytest` is green.
- Update `CHANGELOG.md` (Unreleased section) and any affected docs.
- Don't `git push` to `main` directly — open a PR from a branch.

## Project layout

```
aos/
  config.py        registry.py      model.py        # discovery + model
  collectors/      ...                              # one read-only sensor per file
  health.py        aggregator.py                    # verdict + concurrent snapshot
  actions.py                                        # the ONLY command-executing layer
  cli.py           tui.py           server.py       # three surfaces over one snapshot
  web/index.html                                    # offline /wall
tests/             docs/            configs/
```

See `docs/superpowers/specs/` for the design spec and `docs/superpowers/plans/` +
`docs/superpowers/reports/` for the milestone history.
