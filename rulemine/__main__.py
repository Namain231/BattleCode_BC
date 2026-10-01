"""rulemine command line. Stages (RULE_MINING_SPEC.md):

  extract   replays -> one CSV per decision
      python -m rulemine extract --index ladder/scout_fresh/index.json --root ladder/scout_fresh \
          --teams SSS,PPP,Stockfish --decision death --out rulemine_data/death_top.csv -j 10
  contrast  top CSV vs our CSV -> ranked gap report (markdown)
      python -m rulemine contrast --decision death --top rulemine_data/death_top.csv \
          --ours rulemine_data/death_ours.csv --out rulemine_data/contrast_death.md
  learn     CSV -> bake-off (yes/no) or conditional logit (queen_move) -> result JSON + report
      python -m rulemine learn --decision death --data rulemine_data/death_top.csv --team SSS \
          --out rulemine_data/death_SSS.json
  codegen   result JSONs -> C++ header for the bot
      python -m rulemine codegen rulemine_data/death_SSS.json --out viper_s2_rules/rules_learned.hpp
"""
import argparse
import csv
import json
import sys

from . import codegen, contrast, extract, learn
from .features import NAMES


def _read(path, team=None):
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    if team:
        rows = [r for r in rows if r.get("team") == team]
    return rows


def _report(decision, res):
    lines = [f"# Learned rule: {decision}", ""]
    if res.get("type") == "clogit":
        m = res
        lines += [f"Conditional logit over {m['decisions']} decisions from {m['games']} games.",
                  f"Held-out top-1 agreement {m['top1_heldout']:.3f} (chance {m['chance']:.3f}).", "",
                  "| feature | weight (raw units) | weight (standardised) |", "|---|---|---|"]
        for f, w, ws in zip(m["features"], m["weights"], m["weights_standardised"]):
            lines.append(f"| {f} | {w:+.4f} | {ws:+.3f} |")
        lines += ["", "Single-feature baselines (always pick the max):", ""]
        lines += [f"- {k}: {v:.3f}" for k, v in m["baselines"].items()]
        if not m.get("useful", True):
            lines += ["", "**DO NOT SHIP**: on held-out games this model does no better than chance or the best "
                          "single-feature rule. More games, or a per-team fit, before wiring it in."]
        return "\n".join(lines) + "\n"
    lines += [f"{res['n']} opportunities, {res['positives']} positives, {res['games']} games.",
              "", "| model | held-out AUC (grouped by game) |", "|---|---|"]
    lines += [f"| {k} | {v:.3f} |" for k, v in res["auc"].items()]
    lines += ["", f"Picked: **{res['pick']}**, threshold {res['threshold']:.3f}: fires on {100 * res['fire_rate']:.2f}% "
                  f"of opportunities (the team: {100 * res['base_rate']:.2f}%), precision {res['precision']:.2f}, "
                  f"recall {res['recall']:.2f}. Ceiling gap {res['ceiling_gap']:+.3f}"
                  + (" -- consider the GBM as a score term." if res["use_gbm_as_score_term"] else "."), ""]
    if res["per_map_auc"]:
        lines += ["Per-map AUC: " + ", ".join(f"{m} {a:.2f}" for m, a in res["per_map_auc"].items())]
    if res["unstable_maps"]:
        lines += [f"UNSTABLE on: {', '.join(res['unstable_maps'])} -- reject or re-derive."]
    m = res["model"]
    lines += ["", "```"]
    if m["type"] == "logistic":
        lines.append(f"logit = {m['bias']:+.4f}")
        lines += [f"      {w:+.4f} * {f}" for f, w in zip(m["features"], m["weights"]) if abs(w) > 1e-9]
    else:
        nodes = m["nodes"]

        def emit(k, ind):
            nd = nodes[k]
            if nd["left"] < 0:
                lines.append("  " * ind + f"-> p={nd['p']:.3f} (n={nd['n']})")
                return
            f = m["features"][nd["feature"]]
            lines.append("  " * ind + f"if {f} <= {nd['threshold']:.3f}:")
            emit(nd["left"], ind + 1)
            lines.append("  " * ind + "else:")
            emit(nd["right"], ind + 1)
        emit(0, 0)
    lines.append("```")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rulemine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--index", required=True); e.add_argument("--root", required=True)
    e.add_argument("--decision", required=True, choices=["death", "bud", "queen_move"])
    e.add_argument("--teams", help="comma-separated team names (default: all in the index)")
    e.add_argument("--winners-only", action="store_true")
    e.add_argument("--out", required=True); e.add_argument("-j", type=int, default=1)
    e.add_argument("--no-pwin", action="store_true", help="skip the bceval p_win context column")
    c = sub.add_parser("contrast")
    c.add_argument("--decision", required=True); c.add_argument("--top", required=True)
    c.add_argument("--ours", required=True); c.add_argument("--by", help="comma-separated features")
    c.add_argument("--out", required=True)
    le = sub.add_parser("learn")
    le.add_argument("--decision", required=True); le.add_argument("--data", required=True)
    le.add_argument("--team"); le.add_argument("--features", help="comma-separated (default: all except clock)")
    le.add_argument("--with-round", action="store_true"); le.add_argument("--out", required=True)
    le.add_argument("--label", default="label", help="label column, e.g. fed_ok to learn only good feeds")
    le.add_argument("--min-pwin", type=float, help="only rows where the source side's bceval p_win >= this")
    g = sub.add_parser("codegen")
    g.add_argument("results", nargs="+"); g.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "extract":
        teams = set(a.teams.split(",")) if a.teams else None
        extract.extract(a.index, a.root, a.decision, a.out, teams, a.j, a.winners_only, pwin=not a.no_pwin)
    elif a.cmd == "contrast":
        top, ours = _read(a.top), _read(a.ours)
        if a.decision == "queen_move":
            res = contrast.moves(top, ours)
        else:
            by = a.by.split(",") if a.by else list(contrast.DEFAULT_BY[a.decision])
            if not a.by and all(r.get("p_win") not in (None, "") for r in (top[:1] + ours[:1])):
                by.append(contrast.WITH_PWIN)
            res = contrast.binary(top, ours, by)
        open(a.out, "w").write(contrast.markdown(a.decision, res))
        print(open(a.out).read())
    elif a.cmd == "learn":
        rows = _read(a.data, a.team)
        if a.min_pwin is not None:
            rows = [r for r in rows if r.get("p_win") not in (None, "") and float(r["p_win"]) >= a.min_pwin]
        if not rows:
            sys.exit("no rows")
        if a.decision == "queen_move":
            feats = a.features.split(",") if a.features else ["eat", "straight", "room_after", "d_enemy", "d_ally",
                                                               "toward_allies", "enemy_reach"]
            res = learn.conditional_logit(rows, feats)
            res["model"] = {k: res[k] for k in ("type", "features", "weights")}
        else:
            skip = set() if a.with_round else learn.DEFAULT_EXCLUDE
            feats = a.features.split(",") if a.features else [f for f in NAMES if f not in skip]
            res = learn.bakeoff(rows, feats, label=a.label)
        res["decision"] = a.decision
        res["team"] = a.team
        import hashlib
        res["data"] = {"path": a.data, "sha256": hashlib.sha256(open(a.data, "rb").read()).hexdigest()[:12],
                       "rows": len(rows)}
        learn.save(res, a.out)
        rep = a.out.rsplit(".", 1)[0] + ".md"
        open(rep, "w").write(_report(a.decision, res))
        print(open(rep).read())
    elif a.cmd == "codegen":
        codegen.from_results(a.results, a.out)
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
