from __future__ import annotations

import subprocess
from pathlib import Path

from aos.model import SecurityFinding, SecurityFindings

_SECRET_EXT = {".pem", ".key"}
_EXAMPLE_SUFFIXES = (".example", ".sample", ".template", ".dist", ".tmpl")


def _is_example(name: str) -> bool:
    return any(name.endswith(suf) for suf in _EXAMPLE_SUFFIXES)


def _is_secret(name: str) -> bool:
    if _is_example(name):
        return False
    return name == "env.bak" or name.startswith(".env") or Path(name).suffix in _SECRET_EXT


def _kind(name: str) -> str:
    if "env" in name:
        return "env"
    if Path(name).suffix in _SECRET_EXT:
        return "key"
    return "secret"


def collect_security(path, git_bin: str = "/usr/bin/git", timeout: int = 5, runner=subprocess.run) -> SecurityFindings:
    """Shallow (top-level) scan for secret-like files + git-tracked status. Read-only."""
    path = Path(path)
    candidates = [f for f in path.iterdir() if f.is_file() and _is_secret(f.name)] if path.is_dir() else []
    tracked: set[str] = set()
    if candidates and (path / ".git").exists():
        rels = [f.name for f in candidates]
        try:
            cp = runner([git_bin, "-C", str(path), "ls-files", "--", *rels],
                        capture_output=True, text=True, timeout=timeout)
            tracked = {ln.strip() for ln in (cp.stdout or "").splitlines() if ln.strip()}
        except Exception:
            tracked = set()
    findings = [
        SecurityFinding(path=f.name, kind=_kind(f.name), tracked=f.name in tracked)
        for f in sorted(candidates)
    ]
    return SecurityFindings(findings=findings, has_security_md=(path / "SECURITY.md").exists())
