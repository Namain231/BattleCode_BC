# Game knowledge: Loong mechanics, maps and ladder evidence

A compact reference for what decides games and what our measurements support.
Separates OLD rules before 2026-10-01 from NEW queen and sprint rules.
Preserves dated results, limitations and yardsticks; no new matches were run for this consolidation.

## Contents

- [Rules and execution](#rules-and-execution)
- [Mechanics and numbers](#mechanics-and-numbers)
- [Maps and closed starts](#maps-and-closed-starts)
- [What decides games](#what-decides-games)
- [Opponents and build results](#opponents-and-build-results)
- [Measurement lessons](#measurement-lessons)

## Rules and execution

Newest dated evidence takes precedence: 2026-10-03 traces/Y.9.6 and 2026-10-05–07 insights supersede early strategy recommendations and the old champion yardstick.

| Topic | OLD: before 2026-10-01 | NEW: from 2026-10-01 |
|---|---|---|
| Round-limit winner | Longest living dragon, then total length, then draw | Fixed queen length (dead = 0), then longest living dragon, then total length, then draw |
| Sprint free allowance | One step | f(L) = ceil(L/4), using length at move start |
| Extra-step cost | One segment per step beyond first | max(0, steps − f(L)) segments |
| Queen meaning | Bot-elected longest/feeding sink | Official initial dragon id 0 or 1; split parent retains id; no official successor |

- Games have 500 rounds, indexed 0–499. “r500” denotes the round-limit result.
- Two teams, up to 64 living dragons each; dragons act sequentially in ascending id.
- Split children receive the next unused id and act later in that same round.
- Queens act before all later-id drones. A seen queen cannot move again that round, but can die before a receiver acts.
- Queen identity requires team plus starting id; do not assume MY_TEAM alone maps correctly to id.
- Queen death does not end a game. Elimination of all a team's dragons does.
- Lower tiebreaks apply when both queens are dead **or living queen lengths tie**.
- Killing an enemy queen is valuable, but does not guarantee victory if ours is dead too.
- Each dragon is a separate process with persistent local memory, no shared memory; newborns inherit no parent memory.

## Mechanics and numbers

### Movement, collisions and splitting

| Length L | NEW free steps | NEW no-growth payable reach L−2+f(L) | OLD reach L−1 |
|---:|---:|---:|---:|
| 2 | 1 | 1 | 1 |
| 3 | 1 | 2 | 2 |
| 4 | 1 | 3 | 3 |
| 5 | 2 | 5 | 4 |
| 9 | 3 | 10 | 8 |
| 12 | 3 | 13 | 11 |
| 16 | 4 | 18 | 15 |
| 40 | 10 | 48 | 39 |

- Reach formula assumes no growth and a legal path. Walls, portals, own body and intermediate occupancy matter.
- Every sprint step checks collisions and eats pearls; NNE and ENN can have different outcomes.
- Own body, including the tail, blocks a destination **before** the tail advances.
- Entering another head kills both dragons regardless of length; entering its body kills only the mover.
- Paid steps require enough length to remain at least 2. Overlong requests are not truncated: the dragon dies when payment fails.
- Eating during a sprint can change available length; it does not change that move's initial free-step allowance.
- Split is the whole action, so the parent stays put. Rear segments reverse; the old tail becomes the child's head.
- Parent and child must each retain at least 2 segments and the team must be below 64 units.
- Illegal split, including SPLIT 1, kills the parent; missing/invalid action, crash or timeout also kills.
- MOVE and SPLIT overwrite each other: only the last action command is applied.
- A split can stall a trapped queen, but repeated shedding requires length and an actual child escape route.

### Pearls, corpses, kelp and portals

- Pearls are the only growth resource: eating one prevents ordinary tail retraction and adds one segment.
- No pearls initially in the summarized mechanics; listed bed countdowns start from hidden per-tile gap ranges.
- Countdowns decrement at round start; at zero, an empty tile spawns, then redraws uniformly from its hidden min/max gap.
- Occupancy prevents that spawn but still resets the countdown. Unlisted/nonspawning tiles report −1.
- Symmetric tiles share countdowns; only empty counterparts actually spawn.
- Countdown c observed at round r predicts r+c if the tile is empty under the summarized convention.
- Death crystallizes every second segment from the head: ceil(L/2) corpse pearls.
- Intentional invalid actions can feed a queen; the pearls must still be collected.
- Head-on resolves the struck dragon's death first, then the mover's; remaining sprint and sonar are discarded.
- Kelp and portals occupy **edges**, including wrapped border edges. Crossing kelp kills.
- Portals pair edges of the same orientation, work from either side and preserve corresponding travel direction.
- Vision does not see through portals; movement, bodies and sonar use the teleport.
- Geometry tools must model portal exits, not treat portal edges as ordinary open edges.

### Vision, sonar and protocol

- Maps are toroidal, width/height 10–64, with vertical, horizontal or rotational symmetry.
- Coordinates start top-left, x right and y down; every distance/path calculation must wrap.
- Vision is a wrapped 7×7 window (Chebyshev radius 3); tile queries outside it return no visible tile.
- Visible body records contain team, id, position, facing and head status.
- Protocol 3 permits four directional unsigned 64-bit sonars, one per direction; last in each direction wins.
- Rays stop at first kelp or dragon part, including allies/self, pass portals/wrap, and expire after WIDTH+HEIGHT travel.
- A ray opposite facing exits through the tail in its direction (Total Internal Refraction).
- Sonar casts after a surviving action; death cancels it.
- Receipt is at the recipient's next turn: same round for higher id, next round for lower id.
- Messages carry no engine-authenticated sender/team identity.
- Echo categories are kelp, ally, ally_head, enemy, enemy_head; they do not reveal queen identity, length or distance.
- F1b tested authentication, tamper/expiry rejection, delivery and preservation of original observation age.
- Those correctness checks do not prove win improvement, all tail cases or adversarial inbox safety.
- Sender metadata/traffic can still expose queen identity; indicators and sonar formats are public in replays.
- Terrain sharing versus encrypted position/destination sharing is a research proposal, not measured strength.
- Silence is suspected death, not confirmation; queen-death claims need freshness, refutation and current occupancy.

### CPU and sandbox limits

| Measurement | Sample/context | Points |
|---|---|---:|
| Hard per-dragon-turn kill budget | Project mechanics/playbook | 100M |
| Output cost | Per write, plus bytes | 2.5M + 4,000/byte |
| V7.12 OLD profile | ~105k turns | mean 4–7M; p99 <10M; max 59M |
| vB19 2026-10-02 audit | 20 games | max 76.876136M |
| F1 final H2H | A / B | 74.716414M / 70.520927M |
| Later vB19 / v6 bot | Big-map panels, 2026-10-03 | 98.8M / 96.5M |
| Y.9.6 | Australia/Around UNSW; Islands; Maze | 73.0M; 69.7M; 60.7M |
| CPU-fix candidate | 2026-10-03 sampled peak | 53.4M |
| opening_recipe | 2026-10-06 sampled peak | 64.648M |
| Kamikaze fresh smoke | 2026-10-07 | 63.741005M |

- Historical target is complete-turn max ≤65M; later parameter-search evidence specifies ≤66M.
- Sampled maxima are not bounds. The older “room for 10× thinking” claim is not supported for later builds.
- Schooltime normally disables the net, yet produced the ~77M peak: inference alone does not explain CPU tails.
- Input/init/output partly sit outside think's elapsedMs clock; optional searches need cumulative budgets and valid fallback.
- Memory limit reported in the playbook: 48 MB per dragon; V7.12 used ~1 MB.
- WASM has no usable network, subprocess, threads or writable disk; /bot is read-only.
- Clock is virtual CPU time. Sandbox random streams are per-dragon/per-game and support deterministic replay.
- Mechanics summary lists Clang 20 C17/C++20, -O2 -msimd128, and Python 3.13 plus NumPy.
- “Roughly 25 ms” in the summary is approximate; point accounting is the decisive budget.

## Maps and closed starts

| Historical live map group | Names / portal counts reported in OLD playbook |
|---|---|
| Open-map tuning group | Portals, Slithery Fight, Schooltime |
| Maze panel | Trophy 1, QoS 2, Default 12, Dilemma 4, Autarky 8, Devil 0, Trauma 6 |

- Portal counts are historical map facts, not a guarantee about current variants.
- The pool was 10 known maps at the 2026-10-01 API check; later 2026-10-04 scout covered all 17 live maps.
- Known geometry/name does not establish exact pearl-gap tables for current variants.
- STATUS reports author-found table failures: Dilemma 20/40, QoS 14/40, Devil 16/40, Schooltime 23/40, Slithery 19/40.
- These are author evidence, not reproduced table validation; direct table check covered only one Autarky replay.
- Old gen_random_maps.py kelp/bed-gap/portal distributions need revalidation after the rule change.
- strategy.md start-distance estimates ignored kelp: Default/Colosseum distance 2 and Slithery distance 18 are lower bounds, not legal strike proofs.
- Its early Slithery “25-long non-queen” description is superseded by the 2026-10-03 trace identifying both L25 queens.

### Slithery Fight: closed coil (2026-10-03)

- Queen 0 starts head (3,22), L25, in a closed spiral; all four neighbours are own body (indices 1, 3, 5, 7).
- Sv5.1 r0 ESCAPE-SPLIT 23 leaves queen L2 and child L23 at old tail (1,24).
- At r1 the queen moves into her body and dies: 6/6 local games and 8/8 ladder games, both queens.
- Child body still surrounds her when queens act first. Child needs ≥2/4/6 r0 steps to clear indices 3/5/7; L23 has six free steps.
- No coordinated uncoil exists in the traced behavior; L2 queen cannot split again.
- Both old and new tables gave r1 queen deaths in 6/6 each: this was not a table problem.
- Sample game had 287 wall +216 self deaths, ~500 total; almost all after r20.
- Death bins: r21–100 83, r101–250 263, >250 153, from over-budding/trapped short drones in one-wide corridors.
- Simulated child uncoil, retained queen length and room-aware budding were hypotheses, not verified fixes.

### Prisoners Dilemma and other closed starts

- 2026-10-03 Sv5.1: 0/6 versus Y.9.6 with either table regime; queen starts L3.
- Ours units r50/r100/r200: 5–8 / 5–8 / 5–10; opponent: 6–8 / 6–7 / 6–13.
- At r300/r400: ours 1–8 / 1–3, opponent 10–18 / 15–24; end ours 0–3, queen head-on death r190–470.
- Per game self deaths 4–16, wall 4–18, head-ons 7–15 are substantial for such a small population.
- By contrast Default wins 5/6, with 16–25 units r100 and 25–45 r200.
- Bed access, portal exploration and dead-end avoidance are untested explanations for Dilemma's stalled economy.
- Y.9.6 PEXPLORE addresses unknown portal partners: hungry L≤4 drones after 12 nongrowing rounds target unexplored portals.
- Its Stripes comment records a 24×12 portal-only pearl-box loss, 4 pearls versus 60.
- QBOX-SHED addresses an L4 queen trapped in a 2×2 Schooltime box at r0.
- SELFTRACK trusts exact move history after visible body-chain mislinks; comments cite Slithery L55/L29 self deaths.
- 2026-10-06 opening_recipe improved Stripes units@100 6.5→11.5 and split timing 42→11, but only 1/4 halfway targets.
- It lost population on Around UNSW, Australia, Maze and Tower Defense; no universal box exit was verified.

## What decides games

### Early NEW-rule local evidence: inherited bots, not the whole meta

numbers.md analyzed 59 replays: 31 initial, 14 gQ, 14 gQ2; NEW unswbc 1.2.3, OLD 1.2.2.
Winner reconstruction matched 59/59 and end counters 118/118 team-games; raw r5 deaths were checked.

| NEW-engine group | Games | Reach round limit | Elimination | Deciding criterion at limit |
|---|---:|---:|---:|---|
| gP/v7_12 plus self-play | 21 | 17 | 4 | Longest in all 17 |
| gQ versus gP | 14 | 9 | 5 | Longest in all 9 |
| gQ2 versus gP | 14 | 10 | 4 | Longest in all 10 |
| Total | 49 | 36 (73%) | 13 | Both queens dead in all 36 |

- Across OLD+NEW 118 team-games, only 2 queens alive at end, in elimination games r119/r194.
- All 84 queens in 42 round-limit games died; median death r58, range r5–367.
- Queen deaths: head-on 60/116 (52%), self 26 (22%), wall 21 (18%), body 9 (8%).
- 53 deaths before r50, then 26/19/9/5/2/1/1 in successive 50-round bins through r399.
- All 18 early-panel Dilemma/Slithery games produced r5 deaths for all four bots (36 team-games).
- This r5 finding is specific to those bots/replays; later Sv5.1 traces show Slithery r1 and Dilemma much later deaths.
- Only 1/102 team-games reaching r340 retained its queen then; that queen died r367.
- gP r100 queens alive 18/50, mean surviving length 2.6 and own-team rank 8.1 among 29.3 dragons.
- At r250 only 3/42 alive; r400 0/38. Sampled queen peak mean 7.0 versus team-longest peak 19.4.
- The early claim “queen rule inert” describes this sample, not a durable rule/meta conclusion.
- Later top-win census in STATUS: 118/142 round-limit wins had both queens dead; six living-queen wins beat longer opposing non-queens.
- That census is conditional on top wins reaching r500; it is not a frequency over all ladder games.

### Economy, consolidation and fallback

| Experiment | Outcome | Reason / decision |
|---|---|---|
| gQ fixed-id-only gossip | 3–11 vs gP; 0–9 at limit, 3–2 elimination | Removed fresh fallback sink and late consolidation; not a valid queen-strategy verdict |
| gQ end vs gP means | units 26.8 vs 10.0; total 155.9 vs 70.9; longest 11.5 vs 20.4 | More mass/population could not compensate for losing longest criterion |
| gQ2 additive protection after r340 | 7–7 | All 14 event streams matched gP; intervention never fired, pure side asymmetry |
| gP vs v7_12 OLD / NEW | 8–2 / 12–4 | Wilson intervals .49–.94 / .51–.90; Fisher p=1.00, no measured engine effect |

- NEW gP turns were 88.9% L2–4, unaffected in free allowance; only 1.14% of moves were multi-step.
- L≥5 wasted 1.70 free steps/turn (62.2%); L≥9 2.93 (73.6%); L≥13 3.98 (79.2%).
- Later winning-team census also left allowance unused on 86% drone and 90% queen L≥5 moves; multi-step ~0.9%.
- Unused allowance measures mobility, not lost length or demonstrated lost games.
- gP protectedQueen() gated four split decisions only; “do not split” was mass retention, not general safety.
- gQ broke tryFeed, feeding and qCell routing by leaving dead/unseen queen record stale; r250→r400 longest crossover exposes the effect.
- Retain true-queen feeding while alive and a separate longest-dragon fallback after confirmed death; no official queen succession.
- Y.9.6 combines old longest election with true-queen rules, protectFrom 200 and true-queen sink from r280.
- Y.9.6 comments cite Trauma opponent queen feeding 2→16, Portals r287 queen boxed by 31 L2 drones, and FUNNEL collapse 51→2 units.
- Its GROWER ladder A/B comment reports 5/15 versus 2/15; code comments are evidence reports, not independently rerun results.
- NEW kamikaze audit (2026-10-07): 389/976 games had legal non-queen routes to enemy queen, 379 fully visible.
- Our queen later died in 171 opportunity games; enemy L≤4 initiators rammed queens in 414 games.
- Existing tagged attacks already killed enemy queens head-on in 367 games: opportunity incidence is not incremental benefit.
- Fresh reconstruction had no errors; smoke 1/2 wins, no rams. No demonstrated promotion strength.

## Opponents and build results

### OLD-rule landscape: historical reference only

- Top-24 scouting found length-4 budding into 2+2, 25–36 units r100 and 30–64 r200–300.
- V7.12 often had 4–12 versus strong opponents' 25–40 r100; ensuing head-on wars explained losses.
- Opening death rates per dragon-turn: ours ~.020 versus ~.012; split frequency similar.
- Devil replay geometry showed allied L2 drones entering opposite ends of unseen one-tile lanes and trapping each other.
- Fast-bed pearls r0–100, tungtung67 vs V7.12: Trophy 44–0, Devil 169–49, Trauma 59–10, Autarky 105–50.
- Longest usually stayed 3–10 until ~r300, then 12–31; !ghaplebaaz Trauma giant was 7 r100, 21 r300, 25 final.
- V7.12 lost that Trauma game with total length 82 vs25, because its late longest reached only18.

| OLD build / experiment | Result / decision |
|---|---|
| V7.5 → V7.10 → V7.12 maze panel | 14/28 → ~19/28 → 23/28 |
| V7.12 versus 1690+ teams | 7/25: tungtung67 0/5, !ghaplebaaz 1/5, kfcvme50/WCTW/Rogo each2/5; 1840+ typically0–1/5 |
| V7.13 fountain rush | +10% early eating but more deaths;5/25 vs control7/25 |
| gP unseen maps vs Y.8m | 61% over240 games, ~+1 final-longest margin; historical starting point only |
| gD anti-circling | Known maps40–20 vs control31–29; unseen55% vs gP61%, no unseen gain |
| gM/gJ final merge | No tested variant beat gP |
| gB transplanted open settings | 18%; early collapse, not late feeding |
| Rulemine cycle1 | PPP death rule regressed both sets;5 queen models47–61%, all within noise |
| Pearl gossip / replay attack | 15/30 vs16/30;5/30 vs4/30, historical null |
| Lane sonar | Devil6/6 promising subset; broader22/42 neutral |
| Probe danger | 43.8% vs50%, sample count unavailable (unverified); map-dependent |

- Late cull everywhere and r350 maze mass feeding lost population; queen intake was insufficient.
- Autarky stop-budding r300 was wrong against opponents retaining 55–64 units.
- r440 feeding alone rarely fired without a formed sink; stricter mining/child-escape checks improved self-play but lost ladder.
- Self-play-neutral unvalidated tweaks included flee-outnumbered, earlier even trades, queen r300 and feed r420; queen r380/mining ending150–200 were worse.
- Five historical parameter transplants failed; tuned “open map” settings were not a general open-map policy.

### NEW-rule yardsticks and ladder

| Date / build / comparator | Result | Interpretation |
|---|---|---|
| 10-02 gP / Port1 vs y7_12_49 | 4/20 /7/20 | gP rejected as foundation; Port1 gain inconclusive |
| vB19 vs y7_12_49 | 11/20 | Weak old-lineage yardstick, not champion proof |
| vB19 server14297 / same-source14299 | 8/25 /4/20 | Unmatched server records, not controlled strength |
| V4 learnGap vs vB19 dev | 22/40 | Correct port; noisy benefit |
| V5 split sonar / V6 torus feed vs vB19 live | 10/20 /9/20 | Neither promoted |
| F1 vs vB19 live | 18W/20L/2D, score19/40 | 47.5%, no established gain;0 failed games |
| vB19 / V4 vs old champion y7_12_nn1 | 10/20 /9/20 | 50%-parity screen PASS/FAIL only; one Trauma flip |
| Drone wNN0/1/2/4/8 vs y7_12_49 | 11/20/23/17/20 wins of40 each | Retain2; optimum unproven; queen weight stayed.4 |
| 10-03 vB19 / v6 nets vs Y.9.6 | 16/40 /14–15/40 | Reject vB19 as foundation; same n4 weights, rules matter |
| 10-06 opening_recipe closed / safety | 26/64 vs39/64;50/98 vs59/98 | Only1/4 halfway targets;−9.18pp safety, unpromoted |
| 10-06 MLP student safety | 50/98 vs cached parent59/98; earlier47/98 | FAIL; historical control provenance unavailable, fresh sealed control needed |

F1 map scores /4: Trauma1, Autarky2, Trophy2, Default2, Dilemma2, Devil1, Slithery3, Schooltime2, Portals2 (one win/two draws), QoS2.
The old-champion screen /2 was Trauma1→0 for V4; both otherwise Autarky1,Trophy1,Default2,Dilemma1,Devil0,Slithery0,Schooltime1,Portals2,QoS1.

Sv5.1 (Y.9.6 + CPU guard +716-game v6 net), 2026-10-03, tools/analyze_ours.py:
- 20 series (16 ranked/4 unranked),135 games,57–78 (42.2%),rating1634; Y.9.6 comparison218–219.
- User restored Y.9.6 id14940; dated active build, not guaranteed current server state.
- Opponents: WeHaveQuizzes2020 0/5,Kamikaze1944 0/5,Adrak1867 1/5,dev test1804 0/5,chaoliangUNSW1775 0/5; roughly even1600–1750.
- Worst maps Maze0/6,Slithery1/8,Autarky1/5,Stripes2/10,Dilemma2/8.
- Best Around UNSW6/9,Islands6/9,Australia5/7,Schooltime5/8,Portals5/8.
- Known maps41.0% (78),new45.5% (55); no visible new-map penalty in this small sample.
- Decoded subset133: our queen died100 (75%),medianr94.5; causes head-on51,wall24,body12,no-action8,self5.
- Queen dead byr100 in52 games,34.6% wins; enemy queen died98 (74%),medianr175,68 head-ons.
- In76 decoded losses enemy queen dead92%,ours70%: longest/elimination often remained decisive.
- ~150 dragon deaths/game; total head-ons7621,wall5195,self4107,no-action1953,body1145.
- Hotspots/game Slithery218wall+192self,Maze80wall+34no-action,Devil65wall+78self,Portals79self,Around UNSW85wall,Weakhold43wall; causal explanations unverified.

### Later network/proxy lessons

- 10-04 refresh scout preserved358 top wins from11 teams,all17 maps,382,051,345 bytes; no refreshed net/strength result.
- Training boundary:1513 game IDs in ladder/scout_v6/shards_145/manifest.json, ending933320 at2026-10-03T04:45:14.561Z; extra manifest rows were not necessarily trained.
- 10-05 eight league/team_<id> proxies all failed units@r100 fidelity: local/real equal-map median ratios.088–.566.
- Roster: tungtung67,avid coders,Just Keep Swimming,code matters,Jingling Munmin,hm,SSS,forgot to mention.
- Sv5.3 won15–17/20 against each, failing to reproduce real ladder difficulty; movement imitation left split/feed actions to our rules.
- Rejected proxies are not ladder-faithful gate opponents; farm uses opening census as primary metric and proxy wins as secondary safety only.
- MLP best epoch7/8 holdout top-1 68.628% vs conv68.579%, but backward recall8.77% vs43.97%.
- Holdout newest60 games/582,515 states; native parity1600/1600,max logit error.000671.
- Sampled MLP mean/max1.659M/2.482M vs conv21.137M (12.74× mean saving); accuracy/parity/CPU savings did not prevent gameplay FAIL.

## Measurement lessons

- Freeze source/weights/map/engine/judge/seed/side and bind replay/version to analyses and resumed caches.
- Replays omit/zero bed-gap data and strip CPU points; load map data separately and retain CPU sidecars/stdout.
- Round counts use last+1. Sprint reconstruction must follow individual successful-step events, not one final update.
- Preserve map/seed/side pairs; do not mix PowerShell and in-WSL panel numbers.
- Count intervention firings first: gQ2's identical play carries zero information about its added protection.
- Exclude self-play and duplicate streams: NEW “17–4” was actually12–4 plus5 self-play; Portals orderings duplicated in both eras.
- Local fixed-opponent panels measure eats/splits/queen length, but contention-driven movement/trade gains need same-time ladder controls.
- Measure per-dragon-turn eats/splits/deaths by phase with early_game.py/tempo.py, inspect deaths with board_at.py/trace.py, and report queens separately.
- At n40 near50%, binary SE~7.9pp and approximate95% width±15.5pp; n20 SE~11.2pp,width±21.9pp.
- Paired effects need paired outcomes; map/seed clustering reduces independence.0/8 has exact95% upper bound~37%, not zero uncertainty.
- wNN23/40 vs11/40 is30pp; independent SE10.54pp (~2.85SE), correcting the earlier1.5SE claim; selection across five settings limits optimum claims.
- Historical “~7pp local optimism” is not a calibrated correction for NEW rules.
- 2000 games/arm nominal pooled uncertainty±2.2pp, nine-way opponent-group±6.6pp; default farm has3–4 independent seed clusters/map, not≥27.
- A20-game parity screen is not promotion. Historical gate required≥22/40 vs champion and≥10/20 vs V7.5, then decisive ladder panel.
- Current yardstick instruction uses baselines/Y9_6; check actual active server submission before ladder tests and restore that id.
- Compare candidate/control at the same time, same opponents/maps and interleaved seats;100 games/arm needs≥4 windows at60 games/hour.
- Re-test opponents before ranked challenges: OLD All Roads/iced calamansi reversed within a morning; forgot to mention(+236) went2/5 unranked then0/5 ranked.
- OLD targeting rule:≥3/5 and≥Elo-expected+.2, selecting won maps; five games remain noisy.
- OLD Elo K96→24/12-hour and two-hour autoscrim notes conflict with strategy.md's Kalman/per-map ratings,±75 uncertainty,3 autoscrims/hour and first-seat+20.
- STATUS/critic reject assuming separate DEV quota or continuous schedule. These scheduling/rating claims are **(unverified)** for current operation; no live API check was part of this job.
- Search S0 lost-length proxy: ours9.50%,losses10.44%,local16.79%,top16.74%; no demonstrated relative advantage, not an exhaustive bound on search value.
- S1 oracle parity1888/1888 rounds,72,373 turns,four games validates exogenous-spawn replay only, not current RNG/full protocol/wasm strength.
- Fixed-radius BFS is a proposed one-turn geometric threat mask, not a full body/pearl-aware legality proof; multi-turn queries need evolving(cell,length) and body state.
- Follow-up specialization/escort/role-switching/nest ideas are untested in Loong; external escort14%→75% at2→3 is not our result.
- Old bceval whole-board inputs are not legal policy inputs; missing replay economy fields and selected samples prevent direct local/public score comparison.

Sources consolidated: game-mechanics-summary.md; insights.md; INSIGHTS_AND_PLAYBOOK.md; research_new_meta/numbers.md; research_new_meta/strategy.md; research_new_meta/strategies_followup.md; research_new_meta/y96_analysis.md; research_new_meta/sv51_ladder_analysis.md; research_new_meta/slithery_dilemma_trace.md; research_new_meta/yardstick_vs_champion.md; research_new_meta/f1_h2h.md; research_new_meta/STATUS_2026-10-02.md; research_new_meta/CRITIC_status_2026-10-02.md. Original files are retained; their history remains in git.
