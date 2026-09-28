"""The entry point the website calls. Pyodide runs this exact code in the visitor's browser."""
from __future__ import annotations

import json
import random

from .__main__ import clock
from .city import City
from .planner import plan_outing, shortlist
from .spots import Guide, load

_GUIDE, _CITY = Guide(load()), City()


def plan_json(wake: str, sleep: str, hours: float, mood: str = "everything", seed=None) -> str:
    """'8:00', '23:00', 6 -> a JSON plan the page can draw."""
    to_min = lambda t: int(t.split(":")[0]) * 60 + int(t.split(":")[1] or 0)
    seed = int(seed) if seed not in (None, "") else random.randrange(1000, 10000)
    spots = shortlist(_GUIDE.for_mood(mood) + [_GUIDE.find("Medici")], [], random.Random(seed))
    plan = plan_outing(spots, _CITY, "West Campus", to_min(wake), to_min(sleep), float(hours))
    stops = []
    for s in plan.stops:
        free = s.start - s.arrive
        if free >= 30:
            stops.append({"time": clock(s.arrive - s.drive), "free": int(free)})
        stops.append({"time": clock(s.start), "name": s.spot.name, "note": s.spot.note,
                      "category": s.spot.category, "minutes": s.spot.stay})
    return json.dumps({
        "seed": seed,
        "stops": stops,
        "leave": clock(plan.leave) if plan.stops else None,
        "home": clock(plan.home_by) if plan.stops else None,
        "hours_out": round(plan.outside / 60, 1),
        "driving": plan.driving,
    })
