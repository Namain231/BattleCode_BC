"""Round-by-round comparison of two replays of the SAME game setup (map, seed, side): e.g. champion vs candidate.

    python tools/pair_diff.py BASE.replay CAND.replay [--side A|B] [--every 10] [--to 500]

Per window: for each build, our units/mass/longest and theirs, our deaths by cause, their deaths, our splits, feeds
(SPLIT 1 / suicide), head-ons we caused vs suffered. Marks the first window where our units differ by >= 3 or mass by
>= 10 ("DIVERGE"), and windows where one build's trajectory turns (units drop >= 25% in a window).
"""
import argparse
import collections
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402

SHORT = {"head to head": "h2h", "hit a wall": "wall", "hit wall": "wall", "hit itself": "self", "hit self": "self",
         "hit another dragon": "body", "hit other body": "body", "no valid action": "nva"}


def trace(path, ours, every, to):
    rep = _decode(str(path))
    team, body = {}, {}
    nid = 0
    for l in rep["map"].splitlines():
        p = l.split()
        if p and p[0] == "DRAGON":
            n = int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = int(p[1]); body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    alive = set(team); rnd = 0; last = {}
    queen_ours = min(i for i in team if team[i] == ours)        # first dragon of each team in map order
    queen_theirs = min(i for i in team if team[i] != ours)
    queen_death = {}
    W = {}   # window start -> stats
    def win(r): return W.setdefault(r // every * every, {"od": collections.Counter(), "td": collections.Counter(),
                                                         "osp": 0, "tsp": 0, "ofeed": 0, "tfeed": 0,
                                                         "tags": collections.Counter()})
    snaps = {}
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd > to: break
            if rnd % every == 0:
                o = [len(body[i]) for i in alive if team[i] == ours]; t = [len(body[i]) for i in alive if team[i] != ours]
                qo = len(body[queen_ours]) if queen_ours in alive else 0
                qt = len(body[queen_theirs]) if queen_theirs in alive else 0
                snaps[rnd] = (len(o), sum(o), max(o, default=0), len(t), sum(t), max(t, default=0), qo, qt)
        elif k == "dragonAction":
            last[e["id"]] = e
        elif k == "dragonIndicator" and team.get(e["id"]) == ours and e.get("text"):
            tag = e["text"].split()[0]
            tag = re.sub(r"\d.*$", "", tag) or tag   # "L7 ..." -> "L" (ordinary move); "ATK" stays
            win(rnd)["tags"][tag] += 1
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]; hd = tuple(e["head"])
            if b[0] != hd: b.insert(0, hd)
            tl = tuple(e["tail"]) if e.get("tail") else None
            while len(b) > 1 and tl is not None and b[-1] != tl: b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]; body[e["child"]] = [tuple(x) for x in e["childBody"]]
            body[e["parent"]] = [tuple(x) for x in e["parentBody"]]; alive.add(e["child"])
            w = win(rnd); w["osp" if e["team"] == ours else "tsp"] += 1
        elif k == "dragonDeath":
            i = e["id"]; alive.discard(i)
            cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
            if i == queen_ours or i == queen_theirs:
                queen_death[i] = (rnd, cause)
            a = last.get(i, {})
            feed = cause == "no valid action" and (a.get("act") == "suicide" or (a.get("act") == "split" and a.get("size") == 1))
            w = win(rnd); side = "o" if team.get(i) == ours else "t"
            if feed: w[side + "feed"] += 1
            else: w[side + "d"][SHORT.get(cause, cause)] += 1
    return snaps, W, rep.get("result", {}), queen_death, queen_ours, queen_theirs


def fmt_d(c):
    return " ".join(f"{k}{v}" for k, v in sorted(c.items(), key=lambda kv: -kv[1])) or "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base"); ap.add_argument("cand")
    ap.add_argument("--side", default=""); ap.add_argument("--every", type=int, default=10); ap.add_argument("--to", type=int, default=500)
    ap.add_argument("--tags", action="store_true", help="also tally our dragons' decision tags (indicator first word) per window")
    a = ap.parse_args()
    m = re.search(r"_([AB])_\d+\.replay$", a.base)
    side = a.side or (m.group(1) if m else "A"); ours = 0 if side == "A" else 1
    sb, wb, rb, qdb, qob, qtb = trace(a.base, ours, a.every, a.to)
    sc, wc, rc, qdc, qoc, qtc = trace(a.cand, ours, a.every, a.to)
    def res(r):
        me, th = (r.get("A", {}), r.get("B", {})) if ours == 0 else (r.get("B", {}), r.get("A", {}))
        return f"{'WIN' if r.get('winner') == ours else 'LOSS'} ({'elim' if r.get('endReason') == 0 else 'length'}) end ours {me.get('count')}/{me.get('total')}/L{me.get('longest')} v {th.get('count')}/{th.get('total')}/L{th.get('longest')}"
    def qinfo(qd, qo, qt):
        parts = []
        for qid, label in ((qo, "ours"), (qt, "theirs")):
            if qid in qd:
                r, cause = qd[qid]
                parts.append(f"{label} died r{r} {cause}")
            else:
                parts.append(f"{label} alive")
        return ", ".join(parts)
    print(f"BASE {res(rb)} | queen: {qinfo(qdb, qob, qtb)}")
    print(f"CAND {res(rc)} | queen: {qinfo(qdc, qoc, qtc)}")
    print(f"(per window: units/mass/longest ours v theirs | Q ours/theirs | our deaths | their deaths | splits ours/theirs | feeds)")
    diverged = False
    for r in sorted(set(sb) | set(sc)):
        flag = ""
        b, c = sb.get(r), sc.get(r)
        if b and c and not diverged and (abs(b[0] - c[0]) >= 3 or abs(b[1] - c[1]) >= 10):
            flag = "  <== DIVERGE"; diverged = True
        for tag, s, w in (("base", b, wb.get(r)), ("cand", c, wc.get(r))):
            if not s: continue
            w = w or {"od": {}, "td": {}, "osp": 0, "tsp": 0, "ofeed": 0, "tfeed": 0, "tags": {}}
            print(f"r{r:3d} {tag} {s[0]:2d}/{s[1]:3d}/L{s[2]:<2d} v {s[3]:2d}/{s[4]:3d}/L{s[5]:<2d} | Q {s[6]}/{s[7]} | our {fmt_d(w['od']):24s} | their {fmt_d(w['td']):18s}"
                  f" | sp {w['osp']}/{w['tsp']} | feed {w['ofeed']}/{w['tfeed']}{flag if tag == 'cand' else ''}")
            if a.tags:
                t = {k: v for k, v in w["tags"].items() if k != "L"}
                print(f"         {tag} tags: " + " ".join(f"{k}{v}" for k, v in sorted(t.items(), key=lambda kv: -kv[1])[:8]))


if __name__ == "__main__":
    main()
