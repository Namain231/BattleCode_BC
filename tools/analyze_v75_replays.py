import glob
import io
import json
import os
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TOOLS_DIR)
for p in (TOOLS_DIR, ROOT_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from replay import load, DEATHS

replays = sorted(glob.glob("ladder/losses/v75_replays/*.replay"))
print(f"Analyzing {len(replays)} replays for V7.5 losses...\n")

records = []

for path in replays:
    rep = load(path)
    fn = os.path.basename(path)
    lines = rep['map'].splitlines()
    map_name = next((l.split(" ", 1)[1] for l in lines if l.startswith("MAP_NAME")), lines[0] if lines else "?")
    res = rep.get('result', {})

    team = {}
    nid = 0
    for l in lines:
        p = l.split()
        if p and p[0] == "DRAGON":
            team[nid] = int(p[1])
            nid += 1

    deaths = [Counter(), Counter()]
    rounds = 0

    for e in rep['events']:
        k = e['kind']
        if k == 'roundStart':
            rounds = e['round']
        elif k == 'dragonSplit':
            team[e['child']] = e['team']
        elif k == 'dragonDeath':
            i = e['id']
            t = team.get(i)
            r = e['reason']
            r_str = DEATHS[r] if r < len(DEATHS) else str(r)
            if t in (0, 1):
                deaths[t][r_str] += 1

    # In our dataset, V7.5 was always Team A (0) in these games
    our_stats = res.get('A', {}) or {}
    opp_stats = res.get('B', {}) or {}
    winner = res.get('winner')
    end_reason = res.get('endReason')

    rec = {
        "file": fn,
        "map": map_name,
        "rounds": rounds,
        "winner": winner,
        "endReason": "elimination" if end_reason == 0 else ("round_limit" if end_reason == 1 else str(end_reason)),
        "ourCount": our_stats.get('count', 0),
        "ourLongest": our_stats.get('longest', 0),
        "ourTotal": our_stats.get('total', 0),
        "oppCount": opp_stats.get('count', 0),
        "oppLongest": opp_stats.get('longest', 0),
        "oppTotal": opp_stats.get('total', 0),
        "ourDeaths": dict(deaths[0]),
        "oppDeaths": dict(deaths[1])
    }
    records.append(rec)

# Print tabular report
print(f"{'Map':<18} {'Rounds':<7} {'End Reason':<13} {'Our Units':<10} {'Opp Units':<10} {'Our Lgst/Tot':<13} {'Opp Lgst/Tot':<13} {'Our Deaths'}")
print("-" * 125)
for r in sorted(records, key=lambda x: x['map']):
    our_u = f"{r['ourCount']}"
    opp_u = f"{r['oppCount']}"
    our_lt = f"{r['ourLongest']}/{r['ourTotal']}"
    opp_lt = f"{r['oppLongest']}/{r['oppTotal']}"
    deaths_summary = ", ".join(f"{k}:{v}" for k, v in r['ourDeaths'].items())
    print(f"{r['map']:<18} {r['rounds']:<7} {r['endReason']:<13} {our_u:<10} {opp_u:<10} {our_lt:<13} {opp_lt:<13} {deaths_summary}")

# Aggregate statistics
eliminated_count = sum(1 for r in records if r['ourCount'] == 0)
round_limit_count = sum(1 for r in records if r['endReason'] == 'round_limit')
print(f"\nTotal V7.5 Losses Analyzed: {len(records)}")
print(f"Total Eliminations (wiped out to 0): {eliminated_count} ({eliminated_count/len(records)*100:.1f}%)")
print(f"Lost on Round 500 Tiebreak: {round_limit_count} ({round_limit_count/len(records)*100:.1f}%)")

# Aggregate deaths by cause across all 22 losses
total_our_deaths = Counter()
total_opp_deaths = Counter()
for r in records:
    total_our_deaths.update(r['ourDeaths'])
    total_opp_deaths.update(r['oppDeaths'])

print("\n--- Total Deaths Across All 22 V7.5 Losses ---")
for k, v in total_our_deaths.most_common():
    opp_v = total_opp_deaths.get(k, 0)
    print(f"  {k:<20}: V7.5 died {v:4d} times | Opponents died {opp_v:4d} times")
