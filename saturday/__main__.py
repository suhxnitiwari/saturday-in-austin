"""Saturday in Austin ✦  Tell it how long you have and what you're in the mood for.

    python -m saturday                      a surprise Saturday from my favorites, different every time
    python -m saturday --mood cozy
    python -m saturday --hours 6 --mood foodie --include "Clay Pit" --chart
    python -m saturday --seed 325           repeat a Saturday you liked
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from .city import City
from .planner import plan_day, shortlist
from .spots import MOODS, Guide, UnknownSpotError, load

PINK, BOLD, DIM, RESET = "\033[38;5;211m", "\033[1m", "\033[2m", "\033[0m"


def clock(minutes: float) -> str:
    h, m = divmod(int(round(minutes)), 60)
    return f"{(h - 1) % 12 + 1}:{m:02d} {'AM' if h % 24 < 12 else 'PM'}"


def parse_time(text: str) -> int:
    """'9', '9:30', '14:00' -> minutes after midnight."""
    h, _, m = text.partition(":")
    minutes = int(h) * 60 + int(m or 0)
    if not 0 <= minutes < 24 * 60:
        raise argparse.ArgumentTypeError(f"{text} isn't a time of day")
    return minutes


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="saturday", description="Plan the best day in Austin.")
    p.add_argument("--hours", type=float, default=10, help="how long you have (default 10)")
    p.add_argument("--mood", choices=MOODS, default="everything")
    p.add_argument("--start", type=parse_time, default=10 * 60, metavar="TIME", help="when you leave (default 10:00)")
    p.add_argument("--home", default="West Campus", help="where you start and end (default West Campus)")
    p.add_argument("--include", action="append", default=[], metavar="SPOT", help="a spot you have to go to")
    p.add_argument("--skip", action="append", default=[], metavar="SPOT", help="a spot to leave out")
    p.add_argument("--chart", action="store_true", help="also save the day as plan.png")
    p.add_argument("--seed", type=int, help="repeat a specific Saturday (each run prints its seed)")
    args = p.parse_args(argv)

    guide, city = Guide(load()), City()
    try:
        must = [guide.find(name) for name in args.include]
        skip = {guide.find(name).name for name in args.skip}
    except UnknownSpotError as err:
        print(err.args[0])
        return 1
    if args.home not in city.roads:
        print(f"I don't know the neighborhood '{args.home}'. Try one of: {', '.join(sorted(city.roads))}")
        return 1

    pool = [s for s in guide.for_mood(args.mood) + must if s.name not in skip]
    pool.append(guide.find("Medici")) if not any(s.category == "coffee" for s in pool) else None
    seed = args.seed if args.seed is not None else random.randrange(1000, 10000)
    spots = shortlist(pool, must, random.Random(seed))
    end = args.start + int(args.hours * 60)
    plan = plan_day(spots, city, args.home, args.start, end, must)

    if not plan.stops:
        print("Nothing fits in that window. Try more hours, a different mood, or fewer must-haves.")
        return 1

    hours = f"{args.hours:g} hour{'s' * (args.hours != 1)}"
    print(f"\n{PINK}{BOLD}Your Saturday ✦{RESET}  {DIM}{args.mood}, {hours} from {args.home}{RESET}")
    for stop in plan.stops:
        free = stop.start - stop.arrive  # waiting for the next spot's window to open
        if free >= 30:
            h, m = divmod(int(free), 60)
            length = f"{h}h {m}m" if h else f"{m} min"
            print(f"  {clock(stop.arrive - stop.drive):>8}  {DIM}free time ({length}): nap, journal, wander{RESET}")
        note = f"  {DIM}({stop.spot.note}){RESET}" if stop.spot.note else ""
        print(f"  {clock(stop.start):>8}  {stop.spot.name}{note}")
    print(f"  {clock(plan.home_by):>8}  home, happy")
    stops = f"{len(plan.stops)} stop{'s' * (len(plan.stops) != 1)}"
    print(f"\n  {DIM}{stops} · {plan.driving} min of driving · seed {seed}{RESET}")
    print(f"  {DIM}run it again for a different Saturday ✦{RESET}\n")

    if args.chart:
        from .chart import draw
        print(f"  saved {draw(plan, Path('plan.png'))}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
