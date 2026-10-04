# Task swarmsplit_fix

Repo: C:\Users\sohan\Downloads\BattleCode_BC (Battlecode "Loong" snake-game bot, C++ in `viper_s2_fix/main.cpp`).
Work ONLY in `viper_s2_fix/` (a copy of `baselines/s2_gP`). Do not touch `baselines/` or any other dir.

## Bug
`swarmSplit()` (auto-budding at length >= P.budAt) can bud the true queen (dragon id 0 or 1) to death around
round 5 on maps where the queen starts at length > 4 (`dilemma`, `slithery_fight`). At the call site (~line 1507):

    if (!protectedQueen() && (opts[0].ev.pDeath < 0.5 || ...) && !opts[0].ev.adjacent && swarmSplit()) return;

`protectedQueen()` only becomes true from `P.protectFrom`, so early on the true queen is not protected.

## Change
1. Add near the other helpers (before first use): `static inline bool isTrueQueen() { return MY_ID <= 1; }`
   (queens are ids 0 and 1; which team owns id 0 depends on the map). Reference implementation:
   `baselines/y7_12_49/main.cpp` line 92.
2. At that call site change the guard from `!protectedQueen()` to `(!isTrueQueen() || protectedQueen())`
   for the `swarmSplit()` line ONLY. Leave the `trySplit` line and every other use alone.
3. Mark the edits with a `// QSPLIT` comment, matching how y7_12_49 uses `// NEWRULES`.
4. Do not change anything else. Do not reformat.

## Verify (report results, do not claim what you did not run)
- Confirm MY_ID is declared before your helper (compile-order).
- Compile check: `uv run --python 3.11 --with unswbc python tools/buildwasm.py viper_s2_fix` must succeed.
- Do NOT run game panels; the director does that.

## Report
Append one line to the "### Log" section at the bottom of `AGENTS.md`:
`- [2026-10-02] [executor] [swarmsplit_fix] <files changed, build result, anything unverified>`
