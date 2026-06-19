from pathlib import Path

import aos


def test_index_html_is_offline_and_has_hooks():
    html = (Path(aos.__file__).parent / "web" / "index.html").read_text(encoding="utf-8")
    # no external network references (offline-only)
    assert "http://" not in html and "https://" not in html
    assert "cdn" not in html.lower()
    # template hooks the server fills in
    assert "__AOS_TOKEN__" in html
    assert "__AOS_REFRESH__" in html
    # talks to the read API
    assert "/api/projects" in html
