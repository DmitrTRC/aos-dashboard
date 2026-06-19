from pathlib import Path

from aos.collectors.progress import collect_progress, count_checkboxes


def test_count_checkboxes():
    md = "- [ ] a\n- [x] b\n- [X] c\nnot a box\n  - [ ] nested d\n"
    assert count_checkboxes(md) == (2, 4)


def test_collect_progress_picks_latest_plan(tmp_path: Path):
    plans = tmp_path / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-06-01-old.md").write_text("- [x] done\n- [ ] todo\n")
    (plans / "2026-06-15-new.md").write_text("- [x] a\n- [x] b\n- [ ] c\n- [ ] d\n")
    ps = collect_progress(tmp_path)
    assert ps.plan.endswith("2026-06-15-new.md")
    assert (ps.done, ps.total) == (2, 4)
    assert ps.percent == 50


def test_manual_mode(tmp_path: Path):
    ps = collect_progress(tmp_path, mode="manual", percent=80)
    assert ps.mode == "manual"
    assert ps.percent == 80
