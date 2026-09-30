import json
import random

import pytest

from saturday import rules
from saturday.__main__ import clock, main, parse_time
from saturday.city import City
from saturday.planner import best_score_by_search, meals, plan_day, plan_outing, schedule, shortlist, walking
from saturday.sass import judge, sign_off
from saturday.spots import AREAS, MOODS, RULES, SHELF, WINDOWS, Guide, UnknownSpotError, load
from saturday.web import plan_json

TEN_AM, EIGHT_PM = 10 * 60, 20 * 60


@pytest.fixture(scope="module")
def city():
    return City()


@pytest.fixture(scope="module")
def guide():
    return Guide(load())


def day(*args, **kwargs):
    return json.loads(plan_json(*args, **kwargs))


def names(data):
    return [s["name"] for s in data["stops"] if s.get("type") == "stop"]


def minutes_of(label: str) -> int:
    """'1:30 PM' -> minutes after midnight."""
    t, ampm = label.split()
    h, m = map(int, t.split(":"))
    return (h % 12 + (12 if ampm == "PM" else 0)) * 60 + m


# ---------------------------------------------------------------- the map

def test_fastest_drive_takes_the_quicker_road(city):
    assert city.drive("West Campus", "South Congress") == (15, ["West Campus", "Downtown", "South Congress"])
    assert city.drive("Campus / UT Corridor", "Campus / UT Corridor") == (0, ["Campus / UT Corridor"])


def test_every_spot_is_reachable(city, guide):
    for spot in guide.spots:
        assert city.minutes("West Campus", spot.zone) >= 0


def test_unknown_neighborhood(city):
    with pytest.raises(KeyError):
        city.drive("Campus / UT Corridor", "Narnia")


# ---------------------------------------------------------------- the spots

def test_lookup_ignores_case_and_suggests_fixes(guide):
    assert guide.find("  medici ").name == "Medici"
    with pytest.raises(UnknownSpotError, match="Did you mean Medici"):
        guide.find("medicci")


def test_moods(guide):
    assert all("productive" in s.moods for s in guide.for_mood("productive"))
    assert "Barton Springs Pool" in {s.name for s in guide.for_mood("outside")}
    assert "Movie night" not in {s.name for s in guide.for_mood("everything")}  # a surprise day is a day out
    assert guide.find("Movie night").zone == "West Campus"  # day-in spots are wherever home is
    with pytest.raises(ValueError):
        guide.for_mood("grumpy")


def test_there_are_plenty_of_spots(guide):
    assert len(guide.spots) >= 175  # curated, not everything: but always enough for any mood
    for mood in MOODS:
        assert len(guide.for_mood(mood)) >= 8, mood


def test_black_fox_is_coffee_not_brunch(guide):
    assert guide.find("Black Fox").category == "coffee"
    assert {"Josephine House", "Hillside Farmacy"} <= {s.name for s in guide.spots if s.category == "brunch"}


# ---------------------------------------------------------------- being a person (rules.py)

def sequence(guide, *spot_names):
    home = rules.resets("West Campus")
    lookup = {"shower": home[0], "change": home[1]}
    return [lookup.get(n) or guide.find(n) for n in spot_names]


def test_1_pilates_then_coffee_then_shower_is_fine(guide):
    assert rules.valid(sequence(guide, "Prana Wellness Club", "Black Fox", "shower"))


def test_2_pilates_then_a_latte_then_shower_is_fine(guide):
    assert rules.valid(sequence(guide, "Prana Wellness Club", "Medici", "shower"))


def test_3_pilates_then_shower_is_fine(guide):
    assert rules.valid(sequence(guide, "Prana Wellness Club", "shower", "Josephine House"),
                       starts=[9 * 60, 10 * 60, 11 * 60 + 30])


def test_4_pilates_then_shopping_is_not(guide):
    assert not rules.valid(sequence(guide, "Prana Wellness Club", "South Congress", "shower"))


def test_5_pilates_coffee_shopping_is_not(guide):
    assert not rules.valid(sequence(guide, "Prana Wellness Club", "Black Fox", "South Congress", "shower"))


def test_6_brunch_then_lunch_is_not(guide):
    assert not rules.valid(sequence(guide, "Josephine House", "Veracruz"))
    assert not rules.valid(sequence(guide, "Josephine House", "Black Fox", "Veracruz"))  # a latte isn't a palate reset
    assert rules.valid(sequence(guide, "Josephine House", "BookPeople", "Blanton Museum of Art", "Veracruz"))
    assert not rules.valid(sequence(guide, "Veracruz", "Dolce Neve"))  # not dessert straight after lunch
    assert not rules.valid(sequence(guide, "Paperboy", "Austin Bouldering Project"))  # not climbing on a full stomach


def test_7_no_car_never_walks_across_town(guide):
    city, _ = walking(guide.spots, "West Campus")
    assert city.minutes("South Congress", "The Domain / Rock Rose") == city.TOO_FAR
    for seed in range(8):
        data = day("9:00", "23:00", 8, "everything", seed, walk=True)
        stops = ["West Campus"] + [s["name"] if s["type"] == "stop" else "West Campus"
                                   for s in data["stops"] if s["type"] != "free"] + ["West Campus"]
        assert len(stops) > 2 and all(city.reach.miles(a, b) <= 1.0001 for a, b in zip(stops, stops[1:]))


def test_7_driving_zigzags_cost_more(guide, city):
    soco, domain, soco2 = guide.find("South Congress"), guide.find("Éma"), guide.find("Jo's Coffee")
    zigzag = schedule([soco, domain, soco2], city, "West Campus", 10 * 60)
    stay = schedule([soco, soco2], city, "West Campus", 10 * 60)
    assert zigzag.cost - stay.cost > rules.JOY * domain.joy  # the Domain isn't worth the round trip


def test_8_saturday_brunch_favorites_win(guide):
    josephine, snooze = guide.find("Josephine House"), guide.find("June's All Day")
    assert josephine.joy == snooze.joy
    assert rules.cost(None, josephine, 10 * 60 + 30, 0) < rules.cost(None, snooze, 10 * 60 + 30, 0)
    assert rules.cost(None, snooze, 10 * 60 + 30, 0) < rules.cost(None, guide.find("Veracruz"), 12 * 60, 0)
    picks = {"Josephine House": 0, "June's All Day": 0}
    brunches = [s for s in guide.spots if s.category == "brunch"]
    for seed in range(300):
        chosen = {s.name for s in shortlist(brunches, [], random.Random(seed))}
        for name in picks:
            picks[name] += name in chosen
    assert picks["Josephine House"] > 1.5 * picks["June's All Day"]
    brunched = sum(any(s["category"] == "brunch" for s in day("9:00", "18:00", "all", "everything", seed)["stops"])
                   for seed in range(20))
    assert brunched >= 16  # a Saturday morning out is a brunch morning


def test_9_workout_then_brunch_allows_coffee_not_breakfast(guide):
    assert rules.valid(sequence(guide, "Prana Wellness Club", "Black Fox", "shower", "Josephine House"),
                       starts=[8 * 60, 9 * 60, 9 * 60 + 30, 11 * 60])
    assert not rules.valid(sequence(guide, "Prana Wellness Club", "shower", "Kerbey Lane Cafe", "Josephine House"),
                           starts=[8 * 60, 9 * 60, 10 * 60, 11 * 60 + 30])


def test_10_never_outside_opening_hours(guide):
    brunch = guide.find("Josephine House")
    assert brunch.opens_by(8 * 60) == 9 * 60  # early: wait for it
    assert brunch.opens_by(13 * 60) is None   # nobody brunches at 1
    assert plan_day([brunch], City(), "West Campus", 14 * 60, 20 * 60, need=()).stops == []
    for seed in range(30):
        for mood in ("everything", "foodie", "creative"):
            for stop in day("8:00", "23:30", "all", mood, seed)["stops"]:
                if stop["type"] == "free":
                    continue
                start = minutes_of(stop["time"])
                earliest, latest = WINDOWS[stop["category"]]
                assert earliest <= start <= latest, stop
                assert start + stop["minutes"] <= rules.KINDS[stop["category"]].close, stop


def test_no_coffee_right_after_brunch(guide):
    brunch, coffee = guide.find("Josephine House"), guide.find("Black Fox")
    assert not rules.valid([brunch, coffee], [10 * 60, 12 * 60])  # it came with coffee. Give it a minute
    assert rules.valid([brunch, guide.find("BookPeople"), coffee], [10 * 60, 12 * 60, 13 * 60 + 30])
    assert rules.valid([coffee, brunch], [9 * 60, 10 * 60])


def test_no_coffee_after_dinner(guide):
    dinner, coffee = guide.find("Uchi"), guide.find("Black Fox")
    assert not rules.valid([dinner, coffee], [16 * 60 + 30, 18 * 60])  # a latte after dinner is tomorrow's problem
    assert not rules.valid([dinner, guide.find("BookPeople"), coffee], [16 * 60, 17 * 60 + 30, 18 * 60 + 30])


def test_after_a_workout_only_coffee_or_a_smoothie(guide):
    pilates = guide.find("Prana Wellness Club")
    for nice in ("Aba", "Josephine House", "BookPeople", "Blanton Museum of Art"):
        assert not rules.valid([pilates, guide.find(nice)], [9 * 60, 10 * 60 + 30])  # a shower is missing from this story
        assert not rules.valid([pilates, guide.find("Black Fox"), guide.find(nice)], [9 * 60, 10 * 60, 11 * 60])
    assert rules.valid([pilates, guide.find("Medici"), rules.resets("West Campus")[0], guide.find("Aba")],
                       [8 * 60, 9 * 60, 10 * 60, 17 * 60])

def test_no_workout_after_cocktails(guide):
    pilates = guide.find("Prana Wellness Club")
    for drinks in ("Josephine House", "Cidercade"):
        assert not rules.valid([guide.find(drinks), guide.find("BookPeople"), guide.find("Blanton Museum of Art"), pilates],
                               [10 * 60, 13 * 60, 14 * 60, 17 * 60])  # absolutely not
    assert rules.valid([pilates, rules.resets("West Campus")[0], guide.find("Josephine House")], [8 * 60, 9 * 60 + 30, 11 * 60])


def test_planned_days_skip_coffee_after_brunch_and_pilates_after_drinks():
    for seed in range(25):
        for mood in ("everything", "slow", "social"):
            kinds = [s["category"] for s in day("8:00", "23:00", "all", mood, seed)["stops"] if s["type"] != "free"]
            for i, k in enumerate(kinds[1:], 1):
                assert not (k == "coffee" and kinds[i - 1] == "brunch")
                assert not (k == "exercise" and any(rules.KINDS[x].drinks for x in kinds[:i]))

def test_the_person_state_moves_like_a_person(guide):
    pilates, coffee, lunch = guide.find("Prana Wellness Club"), guide.find("Black Fox"), guide.find("Veracruz")
    s = rules.step(rules.START, pilates, 9 * 60, 0)
    assert s[0] == 2                                   # sweaty
    s = rules.step(s, coffee, 10 * 60, 60)
    assert s[0] == 1                                   # coffee after Pilates is allowed...
    assert rules.step(s, lunch, 11 * 60 + 30, 150) is None  # ...but now you shower
    change = rules.resets("West Campus")[1]
    assert rules.step(rules.START, change, 18 * 60, 5 * 60) == (0, 0, 1, 0, 0)
    assert not rules.can_end((0, 0, 1, 0, 0))                # changing for nothing
    assert not rules.valid([change, guide.find("Pizza Press")])  # not dressing up for Pizza Press


def test_planned_days_follow_the_person_rules():
    for seed in range(25):
        for mood in ("productive", "outside", "everything"):
            data = day("8:00", "23:00", "all", mood, seed)
            kinds = [s["category"] for s in data["stops"] if s["type"] != "free"]
            for i, k in enumerate(kinds):
                after = kinds[i + 1:i + 3]
                if k == "exercise" and after:
                    assert after[0] in ("coffee", "smoothie", "reset-shower")
                    if after[0] != "reset-shower" and len(after) > 1:
                        assert after[1] == "reset-shower"
                if k == "reset-change":
                    assert i + 1 < len(kinds)


def test_why_notes_are_few_and_real():
    seen = set()
    for seed in range(30):
        data = day("9:00", "22:00", "all", "everything", seed)
        notes = [s["why"] for s in data["stops"] if s.get("why")]
        assert len(notes) <= 3 and len(set(notes)) == len(notes)
        seen |= set(notes)
        for s in data["stops"]:
            if s.get("why") == "It's Saturday. We're getting brunch.":
                assert s["category"] == "brunch"
    assert "It's Saturday. We're getting brunch." in seen


# ---------------------------------------------------------------- the planner

@pytest.mark.parametrize("mood", MOODS)
def test_every_mood_makes_its_own_kind_of_day(city, guide, mood):
    rules_ = RULES[mood]
    for seed in range(6):
        spots = shortlist(guide.pool(mood), [], random.Random(seed), caps=rules_.caps, need=rules_.need, favor=rules_.want)
        plan = plan_outing(spots, city, "West Campus", 8 * 60, 23 * 60 + 30, 10, mood=rules_)
        stops = [s.spot for s in plan.places]
        assert stops, "there's always something to do"
        assert all(mood == "everything" or mood in s.moods or s.name == "Medici" for s in stops)
        for need in rules_.need + rules_.want:  # a 10-hour day has room for everything
            assert any(need in (s.category, s.slot) for s in stops), f"{mood} always has {need}"
        for slot in {s.slot for s in stops}:
            assert sum(s.slot == slot for s in stops) <= rules_.caps.get(slot, 1)
        every = [s.spot for s in plan.stops]
        assert all(a.slot != b.slot for a, b in zip(every, every[1:])), "never the same thing twice in a row"
        for meal in meals(plan.leave, plan.home_by):
            assert any(s.slot == meal for s in stops), f"out through mealtime means a real {meal}"


def matches_brute_force(plan, best):
    return not plan.stops if best is None else plan.score == pytest.approx(best)


def test_planner_finds_the_best_day_every_time(city, guide):
    """Compare against trying every possible order, with every rule, on 40 random small days."""
    rng = random.Random(2026)
    pool = [s for s in guide.spots if s.name not in guide.home_spots]
    for _ in range(40):
        spots = rng.sample(pool, 6) + [guide.find("Prana Wellness Club")] + rules.resets("Campus / UT Corridor")[:1]
        leave = rng.choice([8, 9, 10, 12]) * 60
        end = leave + rng.choice([3, 5, 8, 11]) * 60
        plan = plan_day(spots, city, "Campus / UT Corridor", leave, end, need=())
        assert matches_brute_force(plan, best_score_by_search(spots, city, "Campus / UT Corridor", leave, end, need=()))


def test_capped_slots_match_brute_force(city, guide):
    rng = random.Random(7)
    for mood in ("productive", "outside", "creative"):
        caps = RULES[mood].caps
        for _ in range(8):
            spots = rng.sample(guide.pool(mood), 7)
            leave = rng.choice([8, 10, 12]) * 60
            end = leave + rng.choice([4, 7, 10]) * 60
            plan = plan_day(spots, city, "Campus / UT Corridor", leave, end, need=(), caps=caps)
            assert matches_brute_force(plan, best_score_by_search(spots, city, "Campus / UT Corridor", leave, end, need=(), caps=caps))


def test_must_haves_are_included():
    assert "Peter Pan Mini-Golf" in names(day("9:00", "23:00", "all", "everything", 3, include="Peter Pan Mini-Golf"))


def test_absolutely_not():
    for seed in range(8):
        assert not any(s.get("category") == "exercise"
                       for s in day("8:00", "22:00", "all", "productive", seed, exclude="workouts")["stops"])
        assert "Medici" not in names(day("8:00", "22:00", "all", "productive", seed, exclude="Medici"))


def test_impossible_day_returns_an_empty_plan(city, guide):
    spots = [s for s in guide.spots if s.category != "coffee"][:6]
    assert plan_day(spots, city, "Campus / UT Corridor", TEN_AM, EIGHT_PM, need=("coffee",)).stops == []
    assert plan_day(guide.spots[:3], city, "Campus / UT Corridor", TEN_AM, TEN_AM + 10).stops == []


def test_schedule_waits_for_windows(city, guide):
    plan = schedule([guide.find("Medici"), guide.find("Uchi")], city, "West Campus", TEN_AM)
    dinner = plan.stops[1]
    assert dinner.start == 17 * 60 + 30 and dinner.arrive < dinner.start


@pytest.mark.parametrize("start,end,hours", [(8, 23, 6), (10, 24, 10), (7, 22, 3), (9, 1, None), (11, 20, 2)])
def test_outing_fits_between_start_and_home(city, guide, start, end, hours):
    start, end = start * 60, (end % 24) * 60
    spots = shortlist(guide.for_mood("everything"), [], random.Random(start), need=("coffee",))
    plan = plan_outing(spots, city, "West Campus", start, end, hours)
    home_by = end if end > start else end + 24 * 60
    assert plan.stops, "there's always something to do"
    assert plan.leave >= start and plan.home_by <= home_by
    assert hours is None or plan.outside <= hours * 60


def test_all_day_isnt_a_marathon():
    lengths = [day("8:00", "23:30", "all", "everything", seed)["stats"]["hours_out"] for seed in range(15)]
    assert max(lengths) <= 12.5 and sum(lengths) / len(lengths) <= 11


def test_no_time_no_plan(city, guide):
    spots = shortlist(guide.spots, [])
    assert plan_outing(spots, city, "West Campus", 22 * 60, 22 * 60 + 30, 4).stops == []


# ---------------------------------------------------------------- moods, filters, neighborhoods

def test_treat_myself_is_a_domain_day():
    for seed in range(8):
        stops = [s for s in day("9:00", "23:00", 8, "treat-myself", seed)["stops"] if s["type"] == "stop"]
        wheres = [s["where"] for s in stops]
        assert stops and wheres.count("the Domain") >= len(wheres) - 1  # all at the Domain, except maybe Milano


def test_day_in_is_food_and_a_movie_at_home():
    data = day("9:00", "23:00", 3, "day-in", 3)
    kinds = [s["category"] for s in data["stops"] if s["type"] == "stop"]
    assert "order in" in kinds and "movie" in kinds and kinds.index("order in") < kinds.index("movie")
    assert data["driving"] == 0
    movie = next(s for s in data["stops"] if s.get("category") == "movie")
    assert movie["note"] in SHELF["movie"]


@pytest.mark.parametrize("start,end,hours", [(7, 10, 1.5), (8, 11, 3), (7, 23, 3), (20, 23, 2)])
def test_a_day_in_always_has_something_to_do(start, end, hours):
    data = day(f"{start}:00", f"{end}:00", hours, "day-in", 1)
    assert data["stops"] and data["driving"] == 0 or start >= 18


def test_rainy_days_stay_inside():
    from saturday.spots import OUTDOORS
    for seed in range(6):
        data = day("8:00", "23:00", 10, "outside", seed, rainy=True)
        assert data["stops"] and not any(s.get("category") in OUTDOORS for s in data["stops"])


@pytest.mark.parametrize("area", ["ut", "downtown", "soco", "domain", "east", "mueller"])
def test_neighborhood_days_stay_in_the_neighborhood(guide, area):
    zones = AREAS[area][1]
    for seed in range(4):
        found = names(day("9:00", "23:00", 8, "everything", seed, area=area))
        assert found and all(guide.find(n).zone in zones for n in found)


@pytest.mark.parametrize("seed", range(6))
def test_one_hour_still_gets_a_plan(seed):
    assert day("9:00", "23:00", 1, "everything", seed)["stops"]


# ---------------------------------------------------------------- the website

def test_web_day_has_everything_the_page_draws():
    data = day("8:00", "23:00", 6, "slow", 5)
    assert data["seed"] == 5 and data["stops"] and data["stats"]["stops"] >= 1
    assert {"type", "time", "name", "where", "minutes", "travel", "why"} <= set(data["stops"][-1])
    assert day("8:00", "23:00", 6, "slow", 5) == data  # same seed, same Saturday


# ---------------------------------------------------------------- the lottery

def test_random_days_are_different():
    days = {tuple(names(day("9:00", "22:00", "all", "everything", seed))) for seed in range(30)}
    assert len(days) >= 20


def test_every_favorite_gets_its_turn(guide):
    seen = set()
    for seed in range(3000):  # lots of dinners now, so it takes a few thousand Saturdays
        seen |= {s.name for s in shortlist(guide.spots, [], random.Random(seed))}
    assert {s.name for s in guide.spots if s.category == "dinner"} <= seen


def test_higher_rated_spots_win_more_often(guide):
    wins = {"Numero 28": 0, "Arriba Abajo": 0}
    for seed in range(3000):  # the list is long now, so it takes a few thousand Saturdays to see the odds
        chosen = {s.name for s in shortlist(guide.spots, [], random.Random(seed))}
        for name in wins:
            wins[name] += name in chosen
    assert wins["Numero 28"] > wins["Arriba Abajo"] > 0


def test_nearby_spots_win_more_often(guide, city):
    near, far = guide.find("Veracruz"), guide.find("Tacodeli")
    assert near.joy == far.joy
    picks = {near.name: 0, far.name: 0}
    for seed in range(400):
        chosen = {s.name for s in shortlist([near, far, guide.find("Chi'Lantro")], [], random.Random(seed), per_slot=1,
                                            distance=lambda s: city.minutes("East Austin", s.zone))}
        for name in picks:
            picks[name] += name in chosen
    assert picks[near.name] > picks[far.name]


def test_shortlist_always_fits_the_planner(guide):
    for extra in ([], ["Clay Pit Contemporary Indian Cuisine", "7th Street Candle Co."], ["Perry-Castañeda Library (PCL)", "Life Science Library", "Éma"]):
        must = [guide.find(n) for n in extra]
        spots = shortlist(guide.for_mood("everything"), must, need=("coffee",))
        assert len(spots) <= 12 and all(m in spots for m in must)
        assert {"coffee", "midday meal", "dinner"} <= {s.slot for s in spots}


# ---------------------------------------------------------------- the command line

def test_clock_and_time_parsing():
    assert clock(0) == "12:00 AM" and clock(12 * 60 + 5) == "12:05 PM" and clock(21 * 60) == "9:00 PM"
    assert parse_time("9:30") == 570 and parse_time("14") == 840


def test_cli_runs(capsys):
    assert main(["--mood", "treat-myself"]) == 0
    out = capsys.readouterr().out
    assert "Your Saturday" in out and "home" in out and "Saturday #" in out


def test_same_seed_same_saturday(capsys):
    main(["--seed", "325"])
    first = capsys.readouterr().out
    main(["--seed", "325"])
    assert capsys.readouterr().out == first


def test_cli_handles_mistakes(capsys):
    assert main(["--include", "medicci"]) == 1
    assert "Did you mean Medici?" in capsys.readouterr().out
    assert main(["--home", "Narnia"]) == 1
    assert main(["--hours", "0.25"]) == 1
    assert "Nothing fits" in capsys.readouterr().out


# ---------------------------------------------------------------- the sass

def test_sass():
    assert judge(9 * 60, 23 * 60, 8) == []
    assert "not a morning person" in judge(12 * 60, 23 * 60, 8)[0]
    four = judge(16 * 60, 23 * 60 + 30, 5)[0]
    assert "4:00 PM" in four and "noon" not in four
    assert "homebody" in judge(9 * 60, 23 * 60, 2)[0]
    assert "even sure about going out" in judge(9 * 60, 23 * 60, 1)[0]
    assert "escaping" in judge(7 * 60, 23 * 60 + 30, 14)[0]
    assert judge(9 * 60, 23 * 60, None) == []  # "all day" isn't a cry for help
    assert any("Did you mean 10:00 PM" in n for n in judge(7 * 60, 10 * 60, 1.5))
    assert "vampire" in judge(23 * 60, 22 * 60, 14)[0]
    assert any("two-hour walk" in n for n in judge(9 * 60, 23 * 60, 6, "treat-myself", walk=True))


def test_sign_off():
    assert "errand" in sign_off(11 * 60, 1, 5)
    assert "couch" in sign_off(15 * 60, 2, 5)
    assert "feet" in sign_off(23 * 60, 14, 5)
    assert sign_off(18 * 60, 6, 5) == sign_off(18 * 60, 6, 5)
    assert "credits" in sign_off(22 * 60, 3, 5, "day-in", movie=True)


# ---------------------------------------------------------------- getting around, and money

def test_uber_fares_have_a_minimum():
    assert rules.uber_fare(0) == 0
    assert rules.uber_fare(3) == 10  # the minimum fare
    assert rules.uber_fare(30) > rules.uber_fare(10) > 10


def test_uber_days_stay_put():
    car = [day("9:00", "22:00", 8, "everything", s, travel="car")["stats"]["neighborhoods"] for s in range(10)]
    uber = [day("9:00", "22:00", 8, "everything", s, travel="uber") for s in range(10)]
    assert sum(u["stats"]["neighborhoods"] for u in uber) < sum(car)
    for u in uber:
        legs = [s["fare"] for s in u["stops"] if s["type"] != "free"] + [u["back_fare"]]
        assert u["stats"]["fares"] == pytest.approx(sum(legs), abs=len(legs))  # rounding, one dollar a leg


def test_bus_days_walk_or_take_one_bus_somewhere(guide):
    from saturday.city import TransitCity
    city = TransitCity({s.name: s.zone for s in guide.spots})
    for seed in range(8):
        data = day("9:00", "22:00", 8, "everything", seed, travel="transit")
        assert data["stops"] and data["stats"]["fares"] == 0
        stops = [s for s in data["stops"] if s["type"] == "stop"]
        far_zones = {guide.find(s["name"]).zone for s in stops if city.walk.miles("West Campus", s["name"]) > 1}
        assert len(far_zones) <= 1  # one bus destination at most
        for s in data["stops"]:
            if s.get("via") == "walk" and s["type"] == "stop":
                assert s["travel"] <= 20 * 1.0 + 1  # a walk is a mile or less


def test_student_budget_spends_less():
    student = sum(day("9:00", "22:00", 8, "everything", s, budget="student")["stats"]["spend"] for s in range(10))
    splurge = sum(day("9:00", "22:00", 8, "everything", s, budget="splurge")["stats"]["spend"] for s in range(10))
    assert student < splurge


def test_every_spot_has_a_price(guide):
    assert all(s.price >= 0 for s in guide.spots)
    assert guide.find("Texas State Capitol").price == 0 and guide.find("Uchi").price > guide.find("Cabo Bob's").price


def test_starting_somewhere_else_moves_the_day():
    campus = day("9:00", "22:00", 6, "everything", 5, travel="walk", start_from="ut")
    soco = day("9:00", "22:00", 6, "everything", 5, travel="walk", start_from="soco")
    assert {s["where"] for s in soco["stops"] if s["type"] == "stop"} != {s["where"] for s in campus["stops"] if s["type"] == "stop"}
