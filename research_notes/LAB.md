# LAB (Claude, Codex, Gemini: co-scientists). Keep this file SHORT: facts <= 15 lines, entries <= 12 lines each.

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
