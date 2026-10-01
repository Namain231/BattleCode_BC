import subprocess
import sys
from conftest import ensure_fixtures
ensure_fixtures()
from conftest import ROOT

DATA = ROOT / "tests" / "data"


def rm(*args, cwd):
    import os
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run([sys.executable, "-m", "rulemine", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", check=True, env=env).stdout


def test_extract_contrast_learn_codegen_compile(tmp_path):
    idx, root = str(DATA / "index.json"), str(DATA / "replays")
    top, ours = tmp_path / "death_top.csv", tmp_path / "death_ours.csv"
    rm("extract", "--index", idx, "--root", root, "--decision", "death", "--teams", "SSS,cheji bt",
       "--out", str(top), "-j", "2", cwd=ROOT)
    rm("extract", "--index", idx, "--root", root, "--decision", "death", "--teams", "Bhole Chature",
       "--out", str(ours), cwd=ROOT)
    assert top.stat().st_size > 0 and ours.stat().st_size > 0
    rep = rm("contrast", "--decision", "death", "--top", str(top), "--ours", str(ours),
             "--out", str(tmp_path / "c.md"), cwd=ROOT)
    assert "Overall rate" in rep
    res = tmp_path / "death.json"
    out = rm("learn", "--decision", "death", "--data", str(top), "--out", str(res), cwd=ROOT)
    assert "Picked" in out
    hdr = tmp_path / "rules_learned.hpp"
    rm("codegen", str(res), "--out", str(hdr), cwd=ROOT)
    main = tmp_path / "m.cpp"
    main.write_text('#include "rules_learned.hpp"\nint main(){ double f[rm::death_NF] = {}; return rm::death_prob(f) < 0; }\n')
    import shutil
    if shutil.which("clang++"):
        subprocess.run(["clang++", "-std=c++17", "-fsyntax-only", "-I", str(tmp_path), str(main)], check=True)


def test_bceval_context_is_symmetric_and_evalpair_is_zero_on_identical_games(tmp_path):
    import shutil
    from rulemine import evalstate, evalpair
    if not evalstate.available():
        import pytest
        pytest.skip("bceval/pycapnp not installed")
    rp = str(DATA / "replays" / "690143.replay")
    a, b = evalstate.series(rp, 0), evalstate.series(rp, 1)
    assert a and all(abs(a[r] + b[r] - 1) < 1e-9 for r in a)
    for d in ("cand", "ctrl"):
        (tmp_path / d).mkdir()
        shutil.copy(rp, tmp_path / d / "schooltime_1_A.replay")
    res = evalpair.compare(str(tmp_path / "cand"), str(tmp_path / "ctrl"))
    assert res["paired"] == 1 and res["flips"] == [0, 0]
    assert all(abs(m[0]) < 1e-12 for m in res["metrics"].values())


def test_evalpair_counts_only_our_sides_feed_indicators(monkeypatch):
    # dragons 0 (team A) and 1 (team B) start on the map; 2 is A's split child. Only A's FEED lines count for side A.
    from rulemine import evalpair, evalstate
    fake = {"map": "MAP 4 4\nDRAGON 0 1 0 0\nDRAGON 1 1 3 3\n",
            "result": {"winner": 0, "A": {"longest": 5}, "B": {"longest": 3}},
            "events": [{"kind": "dragonIndicator", "id": 0, "text": "FEED 2"},
                       {"kind": "dragonSplit", "parent": 0, "child": 2, "team": 0},
                       {"kind": "dragonIndicator", "id": 2, "text": "FEED"},
                       {"kind": "dragonIndicator", "id": 1, "text": "FEED 0"},
                       {"kind": "dragonIndicator", "id": 2, "text": "L3 FEEDING"}]}
    monkeypatch.setattr(evalpair, "decode_lite", lambda path, kinds: fake)
    monkeypatch.setattr(evalstate, "series", lambda *a, **k: None)
    monkeypatch.setattr(evalstate, "longest", lambda *a, **k: None)
    a = evalpair.measure("x/trauma_1_A.replay", (400,))
    b = evalpair.measure("x/trauma_1_B.replay", (400,))
    assert (a["feeds"], b["feeds"]) == (2, 1)
    assert (a["win"], a["margin"], b["margin"]) == (1.0, 2, -2)
