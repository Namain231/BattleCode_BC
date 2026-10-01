import json
import subprocess
import numpy as np
import pytest
from rulemine import learn, codegen


def synthetic(n_games=40, per=200, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_games):
        for _ in range(per):
            ratio = rng.uniform(0.5, 4)
            dist = int(rng.integers(0, 10))
            noise = rng.normal()
            y = int(ratio > 2 and dist <= 2) if rng.random() > 0.05 else int(rng.random() < 0.5)
            rows.append({"game": f"g{g}", "map": f"m{g % 4}", "top_ally_ratio": ratio, "top_ally_dist": dist,
                         "noise": noise, "label": y})
    return rows


FEATS = ["top_ally_ratio", "top_ally_dist", "noise"]


@pytest.fixture(scope="module")
def res():
    return learn.bakeoff(synthetic(), FEATS)


def test_bakeoff_finds_an_and_rule_with_a_simple_model(res):
    assert res["pick"] in ("tree_d3", "logistic_l1")
    assert res["auc"]["tree_d3"] > 0.9
    assert res["pick"] == "tree_d3"               # an AND of two thresholds is a tree's home ground
    assert not res["unstable_maps"]


def test_threshold_fires_about_as_often_as_the_team_does_on_rare_decisions():
    # feeding deaths are ~1% of opportunities. A balanced-accuracy threshold fires on a large share of them (a
    # fixture-trained rule fed ~500 times a game vs gP's ~40); an irreversible action must instead fire at about
    # the rate the team itself does.
    rng = np.random.default_rng(3)
    rows = []
    for g in range(40):
        for _ in range(500):
            x = rng.normal(size=2)
            y = int(rng.random() < 1 / (1 + np.exp(-(2.5 * x[0] - 6))))
            rows.append({"game": f"g{g}", "map": f"m{g % 4}", "a": x[0], "b": x[1], "label": y})
    r = learn.bakeoff(rows, ["a", "b"])
    base = np.mean([row["label"] for row in rows])
    fired = np.mean([learn.predict(r["model"], [row["a"], row["b"]]) >= r["threshold"] for row in rows])
    assert base < 0.05
    assert fired <= 1.5 * base
    assert r["fire_rate"] == pytest.approx(fired, abs=0.01)


def test_exported_tree_predicts_like_the_fitted_model(res):
    m = res["model"]
    assert learn.predict(m, [3.0, 1, 0.0]) > 0.8
    assert learn.predict(m, [1.0, 1, 0.0]) < 0.2
    assert learn.predict(m, [3.0, 7, 0.0]) < 0.2


def _compile_and_eval(models, rows, tmp_path):
    import shutil
    if not shutil.which("clang++"):
        pytest.skip("clang++ not installed (the team setup needs none); codegen parity runs where it is")
    hdr = tmp_path / "rules_learned.hpp"
    hdr.write_text(codegen.header(models))
    main = tmp_path / "main.cpp"
    calls = "\n".join(f'        printf("%.12f\\n", rm::{n}_prob(f));' for n in models)
    main.write_text(f'''#include <cstdio>
#include "rules_learned.hpp"
int main() {{
    double f[3];
    while (scanf("%lf %lf %lf", &f[0], &f[1], &f[2]) == 3) {{
{calls}
    }}
}}''')
    exe = tmp_path / "a.out"
    subprocess.run(["clang++", "-std=c++17", "-O2", "-o", str(exe), str(main)], check=True)
    inp = "\n".join(" ".join(repr(v) for v in r) for r in rows)
    out = subprocess.run([str(exe)], input=inp, capture_output=True, text=True, encoding="utf-8",
                         check=True).stdout.split()
    return [float(v) for v in out]


def test_generated_cpp_matches_the_python_reference(tmp_path, res):
    rng = np.random.default_rng(3)
    xs = [[float(rng.uniform(0, 5)), float(rng.integers(0, 12)), float(rng.normal())] for _ in range(300)]
    tree = res["model"]
    logi = learn.export(learn._models(1000)["logistic_l1"]().fit(
        np.array([[r[f] for f in FEATS] for r in synthetic(10, 100)]),
        np.array([r["label"] for r in synthetic(10, 100)])), "logistic_l1", FEATS)
    got = _compile_and_eval({"death": tree, "death_lin": logi}, xs, tmp_path)
    want = []
    for x in xs:
        want += [learn.predict(tree, x), learn.predict(logi, x)]
    assert np.allclose(got, want, atol=1e-9)


def test_conditional_logit_recovers_preferences():
    rng = np.random.default_rng(5)
    rows = []
    true_w = np.array([2.0, 0.5, -1.0])      # eat, room, enemy_reach
    for d in range(1500):
        k = int(rng.integers(2, 5))
        X = np.column_stack([rng.integers(0, 2, k), rng.uniform(0, 6, k), rng.integers(0, 3, k)])
        u = X @ true_w + rng.gumbel(size=k)
        ch = int(np.argmax(u))
        for j in range(k):
            rows.append({"decision": f"d{d}", "game": f"g{d % 30}", "chosen": int(j == ch),
                         "eat": X[j, 0], "room_after": X[j, 1], "enemy_reach": X[j, 2]})
    res = learn.conditional_logit(rows, ["eat", "room_after", "enemy_reach"])
    w = np.array(res["weights"])
    assert w[0] > 0 and w[1] > 0 and w[2] < 0
    assert abs(w[0] / w[1] - 4.0) < 1.5
    assert res["top1_heldout"] > res["chance"] + 0.2
    assert res["useful"]


def test_conditional_logit_flags_a_model_that_does_not_generalise_across_games():
    # half the games prefer eating, half avoid it: no single model transfers to an unseen game
    rng = np.random.default_rng(6)
    rows = []
    for d in range(1200):
        g = d % 20
        sign = 1 if g % 2 else -1
        X = np.column_stack([rng.integers(0, 2, 3), rng.uniform(0, 6, 3)])
        ch = int(np.argmax(sign * 3 * X[:, 0] + rng.gumbel(size=3)))
        for j in range(3):
            rows.append({"decision": f"d{d}", "game": f"g{g}", "chosen": int(j == ch),
                         "eat": X[j, 0], "room_after": X[j, 1]})
    res = learn.conditional_logit(rows, ["eat", "room_after"])
    assert not res["useful"]
