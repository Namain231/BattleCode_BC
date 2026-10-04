# CPU fix verification - 2026-10-02

Candidate `viper_b19_cpu` versus `baselines/y7_12_nn1`. Fresh eight-game CPU panel: own-side maximum **51,958,038 points**, all eight below 65M. Live gate: **12/20**, PASS; 0 asymmetric queen deaths before round 50.

| Map | Seed | Our seat | F1 before max | CPU fix after max |
|---|---:|:---:|---:|---:|
| schooltime | 1 | A | 76,870,551 | 51,868,602 |
| schooltime | 1 | B | 63,257,872 | 51,465,973 |
| schooltime | 2 | A | unavailable | 51,958,038 |
| schooltime | 2 | B | unavailable | 51,780,516 |
| devil | 1 | A | unavailable | 42,875,350 |
| devil | 1 | B | unavailable | 29,120,685 |
| devil | 2 | A | 56,235,797 | 44,980,551 |
| devil | 2 | B | 43,058,418 | 43,448,533 |

CPU is the maximum complete-turn points from the judge stdout: A points column 12 or B column 14 (zero-based), third component of p50/mean/max; selection follows our seat, never the winner. Before values are the surviving measurements in `cpu_fix_result.md`. The largest recorded before value is 76,870,551; the after-panel peak is 51,958,038 (32.4% lower), though those peaks belong to different games.

| Live map, seed 1 | Wins / 2 | Seat A queen death: ours / champion | Seat B queen death: ours / champion |
|---|---:|---|---|
| autarky | 2/2 | r5 / r5 | r5 / r5 |
| default | 2/2 | survived / r105 | survived / r26 |
| devil | 0/2 | r491 / r50 | r165 / r35 |
| dilemma | 1/2 | r5 / r5 | r5 / r5 |
| portals | 2/2 | survived / r29 | survived / r228 |
| queen_of_spades | 1/2 | r299 / r188 | r334 / r180 |
| schooltime | 2/2 | r179 / r60 | r360 / r112 |
| slithery_fight | 0/2 | r5 / r5 | r5 / r5 |
| trauma | 1/2 | survived / r91 | r339 / r91 |
| trophy | 1/2 | r282 / r52 | survived / r82 |

Our starting queen (dragon 0/1, as defined by the gate) died in 14/20 games; the champion's died in 20/20. Six own early deaths at r5 have paired champion deaths at r5, so they do not trigger the gate. These are candidate-versus-champion pairs, not candidate-versus-F1 control pairs. The prior Schooltime seed2 A queen regression (454 to 409) remains unresolved by this task.

The prior 10/20 yardstick is attributed to vB19, not an independently verified F1 control. The current 12/20 is a regression screen only: n=20 gives roughly 11 percentage points standard error near 50%; two extra wins do not establish improved strength. Passing this tool does not complete the mandatory promotion gate, and eight CPU games do not prove a universal CPU cap.

Commands used the requested maps/seeds and -j 2, via Git Bash with `uv run --python 3.11 --with unswbc python`. Existing output replays caused cache hits, so CPU games were rerun fresh under `out/cpu_after/fresh`; the requested live gate reused all 20 already completed `out/cpu_gate` replays. This gate run completed analysis rather than generating a fresh live20 control. Candidate main.cpp SHA256 matches the fix report: `79cc439e62c2a4ef092e4214d0751ba7dda74214ea5a6b9f4cebab9e56a39716`.

Retained evidence: `out/cpu_after/fresh/panel.log`, `summary.json`, `out/cpu_gate/gate.log`, `gate_report.json`, and `paired_queens.json`. Task-folder replay files were deleted after extraction; C: remained above 1.5 GB (observed about 3.0-3.4 GiB; final 3,191,664,640 bytes). No bot code or ladder submission changed.
