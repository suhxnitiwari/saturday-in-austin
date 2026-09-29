"""The entry point the website calls. Pyodide runs this exact code in the visitor's browser."""
from __future__ import annotations

import json
import random

from . import rules
from .__main__ import clock
from .city import City
from .planner import BUFFER, plan_outing, reachable, shortlist, walking
from .sass import judge, sign_off
from .spots import AREAS, MOOD_NAMES, NOT_THESE, RULES, Guide, UnknownSpotError, half_hour, load, shelf_note

HOME = "West Campus"
_GUIDE, _DRIVE = Guide(load(), HOME), City()
_ZONE = {s.name: s.zone for s in _GUIDE.spots}  # a walking day renames zones; this remembers the real ones

LABELS = {
    "exercise": "workout", "study": "study spot", "creative": "make something", "paddle": "on the water",
    "murals": "mural", "game": "game day", "cinema": "movie", "order in": "dinner in", "movie": "movie night",
    "read": "reading", "games": "game night",
}
NEIGHBORHOODS = {"Campus": "UT campus", "Domain": "the Domain"}


def _zone(spot) -> str:
    return HOME if rules.kind(spot).reset else _ZONE.get(spot.name, spot.zone)


def _neighborhood(spot) -> str:
    if spot.name in _GUIDE.home_spots or rules.kind(spot).reset:
        return "home"
    return NEIGHBORHOODS.get(_zone(spot), _zone(spot))


def names() -> str:
    """Every place, for the "one place I really want to go" search box."""
    return json.dumps(sorted(s.name for s in _GUIDE.spots if s.name not in _GUIDE.home_spots))


def plan_json(start: str, end: str, hours="all", mood: str = "everything", seed=None,
              walk: bool = False, rainy: bool = False, area: str = "anywhere",
              include: str = "", exclude: str = "") -> str:
    """'9:00', '23:00', 6 -> a JSON day the page can draw.

    start is when you're ready to go, end is when you want to be home. hours is a number
    or "all". include is one place; exclude is a comma list of places and/or NOT_THESE keys.
    """
    to_min = lambda t: int(t.split(":")[0]) * 60 + int(t.split(":")[1] or 0)
    t0, t1 = to_min(start), to_min(end)
    hours = None if hours in (None, "", "all") else float(hours)
    seed = int(seed) if seed not in (None, "") else random.randrange(1000, 10000)
    area = area or "anywhere"
    rng = random.Random(seed)  # for the shelf picks

    problems, must, skip = [], [], set()
    if include.strip():
        try:
            must = [_GUIDE.find(include)]
        except UnknownSpotError as err:
            problems.append(err.args[0])
    tokens = [x.strip() for x in exclude.split(",") if x.strip()]
    not_these = [x for x in tokens if x in NOT_THESE]
    for x in tokens:
        if x not in NOT_THESE:
            try:
                skip.add(_GUIDE.find(x).name)
            except UnknownSpotError as err:
                problems.append(err.args[0])

    window = ((t1 - t0) % (24 * 60) or 24 * 60) if hours is None else hours * 60
    brunch_time = t0 <= rules.BRUNCH_HOURS[1] and (t1 if t1 > t0 else t1 + 24 * 60) >= rules.BRUNCH_HOURS[0] + 90
    zones = AREAS[area][1]

    def attempt(mood: str):
        """Shortlist and plan for one mood; returns (plan, shortlist)."""
        mood_rules = RULES[mood] if area == "anywhere" else RULES[mood].relaxed()
        pool = _GUIDE.pool(mood, must, skip, rainy, area=area, not_these=not_these)
        staples = {"midday meal", "dinner"} | ({"coffee"} if "coffee" in mood_rules.need + mood_rules.want else set())
        fill = [s for s in _GUIDE.spots if s.slot in staples and s.name not in _GUIDE.home_spots and s.name not in skip
                and (zones is None or s.zone in zones)]
        city, pool = walking(pool, HOME, fill) if walk else (_DRIVE, pool)
        keep = [s for s in pool if s.name in {m.name for m in must}]
        far = getattr(city, "reach", city)
        pool = reachable(pool, far, HOME, window, keep)
        spots = shortlist(pool, keep, random.Random(seed), caps=mood_rules.caps, need=mood_rules.need,
                          distance=lambda s: far.minutes(HOME, s.zone) * (3 if walk else 1),  # on foot, near matters more
                          favor=("brunch",) if brunch_time else ())
        plan = plan_outing(spots, city, HOME, t0, t1, hours, keep, mood_rules, walking=walk)
        if walk and not plan.stops:  # on foot, a missing coffee shop shouldn't mean no day at all
            plan = plan_outing(spots, city, HOME, t0, t1, hours, keep, mood_rules.relaxed(), walking=walk)
        return plan, spots

    plan, spots = attempt(mood)
    if not plan.stops and area != "anywhere" and mood not in ("everything", "day-in"):
        plan, spots = attempt("everything")  # nothing for this mood around here: the best of the neighborhood instead
        if plan.stops:
            problems.append(f"{AREAS[area][0]} doesn't really do {MOOD_NAMES[mood].lower()}, so here's the best of it instead.")

    why = rules.explain(plan.stops, spots, _zone, _DRIVE.minutes)
    stops = []
    for i, s in enumerate(plan.stops):
        gap = s.start - (s.arrive - s.drive)  # from the last stop ending to this one starting
        if i and gap - s.drive - BUFFER >= 30:
            stops.append({"type": "free", "time": clock(s.arrive - s.drive), "free": int(gap - s.drive - BUFFER)})
        reset = rules.kind(s.spot).reset
        stops.append({
            "type": "reset" if reset else "stop",
            "time": clock(s.start),
            "name": "Home" if reset else s.spot.name,
            "note": s.spot.note if reset else shelf_note(s.spot, rng),
            "category": s.spot.category,
            "label": "" if reset else LABELS.get(s.spot.category, s.spot.category),
            "where": _neighborhood(s.spot),
            "minutes": s.spot.stay,
            "travel": s.drive,
            "why": why.get(i, ""),
        })
    places = plan.places
    return json.dumps({
        "seed": seed,
        "sass": problems + judge(t0, t1, hours, mood, walk, rainy, AREAS[area][0] if area != "anywhere" else None),
        "stops": stops,
        "leave": clock(plan.leave) if plan.stops else None,
        "home": clock(half_hour(plan.home_by)) if plan.stops else None,
        "back": plan.back,
        "sign_off": sign_off(half_hour(plan.home_by), plan.outside / 60, seed, mood,
                             any(s.spot.slot == "movie" for s in plan.stops)) if plan.stops else None,
        "stats": {
            "stops": len(places),
            "hours_out": round(plan.outside / 60, 1),
            "travel": plan.driving,
            "neighborhoods": len({_neighborhood(s.spot) for s in places} - {"home"}),
        },
        "hours_out": round(plan.outside / 60, 1),
        "driving": plan.driving,
        "walking": walk,
        "mood": MOOD_NAMES[mood],
    })
