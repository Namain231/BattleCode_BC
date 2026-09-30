import io
import json
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open('ladder/losses/losses_dataset.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

v75_games = [g for g in data['allGames'] if g.get('ourSubId') == 7793 or g.get('ourSubName') == 'v7.5-miners']
v75_losses = [g for g in v75_games if g['outcome'] == 'loss']
v75_wins = [g for g in v75_games if g['outcome'] == 'win']

print(f"Total V7.5 games: {len(v75_games)}")
print(f"Wins: {len(v75_wins)}, Losses: {len(v75_losses)}")

# Map breakdown
m_games = Counter()
m_losses = Counter()
m_wins = Counter()
for g in v75_games:
    m = g['mapName']
    m_games[m] += 1
    if g['outcome'] == 'loss':
        m_losses[m] += 1
    elif g['outcome'] == 'win':
        m_wins[m] += 1

print("\n--- V7.5 Record by Map ---")
for m in sorted(m_games.keys(), key=lambda k: m_losses[k]/m_games[k], reverse=True):
    tot = m_games[m]
    l = m_losses[m]
    w = m_wins[m]
    print(f"  {m:<22}: {w}W - {l}L ({l/tot*100:5.1f}% loss rate)")

# Opponent breakdown
opp_games = Counter()
opp_losses = Counter()
opp_wins = Counter()
opp_elo = {}
for g in v75_games:
    opp = g['oppName']
    opp_games[opp] += 1
    if g.get('oppElo'):
        opp_elo[opp] = g['oppElo']
    if g['outcome'] == 'loss':
        opp_losses[opp] += 1
    elif g['outcome'] == 'win':
        opp_wins[opp] += 1

print("\n--- V7.5 Record by Opponent ---")
for opp in sorted(opp_games.keys(), key=lambda k: opp_losses[k]/opp_games[k], reverse=True):
    tot = opp_games[opp]
    l = opp_losses[opp]
    w = opp_wins[opp]
    elo = opp_elo.get(opp, '?')
    print(f"  {opp:<25} ({elo}): {w}W - {l}L ({l/tot*100:5.1f}% loss rate)")

print("\n--- All V7.5 Losses Detail ---")
for g in v75_losses:
    score_str = f"Us {g.get('ourScore', '?')} vs Opp {g.get('oppScore', '?')}"
    print(f"  Game {g['gameId']} [{g['mapName']:<18}] vs {g['oppName']:<15} (Side {g['ourSide']}, Ranked: {str(g['ranked']):<5}) -> {score_str}")
