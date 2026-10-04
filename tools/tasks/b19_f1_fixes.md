# Task b19_f1_fixes — sign vB19's sonar packets with msgauth.hpp and fix two opening-split defects

Repo: C:\Users\sohan\Downloads\BattleCode_BC (UNSW Battlecode "Loong" C++ bot, built to wasm by `tools/buildwasm.py`).
You have no memory of earlier work. Work ONLY in `viper_b19_f1/` (a copy of `baselines/vB19/` plus `msgauth.hpp`).
Never touch `baselines/`, `archive/`, or other dirs. Edit only `viper_b19_f1/main.cpp` and `viper_b19_f1/msgauth.hpp`.
Run python as `uv run --python 3.11 --with unswbc python ...`. Never print or log secret key constants.

## Part A — authenticated sonar (QPOS and EQ packets)
Today vB19 sends sonar words with a constant 16-bit magic and a plaintext cell/round: `packTrueQueenPos`/`unpackTrueQueenPos`
(magic 0x5155) and `packEnemyQueenPos`/`unpackEnemyQueenPos` (magic 0xEC01), used by `updateSonarMesh()` (reads `V.msgs`) and
`castRadar()` (prints `SONAR <dir> <word>`). Public replays record every sonar word, and the docs say a sonar reaches dragons of
BOTH teams, so (1) the enemy can read and forge them and (2) our drones can adopt the ENEMY queen's position when the enemy runs
the same format. `viper_b19_f1/msgauth.hpp` (copied from an earlier attempt) provides `msgauth::seal(Msg, round)` and
`msgauth::open(word, now, Msg&)`: 24-bit SipHash MAC, XOR keystream, 23 data bits, round mixed into the MAC (receiver tries `now`
and `now-1`), sender id and ray `dir` in the clear. Read the file's header comment fully first.

1. Replace the two packet formats by msgauth messages: type `T_QUEEN` for our queen position (data = cell x (6 bits) | y (6 bits)),
   a different type (e.g. `T_GIANT` or add a new enum value <= 7) for the enemy-queen alert (same x,y; the `len` field is not used
   by any consumer: verify with grep and drop it). The `round` of the report is implied by the message round (receiver gets `now`
   or `now-1`): set `trueQueenRound`/`enemyQueenRound` from the round the MAC verified.
   Sender = `MY_ID`, `dir` = the ray the word is printed on (0..3; see `DCH[d]` order in `castRadar`).
2. Receiving: in `updateSonarMesh()` call `msgauth::open(v, ROUND, m)` for each word in `V.msgs`; ignore words that fail. Use
   `msgauth::Dedup` if cheap. Words from the enemy fail the MAC, so they can never move our queen state.
3. Generate a fresh random 128-bit `K0`,`K1` pair for `viper_b19_f1/msgauth.hpp` (replace the placeholder constants and remove the
   "REPLACE" marker comment; get randomness e.g. from `uv run --python 3.11 python -c "import secrets; print(secrets.token_hex(16))"`
   and write it straight into the file without echoing it to your report/log).
4. Also check the other sonar words in main.cpp: the PPROBE word (magic 0x5057) inherited from y7_12_49 is read at ~L1700 area
   (`(v >> 48) == 0x5057`) and written in the SONAR print with `probeDir`; if vB19's code path still sends/reads it, convert it the
   same way (data = x,y), else report that it is unused.
5. CPU: every received word costs ~2 SipHash calls per attempt. Measure on a smoke game (below). Our per-turn max CPU must stay
   under ~65M points, and report it. If cost is a problem, check only words whose `dir`/`type` fields are plausible before the MAC.
Mark edits `// F1`.

## Part B — opening-split defects (main.cpp ~L1590-1620, block starting `ROBUST OPENING SPLIT`)
`bool coiledMap = (W == 54 && H == 18) || (W == 32 && H == 16);` was meant to exclude Autarky (54x18) and Dilemma (32x16) but
Devil and Portals are ALSO 32x16, so Devil's L4 starting drones never get the opening split.
(1) Make the exclusion name-based using the map name that `activateMap` already knows (look for how `isDevil` is set from `nm`)
    so only autarky and dilemma are excluded; if the map name is unknown at round 0 on an unseen map, do not exclude.
(2) The tail check reads `nbr[tail * 4 + d]` with `tail = body[MY_LEN - 1]` WITHOUT checking `tail >= 0` (the body can contain -1
    for unseen cells on unseen maps), which is out-of-bounds. Add the same guard `swarmSplit()` uses (`for (int i = MY_LEN - 2; i < MY_LEN; i++) if (body[i] < 0) return/skip`)
    and check `MY_LEN >= 2`.
Mark edits `// F1`.

## Verify (report real output)
- `uv run --python 3.11 --with unswbc python tools/buildwasm.py viper_b19_f1` succeeds.
- Smoke games (keep -j 2): `uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_b19_f1 baselines/vB19 out/f1_smoke --maps trauma,devil --seeds 1 -j 2`.
  From the replays (see `tools/replay_lite.py` `decode_lite(path, {"dragonIndicator","roundStart","dragonSplit"})`; sonar words may not be
  decoded by it: if not, say so) confirm: (a) no crash, our CPU max < 65M; (b) on devil the opening split now happens at round 0 for
  length-4 drones of our team (count `dragonSplit` events at round 0 for our team on devil, f1 vs vB19 control games);
  (c) feeding/avoidance still works: count `FEED-QUEEN` indicators after round 320 on trauma (vB19 control had ~8).
- A forged/foreign word must be rejected: write a tiny standalone C++ or Python-free check in your head is not enough; instead add a
  one-line compile-time/unit self-test only if cheap (e.g. `static_assert` is not possible); otherwise state it is untested.

## Report
Append to `AGENT_LOG.md` with >>: `- [2026-10-02] [executor] [b19_f1_fixes] <what changed, build, CPU max, devil split counts, FEED-QUEEN count, untested items>` (no key material).
Final message: the diff `diff --strip-trailing-cr baselines/vB19/main.cpp viper_b19_f1/main.cpp` (do not include msgauth.hpp's key constants).
