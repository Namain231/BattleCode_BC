# S4.7 insights (live notes, 2026-09-29)

Working log for the `viper_vS4.7` rewrite effort. For full blow-by-blow detail and reasoning, see
the assistant's memory file `s4_7_rebuild_progress.md`; this file is the human-readable summary.
Versioned snapshots live in `baselines/S4.7.x/` as they're validated.

**Submission naming for this lineage: `S.4.7.x` / `S.4.x`** (dotted). The v10.1/id-10822 submission
described below used the wrong scheme by mistake — use the correct one for everything from here on.

## OVERNIGHT RUN STATUS (read this section first if checking in later)

Reverted `wCrowd` (1.0→0.4) and `feedMaxLen` (999→6) back to the last broadly-validated values,
after the online test below showed a severe DOOMED-death regression. **Five background jobs
running concurrently** as the standing 3-frontier + qualifier cycle the user asked for:

1. Qualifier tournament vs `viper_v7.12` (10 live maps, 2 seeds) — `ladder/losses/qualifier_v712.txt`
2. Qualifier tournament vs `baselines/v7_5` — **this is mislabeled and actually V6 content** (same
   bug already known for `baselines/v7_12`; no real V7.5 source was found locally) —
   `ladder/losses/qualifier_v75.txt`
3. Qualifier tournament vs `viper_vS4.6` — `ladder/losses/qualifier_s46.txt`
4. Self-play collection (restarted on the reverted code) — `ladder/losses/selfplay_log.txt`
5. New automated parameter search (`tools/param_search.py`, coordinate descent over `common.hpp`,
   broad multi-map/multi-seed evaluation, runs against an isolated `viper_vS4.7_tune/` copy so it
   doesn't race the qualifiers) — `ladder/losses/param_search_log.txt`,
   `ladder/param_search/log.jsonl`

**UPDATE (2026-09-29): Phase 1 map-adaptive parameters implemented and validated.** Full detail in
the assistant's memory (`s4_7_v4_and_beyond.md`); this is the consolidated summary.

### What's confirmed and solid
- The Abyss-framework rewrite structurally fixed S4.6's 93%-DOOMED-death crisis.
- Pearl gossip + crowding is a genuine, validated improvement: ~56.6% vs V7.12 on clean maps
  (excluding infra-timeout-corrupted ones), up from S4.6's 20-40%.
- `splitEnemyDist` swarm-exemption was the single biggest lever found early on (V7.12's own bud
  logic has no enemy-distance safety gate at all; ours did, and it silently blocked almost all
  swarm splitting once the board got populous).
- Traced one real trauma game via debug logging: our dragon foraged blind for **78 straight
  rounds without eating a single pearl**, then got trapped — confirming the trophy/trauma/autarky/
  default weakness is a real, structural foraging problem, not bad luck. (Correction: an earlier
  note here claimed trauma's beds "just barely miss" the hot-bed threshold — that had a 10x
  arithmetic slip; the real rate is ~0.01, genuinely slow, not a near-miss. The bypass fix — trust
  known bed rates instead of gating them by a threshold meant for noisy learned data — is still
  reasonable and kept, just not for the reason first stated.)
- **A single flat `gamma` cannot serve every map**: found that `gamma=0.72` (down from the default
  0.80) helped trophy/default a lot but badly regressed dilemma (75-100% → 17%) in a full 36-game
  test. This is now fixed properly: **`gamma` is map-adaptive**, scaled by a measured map property
  (`bedDensity` — the fraction of all cells that hold a pearl bed) rather than a hand-picked
  constant. Validated: dilemma recovered to 67% while trophy/default/devil kept their gains
  (devil even reached 100%). This is a real instance of the "map-adaptive parameters paired with
  map prediction" architecture, not just a discussed idea — see the dedicated section below.
- Enemy head-velocity prediction and the queen-gossip/staggered-feed/throughput-cap consolidation
  mechanisms are roughly neutral — kept (no evidence of harm) but not load-bearing fixes.

### Map-adaptive parameters (Phase 1) — architecture note
The tension "no map-specific strategies, but new maps need generalizable tuning" resolves cleanly
once you separate *map identity* (a name lookup — breaks on new maps) from *observed map
structure* (a measured property — defined on any map, including ones never seen before).
`KnownMapMatcher::adapt(Params)` (in `knownmap.hpp`) computes `bedDensity` the instant a known map
resolves and derives `gamma` from it; on any unrecognised or not-yet-resolved map it returns the
untouched safe defaults. **Phase 2** (not yet built): the same adaptation driven by a
sonar-shared coarse map for maps with no `maps_data.hpp` entry at all — the real generalization
story, since Phase 1 only helps the ~15 maps already known.
**Caution**: the specific `gammaDensityFactor=0.08` constant and the squared-density shape were
fit to 6 known maps' worth of evidence — validate against `maps_gen/`'s 300 unseen maps before
fully trusting it generalizes.

### Root cause found and fixed: `wCompass` (2026-09-29)
Direct debug tracing of a trauma game (`#define BC_DEBUG`, same seed re-run at every stage) showed
the *identical* 78-round blind-forage window survive every fix tried so far, including the hot-bed
certain-data bypass and a `horizon` bump from 48 to 90 tested in isolation. That ruled out both
"threshold too strict" and "BFS horizon too short" as the real explanation. The actual bug: the
long-range pull's value contribution is `wHot * rate * gammaFar^m` (`gammaFar = 0.93`), and this
decays so fast that even a bed correctly recognised as reachable within `horizon` contributes
essentially nothing once `m` (moves away) exceeds ~40-50 — on a 1152-cell map like trauma, the
nearest known bed from a given spawn can legitimately be 60-90+ tiles away by path distance, well
past the point where `0.93^m` rounds to noise. The mechanism was *included* the bed but the
*score* from it was too small to ever move a dragon.

**Fix**: added a second, undiscounted pull — `Policy::macroTarget_`/`macroDist_` (`policy.hpp`,
`buildTargets()`/`scoreFrom()`) — computed once per turn as a single full-board BFS (`Nav::bfs`,
cheap: at most `b.NC` nodes, no measurable CPU impact) from the current head. Among known hot beds
whose BFS distance exceeds `horizon` (i.e., ones the existing decayed pull can't reach usefully),
it picks the best rate-per-distance one and adds a flat `Params::wCompass` (0.05) per tile of
progress toward it, applied only to the immediate move (`k==0`, since the macro field is a
snapshot from the real current position, not valid for hypothetical deeper search nodes).

**Validated** (same 36-game protocol as the gamma test: trauma/autarky/trophy/default/dilemma/
devil × 3 seeds × 2 sides vs `viper_v7.12`), before → after:

| Map     | Before (gamma-fix only) | After (+ wCompass) |
|---------|--------------------------|---------------------|
| trauma  | 0/6 (0%)                 | 0/6 (0%) — see caveat below |
| autarky | 0/6 (0%)                 | 1/6 (16.7%)         |
| trophy  | 3/6 (50%)                | 3/6 (50%)           |
| default | 2/6 (33.3%)              | 4/6 (66.7%)         |
| dilemma | 4/6 (66.7%)              | 4/6 (66.7%)         |
| devil   | 6/6 (100%)               | 6/6 (100%)          |
| **Total** | **15/36 (41.7%)**      | **18/36 (50.0%)**   |

Net +8.3pp overall, no map regressed. **Trauma caveat**: still 0/6, but qualitatively different —
games now consistently run the full 500 rounds (vs. early elimination before) with much closer
death ratios (e.g. seed 1034: 104 our deaths vs 161 theirs, vs. 82/176 before), and the top death
cause on trauma flipped from "lost a head-to-head" to "hit a wall" — consistent with dragons now
actually traveling toward known beds (and running into more walls while doing it on a maze-heavy
map) instead of drifting blind. This is progress, not a fix; trauma still needs its own follow-up
(the wall-death spike suggests the compass pull isn't yet being weighed against local safety
carefully enough on tight maze corridors — a candidate next step is combining the compass bonus
with the existing flood-fill safety check's margin, or reducing `wCompass` specifically when local
room is tight).

### Two follow-up attempts at trauma's wall-death spike (2026-09-29)

**Attempt 1 — gate `wCompass` by local room (kept).** The compass bonus was unconditional; since
it's a per-tile *nudge*, two candidates equally far from the target but with different amounts of
elbow room got the same bonus, so the pull could favour a narrow corridor over a wide one. Scaled
it by `min(1, space / (2*need))` (using the space/need values `scoreFrom` already computes for its
existing safety veto) so the pull is full-strength in open areas and tapers off in tight ones.
Validated with a same-seed trauma trace (seed 1034, deterministic environment): **byte-identical**
early-game behaviour to the pre-fix trace for that seed (the gating simply didn't bind for this
particular trajectory), and the full 36-game batch confirmed exact parity with the wCompass
baseline (18/36 = 50.0%, identical per-map breakdown). Net effect: neutral on this panel, but
removes a real theoretical failure mode (favouring cramped paths) at no measured cost — kept.

**Attempt 2 — `trySplit` "rescue mode" gating (tried, reverted).** Traced further and found a
second, distinct pattern: multiple *independent* dragon ids died the identical way — `SPLIT 2`
then a wall within 1-2 moves — because `trySplit`'s swarm-child check is `bareExit` ("one free
neighbour cell"), not a real room check (a deliberate earlier-session choice matching V7.12's own
permissive bud check). **User caution, correctly applied before changing this**: a split can be a
legitimate last-resort escape valve — sacrificing a small child into a bad pocket to free an
already-cornered parent is worth it even if the child was always doomed, so a blanket stricter
check would break that. Tried gating: only require real child room
(`hasMinRoom`, a cheap `n + margin` floor) when the *parent* would still have a safe move if it
stayed whole (i.e. this isn't a rescue); keep the original lenient `bareExit` when it is a rescue.
**Result: measurably worse** on the identical trauma seed — wall-deaths 59→69, total deaths
104→119, still lost. Reverted; `hasMinRoom` removed rather than left unused. Working theory: the
stricter check rejected some *routine*, non-desperate splits that `bareExit` used to allow,
eroding the population-growth benefit `bareExit` was chosen for. Full detail and a couple of next
ideas (e.g. gate on the *child's* prospective room directly, not a parent-trapped signal) are in
`s4_7_v4_and_beyond.md`.

**Net for the day**: `wCompass` (validated, +8.3pp: 41.7%→50.0%) plus its `roomFactor` refinement
(validated, neutral but safer) are both in `viper_vS4.7`. Trauma's split-then-wall-death pattern
is real and still unsolved — flagged for a future session, not something to keep poking at blindly
without a new idea (two attempts without a clear win is a good place to stop and think, not iterate
faster).

### What's NOT yet resolved
- Trauma remains a loss on every seed despite every fix tried this session (gamma adaptation,
  hot-bed bypass, wCompass, wCompass's roomFactor gating, and the reverted trySplit experiment) —
  the most competitive it's been, but not yet a win.
- No qualifier vs the other two reference bots (`baselines/v7_5` — mislabeled, actually V6 content
  — and `viper_vS4.6`) has completed since the spawn-fix; only the V7.12 qualifier has real data.
- Self-play made near-zero real progress this whole session (repeatedly paused for CPU contention
  or code staleness) — this is expected and correct per the explicit instruction to keep it paused
  until a stable model exists, not a failure.
- Nothing has been (re-)submitted since "v10.1" (wrong naming, noted for next time), which is not
  active — Y.7.12-nn.1 (id 9285) is, and should stay that way until a build is actually validated.

### S.4.7.5 submitted for ladder testing (2026-09-29, end of session)
Snapshotted the validated `viper_vS4.7` (wCompass + roomFactor gating; `trySplit` rescue-mode
reverted) to `baselines/S4.7.5/` and submitted it as **`S.4.7.5`, submission id 11262**. Build
succeeded and went active. While active, queued 40 unranked challenges (10 maps each) against the
standard panel: 777 (team 590, battles 568798-568807), ANON_TOKYO (547, 568808-568817), hmm (189,
568818-568827), Aviators (543, 568828-568837). **Reactivated Y.7.12-nn.1 (id 9285) immediately
after**, confirmed active via API — the champion should still be active when this session resumes;
check that first if anything looks off.

**Ladder test results, pulled and saved (2026-09-29)**: our elo at test time was **1696**. The
first 4 opponents (777, ANON_TOKYO, hmm, Aviators) turned out to all be rated *below* us — the user
correctly flagged this as a weak test — so 3 more were queued above our elo: 1234 (1706), Maccas
(1728), Quaker Qubits (1765). Corrected results (an initial win/loss tally had a bug comparing the
wrong types and showed 0 wins everywhere — fixed):

| Opponent | Elo | Record |
|---|---|---|
| 777 | 1603 | 4W-6L |
| ANON_TOKYO | 1506 | 7W-3L |
| hmm | 1456 | 9W-1L |
| Aviators | 1475 | 7W-3L |
| **1234** | **1706** | **2W-4L** |
| **Maccas** | **1728** | **5W-1L** |
| **Quaker Qubits** | **1765** | **4W-2L** |

**S.4.7.5 beat 2 of 3 higher-rated opponents** (Maccas +32 elo, Quaker Qubits +69 elo), losing only
to the closest one (1234, +10 elo) — a good sign this isn't just beating up on weak teams.
Total: 38W-20L across all 58 games.

Saved for review: `ladder/S4.7.5_ladder_test/results.json` (full battle/game data, elo, team ids)
and `ladder/S4.7.5_ladder_test/replays/` (all 58 `.replay` files, named `<gameId>.replay` — cross-
reference against `results.json`).

**Note**: while wrapping up, a routine check found `Y.7.12-nn.1` unexpectedly not active (showing
`S.4.7.5` active instead, cause not fully diagnosed — possibly a delayed/cached read after the
earlier reactivate call). Re-issued the reactivate and verified it held over a 15s recheck.
**Next session: verify submission 9285 (Y.7.12-nn.1) is active as the very first check.**

**Handoff for next session**: the user is running the outstanding local qualifiers (vs
`baselines/v7_5`/`viper_vS4.6`) separately and will hand results over. On resume: (1) re-verify
9285 is active, (2) review the 58 saved replays/results above alongside the qualifier results,
(3) decide whether S.4.7.5 is ready to promote, needs more iteration, or should stay parked —
trauma's split-then-wall-death pattern (still open, two attempts tried this session, see above) is
the biggest known gap if more iteration is warranted.

## Where this started

`viper_vS4.7` was rebuilt from scratch on top of the public "Abyss framework" (`bc-abyss-main/`,
released by another team, "Cat's paradise"), because the old S4.7 draft (now at
`viper_vS4.7_draft1/`) and S4.6 both suffered a severe, now-diagnosed bug: **93% of S4.6's real
ladder deaths were self-inflicted "DOOMED" traps** (hit wall / hit self), not combat losses — see
`s4_6_loss_diagnosis.md`. The Abyss framework's proper flood-fill safety check before every move
structurally avoids this class of bug.

## Version lineage

| Version | What changed | Measured result |
|---|---|---|
| S4.7.1 (unsaved snapshot) | Base Abyss framework + `BC_TURN_BUDGET` 0.075→0.060 (CPU safety), `knownmap.hpp` (reuses `tools/gen_maps.py` terrain/pearl data, never guesses on unknown maps), `swarmChild` fixed-size bud instead of halving, `splitEnemyDist` exempted for swarm buds (the single biggest fix — 7x7 vision only reaches distance 3, so gating every split on "no visible enemy" silently blocked almost all budding once the board got populous), `bareExit` (no flood-fill check for swarm buds, matching V7.12's own bud logic exactly), `queenDeferMargin` (defer to a visibly-taller grower teammate) | ~47.5% on a 4-map maze subset vs V7.12, up from a near-total loss pre-fix |
| S4.7.2 (unsaved snapshot) | + `gossip.hpp`: pearl gossip via authenticated sonar (reuses `msgauth.hpp`; proven on this ladder already as part of Y.7.12.3/id 9357, +37% early eating). + `World::crowd`: decaying local stigmergy field (ant-colony-style repulsion, vision-only, no messaging) to reduce self-collision crowding | **56.6% decisive win rate** on a clean 84-game, 14-map, 3-seed tournament vs V7.12 (30W-23L across the 9 maps that weren't corrupted by local test-harness timeouts — see "known weak spots" below) |
| S4.7.3 (unsaved snapshot) | `feedMaxLen` 6→999 (V7.12's own feed logic has no absolute length cap, only "not outranking the queen" — the old cap silently locked most of a long-surviving population out of ever feeding), `wCrowd` 0.4→1.0 (relaxing feedMaxLen let far more dragons converge on the queen at once, causing a smaller version of the original mass-convergence self-trap problem; this was a partial mitigation) | Single-game test on portals: population swung to a **1.5x advantage** (13754 vs 8931 dragon-turns) but still lost on the round-500 length tiebreak, and still showed a cluster of self-inflicted deaths during the feed window — population/safety is no longer the bottleneck there, consolidation is |
| S4.7.4 (`baselines/S4.7.4/`) | + `gossip.hpp` queen gossip (`msgauth::T_QUEEN`): a grower broadcasts its own length+position by sonar, and every dragon keeps the *longest currently-believed* claim (with staleness expiry), not just what's directly visible. | Portals re-test (same seed): still lost on length, population 13359 vs 8895, same self-trap death cluster in the feed window — did not fix it |
| S4.7.5 (unsaved, current) | + staggered feed onset (`Params::feedWindow`, each dragon's feed-eligibility round offset by its own id) to stop the whole army converging on the queen in one synchronised wave | Portals re-test (same seed): still lost on length, population 14224 vs 8885, same self-trap cluster — **saturation reached; see the update below, pivoting away from mechanism patches toward a macro-level rethink informed by leaderboard analysis** |

**Key lesson about the tooling while doing this**: `unswbc run --sandbox`'s build cache is keyed
to `main.cpp`'s *content*, not its mtime — editing a header and `touch`-ing `main.cpp` is **not**
enough to force a rebuild; you need an actual content change (a comment/marker line appended) or
the sandbox silently reruns the stale build with no rebuild message and identical results run after
run, which looks exactly like "my change had no effect" and wastes time chasing a phantom bug.

## The current picture: two distinct, separate problems

1. **Growth-speed problem (trophy, and to a lesser extent the population side of other maps)**:
   early on, V7.12 builds a much larger population much faster than a vision-only bot can. Ruled
   out: swarm split-room requirements were not the bottleneck (relaxing them to zero had no
   effect). Still open: probably raw pearl-targeting/pathfinding efficiency, or the head-to-head
   avoidance behaviour in the first ~50 rounds. V7.12's pearl scoring has an extra "single best
   nearby target" bonus term (`wTarget`) that Abyss's flatter summed-value scoring doesn't —
   untested hypothesis.
2. **Consolidation/tiebreak problem (portals, default, and now confirmed NOT a population issue)**:
   even with equal or superior total population, no single dragon grows long enough to win the
   round-500 length tiebreak. This is the same class of problem already diagnosed for S4.6. Queen
   gossip (S4.7.4) is the current attempt at a real fix — untested as of this writing.

Trophy may have *both* problems: with S4.7.2/3, it started surviving to round 500 in some seeds
(where before it was always eliminated early), but then lost to the *same* consolidation issue
seen on portals — i.e., fixing the growth-speed problem there just exposed the consolidation one
underneath.

## Confirmed strong / weak maps (S4.7.2, clean data only)

- Strong: Colosseum (100%), devil (83%), queen_of_spades (83%), dilemma (67%), default_small (67%), arena (even, 50%)
- Weak, confirmed real (not infra noise): trophy (0%), default (17%), autarky (33%, but noisy —
  swung 50%→17%→33% across different small samples, not fully confirmed as a real regression)
- **Data quality warning**: `tools/tourney.py`'s summary counts genuine 500-round draws *and*
  timeout/crash errors under the same "D" column (a real bug in that script, line ~523). On this
  test machine, `stronghold` and `slithery_fight` were ~100% timeouts (0.0 average rounds, zero
  deaths recorded — not real gameplay), `schooltime`/`portals` were partially corrupted the same
  way. Always sanity-check a high-draw map's average round count and death totals before trusting
  its win rate; a real 500-round draw has real death counts, a timeout has none.

## CRITICAL: first real online test result — much worse than local testing, DOOMED deaths are back

Submitted the current build to the ladder (**note: submitted as "v10.1" by mistake — this
lineage's actual naming convention is `S.4.7.x`/`S.4.x`, dotted; use that for every future
submission**) and sent unranked challenges to two teams near our own rating (1716): **Z-A** (1709)
and **Rogo** (1650).

**Result: 1W-9L against each (10% each)** — dramatically worse than the ~56.6% local sandbox result
vs V7.12. Downloaded and analysed the real replays directly: on Portals and Slithery Fight,
self-inflicted "DOOMED" deaths (hit wall + hit self) outnumbered combat deaths roughly 2:1 — **the
exact 93%-DOOMED crisis the whole Abyss-framework rewrite was meant to fix is back**, in real
conditions, despite not showing up remotely this badly across 150+ local games against V7.12.

**Likely explanation**: every local test this whole session was against a single opponent (V7.12,
occasionally the network-augmented Y.7.12-nn.1). A real, diverse ladder opponent apparently
triggers navigation failures that one specific opponent's movement patterns never exposed — this
matches a lesson already written down in `INSIGHTS_AND_PLAYBOOK.md`: self-play/single-opponent
testing can't see what both sides do wrong. **Any future validation must include a genuinely
different opponent (not just V7.12) before trusting local numbers.**

**Reactivated Y.7.12-nn.1 (the team's actual previous champion, submission 9285) immediately
after sending the challenges** — the experimental build must never sit active longer than the
specific test it was for, since ranked autoscrims draw whatever is active. Two more challenges
(WeHaveQuizzes, Cache me outside) are still queued to send once the hourly game quota frees up.

**This is now the top-priority investigation** — bigger than the portals consolidation problem.

## Side-effect finding

The just-finished 84-game tournament showed a real, unexplained asymmetry: **playing as side A won
42.9%, side B won 28.6%** (14.3 percentage points apart) on identical opponent/map/seed sets (both
sides played). Not yet investigated — could be a turn-order/dragon-ID artifact of the game engine
itself rather than anything fixable in the bot.

## Research findings (why not just add more ML/communication complexity)

- The existing champion (`Y.7.12-nn.1`) already proves imitation learning works extremely well:
  it doubled V7.12's maze win rate (32-37% → 53-65%) with a small network trained on other teams'
  public replays. See `ml/results.md` for the full ledger.
- The team already tried pure RL (PPO self-play) and found it **worse** than imitation at their
  compute budget. Full academic learned-communication techniques (CommNet/DIAL) need end-to-end
  differentiable multi-agent training that doesn't fit this project's per-dragon-process,
  imitation-from-public-replays pipeline.
- Critically: our own gossip/crowding internal state can **never** appear in other teams' public
  replays, so a network can only ever learn a policy shaped by these features from replays of S4.7
  actually playing itself — hence the self-play collection pipeline (`tools/selfplay_collect.py`,
  see below), not the existing top-team-replay pipeline.

## Self-play → ML pipeline (in progress)

`tools/selfplay_collect.py` (new): runs S4.7 self-play (plus a configurable fraction vs
`viper_nn`/Y.7.12-nn.1, the actual current champion — **not** plain V7.12, which is a weaker
reference by itself) with replays kept, and writes an `index.json` in exactly the format
`ml/build_dataset.py` already expects, so the rest of the proven pipeline (`ml/train.py` →
`ml/export_cpp.py`) needs no changes. Checkpointed to disk after every game (safe to run
unattended for hours). Currently running (restarted after the S4.7.4 queen-gossip change, so the
collected data reflects the current policy, not a stale one — matters because `ml/results.md`
already documented "old versions teach old habits" as a real failure mode). If this data turns out
useful (a trained network measurably improves play), the result will ship as a **new
`viper_vS4.7-nn` variant**, not by modifying `viper_vS4.7` itself — matching how `viper_nn` is a
separate copy of `viper_v7` with a network layered on top, never edited in place.

## Also running: top-team replay scouting

`tools/scout.py` downloading the top 15 leaderboard teams' recent replays to
`ladder/scout/` for strategy analysis, to inform further parameter/behaviour changes the way the
V7.12 lineage's own playbook did (see `INSIGHTS_AND_PLAYBOOK.md`). Not yet analysed.

## UPDATE: saturation reached on the "grow big, feed late" macro — leaderboard analysis reveals why

After S4.7.4 (queen gossip) still lost portals with a 1.5x population advantage (same self-trap
death cluster during the feed window), two more targeted fixes were tried on the exact same test
case and **both failed to move the outcome**:

- Staggering feed onset by dragon id (spread the convergence over 80 rounds instead of one
  synchronised wave): still lost, still the same self-trap cluster.
- (wCrowd increase, tried just before queen gossip, also insufficient on its own.)

Three isolated mechanism patches in a row with no measurable change is the "saturation" signal —
time to stop patching the current macro and check what actually wins, per plan.

**Leaderboard analysis** (new tool `tools/queen_growth.py`, run over top-15-team replays via
`tools/scout.py`): top teams win Portals/Slithery Fight/Trauma with **small, heavily consolidated
forces** — e.g. a team won Portals with only 2-3 units alive at the end (longest dragon 31-36),
another won it with 17 units (longest 21). Compare to S4.7's own portals games: cumulative
dragon-turns in the **thousands to tens of thousands** — a genuinely massive, constantly-splitting
swarm that then has to fight through a congested mass-feed to consolidate late, which is exactly
the step that keeps failing.

**Likely real fix**: the problem probably isn't a better feed/consolidation mechanism at all — it's
that the swarm shouldn't grow anywhere near this large on these maps in the first place. Commit to
a small number of growers much earlier and keep overall unit count low, instead of growing dozens
of units and trying to collapse them into one queen at round 400+. This is a bigger, more
fundamental change than anything tried so far and hasn't been implemented yet (sample size on the
leaderboard analysis is still small — 11 games — a fuller analysis is queued; treat this as a
strong lead, not yet a proven fix).

## Process notes for whoever picks this up next

- Build/test commands, environment gotchas (broken default Python, background-process monitoring
  via PowerShell not `ps`, etc.) are all in the assistant's memory, not repeated here to avoid
  drift between two copies of the same information.
- No online submission or ranked/unranked ladder testing has happened yet for any S4.7 version —
  everything above is local sandbox play only, per the explicit instruction to validate locally
  first.

## Qualifier results + replay analysis (2026-09-29, end of session)

**Qualifiers vs `baselines/v7_5`** (mislabeled — actually V6): 65W-36L-39D = **46.4%** (140 games).
**vs `viper_vS4.6`**: 52W-47L-41D = **37.1%** (140 games). Both lower than the local 50.0% vs V7.12,
but different opponents so not directly comparable. `stronghold`/`slithery_fight` were 100% draws
in *both* runs — likely a structural property of those two maps (possibly a genuinely symmetric
stalemate) rather than an S4.7.5-specific weakness; flagged as inconclusive, worth a quick look
next session rather than digging in now.

**Replay analysis of S.4.7.5's ladder-test losses** (full detail in memory
`s4_7_v4_and_beyond.md`): the user hand-reviewed several of the 58 saved replays
(`ladder/S4.7.5_ladder_test/replays/`) and found a consistent pattern across losses to multiple
different opponents — **losing control of pearl-dense regions to the opponent's sustained
"breeding" presence there**, rather than any single map-specific bug. Six concrete observations,
distilled into general (non-map-specific) design gaps, ranked by apparent leverage:

1. **Territory/region control is missing** — pearls are scored as individual targets, never as a
   region worth *staying near* once found. Opponents that claim a rich pocket and hold it
   out-breed us even when we're competitive elsewhere. Biggest identified gap.
2. **No emergency split-to-escape at minimum length** — a cornered long/grower dragon dies outright
   instead of splitting at minimum length to save some length, because `trySplit`'s length gates
   (`swarmSplitLen`, `growerKeepBase+growerChild`) don't have an emergency exception. Related: this
   session's reverted `trySplit` "rescue mode" experiment tried to fix a related problem the wrong
   way (tightened the child's room check instead of loosening the length gate for genuine
   emergencies) — worth revisiting from this angle. Also saw a case where the split *did* fire but
   both resulting pieces still died — a separate post-split-navigation issue.
3. **Possible real scoring bug**: dragons reportedly failed to eat *visible* pearls while circling
   already-empty ground — if true this isn't a strategy gap at all, just a bug, and cheap to check
   via a direct trace next session before touching anything else.
4. **Explore value is a one-time never-seen flag**, not a decaying staleness value — once a tile is
   seen it never gets re-explored even if long stale, discouraging useful re-covering of ground
   where beds may have respawned.
5. **Crowd-avoidance may need strengthening in tandem with #1** — own dragons piled into the same
   pearl-rich pocket and died to collisions; claiming territory without also preventing self-
   crowding would make this worse, not better.
6. **Late-game length consolidation onto the grower** — a previously-known, still-open issue
   (length spread across many swarm dragons instead of one long tiebreak-winning dragon),
   reconfirmed by two independent losses this round.

None of this should be implemented as map-specific logic — the fixes are general mechanisms
(a territory/region-control field, an emergency split exception, decaying tile-freshness) that
happen to matter most on maps with distinct pearl-rich pockets, not lookups keyed on map identity.

**Saved for review**: `ladder/S4.7.5_ladder_test/results.json` (corrected win/loss + elo per
opponent) and `ladder/S4.7.5_ladder_test/replays/` (58 `.replay` files). See memory for the
full per-opponent elo/record table.

## Territory clustering + emergency split mechanisms: implemented, a critical bug caught, net result mixed (2026-09-30)

Implemented two mechanisms from the previous session's replay-analysis priorities:
- **Territory/region clustering** (`Params::territoryRadius/territoryWeight/territoryMaxHot`):
  boosts a known bed's effective pull rate by how many other known beds sit nearby, so dense
  clusters compound their pull instead of every bed competing individually. General fix for
  "opponents claim a pearl-rich pocket and breed off it while we spread thin."
- **Emergency split-to-escape**: if a dragon has no safe move at all while staying whole, allow a
  minimal 2-long-child split as a last resort, bypassing the routine growth-split length gates.
  Only ever adds an option in an already-certain-death position; doesn't touch routine splitting.

**Critical bug caught before shipping further**: the first territory-clustering implementation was
unconditionally O(n²) in the number of known beds. On `default` (100% bed density), that blew the
100M-point CPU budget on round 0, killing every starting dragon outright. Caught via a same-seed
batch test showing `default` crash to a literal 0/6 with "1 round, our deaths=4 theirs=0" -- an
unmistakable crash signature once cross-checked with a direct verbose run. **Fixed** with a size
cap (`territoryMaxHot=200`): skip the clustering pass above that many known beds, since the signal
is meaningless in that regime anyway (nearly every cell being a bed means every bed is trivially
"surrounded").

**Full batch result after the fix** (36 games, same protocol as every test this session):

| Map     | Before (50.0% baseline) | After (+ territory + split) |
|---------|--------------------------|-------------------------------|
| trauma  | 0/6                      | 1/6 -- first-ever win          |
| autarky | 1/6                      | 1/6 -- unchanged               |
| trophy  | 3/6                      | 3/6 -- unchanged               |
| default | 4/6                      | 4/6 -- unchanged (CPU fix confirmed solid) |
| dilemma | 4/6                      | 2/6 -- **regressed**           |
| devil   | 6/6                      | 6/6 -- unchanged               |
| **Total** | **18/36 (50.0%)**      | **17/36 (47.2%)**              |

**Net: -2.8pp.** Trauma improved (the mechanism working as designed on a sparse, real-pocket map),
but dilemma regressed more than trauma gained. Working theory: dilemma's very low bed density (a
handful of excellent fountains) means the clustering bonus does little for isolated beds but
over-amplifies whichever few beds happen to sit near each other, possibly causing over-commitment
to one cluster instead of the more distributed approach that worked before.

**Not yet resolved -- decided to let data settle this rather than guess further**: `param_search.py`
was relaunched (properly synced this time -- it had drifted stale at the start of this session,
wasting an earlier run) with `territoryWeight` swept across `[0, 0.075, 0.15, 0.3]` on the same
6-map panel including dilemma, to empirically find whether any non-zero value nets positive, or
whether the mechanism should be gated to only fire on genuinely sparse maps (e.g. by global
bedDensity), or reverted. Check `ladder/losses/param_search_log3.txt` next.

**`baselines/S4.7.5/` has NOT been updated with this session's mechanism work** -- it still holds
the wCompass+roomFactor-only build (the actual validated 50.0% result). Don't overwrite it until
the territory-clustering question above is resolved.

## Resolved: territory clustering disabled by default, emergency-split shipped (2026-09-30)

A targeted same-protocol isolation test (`territoryWeight=0`, emergency-split still on) cleanly
separated the two mechanisms:

| Map     | Baseline | Both mechanisms | **Emergency-split alone** |
|---------|----------|-------------------|------------------------------|
| trauma  | 0/6      | 1/6               | 0/6                            |
| autarky | 1/6      | 1/6               | **2/6**                        |
| trophy  | 3/6      | 3/6               | 3/6                             |
| default | 4/6      | 4/6               | 4/6                             |
| dilemma | 4/6      | 2/6               | **4/6** (fully recovered)       |
| devil   | 6/6      | 6/6               | 5/6 + 1 timeout draw            |
| **Total** | **18/36 (50.0%)** | **17/36 (47.2%)** | **18/36 (50.0%, +1D)** |

**Confirmed**: territory clustering was the sole cause of both trauma's gain and dilemma's bigger
loss in the combined test. **Shipped decision**: emergency-split alone (matches baseline, autarky
genuinely improved), territory clustering disabled by default (`territoryWeight=0`, kept in code
with a comment on what gate it would need to be worth re-enabling — e.g. only fire on genuinely
low-bedDensity maps).

`baselines/S4.7.5/` and `viper_vS4.7_tune/` re-synced to this final state. `param_search.py`
stopped (would have taken hours to reach the same conclusion this isolation test reached directly).

**Where this leaves things**: the shipped build is validated at 50.0% vs V7.12 (same as before
today's mechanism work), plus a real emergency-split improvement on autarky, plus a working-but-
parked territory-clustering idea for later. Trauma is still the biggest unsolved gap (0/6 across
every fix tried across two sessions) — the "visible pearl not eaten" scoring-bug hypothesis
(Observation 5) is the most promising unexplored lead for next time.

## CRITICAL finding: Slithery Fight and Schooltime are catastrophic blind-spot maps (2026-09-30)

User-scheduled real ladder losses for `S.4.7.6` against Rogo/RustyHamsters/UnderTheC (all ~1700+
elo, 22 losses of 30 games) revealed our death totals are wildly uneven by map:

| Map | Our deaths (3 games) | Cause |
|---|---|---|
| **Slithery Fight** | **1959** | hit wall/self -- mass split-death cycling |
| **Schooltime** | **574** | head-to-head (265) |
| Trophy | 222 | head-to-head (known weakness) |
| Trauma | 23 (but opponent reaches 29-33 dragons vs our 0-3) | stagnation |
| everything else | <60 each | |

**Slithery Fight and Schooltime were never in the local 6-map test panel used all session**
(trauma/autarky/trophy/default/dilemma/devil) -- a real blind spot. Reproduced Slithery Fight
locally (viper_vS4.7 vs viper_v7.12, seed 1000): confirmed systemic, not opponent-specific -- our
side spawned **1300+ dragons** (bot id reached 1391) in one 500-round game, a runaway split/death
loop, taking 5m15s to simulate (vs ~1min for a normal map).

**Next priority**: add these two maps to the permanent local test panel, then trace the split-death
loop directly (likely `trySplit`'s swarm gates interacting badly with this map's geometry -- worth
testing with the new emergency-split fix OFF on this map first, same isolation technique used for
the territory-clustering question). Schooltime's head-to-head spike needs its own separate trace.

Full data saved: `ladder/loss_analysis_rogo_rustyhamsters_underthec/` (results.json + 35 replays).

## bceval now works on local sandbox games too, and is wired into the standard workflow (2026-09-30)

`bceval` only ever ran on downloaded ladder replays before. Two additions make it a standard part of
local iteration, not just ladder-loss postmortems:
- `tools/tourney.py --keep-replays DIR`: writes each game's replay to `DIR/<map>_<seed>_<side>.replay`
  (via `unswbc run`'s own `--replay` flag) instead of discarding it with `--no-replay`. Also bumped
  the per-game subprocess timeout 240s -> 420s (Slithery Fight alone legitimately takes ~5m15s with
  no other contention; the old cap produced false TIMEOUTs there even without contention).
- `tools/bceval_batch.py DIR --ours <substring>`: runs `bceval` over every replay in a directory and
  classifies each game's shape -- `dominant`/`close` (never really contested), `early`/`mid`/`late`
  collapse (when we started losing and never recovered), or `recovered` (dipped but came back) --
  instead of a bare win/loss line. For local sandbox replays, `--ours` matches the bot's directory
  name (e.g. `vS4.7`); for downloaded ladder replays, ladder replays record our own submission id as
  a bare string in the `bot_a`/`bot_b` field with the opponent's slot blank, so pass the submission id
  instead (e.g. `11453` for S.4.7.6). Validated against the already-known Rogo/RustyHamsters/
  UnderTheC losses: correctly reproduces the round-39 Trophy collapse and round-419 Slithery Fight
  collapse found by hand earlier this session.

**Recommendation**: from now on, any local `tourney.py` batch run worth reading closely should use
`--keep-replays` and a `bceval_batch.py` pass, not just the win/loss tally -- an early-collapse
cluster in ordinary local testing is worth tracing immediately, the same way a real ladder loss would
be, rather than waiting for it to show up online first.

## New tool adopted: `bceval` win-probability evaluator (2026-09-30)

Vendored `tools/battlecode-eval/` (MIT, https://github.com/xCirno1/battlecode-eval, built by a top-20
ladder player -- a small logistic-regression model, 120 weights over 23 features, no neural net,
trained on ~5,700 real games; 66-84% accurate depending on game phase). Run from inside that folder:
`uv run --python 3.11 --with pycapnp python -m bceval <replay> --every N`. Gives P(A wins)/P(B wins)
per round directly from a `.replay` file -- answers "when did this game turn" in one command instead
of reconstructing it from raw death events. **Adopt as the first diagnostic step on any future loss.**

## bceval sweep across the Rogo/RustyHamsters/UnderTheC losses: two new, precise findings (2026-09-30)

Ran `bceval` on 8 of the 30 loss replays (all Schooltime, Trophy, Trauma and Slithery Fight losses
from the 3-opponent batch, one per opponent). Two sharp, previously-unquantified patterns emerged:

**1. Trophy collapses almost immediately (round 0-40), every single time.** All 3 independent Trophy
losses (vs Rogo, RustyHamsters, UnderTheC, different seeds) show P(us wins) crash from ~0.50 at round
0 to 0.88-0.90 *against* us by round 39-40, and never recover. This is not a late-game consolidation
failure like Portals/Slithery -- it's an early-game problem specific to Trophy (bedDensity=1.0, the
map where `gamma` is already sharpened toward 0.72). Consistent with the known "opponent out-breeds
us in the pearl-dense region" diagnosis (Observation 1/3), but now dated precisely to the opening
~40 rounds, not a slow bleed -- worth a direct `BC_DEBUG` trace of Trophy's first 40 rounds
specifically, the same technique that found trauma's 78-round blind-forage bug.

**2. Slithery Fight collapses at almost exactly round 360-410 in every sampled loss (4 games, 3
different opponents, including one where we were team A and one where we were team B).** This lines
up suspiciously precisely with `Params::feedRound = 400` -- the global trigger where every eligible
dragon stops normal play and starts walking to the queen.

**Isolation test result (2026-09-30): emergency-split is NOT the cause -- ruled out cleanly.** Built
a copy of `viper_vS4.7` with `trySplit`'s `emergency` flag hardcoded to `false` and ran it against
`viper_v7.12` on Slithery Fight, same seed (1000) as the original reproduction, via a direct
`unswbc run --sandbox` call (bypassing `tools/tourney.py`, whose 240s per-game timeout is shorter
than this map's ~5min runtime and produced a misleading all-TIMEOUT batch on the first attempt --
caught before drawing any conclusion from it). Result: **virtually identical to the emergency-split-
on baseline** -- 5m23s vs 5m15s wall-clock, 26113 vs 26170 dragon-turns, bot id still reaching 1386+.
The runaway split-death spiral is present with or without the emergency-split mechanism.

**Map structure check -- CORRECTED (first pass was wrong)**: initially misread `TILE` lines in
`slithery_fight.map` as a walkable-cell listing and concluded the map had no interior walls. That's
wrong -- per `docs/map-files.md`, `TILE x y minGap maxGap` is a **pearl-spawn-rate** directive, not a
terrain listing; walls come from `EDGE` lines instead. Re-checked properly: the map has **514 kelp
edges** (kind 1 -- these block movement like a wall; per `docs/kelp-and-portals.md`, crossing one
kills the dragon "hit wall") plus 4 portal edges (kind 2) among 3402 total listed edges on a 1701-cell
board -- a real, fairly dense internal wall/kelp structure (roughly one blocking edge per ~3 cells),
**not** an open arena. The "population/board-capacity overcrowding, no walls involved" theory below
was built on that false premise and is retracted.

**What's still solidly established**: the isolation-test result itself (emergency-split ruled out --
both sides reach 1000+ dragons with or without it, 5m15s vs 5m23s, 26170 vs 26113 dragon-turns) came
from actual gameplay data, not the map reading, and stands. The "why" is genuinely open again --
given the map does have real, fairly dense wall/kelp structure, the original articulation-point/
chamber-trap hypothesis (see the research section above) is back in play as a strong candidate: a
2-long swarm child (or a routine bud) landing in a pocket that looks open by simple cell-count but is
reached through a kelp-bounded corridor that can seal shut is exactly the failure mode that check is
designed to catch, and Slithery Fight's edge density is the kind of layout where that would matter.

**Recommended next step**: a direct `BC_DEBUG` trace of Slithery Fight around the round-360-410
collapse window (the same technique that found Trauma's 78-round blind-forage bug) to see the actual
board layout and death pattern first-hand, before guessing further from map statistics alone.

## Research: rule-based Tron/Battlesnake techniques not yet in this codebase (2026-09-30)

Looked specifically for **non-neural, rule-based** techniques from the competitive Battlesnake and
Tron/light-cycle communities (per the user's explicit ask), since those games share the exact core
problem shape (multi-agent grid pathing, space-claiming, no-return-into-own-body):

- **Voronoi area control**: flood-fill from *every* living snake's head simultaneously (not just
  our own, which is all `Nav::flood`/the safety check currently does); the boundary where two
  snakes reach a cell in the same number of moves is the real contested-territory line. This is a
  more rigorous version of the "territory/region control" idea (already attempted this session as
  bed-clustering and shelved) -- instead of clustering *pearls*, cluster *board control* directly,
  independent of where pearls happen to be. Cheap: one multi-source BFS per turn instead of
  `wCompass`'s single-source one.
- **Articulation points / "chamber trees"** (from Tron AI postmortems, e.g. a1k0n's Google AI
  Challenge writeup): before committing to a direction, identify board cut-vertices and never enter
  one unless it leads to the *largest* remaining connected chamber among the options. This is a
  substantially stronger version of the current `bareExit`/`hasRoomyMove` split-room checks, which
  only count reachable cells, not whether the path there is a bottleneck that could later seal shut.
  **Directly relevant to the still-open trySplit split-then-death problem** (Observation 2, and
  possibly the Slithery Fight spiral above): a child spawned into a chamber that *looks* big enough
  by cell-count but is reached through a single narrow corridor is exactly what a naive flood-fill
  room check misses and an articulation-point check catches.
- **"Fewest edges removed" heuristic**: when two moves lead to equally-sized open areas, prefer the
  one that keeps the most wall-adjacent (least central) position -- a cheap tie-breaker for filling
  space efficiently without needing a full chamber analysis every turn.
- **Iterative-deepening alpha-beta/maxn with a Voronoi+length+centrality evaluation** is the
  standard strong-Battlesnake architecture -- close to what `Policy`'s own depth-bounded search
  already does; the main gap versus that community's approach is the Voronoi term (multi-agent flood
  fill) and the articulation-point safety check, both above.

## Fixes and tooling worked out from the Loong research, plus a contemplation on roles (2026-09-30)

Per the user's request, while `param_search_bceval` continued running:

**1. Sonar self-message fix (shipped, `viper_vS4.7/gossip.hpp`)**: added a single filter at the top
of `Gossip::receive()`'s message loop, `if (m.sender == (w.init.id % 4096)) continue;`, addressing
the wrap-around self-reception bug the Loong post's author hit in their own roles bot. Smoke-tested:
byte-identical game result to the pre-fix baseline (the bug had zero observable effect before now,
since `T_FOUNTAIN`/`T_QUEEN` self-receipt was already harmless and `T_CHOKE` is off by default) --
a correctness fix with no current behavior change, but necessary before `T_CHOKE` or any future
message type is ever relied on.

**2. SPRT tooling (`tools/sprt.py` + `tools/sprt_test.py`, new)**: implements the Sequential
Probability Ratio Test methodology from the Loong "better-worse-or-undecided" post. `sprt.py` is
the reusable math (Wald's SPRT bounds from a desired false-positive/false-negative rate, updated via
a Bernoulli log-likelihood ratio after each decisive game). `sprt_test.py` is a standalone A/B-test
driver: plays `candidate` vs a fixed `opponent`, cycling through `--maps` and both sides (bumping the
seed each full cycle), feeding each result into the SPRT and **stopping as soon as the result is
statistically decided** instead of a fixed batch -- this directly replaces the "run 16-32 games and
eyeball the win rate against an arbitrary min-gain threshold" approach used for every A/B test this
session. Usage: `uv run --python 3.11 --with unswbc python tools/sprt_test.py CANDIDATE OPPONENT
--maps ... --p0 0.5 --p1 0.6` (or `--elo1 <gain>` instead of `--p1`). Smoke-tested running (launched
with a small `--max-games 12` cap on 2 fast maps); heavily CPU-starved by the concurrently-running
`param_search_bceval` job so it hadn't finished as of this writing -- check `tools/sprt_test.py`'s
own output next session if not already reported. Also fixed the same unflushed-`print()` issue
`tourney.py` has (output can sit invisible for minutes under load) by flushing every print.
**Recommended next step**: consider porting this same early-stopping approach into `param_search.py`
itself (currently still fixed-batch) once the SPRT driver is validated standalone.

**3. Contemplation on roles, plus a new gated experiment (`Params::kamikazeLen`, off by default)**:
the Loong "Roles" post's Kamikaze design (any non-grower dragon at or below ~3 segments *with a
longer teammate visible* hunts and trades with enemy heads unconditionally, no local safety
calculation) is worth comparing carefully against our own combat logic, not just noting as similar.
Checked `policy.hpp` directly: our `tradeOk(myLen, enemyLen)` (`myLen <= enemyLen + tradeSlack`) is
already fairly permissive for a *short* dragon -- a length-4 dragon trading with almost anything
longer already satisfies it, so the parity-gate itself isn't the blocker Loong's design implies it
might be. The real remaining gate is `tradeOk`'s **population floor** (`units >= tradeMinUnits`) and
`buildSquadTargets()`'s `worth` check, which together mean a short dragon still needs the *army* to
be big enough before it's considered "worth" committing to a hunt at all -- Loong's kamikazes have no
such population precondition, they hunt purely from their own local length/teammate comparison.
**This session's own `growth_pattern.py` finding is the deciding piece of evidence**: winners
maintain roughly 50% more units than losers *throughout the entire game*, and the length gap that
actually separates winner from loser doesn't open up until round 300-400 -- meaning a short dragon
traded away early, if it removes a genuine threat, costs very little against a population lead that's
already supposed to be building, and the population-floor gate on hunting may be leaving free,
threat-reducing trades on the table specifically in the expansion phase where the army is still
growing toward that floor. **Implemented as a minimal, precisely-scoped, off-by-default change**:
`Params::kamikazeLen` (default 0, meaning no effect -- `L_ <= 0` never holds since minimum length is
2) -- when set, a non-grower dragon at or below this length treats hunting as always "worth it,"
bypassing `tradeOk`'s population floor specifically for *initiating* a hunt (defensive/reactive trade
logic elsewhere is untouched). Smoke-tested with `kamikazeLen=4` on Dilemma: compiles, runs, wins
(different game shape than baseline -- more dragons alive at various points, still a clean win) --
mechanically sound, not yet A/B tested for real. **Next step**: A/B test `kamikazeLen` (e.g. 3 or 4)
against the current baseline on the full `CORE_PANEL`, ideally using the new SPRT driver once it's
validated, rather than another fixed-batch test.

## Zig judge built and verified working in WSL2: confirmed correct AND faster on our own bots (2026-09-30)

Following up on the earlier finding that the Zig judge couldn't be safely built on native Windows,
the user installed WSL2. Built it there successfully:

- Zig 0.16.0 (first download attempt got a mid-transfer connection reset producing a corrupted,
  segfaulting binary -- fixed with `curl --retry -C -`).
- `libunwind-dev` via apt -- hit a second real hang: running `sudo apt-get` non-interactively via
  `wsl -d Ubuntu -- bash -c "sudo ..."` blocks forever waiting for a password prompt that never
  arrives in this context. Fixed by using `wsl -d Ubuntu -u root` instead of `sudo` entirely.
  **Lesson for any future WSL command needing elevation: always use `-u root`, never `sudo`.**
- wasmtime C API: WSL's network has a specific, repeatable problem reaching GitHub's release-asset
  CDN (immediate TLS handshake resets, not just slow) -- ziglang.org's CDN worked fine from WSL, but
  `github.com`'s release downloads consistently failed there. **Workaround: download on the Windows
  side (where it worked cleanly) and copy the file into WSL via the `/mnt/c` bridge** -- worth
  remembering for any future WSL download from GitHub release assets specifically.
- First build attempt failed: the repo's code uses newer wasmtime C API functions
  (`wasmtime_config_shared_memory_set`, an extended `wasmtime_memorytype_new` signature) than
  v27.0.0 provides. Their README only says "nixpkgs#wasmtime" (whatever's current), not a pinned
  version. **Fixed by using the actual latest release, v49.0.1** -- built cleanly on the first try
  after that.
- Also fixed the recurring `wsl: Failed to translate 'G:\...\ffmpeg...'` warning on every `wsl`
  invocation -- traced to a stale/broken Windows PATH entry (the folder doesn't exist) being
  auto-imported into WSL's PATH. Fixed via `/etc/wsl.conf`'s `[interop] appendWindowsPath = false`
  (doesn't touch the actual Windows PATH, which other programs may depend on).

**Verification against our own bots (not just their claim)**: ran the identical map/seed/bot
matchup (`viper_vS4.7` vs `viper_v7.12`, Dilemma, seed 1000) through both `unswbc run --sandbox` and
the built `loong-judge` binary. **Result: identical outcome** -- same winner (A), same round count
(115), same per-side turn counts (823/328), and points-per-turn statistics matching to the exact
number (62.9M/60.8M/63.1M vs 62905118/60817497/63069769, etc.) -- this directly confirms the blog's
"byte-identical replays" correctness claim, on our own code, not just their own test suite.
**Speed: 5.2s vs 14.7s -- ~2.8x faster** on this specific test (in the same ballpark as their
claimed ~4x, expected to vary by map/hardware/workload).

**This is now a real, working, verified tool, not just a research finding.** Binary at
`~/toolchains/zig-judge-out/bin/loong-judge` inside WSL2 Ubuntu, engine wasm at
`~/venv/lib/python3.14/site-packages/unswbc/unswbc_engine.wasm` (installed via a WSL-side venv +
`pip install unswbc`), invoked as `loong-judge --engine <engine.wasm> --map <map> --a <bot.wasm>
--b <bot.wasm> --seed <N>`, reading Windows-side files fine via `/mnt/c/...`.

**Recommended next step, not yet done**: wire this into `tools/tourney.py`/`tools/param_search.py`
as an optional faster backend (e.g. a `--judge zig` flag that shells out to `wsl -d Ubuntu --`
instead of `unswbc run --sandbox`) -- given tonight's param_search took hours partly because of
Schooltime/Slithery Fight's slow simulation time, a ~3-4x speedup there could meaningfully shrink
future parameter-search and validation turnaround, especially for the maps that dominate wall-clock
time. Not implemented yet; a natural next session's task.

## param_search_bceval's 3 confirmed gains applied and broadly validated: net +9.4pp, but Trophy regressed (2026-09-30)

Applied `wTarget=4` (was 1.0), `wPredict=0` (was 1.0), `swarmChild=3` (was 2) to the live
`viper_vS4.7/common.hpp` and ran the same 8-map/2-seed/both-sides protocol as the existing baseline
(`ladder/losses/core8_with_replays.txt`) for a direct, fair comparison:

| Map | Baseline | With gains | Delta |
|---|---|---|---|
| Trauma | 0/4 (0%) | 0/4 (0%) | -- |
| Autarky | 1/4 (25%) | 2/4 (50%) | **+25pp** |
| Trophy | 3/4 (75%) | 2/4 (50%) | **-25pp** |
| Default | 2/4 (50%) | 3/4 (75%) | **+25pp** |
| Dilemma | 3/4 (75%) | 4/4 (100%) | **+25pp** |
| Devil | 4/4 (100%) | 4/4 (100%) | -- |
| Slithery Fight | 0/4 (0%) | 0/4 (0%) | -- |
| Schooltime | 0/4 (0%) | 1/4 (25%) | **+25pp** |
| **Total** | **13/32 (40.6%)** | **16/32 (50.0%)** | **+9.4pp** |

**Net positive, and it generalizes**: the gains show up on Default/Dilemma/Autarky/Schooltime, none
of which were part of `param_search_bceval`'s narrow 4-map test set (Trophy/Trauma/Autarky/
Schooltime) -- real evidence this isn't overfit to the specific maps it was tuned on. **But Trophy
regressed 75%->50%**, a real cost on a previously reliable map. Given the small per-map sample (4
games) and Trophy's already-documented side-asymmetry volatility (100% dominant as A / 100% early
collapse as B, found earlier this session), this specific regression needs more seeds to confirm it's
real rather than noise -- not hidden, but not yet fully confirmed either.

**Decision: keep the 3 changes** (net +9.4pp across two independent map sets is a meaningful, well-
motivated signal -- `wTarget`/`swarmChild` both push toward faster, more decisive growth, matching
the `growth_pattern.py` population-lead finding). **Flagged for follow-up**: a same-seed trace of a
Trophy loss with the new params vs the old, to understand whether the regression is real and why
(possibly `wTarget=4`'s more decisive single-target commitment interacts badly with Trophy's
bedDensity=1.0 regime, where every cell is a viable target and over-committing to one may cost
options a flatter field wouldn't). `baselines/S4.7.5/` has NOT been updated with this change yet --
pending the Trophy follow-up.

Also confirmed while checking on this batch: no CPU/hang regression on Slithery Fight from
`swarmChild=3` (a real risk, since `param_search_bceval`'s test set never included Slithery Fight,
and it's the map with the known population-explosion bug) -- death counts (567-688 range) are
consistent with previous runs, not worse.

## CRITICAL FINDING: we generalize badly to unseen maps -- likely the single most important discovery this session (2026-09-30)

The first-ever `maps_gen/` validation batch (30 procedurally-generated maps, 1 seed, both sides, 60
games, `viper_vS4.7` vs `viper_v7.12`) completed: **21.7% win rate (13W-47L-0D of 60)** -- dramatically
worse than this build's usual ~40-50% against the same opponent on the 8 *official* `CORE_PANEL`
maps. Zero timeouts/errors, average battle length 383 rounds (many running the full 500) -- this is
real, valid gameplay, not corrupted data or an infra artifact.

**Death causes rule out a safety/navigation bug**: "lost a head-to-head" dominates (3835 of ~5482
total deaths, ~70%), not hit-wall/hit-self (DOOMED-style deaths, which would point at a map-
resolution or safety-check gap). **We are not crashing abnormally on unseen maps -- we are genuinely
losing the growth/combat race, consistently, across nearly the whole 30-map sample** (only 3 of 30
maps show a >50% win rate; most sit at 0-50%).

**Why this matters more than almost anything else found this session**: essentially every fix,
parameter, and mechanism validated this session (`gamma` by bed-density, the `hotRate` certain-data
bypass, `wCompass`'s long-range pull, `knownmap.hpp`'s spawn-based instant resolution) depends on
`maps_data.hpp` having an exact entry for the map being played. **On a genuinely new map -- which,
per `AGENTS.md` ("new maps will be added later") and the Loong "shape of the problem" post ("every
tournament map unseen"), describes literally every real competition map -- none of that machinery has
anything to work with**, and the bot falls back to generic defaults. This result suggests that
fallback state is **much weaker than the local 8-map panel has ever revealed**, because that panel is
entirely maps we already have exact data for. **This is very likely why the confirmed 8-map/local
win rate has never fully translated to the real ladder as strongly as expected** -- the ladder
includes a rotating mix of maps, some unseen, and this batch suggests unseen-map performance could be
closer to 20% than 40-50%.

**This reframes Phase 2 of the map-adaptive architecture (a sonar-shared coarse map for maps with no
`maps_data.hpp` entry, mentioned early this session but never built since Phase 1's bed-density
`gamma` adaptation already helped known maps) from "a nice-to-have generalization story" to
"plausibly the single highest-leverage unstarted work."** Concretely, once population/opening-game
fixes from the current `param_search_bceval` run are validated, the recommended next investigation is
a direct trace of *why* we lose the growth race specifically without known-map data -- likely
candidates: `hot_`'s hotRate-based learned-rate gating (the exact mechanism the certain-data bypass
was built to route around, but which fully applies again with no known data to bypass to), and
`wCompass`'s macro-target selection (which only ever targets `hot_` entries, so has nothing to aim at
without learned data accumulating first). **Recommended immediate next step**: run the same 30-map
(or a larger) `maps_gen` batch with `BC_DEBUG` on one clearly-lost game to see directly what the
early-game foraging behavior looks like with zero known-map information, the same technique that
found trauma's original 78-round blind-forage bug.

Full results: `ladder/losses/mapsgen_validation.txt`, replays in `ladder/local_replays_mapsgen/`.

## Three more Loong posts, and a concrete action taken: maps_gen/ finally generated (2026-09-30)

**"Where the points go" (CPU economy)**: profiled their own bot's 100M-point turn budget and found
**output is by far the most expensive operation** (2.5M base cost + 4000/byte -- ~90% of their
measured per-turn spend, ~3.04M of ~3.4M total points used), while actual strategy computation was
cheap (~48K points) and **~96M points sat entirely unused**, available for deeper search. Two
takeaways for us: (1) `out.log()`'s per-byte cost is a real, concrete reason (not just the already-
known "visible to opponents" privacy reason) to trim our own diagnostic log string before a final
submission -- worth a quick check of its actual byte length and CPU cost via `unswbc run -v`'s own
peak-points tracking; (2) if our own measured per-turn usage (this session's own `-v` runs have shown
numbers like 50-65M, i.e. much higher utilization than their ~3.4M example) is genuinely that much
higher, we may already be using our budget well rather than leaving headroom on the table like they
were -- worth confirming with a direct measurement rather than assuming either way.

**"Maps nobody has seen"**: their unseen-map generator (xCirno's 10-stage layered pipeline, bounded
to match official maps' statistical ranges: tile count, aspect ratio, kelp density, portal pairs,
etc.) exposed **two real bugs that never showed up on any official map** -- a self-portal-collision
and a teammate-collision, both only triggered by portal/board-size configurations wider than the
official map pool covers (0/120 losses on bundled maps vs 3/120 on generated ones). **Direct action
taken**: checked our own `maps_gen/` (documented in `AGENTS.md` as "300 random fair maps... for
unseen-map tests") and found **it was empty -- never actually generated in this workspace all
session**, despite being referenced as an existing testing asset. Generated it now
(`tools/gen_random_maps.py --n 300 --seed 1`, lightweight, ran alongside `param_search_bceval`
without contention). **This is a real, previously-untapped blind-spot-detection asset**, in the same
spirit as this session's own Slithery Fight/Schooltime discovery (bugs invisible on a narrow map
panel) -- worth a `tourney.py` run against `maps_gen/gen_*` once `param_search_bceval` finishes,
specifically looking for the same class of "only appears on an unusual portal/board-size
combination" bug their team found.

**"A ladder of our own" (Bradley-Terry offline rating)**: built a private offline ladder using the
Bradley-Terry model (Newton's-method fit) instead of trusting the official online ladder's
sequential, order-dependent Elo -- with a striking concrete example of why: **one of their bots had a
98/100-game record but the sequential online-style Elo rated it only 1916, while properly fitting all
results together (order-independent) gave it 2270** -- a large, measurable bias in exactly the kind
of rating scheme our own team's ladder rating already relies on. This is the third Loong post (after
the evaluation harness's Bradley-Terry+CI mention and the SPRT post) pointing at the same throughline:
**their whole testing philosophy is built around not trusting small-sample or order-dependent win-rate
numbers at face value** -- exactly the discipline this session has had to re-learn by hand multiple
times (every A/B test this session needed a "noisy, small sample" caveat). **Recommended next tooling
investment, alongside the SPRT driver already built today**: a small Bradley-Terry fitting script over
our own accumulated `tourney.py`/`param_search` results, so historical comparisons across different
opponents/sessions become properly comparable instead of read as raw win percentages.

## Deeper Loong research: the Zig judge, cloud infra costs, the evaluation harness, and a real tourney.py bug fix (2026-09-30)

Read 6 more posts and cloned the actual repo (`github.com/overyonder/the-loong-game`, `/tmp/the-loong-game`) to investigate concretely rather than just from the blog text.

**"The machine inside the judge" -- a custom Zig judge, open source, verified compatible**: the
official `unswbc` toolkit spawns one Python thread per dragon (a real race condition -- newly-split
dragons occasionally die "no valid action" from a genuine bug in the official tool). Their
replacement, written in Zig using cooperative fibres instead of OS threads, is **~4x faster end to
end, uses 2.85x fewer core-seconds on 32-vCPU workers, and produced byte-identical replays across
144 paired games** against the official toolkit -- a verified, safe drop-in, not just a claim.
Source: `harness/zig_judge/` in the repo, built via `zig build` (Zig 0.16). **Tried to build it
locally and hit a real portability wall**: it links against `libunwind` and an externally-supplied
wasmtime C API (normally sourced from a Nix dev shell on Linux) -- neither is readily available on
native Windows, and forcing it risks producing a subtly-broken binary that could silently corrupt
test data (exactly the "malfunction" to avoid). **No Docker or WSL available on this machine either**
to sandbox a Linux build safely. **Conclusion: don't attempt a native Windows build** -- this is
built and deployed for Linux, and the honest path to using it is a Linux environment (cloud or WSL),
not fighting Windows compatibility.

**"Games in the cloud" -- their actual AWS pipeline, with real cost numbers**: spot instances across
two regions (320 vCPUs/region cap), S3 for run bundles/results (14-day auto-expiry), SQS to
distribute one game per queue message, OpenTofu (open-source Terraform fork) for infrastructure as
code, a hard 3-hour run deadline plus self-shutdown and an external reaper as safety nets against
runaway cost. **Cost: ~$0.04 per 1000 games** (vs $0.09 via the official toolkit) -- eleven full runs
totaling tens of thousands of games cost $17.51 total. At that rate, **the user's $100 in cloud
credits could buy roughly 2 million+ games** of parallel testing capacity -- several orders of
magnitude beyond what this session's 12-core local machine can do (the current `param_search_bceval`
run needs ~16 more hours for ~90 more trials; the same compute could plausibly finish in cloud in
well under an hour with enough parallel workers). **Not acted on without the user's explicit
involvement** -- this requires their own AWS account/credentials and real spend approval, which I
don't have and shouldn't set up unilaterally. Recommend: once the user is back, decide whether to
invest the setup effort (a scaled-down version of their pipeline -- even a handful of spot instances
without the full SQS/S3/OpenTofu machinery would already be a large local-machine multiplier).

**"The evaluation harness" -- found and fixed a real bug in our own `tourney.py`**: their harness
separates timeouts/crashes into their own error category, explicitly *not* counted as draws --
"crashes and timeouts populate a separate errors column rather than counting them as losses [or
draws], preserving diagnostic information." **Checked our own `tourney.py` and found exactly the bug
this session kept tripping over**: the per-game `tag` was already correctly labeled `"ERR "` vs
`"DRAW"` for *display*, but both cases incremented the *same* `draws` counter underneath -- meaning
every "0 avg rounds, 0 deaths" timeout batch (Devil and Slithery Fight both, earlier today) was
silently indistinguishable from a real draw in the actual stats, not just something I had to
manually notice each time. **Fixed**: `tourney.py` now has a genuine separate `errors` bucket (top-
level and per-map), excluded from win/loss/draw percentage totals (matching the harness's own
"isolate, don't conflate" design), with a new `E` column in the live tracker and final per-map table,
and an explicit "(N infra errors/timeouts, excluded from the totals above)" note in the summary line
when any occurred. Syntax-verified; a live-game re-verification is still pending (deliberately
skipped for now to avoid competing with the running `param_search_bceval` job, per explicit
instruction not to starve it). Other harness ideas not yet ported: Bradley-Terry ratings with 95%
confidence intervals (pairs naturally with the SPRT tooling already built today), content-hash-keyed
result caching (would have avoided several `viper_vS4.7_tune` re-sync/stale-baseline mistakes this
session), and process-group-based timeout handling (`start_new_session=True` + `os.killpg()` --
more robust than the current `subprocess.run(..., timeout=...)`, which can leave orphaned judge
processes behind on a hard timeout).

**"The choice" (language)**: they chose Nim over Python/C/C++/etc for their own bot (measured Python
at ~450x more CPU-expensive than C for an identical flood-fill algorithm, motivating a Python-
readability/C-speed compromise language). Not directly actionable for us -- we already write native
C++, which is the fast end of that same tradeoff -- but a good outside confirmation that C++ was the
right call for this specific 100M-point CPU budget, not a legacy-of-convenience choice.

**"Game data in columns"**: a custom binary columnar replay format (memory-mapped, fixed-size typed
arrays) replacing JSON for cross-replay analysis -- a 500-round game's *first frame* went from 8+
minutes to load down to under a second, memory from 6.1GB to 332MB peak. Our own `replay.py` already
mitigates the slow-reparse problem with a simpler `.pkl` cache-next-to-the-file approach, which is
adequate for the batch sizes handled so far (hundreds of replays via `bceval_batch.py`/
`growth_pattern.py` complete in well under a minute) -- a full columnar rewrite would only pay for
itself at a much larger replay-volume scale (e.g. if the cloud pipeline above gets built and starts
producing tens of thousands of replays routinely). **Lower priority than the fixes above; worth
revisiting only if replay analysis volume grows substantially.**

## Found and read: over-yonder.tech/games/loong -- a dev blog series for this exact competition (2026-09-30)

User pointed to a 19-post blog series accompanying UNSW Battlecode 2026 (evaluation harnesses,
replay decoding, unseen-map generation, role/tactics design, sonar protocol design, room-counting
performance) -- written by someone building a reference bot for this same game. Read the 4 most
directly relevant posts (a 5th, "the-shape-of-the-problem", failed to fetch -- ECONNRESET, retry
later if useful). Findings, each cross-checked against our own code/data:

**"Roles"**: a clean 3-role system -- **Champion** (team's longest dragon, plays purely for length,
keeps a 2-tile buffer from enemy heads), **Kamikaze** (<=3 segments *with a longer teammate*,
aggressively hunts enemy heads and trades itself for threats), **Worker** (everything else, standard
forage/evade). Roles are **self-assigned every turn from sonar alone**: each dragon broadcasts its
own length; a dragon compares itself to "the longest teammate heard in the last 12 turns" and
becomes champion/kamikaze/worker accordingly -- no central coordination, fully decentralized local-
threshold role assignment. **This is a concrete, working realization of the ant-colony response-
threshold idea from this session's earlier research** (idea #2), and maps closely onto our own
grower/swarm split, but with one sharp difference: **their kamikazes actively seek out and trade with
enemy heads specifically because they're short and expendable, not because of any local safety
calculation** -- a deliberately unsafe-looking cheap-aggression policy. Our own `tradeOk`/`huntNext`
logic is more conservative (safety-gated), which may be worth reconsidering given `bceval`'s own
population-lead finding above (a short dragon traded for a kill doesn't cost the population lead
much, and removing enemy threats protects it). **Champions split at 10 segments** to spawn
kamikazes (a length threshold notably higher than our `promoteLen`/`growerKeepBase` values --
worth checking whether ours fires too early).

**"Tactics"** (coiling + feeding, a more complex system layered on Roles): the champion "coils" (curls
tightly, staying within 10 open tiles of margin to avoid self-imprisonment) instead of roaming;
feeders deliver at 6+ segments, within 12 turns of the champion's last heard position, driving in only
when within 2 tiles of the champion's head. **Critically, the author's own result: "initial testing
showed this combined approach performing roughly equal to the simpler roles-based strategy, suggesting
the sacrifice mechanics require further parameter tuning."** This is independent, external
confirmation of this session's own repeated finding (queen-gossip, staggered-feed, throughput-cap all
tested neutral) -- **even the reference implementation's own feeding/consolidation refinement was a
wash over the simpler baseline.** This meaningfully de-risks the earlier internal worry that our own
feed-mechanism tuning must be missing something obvious; it looks like a genuinely hard, low-leverage
area for *everyone* attempting it, reinforcing (again) that population/opening-game execution matters
more than feed-mechanism cleverness. Note their `queenStale`-equivalent is **12 turns**, much fresher
than our `queenStale=60` -- worth testing a shorter staleness window.

**"Sonar"**: two concrete, actionable points. (1) **A real bug they hit**: "wrap-around board edges
cause dragons to receive their own messages" -- since the board wraps on both axes and a sonar ray
travels straight until hitting kelp/the first dragon, an unobstructed ray can loop back to its own
sender. **Checked our own `gossip.hpp`: none of `T_FOUNTAIN`/`T_QUEEN`/`T_CHOKE`'s receive handlers
filter by sender id** (`viper_vS4.6`'s equivalent code did, for `T_INTENT`/`T_CHOKE` -- we didn't
port that filter when adding `T_CHOKE` this session). Low real impact today (`wChoke=0` by default,
and `T_QUEEN`/`T_FOUNTAIN` receiving our own already-known info is harmless), but a real latent bug
to fix (`if (m.sender == w.init.id % 4096) continue;`) before `T_CHOKE` or any future message type is
ever enabled for real. (2) **Design philosophy, matches our own existing caution**: "assume
adversaries will intercept everything -- anything a bot sends should be something it doesn't mind the
other team reading," which is exactly why `AGENTS.md` already flags indicator strings/sonar as public
and why this session's research concluded encryption/secrecy work isn't worth prioritizing without a
specific identified gap.

**"Better, worse or undecided"** (statistical testing methodology) -- **the single most valuable
finding for our own tooling, independent of any specific game strategy**: describes an **SPRT
(Sequential Probability Ratio Test)** for bot comparison instead of a fixed-N-games-then-eyeball-the-
win-rate approach (which is what `param_search.py`'s `--min-gain` threshold and every A/B test this
session actually is). SPRT updates a log-likelihood ratio after every game and stops as soon as
either "candidate is meaningfully better" or "no material difference" is confident, rather than always
playing a fixed batch -- targeting a specific effect size (their example: +70 Elo / ~60% win rate)
needs ~150 games under fixed testing but often resolves in far fewer under sequential testing.
**Key refinement: paired games** -- candidate and baseline each play the *same* opponent/map/seed/
side, which is close to what our own 2-seed/both-sides protocol already does, but a true SPRT would
formalize it and let each run stop as soon as it's decided rather than the fixed 16-32-game batches
used throughout this session (which we've repeatedly had to caveat as "noisy, small sample"). Also:
a cheap **sanity check** of ~10 games vs a random-moving bot to catch implementation errors, which we
don't currently have. **Recommended next tooling investment**: implement SPRT in `param_search.py`
and `tourney.py`'s A/B-test path -- likely both faster (stops early on clear results) and more
statistically honest than the current fixed-batch-plus-eyeball approach used for every finding this
session (territory/choke A/B tests, the whole param_search sweep, etc.).

## Deeper pattern: when consolidation actually happens and how big winners' armies stay (2026-09-30)

`bceval` only gives a win-probability score, not board state (unit counts, dragon lengths). New tool
`tools/growth_pattern.py` (reuses `bceval`'s `replay_features()` to find the winner and
`queen_growth.py`'s event-replay to get units/longest/total-length at rounds 100/200/300/400/500/end)
answers the user's specific questions -- when does consolidation start, how many dragons does a
winner end with, what does the role/length distribution look like -- across all 137 scouted
top-15-team games, winner vs. loser side compared directly:

| Round | Winner units / longest | Loser units / longest |
|---|---|---|
| 100 | 23 / 4   | 15 / 4   |
| 200 | 38 / 5   | 27 / 4   |
| 300 | 45 / 7   | 30 / 5   |
| 400 | 24 / 21.5 | 14 / 11.5 |
| end | 11 / 34  | 5 / 16   |

**Population lead starts early and never closes**: winners run ~50% more units than losers from
round 100 onward, all the way through -- this is not a late-game phenomenon, it's present from the
opening. **Longest-dragon length is nearly identical for winner and loser through round 300** (4-7
for both) -- neither side has really started consolidating during the expansion phase. **The actual
consolidation event is concentrated in the round 300->400 window**: the winner's longest roughly
*doubles* the loser's there (21.5 vs 11.5) and stays ~2x ahead through the end (34 vs 16). End-game
population: winners keep a median of 11 dragons alive (one ~34-long queen plus ~10 shorter
companions) vs. losers' median of 5.

**This gives an empirically-grounded two-phase picture** (matches the user's own earlier-proposed
idea #6/#16, an explicit EXPANSION->CONSOLIDATION phase controller): expansion runs roughly rounds
0-300 (population growth, minimal length differentiation), consolidation is concentrated roughly
300-400+ (the queen pulls away, population culls). **Notably, S4.7's own existing
`growRound=300`/`feedRound=400` already sit right at this empirically-observed transition window** --
the *timing* of the current phase structure isn't wrong; the gap is in *execution* (having enough
population and length lead built up by round 300 to consolidate from) rather than a mistimed switch.
This reframes the priority: population/growth-speed fixes (this session's `param_search_bceval` focus
on `wTarget`/`swarmSplitLen`/`swarmChild`) matter more than adjusting *when* the phase switch fires.

**Caveat on the "consolidation ratio" metric**: also tried classifying games by the first round the
longest dragon holds >=25% of team total length -- this didn't cleanly separate winners from losers
(both distributions were similar, and losers sometimes cross it *earlier*, likely an artifact of
having a smaller total population making the ratio easier to cross even with a modest longest value,
not a real early-queen strategy). The units/longest *absolute* numbers above are the more reliable
signal; a ratio-based "has the swarm picked a queen yet" metric needs a smarter definition (e.g.
longest length as a multiple of the *median* other dragon's length, not a share of the team total) if
revisited.

**Tool**: `uv run --python 3.11 --with pycapnp python tools/growth_pattern.py DIR --side winner|loser`
-- works on any replay directory bceval already handles.

## MAJOR FINDING: top-15-team pattern via bceval -- winning means establishing dominance early, rarely a comeback (2026-09-30)

Extended `bceval_batch.py` with a `--by-winner` mode (classifies a game's trajectory relative to
whoever actually won, not a fixed "our side" -- works on any replay set, including games where
neither side is us). Ran it on all 137 already-scouted top-15-leaderboard team replays
(`ladder/scout/`, pulled earlier this session by `tools/scout.py`, 0 CPU contention with any running
sandbox job since this only reads existing replay files and scores a small model):

**76.6% of top-team wins (105/137) are "dominant"** -- the eventual winner was ahead from early on
and never seriously threatened (never dropped below 0.3 win probability). Only **21.9% (30/137) are
"recovered"** (a real comeback from a real deficit), and just 2 games show the model briefly favoring
the eventual loser late without ever correcting (likely a genuine model miss, consistent with
`bceval`'s own stated accuracy ceiling, not a "the underdog usually wins late" signal).

**This is a clean, well-evidenced answer to "how do you actually win this game":** establish an edge
early and hold it, far more than out-playing a close game late. It directly validates this session's
whole pivot toward opening-game growth-speed fixes (the `param_search_bceval` run's `wTarget`/
`swarmChild` candidates, both about committing faster/bigger early) over further late-game
consolidation mechanisms -- the top of the ladder's own win pattern confirms early dominance is the
dominant strategy, not a coincidence of this session's diagnosis.

**Per-map breakdown also matches our own known weak spots**: Schooltime (7/31 = 23% recovered) and
**Slithery Fight (7/22 = 32% recovered)** -- our two worst real-online maps -- are the most
"volatile"/reversible maps among top teams too (vs. e.g. Autarky 1/16=6%, Prisoners Dilemma 0/4=0%
recovered). A map that naturally allows more back-and-forth swings gives our own known structural
weaknesses (Slithery Fight's split-death spiral, Schooltime's head-to-head losses) more room to
compound into the catastrophic collapses actually observed, whereas a "dominance locks in fast" map
like Autarky or Dilemma punishes a slow start but doesn't have the same volatility ceiling.

**Full breakdown**: Schooltime dominant=24/recovered=7, Slithery Fight dominant=14/late=1/
recovered=7, Portals dominant=14/recovered=5, Trauma dominant=4/recovered=4 (Trauma is unusually
volatile among top teams too, interesting given it's also one of our own worst maps), Autarky
dominant=15/recovered=1, Default dominant=11/late=1/recovered=2, Devil dominant=7/recovered=1,
Queen of Spades dominant=4/recovered=2, Trophy dominant=8/recovered=1, Prisoners Dilemma
dominant=4/recovered=0.

## Pattern confirmed at 5x scale: full-ladder bceval sweep, 719 replays (2026-09-30)

Ran the same `--by-winner` analysis across **every replay currently stored under `ladder/`** (719
files: the 137 scouted top-team games above, plus every local test batch and real ladder loss
pulled this session and in prior sessions -- self-play, S.4.7.5's ladder test, the v10.1 postmortem,
qualifier tournaments, everything). Zero errors, no CPU contention with the concurrently-running
`param_search_bceval` job (confirmed -- this only reads existing files).

**Result: dominant=557 (77.5%), recovered=155 (21.6%), early=2, late=5** -- essentially identical to
the 137-game top-team-only subset (76.6%/21.9%). **The "establish dominance early, rarely a
comeback" pattern holds just as strongly across the full mixed dataset** (top teams, our own tests,
real losses) as it does for elite play alone -- this looks like a structural property of the game
itself (once one side gets meaningfully ahead on length/population, the round-500 tiebreak and
ongoing head-to-head trades make it very hard for the other side to claw back), not something
specific to how well a team plays. **Practical implication, now confirmed at high confidence**: the
single highest-leverage lever for winning more games is protecting/improving the *opening* game,
not building a better comeback/consolidation mechanism for when already behind -- directly
supporting the `param_search_bceval` run's current focus (`wTarget`, `swarmSplitLen`, `swarmChild`)
over further late-game work.

Trauma remains the most volatile map even at this scale (27/89 = 30% recovered, matching the
scout-only subsample's already-high rate) -- worth remembering as context if a future Trauma fix
looks like it "should have won" by round 300 but didn't: comebacks are unusually common on this
specific map, so late-game execution matters more there than the overall pattern would suggest.

## Full bceval sweep of all 35 pulled online replays: early-game collapse is near-universal (2026-09-30)

Earlier this session only 8 of the 35 Rogo/RustyHamsters/UnderTheC replays were hand-picked and run
through `bceval` (the Trophy/Trauma/Schooltime/Slithery Fight losses). Ran the remaining 27 too
(`bceval_batch.py` on the whole `ladder/loss_analysis_rogo_rustyhamsters_underthec/replays/`
directory -- costs under 20s total, no CPU contention with any running sandbox job since it only
reads existing replay files, no game simulation). Aggregate: **17 of 35 games (49%) are "early"
collapses** (round 19-99, never recovered) -- and critically, this isn't confined to the maps
already flagged from local testing (Trophy/Trauma/Autarky/Schooltime). It also shows up on **Devil,
Default, Portals, Prisoners Dilemma, and Queen of Spades** -- maps that test fine locally against
V7.12. **This means the opening-game growth-speed weakness is near-universal in real online play,
not a handful of specific bad maps** -- a real opponent apparently exploits the opening 20-100
rounds far more consistently than our own reference bot (V7.12) does locally. This raises the
priority of the current `param_search_bceval` run's opening-game-focused sweep (`wTarget`,
`swarmSplitLen`, `swarmChild`) even further, and means **any winning param set from that search
should be validated across the full `CORE_PANEL`, not just the 4 maps it's currently focused on**,
since the online data suggests the fix may generalize much more broadly than the local-only maps
that originally flagged it.

## A/B test results: territory safety-margin and T_CHOKE reservation -- both regressed, neither shipped (2026-09-30)

Implemented both ideas from the S4.6 research (territory safety-margin penalty, T_CHOKE sonar
reservation -- see the section below for what they are), each gated behind a new Params field
defaulting to 0 (off), and A/B tested each in isolation against the existing 8-map `CORE_PANEL`
baseline (`ladder/losses/core8_with_replays.txt`, 40.6% = 13W/32). **Both regressed; neither is
shipped -- `wTerritory` and `wChoke` remain 0 by default.**

**Correction after checking the raw per-game lines (not just the summary table)**: both A/B tests'
"draws" on Devil are actually `[ERR] ... TIMEOUT` entries (0 deaths recorded, the known infra-
timeout signature), not real 500-round draws -- caught by re-checking after the user asked whether
the Devil draw was real. Running 3 heavy background jobs simultaneously (2 tourneys + param_search)
contaminated this already-borderline-timing map in both tests. **Devil did not actually regress in
either test** -- the games that did complete were wins in both (2/2 for territory, 3/3 for choke),
consistent with baseline's 4/4; the timed-out games are simply uninterpretable, not evidence of harm.

**Territory safety-margin (`wTerritory=0.5`)**: 21.9% (7W/32), a severe regression from 40.6%.
Per-map vs baseline (excluding Devil's contaminated pair, see correction above): trauma 0/4->1/4
(+1, the one improvement), autarky 1/4->0/4 (-1), trophy 3/4->2/4 (-1), default 2/4->1/4 (-1),
**dilemma 3/4->0/4 (-3, total collapse, all 4 games completed normally -- real deaths recorded, not
timeout-contaminated)**. The dilemma collapse is the *same exact failure signature* as this
session's earlier reverted bed-clustering (`territoryWeight`) experiment (trauma improves, dilemma
collapses) -- **now confirmed twice, with two structurally different implementations**, that
dilemma's sparse, "few excellent fountains" layout is fundamentally incompatible with any
territory-holding bias as currently formulated, not an implementation quirk of one specific
mechanism. **Recommendation**: don't pursue this specific formulation further without a much
smaller magnitude and/or a gate that excludes maps like dilemma (e.g. only apply when *global*
bedDensity is above some threshold, same gating idea already proposed for the original
territory-clustering mechanism).

**T_CHOKE reservation (`wChoke=1.0`)**: 37.5% (12W/32) headline, but with Devil's timeout corrected
for, this is essentially a **null result, not a regression**: 5 of 8 maps were byte-identical to
baseline (exact same death counts) -- the "cramped" trigger condition (only fires on the same rare
full-veto state the emergency-split mechanism also uses) is too narrow to ever activate in ordinary
play, so it neither helped nor hurt anywhere it didn't fire. Slithery Fight's data is separately
contaminated (all 4 games timed out) -- also uninterpretable, not a real effect. **No evidence of
harm found; also no evidence of benefit, because the trigger essentially never activates.**
**Recommendation**: the mechanism itself (reservation via sonar) may still be worth trying with a
broader trigger condition (e.g. `exits<=1`, matching the existing `wPocket` corridor-danger trigger,
instead of only the full emergency veto) so it actually activates often enough to be judged at all.

**Process note**: running 3 heavy background jobs simultaneously (2 tourneys + param_search) caused
real CPU contention that contaminated both Devil and Slithery Fight's timing-sensitive results in
both A/B tests -- worth running only 1-2 heavy jobs at a time on this machine when a slow map is in
the panel, or bumping `tourney.py`'s timeout further under heavy parallel load. Always check the raw
per-game `[ERR]`/`TIMEOUT` lines before trusting a draw in the summary table, not just the death
counts in the per-map table (which can look empty enough to spot at a glance, but didn't stand out
immediately here since the table doesn't repeat "TIMEOUT" -- only the raw log lines do).

## bceval across the full 8-map CORE_PANEL, local games vs V7.12 (2026-09-30)

Ran a fresh local batch (8 maps x 2 seeds x 2 sides, `viper_vS4.7` vs `viper_v7.12`) with
`--keep-replays`, then `tools/bceval_batch.py` on the whole set. Confirms `bceval` works identically
well on local sandbox games as on ladder replays, and surfaces one new, sharp finding:

**Trophy has a near-perfect side asymmetry**: 100% dominant wins as side A (2/2, never contested),
100% early collapse as side B (2/2, both by round ~19). This is much more specific than "Trophy
collapses early" (the ladder-loss finding) -- it only collapses early **when we're side B**. Trophy
has `bedDensity=1.0` (literally every cell is a pearl bed). Dragons act in ascending id order each
round, ids assigned in spawn/file order -- on a map where every tile has a pearl, whichever side's
dragons act first each round may get a systematic first-claim advantage on adjacent pearls that
compounds quickly into a runaway lead, especially round-by-round in the opening phase before either
side has spread out. **Testable hypothesis, not yet confirmed** -- worth checking whether "side A"
correlates with "acts first" here specifically (need to check `DRAGON` order in `trophy.map` / how
`tourney.py` assigns team A vs the file's dragon list) and whether flipping or interleaving turn order
in a controlled local test changes the result. This reframes the earlier project-wide "side effect"
finding (A won more than B, several sessions ago) from "an unexplained engine artifact" to "possibly a
real, mechanistic first-mover effect on maximally-dense pearl maps" -- worth revisiting old bulk
results with this lens.

**Rest of the panel, dated precisely for the first time against our own reference bot (not just
strong ladder opponents)**:
- **Trauma**: all 4 games collapse early/mid (round 39-119) -- consistent with the known "early
  stagnation" diagnosis, now confirmed against V7.12 too, not just online opponents.
- **Schooltime**: 0/4 regardless of collapse shape (2 early, 2 recovered-then-lost) -- a persistent
  weakness that isn't reducible to a single collapse trigger, more consistent with a structural
  skill gap (matches the known head-to-head-dominated death cause) than a timing bug.
- **Slithery Fight**: mixed shapes (2 early, 2 late ~360-380) -- the catastrophic late-collapse
  signature from the ladder losses shows up in half these seeds too, but not all, suggesting the
  runaway spiral's onset is seed/randomness-sensitive, not deterministic per se.
- **Autarky**: 3/4 early collapse (59-79), 1 dominant win -- but the asymmetry runs the *opposite*
  direction from Trophy (the win was as side B, both A games collapsed early) -- so this is not the
  same side-first-mover story, just a separate, real early-game weakness worth its own look.
- **Default/Dilemma**: mixed, roughly matches known ~50-66% rates, nothing new.

## Revisited S4.6/S4.5's pheromone/territory/sonar work in light of today's research (2026-09-30)

The user asked which of today's research pairs well with the map-adaptive-parameters architecture,
and to re-examine `viper_vS4.6`'s pheromone/sonar system (built in an earlier session, "mixed
results"). Read `viper_vS4.6/mains4.6.cpp` and `msgauth.hpp` directly -- three separable mechanisms
with different verdicts, not one:

1. **Fountain pheromone/crowding decay grids** (`viper_vS4.5`, reverted by S4.6): a global decaying
   stigmergy field biasing pearl value, explicitly built "to guide swarm foraging on unknown maps."
   **S4.6's own header says this was reverted** ("Pure Evaluation... Pearl evaluation is 100%
   ground-truth driven") -- already tried and judged net-harmful once. `viper_vS4.7`'s `World::crowd`
   is a much narrower, still-kept version (crowding-only, no pheromone) that avoids the problem this
   solves for. **Not worth reviving as-is.**

2. **Territory (`FEATURE_TERRITORY`, kept, still `1` in the final S4.6)**: computes `enemyDist[]`/
   `friendDist[]` via a clean multi-source BFS from all *visible* heads (cheap, O(board size), capped
   at distance 40) and uses it two ways: (a) discount a contested pearl target if an enemy/friend
   reaches it first, (b) a direct move-safety penalty (`margin = clamp(enemyDist-friendDist,-10,10);
   if margin<0: score += margin*0.6`) for being in enemy-favored territory.
   **Major finding: `viper_vS4.7` already has (a)** -- `Policy::buildFriendFields()`
   (`policy.hpp:448`) computes the identical `friendDist_`/`enemyDist_` fields, and `enemyCloserFactor`
   (`policy.hpp:653`) already discounts contested pearls. **It's missing (b)**, the safety-margin
   penalty -- and since the fields are already computed for (a), adding (b) costs **zero extra BFS**,
   just a few lines in `scoreFrom`. This is a much more principled version of this session's reverted
   bed-clustering hack (`territoryWeight`) and directly matches the Voronoi-area-control research
   idea from earlier today, except it's already half-built and nearly free to finish. **Top concrete
   next implementation**, and it pairs well with map-adaptive parameters by scaling the penalty
   weight by a measured board-openness stat (or reusing `bedDensity`) -- contested space should
   matter more on open maps (Devil, Slithery) than tight mazes (Trauma) where paths are already
   constrained.

3. **Sonar schema** (`msgauth.hpp`'s 8 message types vs. S4.7's current 2): `T_INTENT` (broadcast your
   next 3 moves; receivers reserve those cells so teammates route around them -- literally the
   "reservation table" collision-avoidance technique from today's web research, already built once)
   and `T_CHOKE` (reserve a chokepoint cell for a few rounds, a decentralized anti-congestion signal)
   were **not** flagged as reverted in S4.6's header -- only pheromone/crowding was. Their track
   record is neutral/unknown, not actively bad. Directly relevant to Schooltime's head-to-head-
   dominated losses and the Portals self-trap/Slithery Fight congestion problems. Worth an isolated
   test in S4.7's cleaner framework (proper flood-fill safety already handles what pheromone was
   compensating for) rather than dismissing alongside the pheromone verdict.

**Recommended order**: (1) port the territory safety-margin penalty (free, fields already exist),
(2) prototype `T_INTENT`/`T_CHOKE`-style reservation via sonar for the crowding/congestion problems,
(3) leave fountain-pheromone bridging alone -- already tried, already reverted, needs a genuinely new
angle before it's worth relitigating.

## Further research (2026-09-30, second pass): swarm coordination and competitive-snake community tactics

Continued the rule-based (non-neural) research while a local batch test ran, covering ideas from the
user's original 24-idea brainstorm that hadn't been specifically searched yet:

- **Ant-colony response-threshold task allocation** (Bonabeau et al.): each agent has a per-task
  threshold; if a local stimulus (e.g. "how pearl-rich is my area," "how much longer is the known
  queen than me") exceeds it, the agent switches task (forage/feed/grow) -- fully decentralized, no
  explicit voting needed. **Directly applicable to idea #2** (soft role assignment) and to the
  late-game consolidation problem (#6/#16): instead of `growRound`/`feedRound`'s hard global-round
  switches, each dragon could decide "am I feeding yet?" from a local stimulus (own length relative
  to the best known queen claim, which `gossip.hpp` already tracks) rather than a shared clock --
  this could naturally stagger the feed-phase convergence that's implicated in several open problems
  (Portals' self-trap cluster, possibly part of Slithery Fight's spiral) without needing the
  previously-tried-and-neutral `feedWindow` staggering hack.
- **ID-based echo-wave leader election**: a clean, well-established algorithm for exactly the
  "multiple dragons independently think they're the tallest" problem `gossip.hpp`'s `T_QUEEN` claim
  already partially addresses (keep whichever claim is longer). Concrete, cheap improvement: break
  exact-length ties by dragon id (lower id wins, say) so the swarm converges on a single deterministic
  queen claim instead of possibly oscillating between multiple equal-length candidates -- a one-line
  comparator change (`len` primary, `id` secondary) in `Gossip::receive()`'s `T_QUEEN` handling.
- **Influence maps / potential fields (RTS games)**: validates the *existing* architecture rather
  than introducing something new -- `scoreFrom`'s weighted-sum-of-terms design (`wHot`, `wCrowd`,
  `wPredict`, `wCompass`, ...) is already an influence-map-style approach. The concrete lesson from
  this literature: treat it explicitly as one combined field (attractive pearls/queen, repulsive
  enemies/own-crowd) when adding the Voronoi-territory idea, rather than another bolt-on term, so the
  weights stay interpretable as they multiply.
- **Competitive Snake.io community tactics** (real player strategy guides, not academic): (1) "turn
  your length into a barrier" -- deliberately position a long body to block an opponent's escape
  routes, a combat-sophistication idea already deprioritized this session (matches idea #13,
  "cooperative body walls") since survival/consolidation are the confirmed bottlenecks, not combat
  skill; (2) **"scavenge pearls dropped by any dead dragon, not just count on steady bed income"** --
  worth checking whether `scoreFrom`'s target valuation treats a sudden multi-pearl drop (from any
  death nearby, enemy or ours) with the urgency it deserves, since it's a one-time windfall rather
  than a steady `hot_` rate and could be under-valued by the existing decayed-distance scoring that's
  tuned for steady respawning beds. Cheap to check, not yet investigated.

**Recommended priority for next session's mechanism work** (supersedes the old idea-list ordering
now that Trophy/Slithery Fight have precise diagnoses): (1) confirm the Slithery Fight
emergency-split hypothesis via the isolation test, (2) trace Trophy's round-0-40 collapse directly,
(3) prototype the articulation-point room check for `trySplit`'s child-safety gate specifically
(the most concrete, well-scoped new idea from this research), (4) the Voronoi-territory idea as a
generalization of the shelved bed-clustering mechanism, this time keyed on contested space rather
than pearl locations.

## Sonar echoes: found a real discard bug, added single-probe sensing (2026-09-30)

A teammate tried sending all 3-4 sonar rays together in S4.6 with mixed results, reasoning that
sending several rays per turn loses directional information: `ECHOES` (docs/protocol.md) gives one
aggregate count of what *all* the sonars sent last turn stopped on (kelp, ally, ally head, enemy,
enemy head) -- with more than one ray in flight there is no way to tell *which* direction actually
hit the kelp/enemy/etc. it counted, only that one of them did somewhere.

**Checked our own code first and found something worse: `viper_vS4.7` never read echoes at all.**
`io.hpp`'s `readTurn()` detected the `ECHOES` line (to skip past it correctly) but never captured
its five values -- pure dead data, discarded every turn for free info the engine was already handing
us. This matches idea-list item #18, flagged back on 2026-09-29 as "not currently read at all...
worth adding, cheap" but never done.

**The single-probe idea is the right fix for the attribution problem**: our `gossip.hpp` already
sends 0-3 rays a turn (`T_FOUNTAIN`/`T_QUEEN`/`T_CHOKE` on `w.t.dir`/`+1`/`+2`, dropping the 4th ray
entirely) for messaging, not sensing. On a turn where none of those fire (no pearl to report, not a
grower, not cramped -- common), there is a free ray doing nothing. Sending exactly one exploratory
sonar there, rotating through the least-recently-probed direction, makes next turn's echo
unambiguous: exactly one ray went out, so whichever of the five counts is nonzero (or none) describes
that specific direction with certainty.

**Implemented** (gated off by default, infrastructure only -- see `S4_7_PLAYBOOK.md`):
- `io.hpp`: fixed the parsing bug, `Turn::echo[5]` now holds the real counts every turn.
- `world.hpp`: `lastProbeDir` (the one ray sent alone last turn, -1 if 0 or >1 rays went out that
  turn -- ambiguous) plus `probeRound[4]`/`probeKind[4]`, the most recent unambiguous read per
  direction (kind index 0=kelp/1=ally/2=allyHead/3=enemy/4=enemyHead, -1 = hit nothing).
- `gossip.hpp`: `receive()` attributes this turn's echo to `lastProbeDir` before anything else runs;
  `broadcast()` tracks how many rays actually went out this turn (via a small `send()` lambda) and,
  if zero, spends one on `T_INTENT` (a type nothing currently handles on receipt, i.e. a true no-op
  payload) toward the stalest-known direction.
- `common.hpp`: `Params::probeEnabled = false` -- the whole feature is inert until flipped on.
  **Deliberately not wired into `Policy::scoreFrom` yet.** This commit only builds the sensor;
  turning `probeKind`/`probeRound` into a scoring term (e.g. repel from a direction that just
  echoed an enemy head, or bias toward one that echoed nothing / a kelp-free opening for `maps_gen`
  exploration) is a separate, testable step, the same two-phase pattern as `wTerritory`/`wChoke`.
- Verified: real wasm build (forced past the `main.cpp`-keyed cache via a rebuild-marker touch, see
  AGENTS.md's pitfall note) compiles clean; a same-seed dilemma re-run with the gate at its default
  `false` reproduced the exact prior death counts (26/34), confirming zero behavior change from the
  parsing fix and dormant probe logic alone.

**Where this pairs with map-adaptive parameters and the `maps_gen` generalization gap**: the
probe's real value is highest exactly where `knownmap.hpp` has nothing to offer -- an unrecognized
map, where every pearl bed and every wall has to be discovered from vision alone. A `maps_gen` bot
currently only sees its 7x7 window; a rotating single-probe ray extends that to a full board-width
line in up to 4 directions over a handful of turns, essentially free (the ray was otherwise unused).
This is the same shape as idea-list item #4 (frontier exploration / deliberate scout spread,
"partially redundant with `knownmap.hpp`... but still valuable for `maps_gen`'s 300 unseen maps")
-- single-probe echoes are a concrete, already-half-built mechanism for exactly that gap, and a
natural next experiment once the `maps_gen` 21.7%-win-rate investigation (see above) has a first
`BC_DEBUG` trace to point at a specific failure to fix.

**Not yet done, in order**: (1) A/B the dormant sensor with a first real scoring use (simplest:
mild repulsion from a direction whose most recent `probeKind` is enemy/enemyHead, mirroring
`wDanger`'s shape) against the `CORE_PANEL`; (2) if that's neutral-to-positive, test specifically on
`maps_gen` where the exploration value should matter most; (3) only then consider whether probing
should ever pre-empt a real gossip message (currently it never does -- probes are strictly
leftover-ray-only, so this feature can never cost bandwidth the messaging system already wanted).

## viper_vS4.7 (post-param_search-gains, gated echo/probe additions) vs viper_v7.12 and Y.7.12-nn.1 (2026-09-30)

Full `CORE_PANEL` (8 maps, 2 seeds, both sides, 32 games each), run via the newly-wired
`tools/tourney.py --judge zig` (see above), with `bceval_batch.py`/`growth_pattern.py` on the kept
replays.

**vs viper_v7.12: 16W 16L (50.0%)** -- reproduces the earlier `paramsearch_applied_validation.txt`
result exactly (same per-map W/L, same death counts), now via a different, verified-identical judge
backend, in 712.5s instead of 1097.8s despite running concurrently with the nn.1 batch below.
Per-map: Dilemma/Devil 100%, Default 75%, Autarky/Trophy 50%, Schooltime 25%, **Trauma/Slithery
Fight 0%** -- the same two persistent weak maps as every prior session.

**vs Y.7.12-nn.1 (the actual current ladder champion, V7.12 + move-imitation network): 8W 23L 1E
(25.8%)** -- a real gap. Devil is the only map we win outright (4/4); Default splits (2/2); every
other map is a loss, including Trophy and Autarky (0/4 each) where we're competitive against plain
V7.12 (50%). One infra timeout on Slithery Fight, plausibly from the 12-way WSL judge contention
running both batches at once (see below) -- treated as noise, not a real loss.

**bceval shape analysis makes the gap concrete**: against V7.12, our trajectory is `dominant=12,
early=8, mid=3, late=1, recovered=8` (37.5% of games we're never really behind at all). Against
Y.7.12-nn.1, it's `dominant=4, early=17, mid=2, late=1, recovered=8` -- more than half our games
(53%) are decided in the *opening*, before any tactical mistake could compound, and Trophy/Autarky
are **100% early-collapse** against nn.1 specifically (4/4 and 4/4) vs a 50/50 dominant/early/
recovered mix against plain V7.12 on those same two maps. The network gives V7.12 a faster start
that our current opening play cannot match, not a lategame or combat edge.

**growth_pattern.py confirms an endgame population problem even in our own wins**: winners' median
unit count in games we win against V7.12 *drops* from 26 (round 400) to 14 (end) -- we shed
population getting to the finish line. In games Y.7.12-nn.1 wins, its own winning-side median units
*rises* through the same window (30.5 -> 36.5) and stays far higher overall (round-300 median 54.5
vs our 35.0, end-game mean 33.8 vs our 25.7). nn.1 keeps growing through the phase where we start
consolidating/feeding -- consistent with the still-open Trophy regression and the general
population/growth-speed gap flagged throughout this session, now with a champion-strength comparison
point instead of only V7.12.

**Process note on the two batches run together**: running both comparisons at `-j 6` each (12
parallel WSL `loong-judge` processes on a 12-core machine) genuinely saturated the CPU during the
Slithery Fight/Schooltime tail (all 12 processes independently confirmed at ~98-100% CPU via `ps
aux`, not hung) and produced the one Slithery Fight timeout noted above. No other errors resulted,
and total wall time was still shorter than a single non-parallel sandbox-backed run, but the lesson
holds from earlier in the session: **serialize heavy paired comparisons, or lower `-j`, rather than
running two full `-j6` batches at once** -- the timeout-as-false-draw failure mode this session fixed
once already (tourney.py's `errors` bucket) is exactly what high core contention risks reintroducing.

## Continuous sonar sensing upgrade, and confirming the param_search state (2026-09-30, later)

Per direct user feedback: don't weight the `Y.7.12-nn.1` comparison above too heavily -- it's
specifically trained on the known maps (per its own README) and untested on unknown ones, so it's
not the right yardstick for the generalization work; the real near-term goal is still beating plain
`viper_v7.12` substantially. Keeping the nn.1 numbers on record above since they're real data, but
not treating the 25.8% figure as the headline this session's work should be judged against.

**Continuous probing, upgraded**: the single-probe design above originally only sent when a turn had
*nothing else* to report (`rays == 0`). Checked which ray each existing message targets -- `T_FOUNTAIN`
uses `w.t.dir`, `T_CHOKE` uses `+1`, `T_QUEEN` uses `+2` -- and `(w.t.dir + 3) % 4` is therefore never
used by any message, on any turn, by construction. `gossip.hpp::broadcast()` now sends a scan on that
ray *every turn unconditionally* (still gated off by `Params::probeEnabled`), true continuous
sensing rather than opportunistic idle-ray use. Attribution stays honest: only a turn where the probe
was the sole ray (`rays == 1`) updates `probeKind`/`probeRound` as an exact per-direction read; a
turn where a message also fired still sends the scan (continuous polling), but that round's echo
can't be split between two rays, so it's left unrecorded rather than guessed at. Verified: real wasm
rebuild compiles clean; a same-seed dilemma re-run with the gate at its default `false` reproduced
the exact prior death counts again (26/34) -- still fully inert until `probeEnabled` flips.

**Where this compounds with encrypted sonar into real swarm coordination**: every message is already
authenticated per-sender via `msgauth.hpp` (SipHash MAC), so a dragon's own probe reads are exactly
as trustworthy as a gossiped belief. Once probe data is wired into scoring, the natural next step is
sharing high-value finds (e.g. "enemy head echoed north of cell X") over the same gossip channel
`T_FOUNTAIN` already uses for pearls -- turning individually-sensed threats into team-wide awareness
at the same near-zero bandwidth cost, not just better-informed individuals. Not implemented (a real
message-schema decision, not a small follow-on) -- flagged as the step after the base sensor itself
is validated against `CORE_PANEL`/`maps_gen`.

**Confirmed the actual param_search_bceval state directly from its log** (`ladder/losses/
param_search_bceval.txt`), since the user asked whether the two tournaments above used the real
fine-tuned result: they do (`wTarget=4`, `swarmChild=3`, `wPredict=0` are live in `common.hpp`), but
the search itself is **not fully complete**. The log's coordinate-descent sweep got through 10 of 16
listed `SWEEP` parameters (`wTarget` through `wPocket`) and stopped there -- `wCrowd`, `feedRound`,
`feedMargin`, `queenDeferMargin` were never tested at all, and `wTerritory`/`wChoke` were deliberately
excluded from this sweep (tested separately as their own gated A/B experiments). The `DONE_PARAMSEARCH`
marker at the log's end is an external wrapper marker, not something `param_search.py` prints itself,
so its presence only means the process exited -- consistent with the WSL2 system restart cutting it
off, not a clean finish. Resuming from `wCrowd` is still open work if the remaining sweep is wanted.

**First real scoring use of the probe sensor**, per direct user feedback ("incorporate echo
mechanics well, not just sonar communication") -- the sensor was otherwise still fully dormant
infrastructure. Added `Params::wProbeDanger` (off by default) + `probeMemory` (8 rounds): in
`policy.hpp`'s `k == 0` danger block, a candidate move whose own absolute direction `d` has a recent
(`age <= probeMemory`) exact echo (`world.hpp`'s `probeKind[d]`/`probeRound[d]`) of enemy or enemy
head adds `wProbeDanger * mult` to that move's danger -- the same shape as the existing `wPredict`
vision-range lookahead term just above it, but reaching to sonar range instead. This is deliberately
scoped to the one case a probe echo can name an absolute direction confidently enough to act on
without first building a general probe-derived scoring field (kelp/ally signals still unused).
Verified: real wasm rebuild compiles clean; same-seed dilemma+trophy re-run with `wProbeDanger` at
its default 0 reproduced the exact prior death counts again (26/34 dilemma, 126/158 trophy combined)
-- inert until raised. A/B test launched in `viper_vS4.7_tune` (`probeEnabled=true,
wProbeDanger=1.5`) against `viper_v7.12` on the full `CORE_PANEL`, single batch at `-j4` (not run
alongside another heavy job, learning from the earlier 12-way-contention timeout).

**Result: net regression, not shipped as a flat constant -- but a real, specific gain inside it.**
14W-18L (43.8%) vs the 50.0% baseline. Per-map, though, this is not a uniform loss:

| Map | Baseline | wProbeDanger=1.5 | delta |
|---|---|---|---|
| Slithery Fight | 0% | **50%** | **+50pp** |
| Trauma / Dilemma / Devil | 0% / 100% / 100% | unchanged | 0 |
| Autarky | 50% | 25% | -25pp |
| Trophy | 50% | 25% | -25pp |
| Default | 75% | 25% | -50pp |
| Schooltime | 25% | 25% | 0 |

Slithery Fight -- this session's single most persistent blind spot, 0% in every batch it has ever
appeared in (`paramsearch_applied_validation.txt`, this session's own two earlier comparisons) --
jumped to 50% with sonar-range enemy avoidance active. Consistent with the standing hypothesis
(dense kelp/wall terrain, articulation-point risk) that this map specifically punishes late
detection of an approaching enemy past vision range. But the same flat weight badly hurt the three
dense-bed maps (Autarky/Trophy/Default), where speed-to-eat matters more than defensive range and a
flat danger penalty likely makes dragons too cautious to compete for contested beds.

**Not shipped.** The fix is very likely the same pattern already proven for `gamma`
(`KnownMapMatcher::adapt()`): `wProbeDanger` should scale with measured map structure (low/off on a
dense-bed map, full strength on a sparse/combat-heavy one) instead of being one flat constant across
every map. `wProbeDanger=0` remains the shipped default in `viper_vS4.7`; the tune copy
(`viper_vS4.7_tune`) keeps the experiment value for the next test, not `viper_vS4.7` itself.

## Map-adaptive wProbeDanger: implemented and A/B tested (2026-09-30, later)

Implemented the gating proposed above: `knownmap.hpp` now also computes `wallDensity` (fraction of
all edges that are kelp) alongside `bedDensity` in `apply()`, and `adapt()` adds
`wProbeDangerWallFactor * wallDensity` on top of the flat `wProbeDanger` (both default 0). Measured
`wallDensity` directly from `maps_data.hpp` before choosing a test factor: Slithery Fight 0.151,
Schooltime **0.190** (higher than Slithery Fight), Autarky 0.109, Default 0.106, Trophy 0.070 --
`wProbeDangerWallFactor=10.0` maps Slithery Fight's density to ~1.51, matching the flat value already
tested. Verified: real wasm rebuild compiles clean, same-seed dilemma+trophy re-run with the new
weight at its default 0 reproduced the exact prior death counts again -- inert until raised.

**A/B result (viper_vS4.7_tune, `probeEnabled=true, wProbeDangerWallFactor=10.0, wProbeDanger=0`,
CORE_PANEL, `--judge zig`, `-j4` alone): 15W-17L (46.9%)** vs the 50.0% baseline -- still a net
regression, but the per-map shape moved a lot and in an interesting direction:

| Map | Baseline | Flat wProbeDanger=1.5 | Adaptive (wallDensity-gated) | wallDensity |
|---|---|---|---|---|
| Schooltime | 25% | 25% | **75%** | 0.190 (highest) |
| Slithery Fight | 0% | **50%** | 0% | 0.151 |
| Autarky | 50% | 25% | **50%** (recovered) | 0.109 |
| Trophy | 50% | 25% | 25% | 0.070 |
| Default | 75% | 25% | 25% | 0.106 |
| Trauma/Dilemma/Devil | 0%/100%/100% | unchanged | unchanged | -- |

Two real findings, one likely noise:
1. **Schooltime jumped 25%->75%**, and its `wallDensity` (0.190) is the highest of any tested map --
   consistent with the mechanistic story (dense-wall maps benefit from sonar-range warning). `bceval`
   confirms this isn't a fluke shape: **all 4 Schooltime games are now `recovered`** (fell behind,
   came back to win) -- a distinct, new signature never seen on this map before (it was a flat-loss
   pattern in every earlier batch this session).
2. **Autarky fully recovered to baseline** (25%->50%) once its lower `wallDensity` (0.109) scaled
   the term down from the flat test's full 1.5 -- exactly the intended effect of gating by structure
   instead of using one constant.
3. **Slithery Fight flipped back to 0%**, contradicting the flat test's +50pp gain -- but the
   *effective* `wProbeDanger` there (~1.51) is nearly identical to the flat test's 1.5, so this is
   most likely small-sample noise (4 games/map, the same caution flagged all session), not a real
   reversal. `bceval`'s shape for Slithery Fight here is a mixed `early=2, recovered=2`, not a clean
   loss pattern, which supports reading it as noise rather than a genuine regression. Needs a larger
   sample (or SPRT) specifically on this map before treating either the +50pp or the 0% result as
   settled.

**Net verdict**: still not shipped (46.9% < 50% baseline), but this is closer to a real find than the
flat version was -- Schooltime's clean, mechanistically-explained gain plus Autarky's clean recovery
are two genuine wins from the gating change alone. Trophy/Default remain regressed under both the
flat and adaptive versions despite their low `wallDensity`, which the wall-density signal does not
explain -- something else about those two dense-bed maps is hurt by sonar-range caution specifically,
not yet understood. **Recommended next step**: don't chase a single scalar weight further on a
32-game sample; either (a) run a larger/SPRT-driven batch isolating Schooltime and Slithery Fight
specifically to resolve which of the two contradictory Slithery Fight results is real, or (b) also
gate the term *off* on the two maps it hurts regardless of wall density (Trophy/Default), the same
"why does this help structurally similar maps differently" question already open for `wTerritory`.

## SPRT settles it: wProbeDanger is not a real gain (2026-09-30, later)

Per the recommendation above, ran `tools/sprt_test.py` (extended this session with a `--judge zig`
flag) isolated to exactly the two contested maps: `viper_vS4.7_tune` (wall-density-gated
`wProbeDanger`) vs `viper_v7.12`, Slithery Fight + Schooltime only, testing whether the true combined
win rate is meaningfully above the historically-weak ~25% baseline (p0=0.25) at a genuine 50% level
(p1=0.5). **Result: reject after 29 games, final win rate 27.6%, LLR -2.970 (bound -2.944).** No
material difference from the null. Schooltime's earlier "75%, all 4 games recovered" result was a
4-game sample that did not hold up under a larger, properly-powered test -- exactly the kind of
noise this session has repeatedly warned about with small per-map samples, now caught by the tooling
built specifically to catch it.

**Verdict: `wProbeDanger` (flat or wall-density-gated) is not shipped, and not worth further tuning
at this weight/gate.** Both `wProbeDanger=0` and `wProbeDangerWallFactor=0` remain the defaults in
`viper_vS4.7`. The underlying sensor infrastructure (echo parsing fix, continuous single-ray probe,
`wallDensity`/`bedDensity` map-structure signals) stays in place and cost nothing to keep -- it's the
one specific scoring use of it that didn't pan out, not the sensor itself. Per direct user
feedback, the priority now shifts back to the macro population-growth/consolidation levers this
session's strongest evidence (§1a: winners run ~50% more units from round 100, 77.5% of wins are
`dominant` not `recovered`) actually points to, rather than further tactical sonar/danger tuning --
see the next section for where that leads.

## Trophy's round-0-40 collapse: root cause found via BC_DEBUG -- a real blind-forage bug, same family as Trauma's

Finally ran the direct trace repeatedly recommended and never executed (this exact step was flagged
in this file at least 3 times before today). Used a local, reproducible seed (Trophy, seed 1000, our
build as side B vs `viper_v7.12`) that reproduces the same collapse-by-round-20 signature `bceval`
found on real ladder losses (P(A wins) 0.46->0.81->0.92 by round 19-24).

**First real gotcha, fixed on the spot**: built a `viper_vS4.7_dbg` copy with `#define BC_DEBUG`
and ran it through `--judge zig` first -- **zero `dragonLog`/`dragonIndicator` events in the
replay**, vs 1450/6501 of each from the identical game through `unswbc run --sandbox`. Not a real
limitation, just a missing flag: `loong-judge` has a `--debug` bitmask (`DEBUG_LOGS=1`,
`DEBUG_INDICATOR=2`, default 0 in single-game mode) found by reading `main.zig`/`run.zig`.
`tools/tourney.py`'s `play_zig()` and `--debug` CLI flag now expose it -- with `--debug 3` the Zig
judge's event counts match the sandbox exactly (confirmed: same 1450/6501). **So the Zig judge is
usable for BC_DEBUG tracing too now** (`tourney.py ... --judge zig --debug`), no need to drop to the
slower sandbox judge for this.

**The actual finding, from the sandbox replay's `dragonLog` events**: our dragon **id1 foraged for
41 straight rounds (round 0 through round 40) without eating a single pearl**, staying at L=3, on
**Trophy -- a `bedDensity=1.0` map where literally every cell is a pearl bed.** Its teammate (id3,
also starting L=3) ate at round 21, split at round 22, and both id3 and its child kept eating
periodically (round 27, 40) while id1 sat idle the whole time. This is the same shape as the
already-fixed Trauma 78-round blind-forage bug (`wCompass`'s root cause), just on a completely
different map archetype (maze/sparse vs Trophy's maximally dense), which means the earlier fix did
not cover this case.

id1's own path (from `dragonUpdate` events) shows it oscillating within a small region
(roughly x:14-20, y:19-23) from round 5 through round 25 rather than committing to any pearl, while
real pearl spawns occurred in that same neighborhood (a bed at (23,19) was available from round 0
through round 20, within plausible reach of where id1 was circling). This looks like a genuine
decision bug -- id1 had food nearby and didn't take it -- not a "no pearls were actually available"
explanation.

**Not yet root-caused to the exact mechanism.** `out.log()` currently only records the *chosen*
move's summary (`why`/`depth`/`ms`/`L`/`body`), not the scores of the candidates it rejected, so it's
not possible from this log alone to see *why* id1 didn't value the (23,19) pearl enough to move
toward it. **Concrete next step**: add a temporary, BC_DEBUG-gated dump of the top few candidate
move scores from `Policy::scoreFrom` (not just the winner) for one dragon in this exact window, the
same escalation that found `wCompass`'s bug once the round-level log alone wasn't enough there
either.

**Why this matters more than another map-specific bug**: this is a first real mechanistic handle on
the "opponent out-breeds us in the pearl-dense region" diagnosis that's applied to Trophy all
session -- it was never actually a population*-growth-rate* problem in the abstract, it's a concrete
dragon sitting idle in a sea of food. Given this session's own strongest finding (winners' population
lead starts at round 100 and never closes), a bug that silences one full starting dragon for the
first 40 rounds of a 500-round game is exactly the kind of defect that would produce that signature --
worth checking whether this same pattern recurs on other maps/seeds before assuming it's Trophy-
specific.

## Root cause pinned down precisely, and a fix implemented (2026-09-30, later)

Added per-direction score logging (`Policy::decide()`'s final `total[d]`/`first[d].eat`, BC_DEBUG-
gated) and re-ran the same trace with the Zig judge's newly-fixed `--debug 3` flag (13s instead of
~140s through the sandbox). **Result for `id1` across rounds 0-15**: scores of 0-2 in every
direction, `eat` false everywhere -- confirming this is not a valuation bug rejecting a known nearby
pearl, it's that no direction offers any real signal at all.

Traced this to `World::belief()` (`world.hpp`): it returns **exactly 0** for any tile never directly
seen, full stop -- regardless of whether `knownmap.hpp` already told the bot that tile is a bed.
`Policy::buildTargets()`'s countdown value (`cd`) has the same gate (`w_.next[c] >= 0`, vision-only).
So on Trophy (`bedDensity=1.0`, a *known* map where every cell's bed location is known from round 0),
an unvisited cell is valued identically to a random unexplored tile on a totally unknown map -- only
the flat `exploreValue=0.03` distinguishes it from nothing, which is far too weak a signal relative
to everything else in the score to produce decisive movement. The result: near-tied scores in every
direction, and the dragon wanders/circles a small already-seen patch instead of striking outward,
exactly matching id1's actual observed path (oscillating in a ~6x4 tile pocket for 20+ rounds).

**Fix implemented**: `Params::exploreValueDensityFactor` (default 0), added to `common.hpp`,
applied in `KnownMapMatcher::adapt()` the same way `gamma`'s density adjustment works:
`exploreValue += exploreValueDensityFactor * bedDensity^2`. On a dense-bed map, *any* unexplored
direction is likely to be productive, so the exploration incentive should scale up with measured
density instead of staying flat -- squared so the boost concentrates near `bedDensity==1` (Trophy/
Default's regime) and stays small on sparse maps (Dilemma/Trauma), the same shape `gamma`'s own
adaptation already uses for exactly the same reason. Verified: real wasm rebuild compiles clean,
same-seed dilemma+trophy re-run with the factor at its default 0 reproduced the exact prior death
counts again (26/34, 126/158) -- inert until raised. Snapshotted `baselines/S4.7.7` before this
change per the baseline-before-drastic-changes rule. A/B test (`viper_vS4.7_tune`,
`exploreValueDensityFactor=0.12`, ~0.03->0.15 at `bedDensity=1.0`) launched against `viper_v7.12` on
the full `CORE_PANEL` -- result pending.

**A/B result: net negative, another flat weight that doesn't hold up on the full panel.**
14W-18L (43.8%) vs the 50.0% baseline. Trophy itself was unchanged (50%->50%) -- the fix didn't hurt
the map it was diagnosed on, but didn't clearly help it either at this sample size -- while **Default
regressed hard (75%->25%)**, despite sharing Trophy's exact `bedDensity=1.0`. This is now the third
time this session a flat, bedDensity-gated weight has produced opposite reactions on two maps with
identical measured density (`wProbeDanger`/`wallDensity` did the same to Slithery Fight vs Autarky/
Trophy/Default earlier tonight) -- strong evidence that a single scalar density number is not a rich
enough map-structure signal to gate these terms safely, not evidence that the underlying diagnoses
(Trophy's blind-forage bug, the wall-density mechanism) were wrong. **Not shipped**;
`exploreValueDensityFactor=0` stays the default.

## Self-sensed topology: the actual point, redirected by the user overnight

Direct correction from the user: every map-adaptive fix above (`gamma`, `wProbeDanger`,
`exploreValue`) is gated by `knownmap.hpp`'s `bedDensity`/`wallDensity` -- numbers that only exist on
the 15 maps this repo has data for, i.e. never a real tournament map. Local-panel results from any of
tonight's density-gated features say nothing about the actual goal (dominating on unseen maps); they
can only ever help calibrate parameters or toggle features for known topology classes during testing.
**The bot itself must sense topology purely from vision and sonar, with no lookup table involved.**

**Implemented** (`world.hpp`, `gossip.hpp`, `knownmap.hpp`, `main.cpp`): a self-sensed replacement
for both density signals, designed around what each sensor can actually report:
- **`selfWallDensity()`**: echo counts (kelp/ally/enemy, `docs/sonar.md`) are an aggregate per-turn
  total, not attributable to a single ray when several fire together -- the same limit that
  motivated the single-ray probe (see above). But the *aggregate* is still valid information summed
  over many turns: every ray ever sent contributes to a running `kelp hits / rays sent` ratio,
  independent of single-ray attribution, with no `rays==1` gating needed at all. `gossip.hpp` now
  tracks `lastRaysSent` (however many fired, 0-4) and accumulates `sonarKelpCum`/`sonarRaysCum`
  (plus ally/enemy counts, not yet consumed) every turn something was sent -- so this fills in even
  from ordinary `T_FOUNTAIN`/`T_QUEEN`/`T_CHOKE` traffic with `probeEnabled` off, faster still with
  it on. This is a genuinely different, complementary use of echoes from the directional probe: not
  "which way is the danger" but "what kind of terrain am I generally in."
- **`selfBedDensity()`**: echoes carry no pearl signal at all (the five kinds are terrain/dragon
  only), so this comes from vision instead -- `world.hpp`'s `observe()` now counts each tile once,
  the first time it ever enters vision, into `bedTilesSeenCum`/`totalTilesSeenCum`.
- Both getters return `-1` ("not yet reliable") below a minimum sample floor (30 rays, 100 tiles),
  so early-game noise doesn't produce a wild adjustment before there's real signal.
- **`KnownMapMatcher::adapt()`** now takes `World const&` and prefers the exact known-map number
  when resolved (instant, from round 0), falling back to the self-sensed estimate only when it
  isn't -- so this activates identically on `maps_gen`'s 300 unseen maps as on a known one.

**Real consequence, not a no-op**: `gammaDensityFactor` (already `0.08`, not gated, in the shipped
default) previously only ever adjusted `gamma` on a resolved known map -- every unknown map got zero
adjustment, by construction, since `bedDensity` was always `-1` there. With this fix, **`gamma` now
also self-adapts on unknown maps once ~100 tiles have been seen**, live in the shipped
`viper_vS4.7` default, not a gated experiment. Verified zero change on the known `CORE_PANEL` (exact
same death counts on dilemma/trophy re-runs -- `bedDensity` is already resolved there, so the
fallback never triggers), but this is expected to be a real, if noisy, behavior change on `maps_gen`
specifically -- that's the next test, not yet run as of this note.

**Not yet done**: consuming `sonarAllyCum`/`sonarEnemyCum` (only `sonarKelpCum` feeds `selfWallDensity()`
so far); testing on `maps_gen` directly (the actual target this feature exists for); the multi-echo
"learn surroundings" idea's other natural extension -- sharing a dragon's own high-confidence
self-sensed density over gossip so a teammate's early exploration bootstraps the whole team's
estimate faster, not just individually.

## Tested on maps_gen directly: self-sensed gamma made it worse, reverted

Ran the actual target test: the exact same 30-map/60-game `maps_gen` protocol as the original 21.7%
baseline (same map list, same opponent). **Result: 18.3% (11W-49L) -- worse, not better.**

**Root cause, reasoned through before reverting**: `gamma`'s density adjustment was calibrated
against a known map's true *global* bed fraction (`bedDensity` = bed cells / all cells, computed
once from the whole map's data). `World::selfBedDensity()` instead reflects only the small,
non-uniform *local* patch a dragon has actually walked by the time it hits the 100-tile sample
floor -- and a fresh dragon's early exploration is not a random sample of the map, it lingers near
wherever it started. A dragon that happens to start in (or drift into) a locally pearl-rich pocket
overestimates density and over-sharpens `gamma` for the rest of the game, everywhere else on a map
that may be far sparser overall. This is a real, structural limitation of a raw running-ratio
estimator for this specific use, not a implementation bug.

**Reverted**: `gamma` now uses *only* the exact known-map `bedDensity` again, same as before
self-sensing existed. The self-sensed infrastructure itself (`selfWallDensity()`/`selfBedDensity()`,
the accumulation in `gossip.hpp`/`world.hpp`) stays in place -- it still feeds `wProbeDanger`'s
wall-density term, which is harmless since that weight is 0 by default, and remains available for a
better-designed consumer later.

**Correction, found right after "confirming" the revert**: the re-run (same protocol, gamma reverted
to known-map-only) came back **15.0% (9W-51L)** -- worse than even the 18.3% self-sensed-gamma
result, which undermines the clean "reverting fixed it" story above. Checked why before trusting
either number: **the original 21.7% baseline (`mapsgen_validation.txt`, written 00:06) necessarily
used the sandbox judge -- `tools/tourney.py`'s `--judge zig` support didn't exist until 03:21 the
same night.** Both of tonight's re-runs used `--judge zig`. Zig and sandbox were verified byte-
identical on specific known-map games (Dilemma, Trophy) earlier tonight, but never specifically on
any `maps_gen` map, so a judge-backend difference on procedurally-generated layouts specifically
can't be ruled out as a contributing factor alongside the gamma change itself -- these two tests are
not a clean, isolated comparison. **Correct read**: don't over-interpret the specific 21.7% vs 18.3%
vs 15.0% ordering as proof the self-sensed-gamma change itself made things worse; what all three
numbers agree on is that generalization to unseen maps is badly broken regardless (15-22% across
every variant, vs 40-50%+ on the known panel), and that remains the real, unresolved finding. The
revert stands on its own logical merits (gamma calibrated for a global statistic given a locally-
biased local one, independent of what these specific noisy numbers show) rather than on this
particular before/after comparison. **Process lesson for next time**: always pin the judge backend
identically across any two runs being compared, the same discipline as pinning seeds/maps/opponent.

**What this means for the self-sensing idea overall**: the *sensing* mechanism (accumulating real
signal from echo/vision with no lookup table) is sound and worked as designed -- the mistake was
feeding a locally-biased running estimate into a term calibrated for a true global statistic without
accounting for the difference. A better estimator for future use would need either much more
exploration before trusting the number (the 100-tile floor is likely far too low relative to a
`maps_gen` map's real size), or an explicit correction for how spatially spread the sample is (not
just its raw count) -- worth returning to once there's a specific consumer designed around a noisy,
locally-biased density signal from the start, rather than retrofitting one built for exact data.

## param_search_v2 (resumed, dedicated scratch dir): swarmChild=4 clears the submission bar

Resumed the coordinate-descent sweep from a clean baseline (`viper_vS4.7_paramsearch2`, a fresh
scratch copy so it doesn't collide with any other running experiment -- see `tools/param_search.py`'s
new `--bot-dir`/`--judge` flags), 6 faster maps (trauma/autarky/trophy/default/dilemma/devil), `-j2`,
`--judge zig`, running alongside everything else tonight. **`swarmChild=4`** (up from the current 3)
scored 17/24 = 70.8% vs the 50.0% baseline on this subset and got `KEPT`.

**Validated on the full 8-map `CORE_PANEL`** (isolated, only this one parameter changed from the
shipped default): **53.1% (17W-15L)**, up from 50.0%. Per-map: Trophy 50%->75%, Default unchanged
75%, Slithery Fight 0%->25%, Schooltime 25%->50% -- but **Autarky dropped 50%->0%**, the same kind
of single-map swing every other flat parameter change showed tonight. Net positive, and unlike
`wProbeDanger`/`exploreValueDensityFactor` this one is a real net gain on the full panel, not a net
loss -- but the Autarky regression means this needs the same "don't trust one 32-game sample"
caution as everything else tonight. Per the user's standing instruction (submit anything that clears
52.5% against `viper_v7.12`/`Y.7.12-nn.1`, but always reactivate the current champion afterward), this
clears the bar -- but given how consistently every flat weight tonight has shown large single-map
noise at n=4/map, ran an SPRT confirmation first (`--p0 0.5 --p1 0.6`, full panel) before actually
submitting, rather than act on the 32-game number alone. Result below once it completes.

**SPRT result: reject, 47.5% over 99 games -- essentially a coin flip, not a real gain.** Confirms
the caution was right: the 53.1%/32-game panel result and the 70.8%/24-game param_search signal that
found it were both noise. **Not shipped, not submitted.** This is now the fourth flat single-
parameter tweak this session (`wProbeDanger`, `exploreValueDensityFactor`, and now `swarmChild=4`)
that looked promising on a 24-32-game sample and did not hold up under a properly-powered test --
a strong, repeated pattern by now, not a one-off. Read as further confirmation that continued
single-parameter coordinate-descent search is running low on genuine signal at the current baseline;
the bigger, structural ideas (articulation-point chamber analysis, the phase-based consolidation
controller) are increasingly the better use of further effort than another weight sweep.

## Articulation-point-lite chamber check: implemented, tested, no clear benefit

Implemented the leading untested Slithery Fight hypothesis from earlier tonight (and from research
much earlier this session): `Params::chamberCheck` (off by default) + `Policy::chamberBeyond()` --
`trySplit()`'s swarm-bud `bareExit` check (V7.12's own "just needs one free neighbour" gate, no
flood-fill at all) now optionally walks forward through any true corridor (exactly one way onward)
up to 12 tiles, then flood-fills from wherever it actually opens up or dead-ends, instead of trusting
the first free cell blindly. In open space this adds nothing (the walk terminates after 0 steps,
identical to plain `bareExit`) -- it only differs in a genuine narrow-corridor case, deliberately
scoped this way after an earlier, different room-check tightening on this same path (`hasMinRoom`,
2026-09-29) made Trauma *worse* by over-rejecting routine splits. Verified: compiles clean, zero
regression with the gate off (identical dilemma/trophy death counts again).

**A/B result on Slithery Fight specifically (the map this was built for): 0W-2L, our deaths
607/619** -- essentially identical to every prior baseline (567-688 range across the whole session).
**No improvement at all on the exact failure mode this was designed to fix.** This is a real,
informative negative result, not just noise: the corridor-detection mechanism doesn't appear to be
what's actually driving the spiral. Either (a) the spiral isn't primarily caused by a bad *split*
decision at all (the death cause is "hit a wall" during ordinary movement, which a split-time gate
can't touch), or (b) the specific corridor shape on this map doesn't match what `chamberBeyond()`
detects (e.g. the "trap" might be a wide-but-still-sealable area, not a narrow corridor a 1-exit walk
would catch). Full 8-map panel run in progress to check for collateral effects elsewhere before
closing this out; if that's also neutral, the leading Slithery Fight hypothesis this session has
carried since the wall/kelp-density correction should be considered refuted, not just untested, and
the next step is a fresh `BC_DEBUG` trace of the actual round-360-410 collapse window -- the one
concrete diagnostic step for this specific map that, unlike Trophy's, still hasn't actually been run.

**Full-panel result: 53.1% (17W-15L), but not a real win.** Checked per-map before trusting the
headline number (the session's own repeated lesson by now): every map matches the 50.0% baseline
exactly *except* Slithery Fight, which went from 0/4 to 1/4 -- **the entire "improvement" is one
single game flipping from a loss to a win**, on the exact map the isolated 2-game smoke test just
showed *no* improvement on (607/619 deaths, identical to baseline). This is consistent with ordinary
pearl-seed variance, not a systematic effect. **Not shipped.** `chamberCheck` stays off by default;
the corridor-detection hypothesis for Slithery Fight is refuted by tonight's evidence, not confirmed.

## The actual Slithery Fight BC_DEBUG trace, finally run -- a real, different lead

Ran the trace repeatedly recommended and never done: a reproducible local Slithery Fight loss
(seed 1000, `viper_v7.12` vs our `--debug`-enabled build) with full log capture via the Zig judge's
now-fixed `--debug 3`. Two findings, neither matching the standing hypothesis:

**1. The death rate does not spike at round 360-410 in this local game.** Bucketed by 50-round
window: 51, 140, 138, 144, **178, 159**, 142, 128, 118, 94 (round 0 to 499) -- it peaks at round
200-299 and *declines* steadily afterward, the opposite of the ladder-replay-derived "collapse
window." The specific round-360-410 characterization was measured on real ladder losses against
different opponents (Rogo/RustyHamsters/UnderTheC); it may be opponent-specific and doesn't
reproduce against `viper_v7.12` locally. Total deaths (1292 across both sides over 500 rounds) are
still catastrophic either way -- the underlying pathology is real, just not concentrated where the
ladder data suggested.

**2. The actual mechanism, found by reading `dragonLog` text around real deaths**: dragons get
completely sealed by static kelp -- e.g. `id317`: `r200 reverse` (a defensive split, correctly
detecting it was boxed in) -> `r201 cramped` -> `r202 trapped N:kelp E:kelp S:kelp W:neck` (every
direction blocked: three kelp walls plus its own neck). **472 separate "trapped, every direction
kelp-or-neck" log lines occur across this one game** -- some starting as early as round 2-4, hitting
freshly-spawned length-2 dragons directly. This is a real, literal dead-end: on a map with 514 kelp
edges among 3402, some cells apparently have only one non-kelp neighbor, and once a dragon's own
neck occupies that one neighbor, every remaining direction is a wall.

**Crucially, this is not the split-placement failure `chamberCheck` targets.** Tracing `id317`
specifically: the "boxed in" reverse-split at round 200 was a *reasonable* decision (bareExit's
neighbour existed at that moment) -- the seal happened two ordinary movement turns *later*, as the
dragon (and the shrinking space around it) continued to move. `chamberCheck` only gates the
one-time split decision; it can't fix a trap that develops over several turns of otherwise-normal
movement afterward. This also explains why the chamberCheck A/B test found nothing: it was never
going to touch this failure mode.

**Also found, worth flagging even though this trace is a single game and needs a same-protocol
symmetry check before trusting fully**: all 6 early (round <=10) kelp-trapped dragons in this
specific game belonged to **team 1 (us, side B)** -- team 0's (`viper_v7.12`'s) early splits in the
same window show no matching pattern. This contradicts the earlier "both sides show identical
pathology" finding from the emergency-split isolation test, which measured *overall* death totals by
round 500, not *who specifically* falls into an early kelp trap. If this asymmetry holds up across
more games, it reframes Slithery Fight from "an unfixable, symmetric map hazard neither bot can
help" into something at least partially attributable to our own bot's behavior -- worth checking
whether our normal per-turn safety check (`scoreFrom`'s `space >= need` flood-fill veto) is somehow
less effective at detecting an encroaching kelp pocket than a bareExit/split-time check would be, or
whether it's purely which starting cells happen to be assigned to which team.

**Recommended next steps, in order**: (1) check 2-3 more Slithery Fight games (different seeds/sides)
to see if the team-1-specific early-trap pattern holds or was a one-game fluke; (2) if it holds,
trace exactly why `scoreFrom`'s existing per-move flood-fill veto (`space >= need`) doesn't prevent
walking into a pocket that's about to seal -- the `need` threshold is based on the dragon's *current*
length, but if the pocket keeps shrinking turn over turn (kelp is static, so this must mean the
dragon's own body or another dragon's body is what's actually closing off the space) the veto may be
comparing against a stale room estimate; (3) this is a fundamentally different, likely more
promising, lead than the articulation-point/corridor theory this session carried all along, which
tonight's evidence has now retired.

**Symmetry check run, and it held**: repeated the trace with sides swapped (our bot as A this time,
same seed 1000). Result: early (round<=10) kelp-traps again hit **only our bot's team** (team 0 = A
this time) -- not both sides, and not tied to a fixed board position. **This rules out "unfixable
map hazard" and "which side spawns where" as explanations -- something in our own bot's behavior,
not the map alone, causes this.**

**wCompass isolation test run (the natural next hypothesis, given its own documented history of
causing "commits to a corridor that boxes it in" on Trauma): ruled out.** Same seed/side as the
first trace, `wCompass=0`: **byte-identical result** -- 670/622 deaths (exactly matching the
original with `wCompass` on) and exactly 472 trapped-with-kelp log lines, unchanged. Either
`wCompass` isn't the cause, or it never actually activated in this scenario at all (the identical-
to-the-exact-number result suggests the latter -- plausibly no bed ever crossed the `hotObs`/
`hotRate` threshold to register as "hot" in this particular game, so the term had nothing to pull
toward either way). Either way, `wCompass` is not a productive lead here.

**Status at the end of tonight's investigation**: three hypotheses tested and refuted
(articulation-point/split-placement, the round-360-410 timing characterization, `wCompass`). One
solid, confirmed fact remains: **the early kelp-trap pattern is specific to our bot's own behavior,
reproducible across both side assignments, not a symmetric map hazard.** The actual cause is still
open. Next candidates, not yet tried: (1) the per-move `scoreFrom` safety veto (`space >= need`)
itself -- does it correctly account for a pocket that's shrinking because of the dragon's *own*
growing body, not just static kelp; (2) whatever routine foraging/targeting logic chooses a
direction to move in open play (not split-related) might be the one steering into these pockets in
the first place, before any split or safety check ever gets a say -- worth tracing the moves
*leading up to* a trap (not just the trap itself) on the next attempt.

## Map profile + complementary-team analysis (2026-09-30, next morning)

**Our real per-map profile**, from 35 actual ladder games vs 3 top opponents (Rogo/RustyHamsters/
UnderTheC, `ladder/loss_analysis_rogo_rustyhamsters_underthec/results.json`): **Schooltime,
Slithery Fight, Trauma, Trophy are all 0%**; Autarky/Default/Dilemma 25%; Portals 33%; Devil 50%;
Queen of Spades 67% (best). This is the clearest, most decision-useful ranking of map weakness the
session has produced -- prioritize fixes in this order.

**Complementary team found**: screened all 15 top-rated teams already scouted in `ladder/scout/`
for who is strong exactly on our worst maps. **`Sabotage-d`** (teamId 46, elo ~2000, IIT Kharagpur)
and `SSS` (teamId 91) both go **4/4 on Schooltime** specifically (our single worst map) and 5/6
across the weak-map set. Picked `Sabotage-d` (ranked; `SSS` currently has ranked off).

**Their pattern, from real replays already downloaded** (`ladder/scout/46/`): splits aggressively
from round 0 (multiple simultaneous splits at round 0, vs our later/gated first bud) -- an
early-committed swarm, not grow-then-split. Wins Slithery Fight/Schooltime via the **longest single
dragon**, not raw population: one traced game, their side won with only 5 dragons (longest 66)
against the opponent's 21 dragons (longest 51). Directly confirms the standing "small,
early-committed core beats mass population" hypothesis (§idea-list, "top teams win with small,
early-committed cores rather than a late mass-feed collapse"). Not immune to the kelp-death spiral
either -- 388 wall-deaths in one Slithery Fight win (vs the loser's 724) -- they suffer
proportionally less of it while committing harder to one long dragon, not by avoiding the trap.

**Live battle run against them**: found first that the currently *active* ladder submission is not
this session's S4.7 work at all -- a teammate runs a separate `Y.7.12.13` "maintenance build"
lineage in parallel (different account uploading), plus an unrelated teammate submission
coincidentally named close to tonight's "probe echo" feature (not something this session did).
Since S4.7 hasn't cleared the promotion gate, used the currently-active build for a real unranked
challenge rather than submit unproven work. **Result: 0/25 sub-games (clean sweep loss) on
Schooltime/Slithery Fight/Trauma/Trophy/Autarky.** `bceval` shape: **4 of 5 are `early` collapses**
(round 39-99, before the game is 20% done), only Slithery Fight is `late` (round 359, consistent
with the earlier local BC_DEBUG trace finding a death-rate peak at round 200-300, not 360-410).

**Conclusion**: this isn't an S4.7-specific weakness -- the whole team's current active lineage
loses to `Sabotage-d` the same way, via an early-game tempo deficit. `Sabotage-d`'s round-0
multi-way splitting is a real, learnable, well-evidenced edge, and it lines up exactly with this
session's own strongest meta-finding (population lead from round 100 decides most games). **This is
now the single best-evidenced concrete next mechanism to try**: an earlier, more aggressive opening
split policy (closer to "split immediately and often from round 0" than the current gated
`swarmSplitLen=4`/`growRound=300` timing), tested specifically against the maps this data covers.

## S4.8: a combined structural rehaul, built from the priority list (2026-09-30 morning)

Built `viper_vS4.8` (seeded from `viper_vS4.7`, snapshotted as `baselines/S4.8`) with four changes
**on by default** (deliberately not gated at 0 -- this is meant to test the combined effect, not sit
dormant), each targeting a specific finding from tonight's investigation:

1. **Aggressive early split** (`earlySplitRound`=60, `earlySwarmChild`=4): from the `Sabotage-d`
   analysis. Caught a real bug before shipping it: `swarmSplitLen` is already at the physical floor
   (4 -- both split halves need >=2 segments), so a *lower length gate* is impossible. The actual
   lever is a bigger child once a dragon does grow past the floor, accelerating population growth
   during the opening instead of trying to split earlier than physically possible.
2. **Local nearest-unexplored-bed pull** (`wExploreBed`=0.4, `Policy::exploreTarget_`): root-cause
   fix for the Trophy blind-forage bug, reusing `wCompass`'s own BFS/room-factor machinery but
   targeting the nearest never-seen known bed specifically, instead of `exploreValueDensityFactor`'s
   flat global constant (which net-regressed the panel earlier tonight).
3. **Id-based queen tie-break** (`world.hpp`'s `knownQueenSender`): idea-list #2 -- on an exact
   length tie between two candidates, both dragons independently believing they're the queen (since
   neither's claim is ever strictly longer) now converges on the lower sender id instead.
4. **Staggered growth-phase transition** (`growWindow`=40): applies the same anti-synchronisation
   staggering already proven for `feedRound`/`feedWindow` to the `growRound` EXPANSION->CONSOLIDATION
   switch, which was previously a single global round flipping every eligible dragon's role at once.

Verified: real wasm compiles clean on the first attempt, no CPU blowup (peak 63.2M, within budget),
and a same-seed spot check shows genuinely different behavior from the S4.7 baseline (different
round counts: Dilemma 123/198 vs the baseline's 79/115) -- confirming the changes are live, not
accidentally inert. Full `CORE_PANEL` A/B running now; result below once it completes.

**Full-panel result: 59.4% (19W-13L), +9.4pp over the 50.0% baseline** -- and unlike every single-
feature test tonight (which each moved at most one map, usually with an offsetting regression
elsewhere), **three maps improved together**: Trophy 50%->75% (`wExploreBed`'s direct target),
**Slithery Fight 0%->50%**, **Schooltime 25%->50%** -- our two historically worst maps, both moving
at once. Only Autarky regressed (50%->25%). `bceval` shape adds real texture: Schooltime now shows
a `dominant` win for the first time all session (not just `recovered`), and Slithery Fight shows
`late`/`recovered` shapes instead of blind losses -- consistent with the earlier local trace finding
that this map's death rate peaks around round 200-300 and declines after, not a hopeless spiral the
whole game.

**Not trusting this yet** -- same discipline as every other result tonight, especially given how
good it looks. SPRT confirmation running on the full panel now (`--p0 0.5 --p1 0.6`). Autarky's
regression also needs an isolation pass to see which of the four bundled changes caused it, once/if
the combined result holds up.

# ======================================================================
# POST-MORTEM: what we have been doing wrong (2026-09-30, Opus analysis)
# ======================================================================

A systematic audit of the S4.7.4 -> S4.8 lineage, all 1103 logged decisive games, and 128 replays
with final-state data. **Several conclusions recorded earlier in this file are wrong and are
corrected here.** Read this section before trusting anything above it.

## 1. We optimised the wrong objective, with the wrong sign

Across 1103 logged games:
- when we had **fewer** deaths than the opponent: **20%** win rate (n=785)
- when we had **more** deaths than the opponent: **84%** win rate (n=295)

Deaths are *positively* associated with winning, because dying is how mass is converted (feeding the
queen) and how an aggressive swarm trades. The founding premise of the whole S4.7 rewrite --
"93% of S4.6's deaths are self-inflicted DOOMED traps, so fix safety" -- optimised a metric whose
sign is backwards. Every safety/death-reduction feature built since (wTerritory, wChoke, wPocket
tuning, chamberCheck, wProbeDanger, the entire kelp-trap investigation) was pushing the wrong way or
at best sideways, which is exactly why none of them produced a validated gain.

The repeated puzzled note in this file -- "our deaths are consistently lower than the opponent's yet
we still lose" -- was never a puzzle. It was the answer, misread as a mystery.

## 2. The real objective is concentration, and it is a perfect predictor

From 128 replays with final-state data:
- we had more **units**: 72% win rate (n=86)
- we had more **total length**: 74% win rate (n=84)
- we had the **longer single dragon**: **100% win rate (65/65)**

36% of all games are decided by the round-500 longest-dragon tiebreak, and we win only 23% of those
(vs 46% of eliminations). In the S4.8 tiebreak games our median was **40 units / 214 total length /
longest 20**, against the opponent's **9 units / 83 total / longest 18**. We hold 4.4x their
population and 2.6x their total mass and still lose, because they concentrate it:
concentration ratio (longest/total) in games we lose is **0.071 ours vs 0.173 theirs** -- they are
2.4x better at turning mass into the one number that scores.

Worst cases are unambiguous: `schooltime_1017_B` -- us 61 units / 354 total / longest 22, them 4
units / 84 total / longest 35. Four times the mass, lost on the tiebreak.

**We are winning the resource game decisively and losing the scoring game.** Population is already
won (no headroom left: median 40 vs 9). Concentration is untouched.

Note S4.8's headline feature (`earlySwarmChild`=4, split more aggressively) pushes concentration
*down*. It is mechanistically aimed away from the actual bottleneck.

## 3. Our measurement protocol cannot detect what we were testing

The 32-game fixed-seed CORE_PANEL has a ~7pp optimism bias when used as a selection criterion, twice
measured:
- `swarmChild=4`: panel 53.1% -> SPRT 47.5% (99 games)
- `S4.8`:         panel 59.4% -> SPRT ~53%  (141 games, no verdict)

Mechanism: comparing S4.8 against the S4.7 baseline game by game, 27/32 games changed outcome or
detail, and **7 flipped L->W while 4 flipped W->L**. The "+3 net wins" headline is the residual of
~11 near-coin-flips. Most games sit on a decision boundary (500-round tiebreaks with near-equal death
counts), so any perturbation reshuffles them. A 32-game panel cannot separate "plays better" from
"landed differently", and we selected features *because* they looked good on it.

Therefore **every 32-game "confirmed gain" above is unvalidated**, including the applied
`wTarget=4`/`wPredict=0`/`swarmChild=3` "+9.4pp", which was validated by exactly this method.

Additionally, in 35% of panel games the opponent is wiped out entirely (0 units) -- those games carry
zero information about the tiebreak failure mode, shrinking the informative sample further.

## 4. We were measuring against the wrong opponent

`viper_v7.12` scores ~15% against the real 1700+ field (ml/results.md: 6/40). We score ~50% against
v7.12 and **22%** against the real field (35 ladder games), and 0/25 against Sabotage-d. So local
"50% vs v7.12" maps to roughly 22% real. The 52.5%-vs-v7.12 promotion bar therefore promotes builds
that are still ~22-25% on the ladder. We spent the session climbing a yardstick that does not reach
the target.

## 5. Diagnosis by anecdote, without base rates

The kelp-trap investigation (472 "fully sealed" log lines), Trophy's "41-round blind forage", the
`id317` trap trace -- all single-game anecdotes promoted to root causes without asking what the
*opponent's* equivalent number is. The one time it was checked (Sabotage-d: 388 wall-deaths in a game
they **won**, vs the loser's 724) the conclusion was recorded and then not drawn. Slithery Fight's
"600-700 death spiral" is normal for that map for both sides; it was never our specific bug.

## 6. Feature accumulation without deletion

Params grew 68 -> 93 across S4.7.4 -> S4.8; **inert (gated at 0/false) params grew 1 -> 11**, nine of
them added in one night and never shipped. `common.hpp` is 57% comments (198/349 lines), mostly
obituaries of failed experiments. Complexity is compounding while capability is flat.

## What to do instead (in order)

1. **Change the target metric.** Evaluate every change by the *concentration ratio* and final
   longest-dragon delta -- continuous, per-game, low-variance, and a 100% win predictor -- not by
   binary panel win-rate. A handful of games gives a usable signal on a continuous metric; 32 games
   gives noise on a binary one.
2. **Attack concentration directly.** We do not need more population (40 vs 9). We need one dragon
   that ends at 35+ instead of 20. That means feeding earlier and harder into a single committed core
   (their 4-9 dragons vs our 40 suggests they deliberately stop splitting and convert), not splitting
   more.
3. **Delete the 11 inert params** and the dead code behind them. They are pure carrying cost.
4. **Re-baseline honestly**: current build is ~50% vs a bot that is ~15% on the ladder, i.e. ~22%
   real. State that as the number, and set the bar against `Y.7.12-nn.1` (which is 60% real) or real
   ladder opponents, not v7.12.
5. **Stop the flat-weight search.** Five of five flat-parameter experiments failed under proper
   testing; param_search's remaining candidates sit on the same noise floor.

## S4.8 final verdict, and a validation of the post-mortem

`viper_vS4.8` SPRT, full panel, 150 games: **50.7% (76W-74L), LLR -2.656, inconclusive** (just short
of the reject bound). Against the 50.0% baseline this is **no improvement**.

The panel had said 59.4%. Truth is 50.7% -> **+8.7pp optimism bias**, a third independent measurement
matching the ~7pp derived from `swarmChild=4` and the probe experiments *before* this test finished.
The bias estimate is now reliable: **treat any 32-game panel figure as ~7-9pp optimistic whenever the
change was selected using that panel.**

This also validates the post-mortem's mechanism claim: S4.8 bundled four features, three orthogonal
to the concentration bottleneck and one (`earlySwarmChild`=4, split *more*) pointed away from it, so
"no effect" is the predicted outcome, not a surprise. The post-mortem called this before the result
landed -- the first prediction-then-confirmation of the session rather than an after-the-fact story.

**S4.8 is not shipped.** `baselines/S4.8` is kept as the record of the attempt.

## Concentration work: the measurement tool, and S4.9's useful refutation

Built `tools/concentration.py` -- reports longest-dragon delta and concentration ratio
(longest/total) per replay, the metrics the POST-MORTEM identified as the real decision variables.
Baseline measurement, `viper_vS4.7` vs `viper_v7.12`, 32 games:

| build | our longest | their longest | our conc | their conc |
|---|---|---|---|---|
| S4.7 baseline | 5.5 | 12.0 | 0.062 | 0.130 |
| S4.8 | 7.0 | 11.0 | 0.069 | 0.122 |
| S4.9 (`splitStopRound`=250) | 5.0 | -- | 0.052 | -- |

Deeper measurement: **our average dragon is 3.98 long against the opponent's 8.40** (39 units vs 10).
With `swarmSplitLen=4` at the physical floor, every dragon sheds a child the moment it reaches 4.

**S4.9 tested the obvious implication -- stop splitting from round 250 so dragons can grow -- and it
is refuted.** Our longest went 5.5 -> 5.0 (no growth) and win rate 50% -> 40.6%. Dragons given 250
free rounds to grow still ended at ~5. **Splitting was never what kept them short.**

That leaves one explanation, which the data already supported: **we end with MORE total mass than the
opponent (median total length 214 vs 83) yet our longest is 6 vs their 17.5. This is a mass-TRANSFER
failure, not a production or splitting failure.** Feeding is the transfer mechanism, so feeding is
the bottleneck.

**Root cause found in `Policy::decide()`'s feed block: a priority inversion.** The feeder scanned
*visible* teammates first and used the gossiped global queen only as a fallback when no visible
teammate qualified. With ~39 dragons alive, nearly every feeder finds some local teammate
`feedMargin` longer than itself, so mass pools into dozens of local semi-queens instead of the one
dragon that actually scores. The opponent's ~10 dragons have few local alternatives, so their feeds
converge on one queen by default -- which is exactly the 2.4x concentration gap.

`viper_vS4.10` inverts that priority (global gossiped queen first, visible teammate as fallback) as a
single-variable change, to be measured on `tools/concentration.py`, not win rate.

**Methodology note**: `concentration.py`'s medians include eliminated teams as `longest=0`, which
distorts cross-build comparison (S4.9 appeared to drop the *opponent's* longest from 12 to 4, which
is impossible -- same opponent bot). Use the per-game rows and the tiebreak-only subset it prints for
real comparisons, not the raw median line. Caught this before drawing a conclusion from it.

## CORRECTION to the POST-MORTEM's magnitudes (same error it warns about)

The POST-MORTEM above quotes "our longest 6 vs their 17.5", "average dragon 3.98 vs 8.40" and a
"2.4x concentration gap". **Those magnitudes are inflated by counting eliminated teams as zeros.**
`concentration.py` now restricts to the tiebreak subset (both sides alive, and the games actually
decided on length), which gives the honest picture:

| build | our longest | their longest | our conc | their conc | we were longer |
|---|---|---|---|---|---|
| S4.7 baseline | 17.0 | 19.0 | 0.189 | 0.240 | 4/15 |
| S4.8 | 19.5 | 18.5 | 0.113 | 0.232 | 6/16 |
| S4.9 (`splitStopRound`) | 15.5 | 25.0 | 0.098 | 0.197 | 1/10 |

So the real deficit is **17 vs 19 longest, ~0.19 vs ~0.24 concentration** -- we lose length tiebreaks
by a *small* margin, not a 3x one. That is better news (small gains could flip several games) and it
also means the mechanism story needs less drama than the POST-MORTEM gave it.

What survives unchanged: longest-dragon is the decision variable and we are behind on it; deaths are
the wrong objective (that used all 1103 games, unaffected); the ~7-9pp panel optimism bias (measured
three times on win rates, unaffected); v7.12 is the wrong yardstick.
What is corrected: the *size* of the concentration gap, and with it the claim that population is
"already won with no headroom" -- S4.9's failure plus these numbers suggest population and length are
closer to a genuine trade-off than a free win.

**This is the same error the POST-MORTEM was written to catch (a median over a contaminated
population), made inside the POST-MORTEM itself.** Recorded rather than quietly fixed, because the
pattern -- trusting an aggregate before checking what is in it -- is the actual recurring failure.

# ======================================================================
# THE GAME IS DECIDED BY ROUND 50 (2026-09-30, the real headline)
# ======================================================================

Prompted by the user's hypothesis that population growth and elimination are linked. Reconstructed
per-round unit counts for both teams from 128 replays (`tools/tempo.py`). **Our population edge at
round 50 predicts the result almost deterministically:**

| our pop edge @ round 50 | n | win rate |
|---|---|---|
| behind by 5+ | 31 | 23% |
| behind 1-4 | 30 | 27% |
| ahead 0-4 | 46 | 63% |
| **ahead 5+** | 21 | **100%** |

And it ranks the maps in almost exactly win-rate order:

| map | edge@50 | edge@100 | win rate |
|---|---|---|---|
| devil | +5.0 | +20.5 | 100% |
| dilemma | +3.5 | +7.0 | 100% |
| default | +0.5 | +8.0 | 69% |
| trophy | +2.0 | +6.0 | 56% |
| autarky | -2.0 | -6.5 | 31% |
| schooltime | -7.0 | -33.0 | 25% |
| slithery_fight | -12.5 | -19.0 | 25% |
| trauma | -2.0 | -4.0 | 0% |

Per-game trajectories make the mechanism plain. Wins are runaway expansions (`default_1000_A`:
5v2 -> 18v4 -> 40v4 -> 63v5, elimination follows automatically). Losses are races lost by round 50 and
never recovered (`trauma`: **stuck at 4-11 units for 300 rounds** while the opponent reaches 32;
`schooltime`: opponent hits the 64-unit cap by round 100 while we sit at 11-27; `slithery_fight`:
behind 28v42 from round 50 in all four games).

**This retires the "Slithery Fight death spiral" story entirely.** It was never a spiral or a kelp
bug: we lose the early population race, both sides then cap at 64, and the game goes to a length
tiebreak we lose narrowly. The 600-700 death counts are normal for that map for both sides.

**And it explains why nothing this session worked.** Every change tried -- probe echoes, chamber
checks, `splitStopRound`, `wProbeDanger`, feed priority, `growWindow`, `wExploreBed`, the entire
concentration thesis -- operates at or after mid-game, i.e. downstream of a race already decided.
The only change that ever produced a validated gain in this project's history (`wCompass`, +8.3pp) was
an early-game eating-rate fix. The one external data point (Sabotage-d splitting from round 0) pointed
at round 0 too. We spent the session optimising rounds 250-500 of a game settled by round 50.

## Consequences for how to work

1. **Optimise population tempo in rounds 0-50.** The causal chain is eating rate -> length 4 -> split
   -> more heads -> more eating. On dense maps it cascades and we win 100%; on sparse/contested maps
   (trauma, autarky, schooltime, slithery) it stalls and we lose.
2. **Use `tools/tempo.py`, not win rate.** Edge@50 is continuous, low-variance, visible 50 rounds into
   a 500-round game, and near-deterministic for the outcome. A handful of games gives a signal where
   binary win rate needs 100+ and still carries ~7-9pp selection bias.
3. **Retire flat-weight search.** `param_search_v2` ran ~8 hours and several hundred games for two
   keeps: `swarmChild=4` (SPRT-disproved at 47.5%) and `feedMargin=8` (unvalidated). Zero validated
   gains.
4. First tempo experiment: **`swarmChild` 3 -> 2** (`viper_vS4.11`). `n = min(swarmChild, L-2)`, so at
   the L=4 floor both shed a 2-child, but from L=5 up `swarmChild=3` leaves the parent at 2 while
   `2` leaves it at 3 -- one pearl from splitting again. Smaller children compound faster, which is
   V7.12's own "constant length-2 child" design and plausibly why it out-expands us 2x early on
   exactly the maps we lose.

## Results of the two mid-game experiments, both as the round-50 thesis predicts

**S4.9 (`splitStopRound`=250, stop budding late so dragons grow): 40.6%, refuted.** Our longest went
5.5 -> 5.0 and the tiebreak-subset longest 17.0 -> 15.5. Giving dragons 250 free rounds to grow did
not make them grow, which is what killed the "splitting keeps them short" hypothesis and pointed at
transfer instead.

**S4.10 (feed the gossiped global queen first, visible teammate only as fallback): 53.1% (17W-15L),
noise-level.** Per-map the only moves were autarky 50%->25%, slithery 0%->25%, schooltime 25%->50%,
i.e. +1 net win -- the same ~11-coin-flip reshuffle every change produces. `concentration.py` did show
the mechanism working (`conc` reaching 1.000 in some tiebreak games: the whole team feeds one dragon,
leaving a single unit holding all the length) -- so the change did what it was designed to do and it
still did not matter.

**Both are feed/late-phase changes, and both landed at noise level -- predicted in advance by the
round-50 finding.** That is now three predictions confirmed (S4.8 ~50.7%, S4.9 refuted, S4.10 noise)
from the same model, which is the first time anything in this project has predicted results rather
than explained them afterwards.

## S4.11 (`swarmChild` 3->2): null on tempo too, and the reason is instructive

Result: **43.8% (14W-18L)**, and -- more informative -- **null on the tempo metric as well**:

| build | r25 | r50 | r100 | r150 |
|---|---|---|---|---|
| S4.7 baseline | 7.0 (-0.5) | 10.5 (+0.0) | 17.5 (-3.0) | 20.0 (-7.0) |
| S4.11 (`swarmChild`=2) | 6.0 (+0.0) | 10.0 (-0.5) | 15.0 (-0.5) | 18.0 (-5.0) |

**My mechanistic argument for this change was wrong, and wrong in a checkable way.** I reasoned
"smaller child -> parent keeps more length -> reaches 4 and splits again sooner -> faster compounding".
That is half the story: the child is correspondingly *shorter*, so it takes longer to reach 4. A split
of a length-L dragon produces two dragons and total length L either way -- **`swarmChild` changes
neither the number of splits nor the total length, only how length is distributed between parent and
child.** It is mechanically incapable of moving population count, so a null result was the correct
prediction and I should have derived it before spending a test on it.

**This does not weaken the round-50 thesis -- it sharpens it.** The thesis says population tempo
decides games; it does not say every split-related knob affects tempo. `swarmChild` provably cannot.
The levers that *can* are the ones that change **how fast a dragon reaches length 4**, i.e. eating
rate: `wTarget`, `gamma`, `wCompass`, `exploreValue`, and any safety weight timid enough to make
dragons decline contested early pearls. That is the untested space, and it is where `wCompass` (the
only validated gain in project history, +8.3pp) already lives.

Useful negative result for the next session: **before testing a knob, check whether it can move the
target quantity at all.** Four of this session's experiments (S4.8's `earlySwarmChild`, S4.9, S4.10,
S4.11) were nulls that a few minutes of mechanism-checking would have predicted.

# ======================================================================
# TRAUMA, DIAGNOSED PROPERLY (2026-09-30, the session after the round-50 headline)
# ======================================================================

Took the handoff's step 1 -- trace trauma's early game and let the answer pick the lever, instead
of guessing at weights. Three findings hold up, three hypotheses were falsified (two of them mine,
both by a test specified in advance), and there is **one correction to the handoff itself**.

Tooling: a debug build (`#define BC_DEBUG`) plus new per-turn log fields for `hot_` composition
(`hot`, `fast`, `fdist`) and a full per-direction score decomposition (`expl/bel/tgt/hotSum/
hotMax/comp`). The instrumentation patch is the part worth keeping and lives in
`viper_vS4.12_decomp/` (policy.hpp's `dbgComp[4]` + main.cpp's log line) -- copy that pair into any
build to get the same trace. `#define BC_DEBUG` goes in as line 2 of `common.hpp`, and remember the
build cache keys on `main.cpp` only, so append a rebuild-marker line after editing any header.

Dirs from this session, all kept (each is a one-line edit on top of the previous, and every result is
recorded below, so they can be deleted freely once this section has been read):
`viper_vS4.12` (the consensus fix -- the only one worth keeping as code),
`viper_vS4.13` (+ steady-state bed belief, null),
`viper_vS4.12_decomp` (the score-decomposition instrumentation -- the reusable part),
`viper_vS4.14_dbg` (+ `exploreValue` 0.01, falsified),
`viper_vS4.15_dbg` (+ `wHot` sum -> max, falsified),
`viper_vS4.7_nocompass2` (`wCompass=0`, the inertness proof),
`viper_vS4.7_dbgr50` / `viper_vS4.12_dbg` / `viper_vS4.13_dbg` (debug variants).
`baselines/S4.7-ref` is a snapshot of the `viper_vS4.7` reference taken before any of this.
Replay batches: `ladder/diag_r50` (baseline, 6 maps x 2 seeds), `ladder/s412_panel` (S4.12, full
32-game panel), `ladder/nocompass` (the wCompass=0 batch), plus the single-game `ladder/diag_*` dirs.

## CORRECTION to the handoff: trauma is not an early-race loss

The handoff says to target trauma first because it is 0% win. But trauma's edge@50 is **-2.0** --
the same as autarky's -1.5, which wins 50%. The tempo table reproduces exactly (devil +5.0/100%,
dilemma +4.5/100%, schooltime -7.0/25%, slithery -13.0/25%, trauma -2.0/0%, autarky -1.5/50%), so
the table is right and the inference drawn from it was wrong. **trauma is the one map that breaks
the edge@50 correlation**, which makes it the worst available place to test the round-50 thesis.

The unit trajectories say why (4 games, `viper_vS4.7` vs `viper_v7.12`; we are the first row):

```
trauma_1000_A   r0:2  r50:4  r100:11  r150:11  r200:10  r250:5  r300:3  r400:4  r450:2
   (v7.12)          2     4       6        6       18     31      32      38      32
trauma_1017_A   r0:2  r50:4  r100:6   r150:7   r200:6   r250:7  r300:6  r400:4  r450:2
   (v7.12)          2     8      12       22       32      35      31      29      23
```

Both sides sit at 4 units through rounds 50-100 -- in `1000_A` **we are ahead 11-6 at round 100** --
and then v7.12 takes off to 30-40 while we decay to 2-7. **The divergence is rounds 150-250.**
trauma is a mid-game failure to start compounding, not a lost early race. The causal chain the
round-50 thesis names (eating rate -> length 4 -> split -> more heads) is still the right chain; on
this map it simply runs ~150 rounds later than the thesis's window.

**The maps where edge@50 really is the deciding variable are slithery_fight (-13.0) and schooltime
(-7.0)**, where the early deficit is 6x larger. Those, not trauma, are where the round-50 thesis
should be attacked.

## Finding 1: on trauma we eat literally nothing, and not for any of the obvious reasons

Rounds 0-50, 4 games, both sides (so not a spawn artifact): **we eat 0 pearls, v7.12 eats 7.**
Every dragon is length 2 for 198 of 200 dragon-turns, never splits, 4 units at round 50.

Ruled out with base rates rather than anecdote:
- **not safety** -- `why=cramped` is ~1% of dragon-turns, and no direction is ever score-vetoed
  (a vetoed direction would log ~-993; none ever does).
- **not exploration** -- we visit *more* distinct tiles than v7.12 (162 vs 137) and travel exactly
  as far (max 21 manhattan from spawn, both sides).
- **not scarcity** -- 42 pearls appeared in rounds 0-50 and **35 were still sitting there at r50**.

Trauma's economy: of 1152 tiles, **12 have `minGap=maxGap=1`** (a pearl every single round) and 130
have gap 1..200 (rate 0.00995, worthless). The 12 sit in two clusters: `x=35..36` (enemy side) and a
vertical column `x=11, y=10..14` plus `(12,14)` on ours.

Note the long-standing comment in `buildTargets` claiming "130 of trauma's 142 beds have rate
~0.0995, just under the 0.1 default" is **off by 10x** -- the real rate is 0.00995. So the `certain`
override it justifies is admitting 130 near-worthless beds into `hot_`, not 130 marginal ones.

## Finding 2 (fixed in `viper_vS4.12`): the map is unidentified for ~30 rounds, so `hot_` is EMPTY

`hot=0` for the first ~30 rounds of every trauma game, and for half the dragons all game. With
`hot_` empty there is no directional pull toward food at all and **every legal direction scores a
flat `N=1 E=1 S=1 W=1`** -- the dragon moves by tie-break order, nothing else.

Cause: **trauma and stronghold are the only two 48x24 maps and their four spawn positions are
byte-identical**, so `filterBySpawn`'s round-0 fast path cannot separate them; only 268 of 2304
edges differ, so a dragon has to wander into a differing edge before the pair resolves.

The knowledge was in hand the whole time: the two candidates **agree on all 12 fountains** and on
844 of 1152 tile specs. The old code withheld every bit of it purely because a second candidate had
not yet been eliminated.

`viper_vS4.12` adds `KnownMapMatcher::applyConsensus()`: apply every bed/gap fact all *surviving*
candidates agree on. Safe by construction (a fact every candidate asserts cannot be wrong if the
true map is among them), and beds-only -- kelp edges stay vision-only, because a wrong edge is the
dangerous kind and would only buy fewer deaths, which the post-mortem showed is the wrong objective.

Verified firing: **`hot=22 fast=12 fdist=7..18` from round 0** instead of `hot=0`, scores gain real
spread (`N=8 S=7 W=8`), CPU unchanged (63.8M peak vs 63.9M). Only the 48x24 pair is affected -- the
32x16 group (devil/dilemma/portals) has differing spawns and no agreed fountains, and every other
map has a unique size and resolves at round 0 already.

**Result: null, with unusual clarity.** 32-game panel, `tempo.py`:

| build | r25 | r50 | r100 | r150 | win |
|---|---|---|---|---|---|
| S4.7 baseline | 7.0 (-0.5) | 10.5 (+0.0) | 17.5 (-3.0) | 20.0 (-7.0) | 50% |
| S4.12 | 7.0 (-0.5) | 10.5 (+0.0) | 17.5 (-3.0) | 20.0 (-7.0) | 53% |

Identical on every checkpoint, and per-map edge@50 matches on all eight maps (autarky -1.5,
default +1.0, devil +5.0, dilemma +4.5, schooltime -7.0, slithery -13.0, trauma -2.0, trophy +3.0).
The 50% -> 53% is the usual ~1 net game of panel noise.
**This null was predicted in writing before the run**, on the grounds that the new knowledge could
only reach the value function through a channel too weak to act on. Keep the fix -- it removes 30
genuinely blind rounds and is strictly more information -- but it is a prerequisite, not a gain.

## Finding 3: `wTarget` is structurally blind to known pearl beds

`Policy::targets_` feeds the heavily weighted commitment term `wTarget * bestTargetV`
(`wTarget=4.0`). A cell enters that list on `belief > 0.02`, `countdown >= 0`, or being never-seen.
For a known-but-unseen bed:
- `World::belief()` returns **0** -- it needs `seenPearl` (vision) or `lastSpawn` (an observed spawn);
- `next[c]` (the countdown) is set **only** from vision (`next[c] = v.pearlIn` in `observe()`).

So a known fountain nobody has personally looked at is invisible to `wTarget` entirely, and all map
knowledge must squeeze through `wHot`. Measured directly: `tgt=0.000000 bel=0.000000` on every early
trauma turn.

`viper_vS4.13` gave certain beds their steady-state occupancy (`min(1, sinceKnownEmpty/meanGap)`) so
they enter `targets_`. Mechanically correct, and it fires -- but **trauma r0-50 eats went 0 -> 1.**
Effectively null.

## Falsified hypothesis A (mine): "the explore field dominates"

Predicted that `exploreValue` summed over hundreds of never-seen cells was swamping the food signal.
Probe: `exploreValue` 0.03 -> 0.01 (`viper_vS4.14_dbg`). **Totals moved 12 -> 11 and the path was
unchanged.** Falsified -- explore was only ~1.1 of a ~10 score all along.

## Falsified hypothesis B (mine): "the food term needs to be single-best, not a sum"

The decomposition showed what actually dominates:

```
r4  fdist=5   expl=1.11  bel=0.00  tgt=0.00  hotSum=9.54  hotMax=1.39
r8  fdist=11  expl=0.87  bel=0.00  tgt=0.00  hotSum=7.12  hotMax=0.90
```

`hotSum` -- the **sum** over all 22 hot beds -- is 8-9.5 of the ~10 total, while `hotMax` (the
nearest fountain alone, the only directionally meaningful part) is 1.1-1.4. Per-direction variation
in `hotSum` is 0.1-0.3 on a base of 9, i.e. **3%**: the dominant term carried magnitude but almost
no direction, so the choice between two legal directions was near-arbitrary.

So `viper_vS4.15_dbg` replaced `sum of wHot*rate*fp(m)` with `wHot * max(rate*fp(m))` -- exactly the
argument `policy.hpp` already makes for `wTarget` ("commits more decisively to the single best nearby
pearl instead of a diffuse pull toward everything at once"), never applied to the long-range channel.
It worked mechanically (`hotSum` == `hotMax`, total ~10 -> ~2) and **the path kept the same shape**:
fdist 8,7,6 then 8,9,10,...,16.

The falsifier had been pre-registered: "if `fdist` still wanders up after this, the wandering is not
caused by the value function's shape -- stop attacking the value function." It fired. Stopped.

## What the ground truth shows: a commitment/routing failure

Dumping the dragon's head positions against the fountain coordinates -- the check that should have
come first:

```
r3  (7,15) man=5    r9  (7,9)  man=5    r13 (10,10) man=1    r17 (8,10) man=3
r4  (7,14) man=4    r10 (8,9)  man=4    r14 (10,11) man=1    r18 (8,11) man=3
r5  (7,13) man=4    r12 (10,9) man=2    r15 (9,11)  man=2    r20 (9,12) man=2
```

The dragon **does** travel to the fountain cluster and reaches **manhattan 1** from the fountains at
`(11,10)`/`(11,11)` by r13-r14 -- then turns away and dithers in a 3-cell neighbourhood for the rest
of the early game, never eating. The reason: the `x=11` column is **walled off from `x=10`**, so its
true BFS distance stays 13-16 while the manhattan distance is 1. The only accessible entrance is
`(12,14)` -- and at r4 the dragon sat 5 BFS-moves from it with `hotBest` 1.40 available, and chose a
1.119 direction instead.

**So the defect is not magnitude and not sign -- it is persistence.** The bot re-derives a diffuse
field every turn with a depth 3-4 search, and the landscape shifts enough each turn (own body, the
crowd term, explore decay) to flip its choice before any multi-turn approach completes. Nothing in
the value function commits to "that fountain, via that entrance, for the next 8 turns".

This reframes why `wCompass` is the only validated gain in the project's history (+8.3pp): it is the
**only persistent-commitment mechanism in the bot** -- one target chosen with a full-board BFS,
rather than a field summed inside the tactical horizon.

## `wCompass` is INERT -- measured, 24/24 games byte-identical

**This is the most consequential finding of the session.** Built `viper_vS4.7` with `wCompass = 0.0`
and ran the identical batch (6 maps x 2 seeds x 2 sides, `--judge zig`, same seeds) against
`viper_v7.12`. **All 24 games are byte-identical to the baseline** -- same round count, same
termination reason, same death counts on both sides, on trauma, slithery_fight, schooltime, autarky,
devil and dilemma. The term contributes nothing to any decision.

And it has always been this way: `baselines/S4.7.9` and `baselines/S4.8` both have the same
`t[d] = c.stepTerm + rest` depth loop and the same `k == 0`-gated `value += wCompass * ...`, and
`baselines/S4.7.4` predates the term entirely. **There is no build in `baselines/` in which
`wCompass` does anything.**

So the **+8.3pp attributed to `wCompass` on 2026-09-29 (41.7% -> 50.0%) cannot have been caused by
the compass steering term**, because that term provably does nothing in `viper_vS4.7`, the very
build that scored the 50.0%. Two candidate explanations, both worth noting:
- it was panel noise -- and **+8.3pp sits exactly in the 7-9pp panel optimism bias** the POST-MORTEM
  later measured three independent times; or
- it was an accidental side effect: introducing the compass also introduced
  `macroNav_.bfs(b, w_.head, base_, b.NC)`, a **full-board** BFS every turn whenever `hot_` is
  non-empty. That is pure CPU cost, and trauma already runs at the 64M-point ceiling with the
  anytime search bottoming out at depth 3-4, so adding it *reduced search depth*. The "gain" may
  have been a depth reduction. (Consistent with this test: `wCompass=0` still runs that BFS, which
  is why the games come out identical rather than merely similar.)

Either way: **the hand-written bot has zero validated gains.** The handoff's priority list is built
on `wCompass` being "the only validated gain in project history, and it lives exactly here" -- that
premise does not survive. Note also `insights.md`'s own line about the roomFactor follow-up
"confirmed exact parity with the wCompass [baseline]" -- exact parity was the clue, recorded and not
drawn on at the time.

The two structural defects behind the inertness, both pointing the same way:

1. **It is discarded whenever the search reaches depth >= 2** (the cause of the inertness above). The anytime loop sets
   `t[d] = c.stepTerm + rest`, and `c.stepTerm` is only `(eat?eatBonus:0) - danger`. The compass term
   is added to `value`, not `stepTerm`, and its block is gated `if (k == 0 ...)`, so no leaf at
   `k >= 1` ever recomputes it. Once `total = t` replaces the depth-1 vector the compass contribution
   is gone. Measured depth on trauma: **3-10 on 100% of dragon-turns, never 1.**
   (The `k==0`-gated *danger* terms are unaffected -- they live in `stepTerm`, which does survive.)
2. **It excludes the only fountains that matter anyway.** `macroTarget_` skips any hot bed with
   `dd <= p_.horizon` (48) as "tactical hot pull already covers this". On trauma every fountain is
   inside 48, so `macroTarget_` is -1 for the whole early game (`mdist=-1` in the trace) and later
   points at something 112-122 moves away contributing `comp=-0.03`.

## The throughput gap, and why splitting has no food-access condition

`splits = final_units - initial_units + deaths` is exact, so the tourney log's own death counts plus
the trajectories give the crank rate directly. `trauma_1000_A`, 500 rounds:

| | final units | deaths | => splits |
|---|---|---|---|
| us (S4.7) | 2 | 38 | **38** |
| v7.12 | 32 | 178 | **208** |

**v7.12 turns the pearl -> body crank 5.5x faster.** We are not losing to attrition -- our deaths are
38 against their 178. We barely cycle at all. This is what the POST-MORTEM's "more deaths -> 84% win"
was really measuring: **deaths are a throughput proxy, not a cause**, which is why every attempt to
reduce them was pushing on a symptom.

And `trySplit` gates on: the unit cap, not-mid-eat/trade, `L >= swarmSplitLen (4)`, and `bareExit`
("the tail has a free neighbour cell"). **Nothing anywhere asks whether food is reachable.** On
trauma that is actively harmful: budding at 4 converts one viable length-4 dragon into two length-2
stubs, each needing `spaceFactor*2 + 3 = 7` free cells to escape the safety veto, neither able to
reach the walled fountains. Measured: length 2 on 198 of 200 dragon-turns. The compounding chain only
pays when the new heads have food access; trauma's 12 fountains support perhaps 2-3 dragons, so
splitting past that manufactures starving stubs.

## Consolidation is triggered by the clock, not by the thing that scores

Feeding starts at `feedRound` plus an id stagger, and `lateGame()` stops splits. All time-based. But
what decides 36% of games is "is our longest dragon ahead at round 500", and **nothing keys off
that**. That is why S4.10 was noise even though its mechanism worked (`conc` reached 1.000, the whole
team feeding one dragon): converging at the wrong time onto the wrong dragon does not win a tiebreak.

## The unifying diagnosis

**Both the movement and the population systems are stateless and local.** Movement re-decides every
turn with no memory of any plan; splitting and feeding fire on *thresholds* (length 4, round N)
instead of *conditions* (can I reach food? is our longest behind?). That is entirely adequate on an
open, pearl-dense map -- which is exactly where we win 100% (devil, dilemma) -- and wrong on a maze
whose whole economy is 12 walled-off tiles, which is exactly where we are 0%.

## Pick up here

### First, a change I proposed and then rejected on its own mechanism check

I initially wrote "gate splitting on food access" as step 1, on the strength of the 38-vs-208 crank
rate. **That is backwards and should not be built.** Our split count is *too low*, and it is low
because dragons never reach length 4 (length 2 on 198 of 200 dragon-turns) -- nothing is blocking a
split that wants to happen, so a gate can only push the number further down. Worse, keeping dragons
longer *raises* `need = spaceFactor*L + spaceMargin` (15 free cells at L=6 vs 7 at L=2), so in a maze
it buys more safety vetoes, not more eating. This is also consistent with S4.9's refutation, where a
blanket split-stop made the longest dragon *shorter*.

The 38-vs-208 gap is a **symptom of the eating failure, not an independent lever.** Splitting is
downstream of reaching length 4, so the only thing worth attacking is getting to the food.

### The change to build

1. **A committed route.** Target fountain + path stored in `World` (not re-derived inside
   `Policy::decide`), invalidated only on arrival, target-taken, or timeout, steered by a term that
   (a) sits in `stepTerm` so the depth loop cannot discard it, and (b) is not distance-gated out for
   nearby beds. This is the only mechanism the evidence supports for the dithering, and it is what
   `wCompass` was reaching for -- except `wCompass` never worked (see above), so this is untried
   rather than a retread.

   Mechanism check: it changes whether a dragon completes a multi-turn approach to a reachable
   fountain, which is the measured proximate cause of eating 0 pearls in 50 rounds. Falsifier: if a
   dragon with a committed route still fails to arrive, the problem is the route's feasibility (the
   space veto along narrow corridors) rather than commitment, and the next look should be at
   `spaceFactor`/`spaceMargin` along the approach.

Then:

3. **Re-target the round-50 work to slithery_fight and schooltime**, not trauma.
4. **Keep `viper_vS4.12`** (consensus beds): a real defect fixed, null on its own.
5. **Do not re-test** `exploreValue` scaling or `wHot` sum-vs-max on trauma; both are measured nulls.
6. **Stop citing +8.3pp.** The hand-written bot has no validated gain. Set the bar against
   `Y.7.12-nn.1` or real ladder opponents, per the POST-MORTEM's point 4.
7. Before any build, dump the unit trajectory **and the physical path**. Looking at where the dragon
   actually went took ten minutes and invalidated two builds' worth of theorising. Do it first, and
   check a term is not inert before attributing a gain to it -- one `wCompass=0` run would have
   caught that on 2026-09-29.

## CORRECTION to the section above: the fountains are 64 moves away, not 5

Everything above that describes a dragon "reaching manhattan 1 of a fountain and dithering", or
"5 BFS-moves from the accessible entrance", rests on distances the bot computed **while assuming
every unseen tile is open ground** (Board's `Edge` defaults to kind 0, and the vision-only World
never contradicts it until a dragon walks there). Those distances were fiction.

`viper_vS4.19` extends `applyConsensus` to the agreed **kelp edges** as well as beds -- trauma and
stronghold agree on 2036 of 2304 edges -- so from round 0 the dragon reasons over the real walls.
With the real walls in place the trace reads:

```
r1  fdist=64   r5  fdist=60   r9  fdist=56   r13 fdist=60
```

**The nearest every-round fountain is 64 moves away, and it never gets closer than 56.** There was
never a nearby fountain being ignored. Two consequences, both fatal to the routing premise:

- `horizon = 48` bounds every tactical BFS, and 64 > 48, so the fountains contribute **literally
  nothing** to `targets_` or to the `wHot` field -- not a weak signal, an absent one.
- even in range, `gammaFar^64 = 0.0095`, so the pull would be `wHot * 1.0 * 0.0095 = 0.019`.

So `wHot`'s 8-9.5 of score measured earlier was **the 130 near-dead slow beds**, not the fountains.
The "diffuse centroid pull" reading was right about the shape and wrong about what was being summed.

## And correct walls made eating WORSE, which is the useful part

| build | trauma eats r0-250 | splits | units at r250 |
|---|---|---|---|
| S4.7 baseline (optimistic walls) | **72** | 32 | 5 |
| S4.19 (consensus kelp edges) | **6** | 4 | 2 |

Giving the bot *correct terrain knowledge* cut its eating by 12x. The reason is the interesting bit:
**optimistic routing was accidentally load-bearing.** Believing unseen tiles are open made dragons
strike out boldly across the map and blunder over the 130 slow beds; knowing the real walls made them
route conservatively inside their own pocket and find far less. Our actual trauma economy is the slow
beds we trip over, not the fountains -- and "walk to the fountains" is not a plan available to a
length-2 dragon at distance 64 with a 48-move horizon.

This is worth keeping as a general warning: on this bot, **more accurate world knowledge is not
automatically better play**, because the policy's exploration behaviour is tuned (accidentally) around
the inaccuracy. Any future knowledge improvement has to be measured, not assumed.

## The routing builds, and what was actually wrong with each

- **S4.16** -- committed target in `World` (persists correctly, `route=683` stable all game), steering
  term in `stepTerm` so the depth loop keeps it. But the progress measure compared `macroNav_`'s
  distance-from-head against the per-direction BFS `scoreFrom` already runs from `dest`, and those two
  block different cells (current body vs hypothetical post-move body). **Not a metric**: instrumented
  `rfire` showed two different neighbours BOTH reporting "+1 closer" to the same target while the true
  distance climbed 13 -> 20.
- **S4.17** -- additionally let the diffuse `wHot` field yield to a committed route. Same bug.
- **S4.18** -- the first *correct* implementation: one BFS rooted at the target, head and `dest` read
  from the same field, paid for by deleting the proven-inert macro-compass BFS (so no extra CPU; peak
  stayed 63.7M). The metric is sound and the mechanism fires. **The premise was wrong, not the code**
  -- there is nothing within reach to route to.
- **S4.19** -- consensus kelp edges, above. Worse, informatively.

None of these ship. `viper_vS4.12` (consensus beds) remains the only keeper, and it is null.

## Revised "pick up here"

1. **Do not pursue committed routing on trauma.** The target is 64 moves away behind a 48-move
   horizon; commitment was never the binding constraint. `viper_vS4.18` is a correct implementation
   sitting in the tree if a map ever presents a reachable target worth walking to -- it is the right
   mechanism aimed at the wrong map.
2. **The open question on trauma is now v7.12's, not ours**: with a symmetric map (its cluster at
   x=35-36 is as far from its spawn as ours at x=11-12 is from ours) it reaches 208 splits to our 38.
   Measure what v7.12's dragons actually eat and where, with the same path dump. That is one cheap
   measurement and it is the only remaining lead on this map.
3. **`horizon = 48` is a hard ceiling on the whole value function** and nothing above 48 moves exists
   to this bot at all. On a 48x24 maze with 60+ move traverses that may be the real defect, and it is
   untested. Raising it costs CPU (we are at 63.7M of a 100M budget with a ~65M working guidance), so
   it trades against search depth -- which makes it a real experiment, not a free win.
4. **Re-target the round-50 work to slithery_fight (-13.0) and schooltime (-7.0)**, where the early
   deficit is 6x trauma's and where the maps resolve at round 0 so none of trauma's knowledge
   pathologies apply.
5. Treat "give the bot better information" as a hypothesis to test, not an improvement to assume --
   consensus edges are the counterexample.

# ======================================================================
# WHAT v7.12 ACTUALLY DOES (2026-09-30, structural read of viper_v7.12/main.cpp)
# ======================================================================

## The number that matters: eating rate per dragon-turn, and it is only 1.8x

trauma, `trauma_1000_A`, both sides of the same game:

| rounds | | eats | splits | dragon-turns | **eats/turn** |
|---|---|---|---|---|---|
| 0-250 | us (S4.7) | 72 | 32 | 2059 | **0.035** |
| 0-250 | v7.12 | 166 | 64 | 2569 | **0.065** |
| 0-500 | us | 87 | 38 | 2829 | **0.031** |
| 0-500 | v7.12 | 592 | 191 | 10528 | **0.056** |

The 6.8x total food gap is **1.8x eating efficiency x 3.7x dragon-turns**. At r0-250 it is 1.9x
efficiency x 1.25x turns, so **per-turn efficiency is the primary driver** and the dragon-turn
advantage is what it compounds into afterwards. The target is therefore concrete and modest:
**roughly double eats per dragon-turn in the early game.** Not a new macro, not consolidation.

And it has nothing to do with trauma's 12 every-round fountains. At 64 moves, v7.12's own pull toward
them is `farmBonus(3.0) * wTarget(1.6) * 0.94^64 = 0.096`, gradient ~0.006/step -- negligible for it
too. **v7.12 is simply harvesting the same 130 near-dead slow beds about twice as well as we are.**

## Seven structural differences, in rough order of size

1. **Three discount tables, not one.** `powG = 0.86^m` (summed field), `powT = 0.94^m` (single best
   target, hardcoded), `powM = 0.80^m` (miners only -- "eat what is near"). We apply `gamma = 0.80` to
   everything. Same pearl at distance m: 0.80^30 = 0.0012 vs 0.94^30 = 0.156, a factor of **127**; at
   48 moves it is **3000x**. So our value function has an effective horizon of about **15 tiles**
   however far the BFS reaches, and past that our dragons know nothing and fall back to `exploreValue`
   -- which survives only because it is a sum over hundreds of cells rather than one discounted value.
   This is exactly the defect `wCompass`'s own comment describes, and wCompass never fired.

2. **One BFS does everything, which is how it affords `fieldCap = 90`.** A single BFS from the head
   produces distances, the pearl field sum, the best target, the free-space count and the goal
   distance, accumulating the field *inside the traversal*. We run `nav_.bfs` per candidate direction
   per search node -- hundreds per turn -- and iterate a `targets_` vector inside each. The CPU goes to
   opposite places: **v7.12 buys reach (90 tiles, 1 ply); we buy depth (48 tiles, 3-4 ply).** On a maze
   where the food is far, reach wins and our lookahead searches 4 plies inside an empty bubble.

3. **Time-aware BFS, for OTHER dragons.** `if (ownStamp[n] == stampCtr && ownBT[n] >= nd) continue;`
   and the same for `otherBT`: a body cell blocks only if it is *still occupied by the time we would
   arrive*. **CORRECTION to an earlier claim in this file: our `Nav::bfs` is already time-aware, and
   our own body is handled correctly.** `blk[c]` is documented as "the earliest move number at which
   the head may enter tile c" and `markBody()` frees our own segment i after `L - i + 1` moves -- the
   same mechanism. The real and much narrower defect is in `Policy::buildBase()`, which sets
   `base_[c] = INF` for every cell held by *any other* dragon, teammate or enemy: **other dragons are
   permanent walls in our distance field and never free up.** That is the half v7.12 has (`otherBT`)
   and we do not, and it is what inflates our distances (the measured 5 -> 12 jump in one step was a
   *teammate* moving through the corridor, not our own tail).

   The magnitude scales with crowding, which is the encouraging part: on trauma (4 dragons of length 2)
   it blocks 8 cells, but on slithery_fight and schooltime, which run to the 64-unit cap, it poisons
   most of the board -- and those are precisely the two maps with the worst early deficit (edge@50
   -13.0 and -7.0). Inflated distances flatten every distance-discounted term at once, which is the
   flat-value-landscape pathology measured all session: when every target discounts to nothing,
   `exploreValue` wins by default. Built as `viper_vS4.25`, conservatively -- cells are freed only for
   a dragon whose whole body is visible this turn (its true length is otherwise only a lower bound, and
   freeing a cell too early walks us into a body that is still there), everything else stays a hard
   wall, and no new tuned weight.

4. **Pearl probability at arrival time.** `pearlProb(n, ROUND + nd)` -- the chance a pearl is there
   *when we would get there*, not now. Ours (`World::belief`) is now-only. S4.13's steady-state hack
   was a poor substitute for this.

5. **`farmBonus`: bounded, rate-derived.** `1.0 + min(2.0, 8.0/meanGap)` gives trauma's gap-1 fountains
   3.0x and its gap-1..200 beds 1.08x -- clean discrimination from the map's own data, as a multiplier
   on one probability. Compare our `hot_`, where the `certain` override dumps all 142 beds into a
   summed field so 130 near-dead beds generate 8-9 points of directionless magnitude.

6. **Goal commitment by value hysteresis.** `if (lastGoal != best && valT[lastGoal] >= 0.75*valT[best])
   g = lastGoal;` -- keep last turn's goal unless a rival is worth >1.33x it. Then `wProgress = 0.8`
   per step of progress, **clamped to [-2,+2]**. Note it compares distances from two different BFS the
   same inconsistent way our S4.16 did; the clamp is what makes it survive that.

7. **Things we have no analogue for at all**: symmetry exploitation (`detectSymmetry`/`mirrorCell`, and
   per the map docs mirrored tiles share one countdown and fire together, so every observation is worth
   double); role specialisation with its own discount (miner/drone/queen/hunter); a calibrated danger
   model (`p1=0.85, p2=0.15, p3=0.03` = probability an enemy head at distance d attacks, times
   `deathExtra=30` + length) instead of additive weights; opponent adaptation (`if (swarm) p *= 0.8
   else p *= 0.55` -- "against a swarm every pearl is contested; discounting them all just starves
   us"); and two split modes (swarm bud at length 4 with a constant 2-child, plus a big split at
   length 24 with a 6-child).

## S4.22: the transplant that failed, and why it is the lesson of the whole session

Our friend-closer rule is a hardcoded **hard zero** (`policy.hpp`: `if (fd < m || ...) v = 0;`) -- a
target any teammate is closer to is worth *exactly nothing*. v7.12 keeps 8% (`friendCloser = 0.08`).
That looked like a clean 2x eating defect: dragons cluster, so `friendDist < m` holds over most nearby
cells and most of a grouped dragon's targets vanish from its value function entirely.

Result: **eats per dragon-turn 0.035 -> 0.003, a 10x collapse.** Prediction falsified, hard, and the
reason is the useful part: **the hard zero is our only task-allocation mechanism.** It forces dragons
onto different targets. Soften it and all four chase the same nearest pearl and jam the same corridor.
v7.12 can afford 0.08 *because* it has gossip, roles, `zoneF`/`friendMinId` and a queen protocol doing
that coordination explicitly.

**Generalise this before copying anything else from v7.12: its efficiency is a property of a coherent
set of mechanisms, not of any single transplantable number.** Every parameter in it is load-bearing
against the others. Three separate attempts this session to lift one piece across (`wHot` sum->max,
`friendCloser`, consensus kelp edges) each made things worse, and each for the same reason -- the piece
they replaced was compensating for something else that is missing in our bot.

## Where that leaves the work

The measured target is **2x eats per dragon-turn in rounds 0-250**, and the three candidates with a
real mechanism behind them, in order:

1. **`pearlProb` at arrival time** (v7.12 item 4). Principled, no new tuned weight, and it is the one
   difference that directly changes *which bed is worth walking to* rather than how far we can see.
   S4.13 approximated it badly (steady-state instead of time-indexed) and was null; the proper version
   is untested.
2. **Time-aware BFS** (item 3). Makes every distance estimate correct rather than pessimistic, needs no
   new weights, and fixes a defect we measured directly (the +7 distance jump).
3. **The field discount** `gamma` 0.80 -> 0.86 (item 1), tested as `viper_vS4.23` -- see the result
   logged below.

Do **not** attempt items 2, 5, 6 or 7 as parameter transplants. If the coordination machinery
(roles/gossip) is ever built, revisit `friendCloser` then and not before.

## S4.23 result (gamma 0.80 -> 0.86): decisively WORSE, and it settles the design question

32-game panel, `tempo.py` (the low-variance metric, not win rate):

| build | r25 | r50 | r100 | r150 | win |
|---|---|---|---|---|---|
| baseline, gamma 0.80 | 7.0 (-0.5) | **10.5 (+0.0)** | 17.5 (-3.0) | 20.0 (-7.0) | 53% |
| S4.23, gamma 0.86 | 6.0 (-1.0) | **7.0 (-2.0)** | 11.0 (-3.5) | 14.5 (-9.5) | 41% |

Worse on all four checkpoints and on six of eight maps (default +1.0 -> -3.0 and 75% -> 0%; trophy
+3.0 -> -7.0; schooltime -7 -> -12; slithery -13 -> -16). Only devil improved (+5 -> +8). A 3.5-unit
drop in median edge@50 over 32 games is far outside this metric's noise.

**My "our effective horizon is only ~15 tiles" arithmetic was right and the conclusion drawn from it
was wrong.** A sharp discount is not a defect in this bot -- it is what makes it commit to nearby food
and actually eat it, which is what generates tempo. Widening the horizon dilutes the near-field signal,
the same pathology already measured on `wHot`'s diffuse sum. Also worth recording: `gamma = 0.80` came
from `param_search` validated on the discredited 32-game panel, and it is nonetheless **correct** -- a
biased validation method does not imply a wrong answer, and I over-corrected in assuming it did.

## The conclusion of the whole session

**Our bot and v7.12 are two different coherent designs, and you cannot interpolate between them one
parameter at a time.**

- Ours is a **short-horizon greedy forager** whose tempo comes from close-range commitment plus one
  crude but load-bearing coordination device (the hard friend-zero that forces dragons apart).
- v7.12 is a **long-horizon planner** (0.94 target discount, fieldCap 90, time-aware BFS,
  arrival-time pearl probability, goal hysteresis) whose long reach is *safe* only because explicit
  coordination machinery -- gossip, roles, a queen protocol, `zoneF`/`friendMinId` -- stops its dragons
  converging on the same distant target.

Five attempts this session to move one piece of the second design into the first:

| transplant | result |
|---|---|
| `wHot` sum -> single best (S4.15) | null, path unchanged |
| consensus kelp edges (S4.19) | **eating 12x worse** (72 -> 6) |
| committed routing (S4.16-S4.18) | null; correct mechanism, nothing in reach to route to |
| `friendCloser` hard 0 -> 0.08 (S4.22) | **eating 10x worse** (0.035 -> 0.003/turn) |
| `gamma` 0.80 -> 0.86 (S4.23) | **edge@50 10.5 -> 7.0**, win 53% -> 41% |

Every one failed for the same structural reason: **the piece it replaced was compensating for
something our bot does not have.** Long reach without coordination converges dragons; accurate terrain
without long reach makes them local; a soft friend discount without roles makes them collide.

**So the choice is a real fork, and it should be made deliberately rather than drifted into:**
(a) commit to the short-horizon forager and improve it on its own terms -- the untested items are
`pearlProb` at arrival time and the time-aware BFS, both of which raise eating efficiency without
widening the horizon; or (b) build the coordination machinery FIRST (roles, target gossip), and only
then widen the horizon, in that order, because the reverse order is what failed five times today.

Option (b) is a multi-day rewrite. Option (a) has two concrete untested items and a measured target
(2x eats per dragon-turn in r0-250). Start with (a).

## S4.24 (arrival-time pearl probability): the first non-negative result of the session

Chose fork (a) -- improve the short-horizon forager on its own terms, without widening the horizon,
since five horizon-widening attempts all failed. This is viper_v7.12's `pearlProb(n, ROUND + nd)`.

Ours asked only "is a pearl on this tile RIGHT NOW" and then applied a *value* discount for distance.
That over-values a stale sighting (a pearl seen 20 rounds ago was treated as just as likely to still be
there 20 rounds from now) and under-values a bed that will have ripened by the time we arrive. Now:

    P(present on arrival) = belief * seenDecay^m  +  (1 - belief) * P(spawns within m)

and a bed that will not have spawned by arrival is scored at the *later* of "when we arrive" and "when
it spawns", so walking there and waiting is still valued.

Two deliberate implementation choices: **no new tuned weight** (it reuses the existing `seenDecay`, and
the spawn term comes from the map's own gapMin/gapMax) -- four of five failed transplants were parameter
changes; and **no `pow()` in the inner loop** -- spawn probabilities are bucketed by mean gap (trauma has
exactly two distinct specs, most maps <= 5) into `spawnTab_[bucket][m]`, so the innermost loop over ~1000
targets x hundreds of search nodes costs one array lookup. CPU 64.1M peak: the anytime loop absorbed the
wider `targets_` by trading search depth, which is the right trade here.

32-game panel, `tempo.py` (first number = our median units, parenthesised = edge over the opponent):

| build | r25 | r50 | r100 | r150 | win |
|---|---|---|---|---|---|
| baseline | 7.0 (-0.5) | 10.5 (**+0.0**) | 17.5 (**-3.0**) | 20.0 (-7.0) | 53% |
| S4.24 | 6.5 (+0.0) | 10.0 (**+0.0**) | 14.0 (**+1.0**) | 15.0 (-5.0) | 62% |

**Correction to my own pre-registered falsifier**: I wrote "edge@50 above the baseline's 10.5", but 10.5
is median *units*, not edge. On the edge metric **r50 is a wash (+0.0 both)** and the gains are at r100
(-3.0 -> +1.0, a 4-unit swing) and r150 (-7.0 -> -5.0). Since the round-50 thesis holds that r50 is the
predictor, this is **neutral on the primary metric with real downstream improvement** -- not the clean
win the 53% -> 62% headline suggests, and that headline sits inside the panel's measured 7-9pp noise.

Per-map edge@50: trophy +3.0 -> **+11.5** (50% -> 100% win), slithery -13.0 -> -8.5, trauma -2.0 -> -1.5,
devil +5.0 -> +6.5; against schooltime -7.0 -> **-11.5** and default +1.0 -> -0.5 (still 75% win).

**The mechanism was not the one predicted.** trauma r0-250: eats per dragon-turn **flat** (0.035 ->
0.034), but total eats 72 -> 94, dragon-turns 2059 -> 2761, splits 32 -> 44, deaths unchanged (29 -> 30),
and units at r250 **5 -> 16**. It did not raise per-turn efficiency; it entered the compounding loop
better. So the "2x eats per dragon-turn" target framing is the wrong lens: the loop can be driven from
population as well as from efficiency, and the same per-turn rate over 34% more dragon-turns is worth
just as much.

SPRT verdict (S4.24 vs the S4.7 baseline directly, p0=0.5, p1=0.6): logged below when it lands. **Do not
promote on the 32-game panel** -- that is the exact error the POST-MORTEM was written about, and it has
already produced three false positives in this project.

## S4.25 (time-aware other-dragon bodies): falsified -- but the build had a real bug

Pre-registered prediction: the defect's magnitude scales with crowding, so edge@50 should improve on
slithery_fight (-13.0) and schooltime (-7.0), which run to the 64-unit cap, and barely move on trauma
(-2.0), which has four dragons of length 2. Falsifier: *if it moves on trauma but not on the crowded
maps, the crowding mechanism is wrong -- stop and re-diagnose rather than tune it.*

| map | baseline edge@50 | S4.25 | predicted |
|---|---|---|---|
| slithery_fight | -13.0 | **-13.0** | improve -- NO |
| schooltime | -7.0 | **-8.0** | improve -- NO |
| trauma | -2.0 | -1.5 | barely move -- yes |
| dilemma | +4.5 | **-5.5** (100% -> 0% win) | -- |
| default | +1.0 | -3.5 | -- |
| overall r50 edge | +0.0 | **-3.0** | -- |
| win | 53% | **34%** | -- |

Zero movement on both crowded maps, and severe collateral damage elsewhere.

**However, S4.25's implementation was buggy, so this result does not bear on the idea.** The protocol's
`Part` carries only a `head` flag, never a segment index, so the body ordering has to be reconstructed
by walking from the head through that dragon's own occupied cells -- and **for a coiled body the order
is not recoverable from a single frame.** A length-4 dragon curled into a 2x2 square has its head
adjacent to both segment 1 and segment 3, so a first-match walk can label the true segment 3 as index 1
and get the free times exactly backwards: it frees the cell that empties *last* the soonest, and the
BFS then paths straight into a body that is still there. Dragons coil constantly in a maze, and the
dilemma collapse (100% -> 0%) is the signature of exactly that.

`viper_vS4.26` fixes it: a dragon's cells are freed only when every step of the walk has exactly **one**
unvisited same-id neighbour; ambiguous (coiled) bodies stay hard walls as before. That is always
unambiguous for the length-2/3 dragons a swarm mostly consists of. Re-tested on the same panel.

**Process note worth keeping**: the falsifier fired correctly and would have had me abandon a sound idea
on the strength of a corrupted build. A falsifier is only as good as the implementation under it -- when
a result is *this* bad (a 100% -> 0% map flip), suspect the build before accepting the conclusion. The
right general guard is a correctness check on the new data structure (here: assert the reconstructed
chain length equals the visible part count AND that the walk was forced at every step) before reading
any behavioural result.

## S4.26 (coiled-body bug fixed): the idea itself is bad, not just the implementation

Same panel, after fixing the ordering ambiguity that corrupted S4.25's distance field:

| map | baseline edge@50 | S4.25 (buggy) | S4.26 (fixed) |
|---|---|---|---|
| slithery_fight | -13.0 | -13.0 | **-13.0** |
| schooltime | -7.0 | -8.0 | **-8.0** |
| dilemma | +4.5 | -5.5 | **-5.5** |
| trauma | -2.0 | -1.5 | -1.5 |
| overall r50 edge | +0.0 | -3.0 | **-3.0** |
| win | 53% | 34% | **34%** |

Essentially identical to the buggy version. **The bug fix did not rescue it, so the original falsifier's
verdict stands: time-aware other-dragon bodies genuinely hurt this bot.** Worth noting the process
outcome -- suspecting the build was the right instinct (the bug was real, and a 100% -> 0% map flip did
warrant it), and re-testing after the fix is what turned an ambiguous result into a clean one. The cost
was one extra panel run; the alternative was leaving a permanently ambiguous note in this file.

Why it plausibly hurts: freeing a teammate's cells lets several of our dragons plan through the same
corridor, and our ONLY coordination device is the hard friend-zero in the pearl field. Making bodies
permeable removes the *physical* separation that was doing the rest of the work -- the same lesson as
S4.22's `friendCloser` collapse, from the opposite direction. **Twice now, removing a crude blocking
constraint has cost more than the accuracy it bought, because the crude constraint was our coordination.**

## S4.24 SPRT final standing: ~54%, undecided

n=125: 54.4%, LLR -0.32, oscillating around zero and nowhere near the +2.944 accept bound. It will cap
undecided at ~54%. Panel said 62% -> **a ~8pp optimism gap, the fourth independent measurement**, now
firmly in the 7-9pp band. **S4.24 is marginal at best; shelved, not shipped.**

And the round-50 thesis predicted this correctly in advance: S4.24 was neutral on edge@50, and the thesis
says edge@50 predicts the result -- so a neutral win rate was the forecast, against a 62% panel headline.
That is the thesis's second correct forward prediction, and the practical consequence is that **edge@50
over 32 games is a cheaper and more reliable screen than win rate over 150.**


# ======================================================================
# WHAT THE TOP 16 ACTUALLY DO -- behavioural read of 184 fresh replays (2026-09-30)
# ======================================================================

Data: `ladder/scout_fresh` (16 teams, elo 1947-2108, 184 games) and, as a like-for-like baseline,
`ladder/scout_self` (our own 30 most recent ladder games, 23% win -- matches the ~22% real figure).
Tools: `tools/behaviour_profile.py`, `tools/death_context.py`, `tools/sonar_profile.py`,
`tools/profile_style.py`; `tools/scout.py --team-ids 98` pulls our own games. Outputs are in each
dir as `behaviour.out`, `deaths.out`, `payloads_all_fixed.out`, `profile_fixed.out`.

Public replays carry NO CPU points and NO indicator/log strings for any team (all stripped), so CPU
is only visible through "no valid action" deaths -- which the judge also uses for a turn that
exhausts its 100M points. Our own champion deliberately dies that way to feed (`printf("SPLIT 1")`,
"illegal on purpose"), so that cause must be read in context, which `death_context.py` does.

## 1. The early game is a shared, solved engine -- and ours is already top-grade

Every one of the 17 teams (ours included) buds at length 4 into 2+2 (3.14159265: 5 into 3+2), and
does it **one round after the eat that reached the threshold**. Median dragon length is 2.00 at every
checkpoint for every team. Voronoi area share tracks unit share exactly (`area_per_unit` 0.92-1.13
for winners and losers alike), so **area control is a consequence of population, not a separate
skill** -- which retracts the "missing area-control term" hypothesis raised earlier today.

| early game (r0-99) | ours | top-16 range | top-16 median |
|---|---|---|---|
| eats per dragon-turn | 0.104 | 0.066-0.119 | ~0.09 |
| net growth (splits - deaths) per 1000 dt | +12.7 | +10.2 - +15.1 | ~+12.4 |
| greedy (takes an adjacent pearl) | 77% | 67-97% | ~86% |
| pursuit (closes true distance to a visible pearl) | 56.9% | 54-68% | ~58% |
| birth -> first split, rounds | 10 | 5-16 | ~9 |

We sit inside the top-team band on every early metric. The #1 team (cheji bt) has the LOWEST early
eating (0.066) and the slowest breeding (15 rounds). **Faster early economy is not what wins at the
top**, which also explains why pearl gossip (+37% early eating) changed nothing on the ladder. The
round-50 thesis was a property of the S4.x-vs-v7.12 matchup and does not transfer to the champion.

## 2. Our measurable outlier is the late game: we switch the economy off ~100 rounds early

| late game (r300+) | ours | top-16 |
|---|---|---|
| eats per dragon-turn | **0.057** (35% below our mid) | 0.057-0.178, most HIGHER than their mid |
| greedy capture of an adjacent pearl | **56%** | 68-95% |
| splits per 1000 dragon-turns | **10.2** | 15.8-62.0 (median ~25) |
| deaths per 1000 dragon-turns | **16.5** (lowest in the table) | 19.7-63.9 |
| 90th-percentile round of the last split | **315** | 327-429 (median ~390) |

This is designed, not incidental: the champion's schedule is `budUntil=300` (narrow/maze maps),
`mineUntil=300`, `feedFrom=350`, `endFeedFrom=440`. From ~r300 our drones stop budding, stop mining,
and walk toward the queen instead of eating what is in front of them. **Every top team keeps the full
swarm economy running until ~r390-430 and consolidates in a short final phase.** Their late death
rate is high because the swarm is still churning. Ours is the quietest swarm on the ladder for the
last 200 rounds, which lines up with the champion's documented loss modes (10 late collapses, 221
feed deaths in them, Trauma the worst map).

Supporting history: "earlier queen (round 250)" was screened and was WORSE (15/42), and V7.11 "keep
budding on Autarky" was a gain. Both point the same way -- later consolidation is the untested side.

## 3. Our feeding wastes a quarter of what it feeds

| feed-channel deaths (late, in-place) | feed% (longer ally head within 2) | pearls eaten by own / enemy / never |
|---|---|---|
| **ours (SPLIT 1)** | **39%** | **69 / 7 / 24** |
| SSS | 78% | 91 / 1 / 7 |
| Sponge | 74% | 86 / 3 / 11 |
| tungtung67 | 58% | 95 / 2 / 3 |
| ddabap | 57% | 85 / 2 / 12 |
| bread first search | 53% | 89 / 2 / 9 |
| PPP | 38% | 90 / 0 / 10 |

A dying dragon drops only ceil(L/2) pearls, so a feed is already a 50% recycle; we then lose another
quarter because `tryFeed` lets a drone die anywhere within distance 3 "in her path" and the queen
often never arrives. Top feed channels die next to the queen and lose 3-12%.

## 4. Death is a designed resource for every top team

Each top team has one dominant in-place death channel, recycled 75-97% by its own team within 15
rounds: kelp (calc, Stockfish, PPP, SKKU, bfs, 3.14, Sabotage-d, tungtung, Sponge, 中国), own neck
(Cache me outside, ddabap, SSS), or deliberate invalid output (cheji bt, forgot to mention, Cutlery).
The last three have **zero accidental wall/self deaths** (0.00-0.08 per 1000 dt) -- their only
non-combat death is the chosen one, used in every phase (10-19% of them early). Our own mid-game
wall/self deaths (2212 + 1816 in 30 games) are the risk cost of greedy mining dives rather than a
designed channel, but they are recycled 79-81% by us, so economically they look like everyone else's.

Head-on trades differ in who gets the drops: calc 84/11 own/enemy, cheji 76/20, FTM 71/23 versus ours
60/34. The better teams collide where their own dragons are close enough to eat the result.

## 5. Sonar and echo: state gossip and a bud-safety reflex, not a decision driver

- The #1 team (cheji bt) sends **no sonar at all**, in any game.
- Receiving a teammate's message changes the receiver's next move by at most ~4 points for EVERY team,
  ours included. Messages update persistent state (who is where, pearls, queen); they never trigger a
  reflex.
- After an enemy-head echo every team, ours included, goes straight 2-11 points more often and buds
  about half as often (3-5% -> 1-2%). Nobody flees (moves directly away 10-19%). Radar is used to
  avoid budding into danger.
- Six teams broadcast readable plaintext: PPP (sender id 100%, head cell 89%; 87% of its rays carry
  payload 0 = pure radar), forgot to mention (sender id 88%, head cell 82%, **a pearl cell 41%** --
  pearl gossip in the clear), Stockfish (own x/y 80% plus a second x/y pair = a target), ddabap
  (24-bit constant signature 0x28de00 + id + round), tungtung67 (round stamp 90%). Cache me outside,
  calc, 中国, Cutlery, Sponge, SKKU and we send hashed/random payloads.
- We fire mostly single forward rays early (1.0/dt, 69% one-ray turns, F 53%) and four rays late
  (4.0/dt, queen gossip from r300). Top teams are phase-uniform. Neither pattern correlates with rank.

Conclusion: sonar work is not where the gap is.

## 6. CPU

Not measurable from public replays. The only proxy is "no valid action", and for nearly every team it
is a deliberate death in context (late, beside a longer ally, recycled 80-95%). The one profile
consistent with heavy compute is cheji bt: zero sonar, zero accidental deaths, lowest dither (7%),
and in-place deaths with an enemy head within 2 in 27% of cases (vs 16-20% for the other two
invalid-output teams) -- which fits either deliberate combat suicides or search overruns in combat.
No evidence that the top field wins through heavy computation.

## 7. What changes, and what does not

Retracted today: "area control is the missing term" (area = population), "the foundation is wrong,
rewrite" (the champion's early engine is top-grade), "improve early eating" (pearl gossip + this data).

**Work on the champion's late game, not on S4.x and not on a rewrite.** In order:
1. **Consolidate later.** `budUntil` 300 -> ~390, `mineUntil` 300 -> ~380, `feedFrom` 350 -> ~420,
   `endFeedFrom` 440 -> ~460 (keep `bigFeed` maps separate; they were tuned on the ladder). This is
   the champion's own schedule moved to where the entire top field sits, not a transplant.
2. **Feed only where the queen will eat it.** Require the queen within 1-2 and heading toward the drop
   cells. Target: feed recycle >= 85% own (from 69%), measured with `death_context.py`.
3. **Keep non-feeding drones greedy late** (late greed 56% -> ~80%).

Test with same-time ladder A/B (local screening is saturated per ml/results.md), and read the result
through `behaviour_profile.py` / `death_context.py` on the new build's ladder games so that the
mechanism is confirmed, not just the win rate.

## viper_nn_late: gate FAILED as a bundle, but feedDist alone is a confirmed win (2026-09-30)

Built from `baselines/y7_12_nn1` (the champion): (1) late schedule -- budUntil/mineUntil 300->380,
feedFrom 350->420, endFeedFrom 440->470, gossipFrom 300->370, protectFrom 340->400 on maze maps
(bigFeed maps keep V7.12's values); (2) feedDist 3->2 (die only within 2 of the queen, not 3).

**Stage-1 gate result: FAIL.** vs champion 16/40 = 40.0% (needs >=55%); vs V7.5 15/20 = 75.0% (passes,
needs >=50%). Worst on trauma (0/4), weak on portals/schooltime/autarky (1/4 each). Not submitted --
submission makes a build active immediately, stage 1 failed clearly (not a noise-level miss), and this
does not meet a "build on it" bar.

**Mechanism check (paired, same 40 games, `tools/local_index.py` + `behaviour_profile.py` +
`death_context.py`) shows the two changes pulled in different directions:**

| | champion | late_build |
|---|---|---|
| feed deaths within 2 of queen | 41% | **94%** |
| fed pearls eaten by own team | 66% | **75%** |
| fed pearls never eaten | 28% | 23% |
| 90th-pct last split round | 329 | 347 |
| eats/dturn e\|m\|l | 0.096\|0.085\|0.067 | 0.096\|0.085\|0.066 (near-identical) |

**feedDist=2 worked exactly as predicted** -- a clean, isolated, measured improvement in feed
targeting and recycling. **The schedule shift barely moved economy or split timing** in this batch,
most likely because many gate games (only 40-unit cap, some maps decided by elimination) end well
before round 380, so the new thresholds rarely engage -- and delaying queen consolidation on the games
that DO run long plausibly cost more than late-game eating gained, which would explain the gate loss
despite the earlier top-16 analysis being directionally right about consolidation timing.

**This is a bundling mistake** (the same one the S4.x post-mortem warned about): two changes shipped
in one candidate, so the net result cannot say which one is responsible. feedDist looks like a real,
isolated win; the schedule shift is unproven and is the more likely source of the loss.

**Next step, not yet done (ran out of session time): split into two separate candidates and gate each
alone** -- `viper_nn_feeddist` (feedDist=2 only, champion schedule otherwise) should clear the gate
easily given the paired numbers above; `viper_nn_schedule` (schedule shift only, feedDist=3) isolates
whether the later-consolidation idea holds up outside the top-16 analysis or needs a different shape
(e.g. gated on game length so far, not a flat round number).

All replays kept: `ladder/late1_vs_champ/` (40 games), `ladder/late1_vs_v75/` (20 games),
`ladder/late1_champ_prof/` (the paired mechanism profile + its `behaviour.out`/`deaths.out`).
Candidate source: `viper_nn_late/` (uncommitted, kept for the split above). Champion untouched.

## Split candidates gated: both fail independently, overturning the earlier read (2026-09-30, cont.)

Built `viper_nn_feeddist` (feedDist 3->2 only) and `viper_nn_schedule` (schedule shift only,
feedDist=3), both from `baselines/y7_12_nn1`, each verified as a single isolated diff from the
champion. Gated identically (40 games: 10 live maps x 2 seeds x both sides vs champion).

| candidate | vs champion | verdict |
|---|---|---|
| viper_nn_late (both changes bundled) | 16/40 = 40.0% | FAIL |
| viper_nn_feeddist (feedDist only) | **17/40 = 42.5%** | FAIL |
| viper_nn_schedule (schedule only) | **20/40 = 50.0%** | FAIL (closer, not passing) |

**This overturns the previous entry's read.** The paired mechanism check showed feedDist=2 measurably
improved feed targeting and recycling on the champion's own gate games (41%->94% within 2 of queen,
66%->75% recycled by us) -- that measurement stands, it is real. But isolated and gated head-to-head,
feedDist ALONE does not recover the gate, and is if anything slightly worse than the schedule shift
alone (42.5% vs 50.0%). **Neither piece explains the bundle's loss by itself; they may combine
sub-additively, or 40 games per candidate is too noisy to resolve a further split.** schedule (50.0%)
is the closer of the two but still fails outright, and local head-to-head against this specific
champion has historically sat at ~50% for every network variant tried (ml/results.md) -- so 50.0% here
is consistent with "no detectable difference," not with "worse."

**Conclusion for next session: do not conclude feedDist is the culprit, and do not iterate further on
local gate percentage against this champion** -- three candidates (bundle 40%, feeddist 42.5%,
schedule 50.0%) all failed and none isolates a clear winner, which matches the project's repeated
finding that local self-play against the champion has saturated. The one piece of this work still
worth keeping is the feedDist mechanism measurement itself (real, paired, not in question) -- if this
direction is revisited, it should be tested via same-time ladder A/B against real opponents (as
`ml/results.md` had to do for pearl gossip, lane sonar, etc.), not via more local gate percentage
chasing, which cannot separate signal from the ~7-9pp noise this project has measured repeatedly on
smaller batches and is likely to be at least as large here on 40 games.

None of the three candidates are submitted. All replays kept:
`ladder/late1_vs_champ/`, `ladder/feeddist_vs_champ/`, `ladder/schedule_vs_champ/` (40 games each).
Candidate sources: `viper_nn_late/`, `viper_nn_feeddist/`, `viper_nn_schedule/` (all uncommitted).
Champion (`baselines/y7_12_nn1`) untouched throughout.

## S.1 (viper_nn_schedule) real-opponent panel: 4/25 (16%). Refuted.

Submitted as `S.1` (id 13197), tested via `tools/strong_panel.py` against 5 real teams from today's
top-16 profile (calc 2035, SSS 2039, forgot to mention 2063, Stockfish 2078, Cache me outside 2090),
5 maps each (Trophy/Default/Autarky/Devil/Trauma), unranked, champion (`Y.7.12.13`, id 11461)
auto-restored afterward and confirmed active.

| opponent | result |
|---|---|
| Cache me outside | 0/5 |
| Stockfish | 0/5 |
| forgot to mention | 0/5 |
| calc | 0/5 |
| SSS | 4/5 |
| **total** | **4/25 = 16%** |

**Decisively refuted, and worse than the local gate suggested.** Local self-play had this candidate at
50% vs the champion (noise-level, "no detectable difference"). Against real opponents it is 16% --
four of five teams lost every single game. Only SSS is an outlier worth another look (4/5), but one
team out of five is not enough to save the hypothesis.

**This closes the late-schedule consolidation-timing direction as currently specified.** The top-16
behavioural read that motivated it (they keep the swarm economy running ~100 rounds longer than we
do) was real and is not in question -- what's now shown is that copying their *timing* onto our
*mechanism* does not transfer. The most likely reason, consistent with the whole day's pattern
(`insights.md`'s "no parameter transplants" finding): our swarm's coordination is thin (one hardcoded
friend-zero, no gossip/roles), so running it 80 rounds longer just gives its failure modes more time
to compound, whereas the top teams' late-game economy holds up because it is backed by machinery ours
does not have.

**Do not resubmit this schedule shift, tuned or not, without first explaining the SSS result** (is it
map-specific, a weak opponent, or a real sub-case worth isolating?) and without a mechanism-level
reason the transfer should work this time, given the pattern above.

Not re-activated; `S.1` (id 13197) remains on record as a dead build. Panel log: `ladder/S1_panel/panel.log`.

## CORRECTION: "S.1 refuted" was premature -- it had no control arm. Same-time control run (13:25 UTC)

The 4/25 above was declared a refutation without measuring the champion against the same teams. At
our ~1667 rating the Elo-expected score vs these 2035-2090 teams is ~10% (~2.4/25), so 4/25 alone
proved nothing. Control, run 10 minutes later: `tools/strong_panel.py 11461 11461` (champion,
already active), same 5 teams, same 5 maps.

| team | champion Y.7.12.13 | S.1 (schedule shift) |
|---|---|---|
| calc | 0/5 | 0/5 |
| forgot to mention | 1/5 | 0/5 |
| Cache me outside | 1/5 | 0/5 |
| Stockfish | 2/5 | 0/5 |
| SSS | 4/5 | 4/5 |
| **total** | **8/25 = 32%** | **4/25 = 16%** |

- SSS is simply weak on these maps (both 4/5) -- the "S.1 beats SSS" outlier was not S.1.
- S.1 is directionally worse (never ahead on any team; 0/20 vs 4/20 excluding SSS) but NOT
  statistically established (Fisher p~0.3; paired sign test p~0.25). Verdict: **not shipped,
  directionally negative, unresolved** -- not "refuted".
- The champion scores 32% vs 2000+ teams, ~3x its Elo expectation: our 1667 rating understates the bot
  (consistent with elo inflation elsewhere on the ladder).

Methodology lesson (the one that matters): **a ladder test without a same-time control arm is
uninterpretable**, and 25 games against teams we beat ~20-30% of the time has almost no power (floor
effect; +-12pp per arm). Proper ladder A/B needs near-rating opponents (~50% baseline), paired arms
against the same teams interleaved in time, ~100 games per arm (resolves ~20pp), and mechanism metrics
from the downloaded replays (far lower variance than win rate). Built as `tools/ab_ladder.py`.
Logs: `ladder/S1_panel/panel.log`, `ladder/champ_panel/panel.log`.
