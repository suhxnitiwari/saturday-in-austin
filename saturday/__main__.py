"""Saturday in Austin ✦  Tell it how long you have and what you're in the mood for.

    python -m saturday                                a surprise Saturday, different every time
    python -m saturday --wake 8 --sleep 23 --hours 6  up at 8, in bed by 11, six hours out
    python -m saturday --mood girly --include "Éma" --chart
    python -m saturday --seed 325                     repeat a Saturday you liked
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from .city import City
from .planner import plan_outing, shortlist
from .sass import judge, sign_off
from .spots import MOODS, RULES, Guide, UnknownSpotError, half_hour, load

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
    p.add_argument("--wake", type=parse_time, default=9 * 60, metavar="TIME", help="when you wake up (default 9:00)")
    p.add_argument("--sleep", type=parse_time, default=23 * 60, metavar="TIME", help="when you go to bed (default 23:00)")
    p.add_argument("--hours", type=float, default=10, help="hours you want to spend out (default 10)")
    p.add_argument("--mood", choices=MOODS, default="everything")
    p.add_argument("--home", default="West Campus", help="where you start and end (default West Campus)")
    p.add_argument("--include", action="append", default=[], metavar="SPOT", help="a spot you have to go to")
    p.add_argument("--skip", action="append", default=[], metavar="SPOT", help="a spot to leave out")
    p.add_argument("--chart", action="store_true", help="also save the day as plan.png")
    p.add_argument("--seed", type=int, help="repeat a specific Saturday (each run prints its seed)")
    args = p.parse_args(argv)

    city = City()
    if args.home not in city.roads:
        print(f"I don't know the neighborhood '{args.home}'. Try one of: {', '.join(sorted(city.roads))}")
        return 1
    guide, mood = Guide(load(), args.home), RULES[args.mood]
    for note in judge(args.wake, args.sleep, args.hours, args.mood):
        print(f"\n  {PINK}{note}{RESET}")
    try:
        must = [guide.find(name) for name in args.include]
        skip = {guide.find(name).name for name in args.skip}
    except UnknownSpotError as err:
        print(err.args[0])
        return 1

    seed = args.seed if args.seed is not None else random.randrange(1000, 10000)
    spots = shortlist(guide.pool(args.mood, must, skip), must, random.Random(seed), caps=mood.caps, need=mood.need)
    plan = plan_outing(spots, city, args.home, args.wake, args.sleep, args.hours, must, mood)

    if not plan.stops:
        print("Nothing fits between waking up and bedtime. Try waking up earlier, going to bed later, or fewer must-haves.")
        return 1

    print(f"\n{PINK}{BOLD}Your Saturday ✦{RESET}  {DIM}{args.mood}, up at {clock(args.wake)}, "
          f"bed by {clock(args.sleep)}{RESET}")
    for stop in plan.stops:
        free = stop.start - (stop.arrive - stop.drive)  # from the last stop ending to this one starting
        if free >= 30 + stop.drive:
            h, m = divmod(int(free), 60)
            length = (f"{h}h {m}m" if m else f"{h}h") if h else f"{m} min"
            print(f"  {clock(stop.arrive - stop.drive):>8}  {DIM}free time ({length}): nap, journal, wander{RESET}")
        note = f"  {DIM}({stop.spot.note}){RESET}" if stop.spot.note else ""
        print(f"  {clock(stop.start):>8}  {stop.spot.name}{note}")
    print(f"  {clock(half_hour(plan.home_by)):>8}  {sign_off(half_hour(plan.home_by), plan.outside / 60, seed, args.mood)}")
    out = f"{plan.outside / 60:.1f}".rstrip("0").rstrip(".")
    stops = f"{len(plan.stops)} stop{'s' * (len(plan.stops) != 1)}"
    print(f"\n  {DIM}{stops} · {out} hours out · {plan.driving} min of driving · seed {seed}{RESET}")
    print(f"  {DIM}run it again for a different Saturday ✦{RESET}\n")

    if args.chart:
        from .chart import draw
        print(f"  saved {draw(plan, Path('plan.png'))}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
