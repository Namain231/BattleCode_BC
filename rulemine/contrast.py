"""Contrast mining: where do the top teams' decisions differ most from ours, situation by situation?

Two extracted CSVs of the same decision (top teams vs ours) are bucketed on a few features; every bucket gets the
decision rate in each group, and buckets are ranked by gap x sqrt(smaller support). For move choice (queen_move)
the report instead compares choice tendencies (how often the chosen step is the one that eats, keeps most room,
moves toward allies, ...).
"""
import math

import numpy as np

# default bucket edges per feature (value <= edge -> bucket); anything above the last edge is the last bucket
EDGES = {
    "len": [2, 3, 5, 9, 16],
    "top_ally_ratio": [0, 1.5, 2, 3],
    "top_ally_dist": [1, 2, 4, 8, 98],
    "top_ally_approach": [0],
    "mem_top_dist": [2, 4, 8, 98],
    "units": [8, 16, 32, 56],
    "round": [150, 250, 350, 450],
    "enemy_threat": [0],
    "room": [5, 15, 39],
    "pearls_r3": [0, 2, 5],
    "allies_near_top": [0, 2],
    "p_win": [0.3, 0.5, 0.7],     # bceval context: compare like with like (a losing team plays differently)
}
DEFAULT_BY = {"death": ["top_ally_ratio", "top_ally_dist", "top_ally_approach", "round"],
              "bud": ["len", "units", "round", "enemy_threat"]}
WITH_PWIN = "p_win"            # appended to `by` when both CSVs carry it


def bucket(v, edges):
    for k, e in enumerate(edges):
        if v <= e:
            lo = edges[k - 1] if k else None
            return f"<={e}" if lo is None else f"({lo},{e}]"
    return f">{edges[-1]}"


def binary(top, ours, by, label="label", min_support=30, limit=25):
    def table(rows):
        t = {}
        for r in rows:
            if any(r.get(f) in (None, "") for f in by):
                continue
            key = tuple(bucket(float(r[f]), EDGES.get(f, [0])) for f in by)
            n, k = t.get(key, (0, 0))
            t[key] = (n + 1, k + int(r[label]))
        return t
    tt, to = table(top), table(ours)
    out = []
    for key in set(tt) | set(to):
        nt, kt = tt.get(key, (0, 0))
        no, ko = to.get(key, (0, 0))
        if min(nt, no) < min_support:
            continue
        rt, ro = kt / nt, ko / no
        out.append({"bucket": dict(zip(by, key)), "top_rate": rt, "our_rate": ro, "top_n": nt, "our_n": no,
                    "score": (rt - ro) * math.sqrt(min(nt, no))})
    out.sort(key=lambda r: -abs(r["score"]))
    overall = (sum(int(r[label]) for r in top) / max(1, len(top)), sum(int(r[label]) for r in ours) / max(1, len(ours)))
    return {"by": by, "overall": overall, "rows": out[:limit], "top_total": len(top), "our_total": len(ours)}


TENDENCIES = ["eat", "room_after", "toward_allies", "d_enemy", "straight", "enemy_reach", "d_ally"]


def moves(top, ours):
    def tend(rows):
        dec = {}
        for r in rows:
            dec.setdefault(r["decision"], []).append(r)
        res = {}
        for f in TENDENCIES:
            hit = n = 0
            for cands in dec.values():
                vals = [float(c[f]) for c in cands]
                if max(vals) == min(vals):
                    continue      # the feature does not separate the options here
                best = max(vals) if f not in ("enemy_reach", "d_ally") else min(vals)
                chosen = next(float(c[f]) for c in cands if int(c["chosen"]))
                hit += chosen == best
                n += 1
            res[f] = (hit / n if n else float("nan"), n)
        return res, len(dec)
    (tt, nt), (to, no) = tend(top), tend(ours)
    return {"decisions": (nt, no), "rows": [{"prefers": f"{'min' if f in ('enemy_reach', 'd_ally') else 'max'} {f}",
                                             "top": tt[f][0], "ours": to[f][0], "top_n": tt[f][1], "our_n": to[f][1]}
                                            for f in TENDENCIES]}


def markdown(decision, res):
    lines = [f"# Contrast: {decision}", ""]
    if "by" in res:
        ot, oo = res["overall"]
        lines += [f"Overall rate: top {ot:.3f} ({res['top_total']} opportunities), ours {oo:.3f} ({res['our_total']}).",
                  "", "| " + " | ".join(res["by"]) + " | top rate | our rate | top n | our n | score |",
                  "|" + "---|" * (len(res["by"]) + 5)]
        for r in res["rows"]:
            lines.append("| " + " | ".join(r["bucket"][f] for f in res["by"]) +
                         f" | {r['top_rate']:.3f} | {r['our_rate']:.3f} | {r['top_n']} | {r['our_n']} | {r['score']:+.2f} |")
    else:
        nt, no = res["decisions"]
        lines += [f"Decisions: top {nt}, ours {no}. Share of decisions where the chosen step is the best on a feature",
                  "(only decisions where that feature differs between the options):", "",
                  "| tendency | top | ours | top n | our n |", "|---|---|---|---|---|"]
        for r in res["rows"]:
            lines.append(f"| {r['prefers']} | {r['top']:.2f} | {r['ours']:.2f} | {r['top_n']} | {r['our_n']} |")
    return "\n".join(lines) + "\n"
