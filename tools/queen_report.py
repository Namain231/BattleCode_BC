"""Queen analysis (engine >= 1.2.3 rules: the queen is dragon id 0 for team A, id 1 for team B; at r500 the longer queen
wins, a dead queen counts 0, then longest dragon, then total length).

    python tools/queen_report.py DIR_OR_GLOB [--side-from-name] [--list]

Per game, for OUR queen and THEIR queen: length at r50/100/200/300/400/end, death round and cause (head-on with an ENEMY or
FRIENDLY head, wall, self, other body, feed = no valid action after SPLIT 1/suicide), how many times she split (she keeps
her id when she buds), sprints taken. Aggregate: % of games each queen is alive at the end, death causes by phase, and how
the result was decided (queen / longest / total / elimination).
Our side: from the file name <map>_<A|B>_<seed>.replay (sandbox), else the side whose bot field is set (ladder).
"""
import argparse
import collections
import glob
import pathlib
import re
import statistics as st
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402

CPS = (50, 100, 200, 300, 400)


def our_side(path, rep):
    m = re.search(r"_([AB])_\d+\.replay$", str(path))
    if m: return 0 if m.group(1) == "A" else 1
    a, b = rep.get("botA"), rep.get("botB")
    return 0 if a and not b else 1 if b and not a else 0


def analyse(path):
    rep = _decode(str(path)); ours = our_side(path, rep)
    team, body = {}, {}
    nid = 0
    for l in rep["map"].splitlines():
        p = l.split()
        if p and p[0] == "DRAGON":
            n = int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = int(p[1]); body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    qid = {t: min(i for i in team if team[i] == t) for t in (0, 1)}   # queen = the team's FIRST dragon in map order (ids 0/1; ladder maps may give id 0 to team B)
    q = {t: dict(len={}, death=None, cause=None, splits=0, sprints=0) for t in (0, 1)}
    rnd = 0; last = {}; dead_h2h = []        # (round, id) head-on deaths in order
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd in CPS:
                for t in (0, 1):
                    q[t]["len"][rnd] = len(body.get(qid[t]) or []) if q[t]["death"] is None else 0
        elif k == "dragonAction":
            last[e["id"]] = e
            for t in (0, 1):
                if e["id"] == qid[t] and e.get("act") == "move" and len(e.get("dirs", "")) > 1: q[t]["sprints"] += 1
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]; hd = tuple(e["head"])
            if b[0] != hd: b.insert(0, hd)
            tl = tuple(e["tail"]) if e.get("tail") else None
            while len(b) > 1 and tl is not None and b[-1] != tl: b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]; body[e["child"]] = [tuple(x) for x in e["childBody"]]
            body[e["parent"]] = [tuple(x) for x in e["parentBody"]]
            for t in (0, 1):
                if e["parent"] == qid[t]: q[t]["splits"] += 1
        elif k == "dragonDeath":
            i = e["id"]
            cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
            a = last.get(i, {})
            if cause == "no valid action" and (a.get("act") == "suicide" or (a.get("act") == "split" and a.get("size") == 1)):
                cause = "feed"
            if cause == "head to head": dead_h2h.append((rnd, i))
            for t in (0, 1):
                if i == qid[t] and q[t]["death"] is None:
                    q[t]["death"] = rnd; q[t]["cause"] = cause; q[t]["len_at_death"] = len(body.get(i) or [])
    # head-on partner of a queen: the other death logged in the same round next to it
    for t in (0, 1):
        if q[t]["cause"] == "head to head":
            idx = [j for j, (r, i) in enumerate(dead_h2h) if i == qid[t]]
            if idx:
                j = idx[0]; partner = None
                if j + 1 < len(dead_h2h) and dead_h2h[j + 1][0] == q[t]["death"]: partner = dead_h2h[j + 1][1]
                elif j > 0 and dead_h2h[j - 1][0] == q[t]["death"]: partner = dead_h2h[j - 1][1]
                if partner is not None:
                    q[t]["cause"] = "head-on " + ("FRIENDLY" if team.get(partner) == t else "enemy")
    res = rep.get("result", {}); me = res.get("A" if ours == 0 else "B") or {}; th = res.get("B" if ours == 0 else "A") or {}
    won = res.get("winner") == ours
    if res.get("endReason") == 0: how = "elimination"
    elif me.get("queen", 0) != th.get("queen", 0): how = "queen"
    elif me.get("longest") != th.get("longest"): how = "longest"
    else: how = "total"
    return dict(path=str(path), map=next((l.split(" ", 1)[1] for l in rep["map"].splitlines() if l.startswith("MAP_NAME")), "?"),
                won=won, how=how, ours=q[ours], theirs=q[1 - ours], q_end=(me.get("queen"), th.get("queen")))


def phase(r):
    return "-" if r is None else "r0-50" if r < 50 else "r50-150" if r < 150 else "r150-300" if r < 300 else "r300+"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("--list", action="store_true")
    a = ap.parse_args(); p = pathlib.Path(a.src)
    files = sorted(p.rglob("*.replay")) if p.is_dir() else sorted(glob.glob(a.src))
    rows = [analyse(f) for f in files]
    n = len(rows)
    if a.list:
        for r in rows:
            o, t = r["ours"], r["theirs"]
            print(f"{pathlib.Path(r['path']).name:26s} {r['map'][:12]:12s} {'WIN ' if r['won'] else 'LOSS'} by {r['how']:11s} "
                  f"OUR queen end {r['q_end'][0]} died r{o['death']} ({o['cause']}) splits {o['splits']} | "
                  f"THEIR queen end {r['q_end'][1]} died r{t['death']} ({t['cause']})")
    for who in ("ours", "theirs"):
        alive = sum(1 for r in rows if r[who]["death"] is None)
        causes = collections.Counter((phase(r[who]["death"]), r[who]["cause"]) for r in rows if r[who]["death"] is not None)
        deaths = [r[who]["death"] for r in rows if r[who]["death"] is not None]
        print(f"\n{who.upper()} queen: alive at end {alive}/{n}; death round median {st.median(deaths) if deaths else '-'}; "
              f"splits/game {st.mean(r[who]['splits'] for r in rows):.1f}")
        for (ph, c), k in sorted(causes.items(), key=lambda kv: -kv[1])[:8]: print(f"   {ph:9s} {c:18s} {k}")
    print(f"\nresults: wins {sum(r['won'] for r in rows)}/{n}; decided by {dict(collections.Counter(r['how'] for r in rows))}")
    print("our queen alive & won: %d, alive & lost: %d, dead & won: %d, dead & lost: %d" % (
        sum(1 for r in rows if r['ours']['death'] is None and r['won']), sum(1 for r in rows if r['ours']['death'] is None and not r['won']),
        sum(1 for r in rows if r['ours']['death'] is not None and r['won']), sum(1 for r in rows if r['ours']['death'] is not None and not r['won'])))


if __name__ == "__main__":
    main()
