# Parked ideas: dropped on thin evidence, to revisit with per-game analysis and tuning

User direction (30 Sept 2026, 22:30 IST): many ideas were dropped on one noisy score. Small gains compound, so judge each
idea on whether its mechanism fires and moves its target metric (tools/game_review.py, tools/mechanics.py, viz eatmap),
tune it, and stack the good ones. Ladder pairs diverge by r25, so a 30-game ladder score is mostly noise.

| Idea (dir) | Dropped on | What we actually know | Next analysis / tuning | Priority |
|---|---|---|---|---|
| Last-giant hunt (cand_hunt, hunt3, cutoff) | HUNT3 9 v 10/30 | 5 giant endgames, all lost: Trauma giant never seen (built late at home), Slithery L56 outran us. Audit 3: hunt3's trade rule hits ANY L>=10 enemy longer than our (stale) queen | Narrow version: last-giant check (enemy sightings scarce + reported giant), search for the home-built giant, log report age/pursuit/trades; judge only on games reaching the condition | MED |
| Consolidation sink (cand_sink, cand_sink_m) | sink 4 v 9 (72 g); sink_m 89 v 92 maze | sink throttled open-map feeding (one replay); sink_m barely changes play | Per-game: holders after r300, longest fate at r350/400 on LEN+MASS losses; tune hysteresis 3 -> 2, guard only the queen | MED |
| Pocket trap (cand_pocket) | 11 v 11 (96 g) | Mechanism unverified | Count pocket deaths (tools/avoidable.py) cand vs champion on Slithery replays; tune surv threshold | MED |
| Time-aware space (cand_dijk, dijk2, dijk_o) | maze 72/144, 79/144; open 15 v 13 | Own-body semantics changed (dijk); dijk2 still worse on mazes | Find which decisions change: log space estimates old vs new on the same positions; maybe use only for the pocket check | LOW-MED |
| Open-map network (cand_dual*, cand_g1, mix_a/g) | 6/96, 11/96, 13/96 | Trained on only 150 games; n4 at w1 on open maps is neutral | Wait for the fresh collector; held-out log-loss first (audit: 150 games too few) | LOW (data-bound) |
| NN mixing (cand_nn1 near-tie, cand_nn2 veto) | Kaggle 28/144, 24/144 (laptop 10/24, 11/24) | Kaggle collapse unexplained (pipeline? time guards?) | Log NN-on / truncated-search counts on Kaggle vs laptop before judging (audit 2 #5) | MED (may reveal a Kaggle bug) |
| Later maze schedule (cand_late = S.1's) | ladder 12/30 v 15/30 | Offline exactly equal (92/144, 26/48) | Per-game review of the LATE games: did farming until r380 raise mass at r380? feed timing? | LOW-MED |
| Contest pearls (cand_contest) | 15/29 v 15/30 | Did not raise r0-100 intake (median 80 v 91) | The lever is the opening route (Trophy eatmap: we never enter the centre room). Trace the r0-60 paths | MED (opening is the biggest gap) |
| Scavenging (cand_scav) | 9/24 v 12/24; Kaggle 81/144 | Wreck share follows winning (69% in our wins) | Parked: not a separate skill | LOW |
| Unknown-map mode (cand_unk_*) | 12/32, 2/32 v 16/32 | Maze mode is the right default | Done: keep the default | DONE |

Process now: interleaved ladder A/B (`top_scrims.py --interleave`), a per-game review for every candidate, the score second.
| Regional compass (cand_compass2/3/4) | ladder 13 v 17/30 (QoS 0/5); sandbox 7, 9, 9 v 12 | Reaches rich rooms (Trophy/Devil ladder 5 v 2); QoS enemy-side targets fixed in compass3 (spawn anchors); herding causes early collapses; 1/3 of miners (compass4) removes collapses but gains nothing yet | Coordinate via gossip: count dragons bound to each region, cap 3-4; test on Trophy/Devil ladder games | MED |
