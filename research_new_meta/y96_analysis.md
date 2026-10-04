# Y.9.6 (active champion, id 14940) vs our vB.19 line: what it has that we don't (2026-10-03)

Source: baselines/Y9_6/main.cpp (2087 lines, y8m lineage; 600 diff lines vs vB19). Same n4 network weights/header as vB19 (plane 8 filled),
so its edge is RULES, not the net. Local results: vB19 vs Y9_6 16/40, our v6 nets 14-15/40 (live 10 maps) -> the whole vB19 line loses ~60%.
Its comments cite ladder games and A/B tests on the new maps (Stripes, Portals, Trauma, Schooltime, Slithery, Australia).

| Tag | What it does | Evidence in its comments | Relevance to unknown maps | Effort to port |
|---|---|---|---|---|
| PEXPLORE | On unknown maps (!KM) a small drone (L<=4) that has not grown for 12 rounds steps into a portal whose partner it has not seen; pxTarget = nearest seen cell with an unexplored portal edge; hungry drones may cross unseen portals | Stripes (24x12): pearls in kelp boxes reachable only via portals: 4 pearls vs 60, eliminated. calc's rule | HIGH: portal partners unseen = walls in rebuildNbr | low-medium |
| QFEED (+QFEED2/QROOM/ROWLATE) | From r280 the TRUE queen is the feed/homing sink (queen.len=999 when her position is fresh); queen's greed x0.2 only before r280; crowd/ROW penalties off late except no-adjacent-cell rule | Trauma vs No Idea: they fed THEIR queen 2->16 and won by queen; Portals r287: 31 L2 drones boxed her in (QROOM) | queen length decides at r500 | medium |
| Hybrid queen | keeps the OLD longest-dragon election (queen.id==MY_ID) AND true-queen rules; protectFrom 200 (GROWER: one grower for the longest-dragon tiebreak on maze maps; ladder A/B 5/15 vs 2/15) | GROWER, GROWS (Slithery grower L>=6) | medium | medium |
| Milder queen scoring | enemy head within 3: -12*(4-d) (vB19: -500/-250 within 1/2 + -40 radar + danger +300 within 2) | vB19 queen very passive | medium | tiny (parameters) |
| QBOX-SHED | an L>=4 true queen boxed in at r0 sheds 2 instead of dying | Schooltime vs STAR: L4 queen died r0 in a 2x2 box | variant/unknown maps | tiny |
| SELFTRACK | trust our exact move history for the body when the visible chain mislinks (giants died 'hit self' after DOOMED unknown body) | Slithery vs err404: L55 and L29 died | all maps | small |
| SEARCH1 | 1-ply continuation TRAP VETO: switch to runner-up only if the chosen move has no safe continuation (all >=60% deadly) and runner-up has; <=12 leaf evals, <=50 ms | v1 flipped 67k times on noise; tuned | all maps | medium |
| HUNTL | L<=4 drones away from the sink hunt visible giants (estLen>=20 or >=2x our queen, from r300 or r200 if >=25): pull 12; visible enemy queen pull 8; findAttack value 1e6 for queens | -- | medium | medium |
| CPUGUARD | shallow evaluation after 45 ms, drop sprint options after 65 ms | one dragon exceeded 100M on Australia r409 and died (same risk we measured: vB19 98.8M) | HIGH | have ours (53M peak) |
| MINE2/FLOOR/params | L2 drones mine except Devil; budUntil 300, feedFrom 350, feedRadius 25 + 10-unit floor; p2Drone .15 minerGamma .90 on maze maps | FUNNEL collapsed 51->2 units | -- | tiny |
| SECURE | team-key SipHash 16-bit tag, 48-bit payload (QUEEN, QPOS, PPROBE); opening split/hash of vB19 NOT present | -- | -- | we have f1 |

CPU measured on the big maps (our panel logs, Y9_6 as the opponent): Y.9.6 peak 73.0M (Australia, Around UNSW), 69.7M (Islands), 60.7M (Maze).
vB19 98.8M, our v6 net bot 96.5M, our CPU-fix candidate 53.4M.

## Recommendation
Stop building on vB19. Our line loses ~60% to Y.9.6 and the net retrains do not change that. Take Y.9.6 as the new base and add what is OURS and
targets unknown maps: (1) the CPU margin (our shared 48 ms deadline + exact reach lookup, 53M peak vs their 73M), (2) learnGap (V4) and
seen-terrain handling for unseen maps, (3) a seen-terrain retrained net (only if it beats the n4 net there), (4) sealed-sonar age fix if their SECURE lacks it.
Test every candidate as `candidate vs Y9_6` on UNSEEN maps (the 7 extra site maps in maps/ + maps_rm_dev/test), paired seeds, CPU max reported.
