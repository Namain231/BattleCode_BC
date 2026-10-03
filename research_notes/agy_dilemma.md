# Dilemma Opening Analysis & Remediation

## 1. Root Cause: Why Our Swarm Stays Tiny (1-4 vs 20-47)
- **Queen Spawn Death (r3-5)**: Queen (L11) spawns at (14,2) facing North into a 2-cell dead end at (14,0). At r2 it hits the kelp wall; doomedSplit (`cand_sec/main.cpp:1806`) creates a tail child (L9) moving South, but leaves the Queen (parent, ID 0, L2) pinned at (14,0). At r3, L2 cannot doomedSplit (`MY_LEN < 4`, line 1282), dying at r3-5.
- **Suicidal Drone Lemmings (MINE2)**: On Dilemma, `isDevilMap` is false (line 1118), so `miner` is enabled for all drones L<=4. This zeroes `corridorRisk` (line 1171) and `pocket` penalties (line 1121). Since the only rapid pearls (`gap 1,1`) are in 1-wide shafts x=14/17, our L2-3 drones rush in. Because L<4 cannot bud (`budAt=4`, line 1338) or doomedSplit, 7 of 9 early deaths are DOOMED L2-3s in those shafts.
- **Opponent Snowball**: Opponents circulate one dragon in the loop, bud into open space once L>=4, and consume our death pearls to snowball to 20-47 units.

## 2. Comparison: cand_sec vs vb19 and vb21
- **cand_sec**: No opening uncoil rule; doomedSplit abandons Queen at the front dead-end; MINE2 sends L2-3 drones into 1-wide shafts with zero corridor risk.
- **opponents/vb19**: Lines 1590-1593 explicitly detect coiled maps (`W==32 && H==16`) and ban round 0 opening splits for Queen, but still lacks shaft exclusion for drones.
- **opponents/vb21**: Disables opening splits (line 1759) and suppresses early danger-splits for Queen (line 1394: `ROUND <= 25 && !allowShed`), attempting an uncoil, but still allows drones to perish in shafts.

## 3. Top 3 Concrete Code Changes
1. **Shaft Exclusion for L<=3 Drones** (`cand_sec/main.cpp:1118-1120, 1171`):
   Extend `isDevilMap` to `isShaftMap = KM && (name == "devil" || name == "dilemma")`. Require `L >= 4` for `miner` on Dilemma so L2-3 drones retain `corridorRisk` and avoid entering 1-wide shafts where they cannot bud or escape.
2. **Dedicated LOOPFARM Harvester & Drone Veto** (`cand_sec/main.cpp:964, 1118, 1710`):
   In columns x=14/17, elect exactly ONE designated long dragon to farm the loop; apply a heavy penalty (`score -= 50`) for all other friendly dragons entering those columns to prevent lemming jams.
3. **Queen Opening Uncoil / Sink Transfer** (`cand_sec/main.cpp:1281, 1500, 1806`):
   At r0-2 in 1-wide dead ends, execute a planned uncoil split before the head traps itself, or transfer `trueQueenId`/sink status to the escaping rear child upon doomedSplit so the surviving mass carries queen tiebreak points.
