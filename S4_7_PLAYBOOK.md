# S.4.7 Playbook — the Abyss-framework rewrite

Companion to `INSIGHTS_AND_PLAYBOOK.md` (V7.12 lineage) and `AGENTS.md` (workflow). This file is the
condensed, git-pushable summary of the **S4.7 line** for anyone joining that work: current status,
what's proven, what's still broken, and the tools built along the way. Full blow-by-blow reasoning
lives in the assistant's memory (`s4_7_rebuild_progress.md`, `s4_7_v4_and_beyond.md`) and in the
older `insights.md` at the repo root — this file is the version meant for a teammate to read once and
get oriented, not the append-only working log.

Only write here what was measured; delete things that stop being true.

---

## 1. Why S4.7 exists

S4.6 (the previous non-V7.12 line) had a measured, severe bug: **93% of its real ladder deaths were
self-inflicted "DOOMED" traps** (hit wall / hit self), not combat losses (`s4_6_loss_diagnosis.md`).
S4.7 is a ground-up rebuild on top of a public framework ("Abyss", `bc-abyss-main/`, by another team)
whose proper flood-fill safety check before every move structurally avoids that class of bug.

## 1b. Process rule: baseline before drastic changes (2026-09-30)

`viper_vS4.7` is untracked in git and gets edited in place continuously — there was no real
checkpoint to fall back to before today's echo-parsing fix + single-probe sensor work (a real gap,
per direct user feedback: "when adding such drastic features you should save a new version to
baseline... instead of continuously iterating on vS4.7"). **`baselines/S4.7.6`** now captures the
state right after that work (3 applied `param_search_bceval` gains + the echo fix + the dormant,
off-by-default probe sensor — verified zero behavior change with the gate off). **Going forward**:
before starting a drastic/risky change (a new mechanism, not a tuning tweak), copy the current
`viper_vS4.7/*.hpp/*.cpp/*.toml` into a new `baselines/S4.7.<n>/` first, so there is always a real
fallback to diff against or revert to, not just "I remember what I changed."

## 2. Current status (as of 2026-09-30)

- **Not submitted/active.** `Y.7.12-nn.1` (id 9285, the V7.12+ML champion) remains the team's active
  submission. S4.7 is validated locally and in three rounds of real unranked ladder testing, but has
  not yet beaten the champion decisively enough to promote.
- Best validated local build: `baselines/S4.7.5/` (also the current `viper_vS4.7/` state), **50.0%**
  vs `viper_v7.12` on a 6-map/3-seed/both-sides panel (trauma/autarky/trophy/default/dilemma/devil).
- Real ladder test (`S.4.7.6`, submission id 11453) against 3 opponents rated 1700+ (Rogo,
  RustyHamsters, UnderTheC), 30 games: **8W-22L**. This is the data that surfaced the Slithery
  Fight/Schooltime blind spot below — **local testing on the 6-map panel alone is not sufficient
  validation**; always include Slithery Fight and Schooltime, and ideally a genuinely different
  opponent than V7.12, before trusting a local number.

## 1a. What actually wins: population and length curves from 137 top-team games (2026-09-30)

`tools/growth_pattern.py` (units/longest/total length at rounds 100-500+end, winner vs loser,
`ladder/scout/`): **winners run ~50% more units than losers from round 100 onward — a population
lead that starts early and never closes.** Longest-dragon length is nearly identical for winner and
loser through round 300 (both ~4-7) — real consolidation is concentrated in the **round 300→400
window**, where the winner's longest roughly doubles the loser's (21.5 vs 11.5) and stays ~2x ahead
through the end (34 vs 16 median). End-game: winners keep ~11 dragons alive (one ~34-long queen +
~10 companions) vs losers' ~5. This lines up with a separate `bceval`-based finding: **77.5% of wins
(719-replay sample) are "dominant" throughout, only 21.6% are real comebacks** — winning this game
is mostly about building and keeping an early population lead, not a late clutch play.

Useful validation: S4.7's own `growRound=300`/`feedRound=400` already sit at the empirically-observed
transition window — the phase *timing* isn't the problem; population/growth-speed *execution* during
expansion is (see the `param_search_bceval` focus below).

## 2a. A/B test verdict: territory safety-margin and T_CHOKE reservation (2026-09-30) — neither shipped

Both implemented (see §7 for what they are) and A/B tested in isolation against the 8-map baseline
(40.6%). **Neither is shipped; both `wTerritory` and `wChoke` remain 0 by default.**

- **Territory (`wTerritory=0.5`)**: 21.9%, a real regression. Trauma improved (+1), but **Dilemma
  collapsed 75%→0%** — the identical failure signature as this session's earlier reverted
  bed-clustering experiment, now confirmed with a second, structurally different implementation.
  Dilemma's sparse "few excellent fountains" layout appears genuinely incompatible with any
  territory-holding bias as currently shaped. Don't retry without a much smaller magnitude or a
  bedDensity-based gate excluding maps like Dilemma.
- **T_CHOKE (`wChoke=1.0`)**: essentially a **null result**, not a regression — 5 of 8 maps were
  byte-identical to baseline (the "cramped" trigger is too rare to ever fire in ordinary play).
  Worth retrying with a broader trigger (e.g. `exits<=1`, matching the existing `wPocket` corridor
  check) so it activates often enough to actually be judged.
- **Correction, important process lesson**: both tests initially looked like they'd regressed Devil
  (previously 100% across every test this session) — checking the *raw per-game lines* (not just
  the summary table) showed those "draws" were actually `[ERR] TIMEOUT` entries, caused by running
  3 heavy background jobs at once and pushing an already-borderline-slow map over `tourney.py`'s
  timeout. **Always check for `TIMEOUT` in the raw log before trusting a draw** — the per-map
  summary table doesn't flag it, only the raw `[ERR]` lines do.

## 3. What's confirmed and solid

- The Abyss rewrite structurally fixed the 93%-DOOMED crisis (verified: DOOMED deaths are no longer
  the dominant cause on most maps, see §5 for the two maps where they still are).
- **Pearl gossip + local crowd avoidance** (`gossip.hpp`, `World::crowd`): genuine, validated
  improvement, ~56.6% vs V7.12 on clean maps early in the rebuild (up from S4.6's 20-40%).
- **`splitEnemyDist` swarm-exemption**: V7.12's own bud logic has no enemy-distance gate at all;
  ours originally did and it silently blocked almost all swarm splitting once the board got
  populous. Single biggest lever found in the whole rebuild.
- **Spawn-based instant map resolution** (`knownmap.hpp`): several maps share exact dimensions
  (Portals/Devil/Dilemma are all 32×16), so pure wall/pearl disambiguation from 7×7 vision could take
  a long time. Checking round-0 head position against each candidate map's known spawn list resolves
  the ambiguity instantly. Root-caused a real online DOOMED-death regression this way (every hit-wall
  death implies stepping on a cell we'd never actually seen — i.e. an unresolved map).
- **Map-adaptive `gamma`** (`KnownMapMatcher::adapt()`, `knownmap.hpp`): a function of *measured* map
  structure (bed density: fraction of cells that are pearl beds), not map identity — degrades safely
  to defaults on any unrecognised map. A single flat `gamma` cannot serve both a dense map (Trophy/
  Default want it sharper) and a sparse one (Dilemma is badly hurt by the same sharpening). This is a
  real, working instance of "map-adaptive parameters from measured structure, not a lookup table" —
  worth extending to other params (see §7).
- **`wCompass`**: long-range pearl pull decays too fast (`gammaFar^m`) to matter past ~40-50 moves;
  on a 1152-cell maze like Trauma the nearest known bed can be 60-90+ tiles away. Added an
  undiscounted flat bonus toward the best far-away known bed (one full-board BFS/turn, negligible
  CPU). +8.3pp on the validation panel (41.7% → 50.0%), no map regressed.
- **Emergency split-to-escape** (`trySplit()`): if a dragon has no safe move in any direction while
  staying whole, allow a minimal 2-long-child split as a last resort, bypassing the routine
  growth-split length gates. Validated net-positive in isolation (autarky 1/6 → 2/6, nothing else
  changed) — **but see §5, this may be the cause of the Slithery Fight catastrophe below.**

## 4. Rejected / reverted (so nobody repeats them)

- **`feedMaxLen` relaxation (6→999) + `wCrowd` increase**: caused a real online DOOMED-death
  regression (1W-9L against two ~1700-elo teams). Reverted to `feedMaxLen=6`, `wCrowd=0.4`.
- **Territory/bed clustering** (`Params::territoryWeight`, boosting a known bed's pull rate by how
  many other beds are nearby): helped Trauma (0/6→1/6) but hurt Dilemma more (4/6→2/6) — net -2.8pp.
  **Disabled by default** (`territoryWeight=0.0`), kept in code. The underlying idea (claim-and-hold
  pearl-rich regions) is still a real gap — see the Voronoi-territory idea in §7, a better-motivated
  version of the same instinct.
- **`trySplit` "rescue mode"** (stricter child-room check unless the parent was already trapped):
  measurably worse on an identical seed (104→119 total deaths). The right fix for cornered-dragon
  deaths turned out to be *loosening* the split length gate (→ emergency-split, §3), not tightening
  the room check.
- A critical **O(n²) CPU-overrun bug** was caught and fixed during the territory-clustering
  experiment: on `default` (bedDensity=1.0, 1000+ known beds), an unguarded pairwise loop blew the
  100M-point CPU budget on round 0 and killed every dragon outright. Any future per-bed-pair or
  per-dragon-pair computation must be capped (`territoryMaxHot=200` is the existing pattern).

## 4a. CRITICAL: we generalize badly to unseen maps — likely the top-priority finding of this whole effort (2026-09-30)

First-ever `maps_gen/` validation (30 procedurally-generated maps, 60 games vs `viper_v7.12`):
**21.7% win rate**, vs this build's usual ~40-50% on the *official* `CORE_PANEL`. Deaths are
dominated by "lost a head-to-head" (70%), not crashes — we're not navigating badly, we're genuinely
losing the growth race on maps with no `maps_data.hpp` entry. **Nearly every validated fix this
session (`gamma` by bed-density, `wCompass`, the `hotRate` bypass, spawn-based map resolution)
depends on exact known-map data** — strip that away, which describes every real, new tournament map,
and the fallback behavior is apparently much weaker than the local panel ever revealed (that panel is
entirely maps we already have data for). **This plausibly explains why local 8-map win rates have
never fully translated to the real ladder**, and reframes the long-deferred "Phase 2" idea (a sonar-
shared coarse map for unknown maps) from a nice-to-have into probably the single highest-leverage
unstarted work. **Next step**: a `BC_DEBUG` trace of one lost `maps_gen` game to see the early-game
foraging behavior with zero known-map data, same technique that found Trauma's original bug.

**First real attempt, tried and reverted (2026-09-30 night)**: built a self-sensed
`bedDensity`/`wallDensity` (echo + vision accumulation, no lookup table, `world.hpp`'s
`selfBedDensity()`/`selfWallDensity()`) and fed it into `gamma`'s existing density adaptation as a
fallback for unresolved maps. Tested directly on the same 30-map/60-game protocol: 18.3%, then a
reverted-gamma re-run came back 15.0% -- both below the historical 21.7%, but **not a clean
comparison**: the original 21.7% baseline necessarily used the sandbox judge (`--judge zig` didn't
exist yet when it was measured), both tonight's re-runs used Zig, and Zig-vs-sandbox was never
specifically verified on any `maps_gen` map. Reverted `gamma` back to known-map-only regardless, on
the logic alone (a locally-biased local sample doesn't substitute for the true global statistic that
term was calibrated against — see insights.md's full reasoning), not on these specific noisy
numbers. The sensing infrastructure itself stays; it just needs a better-designed consumer than a
retrofit onto a term built for exact data. **`maps_gen`'s generalization gap is still open, and every
variant tested tonight (15-22%) remains far below the known panel** -- the real problem is unsolved.
Process lesson: pin the judge backend identically across any two runs being compared, same as seeds.

## 5. Open problems, ranked by evidence strength

1. **Slithery Fight: catastrophic, map-wide runaway split-death spiral — confirmed NOT caused by
   emergency-split.** Real ladder losses to 3 different 1700+ opponents show 600-1000+ of our own
   deaths *per game* on this one map (vs <60 on most others), overwhelmingly hit-wall/hit-self.
   Reproduced locally: our side spawned **1300+ dragons in a single 500-round game** (bot id reached
   1391+), taking 5x longer to simulate than a normal map. `bceval` dated 4 independent losses on
   this map to a collapse at almost exactly **round 360-410**, close to `feedRound=400` — but an
   isolation test (emergency-split forced off, direct `unswbc run --sandbox` to bypass
   `tourney.py`'s 240s timeout, same seed 1000) came back **virtually identical to the baseline**
   (5m23s vs 5m15s, 26113 vs 26170 dragon-turns, bot id still 1386+) — **emergency-split is ruled
   out.** (Correction: an earlier pass here claimed the map has no interior walls, based on
   misreading `TILE` lines as terrain — those are actually pearl-spawn directives. Properly checked
   via `EDGE` data: the map has 514 kelp edges, which block movement like a wall, plus 4 portals,
   among 3402 edges on 1701 cells — real, fairly dense wall/kelp structure, not an open arena.) Both
   sides (including unmodified `viper_v7.12`, which has no emergency-split feature) show the
   identical pathology, so the cause is something both bots' ordinary swarm-splitting logic hits on
   this map's layout, independent of the emergency-split mechanism. **Leading hypothesis** (untested):
   the articulation-point/chamber-trap failure mode from §7 — a bud landing in a pocket that looks
   open by cell-count but is reached through a kelp-bounded corridor that can seal shut. **Recommended
   next step**: a direct `BC_DEBUG` trace of the round-360-410 collapse window to see the actual board
   layout and death pattern before guessing further. Slithery Fight
   (and Schooltime) were **never part of the local 6-map validation panel** used for most of this
   rewrite — a real process gap, now fixed (`tools/tourney.py`'s `CORE_PANEL` is the 8-map list that
   should be used from here on). **Settled (2026-09-30): sonar-range enemy avoidance
   (`Params::wProbeDanger`) does not fix this map.** A flat weight moved Slithery Fight alone from
   0%→50% (4 games) and a wall-density-gated version produced a striking Schooltime result
   (25%→75%, all 4 bceval-`recovered`) — but a follow-up SPRT isolated to exactly these two maps
   (29 games) came back **reject** at 27.6%, indistinguishable from the ~25% baseline. Both small
   results were noise. Not shipped, not worth further tuning at this weight.
   **The articulation-point hypothesis is now refuted, and the actual BC_DEBUG trace was finally run
   (2026-09-30 night)**, both on the same night: built `Params::chamberCheck` (corridor-walk chamber
   check for `trySplit`'s bareExit gate) and A/B tested it directly on this map -- 0% change (607/619
   deaths, identical to every prior baseline). Then ran the real trace (Zig judge's `--debug 3`, a
   reproducible local seed): the death rate does **not** spike at round 360-410 locally (peaks at
   200-299, declines after) -- that characterization came from ladder replays against different
   opponents and may be opponent-specific. The real mechanism, from `dragonLog` text: dragons get
   fully sealed by static kelp (**472** "every direction is kelp-or-own-neck" log lines in one game),
   starting as early as round 2-4 for freshly-spawned/split dragons -- but the trap develops over
   *ordinary movement turns after* a split, not at split-decision time, so `chamberCheck` was never
   going to catch it. **New, unconfirmed but concerning**: in this one game, every early trap hit
   *our own team specifically* (team 1/side B), not both sides symmetrically as an earlier, different
   isolation test suggested -- needs a 2-3-game symmetry check before trusting. **New next step**:
   trace why `scoreFrom`'s existing per-move `space >= need` flood-fill veto doesn't prevent walking
   into a pocket that's about to seal, rather than another split-time check.
   **Symmetry check (done) + wCompass isolation (done)**: repeated the trace with sides swapped --
   early kelp-traps again hit only our bot's team, ruling out "symmetric map hazard" and "which side
   spawns where." Then tested `wCompass=0` on the same seed: byte-identical result (670/622 deaths,
   472 trapped-lines, unchanged) -- rules out `wCompass` too (or confirms it never activated in this
   game at all). **Three hypotheses now refuted** (articulation-point, round-360-410 timing,
   `wCompass`); one confirmed fact stands (bot-specific, not map-symmetric); root cause still open.
   Next: trace the moves *leading up to* a trap, not just the trap itself, and check whether
   `scoreFrom`'s safety veto accounts for a pocket shrinking from the dragon's own growing body.
2. **Trophy: near-instant collapse, not a slow bleed — and it's specific to playing side B.** A
   fresh local 8-map `bceval_batch.py` run (vs `viper_v7.12`, `--keep-replays`) found a sharp side
   asymmetry: 100% dominant wins as side A (2/2), 100% early collapse (~round 19) as side B (2/2).
   Trophy has `bedDensity=1.0` (every cell a pearl bed) — since dragons act in ascending id order
   each round, whichever side's dragons act first may get a systematic first-claim advantage that
   compounds fast when literally every tile matters. **Testable, not yet confirmed** — check whether
   side A correlates with "acts first" in dragon id order specifically on this map, and whether
   forcing interleaved/flipped turn order in a controlled test changes the result. Reframes the old
   project-wide "side A wins more" finding from an unexplained engine quirk to a possible real
   mechanistic effect on maximally-dense maps. `bceval` shows all 3 sampled ladder losses on
   Trophy crash from ~50% to ~88-90% *against* us by round 39-40 and never recover — a sharp, early
   failure, not a gradual one. Matches the known "opponent claims the pearl-dense region and
   out-breeds us" diagnosis, but the precision (round 0-40) narrows where to trace next: a direct
   `BC_DEBUG` replay of Trophy's opening 40 rounds (the same technique that found Trauma's 78-round
   blind-forage bug) is the recommended next step, not further parameter tuning.
3. **Schooltime: head-to-head-dominated losses** (265 of 574 total deaths across 3 games) — a
   different failure mode from Slithery Fight's DOOMED spiral. Not yet traced.
4. **Trauma: still 0/6 on every fix tried across two full sessions** (gamma adaptation, hot-bed
   bypass, wCompass, wCompass room-factor gating, territory clustering, emergency split). Games now
   run the full 500 rounds with much closer death ratios than before, so this reads as "close, not
   fixed" rather than "no progress." The best untried lead is a properly gated (low-global-
   bedDensity-only) version of territory clustering, or the articulation-point room check in §6.
5. **Late-game length consolidation**: still spreads length across many swarm dragons instead of one
   queen winning the round-500 tiebreak reliably. Three targeted mechanism patches (queen-gossip,
   staggered feed, feed-throughput-cap) all failed to move a fixed test case — leaderboard analysis
   suggests top teams win with *small, early-committed* cores rather than a late mass-feed collapse,
   but this needs a genuine macro change to test, not another patch.

## 6. Tools available

| Tool | What it answers |
|---|---|
| `tools/tourney.py` (`CORE_PANEL` = trauma/autarky/trophy/default/dilemma/devil/slithery_fight/schooltime) | Local batch validation, both sides, multiple seeds. **Use `CORE_PANEL`, not a 6-map subset.** |
| `tools/battlecode-eval/` (new, 2026-09-30) | `uv run --python 3.11 --with pycapnp python -m bceval <replay> --every N` — win-probability per round from a `.replay`, third-party (MIT), 66-84% accurate. Answers "when did this game turn" in one command; **use this first on any new loss, before manual death-cause tallying.** |
| `tools/bceval_batch.py` + `tourney.py --keep-replays DIR` (new, 2026-09-30) | Runs `bceval` over a whole batch of replays and classifies each game's shape (dominant/close/early-mid-late collapse/recovered), not just win/loss. Works on **local sandbox games too** — pass `--keep-replays DIR` to `tourney.py` to save replays instead of discarding them, then `uv run --python 3.11 --with pycapnp python tools/bceval_batch.py DIR --ours <bot dir name>`. **Use this as the standard way to read any local validation batch from now on**, not just real ladder losses — an "early collapse" cluster during ordinary local testing is worth tracing immediately rather than waiting for it to show up on the ladder first. |
| `tools/replay.py`, `ladder_report.py`, `board_at.py`, `early_game.py` | Existing decoders for exact death causes, positions, per-dragon-turn economy. |
| `tools/queen_growth.py` | Unit-count/longest-dragon timeline from any replay — used for the leaderboard consolidation analysis. |
| `tools/param_search.py` | Coordinate-descent tuning of `common.hpp` `Params` against a tourney fitness function. Runs against `viper_vS4.7_tune/` — **must be manually re-synced from `viper_vS4.7/` before every launch**, it has drifted stale unnoticed twice already. |
| `tools/scout.py`, `scout_report.py`, `profile_team.py` | Download and profile top-ladder teams' public replays. |

## 6a-fix. Fixes/tooling worked out from the Loong research (2026-09-30)

- **Shipped**: `gossip.hpp` now filters self-sent sonar messages (`m.sender == own id`) — fixes the
  wrap-around self-reception bug, no behavior change today (verified by smoke test) since it was
  latent, but required before `T_CHOKE` is ever relied on.
- **New tool, `tools/sprt.py` + `tools/sprt_test.py`**: Sequential Probability Ratio Test A/B driver
  — plays a candidate vs a fixed opponent and **stops as soon as the result is statistically
  decided**, replacing the fixed-16/32-game-batch-plus-eyeball approach used for every test this
  session. `uv run --python 3.11 --with unswbc python tools/sprt_test.py CANDIDATE OPPONENT --maps
  ... --p0 0.5 --p1 0.6`.
- **New gated experiment, `Params::kamikazeLen`** (default 0, off): a non-grower dragon at or below
  this length always treats hunting an enemy as worth it, bypassing `tradeOk`'s population-floor
  gate — a direct, minimal port of Loong's unconditionally-aggressive Kamikaze role, motivated by
  this session's own population-lead finding (§1a). Not yet A/B tested for real, just smoke-tested.

## 6a-maps. maps_gen/ was empty all session — now populated, not yet tested (2026-09-30)

The Loong "maps nobody has seen" post found real bugs (self-portal-collision, teammate-collision)
that only showed up on their procedurally-generated maps, never on official ones. Checked our own
`maps_gen/` (documented in `AGENTS.md` as an existing 300-map unseen-map asset) — **it was empty,
never generated this whole project**. Generated it now (`tools/gen_random_maps.py --n 300 --seed
1`). **Not yet run against anything** — the natural next validation step (`tourney.py` against a
`maps_gen/gen_*` sample) is deliberately deferred to whenever there's free CPU, since Slithery
Fight/Schooltime already proved a narrow official-map panel can hide serious, ladder-relevant bugs.

## 6a-built. Zig judge: built, verified, and working in WSL2 (2026-09-30)

Following up on the earlier "couldn't build on native Windows" finding — the user installed WSL2,
and it's now built and **verified working on our own bots**: ran the identical matchup
(`viper_vS4.7` vs `viper_v7.12`, Dilemma, seed 1000) through both `unswbc --sandbox` and the new
judge — **identical outcome** (same winner, round count, turn counts, points-per-turn stats to the
exact number), confirming correctness directly, not just trusting the blog's own test suite.
**~2.8x faster** on this test (5.2s vs 14.7s).

- Binary: `~/toolchains/zig-judge-out/bin/loong-judge` inside WSL2 Ubuntu.
- Engine wasm: `~/venv/lib/python3.14/site-packages/unswbc/unswbc_engine.wasm` (WSL-side venv +
  `pip install unswbc`).
- Invoke: `loong-judge --engine <engine.wasm> --map <map> --a <bot.wasm> --b <bot.wasm> --seed <N>`
  — reads Windows-side files fine via `/mnt/c/...`.
- **Setup gotchas worth remembering**: use `wsl -d Ubuntu -u root` for anything needing elevation,
  never `sudo` (hangs forever waiting for a password prompt in non-interactive `wsl` calls). WSL's
  network can't reliably reach GitHub's release-asset CDN (TLS resets) even though it reaches other
  CDNs fine — download on the Windows side and copy via `/mnt/c` instead. The repo needs a *current*
  wasmtime release (v49.0.1 worked; their pinned-to-nothing `nixpkgs#wasmtime` reference means "use
  whatever's current," not an old pinned version — v27 was too old, missing newer C API functions).

**DONE (2026-09-30, later same day)**: wired in as `tools/tourney.py --judge zig`. `play_zig()`
shells out to `wsl -d Ubuntu -- loong-judge --engine <fixed path> --map ... --a ... --b ... --seed
...`, parses its one tab-separated figures line (winner/rounds/reason/deaths-by-cause/points, field
layout confirmed against `game.zig`'s own doc comment and a live run), and maps its 5 death-cause
codes (W,S,O,H,A) onto our existing 4 categories + a new "no valid action" bucket. Verified against
known ground truth: same matchup/seed via `--judge zig` reproduced the exact same win/rounds/death
counts as an earlier `--judge sandbox` (default) run. Real speedup confirmed on a heavier matchup
too (not just the easy Dilemma case): `viper_vS4.7` vs `viper_v7.12` on Trophy, seed 1000 — 58.9s
(zig) vs 142.7s (sandbox), same winner/rounds/turns/points down to the exact number. Paths
(`ZIG_JUDGE_WSL`/`ZIG_ENGINE_WSL` constants in `tourney.py`) are this machine's WSL2 setup only —
not portable, rebuild per the setup gotchas above if this ever moves machines.

Caveat found while wiring it in: the speedup is engine/harness overhead only — it does **not** speed
up a bot's own heavy per-turn computation (confirmed by the Trophy case: `viper_v7.12`'s deep search
dominates wall time either way). Expect ~2-2.5x on real matchups, not a fixed multiplier independent
of which bots are playing.

**Second caveat, found and fixed (2026-09-30)**: by default the Zig judge records zero
`dragonLog`/`dragonIndicator` events (vs the sandbox's 1450/6501 on an identical game) — but it's
just a missing `--debug` flag (`DEBUG_LOGS=1|DEBUG_INDICATOR=2`, default 0), not a real limitation.
`tourney.py --judge zig --debug` now passes `--debug 3` and matches the sandbox's event counts
exactly. Use plain `--judge zig` for win/loss batches, add `--debug` for any BC_DEBUG trace.

## 6a-more. Zig judge, cloud infra, and a real tourney.py fix from deeper Loong research (2026-09-30)

Cloned the actual repo (`github.com/overyonder/the-loong-game`) to investigate concretely:

- **Zig judge**: open source (`harness/zig_judge/`), verified ~4x faster / 2.85x fewer core-seconds,
  byte-identical replays across 144 paired tests vs the official toolkit. **Tried to build it locally
  and hit a real wall**: needs `libunwind` + an externally-supplied wasmtime C API, normally from a
  Nix/Linux dev shell — not available on native Windows, and no Docker/WSL here either to sandbox it
  safely. **Did not force a risky build** — a subtly-wrong judge binary could silently corrupt test
  data. This is built for Linux; the honest path to using it is a Linux environment, not fighting
  Windows compatibility.
- **Cloud cost numbers** (their real AWS pipeline: spot instances, S3, SQS, OpenTofu): **~$0.04 per
  1000 games**. At that rate the user's $100 in cloud credits could buy **2M+ games** of testing —
  several orders of magnitude past what this 12-core local machine can do. Not acted on without the
  user's own account/credentials and explicit spend approval.
- **Found and fixed a real bug in our own `tourney.py`**: their harness keeps timeouts/crashes in a
  separate error column, never counted as a draw. Checked ours — the display *label* was already
  correctly "ERR" vs "DRAW", but **both incremented the same `draws` counter underneath**, meaning
  every timeout batch this session (Devil, Slithery Fight) was silently indistinguishable from a real
  draw in the actual stats. **Fixed**: `tourney.py` now has a genuine `errors` bucket, excluded from
  win/loss/draw percentages, with a visible `E` column. Syntax-verified; live re-verification
  deliberately deferred to avoid competing with the running `param_search_bceval` job.
- Other harness ideas not yet ported: Bradley-Terry ratings + 95% CIs (pairs with the SPRT tooling),
  content-hash result caching (would've caught the `viper_vS4.7_tune` drift mistakes earlier),
  process-group timeout handling (more robust than a bare `subprocess.run(timeout=...)`).
- Their language-choice post (Nim over Python/C/C++) and columnar replay-data format are lower
  priority for us — we already write native C++ (the fast end of their tradeoff), and our `.pkl`
  replay cache is adequate at current analysis volumes.

## 6a. over-yonder.tech/games/loong — a dev blog for this exact competition (2026-09-30)

Found a 19-post series accompanying UNSW Battlecode 2026. Four directly relevant findings:

- **Roles**: a clean, fully decentralized 3-role system (Champion/Kamikaze/Worker) self-assigned
  every turn purely from sonar-heard teammate lengths — a working realization of the ant-colony
  response-threshold idea. Their Kamikazes (≤3 segments, has a longer teammate) *aggressively* trade
  with enemy heads by design, more aggressively than our own safety-gated `tradeOk`/`huntNext` logic
  — worth reconsidering given the population-lead finding above (a short dragon is cheap to trade).
- **Tactics (feeding)**: the author's own result — "performing roughly equal to the simpler
  roles-based strategy" — **independent confirmation that feed/consolidation tuning is genuinely
  low-leverage for everyone**, not something we're uniquely getting wrong (matches this session's own
  queen-gossip/staggered-feed/throughput-cap all-neutral results).
- **Sonar bug, found in our own code**: none of `gossip.hpp`'s message handlers filter by sender id —
  the board wraps, so an unobstructed sonar ray can loop back to its own sender (a bug the blog's
  author explicitly hit). Low impact today (`wChoke=0`), but **fix before `T_CHOKE` is ever enabled**:
  `if (m.sender == w.init.id % 4096) continue;`.
- **SPRT testing methodology — the highest-value general finding.** Every A/B test and
  `param_search` result this session used a fixed 16-32-game batch plus an eyeballed win-rate
  threshold, repeatedly caveated as "noisy." A Sequential Probability Ratio Test stops as soon as a
  result is statistically decided (often far fewer games) instead of always running a fixed batch.
  **Recommended next tooling investment**: implement SPRT in `param_search.py`/`tourney.py`'s A/B
  path.

## 6b. Complementary-team analysis: a real, well-evidenced opening lead (2026-09-30 morning)

Our real per-map profile vs 3 top opponents (35 games): **Schooltime/Slithery Fight/Trauma/Trophy
0%**, Autarky/Default/Dilemma 25%, Portals 33%, Devil 50%, QoS 67%. Screened scouted top teams for
who's strong exactly on our worst maps — **`Sabotage-d`** (teamId 46) and `SSS` (teamId 91) both go
4/4 on Schooltime specifically. Their replays show an aggressive **round-0 multi-way split** opening
(vs our later, gated first bud) and they win Slithery Fight/Schooltime via the **longest single
dragon**, not raw population (one game: 5 dragons/longest 66 beat 21 dragons/longest 51).

Ran a real unranked battle against `Sabotage-d` (using the currently-active team submission, not
S4.7 — it hasn't cleared the gate): **0/25, clean sweep, `bceval` shows 4/5 are `early` collapses**
(round 39-99). This confirms an early-game tempo deficit, not an S4.7-specific issue, and lines up
exactly with the session's own strongest meta-finding (population lead from round 100 decides most
games). **Best-evidenced concrete next mechanism**: a more aggressive opening split policy, closer
to "split immediately and often from round 0" than the current `swarmSplitLen=4`/`growRound=300`
gating. See `insights.md`'s "Map profile + complementary-team analysis" for the full writeup.

## 7. Research-backed ideas not yet implemented

From competitive Battlesnake/Tron rule-based AI (not neural — these communities solve the identical
core problem: grid pathing, space-claiming, no-return-into-own-body):

- **Voronoi area control — already half-built, cheapest next win.** `Policy::buildFriendFields()`
  (`policy.hpp:448`) already computes `friendDist_`/`enemyDist_` via multi-source BFS from every
  visible head, and `enemyCloserFactor` (`policy.hpp:653`) already discounts a contested pearl
  target. What's missing — ported from `viper_vS4.6`'s kept `FEATURE_TERRITORY`, not a new idea — is
  the other half: a direct move-safety penalty for standing in enemy-favored territory
  (`margin = clamp(enemyDist-friendDist,-10,10); if margin<0: score += margin*0.6`), which costs
  **zero extra BFS** since the fields already exist. A more principled version of the reverted
  bed-clustering hack (`territoryWeight`). Pairs with map-adaptive params by scaling the penalty
  weight by a board-openness stat (or reusing `bedDensity`) — contested space should matter more on
  open maps (Devil, Slithery) than tight mazes (Trauma) where paths are already constrained.
- **Articulation points / chamber analysis** ("chamber trees" from Tron AI postmortems): before
  entering a region, check whether the path there passes through a cut-vertex, and if so require it
  to lead to the *largest* remaining connected chamber among the options. This is a real upgrade over
  the current `bareExit`/`hasRoomyMove` checks, which count reachable cells but don't detect "this
  looks big enough but the only way in is a corridor that could seal shut" — the exact failure shape
  behind the reverted `trySplit` rescue-mode experiment on Trauma's maze layout, and (pending a direct
  trace) the leading hypothesis for the Slithery Fight spiral too — that map has real, fairly dense
  kelp/wall structure (§5.1), not the open arena an earlier pass here mistakenly claimed.
- **"Fewest edges removed" tie-break**: when two moves lead to similarly-sized open areas, prefer the
  more wall-adjacent (less central) one — a cheap heuristic for efficient space-filling without a
  full chamber analysis every turn.
- **ID-based echo-wave leader election**: a clean, cheap fix for `gossip.hpp`'s `T_QUEEN` claim —
  break exact-length ties by dragon id so the swarm always converges on one deterministic queen
  instead of possibly oscillating between equal-length candidates. One-line comparator change.
- **Ant-colony response-threshold task allocation**: each dragon decides "am I feeding yet?" from a
  local stimulus (own length vs. the gossiped queen claim) instead of a global-round switch
  (`growRound`/`feedRound`) — could naturally stagger feed-phase convergence (implicated in the
  Portals self-trap cluster and possibly part of the Slithery Fight spiral) without the previously-
  tried-and-neutral fixed-offset `feedWindow` staggering hack.
- **Scavenging windfalls**: competitive Snake.io tactics emphasize eating pearls dropped by *any*
  dead dragon, not just steady bed income. Worth checking whether a sudden nearby multi-pearl drop is
  valued with appropriate urgency by the current decayed-distance scoring (tuned for steady
  respawning beds, not one-time windfalls) — cheap to check, not yet investigated.
- **Sonar reservation messages (`T_INTENT`/`T_CHOKE`), ported from `viper_vS4.6`'s `msgauth.hpp`**:
  a dragon broadcasts its next 3 moves (`T_INTENT`) or reserves a chokepoint cell for a few rounds
  (`T_CHOKE`); receivers avoid routing through reserved cells — a decentralized reservation-table
  technique (matches the multi-agent collision-avoidance research above), already built once in an
  earlier lineage and **not flagged as reverted** (only the fountain-pheromone grids were). Directly
  relevant to Schooltime's head-to-head-dominated losses and the Portals/Slithery Fight congestion
  problems. Worth an isolated test in S4.7's cleaner framework — S4.7 currently uses only 2 of
  `msgauth.hpp`'s 8 message types (`T_FOUNTAIN`, `T_QUEEN`).

See `s4_7_user_idea_list.md` (assistant memory) for the fuller 24-idea brainstorm and its priority
ordering against these findings — Voronoi/chamber analysis now rank above most of that list given how
precisely they target the two worst-evidenced remaining problems (§5.1, §5.4).

## 8. Process lessons

- **The local test panel must include every map a real opponent will play on.** Slithery Fight and
  Schooltime were excluded from validation for the entire rewrite and turned out to be the two worst
  maps by a huge margin — always test against the full live-map list before trusting a "validated"
  result.
- **Local testing against a single opponent (V7.12) is not sufficient.** A real online test found a
  DOOMED-death regression that 150+ local games against V7.12 never surfaced. Include a genuinely
  different opponent (scouted top-team replays, or a real unranked ladder test) before promoting.
- **`unswbc run --sandbox`'s build cache is keyed on `main.cpp`'s content, not mtime.** A header-only
  change needs an actual edit to `main.cpp` (a `// rebuild-marker` comment works) or the sandbox
  silently reruns the stale build with identical results — looks exactly like "my change had no
  effect."
- **Never manually overwrite a file a long-running tuner (`param_search.py`) is actively mutating.**
  Doing this once silently reset an in-progress `gamma` finding mid-sweep, invalidating every result
  logged after that point.
- **Isolate one variable at a time**, even when it costs more wall-clock time than a combined test —
  every genuinely resolved question this session (territory clustering vs. emergency-split;
  queen-gossip/staggered-feed/throughput-cap vs. the pre-existing Trauma/Autarky weakness) was
  resolved by a same-protocol isolation test, not by reasoning about a combined result.
