"""The spots: loading them, filtering by mood, and looking them up by name."""
from __future__ import annotations

import csv
import difflib
from dataclasses import dataclass, field, replace
from pathlib import Path

DATA = Path(__file__).parent / "data" / "spots.csv"
MOODS = ("everything", "treat-yourself", "adventurous", "productive", "social", "day-in", "cozy")

# when each kind of stop makes sense: (earliest start, latest start), minutes after midnight
WINDOWS = {
    "coffee": (7 * 60, 17 * 60),
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
    "self care": (11 * 60, 20 * 60),
    "movie": (12 * 60, 22 * 60 + 30),
    "dinner": (17 * 60 + 30, 21 * 60),
    "order in": (17 * 60, 21 * 60 + 30),
    "late night": (21 * 60, 23 * 60 + 30),
}


# categories that fill the same slot in a day: brunch OR lunch, a hike OR a swim...
SLOTS = {"brunch": "midday meal", "lunch": "midday meal", "order in": "dinner",
         "hike": "outdoor", "paddle": "outdoor", "swim": "outdoor", "park": "outdoor"}

# the evening only moves forward: after dinner, the only thing left is a late-night snack
PHASE = {"dinner": 1, "order in": 1, "movie": 2, "late night": 2}

HOME = "Home"  # the zone for day-in stops; it becomes wherever the day starts


@dataclass(frozen=True)
class Mood:
    """What makes each mood its own kind of day."""
    need: tuple = ("coffee",)  # categories every plan must have
    want: tuple = ()  # what the day is built around, whenever it fits
    caps: dict = field(default_factory=dict)  # slots allowed more than once, and how many times
    late: bool = False  # prefer a later start (a slow morning)


RULES = {
    "everything": Mood(),
    "treat-yourself": Mood(need=("nails",)),  # a Domain day: brunch, nails, shopping, dinner
    "adventurous": Mood(caps={"outdoor": 2}),  # two adventures, never back to back
    "productive": Mood(caps={"coffee": 3, "study": 2}),  # café hopping
    "social": Mood(need=(), want=("hangout",)),  # Victory Lap or Topgolf with everyone
    "day-in": Mood(need=("order in",), late=True),
    "cozy": Mood(want=("creative",), caps={"creative": 2}),  # something handmade
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
                     frozenset(r["moods"].split("|")), r["note"])
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

    def pool(self, mood: str, must=(), skip=()) -> list:
        """The spots a mood can pick from, plus must-haves, minus skips, and coffee if it needs it."""
        spots = [s for s in self.for_mood(mood) + list(must) if s.name not in skip]
        if "coffee" in RULES[mood].need and not any(s.category == "coffee" for s in spots):
            spots.append(self.find("Medici"))
        return spots
