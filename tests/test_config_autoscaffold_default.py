from aos.config import load_config


def test_auto_scaffold_is_off_by_default(tmp_path):
    cfg = load_config(tmp_path / "missing.yaml")
    assert cfg["auto_scaffold"] is False


def test_auto_scaffold_can_be_enabled(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("auto_scaffold: true\n")
    assert load_config(p)["auto_scaffold"] is True
