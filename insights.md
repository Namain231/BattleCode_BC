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
