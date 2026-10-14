# Tactics and algorithms: evidence and outcomes

Consolidates the tactical ideas explored in the UNSW Battlecode (Loong) project.
Records each mechanism, its measured evidence, and the decision supported by that evidence.
Separates old-rule results, new-rule experiments, and proposals without demonstrated benefit.

## Contents

- [Rules and evidence](#rules-and-evidence)
- [Sonar and echo](#sonar-and-echo)
- [Queen safety and hunting](#queen-safety-and-hunting)
- [Opening, exploration, and food](#opening-exploration-and-food)
- [Keeper and feeding endgame](#keeper-and-feeding-endgame)
- [Flood fill, corridors, and traps](#flood-fill-corridors-and-traps)
- [Search and calc architecture](#search-and-calc-architecture)
- [Decisions and failed approaches](#decisions-and-failed-approaches)

## Rules and evidence

**OLD rules, before 2026-10-01:** round-500 longest living dragon, then total length; the elected longest dragon was often called a “queen.”
**NEW rules, from 2026-10-01:** round-500 original queen length first (dead queen = 0), then longest living dragon, then total length; free steps = `ceil(L/4)`. Elimination still loses immediately.
Original queens are ids 0/1; a surviving drone cannot inherit queen status. Identify a queen by visible team and `id <= 1`, not by `MY_TEAM` as an id.
The 2026-10-02 audit found dragon 0 on team B in 168/306 games (55%); the old team-to-queen-id helpers were wrong there.

Later completed reports supersede earlier research expectations; the completed 2026-10-07 kamikaze panel supersedes the proposed “always worth one drone” policy.
“Measured” below means the stated corpus or local panel, not a causal ladder gain. “Proposal” means benefit is unverified.
The early top-team corpus comprised 306 games; its trapped-start conclusions are historical, not guarantees for later builds.
The final reports contain no accepted hunger or opening-fix improvement. Their uncompleted plans are omitted.
`reports/queen_guard_build_report.md` was absent; only matching topic entries from `AGENT_LOG.md` supplement the listed sources.

## Sonar and echo

### Ray mechanics and timing

- A dragon can send four unsigned 64-bit words per turn, one each N/E/S/W. Repeating a direction replaces only its own earlier output.
- Sonar casts after the action, only if the sender survives, from the post-move head. A backward ray exits the tail in its outward direction.
- Rays wrap, traverse portals, and stop at the first kelp edge or dragon segment, including the sender's body; an unhit ray expires after `WIDTH + HEIGHT` tiles.
- Reception supplies raw words in send order, without sender, team, or direction. A higher-id recipient reads the word this round; a lower-id recipient next round.
- The sender receives next-turn aggregate counts: kelp, ally, ally_head, enemy, enemy_head. `PROTOCOL 3` is required. Echoes contain no distance, id, direction, or length.
- Vision is 7×7 and does not cross portals. Sonar can inspect a portal lane, but bodies block both sensing and message delivery.
- Sonar itself is free; with one buffered flush, four full-width words cost about 0.46M output points. Extra flushes cost 2.5M each.

`reports/echo_eval_v2.txt` decoded 77/77 games and 22,087 queen records with no failures.
Its reconstruction matched endpoint, hit class, and hit dragon for **4,248,800/4,248,800 real pings (100%)**.
Portal, refraction, sprint-reconstruction, and other mismatch counts were all zero; movement fallback count was zero.
This validates the ray simulator, not the effectiveness of a response policy.

### Attribution and lane inference

A single ray gives an attributable echo. Multiple rays give an aggregate: subtract stops resolved by visible occupancy or known terrain, then infer the unresolved lanes.
A kelp result can certify an unobstructed lane at cast time; moving blockers and a one-turn delay limit its use as a safety certificate.
At L13, four free steps exceed the three-cell vision radius. Blind sprint steps are a particular use case; a flat penalty on every drone is not supported.
The evaluation includes every unresolved non-back lane within FAR=12, including lanes a policy did not cast.
Whole-map terrain and truth-distance masks are privileged upper bounds, not information generally available on unseen maps.
Warnings formed at record i are usable only at later records; precision excludes surviving end censoring.

| Cross-fitted policy | Rays/turn | Lane coverage | Recall / precision | Head-on deaths warned | Warning / no-warning death risk within 5 records |
|---|---:|---:|---:|---:|---:|
| all4 | 4 | 100% | 0.403 / 0.819 | 20/45 | 4.68% / 0.89% |
| three | 3 | 100% | 0.569 / 0.933 | 22/45 | 3.93% / 0.87% |
| fwd1 | 1 | 36.7% | 0.360 / 1.000 | 19/45 | 3.73% / 0.92% |
| adapt2 | 2 | 72.2% | 0.531 / 0.992 | 23/45 | 3.60% / 0.89% |
| oracle | 4 | 100% | 1.000 / 1.000 | 28/45 | 3.14% / 0.80% |
| vision_only | 0 | — | Not an echo policy | 32/45 | 3.25% / 0.72% |

all4 warned 20 deaths versus circular-shuffle mean 6.51, lift 3.07; three 2.53, adapt2 2.64.
The 200 deterministic shifts use offsets ≥20; null intervals describe shuffle variability, not causal benefit or sampling confidence.
`three_nofwd_stale` equaled three after excluding already view-resolved lanes: stale forward carryover added nothing in this evaluation.

### Enemy-ping alarm and friendly reach

`enemy_ping_check.txt`: 222 games, zero failures, 59,692 last-alive queen records; current-round deaths excluded from prediction.
Enemy pings reached the queen in 12.8476% of records; friendly pings in 22.4754%.
Enemy reception rose from 8.7112% before r100 to 18.0717% from r300; friendly reception rose from 14.3375% to 44.7963%.
Head-on risk in the next five rounds was **4.1987% with an enemy ping versus 0.5344% without**.
Using either of the last two rounds gave 3.7134% versus 0.4678%.
91/121 head-on deaths had preceding warnings; for 116 shuffle-eligible deaths, observed 86 versus null mean 38.605, lift 2.228 (null-derived interval 1.910–2.688).
This supports a soft alarm; it does not establish that fleeing improves wins. Payload distributions cover all enemy sonar, not just rays hitting queens.

Hypothetical four-ray friend-to-queen reach in echo_eval_v2 was **45.855%** overall, 51.4% with a friend within eight cells, and 24.9% in head-on death windows.
Map reach ranged from Stripes 4.6% and Tower Defense 16.4% to Maze 73.5%; queen heartbeat silence is unreliable.
The identical two-/three-hop “any friend” rates are true by construction: every final hop is already a direct sender. Relays may expand which friends contribute.

### Authentication, confidentiality, and information leaks

| Mechanism | Evidence | Outcome |
|---|---|---|
| Old plaintext queen gossip | 4,734 queen-gossip and 149 QPOS words landed on enemies in 26 new-rule games using old-lineage code; about 190 reports/game | Reveals actionable queen positions |
| f1 msgauth | 24-bit SipHash tag, 12-bit clear sender id, 3-bit type, 2-bit direction, 23 data bits; auth tests passed, CPU peak 61.1M | Payload sealing still exposed queen identity; relay resealing refreshed stale observation age |
| Sv5.3 secure telemetry | Masked QPOS, STATUS relays, guard/echo/ping hooks | Built; isolated ladder benefit unverified |
| L10 legacy secure packet | Plaintext low 48 bits plus 16-bit SipHash tag | Signed, not confidential; coordinates, length, id, and source round remain readable |
| Proposed msgauth v2 | No clear sender; preserve observation age; authenticate absolute observations | Design only; benefit and estimated CPU unverified |

The proposed v2 SIV-style layout uses tag16/type4/cipher44; its combined situation report carries own/enemy queen positions, ages, own length bucket, and death flags.
The research estimated about 0.1 random accepted forgeries/game with 16 bits and 3,000 attempts/two rounds, versus 0.006 with 20 bits; these are model estimates (unverified).
Encryption does not hide ray geometry. Authentication does not conceal plaintext fields. Relays must retain the original observation time.

Stockfish's intercepted words decoded to its exact current sender head in 79% of cases; opponents received about 989 words/game, including 13.4 queen words, median distance 10 and median round 42.
horse exposed a 12-bit sender id at bit22 in 66% of words; Stockfish used seven-bit x/y at bits53/46. These historical formats are not permanent specifications.
An online format learner requiring ≥5 geometrically/visually consistent decodes was proposed; no in-game benefit was measured.
In 324 games no team was observed replaying an opponent's word. Jamming by overwriting another dragon's sonar is impossible; physical interception is possible.
Active spoofing legality was not verified against separate competition terms; the research recommended organiser clarification before shipping an attack.

Parent rays reached newborns in the split round on 55–62% of splits for four-ray teams, versus 9% for ours.
A newborn has no parent memory; a backward-ray handoff of food or queen observations is a proposal. Which ray caused those deliveries was not verified.

## Queen safety and hunting

### What kills queens

The 2026-10-02 top-team sample had 554/612 queen deaths: winners 252/306, losers 302/306; median death rounds 31 and 57.5.
After r10, 139/350 deaths were incoming enemy rams (40%), 42 queen-initiated head-ons, 75 wall, 39 self, 29 other body, 20 allied head-ons, and six no-valid-action.
Of 148 incoming rams across all rounds, 127 killers were L2/L3; 76/139 post-r10 rams needed paid steps.
Ordinary dragons' incoming-ram share was 8%. Queen-targeting intent remains an inference unless code or a specific policy proves it.

The later Sv5.3 loss dive (2026-10-04) reconstructed 224 replays without movement, tail, or result mismatch.
Of 89 losses, 83 had queen deaths, 66 head-on; all 12 representative head-on queen deaths were incoming rams.
Nearby allies did not guarantee protection: Trophy game1045337 r42 had five friendly heads within radius6 when an L3 enemy used SE to ram the L3 queen.
Other losses were pockets: three walls plus own neck, or two walls plus self plus an ally sealing the last exit. Tails do not strike stationary victims; body collisions kill the mover.

### Reach, anti-ram, and rescue

Without eating, `R(L) = ceil(L/4) + L - 2`: L2/3/4/5/6/8/11 reach 1/2/3/5/6/8/13 walking steps.
A seen enemy queen has already acted before a drone's turn; a fully modeled affordable route to her current head can be checked exactly, including portals and own-body movement.
Older `findAttack` capped enumeration at four steps and `MY_LEN-1`, missing L5+ reach; BFS was proposed instead of exponential `4^k` enumeration.
Early “homing never fires” claims were narrowed: occupied-head `distA=-1` affects close visible fixes; message-only fixes outside vision can still home. Target a reachable free neighbour.
Exact terrain-aware paid-step threat masks were proposed for queen landings; free-step-only reach understates enemy ram capability.

Nv31a's `queenAntiRam` uses existing enemy reach to avoid threatened landings. Versus Y9_6 on matched seeds/sides, Nv30 scored 42/98 and a 48/98.
Queen deaths stayed 90/98; median death round rose 199→222.5, units100 24.1→24.5, eats/round stayed 0.92; peaks 65.251M→65.269M.
This is a provisional local gain without demonstrated reduction in deaths or accepted promotion; confirmation and ladder effect were not established.

`queenAmputate` and QBOX-SHED split a boxed queen to create room; shared Sv5.2/3/L10 assumptions require the child to move before her next turn.
L10 recorded 135 AMPUTATE and 294 QBOX indicators; these are activations, not proven rescues.
Child occupancy is only partially modeled and enemy future actions are uncertain: amputation is a fallback heuristic, not a survival proof.
Sv5.3 guards penalize introduced exit obstruction and assign interceptors. The 2026-10-04 build smoke was 3/4, CPU peak 64.451199M; freeze was OFF and echo penalty 12 points.
Global interceptor caps with partial observation, unknown enemy sprint lengths, moving blockers, and post-split posteriors remained unverified.
Historical loss replays show guard insufficiency, not that guards caused deaths; intercept selection lacks identifying tags.

### Kamikaze: completed rejection

`viper_y96nk` copied `baselines/Nv30`; audit modeled wrap, portals, kelp, occupancy, own body, pearls, and up to two affordable paid steps.
Upper-bound opportunities appeared in L10 294/752 (39.1%), Sv5.3 62/147 (42.2%), Sv5.2 33/77 (42.9%); fully visible routes in 286/61/32 games respectively.
Opportunity-round p50/p90/p99 per game were 0/1/5, 0/2/5, and 0/2/3. Existing tagged attacks already killed queens in 367 corpus games.
Reverse audit found L≤4 enemies ramming our queen in 414/976 games, length quantiles 3/3/4; three portal routes.
The candidate required current proof of ally queen life, or complete visible allies plus a length-based fallback condition; unknown own body/intermediate occupancy rejected paths.
Early trades were restricted to L≤4 unless enemy visible length ≥2× scout; from r150 any scout length with current ally-queen proof. Paid cap L12, search 2,048 nodes/40ms; chase OFF.

| Matched 98-game panel vs Y9_6 | Wins | Verified queen ram kills | Own queen deaths | CPU peak |
|---|---:|---:|---:|---:|
| Nv30 control | 42/98 (42.9%) | 64 | 90/98 | 65.251M |
| Kamikaze candidate | 36/98 (36.7%) | 8 | 90/98 | 65.199M |

C++ decision plus engine_sim ram/four-rejection fixtures passed; audit reconstruction errors were zero, with three missing/identity rows excluded.
Counts used candidate K1 versus control ATK queen-id tags, verified by same-turn head-on deaths; restrictive legacy-attack guards explain why this was not simply adding more attacks.
**Decision: drop**, -6.1pp versus Nv30; no growth sacrifice justified by this panel. Rates have roughly ±5pp standard error/±10pp at95%; ladder and chase benefits remain unverified.
Tools: `kamikaze_measure.py`, `kamikaze_unit.py`, `kamikaze_run.py`, `kamikaze_report.py`; outputs `out/kz_panel`, `out/kz_ctl`.

## Opening, exploration, and food

### Census: extraction, not just first split

The post-2026-10-02 census compares ours with winner-only top-team games, equally weighting 17 map medians; selection, opponent, side, and version confounding remain.
Snapshots are start-of-round; eats cover r0–99, splits r0–49. Early terminal states carry forward while the eat denominator stays100.

| Median of map medians | Ours | Top winners |
|---|---:|---:|
| Units r50 / r100 / r200 | 9 / 15 / 19 | 14 / 20.5 / 35.5 |
| Total length r50 / r100 | 20 / 37 | 36 / 50.5 |
| Splits50 per starting dragon | 2.33 | 4.60 |
| Eats/round | 0.57 | 0.92 |
| Corpse pearl share | 20% | 27% |
| First split, excluding never-split | r0 | r0 |

Map-specific units100/eats per round, ours→top: Stripes 1.5→12.5 /0.01→0.69; Tower3→14.5 /0.04→0.46; Dilemma4→13.5 /0.12→0.68; Devil10→30 /0.57→1.75; Islands29→49 /1.20→2.10; Portals16→28 /0.64→1.71.
Around UNSW matched units10060.5 but lagged length145.5→180 and eats2.62→3.19. Schooltime/weakhold were not universal deficits.
“Stuck” includes late newborns/dead units with ≤3 successful steps before r50; the escape measure is outside graph-radius4 around initial heads, not a literal box exit.
Sv5.3's exclusive loss diagnosis found early unit deficits in52/89 losses; L10 in231/397. These describe timing, not proof of cause.

### Pearl field, wrecks, and hunger

The old-lineage move scorer discounts pearls by real walking distance (`gamma`), alongside danger and flood-fill survival; old tuned values require new-rule validation.
L10 increased contested-pearl values: enemyCloser0.55→0.85, enemyTie0.8→1.0; wCompass0.8→1.6, routing all L≤6 drones with ≥2 units before r150 instead of one third with ≥6 units.
This compass benefit needs recognized map tables; it does not generalize automatically to unseen maps. URISK19 scales small-drone head danger×0.6 at ≥8 units; QSAFE triples queen danger penalties.
The historical Trophy motivation was10 versus124 centre-pearls eaten at r50–100; it is a case observation, not causal validation of the new weights.

Corpse recovery is material: Sv5.3 versus tungtung67 ate3,323 corpse pearls versus6,971, and versus avid coders4,475 versus7,860.
Nv31c `wreckExtend` admits L≤6 miners and favors current pearls on recently vacated occupied cells. This is a corpse-site proxy; death attribution and measured benefit are unverified.

Hunger candidate `viper_nv30h` uses `viper_nv30k` (Sv6,id19955) as control: stronger unseen/unwalked food priors, recent-head-visit penalties, and sticky frontier goals.
Worker grace8, frontier length cap6, visit window30; birth/growth/eat/split reset hunger, paid shrink does not. Ordinary known-open BFS runs at most once per four turns; portal safety unchanged.
Queen grace15/ramp60, hunger≤0.6, mild safe-region/retrace terms, no frontier pull; OFF from r100 or enemy within8.
Judge build, production scorer/engine_sim fixture, and attribution fixture passed. **No completed mechanism/sensitivity/safety result; benefit unverified.**
The extra panel specification is16 games (four maps×two seeds×two sides), not28. Metrics use start-turn L≤6,r0–149; lifetime/exposure confounds unique-visit/streak averages.
Tools: `hunger_unit.py`, `hunger_metrics.py`, `hunger_metrics_check.py`, `hunger_run.py`, `opening_census.py`; data `F:/BC_hunger_20261008/`.

### Failed hand-coded recipe and exploration

`viper_y96qo` used food/renewal flood routing, ally discount, stagnation K6, split2 with known exits, worker separation, boxed-worker unwind, and a constrained queen-food hook through r119.
Winner traces usually grew toL4 then split2; some grewL5/split3. Stripes example: S,E×8,N,E,split2 at r11, child immediately W. No universal fixed-box exit was verified.
Portal override required an unambiguous prior probe and zero echoes; STATUS rays often inhibited it after r12. Legacy PEXPLORE remained.

| Panel | Control | Recipe revisions | Outcome |
|---|---:|---:|---|
| Closed64 | 39/64 | R1 29; R2 28; R3 26/64 | Failed |
| Safety98 | 59/98 | R3 50/98 | -9.18pp, failed5pp limit |
| Closed halfway economy targets | Four maps | R1/R2 0/4; R3 1/4 | Failed |

R3 closed units100/first-split medians: Stripes6.5/r42→11.5/r11; Tower4/r41→3/r50; Spades6.5/r14→7/r12; Dilemma6/r0→5.5/r0.
Safety wins control→candidate: Around10→7, Australia5→4, Islands9→6, Maze8→8, Stripes12→14, Tower6→0, weakhold9→11 (14 games each).
CPU64.802M→64.648M passed≤66M, but population preservation failed4/7 maps. Static review passed; acceptance failed. No promotion.
Opening-fix ablations on16 open games: original7/control9; disabling cycle9, queen-food6, split7, separation8, portal8. These tiny screens do not establish causes.
The composed fix passed syntax/assertions only; runtime/CPU/benefit unverified. Tower routing loss and Australia/Islands wall/self increases remain diagnoses, not isolated causes.
Unknown-map exploration must preserve portal topology; vision cannot certify the destination. A fresh probe for each ambiguous crossing was proposed, including intermediate sprint steps.

## Keeper and feeding endgame

In20 historical r500 games with one surviving queen, that team won; six losers had the longer longest dragon. Both queens were dead in118/142 r500 games.

| Queen state | Research macro | Evidence status |
|---|---|---|
| Both alive | Feed/protect true queen; consider enemy-queen hunt | Correct score target; hunt policy needs measured costs |
| Ours alive, enemy dead | Stop feeding/crowding; hide queen and preserve units | Proposal; elimination remains a loss |
| Ours dead, enemy alive | Hunt enemy queen; preserve longest as fallback | No succession; all-in efficacy unverified |
| Both dead | Protect/feed longest keeper, then preserve total | Score target supported; election protocol proposed |

Old y7 feeding/protection elected the longest, appropriate to OLD rules. vB19/f1 true-queen-only feeding left no sink/protected grower after queen death.
The proposed both-dead keeper uses longest friend seen/heard within40 rounds, lower-id ties; feed only a visible friend≥max(10,2×own length), with UNITS>10.
Proposed remote claim hysteresis: challenger≥2 longer, target held≥10 rounds, claim age≤8; split protection preserves the potential sink.
The FLOOR came from an old-rule feeding collapse22→6 units among62 enemies, followed by elimination; it is a cautionary case, not a validated new-rule threshold.

Y9.6 QFEED/QROOM makes the true queen the sink fromr280, with true-queen plus GROWER protection fromr200 (topic-specific 2026-10-03 log).
L10 retains qfeedFrom280, authenticated queen gossip fromr300, queen spacing and legacy QPOS rays fromr200.
Death transfers pearls, not full length: ceil(L/2) alternating-body drops; repeated feeding can discard mass and workers while crowding the queen.
Sv5.3 loss windows confirmed53 FEED deaths, eight atL>4; L10 recorded11,180 FEED indicators. Untagged noaction must not be called feeding or timeout.
A feed-sacrifice capL4 was proposed after chains includedL5 andL11 donors; no measured cap benefit is reported.
Death notices/keeper claims need witnessed evidence and age-preserving relays. Heartbeat silence alone cannot justify irreversible death belief; queen input lacks a global life/longest census.

## Flood fill, corridors, and traps

The 2026-10-01 algorithm note proposes turn-layered survival space rather than static area alone: an L20 queen hasfive free steps; 40 cells represent roughlyeight turns at maximum pace.
That estimate and a two-turn-area≥L criterion are reasoning, not a proven invariant. Dynamic tails, paid shortening, portals, other actors, and voluntary slower movement matter.
Drone trap risk should be a penalty with escape options; queen filters must avoid trading safety for certain starvation.
Dead-end trees and Tarjan cut vertices decompose chambers; edge count distinguishes open space from a same-area corridor. Checkerboard parity bounds were borrowed from Tron research, not validated here.

Nv31b `trapMap` caches optimistic terrain, peeled branches, and directional Tarjan entry-pocket area/cycle bounds. It applies a soft drone penalty; dynamic safety outranks static risk and exits remain allowed.
Native/WASM fixtures passed depth5 corridor, area3/L6 pocket, short cycles, entry/exit edges, unresolved portals, unknown4096 cells, terrain-cache change, timeout recovery, and all-moves-trapped cases.
Sampled rebuild peak1.019M points. Versus Y9_6, b scored51.5/98 versus Nv30 42/98; queen deaths92 versus90, median207 versus199, units10024.1 and eats0.92 unchanged.
DOOMED/escape counts10,772 versus10,932; full target comparison/confirmation and promotion not established. Optimistic unknown terrain misses traps; block size is only an upper bound on longest cycle.

Slithery trace (2026-10-03): L25 queen head surrounded by own indices1/3/5/7; split23 leaves parentL2, then self-death r1 in6/6 local and8/8 ladder games.
The child has not necessarily freed an exit: it needs2/4/6 steps to vacate indices3/5/7 before the next queen turn. Changing tables did not fix this.
A sampled spiral game had287 wall and216 self deaths, mainly afterr20; over-budding L<4 workers had no escape split.
Coordinated child uncoiling and corridor room tests were proposals; later corpus outcomes must not be replaced by this historical start trace.
Dilemma trace lost0/6; own unitsr3001–8/r4001–3 versus10–18/15–24. Self4–16, wall4–18, head-on7–15 deaths/game were large costs for a5–10-unit population.

Other algorithm proposals remain unverified: weighted Voronoi arrivals ceil(distance/free speed), zero value for mutually lethal ties, cut-vertex escort assignment, greedy role allocation, and bounded joint-action hill climbing.
The early note incorrectly generalized that every escort acts after every enemy drone; ids interleave. Only queen-first order is guaranteed, so escort timing must use actual actor ids.
Length slack `d(L)=(L-1) mod4` measures paid segments before the next free-speed drop; L12 has3, L9 zero. Suggested queen residue0 and one-shot hunter residue1 policies were never validated.
A shared turn-layered `(cell,L)` route planner with Pareto pruning was proposed; two entries/cell are a heuristic approximation. Growth and portals invalidate simplistic monotone-length/torus-distance guarantees.

## Search and calc architecture

**OLD-rule calc writeup:** sonar shares observations; a small net proposes legal candidates; short simulated rollouts check them; explicit rules override known blind spots.
Its256/128 MLP reads local view, downscaled remembered map, length/round/unit/split scalars; outputs direction, split size, and sprint continuation. Training details belong in the net documentation.
Only the first move branches. Candidates above a probability threshold getthree-round rollouts (five in opening), with both teams controlled by the same net; score is own-minus-enemy total length.
Unknown actors are absent, unknown tiles open; spare compute goes to UCB1 randomized rollouts. Ties retain the net move. The writeup reports parity-tested C++ engine simulation.
Rules handle hidden food, unexplored portals, symmetry memory, boxed-dragon splitting, least-bad collisions excluding allied heads, and late keeper/feeding/hunting.
All-four-ray packets carry keeper claims, enemies, ruled-out symmetries and explored portals; calc describes encryption and signing. This is architecture evidence, not an audit of its cryptography.
Calc reported deeper search and learned search evaluation gave no improvement; about+5pp local usually became+1.5–2pp ladder (OLD-rule self-report).

Our FSPRINT enumerates free two-/three-step paths; SEARCH1 vetoes traps. Queen-only complete-information search was ineligible under7×7 vision.
The 2026-10-04 topic log reports ON45/80 = OFF45/80, identical per map,77/80 queen deaths each, andzero overrides on20 dev maps×two seeds×two sides.
After fixes,240 random plus10 hand differential cases passed, max call0.26ms; Australia example127 triggers/397 calls, **eligible0**, all rejected for unknown geometry/unseen actors.
**Decision: park that specification** unless redesigned with beliefs over unseen actors. Triggering a search is not evidence that it influences play.
The algorithm survey favored exact one-ply reach/evaluation over deep MCTS/maxn/minimax; external-game results motivate it but do not establish a Loong gain.
CPU admission guards are not hard bounds: minimum option evaluations, flood fill/field construction, uninterrupted inference and per-size amputation evaluations can exceed admission estimates.

## Decisions and failed approaches

| Idea | Evidence and outcome |
|---|---|
| OLD pearl gossip | +37% early eating, ladder15/30 versus16/30: null; known-map tables reduce information value |
| OLD choke/lane messages | T_CHOKE rarely triggered,5/8 maps byte-identical; champion lane test22/42 neutral |
| OLD flat probe danger | 43.8% versus50% overall; Slithery0→50%, other maps lost25–50pp: no global adoption |
| OLD replay attack, submission9298 | 5/30 versus4/30: no effect; enemy inbox overwrite impossible |
| Sv5.3 guards/status/echo bundle | Fresh98:44 versus Sv5.2 48; combined196:103 versus102, no measurable gain (2026-10-04 log) |
| Queen-only complete-information search | No eligible calls/overrides: no-op, parked |
| Hand-coded opening recipe | Safety50/98 versus59/98; Tower0/14 versus6/14: rejected |
| Kamikaze candidate |36/98 versus42/98, no queen-survival gain: drop |
| Nv31 anti-ram / trap / wreck | Provisional screens or fixtures only; no accepted ladder improvement |
| Hunger / opening-fix composition | Mechanism implemented or syntax checked; benefit unverified |
| Hamiltonian / simple tail chase / uniform-cost JPS | Survey advised against direct transplant; multi-agent partial vision, variable sprint budgets and portals break assumptions; no Loong rejection experiment |

L10's2026-10-07 audit:355/752 wins47.2% versus Sv5.3 58/14739.5% and Sv5.2 29/7737.7%, but mean opponent Elo1697 versus1780 for Sv5.3.
Shared-opponent L10 advantage shrank to+2.9pp (95% -10.4,+15.7); equal-weight shared opponent/map comparisons favored older builds. Historical data cannot causally rank them.
L10 queen deaths503/752, medianr183,355 head-on; live peak66.083242M versus Sv5.3 66.162092M and Sv5.2 65.131331M. No hard worst-case CPU bound.
The four-game big-map smoke was0/4 and all queens died head-on; both enemy queens also died, so longest/total decided those losses.
That audit recommended conservative Sv5.2 for unknown-map qualifiers, not a proven best build or champion change. Local half-draw scores must not be mixed with strict ladder wins.
The useful distinction across these experiments is validated mechanics, observed failure modes, and controlled benefit: the first two do not imply the third.

Sources consolidated: tools/tasks/docs_merge/COMMON.md; research_new_meta/algorithms.md; research_new_meta/sonar_echo_tactics.md; research_new_meta/queen_succession_and_hunt.md; research_new_meta/slithery_dilemma_trace.md (tactics only); calc WRITEUP.md; reports/kamikaze_report.md; reports/hunger_report.md; reports/echo_eval_v2.txt; reports/enemy_ping_check.txt; reports/opening_census.txt; reports/sv53_losses.txt; reports/l10_analysis.txt; reports/opening_recipe_report.md; reports/opening_fix_report.md; reports/nv30_improve_report.md; guide/2_how_our_bot_works.md (old pearl scorer); AGENT_LOG.md (topic matches only: y96_analysis, queen_guard_build, queen_search_result). Original files retained; missing reports/queen_guard_build_report.md skipped.
