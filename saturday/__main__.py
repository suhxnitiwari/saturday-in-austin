"""Saturday in Austin ✦  Tell me when you're free. I'll figure out what we're doing.

    python -m saturday                                  a surprise Saturday, different every time
    python -m saturday --start 9 --back 23 --hours 6    out the door at 9, home by 11, six hours out
    python -m saturday --mood treat-myself --include "Éma" --chart
    python -m saturday --seed 325                       Saturday #325 again
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from . import rules
from .city import City
from .planner import BUFFER, plan_outing, reachable, shortlist, transit, walking
from .sass import judge, sign_off
from .spots import AREAS, MOODS, NOT_THESE, RULES, Guide, UnknownSpotError, half_hour, load, shelf_note


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


def hours_arg(text: str):
    return None if text == "all" else float(text)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="saturday", description="Tell me when you're free. I'll figure out what we're doing.")
    p.add_argument("--start", type=parse_time, default=9 * 60, metavar="TIME", help="when you're ready to go (default 9:00)")
    p.add_argument("--back", type=parse_time, default=23 * 60, metavar="TIME", help="when you want to be home (default 23:00)")
    p.add_argument("--hours", type=hours_arg, default=None, help="hours you actually want to be out, or 'all' (default)")
    p.add_argument("--mood", choices=MOODS, default="everything")
    p.add_argument("--home", default="West Campus", help="where you start and end (default West Campus)")
    p.add_argument("--include", action="append", default=[], metavar="SPOT", help="a spot you have to go to")
    p.add_argument("--skip", action="append", default=[], metavar="SPOT", help="a spot to leave out")
    p.add_argument("--not", dest="not_these", action="append", default=[], choices=NOT_THESE,
                   help="a kind of thing to leave out")
    p.add_argument("--walk", action="store_true", help="no car: no walk over a mile (same as --travel walk)")
    p.add_argument("--travel", choices=rules.MODES, default=None, help="car, uber (cost-efficient), transit (bus + walk) or walk")
    p.add_argument("--budget", choices=list(rules.DOLLAR), default="normal", help="student, normal or splurge")
    p.add_argument("--rainy", action="store_true", help="a rainy day: indoor spots only")
    p.add_argument("--area", choices=AREAS, default="anywhere", help="stay in one neighborhood")
    p.add_argument("--chart", action="store_true", help="also save the day as plan.png")
    p.add_argument("--seed", type=int, help="get a Saturday back by its number")
    args = p.parse_args(argv)

    city = City()
    if args.home not in city.roads:
        print(f"I don't know the neighborhood '{args.home}'. Try one of: {', '.join(sorted(city.roads))}")
        return 1
    guide = Guide(load(), args.home)
    mood = RULES[args.mood] if args.area == "anywhere" else RULES[args.mood].relaxed()
    area = AREAS[args.area][0] if args.area != "anywhere" else None
    mode = args.travel or ("walk" if args.walk else "car")
    ways = rules.Ways(mode, args.budget)
    for note in judge(args.start, args.back, args.hours, args.mood, mode == "walk", args.rainy, area, mode, args.budget):
        print(f"\n  {PINK}{note}{RESET}")
    try:
        must = [guide.find(name) for name in args.include]
        skip = {guide.find(name).name for name in args.skip}
    except UnknownSpotError as err:
        print(err.args[0])
        return 1

    seed = args.seed if args.seed is not None else random.randrange(1000, 10000)
    rng = random.Random(seed)
    pool = guide.pool(args.mood, must, skip, args.rainy, area=args.area, not_these=args.not_these)
    if mode in ("walk", "transit"):
        staples = {"midday meal", "dinner"} | ({"coffee"} if "coffee" in mood.need + mood.want else set())
        zones = AREAS[args.area][1]
        fill = [s for s in guide.spots if s.slot in staples and s.name not in guide.home_spots and s.name not in skip
                and (zones is None or s.zone in zones)]
        if mode == "walk":
            city, pool = walking(pool, args.home, fill)
        else:
            city, pool = transit(pool, args.home, fill, random.Random(seed), must)
        must = [s for s in pool if s.name in {m.name for m in must}]
    window = ((args.back - args.start) % (24 * 60) or 24 * 60) if args.hours is None else args.hours * 60
    pool = reachable(pool, getattr(city, "reach", city), args.home, window, must)
    far = getattr(city, "reach", city)
    back = args.back if args.back > args.start else args.back + 24 * 60
    brunch_time = args.start <= rules.BRUNCH_HOURS[1] and back >= rules.BRUNCH_HOURS[0] + 90
    spots = shortlist(pool, must, rng, caps=mood.caps, need=mood.need,
                      distance=lambda s: min(far.minutes(args.home, s.zone), 300) * {"walk": 3, "transit": 2, "uber": 2}.get(mode, 1),
                      favor=("brunch",) if brunch_time else ())
    plan = plan_outing(spots, city, args.home, args.start, args.back, args.hours, must, mood, ways=ways)
    if mode in ("walk", "transit") and not plan.stops:  # a missing coffee shop shouldn't mean no day at all
        plan = plan_outing(spots, city, args.home, args.start, args.back, args.hours, must, mood.relaxed(), ways=ways)

    if not plan.stops:
        print("Nothing fits. Try a longer day, a different mood, or fewer must-haves.")
        return 1

    zone = {s.name: s.zone for s in guide.spots}
    why = rules.explain(plan.stops, spots, lambda s: args.home if rules.kind(s).reset else zone.get(s.name, s.zone),
                        City().minutes)
    print(f"\n{PINK}{BOLD}Your Saturday ✦{RESET}  {DIM}{args.mood}, out from {clock(args.start)}, "
          f"home by {clock(args.back)}{RESET}")
    for i, stop in enumerate(plan.stops):
        gap = stop.start - (stop.arrive - stop.drive) - stop.drive - BUFFER
        if i and gap >= 30:
            h, m = divmod(int(gap), 60)
            length = (f"{h}h {m}m" if m else f"{h}h") if h else f"{m} min"
            print(f"  {clock(stop.arrive - stop.drive):>8}  {DIM}free time ({length}): nap, journal, wander{RESET}")
        if rules.kind(stop.spot).reset:
            print(f"  {clock(stop.start):>8}  {DIM}Home: {stop.spot.note}{RESET}")
        else:
            picked = shelf_note(stop.spot, rng)
            note = f"  {DIM}({picked}){RESET}" if picked else ""
            print(f"  {clock(stop.start):>8}  {stop.spot.name}{note}")
        if i in why:
            print(f"  {'':>8}  {PINK}{why[i]}{RESET}")
    movie = any(s.spot.slot == "movie" for s in plan.stops)
    ending = sign_off(half_hour(plan.home_by), plan.outside / 60, seed, args.mood, movie)
    print(f"  {clock(half_hour(plan.home_by)):>8}  {ending}")
    out = f"{plan.outside / 60:.1f}".rstrip("0").rstrip(".")
    n = len(plan.places)
    travel = {"walk": "walking", "transit": "bus and walking", "uber": "in Ubers"}.get(mode, "driving")
    print(f"\n  {DIM}{n} stop{'s' * (n != 1)} · {out} hours out · {plan.driving} min {travel} · "
          f"about ${plan.dollars:.0f} · Saturday #{seed}{RESET}")
    print(f"  {DIM}run it again for a different Saturday, or --seed {seed} to get this one back ✦{RESET}\n")

    if args.chart:
        from .chart import draw
        print(f"  saved {draw(plan, Path('plan.png'))}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
