"""Draw the day as a timeline image in my website palette."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLORS = {
    "coffee": "#C8A27A", "brunch": "#F6B8C8", "lunch": "#F6B8C8", "study": "#56634A",
    "creative": "#8F4661", "shopping": "#E8B86B", "exercise": "#9DB08A",
    "dinner": "#8F4661", "late night": "#2A1810",
    "outdoors": "#7FA8B8",
}


def draw(plan, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 2.6), dpi=150)
    fig.patch.set_facecolor("#FBF3EE")
    ax.set_facecolor("#FBF3EE")
    for i, stop in enumerate(plan.stops):
        start_h, length_h = stop.start / 60, stop.spot.stay / 60
        ax.barh(0, length_h, left=start_h, height=0.5, color=COLORS.get(stop.spot.category, "#C9969E"))
        y = 0.42 if i % 2 == 0 else -0.42  # alternate labels above and below so they never collide
        ax.text(start_h + length_h / 2, y, stop.spot.name, ha="center", va="center",
                fontsize=8.5, color="#2A1810")
    first = plan.stops[0].start / 60
    ax.set_xlim(int(first), plan.home_by / 60 + 0.5)
    ax.set_ylim(-0.8, 0.8)
    ax.set_yticks([])
    hours = range(int(first), int(plan.home_by / 60) + 1)
    ax.set_xticks(list(hours))
    ax.set_xticklabels([f"{(h - 1) % 12 + 1}{'am' if h < 12 else 'pm'}" for h in hours], fontsize=8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_title("My Saturday in Austin", loc="left", fontsize=12, color="#2A1810", fontfamily="serif")
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path
