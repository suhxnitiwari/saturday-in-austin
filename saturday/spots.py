"""The spots: loading them, filtering by mood, and looking them up by name."""
from __future__ import annotations

import csv
import difflib
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).parent / "data" / "spots.csv"
MOODS = ("cozy", "creative", "foodie", "productive", "everything")

# when each kind of stop makes sense: (earliest start, latest start), minutes after midnight
WINDOWS = {
    "coffee": (7 * 60, 17 * 60),
    "brunch": (9 * 60, 12 * 60 + 30),
    "lunch": (11 * 60 + 30, 14 * 60 + 30),
    "study": (8 * 60, 21 * 60),
    "exercise": (7 * 60, 19 * 60),
    "creative": (10 * 60, 17 * 60),
    "shopping": (10 * 60, 19 * 60),
    "dinner": (17 * 60 + 30, 21 * 60),
    "late night": (21 * 60, 23 * 60 + 30),
}


# categories that fill the same slot in a day: brunch OR lunch, never both
SLOTS = {"brunch": "midday meal", "lunch": "midday meal"}

# the evening only moves forward: after dinner, the only thing left is a late-night snack
PHASE = {"dinner": 1, "late night": 2}


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
        """When the visit can start: now, after waiting for its window, or None if it's too late."""
        earliest, latest = WINDOWS[self.category]
        start = max(arrival, earliest)
        return start if start <= latest else None


def load(path: Path = DATA) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return [Spot(r["spot"], r["zone"], r["category"], int(r["stay_minutes"]), int(r["joy"]),
                     frozenset(r["moods"].split("|")), r["note"])
                for r in csv.DictReader(f)]


class Guide:
    """All the spots, with case-insensitive lookup by name (a dict, so O(1))."""

    def __init__(self, spots: list) -> None:
        self.spots = spots
        self._by_name = {s.name.lower(): s for s in spots}

    def find(self, name: str) -> Spot:
        key = name.strip().lower()
        if key in self._by_name:
            return self._by_name[key]
        close = difflib.get_close_matches(key, self._by_name, n=1, cutoff=0.5)
        raise UnknownSpotError(name, self._by_name[close[0]].name if close else None)

    def for_mood(self, mood: str) -> list:
        if mood not in MOODS:
            raise ValueError(f"mood must be one of: {', '.join(MOODS)}")
        return [s for s in self.spots if mood == "everything" or mood in s.moods]
