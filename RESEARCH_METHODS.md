# Methods ledger: what we tried, what worked, what should have been tried, what to try next

Written 2026-09-30 from this repo's own records: `HANDOFF.md`, `S4_7_PLAYBOOK.md`, `INSIGHTS_AND_PLAYBOOK.md`,
`insights.md` (read from line ~1986 to the end), `ml/results.md`. It was not written from replays or bot source, so
every result below is quoted from your notes, not re-measured. External techniques (SPRT, PPO, DAgger, etc.) are
cited the way your notes cite them. I did not re-verify those sources.

## 0. Bottom line

1. **Only two things have ever moved real ladder results.**
   - The **imitation network on top of V7.12** (`Y.7.12-nn.1`): maze-map ladder record 32-37% -> 53-65%, and 16/20 vs
     6/20 for V7.12 in a same-time control.
   - The **Abyss-style safety rewrite** (S4.7, flood-fill before every move): it removed the 93%-self-inflicted-death
     bug. It did not make the bot competitive: about 22% on the real ladder.
2. **Everything since is null, negative, or unresolved.** That covers 20+ S4.x builds, all NN refinements, sonar,
   the late-schedule shift, and the horizon and terrain transplants.
3. **The bottleneck is measurement, more than ideas.** Local self-play vs the champion sits at ~50% whatever you
   change. The 32-game panel has a measured 7-9pp optimism bias (4 independent confirmations). A 40-game gate cannot
   tell 42.5% from 50% (see section 5).
4. **The best unshipped lead is the queen fix.** `viper_nn_queen250c` cut the queen splitting herself from ~36 to
   ~7 times per game, matching Stockfish's ~5. It has a mechanism check but no ladder A/B yet.

## 1. What worked

| Method | Evidence | Verdict |
|---|---|---|
| Imitation network (egocentric 15x15 planes, mirror aug) added as `wNN x log p(move)`, maze maps only | Ladder maze 32-37% -> 53-65%. `exp_nn_w2m` 88% vs V7.12 locally. Ladder 24/40 vs V7.12's historical 6/40 | **The one big win** |
| Abyss flood-fill safety before every move (S4.7) | DOOMED deaths no longer dominant | Fixed a bug class. Did not raise the ladder ceiling |
| Pearl gossip + local crowd avoidance (S4.7) | ~56.6% vs V7.12 on clean maps, up from 20-40% (S4.6) | Local gain only |
| `splitEnemyDist` swarm exemption | "Single biggest lever" of the S4.7 rebuild | Local gain |
| Spawn-based instant map resolution; map-adaptive `gamma` (bed density) | Fixed a real DOOMED regression; `gamma` adaptation validated on known maps | Works on known maps only (see section 3, item 7) |
| Churn Engine (S4.3), first build above 50% vs v7.12 | 75/140 = 53.6%, 95% CI 45.3-61.6% | Not distinguishable from 50% |
| **Tooling**: `tempo.py` (edge@r50), `bceval` win-prob, `death_context.py`, `behaviour_profile.py`, Zig judge (~2.8x faster, byte-identical), SPRT driver, `errors` bucket fix in `tourney.py` | Each found or removed a real problem | Kept. This is where most of the durable value is |
| `feedDist` 3->2 | Feed deaths within 2 of the queen 41% -> 94%. Recycled by own team 66% -> 75% | Real mechanism gain, but gate 42.5% |
| Queen election on visible length only (`queen250c`) | Queen self-splits ~36 -> 6.8 per game. Identity churn 65 -> 17 | **Correct fix, not yet ladder-tested** |
| S4.24 arrival-time pearl probability | edge@r100 -3.0 -> +1.0, but SPRT settled at 54.4% of 125 (CI 45.7-62.9%) | Marginal, shelved |

## 2. What did not work

| Method | Result |
|---|---|
| Flat-weight parameter search (8 hours, hundreds of games) | Zero validated gains (5 of 5 flat-param experiments failed) |
| Safety/territory/choke features (`wTerritory`, `wChoke`, `chamberCheck`, `wProbeDanger`, kelp-trap hunt) | Null or worse. Dilemma collapsed 75% -> 0% under territory, twice |
| S4.8 (4 bundled features) | SPRT 50.7% of 150. Uninterpretable and null |
| `splitStopRound=250` (S4.9), gossiped queen feed (S4.10), `swarmChild` 3->2 (S4.11) | Nulls. S4.11 was predictable on paper: it changes neither split count nor total length |
| `wCompass` | Inert. 24/24 games byte-identical with it off. The "+8.3pp validated gain" was noise |
| Five transplants of v7.12 pieces | `wHot` max: null. Consensus kelp: eating 12x worse. Committed routing: null. `friendCloser`: eating 10x worse. `gamma` 0.86: r50 edge 10.5 -> 7.0 |
| Time-aware teammate bodies (S4.25/26) | Win 53% -> 34%, still bad after the coiled-body bug fix |
| NN refinements: more data, v2-v5, TTA, ensembles, distillation, Q/AWR, joint policy+value, team style, memory plane | All ~50% vs champion, all neutral on the ladder. Offline gains (+0.5 to +1.4 points) never showed up in play |
| Sonar: lane sonar, sonar replay attack, jam, signed gossip | Neutral. Jam/replay build: 5/30 |
| PPO fine-tuning (runs 1-6) | Worse than imitation (0.25-0.45). Run 6 killed by low memory. Never got a fair test |
| Late-schedule shift (`viper_nn_schedule`, S.1) | Gate 20/40. Ladder 4/25 vs control 8/25. Fisher p~0.3: not shown worse, not shown better |
| Opening fountain rush (V7.13) | Early eating +10%, deaths rose, 5/25 vs strong teams |
| Earlier queen (round 250) locally, mass feed from 350, late cull everywhere | Worse (15/42 and similar) |

## 3. Why the failures share a shape

1. **Coordination was hiding in crude constraints.** Twice, removing a blunt constraint (hard friend-zero, blocking
   teammate bodies) cost more than the accuracy it bought. Your own diagnosis: the short-horizon forager and v7.12's
   long-horizon planner are two coherent designs, and you can't interpolate between them one parameter at a time.
2. **Wrong yardstick.** ~50% vs v7.12 is ~22% real; v7.12 is ~15% vs the 1700+ field.
3. **Wrong sign and wrong phase, repeatedly.**
   - Deaths correlate positively with winning (84% win with more deaths vs 20% with fewer), so "reduce deaths" pointed
     backwards.
   - The round-50 thesis held for S4.x vs v7.12 but not for the champion. Its early game is top-16 grade on every rate.
   - "Consolidate later" was then reversed by the cycle-2 read: top teams grow a queen from about r250 in parallel with
     late budding.
4. **Bundling and no control arm** (S4.8, `viper_nn_late`, S.1's first "refuted" verdict).
5. **Mechanism not checked before testing.** Four S4.8-S4.11 nulls were derivable on paper.
6. **Complexity compounding**: 68 -> 93 params, 11 inert, `common.hpp` 57% comments.
7. **Known-map dependence.** Nearly every validated local gain uses exact known-map data. On 30 procedurally
   generated maps the bot won 15-22% vs v7.12. This sits uneasily with your rule "no map-specific strategies": the
   embedded map tables (`maps_data.hpp`, `knownmap.hpp`) are map-specific inputs, even where the strategy isn't.

## 4. What should have been tried earlier

- **A same-time ladder control arm from day one.** Your notes state this only after S.1 (`tools/ab_ladder.py` now
  exists).
- **SPRT and Bradley-Terry before the first parameter search.** `tempo.py` (a continuous, low-variance metric) was
  built after weeks of binary win-rate testing.
- **Behavioural cloning first.** It was the one thing that worked, and it only arrived when the S4 line had already
  gone flat.
- **Reading the top teams' queen behaviour before the schedule.** The cycle-2 data (queen length at r300 of 12-17
  for top teams vs our ~5) would have avoided S.1.
- **The Trauma deadlock**: feeding required a teammate of length >= 10, but nothing reaches 10 without being fed.
  It is a logic bug you could have found by reading the code against the rules, before any experiment.
- **Local-combat lookahead and decentralised roles.** Both were noted from the Loong blog. The only port is
  `kamikazeLen`, which is gated off and was never A/B tested.

## 5. Statistics: why most conclusions above are inconclusive

Wilson 95% intervals for the results in your notes, computed here:

| Result | Point | 95% CI |
|---|---|---|
| S4.3 75/140 | 53.6% | 45.3-61.6 |
| S4.6 74/140 | 52.9% | 44.6-60.9 |
| S4.24 SPRT 68/125 | 54.4% | 45.7-62.9 |
| S4.8 SPRT 76/150 | 50.7% | 42.7-58.6 |
| Gate 20/40 (`nn_schedule`) | 50.0% | 35.2-64.8 |
| Gate 17/40 (`nn_feeddist`) | 42.5% | 28.5-57.8 |
| Panel 20/32 (S4.24 headline) | 62.5% | 45.3-77.1 |
| Ladder S.1 4/25 vs control 8/25 | 16% vs 32% | 6.4-34.7 vs 17.2-51.6 |
| Ladder NN 24/40 | 60% | 44.6-73.7 |

Required games (normal approximation, alpha 0.05 two-sided, power 0.8):

| Detect | One-sample vs 50% | Two-arm ladder A/B, per arm |
|---|---|---|
| 55% / +5pp | ~783 | ~1,560 |
| 60% / +10pp | ~194 | ~387 |
| 65% / +15pp | ~85 | ~169 |
| 70% / +20pp | ~47 | ~93 |

Consequences:
- **No S4.x result from S4.3 to S4.6 is distinguishable from 50%.** All of them sit at 50-54%.
- **The 58.6% vs 41.4% side gap (S4.4) is noise.** SE of a difference at 70 games per side is 8.5pp.
- **SPRT with p0=0.5, p1=0.6 needs ~146 games on average even when it works** (expected LLR per game +/-0.02, bound
  +/-2.944). Your S4.24 run at n=125 was still oscillating near zero, as expected for a true ~54%.
- **A 40-game gate is a smoke test, not a promotion criterion.** Use it to catch crashes and timeouts.
- **The right unit for small ideas is a mechanism metric, not win rate.** Examples: queen self-split count, feed
  recycle %, eats/dragon-turn, edge@r50. Your own paired mechanism checks (`feedDist`, `queen250c`) were the most
  informative work in the folder.

## 6. What I would do next (map-agnostic, ordered)

1. **Ladder-A/B `queen250c`.** Same-time control arm, near-rating opponents (about 50% baseline, not 2000+ teams
   where you are on the floor), ~100 games per arm to resolve ~20pp, plus the queen mechanism metrics. It is the
   only fix with a demonstrated mechanism shift toward the top teams' numbers. Then attack layer 3: the stable queen
   still barely eats (about 9 vs Stockfish's 34 over r250-500).
2. **Change the metric before any new feature.** Adopt: (a) mechanism metric per feature, pre-registered with a
   falsifier (you already do this well from S4.24 onward); (b) SPRT with a wider effect size (p1=0.65) so it
   terminates in ~85 games; (c) Bradley-Terry ratings with CIs across builds, as noted in section 6a-more of your
   playbook; (d) content-hash caching of results so `_tune` drift can't recur.
3. **Route commitment with danger-weighted Dijkstra.** Path directness is 0.60 on the ladder vs 0.68-0.79 for the top
   teams. The champion is 0.73 locally, so this is contention-driven and local self-play can't test it.
   A plain BFS->A* swap won't help, as your notes already point out. This needs the ladder harness.
4. **Fix known-map dependence.** This matters because of your "no map-specific strategies" constraint, and because
   the generalisation gap on `maps_gen` (15-22%) is unsolved. Feed the sensing you already built (`selfBedDensity`
   etc.) into a consumer designed for it, not a retrofit onto `gamma`. Add `maps_gen` to every validation batch.
5. **Decentralised roles + target gossip before any horizon widening** (option (b) from your fork). Your five
   failed transplants argue this order. It is a multi-day rewrite, so only do it after 1-4 give you a reliable
   measurement.
6. **Late bed-holding.** The Cache-me-outside gap: at-bed time falls late (45/40/32%) vs their 54/67/80%. This is the
   one piece of the top-16 read that is a behaviour, not a schedule.
7. **Untried ML items your notes list:** on-policy DAgger data (collection failed when the PC slept, never rerun),
   critic warm-up plus lr ramp, UPGO/TD(lambda), DiL-piKL (sample `wNN` per game). Realistically RL at laptop scale
   looks like a dead end (6 games per update); DAgger is the cheaper of these.
8. **Explicitly do not:** resume flat-weight search, resubmit the late schedule, or transplant single v7.12 pieces.

## 7. Open questions (need code or replays, not just the notes)

- Does `queen250c` change eating on non-Trauma maps? Layer 3 may be map-specific.
- Why do 4 of 5 top teams beat the champion 0-2/5? Is it the queen, or head-on losses the notes don't isolate?
- What fraction of the 32% champion score vs 2000+ teams is map-driven (Trophy/Autarky/Devil vs Trauma)?
- Which parts of the champion's 60% maze figure come from the network vs the known-map tables?
- Are the "cloud games at ~$0.04 per 1000" numbers usable under your account? A proper A/B needs ~400 games per arm
  for a 10pp effect, which local hardware can't supply.
