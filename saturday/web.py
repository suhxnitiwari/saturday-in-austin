"""The entry point the website calls. Pyodide runs this exact code in the visitor's browser."""
from __future__ import annotations

import json
import random

from . import rules
from .__main__ import clock
from .city import City
from .planner import BUFFER, plan_outing, reachable, shortlist, transit, walking
from .sass import judge, sign_off
from .spots import AREAS, DAY_TRIPS, MOOD_NAMES, NOT_THESE, RULES, STARTS, Guide, UnknownSpotError, half_hour, load, shelf_note

_SPOTS, _DRIVE = load(), City()
_GUIDES = {}  # one Guide per home: day-in spots live wherever home is


def _guide(home: str) -> Guide:
    if home not in _GUIDES:
        _GUIDES[home] = Guide(_SPOTS, home)
    return _GUIDES[home]


LABELS = {
    "exercise": "workout", "study": "study spot", "creative": "make something", "paddle": "on the water",
    "murals": "mural", "game": "game day", "cinema": "movie", "order in": "dinner in", "movie": "movie night",
    "read": "reading", "games": "game night", "nightlife": "21+ night out", "comedy": "comedy & shows",
}
NEIGHBORHOODS = {"Campus / UT Corridor": "UT campus", "The Domain / Rock Rose": "the Domain"}


def names() -> str:
    """Every place, for the "one place I really want to go" search box."""
    guide = _guide("West Campus")
    return json.dumps(sorted(s.name for s in guide.spots if s.name not in guide.home_spots))


def stats() -> str:
    """This planner, by the numbers: counted from the data, so they grow as the list does."""
    from .spots import MOODS
    guide = _guide("West Campus")
    places = [s for s in guide.spots if s.name not in guide.home_spots]
    return json.dumps({"places": len(places), "neighborhoods": len({s.zone for s in places} - DAY_TRIPS), "moods": len(MOODS)})


def plan_json(start: str, end: str, hours="all", mood: str = "everything", seed=None,
              walk: bool = False, rainy: bool = False, area: str = "anywhere",
              include: str = "", exclude: str = "", travel: str = "", budget: str = "normal",
              start_from: str = "ut") -> str:
    """'9:00', '23:00', 6 -> a JSON day the page can draw.

    start is when you're ready to go, end is when you want to be home. hours is a number
    or "all". include is one place; exclude is a comma list of places and/or NOT_THESE keys.
    travel is car, uber, transit or walk (walk=True still means walk); budget is student,
    normal or splurge; start_from is where home is (a key of STARTS).
    """
    to_min = lambda t: int(t.split(":")[0]) * 60 + int(t.split(":")[1] or 0)
    t0, t1 = to_min(start), to_min(end)
    hours = None if hours in (None, "", "all") else float(hours)
    seed = int(seed) if seed not in (None, "") else random.randrange(1000, 10000)
    area = area or "anywhere"
    mode = travel or ("walk" if walk else "car")
    ways = rules.Ways(mode, budget or "normal")
    home = STARTS.get(start_from or "ut", "West Campus")
    guide = _guide(home)
    zone_of = {s.name: s.zone for s in guide.spots}  # walking and bus days rename zones; this keeps the real ones
    rng = random.Random(seed)  # for the shelf picks

    problems, must, skip = [], [], set()
    if include.strip():
        try:
            must = [guide.find(include)]
        except UnknownSpotError as err:
            problems.append(err.args[0])
    tokens = [x.strip() for x in exclude.split(",") if x.strip()]
    not_these = [x for x in tokens if x in NOT_THESE]
    for x in tokens:
        if x not in NOT_THESE:
            try:
                skip.add(guide.find(x).name)
            except UnknownSpotError as err:
                problems.append(err.args[0])

    window = ((t1 - t0) % (24 * 60) or 24 * 60) if hours is None else hours * 60
    brunch_time = t0 <= rules.BRUNCH_HOURS[1] and (t1 if t1 > t0 else t1 + 24 * 60) >= rules.BRUNCH_HOURS[0] + 90
    zones = AREAS[area][1]

    def attempt(mood: str):
        """Shortlist and plan for one mood; returns (plan, shortlist, city)."""
        mood_rules = RULES[mood] if area == "anywhere" else RULES[mood].relaxed()
        pool = guide.pool(mood, must, skip, rainy, area=area, not_these=not_these)
        staples = {"midday meal", "dinner"} | ({"coffee"} if "coffee" in mood_rules.need + mood_rules.want else set())
        fill = [s for s in guide.spots if s.slot in staples and s.name not in guide.home_spots and s.name not in skip
                and (zones is None or s.zone in zones)]
        if mode == "transit":
            city, pool = transit(pool, home, fill, random.Random(seed), must)
        elif mode == "walk":
            city, pool = walking(pool, home, fill)
        else:
            city = _DRIVE
        keep = [s for s in pool if s.name in {m.name for m in must}]
        far = getattr(city, "reach", city)
        pool = reachable(pool, far, home, window, keep)
        near_matters = {"walk": 3, "transit": 2, "uber": 2}.get(mode, 1)  # without a car, near matters more
        spots = shortlist(pool, keep, random.Random(seed), caps=mood_rules.caps, need=mood_rules.need,
                          distance=lambda s: min(far.minutes(home, s.zone), 300) * near_matters,
                          favor=(("brunch",) if brunch_time else ()) + tuple(mood_rules.want))  # what the mood wants always gets a ticket
        plan = plan_outing(spots, city, home, t0, t1, hours, keep, mood_rules, ways=ways)
        if mode in ("walk", "transit") and not plan.stops:  # a missing coffee shop shouldn't mean no day at all
            plan = plan_outing(spots, city, home, t0, t1, hours, keep, mood_rules.relaxed(), ways=ways)
        return plan, spots, city

    plan, spots, city = attempt(mood)
    if not plan.stops and area != "anywhere" and mood not in ("everything", "day-in"):
        plan, spots, city = attempt("everything")  # nothing for this mood around here: the best of the neighborhood
        if plan.stops:
            problems.append(f"{AREAS[area][0]} doesn't really do {MOOD_NAMES[mood].lower()}, so here's the best of it instead.")

    def real_zone(spot) -> str:
        return home if rules.kind(spot).reset else zone_of.get(spot.name, spot.zone)

    def neighborhood(spot) -> str:
        if spot.name in guide.home_spots or rules.kind(spot).reset:
            return "home"
        return NEIGHBORHOODS.get(real_zone(spot), real_zone(spot))

    def leg(a: str, b: str, minutes: int) -> dict:
        """How you get from place a to place b (in the city's own terms)."""
        if not minutes:
            return {"via": "walk", "fare": 0}
        if mode == "uber":
            return {"via": "uber", "fare": round(rules.uber_fare(minutes))}
        if mode == "transit":
            return {"via": city.how(a, b), "fare": 0}
        return {"via": "walk" if mode == "walk" else "drive", "fare": 0}

    why = rules.explain(plan.stops, spots, real_zone, _DRIVE.minutes)
    stops, here = [], home
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
            "where": neighborhood(s.spot),
            "minutes": s.spot.stay,
            "travel": s.drive,
            "price": s.spot.price,
            "why": why.get(i, ""),
            **leg(here, s.spot.zone, s.drive),
        })
        here = s.spot.zone
    places = plan.places
    back_leg = leg(here, home, plan.back) if plan.stops else {"via": "", "fare": 0}
    return json.dumps({
        "seed": seed,
        "sass": problems + judge(t0, t1, hours, mood, mode == "walk", rainy,
                                 AREAS[area][0] if area != "anywhere" else None, mode, budget),
        "stops": stops,
        "leave": clock(plan.leave) if plan.stops else None,
        "home": clock(half_hour(plan.home_by)) if plan.stops else None,
        "back": plan.back,
        "back_via": back_leg["via"],
        "back_fare": back_leg["fare"],
        "sign_off": sign_off(half_hour(plan.home_by), plan.outside / 60, seed, mood,
                             any(s.spot.slot == "movie" for s in plan.stops)) if plan.stops else None,
        "stats": {
            "stops": len(places),
            "hours_out": round(plan.outside / 60, 1),
            "travel": plan.driving,
            "neighborhoods": len({neighborhood(s.spot) for s in places} - {"home"}),
            "spend": round(plan.dollars),
            "fares": round(plan.fares),
        },
        "hours_out": round(plan.outside / 60, 1),
        "driving": plan.driving,
        "walking": mode == "walk",
        "mode": mode,
        "mood": MOOD_NAMES[mood],
    })
