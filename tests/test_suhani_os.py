"""Tests for Suhani OS. Run with:  pytest -q"""
import random
from fractions import Fraction

import pytest

from suhani_os import austin, bakery, bookshelf, closet, laderach, mosaic, sitara, timeline
from suhani_os.errors import (HorrorError, NotAGiftError, OutOfFairyDust, PolyesterError,
                              SuhaniError)


# ---------------------------------------------------------------- closet

def test_natural_blend_passes_inspection():
    dress = closet.Dress("Midi", "FARM Rio", 198, {"Linen": 70, "cotton": 30})
    dress.inspect()  # no exception
    assert dress.label() == "70% linen, 30% cotton"


def test_polyester_is_rejected_even_from_a_favorite_brand():
    dress = closet.Dress("Mini", "LoveShackFancy", 325, {"polyester": 80, "silk": 20})
    with pytest.raises(PolyesterError) as err:
        dress.inspect()
    assert err.value.offenders == ["polyester"]
    assert isinstance(err.value, SuhaniError)  # catchable as any Suhani rule


def test_blend_must_add_up_to_100():
    with pytest.raises(ValueError):
        closet.Top("Tee", "X", 20, {"cotton": 90})


def test_food_and_flowers_are_extras_not_main_gifts():
    journal = closet.Stationery("Journal", "Rifle Paper Co.", 28)
    assert closet.Gift(journal, closet.Flowers("Peonies", "Florist", 35)).approve().startswith("Approved")
    for main in (closet.Food("Läderach box", "Läderach", 40), closet.Flowers("Peonies", "Florist", 35)):
        with pytest.raises(NotAGiftError):
            closet.Gift(main).approve()


def test_shop_splits_the_cart():
    good = closet.Top("Cami", "LSF", 98, {"silk": 100})
    bad = closet.Top("Cardigan", "?", 60, {"wool": 60, "acrylic": 40})
    keep, put_back = closet.shop([good, bad])
    assert keep == [good] and put_back[0][0] is bad


# ---------------------------------------------------------------- bookshelf

@pytest.fixture
def books():
    return bookshelf.load_books()


def test_avl_stays_balanced_with_sorted_input(books):
    shelf = bookshelf.Bookshelf(sorted(books, key=lambda b: b.sort_title))
    assert len(shelf) == len(books) == 30
    assert shelf.height <= 6  # a plain BST would be 30 tall


def test_in_order_traversal_is_alphabetical_ignoring_the(books):
    shelf = bookshelf.Bookshelf(books)
    keys = [b.sort_title for b in shelf]
    assert keys == sorted(keys)
    assert keys[0] == "48 laws of power"


def test_find_remove_and_duplicates(books):
    shelf = bookshelf.Bookshelf(books)
    assert shelf.find("the love hypothesis").author == "Ali Hazelwood"
    assert shelf.find("Not A Real Book") is None
    shelf.add(bookshelf.Book("The Love Hypothesis", "Ali Hazelwood", "romance"))
    assert len(shelf) == 30  # same title replaces, never duplicates
    shelf.remove("The Love Hypothesis")
    assert shelf.find("The Love Hypothesis") is None and len(shelf) == 29
    with pytest.raises(KeyError):
        shelf.remove("The Love Hypothesis")


def test_avl_survives_random_inserts_and_deletes():
    rng = random.Random(313)
    titles = [f"book {i:03d}" for i in range(300)]
    rng.shuffle(titles)
    shelf = bookshelf.Bookshelf(bookshelf.Book(t, "a b", "s") for t in titles)
    for t in titles[:150]:
        shelf.remove(t)
    remaining = sorted(titles[150:])
    assert [b.title for b in shelf] == remaining
    assert shelf.height <= 1.45 * 8  # log2(150) ~ 7.2


def test_range_query(books):
    shelf = bookshelf.Bookshelf(books)
    titles = [b.title for b in shelf.between("c", "dz")]
    assert "The Deal" in titles and "Atomic Habits" not in titles


@pytest.mark.parametrize("sort", [bookshelf.merge_sort, bookshelf.quicksort])
def test_sorts_match_python(sort):
    rng = random.Random(303)
    for n in (0, 1, 2, 17, 200):
        data = [rng.randint(-50, 50) for _ in range(n)]
        assert sort(data) == sorted(data)
    assert sort(list(range(500))) == list(range(500))  # already sorted: no worst case


def test_merge_sort_is_stable(books):
    by_author = bookshelf.merge_sort(books, key=lambda b: b.author_last)
    henry = [b.title for b in by_author if b.author_last == "henry"]
    assert henry == ["People We Meet on Vacation", "Funny Story"]  # original CSV order kept


def test_binary_search_edges():
    data = [1, 3, 5, 7, 9]
    assert [bookshelf.binary_search(data, x) for x in (1, 9, 5)] == [0, 4, 2]
    assert bookshelf.binary_search(data, 4) == -1
    assert bookshelf.binary_search([], 4) == -1


# ---------------------------------------------------------------- laderach

def test_hash_map_resizes_and_is_case_insensitive():
    m = laderach.FlavorMap(capacity=2)
    for i in range(50):
        m.put(f"flavor {i}", i)
    assert len(m) == 50 and m.capacity >= 64
    assert m.get("FLAVOR 7") == 7 and "Flavor 49" in m
    m.put("flavor 7", 700)
    assert m.get("flavor 7") == 700 and len(m) == 50
    m.remove("flavor 7")
    assert "flavor 7" not in m
    with pytest.raises(KeyError):
        m.remove("flavor 7")


def test_heap_pops_in_descending_order():
    rng = random.Random(4)
    data = [rng.randint(0, 1000) for _ in range(200)]
    h = laderach.MaxHeap(data)
    h.push(5000)
    assert h.peek() == 5000
    out = [h.pop() for _ in range(len(h))]
    assert out == sorted(data + [5000], reverse=True)
    with pytest.raises(IndexError):
        h.pop()


def test_dp_box_beats_greedy_and_respects_the_limit():
    g_love, _ = laderach.greedy_box(laderach.COUNTER, 300)
    d_love, box = laderach.best_box(laderach.COUNTER, 300)
    assert d_love > g_love
    assert sum(p.grams for p in box) <= 300


def test_dp_box_is_optimal_by_brute_force():
    from itertools import combinations
    pieces = laderach.COUNTER
    for limit in (0, 50, 180, 300, 450):
        best = max((sum(p.love for p in c) for r in range(len(pieces) + 1)
                    for c in combinations(pieces, r) if sum(p.grams for p in c) <= limit), default=0)
        assert laderach.best_box(pieces, limit)[0] == best


# ---------------------------------------------------------------- bakery

def test_linked_list_insert_pop_reverse():
    steps = bakery.StepList(["a", "b", "d"])
    steps.insert(2, "c")
    steps.insert(0, "start")
    assert list(steps) == ["start", "a", "b", "c", "d"]
    assert steps.pop(4) == "d" and steps.pop(0) == "start"
    steps.append("e")  # tail pointer still right after popping the old tail
    steps.reverse()
    assert list(steps) == ["e", "c", "b", "a"] and len(steps) == 4
    with pytest.raises(IndexError):
        steps.pop(9)


def test_queue_is_first_in_first_out():
    k = bakery.Kitchen()
    assert k.order("Lego cake", "Amaira") == 1
    k.order("Rainbow cake", "Mumma")
    assert k.bake_next().startswith("Lego cake")
    assert k.bake_next().startswith("Rainbow cake")
    with pytest.raises(IndexError):
        k.bake_next()


def test_undo_reverses_edits_in_order():
    r = bakery.BANANA_BREAD.scaled(8)
    original = list(r.steps)
    r.add_step("Preheat the oven.", index=0)
    r.remove_step(3)
    r.undo()
    r.undo()
    assert list(r.steps) == original
    with pytest.raises(IndexError):
        r.undo()


def test_scaling_uses_exact_fractions():
    doubled = bakery.BANANA_BREAD.scaled(16)
    assert doubled.ingredients["flour"] == (Fraction(3), "cup")
    assert bakery.BANANA_BREAD.ingredients["flour"][0] == Fraction(3, 2)  # original untouched
    assert bakery.pretty_amount(Fraction(9, 8)) == "1 1/8"
    assert bakery.pretty_amount(Fraction(2, 3)) == "2/3"
    assert "3 cups" in doubled.card()


# ---------------------------------------------------------------- austin

@pytest.fixture
def city():
    return austin.Austin()


def test_dijkstra_takes_the_faster_road(city):
    minutes, route = city.drive("West Campus", "South Congress")
    assert minutes == 15 and route == ["West Campus", "Downtown", "South Congress"]
    assert city.drive("Campus", "Campus") == (0, ["Campus"])


def test_bfs_counts_stops_not_minutes(city):
    assert city.fewest_stops("Campus", "Domain") == ["Campus", "North Loop", "Domain"]


def test_saturday_follows_every_rule(city):
    spots = austin.pick_candidates(austin.load_spots())
    joy, minutes, order = austin.perfect_saturday(spots, city, "West Campus", budget=12 * 60)
    cats = [s.category for s in order]
    assert "coffee" in cats and len(cats) == len(set(cats))  # coffee, one per category
    assert minutes <= 12 * 60 and joy == sum(s.joy for s in order)
    clock, zone = 9 * 60, "West Campus"
    for s in order:  # replay the day: every stop starts inside its window
        start = austin.begin_at(s, clock + city.drive(zone, s.zone)[0])
        earliest, latest = austin.WINDOWS[s.category]
        assert start is not None and earliest <= start <= latest
        clock, zone = start + s.stay, s.zone


def test_dp_matches_brute_force_on_random_small_days(city):
    rng = random.Random(325)
    everything = austin.load_spots()
    for _ in range(15):
        spots = rng.sample(everything, 6)
        budget = rng.choice([180, 300, 480, 720])
        dp_joy, _, _ = austin.perfect_saturday(spots, city, "Campus", budget)
        assert dp_joy == austin.brute_force_saturday(spots, city, "Campus", budget)


def test_no_coffee_no_saturday(city):
    spots = [s for s in austin.load_spots() if s.category != "coffee"][:5]
    assert austin.perfect_saturday(spots, city, "Campus", 600) == (0, 0, [])


# ---------------------------------------------------------------- mosaic

def test_rows_are_independent_lists():
    grid = mosaic.blank(3, 3)
    grid[0][0] = "x"
    assert grid[1][0] == mosaic.EMPTY


def test_flood_fill_stays_inside_walls():
    grid = [list(row) for row in ("#####", "#...#", "#####", "#...#")]
    assert mosaic.flood_fill(grid, 1, 1, "o") == 3
    assert "".join(grid[3]) == "#...#"  # the other room is untouched
    assert mosaic.flood_fill(grid, 1, 1, "o") == 0  # already that color


def test_mosaic_is_symmetric_and_fully_painted():
    grid = mosaic.make_mosaic(31)
    assert all(tile in mosaic.PALETTE for row in grid for tile in row)
    star = [[t in ("baby pink", "mulberry") for t in row] for row in grid]
    assert star == star[::-1] and star == [row[::-1] for row in star]


# ---------------------------------------------------------------- timeline

def test_timeline_facts():
    df = timeline.load(today="2026-09-28")
    s = timeline.summary(df)
    assert (s["homes"], s["countries"]) == (8, 3)
    assert s["longest"][0] == "Cupertino"
    assert s["india_cities"] == ["Lucknow", "Delhi", "Ahmedabad", "Bangalore"]
    assert df["current"].sum() == 1 and df.loc[df["current"], "place"].item() == "Austin"


# ---------------------------------------------------------------- mini sitara

def test_sitara_answers_and_refuses_horror():
    fairy = sitara.Sitara()
    assert "Hana, Reese and Avery" in fairy.ask("Who is her BEST friend?!")
    assert "Baby pink" in fairy.ask("favorite colour")
    assert "not in my notes" in fairy.ask("What's her shoe size?")
    with pytest.raises(HorrorError):
        fairy.ask("horror movie night?")


def test_sitara_runs_out_of_fairy_dust():
    fairy = sitara.Sitara()
    replies = [fairy.ask("color") for _ in range(sitara.DUST_LIMIT)]
    assert "last question" in replies[-2] and "last question" not in replies[-1]
    with pytest.raises(OutOfFairyDust):
        fairy.ask("color")
