# Python forward simulator S1 status (2026-10-02)

Implemented tools/engine_sim.py and tools/engine_sim_test.py. The requested
oracle gate passes: **1888/1888 exact rounds (100%)**,
72,373 dragon-turns across four newly generated official Zig-judge games.
No first divergence in any game. Terminal winners and count/longest/total
standings also agree. The oracle never resynchronises a divergent state.

| Game | Exact rounds | Dragon-turns | us/round | First divergence |
|---|---:|---:|---:|---|
| default_1_A.replay | 388/388 | 16996 | 719.7 | none |
| default_1_B.replay | 500/500 | 19576 | 761.2 | none |
| trauma_1_A.replay | 500/500 | 17723 | 658.4 | none |
| trauma_1_B.replay | 500/500 | 18078 | 713.1 | none |

Measured on Windows with uv Python 3.11: **712.7
microseconds per copied full-round step**, **18.6
microseconds per dragon-turn amortised**. Timing includes copying, ticking,
actions, collision checks, death drops, split children, and event creation;
excludes replay decoding and oracle reconstruction. This is a Python
measurement, not an estimate of C++ wasm CPU points.

## Rules and interface

load_map(text, seed=1) returns initial State with round=-1. step(state,
actions, spawn_input=None) returns a new state after the next zero-based
round. A mapping supplies replay-style action dictionaries (act/dirs/size);
a callable receives current state and dragon ID, including newborns.
Missing action means suicide. Mutable bodies, pearls, countdowns, and RNG
are copied; immutable precomputed map topology is shared.

Moves run **sequentially in ascending dragon ID**, following the official
execution order. They are not simultaneous. Split children act this round.
Free-step allowance ceil(initial length/4) is fixed throughout each move.
Own tail is checked before tail advance; head-on kills the other dragon
first; paid steps check ability to pay before movement. Death pearls use
the current body. Round index 499 is the 500th round; queen length,
longest living dragon, then total length resolve its tiebreak.

Expected bodies are rebuilt from every individual recorded dragonUpdate,
inserting that update's head and trimming through its tail. Complete split
bodies and death reasons come directly from events. Ordered move/split/death/
tile events plus full bodies, lengths, facing, deaths, pearl set and countdown
state are compared each round. rulemine/state.py is never imported.
tools/replay_lite.py now decodes pearlCountdown, without pickle caches.

## Sources and limits

Read the search plan simulator/oracle and S1/S2 sections, local rules,
Loong blog posts 20 (engine), 26 (planning), and 29 (rule change), and the
runtime/gamedata/harness/replay source layout. DIGEST.md does not exist.
The released harness/zig_judge/reference/engine.h supplies topology,
movement, splitting, death and seeded symmetric spawning. Its Move and
EndRound still use old rules; this implementation applies the current
documented free-step and queen rules. Its MIT notice is retained.

Replay initial countdowns, round-start spawns and countdown resets are
exogenous oracle inputs. Eating and death drops are simulated and checked,
never injected. Standalone seeded RNG/spawning is implemented from the
reference, but exact seeded spawn parity with today's official wasm is
**not established** by these tests. Sonar, bot output parsing and instruction
metering are outside this forward-state simulator; feed their resulting
actions (or missing actions) to step.

Crafted assertion tests passed: branching, sprint payment and current-body
drops, own-tail collision, head-on death order, split child turn/wrap,
illegal split/no action, fixed free allowance after growth, length-five
free steps, team unit cap, kelp, portal direction in a sprint, body collision,
queen priority over a longer drone, longest tiebreak, symmetric blocked
spawn reset, and seeded branch reproducibility. These are simulator tests,
not official-engine crafted-map differential tests.

The four-game task gate is met. The plan's larger S1 milestone (40 local +
20 public games) and S1b official-engine edge-case suite remain unvalidated;
no claim is made that the broader milestone is complete. Existing out/sw_0
and ladder/scout_v6 contain no replay files to reuse. S2 tactical ceiling
analysis and the C++ port are subsequent work.

## Reproduction and cleanup

Generate:
uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_b19_f1 baselines/vB19 out/sim_oracle --maps trauma,default --seeds 1 -j 2

Check:
uv run --python 3.11 python tools/engine_sim_test.py out/sim_oracle --json out/sim_oracle/parity.json

Scenario-only check:
uv run --python 3.11 python tools/engine_sim_test.py

Deleted only the four generated out/sim_oracle/*.replay files after saving
the compact parity.json and summary.json reports (about 16 MB reclaimed).
No .pkl caches were generated. No bots or baselines were changed.
