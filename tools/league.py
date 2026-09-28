"""League screen: every candidate plays the same pool of different opponents; rank by average win rate.

    python tools/league.py cand1 cand2 ... --pool baselines/v7_12,ladder/team_subs/b9195,ladder/team_subs/b8982
        [--maps trophy,...] [--seeds 2] [-j 9]

Head-to-head screens between two close builds (e.g. two network builds) saturate near 50%; a pool of different
styles separates them better, the way the network's gain showed up against V7.12 (88%) but not against itself.
"""
import argparse
import collections
import concurrent.futures as cf
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tourney  # noqa: E402

MAZE = "trophy,queen_of_spades,default,dilemma,autarky,devil,trauma"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates", nargs="+")
    ap.add_argument("--pool", required=True)
    ap.add_argument("--maps", default=MAZE)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("-j", type=int, default=9)
    a = ap.parse_args()
    maps = a.maps.split(",")
    pool = a.pool.split(",")
    built = {p: tourney.prepare(p) for p in a.candidates + pool}
    jobs = []
    for c in a.candidates:
        for o in pool:
            for m in maps:
                for s in range(a.seeds):
                    seed = 1000 + 17 * s
                    jobs.append((c, o, m, "A", built[c], built[o], seed))
                    jobs.append((c, o, m, "B", built[o], built[c], seed))
    res = collections.defaultdict(lambda: [0.0, 0])          # (cand, opp) -> [wins, games]
    per_map = collections.defaultdict(lambda: [0.0, 0])      # (cand, map)
    with cf.ThreadPoolExecutor(a.j) as ex:
        futs = {ex.submit(tourney.play, m, x, y, seed): (c, o, m, side) for c, o, m, side, x, y, seed in jobs}
        for f in cf.as_completed(futs):
            c, o, m, side = futs[f]
            winner, rounds, how, deaths, peak = f.result()
            if how.startswith("ERROR") or how == "TIMEOUT":
                continue
            w = 1.0 if winner == side else 0.5 if winner is None else 0.0
            for key, d in (((c, o), res), ((c, m), per_map)):
                d[key][0] += w; d[key][1] += 1
    names = [pathlib.Path(o).name for o in pool]
    print(f"{'candidate':22s} " + " ".join(f"{n[:12]:>12s}" for n in names) + "   average")
    for c in a.candidates:
        cells = [res[(c, o)] for o in pool]
        avg = sum(w / n for w, n in cells if n) / max(1, sum(1 for w, n in cells if n))
        print(f"{pathlib.Path(c).name[:22]:22s} " + " ".join(f"{w:5.1f}/{n:<6d}" for w, n in cells) + f"   {100 * avg:5.1f}%")
    print("\nper map (all opponents):")
    for c in a.candidates:
        print(f"  {pathlib.Path(c).name[:22]:22s} " + " ".join(f"{m[:6]}:{per_map[(c, m)][0]:.0f}/{per_map[(c, m)][1]}" for m in maps))


if __name__ == "__main__":
    main()
