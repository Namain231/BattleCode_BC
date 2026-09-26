"""Early-game economy of one side of a replay: pearls eaten per dragon-turn, splits, deaths.

Used to compare how fast teams expand in the first N rounds.
"""
import collections
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from replay import load, DEATHS  # noqa: E402


def early(path, side, until=100):
    rep = load(path)
    lines = rep["map"].splitlines()
    team, body, nid = {}, {}, 0
    for l in lines:
        p = l.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t; body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    alive = set(team)
    rnd = 0
    out = collections.Counter()
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd >= until:
                break
            out["dragon_turns"] += sum(1 for i in alive if team[i] == side)
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]
            before = len(b)
            moved = b[0] != e["head"]
            if moved:
                b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]:
                b.pop()
            if team.get(e["id"]) == side and moved and len(b) > before:
                out["eats"] += len(b) - before
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            body[e["child"]] = e["childBody"]; body[e["parent"]] = e["parentBody"]; alive.add(e["child"])
            if e["team"] == side:
                out["splits"] += 1
        elif k == "dragonDeath":
            if team.get(e["id"]) == side:
                out["deaths"] += 1
                out["death_" + DEATHS[e["reason"]]] += 1
            alive.discard(e["id"])
        elif k == "dragonAction" and team.get(e["id"]) == side and e.get("act") == "move" and len(e.get("dirs", "")) > 1:
            out["sprints"] += 1
    out["units_end"] = sum(1 for i in alive if team[i] == side)
    return out
