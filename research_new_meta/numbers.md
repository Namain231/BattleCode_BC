# New-meta measurements: queen rule, sprint cost, and the gQ control

Every figure below is measured from the 59 games in `results.tsv` (31), `results_gQ.tsv` (14) and
`results_gQ2.tsv` (14, run for this report), via `analyze.py` over the 59 replays in `replays/`.
Lines marked **(inference)** are mine, not measurements. Engine: `new_*`/`q_*`/`q2_*` = unswbc 1.2.3,
`old_*` = 1.2.2. "Team-game" = one side of one game (118 in total).

## What was fixed in analyze.py

No logic bugs were found, but it could not answer two of the questions as written, so it was extended:

- **Moves were pooled across both teams**, with no team or id attached, so no sprint figure could be
  attributed to a bot. Now bucketed per team as a `Counter` over `(length, steps)` — which also shrinks the
  JSON, since the draft dumped every move of every game.
- **The death list was filtered to ids 0/1**, making non-queen death rates unmeasurable. The full list with
  each dragon's team is now carried, as are checkpoint team totals, end-of-game queen rank, a 25-round
  `series`, and the engine's own end counters.

Validation: `endReason == 1` is indeed the round-limit end (`bceval/features.py:257` maps 0 to elimination);
`rounds = last + 1` matches the judge on all 59 games; the recomputed winner matched the engine's in
**59/59** games and the recomputed `(count, longest, total)` matched its counters in **118/118** team-games.
The startling round-5 queen deaths were checked against raw replay events and are real.

## 1. How games end under the new engine — the queen rule has decided nothing

| set | n | reach 500 | elimination | tiebreak that decided the 500-round games | rulesets disagree |
|---|---|---|---|---|---|
| `new_*` (gP v v7_12 + gP self-play) | 21 | 17 | 4 | longest dragon 17, queen length 0, total 0 | 0 |
| `q_*` (gQ v gP) | 14 | 9 | 5 | longest dragon 9, queen length 0, total 0 | 0 |
| `q2_*` (gQ2 v gP) | 14 | 10 | 4 | longest dragon 10, queen length 0, total 0 | 0 |
| **all new-engine** | **49** | **36 (73%)** | **13** | **longest dragon 36, queen length 0** | **0** |
| `old_*` | 10 | 6 | 4 | longest dragon 6 | 0 |

**The queen rule and the old rule award every one of the 59 games to the same team.** Not one game was
decided on queen length: in all 36 round-500 games *both* queens were already dead, so criterion (1) is a
0–0 tie and the game falls through to the longest living dragon exactly as before. Total length never
decided a game either. Under current play the rule change is **inert** — not because games end early (73%
do reach round 500), but because nobody keeps a queen alive.

## 2. Queen survival — dragon 0/1 is dead long before the tiebreak

Across all 118 team-games: queen alive at the end in **2 (2%)**, both in elimination games that ended at
rounds 119 and 194. Across all 42 games that reached round 500, on either engine, **0 of 84 queens survived**.

| group | team-games | alive at end | death round (med / min / max) |
|---|---|---|---|
| all | 118 | 2 (2%) | 58 / 5 / 367 |
| new engine | 98 | 2 (2%) | 58 / 5 / 367 |
| old engine | 20 | 0 | 50 / 5 / 213 |
| gP | 64 | 1 (2%) | 58 / 5 / 311 |
| v7_12 | 26 | 0 | 32 / 5 / 213 |
| gQ | 14 | 1 (7%) | 69 / 5 / 367 |
| gQ2 | 14 | 0 | 58 / 5 / 203 |
| games reaching round 500 | 84 | **0** | 58 / 5 / 367 |

Death cause (116 queen deaths): **headon 60 (52%), self 26 (22%), wall 21 (18%), body 9 (8%)** — half of all
queen deaths are head-on collisions. Death round, bucketed: 0–49 **53 (46%)**, 50–99 26, 100–149 19,
150–199 9, 200–249 5, 250–299 2, 300–349 1, 350–399 1.

Two specifics worth more than the averages:

- On **dilemma** and **slithery_fight** the queen dies at **round 5, every single time**, on both engines and
  for all four bots: dragon 0/1 splits itself at rounds 0, 1 and 4, drops to length ~1–2, then walks into a
  wall (id 0) or itself (id 1). **36 of the 118 team-games** (all 18 games on those two maps) are this, and
  they are most of the 46% of queen deaths that fall in rounds 0–49.
- Of the 102 team-games in games that *reached* round 340 (`P.protectFrom`), the queen was still alive at
  340 in exactly **1** (`q_g11_open_0_GQ`, died at 367). This single number governs §6.

## 3. Queen length trajectory — mid-pack while it lives, then zero

Means over gP's 50 team-games in the `old_*`/`new_*`/`q_*` sets (`v7_12` and `gQ` are similar; the `q2_*`
set is excluded here because §6 shows it is gP self-play), both unconditionally and conditioned on the
queen still being alive at that checkpoint:

| checkpoint | gP queens alive | queen len (all) | queen len (if alive) | its rank in own team (if alive) | dragons in team | team's longest |
|---|---|---|---|---|---|---|
| r100 | 18/50 | 0.9 | 2.6 | **8.1st** | 29.3 | 3.8 |
| r250 | 3/42 | 0.2 | 2.3 | 8.3rd | 40.3 | 4.0 |
| r400 | 0/38 | 0.0 | — | — | 21.8 | 13.8 |
| end | 1/50 | 0.0 | — | — | 15.7 | 18.5 |

So it is worse than "the 5th-longest dragon": while alive it is about the **8th of ~30**, at length 2–3
against a team longest of ~4, and in 64% of team-games it is already dead by round 100. Lifetime peak queen
length (sampled every 25 rounds), new-engine gP: mean **7.0** against a mean team-longest peak of **19.4**;
per-game peak was 3 in 12 games, 4 in 10, 6 in 2, 7 in 6, 11 in 6, 21 in 4.

## 4. Sprint usage — gP leaves most of the new allowance unused, but it barely matters

Matched maps only (default/trophy/dilemma/portals/slithery_fight, GV+VG), so old and new are comparable:

| engine | bot | subset | move-turns | steps>1 | steps ≥ ceil(L/4) | free/turn | used/turn | wasted/turn | % of free unused |
|---|---|---|---|---|---|---|---|---|---|
| old | gP | all | 106,331 | 0.62% | 95.1% | 1.10 | 1.00 | 0.10 | 9.2% |
| new | gP | all | 94,825 | 0.72% | 94.0% | 1.13 | 1.00 | 0.13 | 11.2% |
| old | gP | L≥5 | 5,238 | 1.28% | 0.7% | 3.07 | 1.01 | 2.06 | 67.0% |
| new | gP | L≥5 | 5,690 | 1.79% | 0.7% | 3.12 | 1.02 | 2.10 | 67.3% |
| new | v7_12 | all | 96,069 | 0.69% | 92.5% | 1.15 | 1.00 | 0.14 | 12.6% |

**The engine change alone shifted nothing** — gP's step distribution on the same maps is the same before
and after, as expected from a bot whose cost model never changed.

The 94% "uses the full allowance" figure is an artefact of how short gP's dragons are: on the full
new-engine set 55.5% of its move-turns come from a length-2 dragon, 27.6% length-3, 5.8% length-4, so
**88.9% have `ceil(L/4) == 1`, where old and new are identical**. Only **1.14%** of all moves take more than
one step at all. Restricting to the dragons the rule actually changed:

| new-engine gP | move-turns | share of all | free/turn | used/turn | wasted/turn | % of free unused |
|---|---|---|---|---|---|---|
| L≥5 | 55,669 | 11.1% | 2.73 | 1.03 | **1.70** | 62.2% |
| L≥9 | 20,611 | 4.1% | 3.98 | 1.05 | **2.93** | 73.6% |
| L≥13 | 10,040 | 2.0% | 5.02 | 1.05 | **3.98** | 79.2% |

So: ~0.19 free steps wasted per dragon-turn overall, 1.7 for a length-5+ dragon, 4.0 for a length-13+ one.
**(inference)** The waste sits in exactly the dragons that win the current tiebreak, so it is worth more
than the 0.19 headline suggests — but it is a mobility loss, not a length loss.

## 5. Old vs new engine, same bots — no measurable difference

| engine | gP v v7_12 | win rate | Wilson 95% CI |
|---|---|---|---|
| old (1.2.2) | **8–2** (10 games) | 0.80 | 0.49 – 0.94 |
| new (1.2.3) | **12–4** (16 games) | 0.75 | 0.51 – 0.90 |

Fisher exact, two-sided: **p = 1.00**; the intervals overlap almost completely. No evidence the engine
change moved this matchup at all. Two corrections to the premise:

- The new-engine record is **12–4, not 17–4**. The `new_*` set is 16 gP-v-v7_12 games plus **5 gP-v-gP
  self-play games** (`new_*_GG`); counting those 5 as gP wins gives 17.
- Two pairs are not independent: on **portals** the GV and VG replays are the *same game* event-for-event in
  both eras — gP and v7_12 make identical decisions there (gP's `bigFeed` branch restores "the old
  champion's values", `main.cpp:343`). Dropping the duplicates gives 7–2 and 11–4; nothing changes.

## 6. The gQ puzzle — a patch artefact, but not the hypothesised one

### What `protectedQueen()` actually gates

It has exactly four call sites in `baselines/s2_gP/main.cpp`, and **all four are split decisions**:

| line | effect when `protectedQueen()` is true |
|---|---|
| 1487 | raises the last-ditch "doomed split" trigger from `pDeath ≥ 0.90` to `≥ 0.99` |
| 1489 | disables the "about to be rammed" danger-split for a dragon of length ≥ 8 |
| 1507 | disables `swarmSplit()` |
| 1508 | disables voluntary `trySplit()` |

It never touches movement risk, targeting or feeding, so it is a **"do not split" flag**, not general
caution. Your reading that it applies broadly across gP's swarm is right — any dragon with
`MY_LEN >= queen.len`, plus any whose gossip has gone stale, since `updateQueen()` ends with
`if (ROUND - queen.round > 40) queen = me;` — but what it buys is **mass retention**, not survival.

### The real handicap is in the two gossip lines, not `protectedQueen()`

gQ also made `considerQueen` reject any candidate with `q.id != QID()` and gated that stale fallback on
`MY_ID == QID()`. So once the fixed queen is dead or unseen — nearly always, per §2 — a gQ non-queen
dragon's `queen` record stays at its default `{cell=-1, len=0, round=-1000, id=-1}` for the rest of the
game. The decisive readers of `queen` are the consolidation path: `tryFeed()` (1323), the `feeding` flag
(1423) and the pearl-routing `qCell` (912) all require `ROUND - queen.round <= 25`, impossible at
`round = -1000`. **gQ therefore loses the entire late-game mass-consolidation system**, on every map,
including the `bigFeed` ones where `protectedQueen()` is false for gP anyway.

### The signature in the data (14 games, means)

| checkpoint | gQ: dragons / total / longest | gP: dragons / total / longest |
|---|---|---|
| r250 | 43.3 / 106.5 / **5.2** | 37.8 / 91.2 / **3.6** |
| r400 | 31.8 / 131.7 / **10.8** | 20.7 / 98.5 / **18.0** |
| end | 26.8 / 155.9 / **11.5** | 10.0 / 70.9 / **20.4** |

gQ ends with **2.2× gP's total length and 2.7× its dragon count, but 56% of its longest dragon**, and the
crossover sits squarely between r250 and r400 — across `P.protectFrom = 340`. Your predicted side effect is
**absent and inverted**: gQ's non-queen death rate is *lower* (0.896 vs 0.940 of non-queen dragons born;
91.4% vs 95.4% of all dragons died). Its queen survived marginally better (1/14 vs 0/14 alive, mean final
queen length 0.21 vs 0.00) — statistically nothing. The win pattern is exact: **gQ went 0–9 in the nine games
that reached round 500** (all decided on longest dragon) **and 3–2 in the five elimination games**.

So the 3–11 says nothing about queen strategy. gQ is not a worse fighter; it loses precisely and only the
metric that split-suppression defends. Caveat: 14 games, 7 maps, one seed, and a map's two orderings are not
independent. The 0–9 is 5 map-level sweeps, a map-level sign test giving p = 0.06 — consistent with a large
effect, not formally established.

### `s2_gQ2` — the fairer control, and why it answers nothing

`research_new_meta/s2_gQ2/` is gP with one strictly **additive** change: gossip, feeding and the original
broad no-split rule untouched, and the fixed-id dragon *also* qualifies for split-suppression
(`MY_ID == QID() && ROUND >= P.protectFrom && MY_LEN >= 4`). 14 games, same maps and seed as `jobs_gQ.txt`
(`jobs_gQ2.txt`, `results_gQ2.tsv`).

Result: **gQ2 7 – gP 7**, and the record is meaningless. All 7 map pairs produced **byte-identical play in
both orderings** — verified by comparing decoded event streams, not just the scoreline: identical round
counts, queen death rounds, end lengths and split counts. gQ2 made exactly the same decisions as gP in all
14 games, so the 7–7 is pure side asymmetry and the `q2_*` games are gP self-play. The cause is §2's last
number: gQ2's extra clause can only fire if dragon 0/1 is alive at round ≥ 340, and in **101 of 102**
team-games reaching 340 the queen was already dead.

**This is not "14 games is too few".** The intervention never fired once, so these games carry zero
information about queen strategy, and more would carry zero too. **(inference)** Any queen-targeting patch
gated at `P.protectFrom = 340` is untestable until dragon 0/1 survives past roughly round 100; the gap to
close is early queen survival, not late consolidation.

## What the data cannot answer

- Whether protecting a queen *would* win games — criterion (1) was never once applied in 42 round-500 games.
- Whether the unused sprint allowance costs games: measurable as wasted steps, but tied to no outcome here.
- Old-vs-new engine effects beyond the gP-v7_12 matchup: the sets differ in seed and map mix, so only §4's
  matched-map sprint comparison is a clean pairing.
