"""Measure the metric that actually decides games: the longest single dragon.

    uv run --python 3.11 --with pycapnp python tools/concentration.py REPLAY_DIR [REPLAY_DIR ...]

Why this exists (see insights.md's POST-MORTEM section): across 128 replays, having the longer single
dragon predicted winning in 65/65 games (100%), while more units predicted 72% and more total length
74%. 36% of games are decided by the round-500 longest-dragon tiebreak. Binary win-rate on a 32-game
panel carries ~7-9pp optimism bias and needs 100+ games to resolve anything; these numbers are
continuous, per-game, and low-variance, so a handful of games gives a usable signal.

Reports, from each replay's final state:
  longest        our longest single dragon vs theirs (the actual tiebreak variable)
  concentration  longest / total team length -- how well mass is converted into score
  units, total   the resource game, which we generally already win

Side is taken from the filename suffix (`_A.replay` / `_B.replay`), matching tourney.py --keep-replays.
"""
import argparse
import glob
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from replay import load  # noqa: E402


def rows_for(directory):
    out = []
    for path in sorted(glob.glob(os.path.join(directory, "*.replay"))):
        name = os.path.basename(path)
        if "_A." not in name and "_B." not in name:
            continue
        rep = load(path)
        res = rep.get("result") or {}
        a, b = res.get("A"), res.get("B")
        if not a or not b:
            continue
        side = "A" if "_A." in name else "B"
        us, them = (a, b) if side == "A" else (b, a)
        won = res.get("winner") == (0 if side == "A" else 1)
        out.append({
            "game": name, "side": side, "won": won,
            "tiebreak": res.get("endReason") == 1,
            "us": us, "them": them,
        })
    return out


def conc(team):
    return team["longest"] / team["total"] if team["total"] else 0.0


def report(label, rows):
    if not rows:
        print(f"{label}: no replays found")
        return
    med = st.median
    print(f"\n{'=' * 78}\n{label}  (n={len(rows)})\n{'=' * 78}")
    print(f"{'game':32s} {'win':5s} {'ourLong':8s}{'thLong':7s}{'d':5s} {'ourConc':8s}{'thConc':7s}")
    for r in rows:
        d = r["us"]["longest"] - r["them"]["longest"]
        print(f"{r['game']:32s} {str(r['won']):5s} {r['us']['longest']:<8d}{r['them']['longest']:<7d}"
              f"{d:<+5d} {conc(r['us']):<8.3f}{conc(r['them']):<7.3f}")

    print(f"\n  LONGEST DRAGON   ours {med(r['us']['longest'] for r in rows):6.1f}   "
          f"theirs {med(r['them']['longest'] for r in rows):6.1f}   "
          f"median delta {med(r['us']['longest'] - r['them']['longest'] for r in rows):+.1f}")
    print(f"  CONCENTRATION    ours {med(conc(r['us']) for r in rows):6.3f}   "
          f"theirs {med(conc(r['them']) for r in rows):6.3f}")
    print(f"  units            ours {med(r['us']['count'] for r in rows):6.1f}   "
          f"theirs {med(r['them']['count'] for r in rows):6.1f}")
    print(f"  total length     ours {med(r['us']['total'] for r in rows):6.1f}   "
          f"theirs {med(r['them']['total'] for r in rows):6.1f}")

    longer = sum(1 for r in rows if r["us"]["longest"] > r["them"]["longest"])
    print(f"\n  we had the longer dragon in {longer}/{len(rows)} ({100 * longer / len(rows):.0f}%)"
          f"   -- win rate {100 * sum(r['won'] for r in rows) / len(rows):.0f}%")
    tb = [r for r in rows if r["tiebreak"]]
    if tb:
        tbl = sum(1 for r in tb if r["us"]["longest"] > r["them"]["longest"])
        print(f"  round-500 tiebreak games: {len(tb)}, longer dragon in {tbl}/{len(tb)}, "
              f"won {sum(r['won'] for r in tb)}/{len(tb)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--quiet", action="store_true", help="summary only, no per-game rows")
    args = ap.parse_args()
    for d in args.dirs:
        rows = rows_for(d)
        if args.quiet and rows:
            med = st.median
            # Only games where BOTH sides still have dragons. An eliminated side contributes
            # longest=0/total=0, and mixing those into a median makes cross-build comparison
            # meaningless -- it once appeared to change the *opponent's* median longest from 12 to 4
            # when the opponent bot had not changed at all. Tiebreak games are the cleanest subset
            # (both alive by definition, and they are the 36% of games decided on length).
            live = [r for r in rows if r["us"]["count"] > 0 and r["them"]["count"] > 0]
            tb = [r for r in rows if r["tiebreak"]]
            use, tag = (tb, "tiebreak") if tb else (live, "both-alive")
            if not use:
                print(f"{d:40s} no comparable games")
                continue
            print(f"{d:40s} [{tag} n={len(use):2d}] longest ours={med(r['us']['longest'] for r in use):5.1f} "
                  f"theirs={med(r['them']['longest'] for r in use):5.1f} "
                  f"conc ours={med(conc(r['us']) for r in use):.3f} theirs={med(conc(r['them']) for r in use):.3f} "
                  f"| longer in {sum(1 for r in use if r['us']['longest'] > r['them']['longest'])}/{len(use)}"
                  f" | overall win={100 * sum(r['won'] for r in rows) / len(rows):3.0f}% (n={len(rows)})")
        else:
            report(d, rows)


if __name__ == "__main__":
    main()
