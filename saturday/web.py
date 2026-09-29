"""The entry point the website calls. Pyodide runs this exact code in the visitor's browser."""
from __future__ import annotations

import json
import random

from .__main__ import clock
from .city import WALK_PACE, City
from .planner import plan_outing, shortlist
from .sass import judge, sign_off
from .spots import RULES, Guide, half_hour, load, shelf_note

HOME = "West Campus"
MAX_WALK = 45  # minutes: with no car, only spots within a walk of home
_GUIDE, _DRIVE, _WALK = Guide(load(), HOME), City(), City(pace=WALK_PACE)


def plan_json(wake: str, sleep: str, hours: float, mood: str = "everything", seed=None,
              walk: bool = False, rainy: bool = False) -> str:
    """'8:00', '23:00', 6 -> a JSON plan the page can draw."""
    to_min = lambda t: int(t.split(":")[0]) * 60 + int(t.split(":")[1] or 0)
    seed = int(seed) if seed not in (None, "") else random.randrange(1000, 10000)
    rules, city = RULES[mood], _WALK if walk else _DRIVE
    near = (lambda s: city.minutes(HOME, s.zone) <= MAX_WALK) if walk else None
    rng = random.Random(seed)
    spots = shortlist(_GUIDE.pool(mood, rainy=rainy, near=near), [], rng, caps=rules.caps, need=rules.need)
    plan = plan_outing(spots, city, HOME, to_min(wake), to_min(sleep), float(hours), mood=rules)
    stops = []
    for s in plan.stops:
        free = s.start - (s.arrive - s.drive)  # from the last stop ending to this one starting
        if free >= 30 + s.drive:
            stops.append({"time": clock(s.arrive - s.drive), "free": int(free)})
        stops.append({"time": clock(s.start), "name": s.spot.name, "note": shelf_note(s.spot, rng),
                      "category": s.spot.category, "minutes": s.spot.stay})
    return json.dumps({
        "seed": seed,
        "sass": judge(to_min(wake), to_min(sleep), float(hours), mood, walk, rainy),
        "stops": stops,
        "leave": clock(plan.leave) if plan.stops else None,
        "home": clock(half_hour(plan.home_by)) if plan.stops else None,
        "sign_off": sign_off(half_hour(plan.home_by), plan.outside / 60, seed, mood,
                             any(s.spot.slot == "movie" for s in plan.stops)) if plan.stops else None,
        "hours_out": round(plan.outside / 60, 1),
        "driving": plan.driving,
        "walking": walk,
    })
