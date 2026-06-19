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
