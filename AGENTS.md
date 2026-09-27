# AGENTS.md — working on this repo

For any teammate or agent continuing the UNSW Battlecode work. Read this, then `INSIGHTS_AND_PLAYBOOK.md`
(what we know about the game and the ladder). **Keep both files current**: when you learn something, change
the bot or submit, update them in the same commit.

## Where we are

- **V7.5 is the state of the art** (`baselines/v7_5`, submission 7793). `viper_v7/` is the working copy and
  starts identical to it.
- Rating ~1500 (rank ~210 of 851, top ~2124) on 2026-09-27.
- V7.5 is one design point, not a destination. Its known ceiling: it loses to the 1650+ teams, and on
  Trophy, Autarky and Devil to strong mid-ladder teams. **New directions are welcome**: a different macro,
  a different language, a fresh bot. Anything is fair game as long as it passes the gate below.

## Setup

- Python 3.11+, `pip install unswbc`. No local C/C++ compiler is needed: C++ bots build with the judge's own
  clang inside `unswbc run --sandbox` (cached by content hash).
- API key: `secrets.env` (private repo only; if the repo is ever made public, delete it and rotate the key
  on the team page). `unswbc auth set <key>` for `unswbc submit`; export `UNSWBC_KEY` for the scripts in
  `tools/` (`export $(cat secrets.env | xargs)`).
For any teammate or agent continuing the UNSW Battlecode work. Read this, then `INSIGHTS_AND_PLAYBOOK.md`
(what we know about the game and the ladder). **Keep both files current**: when you learn something, change
the bot or submit, update them in the same commit.

## Where we are

- **V7.5 is the state of the art** (`baselines/v7_5`, submission 7793). `viper_v7/` is the working copy and
  starts identical to it.
- Rating ~1500 (rank ~210 of 851, top ~2124) on 2026-09-27.
- V7.5 is one design point, not a destination. Its known ceiling: it loses to the 1650+ teams, and on
  Trophy, Autarky and Devil to strong mid-ladder teams. **New directions are welcome**: a different macro,
  a different language, a fresh bot. Anything is fair game as long as it passes the gate below.

## Setup

- Python 3.11+, `pip install unswbc`. No local C/C++ compiler is needed: C++ bots build with the judge's own
  clang inside `unswbc run --sandbox` (cached by content hash).
- API key: `secrets.env` (private repo only; if the repo is ever made public, delete it and rotate the key
  on the team page). `unswbc auth set <key>` for `unswbc submit`; export `UNSWBC_KEY` for the scripts in
  `tools/` (`export $(cat secrets.env | xargs)`).

## Repo layout

| Path | What |
|---|---|
| `viper_v7/` | Working copy of the C++ bot: `main.cpp`, generated `maps_data.hpp` (`python tools/gen_maps.py`), `bot.toml`. |
| `baselines/` | Exact submitted sources of kept builds: `v7_5` (champion), `v7_4`, `v7_3`, `v7_2`, `v6_6` (regression opponents). |
| `swarm_bot/` | Python stand-in for a head-hunting swarm (slow in the sandbox). |
| `maps/` | The live pool plus older bundled maps. `GET /maps` shows the pool in play. |
| `docs/` | Game docs (mechanics, protocol, timeouts, API). |
| `viper_v7/` | Working copy of the C++ bot: `main.cpp`, generated `maps_data.hpp` (`python tools/gen_maps.py`), `bot.toml`. |
| `baselines/` | Exact submitted sources of kept builds: `v7_5` (champion), `v7_4`, `v7_3`, `v7_2`, `v6_6` (regression opponents). |
| `swarm_bot/` | Python stand-in for a head-hunting swarm (slow in the sandbox). |
| `maps/` | The live pool plus older bundled maps. `GET /maps` shows the pool in play. |
| `docs/` | Game docs (mechanics, protocol, timeouts, API). |
| `tools/` | Test, analysis and ladder scripts (below). |
| `ladder/`, `replays/` | Local data, gitignored. |
| `ladder/`, `replays/` | Local data, gitignored. |

## The promotion gate (mandatory)

1. **Local sanity**: `python tools/gate.py viper_v7 --champion baselines/v7_5`. Needs ≥ 55% vs the champion
   (40 games) and ≥ 50% vs each other baseline (20 games), on the 10 live maps, both sides. This only
   filters out obvious regressions: a build can pass it and still be worse on the ladder (V7.6 did).
2. **Ladder panel (decisive)**: submit (the build becomes active immediately), then run unranked 10-map
   challenges against the panel and compare **map by map** with V7.5:
   - **777** (team 590): V7.5 wins all but Trophy, Autarky, Devil.
   - **ANON_TOKYO** (547): V7.5 won Autarky, Default, Portals, QoS, Dilemma.
   - **hmm** (189), **Aviators** (543): mid-ladder swarms; V7.4/V7.5 win most maps.

   Keep the build active only if it is at least as good; otherwise re-activate V7.5
   (`POST /submissions/7793/activate`). Games are near-deterministic per (bot, bot, map), so an unchanged
   map result means the change did nothing there.
3. When a build passes, copy its exact source into `baselines/<name>/`, make it the champion here, and log
   what it changed in the playbook.

Autoscrims (ranked) run every 2 hours on the hour and use whatever is active at that moment.

## Tools

| Script | Use |
|---|---|
| `tourney.py A B --seeds 2 --maps …` | Parallel sandbox matches, both sides. |
| `gate.py` | Stage 1 of the gate. |
| `trace.py map A B --deaths --ctx 6` | A dragon's own indicator strings before each death. |
| `replay.py` | Replay decoder (gzip + Cap'n Proto packed). Works on judge and local replays. |
| `ladder_report.py x.replay --ours <label>` | Units/longest/total timelines and deaths with context. `<label>` = folder name locally, submission id on the server. |
| `board_at.py x.replay <dragonId> <round>` | The true board around a dragon: what it could not see. |
| `early_game.py` | Eats/splits/deaths per dragon-turn: the economy numbers that explain most results. |
| `challenge_wait.py outdir <our sub id> <battle ids…>` | Wait for challenges, print map results, download replays. |
| `scout.py` / `scout_report.py` / `profile_team.py` | Download and profile other teams' public replays (top of the ladder). |
| `find_targets.py` | Higher-rated teams whose rating is falling: candidates for ranked challenges. |
| `gen_maps.py` | Regenerate `maps_data.hpp` after adding maps. |

Unranked challenge: `curl -s $BASE/battles -H "Authorization: Bearer $UNSWBC_KEY" -H "Content-Type: application/json"
-d '{"teamId": 590, "ranked": false, "mapIds": [20,21,9,11,7,4,17,19,13,15]}'` (map ids: Portals 20, Slithery 21,
Schooltime 9, Trophy 11, QoS 7, Default 4, Dilemma 17, Autarky 19, Devil 13, Trauma 15). Base URL
`https://game.battlecode.au/api/v1`. Other teams' replays are public (`GET /battles/<gameId>/replay`, follow
redirects).
## The promotion gate (mandatory)

1. **Local sanity**: `python tools/gate.py viper_v7 --champion baselines/v7_5`. Needs ≥ 55% vs the champion
   (40 games) and ≥ 50% vs each other baseline (20 games), on the 10 live maps, both sides. This only
   filters out obvious regressions: a build can pass it and still be worse on the ladder (V7.6 did).
2. **Ladder panel (decisive)**: submit (the build becomes active immediately), then run unranked 10-map
   challenges against the panel and compare **map by map** with V7.5:
   - **777** (team 590): V7.5 wins all but Trophy, Autarky, Devil.
   - **ANON_TOKYO** (547): V7.5 won Autarky, Default, Portals, QoS, Dilemma.
   - **hmm** (189), **Aviators** (543): mid-ladder swarms; V7.4/V7.5 win most maps.

   Keep the build active only if it is at least as good; otherwise re-activate V7.5
   (`POST /submissions/7793/activate`). Games are near-deterministic per (bot, bot, map), so an unchanged
   map result means the change did nothing there.
3. When a build passes, copy its exact source into `baselines/<name>/`, make it the champion here, and log
   what it changed in the playbook.

Autoscrims (ranked) run every 2 hours on the hour and use whatever is active at that moment.

## Tools

| Script | Use |
|---|---|
| `tourney.py A B --seeds 2 --maps …` | Parallel sandbox matches, both sides. |
| `gate.py` | Stage 1 of the gate. |
| `trace.py map A B --deaths --ctx 6` | A dragon's own indicator strings before each death. |
| `replay.py` | Replay decoder (gzip + Cap'n Proto packed). Works on judge and local replays. |
| `ladder_report.py x.replay --ours <label>` | Units/longest/total timelines and deaths with context. `<label>` = folder name locally, submission id on the server. |
| `board_at.py x.replay <dragonId> <round>` | The true board around a dragon: what it could not see. |
| `early_game.py` | Eats/splits/deaths per dragon-turn: the economy numbers that explain most results. |
| `challenge_wait.py outdir <our sub id> <battle ids…>` | Wait for challenges, print map results, download replays. |
| `scout.py` / `scout_report.py` / `profile_team.py` | Download and profile other teams' public replays (top of the ladder). |
| `find_targets.py` | Higher-rated teams whose rating is falling: candidates for ranked challenges. |
| `gen_maps.py` | Regenerate `maps_data.hpp` after adding maps. |

Unranked challenge: `curl -s $BASE/battles -H "Authorization: Bearer $UNSWBC_KEY" -H "Content-Type: application/json"
-d '{"teamId": 590, "ranked": false, "mapIds": [20,21,9,11,7,4,17,19,13,15]}'` (map ids: Portals 20, Slithery 21,
Schooltime 9, Trophy 11, QoS 7, Default 4, Dilemma 17, Autarky 19, Devil 13, Trauma 15). Base URL
`https://game.battlecode.au/api/v1`. Other teams' replays are public (`GET /battles/<gameId>/replay`, follow
redirects).

## Pitfalls
## Pitfalls

- Quotas: 60 challenge games per team per hour (a 10-map challenge uses 10); 120 API requests/min.
- A new build's first ranked battles use a high K (up to 96) only if it is the first new-code build to play
  ranked after the team's 12-hour window reopens; otherwise it inherits the team's count (K = 24).
- Ranked challenges: opponent must have ranked on and be rated no more than 50 below us.
- CPU: 100M points per dragon-turn; exceeding it kills the dragon. Keep `max` in `unswbc run --sandbox`
  output ≲ 65M. `elapsedMs()` guards exist in the code (1 ms ≈ 1M points).
- Windows: Python `subprocess` needs `encoding="utf-8"` (team names are not ASCII). Writing C++ through a
  shell heredoc turns `\n` inside string literals into real newlines: edit with an editor or a patch file.
- Indicator strings are visible to opponents in replays; strip them before the final tournament.
- Debug builds: copy the bot to `dbg7/` and add `debug_cfg.hpp` with `#define DEBUG_FROM a` / `#define DEBUG_TO b`
  for board dumps and per-option evaluation logs in the replay.