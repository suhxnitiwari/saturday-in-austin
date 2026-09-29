"""How a person actually does a Saturday.

A schedule can fit every time window and still be a weird day: Pilates, then a museum,
then dinner, still sweaty. So every kind of stop carries a little metadata (Kind), and
the planner asks two questions about every move from one stop to the next:

    step(state, spot, start, out)  is this move allowed? returns the new state, or None
    cost(prev, spot, start, travel)  how much do I like it? lower is better

The state is five small numbers about the person, not the place:

    sweat   2 = just worked out, 1 = grabbed a coffee after, 0 = showered and fine
    full    2 = just ate a real meal, counting down one per stop after
    change  1 = just went home to change, so the next stop had better be worth it
    coffee  1 = just had brunch, which came with coffee; 2 = had dinner, so no more coffee today
    drinks  1 = there have been cocktails today, so no more workouts

explain() looks at a finished plan and says which of these rules shaped it.
"""
from __future__ import annotations

from dataclasses import dataclass

DAY = 24 * 60


@dataclass(frozen=True)
class Kind:
    food: str = ""            # "full" (a real meal), "small" (coffee, a treat) or "" (not food)
    workout: bool = False     # leaves you needing a shower
    sweaty_ok: bool = False   # fine to walk into in workout clothes (coffee, a smoothie)
    reset: str = ""           # "shower" or "change": a block at home, not a place
    close: int = DAY + 120    # the latest a visit can end
    prefer: tuple = ()        # the hours it's best at; starting outside them costs a little
    brunch: bool = False      # it's Saturday: brunch in the brunch window gets a bonus
    drinks: bool = False      # mimosas, cocktails: no workout after, for the rest of the day


H = 60
KINDS = {
    "coffee": Kind(food="small", sweaty_ok=True, close=19 * H, prefer=((7 * H, 15 * H),)),
    "smoothie": Kind(food="small", sweaty_ok=True, close=19 * H),
    "brunch": Kind(food="full", close=15 * H, brunch=True, drinks=True),  # with coffee and mimosas
    "lunch": Kind(food="full", close=16 * H),
    "dinner": Kind(food="full", drinks=True),
    "order in": Kind(food="full"),
    "treat": Kind(food="small", close=22 * H),
    "snack": Kind(food="small"),
    "late night": Kind(food="small"),
    "exercise": Kind(workout=True, close=20 * H, prefer=((7 * H, 10 * H + 30),)),  # a Saturday morning class
    "study": Kind(close=22 * H),
    "museum": Kind(close=17 * H + 30),
    "creative": Kind(close=19 * H),
    "shopping": Kind(close=21 * H, prefer=((11 * H, 19 * H),)),
    "market": Kind(close=13 * H + 30, prefer=((8 * H, 11 * H),)),
    "nails": Kind(close=19 * H),
    "spa": Kind(close=19 * H + 30),
    "hike": Kind(close=18 * H, prefer=((7 * H, 11 * H + 30),)),
    "paddle": Kind(close=19 * H + 30, prefer=((8 * H, 12 * H), (16 * H, 19 * H + 30))),
    "swim": Kind(close=19 * H + 30),
    "park": Kind(close=20 * H + 30, prefer=((8 * H, 11 * H + 30), (16 * H, 19 * H + 30))),
    "sunset": Kind(close=21 * H + 30),
    "murals": Kind(close=20 * H),
    "hangout": Kind(drinks=True),
    "game": Kind(),
    "cinema": Kind(),
    "live music": Kind(drinks=True),
    "self care": Kind(),
    "movie": Kind(),
    "show": Kind(),
    "read": Kind(),
    "games": Kind(),
    "reset-shower": Kind(reset="shower"),
    "reset-change": Kind(reset="change"),
}

BRUNCH_HOURS = (9 * H + 30, 13 * H + 30)                   # Saturday brunch o'clock
FAVORITE_BRUNCH = {"Josephine House", "Hillside Farmacy"}  # the two I'd pick first

# what a plan's score is made of: 10 points per point of joy, minus these costs
JOY = 10
DRIVE_COST = 2.5      # per minute in the car: zigzagging across town is expensive
WALK_COST = 1.0       # per minute on foot (walks are already capped at a mile)
OFF_HOURS = 15        # a park at 1 PM in July, a latte at 4:30
BRUNCH_BONUS = 40     # it's Saturday. We're getting brunch
FAVORITE_BONUS = 20   # ...ideally at Josephine House or Hillside Farmacy
AFTER_MEAL_SHOP = 5   # shopping right after brunch or lunch just works
TRANSIT_COST = 1.5    # per minute on the bus (it's free with a UT ID; it just takes a while)
RIDE_TIME = 1.0       # per minute in an Uber...
UBER_DOLLAR = 4       # ...plus every dollar of the fare: cost-efficient means staying put
STOP_COST = 40        # every stop takes a little energy: fewer, better stops beat a packed day
LONG_DAY = 1.0        # per minute out past LONG: nobody needs a 14-hour Saturday
LONG = 8 * 60

# what a dollar costs, by budget: on a student budget, free things win
DOLLAR = {"student": 3.0, "normal": 0.6, "splurge": 0.0}
MODES = ("car", "uber", "transit", "walk")


@dataclass(frozen=True)
class Ways:
    """How you get around and what you want to spend."""
    mode: str = "car"       # car, uber, transit (bus + walk) or walk
    budget: str = "normal"  # student, normal or splurge


def uber_fare(minutes: float) -> float:
    """A rough UberX fare for a ride this long in Austin: a base, per minute, and a minimum."""
    return max(10.0, 4 + 0.8 * minutes) if minutes else 0.0


def travel_cost(minutes: float, ways: "Ways" = None) -> float:
    """What getting somewhere costs the plan, by how you're getting there."""
    mode = (ways or Ways()).mode
    if mode == "uber":
        return minutes * RIDE_TIME + uber_fare(minutes) * UBER_DOLLAR  # 0 minutes = same neighborhood = walk
    return minutes * {"car": DRIVE_COST, "walk": WALK_COST, "transit": TRANSIT_COST}[mode]


EVENING = 16 * H + 30  # changing to go out only makes sense this late
OUT_A_WHILE = 3 * H    # ...after being out at least this long

START = (0, 0, 0, 0, 0)  # (sweat, full, change, coffee, drinks): fresh, hungry-ish, dressed, sober


def kind(spot) -> Kind:
    return KINDS.get(spot.category, Kind())


def step(state: tuple, spot, start: int, out: int):
    """The person after this stop, or None if a person wouldn't do it.
    start is when the stop begins, out is how long they've been out by then."""
    sweat, full, change, coffee, drinks = state
    k = kind(spot)
    if change and not spot.dressy:
        return None  # went home to change for... this?
    if sweat == 2 and not (k.sweaty_ok or k.reset == "shower"):
        return None  # straight from Pilates: coffee, a smoothie or a shower, nothing else
    if sweat == 1 and k.reset != "shower":
        return None  # coffee after Pilates is allowed. Now you shower
    if k.reset == "shower" and not sweat:
        return None  # nothing to shower off
    if k.reset == "change" and (sweat or not late_enough(start, out)):
        return None
    if k.food == "full" and full:
        return None  # you just ate
    if k.food == "small" and not k.sweaty_ok and full == 2:
        return None  # not dessert straight after lunch either; walk it off first
    if k.workout and full == 2:
        return None  # and not Pilates on a full stomach
    if k.workout and drinks:
        return None  # cocktails, then Pilates? Absolutely not
    if spot.category == "coffee" and coffee:
        return None  # brunch came with coffee (give it a minute); after dinner, a latte is tomorrow's problem
    new_sweat = 2 if k.workout else 1 if sweat == 2 and k.sweaty_ok else 0 if k.reset == "shower" else sweat
    new_full = 2 if k.food == "full" else max(0, full - 1)
    return new_sweat, new_full, 1 if k.reset == "change" else 0, 2 if coffee == 2 or spot.category == "dinner" else 1 if k.brunch else 0, 1 if drinks or k.drinks else 0


def can_end(state: tuple) -> bool:
    """Heading home is always fine (that's where the shower is), unless you just changed for nothing."""
    return not state[2]


def valid(spots: list, starts: list = None) -> bool:
    """Does this order of stops follow the rules? (starts default to a lazy afternoon.)"""
    state = START
    for i, spot in enumerate(spots):
        start = starts[i] if starts else 18 * H + 30 * i
        state = step(state, spot, start, OUT_A_WHILE + 30 * i)
        if state is None:
            return False
    return can_end(state)


def _outside(start: int, windows: tuple) -> bool:
    return bool(windows) and not any(a <= start <= b for a, b in windows)


def move_cost(prev, spot, travel: int, ways: Ways = Ways()) -> float:
    """The part of a move's cost that doesn't care what time it is: travel, energy, money, what came before."""
    c = travel_cost(travel, ways) + (0 if kind(spot).reset else STOP_COST) + spot.price * DOLLAR[ways.budget]
    if prev is not None and spot.category == "shopping" and kind(prev).food == "full":
        c -= AFTER_MEAL_SHOP
    return c


def time_cost(spot, start: int) -> float:
    """The part that does: off-hours cost a little, Saturday brunch in brunch hours is a discount."""
    k, c = kind(spot), 0
    if _outside(start, k.prefer):
        c += OFF_HOURS
    if k.brunch and BRUNCH_HOURS[0] <= start <= BRUNCH_HOURS[1]:
        c -= BRUNCH_BONUS + (FAVORITE_BONUS if spot.name in FAVORITE_BRUNCH else 0)
    return c


def cost(prev, spot, start: int, travel: int, ways: Ways = Ways()) -> float:
    """What this move costs the plan. Lower is better."""
    return move_cost(prev, spot, travel, ways) + time_cost(spot, start)


def late_enough(start: int, out: int) -> bool:
    """The only way time matters to step(): is it evening, and have you been out a while?"""
    return start >= EVENING and out >= OUT_A_WHILE


def long_day(minutes_out: float) -> float:
    return LONG_DAY * max(0, minutes_out - LONG)


def resets(home: str) -> list:
    """The two blocks at home the planner can use: a shower after a workout, a change before going out."""
    from .spots import Spot
    return [Spot("Home", home, "reset-shower", 60, 0, frozenset(), "shower + get ready"),
            Spot("Home", home, "reset-change", 45, 3, frozenset(), "change + reset")]  # free, obviously


# ------------------------------------------------------------------ why?

def _workout_word(spot) -> str:
    name = spot.name.lower() + " " + spot.note.lower()
    return "Pilates" if "pilates" in name or "solidcore" in name else "yoga" if "yoga" in name else "a workout"


def explain(stops: list, shortlist: list, zone_of, minutes) -> dict:
    """Which rules shaped this plan, as a few short notes: {stop index: note}.

    stops are the plan's Stop objects in order; zone_of(spot) gives its neighborhood;
    minutes(a, b) is the drive between two neighborhoods. At most three notes, and only
    for rules that actually changed something.
    """
    notes = {}
    spots = [s.spot for s in stops]
    for i, s in enumerate(spots):
        k, before = kind(s), spots[i - 1] if i else None
        if k.brunch and BRUNCH_HOURS[0] <= stops[i].start <= BRUNCH_HOURS[1]:
            notes.setdefault(i, "It's Saturday. We're getting brunch.")
        elif before is not None and kind(before).workout and k.sweaty_ok:
            thing = "Coffee" if s.category == "coffee" else "A smoothie"
            notes.setdefault(i, f"{thing} after {_workout_word(before)} is allowed.")
        elif k.reset == "shower":
            notes.setdefault(i, "You need to shower before we continue.")
        elif k.reset == "change":
            notes.setdefault(i, "Going home to change first. You'll thank me.")
        elif (before is not None and kind(before).brunch and any(c.category == "coffee" and c not in spots for c in shortlist)):
            notes.setdefault(i, "You almost certainly just had coffee. Give it a minute.")
        elif (before is not None and kind(before).food == "full" and not k.food and before.category != "dinner"
              and any(kind(c).food == "full" and c not in spots for c in shortlist)):
            notes.setdefault(i, "You just ate. I'm not giving you another restaurant.")

    # staying put: three stops in a row in one neighborhood
    run = 1
    for i in range(1, len(spots)):
        same = zone_of(spots[i]) == zone_of(spots[i - 1]) and not kind(spots[i]).reset
        run = run + 1 if same else 1
        if run == 3 and i not in notes:
            notes[i] = f"We're already in {_place(zone_of(spots[i]))}, so we're staying over here for a bit."
            break

    # the big detour I didn't take
    zones = [zone_of(s) for s in spots if not kind(s).reset]
    if zones:
        home_base = max(set(zones), key=zones.count)
        # only when it really happened: a great spot far away lost to a closer one of the same kind
        far = [c for c in shortlist if c not in spots and zone_of(c) not in zones
               and minutes(home_base, zone_of(c)) >= 20
               and any(p.slot == c.slot and p.joy <= c.joy for p in spots)]
        if far and 0 not in notes:
            notes[0] = f"Absolutely not driving to {_place(zone_of(far[0]))} and immediately coming back to {_place(home_base)}."

    once, seen = {}, set()
    for i, note in sorted(notes.items()):  # each note once: it's funny the first time
        if note not in seen:
            once[i] = note
            seen.add(note)
    return dict(list(once.items())[:3])


PLACE_NAMES = {"Domain": "the Domain", "Campus": "UT campus", "Northwest": "North Austin",
               "Southwest": "Southwest Austin", "Hill Country": "the Hill Country", "Southeast": "Southeast Austin"}


def _place(zone: str) -> str:
    return PLACE_NAMES.get(zone, zone)
