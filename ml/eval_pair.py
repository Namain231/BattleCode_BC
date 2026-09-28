"""Head-to-head of two network checkpoints in the in-process engine (greedy play, every map, sides alternating).

    python ml/eval_pair.py ml/models/sil_r1.pt ml/models/policy_v1b.pt --games 40 --workers 5

Any checkpoint works (imitation 6-output, RL 12-output). Seeds are paired: game k and its side-swapped twin use the
same seed, so pearl luck cancels. Prints A's wins/ties/losses and the per-map record.
"""
import argparse
import collections
import multiprocessing as mp
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rl_train  # noqa: E402
from train import Policy  # noqa: E402


def as_rl_state(path):
    """A checkpoint as the 12-output state dict the RL worker plays (imitation heads copied, value row zero)."""
    sd = torch.load(path, map_location="cpu")["state_dict"]
    net = Policy(scalars=3, classes=12); out = net.state_dict()
    for k, v in sd.items():
        if k.startswith("out."):
            out[k][:v.shape[0]] = v
        else:
            out[k] = v
    return {k: v.clone() for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--workers", type=int, default=5)
    a = ap.parse_args()
    sa, sb = as_rl_state(a.a), as_rl_state(a.b)
    maps = rl_train.MAPS
    jobs = []
    for k in range(a.games // 2):
        m, seed = maps[k % len(maps)], 1000 + k
        jobs += [(sa, sb, m, seed, "A", True, 0), (sa, sb, m, seed, "B", True, 0)]   # same seed, sides swapped
    with mp.Pool(a.workers, maxtasksperchild=4) as pool:
        res = pool.map(rl_train.worker, jobs)
    tot = collections.Counter(); per = collections.defaultdict(lambda: [0, 0])
    for w, _, m in res:
        tot[w] += 1; per[m][0] += w > 0; per[m][1] += 1
    n = len(res)
    print(f"{os.path.basename(a.a)} vs {os.path.basename(a.b)}: {tot[1.0]}W {tot[0.0]}T {tot[-1.0]}L "
          f"= {tot[1.0] / n:.3f} over {n} games")
    print("  " + "  ".join(f"{m[:6]} {w}/{g}" for m, (w, g) in per.items()))


if __name__ == "__main__":
    main()
