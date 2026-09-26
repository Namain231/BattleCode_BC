# AGENTS.md — working on this repo

Hand-off guide for any agent (or person) continuing the UNSW Battlecode work.
Read this first, then `INSIGHTS_AND_PLAYBOOK.md` (the long-form record of what we learned and why).
**Keep both files updated** whenever you change the bot, learn something about the game, or submit.

## Current state (update this block every time you submit)

| | |
|---|---|
| Team | Bhole Chature (team id 98), members Namain231 (leader), forcefullegend, yashguy65, SoHanSolo |
| Active submission | `v7.2-partial-feed` (id 7741), source in `viper_v7/` |
| Previous good builds | `v6.6-danger-split` (7682, source = `viper_v6/` minus later V6 edits), `v7.1-feed` (7726) |
| Rating | ~1428 (rank ~290 of 851) as of 2026-09-27; top of ladder ~2124 |
| Live map pool | Portals, Slithery Fight, Schooltime, Trophy, Queen Of Spades, Default, Prisoners Dilemma, Autarky, Devil, Trauma |

Latest ladder measurements (unranked, 10 maps): V7.x vs Aviators 5/10, Give me a job 6/10, hmm 6/10; vs the top three (龙虎豹, 中国人能飞, Sponge) 0/10 each.

## Secrets

- The contest API key is in `secrets.env` (repo is private; **never make this repo public without deleting that file and rotating the key** on the team page).
- `unswbc submit` uses the key stored by `unswbc auth set <key>`; the API scripts in `tools/` read `UNSWBC_KEY`:
  `export $(cat secrets.env | xargs)` in bash before running them.

## Repo layout

| Path | What |
|---|---|
| `viper_v7/` | **Current bot** (C++). `main.cpp` + generated `maps_data.hpp` + `bot.toml`. |
| `viper_v6/` | Previous C++ generation (single-dragon survival engine; V7 is V6 + swarm macro). |
| `viper_bot`, `viper_v2`…`viper_v5` | Old Python bots (V1–V5), kept as sparring partners. |
| `swarm_bot/` | Python stand-in for ladder swarms (V3 that splits pairs at every chance). Slow in the sandbox. |
| `starter_bot/` | The toolkit's starter. |
| `maps/` | Local maps: the 13 bundled ones plus `portals.map`, `slithery_fight.map` pulled from `/maps`. |
| `docs/` | Scraped game docs (mechanics, protocol, timeouts, API). |
| `tools/` | Test, analysis and ladder scripts (below). |
| `ladder/`, `replays/` | Local data (gitignored): downloaded replays, scouting data, reports. |

## The bot in one page (`viper_v7/main.cpp`)

Each dragon is its own process; per turn: parse the 7x7 view → update persistent memory → decide one action.
- **Knowledge**: edges/portals from vision, validated embedded maps (`maps_data.hpp`, regenerate with `python tools/gen_maps.py` after adding maps), pearl countdown memory, memory of unseen bodies (`memExpire`), sonar radar/gossip.
- **Own body**: vision chain + tracked history; own visible segments that cannot be ordered become walls (`ownLost`).
- **Evaluation** (`evaluate`): growth, pearl field (`pearlProb`, farm bonus for fast tiles), committed goal progress, head-on danger (incl. enemy sprint reach, unit value), survival (Voronoi static room, then optimistic + pessimistic DFS), corridor risk, pocket penalty. Options are ordered lexicographically by a coarse safety class, then score.
- **Actions, in priority order** (`think`): feed (late game) → doomed/danger escape splits (`doomedSplit`) → guaranteed head-on trades (`findAttack`) → swarm budding (`swarmSplit`) → other splits (`trySplit`) → best move (plus escape sprints when doomed).
- **Swarm macro** (V7): bud a length-2 child at length 4 until round 330 (`budAt`, `budUntil`); from round 300 every dragon gossips the best-known queen (longest dragon) over sonar (`packQueen`); from round 350 drones within 10 tiles of the queen walk to her and die on purpose (`tryFeed`, illegal `SPLIT 1`) so their bodies become pearls in her path.
- All tunables are in `struct Params` at the top of `main.cpp`.

## Workflow

**Build/run** — there is no local C++ compiler; C++ bots only run in the judge's sandbox:
```
unswbc run maps/trauma.map viper_v7 viper_v3 --sandbox --seed 1000 -o ladder/x.replay
```
Builds are cached by content hash, so repeated runs are fast.

**Local A/B (do this before every submit)** — always on the live pool maps, both sides, 2 seeds:
```
python tools/tourney.py viper_v7 v71 -j 12 --seeds 2 --maps portals,slithery_fight,schooltime,trophy,queen_of_spades,default,dilemma,autarky,devil,trauma
```
For a baseline of the exact submitted code: `curl -L -o x.zip $BASE/submissions/<id>/download -H "Authorization: Bearer $UNSWBC_KEY"` and unzip into a folder.

**Why a death happened**:
- `python tools/trace.py maps/X.map botA botB --seed N --deaths --ctx 6` — per-dragon indicator history before each death.
- `python tools/ladder_report.py ladder/x.replay --ours <label>` — team timelines (units/longest/total every 50 rounds) and deaths with context. `<label>` is the bot folder name locally, the submission id on the server.
- `python tools/board_at.py ladder/x.replay <dragonId> <round>` — the true board around a dragon (what it could not see).
- Debug build: copy the bot to `dbg7/`, add `debug_cfg.hpp` with `#define DEBUG_FROM a` / `#define DEBUG_TO b`; it logs a board dump and every option's evaluation.

**Real opponents (the measurement that matters)**:
```
curl -s $BASE/battles -H "Authorization: Bearer $UNSWBC_KEY" -H "Content-Type: application/json" \
     -d '{"teamId": 189, "ranked": false, "mapIds": [20,21,9,11,7,4,17,19,13,15]}'
python tools/challenge_wait.py ladder/cN <our submission id> <first game id of each battle...>
```
Unranked challenges do not move ELO. Map ids: Portals 20, Slithery 21, Schooltime 9, Trophy 11, QoS 7, Default 4, Dilemma 17, Autarky 19, Devil 13, Trauma 15.

**Scouting**: `python tools/scout.py --top 12` then `python tools/scout_report.py` (other teams' replays are public). `tools/profile_team.py` profiles one side of individual replays.

**Replays**: `tools/replay.py` decodes the format (gzip + Cap'n Proto packed; schema taken from the VS Code viewer). Server replays of other teams have empty bot labels — take sides from `/battles/:id` (`teamAName`/`teamBName`).

## Rules of the road (learned the hard way)

- Local wins against our own old bots did **not** predict ladder results; test against real teams with unranked challenges.
- Quota: 60 games/hour per team (a 10-map challenge = 10 games); 120 API requests/min (30 for `/leaderboard`).
- A new submission becomes active as soon as it builds and plays ranked autoscrims (every 2 h, UTC). New code gets a high K-factor (up to 96) for its first 10 ranked battles: big swings both ways.
- Ranked challenges: only targets ≤ 50 below us, both teams need the ranked switch on.
- CPU: 100M points per dragon per turn; exceeding it kills the dragon. `unswbc run --sandbox` prints p99/max; keep max ≲ 65M. The code has elapsed-time guards (`elapsedMs()`, 1 ms ≈ 1M points).
- Windows gotchas: Python `subprocess` needs `encoding="utf-8"` (team names are not ASCII); writing C++ through bash heredocs turns `\n` in string literals into real newlines — use the Edit tool or a patch file for such edits.
- Output: every `print` costs 2.5M points + 4000/byte; the helpers flush once per turn. Indicators are visible to opponents in replays — consider stripping them before the final tournament.

## Open problems / next steps

1. **Expansion speed**: top teams have ~31 units at round 100, we have ~15. Small drones need to eat more aggressively (less caution when cheap, better pearl routing).
2. **Consolidation yield**: our feeding still collapses units and wastes pearls (longest ~12–20 vs top teams' 23–31). Try: feeders approach the queen's *path*, queen routes towards dropped pearls, tune `feedFrom`/`feedRadius`.
3. **Head-on war**: top teams make 26–90 head-on kills per game. Revisit `findAttack` for cheap drones (trade into bigger enemies more readily when we outnumber them).
4. Map-specific: Trauma/Dilemma dead-end fountain corridors, Portals cages (require portal traversal — handled on known maps).
5. Before the final tournament: strip indicator strings, re-verify CPU.
