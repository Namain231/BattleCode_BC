# ML track: morning report

## Test queue (run whenever a resource is free; screen locally vs the champion, ladder-test only what screens well)

Champion: **Y.7.12-nn.1** (9285). Local screens are 42 maze games vs the champion unless noted.

| Idea | Evidence behind it | Result | Verdict |
|---|---|---|---|
| v2 model (679 games, prev-turn input, AWR 0.5) | 72.0% vs 70.6% offline | 26/56 (46%) vs champion | not better |
| more data only (v1b: v2 data, v1 inputs) | 71.8% offline | — | explains most of v2's offline gain |
| opening-focused v2 (rounds < 200) | win predictor | 72.4% offline on openings | not screened yet |
| lane sonar on the champion | V7.14 fewer self-traps | 22/42 (52%) | neutral |
| giant hunt / surround on the champion | late collapses vs giants | 20/42 (48%) | neutral |
| earlier queen (round 250) | longest lead from r200 wins 73% | 15/42 (36%) | **worse**: keep 340 |
| soft opening safety for the network | top teams accept 3x our wall deaths | 20/42 (48%) | neutral |
| sonar replay attack (9298) | top teams send thousands of msgs/game | ladder same-time A/B vs 6 top teams: 5/30 vs champion 4/30 | no effect: dropped |
| offline Q-network (move -> 20-round outcome) | offline RL | held-out corr 0.35; top-20% rated moves +1.10 vs bottom-20% -0.53 | learnable |
| joint policy+value network (one pass) | Q signal at no extra CPU | policy 71.9%, value corr 0.35; vs champion 19/42 (wQ 0.5), 19/41 (wQ 1) | neutral |
| more data only (v1b build) | 71.8% offline | 22/42 (52%) | neutral |
| **pearl gossip** (signed sonar: share a visible pearl we are not chasing) | top teams send thousands of msgs/game | 31/54, then 44/84 maze (52%); **early eating 0.089 vs 0.065 per dragon-turn (+37%), 70% more dragon-turns by r100** | economy lever confirmed; ladder A/B running as **Y.7.12.3** (9357) |
| v3 policy (current-version data only, 585 games) | old versions teach old habits | 70.5% offline (harder val set) | screening |
| distillation: 64-ch teacher 73.5% -> 32-ch student | Hinton KD | training | |
| signed sonar gossip (keyed hash, unforgeable, unreadable) | defence; top teams' msgs look random | behaviour unchanged (3/6) | keep in every build |
| distillation (64-ch teacher -> 32-ch student) | +0.9% offline at 4x cost | Colab teacher running | queued |
| data from teams' latest submissions only; ranks 13-40 | old versions teach old habits | filtering / downloading | queued |

## Pipeline (all verified)

| Step | Where | Status |
|---|---|---|
| Replays → training samples | `ml/build_dataset.py` | 2.34M decisions from 356 winning top-12 games (`ml/data_v1`). Egocentric 15×15, rotated to face up; only information our bot has. Rotation checked against `board_at.py`. |
| Training | `ml/train.py` | RTX 3050, ~30 s/epoch on 1.1M samples. Mirror augmentation, validation on held-out games. |
| Export to C++ | `ml/export_cpp.py` → `viper_nn/policy_weights.hpp` | C++ forward pass (`viper_nn/policy_nn.hpp`) matches PyTorch exactly (self-test in the sandbox). |
| In-bot inputs | `viper_nn/main.cpp` (`nnInput`) | Bot vs Python on the same states: same top move 560/581, median probability gap 0.01. |
| Cost in the judge | `unswbc run --sandbox -v` | ~18M points per network call (padded convolutions; the first version cost 44M). Limit 100M. |

Bugs caught by the checks: walls/portals were stored at 1/255 strength in the first dataset (fixed); the sandbox
build cache keys on `main.cpp` only (touch it after changing a header).

## Offline accuracy (move of a top-team dragon, held-out games)

| Model | Data | Accuracy | "Always forward" |
|---|---|---|---|
| pilot (walls invisible by bug) | 1.13M, 171 games | 71.5% | 42.2% |
| v1 (32 ch, 125k weights) | 1.1M of 2.34M, 356 games | 70.6% | 45.8% |

Colab sweep (full 2.34M data; 32/48/64 channels; opening-only): queued, results below when done.

## Does it play better? (local self-play vs V7.12)

`viper_nn` = V7.12 + `wNN × log p(move)` added to every move's score (the safety classes still come first).
Model v1. Maze maps 42 games (3 seeds × both sides × 7 maps), open maps 12 games.

| wNN | Maze vs V7.12 | Open vs V7.12 | Notable |
|---|---|---|---|
| 0.5 | 22/42 (52%) | 5/12 | |
| 1 | **32/42 (76%)** | 5/12 | Autarky 6/6, Devil 6/6, QoS 6/6, Dilemma 5/6; Portals 0/4 |
| 2 | **34/42 (81%)** | 4/12 | Autarky, Devil, Dilemma 6/6; QoS 5/6; Portals 0/4 |

Every earlier self-play variant of V7.12 landed near 50% (the best ever: 60%). Worst turn 60M points (limit 100M).
The network hurts on the open maps (Portals 0/4), matching the win-predictor finding that Portals plays differently:
next variant keeps V7.12's play there (`exp_nn_w2m`/`w3m`: network off on Portals/Slithery/Schooltime).
Self-play has misled us before (V7.6), so it also gets tested against teammates' S.2 and vB.4 (different styles).

**Network on maze maps only** (84 maze games, fresh seeds; open maps play exactly like V7.12):

| Variant | Maze vs V7.12 | Per map | Open vs V7.12 |
|---|---|---|---|
| `exp_nn_w2m` (wNN 2) | **74W 9L 1D (88%)** | Autarky 12/12, Devil 12/12, Dilemma 12/12, QoS 11/12, Trophy 10/11, Default 9/12, Trauma 8/12 | 6/12 (even) |
| `exp_nn_w3m` (wNN 3) | 70W 14L (83%) | Trauma 4/12 | |

`exp_nn_w2m` is the candidate.

**Gate (stage 1):** 70% vs V7.12 over all 10 maps (no map below 50%), 75% vs V7.5.
**Cross-style (local):** vs teammates' S.2 70% (V7.12: 69%) — dominant on maze maps (Autarky/Devil/Dilemma 4/4),
weak on Portals 1/4, Trauma/Slithery/Schooltime 2/4 = S.2's strengths (queen/endgame, few sprints). vs vB.4 75%.

## Ladder (unranked) — `test-v7.17-nn` (id 9258, = `Y.7.12-nn.1`), 2026-09-28 ~03:45 IST

8 strong teams × 5 maze maps [Trophy, Default, Autarky, Devil, Trauma]: **24/40 (60%)**.
V7.12's historical rate on the same opponent+map: **6.0/40**. (Opponents' bots change: a same-time V7.12 control
against 4 of them is running.)

| Team | Y.7.12-nn.1 | Team | Y.7.12-nn.1 |
|---|---|---|---|
| Rogo | 4/5 | Hakimi | 3/5 |
| WeLikCoding | 4/5 | Shannon | 3/5 |
| kfcvme50 | 4/5 | WCTW | 2/5 |
| !ghaplebaaz | 4/5 | tungtung67 (now 1938) | 0/5 |

Per map: Trophy 6/8, Autarky 6/8, Devil 5/8, Default 4/8, Trauma 3/8. Kept active as the best build.

**Same-time control** (03:54 IST, V7.12 vs 4 of the same teams, same maps): V7.12 **6/20** (Rogo 1, WeLikCoding 2,
kfcvme50 1, !ghaplebaaz 2) vs Y.7.12-nn.1 **16/20** (4/5 each). Resubmitted as **Y.7.12-nn.1** (id 9285), champion.

Teammates' S.3 on the ladder (5 teams ~1670-1700): 13/45 (29%), open maps 5/15 — its open-map edge in local games
against our bots does not show against real opponents, so nothing to borrow yet.

## Colab sweep (full 2.34M data, T4)

| Model | Val accuracy |
|---|---|
| 32 channels (v1 size) | 70.4% |
| 48 channels | 71.1% |
| 64 channels | 71.3% |
| 32 channels, rounds < 200 only | 70.6% |

Capacity is saturated (+0.9 points for 4× the compute): the limit is the information in the inputs, not the network.

## Win predictors (all 1,917 replays, `ml/state_value.py`, raw output `ml/state_value.log`)

A gradient-boosted model predicts the winner from the us-minus-them state at a checkpoint (held-out games):
round 50 **72%**, round 100 72%, round 200 **79%**, round 300 77%, round 400 78%. The game is largely decided early.

| Checkpoint | Most predictive | Win rate when ahead / behind |
|---|---|---|
| r50 | total length, fountain eats, splits | units +6: 79% / −6: 21% |
| r100 | total, splits, units | units +6: **82%** / −6: 18% |
| r200 | total, splits, units | longest +1..+5: **73%** / −1..−5: 27% |
| r400 | **longest**, splits | longest +6: **88%** / −6: 12% |

Per map at r100 (win rate when ahead on units by 5+ / on longest by 3+): Devil 94/81, QoS 86/53, Dilemma 86/58,
Trophy 83/55, Trauma 82/**83**, Default 80/67, Autarky 78/70, Schooltime 73/57, Portals 70/**40**,
**Slithery 54/60**.

Reading (correlation, not causation: stronger teams lead on everything):
- The opening decides most games; the imitation network's focus on moves is aimed at the right phase.
- The longest dragon matters from ~round 200, earlier than V7.12's queen (round 340).
- Maps differ: unit count is king on Devil/QoS/Dilemma/Trophy; Trauma rewards an early giant (S.2's strength);
  on Slithery unit count barely helps (our 2/14 ranked there: opponents swarm *and* grow a 24-long dragon by r100);
  on Portals an early long dragon is a liability.


## Why the champion (Y.7.12-nn.1) still loses (46 lost ladder games, mostly vs 1900-2000 teams)

Loss types: wiped early 12, outnumbered by r100 11, mid-game war 11, late collapse 10, behind on mass 2; worst map
Trauma (12). Early/mid deaths are now mostly head-ons (trapping was largely fixed by the network), but the head-on
trade is even (our/their head-on deaths: r0-150 1.14, r150-350 1.04, r350+ 0.89; the small surplus is our own
dragons colliding). We lose the war because we have fewer units, not because we fight worse: early growth
(pearl-finding, budding) remains the main lever, then the maze endgame (feeding: 221 feed deaths in 10 late
collapses).

Colab, full v2 data (4M+ samples): plain 72.8%, AWR 0.5 72.7%, AWR 1.0 72.5% (AWR does not add accuracy).
Every network variant is now ~50% head-to-head vs the champion: self-play among network builds has saturated,
only same-time ladder A/B tests can separate them.


## Overnight results (2026-09-28, times IST)

**League screen** (each candidate vs V7.12, S.3, vB.4; 84 maze games each): champion 82.1%, pearl gossip 79.8%,
v3 (current-version data) 82.1%, v1b (more data) 81.0%, joint policy+value 82.1% -> all equal within noise.
**Ladder same-time A/B, champion vs pearl gossip** (6 teams x 5 maze maps, ~06:00): 15/30 vs 16/30 -> no difference
(Shannon 1/5 vs 4/5, Hakimi 3/5 vs 1/5: per-team swings are noise). Pearl gossip raises early eating (+37%
locally) but that did not convert into wins.
**Distillation:** 64-ch teacher 73.6% -> 32-ch student 72.2% (direct training 72.0%): small, not worth a build.
**Rating:** 1664 -> 1689 overnight with Y.7.12-nn.1 active (autoscrims/incoming ranked).
The PC slept ~06:00-14:28, so the on-policy collection failed (no network) and should be rerun.

Conclusion so far: the imitation network is a big step over V7.12 (ladder 24/40 vs 6/40 historical, same-time
16/20 vs 6/20), but every refinement since (more/fresher data, extra inputs, outcome weighting, value head,
distillation, lane sonar, giant hunt, pearl gossip, soft safety) is neutral. Next candidates: v5 (remembered-pearls
input, training now) and fixing the maze endgame (still the main loss mode: Trauma).


## Pushing the ~72% accuracy (2026-09-28 afternoon; one validation set: 10% of v4 games = current bots of 50 teams)

| Technique (source) | Accuracy | Cost in the judge |
|---|---|---|
| single model (v1b/v3/v4/v2/student) | 70.6-70.9% | 1 forward pass |
| test-time mirror averaging (standard TTA) | +0.3-0.4 | 2 passes |
| ensemble of 5 models ("Swarm BC" / ensembles) | 71.4% (+0.5) | 5 passes |
| team conditioning (mixed-expert BC, arXiv 1903.10304) | 71.4% vs 70.5% (+0.9) | none (pick a team style) |
| single top team only (Lux AI 2021 "imitate Toad Brigade") | 67.8% (Vibing++, 148k samples) | none |
| remembered-pearls input (v5) | 70.0% vs 70.5% | none |
| 64-ch network / distillation | 73.5% / student 72.2% | 4x / none |

Reading: the ceiling is information the network cannot see (the demonstrator's memory, sonar and plans), not
capacity or mixed styles; each trick adds <1 point, and +1.4 points (v2) did not change play. Better payoff:
on-policy data (DAgger-style: top teams playing against our bot, rerunning now) and eventually RL fine-tuning.


## Reinforcement learning setup (2026-09-28 afternoon)

- `ml/rl_env.py`: the engine (unswbc EngineModule, WebAssembly) runs a full match in-process and calls Python for
  every dragon turn; a Python agent parses the turn input + known map into the same 16-plane egocentric input as
  the imitation network. No bot processes, no sandbox: ~480 dragon-turns/s per process, a full 500-round game in
  45-65 s, ~10 games/min on 10 processes.
- `ml/rl_policy.py`: legal-move masking (kelp side, occupied neighbour, no reversing) and the split action
  (`SPLIT 2` from length 4). The pure network plays complete games (swarms of 28-45 dragons).
- `ml/rl_train.py`: PPO fine-tuning from the imitation model (HandyRL / AlphaStar recipe): value head as baseline,
  reward = final result +-1 + 0.05 x dragon length gain over 20 rounds, KL penalty to the imitation policy, league
  of frozen snapshots as opponents, greedy evaluation vs the imitation model every 5 iterations.
  Smoke test OK (1 iteration: 35k decisions, PPO update, 10 eval games). Full run `ml/models/rl_run1`
  (log `ml/rl_run1.log`) starts when the CPU is free.
- An RL-improved network exports to C++ unchanged (same architecture; `ml/export_cpp.py`).


## Team-style league (network conditioned on one top team's style; 84 maze games each vs V7.12, S.3, vB.4)

| Build | Average | Trophy | Trauma |
|---|---|---|---|
| champion Y.7.12-nn.1 | 82.1% | 10/12 | 7/12 |
| style Sabotage-d | 79.8% | 9/12 | 5/12 |
| **style Vibing++ (#2 team)** | **86.3%** | **12/12** | 6/12 |
| style calc | 81.0% | 6/12 | 6/12 |

Vibing++ style submitted as Y.7.12.4 (10047). **Same-time ladder A/B vs the champion (6 teams x 5 maze maps):
champion 17/30, Vibing style 16/30** — no difference (per-team swings like Rogo 5/5 vs 3/5 are noise). The league's
+4 points did not transfer to the ladder; champion stays Y.7.12-nn.1.

RL run 1 crashed after iteration 1 (iter 1: 157k learner decisions, vs league 0.42) with a MemoryError: whole games
sent back through the worker pool do not fit in 15 GB. Fixed: workers keep 30% of decisions and return compact
arrays; the run needs restarting.

## Ladder record per build, open vs maze (2026-09-28, last 200 battles; build read from each battle's replay)

The v1 API no longer returns submission ids for battles; `tools/build_record.py` reads botA/botB from one replay
per battle (cached in `ladder/attrib/`).

| Build | Open (all) | Maze (all) | Open ranked | Maze ranked |
|---|---|---|---|---|
| V7.12 (8242) | 46/67 69% | 102/316 32% | 14/24 58% | 19/51 37% |
| **Y.7.12-nn.1 (9285)** | 40/57 70% | **115/216 53%** | 20/30 67% | **39/60 65%** |
| test-v7.17-nn (9258, same code) | - | 24/40 60% | - | - |
| Y.7.12.3 pearl gossip (9357) | 0/6 | 18/44 41% | - | - |
| Y.7.12.4 Vibing style (10047) | - | 9/20 45% | - | - |
| Y.7.12-nn.1-jam (9298) | - | 5/30 17% | - | - |

The network (maze maps only) took the maze record from 32-37% to 53-65%; open maps play identical code (~70%).
The unranked rows mix in deliberate tests against stronger teams, so compare within a column.

## RL runs 2-5 (2026-09-28)

- Run 4 (v1b init, per-dragon reward, 4 workers): greedy vs imitation 0.40 (iter 5), 0.30 (iter 10), 0.50 (iter 15,
  resumed run) over 10 games each: no gain yet, within noise. An orphaned copy of the run survived a session
  restart and a second copy exhausted RAM (crash); the workers now record only the learner's kept decisions while
  playing (~0.5 GB per worker instead of ~1.5 GB) and the trainer pauses below 3 GB free (`--min-free-gb`).
- **Run 5** (`ml/models/rl_run5`, log `ml/rl_run5.log`): generals.io recipe (arXiv 2507.06825: BC on top replays,
  then PPO self-play; team shaping potential took self-play 68.8% -> 71.9%). Adds `--team-coef 1.0`: reward
  += change over 20 rounds of the team standing phi = 0.5 log(units ratio) + 0.5 log(total length ratio), each
  normalised by log 8 to [-1, 1] (the result at the end of the game). Opponents: half imitation, half one of the 3
  latest snapshots. Eval: 20 greedy games (every map twice, both sides) every 10 iterations.
- Colab `rl_colab_fix` (v4 init, per-dragon reward, 6 workers): snapshots rl_0005, rl_0010 so far.

Ideas from the literature not yet tried: UPGO / TD(lambda) targets instead of Monte-Carlo returns (Lux 2021 1st,
Hungry Geese); shaped reward first, then anneal to win/loss only (Lux 2021); 180-degree rotation TTA at inference;
piKL view of our bot (heuristic score + wNN log p = KL-regularised choice; DiL-piKL samples lambda per game);
SPRT (fishtest) to stop A/B tests early instead of fixed game counts.
- Eval sanity check: the imitation model vs itself under the same eval protocol = 10/20, so the eval is fair.
  **Run 5 is worse than imitation: 5/20 at iterations 10 and 20 (10/40, p ~ 0.001).** With 6 games per update
  (the laptop's throughput) the PPO signal is too noisy and the finely tuned imitation policy drifts (KL only
  0.02-0.04, but greedy argmax flips at near-ties). The network has no dropout/batch-norm (no train/eval mismatch).
- **Run 6** (`ml/models/rl_run6`): conservative updates: KL weight 1.0 (was 0.2), lr 3e-5 (was 1e-4), 12 games per
  update, team reward 1.0, 20-game eval every 5 iterations. Stop rule: below 0.40 at iteration 15 -> RL at laptop
  scale does not pay; the CPU goes back to imitation data (DAgger-style on-policy games) instead.
- Run 6, iteration 5: 9/20 (0.45) vs imitation: the stronger KL anchor stopped the drift (run 5 was 5/20).

## Filtered self-imitation (SIL / ReST) pipeline (2026-09-28)

Cheap-RL survey: search-based improvement (Gumbel AlphaZero, expert iteration) needs mid-game state branching,
which the in-process engine cannot do (it runs a game start to finish); SPSA tuning of the bot needs 30k-100k
games. What fits: filtered self-imitation (arXiv 1806.05635; offline fictitious self-play 2403.00841) with
RLPD-style 50/50 batches of new and prior data (2302.02948), paired seeds for variance reduction.

- `ml/selfplay_collect.py`: both teams play the imitation network sampling at temperature 1; every game is saved
  as a real engine replay (`EngineModule.replay`) and indexed with the winner as "side", so `build_dataset.py`
  extracts the winning team's decisions with exact features (the environment only approximates body order).
  One game gives ~11k samples.
- `ml/train.py`: `--data` takes several folders (`--max-samples` per folder -> 50/50 mixes), `--init` fine-tunes
  from a checkpoint.
- Collection 1: 300 games from v1b, 4 workers, `ladder/selfplay/` (log `ml/selfplay1.log`).
- Collection 1 stopped by a session restart at 120 games (collector leaked memory: 7 -> 3 GB free; fixed with
  `maxtasksperchild=4`); resumed for 180 more.
- **Kaggle as a second offload platform** (CLI only, no browser): token in `~/.kaggle/access_token` (user
  kumaryash1134). Code uploaded as private dataset `kumaryash1134/vcode01` (`code.tar`: ml/*.py, tools/replay.py,
  maps, policy_v1b.pt); private script kernels `sp-run-1`, `sp-run-2` run `selfplay_collect.py` (400 games each,
  all CPUs) into `/kaggle/working/selfplay`; fetch with `kaggle kernels output kumaryash1134/sp-run-N -p <dir>`.
  Game ids restart at 1e9 in every run: renumber when merging.
- Colab worker v3 (`ml/colab_worker.ipynb`, copy in Drive): the laptop stops a job by creating
  `jobs/STOP_<name>`; the old RL job was terminated (8 evals averaged 0.37 vs imitation).

## Technique ledger (keep current; read before starting a new ML/RL experiment)

| Technique | Source | Result here |
|---|---|---|
| Imitation of top teams, egocentric rotated planes, mirror augmentation | Hungry Geese / Lux winners | **the win**: maze 32-37% -> 53-65% on the ladder |
| More data / newer-season data / latest-submission filter (v1b, v2-v5) | - | 71-73% offline ceiling, league equal |
| TTA, ensembles, distillation (teacher 64ch -> student) | Lux 2021 (180-degree TTA) | <= +0.5% offline, not worth the CPU |
| Team conditioning (one team's style) | - | league +4 points, ladder equal (Y.7.12.4) |
| Offline AWR, offline Q, joint policy+value | AWAC / CRR | neutral |
| Memory plane (remembered pearls), previous-turn scalars | generals.io memory planes | neutral |
| PPO self-play, per-dragon reward, KL 0.2, lr 1e-4 | HandyRL / AlphaStar | worse than imitation (0.25-0.40 greedy), local and Colab |
| + team-standing reward (units, length ratios) | generals.io PBRS | run 5: 0.25, no better |
| + KL 1.0, lr 3e-5, 12 games/update | - | run 6: 0.45 at iteration 5 (drift stopped); killed by low memory |
| Filtered self-imitation (winners' decisions, 50/50 with top-team data) | SIL, ReST, RLPD symmetric sampling | round 1 training (`ml/models/sil_r1.pt`) |

Known quirks to allow for (do not stop runs too early):
- **PPO from an imitation policy dips first, then recovers** (PIRLNav, arXiv 2301.07302): a fresh critic gives
  bad advantages. Fix: critic warm-up (value head only, policy frozen) then a policy lr ramp:
  `rl_train.py --critic-warmup N --lr-ramp M`. The Colab run showed the dip: 0.6 -> 0.2 -> 0.4-0.5.
- **Plateaus then sudden gains** (grokking; self-play phase transitions): long flat stretches can precede a jump;
  weight decay x lr sets the delay. Judge a run by its trend over >= 60 eval games, not one eval.
- **Self-play stagnation / strategy cycling**: a frozen teacher KL and a pool of past snapshots prevent it (Lux 2021);
  the imitation model stays in the pool.
- **Eval noise**: 20 games has +-11% standard error; the imitation model vs itself = 10/20. Use paired seeds and
  SPRT-style stopping for decisions.
- **Offline gains do not transfer**: league +4 did not show on the ladder (Vibing style); only same-time ladder
  A/B decides.

Still untried: UPGO / TD(lambda) targets (Lux 2021), shaped-then-sparse reward annealing, DiL-piKL (sample wNN per
game), SPRT for A/B, critic warm-up run.
