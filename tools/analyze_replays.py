import glob
import io
import os
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
# Ensure tools directory is in sys.path for runtime execution from any working directory
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TOOLS_DIR)
for p in (TOOLS_DIR, ROOT_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from tools.replay import load, DEATHS
except (ImportError, ModuleNotFoundError):
    from replay import load, DEATHS


def parse_replay(path):
    rep = load(path)
    fn = os.path.basename(path)
    lines = rep['map'].splitlines()
    map_name = next((l.split(" ", 1)[1] for l in lines if l.startswith("MAP_NAME")), lines[0] if lines else "?")
    res = rep.get('result', {})

    # Map dragon id to team
    team = {}
    nid = 0
    for l in lines:
        p = l.split()
        if p and p[0] == "DRAGON":
            team[nid] = int(p[1])
            nid += 1

    deaths = [Counter(), Counter()]
    kills_h2h = [0, 0]
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
                if r == 3:  # head to head
                    kills_h2h[1 - t] += 1

    print(f"\n========================================================")
    print(f"File: {fn}")
    print(f"Map: {map_name} | Total Rounds: {rounds}")
    print(f"Final Outcome: Winner={res.get('winner')} EndReason={res.get('endReason')}")
    print(f"Team 0 Stats: Count={res.get('A', {}).get('count')} Longest={res.get('A', {}).get('longest')} TotalLen={res.get('A', {}).get('total')}")
    print(f"Team 1 Stats: Count={res.get('B', {}).get('count')} Longest={res.get('B', {}).get('longest')} TotalLen={res.get('B', {}).get('total')}")
    print(f"Team 0 Deaths: {dict(deaths[0])}")
    print(f"Team 1 Deaths: {dict(deaths[1])}")

for path in sorted(glob.glob('ladder/losses/replays/*.replay')):
    parse_replay(path)
