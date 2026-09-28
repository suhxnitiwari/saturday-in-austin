"""The Perfect Saturday planner: Suhani's Austin as a weighted graph.

Zones (West Campus, East Austin, South Congress...) are nodes and roads are edges
weighted in drive minutes. Her favorite spots live in those zones.

  Dijkstra    fastest drive between any two zones             O((V + E) log V)
  BFS         fewest stops between zones (ignores minutes)    O(V + E)
  Bitmask DP   the most joy you can fit into one day          O(2^n * n^2)
  Backtracking the same answer by brute force, used to double-check the DP
"""
from __future__ import annotations

import csv
import heapq
from collections import deque
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).parent / "data" / "austin_spots.csv"

# approximate drive minutes between neighboring zones
ROADS = [
    ("Campus", "West Campus", 4), ("Campus", "North Loop", 8), ("Campus", "Downtown", 7),
    ("Campus", "East Austin", 8), ("West Campus", "Clarksville", 6), ("West Campus", "Downtown", 8),
    ("Clarksville", "Downtown", 6), ("Clarksville", "Lake Austin", 7), ("North Loop", "Domain", 14),
    ("Downtown", "East Austin", 6), ("Downtown", "South Congress", 7), ("Lake Austin", "South Congress", 12),
]


@dataclass(frozen=True)
class Spot:
    name: str
    zone: str
    category: str
    stay: int  # minutes she'd happily spend there
    joy: int   # 1 to 10


def load_spots(path: Path = DATA) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return [Spot(r["spot"], r["zone"], r["category"], int(r["stay_minutes"]), int(r["joy"]))
                for r in csv.DictReader(f)]


class Austin:
    def __init__(self, roads=ROADS) -> None:
        self.graph = {}
        for a, b, minutes in roads:
            self.graph.setdefault(a, {})[b] = minutes
            self.graph.setdefault(b, {})[a] = minutes

    def drive(self, start: str, end: str) -> tuple:
        """Dijkstra: (minutes, route) for the fastest drive."""
        dist, prev = {start: 0}, {}
        heap = [(0, start)]
        while heap:
            d, zone = heapq.heappop(heap)
            if zone == end:
                break
            if d > dist[zone]:
                continue  # stale entry
            for nxt, w in self.graph[zone].items():
                if d + w < dist.get(nxt, float("inf")):
                    dist[nxt], prev[nxt] = d + w, zone
                    heapq.heappush(heap, (d + w, nxt))
        if end not in dist:
            raise ValueError(f"can't drive from {start} to {end}")
        route = [end]
        while route[-1] != start:
            route.append(prev[route[-1]])
        return dist[end], route[::-1]

    def fewest_stops(self, start: str, end: str) -> list:
        """BFS: the route through the fewest zones, regardless of minutes."""
        parent, frontier = {start: None}, deque([start])
        while frontier:
            zone = frontier.popleft()
            if zone == end:
                path = []
                while zone:
                    path.append(zone)
                    zone = parent[zone]
                return path[::-1]
            for nxt in self.graph[zone]:
                if nxt not in parent:
                    parent[nxt] = zone
                    frontier.append(nxt)
        raise ValueError(f"can't reach {end} from {start}")

    def travel_table(self, zones) -> dict:
        """Minutes between every pair of zones (one Dijkstra per pair, cached as a dict)."""
        zones = sorted(set(zones))
        return {(a, b): (0 if a == b else self.drive(a, b)[0]) for a in zones for b in zones}


# when each kind of stop makes sense: (earliest start, latest start), in minutes after midnight
WINDOWS = {
    "coffee": (7 * 60, 17 * 60),
    "brunch": (9 * 60, 12 * 60 + 30),
    "study": (8 * 60, 21 * 60),
    "pilates": (7 * 60, 19 * 60),
    "shopping": (10 * 60, 19 * 60),
    "creative": (10 * 60, 17 * 60),
    "dinner": (17 * 60 + 30, 21 * 60),
}


def begin_at(spot: Spot, arrival: float):
    """When the visit can start: right away, after waiting for it to open, or None if too late."""
    earliest, latest = WINDOWS.get(spot.category, (0, 24 * 60))
    start = max(arrival, earliest)
    return start if start <= latest else None


def perfect_saturday(spots: list, city: Austin, start_zone: str, budget: int,
                     start_hour: int = 9, must_have=("coffee",)) -> tuple:
    """Pick and order spots to maximize total joy within `budget` minutes of leaving home.

    Rules: one stop per category (one brunch, one dinner...), every stop starts inside its
    time window (brunch in the morning, dinner in the evening), and there's always coffee.

    Bitmask DP: end[mask][last] = the earliest clock time you can finish visiting exactly
    the spots in `mask`, ending at `last`. Finishing earlier is never worse (you can always
    wait), so keeping only the earliest finish per state is safe. The answer is the
    feasible mask with the most joy. O(2^n * n^2), and the one-per-category rule prunes
    most masks before they're ever expanded.
    """
    n = len(spots)
    travel = city.travel_table([start_zone] + [s.zone for s in spots])
    cats = sorted({s.category for s in spots})
    catbit = [1 << cats.index(s.category) for s in spots]
    leave, deadline = start_hour * 60, start_hour * 60 + budget
    INF = float("inf")
    end = [[INF] * n for _ in range(1 << n)]
    prev = [[-1] * n for _ in range(1 << n)]
    catmask = [0] * (1 << n)

    for i, s in enumerate(spots):
        b = begin_at(s, leave + travel[start_zone, s.zone])
        if b is not None and b + s.stay <= deadline:
            end[1 << i][i] = b + s.stay

    for mask in range(1, 1 << n):
        low = (mask & -mask).bit_length() - 1
        catmask[mask] = catmask[mask & (mask - 1)] | catbit[low]
        for last in range(n):
            t = end[mask][last]
            if t == INF:
                continue
            for nxt in range(n):
                if mask & (1 << nxt) or catmask[mask] & catbit[nxt]:
                    continue
                b = begin_at(spots[nxt], t + travel[spots[last].zone, spots[nxt].zone])
                if b is None or b + spots[nxt].stay > deadline:
                    continue
                new = mask | (1 << nxt)
                if b + spots[nxt].stay < end[new][nxt]:
                    end[new][nxt], prev[new][nxt] = b + spots[nxt].stay, last

    best = (0, INF, 0, -1)  # (joy, finish time, mask, last)
    for mask in range(1, 1 << n):
        last = min(range(n), key=lambda i: end[mask][i])
        if end[mask][last] == INF:
            continue
        chosen = [spots[i] for i in range(n) if mask & (1 << i)]
        if not all(any(s.category == c for s in chosen) for c in must_have):
            continue
        joy = sum(s.joy for s in chosen)
        if (joy, -end[mask][last]) > (best[0], -best[1]):
            best = (joy, end[mask][last], mask, last)

    joy, finish, mask, last = best
    order = []
    while last != -1:
        order.append(spots[last])
        mask, last = mask ^ (1 << last), prev[mask][last]
    return joy, (finish - leave if order else 0), order[::-1]


def brute_force_saturday(spots: list, city: Austin, start_zone: str, budget: int,
                         start_hour: int = 9, must_have=("coffee",)) -> int:
    """Backtracking over every possible order, pruning any path that breaks a rule.

    Exponential, so only for small inputs; the tests use it to prove the DP is right.
    """
    travel = city.travel_table([start_zone] + [s.zone for s in spots])
    deadline = start_hour * 60 + budget
    best = 0

    def explore(zone: str, clock: float, used: int, joy: int, cats: frozenset) -> None:
        nonlocal best
        if all(c in cats for c in must_have):
            best = max(best, joy)
        for i, s in enumerate(spots):
            if used & (1 << i) or s.category in cats:
                continue
            b = begin_at(s, clock + travel[zone, s.zone])
            if b is not None and b + s.stay <= deadline:  # prune: never continue a broken day
                explore(s.zone, b + s.stay, used | (1 << i), joy + s.joy, cats | {s.category})

    explore(start_zone, start_hour * 60, 0, 0, frozenset())
    return best


def pick_candidates(spots: list, per_category: int = 2) -> list:
    """Keep the top spots in each category so the DP runs in well under a second."""
    by_cat = {}
    for s in sorted(spots, key=lambda s: (-s.joy, s.stay, s.name)):
        by_cat.setdefault(s.category, [])
        if len(by_cat[s.category]) < per_category:
            by_cat[s.category].append(s)
    return [s for group in by_cat.values() for s in group]


def itinerary(order: list, city: Austin, start_zone: str, start_hour: int = 9) -> list:
    """Turn an ordered list of spots into a timed schedule, e.g. '9:04 AM  Medici'."""
    lines, clock, zone = [], start_hour * 60, start_zone
    for s in order:
        clock = begin_at(s, clock + city.drive(zone, s.zone)[0])
        lines.append(f"{_fmt(clock):>8}  {s.name} ({s.category}, {s.stay} min)")
        clock += s.stay
        zone = s.zone
    lines.append(f"{_fmt(clock):>8}  home, happy ✦")
    return lines


def _fmt(minutes: int) -> str:
    h, m = divmod(int(minutes), 60)
    return f"{(h - 1) % 12 + 1}:{m:02d} {'AM' if h < 12 else 'PM'}"
