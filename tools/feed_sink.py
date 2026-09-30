"""Where do our late feed pearls go? For each replay: our feeds (no valid action) from --from, the pearls they drop,
how many different dragons of ours ate them, and the share eaten by our final longest dragon.

    python tools/feed_sink.py DIR_OR_GLOB [--from 350]
"""
import argparse, collections, glob, pathlib, re, statistics as st, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402
DXY = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}

def one(path, r0, flip=False):
    rep = _decode(str(path))
    m = re.search(r"_([AB])_\d+\.replay$", str(path))
    ours = (0 if m.group(1) == "A" else 1) if m else (0 if rep["botA"] and not rep["botB"] else 1)
    if flip: ours = 1 - ours   # analyse the opponent
    L = rep["map"].splitlines(); W, H = map(int, L[0].split()[1:3]); tm = {}; body = {}; nid = 0
    for l in L:
        q = l.split()
        if q and q[0] == "DRAGON":
            n = int(q[2]); c = [int(v) for v in q[3:3 + 2 * n]]; tm[nid] = int(q[1]); body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    pearls = set(); feed = {}; eater = collections.Counter(); rnd = 0; alive = set(tm); dropped = 0
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart": rnd = e["round"]
        elif k == "tileChange":
            t = tuple(e["tile"]); (pearls.add if e.get("pearl") else pearls.discard)(t)
        elif k == "dragonSplit":
            tm[e["child"]] = e["team"]; body[e["child"]] = [tuple(x) for x in e["childBody"]]
            body[e["parent"]] = [tuple(x) for x in e["parentBody"]]; alive.add(e["child"])
        elif k == "dragonAction" and e.get("act") == "move" and e["id"] in body and body[e["id"]] and tm.get(e["id"]) == ours:
            x, y = body[e["id"]][0]
            for ch in e.get("dirs", ""):
                dx, dy = DXY.get(ch, (0, 0)); x, y = (x + dx) % W, (y + dy) % H
                if (x, y) in pearls and (x, y) in feed: eater[e["id"]] += 1; feed.pop((x, y))
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]; hd = tuple(e["head"])
            if b[0] != hd: b.insert(0, hd)
            tl = tuple(e["tail"]) if e.get("tail") else None
            while len(b) > 1 and tl is not None and b[-1] != tl: b.pop()
        elif k == "dragonDeath":
            i = e["id"]; alive.discard(i)
            cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
            if tm.get(i) == ours and cause == "no valid action" and rnd >= r0:
                cells = (body.get(i) or [])[0::2]; dropped += len(cells)
                for cc in cells: feed[cc] = rnd
    fin = sorted(((len(body[i]), i) for i in alive if tm[i] == ours), reverse=True)
    top = fin[0][1] if fin else None
    eaten = sum(eater.values())
    return dict(dropped=dropped, eaten=eaten, eaters=len(eater), top_share=(eater.get(top, 0) / eaten) if eaten else None,
                final_longest=fin[0][0] if fin else 0)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("--from", dest="r0", type=int, default=350)
    ap.add_argument("--opponent", action="store_true", help="measure the other side")
    a = ap.parse_args(); p = pathlib.Path(a.src)
    files = sorted(p.glob("*.replay")) if p.is_dir() else sorted(glob.glob(a.src))
    rs = [one(f, a.r0, a.opponent) for f in files]
    rs = [r for r in rs if r["dropped"]]
    if not rs: print("no late feeds"); return
    sh = [r["top_share"] for r in rs if r["top_share"] is not None]
    print(f"{len(rs)} games with late feeds: dropped/game {st.mean(r['dropped'] for r in rs):.0f}, eaten by us {st.mean(r['eaten'] for r in rs):.0f},"
          f" distinct eaters (median) {st.median(r['eaters'] for r in rs)}, share eaten by our final longest (median) {100 * st.median(sh):.0f}%"
          f" (mean {100 * st.mean(sh):.0f}%), final longest (median) {st.median(r['final_longest'] for r in rs)}")

if __name__ == "__main__":
    main()
