"""Late-game traffic around the longest dragon (r400-499): allied heads within Chebyshev 4 of its head, free neighbour
cells of its head, cells travelled; top-team open-map wins vs our open-map losses.

    python tools/queen_traffic.py --n 20
"""
import argparse, glob, json, os, pathlib, random, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode  # noqa: E402
ROOT = pathlib.Path(__file__).resolve().parents[1]
OPEN = {"Portals", "Slithery Fight", "Schooltime"}


def traffic(path, team):
    rep = _decode(path)
    lines = rep["map"].splitlines()
    W = H = None; tm, body, nid = {}, {}, 0
    for l in lines:
        p = l.split()
        if p and p[0] in ("MAP", "SIZE") and len(p) >= 3 and W is None:
            try: W, H = int(p[1]), int(p[2])
            except ValueError: pass
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            tm[nid] = t; body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    if W is None:  # fall back: infer from coordinates seen
        W = H = 64
    alive = set(tm); rnd = 0; crowd = []; free = []; moves = 0; last = None; name = None
    def cheb(a, b):
        dx = abs(a[0] - b[0]); dy = abs(a[1] - b[1])
        return max(min(dx, W - dx), min(dy, H - dy))
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if 400 <= rnd <= 499:
                ours = [i for i in alive if tm[i] == team and body[i]]
                if ours:
                    q = max(ours, key=lambda i: len(body[i])); h = body[q][0]
                    crowd.append(sum(1 for i in ours if i != q and cheb(body[i][0], h) <= 4))
                    occ = {c for i in alive for c in body[i]}
                    nb = [((h[0] + dx) % W, (h[1] + dy) % H) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
                    free.append(sum(1 for c in nb if c not in occ))
                    if last is not None and last[0] == q and last[1] != h: moves += 1
                    last = (q, h)
        elif k == "dragonUpdate":
            i = e["id"]; b = body.get(i)
            if b is None or e["head"] is None: continue
            if b[0] != e["head"]: b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]: b.pop()
        elif k == "dragonSplit":
            tm[e["child"]] = e["team"]; body[e["child"]] = e["childBody"]; body[e["parent"]] = e["parentBody"]; alive.add(e["child"])
        elif k == "dragonDeath":
            alive.discard(e["id"])
    avg = lambda v: sum(v) / len(v) if v else float("nan")
    return avg(crowd), avg(free), moves, len(crowd)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=20); a = ap.parse_args()
    idx = json.load(open(ROOT / "ladder" / "slope" / "index.json", encoding="utf-8"))
    top = [r for r in idx if r["map"] in OPEN and r["rank"] <= 5 and r["winner"] == r["side"]
           and (ROOT / r["path"].replace("\\", "/")).exists()]
    random.Random(2).shuffle(top)
    res = {"top wins": [], "our losses": []}
    for r in top[:a.n]:
        res["top wins"].append(traffic(str(ROOT / r["path"].replace("\\", "/")), 0 if r["side"] == "A" else 1))
    ours = []
    for f in sorted(glob.glob(str(ROOT / "ladder" / "losses" / "*" / "*.replay")), key=os.path.getmtime, reverse=True):
        try:
            rep = _decode(f)
        except Exception:
            continue
        name = next((l.split(" ", 1)[1] for l in rep["map"].splitlines() if l.startswith("MAP_NAME")), "")
        if name not in OPEN: continue
        side = 0 if rep["botA"] and not rep["botB"] else 1 if rep["botB"] and not rep["botA"] else None
        if side is None or rep.get("result", {}).get("winner") == side: continue
        res["our losses"].append(traffic(f, side))
        if len(res["our losses"]) >= a.n: break
    for k, v in res.items():
        v = [x for x in v if x[3] > 0]
        if not v: print(k, "no data"); continue
        m = lambda j: sum(x[j] for x in v) / len(v)
        print(f"{k:10s} n={len(v)}  allied heads within 4 of the longest: {m(0):.1f}   free cells at its head: {m(1):.2f}"
              f"   head moves r400-499: {m(2):.0f}")


if __name__ == "__main__":
    main()
