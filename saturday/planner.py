"""The planner: pick and order the stops that make the happiest day in the time you have.

The rules:
  - every stop starts inside its window (brunch in the morning, dinner in the evening)
  - one stop per slot (one midday meal, one dinner, one coffee...)
  - nothing after dinner except a late-night snack
  - the day fits between leaving home and your end time
  - coffee is always included, plus any spots you insist on

Why not just take the highest-joy spots? Because driving and opening hours interact:
a 10/10 dinner can push out two 8/10 afternoon stops. So the planner searches every
combination, with dynamic programming keeping that search fast.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .city import City
from .spots import Spot


@dataclass
class Stop:
    spot: Spot
    arrive: float  # minutes after midnight
    start: float
    drive: int


@dataclass
class Plan:
    stops: list = field(default_factory=list)
    home_by: float = 0

    @property
    def joy(self) -> int:
        return sum(s.spot.joy for s in self.stops)

    @property
    def driving(self) -> int:
        return sum(s.drive for s in self.stops)


def shortlist(spots: list, must: list, per_slot: int = 2, limit: int = 15) -> list:
    """Keep the best couple of spots per slot (plus anything required), so the search stays small.

    If that's still more than `limit`, drop the weakest backup choices first. Must-haves stay.
    """
    must_names = {s.name for s in must}
    ranked = sorted({s.name: s for s in spots}.values(), key=lambda s: (-s.joy, s.stay, s.name))
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
    INF = float("inf")
    finish = [[INF] * n for _ in range(1 << n)]
    prev = [[-1] * n for _ in range(1 << n)]
    catmask = [0] * (1 << n)

    for i, s in enumerate(spots):
        start = s.opens_by(leave + city.minutes(home, s.zone))
        if start is not None and start + s.stay <= end:
            finish[1 << i][i] = start + s.stay

    for mask in range(1, 1 << n):
        low = (mask & -mask).bit_length() - 1
        catmask[mask] = catmask[mask & (mask - 1)] | catbit[low]
        for last in range(n):
            t = finish[mask][last]
            if t == INF:
                continue
            for nxt in range(n):
                if mask >> nxt & 1 or catmask[mask] & catbit[nxt]:
                    continue
                if spots[nxt].phase < spots[last].phase:
                    continue
                s = spots[nxt]
                start = s.opens_by(t + city.minutes(spots[last].zone, s.zone))
                if start is None:
                    continue
                done = start + s.stay
                if done + city.minutes(s.zone, home) > end:
                    continue
                new = mask | 1 << nxt
                if done < finish[new][nxt]:
                    finish[new][nxt], prev[new][nxt] = done, last

    must_mask = sum(1 << spots.index(s) for s in must)
    best = None  # (joy, -home_by, mask, last)
    for mask in range(1, 1 << n):
        if mask & must_mask != must_mask:
            continue
        chosen = [spots[i] for i in range(n) if mask >> i & 1]
        if not all(any(s.category == c for s in chosen) for c in need):
            continue
        for last in range(n):
            if finish[mask][last] == INF:
                continue
            home_by = finish[mask][last] + city.minutes(spots[last].zone, home)
            if home_by > end:
                continue
            key = (sum(s.joy for s in chosen), -home_by, mask, last)
            if best is None or key[:2] > best[:2]:
                best = key

    if best is None:
        return Plan()
    _, _, mask, last = best
    order = []
    while last != -1:
        order.append(spots[last])
        mask, last = mask ^ (1 << last), prev[mask][last]
    return schedule(order[::-1], city, home, leave)


def schedule(order: list, city: City, home: str, leave: int) -> Plan:
    """Turn an ordered list of spots into real times, including any wait for a window to open."""
    plan, clock, zone = Plan(), leave, home
    for s in order:
        drive = city.minutes(zone, s.zone)
        start = s.opens_by(clock + drive)
        plan.stops.append(Stop(s, clock + drive, start, drive))
        clock, zone = start + s.stay, s.zone
    plan.home_by = clock + city.minutes(zone, home)
    return plan


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
