# Task search_s3_proto — unmetered served-policy search prototype: does net-guided search beat the plain rule/net bot? (research prototype, NOT a submission)

Repo: C:\Users\sohan\Downloads\BattleCode_BC (Windows; heavy tooling in WSL Ubuntu: `wsl -d Ubuntu -- bash -lc '...'`; repo at /mnt/c/Users/sohan/Downloads/BattleCode_BC; Loong checkout ~/the-loong-game). No memory of earlier work.

Read first: `research_new_meta/loong_blog/DIGEST.md` (served policy: `just zig-judge --engine ENGINE.wasm --map arena.map --a OPP.wasm --b OPP.wasm --seed 123 --serve /path/policy.sock --serve-team B --replay served.replay`, wrap with `timeout 300`; section (a) and the tools table), `research_new_meta/search_layer_plan.md` (search design, leaf score, budgets, sections 2d/2e), `research_new_meta/search_s0_result.md` (an offline audit says NO-GO by its own guessed thresholds: your job is to test the idea directly), `tools/engine_sim.py` + `research_new_meta/engine_sim_status.md` (pure-Python simulator, 100% round-exact on 4 replays), `engine_cpp/` if it exists when you need speed (another job is building a C++ engine: do not edit it), `ml/p8_sensitivity.py` (numpy forward pass of the shipped net `baselines/vB19/policy_weights.hpp`, 19 planes), docs/protocol.md, and ~/the-loong-game/harness/zig_judge/src/served.zig and main.zig for the served socket protocol.

## Goal
A Python (numpy) external policy `tools/search_proto/serve_search.py` that plays one team through the served-policy socket against the official wasm opponent `baselines/vB19` (build with `uv run --python 3.11 --with unswbc python tools/buildwasm.py baselines/vB19`), unmetered (no CPU limit: this is a research bound), and report its win rate on the 10 live maps (trauma, autarky, trophy, default, dilemma, devil, slithery_fight, schooltime, portals, queen_of_spades), both sides, versus the SAME harness running the plain policy.

## Milestones
Log each as one appended plain-ASCII line `- [2026-10-02] [executor] [search_s3] Mx <result>` in AGENT_LOG.md (append only) and continue unless blocked.
- M0: get the serve harness working: a trivial served policy plays a full game vs vB19 via the socket; record how the served protocol delivers observations/actions per dragon and per round. One process decides ALL our dragons, so they share knowledge: this is an UPPER BOUND vs the shipped per-dragon bot; say so. If `--serve` is unsupported by the installed judge (~/toolchains/zig-judge-out/bin/loong-judge is old), try rebuilding from ~/the-loong-game (`just zig-judge-build`; needs Zig 0.16 at ~/toolchains/zig-linux, Nim, just). Do not install system packages; report blockers precisely and stop.
- M1: net-only policy (numpy shipped net, argmax, simple rules for split/legal moves) as the BASELINE under the same harness, 20 games on the live maps (both sides, seed 1). Report the win rate vs vB19 wasm.
- M2: search policy: build an estimated world from our merged observations; the net proposes moves for every dragon on both teams (opponent modelled by the same net, sample 2 replies); candidates above a probability threshold; 3-round rollouts with tools/engine_sim.py (or engine_cpp if ready); leaf score = our total length minus theirs plus a queen term (our queen dying very negative, theirs dying positive; queen length counts at round 500); UCB1 over candidates; ties go to the net's pick. Run the same 20 games. Report win rate, queen death rounds, per-turn search time, rollout depth reached. Compare M2 vs M1 with the honest standard error (n=20 is ~11 points; run 40 if time allows).
- M3: ablate: depth 1 vs 3, with/without the queen term.

## Hard rules
No edits to baselines/ or to shipped bots; games at -j 2; delete replays when finished (disk ~6 GB free); no .pkl; python via `uv run --python 3.11 --with unswbc --with numpy python ...`.

## Report
Write `research_new_meta/search_s3_result.md` (method, table, caveats, verdict with go/no-go for building a wasm version under the 100M CPU budget). Final message: <=10 lines.
