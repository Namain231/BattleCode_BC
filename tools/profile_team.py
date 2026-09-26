"""Behaviour profile of one team across replays: macro timeline, splits, sprints, deaths, debug text.

    python tools/profile_team.py ladder/top/*.replay --label 4961 --label 6800 --label 7701
(--label is the submission id / bot label as it appears in the replay header.)
"""
import argparse
import collections
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from replay import load, DEATHS  # noqa: E402


def profile(path, labels):
    rep = load(path)
    lines = rep["map"].splitlines()
    name = next((l.split(" ", 1)[1] for l in lines if l.startswith("MAP_NAME")), lines[0])
    side = labels if isinstance(labels, int) else (0 if rep["botA"] in labels else 1 if rep["botB"] in labels else None)
    if side is None:
        return None
    team, body, nid = {}, {}, 0
    for l in lines:
        p = l.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t; body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    alive = set(team)
    rnd = 0
    out = {"map": name, "splits": [], "sprints": collections.Counter(), "moves": 0, "suicide": 0,
           "deaths": collections.Counter(), "kills_h2h": 0, "timeline": [], "texts": collections.Counter(),
           "first_actions": []}
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd % 50 == 0:
                snap = []
                for t in (0, 1):
                    ls = [len(body[i]) for i in alive if team[i] == t]
                    snap.append((len(ls), max(ls) if ls else 0, sum(ls)))
                out["timeline"].append((rnd, snap[side], snap[1 - side]))
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]
            if b[0] != e["head"]: b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]: b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            if e["team"] == side:
                out["splits"].append((rnd, len(e["parentBody"]) + len(e["childBody"]), len(e["childBody"])))
            body[e["child"]] = e["childBody"]; body[e["parent"]] = e["parentBody"]; alive.add(e["child"])
        elif k == "dragonDeath":
            i = e["id"]; alive.discard(i)
            if team.get(i) == side:
                out["deaths"][DEATHS[e["reason"]]] += 1
            elif e["reason"] == 3:
                out["kills_h2h"] += 1
        elif k == "dragonAction" and team.get(e["id"]) == side:
            if e.get("act") == "move":
                out["moves"] += 1
                n = len(e.get("dirs", ""))
                if n > 1: out["sprints"][n] += 1
            elif e.get("act") == "suicide":
                out["suicide"] += 1
            if rnd < 3:
                out["first_actions"].append((rnd, e["id"], e.get("act"), e.get("dirs") or e.get("size")))
        elif k in ("dragonIndicator", "dragonLog") and team.get(e["id"]) == side:
            out["texts"][e["text"][:60]] += 1
    out["result"] = rep.get("result")
    out["side"] = side
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--label", action="append", default=[])
    ap.add_argument("--side", choices=["A", "B"], help="profile this side instead of matching a label")
    ap.add_argument("--texts", type=int, default=5)
    a = ap.parse_args()
    for p in a.paths:
        o = profile(p, "AB".index(a.side) if a.side else set(a.label))
        if o is None:
            continue
        res = o["result"]; us = res["AB"[o["side"]]]; them = res["AB"[1 - o["side"]]]
        won = res.get("winner") == o["side"]
        print(f"=== {p} {o['map']}: {'WIN' if won else 'LOSS'} end={res['endReason']}  them={us}  opp={them}")
        print("   round: (count, longest, total) profiled | opponent")
        for r, a1, b1 in o["timeline"][::2]:
            print(f"   {r:3d}: {a1} | {b1}")
        sp = o["splits"]
        if sp:
            print(f"   splits: {len(sp)}; first rounds {[s[0] for s in sp[:8]]}; parent len at split (median) "
                  f"{sorted(s[1] for s in sp)[len(sp) // 2]}; child sizes {collections.Counter(s[2] for s in sp).most_common(4)}")
        print(f"   moves {o['moves']} sprints {dict(o['sprints'])} suicides {o['suicide']} deaths {dict(o['deaths'])} "
              f"h2h kills on opponent {o['kills_h2h']}")
        print(f"   opening actions: {o['first_actions'][:10]}")
        if o["texts"]:
            print(f"   debug text samples: {o['texts'].most_common(a.texts)}")


if __name__ == "__main__":
    main()
