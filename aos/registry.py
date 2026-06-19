from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProjectRef:
    name: str
    path: str
    layout: str = ""
    registered: bool = True


def expand_path(raw: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def parse_projects_conf(text: str) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split("|")]
        if len(parts) < 2:
            continue
        name, path = parts[0], parts[1]
        layout = parts[2] if len(parts) > 2 else ""
        entries.append((name, path, layout))
    return entries


def _is_project_dir(d: Path) -> bool:
    return (d / ".git").exists() or (d / ".aos" / "project.yaml").exists()


def discover(
    roots: list[str],
    conf_path: Path | None = None,
    exclude_dirs: list[str] | None = None,
) -> list[ProjectRef]:
    exclude = set(exclude_dirs or [])
    refs: dict[str, ProjectRef] = {}  # keyed by resolved path

    if conf_path and Path(conf_path).exists():
        for name, raw, layout in parse_projects_conf(Path(conf_path).read_text(encoding="utf-8")):
            p = expand_path(raw)
            refs[str(p)] = ProjectRef(name=name, path=str(p), layout=layout, registered=True)

    for root in roots:
        rp = expand_path(root)
        if not rp.is_dir():
            continue
        for child in sorted(rp.iterdir()):
            if not child.is_dir() or child.name in exclude or child.name.startswith("."):
                continue
            key = str(child.resolve())
            if key in refs:
                continue
            if _is_project_dir(child):
                refs[key] = ProjectRef(name=child.name, path=key, layout="", registered=False)

    return list(refs.values())
