"""Deeper look at our ladder games (output of tools/analyze_ours.py): why did we lose?

    uv run --python 3.11 --with unswbc python tools/analyze_losses.py ladder/sv52

Per game: unit counts (ours/theirs) at r50/100/200/300/400, final result counts, queen deaths (correct team mapping), then classifies
each LOSS: behind-early (<= 0.8x their units at r100), late-collapse (units >= theirs at r200 but ~0 at the end), queen-race (their queen alive at
the end, ours dead), eliminated (our count 0), other. Aggregates by opponent and map, win rate by situation at r100/r200.
"""
import collections, json, os, sys, statistics as st
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from replay_lite import decode_lite  # noqa: E402

D = ["wall", "self", "body", "headon", "noaction"]
out = Path(sys.argv[1]); games = [g for g in json.load(open(out / "games.json", encoding="utf-8")) if "our_queen_death" in g]
rows = []
for g in games:
    rep = decode_lite(str(out / f"{g['game']}.replay"), {"roundStart", "dragonDeath", "dragonSplit"})
    dl = [l.split() for l in rep["map"].splitlines() if l.split()[:1] == ["DRAGON"]]
    owner = {i: int(d[1]) for i, d in enumerate(dl)}; me = g["me"]
    alive = collections.Counter(owner.values()); snap = {}; rnd = -1; feed = 0
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            if rnd in (50, 100, 200, 300, 400):
                snap[rnd] = (alive[me], alive[1 - me])
            rnd = e["round"]
        elif k == "dragonSplit":
            owner[e["child"]] = e["team"]; alive[e["team"]] += 1
        elif k == "dragonDeath":
            t = owner.get(e["id"])
            if t is not None:
                alive[t] -= 1
                if t == me and e["reason"] == 4 and rnd >= 280:
                    feed += 1
    res = rep["result"]; ours = res.get("AB"[me]) or {}; theirs = res.get("AB"[1 - me]) or {}
    rows.append(dict(g, snap=snap, ours_res=ours, theirs_res=theirs, feed=feed))


def cls(r):
    if r["win"]:
        return "win"
    s = r["snap"]
    o100, t100 = s.get(100, (0, 0)); o200, t200 = s.get(200, (0, 0))
    end_o = r["ours_res"].get("count", 0); end_t = r["theirs_res"].get("count", 0)
    if t100 and o100 <= 0.8 * t100:
        return "behind-early (<=0.8x units at r100)"
    if end_o == 0:
        return "eliminated"
    if o200 >= t200 and r["our_queen_death"] and not r["enemy_queen_death"]:
        return "queen-race (even swarm, our queen died, theirs alive)"
    if o200 >= t200:
        return "late-collapse/other (even swarm at r200)"
    return "behind-mid (fewer units at r200)"


print(f"{len(rows)} games, W {sum(r['win'] for r in rows)}")
print("\nLOSS classes:", dict(collections.Counter(cls(r) for r in rows if not r["win"])))
for tag, f in (("units at r100 ours>=theirs", lambda r: r["snap"].get(100, (0, 0))[0] >= r["snap"].get(100, (0, 0))[1]),
               ("units at r200 ours>=theirs", lambda r: r["snap"].get(200, (0, 0))[0] >= r["snap"].get(200, (0, 0))[1]),
               ("our queen alive at end", lambda r: not r["our_queen_death"]),
               ("their queen dead", lambda r: bool(r["enemy_queen_death"]))):
    a = [r for r in rows if f(r)]; b = [r for r in rows if not f(r)]
    print(f"  {tag}: win% {100*sum(r['win'] for r in a)/max(1,len(a)):.0f} (n={len(a)}) vs {100*sum(r['win'] for r in b)/max(1,len(b)):.0f} (n={len(b)})")
by = collections.defaultdict(lambda: [0, 0, 0])
for r in rows:
    by[r["opp"]][0] += r["win"]; by[r["opp"]][1] += 1; by[r["opp"]][2] = r["oppElo"]
print("\nby opponent (W/N, elo):", {o.encode('ascii', 'replace').decode(): f"{a}/{b} {e}" for o, (a, b, e) in sorted(by.items(), key=lambda kv: -kv[1][2])})
bm = collections.defaultdict(list)
for r in rows:
    bm[r["map"]].append(r)
print("\nmap | n | W | our queen died (median r) | our units r100/r200/r300 avg | their units r100/r200/r300 avg")
for m, s in sorted(bm.items(), key=lambda kv: sum(r["win"] for r in kv[1]) / len(kv[1])):
    qd = [r["our_queen_death"][0] for r in s if r["our_queen_death"]]
    av = lambda i, side: sum(r["snap"].get(i, (0, 0))[side] for r in s) / len(s)
    print(f"{m} | {len(s)} | {sum(r['win'] for r in s)} | {len(qd)}/{len(s)} ({int(st.median(qd)) if qd else '-'}) | {av(100,0):.0f}/{av(200,0):.0f}/{av(300,0):.0f} | {av(100,1):.0f}/{av(200,1):.0f}/{av(300,1):.0f}")
lost = collections.Counter()
for r in rows:
    for k, v in r["lost"].items():
        lost[k] += v
print("\nour dragons lost per game by cause:", {k: round(v / len(rows)) for k, v in lost.items()})
print("late feed suicides (noaction after r280) per game:", round(sum(r["feed"] for r in rows) / len(rows), 1))
q = [r["our_queen_death"] for r in rows if r["our_queen_death"]]
print(f"our queen died {len(q)}/{len(rows)}; median r {st.median([x[0] for x in q]) if q else '-'}; causes {dict(collections.Counter(x[1] for x in q))}; early (<=20): {sum(x[0] <= 20 for x in q)}")
print("games with our queen alive: win%", round(100 * sum(r['win'] for r in rows if not r['our_queen_death']) / max(1, sum(1 for r in rows if not r['our_queen_death']))), "| dead:", round(100 * sum(r['win'] for r in rows if r['our_queen_death']) / max(1, sum(1 for r in rows if r['our_queen_death']))))
