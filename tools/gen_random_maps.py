"""Random fair maps for generalisation: self-play on many layouts, and a test set of maps no rule was tuned on.

    python tools/gen_random_maps.py --n 200 --out maps_gen [--seed 0]

The next phase uses new maps; a policy trained or tuned on a handful of layouts overfits them (Procgen; procedural
map generators: a specialist fell to 3% on unseen mazes, a mixed-generator policy kept 91%). Every map here is
point-symmetric (SYMMETRY xy, like most live maps) and wraps around (torus), with the live maps' ranges:
  - size 20-64 x 14-40; kelp on 4-30% of the edges, drawn as wall segments (corridors, rooms, dead ends);
  - pearl tiles: 6-14% of tiles slow (1..200 rounds), a few fast fountains (1..1);
  - 0-5 portal pairs; 1-7 dragons per team of length 4, mirrored starts.
Each map is validated by the engine itself (a short random game) and kept only if its open area is connected.
Output: <out>/gen_<n>.map with MAP_NAME Gen<n> (maps_gen/ is kept out of maps_data.hpp).
"""
import argparse
import pathlib
import random
import sys
from collections import deque

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Board:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.north = [[0] * W for _ in range(H)]   # kind of the north side of tile (x, y): 0 open, 1 kelp, 2 portal
        self.west = [[0] * W for _ in range(H)]
        self.pid = {}                               # (side, x, y) -> portal id

    def mirror(self, side, x, y):
        """Point reflection of a tile side: the north side of (x, y) is the south side of (x, y-1)."""
        W, H = self.W, self.H
        if side == "n":
            return "n", (W - 1 - x) % W, (H - y) % H
        return "w", (W - x) % W, (H - 1 - y) % H

    def set(self, side, x, y, kind, pid=None):
        for s, xx, yy in ((side, x, y), self.mirror(side, x, y)):
            (self.north if s == "n" else self.west)[yy][xx] = kind
            if pid is not None:
                self.pid[(s, xx, yy)] = pid

    def blocked(self, x, y, d):
        """Kelp between tile (x, y) and its neighbour in direction d (0 N, 1 E, 2 S, 3 W)."""
        W, H = self.W, self.H
        if d == 0:
            return self.north[y][x] == 1
        if d == 2:
            return self.north[(y + 1) % H][x] == 1
        if d == 3:
            return self.west[y][x] == 1
        return self.west[y][(x + 1) % W] == 1

    def components(self):
        W, H = self.W, self.H
        comp = [[-1] * W for _ in range(H)]
        sizes = []
        for sy in range(H):
            for sx in range(W):
                if comp[sy][sx] >= 0:
                    continue
                c = len(sizes); comp[sy][sx] = c; q = deque([(sx, sy)]); n = 0
                while q:
                    x, y = q.popleft(); n += 1
                    for d, (dx, dy) in enumerate(((0, -1), (1, 0), (0, 1), (-1, 0))):
                        nx, ny = (x + dx) % W, (y + dy) % H
                        if comp[ny][nx] < 0 and not self.blocked(x, y, d):
                            comp[ny][nx] = c; q.append((nx, ny))
                sizes.append(n)
        return comp, sizes


def make_map(rng, idx):
    W, H = rng.randint(20, 64), rng.randint(14, 40)
    b = Board(W, H)
    density = rng.uniform(0.04, 0.30)
    target = int(density * 2 * W * H)
    placed = 0
    while placed < target:                          # wall segments: corridors, rooms, dead ends
        side = rng.choice("nw"); x, y = rng.randrange(W), rng.randrange(H)
        length = rng.choice([1, 2, 3, 4, 5, 6, 8, 10])
        for k in range(length):
            xx, yy = (x + k, y) if side == "n" else (x, y + k)   # a north-side wall runs east, a west-side one south
            b.set(side, xx % W, yy % H, 1)
        placed += 2 * length
    for p in range(rng.randint(0, 5)):              # portal pairs: two same-orientation open edges, mirrored
        side = rng.choice("nw")
        a = (rng.randrange(W), rng.randrange(H)); c = (rng.randrange(W), rng.randrange(H))
        if a == c:
            continue
        b.set(side, *a, 2, pid=2 * p); b.set(side, *c, 2, pid=2 * p)
        # mirrored copies share the id of their originals: give the mirror pair its own id
        ma, mc = b.mirror(side, *a), b.mirror(side, *c)
        if {ma, mc} != {(side,) + a, (side,) + c}:
            b.pid[ma] = 2 * p + 1; b.pid[mc] = 2 * p + 1
    comp, sizes = b.components()
    big = max(range(len(sizes)), key=lambda c: sizes[c])
    if sizes[big] < 0.85 * W * H:
        return None
    # dragons: straight length-4 bodies in the big component, mirrored for team B
    occ = set(); dragons = []
    for _ in range(rng.randint(1, 7)):
        for _try in range(50):
            x, y, d = rng.randrange(W), rng.randrange(H), rng.randrange(4)
            dx, dy = ((0, -1), (1, 0), (0, 1), (-1, 0))[d]
            cells = [((x - k * dx) % W, (y - k * dy) % H) for k in range(4)]   # head first, body behind
            mir = [((W - 1 - cx) % W, (H - 1 - cy) % H) for cx, cy in cells]
            allc = cells + mir
            if len(set(allc)) < 8 or any(c in occ for c in allc) or any(comp[cy][cx] != big for cx, cy in allc):
                continue
            # no kelp between consecutive segments, and room to move out
            ok = all(not b.blocked(cells[k + 1][0], cells[k + 1][1], d) for k in range(3))
            if ok and not b.blocked(x, y, d):
                occ.update(allc); dragons.append((cells, mir)); break
    if not dragons:
        return None
    lines = [f"MAP {W} {H}", "SYMMETRY xy", f"MAP_NAME Gen{idx}", f"TILE_COUNT {W * H}"]
    slow, fast = rng.uniform(0.06, 0.14), rng.uniform(0.0, 0.012)
    rate = {}
    for y in range(H):
        for x in range(W):
            if (x, y) in rate:
                continue
            r = rng.random()
            v = (1, 1) if r < fast else (1, 200) if r < fast + slow else (0, 0)
            rate[(x, y)] = v; rate[((W - 1 - x) % W, (H - 1 - y) % H)] = v
    lines += [f"TILE {x} {y} {rate[(x, y)][0]} {rate[(x, y)][1]}" for y in range(H) for x in range(W)]
    edges = []
    for y in range(H):
        for x in range(W):
            for side, r in (("n", 2 * y), ("w", 2 * y + 1)):
                k = (b.north if side == "n" else b.west)[y][x]
                edges.append(f"EDGE {r * (W + 1) + x} {k} {b.pid.get((side, x, y), -1) if k == 2 else -1}")
    lines += [f"EDGE_COUNT {len(edges)}"] + edges
    lines.append(f"DRAGON_COUNT {2 * len(dragons)}")
    for cells, _ in dragons:
        lines.append("DRAGON 0 4 " + " ".join(f"{x} {y}" for x, y in cells))
    for _, mir in dragons:
        lines.append("DRAGON 1 4 " + " ".join(f"{x} {y}" for x, y in mir))
    lines.append("END")
    return "\n".join(lines) + "\n"


def engine_ok(text):
    """Run a short game in the real engine: it rejects malformed maps."""
    sys.path.insert(0, str(ROOT / "ml"))
    from unswbc.engine import EngineModule

    def reply(did, block):
        return b"MOVE N\nENDTURN\n"
    try:
        EngineModule().run(text.encode(), reply, None, None, lambda line: None, 0, 1)
        return True, ""
    except Exception as e:
        return False, str(e)[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", default="maps_gen")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    out = ROOT / a.out; out.mkdir(exist_ok=True)
    made = tries = 0
    while made < a.n and tries < 20 * a.n:
        tries += 1
        text = make_map(rng, made)
        if text is None:
            continue
        ok, err = engine_ok(text)
        if not ok:
            print("engine rejected:", err); continue
        (out / f"gen_{made:03d}.map").write_text(text)
        made += 1
    print(f"{made} maps in {out} ({tries} tries)")


if __name__ == "__main__":
    main()
