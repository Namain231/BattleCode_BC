"""Behavioural profile of a team from its public replays: does it control area or forage greedily?

Written to test the one strategic hypothesis marginal tuning cannot settle (insights.md, 2026-09-30):
our bots are per-unit greedy potential-field foragers, while the game may actually be a multi-unit
AREA-CONTROL game. Note `Params::wTerritory` and `territoryWeight` exist in our code and are BOTH
inert (0) -- territory was attempted and switched off, so if this is the missing term we have never
actually measured it.

Per replay and per side, at several round checkpoints:

  units      live dragon count
  voronoi    share of reachable cells strictly closer to this team's heads than the other's
             (multi-source BFS over the real kelp graph) -- the direct area-control measure
  spread     mean pairwise distance between own heads: are units dispersed or balled up
  home       mean distance of own heads from the nearest own spawn cell: hold home or invade
  len        mean dragon length (mass per unit)

Usage:
    uv run --python 3.11 --with unswbc python tools/profile_style.py ladder/scout_fresh
    uv run --python 3.11 --with unswbc python tools/profile_style.py DIR --rounds 25,50,100,200
    uv run --python 3.11 --with unswbc python tools/profile_style.py DIR --per-team

Portals (edge kind 2) are treated as open to the geometric neighbour rather than as teleports: they
are a small minority of edges (0 on devil, 12 on trauma) and modelling them properly would not change
an area-share aggregate.
"""
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import load  # noqa: E402

INF = 1 << 29


def parse_map(text):
    """-> (w, h, nbr, spawn_by_team). nbr[c] = list of neighbour cells (kelp removed)."""
    w = h = 0
    edges, dragons = [], []
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "MAP":
            w, h = int(p[1]), int(p[2])
        elif p[0] == "EDGE":
            edges.append((int(p[1]), int(p[2]), int(p[3]) if len(p) > 3 else -1))
        elif p[0] == "DRAGON":
            team, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3:3 + 2 * n]]
            dragons.append((team, [(c[2 * i], c[2 * i + 1]) for i in range(n)]))

    # Edge index -> (cell, dir): rows of horizontal (north-side) edges alternate with rows of
    # vertical (west-side) edges, each row w+1 long. Mapping verified against tools/gen_maps.py.
    kelpN = [False] * (w * h)   # north side of this cell is kelp (or an unpaired portal = wall)
    kelpW = [False] * (w * h)   # west side of this cell is kelp
    portal = {}                 # (cell, 'N'|'W') -> partner cell on the paired edge
    by_pid = collections.defaultdict(list)
    for index, kind, pid in edges:
        if kind == 0:
            continue
        r, col = divmod(index, w + 1)
        if r % 2 == 0:
            x, y, o = col % w, (r // 2) % h, "N"
        else:
            x, y, o = col % w, ((r - 1) // 2) % h, "W"
        c = y * w + x
        if kind == 1:
            (kelpN if o == "N" else kelpW)[c] = True
        elif kind == 2:
            by_pid[pid].append((c, o))
    # Portals are teleports, not open edges (2026-09-30 fix: treating them as open split portal maps
    # into disconnected pieces -- 7 components on Queen of Spades -- and made heads "unreachable").
    # Crossing edge e1 of cell a1 emerges on the same side of the paired edge e2 of cell a2, exactly
    # as viper_v7.12's rebuildNbr does (b = stepRaw(a2, d1)). An unpaired end is a wall.
    for pid, ends in by_pid.items():
        if len(ends) == 2 and ends[0][1] == ends[1][1]:
            (a1, o), (a2, _) = ends
            portal[(a1, o)] = a2
            portal[(a2, o)] = a1
        else:
            for c, o in ends:
                (kelpN if o == "N" else kelpW)[c] = True

    def up(c):
        return ((c // w - 1) % h) * w + c % w

    def left(c):
        return (c // w) * w + (c % w - 1) % w

    nbr = [[] for _ in range(w * h)]
    for y in range(h):
        for x in range(w):
            c = y * w + x
            n_ = ((y - 1) % h) * w + x
            s_ = ((y + 1) % h) * w + x
            w_ = y * w + (x - 1) % w
            e_ = y * w + (x + 1) % w
            if not kelpN[c]:                                   # north: our own north edge
                nbr[c].append(up(portal[(c, "N")]) if (c, "N") in portal else n_)
            if not kelpN[s_]:                                  # south: the north edge of the cell below
                nbr[c].append(portal[(s_, "N")] if (s_, "N") in portal else s_)
            if not kelpW[c]:                                   # west: our own west edge
                nbr[c].append(left(portal[(c, "W")]) if (c, "W") in portal else w_)
            if not kelpW[e_]:                                  # east: the west edge of the cell to the right
                nbr[c].append(portal[(e_, "W")] if (e_, "W") in portal else e_)

    spawn = collections.defaultdict(list)
    for team, cells in dragons:
        for x, y in cells:
            spawn[team].append(y * w + x)
    return w, h, nbr, dict(spawn)


def tdist(w, h, a, b):
    ax, ay = a % w, a // w
    bx, by = b % w, b // w
    dx = abs(ax - bx)
    dy = abs(ay - by)
    return min(dx, w - dx) + min(dy, h - dy)


def voronoi_share(nbr, heads0, heads1):
    """Multi-source BFS from both teams' heads. -> (share0, share1) of contested reachable cells."""
    if not heads0 or not heads1:
        return None
    owner = [0] * len(nbr)   # 0 unvisited, 1 team0, 2 team1, 3 tie
    q = collections.deque()
    for c in heads0:
        if owner[c] == 0:
            owner[c] = 1
            q.append(c)
    for c in heads1:
        owner[c] = 3 if owner[c] == 1 else 2
        if owner[c] == 2:
            q.append(c)
    # standard multi-source BFS; equal-distance cells reached from both sides become ties
    while q:
        c = q.popleft()
        for n in nbr[c]:
            if owner[n] == 0:
                owner[n] = owner[c]
                q.append(n)
            elif owner[n] != owner[c] and owner[n] != 3 and owner[c] != 3:
                pass  # first writer wins; BFS order makes this the nearer team
    a = sum(1 for o in owner if o == 1)
    b = sum(1 for o in owner if o == 2)
    tot = a + b
    if tot == 0:
        return None
    return a / tot, b / tot


def profile(path, rounds):
    rep = load(path)
    w, h, nbr, spawn = parse_map(rep["map"])
    team, body, nid = {}, {}, 0
    for line in rep["map"].splitlines():
        p = line.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t
            body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]
            nid += 1
    head = {i: b[0][1] * w + b[0][0] for i, b in body.items()}
    length = {i: len(b) for i, b in body.items()}
    alive = set(team)
    want = sorted(rounds)
    out = {}
    rnd = 0
    wi = 0
    winner = None
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            while wi < len(want) and rnd >= want[wi]:
                out[want[wi]] = snapshot(w, h, nbr, spawn, team, head, length, alive)
                wi += 1
            if wi >= len(want):
                break
        elif k == "dragonUpdate" and e["head"]:
            head[e["id"]] = e["head"][1] * w + e["head"][0]
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            alive.add(e["child"])
            head[e["child"]] = e["childBody"][0][1] * w + e["childBody"][0][0]
            head[e["parent"]] = e["parentBody"][0][1] * w + e["parentBody"][0][0]
            length[e["child"]] = len(e["childBody"])
            length[e["parent"]] = len(e["parentBody"])
        elif k == "dragonDeath":
            alive.discard(e["id"])
    return out, winner


def snapshot(w, h, nbr, spawn, team, head, length, alive):
    hs = {0: [], 1: []}
    ls = {0: [], 1: []}
    for i in alive:
        t = team.get(i)
        if t is None or i not in head:
            continue
        hs[t].append(head[i])
        ls[t].append(length.get(i, 2))
    vor = voronoi_share(nbr, hs[0], hs[1])
    res = {}
    for t in (0, 1):
        n = len(hs[t])
        if n == 0:
            res[t] = None
            continue
        if n > 1:
            tot = cnt = 0
            for a in range(n):
                for b in range(a + 1, n):
                    tot += tdist(w, h, hs[t][a], hs[t][b])
                    cnt += 1
            spread = tot / cnt
        else:
            spread = 0.0
        sp = spawn.get(t, [])
        home = (sum(min(tdist(w, h, c, s) for s in sp) for c in hs[t]) / n) if sp else -1.0
        res[t] = {
            "units": n,
            "spread": spread,
            "home": home,
            "len": sum(ls[t]) / n,
            "voronoi": (vor[t] if vor else None),
        }
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--rounds", default="25,50,100,200")
    ap.add_argument("--per-team", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="cap replays per team (0 = all)")
    args = ap.parse_args()
    rounds = [int(x) for x in args.rounds.split(",")]
    root = pathlib.Path(args.dir)

    # KEYED BY (teamId, game), not game alone: when two of the scouted teams play each other,
    # scout.py writes the SAME game under both teams' directories with one index.json entry
    # each (different team/side/opponent). Keying by game id alone collapses both entries to
    # whichever sorts last, silently misattributing one copy's data and losing the other's --
    # confirmed to hit 36/150 (24%) of games in the 2026-09-30 top-16 pull (see the identical
    # fix and its note in sonar_profile.py, where it was caught).
    index = {}
    idx_path = root / "index.json"
    if idx_path.exists():
        for e in json.load(open(idx_path, encoding="utf-8")):
            index[(str(e["teamId"]), str(e["game"]))] = e

    # gather: per team name, the "their side" and "opponent side" stats
    acc = collections.defaultdict(lambda: collections.defaultdict(list))
    seen = collections.Counter()
    results = []   # (team name, side, "W"/"L", snapshots) -- feeds the BY RESULT table
    for f in sorted(root.rglob("*.replay")):
        meta = index.get((f.parent.name, f.stem))
        if meta is None:
            continue
        name = meta["team"]
        if args.limit and seen[name] >= args.limit:
            continue
        seen[name] += 1
        side = 0 if meta.get("side") in (0, "A", "a") else 1
        try:
            snaps, _ = profile(f, rounds)
        except Exception as exc:  # a malformed or truncated replay should not kill the run
            print(f"  ! {f.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        win = meta.get("winner")
        res = "W" if (win in (0, "A", "a") and side == 0) or (win in (1, "B", "b") and side == 1) else "L"
        results.append((name, side, res, snaps))
        for r, snap in snaps.items():
            me, them = snap.get(side), snap.get(1 - side)
            if me:
                for key in ("units", "spread", "home", "len", "voronoi"):
                    if me[key] is not None:
                        acc[name][(r, "me", key)].append(me[key])
            if them:
                for key in ("units", "spread", "home", "len", "voronoi"):
                    if them[key] is not None:
                        acc[name][(r, "op", key)].append(them[key])

    def med(v):
        if not v:
            return float("nan")
        s = sorted(v)
        return s[len(s) // 2]

    names = sorted(acc, key=lambda n: -len(acc[n][(rounds[0], "me", "units")]))
    print(f"\nProfiled {sum(seen.values())} replays across {len(names)} teams from {root}")
    print("me = that team; op = whoever they played. voronoi = share of contested reachable area.\n")
    hdr = f"{'team':26s} {'r':>4s} {'units':>11s} {'voronoi':>13s} {'spread':>11s} {'home':>11s} {'len':>11s}"
    print(hdr)
    print("-" * len(hdr))
    for name in names:
        for r in rounds:
            row = []
            for key in ("units", "voronoi", "spread", "home", "len"):
                m = med(acc[name][(r, "me", key)])
                o = med(acc[name][(r, "op", key)])
                row.append(f"{m:5.2f}/{o:5.2f}")
            print(f"{name[:26]:26s} {r:>4d} " + " ".join(f"{c:>11s}" if i != 1 else f"{c:>13s}"
                                                        for i, c in enumerate(row)))
        if args.per_team:
            print()

    # pooled
    print("\n" + "=" * 78)
    print("POOLED over all profiled teams (their value / their opponent's value)")
    pool = collections.defaultdict(list)
    for name in names:
        for (r, who, key), v in acc[name].items():
            pool[(r, who, key)] += v
    print(hdr)
    print("-" * len(hdr))
    for r in rounds:
        row = []
        for key in ("units", "voronoi", "spread", "home", "len"):
            row.append(f"{med(pool[(r, 'me', key)]):5.2f}/{med(pool[(r, 'op', key)]):5.2f}")
        print(f"{'ALL':26s} {r:>4d} " + " ".join(f"{c:>11s}" if i != 1 else f"{c:>13s}"
                                                for i, c in enumerate(row)))

    # What actually predicts the result. This is the part that makes the profile evidence rather
    # than description: split every game-side by whether it WON, and compare the two populations.
    # The confound to keep in mind throughout: voronoi share is partly a *consequence* of having
    # more heads (more heads = more nearest cells), so a raw correlation cannot by itself separate
    # "controlling area wins" from "having more units wins and also yields area". The `per-unit`
    # rows below are the attempt at that separation -- area share divided by unit share, i.e. how
    # much ground each unit is worth.
    print("\n" + "=" * 78)
    print("BY RESULT (median among winners vs among losers, pooled over all sides profiled)")
    won = collections.defaultdict(list)
    lost = collections.defaultdict(list)
    for name, side, res, snaps in results:
        for r, snap in snaps.items():
            me, them = snap.get(side), snap.get(1 - side)
            if not me or not them:
                continue
            tgt = won if res == "W" else lost
            for key in ("units", "voronoi", "spread", "home", "len"):
                if me[key] is not None:
                    tgt[(r, key)].append(me[key])
            if me["units"] and them["units"] and me["voronoi"] is not None:
                ushare = me["units"] / (me["units"] + them["units"])
                tgt[(r, "unitshare")].append(ushare)
                if ushare > 0:
                    tgt[(r, "area_per_unit")].append(me["voronoi"] / ushare)
    keys = ("units", "unitshare", "voronoi", "area_per_unit", "spread", "home", "len")
    print(f"{'round':>6s} " + " ".join(f"{k:>16s}" for k in keys))
    print(f"{'':>6s} " + " ".join(f"{'W / L':>16s}" for _ in keys))
    print("-" * (7 + 17 * len(keys)))
    for r in rounds:
        cells = []
        for k in keys:
            cells.append(f"{med(won[(r, k)]):6.2f}/{med(lost[(r, k)]):6.2f}")
        print(f"{r:>6d} " + " ".join(f"{c:>16s}" for c in cells))
    nw = len(won[(rounds[0], "units")])
    nl = len(lost[(rounds[0], "units")])
    print(f"\nn = {nw} winning sides, {nl} losing sides")


if __name__ == "__main__":
    main()
