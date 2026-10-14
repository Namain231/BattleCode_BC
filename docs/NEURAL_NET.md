# Neural networks: imitation, refreshes and validation

Explain the replay data, input layout and networks used by the Loong bot.
Preserve measured training, parity, CPU and play results, including failed experiments.
Provide reproducible pipeline commands and the checks needed before trusting a new net.

## Contents

- [Rules and evidence](#rules-and-evidence)
- [Network timeline](#network-timeline)
- [Replay data and shards](#replay-data-and-shards)
- [Inputs and architecture](#inputs-and-architecture)
- [Plane 8 and seen terrain](#plane-8-and-seen-terrain)
- [How the bot uses the net](#how-the-bot-uses-the-net)
- [Training and failed refinements](#training-and-failed-refinements)
- [Refreshes and drift](#refreshes-and-drift)
- [MLP student](#mlp-student)
- [Parity and CPU](#parity-and-cpu)
- [Runbook](#runbook)
- [Operational pitfalls](#operational-pitfalls)
- [Decisions to retain](#decisions-to-retain)

## Rules and evidence

**OLD rules, before 2026-10-01:** round-500 results used the longest living dragon tiebreak. All September results below belong to that regime.
**NEW rules, from 2026-10-01:** queen length decides at round 500; dead queen = 0; then longest dragon, then total length. Free steps = `ceil(L/4)`.
Old play numbers and parameters require revalidation; the old elected keeper is not the fixed queen (id 0/1).
Where sources disagree, this document prefers later dated evidence: the October 7–8 topic log supersedes the Kaggle preflight report, and the MLP fix-round-2 report supersedes the initial student figures.
Logs were searched only for missing neural-network facts. Figures on different holdouts are not directly comparable.
The October 14 cleanup deleted F: training/replay scratch, four Kaggle datasets and ten bc-v6 kernels; historical artifact paths below are provenance, not guarantees that files remain.

## Network timeline

| Date / rules | Net / data | Held-out move accuracy | Play result / decision |
|---|---|---|---|
| September 2026 / OLD | Pilot: 171 games, 1.13M decisions; walls incorrectly scaled | 71.5%; forward baseline 42.2% | Pipeline bug; not a reliable strength estimate |
| 2026-09-28 / OLD | v1: 356 winning top-12 games, 2.34M decisions; training subset 1.1M | 70.6%; forward 45.8% | Y.7.12-nn.1: 24/40 ladder; same-time 16/20 versus V7.12 6/20; kept |
| 2026-09-28 / OLD | v1b: more data, original inputs; v2: 679 games, previous-turn inputs/AWR | 71.8% / 72.0%; full-v2 plain 72.8% | v1b 22/42; v2 26/56 versus champion: no improvement |
| 2026-09-28 / OLD | v3: current-version data, 585 games; v4 validation: current bots of 50 teams | v3 70.5%; comparable single nets 70.6–70.9% | v3 league 82.1%, champion 82.1% |
| 2026-09-28 / OLD | Team-conditioned Vibing++ style, mixed-team training | 71.4% versus 70.5%; single-team-only 67.8% on 148k samples | League 86.3% versus 82.1%; ladder 16/30 versus champion 17/30: neutral |
| 2026-10-02 / NEW | v6 pipeline smoke: 22 games, 286,729 samples | 60.2%, queen 64%, after 5 epochs, 25% game holdout | Pipeline proof only; 22/22 body reconstructions without mismatches |
| 2026-10-03 / NEW | k_fullft: 1,513 games, full terrain; four additional epochs from k_full | 70.35% (+0.17 pp); queen 72.6% (+1.0 pp) | Included in Sv5.2; composite bot 54.5/98 versus Y9_6, CPU 65.2M; gain not attributable to net alone |
| 2026-10-04 / NEW | Recent refresh: 600 wins, 21 teams, 17 maps, 8,893,206 samples | Existing k_fullft 68.58% on newest-60 holdout versus 70.35% old validation | Both refresh training lanes failed; existing checkpoint selected; no demonstrated refresh gain |
| 2026-10-06 / NEW | MLP initial one-epoch student, old + recent data | 67.98% versus teacher 68.58% | Initial trial 47/98; later reported safety 50/98 versus 59/98: reject |
| 2026-10-06, final fix-round-2 / NEW | MLP eight epochs: 21,644,077 old + 8,893,206 new samples, globally excluding holdout | Best epoch 7: 68.628% versus 68.579% teacher | 50/98 versus 59/98, −9.18 pp: FAIL; unpromoted |
| 2026-10-07–08 / NEW | Kaggle new2: prior 600 + 1,430 eligible games; old data reused; four epochs, recent roots x2 | Newest-143 holdout: 69.85% → 70.66% (+0.81 pp) | viper_nv30k 52/98 versus Nv30 42/98; provisional, fresh confirmation outcome unverified |

OLD ladder aggregate: V7.12 maze 102/316 (32%), ranked 19/51 (37%); Y.7.12-nn.1 maze 115/216 (53%), ranked 39/60 (65%).
Open maps used identical rule code: 46/67 (69%) versus 40/57 (70%). Mixed-strength unranked records should be compared within columns.
OLD maze-only local screen: wNN 2 gave 74W/9L/1D over 84; wNN 3 gave 70/84. Gate: 70% versus V7.12, 75% versus V7.5.
The first net's submitted names were test-v7.17-nn (9258), then Y.7.12-nn.1 (9285), identical code.

## Replay data and shards

`tools/scout.py` downloads public top-team games; `tools/latest_only.py` filters to each team's newest submission.
The new-rules scout also used battle-series sweeps (`ladder/scout_v6/sweep.py`, minimum Elo 1950); refresh4 used Elo ≥2000.
The actual k_fullft training boundary was the 1,513 game IDs in `ladder/scout_v6/shards_145/manifest.json`; extra `manifest_all.csv` rows do not prove training membership.
Filter new-rules data by battle date at/after the switch; old scouting's `recent` list had no date cutoff. Do not silently mix old labels with the new sprint economy.
Use winning top-team sides; exclude our team 98. Winners-only filtering removes losing games, not individual bad moves.

Public replays preserve terrain edges, MAP_NAME, dragon IDs/bodies, multi-step declared directions, split sizes, sonar values and hit kinds.
They zero TILE bed gaps and strip `pearlCountdown`, CPU and indicators; new public botA/botB strings are empty. Determine side from battle metadata.
Local replays retain countdown draws and gaps. Pearl spawns alone cannot recover exact gaps: occupied beds censor intervals (Autarky fountains showed median 8, maximum 142).
The old builder used full true bodies; v6 estimates other dragons' lengths from visible segments, matching the bot rather than leaking hidden tails.

| Measured NEW data fact | Consequence |
|---|---|
| 79 winning games, about 1.07M winner decisions; 13.5k decisions/game average | Budget by game size; large maps produced 20–26k decisions/game |
| 61% of winner decisions at r≥200 | Remove old `keep_late=0.35` downsampling |
| Queen decisions about 1.2%; 58/79 winning queens died, 22 by r10 | Queen conditioning is sparse; proposed queen loss weight x3 |
| Multi-step moves about 0.9%; unused free allowance at L≥5: drones 86%, queens 90% | Unused free steps are not uniquely our weakness; STOP targets dominate |
| 306 wins: 164 elimination; 142 reached r500; both queens dead in 118 | Queen tiebreak decided 24/306 (8%), not most sampled games |
| v6 smoke: 97–120 compressed bytes/sample; README about 120 | Stream shards instead of allocating dense arrays for the full dataset |

Use `tools/replay_lite.decode_lite`, omitting sonar when unnecessary; `replay.load` creates `.pkl` caches and roughly doubles replay storage.
Builders reconstruct growth, tail movement, portals and each recorded `dragonUpdate`; round-0 no-op updates must be ignored.
Continuation crops move and rotate with the simulated head, but retain the turn-start observation: dragons receive no fresh intermediate vision.
Stop emitting continuation states after death; reconcile final head/tail against authoritative updates.
The design proposed hash dedupe capped at four copies, no team above 30%, queen x3 and leave-team/map-out diagnostics; these proposals are not evidence every final run enforced them.
Committed manifests and validation-game identities, rather than CSV row totals or progress counters, determine completeness.

## Inputs and architecture

Inputs are egocentric 15×15 crops, head at (7,7), rotated so facing is up; vision is 7×7. Mirror augmentation swaps left/right channels and labels.
OLD policy: 16 byte planes + three broadcast scalars, three 32-channel convolutions, FC 64, six logits, about 125k weights.
Forward: padded 3×3 conv/ReLU; 2×2 average pooling (drops row/column 14); conv/ReLU; residual conv/ReLU; flattened 1,568→64; output with scalars.
NEW v6 keeps that structure with 19 planes + six scalars (25 conv input channels), seven logits.

| v6 plane | Meaning |
|---|---|
| 0–3 | Kelp edges up/right/down/left |
| 4–7 | Portal edges in the same relative directions |
| 8 | Reserved bed-rate plane, forced zero |
| 9 | Turn-start view mask, 255 in visible cells |
| 10 | Pearls in view |
| 11 | Own body, remaining occupancy `(L−k)*16` |
| 12–13 | Ally/enemy body occupancy using visible-chain estimate, +2 when chain leaves view |
| 14–15 | Ally/enemy estimated head length ×8 |
| 16 | Queen view: own head/body 255/128 (self omitted), enemy head/body 255/160; enemy last-seen memory ≤150, decay exp(−age/40), age≤100 |
| 17 | Enemy free-step reach: portal-aware BFS to ceil(estLen/4); max `255−60(d−1)`, head=255 |
| 18 | Reserved zero; terrain-mask slot was a proposal |

Scalars: `len/32`, `round/500`, `units/64`, `is_queen`, `ceil(L/4)/8`, `steps_taken/4`.
Outputs: `[forward, right, back, left, split, other, STOP]`. At turn start mask STOP; in continuation states mask split/other.
Enemy-queen memory belongs to each dragon's own sightings; split children start blank. Hidden sonar belief is not a replay-reconstructible input.
Full terrain and `--terrain seen` are distinct builder regimes; the latter supports unseen-map data.

## Plane 8 and seen terrain

OLD plane 8 was `min(255, int(2040/(lo+hi)))`, a fast-bed marker. Public replay zeroing created a potential train/inference mismatch.
Table filling is possible on known maps, but gives complete information at birth while unseen-map dragons discover beds gradually; it can fingerprint maps (2–5 distinct values/map).
The critic recommended seen-so-far rates plus a known mask; the implemented v6 decision was simpler: plane 8 zero in both training and inference.
No public countdowns means exact online-gap memory cannot be reconstructed from public games.

| Shipped-net sensitivity, 2026-10-02; 49,584 local states | Six-class argmax flips versus table | Mean KL |
|---|---:|---:|
| Zero | 3.59% (generated 4.08%) | 0.0036 |
| learnGap trusted mask, table value | 1.87% | 0.0012 |
| learnGap estimated value | 2.11% | 0.0013 |
| First-sight reveal | 0.78% | 0.0002 |

Table and zero both agreed with played moves 74.2%; this was our bots' local data, not a top-team held-out test or win test.
Zero exceeded the proposed 2% irrelevance threshold, but the small near-tie changes gave no measured accuracy loss. vB19 already supplied zero on unseen maps.
Trusted fast-bed coverage: Trauma 62%, generated archipelago 32%; first sight 66%/54%. Adjacent beds shared gap classes 92% (29,186/31,618).
First-sight estimation, cluster pooling, online symmetry and sample means were researched alternatives, not validated net improvements.
Random independent dropout does not mimic path-dependent missing terrain; use structured per-dragon seen memory if implementing a mask.
Claims that stored tables disagree in about half of some ladder games were comments without supporting measurements: **unverified**.

## How the bot uses the net

The net supplies a prior inside the rule scorer: `score += wNN * log p(first_step)`; safety classes take precedence.
The rule bot still chooses candidates, splits, feeding and sprint paths. Exporting seven logits does not prove STOP/split outputs are used in play.
The old hybrid used wNN 2 for drones, 0.4 for the queen, and disabled the net on bigFeed maps Portals/Slithery/Schooltime.
It does not run the multi-dragon net-played rollout search described in calc's writeup; that writeup concerned OLD rules and its claims were not independently reproduced.

| NEW-rules wNN sweep, 2026-10-02 | 0 | 1 | 2 | 4 | 8 |
|---|---:|---:|---:|---:|---:|
| Wins/40 versus y7_12_49, live maps, seeds 1/2 | 11 | 20 | 23 | 17 | 20 |

Queen weight remained 0.4. No failures/timeouts; CPU maxima were absent from logs.
Zero lost 12 wins versus wNN 2; the source concluded removing the net was worse. Values 1/2/4/8 were not separated at roughly 8 pp standard error.
Nominal best wNN 2 is not proof of a universal optimum; re-sweep in the actual parent build after changing weights.

## Training and failed refinements

| OLD experiment | Offline / cost evidence | Play / decision |
|---|---|---|
| 32/48/64-channel Colab sweep, 2.34M data | 70.4/71.1/71.3%; largest about 4× compute | Capacity saturated; larger was not justified |
| 64-channel teacher → 32-channel student | 73.6% →72.2%; direct student 72.0% | Small gain; not worth a build |
| Mirror TTA / five-model ensemble | +0.3–0.4 pp / +0.5 pp; 2/5 passes | CPU cost not justified |
| Team conditioning | Vibing league +4.2 pp; Sabotage-d 79.8%, calc 81.0% | Vibing Y.7.12.4 (10047) ladder 16/30 versus 17/30: retain original |
| Remembered pearls v5 | 70.0% versus 70.5% | Neutral; distinct from static bed memory |
| AWR 0.5/1.0 | 72.7/72.5%, plain 72.8% | No accuracy benefit |
| Joint policy/value | Policy 71.9%, value correlation 0.35 | 19/42 and 19/41 versus champion: neutral |
| PPO per-dragon/team reward | Typical greedy scores 0.25–0.40 versus imitation | Worse; run 5 5/20 twice (10/40, reported p≈0.001) |
| PPO stronger anchor | KL 1.0, lr 3e−5, 12 games/update versus KL .2, lr 1e−4 | Run 6 9/20 at iteration 5; drift reduced, later killed by memory |
| Filtered self-imitation | Winning moves mixed 50/50 with top-team data; about 11k samples/game | Round 1 17/28 maze; later round outcome unverified |

PPO near-tie argmax changes harmed play even with KL only 0.02–0.04. No dropout/batch-norm mismatch explained it.
Colab's eight evaluations averaged 0.37 versus imitation. Critic warm-up and LR ramp were added, but no successful later result was established.
Self-play memory fixes: workers returned only 30% compact decisions, then retained only learner decisions; `maxtasksperchild=4` stopped collector leakage.
The old throughput was about 480 dragon-turns/s/process, 45–65s/game; six to twelve games/update were too noisy for reliable PPO improvement.
Colab worker `ml/colab_worker.ipynb` used job files and `STOP_<name>`; Kaggle `sp-run-*` collected real engine replays. Renumber game IDs starting at 1e9 before merging separate runs.

## Refreshes and drift

The first refresh expanded 358 to 600 wins (21 teams, 17 maps), 635,883,281 replay bytes; shards contained 8,893,206 samples.
Newest 60 games were sealed for validation; teacher accuracy fell from 70.35% old validation to 68.58% recent validation, documenting dataset/meta drift.
Fine-tune and scratch Kaggle lanes both exited 1; choosing/exporting existing k_fullft did not create a newly trained improvement.
Refresh4 collected 1,448 games from 42 teams, all 17 maps, dated October 5 01:49 UTC to October 6 23:20 UTC.
Exactly 18 involved team 98 and were deliberately excluded: 1,430 eligible games, 167 new2 shards, about 20.8M samples. An all-CSV completeness check incorrectly blocked this eligible-only build.
Local GTX 1650 refresh4 stopped before training with `[Errno 22] Invalid argument`; its safeguards passed fault injection, but that did not prove successful training.
Later Kaggle new2 combined the 600-game and 1,430-game recent roots (3.4 GB staged), reused old shards and initialized from k_fullft.
The T4 run took 107 minutes: four epochs, reported 30M sample corpus with old x1/new x2, newest-143-game holdout 69.85%→70.66%.
`viper_nv30k` changed only Nv30's `policy_weights_v6.hpp`. Screen: 52/98 versus Nv30 control 42/98; queen deaths 88 versus 90, median death round 179.5 versus 199.
Most gain was Islands (8 wins versus 2). Other variants also beat the low control (48/98, 51.5/98); regression to the mean was plausible. Fresh-seed confirmation result and isolated ladder gain are **unverified**.

## MLP student

`viper_y96qm` copied `viper_y96qg`; `Params::nnKind=1` selects MLP, 0 restores conv. Bot logic, nnInput6 and wNN were preserved.
Architecture: same 19×15×15 + six scalars, hidden 256/128, seven logits; cross-entropy plus teacher KL at temperature 2.
Sparse export retained 3,831 inputs, omitted zero planes 8/18, used int32 coefficients ±16,777,215, float scales and double accumulation.

| Measure | Initial October 6 entry | Final fix-round-2 report |
|---|---|---|
| Student / teacher holdout | 67.98% / 68.58% | 68.628% / 68.579%, epoch 7 of 8 |
| MLP / conv CPU points per call | 1.25M /21.1M, about 17× | 1.659M mean, 2.482M sampled max /21.137M, 12.74× mean |
| Package | 3.88 MB | 3,911,843 bytes, below 4 MB cap |
| Native parity | PASS | 1,600/1,600 argmax; max logit error 0.000671387 |
| Safety | Reported 50/98 versus 59/98 | Same failed acceptance result; historical control provenance unavailable |

Holdout: newest 60 games, 582,515 states, zero teacher-training overlap. Sampled CPU: 64 real states from first two recent shards, not a universal maximum.
Class student/teacher accuracy (%): forward 77.59/75.91, side 61.49/62.25, back 8.77/43.97, split 56.17/55.31, other 0.33/0.79, STOP 82.99/84.16.
Safety by map: around_unsw 7/14, australia 10/14, islands 11/14, maze 9/14, stripes 5/14, tower_defense 1/14, weakhold 7/14.
Queen deaths student/control 91/98 versus 87/98; units@100 mean 25.643 versus 25.296, median 21 versus 22.
Whole-game peaks: Australia 57.361M, Around UNSW 57.616M. Faster inference and slightly better final top-1 did not prevent the −9.18 pp safety result.
Final decision: drop/unpromoted; supervisor retired. Future comparisons require fresh sealed paired control, not reconstructed cached provenance.

## Parity and CPU

OLD exported C++ self-test matched torch; bot versus builder top move 560/581 (96.4%), median probability gap 0.01.
NEW v6 smoke forward parity: 1,600 states, 100% argmax, max error 2.3e−5; plane-8 conv1 weights max .0665 versus initialization bound .0667.
Input parity, Trauma seed 1: seat A 7,330 states, 90.7% all planes equal; seat B 9,423, 96.2%. Planes 8–17 matched ≥99.9%.
Terrain mismatches were 8.7%/3.8%; fell from 29% at birth to 5% after age 50. Seen mode matched only 282 mismatching states: known-map identification was hybrid, not uniformly full or seen.
Eight late nonterrain mismatches remained unexplained. Scalars were reviewed, not hashed; continuation/steps_taken>0 was not tested. The source's partial PASS does not close terrain parity.
New2 forward argmax was 100% on 1,600 states, but max error 0.0027 exceeded script threshold 0.001 (old net .00022): cause unresolved; do not call this full parity PASS.
CPU: original convolution implementation 44M/call, optimized OLD net about 18M, v6 conv measured 21.137M. Dragon-turn limit 100M; target peaks about 65M.
Native forward parity, input reconstruction parity, sampled per-call cost and whole-game CPU peak are separate checks.
MLP repaired checks reject >3M, zero, negative, NaN/infinity costs; native argument/input/output-open failures return nonzero.

## Runbook

Run from the repo root. Commands below are retained source commands; rebuilding deleted data is required. `PY310` means `C:/Users/sohan/AppData/Local/Programs/Python/Python310/python.exe`.
Credentials must already be available in the environment; no credential values belong in datasets, headers or reports. Placeholder arguments require real paths/IDs.

```bash
# Scout and latest-submission filter (probe and larger scout from nn_plan).
python tools/scout.py --top 3 --per-team 2 --out ladder/il_probe
python tools/scout.py --top 16 --per-team 60 --min-game-id <G0> --out ladder/il_new
python tools/latest_only.py ladder/il_new/index.json --out ladder/il_new/latest_index.json --min-games 4
# Streaming v6 build and validation; refresh4's eligible-game manifest.
uv run --python 3.11 --with unswbc --with numpy python ml/v6/build_dataset_v6.py --workers 2 --out ladder/scout_v6/shards
uv run --python 3.11 --with numpy python ml/v6/test_builder.py ladder/scout_v6/shards
uv run --python 3.11 --with unswbc --with numpy python ml/v6/build_dataset_v6.py --index ladder/scout_v6/manifest_new2.csv --out ladder/scout_v6/shards_new2 --workers 2
# Local CUDA training, export and torch/native parity (README).
PY310 ml/v6/train_v6.py --data ladder/scout_v6/shards --out ladder/scout_v6/train_out/v6.pt --epochs 8 --val-frac 0.1 --amp
PY310 ml/export_cpp.py v6.pt OUTDIR/policy_weights_v6.hpp --data ladder/scout_v6/shards
PY310 ml/v6/parity.py v6.pt ladder/scout_v6/shards OUTDIR
# Private Kaggle uploads/kernel/fetch (smoke's verified interfaces).
bash tools/kaggle_train/push_dataset.sh DATASET_DIR
bash tools/kaggle_train/push_dataset.sh DATASET_DIR version 'Updated shards'
bash tools/kaggle_train/push_kernel.sh KERNEL_DIR 43200 NvidiaTeslaT4
bash tools/kaggle_train/fetch_output.sh sohansridutta/KERNEL OUTPUT_DIR 10800
# Integrated v6 script; repeat kernel without uploading shared mounts again.
bash tools/kaggle_train/run_v6.sh ladder/scout_v6/shards ladder/scout_v6/train_out/kaggle 8
TAG=-second SKIP_UPLOAD=1 bash tools/kaggle_train/run_v6.sh ladder/scout_v6/shards ladder/scout_v6/train_out/kaggle_second 8
# Build and input parity tool (bot_parity arguments depend on debug replay).
python tools/buildwasm.py BOT_DIR
# Paired outcomes after separate same-seed candidate/control panels.
python -m rulemine.evalpair CAND_OUT CTRL_OUT
```

Resolve README's `v6.pt` shorthand to the checkpoint actually produced; it is not automatically copied to the repo root.
`--min-game-id` was a planned scout extension in nn_plan; confirm `--help` before relying on it. Date-filter manifests independently.
Recent training supports repeated `--extra-data DIR` (visit recent shards twice/epoch), `--val-data NEW_DIR` and `--val-games holdout_games.json`; held-out IDs are excluded from every training directory.
Kaggle mixed-run settings: `DTAG=-new OLD_DATASET=bc-v6-shards OLD_MANIFEST=... VAL_GAMES=... INIT=... CREATE_SHARDS=1`; `FETCH_TIMEOUT` and `KERNEL_TIMEOUT` override limits.
`run_v6.sh` handles one recent root; the two-root new2 run required isolated staging/adaptation and `shard_manifest.py` in the package. Do not present the one-root script as a complete two-root recipe.

```powershell
# Exact final MLP commands from its report.
C:/Users/sohan/AppData/Local/Programs/Python/Python310/python.exe -B ml/v6/train_mlp_student.py --out F:\BattleCode_data\ladder\scout_v6\train_out\mlp_student_fix2 --epochs 8 --width 256 --batch 512
C:/Users/sohan/AppData/Local/Programs/Python/Python310/python.exe -B ml/v6/parity_mlp_student.py --out F:\BattleCode_data\ladder\scout_v6\train_out\mlp_student_fix2
uv run --python 3.11 --with unswbc python -B ml/v6/bench_mlp_student.py --out F:\BattleCode_data\ladder\scout_v6\train_out\mlp_student_fix2
uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_y96qm baselines/Y9_6 out/mlp_safety --maps around_unsw,australia,islands,maze,stripes,tower_defense,weakhold --seeds 3,4,5,6,7,8,9 -j 2
uv run --python 3.11 --with unswbc python tools/panel_queen.py out/mlp_safety out/p2_viper_y96qg
uv run --python 3.11 --with unswbc python tools/opening_census.py --dir out/mlp_safety
```

These are historical reproduction commands, not an instruction to promote the failed student; its candidate directory was removed in cleanup.
For acceptance, seal both builds and engine/map/seed/side provenance before play, measure queen survival and units@100, then compare against a fresh control. Keep PowerShell and in-WSL panel paths separate.

## Operational pitfalls

| Failure | Evidence / corrective rule |
|---|---|
| GPU requested but CPU granted | October 2 smoke: three versions, torch 2.10+cpu, CUDA false, no nvidia-smi; COMPLETE did not mean training succeeded. Later phone verification was followed by a successful 2×T4 CUDA probe and 287k-sample three-epoch/export run in 41s |
| Kaggle quota disagreement | Smoke CLI said 30 GPU hours; direct API said 6. Exact account allowance unresolved; metadata is not resource proof |
| Windows dataset path | `datasets create -p kaggle_smoke/dataset` broke upload-state paths; cd into dataset and use `-p .` |
| Double upload | Reuse mounted datasets with `SKIP_UPLOAD=1` for another kernel, or `SKIP_SHARDS=1` when only code/init changes; a specific historical double-upload incident is unverified |
| 403 responses | Cause and successful remedy not established in listed neural sources: unverified. Do not interpret 403 as dataset-not-found; upsert must distinguish 404 from auth/other errors |
| TLS/fetch flakes | Retry `Failed to fetch`, `invalid peer certificate`, `Request failed after` up to three times; immediate retries often succeed. A seen-terrain training run needed this retry |
| Fetch timeout | Standalone fetch default 2,400s is shorter than the 107-minute run; integrated script uses 10,800s. Timeout returns 124, not a training failure verdict |
| Nested shard directories | Default uploader `-r skip` accepts top-level files; new2 used `-r zip` to preserve both subfolders. Archives unpack on Kaggle; verify resulting mount layout |
| Title collision | Smoke kernel HTTP 409 came from a title already used by a dataset; choose a distinct kernel title/slug |
| Missing code dependency | Existing run_v6 package omitted `shard_manifest.py`; mixed-data adaptation must include it and verify manifests/holdout/init hashes |
| RAM / disk | First refresh guard stopped at C: 2.70 GiB; MLP reduced workers 4→2 when free RAM reached 650MB. Use memory/disk guards before heavy stages; cap CSV/learning fan-out at four |
| Junction imports | `Path(__file__).resolve()` on ladder scripts points to F:, losing C: repo imports; use repository working directory |
| Stale sandbox cache | unswbc cache keys main.cpp only; touch it after header edits, or use tools/buildwasm.py, which hashes all sources |

## Decisions to retain

Offline accuracy is a sanity check, never a promotion criterion. The first imitation net helped; larger nets, more data, team styles and faster students repeatedly showed that later offline gains need not improve play.
Use held-out games, explicit newest-game validation, global exclusion across all roots, and separate per-class/queen/phase metrics. Rare back moves exposed a large MLP regression hidden by aggregate top-1.
Require both input and forward parity, measured whole-game CPU, and fresh paired play. Do not waive documented terrain or numeric mismatches merely because argmax agrees on a sample.
Keep known-map and unseen-map results separate. Local fixed opponents and repeatedly reused panels can favor candidates; only same-time ladder A/B establishes ladder improvement.
The new2 52/98 screen was encouraging but insufficient to isolate a durable net gain; the MLP safety failure remains the rejection decision despite its speed and accuracy.

Sources consolidated: tools/tasks/docs_merge/COMMON.md; research_new_meta/nn_plan.md; research_new_meta/dataset_v6_and_bceval.md; research_new_meta/plane8_opt1_review.md; research_new_meta/plane8_sensitivity.md; research_new_meta/v6_parity_result.md; research_new_meta/kaggle_smoke_result.md; research_new_meta/wnn_sweep_results.md; ml/results.md; ml/v6/README.md; guide/5_the_neural_network.md; reports/mlp_student_report.md; reports/nn_refresh4_report.md; reports/kaggle_train_new2_report.md; AGENT_LOG.md (topic-only matches); tools/kaggle_train/run_v6.sh; tools/kaggle_train/push_dataset.sh; tools/kaggle_train/fetch_output.sh; README.md; insights.md (top banner). Originals remain in git history.
