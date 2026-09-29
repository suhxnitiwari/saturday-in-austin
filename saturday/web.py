"""The entry point the website calls. Pyodide runs this exact code in the visitor's browser."""
from __future__ import annotations

import json
import random

from .__main__ import clock
from .city import City
from .planner import plan_outing, shortlist
from .sass import judge, sign_off
from .spots import RULES, Guide, half_hour, load

_GUIDE, _CITY = Guide(load()), City()


def plan_json(wake: str, sleep: str, hours: float, mood: str = "everything", seed=None) -> str:
    """'8:00', '23:00', 6 -> a JSON plan the page can draw."""
    to_min = lambda t: int(t.split(":")[0]) * 60 + int(t.split(":")[1] or 0)
    seed = int(seed) if seed not in (None, "") else random.randrange(1000, 10000)
    rules = RULES[mood]
    spots = shortlist(_GUIDE.pool(mood), [], random.Random(seed), caps=rules.caps, need=rules.need)
    plan = plan_outing(spots, _CITY, "West Campus", to_min(wake), to_min(sleep), float(hours), mood=rules)
    stops = []
    for s in plan.stops:
        free = s.start - (s.arrive - s.drive)  # from the last stop ending to this one starting
        if free >= 30 + s.drive:
            stops.append({"time": clock(s.arrive - s.drive), "free": int(free)})
        stops.append({"time": clock(s.start), "name": s.spot.name, "note": s.spot.note,
                      "category": s.spot.category, "minutes": s.spot.stay})
    return json.dumps({
        "seed": seed,
        "sass": judge(to_min(wake), to_min(sleep), float(hours), mood),
        "stops": stops,
        "leave": clock(plan.leave) if plan.stops else None,
        "home": clock(half_hour(plan.home_by)) if plan.stops else None,
        "sign_off": sign_off(half_hour(plan.home_by), plan.outside / 60, seed, mood) if plan.stops else None,
        "hours_out": round(plan.outside / 60, 1),
        "driving": plan.driving,
    })
