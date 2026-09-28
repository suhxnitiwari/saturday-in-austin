"""Suhani OS ✦, the menu. Run it with:  python -m suhani_os        (interactive)
                                        python -m suhani_os demo   (everything at once)
"""
from __future__ import annotations

import sys
from pathlib import Path

from . import austin, bakery, bookshelf, closet, laderach, mosaic, sitara, timeline
from .errors import SuhaniError

OUT = Path(__file__).resolve().parent.parent / "out"
PINK, BOLD, DIM, RESET = "\033[38;5;211m", "\033[1m", "\033[2m", "\033[0m"


def title(text: str) -> None:
    print(f"\n{PINK}{BOLD}✦ {text}{RESET}\n{DIM}{'─' * (len(text) + 2)}{RESET}")


def show_closet() -> None:
    title("The Closet: the fabric rule beats the brand")
    cart = [
        closet.Dress("Floral midi dress", "FARM Rio", 198, {"linen": 70, "cotton": 30}),
        closet.Dress("Ruffle mini dress", "LoveShackFancy", 325, {"polyester": 100}),
        closet.Top("Silk cami", "LoveShackFancy", 98, {"silk": 100}),
        closet.Top("Cozy cardigan", "Mystery brand", 60, {"wool": 60, "acrylic": 40}),
    ]
    keep, put_back = closet.shop(cart)
    for item in keep:
        print(f"  ✓ {item}  [{item.label()}]")
    for item, why in put_back:
        print(f"  ✗ {item.name}: {why}")
    print()
    for gift in (closet.Gift(closet.Stationery("Rifle Paper Co. journal", "Rifle Paper Co.", 28),
                             closet.Flowers("Peonies", "Local florist", 35)),
                 closet.Gift(closet.Food("Läderach box", "Läderach", 40))):
        try:
            print(f"  {gift.approve()}")
        except SuhaniError as err:
            print(f"  ✗ {err}")


def show_bookshelf() -> None:
    title("The Bookshelf: an AVL tree that stays balanced")
    books = bookshelf.load_books()
    alphabetical = sorted(books, key=lambda b: b.sort_title)
    shelf = bookshelf.Bookshelf(alphabetical)  # worst-case insert order for a plain BST
    print(f"  {len(shelf)} books added in alphabetical order (a plain BST would be {len(shelf)} levels tall)")
    print(f"  AVL tree height: {shelf.height}")
    found = shelf.find("People We Meet on Vacation")
    print(f"  find('People We Meet on Vacation') -> {found.author}, {found.shelf} shelf")
    print(f"  titles from C to D: {', '.join(b.title for b in shelf.between('c', 'dz'))}")
    by_author = bookshelf.merge_sort(books, key=lambda b: b.author_last)
    i = bookshelf.binary_search(by_author, "henry", key=lambda b: b.author_last)
    print(f"  binary search for Emily Henry -> {by_author[i].title}")
    for name, group in bookshelf.shelves(books).items():
        print(f"  {name}: {len(group)} books, starting with {group[0].title}")


def show_laderach() -> None:
    title("The Läderach Counter: greedy vs. dynamic programming")
    menu = laderach.build_menu()
    print(f"  {len(menu)} flavors in a hand-built hash map ({menu.capacity} buckets after resizing)")
    print(f"  favorites on the counter: {', '.join(f for f in laderach.FAVORITES if f in menu)}")
    limit = 300
    g_love, g_box = laderach.greedy_box(laderach.COUNTER, limit)
    d_love, d_box = laderach.best_box(laderach.COUNTER, limit)
    print(f"  {limit} g box, greedy: love {g_love}  ({', '.join(p.flavor for p in g_box)})")
    print(f"  {limit} g box, DP:     love {d_love}  ({', '.join(p.flavor for p in d_box)})")
    if d_love > g_love:
        print(f"  {DIM}greedy grabbed the best love-per-gram first and left {d_love - g_love} love on the counter{RESET}")


def show_bakery() -> None:
    title("The Bakery: linked list, stack and queue")
    kitchen = bakery.Kitchen()
    for cake, who in zip(bakery.CAKES_SHE_HAS_MADE, ("Amaira", "the Girls Who Code party", "Mumma")):
        kitchen.order(cake, who)
    print(f"  {len(kitchen.orders)} cake orders in the queue")
    print(f"  {kitchen.bake_next()}")
    recipe = bakery.BANANA_BREAD.scaled(16)  # double batch
    recipe.add_step("Sprinkle extra chips on top before baking.", index=4)
    recipe.remove_step(0)
    recipe.undo()  # changed her mind: the bananas do need mashing
    print("\n" + "\n".join("  " + line for line in recipe.card().splitlines()))
    print(f"\n  cooking: {kitchen.make_toast()}")


def show_austin() -> None:
    title("A Perfect Saturday in Austin: graphs + dynamic programming")
    city = austin.Austin()
    minutes, route = city.drive("West Campus", "South Congress")
    print(f"  fastest drive West Campus -> South Congress: {minutes} min via {' -> '.join(route)}")
    candidates = austin.pick_candidates(austin.load_spots())
    joy, used, order = austin.perfect_saturday(candidates, city, "West Campus", budget=12 * 60)
    print(f"  best day (9 AM to 9 PM) from {len(candidates)} favorite spots: joy {joy}, {used} minutes\n")
    for line in austin.itinerary(order, city, "West Campus"):
        print(f"    {line}")


def show_mosaic() -> None:
    title("Mosaic Workshop: 2D lists, recursion, graphics")
    grid = mosaic.make_mosaic(21)
    print("\n".join("    " + row for row in mosaic.as_text(grid).splitlines()))
    path = mosaic.render(mosaic.make_mosaic(31), OUT / "mosaic.png")
    print(f"\n  saved {path.relative_to(OUT.parent)}")


def show_timeline() -> None:
    title("Three Countries, Eight Homes: pandas + matplotlib")
    df = timeline.load()
    s = timeline.summary(df)
    print(f"  {s['homes']} homes, {s['countries']} countries, {s['continents']} continents")
    print(f"  longest stay: {s['longest'][0]} ({s['longest'][1]:g} years)")
    print(f"  years in the US so far: {s['us_years']:g}")
    print("\n" + "\n".join("    " + line for line in s["by_country"].to_string().splitlines()))
    path = timeline.chart(df, OUT / "timeline.png")
    print(f"\n  saved {path.relative_to(OUT.parent)}")


def show_sitara() -> None:
    title("Mini Sitara: strings, dicts and files")
    fairy = sitara.Sitara()
    for q in ("What's her favorite color?", "Who are her best friends?", "Want to watch a horror movie?"):
        try:
            print(f"  Q: {q}\n  A: {fairy.ask(q)}\n")
        except SuhaniError as err:
            print(f"  Q: {q}\n  A: {err}\n")


SECTIONS = {
    "1": ("The Closet", show_closet),
    "2": ("The Bookshelf", show_bookshelf),
    "3": ("The Läderach Counter", show_laderach),
    "4": ("The Bakery", show_bakery),
    "5": ("A Perfect Saturday in Austin", show_austin),
    "6": ("Mosaic Workshop", show_mosaic),
    "7": ("Three Countries, Eight Homes", show_timeline),
    "8": ("Mini Sitara", show_sitara),
}


def banner() -> None:
    print(f"{PINK}{BOLD}\n  Suhani OS ✦{RESET}  {DIM}my life, as data structures and algorithms · Suhani Coded™{RESET}")


def main(argv: list) -> None:
    banner()
    if argv[:1] == ["demo"]:
        for _, show in SECTIONS.values():
            show()
        return
    while True:
        print()
        for key, (name, _) in SECTIONS.items():
            print(f"  {key}. {name}")
        print("  q. quit")
        choice = input(f"\n{PINK}pick one ✦ {RESET}").strip().lower()
        if choice in ("q", "quit", "exit"):
            print("bye ✦")
            return
        if choice in SECTIONS:
            SECTIONS[choice][1]()
        else:
            print("  that's not on the menu, but I admire the curiosity")


if __name__ == "__main__":
    main(sys.argv[1:])
