# Integration: seed `.aos/project.yaml` in new projects

`aos init <name>` / `aos init --all` scaffolds a stub `.aos/project.yaml`. If you set
`auto_scaffold: true`, `aos serve`/`aos scan` also seed missing stubs automatically
(off by default). To seed it at creation time instead, add this block to
`~/Projects/new-project.sh` just before the first commit:

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
