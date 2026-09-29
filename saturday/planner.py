"""The planner: pick and order the stops that make the happiest day in the time you have.

The rules (the human ones live in rules.py):
  - every stop starts inside its window and ends before closing (brunch in the morning, dinner in the evening)
  - one stop per slot (one midday meal, one dinner...), unless the mood allows more
    (café hopping on a productive day, two adventures on an outside one)
  - never the same kind of stop twice in a row: there's a break between two hikes
  - nothing after dinner except a late-night snack
  - the day fits between leaving home and your end time
  - out through lunchtime means a real lunch, and through dinnertime a real dinner
  - what the mood needs is always included (coffee, nails, dinner in), plus spots you insist on
  - after a workout: coffee or a smoothie, then a shower. After a meal: not another meal
  - the plan with the best score wins: 10 points per point of joy, minus travel and bad timing

Why not just take the highest-joy spots? Because driving and opening hours interact:
a 10/10 dinner can push out two 8/10 afternoon stops. So the planner searches every
combination, with dynamic programming keeping that search fast.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .city import City

from . import rules
from .spots import SLOTS, WINDOWS, Mood, Spot, half_hour

INF = float("inf")
BUFFER = 5  # minutes to park and walk in, whenever you actually go somewhere
SLACK = 25  # how much the half-hour grid can waste before the first stop


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
    cost: float = 0  # travel and timing, in score points (see rules.cost)

    @property
    def outside(self) -> float:
        """Minutes from walking out the door to getting home."""
        return self.home_by - self.leave if self.stops else 0

    @property
    def joy(self) -> int:
        return sum(s.spot.joy for s in self.stops)

    @property
    def driving(self) -> int:
        """Minutes of travel, there and back."""
        return sum(s.drive for s in self.stops) + self.back

    back: int = 0  # minutes from the last stop home

    @property
    def score(self) -> float:
        return rules.JOY * self.joy - self.cost

    @property
    def places(self) -> list:
        """The real places: stops, without the blocks at home."""
        return [s for s in self.stops if not rules.kind(s.spot).reset]


def shortlist(spots: list, must: list, rng=None, per_slot: int = 2, limit: int = 12,
              caps: dict = None, need=(), distance=None, favor=()) -> list:
    """Pick a couple of candidates per slot (plus anything required), so the search stays small.

    With an rng, it's a weighted lottery: every spot can win, higher-rated ones win more often,
    so each run is a different Saturday built from the favorites. Without one, it's simply
    the top-rated spots (handy for tests).

    The lottery is the Efraimidis-Spirakis method: give each spot the key random() ** (1 / weight)
    and keep the biggest keys. That's weighted sampling without replacement in one sort.

    With more slots than the limit (a surprise day can be anything), whole slots sit this
    round out, except the ones the mood needs. With distance(spot) in minutes from home,
    far-away spots get fewer tickets: a 30-minute drive halves your odds. The luckiest spot
    of each favored category always makes it (on a Saturday morning, that's brunch).
    """
    caps = caps or {}
    must_names = {s.name for s in must}
    unique = {s.name: s for s in spots}.values()
    if rng is None:
        ranked = sorted(unique, key=lambda s: (-s.joy, s.stay, s.name))
    else:
        # Saturday brunch favorites get extra tickets in the lottery
        weight = lambda s: (s.joy ** 2 * (2.5 if s.name in rules.FAVORITE_BRUNCH else 1)
                            / (1 + (distance(s) if distance else 0) / 30))
        ranked = sorted(unique, key=lambda s: rng.random() ** (1 / weight(s)), reverse=True)
    keep, counts = {s.name: s for s in must}, {}
    for category in favor:
        lucky = next((s for s in ranked if s.category == category), None)
        if lucky:
            keep.setdefault(lucky.name, lucky)
            counts[lucky.slot] = counts.get(lucky.slot, 0) + 1
            must_names = must_names | {lucky.name}
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
             must: list = (), need=("coffee",), caps: dict = None, walking: bool = False,
             real_meals: bool = True) -> Plan:
    """Bitmask dynamic programming over subsets of spots, with a person inside.

    A state is (which spots, how many of each slot, the person's state from rules.step,
    the last spot, the time you finish it), and for each one we keep the lowest cost.
    Finish time has to be part of the state: with timing costs (a park is nicer at 10 than
    at 1), finishing earlier isn't always better. Then the answer is the valid state with
    the best score: 10 x joy - travel and timing costs. Far fewer states than the n! orders.
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
    out = [city.minutes(home, s.zone) for s in spots]
    back = [city.minutes(s.zone, home) for s in spots]
    opens = [WINDOWS[s.category] for s in spots]
    closes = [rules.kind(s).close for s in spots]
    stay = [s.stay for s in spots]
    phase = [s.phase for s in spots]
    back_cost = [b * (rules.WALK_COST if walking else rules.DRIVE_COST) for b in back]
    # the rules, looked up instead of called: move costs as a table, the rest cached as we go
    move = [[rules.move_cost(a, b, drive[i][j], walking) for j, b in enumerate(spots)] for i, a in enumerate(spots)]
    timing, steps = {}, {}

    def time_cost(j, begin):
        key = (j, begin)
        if key not in timing:
            timing[key] = rules.time_cost(spots[j], begin)
        return timing[key]

    def step(h, j, begin):
        late = rules.late_enough(begin, begin - leave)  # step() only depends on time through this
        key = (h, j, late)
        if key not in steps:
            steps[key] = rules.step(h, spots[j], begin, begin - leave)
        return steps[key]

    def begin_at(t, travel, j):
        begin = half_hour(max(t + travel + (BUFFER if travel else 0), opens[j][0]))
        ok = begin <= opens[j][1] and begin + stay[j] <= closes[j] and begin + stay[j] + back[j] <= end
        return begin if ok else None

    # best[state] = cost, where a state ends in its finish time; prev[state] = the state before it
    best, prev, layer = {}, {}, {}
    for i, s in enumerate(spots):
        begin = begin_at(leave, out[i], i)
        if begin is None:
            continue
        h = step(rules.START, i, begin)
        if h is not None:
            layer[(1 << i, unit[i], h, i, begin + stay[i])] = rules.cost(None, s, begin, out[i], walking)
    while layer:
        best.update(layer)
        nxt_layer = {}
        for state, c in layer.items():
            mask, cats, h, last, t = state
            for j in range(n):
                if mask >> j & 1 or same[last][j] or phase[j] < phase[last]:
                    continue
                if (cats >> shift[j]) & 3 >= cap[j]:
                    continue
                begin = begin_at(t, drive[last][j], j)
                if begin is None:
                    continue
                h2 = step(h, j, begin)
                if h2 is None:
                    continue
                value = c + move[last][j] + time_cost(j, begin)
                key = (mask | 1 << j, cats + unit[j], h2, j, begin + stay[j])
                if value < nxt_layer.get(key, INF):
                    nxt_layer[key] = value
                    prev[key] = state
        layer = nxt_layer

    on_list = {s.slot for s in spots}
    must_mask = sum(1 << spots.index(s) for s in must)
    joy = [s.joy for s in spots]
    winner, top = None, None  # (score, -home_by)
    for state, c in best.items():
        mask, _, h, last, t = state
        if mask & must_mask != must_mask or not rules.can_end(h):
            continue
        home_at = t + back[last]
        # out through lunchtime or dinnertime (by when you'd actually be out) means a real meal,
        # as long as there's a real meal on the list to go to
        required = need + (tuple(m for m in meals(leave, home_at) if m in on_list) if real_meals else ())
        if not all(any(mask >> i & 1 and x in (spots[i].category, spots[i].slot) for i in range(n)) for x in required):
            continue
        score = rules.JOY * sum(joy[i] for i in range(n) if mask >> i & 1) - c - back_cost[last]
        rank = (score - rules.long_day(home_at - leave), -home_at)
        if top is None or rank > top:
            winner, top = state, rank

    if winner is None:
        return Plan()
    order, state = [], winner
    while state is not None:
        order.append(spots[state[3]])
        state = prev.get(state)
    return schedule(order[::-1], city, home, leave, walking)


def schedule(order: list, city: City, home: str, leave: int, walking: bool = False) -> Plan:
    """Turn an ordered list of spots into real times, including any wait for a window to open.

    If the first stop isn't open yet, you simply leave home later instead of waiting outside.
    """
    planned = leave
    if order:
        travel = city.minutes(home, order[0].zone)
        first = order[0].opens_by(leave + travel + (BUFFER if travel else 0))
        leave = first - travel - (BUFFER if travel else 0)
    plan, clock, zone, prev = Plan(leave=leave), leave, home, None
    for s in order:
        travel = city.minutes(zone, s.zone)
        start = s.opens_by(clock + travel + (BUFFER if travel else 0))
        plan.stops.append(Stop(s, clock + travel, start, travel))
        plan.cost += rules.cost(prev, s, start, travel, walking)
        clock, zone, prev = start + s.stay, s.zone, s
    plan.back = city.minutes(zone, home)
    plan.cost += plan.back * (rules.WALK_COST if walking else rules.DRIVE_COST)
    plan.home_by = clock + plan.back
    plan.cost += rules.long_day(plan.home_by - planned)
    return plan


MEALTIMES = {"midday meal": (11 * 60 + 30, 14 * 60 + 30), "dinner": (17 * 60 + 30, 21 * 60)}

WALK_RADIUS = 1  # miles from home on a no-car day: every stop a short walk from your door


def walking(spots: list, home: str, fill: list = ()) -> tuple:
    """A no-car day: every spot becomes its own place on the map, and no walk is over a mile.
    Only spots within WALK_RADIUS of home. If nothing left is coffee, a midday meal or dinner,
    the closest walkable one from `fill` joins (a mood's favorites might all be across town).
    Returns the walking city and the spots, renamed so each spot's "zone" is itself.
    city.reach has no mile limit, for asking what could fit at all."""
    from dataclasses import replace
    from .city import WalkCity
    fallback = {s.name: s.zone for s in spots}
    city = WalkCity(fallback)
    city.reach = WalkCity(fallback, max_miles=None)
    # close to home, and reachable from home in hops of a mile or less (breadth-first search)
    close = [s for s in spots if city.reach.miles(home, s.name) <= WALK_RADIUS]
    seen, frontier = set(), [home]
    while frontier:
        here = frontier.pop()
        for s in close:
            if s.name not in seen and city.minutes(here, s.name) < WalkCity.TOO_FAR:
                seen.add(s.name)
                frontier.append(s.name)
    kept = [s for s in close if s.name in seen]
    city.fallback.update({c.name: c.zone for c in fill})
    for slot in ("coffee", "midday meal", "dinner"):
        options = [c for c in fill if c.slot == slot and city.minutes(home, c.name) < WalkCity.TOO_FAR]
        if options and not any(s.slot == slot for s in kept):
            kept.append(min(options, key=lambda c: city.reach.miles(home, c.name)))
    return city, [replace(s, zone=s.name) for s in kept]


def reachable(spots: list, city: City, home: str, minutes: float, keep=()) -> list:
    """Only spots you could get to, enjoy and get home from in the time you have
    (so a one-hour outing picks from quick coffees, not a two-hour pottery class)."""
    return [s for s in spots if s in keep or s.stay + 2 * city.minutes(home, s.zone) <= minutes]


def meals(leave: int, end: int) -> tuple:
    """Snacks don't count as meals: out for 90+ minutes of lunchtime means a real lunch,
    and the same for dinner."""
    return tuple(meal for meal, (a, b) in MEALTIMES.items() if min(end, b) - max(leave, a) >= 90)


def plan_outing(spots: list, city: City, home: str, start: int, end: int, hours: float = None,
                must: list = (), mood: Mood = Mood(), step: int = 30, walking: bool = False) -> Plan:
    """The best `hours` out, somewhere between `start` (ready to go) and `end` (home by).
    hours=None means all of it. Times are minutes after midnight; home by 1:00 AM works too.

    Tries every departure time, `step` minutes apart, and keeps the best-scoring plan
    (ties go to the earlier start, or the later one for a slow day). A shower or a
    change at home joins the candidates when the day could need one.
    """
    if end <= start:
        end += 24 * 60
    length = end - start if hours is None else min(int(hours * 60), end - start)
    if length <= 0:
        return Plan()
    extra = [r for r in rules.resets(home)
             if r.category == "reset-shower" and any(rules.kind(s).workout for s in spots)
             or r.category == "reset-change" and any(s.dressy for s in spots)]
    spots = list(spots) + extra
    best, rank = Plan(), None
    start_pref = 1 if mood.late else -1
    # the whole day if it fits; otherwise skip the meals, then what the mood is built around
    for with_meals, with_wants in ((True, True), (False, True), (False, False)):
        # leave right away, or on any :00 or :30 after (stops start on the half hour, so those waste nothing)
        for leave in [start] + list(range(half_hour(start + 1), end - length + 1, step)):
            need = mood.need + (mood.want if with_wants else ())
            # stops start on :00 and :30, so the search gets a little slack; the real plan still has to fit
            plan = plan_day(spots, city, home, leave, min(leave + length + SLACK, end), must, need, mood.caps,
                            walking, real_meals=with_meals)
            if not plan.stops or plan.outside > length:
                continue
            key = (plan.score, start_pref * plan.leave)
            if rank is None or key > rank:
                best, rank = plan, key
        if best.stops:
            return best
    return best


def best_score_by_search(spots: list, city: City, home: str, leave: int, end: int,
                         need=("coffee",), caps: dict = None, real_meals: bool = True) -> float:
    """Backtracking over every possible order, same rules. Exponential; the tests use it to check plan_day."""
    caps = caps or {}
    best, on_list = None, {s.slot for s in spots}

    def explore(zone, clock, used, joy, cost, counts, cats, phase, last, h):
        nonlocal best
        home_trip = city.minutes(zone, home)
        required = need + (tuple(m for m in meals(leave, clock + home_trip) if m in on_list) if real_meals else ())
        if used and clock + home_trip <= end and rules.can_end(h) and all(c in cats for c in required):
            score = rules.JOY * joy - cost - home_trip * rules.DRIVE_COST - rules.long_day(clock + home_trip - leave)
            best = score if best is None else max(best, score)
        for i, s in enumerate(spots):
            if used >> i & 1 or s.slot == (last.slot if last else None) or s.phase < phase:
                continue
            if counts.get(s.slot, 0) >= min(caps.get(s.slot, 1), 3):
                continue
            travel = city.minutes(zone, s.zone)
            start = s.opens_by(clock + travel + (BUFFER if travel else 0))
            if start is None or start + s.stay > rules.kind(s).close or start + s.stay + city.minutes(s.zone, home) > end:
                continue
            h2 = rules.step(h, s, start, start - leave)
            if h2 is None:
                continue
            explore(s.zone, start + s.stay, used | 1 << i, joy + s.joy, cost + rules.cost(last, s, start, travel),
                    {**counts, s.slot: counts.get(s.slot, 0) + 1}, cats | {s.category, s.slot}, s.phase, s, h2)

    explore(home, leave, 0, 0, 0, {}, frozenset(), 0, None, rules.START)
    return best
