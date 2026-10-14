# Bot history and ladder submissions

This document records the Loong bot lineages, submitted builds, and measured decisions.
It separates results under the old rules from results after the 2026-10-01 rules change.
It preserves failed experiments so the next attempt starts from evidence rather than repeated guesses.

## Contents

- [Rules and evidence](#rules-and-evidence)
- [Old rules: V7.x and imitation](#old-rules-v7x-and-imitation)
- [Old rules: S4.x rewrite](#old-rules-s4x-rewrite)
- [Old rules: Y.8m and gP](#old-rules-y8m-and-gp)
- [New rules: Y.9.x and Sv5.x](#new-rules-y9x-and-sv5x)
- [New rules: L.10, Nv, Y.12.x, and Sv6](#new-rules-l10-nv-y12x-and-sv6)
- [October experiment decisions](#october-experiment-decisions)
- [Lessons for the next attempt](#lessons-for-the-next-attempt)

## Rules and evidence

**OLD rules, before 2026-10-01:** round-500 tiebreak used longest living dragon, then total length.
The old elected “queen” was a consolidation role, not the fixed rule-queen.
**NEW rules, from 2026-10-01:** compare fixed queen length at round 500; dead queen = 0; then longest dragon, then total length.
The true queens are dragon IDs 0/1; free movement steps = `ceil(L/4)`.
Old-rule wins, timings, and parameter values require revalidation under the new rules.

Newest dated evidence takes precedence: HANDOFF corrections supersede S4_7_PLAYBOOK claims; October 3 queen-parser corrections supersede October 1 diagnoses; October 7–8 outcomes supersede earlier incomplete reports.
Submission is evidence of deployment, not proof of improvement.
Ladder records below mix different opponents and dates unless explicitly marked same-time A/B.
Local screens are provisional; fractional wins represent scored draws where reported.
“Not recorded” means the sources supply no result, not that the build was never tested.
The active server submission is the champion; dated active IDs below are historical snapshots, not a current-server assertion.

## Old rules: V7.x and imitation

| Build | Submission id | Contents | Ladder or local result | Verdict |
|---|---|---|---|---|
| V7.5 | Not recorded | Mining drones | Maze ladder panel 14/28 | Historical gate opponent |
| V7.9 | Not recorded | Short-horizon opening miners | Separate result not recorded | Kept in V7 lineage |
| V7.10 | Not recorded | Even head-on trades | Maze panel ~19/28 (unverified approximation) | Kept |
| V7.11 | Not recorded | Keep budding on Autarky | Separate result not recorded | Kept |
| V7.12 | 8242 | Maze longest protection r340; nearby feed r440 | Maze panel 23/28; strong-team panel 7/25 | Champion before imitation |
| V7.13 | Not recorded | Opening fountain rush: 80 rounds, less enemy discount, long horizon | Early eating +10%; strong panel 5/25 versus V7.12 7/25 | Dropped; deaths rose |
| test-v7.17-nn | 9258 | V7.12 + v1 imitation, wNN=2, maze only | Ladder 24/40; same-time subset 16/20 versus V7.12 6/20 | Resubmitted unchanged |
| Y.7.12-nn.1 | 9285 | Same code as 9258; `viper_nn/`, `baselines/y7_12_nn1/` | Local gate 70% vs V7.12, 75% vs V7.5 | Old-rule champion |
| Y.7.12-nn.1-jam | 9298 | Sonar replay attack | Same-time ladder 5/30 versus control 4/30 | Dropped; no effect |
| Y.7.12.3 | 9357 | Signed sonar + visible-pearl gossip | Local 44/84 maze; ladder 16/30 versus control 15/30 | Economy improved, no ladder gain |
| Y.7.12.4 | 10047 | Signed sonar + Vibing++ style network | League 86.3% versus 82.1%; ladder 16/30 versus control 17/30 | No promotion over 9285 |
| Y.7.12.13 / Y.8m | 11461 | Teammate maintenance lineage | Used as later old-rule control | Historical active build |
| S.1 | 13197 | `viper_nn_schedule`: later economy/consolidation schedule | Local 20/40; real panel 4/25 | Dropped; timing transplant failed |

V7.12’s maze panel was 777 4/7, ANON_TOKYO 7/7, hmm 6/7, Aviators 6/7.
The strong-team 7/25 was tungtung67 0/5, !ghaplebaaz 1/5, kfcvme50 2/5, WCTW 2/5, Rogo 2/5.
Its old macro mined through r300; open maps budded to r330 and fed from r350; maze budding continued to r420 below 40 units.
V7.11 fixed the premature Autarky budding stop: strong teams maintained 55–64 units there.
Earlier maze mass-feeding from r350 collapsed units; a late-feed rule alone rarely fired because no long dragon existed.

The v1 net learned top-team moves; safety classes still preceded `wNN × log p(move)`.
Maze-only wNN=2 scored 74W/9L/1D in 84 fresh local games; wNN=3 scored 70W/14L.
The net hurt open maps, including Portals 0/4, so it stayed off on Portals, Slithery Fight, and Schooltime.
The first dataset had invisible walls/portals at 1/255 strength; this was fixed before the validated pipeline.
Network inference fell from 44M to ~18M points/call; measured whole-turn peak was ~60M.

| September 28 attributed ladder record | Open, all | Maze, all | Open, ranked | Maze, ranked |
|---|---|---|---|---|
| V7.12 (8242) | 46/67 | 102/316 | 14/24 | 19/51 |
| Y.7.12-nn.1 (9285) | 40/57 | 115/216 | 20/30 | 39/60 |

Pearl gossip raised early eating 0.065→0.089/dragon-turn (+37%) and dragon-turns by r100 by 70%, without a same-time ladder win gain.
Signed sonar was retained as defense; its small behavior check was 3/6, not strength evidence.
Lane sonar was 22/42, giant hunt 20/42, soft opening safety 20/42: neutral local refinements.
Earlier queen r250 was 15/42: worse, keep r340 under the old rules.
More data v1b was 22/42; v2 with previous-turn/AWR inputs was 26/56 despite offline 70.6%→72.0%.
Joint policy/value scored 19/42 or 19/41; value correlation 0.35 did not yield stronger play.
Teacher distillation reached 72.2% versus direct 72.0%; team conditioning’s league gain did not transfer.
PPO drifted below imitation: run 5 was 10/40 at two evaluations; conservative run 6 was 9/20, then stopped for low memory.
Filtered self-imitation had no completed gameplay verdict in these sources.

Late-game diagnosis also failed to transfer.
`viper_nn_late` bundled schedule shift and feedDist=2: 16/40 versus champion, 75% versus V7.5; not submitted.
Isolated feedDist=2 was 17/40; feed targeting improved 41%→94% within two cells, recycling 66%→75%, but wins did not.
Isolated schedule was 20/40, then S.1 went 4/25 against calc, SSS, forgot to mention, Stockfish, Cache me outside.
Only SSS was 4/5; the other four were 0/5. The specified late-schedule direction was closed.

## Old rules: S4.x rewrite

S4.6’s diagnosis attributed 93% of ladder deaths to wall/self “DOOMED” traps.
S4.7 rebuilt on the public Abyss framework (`bc-abyss-main/`, Cat’s paradise), not teammate code.
Later HANDOFF analysis overturned safety-first conclusions: compare eating/population and opponent death rates, not raw death totals.

| Build | Submission id | Contents | Ladder or local result | Verdict |
|---|---|---|---|---|
| S4.7 / S4.7.5 | Not recorded | Flood-fill safety, gossip/crowd avoidance, adaptive known-map behavior | 50% vs V7.12 on six-map panel; unseen 21.7%/60 games | Reference, no decisive promotion |
| S.4.7.6 | 11453 | S4.7 snapshot; tuning, echo fix, dormant probe | 8W–22L vs Rogo, RustyHamsters, UnderTheC | Local strength failed to transfer |
| S4.7.4–S4.7.9 | Not recorded | Incremental snapshots | Individual robust gains not established | History |
| S4.8 | Not recorded | Early split, exploreBed, queen tie-break, growWindow bundled | SPRT 50.7%/150 | Null |
| S4.9 | Not recorded | Stop splitting r250 | 40.6%; longest 17.0→15.5 | Rejected |
| S4.10 | Not recorded | Feed global gossiped queen first | 53.1%; tempo identical | Noise |
| S4.11 | Not recorded | swarmChild 3→2 | 43.8%; r50 edge 10.5→10.0 | Null on population tempo |
| S4.12 | Not recorded | Consensus beds | Null | Infrastructure keeper, no strength claim |
| S4.13 | Not recorded | Bed belief | Null or worse | Not shipped |
| S4.16 / S4.17 | Not recorded | Committed routing | Metric bug invalidated interpretation | Not shipped |
| S4.18 | Not recorded | Correct committed routing | Null | Not shipped |
| S4.19 | Not recorded | Consensus kelp terrain | Trauma r0–250 eating 72→6 | Rejected |

The claimed `wCompass` +8.3 pp (41.7%→50%) was retracted: disabling it produced 24 byte-identical games.
Small-panel selection bias was ~7–9 pp: swarmChild=4 fell 53.1%→47.5%/99 games; S4.8 fell 59.4%→50.7%/150.
The claimed wTarget/wPredict/swarmChild +9.4 pp therefore remained unvalidated.
Slithery’s 600–700 deaths were later recognized as normal for both sides; early population deficit was the relevant comparison.
Emergency-split-off did not fix the Slithery pathology; chamberCheck and wCompass isolation also showed no change.
Probe danger’s initial 0→50% Slithery and 25→75% Schooltime samples failed follow-up SPRT: 27.6%/29 games; not shipped.
Territory weight 0.5 fell 40.6%→21.9%; Dilemma 75%→0%. Choke reservation was mostly inert (5/8 maps identical).
Bed clustering was net −2.8 pp; feedMaxLen 6→999 plus crowd increase went 1W–9L online and was reverted.
An uncapped bed-pair loop killed all Default dragons at r0 by exceeding 100M CPU; cap pairwise work.

Trauma’s fountains were actually 64 moves away, beyond horizon=48; optimistic unseen terrain had supplied misleading 5–8 estimates.
V7.12 ate 0.056/dragon-turn versus S4’s 0.031; it split 208 times versus 38 in the compared game.
Five transplants failed: hot sum→max, consensus terrain, committed routing, friendCloser 0→0.08, gamma .80→.86.
FriendCloser cut eating ~10×; gamma changed edge@50 10.5→7.0 and win 53%→41%.
Later HANDOFF conclusion: S4 had zero validated handwritten gains; coordination and horizon formed a coupled design.
The 18.3% and reverted 15% unseen-map reruns used Zig whereas the original 21.7% used sandbox; these are not clean A/B results.

## Old rules: Y.8m and gP

| Build | Submission id | Contents | Ladder or local result | Verdict |
|---|---|---|---|---|
| gP / S.2 | 13685 | Y.8m + unknown-map learnGap + protectFrom 400→340 | Pooled ~61% over 240 scheduled unseen games; live 31–29; unranked 3–7 | Best old-rule new-map reference; revalidation required |
| Bed learning only | Not recorded | Observed reset/countdown gap estimates | Set A 53–67; B 67–53 | 50%, insufficient alone |
| gPQ | Not recorded | Queen length lower bound; reports expire after 15 rounds | 44–76 | Dropped |
| gPE | Not recorded | Protect r280 with 30+ units | 71–49 | No gain over gP |
| gD | Not recorded | Tabu against no-eat revisits | Live 40–20; unseen 66–54 | Even overall |
| gM | Not recorded | Feed queen or longer ally from r430 | Live 30–30; queen +0.9, fewer units | Not kept |
| gJ | Not recorded | gD + merge at 460 minus queen travel | Unseen 68–52; live 28–32 | Not kept |
| gB | Not recorded | Open-map macro on unknown maps | 22–98 | Rejected; maze defaults better |

gP was uploaded September 30 18:40 UTC from `viper_y8m_gP/`; only main.cpp changed.
Set A was 72–47 (one scheduled outcome not accounted for); B 73–47. The source rounds pooled performance to 61%.
Final longest 16.1 versus bed-only 15.1; paired margin +1.08±0.60 versus −0.45±0.59.
Bed learning raised r500 units about 18→23.5; protection converted population into length.
Unknown-map gap estimates were per-dragon and lost on child creation; reset evidence prevented false fountain classification.
Peak CPU 61.7M, no increase over control. Ladder losses had mass spread across medium dragons rather than one long winner.
After its 3–7 test versus Yueci Li/Maccas, maintenance submission 13618 was restored.

## New rules: Y.9.x and Sv5.x

October 1 `baselines/y7_12_49` beat gP 6–4/10 locally and already separated true-queen protection from longest election.
gQ/gQ2 had conflated those roles and broken late feeding.
The proposed swarmSplit guard fix produced identical failures in eight games; early splits traced to doomedSplit (SHED/ESCAPE-SPLIT).
October 3 found a deeper analysis bug: `startswith("DRAGON")` matched DRAGON_COUNT and assigned queens to wrong teams.
The old general “queen dies r5 because swarmSplit” diagnosis is retracted; validate exact parser tokens and real starting bodies.

| Build | Submission id | Contents | Ladder or local result | Verdict |
|---|---|---|---|---|
| Y.9.5 | 14685 | Teammate new-rule maintenance | Not recorded | Historical active ID |
| vB19 | Not recorded | Alternative new-rule foundation, n4 net | 16/40 vs Y9_6; cited real records 8–17 and 4–16 | Abandoned as foundation |
| Y.9.6 | 14940 | Portal exploration, hybrid queen, QFEED, QBOX-SHED, SELFTRACK, continuation veto, hunting, secure sonar | Historical ladder 218–219; stronger than vB19 | October 3 champion/base |
| Sv5.1 | 15682 (user-supplied; id unverified in listed log) | Y9_6 + tight CPU guard + 716-game v6 net; viper_y96xn | Local 15/28, peak 64.9M; corrected ladder 60–85/145 | Superseded by Sv5.2 |
| Sv5.2 | 16106 | viper_y96qf: full-terrain k_fullft net, 1513 games; coil-aware queenAmputate/QBOX; refreshed map tables; CPU guard | Local 54.5/98, peak 65.2M; ladder 29–48/77 (37.7%) | Retained conservative candidate |
| Sv5.3 | 16651 | viper_y96qg: guards, secure status/QPOS/echo telemetry | Fresh local 44/98 vs Sv5.2 48/98; ladder 58–89/147 (39.5%) | No measured local advantage; retained lineage |
| Y.11d-conveyor | 15978 | Teammate build; details not recorded | Not recorded | Seen at Sv5.2 submission |

Y9_6 retained the same n4 weights as vB19; its advantage implicated rules rather than retraining.
It added hungry unknown-portal exploration, true-queen feeding from r280, longest protection r200, and milder queen scoring.
Measured Y9_6 peaks were 73.0M on Australia/Around UNSW, 69.7M Islands, 60.7M Maze.
vB19 reached 98.8M; a v6-net bot 96.5M; a CPU-fix candidate 53.4M. The kill limit remained 100M.
Sv5.2 upload October 4 used five files/606 KB and empty description.
Six embedded maps were refreshed: Autarky, Default, Dilemma, Schooltime, Slithery Fight, Trophy.
Seven new maps stayed unknown: Stripes, Tower Defense, Islands, Around UNSW, weakhold, Maze, Australia.
Submitted Sv5.1 and Y9_6 kept the old tables; source/header identity matters in comparisons.

Corrected Sv5.1 analysis: 105/145 queen deaths (72%), median r176; head-on 76, self 14, wall 13, body 2.
With queen surviving it won 82%/40; with queen dead 26%/105; this is observational, not causal.
Live Slithery queen started L25 rather than local L7 and died self at r1 in 8/8 ladder games; wins 1/8.
Queen-only complete-information search was parked: 45/80 ON and OFF, 77/80 queen deaths, zero overrides.
Even after differential fixtures passed (240 random + 10 hand cases), all triggers failed eligibility under 7×7 visibility.
New-rule wNN sweep versus y7_12_49 (40 games each): weights0/1/2/4/8 won11/20/23/17/20; no failures/timeouts, CPU absent from logs.
wNN=0 was clearly worse; weights1/2/4/8 were statistically indistinguishable; keep2 as nominal best, not a proven optimum.
Combined Sv5.3/Sv5.2 local comparison over 196 games was 103 versus 102: no measurable gain.
Sv5.3’s 89 losses included 52 early deficits, 22 equal-queen longest/total losses, nine later eliminations, five queen-only, one living-queen deficit.

## New rules: L.10, Nv, Y.12.x, and Sv6

| Build | Submission id | Contents | Ladder or local result | Verdict |
|---|---|---|---|---|
| L.10 | 17124 | Teammate lineage; k_fullft net; later Nv30 parent | 355/752 (47.2%); peak 66.083M | Historical active build, not fair A/B versus Sv5.x |
| Nv3.0 | 18983 | L.10 + 29-line WRECK miner pearl targeting; baselines/Nv30 | Early ladder 29/67 (43%); local control 42/98 vs Y9_6 | Locked October 7 base |
| Y.12.x | 19942–20032 (range user-supplied, individual mappings unverified) | Teammate c28–c43 queen defense, guards, phases, exploration, v7 net | Series-wide ladder record not recorded | Several independent tactics made Nv experiments redundant |
| Y.12.11 | 19952 | c43 snapshot, baselines/Y12_11 | Reactivated by teammates after Sv6 upload | Confirmed October 8 historical active build |
| Sv6 | 19955 | viper_nv30k: Nv30 + refreshed weights only | Local 52/98 versus Nv30 control 42/98 | Submitted October 8; fresh confirmation not completed |
| Nv3.5 | 20500 | Teammate build; exact incremental contents unverified | Unranked A/B 25/48 | Restored after Sv6h test |
| Sv6h | 20531 | viper_nv30h_s4: Sv6 + strong hunger on maps ≤900 cells | Unranked A/B 23/48 versus Nv3.5 25/48 | No demonstrated ladder improvement |
| Nv3.10 | 21312 (user-supplied, unverified in listed sources) | Contents not corroborated | Not recorded | No strength or final-active claim supported |

L.10’s opponents averaged Elo1697 versus Sv5.3’s 1780; its higher raw percentage cannot establish superiority.
L.10 queen deaths were 503/752, median r183, 355 head-on; 231/397 losses had early deficits.
Early Nv3.0 faced mean Elo1971 and was about ten wins above Elo expectation; this is a dated small sample.
WRECK made L2/3 nonqueens commit to ground pearls within four steps when bed countdown exceeded walking time.

Y.12.11’s source comments preserve the teammate chain:
c28q added QHUNT to Nv30; c29g added guard interception and 1/5 small-drone escorts; c30g added queen visibility/position from r40.
c32 combined WRECK, QHUNT, EXPL31, phases (outgrow/conserve/protect/eliminate/longest), guards, alarm, acting queen, and v7_plain.
Sonar added encrypted payload, game-bound authentication, one-round replay window, and movement plausibility.
c33 selected v7 by default and v6 on Default/Dilemma/Trauma; c34 added escort calls and a 30-unit budding cap.
c35 disabled COMPASS on Schooltime; c36 added STUCK36 (ban targets after 15 nongrowing rounds), removed budding cap, and feed floor20/throttle1/4.
c38 also disabled COMPASS on Trophy; c39 prevented escort boxing (≥3 cells); c41 disabled bigFeed suicides from r300.
c43 (Y.12.11) added known-map Maze/Stripes tables, 17 maps total. These are contents, not isolated gain claims.

Sv6 used four Kaggle T4 epochs over ~30M weighted samples, old ×1/new ×2, 107 minutes.
Newest-143-game holdout accuracy rose 69.85%→70.66%; native argmax matched 1600/1600.
Max logit error 2.7e−3 exceeded the script’s 1e−3 bar (old net 2.2e−4); significance remained unverified.
Screen queen deaths were 88 versus 90; median death r179.5 versus r199; Islands wins 8 versus 2 explained much of the gain.
All tested Nv variants improved on the low 42/98 control, raising regression-to-mean concerns.
Sv6 was submitted October 8 at 02:07, then displaced by teammate Y.12.11; confirmation was stopped by user direction.

Sv6h’s hunger strengthened exploration priors, discouraged revisits, and pulled small drones toward known frontiers.
Queen hunger was conservative and off from r100 or nearby enemies; worker frontier pull capped at L6.
Closed-start 64-game test: Sv6 29 wins/retrace34.1%/unique26.4/units100 6.63 → strong hunger 38/24.5%/29.5/7.09.
Strong hunger harmed large maps: Australia 1/14 versus7/14, Around UNSW6/14 versus8/14, Islands0/3.
It was gated to W×H≤900; weakhold scored10/14 versus11/14.
Large-map flag-off parity was not exact (3/4 games differed), attributed to CPU-guard timing overhead; neutrality unverified.

October 8 unranked A/B used eight near-rating teams × six maps, back-to-back; Sv6h23/48 versus Nv3.5 25/48.
| Map | Sv6h wins/8 | Nv3.5 wins/8 |
|---|---|---|
| Stripes | 4 | 2 |
| Maze | 1 | 3 |
| weakhold | 7 | 8 |
| Islands | 5 | 5 |
| Tower Defense | 3 | 3 |
| Around UNSW | 3 | 4 |

CookAgent3–3, Oswald3–3, zzz3nith2–2, 7773–4, life is NP hard5–3, err4042–3, slither hither1–3, Ravenus4–4 (wins per six-game team series).
Two tools/ab_ladder.py bugs were fixed: case comparison falsely reported0/48; wait_all crashed on non-dict responses.
The tool restored Nv3.5 (20500) in finally. The A/B did not establish a difference.

## October experiment decisions

| Experiment / tool | Measured result | Decision and reason |
|---|---|---|
| Eight league proxies, tools/league_build.py | 64 fidelity +160 Sv53 +8 verification games; 0/8 accepted; 2/12 discordant rankings, four collapsed ties | Reject as ladder-faithful; opening population collapsed despite numerical parity |
| Parameter search, tools/param_search.py | ps00–03 each350 paired games; scores .949/1.028/.590/.971; CPU65.17–65.28M; all four halfway targets failed | No eligible candidate; user stopped after20h as indirect/slow |
| Farm tooling, farm_run.sh/farm_scale.py | Pack/guards/resume fixtures passed; farm_report lists1400 evaluations/700 pairs and186.2/hour | No promoted build; farm candidate identity and current-run interpretation unverified; critic found shared-report fixture contamination |
| MLP student, viper_y96qm | Eight epochs;68.628% versus68.579%;1600/1600 parity;1.659M mean/2.482M sampled max versus conv21.137M | Drop: safety50/98 versus59/98 (−9.18pp); first trial47/98; speed/accuracy did not preserve play |
| Opening recipe, viper_y96qo | Closed R1/R2/R3 wins29/28/26 of64 versus39; halfway1/4; safety50/98 versus59 | Drop: Tower0/14 versus6/14; population worsened4/7 maps despite Stripes improvement; CPU64.648M passed |
| Opening fix / ablations | Open cycle-off9/16 vs original7/16; queen-food-off6/16; split-off7/16; separation/portal-off8/16; control9/16 | No accepted fix; closed/safety composition unverified; stopped when Nv30 became locked base |
| Kamikaze, viper_y96nk | Candidate36/98 vs Nv30 42/98; ram kills8 vs64; queen deaths90 each; peak65.199M | Drop: restrictive replacement reduced attacks and scored−6.1pp; chase benefit unverified |
| nv31a queenAntiRam |48/98 vs42; queen deaths90 each; medianr222.5 vs199; peak65.269M | No promotion: head-on deaths69→59, wall/self15/6→20/10; survival unchanged |
| nv31b trapMap |51.5/98 vs42; queen deaths92; DOOMED/escape10772 vs10932; peak65.251M | No confirmation or target improvement established; later stopped as redundant |
| nv31c wreckExtend | Longer miner corpse-site targeting proposed; completed screen not recorded | No recommendation; vacated occupancy was a corpse proxy, not proven deaths |
| Local nn_refresh4 |1448-game/42-team/17-map report; error Invalid argument; no verified exported candidate | No promotion; provenance/resume/CPU and manifest-loading critique failed |
| Kaggle refresh → Sv6 | Earlier report blocked on1448 CSV vs1430 eligible games (18 own-team exclusions); later October7–8 logs document training and52/98 screen | Later completion supersedes blocked report; confirmation and ladder gain still unverified |

MLP backward recall was8.77% versus teacher43.97%; a diagnostic, not a proven cause of loss.
MLP safety control execution-time provenance was unsealed; repaired parity/finite CPU checks did not reverse its FAIL verdict.
League proxies were tungtung67, avid coders, Just Keep Swimming, code matters, Jingling Munmin, hm, SSS, forgot to mention.
Sv5.3 beat them15–17/20 while losing badly to corresponding real teams; movement imitation left splits/feeding to shared rules.
Farm/league/search consumed ~2.5 days with zero promoted candidates; the user closed those infrastructure fronts October6.
Kamikaze opportunities were upper bounds: L10 294/752, Sv5.3 62/147, Sv5.2 33/77; existing attacks already rammed queens.
Later kamikaze report records identity/coverage/CPU/audit fixes passing; its earlier incomplete critique does not supersede the completed negative screen.
nv31 fix-round1 records trap-timeout retry, directional fixtures, source-bound native tests, and derived-cache binding; these repairs do not constitute gameplay acceptance.

October14 cleanup retained viper_y96qf (Sv5.2), viper_y96qg (Sv5.3), viper_nv30k (Sv6), viper_nv30h_s4 (Sv6h) and original reference lines.
It removed53 experimental bot directories and41GB of F: scratch; server submissions and teammate files were left intact.
No final tournament outcome or final active submission is established by these sources.

## Lessons for the next attempt

- Revalidate every old-rule result; fixed rule-queen and elected longest dragon are separate responsibilities.
- Use the active server build as ladder champion, record its ID, and restore that exact build after testing.
- Compare paired seeds/sides against sealed builds, maps, engine, judge, and analysis versions; reject stale caches.
- Validate parser ownership against exact DRAGON tokens and real live-map starting bodies before diagnosing queen deaths.
- Treat local wins, imitation accuracy, and CPU savings as screens; require same-time ladder evidence for promotion.
- Measure eats/dragon-turn, units50/100, queen survival, and target-rule activations; compare opponent base rates.
- Change one mechanism at a time; preserve checkpoints before major changes and include closed, large, open, and unseen maps.
- Test coupling: longer horizons need coordination; disabling a feature can change CPU-guard timing and break parity.
- Separate fixture reports from production evidence; completed workflows and tooling PASS do not approve candidates.
- Stop directions with repeated negative results; infrastructure and redundant teammate features consumed time without promotion.

Sources consolidated: tools/tasks/docs_merge/COMMON.md; S4_7_PLAYBOOK.md; HANDOFF.md; SESSION_HANDOFF.md; INSIGHTS_AND_PLAYBOOK.md; AGENTS.md (historical champion/submission sections and dated corrections); ml/results.md (bot/ladder result parts); research_new_meta/yvsg/REVIEW_y7_12_49.md; research_new_meta/s2_gQ/README.md; research_new_meta/wnn_sweep_results.md; reports/farm_report.md; reports/farm_scale_report.md; reports/farm_scale_critique.md; reports/hunger_report.md; reports/hunger_critique.md; reports/kaggle_train_new2_report.md; reports/kamikaze_report.md; reports/kamikaze_critique.md; reports/league_build_report.md; reports/league_build_critique.md; reports/mlp_student_report.md; reports/mlp_student_critique.md; reports/nn_refresh4_report.md; reports/nn_refresh4_critique.md; reports/nv30_improve_report.md; reports/nv30_improve_critique.md; reports/opening_fix_report.md; reports/opening_recipe_report.md; reports/param_search_report.md; reports/param_search_critique.md; topic-only AGENT_LOG.md entries; NEXT_STEPS.md; research_new_meta/y96_analysis.md; baselines/Y12_11/main.cpp lineage comments; docs/TACTICS_AND_ALGORITHMS.md (L10 audit facts). Original notes remain available in git history where tracked.