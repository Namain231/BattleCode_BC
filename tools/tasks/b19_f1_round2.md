# Task b19_f1_round2 — fix review findings in viper_b19_f1 (sealed sonar for vB19)

Repo: C:\Users\sohan\Downloads\BattleCode_BC. No memory of earlier work assumed. Work ONLY in `viper_b19_f1/` (edit `main.cpp`, `msgauth.hpp`).
Never touch `baselines/`, `archive/`. Python: `uv run --python 3.11 --with unswbc python ...`. Never print key constants (K0/K1) in your report.
Read first: `tools/tasks/b19_f1_fixes.md` (round-1 task), the latest `tools/tasks/b19_f1_fixes.*.critique.log` and `.exec.log`, and
`diff --strip-trailing-cr baselines/vB19/main.cpp viper_b19_f1/main.cpp`. Round 1 sealed QPOS/EQ/PPROBE words with msgauth.hpp. The critic found:

1. RELAY FRESHNESS BUG (material): `packPosition()` seals with `ROUND`, and receivers set `trueQueenRound`/`enemyQueenRound` from the
   MAC-verified round, so a RELAYED report is re-stamped as fresh. Obsolete enemy-queen alerts can circulate forever (suppressing queen relays
   and probes) and old queen positions look new. FIX: put the report's age in the data bits (data has 23 bits: cell x 6 + y 6 = 12; use up to
   4-5 bits for `age = min(15 or 31, ROUND - reportRound)` of the ORIGINAL observation), the receiver computes `reportRound = verifiedRound - age`,
   drops reports older than the existing limits (<=6 for queen relay use, <=4 for EQ), and relayers increment the age instead of resetting it.
   A report must never become fresher by being relayed.
2. BEHAVIOUR REGRESSION CHECK: round-1 smoke on Trauma counted FEED-QUEEN indicators after round 320: candidate 0 vs control 5 (and 0/0 in another
   pair). Find out whether the signed relay broke queen-position delivery (feeding needs `trueQueenCell` fresh within 25-30 rounds). Diagnose with a
   short game (decode_lite on the replay: `dragonIndicator` events with FEED-QUEEN, and add a temporary indicator/printf of `trueQueenRound` age if
   needed; remove debug afterwards). Fix the cause. State the result with counts over >= 2 seeds x both sides on trauma (candidate vs vB19 control).
3. CPU: round 1 reported 61.1M points per-turn max (near the ~65M safe cap, 100M hard cap). Find which dragon/turn it is (the panel_zig output
   lists CPU as mean/p50/max style triples per side; the per-turn max of OUR side only) and whether the new MAC checks add to it versus the control
   (vB19 vs vB19 gives the baseline). If our added cost matters, cheapen it: reject words whose type/dir fields are implausible before the MAC;
   cap words examined per turn.
4. "invalid-action deaths" in the smoke report: check that they are not caused by the new code (e.g. a malformed SONAR line) by looking at the death
   reasons for our dragons in f1 games vs control games.
5. Confirm by grep that nothing else reads the old unsigned queen/election formats, and show the grep output in your report.
6. Provide a small standalone native C++ test file `viper_b19_f1/msgauth_test.cpp` (NOT included by main.cpp; compile with the judge clang or
   `clang++`/`g++` if available; if no compiler is on PATH say so) that checks: seal/open round-trip, rejection of a flipped bit, rejection of a
   word replayed 3 rounds later, acceptance within 2 rounds. Run it and show the output. Never print K0/K1.
Mark new edits `// F1b`.

## Verify (real output, no claims you did not run; panels at -j 2)
- build: `uv run --python 3.11 --with unswbc python tools/buildwasm.py viper_b19_f1`
- games: `uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_b19_f1 baselines/vB19 out/f1b_smoke --maps trauma,devil --seeds 1,2 -j 2`

## Report
Append to `AGENT_LOG.md` with >>: `- [2026-10-02] [executor] [b19_f1_round2] <findings per item 1-6 with numbers>` (no key material).
Final message: per-item results and the diff of your changes (omit key constants).
