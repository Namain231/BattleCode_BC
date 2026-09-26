"""Render the true board around a dragon at the start of its turn in a given round.

    python tools/board_at.py ladder/305467.replay 7 169 [--radius 9]
"""
import argparse, sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from replay import load

ap = argparse.ArgumentParser()
ap.add_argument("path"); ap.add_argument("id", type=int); ap.add_argument("round", type=int)
ap.add_argument("--radius", type=int, default=9)
a = ap.parse_args()
rep = load(a.path)
lines = rep["map"].splitlines()
W, H = map(int, lines[0].split()[1:3])
kel = {}
team, body, nid = {}, {}, 0
for l in lines:
    p = l.split()
    if not p: continue
    if p[0] == "EDGE":
        i, k, pid = map(int, p[1:4]); r, c = divmod(i, W + 1)
        key = (c % W, (r // 2) % H, "N") if r % 2 == 0 else (c % W, ((r - 1) // 2) % H, "W")
        kel[key] = k
    if p[0] == "DRAGON":
        t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
        team[nid] = t; body[nid] = [(c[2*i], c[2*i+1]) for i in range(n)]; nid += 1
pearls = set(); rnd = 0; alive = set(team); ind = ""
for e in rep["events"]:
    k = e["kind"]
    if k == "roundStart": rnd = e["round"]
    if k == "turnStart" and rnd == a.round and e["id"] == a.id: break
    if k == "tileChange":
        (pearls.add if e["pearl"] else pearls.discard)(e["tile"])
    elif k == "dragonUpdate" and e["id"] in body and e["head"]:
        b = body[e["id"]]
        if b[0] != e["head"]: b.insert(0, e["head"])
        while len(b) > 1 and b[-1] != e["tail"]: b.pop()
        pearls.discard(e["head"])
    elif k == "dragonSplit":
        team[e["child"]] = e["team"]; body[e["child"]] = e["childBody"]; body[e["parent"]] = e["parentBody"]; alive.add(e["child"])
    elif k == "dragonDeath": alive.discard(e["id"])
    elif k == "dragonIndicator" and e["id"] == a.id: ind = f"r{rnd} {e['text']}"
occ = {}
for i in alive:
    for j, c in enumerate(body[i]):
        occ[c] = (i, j)
me = team[a.id]; hx, hy = body[a.id][0]
print(f"round {a.round} dragon {a.id} len {len(body[a.id])} head {hx},{hy}; last indicator: {ind}")
print("legend: @=our head, o=our body, a/A=ally body/head, x/X=enemy body/head, *=pearl, |/-- kelp, P portal, #=7x7 view edge")
R = a.radius
for dy in range(-R, R + 1):
    top = row = ""
    for dx in range(-R, R + 1):
        x, y = (hx + dx) % W, (hy + dy) % H
        kn, kw = kel.get((x, y, "N"), 0), kel.get((x, y, "W"), 0)
        top += "+" + ("--" if kn == 1 else "PP" if kn == 2 else "  ")
        row += "|" if kw == 1 else "P" if kw == 2 else " "
        inview = abs(dx) <= 3 and abs(dy) <= 3
        if (x, y) in occ:
            i, j = occ[(x, y)]
            if i == a.id: ch = "@" if j == 0 else "o"
            elif team[i] == me: ch = "A" if j == 0 else "a"
            else: ch = "X" if j == 0 else "x"
            tag = str(i % 10)
        else:
            ch = "*" if (x, y) in pearls else " "; tag = " "
        row += ch + ("#" if not inview and ch == " " and False else tag)
    print(top); print(row)
