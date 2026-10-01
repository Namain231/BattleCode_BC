"""Generate held-out maps in every style of the Loong/xCirno generator, bounded by the official maps' envelope.

    python tools/gen_style_maps.py OUT_DIR SEED PER_STYLE      (run from the repo root: the envelope reads maps/)

Needs a checkout of github.com/overyonder/the-loong-game; set LOONG_REPO (default ../the-loong-game).
maps_rm_dev/ (seed 11) and maps_rm_test/ (seed 97, held out) were made with 2 per style, plus 6 each from
tools/gen_random_maps.py --dense (prefixed r).
"""
import os, sys, random
from pathlib import Path
sys.path.insert(0, os.environ.get("LOONG_REPO", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "the-loong-game")))
from harness.mapgen import generate, official_envelope, STYLES
env = official_envelope()
out = Path(sys.argv[1]); seed = int(sys.argv[2]); per = int(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
for si, style in enumerate(sorted(STYLES)):
    for k in range(per):
        for attempt in range(20):
            try:
                w = generate(((seed * 100 + si) * 10 + k) * 20 + attempt, env, 4, style=style)
                break
            except RuntimeError:
                continue
        else:
            print("fail", style, k); continue
        p = out / f"g{seed}_{style}_{k}.map"
        p.write_text(w.text())
        print(p.name, w.summary().splitlines()[0] if w.summary() else "", flush=True)
