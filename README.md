# Saturday in Austin ✦

**Tell me when you're free. I'll figure out what we're doing.**

**[Try it live →](https://suhxnitiwari.github.io/saturday-in-austin/)** (the Python runs right in your browser)

I gave Python my favorite Austin spots and, apparently, my opinions about how a Saturday should work. Coffee belongs in the morning. Saturday is for brunch. You probably want to shower after Pilates. And I'm not sending you from South Congress to the Domain and back for no reason.

```
$ python -m saturday --start 8:00 --back 22:00 --seed 54

Your Saturday ✦  everything, out from 8:00 AM, home by 10:00 PM
   8:00 AM  CorePower Yoga
   9:00 AM  Home: shower + get ready
            You need to shower before we continue.
  10:30 AM  Hillside Farmacy
            It's Saturday. We're getting brunch.
  12:30 PM  Cosmic Coffee + Beer Garden  (the garden)
   2:00 PM  Dolce Neve  (gelato)
   3:00 PM  home, glowing ✦

  4 stops · 6.8 hours out · 40 min of driving · Saturday #54
```

## Try it

```bash
python3 -m venv .venv && .venv/bin/pip install matplotlib pytest
.venv/bin/python -m saturday                                   # a surprise Saturday
.venv/bin/python -m saturday --mood slow --hours 6
.venv/bin/python -m saturday --mood social --include "Victory Lap" --area ut --chart
.venv/bin/python -m pytest -q
```

| Option | What it does |
|---|---|
| `--start 9:00` / `--back 23:00` | when you're ready to go, and when you want to be home (after midnight works) |
| `--hours 6` | how long you actually want to be out, or `all` |
| `--mood` | `slow`, `social`, `creative`, `foodie`, `outside`, `shopping`, `productive`, `treat-myself`, `day-in` or `everything` |
| `--area soco` | stay in one neighborhood: `ut`, `downtown`, `east`, `soco` (South Congress + South First), `clarksville`, `domain` (The Domain / Rock Rose), `zilker` (+ Barton Springs, the Greenbelt), `south-lamar`, `north-loop` (Hyde Park / North Loop), `burnet` (Burnet Road), `mueller` |
| `--travel` | `car`, `uber` (cost-efficient: every ride has a fare, so the day stays in one area), `transit` (bus + walk, CapMetro is free with a UT ID) or `walk` (no walk over a mile) |
| `--budget` | `student`, `normal` or `splurge`: every spot has a rough price, and a student budget makes free things win |
| `--rainy` | nothing outdoors |
| `--include "Numero 28"` | one place you really want to go |
| `--skip PCL` / `--not workouts` | absolutely not (a place, or a kind of thing) |
| `--seed 184` | get Saturday #184 back |
| `--chart` | save the day as a picture |

## The rules about being a person

A schedule can fit every opening hour and still be a strange day. So the planner has rules, and they live as data in [`saturday/rules.py`](saturday/rules.py), not as if-statements scattered around:

- **After a workout:** only coffee or a smoothie, in workout clothes. Then you shower. Pilates → Black Fox → shower is a Saturday. Pilates → a nice dinner is not: there is a shower missing from this story.
- **Drinks:** brunch comes with coffee, so no coffee right after it. After dinner, a 9 PM latte is tomorrow's problem. And after cocktails (mimosas count), no workout for the rest of the day. Absolutely not.
- **It's Saturday:** between 9:30 and 1:30, brunch gets a bonus, and Josephine House and Hillside Farmacy get a little more. On a Saturday morning, brunch always gets a ticket in the lottery.
- **Meals are anchors:** no second restaurant right after a real meal (it takes a couple of stops to be hungry again), no dessert straight after lunch, and no Pilates on a full stomach. Out through lunchtime or dinnertime means an actual meal.
- **Geography:** every minute in the car costs points, so a detour to the Domain has to be worth it. Nearby places also get more lottery tickets. With no car, nothing is more than a mile's walk.
- **Pacing:** every stop takes a little energy and days past eight hours cost extra, so "all day" is a full day, not a marathon. Parks and hikes are better in the morning or evening; coffee is better before 3.
- **Home is a place too:** a shower after a workout, or a change before a dressy dinner, shows up as its own block.
- **Hours:** nothing starts outside its window or runs past closing. Ever.

When a rule shapes the day, the plan says so: *"It's Saturday. We're getting brunch."* *"You just ate. I'm not giving you another restaurant."* *"Absolutely not driving to the Domain and immediately coming back to South Congress."*

## On the website

- **Getting around:** Car, Uber, Bus + walk or Walk, from wherever you're starting. Uber days show the fares; bus days take at most one bus somewhere and walk the rest (the CapMetro map is an approximation of MetroRapid 801/803 and a few local routes, so check the CapMetro app for live times).
- **Budget:** Student, Normal or Splurge, with a rough total for the day (food, tickets and Ubers).
- **💌 Send it as a letter:** the day becomes a Bridgerton-style letter to a friend, with a link that opens the exact same Saturday.
- **The map:** every neighborhood in the planner, numbered on a simplified street map, with the drives the planner knows between them. Tap one to see them.
- **Austin, right now:** live weather and sunset from Open-Meteo, plus Austin's population from the U.S. Census Bureau's July 2025 estimate (1,002,632), on the Austin page, with a flip to the planner's own numbers. If it's raining in Austin, Rainy day turns itself on.

## How it works

1. **Map** (`city.py`): Austin's neighborhoods are a weighted graph, with roads in drive minutes. **Dijkstra's algorithm** with a min-heap finds the fastest drive between any two, and results are cached. With no car, each place gets its real coordinates (`data/places.json`, from OpenStreetMap), walks are measured with the haversine formula, and a **breadth-first search** keeps only places reachable in hops of a mile or less.
2. **Lottery** (`planner.shortlist`): filter by mood, neighborhood, weather and your "absolutely not," then draw about a dozen candidates with **weighted sampling without replacement** (Efraimidis–Spirakis: each place gets the key `random() ** (1 / weight)` and the biggest keys win). Weight grows with how much I love a place and shrinks with how far away it is.
3. **Rules** (`rules.py`): every kind of stop has a `Kind`: how filling it is, whether it's a workout, whether you can show up sweaty, when it closes, the hours it's best at. `step(state, spot)` says whether a person would make that move, where the state is five tiny numbers (just worked out? just ate? just changed? had coffee? had cocktails?). `cost(...)` prices travel and timing. `explain(...)` writes the notes.
4. **Plan** (`planner.plan_day`): **dynamic programming over subsets** (bitmask DP). A state is which places you've been, how many of each kind, the person state, the last stop and when you finish it; each keeps its cheapest cost. The winner scores `10 × joy − travel − timing − energy`. That turns n! orderings into a search that runs in a fraction of a second, in the browser.
5. **Check** (`tests/`): 86 tests. A **backtracking** search that really tries every order, with every rule, runs on dozens of random days and the DP has to match its best score every time. The people rules are tested one by one: Pilates → coffee → shower is valid, Pilates → coffee → shopping is not, brunch → lunch 45 minutes later never happens, and nothing is scheduled outside its hours.

Every Saturday has a number. The randomness is seeded, so Saturday #184 is always the same Saturday.

The spots and notes are my favorites plus places I researched; drive times, visit lengths and ratings are my own estimates. ✦
