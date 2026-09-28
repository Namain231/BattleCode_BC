"""Offline accuracy of inference tricks on one validation set: test-time mirror averaging and model ensembles.

    python ml/eval_tricks.py --data ml/data_v4 --models ml/models/policy_v1b.pt ml/models/policy_v3.pt ...

Validation = 10% of games (same split as train.py, seed 0). Each model sees the scalars it was trained with.
"""
import argparse
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train import Policy, load_shards, MIRROR_PLANES, MIRROR_LABELS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="ml/data_v4")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--max-samples", type=int, default=600000)
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    P, S, Y, G, M = load_shards(a.data, a.max_samples)
    rng = np.random.default_rng(0)
    games = np.unique(G)
    val_games = set(rng.choice(games, max(1, len(games) // 10), replace=False).tolist())
    va = np.array([g in val_games for g in G])
    P, S, Y = P[va], S[va], Y[va]
    y = torch.from_numpy(Y).to(dev)
    probs, probs_tta = [], []
    for path in a.models:
        ck = torch.load(path, map_location="cpu")
        npl, nsc = ck.get("planes", 16), ck.get("scalars", 3)
        m = Policy(planes=npl, scalars=nsc, ch=ck.get("channels", 32), hidden=ck.get("hidden", 64),
                   classes=ck.get("classes", 6)).to(dev)
        m.load_state_dict(ck["state_dict"]); m.eval()
        mp = torch.tensor(MIRROR_PLANES[:8] + list(range(8, npl)), device=dev)
        my = MIRROR_LABELS.to(dev)
        pr, pt = [], []
        with torch.no_grad():
            for i in range(0, len(Y), 4096):
                x = torch.from_numpy(P[i:i + 4096, :npl]).to(dev).float() / 255
                s = torch.from_numpy(np.ascontiguousarray(S[i:i + 4096, :nsc])).to(dev)
                p = F.softmax(m(x, s)[:, :6], 1)
                pm = F.softmax(m(x[:, mp].flip(-1), s)[:, :6], 1)[:, my]   # mirrored input, labels mapped back
                pr.append(p); pt.append(0.5 * (p + pm))
        pr, pt = torch.cat(pr), torch.cat(pt)
        probs.append(pr); probs_tta.append(pt)
        print(f"{os.path.basename(path):24s} acc {(pr.argmax(1) == y).float().mean():.4f}   with mirror TTA "
              f"{(pt.argmax(1) == y).float().mean():.4f}", flush=True)
    if len(probs) > 1:
        e = torch.stack(probs).mean(0); et = torch.stack(probs_tta).mean(0)
        print(f"{'ensemble of ' + str(len(probs)):24s} acc {(e.argmax(1) == y).float().mean():.4f}   with mirror TTA "
              f"{(et.argmax(1) == y).float().mean():.4f}")


if __name__ == "__main__":
    main()
