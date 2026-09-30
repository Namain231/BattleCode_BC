# HANDOFF — start here (written 2026-09-30, updated later the same day)

> ## LATEST (supersedes the direction below): work on the champion's LATE game
>
> A behavioural read of 184 fresh top-16 replays against our own 30 recent ladder games
> (`insights.md`, "WHAT THE TOP 16 ACTUALLY DO") shows the champion `Y.7.12-nn.1`'s **early game is
> already top-grade** on every rate (eating, net growth, greed, pursuit, breeding) and that every top
> team runs the same bud-at-4-into-2+2 engine. The measurable outlier is the **late game**: we stop
> budding/mining at ~r300 and feed from r350 (`budUntil`, `mineUntil`, `feedFrom`), while the whole
> top field keeps the economy running until ~r390-430. Our late eating drops 35%, late splits are
> 10/1000 dt vs ~25, and **24% of the pearls we feed are never eaten** (top teams: 3-12%).
> Next: consolidate later, feed only beside the queen, keep non-feeding drones greedy -- tested by
> same-time ladder A/B on the champion. Not S4.x, not a rewrite, not sonar, not early economy.
>
> **UPDATE (same day, later): built and gated `viper_nn_late` (schedule shift + feedDist=2 bundled).
> Gate FAILED vs champion (16/40=40%, needs 55%; passed vs V7.5 at 75%). Not submitted.** Paired
> mechanism check on the exact same 40 games shows feedDist=2 alone worked exactly as predicted (feed
> deaths within 2 of queen 41%->94%, recycled-by-us 66%->75%) while the schedule shift barely moved
> anything (near-identical eat rates, split timing 329->347) -- likely because most gate games (40-unit
> cap, some decided by elimination) end before round 380, so the new thresholds rarely engage. **This
> was a bundling mistake: two changes in one candidate, so the gate loss cannot be attributed to
> either.** Split and gated both pieces to check -- **both fail independently, overturning that read.**
> `viper_nn_feeddist` (feedDist=2 only): 17/40 = 42.5%. `viper_nn_schedule` (schedule shift only):
> 20/40 = 50.0%. Neither clears 55%, and neither isolates a clear culprit -- feedDist's real, measured
> mechanism gain (41%->94% feed targeting) does NOT translate to a local win. **Do not iterate further
> on local gate percentage against this champion**: local self-play here has saturated the same way it
> has for every network variant in `ml/results.md` (~50% regardless of the change), and 40 games
> cannot separate signal from that noise. If this direction is revisited, it needs a same-time ladder
> A/B against real opponents, not more local gating. Nothing submitted; champion untouched; full
> detail and all replays in `insights.md`'s last two sections.
>
> **UPDATE (same day, later still): ran the real-opponent test. Refuted, decisively.** Submitted
> `viper_nn_schedule` as `S.1` (id 13197), tested via `strong_panel.py` against 5 real teams (calc,
> SSS, forgot to mention, Stockfish, Cache me outside), champion (`Y.7.12.13`, id 11461)
> auto-restored and confirmed active afterward. **Result: 4/25 = 16%** -- four of five teams lost
> every game; only SSS went 4/5. Worse than the local gate's 50% (noise), not better -- copying the
> top teams' late-game *timing* onto our *mechanism* does not transfer, most likely because our
> swarm's coordination is thin (one hardcoded friend-zero, no gossip/roles) and running it 80 rounds
> longer just gives its failure modes more time to compound. **This closes the late-schedule direction
> as currently specified.** Do not resubmit without explaining the SSS result and a mechanism-level
> reason it should work. Full detail in `insights.md`'s final section.

Read this file, then `insights.md`'s last **four** sections (POST-MORTEM, the CORRECTION,
"THE GAME IS DECIDED BY ROUND 50", and "TRAUMA, DIAGNOSED PROPERLY"). **Everything in `insights.md`
above the POST-MORTEM predates a set of corrections and should not be trusted on its own.**
`S4_7_PLAYBOOK.md` is current except where the POST-MORTEM contradicts it.

> ## Read this before anything else in this file
>
> **`wCompass` is inert, and the hand-written bot has zero validated gains.** Built `viper_vS4.7`
> with `wCompass = 0.0` and ran the identical 24-game batch: **all 24 games byte-identical** — same
> rounds, same termination, same death counts both sides, across 6 maps. Every build in `baselines/`
> has the same structure, so the term has never done anything. The **+8.3pp "only validated gain"
> therefore cannot be attributed to it** — it is either panel noise (+8.3pp sits exactly in the
> measured 7-9pp panel bias) or an accidental side effect of the full-board BFS that shipped with it
> eating CPU and reducing search depth. Sections of this file below that lean on "wCompass is the
> only validated gain, and it lives exactly here" are **superseded**.
>
> **Also superseded: "go after trauma".** trauma's edge@50 is −2.0, the same as autarky's −1.5 which
> wins 50%; trauma is the one map that *breaks* the edge@50 correlation, and its divergence is
> rounds 150–250, not 0–50 (we are ahead 11-6 at r100 in one game and decay to 2 by r450). The maps
> where edge@50 genuinely decides are **slithery_fight (−13.0) and schooltime (−7.0)**.
>
> **The headline on trauma: its every-round fountains are 64 moves away, and `horizon = 48` means
> they do not exist to this bot at all.** Every earlier reading that made them look 5-8 moves away —
> including my own first write-up — was an artefact of the vision-only World treating unseen tiles as
> open ground. With the real walls supplied (`viper_vS4.19`, consensus kelp edges) the true distance
> is 64, never closing below 56, and `gammaFar^64 = 0.0095` would make the pull negligible even in
> range. So trauma's real economy is the 130 near-dead slow beds we trip over, not the 12 fountains.
>
> **And correct terrain made eating 12x worse** (72 → 6 pearls in r0-250): optimistic routing was
> accidentally load-bearing, making dragons strike out boldly and blunder onto slow beds. Treat "give
> the bot better information" as a hypothesis to test, never an improvement to assume.
>
> Four builds this session, all null-or-worse and none shipped: `S4.12` (consensus beds — the only
> keeper, null), `S4.13` (bed belief), `S4.16`/`S4.17` (committed routing, with a real metric bug),
> `S4.18` (committed routing done correctly — right mechanism, wrong map), `S4.19` (consensus kelp).
> Also: `wTarget` is structurally blind to known beds, and v7.12 turns the pearl→body crank 5.5x
> faster (208 splits vs our 38) — but that gap is a *symptom*, not a lever, since our splits are few
> because dragons never reach length 4.
>
> **The measured target, from reading v7.12's source and both sides of the same game:** trauma eats
> per dragon-turn is **0.031 (us) vs 0.056 (v7.12)**. The 6.8x total food gap is 1.8x eating efficiency
> × 3.7x dragon-turns, and at r0-250 it is 1.9x efficiency × 1.25x turns — so **per-turn efficiency is
> the driver** and the rest is what it compounds into. The goal is concrete and modest: **~2x eats per
> dragon-turn in rounds 0-250.** Not a new macro, not consolidation. And not the 12 fountains — at 64
> moves v7.12's own pull toward them is 0.096 with a 0.006/step gradient, negligible for it too. It is
> simply harvesting the same nearby near-dead beds twice as well.
>
> **The biggest single structural difference:** v7.12 keeps *three* discount tables (0.86 field / 0.94
> best-target / 0.80 miners); we apply 0.80 to everything, which caps our effective horizon at ~15
> tiles no matter how far the BFS reaches. It also does all of it in **one** BFS per candidate (so it
> affords `fieldCap=90` where we afford 48), uses a **time-aware** BFS where a tail that will have moved
> is walkable, and evaluates pearl probability **at arrival time**.
>
> **The hard-won rule: our bot and v7.12 are two different coherent designs and you cannot interpolate
> between them one parameter at a time.** Ours is a short-horizon greedy forager whose tempo comes from
> close-range commitment plus one crude but load-bearing coordination device (the hard friend-zero that
> forces dragons apart). v7.12 is a long-horizon planner whose long reach is safe *only because* gossip,
> roles and a queen protocol stop its dragons converging on the same distant target. **Five transplants
> were tried and all five failed:** `wHot` sum→max (null), consensus kelp edges (eating **12x** worse),
> committed routing (null), `friendCloser` 0→0.08 (eating **10x** worse), `gamma` 0.80→0.86 (edge@50
> **10.5 → 7.0**, win 53% → 41%). Each failed because the piece it replaced was compensating for
> something our bot lacks.
>
> Corollary worth keeping: `gamma = 0.80` was set by `param_search` on the discredited 32-game panel and
> is nonetheless **correct**. A biased validation method does not imply a wrong answer.
>
> **The fork, to be chosen deliberately rather than drifted into:** (a) commit to the short-horizon
> forager and improve it on its own terms — two untested items, `pearlProb` evaluated at *arrival time*
> and a *time-aware* BFS (a tail that will have moved is walkable), both of which raise eating efficiency
> without widening the horizon; or (b) build the coordination machinery first (roles, target gossip) and
> only then widen the horizon — that order, because the reverse is what failed five times. (b) is a
> multi-day rewrite; **(a) has a measured target (~2x eats/dragon-turn in r0-250) — start there.**
>
> Full detail and the ranked next steps are in `insights.md`'s last four sections.

---

## The one thing to know

**The game is decided by round 50.** Our population edge at round 50 predicts the result almost
deterministically (128 replays):

| our pop edge @ r50 | n | win rate |
|---|---|---|
| behind 5+ | 31 | 23% |
| behind 1-4 | 30 | 27% |
| ahead 0-4 | 46 | 63% |
| **ahead 5+** | 21 | **100%** |

Per map, edge@50 ranks the maps in win-rate order: devil +5.0 → 100%, dilemma +3.5 → 100%,
default +0.5 → 69%, trophy +2.0 → 56%, autarky −2.0 → 31%, schooltime −7.0 → 25%,
slithery_fight −12.5 → 25%, trauma −2.0 → 0%.

Causal chain: **eating rate → reach length 4 → split → more heads → more eating.** On dense-pearl maps
it cascades and we win outright by elimination; on sparse/contested maps it stalls (trauma: stuck at
4-11 units for 300 rounds while the opponent reaches 32) and we lose.

**So: optimise rounds 0-50. Nothing else has ever worked.** The only validated gain in this project's
history (`wCompass`, +8.3pp) was an early-game eating-rate fix.

## Four things we were doing wrong (all measured, all documented)

1. **Deaths have the inverted sign.** Fewer deaths than the opponent → 20% win (n=785); more deaths →
   84% (n=295). The whole S4.7 rewrite premise ("93% of deaths are self-inflicted, fix safety") pointed
   backwards. Every safety feature built since failed, and that is why.
2. **32-game panel win-rate carries ~7-9pp optimism bias** when used to select changes. Measured three
   times: `swarmChild=4` 53.1%→47.5% (SPRT, 99 games); S4.8 59.4%→50.7% (SPRT, 150); S4.10 53.1% with
   *identical* tempo numbers to baseline. ~11 of 32 panel games flip semi-randomly per change, so a
   "+3 net wins" headline is noise. **Every 32-game "confirmed gain" in the old notes is unvalidated,
   including the shipped `wTarget=4`/`wPredict=0`/`swarmChild=3` "+9.4pp".**
3. **`viper_v7.12` is the wrong yardstick.** It scores ~15% against the real 1700+ field; we score 50%
   vs it and 22% vs the real field. "50% vs v7.12" ≈ 22% real. The old 52.5% promotion bar promotes
   builds that are still ~22-25% on the ladder.
4. **Diagnosis by anecdote, no base rates.** The "Slithery Fight kelp death spiral" was not a bug:
   600-700 deaths is normal there for *both* sides, and the real cause is losing the early population
   race (behind 28v42 by round 50 in all 4 games). Always get the opponent's equivalent number before
   calling something a bug.

## Use these metrics, not win rate

- **`tools/tempo.py DIR [--per-map]`** — population edge at rounds 25/50/100/150. Near-deterministic
  for the outcome, continuous, low-variance, visible 50 rounds into a 500-round game. **This is the
  optimisation target and the test metric.** A handful of games gives a signal; win rate needs 100+.
- **`tools/concentration.py DIR [--quiet]`** — longest-dragon delta and concentration ratio, for the
  36% of games that reach the round-500 length tiebreak. Use the tiebreak subset it prints, never the
  raw median (eliminated teams contribute longest=0 and destroy cross-build comparison — this error
  was made once and corrected).

Standard invocation for everything: `uv run --python 3.11 --with unswbc python tools/tourney.py A B
--judge zig --seeds 2 --maps <CORE_PANEL> -j 4 --keep-replays DIR`. Add `--debug` to `--judge zig`
when you need `BC_DEBUG` log/indicator data in the replay.

## State of the builds

| build | what it is | verdict |
|---|---|---|
| `viper_vS4.7` | the real baseline; 50.0% vs v7.12 (≈22% real) | current reference |
| `baselines/S4.7.4-S4.7.9` | incremental snapshots | history |
| `viper_vS4.8` / `baselines/S4.8` | 4 bundled features (early split, exploreBed, queen tie-break, growWindow) | **SPRT 50.7%/150 games — no effect** |
| `viper_vS4.9` | `splitStopRound=250` | **refuted** — 40.6%, longest went *down* 17.0→15.5 |
| `viper_vS4.10` | feed gossiped global queen first | **noise** — 53.1%, tempo identical to baseline |
| `viper_vS4.11` | `swarmChild` 3→2, first *early-phase* test | **null, 43.8%** — and null on tempo too (see below) |
| `viper_vS4.7_paramsearch2` | param_search scratch dir | 8 hours, several hundred games, **zero validated gains** |

**Nothing from this session shipped.** `viper_vS4.7`'s defaults are unchanged apart from inert gated
features. Last real submission is `S.4.7.6` (idle). Active ladder submission is a teammate's
`Y.7.12.13` maintenance build — a separate lineage, different account; don't clobber it.

## S4.11's result, and the lesson that should shape the next session

`swarmChild` 3→2 came back **43.8%, and null on tempo** (r25 6.0 vs baseline 7.0, r50 10.0 vs 10.5).

**The reason matters more than the result.** My argument was "smaller child → parent keeps more length
→ splits again sooner → faster compounding". That is only half of it: the child is correspondingly
shorter and takes longer to reach 4. A split of a length-L dragon yields two dragons and total length
L either way — **`swarmChild` changes neither the split count nor the total length, only the
parent/child distribution. It cannot move population.** A null was derivable on paper in two minutes.

This *sharpens* the round-50 thesis rather than weakening it: population tempo decides games, but not
every split knob touches tempo. Four of this session's experiments (S4.8's `earlySwarmChild`, S4.9,
S4.10, S4.11) were nulls that mechanism-checking would have predicted.

**Rule for the next session: before testing a knob, verify it can move the target quantity at all.**

## Pick up here

1. **Go after eating rate — how fast a dragon reaches length 4.** That is the only thing that can move
   r0-50 population, and it is the untested space. Levers: `wTarget` (commit to nearest pearl),
   `gamma` (distance discount), `wCompass` (long-range pull — the only validated gain in project
   history, +8.3pp, and it lives exactly here), `exploreValue`, and any safety weight (`wDanger`,
   `wExposed`, `growerDanger`, `spaceFactor`) timid enough to make dragons decline contested early
   pearls. Target the four deficit maps: **trauma (edge@50 −2.0, 0% win), slithery_fight (−12.5, 25%),
   schooltime (−7.0, 25%), autarky (−2.0, 31%)**.
2. **Diagnose before building.** A `BC_DEBUG` trace of trauma's first 50 rounds would show directly why
   dragons sit at 4-11 units for 300 rounds — are they failing to find pearls, declining them on
   safety grounds, or eating too slowly to reach 4? That answer picks the lever. Use
   `--judge zig --debug` (fast, and now records log/indicator events).
3. **Delete the 11 inert params** (`exploreValueDensityFactor`, `wTerritory`, `wChoke`, `kamikazeLen`,
   `probeEnabled`, `chamberCheck`, `wProbeDanger`, `wProbeDangerWallFactor`, `territoryWeight`,
   `exposureMode`, plus `wPredict=0`) and the dead code behind them. They are pure carrying cost;
   `common.hpp` is 57% comments, mostly obituaries.
4. **Do not resume flat-weight parameter search.** Five of five flat-parameter experiments failed under
   proper testing.
5. Re-baseline honestly when reporting: state ~22% real, not 50% vs v7.12.

## Process rules that earned their place

- One change at a time. S4.8 bundled four and the result was uninterpretable *and* null.
- Snapshot to `baselines/S4.x` before a drastic change.
- Always `--judge zig`; the build cache keys on `main.cpp` only, so append a `// rebuild-marker` line
  after editing any header or you will silently test the stale build (this happened this session and
  was caught by the wasm hash being identical to the previous build's).
- Run `tools/bceval_batch.py` on every tournament's replays; shape (dominant/early/late/recovered)
  explains results that win-rate hides.
- Check what is *inside* an aggregate before trusting it. The one error made inside the post-mortem
  itself was a median over a population containing eliminated teams.
