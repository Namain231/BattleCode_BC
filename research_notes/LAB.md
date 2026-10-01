# LAB (Claude, Codex, Gemini: co-scientists). Keep this file SHORT: facts <= 15 lines, entries <= 12 lines each.

## 1 Oct (opencode) queen display
- pair_diff.py: window lines now show `Q ours/theirs <len>/<len>` (queen = dragon id 0 for A, 1 for B; 0 once dead); BASE/CAND header shows each queen's death round and cause (or "alive").
- viz.py: frame header now includes `Q ours/theirs <len>/<len>` alongside units/mass/longest.
- Tested on devsmoke/autarky_A_1000.replay: both queens die r6 (hit wall), Q 14/14 at r0 → 0/0 from r50.

Game: UNSW Battlecode 2026. Dragons = snakes on a wrapping grid; eat pearls to grow; head-ons kill both; an illegal
action kills a dragon and drops ceil(L/2) pearls ("feeding"); a pearl spawns only on an EMPTY tile; 7x7 vision (not
through portals); <=64 units; round 500: longest living dragon wins (a wiped-out team loses earlier).

## Facts (30 Sept, measured)
- We (~1661 Elo) score ~0/30 vs the top-6 teams (~2050). Offline self-play panels are saturated: ignore small edges.
- Top teams, maze maps (Trophy, Devil, Default, Autarky): mostly win by ELIMINATION before r500; their units
  r100/200/300 ~ 20-30 / 32-40 / 43-55.
- Top teams, open maps (Portals, Slithery, Schooltime) + Trauma: swarm to ~60 units by r300 (longest ~7), then
  consolidate: 35/18/7 units at r350/400/500, longest 11/25/37/48; ~78 feeds after r300, only ~4 within 3 cells of the
  final giant: it grows by eating piles dropped elsewhere. Ours: giant +19 after r300 (theirs +39), 31 feeds.
- Our history: Slithery is our worst map (7/46); Y.7.12-nn.1 (move network) is our best ladder bot on mazes.
- Traps (tools/trap_compare.py, r100-300 deaths per 100 dragon-rounds, our lost games): we hit walls 0.94 / self 0.70 /
  lose head-ons 0.79; the SAME opponents 0.51 / 0.42 / 0.42. Our trapped dragons are ~3 long (mining drones).
- Ladder scrims vs "Computers" (rank ~30, 5 maps): Y.10o 0/5, Y.10 1/5, champion 0/5 (too strong to separate builds).
- Falsified: "our queen suffocates in traffic". Tried, no clear gain: feed thresholds, S.4.7.5 feed protocol, fountain
  sharing, budding tweaks, compass, portal safety, NN retraining.

## Protocol
Own a hypothesis. Implement it in YOUR folder cand_<you>_<n> (Claude copies a base on request: cand_y10 = dev bot,
main.cpp; key functions: think(), evaluate(), tryFeed(), swarmSplit(), updateQueen(), activateMap()). Read only the
functions you need. Tag changes. Add an entry below (<= 12 lines): hypothesis, change, test wanted. Claude runs tests
(vs 6 team bots offline, Kaggle, or free ladder scrims vs one strong team) and appends results under your entry.

## Entries
- Codex — Hypothesis: open-map losses partly come from starting consolidation 30–50 rounds after stronger teams; their swarm falls from ~60 units at r300 while our current schedule buds to r330 and homes at r350 (growth_codex.md / LAB facts).
- Change: on bigFeed maps, stop swarm budding at r300, begin queen homing at r320, and allow close deliberate feeds from r330; preserve maze settings and queen rules. Tagged `// CDX1` in `cand_codex_1/main.cpp`.
- Test wanted: vs 6 team bots on open maps (Portals, Slithery, Schooltime), 2 seeds, compare per-map longest length at r400/r500 and wins; analyze every loss.
  - Claude (06:15): builds OK; queued vs 6 team bots, open maps, 2 seeds (ladder/open_cand_codex_1_vs_*.txt), after Y.10
    baseline and Y.10o2/o3 on the same games. Y.10o (similar, more aggressive: r290/r300) scored 46/72 there.
- Claude — Hypothesis: we lose the numbers war partly by self-trapping small miners (our lost games: wall+self deaths
  1.64 per 100 dragon-rounds r100-300 vs 0.93 for the same opponents; trapped dragons ~3 long). Change (cand_claude_1,
  tag CLA1): a dead end too deep to bud out of (surv < L+2 with pDeath >= 0.5) loses the miner/cheap-drone risk excuse
  (an old version, cand_trap1, looked worse only vs our own bots). Test: Kaggle vs 6 team bots, all maps, seeds 4
  (same games as the Y.10/Y.10x/Y.10s batch kp0930_0550).
- Claude — Hypothesis 2: we lose ~2x the head-ons of the teams that beat us (0.79 vs 0.42, r100-300); part may be our
  deliberate "war of numbers" even trades (UNITS >= 12, length <= 3). Change: cand_claude_2 (CLA2) disables them.
  Test: Kaggle vs 6 team bots, all maps, seeds 4 (kp batch with base Y.10).
- Claude (07:10) — RESULTS open maps vs 6 team bots (72 games): Y.10 48, Y.10o 46, Y.10o2 (+feeder cap) 40 => late
  consolidation line closed. NEW LINE (early grower): okbro (~1710) keeps one 25-35-long dragon by r100-200 on open maps;
  ours stay 4-8 until r300. Candidates: cand_claude_3 (CLA3: queen never buds from r30 on open maps; sanity: 14 at
  r200, 35 at end), cand_codex_2 (CDX2: + nearby 4+ dragons feed her from r50 once she is 8), cand_agy_2 (AGY2, in
  progress). Test: ladder scrims vs okbro + usagi on open maps (Y.10 control) -> ladder/scrims_grower_open.txt.
- Claude (12:00) — RESULTS. Grower line (ladder, open maps, all rounds): AGY2 9/21, CLA3 7/21, CDX3 9/30, CDX4 2/15,
  Y.10 10/36 -> neutral; paired loop AGY2 vs Y.10 running (round 0: 8 vs 9 of 15). Offline Colab (open, 72 games):
  CLA3 51, Y.10 49, AGY2 43, CDX2 35. Kaggle all maps: Y.10 76/120, x (exploration) 75, s (spawn blocking) 71, CLA2 (no
  even trades) 62 = worse, CLA1 (traps) 71/119. MAZE maps are decided by r100 (our maze losses: 9 units at r100).
  Our army per map r100/200/300 vs top wins: Devil 10/6/5 vs 27/40/53, QoS 6/6/7 vs 13/27/33, Dilemma 8/5/4 vs 13/20/20,
  Trauma 7/17/22 vs 15/37/42, Trophy 23/27/24 vs 30/37/55: on Devil/QoS/Dilemma our army SHRINKS after r100.
  Testing (Kaggle, maze maps, same seeds): Y.10, CDX5 (goalPatience 24 on mazes), CLA5 (contest pearls: enemyCloser 0.8).
- Claude (12:25) — MAP-SPECIFIC trap finding. Loss log: on Devil we lose 11.8 dragons/game to self-trapping in r0-100
  (vs 5.4 head-on); Queen of Spades r100-300 trapping 8.3 vs head-on 4.2; Trophy is all head-ons. CLA1 (no risk excuse
  for dead ends too deep to bud out of) HALVES trap deaths there (vs s475, Devil+QoS, same seeds: wall 139->76, self
  192->98) but on Kaggle all-maps it hurt Dilemma (7->3/12) and Autarky (9->6/12). => CLA1d (12703): the rule only on
  Devil + QoS. Ladder paired loop CLA1d vs Y.10 on Devil/QoS running (ladder/ladder_ab_CLA1d.txt). Lesson: judge changes
  per map and gate them per map (portfolio). AGY2 vs Y.10 ladder loop stopped at 16 vs 17 of 30 paired (no difference).
- Claude (14:55) — Nv1.9 source downloaded (API GET /submissions/12130/download -> opponents/nv19). It is Y.7.12-nn.1
  + sonar changes only (mapping probes on UNSEEN maps; weakly signed gossip; pearl gossip OFF). On known maps it plays
  like nn.1. Nv1.9 vs 1950+ teams (last 17 h): 3/35 (wins: Devil vs Cutlery by numbers 26 vs 9 units at r100; QoS vs
  Stockfish; Schooltime vs SKKU by top-team-style consolidation 62 -> 13 units, longest 41 vs 40). Champion Y.8m (= nn.1
  + maze-only fixes: n4, p2Drone 0.15, minerGamma 0.9, blind portal 2.0) 0/30 vs the top 6. Hypothesis: Y.8m's maze
  fixes hurt vs strong teams. Queued on the ladder vs the champion's own past games (same teams/maps): Y.11 (AB set,
  top-6 set), vB18 (top-6), nn.1 (top-6), Nv1.9 (AB set). Champion references: AB 16/30, top-6 0/30.

## 30 Sept 17:25 IST: rules+NN mixing, outside panel (nick bots; slithery/schooltime/portals/trauma, 3 seeds, 96 games)
Kaggle kp0930_1623: champion 13, mix_a (n4 on open maps, w2) 9, mix_b (confidence weight) 13 (identical games), mix_e 11,
**mix_g (NN on all maps; w1 open, w3 maze) 15**. Laptop paired vs stored champion (11/96): mix_c 13, mix_d 13, mix_e 3/72 stop, mix_f 10.
Lesson: on open maps the NN helps only lightly weighted (w1 > off > w2). Open-map networks open_ft (init n4, val 0.709) and
open_sc (scratch, 0.706) trained on 150 top-10 open wins (tools/kaggle_train.py --scalars 3). Testing cand_dual (open_ft w2),
cand_dual_sc, cand_dual_w1 (open_ft w1): Kaggle kp0930_1708/1709/1724 + laptop queue. Maze check of mix_g: kp0930_1725.
cand_pocket (Codex): no miner waiver on open maps for L3-4 when surv < L+1 (Slithery pocket self-traps).

## 30 Sept 17:55 IST: why we lose on length with more mass (tools/endgame_gap.py, 40 champion losses, ladder/endgame_gap.txt)
Our longest vs theirs: r300 4 vs 7.5, r400 7 vs 13.5, r450 11 vs 18.5; units r400 37 vs 13, r450 26 vs 5.
Median 21 different dragons held our "longest" after r300 (no stable sink). Our r350-longest died in 33/40 games:
13 by feeding itself (tryFeed), 10 wall, 7 head-on. Causes in code: the queen is re-elected every turn from gossip +
view (ties/changes flip it); on open maps any dragon feeds into any visible friend >= L+3; protectedQueen() is off on
open maps. -> cand_sink (Codex): sticky queen, the queen and big dragons never feed or trade head-ons, feed only into the
queen from within 2 of her head, no voluntary splits after r300 unless < 12 units. Tags SINK-A..D for ablation.
Other results: cand_dual (open_ft w2) and cand_dual_sc NOT BETTER (laptop SPRT early stop; Kaggle dual_sc 11/96).
cand_dijk (time-aware Dijkstra space count, Codex) smoke 3/4 vs champion; Kaggle kp0930_1748 (open), maze pending slot.

## 30 Sept 18:15 IST: verdicts
- Separate open-map network: DROPPED. cand_dual (open_ft w2) Kaggle 6/96 + laptop SPRT NOT BETTER; cand_dual_sc 11/96 + NOT
  BETTER; cand_dual_w1 Kaggle 6/96, laptop 9 vs 11. Champion 13/96 (laptop stored 11/96). Imitation on 150 open-map top
  games is not enough; n4 at w1 on open maps (mix_g) 15/96 -> cand_g1 isolates it (Kaggle).
- mix_g on the maze panel (6 maps, 144 games): 89 vs champion 92: w3 on mazes no better.
- cand_pocket 11 vs 11 (no decision). cand_sink (all 4 parts, all maps) NOT BETTER 4 vs 9 of 72: on open maps it throttles
  the champion's working consolidation (one Slithery replay: r400 31 units / longest 14 vs champion 13 / 18; end longest
  22 vs 36). -> cand_sink_m = sticky queen + queen guard, maze maps only (Kaggle maze + laptop Trauma/Autarky/Default).

## 30 Sept 19:10 IST
- S.1 (13197, teammate S, downloaded to opponents/s1_13197) = nn.1 + LATER schedule on maze maps only (mine/bud until 380,
  feed from 420, endFeed 470, gossip 370, protect 400). Ladder (unranked, 5 maze maps): 4/5 vs SSS (rank 5), 0/5 vs ranks
  2,3,4,6 -> 4/25 vs top 6 (champion 0/30 yesterday). Ported onto the champion: cand_late (Kaggle maze + laptop).
- cand_g1 (n4 w1 on open maps) laptop 8 vs 11: NO. cand_dijk_o NOT BETTER. cand_sink_m Kaggle maze 89 vs 92, laptop 27 vs 26: neutral.
- New tools: tourney.py --replays DIR; tools/loss_digest.py (loss types ELIM / LEN+MASS / LEN-MASS, gap round, longest
  fate, holders; --pair BASE CAND for same-seed diffs); tools/kernel_result.py.
  Last 20 champion ladder losses: ELIM 9 (Trophy 4/4), LEN-MASS 7, LEN+MASS 4; mass gap opens ~r37; units r100 9.5 v 24.5.

## 30 Sept 19:45 IST: last-giant hunt
Pair view (loss_digest --pair, champion vs cand_late, nick_farm, 24 games): builds identical until r325; the 4 differing games
are late scrambles. autarky_B_1017: champion 42 units/103 mass vs 6/14 at r300 and still LOST on length (L12 v L13);
cand_late won it by elimination. In ladder losses on length (endgame_gap, 40 games) the enemy ended with 1-3 units in 14
(35%) while we had 9-36 units: their single giant (L18-44) wins the tiebreak. A head-on kills both regardless of length.
The champion hunts only visible heads; the old "giant hunt" (v7.16) was judged on 15 games. -> cand_hunt (Codex): gossip
the giant's cell from r350, pull small drones to it from r380, trade any L>=10 enemy head when UNITS >= 6.
Also: cand_dijk2 maze 79/144 vs 92: Dijkstra line dropped. cand_nn1 laptop 10/24 vs 14/24.

## 30 Sept 20:30 IST: mechanics vs top teams (tools/mechanics.py, tools/viz.py eatmap)
Rules: min dragon length 2 (SPLIT 1 illegal; the parent keeps the head); body hit kills only the mover; head-on kills both.
Sprint x steps costs x-1 segments. Champion LOSSES vs top-6 WINS, 25 games each:
- maze: pearls eaten r0-50 18 vs 41, r50-100 30 vs 75 (2.3x); splits r0-100 20 vs 60 (budding = growth: same 4 -> 2+2
  rule); sprints 33 vs 26/game, attacks 17% vs 35% of sprints, travel 64% vs 47%; r300+ sprints 15 vs 6.
- open: sprints 158 vs 99/game (173 vs 128 segments), attacks 12% vs 25%; head-on deaths 114 vs 75/game.
- split-then-head-on is rare for top teams (6-7%): they trade with small dragons anyway (2.8-3.3 segments per head-on).
- eatmap Trophy loss (646876) r0-60: ours 25 vs theirs 51; they ate the whole central fountain room (~20), we none.
  -> cand_contest = champion + maze enemyCloser 0.8 / enemyTie 1.0 (V.13c's contest rule, never tested with the network).
- Ladder (seed 930 AB set, vs champion's stored 16/30): LATE 12/30 (maze 10/22), HUNT 18/28 (maze 16/20; hunt did not
  convert the two Slithery single-giant games: body blocks, not head-ons -> cand_cutoff queued on open maps).

## 30 Sept 21:10 IST: more mechanics (tools/mechanics.py: pearl timing, wreck scavenging, head-on exchange, unit cap)
Champion losses vs top-6 wins, 15 games each:
- maze: wreck (death-pearl) share eaten 38% (115/game) vs 81% (263/game) <- biggest economic gap found;
  pearls eaten within 1 round of appearing 21% vs 37% (mean wait 18.8 vs 8.8 rounds); head-ons even (32 v 32; 29 v 30).
- open: wreck share 44% vs 57%; head-on deaths ours v theirs 112 v 87 (we lose the exchange) vs top 52 v 94;
  rounds at the unit cap 96 vs 50.
- Sandbox (nick_farm): champion's opening intake is normal (r0-50 37, r50-100 72): the gap appears only vs teams that contest.
- cand_contest Kaggle maze 95/144 vs 92 (noise level, right direction); laptop 13 v 12. Ladder queued.
- S.1 ladder 12/30 (maze 10/22) vs champion stored 16/30: champion stays. -> cand_scav (Codex): wreck pearls x1.6 for
  15 rounds, no enemy-closer discount vs heads <= our length.

## 30 Sept 22:00 IST: audits + same-time ladder control
- Codex audit 1 (ladder/cosci/codex_21.md): wreck share denominator was consumed pearls (fixed: now over pearls dropped);
  losses-vs-wins selection bias; stale baselines; cand_contest swarm branch ignored enemyTie (fixed); cand_scav zero-init
  (fixed). Champion's OWN maze games: wreck share 69% in wins vs 34% in losses (top-6 wins 68%) -> scavenging follows
  winning, not a separate skill; cand_scav laptop 9/24 v 12/24, share 57% v 63%: DROPPED. Opening intake r0-50 even in our
  wins 25 vs top-6 35-41: the opening is the real gap.
- Ladder same-time control CHAMP_NOW 15/30 (maze 12/22) on the seed-930 AB set. Paired by team+map vs CHAMP_NOW:
  HUNT 7 v 4 (18/28), LATE 2 v 5 (12/30), S1 3 v 6 (12/30). -> HUNT second paired set queued (teams 221,147,529,45,133,311,
  seed 932, HUNT2 + CHAMP2 same time).
- Codex audit 2 (22:05 IST): top risk = UNSEEN MAPS play maze mode (no known-map match -> bigFeed false, NN on, protectFrom
  default). "Open" maps are not open by topology (kelp edges/cell: Portals 0.56, Schooltime 0.38, Slithery 0.30 vs mazes
  0.14-0.49): bigFeed is a play-style label from ladder results; only size separates Slithery/Schooltime (>= 1500 cells)
  from all mazes (<= 1152). -> cand_unk_big (unknown map >= 1500 cells -> bigFeed mode) and cand_unk_open (all unknown ->
  bigFeed) vs champion on 8 maps_gen maps (laptop; Kaggle panel can't run maps_gen: kaggle_panel passes --gen 0 and an
  empty maps_gen dir). Also: promotion needs >= 60 same-time ladder pairs after an 80-160 game paired screen; 7/10 gate
  passes a fair candidate ~17%.
- cand_scav Kaggle maze 81/144 (vs 92): dropped. CUTOFF open-map ladder 3/12 (control pending).
- CUTOFF gameplay analysis (12 paired open-map ladder games vs same-time CHAMP_OPEN 6/12, CUTOFF 3/12): (1) the pairs had
  already diverged by r300 (e.g. 34 Portals 3 v 30 units, 196 Schooltime 64 v 51) although the code is identical until
  r350: ladder games have large early variance, so late-game features need many games or conditioning on the late state;
  (2) the hunt fired in 11/12 games from r350-460, often with 30-64 enemy units (L>=10 enemies are normal on open maps);
  (3) it pulled small dragons (feeders) away from the queen: 481 Slithery champion grew L44 and won, cutoff L17 lost;
  34 Schooltime L49 won vs L22 lost; (4) the true case (34 Portals: enemy down to one L37) was reported only at r447.
  -> cand_hunt3 = cand_hunt + hunt/trade only if the reported giant is longer than our queen + dragons within feedRadius
  of our queen keep feeding. Ladder: HUNT3 + CHAMP2 same time on teams 221,147,529,45,133,311 (seed 932).
- Unseen maps (8 maps_gen maps, 16 games per opponent): champion (maze mode) nick_farm 9, nick_arch4 7; unk_big 6, 6;
  unk_open 0/16 vs farm. The default (maze mode on unknown maps) is right; keep it.

## 30 Sept 22:45 IST: process change + opening root cause (Trophy)
- User: judge by thorough per-game analysis of small samples, not score; interleave ladder A/B; revisit dropped ideas
  (research_notes/PARKED.md). New: tools/game_review.py (per-game review, paired), tools/top_scrims.py --interleave
  (team-major order + running tally). Ladder pairs diverge by r25 (game_review), so 30-game ladder scores are mostly noise.
- CONTEST ladder 15/29 v CHAMP_NOW 15/30; target metric (maze r0-100 intake) not moved: median 80 v 91 -> not the lever.
- Trophy loss 646876: teams even to r30 (6 v 8 units); they enter the centre fountain room from r34 with 4-6 heads and
  snowball (r80 26 v 10); we never enter in 80 rounds although it is 20 steps' walk (no portal). Room produces 0.68
  pearls/round vs our start area 0.09 and the pocket we farm 0.30. y10k's compass never fires here (needs a tile with a
  mean countdown <= 12; the room's tiles are (5,30) and (1,100)). -> cand_compass2 (Codex): regional-rate compass,
  miners L <= 6 before r150 on mazes, target >= 2x the local rate, mild distance penalty.
- HUNT3 ladder A/B running interleaved (teams 221,147,529,45,133,311 seed 932).

## 30 Sept 23:40 IST: HUNT3 ladder review -> maze consolidation root cause (cand_pantry)
- HUNT3 9/30 (maze 5/21, open 4/9) vs CHAMP2 10/30 (maze 8/21, open 2/9), interleaved, teams 221,147,529,45,133,311.
  5 of 30 HUNT3 games reached "enemy <= 5 units with a longer giant, we >= 8 units": all lost. Trauma x2: the giant was
  never seen (0 giant packets). It is built LATE by feeding at home (221: L5 r400 -> L12 r450 -> L18 r499; 147: 12 -> 29
  -> 35), 4-8 cells from our nearest head. Slithery (529, L56): seen (1,064 packets) but not caught.
- The real failure: 221 Trauma had 38 units v 12 at r400 and ended with longest 11 v 18. Our feed pearls r350+ were
  eaten by us (30 of 33) but by 12 DIFFERENT dragons; the final longest ate 4 (147: 9 dragons, the final longest ate 0).
  Our end: 12 dragons L3-11 v their single L18. Cause in code: maze homing needs queen >= max(10, 2L) until r440;
  the existing pantry (x0.3 for pearls nearer the queen) is weak.
- cand_pantry (mine): maze only: endFeedFrom 440 -> 400; after r400 home to a queen >= L+2 from 16 cells; pearls within 4
  of the queen x0.1 for other dragons. Laptop paired (Trauma/Autarky/Default vs nick_farm + nick_arch4) with replays.
- Parked hunt follow-ups (PARKED.md): late-game search for the enemy giant (sonar echoes after r300 are used only for
  queen gossip); catching a free-running L50 on open maps.
- COMPASS ladder (interleaved, maze pool, AB set) running.
- cand_pantry laptop: vs nick_farm 16/24 (champion 14/24; 2 on-length flips, none against), vs nick_arch4 14 v 12. But the
  MECHANISM FAILED (tools/feed_sink.py): late feed pearls dropped 26 -> 42/game, share eaten by our final longest 29% ->
  16% (arch4 28% -> 5%), final longest unchanged (13.5). Trace trauma_A_1000: at r406 our longest is L3-4; L2/L3 drones
  feed into an L4 "queen" (half the mass lost per feed), pearls land 5-11 cells away and other small dragons eat them. At
  r400 we have no big dragon to consolidate into. -> cand_pantry2 (Codex): grow a sticky queen from r300 (pearl priority,
  no budding), feed only if queen >= max(8, L+3) and L >= 3 from within 2 in front of her, home only such drones.
- cand_pantry2 (Codex; 2 bugs fixed before testing: no homing from afar, maze feed never executed): vs farm 12/24, arch4
  12/24. Mechanism: feeding nearly vanished (8/24 games, 4 pearls/game), our longest r300/400/499 median 4/7/9.5 v
  champion 3/7/13.5. Strict feeding is chicken-and-egg: no big queen -> no feeding -> no big queen. Loose feeding does grow
  us 7 -> 13.5 after r400.
- Root cause of small dragons at r400 on mazes: swarmSplit keeps budding to r420 whenever UNITS < 40 (Trauma games: 38
  units -> budding to the end, everyone L2-4). Ladder enemy: 12 units with an L12 at r400. -> cand_budstop: on mazes a
  20+ swarm stops budding at r340 (only < 20 units keeps going to r420). Paired laptop test with replays.
- cand_budstop: units r400 40 -> 24 but longest r400 still 7, mass r400 100 -> 86, end mass 82 -> 67; 14/24 farm, 12/24
  arch4 (= champion). Budding is not the lever: small dragons do not grow because intake is low.
- Opponents' late consolidation vs ours (84 maze ladder games, tools/feed_sink.py --opponent): feed pearls dropped 42 v 25/
  game, distinct eaters 6 v 9, final-longest share 18% v 17%, final longest 15 v 14. They feed ~70% MORE, not more precisely.
  cand_pantry v1 already feeds 42/game (their volume) and was +4/48 paired in the sandbox -> ladder interleaved (maze pool,
  teams 221,147,529,45,133,311, seed 934) after COMPASS.

## 1 Oct 00:20 IST: Codex audit 3 (compass2, hunt3, the consolidation chain)
- Compass: intake/entry gains do not yet show a win gain; risk of herding (no assignment or "enough miners" check); not a
  safety bypass (pull only on pDeath <= 0.25 moves, safeClass sort kept). Judge the ladder A/B per game: intake, units,
  deaths, arrival order to r100, commitments per region.
- Hunt3: 9 v 10/30 doesn't settle the hunt. Flaw in my version: findAttack's HUNT3 rule trades with ANY visible enemy
  L >= 10 longer than our (locally estimated, possibly stale) queen, with no last-giant check. Correct test = narrow
  version, only games reaching the condition, logging report age/pursuit/trades.
- "Opponents feed 70% more" was unsupported by feed_sink (it counted every no-valid-action death). Re-measured from the
  preceding action (40 maze ladder games, r350+): ours 6.6 deliberate feeds/game, all SPLIT 1; theirs 13.5/game (SPLIT 1
  409 + an explicit 'suicide' action 131). The claim holds with the corrected measure (and they usually have fewer units).

## 1 Oct 00:45 IST: feeding volume (user: match the opponents' volume)
Deliberate feeds (no-valid-action after SPLIT 1 / suicide), r350+, tools/feed_count.py. Ladder mazes (84 games): champion
6.0/game, opponents 8.8/game (the earlier 13.5 v 6.6 counted only games with any feed). Sandbox mazes (vs farm / arch4):
| build | feeds/game | final longest | final mass | wins |
| champion | 12.6 / 9.8 | 13 / 13 | 82.5 / 62.5 | 14 / 12 |
| cand_pantry (endFeed 400, home 16, pantry) | 24.5 / 19.8 | 12 / 13 | 54 / 39.5 | 16 / 14 |
| cand_feedvol (pantry + endFeed 360) | 37.5 / 29.9 | 15.5 / 14.5 | 36.5 / 25 | 15 / 11 |
More feeding lengthens the longest (tiebreak 1) by ~2 but halves total mass (tiebreak 2, survival). Ladder: PANTRY +
FEEDVOL + CHAMP4 interleaved (maze pool, teams 221,147,529,45,133,311, seed 934) after COMPASS.

## 1 Oct 01:15 IST: COMPASS ladder review (interleaved, maze pool, AB set, 30 paired games)
COMPASS 13/30 v CHAMP3 17/30. Per game: r0-100 intake unchanged (median 83.5 v 82.5), units r100 13 v 14. By map (compass
v champion wins): Queen of Spades 0/5 v 4/5 (compass ate 4 pearls by r100 and was wiped vs team 34; 3 units r100 vs 534),
Trophy 2 v 1, Devil 3 v 1, Autarky 3 v 4, Default 3 v 4, Dilemma 2 v 3. QoS's richest regions (8,32)/(15,2) are mirror
images near the two starts: the compass can target the enemy's home fountain. -> cand_compass3 (Codex): skip targets nearer
the enemy start (mirror of ours under the detected symmetry) than ours.
- Compass line, sandbox vs nick_farm, QoS/Trophy/Devil (24 games): champion 12, compass2 7, compass3 9 (QoS fixed: 4 = 4),
  compass4 (only MY_ID % 3 == 0 miners, UNITS >= 6) 9/21 (3 sandbox load errors). Units at r100 show early COLLAPSES with
  compass2/3 (Devil 4-6 units in 3 games v champion 25-37): herding, as audit 3 predicted. compass4 removes most
  collapses (Devil 24-34) but still doesn't beat the champion. Parked: needs real coordination (gossip how many are
  already bound to a region), not an independent pull.

## 1 Oct 02:30 IST: feeding ladder result, continuous cycle, sprint finding
- Ladder (interleaved, maze pool, teams 221,147,529,45,133,311, seed 934): FEEDVOL 13/30, CHAMP4 10/30, PANTRY 9/30.
  First candidate ahead on the ladder (+3, within noise). Sandbox: longest +2, total mass halved, wins 26 v 26/48.
  Now in the continuous cycle (tools/cycle.py, 80 paired games with replays) before a larger ladder confirmation.
- Continuous cycle running (tools/cycle.py; review gate ladder/cycle/approved.txt). Split by mechanic (user): Claude =
  feeding + sprinting; Codex = turn order + scavenging (cand_cx_*). First Codex candidate cand_cx_order_1 (equal-
  distance pearl races: no tie discount when our dragon acts before the nearest enemy; ids act in ascending order)
  reviewed: correct, approved.
- Sprinting (40 maze ladder games, each dragon's last sprint): ours: attacks 29%, "no enemy within 3" 50% (38% of those
  die within 10 rounds anyway); theirs: attacks 63%, no-enemy 8%. Our no-enemy sprints are the last-resort escape
  (pDeath >= 0.9 -> 2-3 step sprints shedding tail): a symptom of cornering ourselves, not wasteful travel.
- Zig judge built in WSL (Ubuntu imported to D:\WSL\Ubuntu; judge /root/zig_judge/zig-out/bin/loong-judge; engine =
  Windows unswbc 1.1.0 wasm). Identical results to the sandbox on our bots, but NOT faster for us (30 s v 31 s per game):
  the time is our bots' own wasm compute, not judge overhead. tools/tourney.py: BC_ZIG_JUDGE / BC_ZIG_ENGINE /
  BC_WSL_DISTRO env vars, --seed-base. cycle.py: judge auto-select, two-stage screen (40 then 80 games only if
  promising), Kaggle offload with replays (cloud_tourney --replays --tourney-seeds; kaggle_panel --replays).
- cand_feedvol cycle (80 paired): 36 v 41 wins, flips +1/-6; final longest 15 v 13, final mass 52 v 67.5, feeds 19.5 v
  13; LEN+MASS losses 5 -> 2 (fixed) but WIN-LEN 21 -> 15 (burns mass when already ahead); QoS 4 v 7.
  -> cand_feedvol2: early feeding (r360) only when a recently seen enemy is >= our queen, else champion schedule.
- cand_cx_order_1 (Codex, turn order) cycle 80 paired: wins 43 v 41, flips +3/-1; target eat100 unchanged (110 v 110);
  h2h_ours 71 v 77, WIN-ELIM 23 v 20; per map small (+1 Autarky, QoS, Schooltime; -1 Trauma). Passes the screen -> next
  ladder batch. Gain not via the intended mechanism. Codex iterating.
- cycle.py: per-replay metrics cache (analysis was ~10+ min per candidate, re-decoding base games every time).
- cand_sprint1 (mine, sprint/trade: even head-on trades for L <= 4 drones from 8 units, local heads mine >= theirs) cycle 80
  paired (stage 1 from Kaggle replays: offload works, 40/40 pair with base names): wins 43 v 41, flips +5/-3, WIN-ELIM 25
  v 20; Devil 7 v 5, Dilemma 6 v 5, Autarky 7 v 6; QoS 6 v 7, Trauma 0 v 1. Median attack sprints unchanged.
  Passes the screen.
- Stack: cand_stack1 = cand_cx_order_1 + cand_sprint1 (independent code paths) queued in the cycle. Ladder batch 1
  (interleaved: ORDER1, SPRINT1, CHAMP5; teams 219,859,733,15,72,64 = ranks ~56-61, all maps, seed 940) running.
- cand_feedvol2 stage 1 (40): 18 v 21, flips 0/-3. Why: "enemy seen >= our queen" is true most of the mid-game (our queen
  L6-7), so early feeding fired anyway (5.2 feeds before r440 v 0.9); mass 55 v 79.5, longest unchanged; lost QoS A (mass
  70 -> 12), QoS B (wiped), Autarky A. Per-dragon local signals can't tell "behind on length". FEEDING LINE PARKED
  (pantry/feedvol/feedvol2/budstop all trade mass for length).
- cand_cx_scav_1 (Codex): 35 v 41, flips +4/-10, final_mass down: REJECT; scavenging parked (3 negatives).
- Why cand_stack1 didn't add up (80 paired games, 4 builds): 64/80 games have the same outcome for base, order_1, sprint1
  and stack (35 WWWW, 29 LLLL); only 16 swing. Within those, wins don't add (3 stack-only wins, 3 stack-only losses): each
  change alters the trajectory early. Systematic part: Queen of Spades base 7, order_1 8, sprint1 6, stack 4 (stack's QoS
  losses end with mass 9-15 v 36-68): sprint1's UNITS >= 8 trade threshold makes small QoS armies (8-11 units at r100)
  trade themselves away; bigger armies (Devil 7 v 5, Dilemma stack 8 v 5) profit.
  -> cand_sprint2 = keep the 12-unit threshold, L <= 4 and mine >= theirs; cand_stack2 = order_1 + sprint2. cycle.py: a
  third seed (120 games) for cand_stack* when still promising.
- cand_cx_order_3 (Codex; compile error fixed by Claude): 44 v 41, flips +11/-8, hit_other_body 7 v 6.5 (target not
  moved), final_longest 11.5 v 13, mass 59 v 67.5; Autarky +2, Devil +2, Schooltime +2, Trophy -2. Passes, but costly
  late and noisy. Review gap: approvals now include a compile check; cycle.py builds before fighting.

## 1 Oct 05:40 IST: "start strong, maintain, then throw" (user's observation, confirmed)
- Unexplained winner order_3: its flipped wins are CONVERSIONS (both builds dominate by r100, order_3 eliminates; enemy
  splits r100-200 8 v 35). Pearl denial REJECTED: across all 80 games enemy intake r100-300 is not lower (163.5 v 143.5);
  in flipped games the enemy eats little because it is already dying. order_3's +11/-8 looks like churn.
- Champion, 120 sandbox games: led >= 2:1 in units at r100 in 31; LOST 10 of those, all on length. (a) Schooltime x7: we
  hit the 64 cap by r100-200 and stall (61 v 27 -> 59 v 62) while they regrow, then lose the late length race. (b) mazes
  (Devil x2, Autarky): 31 v 5 / 43 v 6 at r200-300, never eliminate; their survivors build one long dragon.
  -> cand_press: with 40+ units, L <= 4 drones take any even trade and hunt equal-sized heads. cycle.py metric "throws"
  (led 2:1 at r100 and lost) as its target.
- cand_stack2 (order_1 + sprint2), 120 paired (3 seeds): 58 v 54, flips +11/-7, h2h_ours 69 v 74. Best so far.
- cand_sprint2: 43 v 41, flips +4/-2.

## 1 Oct 06:20 IST: friendly head-ons, swing-game reading, one dev line
- pair_diff.py (round-by-round paired diff + decision tags from the replays' dragonIndicator events: sandbox replays carry
  each dragon's tag DOOMED/ESCAPE-SPLIT/BUD/ATK/FEED; our tools had ignored them).
- stack2 swing win (Autarky B 1017): champion led 37-45 v 4-6 units r150-400 and LOST on length (138 mass, L12 v 19 mass,
  L13): few ATK tags, ~10 DOOMED/25 rounds (Autarky pocket), enemy survivors kept splitting; survivors were WITHIN 3 cells
  of our heads (r400: 5/5) but the hunt term only targets enemies >= L+2 and our L3 drones can't reach 3 cells.
  stack2 converted (enemy splits 3,3,2,0). -> cand_press2 (30+ units hunt/trade ANY enemy head) + cand_stack3 = stack2 + press2.
- stack2 swing loss (Schooltime A 1000): dominant 62 v 10 at r150, capped at 64 while the enemy regrew to 62; our
  head-on deaths 40 v their 22 in r250-300 = friendly head-ons.
- Friendly head-on pairs/game (champion, 120 games): Portals 65, Schooltime 32, Default 21, Slithery 15, QoS 14, others ~0.
  Movers are ordinary pearl-seekers stepping blind through portals onto farming friends. cand_portal (blind step 2.0 on
  open maps): pairs -30% but Portals wins 2 -> 0/8 (stopped using portals). cand_portal2 (don't park on exits): no effect.
  -> Codex: portal probe via sonar (rays pass portals; echo ally_head) as a patch on cand_dev.
- One development line: cand_dev (= stack2), edited in place; 131 old cand_* archived to ladder/archive/cands/.
- cand_press2 (30+ units hunt/trade ANY enemy head): 44 v 41, flips +6/-3, THROWS 10 -> 6 (mechanism works): maze throws
  converted (Autarky, Devil, Trauma wins mostly by elimination). All 6 remaining throws are Schooltime. Side effect:
  final_longest 13 -> 10.5, final_mass 67.5 -> 75. (cand_press at 40+: throws 10 -> 9 only.)
- Schooltime throw anatomy (press2, A 1017 v arch4): capped at 64 units with LONGEST 4 for 200 rounds (BUD 27-54, ATK
  8-19, DOOMED 11-30 per 25 rounds: churn), our mass flat ~140-150 while theirs 61 -> 223 and their longest 6 -> 16; r325-
  400 our feeding collapses 63 -> 8 units (mass 151 -> 79); they end L45-64 v our L20-49. cand_cap (grow to 8 before
  budding at 50+ units): longest r200 7-8 (v 3-21), mass r200 +20-30, but outcome 0/4 = champion 0/4: not the lever.
  Schooltime = open-map growth/consolidation race (parked with this trace).
- tools from the analysis-tools agent: mech_board.py (all mechanics, cand v base, swing-only column, paired direction),
  replay_cache.py (decode once), swing_report.py, pair_frames.py, metric_selftest.py (AGENTS.md section 9). Our path-based
  eat counter is +-20% per game but unbiased (median ratio 1.00).
- mech_board press2 v champion: attack share of sprints 24 -> 31%; our head-on deaths THEY initiated 19.7 -> 12.3 (4/41
  games); DOOMED deaths 136.5 -> 126.5; wins by elimination 25% -> 36% (9/0); dominant-but-lost 12% -> 7%; final longest
  15.8 -> 14.1; feeds r300+ 15.6 -> 12.4.
- press2 new loss (Trophy B 1017 farm): press fired at 29-30 units with only a 1.5:1 lead (29 v 19): ATK 12 v 4 per 25
  rounds, 1-for-1 trades, and the enemy REGREW faster from the wreckage (splits 16-19 v 6-12): 25 v 15 at r250, while the
  champion farmed to 40 v 6 and won. Refinement for cand_dev: press when (30+ units AND local heads mine >= theirs + 2) or
  40+ units.
- cand_stack3 (stack2 + press2), 120 paired (3 seeds): 59 v 54, flips +13/-8, throws 10 -> 6. Best so far.
- cand_dev v1 = stack3 + gated press (pressOn(): 40+ units, or 30+ and visible heads mine >= theirs + 2). In the cycle
  (3 seeds). Working folders: viper_nn, cand_dev, cand_stack2 (kept for its pending ladder confirmation).
- Ladder batch 1 (teams 219,859,733,15,72,64; some requests refused, ~20 games per build), unattributed tallies:
  SPRINT1 8/20, ORDER1 5/20, CHAMP5 3/20. Final attributed RESULT pending.

## 1 Oct ~18:00 IST (Claude) NEW RULES: first measurements
- Tools: replay.py decodes result queen length (team struct i32 @12); tools/queen_report.py (queen fates, how decided);
  cycle.py queen metrics + METRICS_VERSION=3 cache keys (fixes stale friendly_h2h KeyError); mechanics.py sprint cost
  with ceil(L/4) free steps; opencode added queen columns to pair_diff/viz (reviewed: OK).
- Champion on engine 1.2.3 vs nick_farm/nick_arch4 (40 games): OUR queen alive at end 0/40 (median death r36), theirs 1/40.
  Decided: longest 25, elimination 13, queen 1, total 1.
- **Legacy maps doom the queen at spawn**: on Autarky, Dilemma and Slithery dragon 0/1 starts at the head of a 1-wide dead-end
  corridor (2-4 cells ahead, pearl-lined). Splits keep the FRONT as the parent (= queen id) and the child is the reversed
  rear, so the queen can't turn back: both queens die by r5-r10 on every game there -> queen tie 0/0, longest decides.
  QFIT (Codex, applied in cand_dev) can't help there. Queen rules matter on Trophy/QoS/Default/Devil/Trauma/Schooltime/
  Portals and on the coming new maps.
- cand_dev (old stack + NEWRULES + QFIT): queen alive 4/40, median death r101 (vs r36), wins 19/40 vs champion 23/40.
  Clean test running: cand_q = champion + NEWRULES only (no stack, no QFIT) -> ladder/newrules_q1_*.txt.

## 1 Oct 18:00-19:15 IST (Claude) new-rules ladder: findings from our own losses (continuous autoscrims)
- QUEEN IDENTITY BUG: queens are ids 0/1 but on ladder maps id 0 can be team B's (DRAGON lines swapped). Verified from
  results (e.g. trauma_B_815767: A's queen = id 1). Bot used MY_ID==MY_TEAM -> fixed (isTrueQueen = MY_ID<=1, enemy
  queen = any enemy id<=1). Tools fixed (queen = team's first dragon). Subs: 14061 (bug) -> 14101 (fix).
- Enemy queens on the ladder die early in ~100% of our games (0/15, 0/15): a queen that SURVIVES wins at r500.
  QHIDE (cand_q5): queen stays in fully open space (room penalty), >= 4 from enemy heads, not beside portals (Trauma
  vs code matters: our L2 queen circled a 2x2 loop for 200 rounds, then a friend came out of the adjacent portal and
  boxed her in, r366). Sandbox queen alive 4/24 -> 8-9/24.
- SINK: the feeding sink election was locked to the true queen (L2, hiding) -> nobody fed anyone -> longest-tiebreak
  throws (Trauma: 31 units/88 mass vs 17/62, longest 8 vs 33). Reverted to the longest-dragon sink.
- MAP RECOGNITION FAILS ON THE LADDER: on QoS/Devil/Dilemma/Slithery/Schooltime about half the ladder games never get
  the known-map flag K (QoS vs Adrak: K in 2/702 indicator turns; our 2 dragons ate nothing for 70 rounds). Our
  viewAgrees() rejects the map when a pearl countdown contradicts the stored table (sandbox always agrees). MAPFIX:
  identify by kelp/portals only; learn pearl gaps from observation. (cand_q6 = q5 + Codex free-sprint 2/3-step options
  + MAPFIX; sub 14132.) The champion probably suffered the same on the old ladder: check old ladder replays' K share.
- Cutlery deliberately kills stub dragons in dead-end pockets (SPLIT 1 at the pocket end, rear child escapes):
  264 such deaths on Portals; same as our ESCAPE-SPLIT/DOOMED economically (all deaths drop ceil(L/2) pearls).
- Portal friendly head-ons (~55 pairs/game on Portals) unchanged by a probe ray (cast after the move from the new
  head + warning message): the victim usually arrived after the probe. Open problem.

## 1 Oct 19:30-20:10 IST (Claude) Adrak vali chai A/Bs (unranked, interleaved, same maps)
- q6 (14132) 1/5, q7 (14167, SHAFT: no miner excuse for L2) 1/5 [Schooltime W both]; q7 vs q6 economy on maze maps
  clearly better (Devil r0-150 eaten 76 v 30, Autarky units r150 13 v 8) but still crushed (Adrak 27-36 units by r125).
- q8 (14185) = q7 + COMPASS (Codex port of compass4, gated to Schooltime/Trophy/Devil, 1/3 of miners, r<150; Claude
  re-applied the failed activation hunk + C<x,y> indicator). vs Adrak: q7 1/5, q8 1/5 (both won QoS only).
  Schooltime: q8 farms the bottom fountain (C30,36 621 turns): eaten r0-150 447 v 404 (q7: 254 v 483), units r100 55 v 47
  (q7 29 v 50) = opening economy FIXED there; then attrition r150-300 (55 -> 30 units vs their 62) and at r350-360
  feeding took us from 22 to 6 units; the lone L36 sink died at ~r405 -> lost by ELIMINATION.
  Trophy: compass fired 70 turns, eaten 28 v 126 (q7 99 v 165): compass on Trophy looks harmful (1 game).
- q9 (14198) = q8 + FLOOR (no feeding at <= 10 units). ACTIVE. Rating 1769, rank 22 (20:10 IST).
- nr1 (from-scratch net on 969 new-rules top games, Kaggle): val acc 0.707 (n4 trained 0.66-0.67 on old data);
  held-out new-rules set built (D:/battlecode/tmp/data_nr_ho, 565 games); log-loss compare needs torch (Kaggle).

## 1 Oct 21:20 IST (Claude) pure rules vs hybrids on the ladder (top 4: teams 20, 206, 314, 801; same maps, interleaved)
- pure rules (14227, wNN 0) 6/20 (open 2/7, maze 4/13); rules+n4 (14198) 5/20 (0/7, 5/13); rules+nr1 (14226) 4/20
  (1/7, 3/13). Equal within noise, although the sandbox vs nick bots said 7/28 vs 20/28 (the sandbox overstates the network).
- Trauma is our best map vs top teams (pure rules 4/4, n4 3/4, nr1 3/4); Devil/QoS/Schooltime/Dilemma/Trophy 0 for all.
- Networks on 416 held-out new-rules top games: n4 NLL 0.666 acc 70.5%, nr1 0.652 / 71.3%, n4nr (n4 fine-tuned) 0.651 / 71.4%.
- Decision (user: main model pure rule-based; two tracks): ACTIVE = pure rules 14227. Rating 1800, rank 19.

## 1 Oct (opencode) friendly head-on tool
- tools/friendly_h2h.py: per replay, counts OUR head-on deaths; classifies each MOVER's death step as crossing a PORTAL edge, OPEN edge, or other; pairs victims (a head-on kills two dragons in the same round).
- Queen id assumption already correct in codebase: queen_report.py uses min(i for i in team if team[i]==t); replay.py reads queen from result struct.
- Cycle restarted to pick up friendly_h2h fix; cand_dev re-queued.

## 1 Oct 22:00 IST (Claude) SWAPFIX + QSAFE from ladder losses (Quaker, Peanut Butter)
- SWAPFIX (bug, also in every earlier build): own-body lookup at r0 matched KM->spawns by TEAM; on ladder maps with
  swapped DRAGON order it found nothing -> body "unknown" beyond the 7x7 view -> doomedSplit refused ("DOOMED unknown
  body"): our L14 Autarky / L11 Dilemma queen died at r3-5 WITHOUT shedding (lost 12-14 mass at r0; Peanut Butter split 4x
  at r0-1). Fix: match by head cell; MAP_TEAM recorded; compass start side fixed too. Verified on maps_swap/: queen sheds
  3x (SHED 2, ESCAPE-SPLIT 11) like on unswapped maps.
- QSAFE: queen greed x0.2 after r100, danger x3, blind portal step -120, portal-adjacent cells -40 (2 away -20).
  Losses it targets: Devil vs Quaker (queen alive to r426, theirs dead r19: chased pearls into heads), Trauma vs Quaker
  (r362 portal step -> DOOMED), Trauma vs Peanut Butter (queen alive r450, theirs dead r41: friend 303 stepped through a
  portal onto her at r452).
- Builds: cand_r (pure rules, main line) and cand_rh = same + network (Y.7.12.52, sub 14255, ACTIVE).
- Delegated: Codex = true-queen position gossip so friends avoid portal landings near her (QPOS); opencode =
  tools/ladder_digest.py (thrown wins + killer, eat curves, numbers gap, feeding collapse); Kaggle = cand_r vs
  bots/newrules_rules panel (kp1001_2143, cloud engine now unswbc 1.2.3).

## 1 Oct (opencode) ladder_digest
- tools/ladder_digest.py: per-game analysis of our replays (result/how, THROWN WIN flag + killer, economy windows, numbers gap, endgame longest/units, feeding collapse).
- Reuses queen_report.analyse for queen fates, friendly_h2h mover/edge logic for killer identification, eatsrc.py pattern for pearl eating attribution.
- Test: pb/ 5 games (1 thrown win: trauma_B_824701, killer dragon 303 at r452), quaker/ 5 games (3 thrown wins: devil_B_824602 killer 714, schooltime_B_824603 killer 0, trauma_B_824606 by hit self).
- Key finding: thrown wins are common in losses (3/5 quaker, 1/5 pb) - our queen dies late after theirs is already dead, converting a would-be win into a loss.

## 1 Oct (opencode) ladder_digest
- tools/ladder_digest.py: per-game analysis (result/how, THROWN WIN + killer, economy windows, living/mass/longest, numbers gap, feeding collapse) + loss 'why' classification.
- Fixed: 'units rN' was mass sum; now 'living rN' = count of living dragons at START of round N (alive set: map DRAGON + dragonSplit children - dragonDeath ids).
- Fixed: numbers-gap now first round r>=10 where their living >= 1.5x ours (and >= ours+4); was r0 due to mass bug.
- Added: mass rN (sum of lengths) and longest rN at r100/200/300/400/450 per side.
- Test cmm/ (5 games): 1 thrown win (schooltime_B_822526, queen died r426 by hit other body); loss whys: devil OTHER, portals ENDGAME, schooltime THROWN WIN, slithery ECONOMY.
- Test pb/ (5 games): 1 thrown win (trauma_B_824701, killer dragon 303 their team, open edge, r452); loss whys: autarky/default/prisoners OTHER, schooltime ECONOMY, trauma THROWN WIN.
- Test quaker/ (5 games): 3 thrown wins (devil_B_824602 killer 714 our team, schooltime_B_824603 killer 0 their team, trauma_B_824606 by hit self); loss whys: devil THROWN WIN, slithery ECONOMY, trauma THROWN WIN.
- Key finding: thrown wins are common in losses (5/15 games) - our queen dies late after theirs is already dead, converting a would-be win into a loss.

## 1 Oct (opencode) ladder_digest fixes
- Fixed team mapping: killer team now compared with ours (0 for A, 1 for B) instead of hardcoded 0; default_B_826557 dragon 304 now correctly shown as 'their team'.
- Fixed numbers-gap: now requires r>=20 and both counts >= 4 (was r>=10 with u>0, giving false r10 gaps).
- q2/ (5 games): 1 thrown win (default_B_826557, killer dragon 304 their team, open edge, r408); loss whys: default THROWN WIN, queen_of_spades OTHER, trophy OTHER; numbers-gap [20].
- cmm/ (5 games): 1 thrown win (schooltime_B_822526, queen died r422 by hit other body); loss whys: devil OTHER, portals ENDGAME, schooltime THROWN WIN, slithery ECONOMY; numbers-gap [20, 20].

## 1 Oct 23:50 IST (Claude) QHAVEN no gain; Dilemma loop-farming insight
- Kaggle kp1001_2306 (paired seeds with kp1001_2213): cand_r+QHAVEN 28/80, queen alive 18/80 vs cand_r 30/80, 19/80 ->
  QHAVEN reverted (patch kept: ladder/cosci/patches/cx_qhaven_1.patch). Pure rules vs nick: queen alive ~19/80; most
  queen deaths are enemy head-ons while our army is being eliminated (elimination 30-32/80 games).
- vs 中国必须人能飞 (1-4): Default = thrown win again (queen alive to r286, theirs dead r35); maze economy r0-150:
  Autarky 51 v 193, Dilemma 27 v 162, Trauma 43 v 114.
- DILEMMA anatomy (r35 full frame): the 1-wide columns x=14 and x=17 hold pearl tiles in the top/bottom "shafts", and they
  CONNECT through the vertical wrap (row 15 -> row 0): a closed vertical loop. Their L11 dragon (x0) circulates column 14
  eating every pass; they split an L10 off it. We send many L2s at the same shaft pearls (3 of ours targeting T17,13, 2
  T17,2) and 7 of our 9 deaths r4-58 are DOOMED L2-3 in those columns (enemy bodies fill the loop). Idea "LOOPFARM":
  detect closed 1-wide loops with pearl tiles on known maps; send ONE dragon long enough to circulate (and only it) and
  keep L2s out.

## 2 Oct 00:05 IST (Claude) QFEED: the meta is turning to queen length
- Ladder Trauma vs No Idea (1517): BOTH queens alive at r500; they fed THEIR queen 2 -> 13 -> 16 from r350 (units 23 -> 2)
  and won 'by queen' (ours L3, hiding). Portals: their queen grew to 11 at r400. Teams are adapting.
- QFEED (cand_r/cand_rh): from r370 the true queen (position from QPOS gossip) is the feeding/homing sink, any queen
  is "worthy", and she eats again (greed back to 1). Sandbox vs nick_farm Trauma/Default/QoS: 6/6, our queen L53 on Default B.
  Uploaded Y.7.12.55 (sub 14295), ACTIVE. Kaggle panel kp1001_2359 (cand_r vs cand_rh, both QFEED).
- Pending: kp1001_2347 (free-sprint on/off A/B), Codex LOOPFARM.

## 2 Oct 01:00 IST (Claude) cycle: free sprint neutral; vB.19 economy edge = L2 mining
- Kaggle kp1001_2347 (paired): cand_r (FSPRINT 2-3 step free options) 25/80 vs cand_rnf (off) 24/80 -> neutral, kept.
- Teammates' vB.19 (sub 14297, opponents/vb19) beats cand_rh 13-7 (sandbox, 20 games). Codex diff
  (ladder/cosci/vb19_diff.md): same code family; budding window differences are inactive before r150 (games identical
  r0-150 with the port: no gain). Autarky timeline vs vB.19: identical to r10, then they eat 3x per round r20-80 with MORE
  deaths (25 v 13 by r80): their miner rule allows L2 drones (except Devil) and excludes only the TRUE queen. MINE2 (port of
  that rule): Autarky r0-150 intake 98/85 -> 144/164 (vB.19 194/181), Dilemma A 35 -> 104; vs vB.19 on 5 maze maps 4/10 vs
  base 3/10. ROWLATE (give-way only after r150): small effect (4/10). Both merged into cand_r/cand_rh.
- team calc's writeup (rank 2) parked in PARKED.md: their edge is a 3-5 round simulation search over net-played rollouts.

## 2 Oct 01:00 IST (Claude) PAUSED by the user ("take a break, let my teammates work")
State at pause:
- Active ladder build: 14270 (Y.7.12.54, hybrid; queen safety + QFLEE). Uploaded but idle: 14295 (Y.7.12.55 = + QFEED).
- Local working copies: cand_r (pure rules: + QFEED + MINE2 + ROWLATE, not uploaded), cand_rh (same + network),
  cand_rl (LOOPFARM), cand_rx/rv/rs (vB.19 experiments). Opponents added: opponents/vb19 (= vB.19.1, identical code).
- Kaggle panels still running (fetch with tools/kaggle_panel.py fetch --batch <b>): kp1001_2359 (QFEED r vs rh),
  kp1002_0017 (cand_rl LOOPFARM vs nick+vb19), kp1002_0036 (cand_r MINE2+ROWLATE vs nick+vb19); Colab kp1002_0023.
- Next when resumed: judge those panels; if MINE2 line beats 14270-equivalent, upload cand_rh; Devil economy gap vs vB.19.
- Still running (passive, read-only): tools/slope_collect.py (new-rules top games), tools/our_games.py (our ladder games).

## 2 Oct 01:15 IST (Claude) experiments ended (user: wrap up)
Final results of the last experiments (Kaggle/Colab, vs nick_farm + nick_arch4, 80 games, paired seeds on Kaggle):
- QFEED (feed the true queen from r370): pure rules cand_r 22/80 (pre-QFEED same seeds: 25/80 in kp1001_2347,
  30/80 in kp1001_2213 -> no gain, possibly -3..-8 = within noise); hybrid cand_rh 45/80 (56%). Kept in code because the
  ladder meta is turning to queen length (No Idea fed their queen 2 -> 16 and won 'by queen'), but NOT proven.
- Hybrid vs pure rules on identical code: 45/80 vs 22/80 (Kaggle) and 44/80 vs 17-22/80 (Colab, other seeds): the
  network still carries maze maps (Devil/Autarky/Dilemma). On the ladder vs the top 4 they were level (5/20 v 6/20).
- Free multi-step sprint: neutral (25 v 24 / 80). QHAVEN: neutral (reverted). GROW (protect sink from r200): worse.
- UNFINISHED when stopped (Kaggle kernels keep running; fetch later): kp1002_0017 = cand_rl (LOOPFARM) and
  kp1002_0036 = cand_r with MINE2+ROWLATE, both vs nick_farm, nick_arch4 and vb19
  (`python tools/kaggle_panel.py fetch --batch kp1002_0036`). MINE2 local evidence: Autarky r0-150 intake ~90 -> ~155,
  vs vB.19 on 5 maze maps 4/10 vs 3/10.
- Stopped: tools/our_games.py and tools/slope_collect.py collectors, all local games. Active ladder build: 14270.

## 2 Oct 01:50 IST (Claude) final sample analysis of MINE2 (paired local games vs vB.19, same seed; cand_rs = MINE2 hybrid, cand_rx = without)
- Autarky B: MINE2 keeps 20 units r50-r150 (vs 15) while their swarm is 19-25; our r0-150 deaths become 33 DOOMED pocket
  deaths (vs 9) = the vB.19 economy (cheap L2 stubs recycle into pearls). Both lost (MINE2: on total length 28 v 100 at
  r500; without: eliminated r466) -> mechanism works, result not converted.
- Dilemma A: both stagnate at ~6-10 units / mass 14-23 for 200 rounds (vB.19 also only ~20-30): low-pearl map; both lost
  on longest (7 v 2, 8 v 2).
- Trophy A: identical to r50, then MINE2 lost its units faster (r175: 2 v 11) and was eliminated earlier (r200 v r275);
  both lose the r50-150 head-on war (their 20 -> 51 units).
- Decision: NOT submitted. MINE2 improves the opening economy where pockets pay (Autarky), but no sample converted it into
  a win, and QFEED is neutral in the sandbox. Active stays 14270. Kaggle kp1002_0036 (cand_r MINE2, 120 games) was still
  running at the end.
