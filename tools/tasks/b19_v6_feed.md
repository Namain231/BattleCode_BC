# Task b19_v6_feed — restore suicide-feeding to the true queen in vB19

Repo: C:\Users\sohan\Downloads\BattleCode_BC (Battlecode "Loong" C++ bot). No memory of earlier work assumed.
Working dir: create `viper_b19_v6/` as a copy of `baselines/vB19/` (all files). Edit ONLY `viper_b19_v6/main.cpp`.
Never touch `baselines/` or other dirs.

## Defect (an audit found it; VERIFY it by reading the code before changing anything)
In `tryFeed()` (~L1500-1520) vB19 computes `int d = distA[dr.headCell]` for the true queen's head and requires
`d > 0 && d <= 3` before it prints `SPLIT 1` (the deliberate "die and become pearls next to her" move). But the
queen's head cell is occupied by her body, and the BFS that fills `distA` skips cells whose `otherBT >= nd`
(~L984, with `otherBT[head] ~ her length`, ~L622), so `distA[queen head]` is -1 for a queen longer than ~2 and the
branch never fires. The original y7_12_49 used `torusDist(dr.headCell, body[0]) <= 3`
(`baselines/y7_12_49/main.cpp`, search `FEED`/`tryFeed`). Result: from round 320 drones home next to her but never
feed.

## Change (if real)
Replace the distance test with `torusDist(dr.headCell, body[0]) <= 3` (keep `> 0`-style non-zero check if needed so a
drone on her head cell is excluded). Keep every other condition (`UNITS <= 10` floor, `ROUND < P.feedFrom`, the
`trueQueenRound` staleness check, `feedRadius`, STRICTLY-true-queen filter). Also check the sibling use at
~L1673-1686 (homing goal `distA[trueQueenCell]` / `distA[enemyQueenCell]`): if the same -1 problem makes the
homing goal inert or wrong, report it but change ONLY tryFeed unless the fix is a one-liner of the same kind
(then fix it and mark `// V6b`). Mark edits `// V6`. No reformatting.

## Verify (real output only)
- `uv run --python 3.11 --with unswbc python tools/buildwasm.py viper_b19_v6` succeeds.
- Prove the branch now fires: `uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_b19_v6 baselines/vB19 out/b19v6_smoke --maps trauma --seeds 1 -j 2`
  then decode the replays (see `tools/replay_lite.py` `decode_lite(path, {"dragonIndicator","roundStart"})`) and count
  `FEED-QUEEN` indicator events per side after round 320. Report the counts for the v6 side vs the vB19 side
  (expected: v6 > 0, vB19 ~ 0). If games end before round 320, say so and use another map or seed 2.
  Keep panels at -j 2 (another panel is running).

## Report
Append to `AGENT_LOG.md` with >>: `- [2026-10-02] [executor] [b19_v6_feed] <defect real?, change, build, FEED-QUEEN counts>`.
Final message: `diff --strip-trailing-cr baselines/vB19/main.cpp viper_b19_v6/main.cpp` plus the counts.
