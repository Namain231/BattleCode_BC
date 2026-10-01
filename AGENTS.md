# AGENTS.md — working on this repo

**The game's rules changed on 2026-10-01.** `insights.md` was restarted fresh that day — read its top banner
first. Everything in this file's "Where we are" below (and anything in `baselines/`) was measured against the
OLD rules and needs re-validation through the gate before being trusted again. The old insights history (all
prior cycles) is archived at `archive/insights_pre_rules_change_2026-10-01.md`, useful for methodology, not for
specific numbers. `archive/README.md` explains what else moved there in the same cleanup.

For any teammate or agent continuing the UNSW Battlecode work. **New here? Read `README.md` and `guide/` first** (plain-language setup, testing and mistakes to avoid). Then this, then `insights.md`
(what we know about the game and the ladder). **Keep both files current**: when you learn something, change
the bot or submit, update them in the same commit.

## Where we are

- **Champion: Y.7.12-nn.1** (`baselines/y7_12_nn1`, submission 9285, active): V7.12 + a move-imitation network
  trained on top teams' replays (`ml/`, `viper_nn/`), used on maze maps. Ladder: 24/40 vs 8 strong teams; same-time
  control vs 4 of them 16/20 (V7.12 6/20). Details and numbers: `ml/results.md`.
- Previous champion: **V7.12** Maze panel **23/28** (V7.5 14/28, V7.10 ~19/28).
  Lineage: V7.5 → V7.9 (short-horizon early miners) → V7.10 (even head-on trades) → V7.11 (keep budding on
  Autarky) → V7.12 (late queen on maze maps: from round 340 the dragon(s) tied for longest stop budding and get
  pearls first; from round 440 nearby drones feed a queen at least 2 longer). `viper_v7/` is V7.12; `viper_nn/` is the champion.
- Rating ~1566 on 2026-09-27 (+31 from V7.12's first K = 96 ranked battle).
- V7.12 still loses to most 1690+ teams (Rogo, WCTW 2/5) and to 777 on Dilemma, Autarky and Devil.
  **New directions are welcome**: a different macro, a different language, a fresh bot. Anything is fair game
  as long as it passes the gate below.
- **New-map events (sprint, final; from 2026-10-01):** the build for them is gP (`baselines/s2_gP`, S.2). Rule
  mining for it is planned in `RULE_MINING_SPEC.md` and built in `rulemine/` (how-to: `README_RULEMINE.md`).

**Submission names (from 2026-09-28):** neutral names only, `Y.7.12.<n>` in sequence, with a bland or empty
description — never name what a build contains (other teams may see names; battles and replays are public).
The mapping lives here and in `ml/results.md`:

| Name | Id | Contents |
|---|---|---|
| test-v7.17-nn | 9258 | V7.12 + imitation network v1, wNN 2, maze maps only (first ladder test) |
| Y.7.12-nn.1 | 9285 | same code as 9258; champion |
| Y.7.12-nn.1-jam | 9298 | champion + sonar replay attack (experiment) |
| Y.7.12.3 | 9357 | champion + signed sonar + pearl gossip (friends share visible pearls) |
| Y.7.12.4 | 10047 | champion settings + signed sonar + team-conditioned network copying Vibing++'s style (league 86.3% vs 82.1%) |

Replays are public: indicator strings and sonar formats reveal our logic to anyone who reads them.

## Setup

- Python 3.11+, `pip install unswbc`. No local C/C++ compiler is needed: C++ bots build with the judge's own
  clang inside `unswbc run --sandbox` (cached by content hash).
- API key: `secrets.env` (private repo only; if the repo is ever made public, delete it and rotate the key
  on the team page). `unswbc auth set <key>` for `unswbc submit`; export `UNSWBC_KEY` for the scripts in
  `tools/` (`export $(cat secrets.env | xargs)`).
- Rule mining (`rulemine/`, `tests/`): also `pip install scikit-learn scipy pytest`, and `pycapnp` for the bceval
  context. Two tests compile generated C++ with `clang++` and skip when it is absent.

## Repo layout

| Path | What |
|---|---|
| `viper_nn/` | **The champion Y.7.12-nn.1** (identical to `baselines/y7_12_nn1`). Copy it to start a new build. |
| `viper_v7/` | V7.12, the same bot without the network: `main.cpp`, generated `maps_data.hpp` (`python tools/gen_maps.py`), `bot.toml`. |
| `guide/`, `README.md` | Plain-language guides for teammates: setup, how the bot works, testing, mistakes, the network, ideas. |
| `experiments/` | Unproven builds kept for later: `signed_sonar`, `pearl_gossip`, `nn_generic` (network build with generic input sizes, used by `ml/`). |
| `maps_gen/` | 300 random fair maps (`tools/gen_random_maps.py --n 300 --seed 1`, gitignored) for unseen-map tests: `tourney.py --maps maps_gen/gen_000,…`. |
| `baselines/` | Exact submitted sources of kept builds: `y7_12_nn1` (champion), `v7_12`, `v7_5` (gate opponent), `s2_gP` (pre-rules-change new-map build, S.2 — needs re-validation, see top of this file). Older builds and experiments: git history. |
| `archive/` | Gitignored. Superseded build dirs and the pre-2026-10-01 `insights.md`, moved out during the 2026-10-01 cleanup. See `archive/README.md`. Nothing here is built or tested against. |
| `swarm_bot/` | Python stand-in for a head-hunting swarm (slow in the sandbox). |
| `maps/` | The live pool plus older bundled maps. `GET /maps` shows the pool in play. |
| `docs/` | Game docs (mechanics, protocol, timeouts, API). |
| `tools/` | Test, analysis and ladder scripts (below). |
| `ladder/`, `replays/` | Local data, gitignored. |
| `rulemine/`, `README_RULEMINE.md`, `RULE_MINING_SPEC.md` | Rule mining from top-team replays for gP: replay state with per-dragon memory, features (unknown-map knowledge only), decision extractors, contrast report, learners, C++ codegen, bceval context, paired screen. Tests in `tests/` (`python -m pytest -q tests`). |
| `viper_s2_rules/` | gP (S.2) plus learned-rule hooks (`rm_hooks.hpp`, `rules_learned.hpp`) behind `Params::rmDeath` / `rmQueen` / `rmLog`, all off by default (then it plays exactly like gP). **Never submit with `rmLog = 1`**: it logs feature vectors into every replay. |
| `farm/`, `.github/workflows/farm.yml` | Game-farm bundle (`pack.sh`, `make_jobs.py`, `run_shard.sh`, `summarize.py`, Kaggle script) for WSL, Kaggle or GitHub Actions. |
| `maps_rm_dev/`, `maps_rm_test/` | 20 + 20 generated maps (all 7 Loong generator styles + dense random). `maps_rm_test` is held out: final checks only. |
| `proto_rehaul/` | Throwaway from-scratch rule bot (2026-10-01): v7.12 parity, 28% vs the champion. A test opponent, not a candidate. |

## The promotion gate (mandatory)

1. **Local sanity**: `python tools/gate.py <candidate dir> --champion baselines/y7_12_nn1`. Needs ≥ 55% vs the champion
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

Rule-mining candidates go through a cheaper screen first (`README_RULEMINE.md`, step 7: paired final-length margin
vs gP on unseen maps). The screen decides what reaches this gate; it does not replace it.

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
| `panel_zig.py BOT OPP OUT --set live/dev/test/setA/setB -j 10` | Local panel on the Zig judge (`LOONG_JUDGE`); replays named for `python -m rulemine.evalpair CAND_OUT CTRL_OUT`, the paired screen. |
| `buildwasm.py BOT_DIR` | Build a bot to wasm with the judge's clang, rebuilding on header edits too. |
| `gen_style_maps.py OUT SEED N` | Generated maps in every Loong generator style (needs a `the-loong-game` checkout via `LOONG_REPO`). |
| `team_mechanics.py` / `sprint_purpose.py` | Per team: sprint and sonar use; what sprints are for, and deaths to enemy sprints vs steps. |
| `python -m rulemine …` | `extract` / `contrast` / `learn` / `codegen`, plus `python -m rulemine.parity` and `python -m rulemine.evalpair`. See `README_RULEMINE.md`. |
| `players_index.py SCOUT_DIR` | Builds `SCOUT_DIR/PLAYERS.md`: a per-player (not per-game) index of a `scout.py`-style directory — summary table plus every game with map/side/opponent/result. |
| `mem_guard.sh MIN_MB` | Blocks until free physical memory clears `MIN_MB` (checks every 20s via PowerShell). Put before every memory-heavy stage of an unattended/background chain — see AGENTS.md "Running things safely on this machine". |
| `split_by_team.py SRC_CSV OUT_DIR COLUMN` | Streams a large CSV once and writes one small CSV per distinct value of `COLUMN` into `OUT_DIR`. Use before fanning out parallel jobs that would otherwise each load the full file (the OOM cause below). |

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
- The sandbox build cache (`unswbc run --sandbox`) is keyed on `main.cpp` only: after changing a header
  (e.g. `maps_data.hpp`, `viper_nn/policy_weights.hpp`), also touch `main.cpp` or you silently test the old build.
  (`tools/buildwasm.py` keys on every source file and avoids this.)
- Windows: Python `subprocess` needs `encoding="utf-8"` (team names are not ASCII). Writing C++ through a
  shell heredoc turns `\n` inside string literals into real newlines: edit with an editor or a patch file.
- Indicator strings are visible to opponents in replays; strip them before the final tournament.
- Debug builds: copy the bot to `dbg7/` and add `debug_cfg.hpp` with `#define DEBUG_FROM a` / `#define DEBUG_TO b`
  for board dumps and per-option evaluation logs in the replay.

## Running things safely on this machine (learned 2026-10-01, see `insights.md` for the incidents)

- **This machine has crashed from an OOM once already.** Cause: ~20 Python jobs in parallel each loading a full
  multi-million-row CSV into memory (`list(csv.DictReader(fh))`, no streaming). Fix that held: pre-split any
  large CSV by the group key you're about to fan out on (one streaming pass), so each parallel job only loads
  its own small slice. Cap CSV-loading/learning fan-out at **4 concurrent**; cap `tourney.py` game-running at
  **`-j 6`** whenever something else might be running at the same time (`-j 10` is fine solo). Use
  `tools/mem_guard.sh MIN_MB` (polls `Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory` via
  `powershell.exe`, blocks until clear) before every memory-heavy stage of any unattended/background chain —
  if it's been deleted, it's ~15 lines, rewrite it before fanning out anything big again.
- **The desktop's own apps and the WSL2 VM backing the Zig judge compete for the same RAM.** `vmmemWSL` alone
  sits around 2.5-3GB resident even when idle; browser/Discord/IDE/antivirus add 2-3GB more. On a 16GB machine
  that's real headroom lost before any of our own jobs start — don't size parallelism off the total RAM figure.
- **Disk fills up silently from replay dumps.** A single `tourney.py --keep-replays` batch with `--debug` is
  several hundred MB; `tools/local_index.py` and `replay.py`'s `.pkl` cache roughly double the footprint of
  whatever you then analyse. Check `df -h /c` before and after any batch of 20+ games with `--keep-replays`,
  and delete `*.replay`/`*.pkl` from a `ladder/` subdirectory as soon as its numbers are extracted and logged —
  it's gitignored and disposable once the result is written down. This machine went from ~240GB to 197MB free
  in one session of back-to-back candidate screens before anyone checked.
- **`uv run --with X python ...` fails transiently under load**: `Failed to fetch: https://pypi.org/simple/...`
  / `invalid peer certificate: UnknownIssuer`. Not a real cert problem — retrying immediately works. Any
  unattended chain of `uv run` calls should grep its own output for "Failed to fetch" / "invalid peer
  certificate" / "Request failed after" and retry 2-3 times before treating it as a real failure.
- **Process management**: there's no reliable `pkill`/`ps` by pattern. Use
  `powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like
  '*pattern*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"`. A commandline-substring match can
  also match the query shell itself (this harness runs Bash calls through a nested eval wrapper) — sanity-check
  the returned PIDs/commandlines, and re-check after killing rather than trusting an empty result at face value.
- A backgrounded orchestrator script must `mkdir -p` any directory before redirecting stdout into a file inside
  it — bash sets up `>` redirection before the command runs, so a not-yet-created target directory fails the
  whole command silently if its stderr is redirected the same way. This produced a false "finished instantly
  with empty results" for an entire batch of candidate screens before being caught.
- Prefer one backgrounded shell script (`nohup bash chain.sh &`) over many separate tool calls for a multi-stage
  unattended chain — `sleep`-chaining across tool calls is blocked by the harness (use `run_in_background: true`
  or a real `until <condition>; do sleep N; done` loop instead), and one script is far easier to make
  memory-gated and resumable than re-deriving queue state across calls.
