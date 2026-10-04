# Search layer plan: what the net saw, and what a net-played rollout search needs (2026-10-02, researcher)

Tags: **[R]** read in a repo file (cited), **[M]** measured by me today (read-only scripts, no games, no code edits),
**[W]** calc's writeup or chat claim (unverifiable), **[I]** my inference, untested. Anything not tagged [R]/[M] is
unverified.

---

## 0. Bottom line

1. **What the nets saw.** There are two shipped nets, and both were trained on the old rules (games before 2026-10-01: old
   longest-dragon win condition, old sprint cost of x-1). `policy_v1` (champion `viper_nn` / `baselines/y7_12_nn1`) was trained
   on 356 winning top-12 games (~27 Sep). `n4` (in `vB19`, `y7_12_49`, `s2_gP`) used fresher top-10 data (29-30 Sep)
   plus v1-era data. Both have 16 planes + 3 scalars, first-step/split/other labels, winners only, and late rounds
   downsampled to 35%. **dataset_v6 fixes most of the staleness** (labels, queen identity, enemy reach, length skew,
   plane 8). It **does not fix** four things: (a) demonstrator version filtering (public replays no longer name the bot, so
   only a recency filter is possible); (b) the bot-side gate that turns the net off on Portals/Slithery/Schooltime, which was
   set from old-rules evidence; (c) a cheap, simulator-computable **rollout net**, which search needs and v6 does not
   provide; (d) unseen-map terrain (F12 is optional in v6). See §1.4.
2. **No in-process forward simulator exists that a bot can use.** The official engine is an opaque wasm module with
   a run-a-whole-match API (no snapshot, no branching). bceval and rulemine rebuild state from replay events and do not
   apply rules. vB19's `simulate()` moves only our own dragon against a frozen board. **A C++ simulator must be written.**
   Scope: ~600-800 lines of C++ (simulator + imagined world + search driver), plus ~300-400 lines of Python/C++ test
   tooling. The test oracle is a replay round-trip on local Zig-judge replays (full information), plus crafted-map
   scenario tests run through the official engine (§2a).
3. **The current conv net is ~2.24M MACs and costs ~18M points per call** [R `ml/results.md`]. That allows about 2
   rollout steps in a 40M budget, which is useless for search. A rollout needs **≤ ~0.3M points per net call**
   (3 candidates × 1 greedy rollout of 6 dragons × 3 rounds = 54 steps). Only a calc-style MLP with SIMD and zero-skipping
   reaches that (§2c, §2d table).
4. **Terminal score (new rules):** our total length minus theirs over the imagined world (as calc does), plus a queen term
   (own queen dead = −(L_q+20), enemy queen dead = +(L_eq+10), own-queen growth weighted up late), plus a trap penalty at the
   leaf. The queen tiebreak decides only ~8% of top-team games and 54% end by elimination [R `dataset_v6_and_bceval.md`
   §1.8], so **material stays the main term** and the queen term mainly prevents losing the queen (§2d.3).
5. **Verdict:** this is ~8-10 working days for one director plus executor/critic agents, against a final date that is
   **not recorded anywhere in the repo** (§2e.4). Our rule layer already does exact 1-ply survival and enemy-reach checks,
   so search would add less here than it did on top of calc's pure net [I]. **Do the cheap stage first (S0, half a day,
   offline, no games).** It measures how much of our lost length comes from situations a view-limited 3-round search could
   see and avoid. Build further only if that ceiling is large.

---

## PART 1: what did the shipped nets actually see?

### 1.1 Two nets, both old-rules

| | `policy_v1` (champion `viper_nn`, `baselines/y7_12_nn1`) | `n4` (`baselines/vB19`, `y7_12_49`, `s2_gP`, `y8m_active`) |
|---|---|---|
| Provenance | `ml/data_v1`: 2.34M decisions from **356 winning top-12 games**; trained on 1.1M of them; scouted ~2026-09-27 [R `ml/results.md` "Pipeline"] | "n2a (slope data) → n3 (+upset winners +winners vs us) → **n4 (+v1-era data)**". Slope collector = top-10 teams' fresh games, 29-30 Sep. Held-out log-loss on 451 new games: v1 0.690, n4 **0.670** [R `git show da053f8:AGENTS.md` l.89, 225] |
| Exact volume | 1.1M samples used | **Unknown** (not logged in what survives; `guide/5` says "about 900 games" for the pipeline in general). `.pt` files and shards are gone from disk [R `nn_plan.md` §2.3] |
| Era | Old rules: r500 winner = longest living dragon; sprint x steps cost x−1; any order of DRAGON lines | Same (newest data 30 Sep; rules changed 1 Oct after the sprint tournament [R `docs/CHANGES_2026-10-01.md`]) |
| Architecture | 19 input ch (16 uint8 planes 15×15 + 3 broadcast scalars) → conv3×3 32 → avgpool → conv 32 → conv 32 + residual → FC 64 → 6 logits [R `policy_nn.hpp`] | Identical shape (`NN_NSCAL 3, NN_CH 32, NN_HID 64`) [R header of `baselines/vB19/policy_weights.hpp`] |
| Planes | 0-3 kelp sides, 4-7 portal sides (full known map), 8 spawn rate 2/(lo+hi), 9 view mask, 10 pearl in view, 11-13 own/ally/enemy body rounds-until-free ×16, 14-15 ally/enemy head length ×8 [R `ml/build_dataset.py` header] | same |
| Scalars | len/32, round/500, units/64 | same |
| Labels | first step relative to facing (F/R/B/L) of a move or sprint, split, suicide/illegal | same |
| Filters | winners only (`build_dataset.py:233`); **late rounds kept at 35%** (`keep_late=0.35`, l.160); mirror augmentation; validation split by game | + "upset winners", "winners vs us" (n3), v1-era data (n4) |
| Offline accuracy | 70.6% (v1) | ~71-73% band (ceiling = missing information, not capacity) [R `ml/results.md`] |

### 1.2 What the old-rules labels taught that is wrong or at risk now

| Learned behaviour (old data) | Why it is stale under the 2026-10-01 rules | Evidence |
|---|---|---|
| **Endgame feeding and "keeper" movement towards the longest ally head** (planes 14-15 encode head length; late samples kept at 35%) | The feed target is now the queen (id 0/1), not the longest. The net cannot tell them apart: there is no queen input | `nnInput` has no queen field [R `nn_plan.md` §2.1]; the old keeper/election design [W calc §4] |
| **Long-dragon caution** (a long dragon late in the game behaves as the r500 tiebreaker) | A long non-queen is now only tiebreak 2. A queen of any length is tiebreak 1 | `docs/structure.md` via CHANGES |
| **Enemy-head distance heuristics** (one enemy step per turn; sprinting cost segments) | Enemies now take ceil(L/4) free steps. A 12-long enemy covers 3 cells a turn for free, so "2 cells away" is no longer safe-ish | `docs/movement.md`, `execution-order.md`; vB19 already patches the rules side (`buildReaches` `spd`) [R main.cpp:787] |
| Sprint habits | Label = first step only, so sprint length was never learned. Little to unlearn; also winners now leave free steps unused 86-90% of the time | [R dataset_v6 §2.1] |
| Opening on trapped-queen maps | New DRAGON order puts an 11-long queen boxed in on Dilemma/Slithery Fight. The round-0 SHED/ESCAPE split is correct and is handled by rules | [R AGENT_LOG qdoomed_off] |

**Use on queen vs non-queen dragons now:** vB19 adds `wNN × log p(first step)` within safety classes. wNN is 2.0 for drones
and **0.4 for the true queen**; the net is **off** on `bigFeed` maps (Portals, Slithery Fight, Schooltime), after `nnUntil`,
and once `elapsedMs() > 40` [R `baselines/vB19/main.cpp:361-369, 1558, 1738`]. The sweep under the new rules says the
stale net still pays on maze maps: wNN 0 scores 11/40, wNN 2 scores 23/40, and wNN 1/4/8 are indistinguishable from 2
[R `wnn_sweep_results.md`]. Its value is most likely physics and trap avoidance, not strategy (director's verdict,
AGENT_LOG retrain_debate).

### 1.3 Does dataset_v6 cover the staleness? One line per gap

| # | Gap | Covered by v6? | Where / what is still needed |
|---|---|---|---|
| 1 | Old-objective labels (longest-dragon feeding, keeper election, old sprint economy) | **YES** | v6 uses new-rules winners only with a date filter `at` ≥ switch (§5.1). Caveat: 1-2 Oct bots are transitional ports of old logic, so re-scout every 2-3 days |
| 2 | No queen identity (self / own queen / enemy queen) | **YES** | F1 `is_queen`, plane 16 (queens in view + enemy-queen memory) |
| 3 | Free-step enemy reach | **YES** | plane 17 (port of `EnemyReach`), F5 `ceil(L/4)/8` |
| 4 | Visible-length skew on planes 12-15 | **YES** | §2.0 skew 2, computed the way the bot sees it |
| 5 | Plane 8 (TILE zeroed in public replays) | **YES** | zero in both training and play (director decision) |
| 6 | Late-round downsampling (old 35%) hides queen/endgame decisions | **YES** | removed |
| 7 | **Demonstrator version filter** (old pipeline used `latest_only.py` by submission) | **NO** | Public replays now have empty botA/botB [R dataset_v6 §1.2] and the v1 API dropped submission ids [R `ml/results.md`]. Only recency remains: weight games from the last 24-48 h ×2, or drop games older than 3 days at each re-scout. Small separate item |
| 8 | Bot-side gates tuned on old evidence: queen weight 0.4 | **YES** | v6 §8.3 re-sweeps 0.4 vs 1.0 |
| 9 | Bot-side gate: **net off on Portals/Slithery/Schooltime** (old-rules open-map losses) | **NO** | Never re-tested under the new rules. Cheap separate test: vB19 with `bigFeed`-gate removed for the net only, on those 3 maps |
| 10 | Behaviours wrong now (§1.2) | **YES for the net**, by retraining on new labels | Rules-side equivalents (feed sink, protection) are already handled in vB19 |
| 11 | Unseen-map terrain (planes 0-7 = full map in training; the bot has only seen cells on new maps) | **PARTLY** | F12 seen-mask regime mix is rank 8, "0 ladder / + final". Needed for the final event; not needed for the ladder |
| 12 | **A rollout net for search** (cheap; inputs computable for *any* dragon from simulator state; multi-step moves; split) | **NO** | v6 gives labels and the STOP/continue head (good for enemy sprints in rollouts). But it is a conv net at ~21M points per call [R v6 §9] with per-dragon memory inputs (F3 enemy-queen memory, F12 mask) that the simulator cannot produce for other dragons. Needs a separate distilled MLP (§2c) trained on the same v6 shards, using only "imagined-world" inputs |

**Answer:** v6 is sufficient for the move net's staleness. Gaps 7 and 9 are small separate items. Gap 12 is the search
layer's own requirement and is planned in Part 2.

---

## PART 2: the search layer

### (a) Is there any usable in-process forward simulation?

| Candidate | Language / where | API | In bot wasm? | Deterministic | Fidelity vs official engine | Verdict |
|---|---|---|---|---|---|---|
| **Official engine** `unswbc_engine.wasm` | Organisers' binary, opaque wasm; hosted by `unswbc.engine.EngineModule` (Python, wasmtime) [M source read] and by the Zig judge `harness/zig_judge/src/engine.zig` ("owns every rule and writes the replay; the judge only serves its three imports") [R] | `run(map_bytes, bot_reply, on_death, bot_spawn, seed)` → `MatchResult`. Whole match from a map file; **no state snapshot, restore or step API** | **No.** A bot cannot host a wasm runtime, there is no source, and it is far too large | Yes (seeded) | Exact by definition | **Oracle only.** Scenario tests via crafted maps: `DRAGON` lines place arbitrary bodies, and `TILE x y 1 1` spawns deterministically. Limits: teams must alternate per line (so counts must be equal ±1), ids = file order, no initial pearls. Mid-game states cannot be loaded in general |
| `ml/rl_env.py` | Python wrapper of the same engine, every dragon a Python callback | `play_game(map, policy_a, policy_b, seed)` | No | Yes | Exact | Offline only; ~480 dragon-turns/s; full games, no branching ("search-based improvement needs mid-game state branching, which the in-process engine cannot do" [R `ml/results.md` SIL section]) |
| vB19 `simulate()` | C++ in bot, `main.cpp:736` | `SimResult simulate(const vector<int>& dirs)` on globals `body`, `occId`, `viewIndex`, `nbr` | Already in it | Yes | **Own dragon only**: free steps ceil(L/4), the pay check, self-collision with the tail, pearl eat, extra tail pop are all correct. **Others are frozen**, unseen cells are flagged `outside`, there are no deaths/drops for others, no splits, no turn order | Reusable pieces: `nbr[]` (portals with direction preserved, wrap) and the step logic. Not a simulator |
| bceval rebuild (`tools/battlecode-eval/bceval/features.py`, `mapdata.step`) | Python | Replay events → bodies; applies `move` dirs provisionally, corrected by `dragonUpdate` | No | n/a | Rebuild "ok" on 179/179 new-rules public replays [R v6 §1.2]. **Deaths come from events, not from rules** | Reference for the Python oracle's replay parser |
| `rulemine/state.py` | Python | `turns(path)` yields per-turn snapshots with per-dragon memory | No | n/a | Event-driven. Reading l.188-197: `dragonUpdate` inserts **one** head cell, so after a multi-step move the body would miss intermediate cells **[I, read not run]** | Good for "what did dragon i know"; **do not use as the rules oracle** for multi-step moves without a check |
| Loong repo `gamedata/board.nim`, `replay_board.nim`; `examples/repertoire/.../movement.nim` | Nim | Replay reconstruction (`moveDragon(head, tail)`), a one-step safe-move filter | No | n/a | Not a rule engine | Not usable |
| calc's "C++ copy of the game engine" | — | — | — | — | "matches turn for turn" [W] | Not available to us |

**Conclusion: nothing usable. A C++ port is required.**

#### C++ simulator: components and size

Spec sources: `docs/execution-order.md`, `movement.md`, `death.md`, `splitting.md`, `pearls.md`, `kelp-and-portals.md`.

| Component | Behaviour that must match | Lines [I] |
|---|---|---|
| `SimState` (fixed arrays, no heap) | cells ≤ 64×64; `occ[cell]` = dragon idx+1 and is-head flag; `pearl` bitset; `cd[cell]` countdown (−1 unknown); ≤ 32 dragons with ring-buffer bodies (≤ 256), team, facing, alive, id; round; turn cursor. One copy ≈ 25 KB ≈ 3.2k points via `memory.copy` | 80 |
| Step / topology | Reuse the bot's `nbr[]` (kelp = −1, portals keep the direction, wrap) | 10 |
| `applyMove(d, dirs[])` | Per step j: if j ≥ ceil(L₀/4) (L₀ fixed at move start), pay check (length 2 cannot pay → dies "no valid action"); facing = dir; kelp kills; **own body checked first, tail included (it has not moved yet)**; then other dragons: **another head → that dragon dies first, then this one**; any other segment kills only this one; move the head; eat a pearl (no tail advance), else advance the tail; on a paid step pop one more tail segment. A death discards the remaining steps | 80 |
| `kill(d)` | Every second segment of the body *as it stands* becomes a pearl (head, skip one, …); countdowns unchanged; remove from `occ` | 25 |
| `applySplit(d, size)` | Checks before moving: child ≥ 2, parent ≥ 2, team < UNIT_LIMIT (64), else the parent dies; child = rear segments reversed, next id, **appended to this round's turn list** | 35 |
| Round loop | Pearl tick first (countdowns −1, top row to bottom, left to right; at 0 spawn if the tile is free, redraw: unknown draw → treat as "no spawn within horizon"); then living dragons in **ascending id**, skipping the dead and appending children. **Start mid-round** at our own turn (lower ids have already moved; their result is in our input) | 50 |
| Imagined-world builder | Known map (exact on ladder maps from `maps_data.hpp`; seen-only on new maps, unknown = open water as calc does); dragons = visible ones (ids, cells in view, `estLen`), body beyond the view truncated; remembered pearls; seen countdowns (decremented since seen); optional ghosts from last sighting / sonar EQPOS (age ≤ 3) | 100 |
| Rollout-policy input | Egocentric 7×7 (+ coarse map) for **any** dragon from `SimState`; legal mask (no reverse into own neck, kelp) | 80 |
| Search driver | Candidates, contact trigger, greedy pass, UCB1, leaf score, `elapsedMs()` guards, tie rule | 150 |
| **Total C++** | | **~610** (≈ 800 with debug/self-test) |

Not needed: sonar (rays and inboxes), indicators, echo counts.

#### Test oracle (blocking before any in-bot use)

1. **Python reference simulator** `rulemine/sim.py` (~200 lines), the same rules written plainly. **Replay round-trip**
   `tools/sim_parity.py`: for each local Zig-judge replay (full TILE gaps and `pearlCountdown` events; e.g. the 41
   replays in `out/sw_0`, and other `out/sw_*`), at every `turnStart` take the true state, apply the recorded
   `dragonAction` (`move` dirs / split size / suicide), and compare against the replay's next `dragonUpdate` /
   `dragonDeath` (reason) / `dragonSplit` bodies / `tileChange`. Pearl spawns come from the replay's `tileChange`
   (exogenous). Pass = **100% of dragon-turns bit-exact** on ≥ 40 games. Also run on `ladder/scout_v6` public replays
   (rules are identical; only spawns differ, and those are exogenous anyway).
2. **C++ port** checked against the same dumps: `tools/sim_parity.py --dump DIR` writes (state, action, expected) text
   records; a native test `g++ -std=c++17 -O2 -DSIM_NATIVE_TEST viper_search/sim_test.cpp` must match 100%. The same
   pattern already exists for the sonar auth (`-DMSGAUTH_NATIVE_TEST`, AGENT_LOG b19_f1_round2).
3. **Edge-case scenarios through the official engine**: crafted 9×9 maps with scripted bots for free-step payment at
   L = 2..9, head-on ordering (lower vs higher id), the tail-tile rule, a portal mid-sprint, split child turn order,
   and death pearl drops on a multi-step move. Run with `unswbc run` (no `--sandbox` needed); expected outcomes come from
   the replay. This is the only check that covers rules our own games rarely hit.
4. In-bot round-0 self-test (like `nnSelfTest`): one stored scenario, compare and LOG on mismatch. Debug builds only.

### (b) `policy_nn.hpp`: pure, loopable, and its cost

- **Pure in-memory: confirmed** [R `viper_nn/policy_nn.hpp`, same shape in vB19]. Static global buffers
  (`in_`, `a1`, `p1`, `a2`, `a3`, `h`), weights are `static const` arrays, no allocation, no I/O. `forward(planes, scal,
  logits)` can be called any number of times. It is not re-entrant (shared statics), which is fine single-threaded. The
  only I/O is `nnSelfTest()`'s `printf` at round 0, outside `forward`. **But the input builder `nnInput` reads the bot's
  live globals** (`V`, `others`, `body`), so it cannot produce inputs for a simulated state or another dragon. It needs a
  `SimState` version.
- **MACs** [M, from the shapes]: conv1 19×32×9×225 = 1,231,200; conv2 and conv3 32×32×9×49 = 451,584 each; FC 1568×64 =
  100,352; out 402. **Total ≈ 2.235M MACs.** The measured cost is ~18M points per call [R `ml/results.md`], so **~8 points/MAC**.
- **Is it already vectorised?** Static count in `wasm_cache/vB19-4c23c57aea0e3e6f.wasm`'s code section [M]: 22
  `f32x4.mul`, 23 `f32x4.add`, 18 `f32x4.splat`, 236 scalar `f32.mul`. Clang `-O2 -msimd128` vectorised some loops
  (probably the conv `u` loops). Widths 15 and 7 leave 3-wide scalar remainders, and the loads are unaligned
  **[I: which loops vectorised is not attributed]**.
- **Gains available on the conv net [I]:** pad the `u` dimension to 16 / 8 and write the inner loop with
  `wasm_simd128.h` (per 4 outputs per tap: `v128.load` 2 + `f32x4.mul` 2 + `f32x4.add` 2 = 1.5 pts/MAC, ~2 with
  overhead). That gives ~4-5M per call. Skipping all-zero input channels (plane 8 is now zero; portal planes are mostly
  zero) saves up to ~30% of conv1. **Batching** helps little in wasm (it only amortises weight loads, ~1.3×).
  **Incremental updates do not apply**: the frame is egocentric and rotated, so every move shifts every input.
  **Caching does apply** in rollouts: a dragon whose 7×7 did not change between two candidates' rollouts gets an identical
  input, so hash the input and reuse the logits. Expected hit rate is 30-50% for dragons far from our candidate cell [I].
- Even a perfect 5M conv allows <1 rollout in 40M (§2d table). **The conv net cannot be the rollout policy.**

### (c) Cheap-net options

| Option | Expected cost / call | Accuracy risk | Notes |
|---|---|---|---|
| Conv as is (scalar + partial SIMD) | ~18M [R] | 0 | Baseline |
| Conv, explicit SIMD + padding + zero-channel skip | ~4-5M [I] | 0 (same function) | Good for the **root** call; useless for rollouts |
| **MLP** (calc's shape: 256→128) on 7×7 local planes (~10 ch × 49 = 490) + coarse remembered map 8×8×4 = 256 + ~8 scalars ≈ 750 inputs | 750×256 + 256×128 + 128×7 ≈ 225k MACs; with f32x4 SIMD ~1.6-2 pts/MAC → **~0.4M** [I] | Medium: loses the 15×15 known-terrain context; calc reports 80-85% (different label set) [W chat l.646] vs our conv 72% | calc's "8× cheaper" [W] |
| + **zero-input skipping** (column-major W1; add the column for each non-zero input only; binary planes are ~10-20% non-zero) | layer 1 ~35k MACs → **~0.1-0.15M** total [I] | 0 (exact) | Biggest single win for sparse inputs |
| + caching of identical inputs | effective ×0.5-0.7 [I] | 0 | Rollouts repeat inputs across candidates |
| int8 weights, compute via `i32x4.dot_i16x8_s` | ~0.75 pt/MAC [I] | Small (per-channel scales) | More code; relaxed-SIMD int8 dot is probably unavailable (only `-msimd128`) **[unverified]** |
| fp16 | storage only | none | wasm SIMD128 has no f16 arithmetic. Use fp16/int8 only to keep the zip < 4 MB (as text, 250k fp32 weights ≈ 3 MB; emit hex bytes) |
| **Distil from a teacher** (n4 now, the v6 conv later) into the MLP, on v6 shards (KD on teacher logits + hard labels) | — | Agreement with the teacher's top-1 must be ≥ 90% on held-out games [I threshold]; our own 64→32-ch KD lost 1.4 pt [R] | Gives the rollout policy and the cheap root policy in one artefact |
| Fallback rollout policy: tiny linear softmax on ~20 hand features (free cells ahead/left/right, pearl direction, enemy-reach flag) | ~0.01-0.02M | High (crude) | Use if the MLP misses the budget. AlphaGo used exactly this split (expensive prior, cheap rollout) |

**Recommendation:** rollout policy = distilled MLP with SIMD + zero-skip + cache (target ≤ 0.15M per call). Root prior
= the same MLP on search turns, and the conv net (v6) on non-search turns. Do not invest in int8 unless the zip size
forces it.

### (d) Search design

#### d.1 Algorithm (calc's §3, adapted)

1. **Trigger (contact only):** run search only when an enemy head's reach `3·ceil(Le/4)+1` overlaps our 3-round reach,
   or a pearl in view is contested, or the rule scorer's top two options are within ε. Other turns use the current
   rules + net move unchanged (most turns, so the mean CPU stays as now) [I].
2. **Candidates:** rule-legal first moves (current `opts`, safety class ≥ best class − 1) with `p_net ≥ 0.05`, at most 4.
   Multi-step options from FSPRINT enter as their own candidates.
3. **Imagined world:** §2a builder. Active dragons = those whose reach can intersect ours within D rounds (mask by
   `R(L)` reach, not raw distance [R `algorithms.md` §5.4]). Others are frozen (a static body).
4. **Rollout:** apply the candidate for us; finish this round for higher ids; then D = 3 rounds (5 in r < 50) with every
   active dragon on both sides played by the rollout net: greedy in pass 1, sampled at T = 1 in later passes. Sprints
   come from the STOP head (or "1 step" if absent). Splits use the net's split class with size = half.
5. **Leaf score** (d.3). 6. **UCB1** over candidates for the remaining budget: `x = 0.5+0.5·tanh(S/8)`,
   index = mean + 0.7·√(ln N / n) [I constants]. With greedy-only rollouts, UCB is pointless (they are deterministic),
   which is why passes ≥ 2 sample.
7. **Decision, two modes:** **veto mode first**, which replaces the rule pick only if its mean is ≥ T (e.g. 2 length) below
   the best candidate or the queen dies in its greedy rollout. **Full mode** (score = rule score + w_s·mean) comes only
   after veto mode passes. Ties go to the rule/net pick.

#### d.2 Per dragon or shared?

**Per dragon, unavoidably.** Each dragon is a separate process with no shared memory [R `docs/overview.md`, `timeouts.md`];
sonar carries 4 values per turn, so search trees cannot be shared. This costs nothing in budget: the 100M cap is per
dragon-turn, so total search grows with unit count. Consequences: allies' searches are inconsistent (each models the
others as net players); lower-id allies have already moved this round, so the start state is exact for them [R
execution order]. Accept the inconsistency (calc does) [W].

#### d.3 Terminal score under the new rules

`S = Δ(Σ our L − Σ their L)` over the imagined world (calc) **+** queen terms **+** a horizon guard:

| Term | Value [I weights] | Why |
|---|---|---|
| Material | Σ our lengths − Σ theirs (change from the root) | 54% of top-team wins end by elimination; length/territory still call 81-92% of games [R v6 §1.5, §1.8] |
| Own queen dies in the rollout | −(L_q + 20) | Tiebreak 1; queen death is the irreversible event |
| Enemy queen dies | +(L_eq + 10) | Only if she is in the imagined world |
| Own queen growth | +w_q·ΔL_q, w_q = 0.5 (r<300) → 1.5 (r≥300) | Only 8% of games are queen-decided, but those are the late ones |
| Dropped-pearl smoothing | +0.5·(dropped pearls closer to our heads than to theirs) | A kill's pearls are eaten after the 3-round horizon |
| Leaf trap guard | −0.5·L_me if my free flood-fill area < L_me at the leaf (reuse `space`) | 3 rounds miss dead-end traps; the rules' survival search already knows this |
| Units | +0.3·Δunits for r < 150, else 0 | bceval: more bodies helps early, hurts after r125 at equal length [R v6 §1.3] |

Feeding late is a known conflict: a drone dying next to the queen lowers total length. Do not search feeding drones
(they are rule-driven anyway); search only non-feeding dragons.

#### d.4 CPU budget

Assumptions [I]: per rollout step (one dragon's turn in the simulator) cost = net call + 0.05M (input build + apply +
copy share). One rollout = K = 6 active dragons × D = 3 rounds = 18 steps. Minimum useful search = 3 candidates × 1
greedy rollout = 54 steps. Per-turn cap 100M; keep the max ≤ 65M [R AGENTS.md]. The current vB19 peak is ~61M and the mean
~22M with the 18M conv call included (director's figures; executor smoke saw max 59-61M [R AGENT_LOG]).

| Net cost per call | Steps in 20M | Rollouts (18 steps) in 20M | Steps in 40M | Rollouts in 40M | Enough for 3 candidates? |
|---|---|---|---|---|---|
| 18M (current conv) | 1 | 0.06 | 2 | 0.1 | no |
| 5M (SIMD conv) | 4 | 0.2 | 8 | 0.4 | no |
| 1M | 19 | 1.1 | 38 | 2.1 | no (only 1-2 candidates) |
| 0.3M (MLP + SIMD) | 57 | 3.2 | 114 | 6.3 | **yes at 20M** (greedy only); a little UCB at 40M |
| 0.1M (+ zero-skip + cache) | 133 | 7.4 | 266 | 14.8 | yes, with UCB |
| 0.02M (linear rollout policy) | 285 | 16 | 571 | 32 | yes, with ample UCB |

Where the 20-40M comes from (what must be cut on search turns):
1. **The 18M conv call at the root** → the MLP prior on search turns (frees ~18M).
2. **FSPRINT path enumeration and the dfs survival budget** (`dfsBudget`; guards at 55-70 ms): cap them on search turns,
   since the rollouts cover multi-step options. This is where the ~61M peaks come from [I; attribute with a
   per-section `elapsedMs()` profile in a debug build first].
3. Compass BFS (already guarded at 40 ms) is skipped on search turns.
4. A search guard: start only if `elapsedMs() < 25`, stop scheduling rollouts at 50, and stop at 55 at the latest.
5. Rollouts whose active set K > 8 shrink D to 2.

#### d.5 Fidelity cost of unseen dragons

- **The view is 7×7 (radius 3).** With free steps, a 12-long enemy moves 3 cells per turn (more with paid steps), so within
  D = 3 rounds a head from outside the view can reach us. The imagined world omits it. This is the main fidelity hole, and
  it is worse under the new rules than under the old ones [I].
- **Bodies with tails out of view:** cells beyond the view are unknown. Truncating them is optimistic (it frees cells
  early); keeping the last-seen cells is pessimistic. Prefer keeping last-seen cells for ≤ 3 rounds [I].
- **Unknown terrain:** exact on the 10 ladder maps (tables). On new maps, "open water" (calc) makes rollouts walk into
  unseen kelp. Mitigation: score unknown cells as `outside` (as `simulate()` already flags) and penalise leaving known
  cells in the rollout [I].
- **Pearl spawns:** exact for seen tiles with a known countdown that are free at spawn time. Unseen tiles never spawn
  in the simulation (pessimistic and fine).
- **Measure before building:** S0 below reports the share of our lost length where the killer was not visible at t−1..t−3.

### (e) Milestones, delegation, verdict, cheapest test

Paths: Git Bash for `export`, PowerShell/uv for Python tools. `PY` = `uv run --python 3.11 --with unswbc --with numpy python`
(msys python segfaults on zlib). **Disk is 4.3 GB free [M `df -h /c`]**: S0-S2 read existing replays only; delete
nothing they did not create.

| Stage | What | Files / commands | Owner | Effort | Go / no-go |
|---|---|---|---|---|---|
| **S0** (cheapest; offline, no games) | **Addressable-loss ceiling.** For our side in local replays (`out/sw_*` = vB19 and variants vs y7_12_49; 41 replays each) and for top-team winners in `ladder/scout_v6/top`: every length loss (death by reason, head-on), the length lost, whether the killer's head was in the victim's 7×7 at t−1/t−2/t−3, whether a non-fatal alternative first move existed at those turns (1-step legality only), and the share of total lost length that is "visible and had an alternative" | new `tools/search_ceiling.py` built on `rulemine/state.py` (deaths and views; single-step only) + `tools/replay_lite.py`; `$PY tools/search_ceiling.py out/sw_2/*.replay --side ours` | executor + critic | 0.5 d | **Go** if visible-and-avoidable lost length is ≥ ~15% of our mean lost length, and ours is clearly above top teams' share. **Stop** otherwise [I thresholds] |
| S1 | Python reference simulator + replay round-trip parity | `rulemine/sim.py`, `tools/sim_parity.py REPLAY... [--dump DIR]` | executor; critic checks every rule against `docs/execution-order.md` line by line | 1.5 d | 100% bit-exact dragon-turns on ≥ 40 local replays + 20 scout_v6 replays |
| S1b | Official-engine scenario maps | `tests/sim_scenarios/*.map` + scripted bot; `unswbc run` | executor | 0.5 d | Every scenario matches `rulemine/sim.py` |
| **S2** (value test before any C++) | **Offline hindsight search**: at ~5k contact states from the S0 replays, roll each candidate 3 rounds in `rulemine/sim.py` with every active dragon played greedy by the numpy net (`ml/p8_sensitivity.py: load_weights/forward`), imagined world = the victim's view only. Report (i) agreement with the played move, (ii) **recall**: share of moves that lost length/died within 3 rounds where search picks something else, (iii) **false alarms**: share of fine moves it overrides, (iv) the same on top-team winners' moves (if it "corrects" winners often, the model is biased) | new `tools/search_offline.py` | executor + critic | 1 d | **Go** if recall ≥ 40% at false alarms ≤ 5% on our moves and ≤ 5% overrides on winners [I] |
| S3 | Cheap rollout net | `ml/distill_mlp.py` (teacher n4 now, the v6 conv later; inputs = imagined-world only); export `viper_search/policy_mlp.hpp` (SIMD, zero-skip, int8/fp16 storage) with self-test vectors | executor + critic; director trains (Python310 CUDA) | 1.5 d | Top-1 agreement with teacher ≥ 90%; `unswbc run maps/trauma.map viper_search baselines/vB19 --sandbox -v` shows ≤ 0.3M per call (microbenchmark turn) |
| S4 | C++ simulator port | `viper_search/sim.hpp`, `viper_search/sim_test.cpp`; `g++ -std=c++17 -O2 -DSIM_NATIVE_TEST viper_search/sim_test.cpp && ./a.out dumps/` | executor; critic diffs against `rulemine/sim.py` | 2 d | 100% on the S1 dumps; `python tools/buildwasm.py viper_search` builds |
| S5 | Search driver, veto mode, contact trigger, guards | `viper_search/main.cpp` (copy of the current best base: vB19 or viper_b19_v4) | executor + critic | 1.5 d | CPU max < 65M over a 20-game smoke; no new timeouts; veto fires on ≥ 5% of contact turns |
| S6 | Paired screen → ladder | `$PY tools/panel_zig.py viper_search baselines/y7_12_49 out/srch_live --set live --seeds 1,2,3 -j 6` (+ `--set dev`), `python -m rulemine.evalpair`, `tools/regression_gate.py`, then `tools/ab_ladder.py` with a vB19 control arm | director | 1-2 d | `nn_plan.md` §5 bars (≥ 10pp paired over ≥ 80 games, then same-time ladder A/B) |

Total ≈ 9-10 working days to S6; ≈ 3 days to the S2 decision.

**Delegable to executor/critic:** S0, S1, S1b, S2 scripts, S3 export and C++ forward, S4, S5 code. **Director only:**
thresholds and go/no-go calls, training runs, panels, every ladder action, deleting data.

#### e.4 Verdict

- **Event dates: unknown.** The sprint tournament happened before 2026-10-01 [R `docs/CHANGES_2026-10-01.md`]; the
  final's date is not in `docs/`, `insights.md`, `AGENTS.md`, the handoffs or the chat transcript, and `/tournaments`
  returned `[]` on 2026-10-01 [R `insights.md` l.84-91]. **The director must get the date.**
- **If ≥ ~2 weeks remain:** realistic as a gated bet. Run S0 (0.5 d) and, if it passes, S1+S2 (2.5 d) before committing to
  the C++ work. **If < ~1 week:** not realistic. Spend the time on the v6 retrain (it already covers the staleness) and on
  rules.
- **Prior on value: modest.** calc's search sat on a pure net, where it was "a tactical safety and food check … most of
  the time it agrees with the net" [W]. Our rules already do exact own-body survival search and free-step enemy reach,
  so the search would add mainly 2-3-round interactions and opponent modelling. The literature we collected says
  evaluation beats depth at this budget [R `algorithms.md` §5]. calc lists "a deeper search" and "a learned value
  function" as useless [W]. Keep D ≤ 3 and the leaf score hand-made.
- **The cheapest test of the idea is S0, then S2.** Both are offline on existing replays, need no games or panels, and
  are compatible with the running pipeline.
