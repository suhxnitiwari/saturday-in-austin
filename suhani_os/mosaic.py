"""Mosaic Workshop, in code: 2D lists, nested loops, recursion and graphics.

A mosaic is just a grid of tiles, which is exactly what a 2D list is.
We draw a four-point sparkle (✦) with nested loops, fill the background with a
recursive flood fill (the paint-bucket tool), and render it with matplotlib.
"""
from __future__ import annotations

import sys
from pathlib import Path

# her website palette
PALETTE = {
    "cream": "#FBF3EE",
    "blush": "#F2CFD7",
    "baby pink": "#F6B8C8",
    "mulberry": "#8F4661",
    "olive": "#56634A",
    "gold": "#E8B86B",
}

EMPTY = "."


def blank(rows: int, cols: int, fill: str = EMPTY) -> list:
    """A rows x cols grid. List comprehension, so each row is its OWN list.

    ([[fill] * cols] * rows would repeat one row object: paint a tile, paint a whole column.)
    """
    return [[fill for _ in range(cols)] for _ in range(rows)]


def in_sparkle(r: int, c: int, rows: int, cols: int) -> bool:
    """Inside a four-point star? Uses the curve |x|^0.55 + |y|^0.55 <= 1 (concave sides, sharp tips)."""
    cy, cx = (rows - 1) / 2, (cols - 1) / 2
    x, y = abs(c - cx) / (cx - 1), abs(r - cy) / (cy - 1)
    return x ** 0.55 + y ** 0.55 <= 1


def draw_outline(grid: list, color: str) -> list:
    """Nested loops: a tile is on the outline if it's inside the star but touches the outside,
    including diagonally, so the outline has no gaps for the paint bucket to leak through."""
    rows, cols = len(grid), len(grid[0])
    for r in range(rows):
        for c in range(cols):
            if not in_sparkle(r, c, rows, cols):
                continue
            if any(not in_sparkle(r + dr, c + dc, rows, cols)
                   for dr in (-1, 0, 1) for dc in (-1, 0, 1)):
                grid[r][c] = color
    return grid


def flood_fill(grid: list, r: int, c: int, new: str, old=None) -> int:
    """Recursive paint bucket: recolor the connected region around (r, c). Returns tiles changed.

    Base cases: off the grid, or a tile that isn't the color we're replacing.
    Recursive case: paint this tile, then spread up, down, left and right.
    """
    if old is None:
        old = grid[r][c]
        if old == new:
            return 0
    if not (0 <= r < len(grid) and 0 <= c < len(grid[0])) or grid[r][c] != old:
        return 0
    grid[r][c] = new
    return 1 + sum(flood_fill(grid, r + dr, c + dc, new, old)
                   for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def scatter(grid: list, color: str, every: int = 7) -> list:
    """Sprinkle tiny accent tiles on the background in a diagonal pattern (nested loops + modulo)."""
    for r, row in enumerate(grid):
        for c, tile in enumerate(row):
            if tile == "cream" and (r * 3 + c) % every == 0 and r % 4 == 0:
                grid[r][c] = color
    return grid


def make_mosaic(size: int = 31) -> list:
    sys.setrecursionlimit(max(sys.getrecursionlimit(), size * size * 4))
    grid = blank(size, size)
    draw_outline(grid, "mulberry")
    flood_fill(grid, size // 2, size // 2, "baby pink")  # paint bucket inside the outline
    flood_fill(grid, 0, 0, "cream")                     # and again for the background
    scatter(grid, "gold")
    return grid


def as_text(grid: list) -> str:
    """Terminal preview: one character per tile."""
    symbols = {"cream": " ", "baby pink": "✦", "mulberry": "*", "gold": "·"}
    return "\n".join("".join(symbols.get(t, "?") for t in row) for row in grid)


def render(grid: list, path: Path) -> Path:
    """Graphics: draw every tile as a small rounded square with a grout line, and save a PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    rows, cols = len(grid), len(grid[0])
    fig, ax = plt.subplots(figsize=(6, 6), dpi=150)
    fig.patch.set_facecolor(PALETTE["blush"])
    for r in range(rows):
        for c in range(cols):
            ax.add_patch(FancyBboxPatch((c + 0.08, rows - r - 1 + 0.08), 0.84, 0.84,
                                        boxstyle="round,pad=0,rounding_size=0.18",
                                        facecolor=PALETTE[grid[r][c]], edgecolor="none"))
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)
    ax.set_aspect("equal")
    ax.axis("off")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path
