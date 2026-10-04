# Slithery coil and Dilemma traces (viper_y96xn = Sv5.1 code, new tables, vs Y.9.6; local debug replays out/m6_new), 2026-10-03

## Slithery Fight (live map: both queens start L25 in a closed spiral)
- Queen 0 head (3,22): all four neighbours are her own body (neck idx1 + coil turns idx3/idx5/idx7). Every move into own body kills (collision is checked before the tail leaves).
- r0: ESCAPE-SPLIT 23 -> parent keeps 2 segments, child gets 23 (child head at old tail (1,24)). r1: queen "DOOMED len/units", moves into own body, dies 'self' (6/6 local games, 8/8 ladder games, both queens).
- Cause: after any split the cells around her head are still occupied (child body); queens move first each round, so the child has not vacated them at r1. Child needs >=2 sprint steps at r0 to free idx3, 4 for idx5, 6 for idx7 (free steps for L23 = 6), but nothing coordinates this and the queen is L2 (cannot split again).
- Aftermath: ~500 wall+self deaths per game, each preceded by "DOOMED" (287 wall, 216 self in the sampled game), almost all after r20 (by round bin: 21-100: 83, 101-250: 263, >250: 153): small drones trapped in one-wide spiral corridors (over-budding into a closed spiral / doomed with len<4 so no escape split).
- Not a table problem: new and old tables behave the same (queen dead r1 in 6/6 with each).
Ideas: (1) coil opening: choose the split size by simulating the child's r0 uncoil (engine_sim/engine_cpp), make the child sprint >=k steps along its own body path; (2) keep the queen longer than 2 if one of idx3/5/7 can be freed; (3) cap budding in closed corridors (room test).

## Prisoners Dilemma (live map: queen L3; 0/6 vs Y.9.6 with both tables)
- Both sides stay tiny: units at r50/r100/r200 ours 5-8 / 5-8 / 5-10 vs theirs 6-8 / 6-7 / 6-13; the gap opens at r200-300: ours 1-8 at r300 and 1-3 at r400 vs theirs 10-18 and 15-24. We are out-grown and eliminated (count 0-3 at the end), the queen dies head-on r190-470.
- Compare Default (we win 5/6): our units 16-25 at r100, 25-45 at r200.
- Our losses per game on Dilemma: self 4-16, wall 4-18, head-on 7-15 out of a population of only 5-10: avoidable suicides are a large share. Hypotheses to test: economy stalls (few pearl beds reached), no portal use (PEXPLORE), small drones DOOMED in dead ends.
