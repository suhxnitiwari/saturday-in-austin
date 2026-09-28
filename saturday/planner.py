"""The planner: pick and order the stops that make the happiest day in the time you have.

The rules:
  - every stop starts inside its window (brunch in the morning, dinner in the evening)
  - one stop per slot (one midday meal, one dinner, one coffee...)
  - the evening only moves forward: dinner, then a night out, then a late-night snack
  - the day fits between leaving home and your end time
  - coffee is always included, plus any spots you insist on

Why not just take the highest-joy spots? Because driving and opening hours interact:
a 10/10 dinner can push out two 8/10 afternoon stops. So the planner searches every
combination, with dynamic programming keeping that search fast.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .city import City

INF = float("inf")
from .spots import WINDOWS, Spot, half_hour


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


def shortlist(spots: list, must: list, rng=None, per_slot: int = 2, limit: int = 15) -> list:
    """Pick a couple of candidates per slot (plus anything required), so the search stays small.

    With an rng, it's a weighted lottery: every spot can win, higher-rated ones win more often,
    so each run is a different Saturday built from the favorites. Without one, it's simply
    the top-rated spots (handy for tests).

    The lottery is the Efraimidis-Spirakis method: give each spot the key random() ** (1 / weight)
    and keep the biggest keys. That's weighted sampling without replacement in one sort.
    """
    must_names = {s.name for s in must}
    unique = {s.name: s for s in spots}.values()
    if rng is None:
        ranked = sorted(unique, key=lambda s: (-s.joy, s.stay, s.name))
    else:
        ranked = sorted(unique, key=lambda s: rng.random() ** (1 / s.joy ** 2), reverse=True)
    keep, counts = {s.name: s for s in must}, {}
    for s in ranked:
        counts[s.slot] = counts.get(s.slot, 0) + 1
        if counts[s.slot] <= per_slot:
            keep.setdefault(s.name, s)
    extras = sorted((s for s in keep.values() if s.name not in must_names), key=lambda s: (s.joy, s.name))
    while len(keep) > limit and extras:
        weakest = extras.pop(0)
        if sum(1 for s in keep.values() if s.slot == weakest.slot) > 1:  # never empty a slot
            del keep[weakest.name]
    return sorted(keep.values(), key=lambda s: s.name)


def plan_day(spots: list, city: City, home: str, leave: int, end: int,
             must: list = (), need=("coffee",)) -> Plan:
    """Bitmask dynamic programming over subsets of spots.

    finish[mask][last] = the earliest time you can be done visiting exactly the spots in
    `mask`, ending at `last`. Being done earlier is never worse (you can always wait), so
    one number per state is enough. Then the answer is the valid subset with the most joy.
    O(2^n * n^2) instead of trying all n! orders.
    """
    n = len(spots)
    if n > 16:
        raise ValueError("shortlist the spots first; 2^n states grows fast")
    slots = sorted({s.slot for s in spots})
    catbit = [1 << slots.index(s.slot) for s in spots]
    # look everything up once, so the hot loop is plain list indexing
    drive = [[city.minutes(a.zone, b.zone) for b in spots] for a in spots]
    back = [city.minutes(s.zone, home) for s in spots]
    opens = [WINDOWS[s.category] for s in spots]
    stay = [s.stay for s in spots]
    phase = [s.phase for s in spots]

    # finish[(mask, last)] = earliest finish; only states that can actually happen are stored.
    # One stop per slot means far fewer reachable states than 2^n * n, so we grow them layer
    # by layer (1 stop, then 2, then 3...) instead of scanning every possible mask.
    finish, prev = {}, {}
    layer = {}
    for i, s in enumerate(spots):
        begin = half_hour(max(leave + city.minutes(home, s.zone), opens[i][0]))
        if begin <= opens[i][1] and begin + stay[i] + back[i] <= end:
            layer[(1 << i, catbit[i]), i] = begin + stay[i]
    while layer:
        finish.update({(m, last): t for ((m, _), last), t in layer.items()})
        nxt_layer = {}
        for ((mask, cats), last), t in layer.items():
            for j in range(n):
                if mask >> j & 1 or cats & catbit[j] or phase[j] < phase[last]:
                    continue
                begin = half_hour(max(t + drive[last][j], opens[j][0]))
                if begin > opens[j][1]:
                    continue
                done = begin + stay[j]
                if done + back[j] > end:
                    continue
                key = ((mask | 1 << j, cats | catbit[j]), j)
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
        if not all(any(mask >> i & 1 and spots[i].category == c for i in range(n)) for c in need):
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


def plan_outing(spots: list, city: City, home: str, wake: int, sleep: int, hours: float,
                must: list = (), step: int = 30) -> Plan:
    """The best `hours` outside, somewhere between waking up and going to bed.

    Tries every departure time, `step` minutes apart, and keeps the happiest plan
    (ties go to less driving, then the earlier start). Times are minutes after midnight;
    a bedtime after midnight (like 1:00 AM) works too.
    """
    if sleep <= wake:
        sleep += 24 * 60
    first, last_home = wake + GET_READY, sleep - WIND_DOWN
    length = min(int(hours * 60), last_home - first)
    if length <= 0:
        return Plan()
    best = Plan()
    for leave in range(first, last_home - length + 1, step):
        plan = plan_day(spots, city, home, leave, leave + length, must)
        if plan.stops and (plan.joy, -plan.driving, -plan.leave) > (best.joy, -best.driving, -best.leave):
            best = plan
    return best


def best_joy_by_search(spots: list, city: City, home: str, leave: int, end: int,
                       need=("coffee",)) -> int:
    """Backtracking over every possible order. Exponential; the tests use it to check plan_day."""
    best = 0

    def explore(zone, clock, used, joy, cats, phase):
        nonlocal best
        if clock + city.minutes(zone, home) <= end and all(c in cats for c in need):
            best = max(best, joy)
        for i, s in enumerate(spots):
            if used >> i & 1 or s.slot in cats or s.phase < phase:
                continue
            start = s.opens_by(clock + city.minutes(zone, s.zone))
            if start is not None and start + s.stay <= end:
                explore(s.zone, start + s.stay, used | 1 << i, joy + s.joy, cats | {s.slot, s.category}, s.phase)

    explore(home, leave, 0, 0, frozenset(), 0)
    return best
