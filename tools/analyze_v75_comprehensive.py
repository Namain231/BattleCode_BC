"""Comprehensive statistical analysis of all 242 games and 110 losses of V7.5.
"""
import io
import json
import os
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open("ladder/losses/v75_games.json", "r", encoding="utf-8") as f:
    games = json.load(f)

with open("ladder/losses/v75_losses.json", "r", encoding="utf-8") as f:
    losses = json.load(f)

print(f"================================================================================")
print(f"V7.5 COMPREHENSIVE LADDER & SCRIM EVALUATION (242 GAMES)")
print(f"================================================================================")
total_games = len(games)
wins = len([g for g in games if g['outcome'] == 'win'])
losses_cnt = len([g for g in games if g['outcome'] == 'loss'])
draws = len([g for g in games if g['outcome'] == 'draw'])

print(f"Total Games Played: {total_games}")
print(f"Wins:               {wins} ({wins/total_games*100:.1f}%)")
print(f"Losses:             {losses_cnt} ({losses_cnt/total_games*100:.1f}%)")
print(f"Draws:              {draws} ({draws/total_games*100:.1f}%)")

# 1. Map Breakdown
map_games = Counter()
map_wins = Counter()
map_losses = Counter()
map_draws = Counter()

for g in games:
    m = g['mapName'] or "Unknown"
    map_games[m] += 1
    if g['outcome'] == 'win':
        map_wins[m] += 1
    elif g['outcome'] == 'loss':
        map_losses[m] += 1
    else:
        map_draws[m] += 1

print(f"\n--- MAP RECORD BREAKDOWN (Sorted by Loss Rate) ---")
print(f"{'Map Name':<22} {'Losses':<8} {'Wins':<8} {'Draws':<8} {'Total':<8} {'Loss Rate':<10} {'Win Rate'}")
print("-" * 75)
for m in sorted(map_games.keys(), key=lambda k: map_losses[k]/map_games[k], reverse=True):
    tot = map_games[m]
    l = map_losses[m]
    w = map_wins[m]
    d = map_draws[m]
    l_rate = l / tot * 100
    w_rate = w / tot * 100
    print(f"{m:<22} {l:<8} {w:<8} {d:<8} {tot:<8} {l_rate:>5.1f}%     {w_rate:>5.1f}%")

# 2. Opponent Breakdown
opp_games = Counter()
opp_wins = Counter()
opp_losses = Counter()
opp_elo = {}

for g in games:
    opp = g['oppName']
    opp_games[opp] += 1
    if g.get('oppElo'):
        opp_elo[opp] = g['oppElo']
    if g['outcome'] == 'win':
        opp_wins[opp] += 1
    elif g['outcome'] == 'loss':
        opp_losses[opp] += 1

print(f"\n--- OPPONENT PERFORMANCE BREAKDOWN ---")
print(f"{'Opponent':<28} {'ELO':<6} {'Record (W-L-D)':<16} {'Games':<8} {'Loss Rate'}")
print("-" * 70)
for opp in sorted(opp_games.keys(), key=lambda k: opp_losses[k]/opp_games[k], reverse=True):
    tot = opp_games[opp]
    l = opp_losses[opp]
    w = opp_wins[opp]
    d = tot - w - l
    rate = l / tot * 100
    elo_str = str(opp_elo.get(opp, '?'))
    rec_str = f"{w}W - {l}L - {d}D"
    print(f"{opp:<28} {elo_str:<6} {rec_str:<16} {tot:<8} {rate:>5.1f}%")

# 3. Ranked vs Unranked
print(f"\n--- MATCH TYPE ---")
for t_name, is_r in [("Ranked", True), ("Unranked", False)]:
    sub = [g for g in games if g['ranked'] == is_r]
    w_sub = len([g for g in sub if g['outcome'] == 'win'])
    l_sub = len([g for g in sub if g['outcome'] == 'loss'])
    d_sub = len(sub) - w_sub - l_sub
    print(f"{t_name:<10}: {w_sub}W - {l_sub}L - {d_sub}D ({len(sub)} games, {l_sub/len(sub)*100:.1f}% loss rate)")

# 4. Side Bias
print(f"\n--- SIDE BIAS ---")
for s in ['A', 'B']:
    sub = [g for g in games if g['ourSide'] == s]
    w_sub = len([g for g in sub if g['outcome'] == 'win'])
    l_sub = len([g for g in sub if g['outcome'] == 'loss'])
    d_sub = len(sub) - w_sub - l_sub
    print(f"Side {s}: {w_sub}W - {l_sub}L - {d_sub}D ({len(sub)} games, {l_sub/len(sub)*100:.1f}% loss rate)")

# 5. Loss Margins & Scores
print(f"\n--- AVERAGE SCORE & LOSS MARGIN BY MAP IN LOSSES ---")
map_scores_us = defaultdict(list)
map_scores_opp = defaultdict(list)
crashes = []

for l in losses:
    m = l['mapName']
    if l.get('log'):
        crashes.append(l)
    us = l.get('ourScore')
    opp = l.get('oppScore')
    if us is not None and opp is not None:
        map_scores_us[m].append(us)
        map_scores_opp[m].append(opp)

for m in sorted(map_scores_us.keys()):
    avg_us = sum(map_scores_us[m]) / len(map_scores_us[m])
    avg_opp = sum(map_scores_opp[m]) / len(map_scores_opp[m])
    print(f"  {m:<22}: Avg Us {avg_us:5.1f} vs Avg Opp {avg_opp:5.1f} (Margin: -{avg_opp - avg_us:5.1f})")

if crashes:
    print(f"\nLosses with Server Crash/Timeout Logs: {len(crashes)}")
    for c in crashes[:5]:
        print(f"  Game {c['gameId']} ({c['mapName']}) vs {c['oppName']}: {c['log']}")
else:
    print(f"\nNo server crash logs or timeout errors found in any of the 110 losses.")
