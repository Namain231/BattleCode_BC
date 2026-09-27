"""Comprehensive analysis of losses against opponents.
"""
import io
import json
import sys
from collections import Counter, defaultdict

# Force UTF-8 on Windows stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open('ladder/losses/losses_dataset.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

losses = data['losses']
all_games = data['allGames']
subs = data.get('submissions', {})

print(f"=== BHOLE CHATURE (Team #98) LOSS ANALYSIS ===")
print(f"Total Battles Recorded: {data['summary']['totalBattles']}")
print(f"Total Games Played:     {len(all_games)}")
print(f"Total Wins:             {data['summary']['totalWins']} ({data['summary']['totalWins']/len(all_games)*100:.1f}%)")
print(f"Total Losses:           {len(losses)} ({len(losses)/len(all_games)*100:.1f}%)")
print(f"Total Draws:            {data['summary']['totalDraws']}")

# 1. Opponent Breakdown
opp_losses = Counter()
opp_games = Counter()
opp_wins = Counter()
opp_elo = {}
for g in all_games:
    opp = g['oppName']
    opp_games[opp] += 1
    if g.get('oppElo'):
        opp_elo[opp] = g['oppElo']
    if g['outcome'] == 'loss':
        opp_losses[opp] += 1
    elif g['outcome'] == 'win':
        opp_wins[opp] += 1

print("\n--- LOSSES BY OPPONENT (All-Time) ---")
print(f"{'Opponent':<28} {'ELO':<6} {'Losses':<8} {'Total':<8} {'Loss Rate':<10} {'Record (W-L)'}")
print("-" * 75)
for opp, cnt in opp_losses.most_common():
    tot = opp_games[opp]
    w = opp_wins[opp]
    rate = cnt / tot * 100
    elo_str = str(opp_elo.get(opp, '?'))
    print(f"{opp:<28} {elo_str:<6} {cnt:<8} {tot:<8} {rate:>5.1f}%     {w}W - {cnt}L")

# 2. Map Breakdown
map_losses = Counter()
map_games = Counter()
map_wins = Counter()
for g in all_games:
    m = g['mapName'] or "Unknown"
    map_games[m] += 1
    if g['outcome'] == 'loss':
        map_losses[m] += 1
    elif g['outcome'] == 'win':
        map_wins[m] += 1

print("\n--- LOSSES BY MAP (All-Time) ---")
print(f"{'Map Name':<22} {'Losses':<8} {'Total':<8} {'Loss Rate':<10} {'Record (W-L)'}")
print("-" * 65)
for m, cnt in map_losses.most_common():
    tot = map_games[m]
    w = map_wins[m]
    rate = cnt / tot * 100
    print(f"{m:<22} {cnt:<8} {tot:<8} {rate:>5.1f}%     {w}W - {cnt}L")

# 3. Version Breakdown
ver_losses = Counter()
ver_games = Counter()
ver_wins = Counter()
for g in all_games:
    v = g['ourSubName']
    ver_games[v] += 1
    if g['outcome'] == 'loss':
        ver_losses[v] += 1
    elif g['outcome'] == 'win':
        ver_wins[v] += 1

print("\n--- LOSSES BY BOT SUBMISSION VERSION ---")
print(f"{'Version':<26} {'Losses':<8} {'Total':<8} {'Loss Rate':<10} {'Record (W-L)'}")
print("-" * 70)
# Sort by submission id or version order
sub_ids = sorted(subs.keys(), reverse=True)
for sid in sub_ids:
    sname = subs[sid]['name']
    cnt = ver_losses[sname]
    tot = ver_games[sname]
    w = ver_wins[sname]
    if tot == 0:
        continue
    rate = cnt / tot * 100
    print(f"{sname:<26} {cnt:<8} {tot:<8} {rate:>5.1f}%     {w}W - {cnt}L")

# 4. Recent Versions (v7.4 - v7.7) Detailed Performance per Map
recent_vers = ["v7.7-viable-buds", "v7.6-escapable-miners", "v7.5-miners", "v7.4-numbers"]
print("\n--- RECENT GENERATION (V7.4 - V7.7) MAP LOSS MATRIX ---")
header = f"{'Map':<20}" + "".join([f"{v[:12]:<14}" for v in recent_vers]) + "Total Loss Rate"
print(header)
print("-" * len(header))

all_maps = sorted(map_games.keys())
for m in all_maps:
    row = f"{m:<20}"
    tot_rec_m = 0
    loss_rec_m = 0
    for v in recent_vers:
        g_mv = [g for g in all_games if g['mapName'] == m and g['ourSubName'] == v]
        l_mv = [g for g in g_mv if g['outcome'] == 'loss']
        tot_rec_m += len(g_mv)
        loss_rec_m += len(l_mv)
        if g_mv:
            row += f"{len(l_mv)}L/{len(g_mv)}G ({len(g_mv)-len(l_mv)}W)  "
        else:
            row += f"{'-':<14}"
    overall = f"{loss_rec_m}/{tot_rec_m} ({loss_rec_m/tot_rec_m*100:.0f}%)" if tot_rec_m else "-"
    row += overall
    print(row)

# 5. Side comparison (Team A vs Team B)
side_losses = Counter()
side_games = Counter()
for g in all_games:
    s = g['ourSide']
    side_games[s] += 1
    if g['outcome'] == 'loss':
        side_losses[s] += 1

print("\n--- SIDE BIAS ---")
for s in ['A', 'B']:
    tot = side_games[s]
    l = side_losses[s]
    print(f"Side {s}: {l} losses out of {tot} games ({l/tot*100:.1f}% loss rate)")

# 6. Ranked vs Unranked
match_type_losses = Counter()
match_type_games = Counter()
for g in all_games:
    t = "Ranked" if g['ranked'] else "Unranked"
    match_type_games[t] += 1
    if g['outcome'] == 'loss':
        match_type_losses[t] += 1

print("\n--- MATCH TYPE ---")
for t in ['Ranked', 'Unranked']:
    tot = match_type_games[t]
    l = match_type_losses[t]
    print(f"{t}: {l} losses out of {tot} games ({l/tot*100:.1f}% loss rate)")
