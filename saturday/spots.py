"""The spots: loading them, filtering by mood, and looking them up by name."""
from __future__ import annotations

import csv
import difflib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path

DATA = Path(__file__).parent / "data" / "spots.csv"
MOODS = ("everything", "slow", "social", "creative", "foodie", "outside", "shopping", "productive", "treat-myself", "day-in")
MOOD_NAMES = {"everything": "Surprise me", "slow": "Slow", "social": "Social", "creative": "Creative", "foodie": "Foodie",
              "outside": "Outside", "shopping": "Shopping", "productive": "Productive", "treat-myself": "Treat myself",
              "day-in": "Day in"}

# when each kind of stop makes sense: (earliest start, latest start), minutes after midnight
WINDOWS = {
    "coffee": (7 * 60, 17 * 60),
    "smoothie": (8 * 60, 18 * 60),
    "reset-shower": (6 * 60, 22 * 60),
    "reset-change": (16 * 60 + 30, 21 * 60),
    "brunch": (9 * 60, 12 * 60 + 30),
    "lunch": (11 * 60 + 30, 14 * 60 + 30),
    "study": (8 * 60, 21 * 60),
    "museum": (10 * 60, 16 * 60 + 30),
    "exercise": (7 * 60, 19 * 60),
    "creative": (10 * 60, 17 * 60),
    "shopping": (10 * 60, 19 * 60),
    "market": (8 * 60, 12 * 60 + 30),
    "nails": (10 * 60, 17 * 60 + 30),
    "hike": (7 * 60, 16 * 60),        # before it gets too hot
    "paddle": (8 * 60, 18 * 60),
    "swim": (9 * 60, 18 * 60),
    "park": (8 * 60, 19 * 60),
    "sunset": (18 * 60 + 30, 20 * 60 + 30),
    "hangout": (11 * 60, 21 * 60),
    "cinema": (12 * 60, 21 * 60),
    "treat": (14 * 60, 21 * 60 + 30),  # after lunch, not instead of it
    "self care": (8 * 60, 21 * 60),
    "snack": (7 * 60, 21 * 60 + 30),
    "movie": (8 * 60, 22 * 60 + 30),  # at home, any time is movie time
    "show": (8 * 60, 22 * 60 + 30),
    "read": (8 * 60, 22 * 60),
    "games": (10 * 60, 22 * 60),
    "spa": (10 * 60, 18 * 60),
    "murals": (9 * 60, 19 * 60),
    "game": (11 * 60, 19 * 60 + 30),
    "live music": (19 * 60, 23 * 60),
    "dinner": (17 * 60 + 30, 21 * 60),
    "order in": (17 * 60, 21 * 60 + 30),
    "late night": (21 * 60, 23 * 60 + 30),
    "nightlife": (20 * 60, 23 * 60 + 30),   # 21+
    "karaoke": (20 * 60, 23 * 60),
    "comedy": (19 * 60, 22 * 60 + 30),
    "tea": (10 * 60, 21 * 60 + 30),       # boba, matcha, high tea
    "escape room": (10 * 60, 22 * 60),
    "boat": (16 * 60 + 30, 20 * 60 + 30),  # golden hour on the lake
    "tour": (9 * 60 + 30, 16 * 60),       # food, bike and bus tours run by day
    "ghost tour": (19 * 60, 21 * 60 + 30),
    "brewery": (12 * 60, 21 * 60 + 30),   # 21+ to drink
}


# categories that fill the same slot in a day: brunch OR lunch, a hike OR a swim...
SLOTS = {"brunch": "midday meal", "lunch": "midday meal", "order in": "dinner",
         "hike": "outdoor", "paddle": "outdoor", "swim": "outdoor", "park": "outdoor",
         "game": "hangout", "spa": "nails", "show": "movie",
         "nightlife": "night out", "karaoke": "night out", "escape room": "hangout", "tea": "treat", "boat": "outdoor", "comedy": "evening show", "live music": "evening show",
         "ghost tour": "evening show"}

# the evening only moves forward: after dinner, the only thing left is a late-night snack
PHASE = {"dinner": 1, "order in": 1, "movie": 2, "show": 2, "live music": 2, "late night": 2, "nightlife": 2, "karaoke": 2, "comedy": 2,
         "ghost tour": 2}

# out in the weather: left out on a rainy day
OUTDOORS = {"hike", "paddle", "swim", "park", "sunset", "murals", "market", "game", "boat", "tour", "ghost tour"}

# movie night and reading pick from my real shelves (suhanitiwari.com/home/favorites)
SHELF = json.loads((Path(__file__).parent / "data" / "shelf.json").read_text(encoding="utf-8"))

HOME = "Home"  # the zone for day-in stops; it becomes wherever the day starts

# "just the Domain", "just SoCo": the neighborhoods a day can stay inside
AREAS = {
    "anywhere": ("Anywhere", None),
    "ut": ("UT / West Campus", {"Campus / UT Corridor", "West Campus"}),
    "downtown": ("Downtown", {"Downtown"}),
    "east": ("East Austin", {"East Austin"}),
    "soco": ("South Congress / South First", {"South Congress", "South First"}),
    "clarksville": ("Clarksville / West Austin", {"Clarksville / West Austin", "Lake Austin / West Austin"}),
    "domain": ("The Domain / Rock Rose", {"The Domain / Rock Rose"}),
    "zilker": ("Zilker / Barton Springs", {"Zilker / Barton Springs / Greenbelt"}),
    "south-lamar": ("South Lamar", {"South Lamar"}),
    "north-loop": ("Hyde Park / North Loop", {"Hyde Park / North Loop"}),
    "burnet": ("Burnet Road", {"Burnet Road / Mid-North"}),
    "mueller": ("Mueller", {"Mueller"}),
}

# "starting from": where home is, as one of the map's neighborhoods
STARTS = {"ut": "West Campus", "downtown": "Downtown", "east": "East Austin", "soco": "South Congress",
          "clarksville": "Clarksville / West Austin", "domain": "The Domain / Rock Rose", "zilker": "Zilker / Barton Springs / Greenbelt",
          "south-lamar": "South Lamar", "north-loop": "Hyde Park / North Loop", "burnet": "Burnet Road / Mid-North", "mueller": "Mueller"}
DAY_TRIPS = {"Southeast Austin", "Lake Travis"}  # worth the drive, but not neighborhoods on the map

# what "absolutely not" can rule out besides one place
NOT_THESE = {
    "workouts": ("Workouts", {"exercise"}),
    "museums": ("Museums", {"museum"}),
    "shopping": ("Shopping", {"shopping", "market"}),
    "outdoors": ("Anything outdoors", {"hike", "paddle", "swim", "park", "sunset", "murals", "market", "game"}),
    "live-music": ("Live music", {"live music"}),
    "nightlife": ("Bars and nightlife", {"nightlife", "karaoke", "brewery"}),
    "studying": ("Studying", {"study"}),
    "sweets": ("Sweets", {"treat", "late night", "snack"}),
}


@dataclass(frozen=True)
class Mood:
    """What makes each mood its own kind of day."""
    need: tuple = ("coffee",)  # categories every plan must have
    want: tuple = ()  # what the day is built around, whenever it fits
    caps: dict = field(default_factory=dict)  # slots allowed more than once, and how many times
    late: bool = False  # prefer a later start (a slow morning)
    meals: bool = True  # out through lunch or dinner means a real meal (a study day eats at home)

    def relaxed(self) -> "Mood":
        """In one neighborhood, a mood's must-haves become nice-to-haves (not every block has nails)."""
        return replace(self, need=(), want=self.need + self.want)


RULES = {
    "everything": Mood(),
    "slow": Mood(late=True),  # a slow morning, lattes, bookstores, nowhere to be
    "social": Mood(need=(), want=("hangout",)),  # Peter Pan, Pins or Cidercade with everyone
    "creative": Mood(want=("creative",), caps={"creative": 2}),  # studios, murals, a show at night
    "foodie": Mood(need=(), caps={"midday meal": 2, "treat": 2}),  # brunch AND lunch, on purpose
    "outside": Mood(caps={"outdoor": 2}),  # two adventures, never back to back
    "shopping": Mood(want=("shopping",), caps={"shopping": 3}),  # SoCo, the Domain, a treat between
    "productive": Mood(caps={"coffee": 3, "study": 2}, meals=False),  # café hopping; they'll eat at home
    "treat-myself": Mood(need=("nails",)),  # a Domain day: brunch, nails, shopping, dinner
    "day-in": Mood(need=(), want=("order in", "movie"), late=True),  # food and a movie, always something to do
}


def half_hour(minutes: float) -> int:
    """Round up to the next :00 or :30. 1:37 PM -> 2:00 PM, 1:30 PM stays 1:30 PM."""
    return -(-int(minutes) // 30) * 30


class UnknownSpotError(KeyError):
    def __init__(self, name: str, suggestion) -> None:
        hint = f" Did you mean {suggestion}?" if suggestion else ""
        super().__init__(f"I don't know a spot called '{name}'.{hint}")


@dataclass(frozen=True)
class Spot:
    name: str
    zone: str
    category: str
    stay: int     # minutes
    joy: int      # 1 to 10
    moods: frozenset
    note: str = ""
    dressy: bool = False  # worth going home to change for
    price: int = 0        # rough dollars per person

    @property
    def slot(self) -> str:
        return SLOTS.get(self.category, self.category)

    @property
    def phase(self) -> int:
        return PHASE.get(self.category, 0)

    def opens_by(self, arrival: float):
        """When the visit can start, on the next hour or half hour (plans say 1:30, not 1:37),
        after waiting for its window if needed. None if it's too late."""
        earliest, latest = WINDOWS[self.category]
        start = half_hour(max(arrival, earliest))
        return start if start <= latest else None


def load(path: Path = DATA) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return [Spot(r["spot"], r["zone"], r["category"], int(r["stay_minutes"]), int(r["joy"]),
                     frozenset(r["moods"].split("|")), r["note"], r.get("dressy") == "yes", int(r.get("price") or 0))
                for r in csv.DictReader(f)]


class Guide:
    """All the spots, with case-insensitive lookup by name (a dict, so O(1)).
    Day-in spots move to `home`, so the map knows where they are."""

    def __init__(self, spots: list, home: str = "West Campus") -> None:
        self.home_spots = {s.name for s in spots if s.zone == HOME}
        self.spots = [replace(s, zone=home) if s.zone == HOME else s for s in spots]
        self._by_name = {s.name.lower(): s for s in self.spots}

    def find(self, name: str) -> Spot:
        key = name.strip().lower()
        if key in self._by_name:
            return self._by_name[key]
        close = difflib.get_close_matches(key, self._by_name, n=1, cutoff=0.5)
        raise UnknownSpotError(name, self._by_name[close[0]].name if close else None)

    def for_mood(self, mood: str) -> list:
        if mood not in MOODS:
            raise ValueError(f"mood must be one of: {', '.join(MOODS)}")
        if mood == "everything":  # a surprise day is a day out
            return [s for s in self.spots if s.name not in self.home_spots]
        return [s for s in self.spots if mood in s.moods]

    def pool(self, mood: str, must=(), skip=(), rainy: bool = False, near=None, area: str = "anywhere",
             not_these=()) -> list:
        """The spots a mood can pick from, plus must-haves, minus skips, and coffee if it needs it.
        On a rainy day, only indoor spots; with `near`, only spots it says are close enough;
        with an area, only spots in those neighborhoods (on a day in, home counts too)."""
        zones = AREAS[area][1]
        banned = set().union(*(NOT_THESE[n][1] for n in not_these)) if not_these else set()
        candidates = {s.name: s for s in self.for_mood(mood) + list(must)}.values()  # no duplicates
        spots = [s for s in candidates
                 if s.name not in skip and (s in must or s.category not in banned
                                            and not (rainy and s.category in OUTDOORS)
                                            and (near is None or near(s))
                                            and (zones is None or s.zone in zones
                                                 or mood == "day-in" and s.name in self.home_spots))]
        if zones is None and "coffee" in RULES[mood].need and not any(s.category == "coffee" for s in spots):
            spots.append(self.find("Medici"))
        return spots


def shelf_note(spot: Spot, rng) -> str:
    """What to watch or read, from the shelf; any other spot keeps its own note."""
    picks = SHELF.get(spot.category)
    return rng.choice(picks) if picks else spot.note
