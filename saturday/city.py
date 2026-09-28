"""Austin as a weighted graph: neighborhoods are nodes, roads are edges in drive minutes."""
from __future__ import annotations

import heapq

# approximate drive minutes between neighboring zones
ROADS = [
    ("Campus", "West Campus", 4), ("Campus", "North Loop", 8), ("Campus", "Downtown", 7),
    ("Campus", "East Austin", 8), ("West Campus", "Clarksville", 6), ("West Campus", "Downtown", 8),
    ("Clarksville", "Downtown", 6), ("Clarksville", "Lake Austin", 7), ("North Loop", "Domain", 14),
    ("Downtown", "East Austin", 6), ("Downtown", "South Congress", 7), ("Downtown", "Zilker", 8),
    ("Zilker", "South Congress", 6), ("Lake Austin", "Zilker", 9), ("Zilker", "Barton Creek", 10),
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
