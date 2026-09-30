"""Where does the final giant's growth come from (r300-499)? For the team's longest dragon at the end: its growth,
own-team "no valid action" deaths (feeds) within Chebyshev 3 of its head at that moment, and the pearls they drop
(ceil(L/2)). Top-team open-map wins vs our open-map losses.

    python tools/feed_delivery.py --n 20
"""
import argparse, glob, json, os, pathlib, random, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402
ROOT = pathlib.Path(__file__).resolve().parents[1]
OPEN = {"Portals", "Slithery Fight", "Schooltime"}


def delivery(path, team):
    rep = _decode(path)
    tm, body, nid = {}, {}, 0
    W = H = 0
    for l in rep["map"].splitlines():
        p = l.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            tm[nid] = t; body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    events = rep["events"]
    for e in events:  # map size from coordinates
        if e["kind"] == "dragonUpdate" and e["head"]:
            W = max(W, e["head"][0] + 1); H = max(H, e["head"][1] + 1)
    alive = set(tm); rnd = 0; log = []; len300 = {}
    def cheb(a, b):
        dx = abs(a[0] - b[0]); dy = abs(a[1] - b[1])
        return max(min(dx, W - dx), min(dy, H - dy))
    for e in events:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd == 300: len300 = {i: len(body[i]) for i in alive if tm[i] == team}
        elif k == "dragonUpdate":
            i = e["id"]; b = body.get(i)
            if b is None or e["head"] is None: continue
            if b[0] != e["head"]: b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]: b.pop()
        elif k == "dragonSplit":
            tm[e["child"]] = e["team"]; body[e["child"]] = e["childBody"]; body[e["parent"]] = e["parentBody"]; alive.add(e["child"])
        elif k == "dragonDeath":
            i = e["id"]; alive.discard(i)
            if rnd >= 300 and tm.get(i) == team and e["reason"] < 5 and DEATHS[e["reason"]] == "no valid action" and body.get(i):
                log.append((rnd, body[i][0], len(body[i]), {j: body[j][0] for j in alive if tm[j] == team and body[j]}))
    ours = [i for i in alive if tm[i] == team and body[i]]
    if not ours: return None
    g = max(ours, key=lambda i: len(body[i]))
    growth = len(body[g]) - len300.get(g, 2)
    feeds = len(log); near = [x for x in log if g in x[3] and cheb(x[1], x[3][g]) <= 3]
    pearls_near = sum((x[2] + 1) // 2 for x in near); pearls_all = sum((x[2] + 1) // 2 for x in log)
    return dict(final=len(body[g]), growth=growth, feeds=feeds, near=len(near), pearls_all=pearls_all, pearls_near=pearls_near)


def summarize(name, rows):
    rows = [r for r in rows if r]
    if not rows: print(name, "no data"); return
    m = lambda k: sum(r[k] for r in rows) / len(rows)
    print(f"{name:11s} n={len(rows)} final longest {m('final'):.0f}, its growth r300+ {m('growth'):.0f}; feeds r300+ {m('feeds'):.0f} "
          f"(pearls {m('pearls_all'):.0f}); feeds within 3 of the final giant {m('near'):.0f} (pearls {m('pearls_near'):.0f})")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=20); a = ap.parse_args()
    idx = json.load(open(ROOT / "ladder" / "slope" / "index.json", encoding="utf-8"))
    top = [r for r in idx if r["map"] in OPEN and r["rank"] <= 5 and r["winner"] == r["side"]
           and (ROOT / r["path"].replace("\\", "/")).exists()]
    random.Random(3).shuffle(top)
    summarize("top wins", [delivery(str(ROOT / r["path"].replace("\\", "/")), 0 if r["side"] == "A" else 1) for r in top[:a.n]])
    ours = []
    for f in sorted(glob.glob(str(ROOT / "ladder" / "losses" / "*" / "*.replay")), key=os.path.getmtime, reverse=True):
        try: rep = _decode(f)
        except Exception: continue
        name = next((l.split(" ", 1)[1] for l in rep["map"].splitlines() if l.startswith("MAP_NAME")), "")
        if name not in OPEN: continue
        side = 0 if rep["botA"] and not rep["botB"] else 1 if rep["botB"] and not rep["botA"] else None
        if side is None or rep.get("result", {}).get("winner") == side: continue
        ours.append(delivery(f, side))
        if len(ours) >= a.n: break
    summarize("our losses", ours)


if __name__ == "__main__":
    main()
