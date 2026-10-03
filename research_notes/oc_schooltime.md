# Schooltime economy gap — analysis of our ladder losses

**Games:** all Schooltime replays in `ladder/ours_nr/index.jsonl` with `played_by` 14475/14549/14576 (15 games, 10 ranked).
**Record:** 1W–9L ranked (only win 843755 vs YY Slayers), 2W–13L including unranked.
**Method:** `tools/replay.py _decode`; pearl intake classified by source via `tileChange` (spawn vs death-drop, own vs enemy) exactly as `D:/battlecode/tmp/eatsrc.py`; eats/deaths/splits tracked per round; regions are 10×10 tiles on the 60×40 map.
**Validation:** our intake for 850917 (STAR) r0-150 reproduces the user's eatsrc.py numbers (ours 305 vs theirs 443; theirs drop-own 151, ours drop-own 74; theirs spawn 263, ours spawn 211 — small deltas are the r150 window boundary).

## Headline

We do not lose the opening. At r100 our units/mass are level with the opponent in almost every game. **The gap opens in r100–200**, and it has three compounding causes, in order of size:

1. **Map coverage of the pearl-rich corridors.** The opponent eats far more *spawn* pearls because they have dragons in the high-density regions where we have literally zero presence. In STAR they eat 525 spawn vs our 330 (+195).
2. **Recycling their own dead ("fountain farming").** They split into many small dragons that die (head-ons, walls) and they eat the dropped pearls. In STAR they recycle 373 of their own dead vs our 167 (+206).
3. **Wreck share — eating OUR dead.** They eat more of our dead's pearls than we eat of theirs (STAR r100-200: they eat 149 of our dead, we eat 31 of theirs).

The deaths are **not** primarily "deliberate split-1 sacrifices". They are mostly split-off children that live a while (median 11–60 rounds) and then die to **head-to-head** and **hit wall**. The opponent simply does this at a larger scale and manages the small dragons better.

## 1. Pearl intake per 50-round window, r0-250, by source

Format per window: `spawn / drop-own / drop-enemy [tot]`. "drop-own" = pearls from their own dead (recycling); "drop-enemy" = pearls from our dead (wreck share). Ours/theirs.

| game | opp | W/L | window | ours | theirs |
|---|---|---|---|---|---|
| 843524 | Weneedmoretokens | L | r0-50 | 4/0/0 [4] | 10/0/0 [10] |
| | | | r50-100 | 23/2/0 [25] | 22/0/0 [22] |
| | | | r100-150 | 23/6/4 [33] | 39/4/9 [52] |
| | | | r150-200 | 27/7/2 [36] | 36/6/10 [52] |
| | | | r200-250 | 17/20/6 [43] | 51/4/7 [62] |
| 843755 | YY Slayers | **W** | r0-50 | 9/0/0 [9] | 2/0/0 [2] |
| | | | r50-100 | 29/0/0 [29] | 10/0/4 [14] |
| | | | r100-150 | 34/3/0 [37] | 17/4/7 [28] |
| | | | r150-200 | 61/25/17 [103] | 5/2/2 [9] |
| | | | r200-250 | 43/16/3 [62] | 0/0/0 [0] |
| 845770 | Atlas | L | r0-50 | 10/0/0 [10] | 11/0/0 [11] |
| | | | r50-100 | 23/1/1 [25] | 16/0/0 [16] |
| | | | r100-150 | 36/4/2 [42] | 26/2/5 [33] |
| | | | r150-200 | 30/14/7 [51] | 32/6/13 [51] |
| | | | r200-250 | 24/16/10 [50] | 30/18/20 [68] |
| 845650 | Atlas | **W** | r0-50 | 7/0/0 [7] | 7/0/0 [7] |
| | | | r50-100 | 23/1/2 [26] | 18/0/2 [20] |
| | | | r100-150 | 41/0/2 [43] | 24/2/9 [35] |
| | | | r150-200 | 39/28/18 [85] | 13/1/1 [15] |
| | | | r200-250 | 44/14/3 [61] | 13/6/4 [23] |
| 846047 | Just Keep Swimming | L | r0-50 | 4/0/0 [4] | 11/0/0 [11] |
| | | | r50-100 | 20/1/0 [21] | 19/0/0 [19] |
| | | | r100-150 | 20/3/5 [28] | 33/10/5 [48] |
| | | | r150-200 | 24/7/3 [34] | 65/4/5 [74] |
| | | | r200-250 | 21/11/5 [37] | 42/14/23 [79] |
| 846700 | chaoliangUNSW | L | r0-50 | 3/0/0 [3] | 11/0/0 [11] |
| | | | r50-100 | 32/2/1 [35] | 17/2/4 [23] |
| | | | r100-150 | 32/3/1 [36] | 25/10/7 [42] |
| | | | r150-200 | 39/8/6 [53] | 19/8/4 [31] |
| | | | r200-250 | 34/15/11 [60] | 22/21/27 [70] |
| 849263 | POFPOF | L | r0-50 | 10/1/0 [11] | 8/0/1 [9] |
| | | | r50-100 | 24/0/1 [25] | 16/2/1 [19] |
| | | | r100-150 | 48/7/4 [59] | 23/2/7 [32] |
| | | | r150-200 | 47/13/4 [64] | 27/9/14 [50] |
| | | | r200-250 | 31/16/12 [59] | 15/19/16 [50] |
| 850053 | ChinaRen | L | r0-50 | 5/0/0 [5] | 7/0/0 [7] |
| | | | r50-100 | 27/5/1 [33] | 11/0/0 [11] |
| | | | r100-150 | 33/3/1 [37] | 29/6/4 [39] |
| | | | r150-200 | 26/6/5 [37] | 60/11/7 [78] |
| | | | r200-250 | 20/14/4 [38] | 26/8/13 [47] |
| **850917** | **STAR** | **L** | r0-50 | 23/0/0 [23] | 47/0/2 [49] |
| | | | r50-100 | 99/25/5 [129] | 119/4/58 [181] |
| | | | r100-150 | 89/49/15 [153] | 97/25/91 [213] |
| | | | r150-200 | 66/48/16 [130] | 106/45/124 [275] |
| | | | r200-250 | 53/45/18 [116] | 156/26/98 [280] |
| | | | **r0-250** | **330/167/54 [551]** | **525/100/373 [998]** |
| 851736 | nsw seng | L | r0-50 | 15/0/0 [15] | 11/0/1 [12] |
| | | | r50-100 | 168/57/3 [228] | 23/0/3 [26] |
| | | | r100-150 | 132/73/8 [213] | 18/15/19 [52] |
| | | | r150-200 | 235/93/15 [343] | 16/18/15 [49] |
| | | | r200-250 | 171/82/9 [262] | 27/17/17 [61] |
| 853192 | Candiru | L | r0-50 | 6/1/0 [7] | 9/0/1 [10] |
| | | | r50-100 | 26/1/0 [27] | 13/3/6 [22] |
| | | | r100-150 | 34/2/0 [36] | 28/3/5 [36] |
| | | | r150-200 | 42/11/5 [58] | 30/9/12 [51] |
| | | | r200-250 | 23/17/12 [52] | 23/12/23 [58] |
| 855860 | tungtung67 | L | r0-50 | 5/1/0 [6] | 4/0/1 [5] |
| | | | r50-100 | 17/0/0 [17] | 22/0/0 [22] |
| | | | r100-150 | 22/4/4 [30] | 23/4/3 [30] |
| | | | r150-200 | 40/5/5 [50] | 48/7/16 [71] |
| | | | r200-250 | 25/21/14 [60] | 71/12/21 [104] |
| 859241 | Weneedmoretokens | L | r0-50 | 5/1/0 [6] | 3/0/2 [5] |
| | | | r50-100 | 18/0/0 [18] | 12/0/1 [13] |
| | | | r100-150 | 30/4/0 [34] | 19/6/9 [34] |
| | | | r150-200 | 24/2/1 [27] | 24/4/14 [42] |
| | | | r200-250 | 19/6/1 [26] | 47/10/22 [79] |
| 859458 | Weneedmoretokens | L | r0-50 | 9/1/0 [10] | 6/0/1 [7] |
| | | | r50-100 | 16/0/1 [17] | 14/0/1 [15] |
| | | | r100-150 | 27/2/2 [31] | 13/0/13 [26] |
| | | | r150-200 | 49/8/3 [60] | 12/4/8 [24] |
| | | | r200-250 | 40/15/4 [59] | 17/9/13 [39] |
| 859451 | Cutlery | L | r0-50 | 5/1/0 [6] | 8/2/2 [12] |
| | | | r50-100 | 22/0/0 [22] | 40/0/0 [40] |
| | | | r100-150 | 24/6/6 [36] | 59/9/13 [81] |
| | | | r150-200 | 23/20/17 [60] | 113/30/61 [204] |
| | | | r200-250 | 32/5/3 [40] | 161/25/47 [233] |

**Read of the table:** in the ranked losses the opponent out-eats us almost entirely in **r100-200**, and the deficit is largest in **spawn** pearls and **our-dead** pearls. The two games we win on economy (843755, 845650) are the ones where we out-eat them in r150-200. 851736 is the cautionary outlier: we out-eat them 556 vs 101 in r100-200 yet still lose (see §5).

## 2. Units / mass trajectory (count / total segments)

| game | opp | r100 ours/theirs | r200 ours/theirs | r250 ours/theirs |
|---|---|---|---|---|
| 843524 | Weneedmoretokens | 16/38 vs 17/41 | 25/63 vs 41/97 | 28/64 vs 56/135 |
| 843755 | YY Slayers (W) | 20/49 vs 10/21 | 47/118 vs 3/12 | 63/151 vs 2/8 |
| 845770 | Atlas | 18/41 vs 16/37 | 30/72 vs 26/60 | 27/64 vs 35/84 |
| 845650 | Atlas (W) | 19/43 vs 13/31 | 47/112 vs 13/29 | 53/123 vs 13/31 |
| 846047 | Just Keep Swimming | 12/32 vs 18/40 | 25/58 vs 54/127 | 20/45 vs 63/149 |
| 846700 | chaoliangUNSW | 16/41 vs 15/34 | 33/79 vs 25/65 | 29/71 vs 28/66 |
| 849263 | POFPOF | 16/40 vs 13/32 | 43/101 vs 25/60 | 43/102 vs 26/61 |
| 850053 | ChinaRen | 16/38 vs 12/28 | 24/61 vs 45/110 | 27/63 vs 51/127 |
| **850917** | **STAR** | **38/95 vs 45/114** | **33/80 vs 63/161** | **27/66 vs 62/213** |
| 851736 | nsw seng | 53/132 vs 15/34 | 63/280 vs 13/32 | 64/329 vs 22/55 |
| 853192 | Candiru | 15/37 vs 13/30 | 31/79 vs 29/70 | 36/83 vs 26/60 |
| 855860 | tungtung67 | 13/33 vs 14/37 | 29/71 vs 33/80 | 32/76 vs 43/109 |
| 859241 | Weneedmoretokens | 12/31 vs 10/23 | 26/64 vs 23/58 | 25/62 vs 33/83 |
| 859458 | Weneedmoretokens | 16/37 vs 12/28 | 37/92 vs 12/30 | 42/103 vs 16/38 |
| 859451 | Cutlery | 13/31 vs 21/53 | 10/23 vs 55/130 | 7/19 vs 61/203 |

At r100 the count/total are close in every game (e.g. STAR 38/95 vs 45/114). By r200 the opponent has pulled ahead in count and/or total in every loss. The user's quoted "37 vs 44 at r100 → 62/163 vs 33/75 at r200" is the STAR game.

## 3. WHERE the opponent eats that we don't (10×10 regions)

Pearl-spawn density per region (from `maps/schooltime.map`), count of spawn tiles:

```
        col0  col1  col2  col3  col4  col5
row0:    7    13     6     6    13     7
row1:   16    40     9     9    40    16
row2:    3     4     3     3     4     3
row3:   20    20    22    22    20    20
```

The rich corridors are **row1 col1 & col4 (40 each)** and **row3 (20–22 each)**. Row2 is barren (3–4).

Regions where the opponent out-eats us (top per game, ours/theirs/diff):

| game | opp | top regions where THEY out-eat us |
|---|---|---|
| 843524 | Weneedmoretokens | col1 row0 0/23/+23, col2 row1 0/21/+21, col5 row3 0/14/+14, col0 row0 0/13/+13 |
| 845770 | Atlas | col1 row1 11/34/+23, col1 row0 3/24/+21, col0 row1 4/19/+15 |
| 846047 | Just Keep Swimming | col2 row3 0/19/+19, col3 row3 0/17/+17, col2 row2 1/16/+15, col2 row1 4/18/+14 |
| 846700 | chaoliangUNSW | col4 row0 4/22/+18, col2 row1 8/25/+17, col5 row0 0/15/+15 |
| 849263 | POFPOF | col5 row3 0/13/+13, col0 row3 0/13/+13, col4 row0 8/20/+12 |
| 850053 | ChinaRen | col4 row0 0/30/+30, col5 row0 0/14/+14, col0 row0 3/15/+12 |
| **850917** | **STAR** | **col3 row3 2/178/+176, col2 row3 3/179/+176, col4 row1 33/191/+158, col4 row0 1/76/+75** |
| 853192 | Candiru | col5 row1 0/17/+17, col3 row1 7/18/+11, col4 row0 10/19/+9 |
| 855860 | tungtung67 | col4 row1 2/28/+26, col4 row0 0/23/+23, col4 row2 2/20/+18, col2 row1 3/21/+18 |
| 859241 | Weneedmoretokens | col3 row1 3/37/+34, col4 row1 2/29/+27, col4 row0 4/30/+26 |
| 859458 | Weneedmoretokens | col1 row0 0/34/+34, col1 row1 4/32/+28, col0 row0 6/21/+15 |
| 859451 | Cutlery | col4 row2 6/33/+27, col3 row1 2/27/+25, col5 row0 0/19/+19 |

**Consistent pattern:** the regions where we eat **zero** and the opponent eats 10–180 are almost always the high-density corridors — **row1 col1/col4** and **row3**. In STAR the opponent eats 178+179+191 = 548 pearls in just three rich regions (col2 row3, col3 row3, col4 row1) where we eat 2+3+33 = 38. We are simply not present in the richest parts of the map.

## 4. How their own deaths happen in r50-200

Death causes (r50-200), ours vs theirs:

| game | opp | OUR causes | THEIR causes |
|---|---|---|---|
| 843524 | Weneedmoretokens | h2h 14, wall 3, self 1 | h2h 10, self 9, other 2 |
| 843755 | YY Slayers | h2h 18, self 4, wall 4, other 2 | h2h 12, wall 5, other 1 |
| 845770 | Atlas | h2h 13, wall 4, self 6, other 1 | h2h 15, other 3, no-valid 8 |
| 845650 | Atlas | h2h 13, other 4, wall 4, self 1 | h2h 19, no-valid 4, other 1 |
| 846047 | Just Keep Swimming | h2h 11, wall 3, self 1, other 1 | h2h 9, other 4, wall 2, self 1 |
| 846700 | chaoliangUNSW | h2h 21, wall 2, self 1 | h2h 17, wall 2 |
| 849263 | POFPOF | h2h 18, wall 4, other 2, self 1 | h2h 16, wall 5, self 3, other 1 |
| 850053 | ChinaRen | h2h 16, self 4, wall 4 | h2h 10, wall 6 |
| **850917** | **STAR** | **h2h 75, wall 37, self 10, other 5** | **wall 89, h2h 74, other 56, self 9** |
| 851736 | nsw seng | wall 69, h2h 57, self 23, other 5 | h2h 39, wall 3, other 2 |
| 853192 | Candiru | h2h 14, wall 5, self 6 | h2h 12, wall 7, other 5 |
| 855860 | tungtung67 | h2h 15 | h2h 15, wall 6, other 1 |
| 859241 | Weneedmoretokens | h2h 6, self 2, wall 2, other 1 | self 14, h2h 4, other 1 |
| 859458 | Weneedmoretokens | wall 6, h2h 7 | other 8, self 8, h2h 7 |
| 859451 | Cutlery | h2h 27, other 2, self 2, wall 2 | h2h 35, no-valid 8, other 3 |

**Head-to-head is the #1 cause for both sides in nearly every game**, followed by hit-wall. This is the central fact: the small dragons die in collisions, not to deliberate sacrifice.

**Are they deliberate split-feeds?** No — not in the "split off a child and immediately sacrifice it" sense. Across all games, **~95% of deaths are split-off children** (e.g. STAR 228/230 theirs, 125/127 ours; 843524 17/18 ours, 21/21 theirs). But the children mostly **live a while before dying** — median lifetime 11 rounds (STAR theirs) to 60 rounds (843755 theirs). Only a minority die within 8 rounds of splitting (STAR theirs 85/230). So the mechanism is "split into many small dragons that forage, then die to head-ons/walls", not "split and instantly feed".

**Where they die:** deaths are concentrated in the same rich corridors. STAR theirs: col4 row1 (52), col2 row3 (43), col3 row3 (34), col4 row0 (20). STAR ours: col1 row1 (24), col2 row1 (16), col5 row1 (14). Both sides send small dragons into the rich regions to forage and die there; the opponent simply has more of them and eats more of the resulting wreckage.

**Split counts (r0-250):** the opponent splits far more in the fountain-farming games — STAR theirs 368 splits vs our 197; 851736 ours 254 vs theirs 80. In the typical games both sides split 50–100 times. The opponent's extra splits are what put more dragons into the rich regions.

## 5. The mechanism, and the 851736 cautionary outlier

The opponent's economy is a **fountain-farming loop**: split into many small dragons → they spread into the pearl-rich corridors and eat spawn pearls → they die to head-ons/walls → the dropped pearls are recycled into the main dragon(s) → repeat. The loop is net-positive for them because (a) the small dragons harvest more spawn pearls than the mass lost to deaths, and (b) they also eat our dead's pearls when we collide.

**851736 (nsw seng) is the warning:** we ran the same loop harder (64 dragons / 343 mass at r200 vs their 13/32) but our small dragons collapsed — 154 deaths in r50-200 (69 wall, 57 h2h, 23 self) — and we ended with 5 dragons / 45 mass while their few long dragons grew to 392. **Out-eating is not sufficient; the small dragons must survive.** The opponent's edge is not just splitting more, it is that enough of their small dragons survive to grow into long dragons (their longest reaches 46 by r500 in STAR).

This is why the rules below pair "cover the rich regions" with "stop dying to head-ons": coverage without survival is how 851736 happens.

## 6. Three concrete rule ideas

### Rule 1 — Cover the pearl-rich corridors (map control)
**Data:** we eat **zero** pearls in the richest 10×10 regions while the opponent eats 10–180 there. The rich corridors are row1 col1/col4 (40 spawns each) and row3 (20–22 each). In STAR the opponent eats 548 pearls in col2 row3 + col3 row3 + col4 row1 where we eat 38.
**Change:** use the MAPFIX pearl table to identify the top-density regions; when choosing a split destination or a move target, bias toward **unoccupied high-density regions**. Concretely, keep at least one dragon in each of row1 col1, row1 col4, and the row3 band, and prefer splitting a child toward a rich region over a poor one. This is a targeting/pathfinding change, not a split-rate change.
**Risk:** over-splitting into poor regions wastes mass (851736). Gate the rule on region density.

### Rule 2 — Head-on avoidance (stop feeding the opponent our dead)
**Data:** head-to-head is the #1 death cause for both sides (STAR: ours 75, theirs 74). A head-on kills **both** dragons, and the opponent eats the wreckage — in STAR r100-200 they eat 149 of our dead's pearls while we eat 31 of theirs. Every head-on is a double loss (our dragon + the pearls they eat).
**Change:** strengthen the collision-avoidance logic (QFLEE/CROWD family) to break off when an enemy head is on a collision course — especially when we are the shorter dragon, or when enemy dragons are positioned to eat the wreckage. Prioritising head-on avoidance over a marginal pearl is correct whenever the enemy is near a rich region (they will eat both sets of pearls).
**Note:** this also protects against the 851736 collapse — most of those 154 deaths were head-ons and walls.

### Rule 3 — Wreckage-recycling priority
**Data:** the opponent eats ~2× the wreck pearls we do (STAR r0-250: theirs 373 own-dead + 100 our-dead = 473; ours 167 own-dead + 54 their-dead = 221). After any death nearby, their dragons eat the dropped pearls; ours often arrive too late or not at all.
**Change:** when a pearl drops (death) within vision, raise its priority above spawn pearls — most urgently **enemy-dead** pearls (deny the opponent) and **our-dead** pearls (recover mass). This is a pearl-priority change in the foraging/scoring logic: a drop pearl within reach should outrank a spawn pearl of equal distance.
**Interaction:** this rewards winning confrontations even when we don't need the mass, because it denies the opponent.

## Appendix — reproduction

```
python schooltime_analysis.py            # per-game intake/regions/deaths/splits -> schooltime_out.txt + schooltime_summary.json
python schooltime_splitfeed.py          # split-child lifetime, causes, feed classification
python schooltime_deathreg.py           # death locations per 10x10 region
python schooltime_mapdensity.py         # pearl-spawn density per region
python schooltime_compact.py            # compact snapshot + intake tables
python D:/battlecode/tmp/eatsrc.py ladder/ours_nr/schooltime_B_850917.replay   # user's original intake check
```

All scripts are in the repo root (untracked scratch). Replays are in `ladder/ours_nr/` (gitignored).
