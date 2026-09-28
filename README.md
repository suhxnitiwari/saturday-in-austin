# Saturday in Austin ✦

**Tell it how long you have and what you're in the mood for. It plans the best day around Austin.**

Every run is a different Saturday, drawn from my favorite coffee shops, brunches, Pilates and yoga, pottery studios, shopping and dinners.

```
$ python -m saturday

Your Saturday ✦  everything, 10 hours from West Campus
  10:06 AM  Josephine House
  11:31 AM  Two Hands
  12:16 PM  Life Science Library  (the prettiest study spot)
   1:54 PM  Mosaic Workshop
   4:07 PM  [solidcore]  (Pilates)
   4:57 PM  South Congress  (Kendra Scott and Tecovas)
   6:34 PM  Clay Pit  (North Indian)
   7:57 PM  home, happy

  7 stops · 44 min of driving · seed 5
  run it again for a different Saturday ✦
```

![A Saturday as a timeline](docs/example-saturday.png)

## Try it

```bash
python3 -m venv .venv && .venv/bin/pip install matplotlib pytest
.venv/bin/python -m saturday                  # a surprise Saturday
.venv/bin/python -m saturday --mood cozy
.venv/bin/python -m saturday --hours 6 --mood foodie --include "Clay Pit" --chart
.venv/bin/python -m pytest -q
```

| Option | What it does |
|---|---|
| `--hours 10` | how long you have |
| `--mood` | `cozy`, `creative`, `foodie`, `productive` or `everything` |
| `--start 10:00` | when you leave |
| `--home "West Campus"` | where the day starts and ends |
| `--include "Numero 28"` | a spot you have to go to (typos get a "did you mean?") |
| `--skip PCL` | a spot to leave out |
| `--chart` | save the day as a picture |
| `--seed 5` | repeat a Saturday you liked (every run prints its seed) |

## The rules every plan follows

- Every stop starts when it makes sense: brunch in the morning, dinner in the evening, pottery before the studio closes.
- One stop per slot: one coffee, one midday meal (brunch *or* lunch), one dinner.
- Nothing after dinner except a late-night snack.
- There is always coffee.
- You're home by the time you said.

## How it works

The hard part is that the obvious approach doesn't work. Taking the highest-rated spots first ignores driving and opening hours: a long 10/10 dinner can push out two great afternoon stops. Trying every possible order works but explodes: 15 spots have over a trillion orderings.

1. **Map** (`city.py`): Austin's neighborhoods are a weighted graph, with roads measured in drive minutes. **Dijkstra's algorithm** with a min-heap finds the fastest drive between any two neighborhoods, and results are cached.
2. **Surprise** (`planner.shortlist`): filter by mood, then run a weighted lottery that picks two candidates per slot. Every favorite can win, and higher-rated ones win more often. It's weighted sampling without replacement (the Efraimidis-Spirakis method: each spot gets the key `random() ** (1 / weight)` and the biggest keys win). Must-haves always stay.
3. **Plan** (`planner.plan_day`): **dynamic programming over subsets** (bitmask DP). For every set of spots and every possible last stop, it keeps the earliest time you could finish. Finishing earlier is never worse, since you can always wait, so one number per state is enough. That turns *n!* orderings into 2ⁿ × n² steps, and a full day plans in a fraction of a second.
4. **Check** (`tests/`): a **backtracking** search that really does try every order runs on 40 random small days, and the DP has to match it every time. Other tests check that 60 random Saturdays all follow the rules, that every dinner spot gets its turn, and that the same seed always gives the same day.

The spots and their notes are my real favorites. Drive times, visit lengths and ratings are my own estimates. ✦
