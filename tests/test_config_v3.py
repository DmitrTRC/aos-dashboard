from aos.config import DEFAULT_CONFIG, load_config


def test_new_defaults_present(tmp_path):
    cfg = load_config(tmp_path / "missing.yaml")
    assert cfg["tools"]["ps"] == "/bin/ps"
    assert "python3" in cfg["exec_allowlist"]
    assert cfg["auto_scaffold"] is True
