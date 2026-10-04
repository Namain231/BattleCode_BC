"""Regression gate: run CANDIDATE vs a reference opponent on a map/seed panel, and fail the build if
either (a) overall win rate drops below a threshold, or (b) the candidate's queen (dragon id 0/1) dies
before a minimum round on any game where the reference doesn't also lose its queen that early — the
exact failure class this tool exists to catch (see research_new_meta/yvsg/REVIEW_y7_12_49.md).

    python tools/regression_gate.py CANDIDATE_DIR OUTDIR [--opp DIR] [--set live|dev|test|setA|setB]
                                     [--maps a,b,c] [--seeds 1,2,3] [-j 4]
                                     [--win-threshold 0.5] [--min-queen-round 50]

Run from the repo root. Reuses tools/panel_zig.py to build and play the games (same JUDGE/ENGINE env
vars, same map sets), then research_new_meta/analyze.py's per-replay queen metrics to check for the
early-queen-death regression. Exits 0 on pass, 1 on fail, so it can gate a commit/promotion step.

Default --opp is baselines/y7_12_nn1 (the current champion) -- override for a different reference,
e.g. a known-good commit of the same bot before your change.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RNM = os.path.join(ROOT, "research_new_meta")
for p in (HERE, ROOT, RNM):
    if p not in sys.path:
        sys.path.insert(0, p)

import panel_zig  # noqa: E402
import analyze as queen_analyze  # noqa: E402  (research_new_meta/analyze.py)

DEFAULT_OPP = os.path.join(ROOT, "baselines", "y7_12_nn1")


def run_panel(ours, opp, outdir, maps, seeds, j):
    os.makedirs(outdir, exist_ok=True)
    wa, wb = panel_zig.wasm(ours), panel_zig.wasm(opp)
    jobs = [(m, int(s), side) for m in maps for s in seeds for side in "AB"]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(j) as ex:
        futs = [ex.submit(panel_zig.play, wa, wb, m, s, side, outdir) for m, s, side in jobs]
        for f in futs:
            out, msg = f.result()
            print(os.path.basename(out), msg, flush=True)
    return [os.path.join(outdir, f"{m.replace('/', '+')}_{s}_{side}.replay") for m, s, side in jobs]


def queen_death_round(replay_path, side):
    """Our queen's death round (None if she survives to the end) via analyze.py's per-team metrics."""
    r = queen_analyze.analyze(replay_path)
    mine = 0 if side == "A" else 1
    qd = r["teams"][mine]["q_death"]
    return qd[0] if qd else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("outdir")
    ap.add_argument("--opp", default=DEFAULT_OPP)
    ap.add_argument("--set", help="named map set: live, dev, test, setA, setB (overrides --maps)")
    ap.add_argument("--maps", default=panel_zig.CORE)
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("-j", type=int, default=4)
    ap.add_argument("--win-threshold", type=float, default=0.5)
    ap.add_argument("--min-queen-round", type=int, default=50,
                     help="flag a game if our queen dies before this round and the opponent's doesn't")
    a = ap.parse_args()
    maps = panel_zig.SETS[a.set]() if a.set else a.maps.split(",")
    seeds = a.seeds.split(",")

    replays = run_panel(a.candidate, a.opp, a.outdir, maps, seeds, a.j)
    rows = [panel_zig.analyse(p) for p in replays]
    win_rate = sum(r["win"] for r in rows) / len(rows)

    regressions = []
    for p, row in zip(replays, rows):
        mp, seed, side = os.path.basename(p)[:-7].rsplit("_", 2)
        our_qd = queen_death_round(p, side)
        opp_side = "B" if side == "A" else "A"
        opp_qd = queen_death_round(p, opp_side)
        if our_qd is not None and our_qd < a.min_queen_round and (opp_qd is None or opp_qd >= a.min_queen_round):
            regressions.append({"map": mp, "seed": seed, "side": side, "our_qdeath": our_qd, "opp_qdeath": opp_qd})

    report = {
        "candidate": a.candidate, "opp": a.opp, "games": len(rows), "win_rate": win_rate,
        "win_threshold": a.win_threshold, "min_queen_round": a.min_queen_round,
        "queen_regressions": regressions,
    }
    json.dump(report, open(os.path.join(a.outdir, "gate_report.json"), "w"), indent=2)

    passed = win_rate >= a.win_threshold and not regressions
    print(f"\n{a.candidate} vs {a.opp}: {sum(r['win'] for r in rows):.1f}/{len(rows)} = {100*win_rate:.1f}%"
          f" (threshold {100*a.win_threshold:.0f}%)")
    if regressions:
        print(f"QUEEN REGRESSIONS ({len(regressions)}): our queen dies before round {a.min_queen_round} "
              f"while the opponent's doesn't:")
        for r in regressions:
            print(f"  {r['map']} seed {r['seed']} side {r['side']}: ours r{r['our_qdeath']}, opp r{r['opp_qdeath']}")
    print("PASS" if passed else "FAIL", f"-- report: {os.path.join(a.outdir, 'gate_report.json')}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
