# league_build critique (2026-10-05)
Required fixes:
- tools/league_build.py:120, league/team_566/main.cpp:2009: movement scores only consume logits 0..3; split/action logits never drive decisions. All eight proxies fail the required economy fidelity (units100 ratios 0.088..0.566); none delivers a ladder-faithful league. Keep them rejected; redesign and revalidate before using league win rates for decisions.
- tools/panel_zig.py:105; tools/league_build.py:135: cache/resume keys omit bot, map, engine and judge hashes. Mocked changed bots still return cached; changed sources can inherit old wins/CPU. Store and validate a complete run fingerprint in panel and aggregate state.
- tools/panel_zig.py:117: a nonzero judge exit with an existing replay returns success. Reproduced rc=9 returning "ok". Check return code and complete replay/result; write to temporary paths and commit replay/CPU together. Reject failed games rather than scoring leftovers.
- tools/panel_zig.py:253; tools/league_finalize.py:6: validate exact map/seed/side identities and bot provenance, not only game counts. Verification finalizer accepts any eight rows; stale replay files exist (team_844/sv53 has 24 files for 20 scheduled games).
- tools/league_build.py:21: guard checks only F: disk, not the required C: >=3 GB. Check C:, F:, junction targets and RAM before every heavy stage; uv/WSL/pagefile can consume C: despite F: staging.
- tools/league_build.py:112; ml/v6/train_v6.py:151: final model/metrics writes are non-atomic and model existence alone skips training. A crash can leave a corrupt model or missing/empty resumed metrics. Commit a validated export bundle atomically and retain prior epoch metrics.
- tools/league_build.py:178: no supervisor lock; duplicate invocations can race state/model writes and run training alongside a three-game panel. Add a global lock covering the workflow; per-output panel locks do not protect aggregate state.
- tools/league_parity.py:15; league/team_566/main.cpp:1828: numerical forward parity does not establish runtime feature-builder parity. Compare identical replay-state inputs byte-for-byte before blaming all fidelity loss on movement-only imitation.
Verification and scope:
- Read AGENTS.md, NEXT_STEPS.md, brief/report and reported scripts/docs; inspected git status and tracked panel diff. Reviewed all eight source sets against viper_y96qf and league/index.json hashes; wasm copies match logged build-cache binaries.
- Recomputed all 64 fidelity +160 Sv53 replay summaries and LOCAL opening metrics against stored state: reproduce exactly. Aggregate fidelity ratios and ranking arithmetic reproduce: 0/8 accepted, 2/12 discordant strict pairs, 4 collapsed ties.
- Repeated the eight-game panel execution using existing cache, with build/output writes suppressed to obey edit-only-critique scope: 1/8, league CPU 55.183464M, Y9_6 CPU 59.857809M. No fresh judge matches or rebuilds were performed.
- Re-executed all eight existing C++ parity binaries into anonymous RAM files and compared to PyTorch: 128 states/team, max absolute error <=6.676e-6, 100% argmax agreement; plane-8 bounds pass. Did not recompile the binaries.
- Dataset sample counts, one-game holdouts and eight-epoch metrics match every report row; validation percentages were checked from saved metrics, not recomputed inference on the full holdout.
- All fidelity schedules are four maps/seed1/both sides; all Sv53 schedules share five maps/seeds1,2/both sides. CPU ownership selects the league side correctly; missing CPU prevents acceptance.
- At most two concurrent checks; C: remained >13 GiB free. ladder/ and out/ resolve to F:. No LLM calls or secret patterns found in reviewed league files; unrelated dirty secrets.env was neither read nor attributed to this task.
What I would not trust:
- These proxies as real-team opponents, their local win rates as ladder forecasts, or strict opponent ranking from 20 games and unmatched real map/seed distributions.
- Real opening medians as unbiased benchmarks: winner-only references, sometimes one real game/map, share games with training. Raw real-reference replay metrics were not independently recomputed.
- Cache results after any source/map/tool change; fresh crash-free execution, recompilation, input parity, or CPU <=66M beyond the measured games.
- The brief's farm/search outcomes: this build implements neither precision estimation nor promotion search. At 95% confidence, +/-1 percentage point needs about 9,604 independent Bernoulli games at worst case; paired/clustered designs need their own interval. No >=3-point paired-seed promotion evidence exists here; no promotion occurred.
VERDICT: FAIL: all eight opponents fail required fidelity; cache provenance, failure handling and crash-resume safeguards need fixes
