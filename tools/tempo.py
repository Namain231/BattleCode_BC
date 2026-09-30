"""Early-game population tempo -- the metric that actually decides games, measurable by round 50.

    uv run --python 3.11 --with pycapnp python tools/tempo.py REPLAY_DIR [REPLAY_DIR ...]

Why (insights.md, "the game is decided by round 50"): across 128 replays, our population *edge* at
round 50 predicts the result almost deterministically --

    behind by 5+ : 23% win      ahead 0-4 : 63% win
    behind 1-4   : 27% win      ahead 5+  : 100% win (21/21)

and per map the edge@50 ranks the maps in almost exactly win-rate order. Everything downstream
(feeding, consolidation, length tiebreaks, late-game safety) is decided by a race that is already
over 50 rounds in.

This makes it the right thing to optimise *and* a far cheaper test than win rate: it is continuous,
low-variance, available 50 rounds into a 500-round game, and needs a handful of games rather than the
100+ that a binary win-rate SPRT needs to resolve anything. Win rate on a 32-game panel additionally
carries ~7-9pp optimism bias when used to select changes (measured three times).

Side is taken from the filename suffix (`_A.replay` / `_B.replay`), matching tourney.py --keep-replays.
"""
import argparse
import glob
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from replay import load  # noqa: E402

CHECKPOINTS = (25, 50, 100, 150)


def tempo_for(path):
    rep = load(path)
    res = rep.get("result") or {}
    if not res.get("A") or not res.get("B"):
        return None
    name = os.path.basename(path)
    if "_A." not in name and "_B." not in name:
        return None
    mine = 0 if "_A." in name else 1

    # Initial dragons are listed in the map header in id order.
    team, nid = {}, 0
    for line in rep["map"].splitlines():
        parts = line.split()
        if parts and parts[0] == "DRAGON":
            team[nid] = int(parts[1])
            nid += 1

    alive = set(team)
    snap, rnd = {}, -1
    for e in rep["events"]:
        kind = e["kind"]
        if kind == "roundStart":
            rnd = e["round"]
            if rnd in CHECKPOINTS:
                ours = sum(1 for i in alive if team.get(i) == mine)
                theirs = sum(1 for i in alive if team.get(i) == 1 - mine)
                snap[rnd] = (ours, theirs)
        elif kind == "dragonSplit":
            team[e["parent"]] = e["team"]
            team[e["child"]] = e["team"]
            alive.add(e["child"])
        elif kind == "dragonDeath":
            alive.discard(e["id"])

    return {
        "map": name.rsplit("_", 2)[0],
        "snap": snap,
        "won": res.get("winner") == mine,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--per-map", action="store_true")
    args = ap.parse_args()

    for d in args.dirs:
        rows = [r for f in sorted(glob.glob(os.path.join(d, "*.replay"))) if (r := tempo_for(f))]
        if not rows:
            print(f"{d}: no replays")
            continue
        parts = []
        for cp in CHECKPOINTS:
            s = [r for r in rows if cp in r["snap"]]
            if not s:
                continue
            edge = st.median(r["snap"][cp][0] - r["snap"][cp][1] for r in s)
            ours = st.median(r["snap"][cp][0] for r in s)
            parts.append(f"r{cp}: {ours:4.1f} ({edge:+5.1f})")
        win = 100 * sum(r["won"] for r in rows) / len(rows)
        print(f"{d:40s} n={len(rows):3d}  " + "  ".join(parts) + f"   win={win:3.0f}%")

        if args.per_map:
            for m in sorted({r["map"] for r in rows}):
                s = [r for r in rows if r["map"] == m and 50 in r["snap"]]
                if not s:
                    continue
                e50 = st.median(r["snap"][50][0] - r["snap"][50][1] for r in s)
                print(f"    {m:18s} n={len(s):3d}  edge@50={e50:+6.1f}   "
                      f"win={100 * sum(r['won'] for r in s) / len(s):3.0f}%")


if __name__ == "__main__":
    main()
