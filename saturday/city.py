"""Austin as a weighted graph: neighborhoods are nodes, roads are edges in drive minutes."""
from __future__ import annotations

import heapq
import json
import math
from pathlib import Path

PLACES = Path(__file__).parent / "data" / "places.json"

# approximate drive minutes between neighboring zones
ROADS = [
    ("Campus", "West Campus", 4), ("Campus", "North Loop", 8), ("Campus", "Downtown", 7),
    ("Campus", "East Austin", 8), ("West Campus", "Clarksville", 6), ("West Campus", "Downtown", 8),
    ("Clarksville", "Downtown", 6), ("Clarksville", "Lake Austin", 7), ("North Loop", "Domain", 14),
    ("Downtown", "East Austin", 6), ("Downtown", "South Congress", 7), ("Downtown", "Zilker", 8),
    ("Zilker", "South Congress", 6), ("Lake Austin", "Zilker", 9), ("Zilker", "Barton Creek", 10),
    ("South Lamar", "Zilker", 5), ("South Lamar", "South Congress", 7), ("Barton Creek", "Hill Country", 30),
    ("Downtown", "Southeast", 18), ("South Congress", "Southeast", 15), ("Lake Austin", "Northwest", 12),
    ("Domain", "Northwest", 15), ("Barton Creek", "Southwest", 12), ("South Lamar", "Southwest", 15),
    ("Campus", "Mueller", 10), ("North Loop", "Mueller", 8), ("East Austin", "Mueller", 8),
]


class City:
    def __init__(self, roads=ROADS) -> None:
        self.roads = {}  # zone -> {neighbor: minutes}
        for a, b, minutes in roads:
            self.roads.setdefault(a, {})[b] = minutes
            self.roads.setdefault(b, {})[a] = minutes
        self._cache = {}

    def drive(self, start: str, end: str) -> tuple:
        """Fastest drive as (minutes, route), using Dijkstra's algorithm with a min-heap.

        O((V + E) log V). Results are cached, since the planner asks for the same pairs a lot.
        """
        if (start, end) in self._cache:
            return self._cache[start, end]
        if start not in self.roads or end not in self.roads:
            raise KeyError(f"unknown neighborhood: {start if start not in self.roads else end}")
        dist, prev = {start: 0}, {}
        heap = [(0, start)]
        while heap:
            d, zone = heapq.heappop(heap)
            if zone == end:
                break
            if d > dist[zone]:
                continue  # an outdated, longer entry
            for nxt, w in self.roads[zone].items():
                if d + w < dist.get(nxt, float("inf")):
                    dist[nxt], prev[nxt] = d + w, zone
                    heapq.heappush(heap, (d + w, nxt))
        result = (dist[end], _route(prev, start, end))
        self._cache[start, end] = result
        return result

    def minutes(self, start: str, end: str) -> int:
        return self.drive(start, end)[0]


def _route(prev: dict, start: str, zone: str) -> list:
    """Rebuild the route recursively by walking back from the destination."""
    return [start] if zone == start else _route(prev, start, prev[zone]) + [zone]


class WalkCity:
    """No car: real walking distances between real spots, and no walk longer than a mile.

    Spots come from OpenStreetMap (data/places.json). A spot it couldn't find, or a day-in
    spot, uses the middle of its neighborhood. Places are looked up by spot name, so the
    planner gives each spot its own name as its "zone" on a walking day.
    """
    PACE = 20       # minutes per mile
    DETOUR = 1.2    # streets aren't straight lines
    TOO_FAR = 10 ** 6

    def __init__(self, fallback: dict, max_miles: float = 1.0, path: Path = PLACES) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.spots, self.zones = data["spots"], data["zones"]
        self.fallback = fallback  # spot name -> its neighborhood
        self.max_miles = max_miles

    def where(self, place: str) -> tuple:
        return tuple(self.spots.get(place) or self.zones[self.fallback.get(place, place)])

    def miles(self, a: str, b: str) -> float:
        (la1, lo1), (la2, lo2) = map(lambda p: map(math.radians, self.where(p)), (a, b))
        h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        return 3958.8 * 2 * math.asin(math.sqrt(h)) * self.DETOUR

    def minutes(self, a: str, b: str) -> int:
        d = 0 if a == b else self.miles(a, b)
        if self.max_miles is not None and d > self.max_miles:
            return self.TOO_FAR
        return round(d * self.PACE)

