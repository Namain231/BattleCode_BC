# CPU1 result - 2026-10-02

Status: implementation and build complete; verification INCOMPLETE / NOT CERTIFIED. Do not promote this candidate on these results. C: fell from about 5.6 GB free to effectively zero during the run. Task-generated replays accounted for only about 125 MB. Task processes were stopped; no unrelated files or processes were removed. More disk space is required to finish the requested panels.

## Change

`viper_b19_cpu/` is the isolated F1-derived candidate. All original files except main.cpp remain byte-identical to viper_b19_f1, including msgauth.hpp, maps and network weights. The existing partial CPU1 implementation was inspected and completed rather than overwritten. Authentication constants were never displayed or edited.

CPU1 replaces linear enemy-reach membership with an N-cell arrival array and uses direct per-option arrival lookup. It preserves BFS traversal order, occupancy stopping rules, turn-distance labels, blocked landing cells and the original exclusion of the starting enemy head. Reach construction is still exact, not threat-truncated.

A shared 48ms deadline stops further option evaluation, emergency path search and split probes, retaining the evaluated prefix and its best option. At least the first legal option is evaluated; the existing raw-step fallback remains available if no legal option exists. DFS checks every 64 nodes, restores state on unwind and returns only attained depth. An interrupted pessimistic search cannot falsely establish safety. The optimistic pass rechecks the deadline. Split probes now check before both parent and child evaluations. Attack enumeration uses a 52ms reserve deadline, checks every 16 path codes and retains the best complete attack found. Network admission is tightened from 40ms to 30ms. readTurn parsing is included in the shared clock.

These are admission deadlines, not a proved hard complete-turn cap: one field evaluation can overrun its admission deadline, initialization is outside the shared clock, and final output is charged afterward. Complete-turn judge measurement remains mandatory. Faster reach lookup and adjusted elapsed accounting can change old time-dependent search tiers; action equivalence is established only for the paired observations below.

## Build and CPU reproduction

Build succeeded using tools/buildwasm.py through panel_zig.py. Validated candidate main.cpp SHA256: `79cc439e62c2a4ef092e4214d0751ba7dda74214ea5a6b9f4cebab9e56a39716`. Compiled artifact: `wasm_cache/viper_b19_cpu-7c67cb554ac155e9.wasm`.

Baseline command: `uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_b19_f1 baselines/y7_12_nn1 out/cpu_base --maps schooltime,devil --seeds 1,2 -j 2`. Cached replay rows did not preserve CPU stdout, so a fresh recheck used out/cpu_base/recheck. Only the following own-side complete-turn CPU values survived in usable judge stdout:

| Map | Seed | Our seat | F1 max points |
|---|---:|---|---:|
| Schooltime | 1 | A | 76,870,551 |
| Schooltime | 1 | B | 63,257,872 |
| Devil | 2 | A | 56,235,797 |
| Devil | 2 | B | 43,058,418 |

CPU is selected by candidate seat, not winner or opponent maximum. Other baseline CPU rows are unavailable. The Schooltime A tail was reproduced near the audit's 76,876,136-point peak. Candidate CPU stdout was empty after orchestration interruption; sanitized replays cannot recover it. **After-max and <=65M are unverified.** Logs retained at out/cpu_base/panel.log, out/cpu_base/recheck/panel.log and out/cpu_candidate/panel.log. Interrupted redirection makes the latter logs incomplete; do not treat absent rows as zero CPU.

## Paired behavior and queen deaths

Six candidate replays were validated for terminal results and paired against F1 with the same champion, map, seed and seat. All 509 own actions through round 20 matched. Both Devil seed-1 games had identical complete chronological action sequences. Schooltime first divergences occurred at rounds 222 (seed1 A), 458 (seed1 B), 269 (seed2 A) and 407 (seed2 B). Per-turn CPU is absent, so this is early-action evidence, not proof of equivalence on every under-budget state.

| Map | Seed | Seat | F1 queen death | CPU1 queen death |
|---|---:|---|---:|---:|
| Devil | 1 | A | 491 | 491 |
| Devil | 1 | B | 165 | 165 |
| Schooltime | 1 | A | 179 | 179 |
| Schooltime | 1 | B | 360 | 360 |
| Schooltime | 2 | A | 454 | 409 |
| Schooltime | 2 | B | 337 | 337 |

Queen deaths were 6/6 for both, but Schooltime seed2 A died **45 rounds earlier** in CPU1. This requires investigation; equal death totals do not establish equivalent queen survival. Both builds won 4/6 in this partial panel. This is not wins/20 and not a strength claim.

The requested `uv run --python 3.11 --with unswbc python tools/regression_gate.py viper_b19_cpu out/cpu_gate --opp baselines/y7_12_nn1 --set live --seeds 1 -j 2` did not complete/start its games. No gate verdict or live20 queen comparison exists. The supplied earlier 10/20 yardstick is a reference only: research_new_meta/yardstick_vs_champion.md attributes that run to baselines/vB19, not an independently established F1-vs-champion control. At n=20, SE near 50% is about 11 percentage points; this gate is a regression screen, not a strength claim. Its own-vs-opponent early queen flag also does not replace candidate-vs-F1 pairing.

## Artifacts, review and remaining work

Analysis: viper_b19_cpu/compare_paired.py, capture_paired.py, paired_results.json, base_initial_snapshot.json and candidate_snapshot.json. Snapshots preserve chronological actions and queen deaths without sonar contents. All 22 generated replay files in the task's baseline/recheck/candidate folders were removed after extraction, reclaiming about 124.7 MB; unrelated replay folders were left alone.

Read-only critic confirmed reach correctness, safe DFS interruption and complete-attack retention. Final verdict: cannot certify; investigate the paired queen regression and obtain the missing CPU and live20 evidence.

Resume after disk relief: rerun the exact baseline and candidate eight-game panels with stable stdout logging; require measured candidate own-turn maxima <=65M, then run the full live20 gate and a matching F1 live20 control for map/seed/seat queen comparison. Clean extracted replays between stages. Existing snapshot data can support behavior comparison, but does not replace fresh CPU stdout. No ladder action or promotion occurred.
