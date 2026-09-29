"""Promotion gate: a candidate must dominate every kept build before it may be submitted.

    python tools/gate.py viper_v7 [--champion baselines/y7_12_nn1] [-j 12]

Stage 1 (this script, local sandbox):
  - vs the champion: >= 55% over 40 games (10 live maps x both sides x 2 seeds)
  - vs V7.5 (baselines/v7_5, the long-standing reference): >= 50% over 20 games
  (the other baselines are kept for reference only; playing all of them took too long)
Stage 1 is only a sanity filter: V7.6 passed it and was still a ladder regression.
Stage 2 (manual, required): ladder panel. Submit, then run unranked 10-map challenges against the
panel teams listed in AGENTS.md and compare map by map with the champion's panel results. Only keep
the candidate active if it is at least as good. Self-play alone promoted V7.6, which then lost
ranked games V7.5 wins.
"""
import argparse
import collections
import concurrent.futures as cf
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tourney  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIVE = ["portals", "slithery_fight", "schooltime", "trophy", "queen_of_spades", "default", "dilemma",
        "autarky", "devil", "trauma"]


def series(cand, opp, seeds, j):
    jobs = []
    for m in LIVE:
        for s in range(seeds):
            seed = 1000 + 17 * s
            jobs.append((m, "A", cand, opp, seed))
            jobs.append((m, "B", opp, cand, seed))
    jobs.sort(key=lambda j: tourney.HEAVY.index(j[0]) if j[0] in tourney.HEAVY else len(tourney.HEAVY))
    res = collections.defaultdict(lambda: [0, 0])  # map -> [wins, games]
    wins = games = 0
    with cf.ThreadPoolExecutor(j) as ex:
        futs = {ex.submit(tourney.play, m, x, y, s): (m, side) for m, side, x, y, s in jobs}
        for f in cf.as_completed(futs):
            m, side = futs[f]
            winner, rounds, how, deaths, peak = f.result()
            if how.startswith("ERROR") or how == "TIMEOUT":
                continue
            games += 1
            res[m][1] += 1
            if winner == side:
                wins += 1
                res[m][0] += 1
            elif winner is None:
                wins += 0.5
                res[m][0] += 0.5
    return wins, games, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--champion", default="baselines/y7_12_nn1")
    ap.add_argument("-j", type=int, default=12)
    a = ap.parse_args()
    cand = tourney.prepare(a.candidate)
    champ_dir = (ROOT / a.champion).resolve()
    ref = (ROOT / "baselines" / "v7_5").resolve()
    others = [ref] if ref != champ_dir else []
    verdict = True
    rows = []
    for opp_dir, need, seeds in [(champ_dir, 0.55, 2)] + [(p, 0.50, 1) for p in others]:
        opp = tourney.prepare(str(opp_dir.relative_to(ROOT)))
        w, g, per = series(cand, opp, seeds, a.j)
        rate = w / max(1, g)
        ok = rate >= need
        verdict &= ok
        weak = [m for m, (mw, mg) in per.items() if mg and mw / mg < 0.5]
        rows.append((opp_dir.name, rate, g, need, ok, weak))
        print(f"{'PASS' if ok else 'FAIL'} vs {opp_dir.name:6s}: {w:.1f}/{g} ({100 * rate:.0f}%, need {100 * need:.0f}%)"
              f"  maps below 50%: {', '.join(weak) or '-'}", flush=True)
    print("=" * 60)
    print("STAGE 1 PASSED - now run the ladder panel (AGENTS.md) before keeping it active"
          if verdict else "STAGE 1 FAILED - do not submit")


if __name__ == "__main__":
    main()
