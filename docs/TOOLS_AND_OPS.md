# Tools and operations

Run local matches, inspect replays, and compare a candidate with the ladder control.
Use the guarded local farm and optional private Kaggle workflows without exhausting this machine.
Apply reproducible verification and independent critique before accepting a change.

## Contents

- [Authority and rules](#authority-and-rules)
- [Setup and first match](#setup-and-first-match)
- [Tool index](#tool-index)
- [Local panels and acceptance](#local-panels-and-acceptance)
- [Ladder procedures](#ladder-procedures)
- [Paired opening farm](#paired-opening-farm)
- [Kaggle training and remote farm](#kaggle-training-and-remote-farm)
- [Agent workflow](#agent-workflow)
- [Machine safety and failure fixes](#machine-safety-and-failure-fixes)

## Authority and rules

Newest dated instructions prevail: NEXT_STEPS.md's October 7 control and October 6 stop decisions supersede older README, guide and AGENTS.md defaults; the October 8 A/B record supplies later ladder evidence; the October 14 cleanup supersedes assumptions about artifact availability.

| Scope | Rule or decision |
|---|---|
| OLD rules, before 2026-10-01 | Round-500 tiebreak: longest living dragon, then total length. Old queen references describe a strategy, not the new fixed queen. |
| NEW rules, from 2026-10-01 | At round 500 compare queen length (dead queen = 0), then longest dragon, then total length; free steps = ceil(L/4). |
| Queen identity | Fixed lowest initial friendly ID, normally 0 or 1, resolved from initial team order. |
| Local control, October 7 | baselines/Nv30, locked Nv3.0 submission 18983; replaces Y9_6 and Sv5.3 as the local yardstick. |
| Active ladder control | Query the server before every test; teammates may change it. October 8 recorded Nv3.5, 20500. Neither historical ID establishes today's active slot. |
| Active-slot restriction | October 7: do not switch the active submission without the user; ladder A/B requires approval and restores the recorded control. |
| Stopped work, October 6 | Do not restart league_build, farm_scale or param_search. Their tooling remains documented for authorized future use. |
| Evidence | Local percentages screen regressions; ladder evidence decides promotion. Frozen baselines are never edited. |

OLD-rule results are historical, not current thresholds calibrated to the new game. The old gate used 40 champion games at >=55% and 20 V7.5 games at >=50%, on 10 maps and both sides. V7.12's old maze panel was 23/28 versus V7.5's 14/28; these do not establish current strength.

## Availability after cleanup (2026-10-14)

The tournament ended. Cleanup removed 53 experimental bot directories, league/, maps_gen/, replays/, old maps, F: scratch (41 GB including ladder replays/shards), tmp, uv-cache and BC_hunger, plus four Kaggle datasets and ten bc-v6 kernels. Server submissions were not deleted; there was no delete API.
Kept builds include viper_y96qf (Sv5.2), viper_y96qg (Sv5.3), viper_nv30k (Sv6), viper_nv30h_s4 (Sv6h), and original viper_nn/v7/v7.12/s2_rules builds.
Check bot/map/data paths and junction targets before using examples. Historical datasets, cache and output paths are not guaranteed existing inputs; recreate required inputs for a newly authorized run.

## Setup and first match

Run commands from C:\Users\sohan\Downloads\BattleCode_BC. Shell blocks below are Git Bash unless marked PowerShell; substitute uppercase placeholders. Install Python 3.11+ and the toolkit:

```sh
pip install unswbc
unswbc run maps/trophy.map baselines/Nv30 baselines/Y9_6
unswbc vscode
```

First bot is A, second B. Matches write .replay files; the VS Code viewer shows play and indicators. No local C++ compiler is needed for sandbox builds: the judge supplies clang. Rule-mining dependencies: scikit-learn, scipy, pytest and pycapnp; two generated-C++ tests skip without clang++. Use this environment wrapper for current local Python tools:

```powershell
uv run --python 3.11 --with unswbc python tools/buildwasm.py CANDIDATE_DIR
```

Keep credentials private in secrets.env; never print them, commit them or put them in a task/report. Load the environment in Git Bash with `set -a; . ./secrets.env; set +a`. Configure toolkit authentication with `unswbc auth set <key>` using the private credential locally. Scripts requiring API access use UNSWBC_KEY; Kaggle helpers use KAGGLE_API_TOKEN. Set LOONG_JUDGE to the native Zig judge, UNSWBC_ENGINE if overriding the engine, and LOONG_REPO for style-map generation. Read official docs/ for mechanics/protocol; archive/ is methodology/history, not current test evidence.

## Tool index

Commands beginning with python can use the uv wrapper above. ID means a submission ID unless stated otherwise.

| Script | Use | Command |
|---|---|---|
| tools/buildwasm.py | Header-aware wasm build | `python tools/buildwasm.py CANDIDATE_DIR` |
| tools/tourney.py | Sandbox matches, both sides | `python tools/tourney.py CANDIDATE_DIR baselines/Nv30 --maps trophy,devil,trauma --seeds 2 -j 3` |
| tools/gate.py | Historical stage-1 sanity gate; specify control | `python tools/gate.py CANDIDATE_DIR --champion baselines/Nv30` |
| tools/panel_zig.py | Native Zig panel via WSL | `python tools/panel_zig.py CANDIDATE_DIR baselines/Nv30 out/panel --set dev --seeds 3,4,5,6,7,8,9 -j 3` |
| tools/regression_gate.py | Win threshold and early queen-death gate | `python tools/regression_gate.py CANDIDATE_DIR out/gate --opp baselines/Nv30 --set dev --min-queen-round N` |
| tools/panel_queen.py | Queen deaths and per-map panel results | `python tools/panel_queen.py out/panel` |
| tools/queen_panel.py | Windows-only task verification | `python tools/queen_panel.py CANDIDATE_DIR baselines/Nv30 out/queen --maps MAP_NAMES --seeds 3,4 -j 3` |
| tools/ab_ladder.py | Back-to-back same-team/map ladder A/B | `python tools/ab_ladder.py CANDIDATE_ID ACTIVE_ID --teams TEAM_IDS --maps MAP_IDS --out ladder/ab --deadline-utc HH:MM` |
| tools/strong_panel.py | Unranked panel, restores control by deadline | `python tools/strong_panel.py CANDIDATE_ID ACTIVE_ID --teams TEAM_IDS --deadline-utc HH:MM` |
| tools/challenge_wait.py | Wait, report, download challenges | `python tools/challenge_wait.py ladder/test OUR_ID BATTLE_IDS` |
| tools/elo_bot.py | Ranked daemon using control | `python tools/elo_bot.py --our-sub ACTIVE_ID` |
| tools/find_targets.py | Falling higher-rated challenge targets | `python tools/find_targets.py` |
| tools/loss_report.py | Download/classify decisive loss phase | `python tools/loss_report.py BATTLE_IDS` |
| tools/replay.py | Gzip + packed Cap'n Proto replay decoder | `python tools/replay.py GAME.replay --dump` |
| tools/trace.py | Indicators preceding deaths | `python tools/trace.py trophy CANDIDATE_DIR baselines/Nv30 --deaths --ctx 6` |
| tools/ladder_report.py | Units/longest/total/death timeline | `python tools/ladder_report.py GAME.replay --ours LABEL` |
| tools/board_at.py | True board surrounding a dragon | `python tools/board_at.py GAME.replay DRAGON_ID ROUND` |
| tools/early_game.py | Eats, splits and deaths per dragon-turn | `python -c "import sys; sys.path.insert(0, 'tools'); from early_game import early; print(early('GAME.replay', 0, 100))"` (team 0 or 1) |
| tools/scout.py | Public replay collection | `python tools/scout.py --top 12 --per-team 10 --out ladder/scout` |
| tools/scout_report.py | Aggregate scout behaviour | `python tools/scout_report.py ladder/scout` |
| tools/profile_team.py | Replay team profile | `python tools/profile_team.py GAME.replay --side A` |
| tools/players_index.py | Per-player scout index | `python tools/players_index.py ladder/scout` |
| tools/team_mechanics.py | Sprint/sonar/echo usage | `python tools/team_mechanics.py ladder/scout/index.json ladder/scout` |
| tools/sprint_purpose.py | Sprint kills/eats/escapes and deaths | `python tools/sprint_purpose.py ladder/scout/index.json ladder/scout` |
| tools/gen_maps.py | Regenerate maps_data.hpp | `python tools/gen_maps.py` |
| tools/gen_random_maps.py | Random fair unseen maps | `python tools/gen_random_maps.py --n 300 --seed 1` |
| tools/gen_style_maps.py | All Loong generator styles | `python tools/gen_style_maps.py OUT_DIR SEED N` |
| rulemine modules | Extract/contrast/learn/codegen and parity | `python -m rulemine --help`; `python -m rulemine.parity` |
| rulemine.evalpair | Paired candidate/control screen | `python -m rulemine.evalpair CAND_OUT CTRL_OUT` |
| tools/mem_guard.sh | Wait for physical-memory floor | `bash tools/mem_guard.sh 3000` |
| tools/split_by_team.py | Stream CSV into group slices | `python tools/split_by_team.py SRC.csv OUT_DIR COLUMN` |
| tools/delegate.sh | Executor/verification/critic loop | `bash tools/delegate.sh tools/tasks/X.md "EXACT_VERIFY_COMMAND" MAX_ROUNDS` |
| tools/farm_run.sh | Guarded paired opening farm | `bash tools/farm_run.sh CANDIDATE_DIR --control baselines/Nv30 --games 2000 -j 3` |
| tools/farm_scale.py | PowerShell farm entry | `python -B tools/farm_scale.py CANDIDATE_DIR --control baselines/Nv30 --games 2000 -j 3` |
| farm/pack.sh | Legacy self-contained Linux farm bundle | `sh farm/pack.sh OUT_DIR BOT_DIR OTHER_BOT_DIR` |
| tools/kaggle_train/run_v6.sh | Private GPU training package/run/fetch | `bash tools/kaggle_train/run_v6.sh SHARD_DIR OUT_DIR 8` |

## Local panels and acceptance

Copy the current frozen control to a fresh candidate directory; change one thing at a time. For a basic development panel from PowerShell:

```powershell
uv run --python 3.11 --with unswbc python tools/panel_zig.py CANDIDATE_DIR baselines/Nv30 out/panel --set dev --seeds 3,4,5,6,7,8,9 -j 3
uv run --python 3.11 --with unswbc python tools/panel_queen.py out/panel
```

panel_zig auto-wraps WSL. Named sets documented in AGENTS.md include live/dev/test/setA/setB. The October 7 verification design is seven unseen maps, seeds 3–9, both sides: 98 games. Use that task's explicit seven-map list for a 98-game comparison; --set dev is not a claim of 98 games. Confirm with seeds 10–16, then independent critique, then approved ladder A/B. Hold maps_rm_test out until final checks. Do not compare PowerShell-path and direct-WSL numbers. A resume must bind both bot builds, map, judge, engine, seed and side; version-bound audits and shared worker reservations matter. A cached result from changed inputs is invalid; failed shards are failures to diagnose, not losses or missing rows to hide. CPU limit is 100M points per dragon-turn; exceeding it kills that dragon.
Aim for sandbox max <=65M; task acceptance checks often use <=66M. Rough elapsedMs conversion: 1 ms ~=1M points. buildwasm keys all sources; sandbox caching keys main.cpp only, so header changes also need a main.cpp edit/touch. Queen statistics and replay analysis must identify our side correctly; botA/botB may hold submission IDs.

| Evidence limitation | Concrete observation |
|---|---|
| OLD-rule sample noise | Same bot could win 4/5 and later 1/5; five games prove little. Guide estimates: 60% vs 50% needs ~100 games, 70% vs 50% ~25, 80% vs 50% ~10. |
| OLD-rule gate limitation | V7.6 passed locally and lost on ladder; local gate is only a regression filter. |
| NEW-rule local bias, October 6 | y7_12_49, vB19 and Y9_6 panels overestimated ladder strength; vB19 real records cited as 8W–17L and 4W–16L. |
| League fidelity, October 5 | 0/8 proxies accepted; none is a validated ladder-faithful opponent. |
| MLP safety, October 6 | 50/98 versus Sv5.3 59/98, -9.18 pp; CPU/parity passed but candidate rejected. |
| Infrastructure decision, October 6 | League/farm/search spent ~2.5 days with zero promoted candidates; parameter search stopped after 20h. |

## Ladder procedures

1. Obtain approval for the active-slot test. GET /submissions; record the actual active ID and coordinate with teammates.
2. Confirm candidate passed paired local checks and critique. Submission immediately becomes active.
3. Use neutral names and bland descriptions; the September convention was Y.7.12.<n>, not a current champion identifier.
4. Run both arms against identical near-rating teams and maps, back-to-back within one test window.
5. Check restoration using GET /submissions after the script exits; do not assume finally proves server activation succeeded.
6. Compare totals, per-map results and replay mechanisms. Promote only with clear ladder evidence; freeze exact accepted sources.

| Limit/schedule | Value |
|---|---|
| Challenges | 60 games/team/hour; a 10-map challenge consumes 10 |
| API requests | 120/minute/key; leaderboard and ratings reads 30/minute; 429 supplies Retry-After |
| Uploads | 12 versions/hour; zip <=4 MB; activations unlimited |
| Ranked eligibility | Opponent enables ranked and is no more than 50 Elo below us |
| Autoscrims | Every two hours, even UTC hours (05:30, 07:30… IST); use whichever build is active |
| Historical Elo K rule | Up to 96 only for first new-code ranked build after team's 12-hour window opens; otherwise K=24 |

API base: https://game.battlecode.au/api/v1. GET /maps supplies the current live pool. Historical 10-map IDs: Portals 20, Slithery 21, Schooltime 9, Trophy 11, QoS 7, Default 4, Dilemma 17, Autarky 19, Devil 13, Trauma 15. Do not assume those ten maps are the complete new-rules pool. An unranked request and a restoration request, with credentials already loaded:

```sh
BASE=https://game.battlecode.au/api/v1
curl -s "$BASE/battles" -H "Authorization: Bearer $UNSWBC_KEY" -H "Content-Type: application/json" -d '{"teamId":590,"ranked":false,"mapIds":[11,7,4,17,19,13,15]}'
curl -s -X POST "$BASE/submissions/ACTIVE_ID/activate" -H "Authorization: Bearer $UNSWBC_KEY"
python tools/ab_ladder.py CANDIDATE_ID ACTIVE_ID --teams TEAM_IDS --maps MAP_IDS --out ladder/ab --deadline-utc HH:MM
```

Use a future same-day HH:MM UTC deadline that leaves time for both arms and restoration. Current send_all quota retries have no deadline check; finally attempts restoration but cannot survive a hard process kill. Verify the active slot yourself. ab_ladder restores its supplied champion ID in finally; strong_panel also restores by its deadline. The A/B shares teams/maps, not a guaranteed server pearl seed. Quota waiting and teammate activations can disrupt the window. GET /battles/<gameId>/replay returns public replay data; follow redirects.

| A/B lesson or fix | Evidence |
|---|---|
| OLD-rule floor effect, September 30 | Candidate 4/25 against 2035–2090 teams almost labelled refuted; same-time champion 8/25, our ~1667 Elo expected ~10%. Use near-rating opponents and a control. |
| Fixed October 8: winner case | Case-sensitive comparison incorrectly printed 0/48; compare normalized winner/side. |
| Fixed October 8: wait_all | Non-dict battle entries crashed polling; guard entry type. |
| NEW-rule corrected October 8 A/B | Sv6h 20531: 23/48; recorded-active Nv3.5 20500: 25/48, no difference; eight teams × six maps, unranked; 20500 restored. |

elo_bot tests teams >=20 Elo above us on five maze maps; ranks only won maps if >=3/5 and >=Elo-expected+0.2. It pauses while a candidate is active and restores its configured champion five minutes before autoscrims. Logs: ladder/elo_log.txt and ladder/loss_log.txt. Ensure its configured ID matches authorized slot handling. Indicators and sonar reveal logic in public replays: strip debug logging; never submit rmLog=1.

## Paired opening farm

Operational reference only: October 6 stopped this work; do not resume without new authorization. The default is local WSL, remote lanes OFF, no network or LLM calls inside evaluation loops. Override historical out/sv53_pkg with baselines/Nv30 for current authorized comparisons. Default stage: F:/BattleCode_data/farm_scale; rerun the identical command to resume. 2000 means games per arm across nine opponents: 2000 candidate + 2000 control, 40 shards ×100 evaluations. Odd counts round up to complete side pairs; sides, arms and opponents share seeds. Schedule rotates opponent, map, seed; 17 live maps plus maps_rm_dev, no held-out test maps. Typical default coverage: 3–4 independent seed clusters/map; 222–224 games/opponent/arm.
Manifest hashes sources including .cc, maps, judge, engine, toolchain and analysis; bundle seal hashes actual runtime inputs. Changed identities make a fresh run; mixed/corrupt state is rejected. Atomic state/*.json is authoritative; results.tsv and farm_report.md are rebuilt, with out/farm_report.md copied each shard. Save evaluation before deleting its replay; preserve failed scratch until judge exit. Supervisor lock plus surviving-child Linux flock blocks unsafe overlapping resumes; attempts use unique replay directories. Primary metrics: units50/100, total length100, first split, eats/round over rounds 0–99, terminal carry and final-body parity. Never-split stays NA, counted separately. Benchmarks: out/opening_census.txt map medians, subject to winner-selection confounding.
Use seed-cluster means and Student t intervals for paired opening differences; few clusters remain imprecise. Secondary wins use Wilson intervals with draws half-credit; an interval spanning zero does not establish non-inferiority. Default nominal precision: pooled +/-2.2 pp, per-opponent +/-6.6 pp, not +/-1 pp. --precision-pp 1 budgets >=9604 games/opponent/arm, >=86436/arm for nine opponents; it is not a precision guarantee. Fixtures only, on F:, use farm_verify.py STAGE, farm_fix_verify.py STAGE, then farm_round2_verify.py STAGE with the uv wrapper. Fixes cover surviving-child leases, quoted WSL paths, manifest-read reuse and checkpoint validation; full-scale timing is unmeasured.

## Kaggle training and remote farm

Remote upload/publishing and dispatch require explicit approval; workflows stay private and OFF by default. October 4 Kaggle API returned 403: local training/farm must not depend on it. Local CUDA Python310 on GTX 1650 was reported at ~15k samples/s for small nets; GPU does not accelerate CPU-bound wasm games. For approved GPU training, build and check streaming shards first (repo-root Git Bash):

```sh
uv run --python 3.11 --with unswbc --with numpy python ml/v6/build_dataset_v6.py --index MANIFEST.csv --replays REPLAY_DIR --workers 2 --out SHARD_DIR
uv run --python 3.11 --with numpy python ml/v6/test_builder.py SHARD_DIR
```

Then package and run the private GPU kernel:

```sh
set -a; . ./secrets.env; set +a
bash tools/kaggle_train/run_v6.sh SHARD_DIR OUT_DIR 8
```

run_v6 packages only named ml/ tools and shard files into private bc-v6-code and bc-v6-shards datasets. It pushes a private GPU script kernel, internet disabled, waits and downloads outputs to OUT_DIR. Defaults: shards ladder/scout_v6/shards; output ladder/scout_v6/train_out/kaggle; eight epochs; owner sohansridutta. Optional TAG separates kernel names; TEAM_COND and ONLY_TEAMS control training; SKIP_UPLOAD=1 reuses uploaded datasets. Mixed-data runs use OLD_DATASET/OLD_MANIFEST, VAL_GAMES and optional INIT; manifest/holdout/init hashes bind inputs. Exclude explicit validation games from every training directory; validation data counts once. Training boundary is the 1513 game IDs in ladder/scout_v6/shards_145/manifest.json, not extra manifest_all.csv rows.
Dataset readiness timeout is 1800s; default kernel timeout 7200s and fetch timeout 10800s. Helper calls: push_dataset.sh DATASET_DIR upsert, push_kernel.sh KERNEL_DIR TIMEOUT NvidiaTeslaT4, fetch_output.sh OWNER/KERNEL OUT_DIR TIMEOUT. After fetching, export and verify with the CUDA-enabled Python310 interpreter (PY310 below means C:/Users/sohan/AppData/Local/Programs/Python/Python310/python.exe; invoke with & in PowerShell; native parity needs WSL g++):

```sh
PY310 ml/export_cpp.py OUT_DIR/v6.pt CANDIDATE_DIR/policy_weights_v6.hpp --data SHARD_DIR
PY310 ml/v6/parity.py OUT_DIR/v6.pt SHARD_DIR CANDIDATE_DIR
```

Use the actual checkpoint filename returned by the kernel. Local fallback: `PY310 ml/v6/train_v6.py --data SHARD_DIR --out OUT_DIR/v6.pt --epochs 8 --val-frac 0.1 --amp`. Do not promote from training metrics alone: native parity, plane-8 weight audit, metered CPU and paired safety still apply. Kaggle upload fixes: helpers cd to the dataset and use -p . to avoid Kaggle 2.2.4 Windows upload-state paths. SKIP_UPLOAD=1 avoids duplicate uploads for a second kernel; wait for datasets to report ready before mounting. The helper uses -r skip for flat shards; nested shard directories need -r zip (October 7 new2 upload), or their contents are omitted. fetch_output.sh alone defaults to 2400s; run_v6 overrides it to 10800s. Timeouts return 124; inspect logs before resuming.
For an approved offline paired CPU farm, append --pack-only to the local farm command. Upload only its whitelist bundle as a private dataset: wasm/judge/engine/maps/tools/shard JSONs, no secrets or bot sources. Copy into /kaggle/working/farm in a private internet-disabled CPU kernel, one kernel per shard:

```sh
cd /kaggle/working/farm
FARM_LANE=kaggle python3 -B farm/worker.py shards/jobs_0000.json -j 2
```

Use account-displayed kernel limits; no fixed concurrency entitlement is assumed. Return state/, manifest.json and bundle_seal.json together. Stop local supervisor before import:

```sh
bash tools/farm_run.sh CANDIDATE_DIR --control baselines/Nv30 --games 2000 --import-results /mnt/f/returned/state --collect-only
bash tools/farm_run.sh CANDIDATE_DIR --control baselines/Nv30 --games 2000
```

Returned schema, finite metrics, job IDs, manifest and seal must match; reject extra IDs and conflicting results. Remote workers cap -j 2; no automatic API fallback or measured remote throughput is claimed. GitHub Actions requires approval and confirmed private visibility; no paired workflow was installed/dispatched. Legacy farm prototype: pack.sh bundles judge/engine/bots/maps; make_jobs.py --pair A:B --maps live,test --seeds 1-4 --shards 16 --out-dir shards. Inside that bundle run sh run_shard.sh shards/jobs_0.tsv 3, then python3 summarize.py results*.tsv. Legacy Kaggle uses kaggle/run_shard_kaggle.py with SHARD=i and returns results_i.tsv; legacy TSV jobs are not paired worker JSON jobs. Zig prototype measured ~3× sandbox speed with identical outcomes on checked games; this is historical, not a throughput guarantee.

### Measured Kaggle and league limits

| Date / workflow | Result and operating implication |
|---|---|
| October 2 GPU probe | Before phone verification: CPU-only, CUDA false, DNS failure. After verification: two Tesla T4, torch 2.10.0+cu128, CUDA/internet true; 50 4096x4096 matmuls in 1.8 s. Check actual allocation. |
| October 3 training | 145 games / 2.24M samples, eight epochs, 539 s (~33k samples/s); holdout 0.7112, best 0.7145 at epoch 7. |
| October 3 concurrency | Third parallel GPU run failed: account allowed two concurrent GPU sessions then. Use today's account limit. |
| October 7 mixed-data run | 107 min, 30M samples old x1/new x2, four epochs; newest-143-game holdout 69.85% ->70.66%. 1600-state argmax parity 100%, max logit error 2.7e-3 exceeded 1e-3 bar (old net 2.2e-4); cause unverified. Accuracy alone does not establish promotion. |

Historical league command (PowerShell): & C:/Users/sohan/AppData/Local/Programs/Python/Python310/python.exe tools/league_build.py.
It streamed post-rule winning replays, held out one game/team, trained 16-channel/32-hidden nets for eight epochs, then ran at most three WSL games. Heavy stages required 3 GB free physical RAM and 6 GiB on F:; state lived in F:/BattleCode_data/league_build.
Fidelity used four replay-covered maps, seed 1, both sides (8/team); Sv53 safety used Maze/Stripes/Devil/Trophy/Portals, seeds 1–2, both sides (20/team). Acceptance required median-of-four-map-medians units100 within 25% of real wins and measured CPU <=66M across fidelity, safety and verification; absent counters prevented acceptance.
All eight failed fidelity. Rules still chose split/feed/sprint actions; movement imitation did not establish ladder fidelity. league_finalize.py wrote league/index.json and out/league_build_report.md after verification. The workflow is stopped and artifacts were cleaned up.

## Agent workflow

October 4 lane routing supersedes October 2's Codex-critic-only rule. Codex CLI and Antigravity handle code/hard analysis; whichever writes code, the OTHER critiques it. Antigravity is GUI-only: user instructs “Follow tools/tasks/ag_queue/NEXT.md”. Menial lane: opencode/OpenRouter longcat for git/downloads/moves/log summaries, never bot-changing code. Every standalone brief names scope/files/constraints and an exact verification command, not “run tests”.

| Role | Required output |
|---|---|
| Director | One tools/tasks/<id>.md per job; own acceptance decision; request <=10-line returns and critique decision-changing results |
| Executor | Edit only named candidate working directory, never baselines; changed files/diff and unverified claims |
| Critic | Attack premise and result, reproduce small checks, file:line fixes; do not edit implementation |
| Runner | Wins/games, per-map, CPU max and failures; resource guards; no raw-log dump |
| Analyst/researcher | Counts or <=10-line finding/plan with code locations and script path |
| Scout/trainer | Dataset/disk counts or metrics/weights/size/p8 checks; trainer disk cap 6 GB |

Generic critic brief allows only out/<name>_critique.md, <=40 lines; last line exactly VERDICT: PASS or VERDICT: FAIL: <reason>. Check silent shard loss, seed/side/map pairing, resume identities, CPU/RAM/disk, secret leakage and actual acceptance premise. A single diff-only critic missed the swarmsplit_fix's wrong guard/root cause: execute the proof and question the diagnosis. Critic reruns small checks only, max three jobs, C: >=3 GB; no LLM inside unattended evaluation/search loops. Normal agent log format is one appended line, newest last: - [date] [director|executor|critic] [task id] message. This consolidation job explicitly forbids appending to AGENT_LOG.md. delegate.sh snapshots with scoped_diff.py, executes the first working backend, captures scoped diff, verifies, critiques and iterates failures.
Excluded diff inputs: secrets.env, out/, ladder/, files >2 MB; generated diffs/logs still require secret hygiene. Artifacts: <task>.<stamp>.exec.log/.diff/.verify.log/.critique.log/.backend.txt; director decides acceptance. orchestrate_build historically allows two fix rounds and writes .stepdone/orch.done even after final failure: markers are not PASS. Create out/ before redirecting its log; stopped default steps must not be relaunched casually. Backend history, October 2: cf/cfcode worked free with tools; OpenRouter free models rate-limited; Groq multi-step rejected reasoning_content. Groq 8000 TPM and daily free-service caps constrain jobs; two small passed tasks do not establish multi-file reliability. Longcat needs account credit (“can only afford N tokens” concerns balance), output capped at 8000; Kimi 403 required paid plan.
CLI paths may require ~/.bun/bin and ~/.kimi-code/bin; never put credentials in a brief.

## Machine safety and failure fixes

| Failure | Cause, evidence and fix |
|---|---|
| OOM crash | ~20 jobs each loaded a full multi-million-row CSV. Stream once with split_by_team.py, then load slices; CSV/learning fan-out <=4. |
| RAM competition | 16 GB machine; idle vmmemWSL ~2.5–3 GB plus desktop apps ~2–3 GB. Size workers from free physical RAM. |
| Current game caps | NEXT_STEPS: -j <=6 alone, <=3 alongside other jobs; older -j 8/10 examples are superseded. Cooperating Windows/WSL panels share reservations. |
| Memory guards | mem_guard.sh checks every 20s; use before each heavy stage. Farm floor max(3000,1500+600×workers) MB; 600 MB/worker is planning, not measured peak. |
| Disk exhaustion | ~240 GB free fell to 197 MB after replay batches. Debug replays cost hundreds of MB; local_index and .pkl caches roughly double footprint. |
| Pagefile/C: | Pagefile growth consumes C:. Keep >=3 GB free; check df -h /c before/after 20+ retained-replay games. Extract/log results, then delete disposable replays/.pkl only from the intended ladder subdirectory. |
| F: storage | ladder/, out/, wasm_cache/ are junctions to F:; older data moved to F:\moved_from_C. Farm F: floor 2 GiB; league requires 6 GiB. Floors cannot protect against other concurrent writers. |
| Junction imports | Path(__file__).resolve() follows ladder to F: and cannot find C: ml/tools. Use repo working directory for repo-relative imports. |
| TLS flakes | uv under load sometimes reports Failed to fetch / invalid peer certificate: UnknownIssuer / Request failed after. Retry 2–3 times before treating as permanent; Kaggle helper retries three attempts. |
| Codex exhaustion | Usage-limit failures can end every job instantly; wait for reset or use authorized other lane. “model at capacity” can be retried; October 2 reset ~17:22 IST was historical. |
| False-positive retry | October 5 detector matched “usage limit” quoted inside logs. Restrict detection to actual error lines; orchestrator uses ^ERROR:.*(capacity\|usage limit) or hit your usage limit. |
| Empty background run | Shell creates redirects before execution. mkdir -p target log directory first; use one guarded resumable shell chain and done markers. |
| Unsafe process kill | Pattern query can match its own wrapper. Inspect PID/command line, stop exact intended PIDs, then recheck; do not trust pattern-only pkill/ps. |
| Stale sandbox build | Header-only edit reused old main.cpp cache; touch/edit main.cpp or use buildwasm.py. |
| Windows text | subprocess needs encoding="utf-8"; shell C++ heredocs can damage literal newline escapes. Use patches/editor. UTF-16 agent logs need NUL cleanup, never overwrite another agent's entries. |
| Remote 403 | Kaggle failure is not a reason to block local farm/training or silently enable remote fallback. |
| Acceptance confusion | Passing tool fixtures, .stepdone, classification accuracy or local win rate does not approve a bot or validate a league proxy. |

PowerShell process inspection: Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*pattern*' }. After reviewing matches, use Stop-Process -Id EXACT_PID -Force and inspect again. Never commit secrets.env, out/ or ladder/; debug builds belong in separate copies with debug_cfg.hpp (DEBUG_FROM/DEBUG_TO).
Sources consolidated: tools/tasks/docs_merge/COMMON.md; AGENTS.md; README.md; guide/1_setup.md; guide/2_how_our_bot_works.md; guide/3_testing_a_change.md; guide/4_mistakes_to_avoid.md; farm/README_FARM.md; farm/README_SCALE.md; tools/README_LEAGUE.md; NEXT_STEPS.md; tools/orchestrate_build.sh (header/retry loop); tools/tasks/critic_generic.md; topic-only AGENT_LOG.md entries (2026-10-05 retry fix, 2026-10-08 A/B fixes/results, 2026-10-14 cleanup, topic-only Kaggle results); command checks in ml/v6/build_dataset_v6.py, ml/v6/test_builder.py, ml/v6/parity.py, tools/ab_ladder.py, tools/panel_zig.py, tools/panel_queen.py, tools/scout.py, tools/scout_report.py, tools/profile_team.py, tools/early_game.py, tools/team_mechanics.py, tools/sprint_purpose.py, farm/pack.sh, tools/kaggle_train/run_v6.sh and helper headers; quota checks in docs/api.md and docs/submitting.md. Original files remain unchanged.
