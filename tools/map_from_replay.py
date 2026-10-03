"""Rebuild a playable map from a ladder replay: ladder replays zero the TILE spawn ranges (TILE x y 0 0), so estimate
each tile's [minGap,maxGap] from the spawns seen in the replay (pearls appearing between roundStart and the first
turnStart of that round = spawns, not death drops). Several replays of the same map can be pooled.
usage: python tools/map_from_replay.py OUT.map REPLAY [REPLAY...]"""
import sys, collections
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from replay import _decode
out, reps = sys.argv[1], sys.argv[2:]
spawns = collections.defaultdict(set); base = None
for f in reps:
    r = _decode(f); base = base or r['map']; rnd = 0; pre = False
    for e in r['events']:
        k = e['kind']
        if k == 'roundStart': rnd = e['round']; pre = True
        elif k == 'turnStart': pre = False
        elif k == 'tileChange' and pre and e.get('pearl'): spawns[tuple(e['tile'])].add((f, rnd))
# mirrored tiles share one table (engine check): pool each tile with its mirror (SYM env: rot|h|v, default rot)
import os as _o
W, H = map(int, base.splitlines()[0].split()[1:3])
sym = _o.environ.get('SYM', 'rot')
def mir(t):
    x, y = t
    return {'rot': (W-1-x, H-1-y), 'h': (W-1-x, y), 'v': (x, H-1-y)}[sym]
for t in list(spawns): spawns[mir(t)] |= spawns[t]
for t in list(spawns): spawns[t] |= spawns[mir(t)]
gaps = {}
for t, s in spawns.items():
    by = collections.defaultdict(list)
    for f, r in s: by[f].append(r)
    g = []
    for rs in by.values():
        rs.sort(); g += [b - a for a, b in zip(rs, rs[1:])]
    first = min(r for _, r in s)
    if g: gaps[t] = (max(1, min(g)), max(g))
    else: gaps[t] = (max(1, first), max(1, first) * 2)
lines = []; n = 0
for l in base.splitlines():
    p = l.split()
    if p and p[0] == 'TILE':
        t = (int(p[1]), int(p[2]))
        if t in gaps: p[3], p[4] = str(gaps[t][0]), str(gaps[t][1]); n += 1
        l = ' '.join(p)
    lines.append(l)
open(out, 'w').write('\n'.join(lines) + '\n')
print(f"{out}: {n} spawning tiles from {len(reps)} replays")
