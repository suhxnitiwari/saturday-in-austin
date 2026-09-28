import random

import pytest

from saturday.__main__ import clock, main, parse_time
from saturday.city import City
from saturday.planner import best_joy_by_search, plan_day, schedule, shortlist
from saturday.spots import WINDOWS, Guide, UnknownSpotError, load

TEN_AM, EIGHT_PM = 10 * 60, 20 * 60


@pytest.fixture(scope="module")
def city():
    return City()


@pytest.fixture(scope="module")
def guide():
    return Guide(load())


# ---------------------------------------------------------------- the city

def test_fastest_drive_takes_the_quicker_road(city):
    assert city.drive("West Campus", "South Congress") == (15, ["West Campus", "Downtown", "South Congress"])
    assert city.drive("Campus", "Campus") == (0, ["Campus"])


def test_every_spot_is_reachable(city, guide):
    for spot in guide.spots:
        assert city.minutes("West Campus", spot.zone) >= 0


def test_unknown_neighborhood(city):
    with pytest.raises(KeyError):
        city.drive("Campus", "Narnia")


# ---------------------------------------------------------------- the spots

def test_lookup_ignores_case_and_suggests_fixes(guide):
    assert guide.find("  medici ").name == "Medici"
    with pytest.raises(UnknownSpotError, match="Did you mean Medici"):
        guide.find("medicci")


def test_moods_filter(guide):
    assert all("productive" in s.moods for s in guide.for_mood("productive"))
    assert len(guide.for_mood("everything")) == len(guide.spots)
    with pytest.raises(ValueError):
        guide.for_mood("grumpy")


def test_windows(guide):
    brunch = guide.find("Josephine House")
    assert brunch.opens_by(8 * 60) == 9 * 60  # early: wait for it
    assert brunch.opens_by(10 * 60) == 10 * 60
    assert brunch.opens_by(13 * 60) is None  # nobody brunches at 1


# ---------------------------------------------------------------- the planner

def follows_the_rules(plan, city, home, leave, end, must=()):
    names = [s.spot.name for s in plan.stops]
    slots = [s.spot.slot for s in plan.stops]
    assert len(slots) == len(set(slots)), "one stop per slot"
    assert any(s.spot.category == "coffee" for s in plan.stops), "always coffee"
    assert all(m.name in names for m in must)
    assert plan.stops[0].start >= leave and plan.home_by <= end
    for stop in plan.stops:
        earliest, latest = WINDOWS[stop.spot.category]
        assert earliest <= stop.start <= latest
    return True


@pytest.mark.parametrize("mood", ["cozy", "creative", "foodie", "productive", "everything"])
def test_every_mood_makes_a_valid_day(city, guide, mood):
    spots = shortlist(guide.for_mood(mood) + [guide.find("Medici")], [])
    plan = plan_day(spots, city, "West Campus", TEN_AM, EIGHT_PM)
    assert follows_the_rules(plan, city, "West Campus", TEN_AM, EIGHT_PM)
    assert plan.stops[-1].spot.category == "dinner"  # a 10-to-8 day always ends with dinner


def test_must_haves_are_included(city, guide):
    must = [guide.find("Clay Pit"), guide.find("7th Street Candle")]
    spots = shortlist(guide.spots, must)
    plan = plan_day(spots, city, "West Campus", TEN_AM, EIGHT_PM, must)
    assert follows_the_rules(plan, city, "West Campus", TEN_AM, EIGHT_PM, must)


def test_brunch_and_lunch_never_both(city, guide):
    spots = shortlist(guide.for_mood("foodie"), [])
    plan = plan_day(spots, city, "West Campus", TEN_AM, EIGHT_PM)
    meals = [s for s in plan.stops if s.spot.category in ("brunch", "lunch")]
    assert len(meals) <= 1


def test_impossible_day_returns_an_empty_plan(city, guide):
    spots = [s for s in guide.spots if s.category != "coffee"][:6]
    assert plan_day(spots, city, "Campus", TEN_AM, EIGHT_PM).stops == []
    assert plan_day(guide.spots[:3], city, "Campus", TEN_AM, TEN_AM + 10).stops == []


def test_planner_finds_the_best_day_every_time(city, guide):
    """Compare against trying every possible order, on 40 random small days."""
    rng = random.Random(2026)
    for _ in range(40):
        spots = rng.sample(guide.spots, 7)
        leave = rng.choice([8, 9, 10, 12]) * 60
        end = leave + rng.choice([3, 5, 8, 11]) * 60
        plan = plan_day(spots, city, "Campus", leave, end)
        assert plan.joy == best_joy_by_search(spots, city, "Campus", leave, end)


def test_schedule_waits_for_windows(city, guide):
    plan = schedule([guide.find("Medici"), guide.find("Numero 28")], city, "West Campus", TEN_AM)
    dinner = plan.stops[1]
    assert dinner.start == 17 * 60 + 30 and dinner.arrive < dinner.start


# ---------------------------------------------------------------- the command line

def test_clock_and_time_parsing():
    assert clock(0) == "12:00 AM" and clock(12 * 60 + 5) == "12:05 PM" and clock(21 * 60) == "9:00 PM"
    assert parse_time("9:30") == 570 and parse_time("14") == 840


def test_cli_runs(capsys):
    assert main(["--mood", "cozy"]) == 0
    out = capsys.readouterr().out
    assert "Your Saturday" in out and "home, happy" in out and "seed" in out


def test_same_seed_same_saturday(capsys):
    main(["--seed", "325"])
    first = capsys.readouterr().out
    main(["--seed", "325"])
    assert capsys.readouterr().out == first


# ---------------------------------------------------------------- the randomness

def test_random_days_are_different_but_always_valid(city, guide):
    days = set()
    for seed in range(60):
        spots = shortlist(guide.spots, [], random.Random(seed))
        plan = plan_day(spots, city, "West Campus", TEN_AM, EIGHT_PM)
        assert follows_the_rules(plan, city, "West Campus", TEN_AM, EIGHT_PM)
        days.add(tuple(s.spot.name for s in plan.stops))
    assert len(days) >= 30  # plenty of variety


def test_every_favorite_gets_its_turn(city, guide):
    """Over many runs, every dinner spot makes the shortlist at least once."""
    seen = set()
    for seed in range(300):
        seen |= {s.name for s in shortlist(guide.spots, [], random.Random(seed))}
    dinners = {s.name for s in guide.spots if s.category == "dinner"}
    assert dinners <= seen


def test_higher_rated_spots_win_more_often(guide):
    wins = {"Numero 28": 0, "Arriba Abajo": 0}
    for seed in range(400):
        names = {s.name for s in shortlist(guide.spots, [], random.Random(seed))}
        for name in wins:
            wins[name] += name in names
    assert wins["Numero 28"] > wins["Arriba Abajo"] > 0


def test_cli_handles_mistakes(capsys):
    assert main(["--include", "medicci"]) == 1
    assert "Did you mean Medici?" in capsys.readouterr().out
    assert main(["--home", "Narnia"]) == 1
    assert main(["--hours", "0.25"]) == 1
    assert "Nothing fits" in capsys.readouterr().out


def test_shortlist_always_fits_the_planner(guide):
    for extra in ([], ["Clay Pit", "7th Street Candle"], ["PCL", "Texas Union", "The Domain"]):
        must = [guide.find(n) for n in extra]
        spots = shortlist(guide.spots, must)
        assert len(spots) <= 15 and all(m in spots for m in must)
        assert {s.slot for s in spots} == {s.slot for s in guide.spots}  # no slot left empty
