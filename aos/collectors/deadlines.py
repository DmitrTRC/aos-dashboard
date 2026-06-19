from __future__ import annotations

from datetime import date

from aos.model import Deadline


def compute_deadlines(items: list[dict] | None, today: date | None = None) -> list[Deadline]:
    today = today or date.today()
    out: list[Deadline] = []
    for it in items or []:
        due = str(it.get("due", ""))
        d = Deadline(title=str(it.get("title", "")), due=due)
        try:
            dd = date.fromisoformat(due)
            d.days_left = (dd - today).days
            d.overdue = d.days_left < 0
        except ValueError:
            pass
        out.append(d)
    return out
