# bceval lessons and the dataset-v6 design (2026-10-02, researcher)

Tags: **[M]** measured by me today (scratch scripts, nothing in the repo edited), **[R]** read in a repo file (cited),
**[I]** my inference, untested. Every number from bceval's README that I could not reproduce is marked as **README claim**.

---

## 0. Bottom line

1. **bceval** (`tools/battlecode-eval/`, MIT, copyright "xCirno1", i.e. team Stockfish's xCirno [R `LICENSE`,
   `battlecode_chat_transcript.md:623`]) is a **round-dependent antisymmetric logistic regression**: 23 per-team board
   features + a side term, 5 weights each (knots r0/125/250/375/500, linearly interpolated), fitted on **5,678 games**
   [R `model.json` "games"]. It sees the whole board, so it is an after-the-fact judge, not a bot feature.
2. **It still calls new-rules games well, but on a biased sample**: on 179 new-rules public games won by top-12 teams
   (`ladder/scout_v6`), it picks the winner 81% at r50, 82% r100, 85% r200, 90% r300, 84% r400, 92% r490 [M]. It has no queen
   term, and **on public replays its 5 economy-rate features are silently zero** (TILE lines are zeroed; `features.py`
   reads spawn rates from them) [M]. Local and public bceval scores are therefore not comparable.
3. **What bceval says wins (old rules, conditional weights):** length is most of it. Total length and walking-distance
   territory decide the middle game, the longest dragon decides the end (weight 5.1 at r500). **At fixed total length, more
   bodies is worse after r125** (consolidation). Late on, the champion's free exits (+) and enemy heads within 6 steps (−)
   matter. Its README says it **cannot see one decision's effect for ~50 rounds**, so it must not be used as a per-decision
   reward or advantage weight. It is a trained model (fitting code and data not shipped). A queen-aware **bceval v2**
   (section 1.8) is worth ~1 day as an **offline secondary metric**. It is not worth it as a net training target or input.
   **The queen tiebreak is rarer than assumed [M, 306 top-team wins]:** 54% end by elimination; of the 142 that reach r500,
   both queens are dead in 118, so the queen tiebreak decided only **24 games (8%)**.
4. **New-rules data facts that change the v6 design** [M, 79 winning games from 3 top teams, 1.07M winner decisions]:
   - **Top winners leave free steps unused as much as we do:** at L≥5, winners' drones take fewer than ceil(L/4) steps on
     **86%** of moves and their queens on **90%**. Only ~0.9% of all moves are multi-step. The "we waste 62-79% of free
     steps" gap in `nn_plan.md`/`numbers.md` §4 is **not a gap against top teams**. A sprint head will be dominated by
     "1 step / stop". It ranks lower than `nn_plan.md` assumed.
   - **Winners' queens die early too:** 58/79 winning queens die; 22/79 by round 10 (the trapped-queen maps); only 21/79 are
     alive at the end. 40/79 games reach r500. Winner-queen decisions are ~1.2% of winner decisions (13.2k moves), and
     39% of them fall in r0-99.
   - Public replays carry the full multi-step `move` list, every sonar ping with `hitKind`, and `dragonSplit` sizes. They do
     **not** carry `pearlCountdown`, TILE gaps, indicators, or **bot names** (botA/botB are empty strings) [M].
   - Size: **~150 B/sample** compressed (16 planes), **~13.5k winner samples per game** without downsampling (20-26k for
     long big-map games), replays average **~1.3 MB** [M].
5. **Minimal v6 (section 9):** 19 planes (16 current, plane 8 zeroed, + queen-in-view, enemy-queen seen-memory, enemy
   free-step reach) + 6 scalars (adding is_queen, ceil(L/4)/8, steps-taken) + **one 7-way head** (F/R/B/L/split/other/STOP)
   trained on normal states **plus "continuation" states inside a sprint** (calc's trick). Body/head-length planes are
   computed **the way the bot sees them** (visible segments only), fixing a train/play skew in the current dataset.
   Expected ~1.5 GB of shards for 600 games. The trainer must stream shards, not load them.

---

## PART 1: bceval

### 1.1 Where it is and what it is

| Item | Location | Notes |
|---|---|---|
| Package | `tools/battlecode-eval/bceval/` (`features.py` 258 lines, `score.py` 79, `mapdata.py` 71, `replay.py`, `replay.capnp`, `model.json`) | Own `.venv` with pycapnp: `tools/battlecode-eval/.venv/Scripts/python.exe` works directly [M] |
| Author | `LICENSE`: "Copyright (c) 2026 xCirno1". Chat: "[Stockfish] xCirno: I tried that similar concept with an evaluation engine, 80% accuracy on end game prediction, still no result in the RL" (`battlecode_chat_transcript.md:623`) | The 80% matches the README's 84% at r401-490. That it is the same artefact is **[I]** |
| Batch tool | `tools/bceval_batch.py` | Classifies each game's p(us) trajectory: dominant / close / early (<r100) / mid (r100-300) / late (>r300) / recovered, threshold 0.3; `--by-winner` for scouted games |
| Outputs | `ladder/bceval_out/` (11 files: `live_gD/gJ/gM/gP`, `s60_*`, `s60b_*`) | Shape summaries of old-rules local panels, e.g. live_gP: dominant 16, early 11, late 9, mid 3, recovered 21 of 60 |
| Other users | `rulemine/evalstate.py` (p_win as mining context, `extract.py` adds it per row), `rulemine/evalpair.py` (p_win at r250/r400 in the paired screen), `tools/growth_pattern.py` (reuses `replay_features` for winners), `tools/param_search.py` (focused on maps bceval flagged as early collapses) | [R] |
| Docs | `S4_7_PLAYBOOK.md:54, 167, 215-226, 247-248`; `RESEARCH_METHODS.md:33`; `research_new_meta/strategy.md:196` ("Retrain on new-rule games or drop it") | [R] |

**Not found:** no bceval dataset, no training script, no write-up beyond the README. `calc WRITEUP.md` does not mention it
(calc says a learned value function did not help their search, which matches bceval's own warning).

### 1.2 Inputs (replay fields)

- `Replay.map` text: `MAP`, `EDGE` (kelp kind 1, portal kind 2 + partner id), `DRAGON` (start bodies, team), and **`TILE x y
  lo hi`** for spawn rates `2/(lo+hi)`, which give the "rich" tiles (mean gap ≤ 60) and the "hot" tiles (fastest tiles making 30% of supply).
- Events: `roundStart`, `turnStart` (who is acting, used to attribute eats), `tileChange` (pearl appear/eaten),
  `dragonAction.move` (list of directions, applied provisionally), `dragonUpdate` (authoritative head/tail),
  `dragonSplit` (full parent/child bodies), `dragonDeath` (reason 3 = head-to-head → kill credit).
- `GameResult`: winner, endReason, and per-team standing, used for an `ok` check (rebuilt alive/longest/total == engine).
  The rebuild was **ok on 179/179 new-rules public replays** [M]. So its body reconstruction, including multi-step moves,
  is a validated reference for our dataset builder (section 6).
- **Public-replay caveat [M]:** TILE lines are zeroed (only 1 of 513-2401 TILE lines non-zero in every public replay
  checked). So `eat_rich`, `eat_hot`, `supply`, `rich_ctrl`, and `hot_ctrl` are 0 for both teams and contribute nothing. bceval on
  ladder replays is effectively the bodies + fights + territory + pearls_near + champion model. Local replays have real
  TILEs. **Never compare a local bceval number to a ladder one.**
- botA/botB are **empty** in new public replays [M], so `bceval_batch.py --ours <id>` cannot find our side on ladder replays.
  Use the battle API's side (`teamAId`/`teamBId`) or `--by-winner`.

### 1.3 Features and fitted weights (from `model.json`; transforms: log = log1p difference, share = a/(a+b) − 0.5, lin = (a−b)/scale)

| feature | r0 | r125 | r250 | r375 | r500 | reading |
|---|---|---|---|---|---|---|
| alive (dragon count) | +0.62 | **−0.87** | −0.75 | −0.30 | −0.86 | more bodies helps only at the start; at fixed length, fewer bodies win |
| total length | +1.07 | **+2.40** | +1.97 | +0.90 | +1.20 | the mid-game driver |
| longest | −0.02 | +0.15 | +0.38 | +1.01 | **+5.12** | old round-500 tiebreak |
| second / third | +0.33/+0.42 | ~0 | ~0 | +0.35/+0.13 | ~0 | |
| big5 / big10 | ~0 | −0.29/−0.35 | −0.30/−0.31 | −0.25/−0.36 | −0.15/−0.31 | negative given total+longest (collinearity: "length spread over several mid-size bodies") |
| eat / eat_rich / eat_hot (25-round) | ~0 | ~0 | ~0 | ~0 | ~0 | eating is already in length; rates add nothing (eat_rich +0.37 at r0 only) |
| deaths (25-round) | +0.14 | −0.30 | −0.32 | +0.05 | +0.05 | mid-game deaths hurt **given** length |
| lost_len, kills_h2h | small | | | | | fights barely matter beyond their effect on length |
| terr (Voronoi share by walking distance) | +1.23 | +1.63 | +1.57 | **+1.75** | +0.64 | second biggest term all game |
| supply (pearl rate of territory) | +0.71 | **+1.86** | +0.91 | +0.68 | 0 | economy control, early-mid |
| rich_ctrl / hot_ctrl | | +0.26/−0.55 | +0.84/−0.21 | +0.87/−0.31 | | |
| pearls_near (pearls on our side of the Voronoi) | **+1.09** | +0.40 | −0.24 | +0.55 | +0.97 | |
| champ_enemy_d (/10) | −0.09 | 0 | +0.08 | +0.23 | +0.24 | late: champion far from enemy heads |
| champ_enemy_n3 (/2) | | | +0.10 | −0.07 | −0.24 | |
| champ_enemy_n6 (/4) | −0.34 | −0.22 | | | **−0.47** | late: enemy heads within 6 steps of the champion |
| champ_ally_d (/10) | | | | −0.17 | | |
| champ_exits (/2) | | | +0.08 | **+0.33** | +0.27 | late: free cells beside the champion's head |
| side (B) | −0.18 | −0.09 | −0.07 | −0.12 | −0.12 | side B small edge (id order) |

Regularisation C = 0.1. **README claims (not reproducible: no data shipped):** leave-one-official-map-out accuracy 66% (r1-100),
74%, 71%, 74%, 84% (r401-490); calibration 25%→29%, 45%→46%, 85%→85%; longest+total alone log-loss 0.502 vs 0.498;
forked continuations indistinguishable for ~50 rounds and only 57-62% separable at 50-120 rounds (2,880 forked games).

### 1.4 What our tools found with it (old rules) [R]

- 77.5% of wins in a 719-replay top-team sample are "dominant" throughout; only 21.6% are comebacks (`S4_7_PLAYBOOK.md:54`).
  This matches `growth_pattern.py`: winners run ~50% more units from r100 and double the loser's longest in r300-400.
- It dated Trophy losses to a crash by r19-40 on side B, and Slithery Fight ladder losses to r360-410. A local trace later
  contradicted the Slithery timing as opponent-specific (`S4_7_PLAYBOOK.md:167-226`).
- `ml/results.md` independently: a GBM predicts the winner 72% at r50, 79% at r200; units +6 at r100 → 82% win.

### 1.5 New-rules check [M]

179 public games (winners = top-12 teams), `replay_features(every=10)` + `win_probability`:

| round | n | winner called right | mean log-loss |
|---|---|---|---|
| 50 | 177 | 0.81 | 0.426 |
| 100 | 163 | 0.82 | 0.370 |
| 200 | 137 | 0.85 | 0.342 |
| 300 | 113 | 0.90 | 0.311 |
| 400 | 96 | 0.84 | 0.304 |
| 490 | 85 | 0.92 | 0.243 |

These are higher than the README's 66-84% because the sample is **top teams beating mostly weaker opponents** (easy games),
not because the model got better. n falls with round because ~half the games end by elimination. This does show the
length/territory core still separates games under the queen rule. It has no queen feature, so it cannot see a queen-tiebreak
reversal.

### 1.6 Lessons, sorted by use

**(a) Training targets / input features for the net**

| Lesson | Use | Verdict |
|---|---|---|
| Effects of one decision are invisible for ~50 rounds (README) | **Do not** weight samples by Δp_win or use p_win as a per-decision advantage. Consistent with AWR being neutral in `ml/results.md` | Hard "don't" |
| Territory (walking-distance Voronoi) and supply are the strongest mid-game terms | Not computable in-bot (whole board). Could be an **auxiliary training-only head** (predict own territory share in the crop region) with zero inference cost; prior is weak (joint value head was neutral) | Low; skip for v6 |
| Champion features late: exits +, enemy heads within 6 steps − | Under the queen rule this is the queen's safety. Inputs that expose it: **enemy-reach plane**, **is_queen**, enemy-queen memory (section 3) | Supports the v6 inputs |
| Enemy-head proximity uses walking distance, not Manhattan | Build reach planes by BFS over known kelp/portals, not by radius | Spec detail |
| Bodies: fewer, longer bodies beat many short ones after r125 at equal total | The net's targets stay imitation; this belongs to the rules (feed/merge timing) | Rules side |
| Side B edge ~0.1 logit | A side scalar would be nearly constant in our data (69/79 winners are side B) [M]: **leave it out** | Skip |

**(b) Rules / eval terms in the bot**

- **Consolidation from r125:** at equal total length, fewer bodies wins. Supports feeding and merging drones into the queen
  and stopping budding earlier than "max units". This contradicts nothing measured: the "deaths correlate positively with
  winning" post-mortem is unconditional, and bceval's −0.3 deaths weight is conditional on length.
- **Queen safety late:** keep ≥2 free exits next to the queen's head and no enemy head within ~6 walking steps
  (vB19 uses ≤2 cells). Correlational; test as a pre-registered rule change, not a param transplant.
- **Territory:** a large term, but our `wTerritory` attempts collapsed Dilemma twice (`RESEARCH_METHODS.md`). Do not retry as
  a flat weight.
- Eat-rate features add nothing beyond length: optimise length and units, not "eats per window".

**(c) Evaluating candidates**

- Keep `bceval_batch.py` shapes on every local batch (existing practice). Add p_win at r100/r200 as a **paired continuous
  secondary metric** (lower variance than W/L), for self-driven mechanisms only (`bc_replay_and_ladder_testing_facts`).
- **Never mix sources:** public replays lose the 5 economy features. Compare local with local and ladder with ladder.
- On ladder replays, identify our side from the battle API, not from bot names (now empty).
- **Retrain bceval for the new rules** (strategy.md's "retrain or drop"): add `queen_len`, `queen_alive`,
  `queen_enemy_n6`, `queen_exits`. Data: every scouted replay contains both teams; randomly swap A/B so labels are balanced.
  The selection bias (games top teams won) remains, so calibrate on a held-out set of our own ladder games. Fitting
  is ~100 lines with sklearn; inputs are `replay_features` + 4 queen features. Effort ~0.5 day. Value: a queen-aware
  "when did it turn" tool and a better evalpair secondary metric.

### 1.7 How bceval is built, and what our net can borrow from the method

It is a **trained model**, not a replay-metric tool (a metric tool would be `bceval_batch.py`, our wrapper). The fitting code
and data are **not shipped**. Below is what `score.py` + `model.json` + the README pin down; the rest is marked [I].

| Aspect | bceval | Source |
|---|---|---|
| Model | Logistic regression, no intercept, input = per-feature team **difference** (log1p-diff for counts, share−0.5 for ground, scaled diff for distances), so it is antisymmetric: swap teams → 1−p | `score.py` |
| Time dependence | Each feature × 5 "hat" basis functions over round (knots 0/125/250/375/500), so 24 × 5 = 120 weights: a weight curve per feature, not one number | `score.py:_hats`, `model.json` |
| Regularisation | `C = 0.1` (sklearn-style inverse L2) | `model.json` [I: sklearn `LogisticRegression`] |
| Data | 5,678 games, "ladder and local" | `model.json`, README |
| Rows / label | One row per (game, round) board state, every N rounds; label = final winner | README, `features.py:replay_features` [I: N unknown; rows from one game are correlated] |
| Validation | Leave-one-official-map-out; accuracy by round band 66/74/71/74/84%; calibration table; log-loss vs a 2-feature model; a **fork test** (2,880 continuations forked from one position: when do outcomes separate?) | README (claims) |
| What it encodes about winning | Sections 1.3/1.6. Its own summary: "most of what it knows is length" (longest+total alone 0.502 vs 0.498 log-loss) | README |

Methodology lessons for **our net and our evaluation**:
1. **Hold out by map, not just by game.** bceval reports leave-one-map-out. Our net's validation splits by game only, and
   calc warns that nets memorise official maps. → v6 hold-out (c), section 5.
2. **Antisymmetry = free augmentation.** bceval builds team symmetry into the model. Our egocentric frame + mirror flip is the
   analogue; extend the mirror to every new plane (section 7.4).
3. **Phase-dependent weights.** bceval gives each feature a weight curve over the rounds. For the net, round/500 is a broadcast
   input, so it can do the same. Per-phase validation (section 5.3) checks that it does.
4. **Fork test = the right test of a decision signal.** bceval's README shows a board-level evaluator cannot tell one decision
   from another for ~50 rounds. Any signal we want to train decisions on (value head, advantage weights, rule mining's
   p_win context) must pass the same check first: fork local games at a state, vary one decision, and see whether the
   signal separates continuations within ~20 rounds. `rulemine.evalpair` on paired seeds is half of this already.
5. **Simple and calibrated beats big.** 120 weights reach the same plateau as our GBM win predictor (72-79%). For outcome
   prediction, the information is in a few aggregates (length, units, territory). This matches our "capacity is saturated"
   finding for the net (`ml/results.md`).

### 1.8 Improving on bceval for the new rules ("bceval v2"), and how to use it

**Measured first [M, 306 top-team wins in `ladder/scout_v6`]:** 164 (54%) end by elimination. Of the 142 that reach r500,
**118 (83%) have both queens dead**, so the decision falls through to longest dragon / total. Only **24 (17% of r500 games,
8% of all)** are decided by the queen tiebreak, and in all 24 the winner had the longer queen. So under the current meta,
the old length/territory evaluator is still mostly right, and a queen term matters in a minority of games. It matters
more for us if we keep our queen alive (a strategy choice no top team has settled on yet).

**Design (features computable from public replays; team differences as in bceval; same knot scheme):**

| Group | New feature | Why (new rule) |
|---|---|---|
| Queen | `queen_alive`, `queen_len` (0 if dead), `queen_len − longest_other` | Tiebreak 1; a dead queen counts 0 |
| Queen safety | walking-BFS distance from queen head to the nearest enemy head **minus that enemy's free steps ceil(Le/4)** ("safety margin"); enemy heads that can reach in 1 turn; free exits beside the queen head | Long enemies now cover ceil(L/4) cells per turn for free; replaces champ_enemy_n3/n6 |
| Queen supply | allied units within 10 walking steps of the queen (feeder pool); pearls in the queen's Voronoi cell | Feeding is how queens grow late |
| Mobility | free steps of the longest dragon `ceil(L/4)`; share of the longest's last-25-round moves that were multi-step | The new movement economy |
| Horizon | rounds left `(500 − r)`, as an **interaction**: `queen_len_diff × (500−r)/500` and `feeder_pool_diff × (500−r)/500` | A queen lead with 20 rounds left is final; with 300 left it is not |
| Keep | bceval's bodies, territory (walking Voronoi), pearls_near, deaths, alive; **drop** eat_rich/eat_hot/supply/rich/hot when TILE is zeroed (public replays) or fill them from `maps/*.map` by MAP_NAME on known maps | Avoids the silent-zero problem |

**Targets (better than W/L alone):**
- Main: P(win) (as bceval).
- Auxiliary **margin regressions**, less noisy than a binary outcome: final queen length difference, final longest difference,
  and `ended_by_elimination`. A paired screen can then compare **expected margin** instead of a win flip.
- Train on both sides of every scouted game (random A/B swap gives balanced labels). Hold out by map **and** by team. Validate
  calibration and run the fork test on local games.
- Data: `ladder/scout_v6` (306 games now) + all local new-rules panels (`out/*`, which have real TILEs and both outcomes).
  ~1,000 games are enough for ~150 weights [I]. Effort ~1 day including the fork test.

**(i) As an offline metric for candidates: yes, as a secondary.** Report the paired difference of p_win (and expected
queen-length margin) at r100/r200/r300, averaged over the paired (map, seed, side) games, next to W/L. It is continuous, so its
variance per pair is lower than a win flip [I: must be checked by computing the paired SD on an existing panel pair, e.g. the
wnn_sweep outputs]. It is only valid for local vs local, and it never replaces the ladder A/B. It also can't see a
candidate's effect in the first ~50 rounds after a change in behaviour, so read it at r200+ for mid-game changes.

**(ii) As a training signal or input for the move net: mostly no.**
- *Input:* it needs the whole board; the bot sees 7x7 plus memory. A bot-side "local eval" would be a different model.
- *Per-decision value target / AWR weight / RL reward:* ruled out by bceval's own fork result (no separation for ~50 rounds),
  by our neutral AWR/value-head results, and by calc's "learned value function did not help". A v2 does not fix this:
  board aggregates simply move slowly.
- *What does work:* (a) **game/segment filter**: drop winner decisions from stretches where the demonstrator was already
  lost (p_win < 0.1 for 50+ rounds, desperation play) [I, small effect]; (b) **leaf evaluation inside a future search**
  (`nn_plan.md` option E): calc scored rollouts by "our total length minus theirs". A bot-computable subset of v2 (own
  length, queen length, visible enemies' reach to our queen) is the natural new-rules leaf score. That is a rules/search
  use, not net training.

### 1.9 Could not verify

- The 5,678-game composition (which teams, local vs ladder, old-rule versions), the accuracy table, the calibration, and the
  fork experiment: no data or fitting code ships.
- Whether its ladder training replays already had TILE zeroed. If they did, the economy weights were fitted partly on zeros.
- That xCirno's chat "evaluation engine" is this package (likely, by LICENSE plus the matching accuracy).
- My 179-game check is winners-only and top-team-only; it says nothing about close games between equal teams.

---

## PART 2: dataset v6

Fixed by the director (not re-argued): plane 8 = 0 in training and inference; replay-only information; no 35% late
downsampling (`ml/build_dataset.py:160`, `keep_late=0.35`); disk-limited streaming shards; new-rules winners from top teams
(`ladder/scout_v6/`).

### 2.0 What the current builder does, and two skews it has [R `ml/build_dataset.py`, `baselines/vB19/main.cpp:1519-1558`]

- Inputs: 16 uint8 planes 15x15 (egocentric, rotated to facing) + scalars len/32, round/500, units/64 (the builder also writes
  three prev-turn bits; the bot uses 3 scalars). Label: first step of the move, or split, or other. Snapshot at `turnStart`.
- **Skew 1, terrain (planes 0-7):** the builder uses the full map; the bot uses `effK` = seen kelp, else the known-map table.
  This is exact on the 10 ladder maps (all in `maps/`). On unseen maps (sprint, final) the bot only has seen cells: the
  same structural skew the critic found for plane 8.
- **Skew 2, other dragons (planes 12-15):** the builder writes rounds-until-free `(L−k)*16` and head length `L*8` from the
  **true** full body. The bot writes `visFree = behind+1 (+2 if uncertain)` and `estLen` from **visible** segments only
  (`main.cpp:621, 632`). Whenever an enemy's tail is out of view, train and play disagree. Cheap to fix in v6: compute
  them with the bot's rule (count segments behind the cell that are inside the 7x7, +2 if the chain leaves the view).

### 2.1 Facts from the new-rules replays [M; 79 winning games of teams 112, 206, 952, 1.6M decisions both sides]

| Fact | Value |
|---|---|
| Winner decisions per game | 13.5k average (Trauma 20.8k, Schooltime 25.6k) |
| Winner decisions at round ≥200 | 61%. Removing the 35% downsampling gives ~1.65x more samples than the old recipe |
| Label mix (Trauma winner) | F 8,009 / R 5,894 / B 293 / L 6,045 / split 561 / other 0 |
| Splits | 2.4% of winner drone decisions (25,615); queen 279 |
| Multi-step moves | ~0.9% of moves (team 952 sample: 2,135 two-step, 414 three-step, 545 four-step of 340k) |
| Multi-step by length (team 952) | L12-15: 7% four-step; L16-19: 15%; L20-23: 13%; L24+: 11%. Almost never 5+ even when free (possible team habit) |
| Free steps unused at L≥5 (winners) | drones 86% of moves (74,303 vs 12,199 at the full allowance); queens 90% |
| Winner queen | died in 58/79 games; 22 by round 10; alive at end in 21/79 |
| Games reaching r500 | 40/79 |
| Sonar | ~1.8 pings per dragon-turn; 91% of hits land on own team, 9% on enemies; `value64` + `hitKind` present |
| Side | 69/79 winners are side B (scouting artefact) |
| Replay size | avg ~1.3 MB; big maps 2.1-2.5 MB (mostly sonar events); eliminations 50-120 KB |

### 3. (1) New inputs: availability, cost, value

Cost reference: the conv net is ~2.2M MACs at ~18M points per call [R `ml/results.md`]; the first conv dominates
(15x15x(planes+scalars)x32x9). Each extra input channel adds ~65k MACs, i.e. ~0.5M points [I, scaled]. Bot max turn should stay ≤ 65M.

| # | Feature | Public replay | Bot at play time | Parity | Bot CPU | Expected value |
|---|---|---|---|---|---|---|
| F1 | **is_queen** scalar (my id is my team's queen id 0/1; team from DRAGON order) | exact | `MY_ID`, already `isTrueQueen()` | exact | ~0 | **High.** The net cannot tell the queen today; vB19 hacks around it with wNN 0.4. Queen samples ~1.2%: weight them x3 |
| F2 | **queens-in-view plane**: own queen segments 128, own queen head 255 (0 for self); enemy queen head 255, body 128 | exact (ids in DRAGON_BODIES) | exact (vision gives id) | exact | +1-2 channels, ~1M pts | **High-medium**: protect/feed own queen, hunt the enemy queen |
| F3 | **enemy-queen last-seen memory**: outside view, this dragon's own last sighting of the enemy queen head, `200*exp(−age/40)`, age ≤100; child starts blank | exact (per-dragon memory from replay) | needs 2 ints per dragon (new; **not** the sonar EQPOS relay, which is not in replays) | exact if the bot uses only its own sightings for this plane | ~0 | Medium-low (most dragons never see her). Merge into the F2 channel to save a plane |
| F4 | **enemy free-step reach plane**: for each enemy head in view, cells within s = ceil(estLen/4) BFS steps over known terrain (portals followed), value 255−60(d−1) | exact (using visible estLen as the bot does) | bot already has `EnemyReach` with `spd=(estLen+3)/4` (`main.cpp:784-787`): port that exact function into the builder | exact if ported | ~0.5M pts + a BFS already done | **Medium.** The new rule lets long enemies cover 3-5 cells a turn, and bceval's late champion term is about enemy heads in walking range |
| F5 | **free steps** scalar ceil(L/4)/8 | exact | exact | exact | ~0 | Medium (the net only sees len/32; a step function is easier to give than to learn) |
| F6 | **steps-taken-this-turn** scalar (0 normally, j inside a sprint, section 5) | exact | exact | exact | ~0 | Needed for the STOP/continue head |
| F7 | round/500 (existing) + phase | exact | exact | exact | 0 | Keep round/500; phase bins add little to a conv+FC net [I] |
| F8 | unit count (existing units/64) | truth | bot's UNITS estimate | approximate (existing) | 0 | Keep as is |
| F9 | own queen alive / distance / length | truth only | belief via vB19 sonar QPOS; demonstrators' beliefs come from their own (encrypted) sonar | **skewed**: truth vs belief | 0 | Unknown; leave out of minimal v6. A/B later as a scalar if F1-F2 help |
| F10 | sonar echo counts (kelp/ally/ally_head/enemy/enemy_head of my last-turn pings) | exact (`hitKind` + sender) | exact | input exact, but it depends on **which** directions the demonstrator pinged (policy leakage) | ~0 | Low; skip |
| F11 | received-sonar count | exact (`hit` id) | exact | content opaque, sender unknown | 0 | Low; skip |
| F12 | seen-terrain mask + memory regime (planes 0-7 = seen-only in some games) | emulable per dragon (`rulemine/state.py` already tracks seen terrain per dragon, child blank) | `obsK` vs `KM` | exact if the bot sets mask=255 on known maps and seen-only otherwise | +1 channel | **0 on the ladder, positive for the unseen-map final.** Per-game regime mix: 70% full map / 30% seen-only [I, following the critic's plane-8 scheme] |
| F13 | team side | exact | exact | exact | 0 | Skip: nearly constant in our data (69/79 side B) |
| F14 | remembered-pearls plane | exact | exact | exact | +1 | Measured neutral (v5, −0.5 pt). Skip |
| F15 | **queen safety margin** scalar (when I am the queen): min over visible enemy heads of (BFS distance to my head − ceil(Le/4)), clipped [−2, 8]/8 | exact | exact (from F4's BFS) | exact | ~0 | Medium for queen samples; it is F4 condensed. Free if F4 exists |
| F16 | **rounds left to r500** / phase interaction: `(500−r)/500` is already round/500; add `is_queen × (500−r)/500` | exact | exact | exact | 0 | Low; the FC layer can form it. Skip unless queen accuracy is poor |
| F17 | **feeding context**: allied heads within view that are longer than me / are the queen (count) | exact | exact | exact | 0 | Low-medium for the drones' feed decision; mostly covered by F2 |

New-rules-only **data** worth extracting even if not used as inputs (for rules and for bceval v2): per game, queen death
round and cause (wall/self/body/head-on, and whether the killer was sprinting: `tools/sprint_purpose.py`), feed events
(rulemine `fed_ok`), the queen's free-step use, and which r500 tiebreak decided. These are cheap to dump in the same pass
as the shards (one row per game in a CSV next to the shards).

### 4. (2) New targets / heads

| Head | Label source | Data volume | Use in bot | Value / effort |
|---|---|---|---|---|
| **STOP/continue as a 7th class on continuation states** (calc's trick: "two sets of move inputs (forward and forward + next move) where the second moves the dragon's view and forwards it into the net again", transcript:744; calc writeup: "whether to keep sprinting after each step") | `dragonAction.move` direction list (section 6) | For every move by an L≥5 dragon: one extra sample per step taken; ~8-10% more samples | FSPRINT path score += wNN·Σ log p(step_j \| state_j) incl. STOP at the end, for paths FSPRINT already enumerates; 1 extra net call per step considered, only for L≥5 dragons and under an `elapsedMs()` guard | **Medium-low**: top teams rarely sprint (0.9%), so the head mostly learns *when not to*. Its worth is in the rare escape/strike states. 1 day |
| Separate steps-count head (1/2/3/4+) | same | same | prior on path length | Dominated by the 7th-class formulation (that one also gives the direction of each step). Skip |
| Split size head | `dragonSplit` child length / L, 3 bins | 2.4% of decisions | prior in `trySplit` | Low; queen splits must stay rule-gated (`AGENT_LOG` qdoomed_off). Optional aux head, 0.3 day |
| Feed / death-intent head | moves ending in own death | | | Dropped by the retrain_debate verdict (confounded). Skip |
| Future first-steps t+1, t+2 (aux, training only) | the same dragon's next turns | free | none (dropped at export) | Low; representation-only, offline gains have never transferred. Skip in v6 |

### 5. (3) Sample weighting and filters

1. **Date filter:** keep a game only if its battle `at` ≥ the rules-change time. `fetch.py` reads each team's `recent` list
   with **no date or game-id filter**, and stores `at` in `manifest.csv`. All pre-switch submissions were deactivated, so
   `at` is sufficient.
2. **Winners only, top-team side only** (fixed). **Exclude `ladder/scout_v6/own/98`** (fetch.py stores our own wins there
   with `OURS=98`): our own style must not leak in. If wanted later, mix it as a separate folder with `--max-samples`.
3. **No late downsampling** (fixed). Report validation per phase (r<100, 100-300, 300+), so a regression in the opening
   (the phase that decides most games: r50 72-81% predictive) is visible.
4. **Queen samples x3** in the loss (1.2% → ~3.5% effective). Do not go higher: the queen dies early in 73% of winning
   games, so the queen samples are mostly r0-100.
5. **Dedupe:** hash (planes bytes, scalars, label). Cap each hash at 4 copies dataset-wide. Deterministic bots replay the
   same openings on the same map across games [I]. Cost: one 8-byte hash per sample.
6. **Per-team cap:** no team above 30% of samples (subsample its games). Teams' download volume is uneven.
7. **Hold-outs (diagnostic only):** (a) 10% of games by game id (as now); (b) leave-one-team-out; (c) leave-one-map-out.
   Report all three. Only (a) is used for early stopping.
8. **Side:** no side input, so the 69/79 side-B skew is harmless for an egocentric net.
9. **Do not** use AWR, bceval-Δp, label smoothing changes, or team conditioning (all measured neutral, `ml/results.md`).

### 6. (4) Sprint labels: encoding and reconstruction

- **Encoding [R `tools/replay.py:198-204`, bceval `features.py`; M]:** one `dragonAction` per dragon-turn. `act.move` is a
  `List(UInt16)` of **absolute** directions (0 N, 1 E, 2 S, 3 W) in the order declared. Its length k is the number of steps.
  The engine applies them one by one (collision and eating per step). The move list is the **declared** decision: if the
  dragon cannot pay (k > ceil(L/4) + L − 1), it dies mid-sprint, and the list still shows all k steps. Then exactly one
  `dragonUpdate` gives the **final** head, tail and facing (authoritative). Splits are `act.split` with `size`; suicide is
  its own variant.
- **Reconstruction (per move, L and facing f₀ at turnStart, pearls P at turnStart):**
  ```
  head = body[0]; F = ceil(L/4)
  for j, a in enumerate(dirs, 1):
      rel_j = (a - f_{j-1}) % 4            # 0 fwd, 1 right, 2 back, 3 left  (label of step j)
      dest, f_j = step(board, head, a)     # bceval mapdata.step semantics; f_j = exit direction (changes through a
                                           # portal whose partner edge has the other orientation)
      if dest is None or dest in occupied: died at step j -> stop generating
      body.insert(0, dest)
      if dest in P: P.remove(dest)  (grow) else: body.pop()
      if j > F: body.pop()                  # paid step
  ```
  Then check that the rebuilt head/tail equals the `dragonUpdate`; on mismatch, drop the game's continuation samples and
  count it (bceval's rebuild matched 179/179 games, so mismatches should be rare).
- **Continuation samples:** for an L≥5 move with k steps, emit states j = 1..k. The input is the crop re-centred on the head
  after j steps and rotated to f_j, with own body/pearls updated. **Every other cell keeps the turn-start observation**:
  the dragon does not see from intermediate cells. Plane 9 (view) marks the turn-start 7x7 window in the new frame, so the
  bot can rebuild exactly the same input from its own state. Scalar steps_taken = j/4. Label = rel_{j+1}, or **STOP** at j = k.
  Generate STOP samples only while j < F + 2 (the free range plus a margin), so the class reflects real choices [I].
  Class masks: at j = 0 STOP is illegal; at j ≥ 1 split/other are illegal (mask the logits in the loss and in the bot).

### 7. (5) Size, disk, memory, build paradigm

| Quantity | Estimate |
|---|---|
| Samples/game (winner side, no downsampling) | 13.5k avg [M] + ~9% continuation |
| Bytes/sample compressed | 143-152 B at 16 planes [M] → ~180 B at 19 planes [I] |
| 300 games | ~4.4M samples, ~0.8 GB shards |
| 600 games | ~8.8M samples, **~1.6 GB** shards |
| Replays | ~1.3 MB each; 600 = ~0.8 GB transient (fetch.py caps at 1.5 GB) |
| Disk free now | 5.5 GB (`df -h /c`) [M] |
| Build speed | 10-20 s/game single process with the old builder [M]; 600 games / 4 workers ≈ 40-50 min |

Paradigm:
1. **Decode with `tools/replay_lite.decode_lite(path, kinds)`**, never `replay.load` (it writes a `.pkl` next to every
   replay, doubling disk). Exclude `sonarPing` from `kinds` (about half of all events on big maps, ~45%), unless F10 is adopted.
2. Per-game worker → arrays; parent appends to a buffer and flushes `shard_NNN.npz` at 50k samples. After each flush, append
   the game ids to `done.txt`. On restart, skip games in `done.txt` (resumable). `mp.Pool(4, maxtasksperchild=8)`, and
   run `tools/mem_guard.sh 3000` before starting. Peak per worker ≈ decode (~300 MB on the biggest maps) + one game's samples
   (~25k × 4.3 KB ≈ 110 MB). **Total <2 GB at 4 workers.**
3. Delete each replay only after the shard containing it is flushed and recorded (the server keeps public replays, so the
   manifest is enough to re-fetch). Check `df` before and after.
4. **Trainer (`ml/train_v6.py`, Python310 CUDA torch):** the current `train.py` loads everything into RAM: 8.8M × 4.3 KB =
   38 GB, impossible. Stream instead: each epoch, shuffle the shard order, load 2 shards at a time (~0.5 GB), shuffle
   within them, and send uint8 batches to the GPU. Validation shards are fixed by game id. Mirror augmentation as now, extended:
   swap the left/right kelp/portal planes, mirror F2-F4/F12 spatially, and swap R↔L labels, including continuation labels.
5. Record in `AGENT_LOG.md`: games per team, samples, label histogram (7 classes), queen samples, continuation samples,
   dedupe drop rate, shard bytes.

### 8. (6) Validation that does not rely on offline accuracy

Offline accuracy gains never transferred (5+ times, `ml/results.md`). Offline numbers are sanity checks only.
1. **Parity gate (blocking):** a debug copy of the bot dumps its 19-plane input + scalars at ~200 states from a local game.
   The builder, run on that game's replay, must produce **byte-identical** planes 0-18 (allowing differences only on
   plane 12-15 cells whose tails are uncertain) and the same top move on ≥95% (old check: 560/581). Continuation states
   are checked the same way.
2. **Sanity (non-blocking):** held-out game accuracy no more than 1 pt below a 16-plane control trained on the same v6 data
   (this isolates the new inputs); per-phase and per-class accuracy; queen-sample and STOP-class accuracy. Offline A/B
   attribution: `nr1` vs `nr1_noq` (no F1-F3), same seed.
3. **wNN re-sweep** for the new net (0/1/2/4; the queen weight 0.4 vs 1.0, since the net now knows the queen). The optimum moves
   with the net (the old sweep: wNN0 11/40, wNN2 23/40, `wnn_sweep_results.md`).
4. **Paired local screen** (`panel_zig.py` + `rulemine.evalpair`, live and dev reported separately, pre-registered in
   `AGENT_LOG.md`). End metric: paired W/L with SPRT p1 = 0.65. Mechanism metrics: queen alive at r250/r400, queen
   length, head-on deaths own/enemy, **free-step use at L≥5** (target: approach the winners' 14% "full allowance" rate,
   not 100%), deaths to enemy sprints (`tools/sprint_purpose.py`), bceval p_win at r100/r200 (local vs local only).
5. **Ladder decides:** same-time A/B against a vB19 control arm (`ab_ladder.py`, near-rating teams, ~100 games per arm).
   Expect calc's shrinkage (+5% local → +1.5-2% ladder).

### 9. Ranking (expected gain per effort) and minimal v6 spec

| Rank | Addition | Gain | Effort |
|---|---|---|---|
| 1 | New-rules winners, no downsampling, plane 8 = 0, date filter, exclude own/98 (fixed core) | high (net is stale; wNN0 is −12/40) | 0.5 d |
| 2 | F1 is_queen + F2 queens-in-view | high-medium | 0.3 d |
| 3 | Visible-length parity for planes 12-15 | medium (removes a skew in every sample) | 0.3 d |
| 4 | Dedupe + per-team cap + queen x3 | small-medium | 0.2 d |
| 5 | F5 free steps scalar + F4 enemy reach plane (port `EnemyReach`) | medium | 0.5 d |
| 6 | Continuation samples + STOP class (+ bot FSPRINT hook) | medium-low (rare sprints) | 1 d |
| 7 | F3 enemy-queen seen-memory (in F2's channel) | low-medium | 0.3 d |
| 8 | F12 terrain seen-mask regime mix | 0 ladder / + final | 0.7 d |
| 9 | bceval v2 with queen features (evaluation tool) | eval quality | 0.5 d |
| — | F9 queen-belief scalars, split-size head, aux future moves, echoes, side, pearl memory | low / unknown | skip in v6 |

**Minimal v6 spec (for the trainer agent):**

- **Planes** (uint8, 15x15, head at (7,7), rotated so facing = up; `NPLANES = 19`):
  - 0-3 kelp up/right/down/left; 4-7 portal (full map, as now; ladder parity).
  - 8 **all zero** (kept for layout; export may drop the channel since its weights multiply 0).
  - 9 view (7x7 = 255); 10 pearl in view; 11 own body `(L−k)*16`.
  - 12/13 ally/enemy body rounds-until-free and 14/15 ally/enemy head length ×8, **computed as the bot does**: segments
    visible behind the cell + 1, +2 if the chain leaves the view; head length = the same `estLen`.
  - 16 **queens**: own-team queen head 255 / body 128 (0 if I am the queen); enemy queen head 255 / body 160 in view;
    outside view, this dragon's last sighting of the enemy-queen head, `min(150, 150*exp(−age/40))`, age ≤ 100. (Own
    vs enemy are separated by value bands; if the critic prefers, split into 16 = own queen, 17 = enemy queen and shift below by one.)
  - 17 **enemy reach**: for each enemy head in view, BFS over known terrain up to s = ceil(estLen/4) steps; cell value
    `255 − 60·(d−1)`, max over enemies; head cell itself 255.
  - 18 reserved = 0 in v6.0 (slot for F12's mask in v6.1; zero costs nothing at export).
- **Scalars** (float32, 6): `len/32, round/500, units/64, is_queen, ceil(L/4)/8, steps_taken/4`.
- **Head:** 7 logits `[F, R, B, L, split, other, STOP]`. Legal mask: steps_taken = 0 → STOP masked; steps_taken ≥ 1 →
  split/other masked.
- **Samples:** every winner-team dragon decision (j = 0), plus continuation states j = 1..k for moves by L≥5 dragons
  (section 6), with STOP generated while j < ceil(L/4) + 2.
- **Meta per sample** (int32): game, team, map hash, round, dragon id, L, facing, j, k, died_this_turn, is_queen, fut20 (as now).
- **Loss:** masked CE; weights queen x3, else 1; mirror augmentation (swap planes 1↔3 and 5↔7, flip spatially, swap labels R↔L).
- **Model:** the current `Policy` with planes = 19, scalars = 6, classes = 7 (c1 input 25 ch vs 19: ~+17% MACs → ~21M points
  per call [I]). Continuation calls only for L≥5 dragons under an `elapsedMs()` guard. Keep the max turn ≤ 65M.
- **Builder:** `ml/build_dataset_v6.py` (new file; old untouched), `decode_lite`, 4 workers, `done.txt` resume, delete
  replays after flush, `manifest.csv` as the index (`winner_side` a/b → side 0/1; `group == "top"` only; `at` ≥ the
  switch).
- **Trainer:** `ml/train_v6.py`, streaming shard loader, Python310 CUDA, ≤1 GB host RAM for data.
