"""SPSA tuning of struct Params (Stockfish-style): each iteration plays theta+ vs theta- and steps towards the winner.

    python -u tools/spsa.py --base viper_nn --iters 60 --games 8 -j 8 [--resume]

Every parameter i gets a perturbation c_i (about 10% of its value) and a random sign d_i. theta+ = theta + c*d and
theta- = theta - c*d are written into two bot copies, played against each other on maze + random maps from both
sides (tools/tourney.py), and theta_i += a * c_i * d_i * r where r = (wins+ - wins-) / games. a decays slowly.
Maze maps only: the open maps reset p2Drone/minerGamma at runtime anyway. State and every iteration are logged in
ladder/spsa_state.json and ladder/spsa_log.jsonl; the current theta can be written into a bot with --emit DIR.
"""
import argparse
import json
import math
import pathlib
import random
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "ladder" / "spsa_state.json"
LOG = ROOT / "ladder" / "spsa_log.jsonl"
MAPS = ["autarky", "devil", "trauma", "trophy", "queen_of_spades", "default", "dilemma"]
GEN = [f"maps_gen/gen_{i:03d}" for i in (3, 11, 19, 31, 42, 58, 77, 90, 111, 123, 147, 164, 199, 233, 250, 281)]
# name: (c as a fraction of the value, min, max, integer?)
TUNE = {
    "gamma": (0.02, 0.6, 0.97, False), "wField": (0.15, 0.02, 2, False), "wTarget": (0.12, 0.1, 5, False),
    "decayTau": (0.15, 10, 300, False), "enemyCloser": (0.12, 0.05, 1, False), "enemyTie": (0.1, 0.1, 1, False),
    "p2Drone": (0.2, 0.02, 0.8, False), "p3Drone": (0.2, 0.01, 0.5, False), "deathExtra": (0.15, 2, 100, False),
    "spaceBonus": (0.2, 0, 5, False), "wPocket": (0.2, 0, 6, False), "wProgress": (0.15, 0, 4, False),
    "minerGamma": (0.03, 0.6, 0.97, False), "minerFarmCap": (0.2, 0.2, 5, False), "wHunt": (0.15, 0, 8, False),
    "wNN": (0.15, 0.3, 6, False), "feedFrom": (0.05, 250, 450, True), "protectFrom": (0.05, 300, 480, True),
    "feedRadius": (0.15, 4, 30, True),
}


def params_block(src):
    i = src.index("struct Params {"); j = src.index("};", i)
    return i, j


def read_theta(src):
    i, j = params_block(src)
    blk = src[i:j]
    th = {}
    for k in TUNE:
        m = re.search(rf"\b{k}\s*=\s*(-?[\d.]+)", blk)
        th[k] = float(m.group(1))
    return th


def write_bot(base, dest, theta, tag):
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(base, dest)
    p = dest / "main.cpp"
    src = p.read_text(encoding="utf-8")
    i, j = params_block(src)
    blk = src[i:j]
    for k, v in theta.items():
        val = str(int(round(v))) if TUNE[k][3] else f"{v:.5g}"
        blk = re.sub(rf"\b({k}\s*=\s*)(-?[\d.]+)", lambda m: m.group(1) + val, blk, count=1)
    src = f"// spsa {tag}\n" + src[:i] + blk + src[j:]   # first line changes: forces a rebuild
    p.write_text(src, encoding="utf-8", newline="\n")


def match(a, b, games, jobs, rng):
    maps = rng.sample(MAPS, 2) + rng.sample(GEN, 2)          # 4 maps x 2 sides x seeds
    seeds = max(1, games // (2 * len(maps)))
    r = subprocess.run([sys.executable, "tools/tourney.py", str(a), str(b), "--maps", ",".join(maps), "--seeds",
                        str(seeds), "-j", str(jobs)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    m = re.search(r"(\d+)W (\d+)L (\d+)D of (\d+)", r.stdout)
    if not m:
        raise RuntimeError(r.stdout[-500:] + r.stderr[-500:])
    w, l, d, n = map(int, m.groups())
    return w, l, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="viper_nn")
    ap.add_argument("--iters", type=int, default=60)
    ap.add_argument("--games", type=int, default=8)
    ap.add_argument("-j", type=int, default=8)
    ap.add_argument("--a", type=float, default=0.6, help="step size (in units of c) at iteration 0")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--emit", default="", help="write the current theta into this bot directory and exit")
    a = ap.parse_args()
    base = ROOT / a.base
    if a.resume or a.emit:
        st = json.loads(STATE.read_text())
    else:
        th0 = read_theta((base / "main.cpp").read_text(encoding="utf-8"))
        st = {"theta": th0, "theta0": th0, "iter": 0}
    if a.emit:
        write_bot(base, ROOT / a.emit, st["theta"], f"theta after {st['iter']} iterations")
        print(json.dumps(st["theta"], indent=1)); return
    rng = random.Random(st["iter"] + 12345)
    plus, minus = ROOT / "spsa_plus", ROOT / "spsa_minus"
    for k in range(st["iter"], st["iter"] + a.iters):
        th = st["theta"]
        c = {n: max(TUNE[n][0] * abs(st["theta0"][n]), 1.0 if TUNE[n][3] else 1e-3) for n in TUNE}
        d = {n: rng.choice((-1, 1)) for n in TUNE}
        clip = lambda n, v: min(TUNE[n][2], max(TUNE[n][1], v))
        tp = {n: clip(n, th[n] + c[n] * d[n]) for n in TUNE}
        tm = {n: clip(n, th[n] - c[n] * d[n]) for n in TUNE}
        write_bot(base, plus, tp, f"+ {k}"); write_bot(base, minus, tm, f"- {k}")
        w, l, n = match(plus.name, minus.name, a.games, a.j, rng)
        r = (w - l) / n
        step = a.a / (1 + k / 20) ** 0.6
        st["theta"] = {nm: clip(nm, th[nm] + step * c[nm] * d[nm] * r) for nm in TUNE}
        st["iter"] = k + 1
        STATE.write_text(json.dumps(st, indent=1))
        with open(LOG, "a") as f:
            f.write(json.dumps({"iter": k, "w": w, "l": l, "n": n, "theta": st["theta"]}) + "\n")
        print(f"iter {k}: +{w} -{l} of {n}  step {step:.3f}", flush=True)


if __name__ == "__main__":
    main()
