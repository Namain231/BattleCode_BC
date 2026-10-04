# Task search_s1b_cpp — C++ forward engine from the official reference, new rules, lockstep-verified, benchmarked vs the Python simulator

Repo: C:\Users\sohan\Downloads\BattleCode_BC (Windows; heavy tooling lives in WSL Ubuntu: run with `wsl -d Ubuntu -- bash -lc '...'`; the repo is at /mnt/c/Users/sohan/Downloads/BattleCode_BC; the Loong game checkout is ~/the-loong-game). No memory of earlier work.

Read first: `research_new_meta/loong_blog/DIGEST.md` (sections (a), rule/engine changes 4-6, tools table: `reference/engine.h`, `just zig-judge-build -Dreference-source=...`, `--lockstep`), `research_new_meta/search_layer_plan.md` (engine port sections), `research_new_meta/engine_sim_status.md` and `tools/engine_sim.py` (our finished Python simulator, 100% round-exact on 4 replays: its rule implementation is the executable spec of the NEW rules), docs/ (execution-order.md, death.md, splitting.md, pearls.md), and blog posts 19-the-machine-inside-the-judge.md and 20-an-engine-on-the-gpu.md in ~/the-loong-game/blog.

## Goal
`engine_cpp/engine.hpp` (+ `engine_cpp/bench.cpp`, `engine_cpp/README.md`): a fast, branchable (cheap state copy), deterministic C++17 engine started from the repo's `reference/engine.h`, modified to the NEW rules: free steps ceil(L/4); queen = dragon id 0/1, round-500 queen length decides, a dead queen counts as 0, then longest, then total; sequential id-order execution with the board updated before the next dragon; pearl tick at round start; split/child ordering and sonar semantics per the digest. It must compile as plain C++17 with clang/g++ and be usable later inside a wasm bot (no exceptions/RTTI/iostream in engine.hpp, fixed-size arrays; 64x64 bound, up to ~128 dragon slots).

## Verification (report REAL output; a skipped game is not a pass)
1. Cross-check against tools/engine_sim.py on the same recorded actions: identical per-round state on the 4 replays that engine_sim_test.py uses (see how it loads them); report matched rounds.
2. Try the official lockstep tool: build the zig-judge with our reference (`just zig-judge-build -Dreference-source=/path/to/our_host.cc` from ~/the-loong-game; this needs a host adapter around engine.hpp, mirror how the existing reference host wraps engine.h) then `just zig-judge --engine ENGINE.wasm --lockstep /path/maps.txt --games 100 --seed 123`. If prerequisites (Nim>=2.2, Zig 0.16 at ~/toolchains/zig-linux, just, wasmtime headers) are missing or the build cannot be done in reasonable time, STOP that part and say exactly what is missing. Do not install system packages.
3. Benchmark: steps/second of engine.hpp (6-dragon and 60-dragon states, 3-round rollouts) vs tools/engine_sim.py; report the speedup.

Disk is limited (~6 GB): delete generated replays/build dirs you create when done; no .pkl; any games at -j 2.

## Report
Write `research_new_meta/engine_cpp_status.md` (what matches, what diverges, speed, blockers). Append ONE plain-ASCII UTF-8 line to AGENT_LOG.md using only an append (never rewrite it): `- [2026-10-02] [executor] [search_s1b_cpp] <match, lockstep result, speedup>`. Final message: <=10 lines.
