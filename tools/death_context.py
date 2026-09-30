"""Why each team's dragons die: deliberate feeding, combat, or CPU overrun.

Public replays strip CPU points, but the judge kills any turn that exhausts its 100M points and records
it as "no valid action" (docs/timeouts.md) -- so that death cause, read in context, is the only CPU
signal left. Context recorded for every death of the profiled team:

  crowd     dragons of any team with a head within Chebyshev 3 of the dying head (what its 7x7 vision
            held -- more parts in view means more to parse and search, so CPU overruns should rise with it)
  feed      a LONGER teammate's head within Manhattan 2 (dying next to a bigger ally = feeding it)
  enemy     an enemy head within Manhattan 2 (combat pressure)
  len/units the dying dragon's length and how many teammates were alive
  recycle   of the pearls its body dropped (ceil(L/2)), how many a teammate ate within 15 rounds, how
            many the enemy ate, how many were left

    uv run --python 3.11 --with unswbc python tools/death_context.py ladder/scout_fresh
"""
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from profile_style import parse_map  # noqa: E402
from replay import load, DEATHS  # noqa: E402


def phase_of(r):
    return "early" if r < 100 else "mid" if r < 300 else "late"


def analyse(path, side, agg):
    rep = load(path)
    w, h, nbr, _ = parse_map(rep["map"])
    team, body, nid = {}, {}, 0
    for line in rep["map"].splitlines():
        p = line.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t
            body[nid] = [c[2 * i + 1] * w + c[2 * i] for i in range(n)]
            nid += 1
    alive = set(team)

    def xy(c):
        return c % w, c // w

    def manh(a, b):
        ax, ay = xy(a)
        bx, by = xy(b)
        dx, dy = abs(ax - bx), abs(ay - by)
        return min(dx, w - dx) + min(dy, h - dy)

    def cheb(a, b):
        ax, ay = xy(a)
        bx, by = xy(b)
        dx, dy = abs(ax - bx), abs(ay - by)
        return max(min(dx, w - dx), min(dy, h - dy))

    rnd = 0
    drops = {}          # cell -> (death record key, round dropped)
    pending = []        # deaths this round awaiting their dropped pearls
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            pending = [p for p in pending if rnd - p["round"] <= 1]
            # expire unclaimed drops
            for c in [c for c, (_, r0) in drops.items() if rnd - r0 > 15]:
                rec, _ = drops.pop(c)
                rec["left"] += 1
        elif k == "tileChange" and e["pearl"]:
            c = e["tile"][1] * w + e["tile"][0]
            for p in pending:
                if c in p["cells"]:
                    drops[c] = (p["rec"], rnd)
                    break
        elif k == "dragonUpdate" and e["head"]:
            d = e["id"]
            if d not in body:
                continue
            hd = e["head"][1] * w + e["head"][0]
            tl = e["tail"][1] * w + e["tail"][0] if e["tail"] else None
            b = body[d]
            if b[0] != hd:
                b.insert(0, hd)
            if tl is not None:
                while len(b) > 1 and b[-1] != tl:
                    b.pop()
            if hd in drops:
                rec, _ = drops.pop(hd)
                rec["own" if team.get(d) == side else "enemy"] += 1
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            alive.add(e["child"])
            body[e["parent"]] = [q[1] * w + q[0] for q in e["parentBody"]]
            body[e["child"]] = [q[1] * w + q[0] for q in e["childBody"]]
        elif k == "dragonDeath":
            d = e["id"]
            alive.discard(d)
            if team.get(d) != side or d not in body:
                continue
            cause = DEATHS[e["reason"]] if e["reason"] < len(DEATHS) else str(e["reason"])
            hd = body[d][0]
            L = len(body[d])
            heads = [(o, body[o][0]) for o in alive if o in body]
            crowd = sum(1 for o, c in heads if cheb(c, hd) <= 3)
            feed = any(team.get(o) == side and len(body[o]) > L and manh(c, hd) <= 2 for o, c in heads)
            enemy = any(team.get(o) != side and manh(c, hd) <= 2 for o, c in heads)
            units = sum(1 for o in alive if team.get(o) == side)
            key = (cause, phase_of(rnd))
            A = agg[key]
            A["n"] += 1
            A["feed"] += feed
            A["enemy"] += enemy
            A["crowd"] += crowd
            A["len"] += L
            A["units"] += units
            rec = collections.Counter()
            A.setdefault("recs", []).append(rec)
            cells = set(body[d][::2])       # every second segment from the head crystallises
            pending.append({"cells": cells, "rec": rec, "round": rnd})
    return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    args = ap.parse_args()
    root = pathlib.Path(args.dir)
    idx = {(str(e["teamId"]), str(e["game"])): e
           for e in json.load(open(root / "index.json", encoding="utf-8"))}
    per_team = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    elo = {}
    for f in sorted(root.rglob("*.replay")):
        m = idx.get((f.parent.name, f.stem))
        if not m:
            continue
        side = 0 if m["side"] in ("A", 0) else 1
        elo[m["team"]] = m.get("elo", 0)
        try:
            analyse(f, side, per_team[m["team"]])
        except Exception as exc:
            print(f"  ! {f}: {type(exc).__name__}: {exc}", file=sys.stderr)

    print("\nDeath context by cause (all phases pooled). feed% = a longer teammate head within 2;"
          " enemy% = enemy head within 2;\ncrowd = heads in its 7x7 vision; recycle own/enemy/left = where"
          " its dropped pearls went (15-round window).\n")
    hdr = (f"{'team':22s} {'cause':16s} {'n':>6s} {'e|m|l %':>12s} {'feed%':>6s} {'enemy%':>7s}"
           f" {'crowd':>6s} {'len':>5s} {'units':>6s} {'recycle own/enemy/left %':>25s}")
    print(hdr)
    print("-" * len(hdr))
    for t in sorted(per_team, key=lambda n: -elo.get(n, 0)):
        A = per_team[t]
        causes = collections.Counter()
        for (cause, ph), c in A.items():
            causes[cause] += c["n"]
        for cause, n in causes.most_common():
            if n < 20:
                continue
            tot = collections.Counter()
            ph = collections.Counter()
            rc = collections.Counter()
            for (c2, p), c in A.items():
                if c2 != cause:
                    continue
                for kk in ("n", "feed", "enemy", "crowd", "len", "units"):
                    tot[kk] += c[kk]
                ph[p] += c["n"]
                for r in c.get("recs", []):
                    rc.update(r)
            rt = sum(rc.values()) or 1
            phs = "|".join(f"{100 * ph[p] / n:3.0f}" for p in ("early", "mid", "late"))
            print(f"{t[:22]:22s} {cause[:16]:16s} {n:>6d} {phs:>12s} {100 * tot['feed'] / n:>6.0f}"
                  f" {100 * tot['enemy'] / n:>7.0f} {tot['crowd'] / n:>6.1f} {tot['len'] / n:>5.1f}"
                  f" {tot['units'] / n:>6.1f} {100 * rc['own'] / rt:>8.0f}/{100 * rc['enemy'] / rt:>3.0f}/{100 * rc['left'] / rt:>3.0f}")
        print()


if __name__ == "__main__":
    main()
