"""Bake a few real Saturdays into web/samples.js so a first-time visitor sees a plan instantly,
before Python has finished loading. Run after changing the spots or the planner:

    python -m web.make_samples

tests/test_saturday.py checks that every baked day still matches what the planner says.
"""
import json
from pathlib import Path

from saturday.web import plan_json

SEEDS = (1204, 2718, 3141, 4242, 5826, 7777)
# exactly what the page asks for with its default settings (see run() in web/app.js)
DEFAULTS = ("09:00", "22:00", "8", "everything")
REST = dict(walk=False, rainy=False, area="anywhere", include="", exclude="", travel="transit",
            budget="student", start_from="ut", hot=False, likes="", nopes="", group=False)


def bake() -> list:
    return [json.loads(plan_json(*DEFAULTS, str(seed), **REST)) for seed in SEEDS]


if __name__ == "__main__":
    out = Path(__file__).with_name("samples.js")
    out.write_text("// Made by web/make_samples.py: real Saturdays for the default settings, shown while Python loads.\n"
                   "window.SAMPLES = " + json.dumps(bake(), ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
