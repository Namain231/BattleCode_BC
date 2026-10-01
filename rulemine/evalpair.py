"""Paired screen: candidate vs control, same maps / seeds / sides against the same opponent (RULE_MINING_SPEC gate).

    python -m rulemine.evalpair CANDIDATE_REPLAY_DIR CONTROL_REPLAY_DIR [--rounds 250,400]

Replay names identify the game: either <map>_<seed>_<ourSide>.replay (tools/panel.py) or farm job ids
<ours>~<opp>~<set+map>~<seed>~<ourSide>.replay (farm/make_jobs.py --replays). Per paired game it measures
  win               1 / 0.5 / 0 for our side
  final margin      our longest minus theirs at the end (the round-500 tiebreak quantity; 85% of new-map games)
  p_win@r           bceval win probability at the given rounds (skipped if bceval is unavailable)
  queen@r           our longest dragon at those rounds (the queen's length; needs bceval too)
  feeds             our feeding splits per game: "FEED" indicators (gP's own feed and the learned rule both set
                    one), kept only by judges run with --debug 2 (tools/panel_zig.py does). A learned rule that
                    feeds far more often than the control is misfiring on these maps.
and reports candidate-minus-control means with standard errors and a sign test on wins.
"""
import argparse
import glob
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from replay_lite import decode_lite  # noqa: E402

from . import evalstate, mapgeo


def key_of(name):
    base = os.path.basename(name)[:-len(".replay")]
    if "~" in base:
        _, _, mp, seed, side = base.split("~")
        return (mp, seed, side)
    mp, seed, side = base.rsplit("_", 2)
    return (mp.split("+")[-1] if "+" in mp else mp, seed, side)


def measure(path, rounds):
    k = key_of(path)
    mine = 0 if k[2] == "A" else 1
    rep = decode_lite(path, {"dragonIndicator", "dragonSplit"})
    res = rep.get("result") or {}
    w = res.get("winner")
    win = 0.5 if w not in (0, 1) else float(w == mine)
    ours, theirs = res.get("AB"[mine]) or {}, res.get("AB"[1 - mine]) or {}
    out = {"win": win, "margin": (ours.get("longest", 0) or 0) - (theirs.get("longest", 0) or 0)}
    team = {i: t for i, (t, _) in enumerate(mapgeo.parse(rep["map"]).dragons)} if rep.get("map") else {}
    feeds, saw_indicators = 0, False
    for e in rep["events"]:
        if e["kind"] == "dragonSplit":
            team[e["child"]] = e["team"]
        elif e["kind"] == "dragonIndicator":
            saw_indicators = True
            if team.get(e["id"]) == mine and (e.get("text") or "").split()[:1] == ["FEED"]:
                feeds += 1
    if saw_indicators:
        out["feeds"] = feeds
    ser = evalstate.series(path, mine, every=10)
    qs = evalstate.longest(path, mine, every=10)
    for r in rounds:
        v = evalstate.at(ser, r)
        if v is not None:
            out[f"p_win@{r}"] = v
        q = evalstate.at(qs, r)
        if q is not None:
            out[f"queen@{r}"] = q
    return out


def compare(cand_dir, ctrl_dir, rounds=(250, 400)):
    cand = {key_of(p): p for p in glob.glob(os.path.join(cand_dir, "*.replay"))}
    ctrl = {key_of(p): p for p in glob.glob(os.path.join(ctrl_dir, "*.replay"))}
    keys = sorted(set(cand) & set(ctrl))
    diffs, wins = {}, [0, 0]
    for k in keys:
        a, b = measure(cand[k], rounds), measure(ctrl[k], rounds)
        for m in a:
            if m in b:
                diffs.setdefault(m, []).append(a[m] - b[m])
        if a["win"] > b["win"]:
            wins[0] += 1
        elif a["win"] < b["win"]:
            wins[1] += 1
    n = wins[0] + wins[1]
    p = 1.0
    if n:
        lo = min(wins)
        p = min(1.0, 2 * sum(math.comb(n, i) for i in range(lo + 1)) / 2 ** n)
    summary = {}
    for m, v in diffs.items():
        mean = sum(v) / len(v)
        sd = math.sqrt(sum((x - mean) ** 2 for x in v) / max(1, len(v) - 1))
        summary[m] = (mean, sd / math.sqrt(len(v)), len(v))
    return {"paired": len(keys), "flips": wins, "sign_p": p, "metrics": summary}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate"); ap.add_argument("control")
    ap.add_argument("--rounds", default="250,400")
    a = ap.parse_args()
    r = compare(a.candidate, a.control, tuple(int(x) for x in a.rounds.split(",")))
    print(f"{r['paired']} paired games; win flips up {r['flips'][0]} / down {r['flips'][1]}, sign test p={r['sign_p']:.3f}")
    for m, (mean, se, n) in r["metrics"].items():
        print(f"  {m:12s} candidate - control = {mean:+.3f} +- {se:.3f}  (n={n})")
    if "margin" in r["metrics"]:
        mean, se, _ = r["metrics"]["margin"]
        print("GATE (paired final margin > 0):", "PASS" if mean > 0 else "FAIL")


if __name__ == "__main__":
    main()
