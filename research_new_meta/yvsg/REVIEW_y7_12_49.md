# y7_12_49 vs s2_gP — code review + head-to-head (2026-10-01)

Correction to how this got labelled earlier in conversation: `bc-abyss-main` is **not** a teammate's
code — it's a public starter framework released by a different competing team ("Cat's paradise"). The
actual teammate baseline is `baselines/y7_12_49` ("Y.8m"), which is what this reviews.

## It's already ahead of s2_gP on the new rules

`y7_12_49`'s `main.cpp` (1766 lines vs s2_gP's ~1550) is tagged `// NEWRULES` throughout and has:

- `isTrueQueen()` = `MY_ID <= 1`, used as a hard gate in the death-penalty term (`+250` on pDeath, vs the
  `deathExtra=30` everyone else gets), an open-space requirement, "give way to the queen" movement
  ordering, and a blind-portal queen-ambush defense.
- The correct `ceil(L/4)` free-step formula (`(MY_LEN+3)/4`), applied consistently in `simulate()` and in
  the enemy-reach estimate `buildReaches()`.
- Crucially: it kept the **old dynamic "elected queen" gossip system** (`QueenInfo queen`, "the old
  election (longest dragon)") *separate* from the new rule-queen, with the comment "the true queen is
  protected separately." This is exactly the architecture our own `gQ`/`gQ2` patches got wrong — `gQ`
  collapsed the two into one id and broke all late-game feeding (`numbers.md` §6); `y7_12_49` never made
  that mistake.

This came from reading the code directly, not from the file's own comments' say-so — confirmed by grep
across the full file and a line-by-line read of the queen-handling functions.

## It has the same gap we found in s2_gP, with a precise cause

Ran 10 games (5 maps × both sides, new engine) between `y7_12_49` and `s2_gP`. **y7_12_49 won 6–4** — a
real edge, but small-sample (treat as "ahead," not "settled"). Full breakdown and `analyze.py` output in
`results.tsv` / `out.json` in this folder.

The more important finding is in the losses, not the win count. On `dilemma` and `slithery_fight`, **both
bots'** queens die at round 5 — same round, same cause pattern (`wall` for id 0, `self` for id 1),
regardless of which bot is playing which side. That ruled out a bot-specific logic bug and pointed at
something structural.

Root cause, confirmed by reading the exact gating code:

```cpp
static bool protectedQueen() { return !bigFeed && ROUND >= P.protectFrom && (queen.id == MY_ID || MY_LEN >= queen.len) && MY_LEN >= (ROUND >= 400 ? 6 : 4); }
...
if (!protectedQueen() && (...) && swarmSplit()) return;   // the ONLY guard on voluntary budding
```

`protectedQueen()` is the *only* thing stopping `swarmSplit()` (the length-4+ auto-bud-a-child-off
routine) from touching the true queen. It requires `ROUND >= P.protectFrom` (340, or never at all on
`bigFeed` maps — and `slithery_fight` is in the `bigFeed` set). Every map we tested spawns the queen at
length 3–4 **except** `dilemma` (length 11) and `slithery_fight` (length 7) — both already at or above
`P.budAt = 4`. So on those two maps specifically, `swarmSplit()`'s length check fires at round 0, before
any protection exists, and buds the queen down to nothing within a handful of rounds — then she dies at
the resulting tiny length. Checked map starting lengths across 8 maps to confirm the correlation holds
(table in this folder's session log): only the two over-length-4 starting queens show this failure.

**This is the same class of bug numbers.md flagged in s2_gP** (queen protection that only switches on
late-game), independently present in a more sophisticated codebase, and now root-caused precisely enough
to fix directly: `protectedQueen()` conflates two different things — "never split, you're the end-game
consolidation sink" (fine to gate on `protectFrom`) and "never bud the rule-queen, ever" (should be
unconditional on `isTrueQueen()`, independent of round or `bigFeed`). The fix is a one-line split of that
condition, not a new system.

## Worth doing next

1. **Fix is identical in both codebases**: gate `swarmSplit()` (and ideally `trySplit`/`doomedSplit`) with
   `!isTrueQueen() || protectedQueen()` rather than `protectedQueen()` alone. Cheap, ~2 lines, testable
   immediately against the same 10-game set.
2. **Worth pulling `y7_12_49`'s architecture pattern into `s2_gP`**: the separate old-election/true-queen
   split is the right shape and avoids the gQ/gQ2 failure mode entirely — this is more valuable than any
   single tuning number in the file.
3. Full main.cpp diff is in `baselines/y7_12_49/` vs `baselines/s2_gP/` in the workspace if a deeper
   standards-style review is wanted later; this pass focused on the queen-rule-relevant paths only, per
   token budget.
