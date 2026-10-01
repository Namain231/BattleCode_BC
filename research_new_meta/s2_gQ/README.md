# gP: the new-map build (submitted as S.2, id 13685)

Exact source of submission **13685 ("S.2", description "Minor revision.")**, uploaded 2026-09-30 18:40 UTC.
Built from `viper_y8m_gP/`. It is the live build **Y.8m** (`baselines/y8m_active`, the maintenance line's
submission 11461) plus two changes that only matter on maps the bot does not recognise. The sprint and the final
tournament use only new maps.

`bot.toml`, `maps_data.hpp`, `policy_nn.hpp` and `policy_weights.hpp` are byte-identical to Y.8m. All changes are
in `main.cpp`.

## Change 1: learning pearl-bed timing on unknown maps

Every tile has a pearl countdown, and it keeps cycling even while a pearl sits on it. On a known map the bot loads
each bed's gap range (`gmin`/`gmax`) from `maps_data.hpp`. On an unknown map those stayed "unknown" for the whole
game. A pearl-every-round fountain then looked the same as a 1-in-100 bed: `farmBonus` was 1.0 everywhere, the
renewal branch of `pearlProb` never ran, and the network's bed-rate input plane was empty.

`learnGap()` (right after `gmin`/`gmax`, near line 277) fixes this from what the dragon sees. It runs only when
`!KM`, i.e. no known map is active.

- Any countdown `t` it observes satisfies `t <= max_gap`, so the largest `t` seen is the `gmax` estimate.
- If a countdown seen on consecutive rounds goes up instead of down, it has just been reset. That value plus 1 is
  a fresh draw from `[min_gap, max_gap]`, and the smallest fresh draw is the `gmin` estimate.
- An estimate is trusted only after one observed reset, so a slow bed first caught at countdown 3 is not mistaken
  for a fountain.

It is called in the vision loop: `if (!KM && V.ptime[i] >= 0) learnGap(c, V.ptime[i]);`.

**Limitation:** memory is per dragon, and a split child starts blank (`docs/splitting.md`), so every child
relearns from zero. Passing learned gaps to children over sonar is the obvious follow-up (see `insights.md`).

## Change 2: queen protection from round 340 on unknown maps

`Params::protectFrom` changes from **400 to 340**. From this round the longest dragon (the queen) stops splitting
voluntarily and grows for the length tiebreak at round 500.

- **Known maze maps:** `activateMap` already set `protectFrom = 340`, so nothing changes.
- **Known open maps (Portals, Slithery Fight, Schooltime; `bigFeed`):** queen protection is switched off there
  (`protectedQueen()` and `lateQ` check `!bigFeed`). One un-gated use remains: the queen's own head-on danger
  weight goes from x2 to x3 at `protectFrom`, so on these three maps that step now happens at r340 instead of r400.
- **Unknown maps:** Y.8m fell back to the default 400, and budding runs to r420 while the swarm has fewer than 40
  dragons. So on a new map the longest dragon kept splitting almost to the end. 85% of unseen-map games end on
  the length tiebreak, so this cost games directly.

## Evidence

All games are local, zig judge, both sides, against live Y.8m (`baselines/y8m_active`), on maps no rule was tuned
on. Set A is `maps_gen` gen_020-049 plus `maps_dense` dense_000-029. Set B is gen_050-079, dense_030-039 and
`maps_dense2` dense_000-019 (`ladder/set60b.txt`). The `maps_dense*` maps come from
`tools/gen_random_maps.py --dense`: live-like bed layers and 10-30% kelp.

| Build | Set A | Set B | Pooled |
|---|---|---|---|
| Y.8m + bed learning only (`viper_y8m_gaps`) | 53-67 | 67-53 | 50% |
| **gP (this build)** | **72-47** | **73-47** | **61%** |

Mechanism (`tools/endgame_len.py`, set A): final longest dragon 16.1 vs 15.1 for the bed-learning-only build.
The paired final margin against Y.8m is +1.08 ±0.60 vs -0.45 ±0.59. Bed learning raises unit count (about 23.5
vs 18 at r500). Protection turns those units into length.

On the 10 live (known) maps, gP vs Y.8m was 31-29 (60 games), as expected: those maps are almost unchanged.

Peak CPU is 61.7M points per dragon-turn on the largest dense maps (live maps about 49-59M). That is under the
100M kill line and slightly under the 65M guard in AGENTS.md. The control build peaks at the same level, so the
peak comes from the maps, not from this change.

## What was tried on top of gP and not kept

All were tested against Y.8m on the same maps (details in `insights.md`, sections from 2026-09-30/10-01).

| Build | Idea | Result |
|---|---|---|
| gPQ | queen election uses a length lower bound, and queen reports expire after 15 rounds | 44-76, dropped |
| gPE | protect the queen from r280 when the swarm has 30+ dragons | 71-49, no gain |
| gD | tabu against re-visiting cells without eating (fixes circling) | live maps 40-20 (gP 31-29); unseen maps 66-54 (gP 73-47); even overall |
| gM | from r430 every dragon walks to and feeds the queen or any teammate at least 2 longer | live 30-30; queen +0.9 but fewer units |
| gJ | gD + merge timed per dragon as `460 - travel to queen` | unseen 68-52, live 28-32 |
| gB | the "open map" (bigFeed) rule set on unknown maps | 22-98: maze defaults are right for new maps |

## Ladder

S.2 played 10 unranked games while active on 2026-09-30 (3-7, vs Yueci Li and Maccas). Those losses show a
separate weakness: more total mass, but spread over several medium dragons, losing the tiebreak to one big enemy
dragon. The active slot was then restored to the maintenance build 13618.

## Reproduce

```
python tools/tourney.py baselines/s2_gP baselines/y8m_active --maps $(cat ladder/set60b.txt) --judge zig -j 10 --keep-replays ladder/x
python tools/local_index.py ladder/x gP y8m ladder/x_idx && python tools/endgame_len.py ladder/x_idx
```

Delete the `_idx` directory and any `*.pkl` caches afterwards: a 120-game run with replays is about 600 MB.
