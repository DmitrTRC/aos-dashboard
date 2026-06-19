from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml

DEFAULT_CONFIG: dict = {
    "roots": ["~/Projects"],
    "port": 7777,
    "refresh_interval_sec": 10,
    "open_browser": True,
    "auto_scaffold": False,
    "tools": {
        "git": "/usr/bin/git",
        "zellij": "/opt/homebrew/bin/zellij",
        "kitty": "/Applications/kitty.app/Contents/MacOS/kitty",
        "graphify": "graphify",
        "ps": "/bin/ps",
    },
    "session": {
        "launch_cmd_template": "{kitty} -1 -e /bin/zsh -ic 'project {name}'",
    },
    "exec_allowlist": [
        "git", "pnpm", "npm", "yarn", "pytest", "python", "python3",
        "node", "make", "just", "bats", "graphify", "cargo", "go",
    ],
    "exclude_dirs": [
        "node_modules", ".git", "dist", "build", "target",
        ".venv", "venv", "__pycache__",
    ],
    "timeouts_sec": {"collector": 5, "tests": 120, "graphify": 300},
    "health": {"deadline_warn_days": 7, "inactive_warn_days": 14},
}


def config_path() -> Path:
    return Path(os.path.expanduser("~/.config/aos/config.yaml"))


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: Path | None = None) -> dict:
    path = path or config_path()
    if path.exists():
        user = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        user = {}
    return _deep_merge(DEFAULT_CONFIG, user)


def expand(p: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(p)))
