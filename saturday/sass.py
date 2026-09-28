"""A little judgment, lovingly delivered, before the plan."""
from __future__ import annotations


def judge(wake: int, sleep: int, hours: float) -> list:
    """Comments on the choices someone made. Times are minutes after midnight."""
    notes = []
    if 12 * 60 <= wake < 18 * 60:
        notes.append("Waking up at noon? Wow, someone is not a morning person. ✦")
    if hours < 3:
        notes.append(f"Only {hours:g} hour{'s' * (hours != 1)} out? A homebody at heart. Honestly, respect.")
    elif hours >= 14:
        notes.append(f"{hours:g} hours outside?! OMG. What are you escaping right now?")
    return notes
