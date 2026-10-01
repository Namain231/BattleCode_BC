"""Learners: a small bake-off for yes/no decisions, and a conditional logit for move choice.

Yes/no (death, bud): L1-logistic and a depth-3 tree are the ship candidates; gradient-boosted trees are a ceiling
check only. Cross-validation is grouped by GAME (never by turn) and the pooled out-of-fold AUC decides. The simplest
candidate within `tolerance` of the best simple one ships; if the ceiling beats it by more than `ceiling_gap`, the
report says so (ship GBM only as a score term, by hand).

Move choice (queen_move): conditional logit. Each decision is a set of candidate steps with features; the model
learns weights w so that P(step) = softmax(w . x). The weights are readable preferences ("room counts 3x eating").
"""
import json
import math

import numpy as np

DEFAULT_EXCLUDE = {"round", "age"}       # clock features stay out unless asked for (spec: condition, not clock)
META = {"game", "map", "side", "id", "round", "won", "label", "fed_ok", "fed_any", "target", "team", "child_len",
        "decision", "dir", "chosen", "p_win"}


def _auc(y, p):
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y)
    if len(set(y.tolist())) < 2:
        return float("nan")
    return float(roc_auc_score(y, p))


def _folds(groups, k):
    uniq = sorted(set(groups))
    k = max(2, min(k, len(uniq)))
    rng = np.random.default_rng(0)
    perm = rng.permutation(len(uniq))
    fold_of = {uniq[g]: n % k for n, g in enumerate(perm)}
    return np.array([fold_of[g] for g in groups]), k


def _models(n):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeClassifier
    leaf = max(20, n // 100)
    return {
        "logistic_l1": lambda: make_pipeline(StandardScaler(), LogisticRegression(
            penalty="l1", solver="liblinear", C=0.1, class_weight="balanced", max_iter=2000)),
        "tree_d3": lambda: DecisionTreeClassifier(max_depth=3, min_samples_leaf=leaf, class_weight="balanced",
                                                  random_state=0),
        "gbm_ceiling": lambda: HistGradientBoostingClassifier(max_depth=4, max_iter=200, learning_rate=0.1,
                                                              class_weight="balanced", random_state=0),
    }


RATE_SLACK = 1.25   # a learned yes/no rule may fire at most this many times as often as the team did


def _rate_threshold(scores, base):
    """Lowest threshold t with mean(scores >= t) <= RATE_SLACK * base (exact scores: no rounding, as balanced
    class weights push the top scores within 1e-6 of 1)."""
    u, counts = np.unique(scores, return_counts=True)
    if not len(u):
        return 1.0
    at_or_above = np.cumsum(counts[::-1])[::-1] / len(scores)    # firing rate for threshold u[i]
    fits = np.flatnonzero(at_or_above <= RATE_SLACK * base)
    return float(u[fits[0]]) if len(fits) else float(np.nextafter(u[-1], np.inf))   # nothing fits: never fire


def bakeoff(rows, features, label="label", k=5, tolerance=0.02, ceiling_gap=0.03):
    X = np.array([[float(r[f]) for f in features] for r in rows])
    y = np.array([int(r[label]) for r in rows])
    groups = [r["game"] for r in rows]
    maps = np.array([r.get("map", "") for r in rows])
    fold, k = _folds(groups, k)
    oof, auc = {}, {}
    for name, make in _models(len(rows)).items():
        p = np.full(len(y), np.nan)
        for f in range(k):
            tr, te = fold != f, fold == f
            if len(set(y[tr])) < 2 or te.sum() == 0:
                continue
            m = make().fit(X[tr], y[tr])
            p[te] = m.predict_proba(X[te])[:, 1]
        ok = ~np.isnan(p)
        oof[name], auc[name] = p, _auc(y[ok], p[ok])
    simple = ["tree_d3", "logistic_l1"]            # tree first: preferred on ties (fewer moving parts)
    best_simple = max(auc[s] for s in simple)
    pick = next(s for s in simple if auc[s] >= best_simple - tolerance)
    final = _models(len(rows))[pick]().fit(X, y)
    # decision threshold: fire about as often as the team does. Balanced accuracy is the wrong target for a rare,
    # irreversible decision (a feeding death is ~1% of opportunities): it trades precision for recall and fires
    # many times more often than the team. So take the lowest threshold whose firing rate stays within
    # RATE_SLACK x the observed positive rate (the highest recall at a believable rate). The rate is set on the
    # shipped model's own scores (that is what the bot will fire on); precision and recall come out-of-fold.
    p = oof[pick]; ok = ~np.isnan(p)
    base = float(y.mean()) if len(y) else 0.0
    shipped = export(final, pick, features)
    scores = np.array([predict(shipped, list(x)) for x in X])
    best_t = _rate_threshold(scores, base)
    fire_rate = float((scores >= best_t).mean())
    t_oof = _rate_threshold(p[ok], base)
    pred = p[ok] >= t_oof
    pos, neg = (y[ok] == 1), (y[ok] == 0)
    tpr = (pred & pos).sum() / max(1, pos.sum())
    tnr = (~pred & neg).sum() / max(1, neg.sum())
    best_ba = (tpr + tnr) / 2
    precision = (pred & pos).sum() / max(1, pred.sum())
    per_map = {}
    for m in sorted(set(maps)):
        sel = ok & (maps == m)
        if (y[sel] == 1).sum() >= 20 and (y[sel] == 0).sum() >= 20:
            per_map[m] = _auc(y[sel], p[sel])
    unstable = [m for m, a in per_map.items() if a < auc[pick] - 0.15]
    return {
        "features": features, "n": len(rows), "positives": int(y.sum()), "games": len(set(groups)),
        "auc": auc, "pick": pick, "threshold": best_t, "balanced_accuracy": float(best_ba),
        "precision": float(precision), "recall": float(tpr), "base_rate": float(base), "fire_rate": fire_rate,
        "ceiling_gap": auc["gbm_ceiling"] - auc[pick], "use_gbm_as_score_term": auc["gbm_ceiling"] - auc[pick] > ceiling_gap,
        "per_map_auc": per_map, "unstable_maps": unstable, "model": export(final, pick, features),
    }


def export(model, kind, features):
    if kind == "logistic_l1":
        sc, lr = model.steps[0][1], model.steps[1][1]
        scale = np.where(sc.scale_ == 0, 1, sc.scale_)
        w = lr.coef_[0] / scale                         # back to raw feature units
        b = float(lr.intercept_[0] - (lr.coef_[0] * sc.mean_ / scale).sum())
        return {"type": "logistic", "features": features, "weights": [float(v) for v in w], "bias": b}
    if kind == "tree_d3":
        t = model.tree_
        cls1 = list(model.classes_).index(1)
        nodes = []
        for n in range(t.node_count):
            v = t.value[n][0]
            nodes.append({"left": int(t.children_left[n]), "right": int(t.children_right[n]),
                          "feature": int(t.feature[n]), "threshold": float(t.threshold[n]),
                          "p": float(v[cls1] / v.sum()) if v.sum() else 0.0, "n": int(t.n_node_samples[n])})
        return {"type": "tree", "features": features, "nodes": nodes}
    raise ValueError(kind)


def predict(model, x):
    """Reference predictor for an exported model (the generated C++ must match this)."""
    if model["type"] == "logistic":
        z = model["bias"] + sum(w * v for w, v in zip(model["weights"], x))
        return 1 / (1 + math.exp(-z))
    n = 0
    nodes = model["nodes"]
    while nodes[n]["left"] >= 0:
        nd = nodes[n]
        n = nd["left"] if x[nd["feature"]] <= nd["threshold"] else nd["right"]
    return nodes[n]["p"]


# ---- conditional logit ---------------------------------------------------------------------------------------
def conditional_logit(rows, features, l2=1e-3, k=5):
    from scipy.optimize import minimize
    dec = {}
    for r in rows:
        dec.setdefault(r["decision"], []).append(r)
    keys = sorted(dec)
    games = [dec[d][0]["game"] for d in keys]
    Xs = [np.array([[float(c[f]) for f in features] for c in dec[d]]) for d in keys]
    ys = [int(np.argmax([int(c["chosen"]) for c in dec[d]])) for d in keys]
    allx = np.concatenate(Xs)
    mu, sd = allx.mean(0), allx.std(0)
    sd[sd == 0] = 1

    def fit(idx):
        def nll(w):
            tot, grad = 0.0, np.zeros_like(w)
            for i in idx:
                z = ((Xs[i] - mu) / sd) @ w
                z -= z.max()
                p = np.exp(z); p /= p.sum()
                tot -= math.log(p[ys[i]] + 1e-12)
                xn = (Xs[i] - mu) / sd
                grad -= xn[ys[i]] - p @ xn
            return tot + l2 * (w @ w), grad + 2 * l2 * w
        return minimize(nll, np.zeros(len(features)), jac=True, method="L-BFGS-B").x

    fold, k = _folds(games, k)
    hits = []
    for f in range(k):
        tr = [i for i in range(len(keys)) if fold[i] != f]
        te = [i for i in range(len(keys)) if fold[i] == f]
        if not tr or not te:
            continue
        w = fit(tr)
        for i in te:
            u = ((Xs[i] - mu) / sd) @ w
            best = np.flatnonzero(u >= u.max() - 1e-9)
            hits.append(float(ys[i] in best) / len(best))     # ties share the credit, like chance does
    w = fit(range(len(keys)))
    raw = w / sd
    baselines = {}
    for fname in features:
        j = features.index(fname)
        baselines[f"argmax {fname}"] = float(np.mean([float(ys[i] in np.flatnonzero(Xs[i][:, j] == Xs[i][:, j].max()))
                                                      / int((Xs[i][:, j] == Xs[i][:, j].max()).sum())
                                                      for i in range(len(keys))]))
    top1 = float(np.mean(hits)) if hits else float("nan")
    chance = float(np.mean([1 / len(x) for x in Xs]))
    # a move model is only worth wiring in if, on games it never saw, it beats both chance and the best
    # one-feature rule (those baselines need no fitting, so their in-sample score is an honest comparison)
    useful = bool(hits) and top1 > max(chance, max(baselines.values(), default=0))
    return {"type": "clogit", "features": features, "weights": [float(v) for v in raw], "useful": useful,
            "weights_standardised": [float(v) for v in w], "decisions": len(keys), "games": len(set(games)),
            "top1_heldout": top1, "chance": chance, "baselines": baselines}


def save(result, path):
    with open(path, "w") as fh:
        json.dump(result, fh, indent=1)
