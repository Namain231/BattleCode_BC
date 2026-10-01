"""How does a team's longest dragon grow over the game? Used to compare top teams' consolidation
against our own (S4.7 loses the round-500 length tiebreak on some maps despite leading on units).

    python tools/queen_growth.py <replay.replay> <side: A|B>
"""
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from replay import load  # noqa: E402

CHECK = (100, 200, 300, 400, 500)


def analyse(path, side_letter):
    side = 0 if side_letter == "A" else 1
    rep = load(path)
    team, body, nid = {}, {}, 0
    for l in rep["map"].splitlines():
        p = l.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t; body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    alive = set(team)
    rnd = 0
    out = {}
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd in CHECK:
                ls = [len(body[i]) for i in alive if team[i] == side]
                out[rnd] = (len(ls), max(ls or [0]), sum(ls))
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]
            if b[0] != e["head"]:
                b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]:
                b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            body[e["child"]] = e["childBody"]; body[e["parent"]] = e["parentBody"]; alive.add(e["child"])
        elif k == "dragonDeath":
            alive.discard(e["id"])
    ls = [len(body[i]) for i in alive if team[i] == side]
    out["end"] = (len(ls), max(ls or [0]), sum(ls))
    return out


if __name__ == "__main__":
    r = analyse(sys.argv[1], sys.argv[2])
    for k in list(CHECK) + ["end"]:
        if k in r:
            print(f"r{k}: units={r[k][0]} longest={r[k][1]} total={r[k][2]}")
