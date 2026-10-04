# C++ forward engine S1b status (2026-10-02)

Implemented engine_cpp/engine.hpp, bench.cpp, README.md, native reference
host adapter and reproducible verification. Independent critic verdict:
PASS for implementation and differential checks. Official lockstep passes 100/100 games against unswbc 1.2.7: 14,264 turns, zero divergences/skips, ten live maps. This verifies observations, turn IDs and terminal winner/counts/totals; terminal queen/longest fields are not independently compared.

## Actual replay results

| Regenerated replay | Matched C++ rounds | First divergence |
|---|---:|---|
| default_1_A | 388/388 | none |
| default_1_B | 500/500 | none |
| trauma_1_A | 500/500 | none |
| trauma_1_B | 500/500 | none |

**1888/1888 rounds; zero divergences, zero skipped games.** Python's existing
engine_sim_test.check_game separately matched the same 1888 rounds against
the official replay, including ordered rule events and terminal standings.
C++ receives the same recorded actions and initial/countdown/spawn inputs
as Python; compares full living bodies/team/facing, historical deaths and
reasons, pearl set, every countdown, acting-ID order, round, terminal status
and winner after each round. No movement/death outputs are injected; no
resynchronisation. Critic independently reran the C++ check, 1888/1888.

S1's original four replays were deleted. We regenerated the same maps,
seed 1, sides and cached bots (viper_b19_f1-676acfa38c240266.wasm vs
vB19-4c23c57aea0e3e6f.wasm). Round counts equal S1's record; byte identity
with the deleted originals cannot be established. Every judge game exited
0; total replay size 15,549,267 bytes. A uv cache engine vanished externally
after the default games. One trauma attempt failed FileNotFound, then both
trauma games succeeded using preserved local unswbc 1.2.7. Default engine
hash was not recorded, so engine continuity is unproven. Trauma engine:
SHA256 26e68680e45eb0f221db702aead9eefde776c2ad2ba066f4ddf8c12500c6a546.

## Extra verification

- Standalone initial countdowns/natural pearl ticks match Python **62/62**
  rounds (dense beds 12, separated beds 50), without spawn/reset injection.
  Critic independently reran 62/62. This is Python differential evidence,
  not official seeded-spawn proof.
- Crafted C++ scenario executable passed: value-copy branch isolation,
  length-five free steps, fixed quota after growth, paid-step death/current
  body drops, own-tail/head collision, same-round child turn/wrap,
  queen/ties/dead-queen-slot scoring, sonar delivery/clearing and tail ray,
  deterministic seeded branching.
- Clang bundled with Zig 0.16 compiled C++17; bench/core built with
  -fno-exceptions -fno-rtti. wasm32-freestanding engine object compiled
  successfully, 36,438 bytes. Compile usability is not wasm runtime parity
  or competition CPU measurement. Separate g++/clang++ are absent.

## Actual benchmark: three-round branches

| Dragons | C++ rounds/s | C++ move steps/s | Python rounds/s | Python move steps/s | Speedup |
|---:|---:|---:|---:|---:|---:|
| 6 | 54,535 | 327,208 | 1,247 | 7,484 | 43.72x |
| 60 | 39,409 | 2,364,528 | 1,098 | 65,855 | 35.90x |

WSL Ubuntu, identical 64x64 states: four-segment dragons on separate rows,
no pearl beds, one east move per dragon/round. Thus move steps/s also means
dragon turns/s here. Three trials; median rates; C++ 100,000 three-round
rollouts/trial, Python 300. Copies, ticks, actions, collisions and terminal
checks included, parsing excluded. Python's production API also constructs
rule events; C++ uses outcome counts. This measures actual forward API
throughput, not identical event-logging workloads or full matches. Volatile
checksum consumption prevents dead-code elimination. Raw timing values from
actual tool stdout are saved in engine_cpp/benchmark_results.json. Critic
reviewed the 6-dragon row; the root captured both final rows before scratch
loss. No wasm speedup or CPU-points claim.

Value-copy Game is 121,328 bytes, including full RNG/inboxes; immutable
Map is 94,224 bytes shared by pointer. No allocation per branch, but this is
larger than the search plan's estimate. Actual copy cost is in the benchmark.

## Historical official lockstep blocker (superseded by followup)

At the original S1b run, WSL `command -v nim just` returned neither; neither was found in
~/toolchains. **Nim >=2.2 and just were then missing; setup now resolved this.** Zig at
~/toolchains/zig-linux reports 0.16.0; Wasmtime C headers exist in v27/v49
local toolchains. Per task instruction, stopped this part at the prerequisite
check without installing packages. No replacement judge build, no 100-game
lockstep execution, zero official lockstep games verified. host.cc mirrors
the released reference C interface; README contains the required commands.

## Limits, provenance and cleanup

Replay checks supply pearl spawns/reset countdowns and exclude sonar/protocol
because engine_sim.py has neither. The reference sonar code has crafted
checks; official observation lockstep was then pending and now passes as below. No observed divergence
within tested scopes. Bounds: 64x64, 128 reusable dragon slots, 512 queued
turns, 64 inbox messages, 10,240 directions/action. Any overflow invalidates
checks. Queens are identified by ID rather than a reused slot. Caller/host
map geometry must be valid; directions are prevalidated before movement.

All large generated files were under /dev/shm/search_s1b_cpp. After the
runner and critic checks and final benchmarks, that RAM directory disappeared
externally before archival (cause unconfirmed). Its absence and empty
/dev/shm were checked. Consequently raw logs, fixture files and replay hashes
are unavailable; compact JSON records reconstruct the actual captured tool
outputs, rather than pretending the original files survived. Final source
hash and known engine hash are in provenance.json. All generated replays,
objects, executables/build caches are gone. No pickle caches were created.
Games ran sequentially, maximum two permitted. No package installs, bot
changes or ladder submissions. C: initially had 103 MB free; large artifacts
were written to RAM instead. Final observed C: free space 2.9 GB.
AGENT_LOG receives exactly one append-only executor line.

## search_followup official lockstep (2026-10-02)

PASS: **100 games the same, 0 differ, 0 skipped, 14,264 turns compared**.
Ten live maps in engine_cpp/lockstep_maps.txt, each ten games, seeds 123..222.
No engine_cpp gameplay or host changes were needed. The reference adapter
compiled with the installed Zig0.16/Wasmtime49 toolchain into a separate
~/toolchains/zig-judge-out-s1b directory, build parallelism -j2. Games were
sequential. No replay/pickle files were written.

Important version correction: the setup report's ~/venv engine is unswbc
1.2.2 (Sep29). An initial actual 100-game run against it yielded 90 same,
10 differ, 0 skipped, 13,069 compared turns. First difference: Portals
seed123, turn46, round9, dragon4 observation contained an extra enemy tail
at (9,0) in our engine. Other differences showed length5 vs official4 after
sprints, consistent with the old free-step rule. This is incompatible rule
version evidence, not a defect to fix by reverting our new-rule engine.

The correct current oracle was found beside unswbc-1.2.7.dist-info:
/mnt/c/Users/sohan/AppData/Local/uv/cache/archive-v0/4Hmu77GCQL90pPgp/Lib/site-packages/unswbc/unswbc_engine.wasm
SHA256: 26e68680e45eb0f221db702aead9eefde776c2ad2ba066f4ddf8c12500c6a546.
The second 100-game run against this oracle exited0 with the PASS above.
This is the same recorded engine hash as the earlier trauma replay tests.

Exact build and verification:
```bash
cd ~/the-loong-game/examples/tooling
just zig-judge-build -j2 --prefix /home/sohan/toolchains/zig-judge-out-s1b -Dreference-source=/mnt/c/Users/sohan/Downloads/BattleCode_BC/engine_cpp/host.cc
/home/sohan/toolchains/zig-judge-out-s1b/bin/loong-judge --engine /mnt/c/Users/sohan/AppData/Local/uv/cache/archive-v0/4Hmu77GCQL90pPgp/Lib/site-packages/unswbc/unswbc_engine.wasm --lockstep /mnt/c/Users/sohan/Downloads/BattleCode_BC/engine_cpp/lockstep_maps.txt --games 100 --seed 123
```
The direct judge call is equivalent to the just zig-judge wrapper and
selects the separate output explicitly. lockstep_results.json retains
captured summary counts and provenance.

Scope: byte-for-byte observations (including sonar/protocol), turn IDs,
end timing, winner, reason, terminal living counts/total lengths and no
array overflow. The upstream lockstep code does NOT compare terminal
queen lengths or longest fields independently; random games are short
and do not demonstrate round500 queen scoring. Earlier crafted scoring
checks remain the evidence for that part.
C: checks were3.79GiB before,3.43GiB after build,3.36GiB during verification;
all above1.5GB floor. Only the separate judge output is disposable;
shared checkout build caches and unrelated artifacts are preserved.
Critic followup verdict: PASS within the reported lockstep scope. After review,
removed only /home/sohan/toolchains/zig-judge-out-s1b (resolved absolute path
verified first); shared caches and rebuilt serve judge preserved. C: free3.33GiB
before cleanup. Rebuild the separate reference output before rerunning.
