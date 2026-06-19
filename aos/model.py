from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


class Health(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNKNOWN = "unknown"


@dataclass
class GitState:
    is_repo: bool = False
    branch: Optional[str] = None
    ahead: int = 0
    behind: int = 0
    staged: int = 0
    unstaged: int = 0
    untracked: int = 0
    insertions: int = 0
    deletions: int = 0
    last_commit: Optional[str] = None
    head: Optional[str] = None
    error: Optional[str] = None

    @property
    def dirty(self) -> bool:
        return (self.staged + self.unstaged + self.untracked) > 0


@dataclass
class GraphifyState:
    status: str = "missing"  # fresh|stale|missing|disabled|error
    hook_installed: bool = False
    built_commit: Optional[str] = None
    last_update: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ProgressState:
    mode: str = "auto"
    percent: Optional[int] = None
    done: int = 0
    total: int = 0
    plan: Optional[str] = None


@dataclass
class Deadline:
    title: str
    due: str
    days_left: Optional[int] = None
    overdue: bool = False


@dataclass
class TestState:
    status: str = "unknown"  # pass|fail|unknown
    last_run: Optional[str] = None
    duration_sec: Optional[float] = None


@dataclass
class Project:
    name: str
    title: str
    path: str
    layout: str = ""
    type: str = "unknown"
    stage: str = "idea"
    priority: str = "medium"
    registered: bool = True
    has_yaml: bool = False
    graphify_required: bool = False
    git: GitState = field(default_factory=GitState)
    graphify: GraphifyState = field(default_factory=GraphifyState)
    progress: ProgressState = field(default_factory=ProgressState)
    deadlines: list[Deadline] = field(default_factory=list)
    tests: TestState = field(default_factory=TestState)
    health: Health = Health.UNKNOWN
    health_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["health"] = self.health.value
        d["git"]["dirty"] = self.git.dirty
        return d
