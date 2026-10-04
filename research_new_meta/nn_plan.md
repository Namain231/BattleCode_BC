# Plan: a neural model on top of our rule bot, done properly (2026-10-02)

Scope: how to get from `baselines/vB19` (y7_12_49 + true-queen rules + the old imitation net, `wNN` 2.0 for drones,
0.4 for the queen; ladder 8W-17L, rating ~1686) to the "net + short search + rules" design the calc writeup
describes, and how to measure each step without fooling ourselves.

Tags: **[W]** = stated in `calc WRITEUP.md` (calc's own account; unverifiable, see section 1.3). **[R]** = read in our
repo (file cited). **[M]** = measured by me today. **[I]** = my inference, untested.

---

## 0. Bottom line

1. **calc's design is policy net -> 1-ply-branching rollout search -> rule overrides, trained by behaviour cloning on
   top teams plus their own search-on games, with a C++ engine copy inside the bot** [W "The big picture", §2, §3,
   "Engineering"]. We have the net (old rules, old data), the rules, and a single-dragon `simulate()`. We do **not**
   have an in-bot multi-dragon simulator, a net cheap enough to call dozens of times per turn, or any new-rules
   training data.
2. **The current net is stale and may already be dead weight.** It was trained on pre-2026-10-01 games, has no queen
   input, scores only the first step of a move, and every one of its training artefacts (`ml/data*`, `ml/models/*.pt`)
   is gone from disk [M]. The cheapest high-value experiment is an ablation (vB19 with `wNN` 0) before anything else.
3. **Ranked by gain per effort:** (a) `wNN` ablation and sweep under the new rules; (b) retrain the same architecture
   on new-rules winners' games with queen inputs, fixing a probable train/inference mismatch on plane 8; (c) make the
   net ~10-30x cheaper (calc-style MLP + SIMD); (d) use the net's split/sprint outputs; (e) net-played rollout search
   with an in-bot multi-dragon simulator; (f) mixing in our own games on generated maps. Things calc and our own
   ledger both found useless (PPO fine-tune, learned value for search, bigger nets, deeper search, ensembles/TTA) are
   off the list.
4. **Imitation caps us near the demonstrators' level.** The way calc claims to beat that cap is search on top of the
   net plus rules where the net is blind, not a better clone. That is also the only route here that does not need
   RL-scale compute, which this machine does not have (section 2.5).
5. **Measurement is the binding constraint, as before.** Local panels carry a ~7pp optimism bias; only paired
   same-time ladder A/B with a control arm decides. calc reports the same: +5% local turned into +1.5-2% on the ladder
   [W "Lessons"].

---

## 1. What calc does, and what we already have

### 1.1 calc's bot, per the writeup

| Layer | calc [W, section] | Ours (vB19) [R] |
|---|---|---|
| Sonar | Every dragon sends packets in all 4 directions every round: keeper candidacy, enemy sightings, ruled-out symmetries, explored portals. Encrypted and signed ["1. Sonar"]. | Signed sonar exists in the lineage. vB19 sends queen telemetry (QPOS/EQPOS, enemy-queen alert 0xEC01). Critic found vB19's queen packets carry no team bit (`AGENT_LOG.md`, b19_review). No symmetry/portal gossip. |
| Policy net | MLP 256->128. Inputs: 7x7 window, a **downscaled picture of the remembered map**, length, round, dragon count, can-split. Outputs: left/straight/right/split, split size, continue-sprint after each step ["2. The policy net"]. | Conv net (`policy_nn.hpp`): 19 input planes 15x15 (16 uint8 + 3 broadcast scalars), 3 conv layers of 32 ch, FC 64, 6 logits (fwd/right/back/left/split/other). ~125k weights, ~18M points per call ([R] `ml/results.md`, `guide/5`). Only the first-step direction is used (`main.cpp:1738`). No memory input beyond the known-map planes. |
| Training | Behaviour cloning of top teams' replays, **mixed with their own search-on games on official and random maps**. PPO-only nets lost on the ladder ["2. Training", "Lessons"]. | BC on 2.34M decisions from 356 (later ~900) winning top-team games, old rules only. PPO runs 1-6 worse than BC. Filtered self-imitation round 1 17/28 maze, never finished (`ml/results.md`). |
| Search | Candidates = legal moves above a probability floor. Imagined world from vision + memory; unseen dragons don't exist, unknown tiles = open water. Each candidate rolled 3 rounds (5 in the opening) in a C++ engine copy, **every dragon on both teams played by the net**. Score = our total length minus theirs. Spare CPU -> randomized play-outs allocated by UCB1. Net's move kept on ties ["3. The search"]. | `simulate()` (`main.cpp:736`) plays **our own** move only (1-3 steps, FSPRINT enumeration) against a frozen world; `evaluate()` hand-scores it (pDeath, danger, food). No other dragon moves, no rollout, no net in the loop. |
| Rules | Hidden food behind kelp, portal exploration, map symmetry mirroring; escape split when boxed in; least-bad collision; keeper election, feed-the-keeper, hunt the enemy's longest ["4. Rules"]. | All of these exist in some form in the v7.12 lineage (`detectSymmetry`, `mirSpawn`, `doomedSplit`, `tryFeed`, hunt, true-queen rules). |
| Engineering | Engine copy matched turn-for-turn with automated checks; CPU measured the judge's way; net made **~8x cheaper with identical moves** (zero-input skipping, SIMD, caching); paired-seed evaluation, ~128-game screens, official vs random maps reported separately ["Engineering"]. | Zig judge + `unswbc` engine wasm outside the bot; `rulemine.parity`; `buildwasm.py`; `panel_zig.py`, `regression_gate.py`, `ab_ladder.py`, `sprt.py`. No in-bot engine; no SIMD work on the net. |
| What did not help | Copying the search's choices (AlphaZero-style), a learned value function, bigger nets, PPO after cloning, deeper search, spawner camping, centre rush ["Lessons"]. | We independently found: bigger nets, ensembles, distillation, joint value head, PPO all neutral or worse (`ml/results.md` technique ledger). |

### 1.2 The single most important difference

calc's net is the **primary move generator**, checked by a search, with rules as overrides. Ours is a **bonus term
inside a rule scorer**: `score += wNN * log p(first step)` within a safety class (`main.cpp:1736-1742`). That is a
reasonable hybrid (it is what took the maze record from 32-37% to 53-65% under the old rules [R `ml/results.md`]),
but it means the net can never do anything the rule scorer's candidate set and safety classes don't already allow,
and it never sees split or sprint-length decisions.

### 1.3 Claims I could not verify

- **The writeup describes the old rules.** It says "a game that reaches round 500 goes to the team with the longest
  living dragon", and its endgame is a "keeper" elected over sonar [W "The game in one paragraph", "4. Rules"]. Under
  the 2026-10-01 rules the queen is fixed to id 0/1 (`docs/CHANGES_2026-10-01.md`). The keeper/feeding layer does not
  transfer as written; the net/search/BC parts are rule-agnostic.
- No numbers are given for net accuracy, data volume, search width, CPU per turn, or ladder results. "8x cheaper" and
  "+5% local -> +1.5-2% ladder" are the only figures.
- "Copying the search's choices didn't help" vs "mixing our own search-on games helped" is close to a contradiction
  (own search-on games are labelled with the search's choices). Possible reading [I]: the first means training on the
  search's visit/score distribution as a target; the second means BC on own games' played moves as extra data,
  mainly for map diversity. Treat the distinction as unknown.
- I cannot confirm calc is still top under the new rules, or that its bot today matches the writeup.
- "Unknown tiles treated as open water" is optimistic for a maze; how they avoid rollouts walking into unseen kelp is
  not stated.

---

## 2. The gap between calc's net and ours

### 2.1 Inputs
| Issue | Evidence | Consequence |
|---|---|---|
| No queen information | `nnInput` (`main.cpp:1519`) writes heads by length only; scalars are length/round/units | The net cannot tell "I am the queen", "that head is the enemy queen", "our queen is next to me". The queen gets `wNN` 0.4 as a workaround. |
| No remembered-map input | 15x15 planes are known-map terrain + 7x7 view; calc adds a downscaled remembered map | ~28% of top-team moves are unexplained by what the net sees (`ml/results.md`: "the ceiling is information the network cannot see"). A memory plane (v5) gave -0.5 offline, but that was pearls only, not terrain/enemy sightings. |
| Known-map dependence | Planes 0-8 come from embedded map tables (`maps_data.hpp`) | On the new maps of the final, kelp/portal/rate planes outside seen cells are empty: a distribution shift the net never trained on. |
| **Probable plane-8 mismatch** | Public replays zero every TILE line (memory note `bc_replay_and_ladder_testing_facts`); `build_dataset.py:64-67` builds plane 8 from the replay's TILE lines; the bot fills plane 8 from `gmin/gmax` (`main.cpp:1534`) | If both hold, the net trained with plane 8 = 0 everywhere and plays with it non-zero. **Not verified**: the dataset was built 09-27/28 and the zeroing was noted 09-30. First thing to check (milestone M2). |
| Sprint economy changed | Free steps are now ceil(L/4) (`docs/CHANGES`) | Old-rules labels for sprints are wrong for any dragon of length >= 5; the scalar `len/32` is there, but the behaviour it was trained on is obsolete. |

### 2.2 Targets
- Labels are the first step of each move (fwd/right/back/left), split, or "other" (`build_dataset.py` header). The bot
  uses only the 4 directions. calc's net also predicts split size and continue-sprint per step [W §2]; under the new
  sprint rule, how far to sprint is a first-order decision for the queen and for strikers.
- No value/outcome target in use (our joint policy+value was neutral; calc's learned value did not help). Keep it
  that way.

### 2.3 Data volume and freshness
- Old data: 2.34M decisions / 356 games (v1), up to ~4M (v2) [R]. **All of it is old rules and none of it is on disk
  now** [M: `ml/` has no `data*` or `models/`; `ladder/scout*` hold only `index.json`/`PLAYERS.md`, no replays].
  The only surviving net is the exported `policy_weights.hpp`.
- New-rules data: unknown volume. Autoscrims run ~3 battles x 5 games per team per hour (`docs/CHANGES`), so a team
  could have ~400+ new-rules games since 2026-10-01 [I], but `tools/scout.py` reads only a team's `recent` list
  (length undocumented) and has no date filter. Filter by game id: every game with id above our own first new-rules
  game (from vB19's battles) is new-rules, since all old submissions were deactivated at the switch.
- Queen samples are scarce by construction: one queen per team per game. If top teams keep queens alive (unknown;
  our own bots lose them by median round 58 [R `numbers.md` §2]), a game gives up to ~500 queen decisions, so ~300
  games give ~100k queen samples, enough for a queen-conditioned head, not a separate net [I].

### 2.4 Label quality
- BC from public replays learns the demonstrators' moves conditioned on our partial inputs; their memory, sonar and
  plans are invisible, so accuracy plateaued at ~71-73% whatever the capacity (`ml/results.md` "Pushing the ~72%").
- Winners-only filtering exists (`build_dataset.py:233`), which removes losing games but not losing moves.
- Teams change bots mid-season; `tools/latest_only.py` keeps each team's newest submission, which matters more now
  that every team is rewriting for the queen rule.

### 2.5 How it is combined with rules, and why imitation caps us
- Combination: additive log-prior inside safety classes, first step only, drones `wNN` 2, queen 0.4, off on
  `bigFeed` maps (Portals/Slithery/Schooltime) (`main.cpp:361-369, 1558, 1738`).
- **Cap [I]:** a BC policy at best reproduces the average demonstrator given our inputs, blurred by the 28% it cannot
  see, plus compounding error under distribution shift (Ross et al. 2011, cited in `RULE_BASED_METHODS.md` §5). Its
  ceiling is "a blurred top team". Our hybrid beat that ceiling only because the rules carry what the net can't. To go
  beyond the demonstrators you need a policy-improvement step: search that corrects the net's tactical errors
  (calc's choice), or RL. RL at laptop scale failed six times here (6-12 games per update; run 5 at 5/20 vs BC, run
  6 killed by memory [R `ml/results.md`]). Search is the feasible improvement operator; it costs CPU at play time,
  not training compute.

---

## 3. Staged plan, ranked by expected gain per effort

Effort in working days for one person plus executor agents. "Gain" is my prior on ladder effect, not a measurement.

| # | Option | Gain | Effort | Evidence for | Main risk / falsifier |
|---|---|---|---|---|---|
| A | **Ablate and sweep `wNN` under new rules** (0 / 1 / 2 / 4 for drones; 0 / 0.4 for queen) | Unknown sign; tells us if the stale net helps at all | 0.3 | Net was the only big win under old rules; rules have since changed | If `wNN` 0 is within noise of 2 on paired metrics, the current net is worth nothing now and B becomes the priority |
| B | **Retrain on new-rules winners' data** with queen inputs (scalars `is_queen`, `f(L)`; planes enemy-queen head, own-queen head), latest submissions only, plane-8 fix, same architecture | Medium-high | 1.5 | BC was the only big win; calc says copy strong players first [W "Lessons"] | Too little new-rules data; offline gains not transferring (has happened 5+ times) |
| C | **Cheap net**: calc-style MLP on 7x7 view + coarse remembered map + scalars, int8 or fp16 weights, SIMD, zero-input skipping; target <= 1-2M points per call | Low alone; enabler for E | 1.5 | calc's 8x [W]; our forward is ~2.2M MACs at ~18M points, i.e. scalar ~8 points/MAC [I from `policy_nn.hpp`] | Accuracy drop vs conv net; wasm SIMD auto-vectorisation may already be partly on (`-O2 -msimd128`): measure before rewriting |
| D | **Use sprint-length and split heads** (add a steps-taken label; feed `p(split)` and `p(k steps)` into `trySplit`/FSPRINT scoring as priors) | Medium for queen and strikers | 1 | Sprint is now cheap for long dragons and top-team behaviour around it is new; we waste 62-79% of free steps at L>=5 [R `numbers.md` §4] | Head is noisy with little data; the queen's split must stay rule-gated (round-0 SHED/ESCAPE split is correct per `AGENT_LOG.md` qdoomed_off) |
| E | **Net-played rollout search** (calc §3): in-bot multi-dragon simulator over the imagined world, candidates = rule-safe moves with p > floor, 3-round rollouts with every visible dragon played by the cheap net, score = our length minus theirs **with queen length weighted for the new tiebreak**, UCB1 for spare CPU | High if it works; this is calc's improvement operator | 4-6 | calc's central layer; tactical misses (head-on trades 60/34 own/enemy vs calc 84/11 [R `RULE_BASED_METHODS.md` §1]) are what search catches | Simulator parity bugs; CPU blow-up; our `RULE_BASED_METHODS.md`/`algorithms.md` argue evaluation > depth. Keep depth fixed at 3, no tree |
| F | **Own-games mixing on generated maps** (DAgger-lite): play the B/E bot on `maps_rm_dev` + `maps_gen`, BC on our winning sides' moves mixed 50/50 with top-team data | Medium for the unseen-map final | 1.5 | calc: mixing own games on generated maps stopped the net memorising official maps [W "Lessons"]; `selfplay_collect.py` exists | calc says copying search choices didn't help; the line between F and that is unclear (section 1.3) |
| G | **Net as primary on drones** (argmax of net among safe moves; rules override only for queen, feeding, hunting, escape) | Unknown; cheap to try as `wNN` 6-10 | 0.3 | calc's architecture | `wNN` 3 was worse than 2 locally under old rules (83% vs 88%) [R] |
| — | Not doing: PPO / any RL fine-tune, learned value in search, bigger nets, deeper search, ensembles/TTA, distillation of the rule bot into the net, team-style conditioning | ~0 | — | calc's "didn't help" list and our ledger agree on every item | — |

**On "distillation of the rule bot into the net"**: this would train the net to copy our own rule bot. It cannot
exceed the rule bot and is roughly what calc's failed "copy the search's choices" is [I]. Its only use is cost: a
cheap net that imitates expensive rule code. Skip until E needs it.

**On ensembling**: +0.5 offline for 5x CPU [R]. Skip; the CPU belongs to search.

**Recommended order:** A -> B (with M2's plane-8 check) -> D (cheap once B's data pipeline exists) -> C -> E -> F.
G rides along with A as an extra sweep value. Stop and re-plan if A shows the net is neutral *and* B's retrained net
is also neutral on paired metrics: then the net is not the lever under the new rules, and the queen rules are.

### Design notes for B
- Inputs: keep the 16 planes (so `nnInput` stays mostly identical), add scalars `is_queen` (MY_ID <= 1),
  `ceil(L/4)/8`, `queen_alive` (own), `enemy_queen_seen_recently`, and planes 16-17 = own-queen head / enemy-queen
  head (from vision; queen = id 0/1 by team). Owner of id 0 varies by map: derive from the replay's DRAGON order,
  never `MY_ID == MY_TEAM` (memory note `project_new_rules_queen_work`).
- Plane 8: either fill from `maps/*.map` by MAP_NAME at dataset time (as `tools/farming_profile.py:bed_gaps` does)
  and from `learnGap` estimates in the bot on unknown maps, or zero it on both sides. Zeroing is the map-agnostic
  choice for the final.
- Memory: build features with `rulemine/state.py`'s per-dragon memory instead of the raw replay, so remembered
  terrain/pearls match what our bot would know [I: verify the state class exposes what's needed].
- Labels: first-step direction + split (as now) + steps taken (1/2/3/4+) as a second head.
- Data filter: game id > G0 (first new-rules game), winner == scouted side, latest submission per team, top ~16
  teams, all maps including generated ones if any appear on the ladder. Weight queen-dragon samples x3 in the loss
  [I] rather than training a second net.
- Train from scratch first; warm-starting from old weights needs a script to re-import `policy_weights.hpp` (the
  `.pt` files are gone). Only worth writing if new-rules data is under ~300k decisions.

### Design notes for E
- Simulator: one compact C++ struct with board, bodies, pearls, and an `apply(dragon, action)` implementing
  `docs/execution-order.md` + `movement.md` (free steps ceil(L/4)) + `death.md` + `splitting.md`. Parity test: replay
  N recorded games through it and compare state round by round (extend `rulemine.parity` or write
  `tools/sim_parity.py`). calc did exactly this with automated checks [W "Engineering"].
- Imagined world: our memory map + visible dragons only; unseen tiles open; pearls as remembered. Opponent dragons
  played by the net greedily (argmax), ours by the net with the rules' safety filter.
- Score: our total length minus theirs, plus a large queen term (queen dead = big negative; enemy queen dead = big
  positive), since the queen is now tiebreak 1. This is a new-rules change to calc's objective [I].
- Budget: 100M points/turn, keep max <= 65M (`AGENTS.md`). With a ~1M-point net and ~6 dragons within the
  horizon, 3 candidates x 3 rounds x 6 dragons = 54 net calls ~ 55M: tight. Hence C first; restrict rollouts to
  dragons within R(L) reach of the horizon (as `algorithms.md` §5.4 suggests); run search only when an enemy head is
  within ~6 cells or a pearl is contested; otherwise use the net+rules move directly.

---

## 4. Hard constraints

| Constraint | Value | Source | Implication |
|---|---|---|---|
| CPU per dragon-turn | 100M points; keep max <= ~65M | `docs/timeouts.md`, `AGENTS.md` | Current net ~18M/call (one call per turn). Search needs <= ~1-2M per call. SIMD instructions cost 2 points for 4 lanes: f32x4 matmul is ~4x cheaper per MAC than scalar [`timeouts.md` price list]. |
| Memory | 48 MB per dragon | `timeouts.md` | Weights are fine (125k floats = 0.5 MB). Simulator copies for rollouts must be small (64x64 max board). |
| Submission size | 4 MB zip | `docs/submitting.md` | `policy_weights.hpp` is 1.56 MB of text for 125k weights [M]; `maps_data.hpp` 133 KB. A 450k-weight calc-size MLP as text would be ~5.5 MB uncompressed: store int8/fp16 as hex or byte arrays. Check zip size at every export. |
| No network, no threads, no writable disk | — | `timeouts.md`, `libraries.md` | All weights compiled in. |
| Determinism | RNG seeded per dragon per game; `__DATE__`/`__TIME__` are errors | `timeouts.md` | Rollout randomness must use the sandbox RNG or a hash of (id, round); fine. Replays then reproduce, which our paired-seed testing needs. |
| stdout cost | 2.5M points per write + 4k/byte | `timeouts.md` | Never log feature vectors in a submitted build (same rule as `rmLog`). |
| Training hardware | GTX 1650, 4 GB VRAM, CUDA 12.4 toolkit; 15.4 GB RAM; 12 logical CPUs | [M] `nvidia-smi`, `nvcc`, CIM | Old runs: ~30 s/epoch on 1.1M samples on an RTX 3050 [R]; the 1650 is slower, est. 1-2 min/epoch [I]: fine for these net sizes. Hold <= ~1M samples in RAM (16x225 B = 3.6 KB each, ~3.6 GB) because WSL + desktop eat 5-6 GB (`AGENTS.md`). |
| Python environments | Torch with CUDA only in `AppData/Local/Programs/Python/Python310` (torch 2.5.1+cu124, `cuda.is_available()` True) [M]; `uv run --python 3.11 --with torch` gives CPU torch 2.14.1 [M]; msys python segfaults on zlib | memory notes | Build datasets with `uv run --python 3.11 --with unswbc --with numpy`, train with Python310. |
| **Disk** | **6.6 GB free on C:** [M `df -h /c`] | — | Hard limit for scouting. ~300-600 replays + shards is likely 1-2 GB [I]. Delete replays after shards are built; check `df` before and after. |
| Free offload compute | Colab worker notebook, Kaggle kernels (account noted in `ml/results.md`), Lightning studio | `guide/5` | Self-play collection (F) belongs there, not on this laptop. |
| Data availability | Public replays via `GET /battles/<id>/replay`; TILE lines zeroed, CPU and indicators stripped | memory note `bc_replay_and_ladder_testing_facts` | Bed rates must come from `maps/*.map` by name, or be dropped (plane 8). |
| Public-replay leakage | Our games are public too | `AGENTS.md` | Anyone can clone our play exactly as we clone theirs; nothing to hide in the weights themselves. Keep indicator strings off, submission names neutral (`Y.7.12.<n>`), sonar encrypted. Expect top teams' new-rules play to shift fast: re-scout every 2-3 days. |
| API quotas | 120 req/min; 60 challenge games/hour; DEV battles separate 60/hour | `AGENTS.md`, `docs/CHANGES` | Scouting ~600 games is ~1,000+ requests: run at the existing 0.6 s pacing (~15 min per team block). |

---

## 5. Evaluation protocol (built to avoid the recorded optimism bias)

The post-mortem facts this must respect: a fixed 32-game panel selected changes with ~7pp optimism; ~11 of 32
games flip per change at random; local self-play vs a champion sits near 50% for every change; local results don't
reproduce contention-driven ladder metrics; offline accuracy gains never transferred (memory
`s4_7_postmortem_wrong_objective`, `bc_replay_and_ladder_testing_facts`; `ml/results.md`).

1. **Offline is a sanity check only.** Held-out *games* (not samples), split by game id. A new net must not lose more
   than 1pt of first-step accuracy against the previous one on new-rules validation data, and must pass the C++
   self-test (`nnSelfTest`) plus a bot-vs-Python parity check (same top move on >= 95% of dumped states, as the old
   560/581 check did). Accuracy gains are never a reason to ship.
2. **Pre-register** in `AGENT_LOG.md` before every run: hypothesis, mechanism metric with threshold, end metric,
   falsifier. Mechanism metrics for this plan: queen survival to r500, queen length r250/r400/r500, enemy-queen kill
   rate, `tempo.py` edge@r50, head-on drop share own/enemy, CPU max.
3. **Local paired screen** (`tools/panel_zig.py`, zig judge, unswbc 1.2.3): candidate and control each play the same
   opponent (`baselines/y7_12_49` and `baselines/vB19`) on the same maps x seeds x both sides; compare per
   (map, seed, side) pair with `python -m rulemine.evalpair CAND_OUT CTRL_OUT`. Sets: `live` (report the trapped-queen
   maps dilemma/slithery_fight/autarky separately; they are being replaced) and `dev` (`maps_rm_dev`), **always
   reported separately** (calc's rule too). `test` (`maps_rm_test`) only for a final check.
4. **Smoke gate:** `tools/regression_gate.py CAND OUT --opp baselines/vB19 --set live --seeds 1,2` (fails on early
   queen deaths the control doesn't have) and CPU max < 65M from `unswbc run --sandbox -v`.
5. **Local bar to reach the ladder:** paired gain >= 10pp on win rate over >= 80 paired games (to clear the ~7pp
   bias) **or** a pre-registered mechanism metric moving with the end metric not falling. Use `tools/sprt.py` with
   p1 = 0.65 so it stops in ~85 games instead of ~150.
6. **Ladder decides:** `tools/ab_ladder.py` with a **same-time control arm** (vB19), near-rating opponents (where the
   baseline is ~50%, not 2000+ teams at a floor), DEV battles (separate 60 games/hour), ~100 games per arm to
   resolve ~20pp. Also read the per-submission rating and per-map offsets the new rating system keeps
   (`docs/elo.md`): a new submission inherits the old rating with +-75 uncertainty, so wait for it to settle
   (1-2 days of autoscrims) before reading it. Don't churn uploads (each resets uncertainty).
7. **Expect shrinkage:** calc saw +5% local become +1.5-2% ladder [W]. Budget for it: a candidate needs a large
   local effect to be worth a ladder slot.

---

## 6. First two days: milestones

Commands assume the repo root, PowerShell for `uv`/panels (auto-wraps WSL), Git Bash for `export`. `PY310` =
`C:/Users/sohan/AppData/Local/Programs/Python/Python310/python.exe`. Run `df -h /c` before any scouting or panel
with replays kept. Cap panels at `-j 6` if anything else runs.

### Day 1

**M1. `wNN` ablation and sweep (director; executor makes the copies).** Covers option A and G.
- Executor task `tools/tasks/nn_ablate.md`: copy `baselines/vB19` to `viper_nn_w0` (Params `wNN = 0`, queen weight
  0), `viper_nn_w1` (`wNN = 1`), `viper_nn_w4` (`wNN = 4`), `viper_nn_w8` (`wNN = 8`, G); touch `main.cpp`; build each
  with `python tools/buildwasm.py <dir>`. Nothing else changes.
- Run (each vs the same opponent; vB19 itself is the control arm):
  `uv run --python 3.11 --with unswbc python tools/panel_zig.py <dir> baselines/y7_12_49 out/abl_<name>_live --set live --seeds 1,2,3 -j 6`
  and the same with `--set dev --seeds 1`, for vB19 and the four variants (5 x 100 games; ~2-3 hours at -j 6 [I]).
- Read: `python -m rulemine.evalpair out/abl_w0_live out/abl_vB19_live` (and dev), plus queen metrics via
  `research_new_meta/analyze.py`.
- Pre-registered falsifier: if `w0` is within +-5pp paired of vB19 on both sets, the stale net is not contributing
  and M3-M6 are the priority; if `w0` is clearly worse, keep the net in every build while retraining.

**M2. Plane-8 and input audit (executor + critic).** Task `tools/tasks/nn_plane8.md`:
- Scout 3-5 public new-rules replays: `python tools/scout.py --top 3 --per-team 2 --out ladder/il_probe`.
- Check whether TILE lines are zeroed (decode with `tools/replay.py`), and what `build_dataset.parse_map` produces for
  plane 8 on them.
- Dump `nnInput` planes for one state in a debug build (copy of vB19, `debug_cfg.hpp`, never submitted) and diff
  against `build_dataset.snapshot` on the same replay state.
- Deliverable: a short table per plane: "train source / bot source / match?". Critic checks the diff method.

**M3. New-rules scout with a game-id cutoff (executor; director runs the download).**
- Executor: add `--min-game-id` to `tools/scout.py` (skip games below it) and log how many `recent` entries each
  team returns. Director finds G0 as the smallest game id in vB19's ladder battles (submission 14297).
- Run (Git Bash): `export $(cat secrets.env | xargs); python tools/scout.py --top 16 --per-team 60 --min-game-id <G0> --out ladder/il_new`
  then `python tools/latest_only.py ladder/il_new/index.json --out ladder/il_new/latest_index.json --min-games 4`.
- Record in `AGENT_LOG.md`: games per team, wins, maps, queen-alive-at-r500 rate for top teams
  (`research_new_meta/analyze.py` on a sample). If top teams also lose queens early, queen-conditioned samples will be
  few; note it.

**M4. Dataset v6 (executor + critic).** Task `tools/tasks/nn_dataset_v6.md`, editing `ml/build_dataset.py` into a new
`ml/build_dataset_v6.py` (old file untouched):
- Scalars: len/32, round/500, units/64, is_queen, ceil(L/4)/8, own_queen_alive.
- Planes: existing 16 (plane 8 per M2's decision) + own-queen head + enemy-queen head. Queen = id 0/1, team from
  DRAGON order.
- Labels: first-step class (as now) + `steps` (1, 2, 3, 4+) for moves.
- Filter: winner == side, game id >= G0.
- Verify: `uv run --python 3.11 --with numpy python ml/build_dataset_v6.py --index ladder/il_new/latest_index.json --out ml/data_v6 --workers 4`,
  then print sample counts, label histogram, queen-sample count, and check shards load in `ml/train.py`'s loader.
  Critic: checks the queen id/team mapping against `docs/map-files.md` alternation, and that no field uses
  information our bot cannot have.

### Day 2

**M5. Train (director).** Executor first extends `ml/train.py` (or a `train_v6.py`) for the extra planes/scalars and
the steps head (loss = CE(first step) + 0.3 CE(steps) [I]), queen samples weighted x3.
`$PY310 ml/train_v6.py --data ml/data_v6 --out ml/models/nr1.pt --epochs 12 --max-samples 1000000`
Also train `nr1_noq` without the queen planes/scalars, to attribute any gain. Record val accuracy per class and for
queen samples separately.

**M6. Export and build (executor + critic).** Extend `ml/export_cpp.py` and `policy_nn.hpp` for 18 planes / 6 scalars;
copy `baselines/vB19` to `viper_nr1`; update `nnInput` to write the new planes/scalars exactly as the dataset does;
keep the additive combination (`wNN` 2 drones; queen weight re-swept later). Verify: `nnSelfTest` matches,
`python tools/buildwasm.py viper_nr1`, and
`unswbc run maps/trauma.map viper_nr1 baselines/vB19 --sandbox -v` with max points < 65M. Critic: diff `nnInput` against
`build_dataset_v6.snapshot` plane by plane. Delete `ladder/il_new/**/*.replay` once shards exist and are logged.

**M7. Paired screen (director).**
`uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_nr1 baselines/y7_12_49 out/nr1_live --set live --seeds 1,2,3 -j 6`
and `--set dev --seeds 1`; compare to M1's `out/abl_vB19_*` with `rulemine.evalpair`; run
`tools/regression_gate.py viper_nr1 out/nr1_gate --opp baselines/vB19 --set live --seeds 1,2`.
Bar (section 5.5). If it passes, schedule M8; if not, record the result and go to option D/C planning, not more
retraining variants.

**M8 (only if M7 passes). Ladder A/B.** Submit as the next neutral name `Y.7.12.<n>` with an empty description,
record the id in `AGENTS.md`'s mapping table, then
`python tools/ab_ladder.py <new sub id> 14297 --teams <near-rating team ids> --maps <map ids> --out ladder/ab_nr1 --deadline-utc HH:MM`
(vB19 = 14297 as the control arm), ~100 games per arm over DEV battles. Note `ab_ladder.py`'s default `--maps` are
the old maze-map ids; check the current pool with `GET /maps` first. Re-activate the better build afterwards.

### What to delegate, per `AGENTS.md` "Agent protocol"
| Delegate to executor (with critic review) | Keep with the director |
|---|---|
| M1 copies/builds; M2 audit scripts; M3 `--min-game-id`; M4 dataset v6; M5 trainer changes; M6 export/`nnInput`/self-test | G0 choice; all panel runs and their reading; pre-registration lines; accept/reject; every ladder action (submit, activate, `ab_ladder.py`); deleting data |

Every task file names its working dir (never `baselines/`), the exact verify command, and what counts as done;
executors report what they did not verify. `opencode`/`codex` are not installed (`AGENTS.md`), so the executor and
critic are Claude subagents following the same protocol.

---

## 7. Beyond day 2 (sketch, gated on the results above)

- **Week 1:** option D (steps/split heads into FSPRINT and `trySplit` priors, queen still rule-gated); option C (MLP
  + SIMD + int8, accuracy within 1pt of the conv net, <= 2M points/call).
- **Week 2:** option E: simulator + parity tool first (no bot changes until parity holds on 50+ replays), then
  search on drones only in contact situations, then the queen.
- **Ongoing:** re-scout every 2-3 days (the meta is moving fast after the rule change); option F's own-games mixing
  on Kaggle/Colab once E exists, since calc's mixed data was its own search-on bot.
