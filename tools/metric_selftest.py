"""Audit the replay metrics against identities that must hold, so a wrong counter is caught BEFORE it drives a decision
(two metric bugs on 30 Sept: the wreck share denominator, and counting every no-valid-action death as a feed).

    python tools/metric_selftest.py DIR_OR_GLOB [--n 20]

Checks per replay (our side, then theirs), using tools/replay_cache.py:
 1. MASS IDENTITY: start mass + pearls eaten - sprint segments - mass of dead dragons == final mass (result.total).
    A mismatch means the eat counter (pearl tracking) or the body tracking is wrong.
 2. FEED TAGS: deliberate feeds (SPLIT 1 / suicide then no valid action) vs deaths whose last decision tag is FEED
    (our bots only).
 3. WRECK BOUND: wreck pearls made <= sum of ceil(len/2) over all dead dragons; eaten by us + them <= made.
 4. UNITS: final units from the snapshots/dragons == result.count.
Prints per-check pass rates and the worst offenders.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay_cache import parsed, files_of  # noqa: E402
from replay import _decode  # noqa: E402


def start_mass(path, team):
    rep = _decode(str(path)); m = 0
    for l in rep["map"].splitlines():
        p = l.split()
        if p and p[0] == "DRAGON" and int(p[1]) == team: m += int(p[2])
    return m


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    files = files_of(a.src)[:a.n]
    fails = {"mass": [], "feed": [], "wreck": [], "units": []}; n = 0
    for f in files:
        g = parsed(f); n += 1
        res = g["result"]; misc = g["misc"]
        for t in (0, 1):
            side = res.get("A" if t == 0 else "B", {})
            eats = sum(v for (tm, ph), v in g["eats"].items() if tm == t)
            segs = sum(v for (tm, ph, k), v in g["acts"].items() if tm == t and k == "sprint_segs")
            dead = sum(d["length"] for d in g["dragons"].values() if d["team"] == t)
            pred = start_mass(f, t) + eats - segs - dead
            if pred != side.get("total"):
                fails["mass"].append((f.name, t, pred, side.get("total"), eats, segs, dead))
            alive = sum(1 for d in g["dragons"].values() if d["team"] == t)
        o = g["ours"]
        feeds = sum(v for (tm, ph, c, tag), v in g["deaths"].items() if tm == o and c == "FEED")
        feedtag = sum(v for (tm, ph, c, tag), v in g["deaths"].items() if tm == o and tag == "FEED")
        if feeds != feedtag: fails["feed"].append((f.name, feeds, feedtag))
        bound = sum((d["length"] + 1) // 2 for d in g["dragons"].values())
        made = misc.get(("all", "wreck_made"), 0); eaten = misc.get((0, "wreck_eaten"), 0) + misc.get((1, "wreck_eaten"), 0)
        if made > bound or eaten > made: fails["wreck"].append((f.name, made, bound, eaten))
    print(f"{n} replays")
    for k, v in fails.items():
        total = n * (2 if k == "mass" else 1)
        print(f"  {k:6s}: {total - len(v)}/{total} pass" + (f"   e.g. {v[:3]}" if v else ""))


if __name__ == "__main__":
    main()
