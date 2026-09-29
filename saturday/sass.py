"""A little judgment, lovingly delivered, before the plan."""
from __future__ import annotations

from .planner import GET_READY, WIND_DOWN


def _clock(minutes: int) -> str:
    h, m = divmod(minutes % (24 * 60), 60)
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def judge(wake: int, sleep: int, hours: float, mood: str = "everything",
          walk: bool = False, rainy: bool = False, area: str = None) -> list:
    """Comments on the choices someone made. Times are minutes after midnight."""
    notes = []
    if 12 * 60 <= wake < 14 * 60:
        notes.append(f"Waking up at {_clock(wake)}? Wow, someone is not a morning person. ✦")
    elif 14 * 60 <= wake < 18 * 60:
        notes.append(f"Waking up at {_clock(wake)}?? The day is basically over, bestie. Dinner is breakfast now.")
    if wake >= 18 * 60:
        notes.append(f"Waking up at {_clock(wake)}?? That's nighttime, vampire. Everything's closed. "
                     f"Did you mean {_clock(wake - 12 * 60)}?")
        return notes  # the hours don't matter if the day hasn't started
    if 11 * 60 <= sleep <= 15 * 60 or wake < sleep <= 15 * 60:  # a bedtime in the daytime
        notes.append(f"Bed at {_clock(sleep)}?? The sun is still up, babe. Did you mean {_clock(sleep + 12 * 60)}?")
    free = ((sleep - wake) % (24 * 60) or 24 * 60) - GET_READY - WIND_DOWN  # time you could actually be out
    if hours * 60 > free:
        h, m = divmod(max(free, 0), 60)
        notes.append(f"{hours:g} hours out when you're only free for {h}h{f' {m}m' if m else ''}? "
                     f"Math is not mathing. I planned what fits.")
    elif mood == "day-in":
        notes.append("A day in? Iconic. Sweatpants on, phone on do not disturb. ✦")
    elif hours <= 1:
        notes.append(f"Only {hours:g} hour{'s' * (hours != 1)} out? Are you even sure about going out?????")
    elif hours < 3:
        notes.append(f"Only {hours:g} hour{'s' * (hours != 1)} out? A homebody at heart. Honestly, respect.")
    elif hours >= 14:
        notes.append(f"{hours:g} hours outside?! OMG. What are you escaping right now?")
    if mood == "treat-yourself" and not walk and hours < 3:
        notes.append(f"{hours:g} hours? Just enough for nails. Give yourself 3 for the full Domain day.")
    if walk and mood == "treat-yourself":
        notes.append("Walking to the Domain? That's a two-hour walk, babe. Treat yourself to a ride.")
    elif walk and mood != "day-in":
        notes.append("No car? Walking it is. Comfy shoes on. 👟")
    if area and mood != "day-in":
        notes.append(f"Just {area}? Keeping it local. Love that.")
    if rainy and mood != "day-in":
        notes.append("Rainy day? Everything's indoors, but bring an umbrella anyway ☔")
    return notes


# how the day ends, picked by the seed so the same Saturday always ends the same way
SIGN_OFFS = (
    "home, glowing ✦",
    "home to rot in bed. You earned it.",
    "home, dramatically flopping onto the bed",
    "home, already planning next Saturday",
    "home, main character energy intact",
    "home, feet up, camera roll full",
)


def sign_off(home_by: int, hours: float, seed: int, mood: str = "everything", movie: bool = False) -> str:
    """The last line of the plan. home_by is minutes after midnight."""
    if mood == "day-in":
        return "credits rolling, already in bed ✦" if movie else "cozy mode: complete ✦"
    if mood == "treat-yourself" and home_by > 12 * 60:
        return "home, nails done, bags full ✦"
    if home_by <= 12 * 60:
        return "home before lunch. That was an errand, not a Saturday."
    if hours <= 2:
        return "home already? The couch won again."
    if hours >= 12:
        return "home, finally. Your feet would like a word."
    if home_by >= 22 * 60 or home_by < 4 * 60:
        return "home just in time to pretend you'll sleep early"
    return SIGN_OFFS[seed % len(SIGN_OFFS)]
