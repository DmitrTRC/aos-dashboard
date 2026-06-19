from pathlib import Path

from aos.registry import ProjectRef, discover, expand_path, parse_projects_conf


def test_parse_skips_comments_and_trims():
    text = "# comment\n\nvillage | $HOME/Projects/village-emrg | dev\nresearch|~/Projects/research|research\n"
    entries = parse_projects_conf(text)
    assert entries[0] == ("village", "$HOME/Projects/village-emrg", "dev")
    assert entries[1] == ("research", "~/Projects/research", "research")


def test_discover_reconciles_registry_name_vs_dirname(tmp_path: Path, monkeypatch):
    root = tmp_path / "Projects"
    (root / "village-emrg" / ".git").mkdir(parents=True)
    (root / "loose" / ".git").mkdir(parents=True)  # not in registry
    conf = tmp_path / "projects.conf"
    conf.write_text(f"village | {root}/village-emrg | dev\n")

    refs = discover(roots=[str(root)], conf_path=conf, exclude_dirs=["node_modules"])
    by_path = {Path(r.path).name: r for r in refs}
    assert by_path["village-emrg"].name == "village"      # registry name wins
    assert by_path["village-emrg"].registered is True
    assert by_path["loose"].name == "loose"               # falls back to dirname
    assert by_path["loose"].registered is False
