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

## 5. Open problems, ranked by evidence strength

1. **Slithery Fight: catastrophic, map-specific runaway split-death spiral.** Real ladder losses to
   3 different 1700+ opponents show 600-1000+ of our own deaths *per game* on this one map (vs <60 on
   most others), overwhelmingly hit-wall/hit-self. Reproduced locally: our side spawned **1300+
   dragons in a single 500-round game** (bot id reached 1391+), taking 5x longer to simulate than a
   normal map. **New finding (bceval, see §6)**: 4 independently-sampled losses on this map all
   collapse at almost exactly **round 360-410** — suspiciously close to `Params::feedRound=400`.
   Working hypothesis: the feed-phase convergence interacts badly with this map's geometry, likely
   producing repeated "no safe move" states that keep re-triggering the new emergency-split fix in
   an unstable loop. **An isolation test (emergency-split forced off on this map) is the direct next
   check** — not yet resolved as of this writing, check `ladder/losses/noemergency_slithery_test.txt`.
   Slithery Fight (and Schooltime, see below) were **never part of the local 6-map validation panel**
   used for most of this rewrite — a real process gap, now fixed (`tools/tourney.py`'s `CORE_PANEL`
   is the 8-map list that should be used from here on).
2. **Trophy: near-instant collapse, not a slow bleed.** `bceval` shows all 3 sampled ladder losses on
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
| `tools/replay.py`, `ladder_report.py`, `board_at.py`, `early_game.py` | Existing decoders for exact death causes, positions, per-dragon-turn economy. |
| `tools/queen_growth.py` | Unit-count/longest-dragon timeline from any replay — used for the leaderboard consolidation analysis. |
| `tools/param_search.py` | Coordinate-descent tuning of `common.hpp` `Params` against a tourney fitness function. Runs against `viper_vS4.7_tune/` — **must be manually re-synced from `viper_vS4.7/` before every launch**, it has drifted stale unnoticed twice already. |
| `tools/scout.py`, `scout_report.py`, `profile_team.py` | Download and profile top-ladder teams' public replays. |

## 7. Research-backed ideas not yet implemented

From competitive Battlesnake/Tron rule-based AI (not neural — these communities solve the identical
core problem: grid pathing, space-claiming, no-return-into-own-body):

- **Voronoi area control**: flood-fill from *every* living dragon's head at once (not just our own),
  and value the region where we reach a cell in fewer moves than any opponent. A more rigorous,
  general version of the shelved bed-clustering idea — claims *contested space*, not pearl locations,
  so it doesn't need `territoryMaxHot`-style density gating to stay cheap or to avoid the Dilemma
  regression. One multi-source BFS per turn.
- **Articulation points / chamber analysis** ("chamber trees" from Tron AI postmortems): before
  entering a region, check whether the path there passes through a cut-vertex, and if so require it
  to lead to the *largest* remaining connected chamber among the options. This is a real upgrade over
  the current `bareExit`/`hasRoomyMove` checks, which count reachable cells but don't detect "this
  looks big enough but the only way in is a corridor that could seal shut" — the exact failure shape
  behind the reverted `trySplit` rescue-mode experiment and a plausible contributor to the Slithery
  Fight spiral (§5.1). **Best-scoped concrete next implementation.**
- **"Fewest edges removed" tie-break**: when two moves lead to similarly-sized open areas, prefer the
  more wall-adjacent (less central) one — a cheap heuristic for efficient space-filling without a
  full chamber analysis every turn.

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
