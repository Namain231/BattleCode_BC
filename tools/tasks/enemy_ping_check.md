# Task enemy_ping_check (EXECUTOR). Write ONE new script tools/enemy_ping_check.py (no other file edits) and run it.

Question: is an ENEMY sonar ray hitting our true queen a useful warning of her death? Data: ladder/sv52/games.json (+ .replay files) and ladder/sv51/games.json (if present, same format; fields: game, me (our team 0/1), map, our_queen_death=[round,cause]).
Decode with tools/replay_lite.decode_lite(path, {"roundStart","dragonUpdate","dragonDeath","dragonSplit","sonarPing"}) (see tools/echo_eval.py for the structure, helper code to reuse: how our queen id is found, how records per round are formed).
sonarPing event fields: sender (dragon id), dir, hit (dragon id hit or None), value, hitKind, origin, end. The sender's team: from the map's DRAGON lines (team per initial id) and dragonSplit (child team).
For each game and each round r in which our queen is alive: ping_in[r] = number of sonarPings in round r whose hit == our queen id and sender team != ours (enemy ray received; the queen reads it at her next turn). Also friend_in[r] (same team, sender != queen).
Use the LAST queen record per round as the unit (one record per round).
Report (to stdout; also save out/enemy_ping_check.txt):
 1. Fraction of queen rounds with ping_in>=1, overall and per phase (<100, 100-299, >=300), and the mean count; same for friend_in.
 2. For head-on queen deaths (cause head-on = our_queen_death[1] == 'headon' or 3; check the value format in games.json): P(head-on death within next 5 rounds | ping_in>=1 this round) vs P(... | ping_in==0), with counts; same for ping_in over the previous 2 rounds ("any in last 2").
 3. Death coverage: of the head-on deaths, how many had ping_in>=1 in at least one of the 5 rounds before death, vs a circular-shuffle null (200 shifts >= 20 rounds per game, same alarm rate), lift with empirical 95% interval.
 4. Does the enemy ping carry a payload format from known teams? Print for the top 5 enemy teams (by game count; team name is in games.json 'opp') the distribution of ping `value` high bits (value>>48) and the 10 most common raw values (so we can see if they broadcast positions). Do not assume; just report.
Run: cd /c/Users/sohan/Downloads/BattleCode_BC; export UV_CACHE_DIR='F:\uv-cache' PYTHONIOENCODING=utf-8; uv run --python 3.11 --with unswbc python tools/enemy_ping_check.py ladder/sv52 [ladder/sv51] (first test on 8 games with a --max-games flag).
Append ONE UTF-8 line to AGENT_LOG.md via printf >> : "- [2026-10-04] [executor] [enemy_ping_check] <headline numbers>". Report: headline numbers and what you could not verify.
