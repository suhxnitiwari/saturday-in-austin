import random

import pytest

from saturday.__main__ import clock, main, parse_time
from saturday.city import City
from saturday.planner import best_joy_by_search, meals, plan_day, plan_outing, schedule, shortlist
from saturday.spots import MOODS, RULES, WINDOWS, Guide, UnknownSpotError, load

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


def test_every_spot_is_reachable(city, guide):  # day-in spots are at home
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
    assert "Barton Springs Pool" in {s.name for s in guide.for_mood("adventurous")}
    assert "Movie night" not in {s.name for s in guide.for_mood("everything")}  # a surprise day is a day out
    assert guide.find("Movie night").zone == "West Campus"  # day-in spots are wherever home is
    with pytest.raises(ValueError):
        guide.for_mood("grumpy")


def test_there_are_plenty_of_spots(guide):
    assert len(guide.spots) >= 100
    for mood in MOODS:
        assert len(guide.for_mood(mood)) >= 8, mood


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


@pytest.mark.parametrize("mood", MOODS)
def test_every_mood_makes_its_own_kind_of_day(city, guide, mood):
    rules = RULES[mood]
    for seed in range(8):
        spots = shortlist(guide.pool(mood), [], random.Random(seed), caps=rules.caps, need=rules.need)
        plan = plan_outing(spots, city, "West Campus", 8 * 60, 23 * 60 + 30, 10, mood=rules)
        stops = [s.spot for s in plan.stops]
        assert stops, "there's always something to do"
        assert all(mood == "everything" or mood in s.moods or s.name == "Medici" for s in stops)
        for need in rules.need + rules.want:  # a 10-hour day has room for everything
            assert any(need in (s.category, s.slot) for s in stops), f"{mood} always has {need}"
        for slot in {s.slot for s in stops}:
            assert sum(s.slot == slot for s in stops) <= rules.caps.get(slot, 1)
        assert all(a.slot != b.slot for a, b in zip(stops, stops[1:])), "never the same thing twice in a row"
        for meal in meals(plan.leave, plan.home_by):
            assert any(s.slot == meal for s in stops), f"out through mealtime means a real {meal}"
        for stop in plan.stops:
            earliest, latest = WINDOWS[stop.spot.category]
            assert earliest <= stop.start <= latest


def test_treat_yourself_is_a_domain_day(city, guide):
    rules = RULES["treat-yourself"]
    for seed in range(8):
        spots = shortlist(guide.pool("treat-yourself"), [], random.Random(seed), caps=rules.caps, need=rules.need)
        plan = plan_outing(spots, city, "West Campus", 9 * 60, 23 * 60, 8, mood=rules)
        zones = [s.spot.zone for s in plan.stops]
        assert zones.count("Domain") >= len(zones) - 1  # everything at the Domain, except maybe Milano


def test_day_in_ends_with_pizza_and_a_movie(city, guide):
    rules = RULES["day-in"]
    spots = shortlist(guide.pool("day-in"), [], random.Random(3), caps=rules.caps, need=rules.need)
    plan = plan_outing(spots, city, "West Campus", 9 * 60, 23 * 60 + 30, 12, mood=rules)
    kinds = [s.spot.category for s in plan.stops]
    assert "order in" in kinds and kinds.index("order in") < kinds.index("movie") if "movie" in kinds else True


def test_adventurous_takes_breaks(city, guide):
    rules = RULES["adventurous"]
    for seed in range(12):
        spots = shortlist(guide.pool("adventurous"), [], random.Random(seed), caps=rules.caps, need=rules.need)
        plan = plan_outing(spots, city, "West Campus", 7 * 60, 23 * 60, 12, mood=rules)
        slots = [s.spot.slot for s in plan.stops]
        assert slots.count("outdoor") <= 2
        assert ("outdoor", "outdoor") not in zip(slots, slots[1:])


def test_capped_slots_match_brute_force(city, guide):
    """The café-hopping and two-adventure rules, checked against trying every order."""
    rng = random.Random(7)
    for mood in ("productive", "adventurous", "cozy"):
        rules = RULES[mood]
        for _ in range(10):
            spots = rng.sample(guide.pool(mood), 7)
            leave = rng.choice([8, 10, 12]) * 60
            end = leave + rng.choice([4, 7, 10]) * 60
            plan = plan_day(spots, city, "Campus", leave, end, need=(), caps=rules.caps)
            assert plan.joy == best_joy_by_search(spots, city, "Campus", leave, end, need=(), caps=rules.caps)


def test_must_haves_are_included(city, guide):
    must = [guide.find("Clay Pit"), guide.find("7th Street Candle")]
    spots = shortlist(guide.spots, must)
    plan = plan_day(spots, city, "West Campus", TEN_AM, EIGHT_PM, must)
    assert follows_the_rules(plan, city, "West Campus", TEN_AM, EIGHT_PM, must)


def test_brunch_and_lunch_never_both(city, guide):
    spots = shortlist(guide.for_mood("social"), [])
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
    assert main(["--mood", "treat-yourself"]) == 0
    out = capsys.readouterr().out
    assert "Your Saturday" in out and "home" in out and "seed" in out


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
        spots = shortlist(guide.for_mood("everything"), must, need=("coffee",))
        assert len(spots) <= 15 and all(m in spots for m in must)
        assert {"coffee", "midday meal", "dinner"} <= {s.slot for s in spots}  # never skip the essentials


# ---------------------------------------------------------------- wake up, bedtime, hours out

from saturday.planner import GET_READY, WIND_DOWN  # noqa: E402


@pytest.mark.parametrize("wake,sleep,hours", [(8, 23, 6), (10, 24, 10), (7, 22, 3), (9, 1, 12), (11, 20, 2)])
def test_outing_fits_between_waking_up_and_bed(city, guide, wake, sleep, hours):
    wake, sleep = wake * 60, (sleep % 24) * 60
    spots = shortlist(guide.spots, [], random.Random(wake + hours))
    plan = plan_outing(spots, city, "West Campus", wake, sleep, hours)
    bedtime = sleep if sleep > wake else sleep + 24 * 60
    assert plan.stops, "there's always something to do"
    assert plan.leave >= wake + GET_READY
    assert plan.home_by <= bedtime - WIND_DOWN
    assert plan.outside <= hours * 60


def test_no_time_no_plan(city, guide):
    spots = shortlist(guide.spots, [])
    assert plan_outing(spots, city, "West Campus", 22 * 60, 23 * 60, 4).stops == []


def test_web_entry_point_returns_a_plan():
    import json
    from saturday.web import plan_json
    data = json.loads(plan_json("8:00", "23:00", 6, "cozy", 5))
    names = [s["name"] for s in data["stops"] if "name" in s]
    assert data["seed"] == 5 and names and data["hours_out"] <= 6
    assert json.loads(plan_json("8:00", "23:00", 6, "cozy", 5)) == data  # same seed, same plan


# ---------------------------------------------------------------- the sass

from saturday.sass import judge, sign_off  # noqa: E402


def test_sass():
    assert judge(9 * 60, 23 * 60, 8) == []
    assert "not a morning person" in judge(12 * 60, 23 * 60, 8)[0]
    assert "homebody" in judge(9 * 60, 23 * 60, 2)[0]
    assert "even sure about going out" in judge(9 * 60, 23 * 60, 1)[0]
    assert "escaping" in judge(7 * 60, 23 * 60 + 30, 14)[0]
    assert len(judge(12 * 60 + 30, 2 * 60, 14)) == 2
    notes = judge(9 * 60, 12 * 60, 14)  # up at 9, "bed" at noon, 14 hours out
    assert any("Did you mean 12:00 AM" in n for n in notes)
    assert any("not mathing" in n for n in notes) and not any("escaping" in n for n in notes)
    assert not any("mathing" in n for n in judge(9 * 60, 12 * 60, 1.5))  # 1.5 hours fits
    assert judge(23 * 60, 22 * 60, 14) == [  # up at 11 PM: the only note is the wake-up one
        "Waking up at 11:00 PM?? That's nighttime, vampire. Everything's closed. Did you mean 11:00 AM?"]


def test_sign_off():
    assert "errand" in sign_off(11 * 60, 1, 5)
    assert "couch" in sign_off(15 * 60, 2, 5)
    assert "feet" in sign_off(23 * 60, 14, 5)
    assert sign_off(18 * 60, 6, 5) == sign_off(18 * 60, 6, 5)  # same seed, same ending
    assert "happy" not in sign_off(18 * 60, 6, 5)
