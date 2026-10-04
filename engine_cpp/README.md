# New-rules C++ forward engine (2026-10-02)

`engine.hpp` derives from Loong's MIT reference engine.h, retaining its
linked-cell bodies, topology, split/child queue, mt19937_64 spawning and
sonar implementation. Changes: fixed ceil(initial length/4) free steps;
round-500 queen ID 0/1 (dead = zero), then longest, then total scoring;
shared immutable map; larger action capacity; direction prevalidation.
No heap, exceptions, RTTI or iostream occur in the header. `host.cc` uses
the native standard library for loading maps and the official lockstep C API.

## API and branching

For native tools, `loong::LoadMap(game, map, text)` is defined by host.cc.
A bot constructs fixed-array Map/Game directly, without linking host.cc.

```cpp
#include "host.cc" // native loading only
loong::Map map{};
loong::Game game{};
auto error = loong::LoadMap(game, map, mapText);
if (!error.empty()) { /* handle invalid map */ }
loong::Begin(game, seed);
loong::Game branch = game; // no allocation, shared immutable map
int slot = loong::Advance(branch);
if (slot >= 0) {
    loong::Action a{};
    a.kind = loong::MOVE;
    a.steps = 1;
    a.step[0] = loong::E;
    loong::Act(branch, a);
}
```

Map must outlive every branch and must remain immutable after loading.
Read observations before Act clears the acting dragon's inbox. Advance
starts/ticks rounds, skips dead/stale queued turns and resolves completed
rounds; Act consumes the current live turn. Begin starts at round 0 before
the pearl tick, whereas Python's initial last-completed round is -1.
StartRound/Act/EndRound permit explicit full-round rollouts, as bench.cpp
demonstrates; skip dead/stale queue entries by both slot AND ID. Dragon IDs
are not reusable array slots. Split children append to this round's queue.
Cell links give constant-time collision and tail operations.

The native Game value copy is 121,328 bytes; Map is 94,224 shared bytes.
Game includes full RNG state and 64 sonar messages per slot, and is larger
than the plan's estimate. Bounds: 64x64, 128 reusable slots, 512 turn entries,
64 inbox messages, 10,240 directions/action (covers a 10 KiB judge reply).
The action count is uint16_t. Validate caller lengths before constructing
an action. Nonzero overflow invalidates a run. The native loader retains
the upstream valid-map contract; do not pass invalid geometry.

## Reproduce

```sh
clang++ -std=c++17 -O3 -fno-exceptions -fno-rtti engine_cpp/bench.cpp -o /tmp/engine-bench
clang++ -std=c++17 -O3 -shared -fPIC engine_cpp/bridge.cpp -o /tmp/libengine.so
clang++ -std=c++17 -O2 engine_cpp/scenarios.cpp -o /tmp/scenarios
/tmp/scenarios
python3 engine_cpp/bench.py /tmp/engine-bench
python3 engine_cpp/seeded_test.py /tmp/libengine.so /tmp/seeded
python3 engine_cpp/verify.py /tmp/replays --export /tmp/fixtures
python3 engine_cpp/verify.py --library /tmp/libengine.so --fixtures /tmp/fixtures
```

This machine used `~/toolchains/zig-linux/zig c++` (bundled Clang) and
RAM scratch with ZIG_GLOBAL_CACHE_DIR set there. Separate g++/clang++ were
absent, so g++ was not independently tested. The header also compiled for
wasm32-freestanding with -fno-exceptions -fno-rtti; wasm_check.cpp is the probe.

Regenerate the four fixtures with existing Zig judge, official engine,
default/trauma, seed 1, both sides, cached viper_b19_f1-676acfa38c240266.wasm
vs vB19-4c23c57aea0e3e6f.wasm, --debug 2, --replay PATH. Run sequentially,
never above two games. verify.py export first runs the existing Python
replay oracle (ordered rule events and terminal standings), then writes
Python full-state snapshots on the same actions/spawn inputs. Comparison
checks all bodies, teams, facing, deaths/reasons, pearls, countdowns,
turn order, terminal status/winner without resynchronisation. Exactly four
nonempty games must match; zero games or skips fail.

Replay spawning/countdown resets are exogenous. seeded_test.py separately
compares natural spawning and initial countdowns without injection.
Python excludes sonar/protocol, so replay parity does too; scenarios.cpp
checks sonar behavior but does not prove official observation parity.

Official lockstep now passes 100/100 games (14,264 turns) against unswbc
1.2.7. Use the exact separate-output build/verification recipe in
[engine_cpp_status.md](../research_new_meta/engine_cpp_status.md#search_followup-official-lockstep-2026-10-02)
and the checked-in lockstep_maps.txt. The setup report's ~/venv engine is
old-rule unswbc1.2.2; use the recorded1.2.7 engine hash/path. Terminal
queen/longest fields are not independently compared by upstream lockstep.
See research_new_meta/engine_cpp_status.md for measured results, limits and
scratch loss. Compact JSON records retain actual tool-output measurements.
