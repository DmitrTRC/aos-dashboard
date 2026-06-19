from pathlib import Path

import aos


def test_index_shows_session_and_security():
    html = (Path(aos.__file__).parent / "web" / "index.html").read_text(encoding="utf-8")
    assert "session" in html
    assert "has_tracked_secret" in html
    # still offline
    assert "http://" not in html and "https://" not in html
