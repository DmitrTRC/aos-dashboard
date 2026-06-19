from __future__ import annotations

from aos.model import Health, Project


def evaluate(p: Project, cfg: dict) -> tuple[Health, list[str]]:
    if not p.git.is_repo and not p.has_yaml:
        return Health.UNKNOWN, ["не git-репозиторий, нет .aos/project.yaml"]

    red: list[str] = []
    yellow: list[str] = []

    if p.tests.status == "fail":
        red.append("тесты упали")
    if any(d.overdue for d in p.deadlines):
        red.append("дедлайн просрочен")
    if p.graphify.status == "missing" and p.graphify_required:
        red.append("Graphify отсутствует (required)")

    if p.git.is_repo and (p.git.staged + p.git.unstaged + p.git.untracked) > 0:
        yellow.append("незакоммиченные изменения")
    if p.graphify.status == "stale":
        yellow.append("Graphify устарел")

    warn = cfg["health"]["deadline_warn_days"]
    for d in p.deadlines:
        if d.days_left is not None and 0 <= d.days_left <= warn:
            yellow.append(f"дедлайн через {d.days_left} дн")

    if red:
        return Health.RED, red + yellow
    if yellow:
        return Health.YELLOW, yellow
    return Health.GREEN, ["всё чисто"]
