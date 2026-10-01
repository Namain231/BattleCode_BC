"""Friendly head-on analysis: for each replay, count OUR head-on deaths and classify each MOVER's death step
as crossing a PORTAL edge, an OPEN edge, or other. Pair victims (a head-on kills two dragons in the same round).

    python tools/friendly_h2h.py REPLAY [REPLAY ...]

Our side: from the file name <map>_<A|B>_<seed>.replay (sandbox), else the side whose bot field is set (ladder).
Edge indexing (docs/map-files.md): rows of horizontal edges (a tile row's north side) alternate with rows of
vertical edges (its west side). Each row is width + 1 long, so the index runs to (2*height + 1) * (width + 1).
For a tile at (x, y):
  - North edge: row 2y, index 2y*(W+1) + x
  - South edge: row 2(y+1), index 2(y+1)*(W+1) + x
  - West edge: row 2y+1, index (2y+1)*(W+1) + x
  - East edge: row 2y+1, index (2y+1)*(W+1) + x + 1
"""
import collections
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402

DXY = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}


def our_side(path, rep):
    m = re.search(r"_([AB])_\d+\.replay$", str(path))
    if m:
        return 0 if m.group(1) == "A" else 1
    a, b = rep.get("botA"), rep.get("botB")
    return 0 if a and not b else 1 if b and not a else 0


def analyse(path):
    rep = _decode(str(path))
    L = rep["map"].splitlines()
    W, H = map(int, L[0].split()[1:3])
    kind = {}
    for l in L:
        p = l.split()
        if p and p[0] == "EDGE" and len(p) >= 3:
            kind[int(p[1])] = int(p[2])

    def edge(x, y, d):
        """Edge kind (0=open, 1=kelp, 2=portal) for the edge of tile (x, y) in direction d."""
        if d == "N":
            return kind.get((2 * y) * (W + 1) + x, 0)
        if d == "S":
            return kind.get((2 * (y + 1)) * (W + 1) + x, 0)
        if d == "W":
            return kind.get((2 * y + 1) * (W + 1) + x, 0)
        if d == "E":
            return kind.get((2 * y + 1) * (W + 1) + x + 1, 0)
        return 0

    team = {}
    head = {}
    nid = 0
    for l in L:
        p = l.split()
        if p and p[0] == "DRAGON":
            team[nid] = int(p[1])
            head[nid] = (int(p[3]), int(p[4]))
            nid += 1

    ours = our_side(path, rep)
    rnd = 0
    last = {}
    last_round = {}
    prevhead = {}
    h2h_deaths = []  # (round, id, cause) for ALL head-on deaths in order
    wall_checks = []  # (round, id, cause, edge_kind) for 'hit wall' deaths

    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            head[e["child"]] = tuple(e["childBody"][0])
        elif k == "dragonUpdate" and e["head"]:
            h = tuple(e["head"])
            prevhead[e["id"]] = (head.get(e["id"]), rnd)
            head[e["id"]] = h
        elif k == "dragonAction":
            last[e["id"]] = e; last_round[e["id"]] = rnd
        elif k == "dragonDeath":
            i = e["id"]
            cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
            if cause == "head to head":
                h2h_deaths.append((rnd, i, cause))
            # For 'hit wall' deaths, check what edge the mover crossed.
            # The dragon's head is at the tile it was in when it tried to move;
            # the edge it crossed is the one in the direction of its move.
            if cause in ("hit a wall", "hit wall"):
                a = last.get(i, {})
                d = (a.get("dirs") or " ")[0]
                h = head.get(i)
                if d in DXY and h:
                    kd = edge(h[0], h[1], d)
                    wall_checks.append((rnd, i, cause, kd))

    # Verify: NO 'hit wall' death move crosses an open edge; all cross kelp edges
    open_wall = sum(1 for _, _, _, kd in wall_checks if kd == 0)
    kelp_wall = sum(1 for _, _, _, kd in wall_checks if kd == 1)
    portal_wall = sum(1 for _, _, _, kd in wall_checks if kd == 2)
    print(f"  wall check: {len(wall_checks)} 'hit wall' deaths, open={open_wall}, kelp={kelp_wall}, portal={portal_wall}"
          f"  (should be open=0)")

    # Pair head-on victims: two dragons die in the same round
    pairs = []  # (round, id1, id2, team1, team2)
    i = 0
    while i < len(h2h_deaths):
        if i + 1 < len(h2h_deaths) and h2h_deaths[i][0] == h2h_deaths[i + 1][0]:
            r, id1, _ = h2h_deaths[i]
            _, id2, _ = h2h_deaths[i + 1]
            pairs.append((r, id1, id2, team.get(id1), team.get(id2)))
            i += 2
        else:
            i += 1

    # Classify each pair that involves us. The MOVER is the dragon that acted this round right before the deaths
    # (its last action is from this round); its death step starts from its current head (no update is emitted
    # for a fatal move). The other dragon is the victim (stationary this round so far).
    portal_friendly = open_friendly = cross_team = other_ours = 0
    for r, id1, id2, t1, t2 in pairs:
        if ours not in (t1, t2):
            continue
        if t1 != t2:
            cross_team += 1
            continue
        mover = id1 if last_round.get(id1) == r else id2 if last_round.get(id2) == r else None
        if mover is None:
            other_ours += 1; continue
        a = last.get(mover, {})
        d = (a.get("dirs") or " ")[0]
        h = head.get(mover)
        kd = edge(h[0], h[1], d) if d in DXY and h else None
        if kd == 2: portal_friendly += 1
        elif kd == 0: open_friendly += 1
        else: other_ours += 1

    return dict(
        path=str(path),
        ours=ours,
        portal_friendly=portal_friendly,
        open_friendly=open_friendly,
        cross_team=cross_team,
        other_ours=other_ours,
        total_ours=portal_friendly + open_friendly + other_ours,
    )


def main():
    import glob as globmod
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    files = []
    for arg in sys.argv[1:]:
        if "*" in arg or "?" in arg:
            files.extend(sorted(globmod.glob(arg)))
        else:
            files.append(arg)
    for f in files:
        r = analyse(f)
        name = pathlib.Path(f).name
        print(f"{name:30s} portal-friend={r['portal_friendly']:2d}  open-friend={r['open_friendly']:2d}  "
              f"cross-team={r['cross_team']:2d}  other-ours={r['other_ours']:2d}  total-ours={r['total_ours']:2d}")


if __name__ == "__main__":
    main()
