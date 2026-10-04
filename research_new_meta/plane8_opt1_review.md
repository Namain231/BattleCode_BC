# Critic review: plane 8 for the retrain (Option 1 vs Option 2 vs alternatives), 2026-10-02

Role: critic. Code was read but not edited. Measurements marked **[M]** were run today with tiny scripts (kept in the session
scratchpad, not the repo) on replays already on disk plus ONE downloaded public replay (game 691134, Autarky, 563 KB).
**[R]** = read in a file (cited). **[I]** = inference, untested.

## 0. Bottom line

1. **Option 1 works on the ladder pool and is a poor fit for the final.** All 10 live maps are in `maps/` [M: `GET /maps`
   returns ids 4,7,9,11,13,15,17,19,20,21, all present], and public replays carry `MAP_NAME` [M]. So a table-filled plane 8
   is cheap and exact for ladder data. That also means **100% of the training data would have a complete plane 8 from
   round 0, and 0% of final-tournament play would**. On unseen maps the bot's plane 8 is per dragon, partial and late.
2. **Public replays strip more than the TILE lines.** They also remove every `pearlCountdown` event [M: the local judge
   replay has 6,740 of them (trauma) and 1,608 (default); the public replay has 0]. So you cannot recover gaps or the
   bot's countdown view from a public replay. Local or self-play replays keep both TILE gaps and every countdown draw
   [M], so on generated maps the bot's information state can be emulated exactly.
3. **Plane 8 is a map fingerprint.** Each live map has 2–5 distinct plane-8 values (Trophy {2,20,58}, QoS {2,40},
   Devil {3,6,13,65,255}, ...) [M]. A complete plane 8 plus terrain lets the net work out which of the 10 maps it is on,
   which is exactly the over-fitting calc warns about [R `calc WRITEUP.md` "Lessons"].
4. **Recommendation:** (i) for the next retrain, use a **"seen-so-far" memory plane plus a known-mask plane**, built the same
   way in the dataset (table value revealed only for beds that this dragon has had in view since its birth) and in the
   bot. If that is too much work this cycle, use **Option 2 (zero on both sides)**, not Option 1. (ii) For the final, use the
   memory+mask design with an improved online estimator (first-sight estimate plus cluster pooling, section B). (iii) The
   single cheap experiment is a **plane-8 sensitivity test of the shipped net**: flip rate of its top move with plane 8 =
   table vs 0 vs learnGap-emulated, on states from local replays. If fewer than about 2% of decisions flip, plane 8 is not
   worth any work and Option 2 is free.

---

## A. Feasibility of Option 1

### A1. Map identity
- The replay header is the full map text: `rep["map"] = root.text(0)` (`tools/replay.py:168`), including `MAP_NAME`
  [M: public 691134 has `MAP_NAME Autarky`]. The battle API also gives `mapId` and `mapName` [M].
- The kelp and portal layers match our file: in public 691134 the `EDGE` lines are identical to `maps/autarky.map`
  (1945/1945) [M]. All 657 pearl spawns seen in that game (tileChange events between `roundStart` and the first
  `turnStart`, i.e. pearl ticks) are on beds listed in `maps/autarky.map` [M]. So for that map and that game, the stored
  table is consistent.
- **Unverified:** the comment in the bot's MAPFIX block says ladder games disagree with the stored pearl tables on
  QoS/Devil/Dilemma/Schooltime in "~half" the games (`viper_b19_v4/main.cpp:463-464`). No measurement backing it was
  found in the repo (only the comment). Before Option 1, run the same spawn-consistency check over ~20 public games per
  map (a few minutes, about 10 MB). If tables differ on the ladder, Option 1 would train on wrong values.
- Live pool = the 10 known maps [M], so ladder training data is 100% known-map. The sprint and final use unseen maps
  (`AGENTS.md` "New-map events"). Trapped-queen maps are "being replaced" (`nn_plan.md` §5.3), and new pool maps would
  be unknown until added to `maps/`.

### A2. What a public replay says about beds
- TILE lines are all `0 0` [M], and the `pearlCountdown` events are removed [M]. The event kind exists in the schema
  (`tools/replay.py:12`, index 2) but our decoder never parses it. Locally its body is `(value i32, flag i32, tile point)`,
  logged at every reset with the fresh draw, plus the initial countdown of every bed at round 0 [M]. The value is always
  within the tile's `[lo, hi]` (142/142, 302/302 and 204/204 beds on three local replays) [M]. Indicator strings and CPU
  are stripped too ([R] memory note `bc_replay_and_ladder_testing_facts`).
- Public replays keep `tileChange`. Spawns are identifiable because they fall before the first `turnStart` of a round
  [M]. That gives bed positions, filled in over the game, and spawn intervals. The intervals are censored: a spawn fails
  while a pearl or a body sits on the tile, so (1,1) fountains on Autarky showed median 8 and maximum 142 [M]. You
  could get a rough estimate of hi from the wait after the tile empties (wait ≤ hi, mean ≈ hi/3 for lo = 1) [I]. That
  is good enough to rank fast beds and useless for slow ones. **Exact per-bed gmin/gmax cannot be rebuilt from public
  replays.** On known maps it doesn't matter, because the table exists.
- The API exposes a per-battle `seed` [M: `"seed":"97f226d327fbd2cb"`]. Re-simulating the engine with it to recover
  countdowns is conceivable, but it depends on the engine's RNG layout. Speculative; not recommended.

### A3. Reproducing the bot's information state in the dataset
How the bot builds plane 8 today (`viper_b19_v4/main.cpp:1564`): it is non-zero wherever `gmax[c] > 0`, over the whole
15x15 crop, including remembered cells. On a known map `gmax` is the table (`:413`). On an unseen map it comes from
`learnGap` (`:291-311`), which trusts a bed only after it has seen a reset (`ptCycles >= 1`). Children start empty
(`docs/splitting.md:11`: a new instance with no memory of the parent).

[M] I emulated `learnGap` per dragon on local replays, using exact countdowns from `pearlCountdown` and heads from
`dragonUpdate`/`dragonSplit`, and measured the share of "fast" beds (table plane-8 value ≥ 20) in the dragon's crop that
the bot would have filled:

| replay | fast-bed crop cells | learnGap trusted | estimate/table (median, IQR) | first-sight estimate (sec. B) |
|---|---|---|---|---|
| trauma (fountains (1,1)) | 41,834 | 62% | 1.00 (1.00–1.00) | 66%, 1.00 (1.00–1.00) |
| g11_archipelago_0 ((1,48), (2,5)) | 2.95M | **32%** | 1.00 (0.85–1.27) | 54%, 1.00 (0.68–1.66) |
| default (all beds slow, plane 8 ≤ 7) | 0 | n/a | n/a | n/a |

So on an unseen map, a table-trained net sees one-third to two-thirds of the fast beds it learned to expect. To that net,
a missing value means "barren", but in play it means "unknown". That is the skew, and it is large.

Emulating it from a **public** replay is feasible only approximately, because there are no countdowns. On known maps:
reveal bed `c` to dragon `i` once `c` has been in `i`'s 7x7 view since `i`'s birth. That is the first-sight variant. To
mimic learnGap's stricter "reset seen" condition, also require a spawn at `c` while `c` was in view on rounds r-1 and r.
That proxy undercounts, because it misses failed spawns. The revealed value is the table value, optionally multiplied
by noise drawn from the measured ratio IQR. Cost: one 7x7 pass per dragon-turn plus a per-dragon set. That is far less
than the existing `snapshot` (full HxW arrays per sample, `ml/build_dataset.py:100-140`). From **local** replays on
generated maps, the emulation can be exact (my script does it). Effort: about half a day in `build_dataset.py`; the
logic is in the review scratch script.

### A4. Known vs generated maps; generators
- Ladder data: 100% known (live pool) [M].
- `maps_gen/` (`tools/gen_random_maps.py:144`) is degenerate for this purpose: every bed is (1,200) or (1,1) [M]. It
  teaches nothing about rate diversity.
- `maps_rm_dev`/`maps_rm_test` (Loong/xCirno styles via `tools/gen_style_maps.py`, needs `LOONG_REPO`, not present on
  this machine [M: unset]) have realistic diversity: 1–4 classes per map, `lo` from 1 to 18, `hi` from 2 to 12,509 [M].
  Self-play on these gives labelled plane 8 **and** exact countdowns, so the dataset can match the bot's state exactly.
  The labels are our own moves, though (calc's "own games mixing", `nn_plan.md` option F), not the top teams'.

---

## B. Improving learnGap

(i) **State is per dragon and per process.** It is static per process and persists across that dragon's turns. It is not
shared (`docs/overview.md:13`), and a child starts empty (`docs/splitting.md:11`). With up to 60 dragons, most of them
born mid-game, almost every dragon re-learns from zero. Sonar is four 64-bit messages per turn, delivered to the first
body hit, sender unknown (`docs/sonar.md`). A bed report (cell 12 bits + rate class 4 bits + tag) fits 3 beds per
message [I]. vB19 already uses the slots for queen telemetry, and calc spends sonar on keeper/enemy/symmetry/portals.
**Value: low to medium; cost: bandwidth and complexity.** Do the cheaper in-process fixes below first.

(ii) **Estimator quality**, ordered by value per effort:
- **First-sight estimate, no reset needed.** A countdown seen at a random time is a residual of the current draw.
  Mean gap ≈ 1.5 × first-seen countdown when a reset has happened since the start; ≈ 1.0 × while still in the initial draw.
  On three local replays, one observation per bed ordered gap classes correctly in **93–100%** of bed pairs [M]. It
  covers every bed the dragon has seen, not only those it saw reset (54% vs 32% of fast crop beds on archipelago [M]).
  Cost: one int per cell.
- **Cluster pooling.** Adjacent beds share a (lo,hi) class **92%** of the time (29,186/31,618 pairs over maps/,
  maps_rm_dev, maps_rm_test; 64–100% on generated maps) [M]. Pool estimates over the 4-connected bed component.
  Bedness is visible (`ptime >= 0`), so a cluster of k beds gives k draws per cycle and every member gets an estimate
  once any member resets. Cost: one flood fill per newly seen bed.
- **Mirror symmetry.** On a symmetric map mirrored tiles **share a countdown** (`docs/pearls.md` "Symmetric Pearls";
  [M] the round-0 events show (0,0) and (47,23) both at 129 on trauma). A learned bed implies its mirror. The catch:
  `detectSymmetry` only runs on known maps, because it compares `KM->gaps` (`viper_b19_v4/main.cpp:329-339`), so on
  unseen maps `SYM = -1` and `mirSpawn` is dead. Online symmetry detection (from spawns and seen terrain, as calc does)
  is a prerequisite and a gain in its own right.
- **Use the sample mean, not extremes.** Plane 8 and the farm values need a rate, 2/(lo+hi), i.e. the **mean gap**. The
  mean of fresh draws estimates it directly without bias. `gmax` = largest countdown seen is biased low with few
  draws, and `gmin` defaults to 1 (`:307`). The default is actually right for most beds (lo = 1 on every live map except
  Dilemma, Schooltime and Arena [M]) but wrong on generated maps (lo up to 18).
- **Probable off-by-one** [I, from `docs/execution-order.md:9`: the tick and reset happen before dragons move, so a dragon
  sees the fresh draw itself]: `fresh = pt + 1` (`:298`) overstates `gmin` by 1. Small effect (e.g. (1,10) gives 170 instead of 185).
- Generator priors: classes per map are few (1–5) [M], but the values differ by map, so there is no global prior beyond
  "lo is usually 1".

(iii) **What the consumers need: a rank, not exact gaps.** Plane 8 = `min(255, int(2040/(lo+hi)))`
(`ml/build_dataset.py:67`, `main.cpp:1564`). Every bed with hi ≥ ~1000 rounds to 0–2, and Default's whole map is ≤ 7
[M]. Plane 8 is effectively a "fast fountain" marker on a coarse log-like scale. Farm and pearl-probability code
(`:528-551`) uses the means. A rank-correct estimate (first sight + pooling) captures most of the value.

(iv) **What fails today:** (a) nothing is filled until a reset has been seen in view (32% coverage above); (b) every
child starts blank; (c) there is no symmetry on unseen maps; (d) for slow beds, the extreme-value `gmax` from one or two draws
can be off by about 2x [I], though plane 8 barely registers them.

---

## C. Architecture and dataset

- **Mask plane + rate plane (recommended).** Plane 8 = rate where known, plane 8b = "bed status known" (0 unknown, 255
  known: either known barren or known bed). The net can then tell "unknown" from "barren". Without the mask, a zero is
  ambiguous and the net learns "zero = barren" from table data.
- **Random i.i.d. plane-8 dropout:** better than nothing, but the real missingness is structured. It depends on where the
  dragon has been, is correlated with its path, and grows with dragon age. Uniform dropout teaches the wrong prior, e.g. that
  known fountains can vanish next to the head. **Use structured "seen-so-far" masking instead.** Mixing regimes per game is
  the honest version of dropout: e.g. 30% of games use the full table with mask = 1 (known-map regime), 70% use memory
  emulation. One net then serves both regimes with correct semantics.
- **Memory plane maintained by the bot**, identical in train and play. The bot would fill plane 8 from what this dragon has
  seen, even on known maps, i.e. it deliberately drops table knowledge. That gives exact parity and kills map
  fingerprinting. The cost is some known-map strength. Combined with the mask and the per-game regime mix, the bot can
  use the table where it has one. Note: a previous pearls-only memory plane was neutral (`ml/results.md:174, 291`).
  This is a different signal (static bed rates, not transient pearls), but the prior is "small effect".
- Queen planes/scalars: yes, as in `nn_plan.md` "Design notes for B". The queen is fixed to id 0/1 and must come from
  the replay's DRAGON order.
- Data and disk: a public replay is ~0.5 MB [M] (local ones are 4 MB because of indicators and countdowns). Use a decode
  path without the `.pkl` cache: `build_dataset.py:30` imports `replay.load`, which writes `<replay>.pkl` next to every
  file (`tools/replay.py:142-160`) and doubles disk use. Stream download → shard → delete replay, one team at a time,
  and check `df` between teams (6 GB free).

| Approach | Expected gain (ladder) | Expected gain (unseen final) | Risk | Effort | Train/play parity |
|---|---|---|---|---|---|
| Option 1 (table at build time) | small + | **negative to 0**: net expects a complete plane, gets 32–66% | map fingerprinting; possibly wrong tables (MAPFIX claim, unverified) | 0.2 d | exact on known maps; **broken** on unseen |
| Option 2 (zero both sides) | small − (loses fountain marker) | 0 (no skew) | lose a real signal if the net used it | 0.1 d | exact |
| i.i.d. plane-8 dropout | ≈ Option 1 | small + | wrong missingness prior | 0.2 d | approximate |
| Memory plane + mask, per-game regime mix | ≈ Option 1 | **+** (correct semantics) | emulation bugs; may be neutral like v5 | 0.5–1 d dataset + 0.5 d bot | exact (local), close (public) |

---

## D. Verdict

- **Next retrain:** do **not** pick Option 1 by default. Run the sensitivity experiment first (below). If plane 8 matters,
  build memory + mask (structured reveal, per-game regime mix). If not, take Option 2 and move on. Option 1 is only
  defensible as "this net is for the ladder pool only, and a separate net or wNN = 0 handles unseen maps". That doubles
  test work, and calc's lesson argues against it.
- **Final, unseen maps:** memory + mask, plus a better online estimator (first-sight + cluster pooling + online symmetry,
  then the mean-of-draws fix). These also improve the rules' farm valuation independently of the net; `b19_v4`'s 22/40 on
  dev is the only evidence so far (SE ~8pp, not significant: `AGENT_LOG.md`).
- **Cheap decisive experiment (about 1 h, CPU, no games):** parse `baselines/vB19/policy_weights.hpp` into numpy and run
  the shipped net on about 20k states built from local replays already on disk (exact gaps and countdowns). Inputs:
  plane 8 = table / 0 / learnGap-emulated / first-sight-emulated. Report the top-move flip rate and mean KL,
  separately for states with a fast bed in the crop. Under 2% flips means plane 8 is irrelevant: Option 2. A large
  table-vs-emulated gap means Option 1 would hurt unseen maps and memory + mask is needed. Add a train-time A/B (same seeds,
  plane 8 on/off) to the retrain itself and compare held-out accuracy on generated-map games, never on live-map games
  alone.
