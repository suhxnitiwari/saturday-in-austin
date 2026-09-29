"""The planner: pick and order the stops that make the happiest day in the time you have.

The rules:
  - every stop starts inside its window (brunch in the morning, dinner in the evening)
  - one stop per slot (one midday meal, one dinner...), unless the mood allows more
    (café hopping on a productive day, two adventures on an adventurous one)
  - never the same kind of stop twice in a row: there's a break between two hikes
  - nothing after dinner except a late-night snack
  - the day fits between leaving home and your end time
  - out through lunchtime means a real lunch, and through dinnertime a real dinner
  - what the mood needs is always included (coffee, nails, dinner in), plus spots you insist on

Why not just take the highest-joy spots? Because driving and opening hours interact:
a 10/10 dinner can push out two 8/10 afternoon stops. So the planner searches every
combination, with dynamic programming keeping that search fast.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .city import City

from .spots import SLOTS, WINDOWS, Mood, Spot, half_hour

INF = float("inf")


@dataclass
class Stop:
    spot: Spot
    arrive: float  # minutes after midnight
    start: float
    drive: int


@dataclass
class Plan:
    stops: list = field(default_factory=list)
    leave: float = 0
    home_by: float = 0

    @property
    def outside(self) -> float:
        """Minutes from walking out the door to getting home."""
        return self.home_by - self.leave if self.stops else 0

    @property
    def joy(self) -> int:
        return sum(s.spot.joy for s in self.stops)

    @property
    def driving(self) -> int:
        return sum(s.drive for s in self.stops)


def shortlist(spots: list, must: list, rng=None, per_slot: int = 2, limit: int = 15,
              caps: dict = None, need=()) -> list:
    """Pick a couple of candidates per slot (plus anything required), so the search stays small.

    With an rng, it's a weighted lottery: every spot can win, higher-rated ones win more often,
    so each run is a different Saturday built from the favorites. Without one, it's simply
    the top-rated spots (handy for tests).

    The lottery is the Efraimidis-Spirakis method: give each spot the key random() ** (1 / weight)
    and keep the biggest keys. That's weighted sampling without replacement in one sort.

    With more slots than the limit (a surprise day can be anything), whole slots sit this
    round out, except the ones the mood needs.
    """
    caps = caps or {}
    must_names = {s.name for s in must}
    unique = {s.name: s for s in spots}.values()
    if rng is None:
        ranked = sorted(unique, key=lambda s: (-s.joy, s.stay, s.name))
    else:
        ranked = sorted(unique, key=lambda s: rng.random() ** (1 / s.joy ** 2), reverse=True)
    keep, counts = {s.name: s for s in must}, {}
    for s in ranked:
        counts[s.slot] = counts.get(s.slot, 0) + 1
        if counts[s.slot] < per_slot + caps.get(s.slot, 1):
            keep.setdefault(s.name, s)
    least_lucky = [s for s in reversed(ranked) if s.name in keep and s.name not in must_names]
    for s in least_lucky:  # too many: first drop runner-ups...
        if len(keep) <= limit:
            break
        if sum(1 for k in keep.values() if k.slot == s.slot) > caps.get(s.slot, 1):
            del keep[s.name]
    needed = {SLOTS.get(c, c) for c in need} | {s.slot for s in must} | {"midday meal", "dinner"}
    for s in least_lucky:  # ...then the least lucky slots skip this Saturday
        if len(keep) <= limit:
            break
        if s.name in keep and s.slot not in needed:
            del keep[s.name]
    return sorted(keep.values(), key=lambda s: s.name)


def plan_day(spots: list, city: City, home: str, leave: int, end: int,
             must: list = (), need=("coffee",), caps: dict = None) -> Plan:
    """Bitmask dynamic programming over subsets of spots.

    finish[mask][last] = the earliest time you can be done visiting exactly the spots in
    `mask`, ending at `last`. Being done earlier is never worse (you can always wait), so
    one number per state is enough. Then the answer is the valid subset with the most joy.
    O(2^n * n^2) instead of trying all n! orders.
    """
    n = len(spots)
    if n > 16:
        raise ValueError("shortlist the spots first; 2^n states grows fast")
    caps = caps or {}
    slots = sorted({s.slot for s in spots})
    # how many of each slot are used, packed 2 bits per slot into one int (so up to 3 each)
    shift = [2 * slots.index(s.slot) for s in spots]
    unit = [1 << b for b in shift]
    cap = [min(caps.get(s.slot, 1), 3) for s in spots]
    same = [[a.slot == b.slot for b in spots] for a in spots]
    # look everything up once, so the hot loop is plain list indexing
    drive = [[city.minutes(a.zone, b.zone) for b in spots] for a in spots]
    back = [city.minutes(s.zone, home) for s in spots]
    opens = [WINDOWS[s.category] for s in spots]
    stay = [s.stay for s in spots]
    phase = [s.phase for s in spots]

    # finish[(mask, last)] = earliest finish; only states that can actually happen are stored.
    # Few stops per slot means far fewer reachable states than 2^n * n, so we grow them layer
    # by layer (1 stop, then 2, then 3...) instead of scanning every possible mask.
    finish, prev = {}, {}
    layer = {}
    for i, s in enumerate(spots):
        begin = half_hour(max(leave + city.minutes(home, s.zone), opens[i][0]))
        if begin <= opens[i][1] and begin + stay[i] + back[i] <= end:
            layer[(1 << i, unit[i]), i] = begin + stay[i]
    while layer:
        finish.update({(m, last): t for ((m, _), last), t in layer.items()})
        nxt_layer = {}
        for ((mask, cats), last), t in layer.items():
            for j in range(n):
                if mask >> j & 1 or same[last][j] or phase[j] < phase[last]:
                    continue
                if (cats >> shift[j]) & 3 >= cap[j]:
                    continue
                begin = half_hour(max(t + drive[last][j], opens[j][0]))
                if begin > opens[j][1]:
                    continue
                done = begin + stay[j]
                if done + back[j] > end:
                    continue
                key = ((mask | 1 << j, cats + unit[j]), j)
                if done < nxt_layer.get(key, INF):
                    nxt_layer[key] = done
                    prev[mask | 1 << j, j] = last
        layer = nxt_layer

    must_mask = sum(1 << spots.index(s) for s in must)
    joy = [s.joy for s in spots]
    best = None  # (joy, -home_by, mask, last)
    for (mask, last), t in finish.items():
        if mask & must_mask != must_mask:
            continue
        if not all(any(mask >> i & 1 and c in (spots[i].category, spots[i].slot) for i in range(n)) for c in need):
            continue
        key = (sum(joy[i] for i in range(n) if mask >> i & 1), -(t + back[last]), mask, last)
        if best is None or key[:2] > best[:2]:
            best = key

    if best is None:
        return Plan()
    _, _, mask, last = best
    order = []
    while True:
        order.append(spots[last])
        before = prev.get((mask, last))
        if before is None:
            break
        mask, last = mask ^ (1 << last), before
    return schedule(order[::-1], city, home, leave)


def schedule(order: list, city: City, home: str, leave: int) -> Plan:
    """Turn an ordered list of spots into real times, including any wait for a window to open.

    If the first stop isn't open yet, you simply leave home later instead of waiting outside.
    """
    if order:
        first = order[0].opens_by(leave + city.minutes(home, order[0].zone))
        leave = first - city.minutes(home, order[0].zone)
    plan, clock, zone = Plan(leave=leave), leave, home
    for s in order:
        drive = city.minutes(zone, s.zone)
        start = s.opens_by(clock + drive)
        plan.stops.append(Stop(s, clock + drive, start, drive))
        clock, zone = start + s.stay, s.zone
    plan.home_by = clock + city.minutes(zone, home)
    return plan


GET_READY = 45   # minutes between waking up and walking out the door
WIND_DOWN = 30   # minutes home before bed


MEALTIMES = {"midday meal": (11 * 60 + 30, 14 * 60 + 30), "dinner": (17 * 60 + 30, 21 * 60)}


WALK_RADIUS = 2  # miles from home on a no-car day


def walking(spots: list, home: str, coffee: list = ()) -> tuple:
    """A no-car day: every spot becomes its own place on the map, and no walk is over a mile.
    Only spots within WALK_RADIUS of home. If none of them is coffee, the closest of `coffee` joins.
    Returns the walking city and the spots, renamed so each spot's "zone" is itself.
    city.reach has no mile limit, for asking what could fit at all."""
    from dataclasses import replace
    from .city import WalkCity
    fallback = {s.name: s.zone for s in spots}
    city = WalkCity(fallback)
    city.reach = WalkCity(fallback, max_miles=None)
    # within two miles of home, and reachable from home in hops of a mile or less (breadth-first search)
    close = [s for s in spots if city.reach.miles(home, s.name) <= WALK_RADIUS]
    seen, frontier = set(), [home]
    while frontier:
        here = frontier.pop()
        for s in close:
            if s.name not in seen and city.minutes(here, s.name) < WalkCity.TOO_FAR:
                seen.add(s.name)
                frontier.append(s.name)
    kept = [s for s in close if s.name in seen]
    if coffee and not any(s.category == "coffee" for s in kept):
        city.fallback.update({c.name: c.zone for c in coffee})
        nearest = min(coffee, key=lambda c: city.reach.miles(home, c.name))
        if city.minutes(home, nearest.name) < WalkCity.TOO_FAR:
            kept.append(nearest)
    return city, [replace(s, zone=s.name) for s in kept]


def reachable(spots: list, city: City, home: str, minutes: float, keep=()) -> list:
    """Only spots you could get to, enjoy and get home from in the time you have
    (so a one-hour outing picks from quick coffees, not a two-hour pottery class)."""
    return [s for s in spots if s in keep or s.stay + 2 * city.minutes(home, s.zone) <= minutes]


def meals(leave: int, end: int) -> tuple:
    """Snacks don't count as meals: out for 90+ minutes of lunchtime means a real lunch,
    and the same for dinner."""
    return tuple(meal for meal, (a, b) in MEALTIMES.items() if min(end, b) - max(leave, a) >= 90)


def plan_outing(spots: list, city: City, home: str, wake: int, sleep: int, hours: float,
                must: list = (), mood: Mood = Mood(), step: int = 30) -> Plan:
    """The best `hours` outside, somewhere between waking up and going to bed.

    Tries every departure time, `step` minutes apart, and keeps the happiest plan
    (ties go to less driving, then the earlier start, or the later one for a slow day).
    Times are minutes after midnight; a bedtime after midnight (like 1:00 AM) works too.
    """
    if sleep <= wake:
        sleep += 24 * 60
    first, last_home = wake + GET_READY, sleep - WIND_DOWN
    length = min(int(hours * 60), last_home - first)
    if length <= 0:
        return Plan()
    best, rank = Plan(), None
    start_pref = 1 if mood.late else -1
    # the whole day if it fits; otherwise skip the meals, then what the mood is built around
    for with_meals, with_wants in ((True, True), (False, True), (False, False)):
        # leave right away, or on any :00 or :30 after (stops start on the half hour, so those waste nothing)
        for leave in [first] + list(range(half_hour(first + 1), last_home - length + 1, step)):
            need = mood.need + (mood.want if with_wants else ()) + (meals(leave, leave + length) if with_meals else ())
            plan = plan_day(spots, city, home, leave, leave + length, must, need, mood.caps)
            if not plan.stops:
                continue
            key = (plan.joy, -plan.driving, start_pref * plan.leave)
            if rank is None or key > rank:
                best, rank = plan, key
        if best.stops:
            return best
    return best


def best_joy_by_search(spots: list, city: City, home: str, leave: int, end: int,
                       need=("coffee",), caps: dict = None) -> int:
    """Backtracking over every possible order. Exponential; the tests use it to check plan_day."""
    caps = caps or {}
    best = 0

    def explore(zone, clock, used, joy, counts, cats, phase, last):
        nonlocal best
        if clock + city.minutes(zone, home) <= end and all(c in cats for c in need):
            best = max(best, joy)
        for i, s in enumerate(spots):
            if used >> i & 1 or s.slot == last or s.phase < phase:
                continue
            if counts.get(s.slot, 0) >= min(caps.get(s.slot, 1), 3):
                continue
            start = s.opens_by(clock + city.minutes(zone, s.zone))
            if start is not None and start + s.stay + city.minutes(s.zone, home) <= end:
                explore(s.zone, start + s.stay, used | 1 << i, joy + s.joy,
                        {**counts, s.slot: counts.get(s.slot, 0) + 1}, cats | {s.category, s.slot}, s.phase, s.slot)

    explore(home, leave, 0, 0, {}, frozenset(), 0, None)
    return best
