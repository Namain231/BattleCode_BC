# Sv5.1 on the ladder (viper_y96xn: Y.9.6 + tight CPU guard + our 716-game v6 net), 2026-10-03

Source: 20 series (16 ranked, 4 unranked) since upload 08:12Z = 135 games, replays in ladder/sv51/, tool tools/analyze_ours.py. Server record 57-78 (42.2%), rating 1634.
Y.9.6 (active) 218-219 for comparison. The user reset the active build to Y.9.6 afterwards.

Results
- By opponent (W/N): WeHaveQuizzes(2020) 0/5, Kamikaze(1944) 0/5, Adrak(1867) 1/5, dev test(1804) 0/5, chaoliangUNSW(1775) 0/5; about even vs 1600-1750 teams.
- By map worst: Maze 0/6, Slithery 1/8, Autarky 1/5, Stripes 2/10, Prisoners Dilemma 2/8; best: Around UNSW 6/9, Islands 6/9, Australia 5/7, Schooltime 5/8, Portals 5/8.
- Known maps 41.0% (n=78), new maps 45.5% (n=55): no visible unseen-map penalty in this sample (small).
- Our true queen died in 100 of 133 games (75%), median round 94.5; causes head-on 51, wall 24, body 12, no-action 8, self 5. 52 games had her dead by r100 (win rate 34.6%).
- Enemy queen died in 98 games (74%), median r175, mostly head-on (68). In the 76 LOSSES the enemy queen died 92% of the time and ours 70%: most games end with both queens dead, so longest dragon / elimination decide.
- Dragons lost per game 150 (head-on 7621 total, wall 5195, self 4107, no-action 1953, body 1145).
- Hot spots (per game): Slithery wall 218 + self 192; Maze wall 80, no-action 34; Devil wall 65 + self 78; Portals self 79; Around UNSW wall 85; Weakhold wall 43. These are suspect (blind steps / body mis-tracking) and not yet traced.
