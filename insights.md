# Insights — started fresh 2026-10-01

**The game's rules changed on 2026-10-01 (after this file was started).** Everything below from before that
line is suspect: win-rate and mechanism numbers were measured against the old rules, old map-generation ranges
and the old pearl/bed mechanics. The full prior history (all cycles since project start) is archived at
`archive/insights_pre_rules_change_2026-10-01.md` — 3500+ lines, still worth reading for *methodology* (how to
measure things, what mistakes were made and corrected) but **do not trust its win rates or specific parameter
values until re-validated against the new rules**. Re-read `docs/` first; they should reflect the new rules.

The previous session ended with `baselines/s2_gP` as the best-validated new-map build (pooled 61% vs live Y.8m
over 240 unseen-map games under the OLD rules). Treat it only as a reference starting point, not a result that
still holds. The gate in `AGENTS.md` is the way to re-establish what's actually good now.

## What's durable (process lessons, not game facts) — carried forward from the archive

1. **Replays zero out bed/pearl data and strip CPU points** — always load bed/gap data from `maps/*.map` /
   `maps_gen/*.map`, never trust a replay's own TILE records for that.
2. **Portals must be modeled as teleports**, not open edges, in any map-geometry tool.
3. **Local self-play vs a fixed opponent is not discriminating** for contention-driven metrics (path directness,
   trade outcomes) — it IS valid for self-driven mechanism metrics (eats/turn, splits, queen length). Ladder A/B
   needs a same-time control.
4. **85% of unseen-map games ended on the round-500 length tiebreak** under the old rules — check whether this
   is still true; it drove which metric mattered (final longest-dragon margin, not raw win rate).
5. **Never transplant a tuned parameter from one build/team to another without testing it in place** — 5/5
   transplants failed historically.
6. **A 40-game local gate is a smoke test, not a verdict**; Wilson CI is roughly ±15pp at that sample size.
   90-100 games per arm gets you to about ±20pp on a ladder A/B.
7. **Windows-specific**: `subprocess`/`open()` need `encoding="utf-8"` (team/player names aren't ASCII); a
   shell heredoc turns `\n` inside C++ string literals into real newlines — edit C++ with Edit/Write, not heredocs.
8. **The sandbox build cache keys on `main.cpp` only** — touch it (or use `tools/buildwasm.py`) after editing a
   header or the cache silently serves the old build.

## System-specific quirks learned running tooling on this machine (2026-10-01) — see also AGENTS.md "Pitfalls"

- **A Windows OOM crashed the whole machine** (not just a graceful OOM-kill) when ~20 Python learn jobs each
  loaded a full 1.6M-row CSV into memory in parallel (`list(csv.DictReader(fh))`, no streaming — several
  hundred MB to low-GB per process). The fix that held up: pre-split the CSV by group key with a one-pass
  streaming script before fanning out, so each parallel job only loads its own slice (see `tools/split_by_team.py`
  if it survived the cleanup, otherwise rewrite it — it's ~25 lines). Cap learn/extract fan-out at 4 concurrent
  on this machine; cap game-running (`tourney.py`) fan-out at `-j 6` when anything else is running concurrently,
  `-j 10` is fine solo.
- **`tools/mem_guard.sh MIN_MB`**: polls free physical memory via `powershell.exe -Command
  "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"` (returned in KB) and blocks until it clears the
  floor. Put this before every memory-heavy stage in an unattended/background chain. It worked correctly in
  practice: when a second heavy job (extraction) started while a game-screen was still running and pushed free
  memory under the floor, the guard just waited and logged "mem low ... waiting" instead of crashing anything.
- **The desktop's own apps compete for the same RAM pool**: `vmmemWSL` (the WSL2 VM backing the Zig judge) alone
  sits around 2.5-3GB resident; the browser, Discord, the IDE and antivirus add another 2-3GB on top. On a 16GB
  machine that leaves meaningfully less headroom for game-running batches than the total RAM suggests — size
  `mem_guard` floors and parallelism with that in mind, don't assume the whole 16GB is available.
- **Disk fills up silently from `ladder/` replay dumps.** A single 120-game `tourney.py --keep-replays` batch
  with `--debug` is several hundred MB; running many candidate screens back to back (12 candidates × ~900MB)
  used ~17GB in one session and took free disk from ~240GB down to 197MB before anyone noticed, because nothing
  warns on this — `df -h /c` was never checked proactively. Also: `tools/local_index.py` copies (or hardlinks)
  replays into a second location (`<out>/<label>/`), and `replay.py`'s `load()` writes a `.pkl` cache beside
  every replay it reads — both roughly double the footprint of a batch you then analyse. **Check `df -h /c`
  before and after any batch of more than ~20 games with `--keep-replays`**, and delete `*.replay`/`*.pkl`
  from a `ladder/` subdirectory as soon as its numbers are extracted and logged — the replays themselves are
  gitignored and disposable once the result is written down.
- **`uv run --python 3.11 --with X python ...` can fail transiently** with
  `Failed to fetch: https://pypi.org/simple/...` / `invalid peer certificate: UnknownIssuer` under load (seen
  mid-way through a chain of a dozen sequential `uv run` invocations). Not a real cert problem — retried
  immediately and it worked. Any unattended chain of `uv run` calls should retry each call 2-3 times on this
  specific error pattern before treating it as a real failure (grep the stdout/stderr for "Failed to fetch" /
  "invalid peer certificate" / "Request failed after" and retry rather than trusting a bare non-zero exit).
- **Process management on Windows via the Bash tool**: `pkill`/`ps` by pattern don't reliably exist; use
  `powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like
  '*pattern*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"`. Caution: matching on a command-line
  substring can also match the *query itself* if it's run through the same nested-bash-via-eval wrapper this
  harness uses — always sanity-check the returned PID list/commandlines before trusting a "0 processes found"
  result, and re-check after killing (a `-ForEach-Object { Stop-Process ...; $_.ProcessId }` that returns nothing
  usually means the match itself found only the query shell, not a real target).
- **A background orchestrator shell script must `mkdir -p` any directory it redirects stdout into** — bash sets
  up `>` redirection before the command behind it runs, so redirecting into a not-yet-created directory fails
  the whole backgrounded command silently (if its own stderr is also being redirected into the same missing
  path). This produced an entire "finished in under a second with empty results" false-negative for 12 candidate
  screens in a row before being caught by actually checking the target directory for replay files.
- **Prefer running retried/sequential multi-stage chains as one shell script backgrounded with `nohup ... &`**,
  not as a sequence of separate tool calls each waited on individually — the harness's own `sleep`-chaining is
  blocked (must use `run_in_background: true` or a real `until <condition>; do sleep N; done` loop), and a
  single orchestrator script is much easier to make memory-gated and crash-resistant than re-deriving the queue
  state across many separate tool calls.

## Sprint / tournament new-map check (2026-10-01)

As of this check, the live `/maps` endpoint still only listed the 10 known maps, and the team's and other top
teams' recent battles were all on those same 10 known maps — no sign of sprint-specific new maps having gone
live yet via the public API. `/tournaments` returns `[]`, there is no `/events` endpoint. Re-check this once the
new rules are confirmed; the map-generation assumptions in `tools/gen_random_maps.py` (kelp %, bed-gap ranges,
portal counts) were tuned to match the OLD live maps and need re-deriving from whatever the new maps actually
look like before `maps_gen`/`maps_dense*` can be trusted as a stand-in for them again.

## Repo state after the 2026-10-01 cleanup

- Disk emergency (197MB free) resolved by deleting all `*.replay`/`*.pkl` under `ladder/` — results were
  already logged before deletion where they mattered. `ladder/scout_lb{,2}/` kept only their small
  `index.json`/`PLAYERS.md`; the actual downloaded replays are gone and would need re-scraping.
- `archive/` (gitignored) now holds: `dead_s4x_lineage/` (the old S4.x line, overturned by an earlier
  postmortem), `pre_gP_exploration/` (early Y.8/queen-debug builds), `rulemine_cycle1_2026-10-01/` (every
  candidate build from the gP-tuning and rulemine cycle below), `old_zips/`. See `archive/README.md`.
- `rulemine/`, `viper_s2_rules/`, `tools/` (incl. `players_index.py`, `panel_zig.py`, `buildwasm.py`) are kept
  as live infrastructure — the pipeline code is reusable even though its specific learned models predate the
  rules change.
- `rulemine_data/` kept only the small learned-model JSON/MD files (20 of them: 10 death + 10 queen-move rules
  from the top-20 leaderboard, 2026-09-30/10-01) and the per-team CSV splits; the large raw extraction CSVs were
  deleted as redundant with the splits.

## Last cycle's results before the rules change (for context only, not to be trusted as current)

Summarized from the archived file, in case useful as a sanity check once new-rules numbers come in:
- `baselines/s2_gP` (Y.8m + online bed-gap learning + `protectFrom` 340 on unknown maps): 61% pooled vs live
  Y.8m over 240 unseen-map games, +~1 final-longest-dragon margin. Full writeup in `baselines/s2_gP/README.md`.
- An anti-circling tabu (`gD`) clearly helped on the 10 known live maps (40-20 vs its own control's 31-29) but
  was a wash on unseen maps (55% vs gP's 61%) — plausibly because the tabu disturbs early bed-learning.
- A "final merge" mechanism (`gM`/`gJ`, pour mass into the queen late) did not beat `gP` in any variant tried.
- Forcing the three known "open map" (bigFeed) parameters onto unknown maps (`gB`) was a clear loss (18%) —
  those parameters are overfit to the three specific maps they were tuned on, not a generalizable "open map"
  style; early-game collapses were the failure mode, not late feeding.
- Rule-mining from top-team replays (conditional-logit queen-move models, decision trees for feed-timing
  deaths): one death rule (PPP's) regressed gP on both test sets. Of 5 queen-move candidates that got a full or
  partial screen before the session ended, all were within noise of gP (47-61% depending on map set) — nothing
  from rule-mining cycle 1 had cleanly beaten gP yet. 15 more learned models (5 queen-move teams never screened,
  all leaderboard-ranks-21-40 teams never even reached learning) are sitting in `rulemine_data/` unscreened.

## 2026-10-04 nn_refresh (in progress)
The 1513-game full-terrain net ends at game 933320 / 2026-10-03T04:45:14.561Z.
The scout's manifest already had additional untrained rows, so new-game selection excludes the
actual shard manifest's game IDs. Recent winning ranked games are being scouted at Elo >=2110
(the leaderboard's twelfth team was 2111). The first 225 new games cover all 17 live maps.
GET /battles/:id returns the series' other game IDs; marking those as covered avoids repeated
series requests. The refresh uses a frozen chronological newest-game holdout, old+new shards,
and two visits to new training shards; old-net drift is evaluated before either new training run.
No refreshed accuracy or playing-strength result exists yet. The memory guard delayed the
runtime split test, whose first attempt exposed an F: junction import-root bug; fixed to repo cwd.

### nn_refresh resource abort
The scout preserved 358 new winning ranked games from 11 teams, 382051345 bytes, covering all 17 maps,
2026-10-04T10:41:57.010Z through 2026-10-04T12:36:56.340Z. C fell to 2.70 GiB, so the disk guard
stopped before BUILD; RAM remained below the required 3000 MiB. No shards, new net or candidate were
produced. All refresh processes were stopped. The corrected workflow passed static critic review;
runtime split test, drift, Kaggle runs, parity and CPU remain unverified. See the saved report.

### 2026-10-05: league_build movement proxies rejected
Eight per-team small v6 nets were trained locally on winning post-rule replays and copied into
league/team_<id> from viper_y96qf with shared wNN=20 and rules fallback. The roster includes
tungtung67, avid coders, Just Keep Swimming, code matters, Jingling Munmin, hm, SSS and forgot to mention.
All eight failed the units@r100 fidelity gate (local/real equal-map medians 0.088-0.566).
Sv5.3 won 15-17/20 against each proxy; these results do not reproduce its real ladder difficulty.
Movement-only imitation leaves splits/feeding/actions to our rules; runtime feature parity is unverified.
Do not use rejected proxies as ladder-faithful gate opponents. Full numbers and limitations:
out/league_build_report.md; raw data, atomic resume state and CPU sidecars on F:/BattleCode_data/league_build.

## 2026-10-05: paired opening farm tooling
Local farm entry: `bash tools/farm_run.sh CANDIDATE_DIR --games 2000`; documentation `farm/README_SCALE.md`. The default plan is 2000 candidate + 2000 Sv5.3 evaluations against Y9_6 and eight rejected league proxies, 17 live + 20 dev maps, both sides, >=27 distinct seeds per map, 40 shards. Primary opening metrics reuse the census analyzer; wins are secondary. Queens are fixed starting IDs 0/1, resolved by map team order. Atomic per-evaluation JSON, F: staging and disk/memory guards support resume; remote lanes OFF. Plan/fixtures passed; this is tooling verification, not candidate performance evidence.
## Farm integrity fix (2026-10-05)
- Python supervisor locks do not pass automatically to WSL children. A judge-side Linux flock plus unique attempt directories prevents shared replay writers; a killed Windows supervisor fixture confirmed the surviving WSL lease blocked resume.
- 2,000 games per arm is nominal +/-2.2 pp pooled and about +/-6.6 pp per nine-way opponent group, not +/-1 pp. Use explicit sample budgets and report achieved clustered intervals.

## Farm scale fix round 2 (2026-10-05)
WSL shell paths quoted; checkpoint manifest parses once per scan. Normal shard summaries reuse validated rows; restart/import/failure/final coverage validate disk state. Path/parse-count/opening/integrity/supervisor-kill fixtures pass. Corrected bundle packed and collected with zero games; throughput and achieved precision unmeasured. Correction to earlier farm entry: default has 3-4 independent seed clusters per map, not >=27. See out/farm_scale_report.md.

## Parameter search tooling (2026-10-05)
`tools/param_search.py` exposes 12 opening parameters from viper_y96qf via generated headers. Successive halving uses the paired farm against Sv5.3; league wins are only safety evidence. Early stops inspect balanced map cycles of independent map-seed clusters, not prefixes; final validation uses fresh seed offset 100000. Interrupted evaluations are authoritative in farm JSON and repair TSV on resume. No candidate is promoted without four closed-start halfway targets, >=1500 paired final games, CPU <=66M, measured safety and separate other-lane critique. See out/param_search_report.md for measured status.

## 2026-10-06 opening_recipe (unpromoted)
Three measured revisions: viper_y96qo improves Stripes units@100 6.5->11.5,split42->11,but meets only1/4 halfway targets. Closed26/64 vs39/64;paired safety50/98 vs59/98(-9.18pp);population drops Around UNSW,Australia,Maze,Tower Defense. CPU64.648M passes;no submission. Details:out/opening_recipe_report.md. Static correctness did not establish performance;no universal box exit verified.

## 2026-10-06: cheap MLP student passes inference checks, fails gameplay
`viper_y96qm` changes only the net call in `viper_y96qg`, retaining nnInput6/wNN and a conv fallback. A 256/128 MLP trained for eight streaming epochs with CE + temperature-2 KL; newest 60 games (582,515 states) held out globally. Best epoch 7 top-1 is 68.628% vs teacher 68.579%, but backward-move recall is 8.77% vs 43.97%.
Sparse first layer drops only reserved zero planes 8/18. Exported int32 coefficients +/-16,777,215 with double accumulation give max logit error 0.000671 and 1600/1600 matching argmaxes. Sampled wasm cost is 1.659M mean / 2.482M maximum vs conv 21.137M: 12.74x cheaper on average; this is not a universal per-call bound.
Safety on the requested seven maps, seeds 3-9, both sides versus Y9_6: 50/98 vs cached parent 59/98 (-9.18 pp), FAIL. Prior epoch-1 trial was 47/98; follow-up reused those same safety seeds, with checkpoint chosen by held-out accuracy only. Peaks: australia 57.361M, around_unsw 57.616M. Overall imitation accuracy close to the teacher does not establish gameplay non-inferiority. Candidate remains unpromoted, with no submission; full numbers/commands in `out/mlp_student_report.md`.

- 2026-10-06 mlp_student fix round 1: candidate dropped after 50/98 vs 59/98 safety FAIL (-9.18 pp). Resume supervisor retired rather than reuse unbound historical caches; original control bot/engine provenance unavailable. No additional experiment or submission.

- MLP student fix round 2 (2026-10-06): hardened CPU threshold/finite checks and native parity I/O; reruns pass (1600/1600, 2.482M sampled max). Historical safety remains FAIL; candidate unpromoted, supervisor retired, fresh sealed control required for future comparisons.

## Kamikaze audit, 2026-10-07 (verification still running)

Fresh replay/version-bound audit: 389/976 games offer a legal non-queen route to the current enemy queen head (379 with a fully visible route); our queen later dies in 171 opportunity games. Enemy length<=4 dragons initiate queen rams in 414 games. Existing tagged attacks already kill the enemy queen head-on in 367 games, so opportunity incidence is not incremental benefit. Reconstruction errors: none. Candidate viper_y96nk is Nv30 with conservative visible queen-life/remaining-longest guards; chase OFF. Fresh smoke passes CPU 63.741005M, 1/2 wins, no rams. Paired 98-game arms pending; no promotion/submission. Build-proven sidecars and replay/analysis identity are required to trust resumed panels. Final evidence: out/kamikaze_report.md.
