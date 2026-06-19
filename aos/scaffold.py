from __future__ import annotations

from pathlib import Path

import yaml

_STUB = {
    "name": None,
    "title": None,
    "type": "unknown",
    "stage": "idea",
    "priority": "medium",
    "tags": [],
    "deadlines": [],
    "progress": {"mode": "auto", "percent": None, "plan": None},
    "graphify": {"required": False, "disabled": False},
    "commands": {},
    "session": {"launch": None},
    "dashboard": {"show_on_wall": True},
}


def _ensure_gitignore(path: Path) -> None:
    gi = path / ".gitignore"
    line = ".aos/state/"
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if line not in existing.splitlines():
        with gi.open("a", encoding="utf-8") as fh:
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            fh.write(line + "\n")


def init_project(path: Path, name: str) -> bool:
    path = Path(path)
    aos_dir = path / ".aos"
    (aos_dir / "state").mkdir(parents=True, exist_ok=True)
    _ensure_gitignore(path)

    yaml_file = aos_dir / "project.yaml"
    if yaml_file.exists():
        return False
    stub = dict(_STUB)
    stub["name"] = name
    stub["title"] = name
    yaml_file.write_text(yaml.safe_dump(stub, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return True
