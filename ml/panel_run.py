"""Run one candidate against several opponents with cloud_tourney.py (Colab/Lightning job entry point).

    python panel_run.py --cand wasm/cand_x.wasm --opps s475,vb17,... --out OUTDIR --maps all --seeds 1 [--seed-base 0]
Writes OUTDIR/<opponent>/summary.json (+ results.jsonl) per opponent, like the Kaggle panel kernels.
"""
import argparse
import subprocess
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--cand", required=True); ap.add_argument("--opps", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--maps", default="all"); ap.add_argument("--seeds", default="1"); ap.add_argument("--seed-base", default="0")
a = ap.parse_args()
for o in a.opps.split(","):
    subprocess.run([sys.executable, "-u", "cloud_tourney.py", "--a", a.cand, "--b", f"wasm/{o}.wasm", "--out", f"{a.out}/{o}",
                    "--maps", a.maps, "--gen", "0", "--seeds", a.seeds, "--seed-base", a.seed_base, "--no-sprt"], check=True)
