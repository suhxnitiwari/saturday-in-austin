"""Austin as a weighted graph: neighborhoods are nodes, roads are edges in drive minutes."""
from __future__ import annotations

import heapq
import json
import math
from pathlib import Path

PLACES = Path(__file__).parent / "data" / "places.json"

# approximate drive minutes between neighboring zones
ROADS = [
    ("West Campus", "Campus / UT Corridor", 4), ("Campus / UT Corridor", "Downtown", 7), ("West Campus", "Downtown", 8),
    ("West Campus", "Clarksville / West Austin", 6), ("Clarksville / West Austin", "Downtown", 6),
    ("Clarksville / West Austin", "Lake Austin / West Austin", 7), ("Campus / UT Corridor", "Hyde Park / North Loop", 7),
    ("Hyde Park / North Loop", "Burnet Road / Mid-North", 6), ("Burnet Road / Mid-North", "The Domain / Rock Rose", 12),
    ("Hyde Park / North Loop", "Mueller", 8), ("Campus / UT Corridor", "Mueller", 10), ("East Austin", "Mueller", 8),
    ("Campus / UT Corridor", "East Austin", 8), ("Downtown", "East Austin", 6), ("Downtown", "South Congress", 7),
    ("Downtown", "South First", 7), ("South Congress", "South First", 3), ("South First", "South Lamar", 5),
    ("South Lamar", "Zilker / Barton Springs / Greenbelt", 5), ("Downtown", "Zilker / Barton Springs / Greenbelt", 8),
    ("Zilker / Barton Springs / Greenbelt", "South Congress", 6), ("Lake Austin / West Austin", "Zilker / Barton Springs / Greenbelt", 9),
    ("Lake Austin / West Austin", "The Domain / Rock Rose", 20), ("Lake Austin / West Austin", "Burnet Road / Mid-North", 12),
    ("South Congress", "Southeast Austin", 15), ("Downtown", "Southeast Austin", 18),      # McKinney Falls, a day trip
    ("Lake Austin / West Austin", "Lake Travis", 30),                                         # a day trip
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



# CapMetro, approximately: the main lines between the neighborhoods on the map, in stop order.
# Good enough to plan a day; check the CapMetro app for live times. (Free with a UT ID.)
BUS_ROUTES = {
    "801": ["Hyde Park / North Loop", "West Campus", "Campus / UT Corridor", "Downtown", "South Congress"],  # MetroRapid N Lamar/S Congress
    "803": ["The Domain / Rock Rose", "Burnet Road / Mid-North", "Hyde Park / North Loop", "West Campus", "Campus / UT Corridor",
            "Downtown", "Zilker / Barton Springs / Greenbelt", "South Lamar"],                        # MetroRapid Burnet/S Lamar
    "20": ["Mueller", "Campus / UT Corridor", "Downtown"],
    "7": ["Hyde Park / North Loop", "Campus / UT Corridor", "Downtown"],                               # Duval
    "4": ["Downtown", "East Austin"],
    "10": ["Downtown", "South First"],                                                                 # S 1st
    "30": ["Downtown", "Zilker / Barton Springs / Greenbelt"],
}
BUS_WAIT = 12       # minutes waiting at the stop (and again at a transfer)
BUS_SLOWER = 1.5    # a bus takes about 1.5x the drive
STOP_WALK = 6       # minutes walking to the stop and from it at the other end


class TransitCity:
    """Bus + walk: walk anything under a mile, take the bus for the rest, and skip what the bus doesn't reach.

    Like WalkCity, places are spot names (their real coordinates), falling back to their neighborhood.
    Bus times come from Dijkstra over (neighborhood, route) states, so a transfer costs another wait.
    """
    TOO_FAR = WalkCity.TOO_FAR

    def __init__(self, fallback: dict, routes: dict = BUS_ROUTES, roads: City = None) -> None:
        self.walk = WalkCity(fallback)
        self.fallback = self.walk.fallback
        roads = roads or City()
        self.edges = {}  # (zone, route) -> [((zone, route), minutes)]
        for name, stops in routes.items():
            for a, b in zip(stops, stops[1:]):
                ride = roads.minutes(a, b) * BUS_SLOWER
                self.edges.setdefault((a, name), []).append(((b, name), ride))
                self.edges.setdefault((b, name), []).append(((a, name), ride))
        self.lines = {}  # zone -> the routes that stop there
        for name, stops in routes.items():
            for z in stops:
                self.lines.setdefault(z, set()).add(name)
        self._bus = {}

    def zone(self, place: str) -> str:
        return self.fallback.get(place, place)

    def bus(self, a: str, b: str) -> float:
        """Stop-to-stop minutes between two neighborhoods, waits included (inf if the bus doesn't go)."""
        if (a, b) in self._bus:
            return self._bus[a, b]
        if a == b or a not in self.lines or b not in self.lines:
            best = float("inf")
        else:
            dist = {(a, r): BUS_WAIT for r in self.lines[a]}
            heap = [(BUS_WAIT, a, r) for r in self.lines[a]]
            heapq.heapify(heap)
            best = float("inf")
            while heap:
                d, z, r = heapq.heappop(heap)
                if d > dist.get((z, r), float("inf")):
                    continue
                if z == b:
                    best = d
                    break
                moves = self.edges.get((z, r), []) + [((z, r2), BUS_WAIT) for r2 in self.lines[z] if r2 != r]
                for state, w in moves:
                    if d + w < dist.get(state, float("inf")):
                        dist[state] = d + w
                        heapq.heappush(heap, (d + w, *state))
        self._bus[a, b] = best
        return best

    def how(self, a: str, b: str) -> str:
        """'walk' or 'bus': whichever the minutes() below picked."""
        if a == b:
            return "walk"
        miles = self.walk.miles(a, b)
        walk = miles * WalkCity.PACE if miles <= 1 else float("inf")
        return "walk" if walk <= self.bus(self.zone(a), self.zone(b)) + 2 * STOP_WALK else "bus"

    def minutes(self, a: str, b: str) -> int:
        if a == b:
            return 0
        miles = self.walk.miles(a, b)
        walk = miles * WalkCity.PACE if miles <= 1 else float("inf")
        best = min(walk, self.bus(self.zone(a), self.zone(b)) + 2 * STOP_WALK)
        return self.TOO_FAR if best == float("inf") else round(best)
