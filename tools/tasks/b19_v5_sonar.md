# Task b19_v5_sonar — fix queen-position starvation in vB19's sonar mesh

Repo: C:\Users\sohan\Downloads\BattleCode_BC (Battlecode "Loong" C++ bot). No memory of earlier work assumed.
Working dir: create `viper_b19_v5/` as a copy of `baselines/vB19/` (all files). Edit ONLY `viper_b19_v5/main.cpp`.
Never touch `baselines/` or other dirs.

## Suspected defect (verify it yourself in the code first; if it is not real, say so and change nothing)
vB19's sonar emit routine (search `Enemy Queen Alert` / `packEnemyQueenPos` / `Relay True Queen location`, near the
bottom of main.cpp, ~L1790-1840) does, in priority order: (1) true queen broadcasts her own position on all four
rays from round 100 and returns; (2) if `enemyQueenCell` was seen within 4 rounds, prints the enemy-queen alert on
ALL FOUR rays and `return`s; (3) otherwise relays the true-queen position. So whenever a dragon sees the enemy
queen, it stops relaying OUR queen's position to friends. Friends use `trueQueenCell` for feeding (tryFeed), for
the blind-portal landing penalty (`QPOS`, -60) and for queen-avoidance, so they go stale exactly when the queen is
in a fight.

## Change (if the defect is real)
In case (2), split the rays: print the enemy-queen alert on two rays and the true-queen relay (if
`trueQueenCell >= 0 && ROUND - trueQueenRound <= 6`) on the other two (choose the rays by `d % 2`, or the two that
the head is NOT facing; keep it simple and deterministic). If there is no fresh true-queen info, keep the old
behaviour (alert on all four). Check how the game's SONAR command works in docs/ (search `docs/` for "SONAR") to be
sure several SONAR lines in one turn are legal and cost nothing extra; report what the docs say.
Mark every edit `// V5`. No other changes, no reformatting.

## Verify (real output only)
- `uv run --python 3.11 --with unswbc python tools/buildwasm.py viper_b19_v5` succeeds.
- Smoke: `uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_b19_v5 baselines/vB19 out/b19v5_smoke --maps trauma --seeds 1 -j 2` produces replays.
  (Other panels are running; keep -j 2.)

## Report
Append to `AGENT_LOG.md` with >>: `- [2026-10-02] [executor] [b19_v5_sonar] <defect real? what changed, docs finding, build, smoke>`.
Final message: `diff --strip-trailing-cr baselines/vB19/main.cpp viper_b19_v5/main.cpp`.
