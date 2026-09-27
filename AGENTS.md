# AGENTS.md — working on this repo

For any teammate or agent continuing the UNSW Battlecode work. Read this, then `INSIGHTS_AND_PLAYBOOK.md`
(what we know about the game and the ladder). **Keep both files current**: when you learn something, change
the bot or submit, update them in the same commit.

## Where we are

- **Champion: V7.12** (`baselines/v7_12`, submission 8242, active). Maze panel **23/28** (V7.5 14/28, V7.10 ~19/28).
  Lineage: V7.5 → V7.9 (short-horizon early miners) → V7.10 (even head-on trades) → V7.11 (keep budding on
  Autarky) → V7.12 (late queen on maze maps: from round 340 the dragon(s) tied for longest stop budding and get
  pearls first; from round 440 nearby drones feed a queen at least 2 longer). `viper_v7/` is the working copy.
- Rating ~1566 on 2026-09-27 (+31 from V7.12's first K = 96 ranked battle).
- V7.12 still loses to most 1690+ teams (Rogo, WCTW 2/5) and to 777 on Dilemma, Autarky and Devil.
  **New directions are welcome**: a different macro, a different language, a fresh bot. Anything is fair game
  as long as it passes the gate below.

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
| `baselines/` | Exact submitted sources of kept builds: `v7_12` (champion), `v7_11` … `v7_9`, `v7_5`, `v7_4`, `v7_3`, `v7_2`, `v6_6` (regression opponents). |
| `swarm_bot/` | Python stand-in for a head-hunting swarm (slow in the sandbox). |
| `maps/` | The live pool plus older bundled maps. `GET /maps` shows the pool in play. |
| `docs/` | Game docs (mechanics, protocol, timeouts, API). |
| `tools/` | Test, analysis and ladder scripts (below). |
| `ladder/`, `replays/` | Local data, gitignored. |

## The promotion gate (mandatory)

1. **Local sanity**: `python tools/gate.py viper_v7 --champion baselines/v7_12`. Needs ≥ 55% vs the champion
   (40 games) and ≥ 50% vs V7.5 (20 games), on the 10 live maps, both sides. Older baselines are kept for
   reference but are not part of the gate. This only
   filters out obvious regressions: a build can pass it and still be worse on the ladder (V7.6 did).
2. **Ladder panel (decisive)**: submit (the build becomes active immediately), then run unranked
   challenges against the panel and compare **map by map** with the champion. V7.12 (champion): **23/28** —
   777 4/7 (W Trophy, QoS, Default, Trauma), ANON_TOKYO 7/7, hmm 6/7 (L Devil), Aviators 6/7 (L QoS).
   For reference, the older V7.5:
   V7.5's panel results on the 7 non-open maps (Trophy, QoS, Default, Dilemma, Autarky, Devil, Trauma),
   unranked, map ids `[11,7,4,17,19,13,15]` — **14/28**:
   - **777** (590): 4/7 — W QoS, Default, Dilemma, Trauma.
   - **ANON_TOKYO** (547): 5/7 — W Trophy, QoS, Default, Dilemma, Autarky.
   - **hmm** (189): 2/7 — W QoS, Trauma.
   - **Aviators** (543): 3/7 — W Dilemma, Devil, Trauma.
   On the open maps (Portals, Slithery, Schooltime) V7.5 usually wins against all four.

   Keep the build active only if it is at least as good; otherwise re-activate the champion
   (`POST /submissions/8242/activate`). Each game draws a random pearl seed, so a single game per map is noisy: the same
   code has flipped results on the same map. Judge by totals over the panel, not one map flip.
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
| `elo_bot.py --our-sub <champion id>` | Always-on ELO daemon on the champion: whenever quota frees, tests teams ≥ 20 above us (5 maze maps) and sends a ranked challenge on the maps we won if the test was ≥ 3/5 **and** ≥ Elo-expected + 0.2. Pauses while a candidate is active; re-activates the champion 5 min before every autoscrim. Log `ladder/elo_log.txt`. |
| `loss_report.py <battle id…>` | Why we lost: downloads the lost games, classifies each (outnumbered by r100, mid-game war, late collapse, tiebreak…) with the timeline and the death causes of the decisive phase. `elo_bot.py` runs it on every finished battle with a loss → `ladder/loss_log.txt`. |
| `strong_panel.py <cand> <champ> --teams … --deadline-utc HH:MM` | Unranked test of a candidate against a team list, then re-activates the champion (by the deadline at the latest). |
| `gen_maps.py` | Regenerate `maps_data.hpp` after adding maps. |

Unranked challenge: `curl -s $BASE/battles -H "Authorization: Bearer $UNSWBC_KEY" -H "Content-Type: application/json"
-d '{"teamId": 590, "ranked": false, "mapIds": [20,21,9,11,7,4,17,19,13,15]}'` (map ids: Portals 20, Slithery 21,
Schooltime 9, Trophy 11, QoS 7, Default 4, Dilemma 17, Autarky 19, Devil 13, Trauma 15). Base URL
`https://game.battlecode.au/api/v1`. Other teams' replays are public (`GET /battles/<gameId>/replay`, follow
redirects).

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
