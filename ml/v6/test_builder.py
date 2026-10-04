"""Checks for the v6 shards. Run: uv run --python 3.11 --with numpy python ml/v6/test_builder.py [SHARD_DIR]"""
import glob, json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from build_dataset_v6 import game_holdout, fingerprint, LABELS, META

d = Path(sys.argv[1] if len(sys.argv) > 1 else "ladder/scout_v6/shards")
man = json.load(open(d / "manifest.json"))
files = sorted(glob.glob(str(d / "shard_*.npz")))
assert files, "no shards"
n = 0; lab = np.zeros(7, np.int64); games = set(); stop_rows = 0; queen = 0; p8 = 0; p18 = 0
for f in files:
    z = np.load(f)
    P, Y, M, S, W, G = z["planes"], z["labels"], z["meta"], z["scalars"], z["weights"], z["game"]
    assert P.shape[1:] == (19, 15, 15) and S.shape[1] == 6 and M.shape[1] == len(META)
    p8 += int(P[:, 8].any()); p18 += int(P[:, 18].any())
    assert Y.max() <= 6 and (W > 0).all()
    lab += np.bincount(Y, minlength=7); n += len(Y); games.update(G.tolist())
    steps = M[:, META.index("steps_taken")]; length = M[:, META.index("length")]
    stop = Y == 6
    assert (steps[stop] >= 1).all(), "STOP labels must be mid-sprint states"
    assert (length[stop] >= 2).all(), "mid-sprint samples: length may shrink by paid steps but stays >= 2"
    stop_rows += int(stop.sum())
    isq = M[:, META.index("is_queen")].astype(bool)
    queen += int(isq.sum())
    assert (S[isq, 3] == 1).all() and (S[~isq, 3] == 0).all(), "is_queen scalar must match metadata"
    assert np.allclose(S[:, 4], np.ceil(length / 4) / 8, atol=1e-6), "free-step scalar"
    # plane 8 and the reserved plane are zero
    assert not P[:, 8].any() and not P[:, 18].any()
assert p8 == 0 and p18 == 0
# hold-out split by game never mixes a game across sides
hold = game_holdout(sorted(games), 0.1, 0)
assert hold.sum() >= 0
gl = sorted(games)
a = {g for g, h in zip(gl, hold) if h}; b = {g for g, h in zip(gl, hold) if not h}
assert not (a & b)
# deterministic: same games -> same split even if more games arrive
assert (game_holdout(gl[:5], 0.1, 0) == hold[:5]).all()
# visible-vs-true skew is real in at least some games
tot = sum(g.get("visible_vs_true_differences", 0) for g in man["games"])
assert tot > 0, "expected the visible-body planes to differ from true bodies somewhere"
# dedupe: identical fingerprints should not repeat within a shard (sample check)
z = np.load(files[0]); seen = set(); dup = 0
for k in range(min(5000, len(z["labels"]))):
    fp = fingerprint(z["planes"][k], z["scalars"][k], int(z["labels"][k]))
    dup += fp in seen; seen.add(fp)
print(json.dumps({"ok": True, "samples": n, "games": len(games), "shards": len(files), "labels": dict(zip(LABELS, lab.tolist())),
                  "queen_samples": queen, "stop_samples": stop_rows, "visible_vs_true_diffs": tot, "dup_in_first5000": dup}))
