from __future__ import annotations

_COLORS = {
    "green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m",
    "unknown": "\033[90m",
}
_RESET = "\033[0m"


def colorize(text: str, health: str, color: bool = True) -> str:
    if not color or health not in _COLORS:
        return text
    return f"{_COLORS[health]}{text}{_RESET}"


def render_table(headers: list[str], rows: list[list[str]], color: bool = True) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    out = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    for row in rows:
        out.append("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))
    return "\n".join(out)
