"""Summarise replays: team sizes over time, and every death of the chosen team with context.

    python tools/ladder_report.py ladder/*.replay --ours 7541
"""
import argparse
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from replay import load, DEATHS  # noqa: E402
CTX = 3


def analyse(path, ours):
    rep = load(path)
    lines = rep["map"].splitlines()
    name = next((l.split(" ", 1)[1] for l in lines if l.startswith("MAP_NAME")), lines[0])
    our_team = 0 if rep["botA"] == ours else 1 if rep["botB"] == ours else None
    team, body = {}, {}
    nid = 0
    for l in lines:
        p = l.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t
            body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]
            nid += 1
    rnd = 0
    last_ind = {}
    timeline = []
    deaths = []
    alive = set(team)

    def snapshot():
        out = []
        for t in (0, 1):
            ls = [len(body[i]) for i in alive if team[i] == t]
            out.append((len(ls), max(ls) if ls else 0, sum(ls)))
        return out

    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd % 50 == 0:
                timeline.append((rnd, snapshot()))
        elif k == "dragonIndicator":
            last_ind.setdefault(e["id"], []).append((rnd, e["text"]))
        elif k == "dragonUpdate":
            i = e["id"]
            b = body.get(i)
            if b is None or e["head"] is None:
                continue
            if b[0] != e["head"]:
                b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]:
                b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            body[e["child"]] = e["childBody"]
            body[e["parent"]] = e["parentBody"]
            alive.add(e["child"])
        elif k == "dragonDeath":
            i = e["id"]
            alive.discard(i)
            deaths.append((rnd, i, team.get(i), len(body.get(i, [])), DEATHS[e["reason"]] if e["reason"] < 5 else e["reason"],
                           last_ind.get(i, [])[-CTX:]))
    res = rep.get("result", {})
    return name, our_team, res, timeline, deaths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--ours", required=True, help="our submission id / bot label in the replay")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    for path in args.paths:
        name, ot, res, timeline, deaths = analyse(path, args.ours)
        us = "AB"[ot] if ot is not None else "?"
        won = res.get("winner")
        verdict = "WIN" if won is not None and won == ot else "LOSS" if won is not None else "DRAW"
        print(f"=== {path}  {name}  we are {us}: {verdict}  final A={res.get('A')} B={res.get('B')}")
        print("   round: (count, longest, total) ours | theirs")
        for r, snap in timeline:
            print(f"   {r:3d}: {snap[ot]} | {snap[1 - ot]}")
        if args.quiet:
            continue
        for r, i, t, ln, why, ind in deaths:
            side = "US  " if t == ot else "them"
            print(f"   r{r:3d} {side} #{i:<3d} len {ln:3d} {why:16s} {' || '.join(f'r{a}:{b[:70]}' for a, b in ind) if t == ot else ''}")


if __name__ == "__main__":
    main()
