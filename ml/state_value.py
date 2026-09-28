"""What game state predicts winning? Snapshots at rounds 50/100/200/300/400 from every replay on disk.

    python ml/state_value.py [--workers 10]

Per game and side: units, longest, total length, eats and deaths so far (by cause), pearls eaten on fast tiles, and
the final result. Then, per checkpoint round, a gradient-boosted model predicts the winner from the us-minus-them
differences; reports held-out accuracy and permutation importance, overall and per map. Writes ml/state_value.csv.
"""
import argparse
import collections
import csv
import glob
import multiprocessing as mp
import os
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from replay import load, DEATHS  # noqa: E402

CHECK = (50, 100, 200, 300, 400)


def features(path):
    try:
        rep = load(path)
    except Exception:
        return None
    lines = rep["map"].splitlines()
    name = next((" ".join(l.split()[1:]) for l in lines[:6] if l.startswith("MAP_NAME")), "?")
    W, H = map(int, lines[0].split()[1:3])
    fast = set()
    for l in lines:
        p = l.split()
        if p and p[0] == "TILE" and len(p) >= 5 and 0 < int(p[4]) and int(p[3]) + int(p[4]) <= 20:
            fast.add((int(p[1]), int(p[2])))
    team, body, nid = {}, {}, 0
    for l in lines:
        p = l.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t; body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    alive = set(team); rnd = 0
    acc = {s: collections.Counter() for s in (0, 1)}
    snaps = {}

    def snap():
        out = {}
        for s in (0, 1):
            ls = sorted((len(body[i]) for i in alive if team[i] == s), reverse=True)
            c = acc[s]
            out[s] = {"units": len(ls), "longest": ls[0] if ls else 0, "second": ls[1] if len(ls) > 1 else 0,
                      "total": sum(ls), "eats": c["eat"], "fast_eats": c["fast"], "splits": c["split"],
                      "d_trapped": c["trapped"], "d_h2h": c["h2h"], "d_feed": c["feed"]}
        return out

    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd in CHECK:
                snaps[rnd] = snap()
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]; before = len(b); moved = b[0] != e["head"]
            if moved: b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]: b.pop()
            if moved and len(b) > before:
                acc[team[e["id"]]]["eat"] += len(b) - before
                if tuple(e["head"]) in fast:
                    acc[team[e["id"]]]["fast"] += len(b) - before
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]; body[e["child"]] = e["childBody"]; body[e["parent"]] = e["parentBody"]
            alive.add(e["child"]); acc[e["team"]]["split"] += 1
        elif k == "dragonDeath":
            i = e["id"]
            if i in team:
                why = DEATHS[e["reason"]]
                acc[team[i]]["h2h" if why == "head to head" else "feed" if why == "no valid action" else "trapped"] += 1
            alive.discard(i)
    end = snap()
    u, t = end[0], end[1]
    if u["units"] and t["units"]:
        win0 = (u["longest"], u["total"]) > (t["longest"], t["total"])
        if (u["longest"], u["total"]) == (t["longest"], t["total"]):
            return None
    else:
        win0 = u["units"] > 0
    return os.path.basename(path).split(".")[0], name, win0, snaps, rnd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args()
    files, seen = [], set()
    for f in glob.glob(str(ROOT / "**" / "*.replay"), recursive=True):
        gid = os.path.basename(f)
        if "ml" in pathlib.Path(f).parts or gid in seen:
            continue
        seen.add(gid); files.append(f)
    print(len(files), "unique replays", flush=True)
    with mp.Pool(a.workers) as pool:
        res = [r for r in pool.imap_unordered(features, files, chunksize=4) if r]
    print(len(res), "decided games", flush=True)
    rows = []
    for gid, name, win0, snaps, last in res:
        for side in (0, 1):
            for r, sn in snaps.items():
                us, them = sn[side], sn[1 - side]
                row = {"game": gid, "map": name, "round": r, "win": int(win0 if side == 0 else not win0)}
                for k in us:
                    row[f"{k}_us"] = us[k]; row[f"{k}_them"] = them[k]; row[f"{k}_diff"] = us[k] - them[k]
                rows.append(row)
    with open(ROOT / "ml" / "state_value.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.inspection import permutation_importance
    from sklearn.model_selection import GroupShuffleSplit
    feats = [k for k in rows[0] if k.endswith("_diff")]
    for r in CHECK:
        R = [x for x in rows if x["round"] == r]
        if len(R) < 200:
            continue
        X = np.array([[x[k] for k in feats] for x in R], float); y = np.array([x["win"] for x in R])
        g = np.array([x["game"] for x in R])
        tr, te = next(GroupShuffleSplit(1, test_size=0.25, random_state=0).split(X, y, g))
        m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08).fit(X[tr], y[tr])
        acc = m.score(X[te], y[te])
        imp = permutation_importance(m, X[te], y[te], n_repeats=5, random_state=0).importances_mean
        top = sorted(zip(feats, imp), key=lambda t: -t[1])[:6]
        print(f"round {r}: {len(R) // 2} games, predict winner {acc:.3f}  | " +
              ", ".join(f"{k[:-5]} {v:.3f}" for k, v in top), flush=True)
        for fname in ("units_diff", "longest_diff", "total_diff"):
            j = feats.index(fname)
            for lo, hi in ((-99, -6), (-5, -1), (0, 0), (1, 5), (6, 99)):
                sel = (X[:, j] >= lo) & (X[:, j] <= hi)
                if sel.sum() >= 40:
                    print(f"     {fname[:-5]:8s} diff {lo:+d}..{hi:+d}: win {y[sel].mean():.2f} (n={sel.sum()})")
    by_map = collections.defaultdict(list)
    for x in rows:
        if x["round"] == 100:
            by_map[x["map"]].append(x)
    print("\nround 100, per map: win rate when ahead on units by 5+ / when ahead on longest by 3+")
    for mp_, R in sorted(by_map.items()):
        u = [x["win"] for x in R if x["units_diff"] >= 5]; l = [x["win"] for x in R if x["longest_diff"] >= 3]
        print(f"  {mp_:18s} n={len(R) // 2:4d}  units+5: {np.mean(u) if u else float('nan'):.2f} ({len(u)})"
              f"  longest+3: {np.mean(l) if l else float('nan'):.2f} ({len(l)})")


if __name__ == "__main__":
    main()
