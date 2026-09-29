"""Generate a random, valid, 180-degree-symmetric map that no bot has in its map database.

    python tools/random_map.py --seed 7 --w 40 --h 22 --out maps/unseen_r7.map

Kelp walls are random (--walls = chance per edge), then removed in symmetric pairs until every
tile is reachable on the torus. Spawn areas are kept open. Pearl gaps follow the live maps: most
tiles never spawn, many spawn rarely, a few are fountains. Do not run gen_maps.py with the map in
maps/ if it is meant to stay unseen.
"""
import argparse
import pathlib
import random

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--w", type=int, default=40)
ap.add_argument("--h", type=int, default=22)
ap.add_argument("--walls", type=float, default=0.30)
ap.add_argument("--out", required=True)
args = ap.parse_args()
rng = random.Random(args.seed)
W, H = args.w, args.h


def rot(x, y):
    return W - 1 - x, H - 1 - y


# edges: ("N", x, y) is the north edge of (x, y), ("W", x, y) its west edge
def edge_rot(e):
    k, x, y = e
    rx, ry = rot(x, y)
    if k == "N":  # north of (x, y) becomes south of (rx, ry) = north of (rx, ry + 1)
        return ("N", rx, (ry + 1) % H)
    return ("W", (rx + 1) % W, ry)  # west becomes east of (rx, ry) = west of (rx + 1, ry)


kelp = set()
for y in range(H):
    for x in range(W):
        for k in "NW":
            e = (k, x, y)
            if rng.random() < args.walls:
                kelp.add(e); kelp.add(edge_rot(e))

# three starting dragons of length 4 per team, heads facing east on the left side
spawn_rows = [H // 2 - 6, H // 2 - 1, H // 2 + 4]
team0 = [[(5, y), (4, y), (3, y), (2, y)] for y in spawn_rows]
team1 = [[rot(x, y) for x, y in d] for d in team0]
for d in team0:
    y = d[0][1]
    for yy in range(y - 1, y + 2):
        for xx in range(1, 8):
            for e in (("N", xx, yy % H), ("W", xx, yy % H), ("N", xx, (yy + 1) % H), ("W", xx + 1, yy % H)):
                kelp.discard(e); kelp.discard(edge_rot(e))


def neighbours(x, y):
    if ("N", x, y) not in kelp: yield x, (y - 1) % H
    if ("N", x, (y + 1) % H) not in kelp: yield x, (y + 1) % H
    if ("W", x, y) not in kelp: yield (x - 1) % W, y
    if ("W", (x + 1) % W, y) not in kelp: yield (x + 1) % W, y


def reached():
    seen = {(team0[0][0])}
    todo = [team0[0][0]]
    while todo:
        c = todo.pop()
        for n in neighbours(*c):
            if n not in seen:
                seen.add(n); todo.append(n)
    return seen


while True:
    seen = reached()
    if len(seen) == W * H:
        break
    # open a wall between a reached tile and an unreached neighbour
    border = [e for e in kelp if (e[1], e[2]) in seen or
              ((e[1], (e[2] - 1) % H) if e[0] == "N" else ((e[1] - 1) % W, e[2])) in seen]
    rng.shuffle(border)
    for e in border:
        a = (e[1], e[2])
        b = (e[1], (e[2] - 1) % H) if e[0] == "N" else ((e[1] - 1) % W, e[2])
        if (a in seen) != (b in seen):
            kelp.discard(e); kelp.discard(edge_rot(e))
            break

# pearl gaps (min, max), symmetric; max 0 = never spawns
gaps = {}
for y in range(H):
    for x in range(W):
        if (x, y) in gaps:
            continue
        r = rng.random()
        g = (0, 0) if r < 0.60 else (1, rng.choice([200, 300, 600])) if r < 0.88 else (1, rng.choice([30, 50, 100]))
        gaps[(x, y)] = g; gaps[rot(x, y)] = g
spawn_cells = {c for d in team0 + team1 for c in d}
fountains = [(W // 2 - 1, H // 2 - 1), (W // 2 - 1, H // 2), (rng.randrange(8, W // 2 - 3), rng.randrange(H)),
             (rng.randrange(8, W // 2 - 3), rng.randrange(H))]
for f in fountains:
    if f in spawn_cells:
        continue
    g = (1, rng.choice([1, 1, 2, 3]))
    gaps[f] = g; gaps[rot(*f)] = g

lines = [f"MAP {W} {H}", "SYMMETRY xy", f"MAP_NAME Unseen R{args.seed}", f"TILE_COUNT {W * H}"]
for y in range(H):
    for x in range(W):
        lo, hi = gaps[(x, y)]
        lines.append(f"TILE {x} {y} {lo} {hi}")
edges = []
for y in range(H):
    for k, r in (("N", 2 * y), ("W", 2 * y + 1)):
        for x in range(W):
            edges.append(f"EDGE {r * (W + 1) + x} {1 if (k, x, y) in kelp else 0} -1")
lines.append(f"EDGE_COUNT {len(edges)}")
lines += edges
dragons = []
for a, b in zip(team0, team1):
    for t, d in ((0, a), (1, b)):
        dragons.append(f"DRAGON {t} {len(d)} " + " ".join(f"{x} {y}" for x, y in d))
lines.append(f"DRAGON_COUNT {len(dragons)}")
lines += dragons
lines.append("END")
pathlib.Path(args.out).write_text("\n".join(lines) + "\n")
narrow = sum(1 for y in range(H) for x in range(W) if len(list(neighbours(x, y))) <= 2)
print(f"wrote {args.out}: {W}x{H}, {len(kelp)} kelp edges, narrow tiles {narrow / (W * H):.2f}, "
      f"fountains {sorted(set(f for f in fountains))}")
