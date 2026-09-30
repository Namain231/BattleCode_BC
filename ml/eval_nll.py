"""Held-out log-loss (NLL) of several policy checkpoints on the same validation games (better proxy than accuracy).

    python ml/eval_nll.py --data ml/data_slope1 --max-samples 1200000 ml/models/policy_v1.pt ml/models/n2a.pt ...

Uses train.py's subsample (seed 0) and its train/val split by game (10%, seed 0), so for a network trained with the
same --data/--max-samples these are exactly its validation games. Reports NLL over all labels and over moves only
(labels 0-3, what the bot uses), plus accuracy.
"""
import argparse

import numpy as np
import torch
import torch.nn.functional as F

from train import Policy, load_shards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    ap.add_argument("--data", default="ml/data_slope1")
    ap.add_argument("--max-samples", type=int, default=1200000)
    ap.add_argument("--scalars", type=int, default=3)
    ap.add_argument("--all", action="store_true", help="evaluate on every game (a held-out folder)")
    a = ap.parse_args()
    P, S, Y, G, M = load_shards(a.data, a.max_samples)
    S = np.ascontiguousarray(S[:, :a.scalars])
    games = np.unique(G)
    rng = np.random.default_rng(0)
    val_games = set(games.tolist()) if a.all else set(rng.choice(games, max(1, int(len(games) * 0.1)), replace=False).tolist())
    va = np.where(np.array([g in val_games for g in G]))[0]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"{len(va)} validation samples from {len(val_games)} games")
    for path in a.models:
        ck = torch.load(path, map_location="cpu")
        model = Policy(planes=ck.get("planes", 16), scalars=a.scalars, ch=ck.get("channels", 32),
                       hidden=ck.get("hidden", 64)).to(dev)
        sd = ck["state_dict"]
        model.load_state_dict({k: (v[:6] if k.startswith("out.") else v) for k, v in sd.items()})
        model.eval()
        nll = nll_mv = 0.0; n_mv = 0; correct = 0
        with torch.no_grad():
            for i in range(0, len(va), 8192):
                ix = va[i:i + 8192]
                x = torch.from_numpy(P[ix]).to(dev).float() / 255
                s = torch.from_numpy(S[ix]).to(dev)
                y = torch.from_numpy(Y[ix]).to(dev)
                lp = F.log_softmax(model(x, s), 1)
                nll += -lp.gather(1, y[:, None]).sum().item()
                correct += (lp.argmax(1) == y).sum().item()
                mv = y < 4
                if mv.any():   # the bot compares moves only: renormalise over the 4 directions
                    lpm = F.log_softmax(lp[mv][:, :4], 1)
                    nll_mv += -lpm.gather(1, y[mv][:, None]).sum().item(); n_mv += int(mv.sum())
        print(f"{path}: NLL {nll / len(va):.4f}  moves-only NLL {nll_mv / n_mv:.4f}  acc {correct / len(va):.3f}")


if __name__ == "__main__":
    main()
