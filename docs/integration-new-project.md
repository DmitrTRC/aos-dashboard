# Integration: seed `.aos/project.yaml` in new projects

`aos serve` and `aos scan` already auto-scaffold a stub `.aos/project.yaml` for any
discovered project (when `auto_scaffold: true`). To seed it at creation time instead,
add this block to `~/Projects/new-project.sh` just before the first commit
(after the `docs/` skeleton step):

```bash
# ── .aos/ (project dashboard contract) ─────────────────────────
mkdir -p .aos/state
cat > .aos/project.yaml <<EOF
name: ${NAME}
title: ${NAME}
type: unknown
stage: idea
priority: medium
tags: []
deadlines: []
progress: { mode: auto, percent: null, plan: null }
graphify: { required: false, disabled: false }
commands: {}
session: { launch: null }
dashboard: { show_on_wall: true }
EOF
grep -qxF '.aos/state/' .gitignore 2>/dev/null || printf '\n.aos/state/\n' >> .gitignore
```

This is optional — the dashboard works without it via auto-scaffold. Equivalent one-shot
for existing projects: `aos init <name>` or `aos init --all`.
