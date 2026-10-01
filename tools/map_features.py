"""Structural features of maps, to find what the name-based switches (bigFeed / farSight) actually key on and to
replace them with quantities a bot can measure. Portal-aware (profile_style.parse_map).

    uv run --python 3.11 python tools/map_features.py maps/*.map [maps_gen/gen_00*.map]
Columns: tiles, open-edge share, dead-end/corridor/junction tile shares (degree 1/2/>=3), tortuosity (mean BFS
distance / torus Manhattan over random pairs), mean BFS distance, fast beds (max gap <= 10) and medium (<= 300)
per 100 tiles, tiles per starting dragon (per team), largest room (tiles of degree>=3 connected through degree>=3).
"""
import random, sys, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from profile_style import parse_map

def feats(path):
    t = pathlib.Path(path).read_text()
    w, h, nbr, spawn = parse_map(t)
    N = w * h
    deg = [len(set(nbr[c])) for c in range(N)]
    rng = random.Random(1)
    def bfs(s):
        d = {s: 0}; q = collections.deque([s])
        while q:
            c = q.popleft()
            for n in nbr[c]:
                if n not in d: d[n] = d[c] + 1; q.append(n)
        return d
    rat, dists = [], []
    for _ in range(12):
        s = rng.randrange(N); d = bfs(s)
        for tgt in rng.sample(range(N), 40):
            if tgt in d and tgt != s:
                dx = abs(s % w - tgt % w); dy = abs(s // w - tgt // w)
                m = min(dx, w - dx) + min(dy, h - dy)
                rat.append(d[tgt] / m); dists.append(d[tgt])
    fast = med = 0
    for l in t.splitlines():
        if l.startswith('TILE '):
            a, b = int(l.split()[3]), int(l.split()[4])
            if b > 0 and b <= 10: fast += 1
            elif b > 0 and b <= 300: med += 1
    ndr = sum(1 for l in t.splitlines() if l.startswith('DRAGON ')) / 2
    # rooms: components of tiles with degree >= 3
    seen = set(); big = 0
    for c in range(N):
        if deg[c] >= 3 and c not in seen:
            q = [c]; seen.add(c); n = 0
            while q:
                x = q.pop(); n += 1
                for y in nbr[x]:
                    if deg[y] >= 3 and y not in seen: seen.add(y); q.append(y)
            big = max(big, n)
    name = next((l.split(maxsplit=1)[1] for l in t.splitlines() if l.startswith('MAP_NAME')), path)
    return dict(name=name[:16], tiles=N, dead=sum(d <= 1 for d in deg) / N, corr=sum(d == 2 for d in deg) / N,
                junc=sum(d >= 3 for d in deg) / N, tort=sum(rat) / len(rat), dist=sum(dists) / len(dists),
                fast=100 * fast / N, med=100 * med / N, perdr=N / max(1, ndr), room=big / N)

print(f"{'map':16s} {'tiles':>5s} {'dead':>5s} {'corr':>5s} {'junc':>5s} {'tort':>5s} {'dist':>5s} {'fast%':>5s} {'med%':>5s} {'t/dr':>5s} {'room':>5s}")
for p in sys.argv[1:]:
    try: f = feats(p)
    except Exception as e: print(p, 'ERR', e); continue
    print(f"{f['name']:16s} {f['tiles']:5d} {f['dead']:5.2f} {f['corr']:5.2f} {f['junc']:5.2f} {f['tort']:5.2f} {f['dist']:5.1f} {f['fast']:5.1f} {f['med']:5.1f} {f['perdr']:5.0f} {f['room']:5.2f}")
