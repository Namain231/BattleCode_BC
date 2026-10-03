# LAB notebook (append-only; dated entries, newest last)

Old-rules entries (to 1 Oct afternoon) are in archive/LAB_to_1oct.md.
Current state and distilled insights: ../HANDOVER.md.

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

## 2 Oct 05:10 IST (Claude) Y.9 released (sub 14391, ACTIVE)
Y.9 = hybrid (n4) + rules: QFEED/QFEED2 (feed the true queen from r370; feeders may reach her), MINE2, ROWLATE, GROWS
(Slithery grower protected from r100), HUNTL (Codex: far drones ram enemy giants late), FUNNEL (from vB.20: map-wide feed
radius, late floor 2) and SELFTRACK.
- SELFTRACK (bug, all builds): ladder Slithery vs err404: our L55 giant died 'hit self' at r460 after "DOOMED unknown
  body" (an L29 at r427 too): when a long dragon coils inside its view the visible chain can mis-link, the match vs the
  predicted body fails and the tail becomes -1 forever. Now the bot trusts its exact own-move history when complete.
- Evidence: vs vB.19 open maps + Trauma, FUNNEL 12/16 vs 9/16; Y.9 vs vB.19 on 6 maps 8/12; Y.8 (rh base) vs vB.20 13/7.
- Rejected: vB.20 port of QSTRICT + PAIDSPRINT (Codex patch): queen alive 2/16 vs 7/16, wins 10 v 11.
- vB.20 (teammates) has the queen-ID bug again (isTrueQueen = MY_ID == MY_TEAM): wrong on ladder maps with swapped DRAGON order.

## 2 Oct 08:00 IST (Claude) SEARCH1 rejected
- Kaggle kp1002_0605 (paired seeds, 120 games vs nick_arch4/nick_farm/vb19): SEARCH1 (Codex 2-ply own-dragon search,
  switches ~1.9% of moves) 39/118 vs Y.9.1 62/120; Colab (other seeds) 23/48 vs vb21+vb19. Clearly worse: a greedy
  continuation with others frozen re-ranks moves badly; the leaf evaluate() without the network/compass terms is not
  comparable to the root scores. Search needs opponent replies + a validated simulator (S2) before another try.
- FEED2 (sink-only feeding, adjacent trigger, crowd cap, stagger, feeders <= 6): vs vb21 14/24 vs control 15/24,
  vs vb19 17/24 vs 15/24 (control's nick_farm part still running).

## 2 Oct 09:00 IST (Claude) SEARCH1 tuned by replay review -> SEARCH1v (trap veto)
Source of the idea: team calc's writeup + Stockfish/calc on Discord (short look-ahead per candidate move).
- v1 (Codex): switched 67,612 decisions in the Kaggle panel, mostly calm positions (rm24, pd0) on 1-3 point score noise.
- Root causes found in replays/debug tags: (1) switched on score improvement; (2) leaf safeClass is noisy; (3) leaf
  evaluate(..., deepAllowed=false) returns a 0.5 pDeath PLACEHOLDER whenever room is short -> continuations looked unsafe.
- v1v: veto only: switch only when EVERY continuation of the chosen move is >= 60% deadly and the runner-up has a <= 25%
  one; leaves use the full survival search. Result: 187 switches in 163k decisions (0.1%), each a real dead end
  (frame-checked default_A r144: L2 drone turned away from a 3x3 portal room instead of entering it, then grew to L3).
  10 games vs vb19: 4/10 (same as baseline range). Kept as a cheap safety layer; impact small.
- Next (search): opponent replies + S2-validated simulator before scoring-based switching again.

## 2 Oct 08:50 IST (Claude) GROWS2 parked; agy Dilemma -> DILSHAFT
- GROWS2 (Slithery grower from r60, L>=4): Colab 15/36 vs control 13/36; local paired 4 games 1/4 vs control 3/4.
  Longest at r200/r300 (viz headers): g2 17,7,7,10 / 21,9,10,6 vs control 20,7,11,6 / 18,8,4,6: no real growth gain.
  Parked (PARKED.md). Notable in BOTH: on side A our units collapse to 8-10 by r400 (theirs 32-40) while our longest
  is 24-41: late feeding still drains the army on Slithery.
- agy (Gemini, after fixing its hung process): Dilemma deaths = L2-3 drones (MINE2) enter the 1-wide gap-1 pearl shafts
  (x=14/17) and die DOOMED (7 of 9 early deaths). DILSHAFT = treat Dilemma like Devil in MINE2 (miners need L>=3).
  Local paired test running (D:/battlecode/tmp/dl).
- DILSHAFT local paired vs vb21 on Dilemma: 4/4 vs control 2/4 (side A flips both: r50 mass 21 vs 14). Kaggle paired
  check vs 4 opponents x 4 seeds launched (tag dl).
- NNFAST (Codex, cand_nf): skips all-zero input planes + branchy zero-skips in conv1. Peak CPU 57.4M -> 51.7M on
  trophy/devil (4 games), not the claimed 2-4x: most planes have some nonzero cell, so whole planes rarely skip. Not
  verified bit-identical (games differ, but our bot uses wall-clock guards, so games differ run to run anyway; no native
  compiler on the laptop for a logits harness). Parked until search needs the CPU; next version should build a
  nonzero-cell list once and scatter (true sparse), verified by nnSelfTest logits.

## 2 Oct 09:05 IST (Claude) POFPOF 2-3 loss (-36): queen boxed in by our own swarm -> QROOM
- Lost Portals (queen 0 vs 3 while leading 26 units to 4 at r200), Trauma (queen died r232 hit wall, L2 in a portal
  corridor), Schooltime (on total, queen died r359 head-on). Won Trophy and Devil by elimination.
- Portals frames r287-291: our true queen is still L2 at r287; after qfeedFrom (280) ROW switches off and 31 friendly
  L2 drones pack the kelp boxes around her: room 13 -> 4 -> 0, DOOMED, illegal move. Sandbox had shown the same at
  r355/r262 (CROWD comment) but CROWD only scores HER moves.
- QROOM (cand_qr): friends never end a move on a cell adjacent to her head, all game (feeders trigger at distance <= 3,
  so feeding still works). Local paired test Portals+Trauma vs vb21, 8 games each with queen fates (D:/battlecode/tmp/qr).
- Wider point: our queen is L2-3 all game on these maps; opponents' queens are L3+ and survive -> they win by queen.

## 2 Oct 09:30 IST (Claude) Y.9.3 released (sub 14549, active) = Y.9.2 + QROOM + SEARCH1v
- QROOM local paired Portals+Trauma vs vb21: 4/8 vs 3/8, our queen alive at r500 5/8 vs 3/8 (flips: Portals A_1017 by
  longest 31-23; Trauma B_1017 by queen 20-0 instead of on total).
- SEARCH1v Colab: vs vb21 25/40 vs control 23/40; vs vb19 22/40 (control part pending). Rare trap veto, no harm.
- DILSHAFT REJECTED by mechanism: Kaggle paired Dilemma 15/32 vs 19/32; vs nick_farm/nick_arch4 on side B 0/8 vs 8/8.
  Without L2 shaft miners our L2s fight head-ons instead (13 vs 8 early head-on deaths) and units fall to 3 by r150
  (control 6-9); the shaft deaths are RECYCLED (the Adrak pattern: pearls drop back into the gap-1 shafts and get re-eaten).
  agy's analysis counted the deaths but not the recycling. Side A gain vs vb21 (3 vs 1) parked.
- FEED2 Colab 40/72 vs 38/72 neutral; Kaggle all-maps still running.

## 2 Oct 09:45 IST (Claude) agy's vB.21 queen study -> QGROW
- Verified in code: our TRUE queen (MY_ID <= 1) still runs swarmSplit(): it buds a 2-child every time she reaches L4,
  gated only by protectedQueen(), which tracks the ELECTED longest from r400. That is why she is L2-3 all game.
  vB.21: queen grows hard r0-150 (growth x2.2), stops budding at UNITS >= 40 or r260, never blind-steps (-50000,
  safeClass 0), sprint-reach exclusion (-200000), room < 12 -> unsafe, ROW all game.
- QGROW (cand_qg = Y.9.3 + queen stops budding at UNITS >= 40 or r260). Paired local test portals/trauma/schooltime vs
  vb21, 12 games each, queen fates (D:/battlecode/tmp/qg). Next candidates from the study: queen blind-step hard veto
  (our -120 keeps safeClass on KM), sprint-reach exclusion for the queen.

## 2 Oct 10:00 IST (Claude) FEED2 rejected; queen candidates
- FEED2 Kaggle all maps (paired, 3 opponents): 58/117 vs Y.9.2 67/116 -> REJECTED (Colab subset had been neutral).
- Colab qq (vb21 part, 24 games each): QGROW 12, QREACH 13, Y.9.3 control 12. Colab workers don't keep replays, so
  Kaggle batch (tag qk) reruns qh/qg/y93 with replays for the queen-fate review.

## 2 Oct 10:20 IST (Claude) STAR 0-5 (-87): queen deaths; QBOX bug fix -> Y.9.4 (sub 14576, active)
- Schooltime (ladder VARIANT map, extracted from the replay to maps_swap/schooltime_ladder850917.map): our L4 queen
  spawns coiled in a CLOSED 2x2 box and died at r0 'hit self' (DOOMED val 0; moving into own tail kills, docs/movement).
  STAR's queen split 2 at r0: the boxed child dies, the L2 queen circles in the box (alive to r281). Our queen-never-
  splits rule had no exception. QBOX: in doomedSplit, when nothing else works, the true queen sheds the rear 2.
  Exact ladder map, 2 games vs vb21: queen alive 2/2, both won by queen 3-0 (control: queen dead r0 in both).
- Portals: we led at r400 (queen L8 alive vs their queen dead, longest 5) but our queen got trapped at r401-403,
  ESCAPE-SPLIT 6 gave her mass to a child, she died r407 hit self -> lost on longest. (Next: queen escape logic.)
- Autarky: queen head-on r390 -> lost by queen. Devil and Dilemma: eliminated (economy: r100 units 8 vs 29, 5 vs 14).
- Y.9.4 = Y.9.3 + QBOX uploaded and active. QREACH/QGROW candidates still testing (Kaggle kp1002_0924 with replays).
- 10:30 Y.9.4 vs JalSena 2-3 (-62): WON Portals + Trauma BY QUEEN (queen alive; QROOM/QBOX era), lost Autarky/Default
  (our queen head-on r380/r283; their queen dead early -> decided on longest: ours 3 vs 30 / 13 vs 17) and Slithery
  (longest 12 vs 33 at r400). Slithery: the ladder start coils the L25 queen around her own head; any split leaves her
  boxed in the centre at r1 (she acts first) -> both queens always die there (theirs too). Unavoidable; Slithery stays a
  longest-dragon map. Recurring gap: we have NO grower when queens die (longest 3 at r400 on Autarky).

## 2 Oct 10:45 IST (Claude) where we lose now: Slithery 0/8, Schooltime 2/10 (Y.9.2-Y.9.4 ladder)
- Per map: Slithery 0/8, Schooltime 2/10, Autarky 2/6, Default 2/5, Dilemma 4/8, Trauma 5/9, Trophy 4/7, Devil 6/9,
  Portals 6/8, QoS 5/5. All Schooltime/Slithery losses end on LONGEST with queens dead.
- Schooltime: we end with 1-7 units / 16-80 mass vs their 18-36 / 170-390. NOT feeding (2-16 feeds after r250):
  late head-ons are even trades (us 24-74 vs them 17-64 after r250); the gap opens r100-200 (STAR: 37/93 vs 44/108
  at r100 -> 33/75 vs 62/163 at r200). Intake r0-150 vs STAR 309 vs 448: they eat 151 of their OWN drops (we 76)
  -> they recycle their deaths (Adrak pattern). opencode is mapping where/how (research_notes/oc_schooltime.md).
- Slithery: queens always dead at r1 (coiled start); longest 26-49 vs 40-75 with similar mass -> we don't concentrate.
- Colab qq (48 games each vs vb21+vb19): QGROW 26, QREACH 24, Y.9.3 control 26 -> no score effect; Kaggle replays pending.

## 2 Oct 11:05 IST (Claude) QREACH/QGROW Kaggle replays (32 games each, vb21+vb19, 4 maps)
- Score: QREACH 18, QGROW 19, Y.9.3 16. Queen alive at r500: QREACH 7, QGROW 10, control 9.
- QREACH doesn't stop the r50-150 head-on queen deaths (7 vs 8): tags show scores -440..-590 = EVERY option was within
  enemy reach; an L2-3 queen can't outrun L2 drones. Parked.
- QGROW2 (cand_qg2 = Y.9.4 + true queen never buds after r0 + growth x2.2 / greed x1.2 before r100, vB.21 style):
  Kaggle kp1002_1031 vs Y.9.4 (cand_qb), with replays.

## 2 Oct 11:20 IST (Claude) NEW MAPS are live (maze 48x24, islands 56x40, around_unsw 64x64); tungtung67 0-5 (-44)
- Saved from the replays to maps_new/. All 5 losses on longest: our longest stays 3-4 until r300 on maze/islands/
  around_unsw (theirs 7-20 by r200, 27-38 by r400) even when we lead units (maze r300 54 vs 33). Schooltime: both
  queens alive L3 = tie -> longest 10 vs 14. Their queen L5-7 by r100 (they grow her; we bud her at L4).
- On unknown maps protectFrom stays 400 and budding runs to r420 while UNITS < 40: nobody grows.
- GROWER (cand_gr = QGROW2 + protectFrom 200 default and maze): local test maze/islands vs vb21 (+control Y.9.4).
- 11:40 QGROW2 REJECTED (Kaggle qk2, 32 games vs Y.9.4): 15 vs 16, queen alive 4/32 vs 9/32: a greedy early queen dies.
- tools/map_from_replay.py (new): ladder replays zero the pearl tables (TILE x y 0 0); rebuild [minGap,maxGap] from
  spawns seen in replays (pearls appearing before the round's first turn), pooled with the mirror tile (maze and
  around_unsw rotational, islands horizontal; SYM env). maps_new/{maze,islands,around_unsw}.map now play locally.
  More replays -> better tables (re-run the tool with all of them).
- Ladder: Hydra 5-0 (+50).

## 2 Oct 12:00 IST (Claude) 7 NEW MAPS in the pool; GROWER ladder A/B
- Map pool now 17: + weakhold 28, Australia 29, Islands 30, Maze 31, Stripes 32, Tower Defense 33, Around UNSW 34.
  Leaderboard: #1 Sponge 2076, #2 horse 2031, #3 Cutlery 1997, ..., tungtung67 #18 1850; us #56 1667.
- GROWER local vs vb21 on rebuilt new maps: 2/6 vs Y.9.4 4/6 (noisy; vb21 doesn't grow early either, so the sandbox
  can't show the tungtung67 failure). Uploaded GROWER as 14643 (Y.9.5g, idle) -> interleaved ladder A/B vs
  tungtung67 (566), Cache me outside (952), 3.14159265 (314) on the new maps only, 5 maps each, both builds
  (ladder/ab_grower_newmaps.txt).

## 2 Oct 12:20 IST (Claude) new maps vs tungtung67: Stripes portal boxes -> PEXPLORE
- A/B so far: tungtung67 GROWER 1/5, Y.9.4 1/5 (same maps); Cache me outside GROWER 0/5.
- Y.9.4 vs tungtung67 per map: Stripes (24x12) eliminated by r100, ate 4 pearls r0-150 vs their 60; Australia intake
  59 vs 237, r200 22/50/3 vs 63/280/18; Around UNSW 352 vs 571 r0-150, lost on total; Maze lost on longest 11 vs 40
  (their 31-long start dragon kept long; we led units 42 vs 16 at r400); Weakhold won.
- Stripes frames r20: the pearls sit inside small kelp boxes whose only entrances are portals. On unknown maps
  rebuildNbr pairs a portal only once BOTH ends were seen, so an unexplored portal is a wall to us: our drones circle
  outside for 30+ rounds with the same target (T17,9). Their drones walk in blind.
- PEXPLORE (cand_px = Y.9.4 + calc's rule): on unknown maps a non-queen dragon (L <= 4) that has not grown for 12
  rounds steps into an adjacent unexplored portal (one try, then forage 12 rounds). Stripes/Australia maps rebuilt.
  Local paired test Stripes vs vb21 running.
- 12:45 PEXPLORE tuning on Stripes vs vb21 (4 games): v1 (adjacent only) fired 5x, 1/4; v2 (+ steer hungry drones to
  the nearest seen unexplored portal edge) 2/4, side A intake 67/53 vs control 29/64; v3 (+ hungry drones' blind
  portal steps keep safeClass, modest penalty like on known maps) 2/4. Side B unchanged in all versions (4-15 pearls):
  not yet understood (box entrance geometry). Harm check on australia/maze/islands/around_unsw running.
- GROWER ladder A/B tally (top_scrims, unattributed): GROWER 5/15, Y94 1/11 so far.
- 12:55 GROWER ladder A/B RESULT (new maps, same teams/maps, interleaved): GROWER 5/15 vs Y.9.4 2/15
  (tungtung67 1 vs 1, Cache me outside 0 vs 0, 3.14159265 4 vs 2). Flips vs 3.14: Around UNSW longest 37-27 (Y.9.4
  lost 26-30), Maze 32-26 (Y.9.4 lost 15-22): the longest-dragon mechanism, as intended. GROWER lost its queen on
  Islands where Y.9.4 won by queen 22 (QGROW2 part; QGROW2 alone had cut sandbox queen survival 9 -> 4/32).
  Plan: Y.9.5 = Y.9.4 + protectFrom 200 (GROWER without QGROW2) + PEXPLORE (if the harm check is clean).
- 13:15 Cutlery (#3, 2005) 0-5 (-26): longest 12/15/22 vs 46/52/66; Stripes eliminated; Schooltime: both queens alive at
  L3 = tie -> longest 3 vs 43 (our queen was our last unit). Growth gap again.
- PEXPLORE harm check (australia/maze/islands/around_unsw vs vb21, 8 games): 5/8 vs Y.9.4 5/8 -> neutral off Stripes.
- Y.9.5 RELEASED (sub 14685, active) = Y.9.4 + GROWER (protectFrom 200 default + maze; no QGROW2) + PEXPLORE v3.

## 2 Oct 17:15 IST (Claude) internet outage ~12:20-17:00 IST
- Y.9.5 (14685) active throughout. Rating 1667 (#56, morning) -> 1701 (#50). Top: Sponge 2159, SSS 2147, Cutlery 2120,
  horse 2079, tungtung67 2062.
- Y.9.5 ranked series vs top teams: Cutlery 2-3 (+7; Y.9.4 was 0-5), calc 1-4 (+2), tungtung67 0-5 (-17),
  AllRed 2-3 (-2); avid coders 2-2 unranked.
- Lost during the outage: agy audit (empty reply), nr2 Kaggle upload (DNS failure), opencode Schooltime study (no
  output). All relaunched.

## 2 Oct 17:45 IST (Claude) WHY the rejected ideas failed (replay review, user asked) + Y.9.5 losses vs top teams
- FEED2 (Kaggle f2k replays, 9 flipped games): FEED2 kept MORE units at r400 (40/30/25/26 vs 39/10/9/10) but its
  longest was far shorter (10 vs 31, 25 vs 60, 16 vs 34): FEED2 allowed feeding only into the true queen or the
  ELECTED sink (queen.id), and banned feeders > L6. The base also feeds ANY clearly bigger friend (>= max(10, 2L), or
  L+3 on open maps); that cascade is what builds the 60-long giant on Slithery. FEED2's premise ('each hop wastes half
  the mass') optimised total mass, but games are decided on LONGEST (queens dead). Wrong objective, not wrong sink.
  Keep from FEED2 only: the staggered start + crowd queue (protects the sink's room).
- QGROW2 (qk2 replays): early deaths unchanged (r50-150 head-on 8 vs 8); extra deaths come LATE: r300+ 10 vs 6.
  Two long queens (L40 Default r462, L27 Trauma r452) died 'hit other body' with pd0.00: a multi-step FREE sprint
  (NEE, ceil(40/4)=10 free steps) went through a portal into an unseen body. Our queen's blind step costs -120 but
  stays allowed; vB.21 forbids it outright. A longer queen sprints further and blind more often.
  TUNE: true queen never takes an 'outside' move unless every in-view move is DOOMED (vB.21 rule).
- GROWS2: replays showed no length gain at r200/300 (17/21 vs 20/18); the grower rule only acts when queen.id ==
  MY_ID (elected) and nobody is long enough to be elected before r200; superseded by GROWER (protectFrom 200).
- DILSHAFT: analysed before rejecting (recycled shaft deaths; more head-ons; units 3 vs 6-9 at r150).
- Y.9.5 vs top teams (Cutlery, calc, tungtung67, AllRed): 6 ELIMINATIONS (QoS, Autarky, Dilemma, Default, Trophy,
  Tower Defense): intake r0-150 10 vs 147 (QoS), 16 vs 117 (TD), 62 vs 239 (Trophy), 53 vs 193 (Autarky).
  Schooltime 5 losses all 'us N1 L3 Q3': the variant boxes both queens (QBOX keeps ours alive at L3), so it is decided
  on longest and our army is gone by r500 (theirs 13-41 units, longest 39-65).

## 2 Oct 18:15 IST (Claude) infrastructure: Zig judge + WSL2 GPU + new maps in the cloud
- Zig judge (over-yonder's loong-judge, already built in WSL2 Ubuntu on D:\WSL): tourney.py now defaults to it when
  BC_ZIG_JUDGE is set (user env set: /root/zig_judge/zig-out/bin/loong-judge, engine /root/engine/unswbc_engine.wasm).
  Same 4 games, identical results: 32 s vs 86 s (2.7x). In git-bash export MSYS_NO_PATHCONV=1 MSYS2_ENV_CONV_EXCL='*'
  or the /root paths get mangled to D:/Git/root.
- WSL2 GPU (RTX 3050 4 GB passthrough works): installing torch cu124 in /root/mlenv for local training (WSL2 trains
  faster than native Windows per NVIDIA/insiderllm; keep data on the Linux disk, /mnt/d is slow for many small files).
- Cloud panels: maps_new/*.map shipped with every Kaggle/Colab package; --maps new (7 new maps) and all17.
  weakhold + tower_defense rebuilt (rotational).
- Running: Kaggle qbl (QBLIND vs Y.9.5), f3 + f3base (FEED3 = cascade kept + FEED2's queue/stagger vs Y.9.5),
  tr-nr2b (network schema 2); Colab jobs_b Y.9.5 / jobs_c QBLIND on the 7 new maps; Codex SYMMIRROR (map symmetry
  fill on unknown maps, calc's rule); opencode Schooltime economy study.
- 18:30 opencode Schooltime study (research_notes/oc_schooltime.md, 15 games): opening is level at r100; gap opens
  r100-200. STAR r0-250 intake ours 551 vs theirs 998: spawn 330 vs 525, and they eat ~373 wreck pearls (table column
  = drop-enemy, i.e. OUR dead; opencode's headline mislabels it as their own) vs our 54 of theirs. Head-on is the #1
  death cause on both sides. Rich regions (row1 col1/col4, row3 col2-3 = the local table's 0.8-1.3 rate regions) are
  where they eat 548 vs our 38. Ideas: (1) hold the rich regions (compass on Schooltime should do this: check why
  it doesn't), (2) don't feed them wrecks: avoid head-ons near their swarm, (3) drop pearls outrank spawn pearls.

## 2 Oct 19:00 IST (Claude) CPU bug on the big new maps -> Y.9.6 (sub 14940, active)
- Zig-judge runs showed our peak 97-99M on Around UNSW (64x64) and Australia; sandbox: 'round 409: bot 148 (team A)
  exceeded CPU limit' (= that dragon dies). Instrumented (CPU/THINK tags): long dragons (L16-29) on open big maps spend
  80-93M points in think(): every free-sprint option (2-3 step paths, ~30) gets the full-board survival evaluation
  (4096 cells). The clock is the judge's points (100M = 100 ms; docs/libraries.md), so elapsedMs guards work.
- CPUGUARD: shallow evaluation after 45 ms, drop remaining (sprint) options after 65 ms (1-step options first).
  Australia/Around UNSW: max 96.6M -> 72.3M, no CPU deaths for us (vb21 still exceeds). Y.9.6 = Y.9.5 + CPUGUARD.
- SYMMIRROR (Codex, map symmetry on unknown maps; reviewed): 7 new maps x 2 sides vs vb21: 10/14 vs Y.9.5 9/14.
  Re-test on top of Y.9.6 next.
- WSL2: torch 2.6.0+cu124, CUDA OK in /root/mlenv. Collector of top-15 games since the new maps -> ladder/slope_new.
- 19:30 SYMMIRROR on Y.9.6 (7 new maps x vb21+vb19, Zig judge): 21/28 vs Y.9.6 20/28; CPU 72.8M. Mechanism check
  (debug tags SY<alive>:<sym>:<compared>): resolves correctly (Islands -> x-mirror r14, Stripes/Maze -> 180 deg) but
  every dragon learns it alone (split children start from scratch): on Maze the first dragon resolves at r74 and most
  dragon-turns still have 2-3 candidates. Next: share the resolved symmetry over sonar (2 bits in the SECURE payload)
  so children inherit it; then the fill helps the whole team from r~15.

## 2 Oct 19:50 IST (Claude) first local GPU network: nm1
- Data: ml/data_nm = 364 winning top-15 games since the new maps (ladder/slope_new, collector running), 2.87M
  samples, schema 2; + every 7th shard of data_nr2. Trained in WSL2 on the RTX 3050: 380k per source (760k total;
  1.2M per source was OOM-killed at WSL's 7 GB), 10 epochs x ~10 s. Val acc 0.690 (majority 0.395).
- Exported (in WSL: torch is only there) to cand_nm = Y.9.6 + MLV2 inputs + nm1 weights; NNTEST logits identical.
  (Patch slip: the MLV2 scalar block landed in updateQueen; moved into nnInput.)
- Test: cand_nm vs Y.9.6 on all 17 maps vs vb21 (Zig judge, replays in D:/battlecode/tmp/nmab).
- 20:15 nm1 (scratch, 760k samples) in the bot: 13/34 vs Y.9.6 (n4) 20/34 (old maps 6/20 vs 10/20, new 7/14 vs 10/14).
  Replays: the maze opening collapses: Trophy A pearls r0-150 27 vs 162 (units r50 4 vs 10), Tower Defense A 44 vs 96.
  A from-scratch net on 760k samples is weaker than n4 (trained on far more top-team maze data; ~0.72 offline).
  Next: nm2 = n4 FINE-TUNED on the new-maps games (schema 1, no input change), lower lr, few epochs.
- 20:45 nm2 = n4 fine-tuned on 831 new-rules top games since the new maps (schema 1, lr 5e-4, 3 epochs x 10 s on
  the 3050): val acc 0.707 (n4 start ~0.70 on this data). In the bot (Y.9.6 + nm2) vs vb21, 17 maps: 18/34 vs
  Y.9.6 20/34 (old 9 vs 10, new 9 vs 10); 12 flipped games split 5/7. No gain yet; keep n4. Retry when the collector
  has more new-map games (it adds ~top-15 games every 20 min).

## 2 Oct 21:15 IST (Claude) Atlas 2-3 / CookAgent 2-3 (Y.9.6) + why nm2 "lost"
- 5 of 6 losses: Dilemma, Default, Devil, QoS ELIMINATED; Weakhold lost on longest 3 vs 32. Dilemma/Default/Devil:
  opening lost (intake r0-150 37 vs 85, 74 vs 134, 145 vs 201). QoS and Weakhold: we LED (QoS intake 132 vs 12;
  Weakhold 18 vs 7 units at r150) and collapsed r150-300. Weakhold: 31 of our deaths were DOOMED L2-3 miners walking
  into 1-wide pearl dead ends (frame r35: L2 enters a 4-cell bottom-row pocket with 3 pearls, rm25 -> rm2 -> dead).
  Miners skip the pocket/corridor penalty (MINE2); that was measured on known maps only.
  -> MINEKM (cand_mk): unknown maps get no miner exemption. Test: 7 new maps x vb21+vb19 x 2 seeds vs Y.9.6.
- nm2 vs n4: 10 flipped games; in ALL 10 the winner was the side that ate more pearls r0-150, and the swings go both
  ways (Devil A nm2 143 vs n4 419; Devil B nm2 383 vs n4 189). The opening is a chaotic race; a different move at
  r10 changes who takes the centre. 18 vs 20 of 34 is noise (would need ~150 paired games). Offline gain was small
  (val 0.704 -> 0.707 during fine-tune; n4's own score on this set not measured) and offline accuracy has never
  translated to wins at this size (HISTORY: v1b..v5).
- 3 Oct 01:00 MINEKM REJECTED: 7 new maps x vb21+vb19 x 2 seeds (Zig judge) 34/56 vs Y.9.6 37/56; Weakhold vs vb19
  (sandbox, indicators) 2/4 vs 4/4. It halves DOOMED deaths (11 vs 22, 11 vs 14) but loses the games: pocket deaths are
  recycled pearls (DILSHAFT lesson). Note: the Zig judge records no indicators unless --debug 3; use BC_JUDGE=sandbox
  for tag-based mechanism checks.
