from aos.tablefmt import render_table


def test_render_table_aligns_and_includes_values():
    rows = [["village", "green", "main"], ["research", "yellow", "main"]]
    out = render_table(["NAME", "HEALTH", "BRANCH"], rows, color=False)
    lines = out.splitlines()
    assert "NAME" in lines[0] and "HEALTH" in lines[0]
    assert "village" in out and "research" in out
    # column is wide enough to fit the longest value
    assert lines[0].index("HEALTH") >= len("research") + 1
