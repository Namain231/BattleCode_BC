"""Does our queen gossip reach the swarm? Reconstructed from replays (every ray's payload + who it hit).

Decodes the champion's queen records (top 16 bits 0xB0C7: x, y, len, round, id) delivered to our own
dragons, and at checkpoints from r260 reports, over our non-queen dragons:
  fresh%    received a queen record within the last 25 rounds (tryFeed / feeding require <= 25)
  right%    the freshest record names the TRUE current longest dragon
  lenerr    median (true queen length - length in that record)
  none%     never received any queen record yet

    uv run --python 3.11 python tools/gossip_coverage.py ladder/q250c_prof [--from 260]
"""
import argparse, collections, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import load  # noqa: E402

QMAGIC = 0xB0C7
FRESH = 25


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--from", dest="start", type=int, default=260)
    a = ap.parse_args()
    agg = collections.defaultdict(collections.Counter)
    lens = collections.defaultdict(list)
    for dd in a.dirs:
        root = pathlib.Path(dd)
        idx = {(str(e["teamId"]), str(e["game"])): e for e in json.load(open(root / "index.json", encoding="utf-8"))}
        for f in sorted(root.rglob("*.replay")):
            m = idx.get((f.parent.name, f.stem))
            if not m:
                continue
            side = 0 if m["side"] in ("A", 0) else 1
            rep = load(f)
            w = int(next(l for l in rep["map"].splitlines() if l.startswith("MAP ")).split()[1])
            team, body, nid = {}, {}, 0
            for l in rep["map"].splitlines():
                p = l.split()
                if p and p[0] == "DRAGON":
                    t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
                    team[nid] = t; body[nid] = [c[2 * i + 1] * w + c[2 * i] for i in range(n)]; nid += 1
            alive = set(team); last = {}; rnd = 0; A = agg[m["team"]]
            for e in rep["events"]:
                k = e["kind"]
                if k == "roundStart":
                    rnd = e["round"]
                    if rnd >= a.start and rnd % 20 == 0:
                        own = [d for d in alive if team.get(d) == side]
                        if len(own) < 2:
                            continue
                        q = max(own, key=lambda d: (len(body[d]), -d))
                        for d in own:
                            if d == q:
                                continue
                            A["n"] += 1
                            if d not in last:
                                A["none"] += 1; continue
                            r0, qid, qlen = last[d]
                            if rnd - r0 <= FRESH:
                                A["fresh"] += 1
                                if qid == q:
                                    A["right"] += 1
                                    lens[m["team"]].append(len(body[q]) - qlen)
                elif k == "dragonSplit":
                    team[e["child"]] = e["team"]; alive.add(e["child"])
                    body[e["parent"]] = [q[1] * w + q[0] for q in e["parentBody"]]
                    body[e["child"]] = [q[1] * w + q[0] for q in e["childBody"]]
                elif k == "dragonUpdate" and e["head"] and e["id"] in body:
                    b = body[e["id"]]
                    hd = e["head"][1] * w + e["head"][0]
                    tl = e["tail"][1] * w + e["tail"][0] if e["tail"] else None
                    if b[0] != hd:
                        b.insert(0, hd)
                    if tl is not None:
                        while len(b) > 1 and b[-1] != tl:
                            b.pop()
                elif k == "dragonDeath":
                    alive.discard(e["id"])
                elif k == "sonarPing":
                    v, hit = e["value"], e["hit"]
                    if hit is None or team.get(hit) != side or team.get(e["sender"]) != side:
                        continue
                    if (v >> 48) != QMAGIC:
                        continue
                    last[hit] = (rnd, v & 4095, (v >> 24) & 4095)
    for t, A in agg.items():
        n = A["n"] or 1
        L = sorted(lens[t])
        med = L[len(L) // 2] if L else float("nan")
        print(f"{t:14s} samples={A['n']:6d} fresh%={100*A['fresh']/n:5.1f} right%={100*A['right']/n:5.1f} "
              f"none%={100*A['none']/n:5.1f} median lenerr={med}")


if __name__ == "__main__":
    main()
