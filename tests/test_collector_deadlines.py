from datetime import date

from aos.collectors.deadlines import compute_deadlines


def test_days_left_and_overdue():
    items = [
        {"title": "soon", "due": "2026-06-25"},
        {"title": "past", "due": "2026-06-10"},
        {"title": "bad", "due": "not-a-date"},
    ]
    out = compute_deadlines(items, today=date(2026, 6, 19))
    assert out[0].days_left == 6 and out[0].overdue is False
    assert out[1].days_left == -9 and out[1].overdue is True
    assert out[2].days_left is None and out[2].overdue is False
