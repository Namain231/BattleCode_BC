# Task port1_movement — port the new-rules MOVEMENT model from y7_12_49 into a copy of s2_gP

Repo: C:\Users\sohan\Downloads\BattleCode_BC (Battlecode "Loong" bot, C++). You have no memory of earlier work.

New rules (2026-10-01): a dragon of current length L gets `ceil(L/4)` = `(L+3)/4` free steps per turn
(sprinting); old code assumes 1 step/turn. `baselines/s2_gP/main.cpp` is the old-model bot;
`baselines/y7_12_49/main.cpp` is a teammate's bot that already models the new rules. Port ONLY the movement
model, not the strategy.

## Working dir
Create `viper_port1/` as a copy of `baselines/s2_gP/` (all files: main.cpp, bot.toml, maps_data.hpp,
policy_nn.hpp, policy_weights.hpp, README.md). Edit only `viper_port1/main.cpp`. Never touch `baselines/`.

## What to port (use `diff baselines/s2_gP/main.cpp baselines/y7_12_49/main.cpp` as the spec)
1. `simulate()` (~L690-710 in s2_gP): add `const int freeSteps = max(1, (MY_LEN + 3) / 4);` and replace the two
   `j > 0` conditions (`r.len < 3` death test; `body.pop_back(); r.len--`) with `(int)j >= freeSteps`, exactly as y7_12_49.
2. Enemy reach (~L735-745 in s2_gP): per enemy `spd = max(1, (dr.estLen + 3) / 4)`, loop `depth <= 3 * spd`, and
   record `(depth + spd - 1) / spd` as the arrival time, exactly as y7_12_49.
3. FSPRINT: the multi-step free-path option search block in the main decision (y7_12_49 ~L1560-1589, tagged
   `// FSPRINT`), replacing s2_gP's `if (MY_LEN >= 8 && !endgame()) {... threat ...}` two-step block. Keep the
   evaluate/sort structure consistent: in y7_12_49 `for (auto& o : opts) o.ev = evaluate(o.sim, true);` moves after
   the path search. Do NOT port the PPROBE block that follows it (probeDir/probeCell/ECHO/SONAR warn) — leave it out.
4. Do NOT port: isTrueQueen scoring/guards, QHIDE, COMPASS, MAPFIX, CX, PRESS2, SPRINT2, SHAFT, FLOOR, PPROBE,
   protectFrom change. Another stage handles those.
5. Mark every edited line with `// PORT1`. Do not reformat anything else.

## Verify (run these; report real output, do not claim what you did not run)
- Build: `uv run --python 3.11 --with unswbc python tools/buildwasm.py viper_port1` must succeed.
- Smoke: `uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_port1 baselines/y7_12_49 out/port1_smoke --maps default --seeds 1 -j 2`
  must produce two replays and a summary (takes ~1-2 min). Check the CPU column: per-turn max must stay under
  ~65M points (the bot's elapsedMs guards exist; the new path search is the risk). Report the numbers.

## Report
Append one line to `AGENT_LOG.md` (use >>): `- [2026-10-02] [executor] [port1_movement] <files, build result, smoke result, CPU max, anything unverified>`.
Final message: the full `diff baselines/s2_gP/main.cpp viper_port1/main.cpp`.
