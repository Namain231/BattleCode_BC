"""Offline action-value (Q) network: predict a move's 20-round outcome from top teams' games.

    python ml/train_q.py --data ml/data_v2 --out ml/models/q_v1.pt [--max-samples 1100000]

Same inputs and trunk as the policy network (ml/train.py Policy); 6 outputs = predicted outcome score of each
action (forward/right/back/left/split/other). Only the action actually taken has a target (meta[:, 4]: the
dragon's length 20 rounds later + children split off - length now, 0-length if it died), so the loss is the
squared error on that action. Reports how well it ranks: correlation of prediction and outcome on held-out games,
and the outcome of moves it rates best vs worst.
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
    ap.add_argument("--data", default="ml/data_v2")
    ap.add_argument("--out", default="ml/models/q_v1.pt")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--max-samples", type=int, default=1100000)
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    P, S, Y, G, M = load_shards(a.data, a.max_samples)
    fut = np.clip(M[:, 4].astype(np.float32), -8, 8)
    rng = np.random.default_rng(0)
    games = np.unique(G)
    val_games = set(rng.choice(games, max(1, len(games) // 10), replace=False).tolist())
    is_val = np.array([g in val_games for g in G])
    tr, va = np.where(~is_val)[0], np.where(is_val)[0]
    print(f"{len(Y)} samples, outcome mean {fut.mean():.2f} std {fut.std():.2f}", flush=True)
    Pt, St, Yt, Ft = (torch.from_numpy(x) for x in (P, S, Y, fut))
    model = Policy(scalars=S.shape[1]).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    mp = torch.tensor(MIRROR_PLANES, device=dev); my = MIRROR_LABELS.to(dev)
    for ep in range(a.epochs):
        perm = rng.permutation(tr); tot = 0.0
        for i in range(0, len(perm), a.batch):
            ix = torch.from_numpy(perm[i:i + a.batch])
            x = Pt[ix].to(dev).float() / 255; s = St[ix].to(dev); y = Yt[ix].to(dev); f = Ft[ix].to(dev)
            flip = torch.rand(len(ix), device=dev) < 0.5
            if flip.any():
                x[flip] = x[flip][:, mp].flip(-1); y = torch.where(flip, my[y], y)
            q = model(x, s).gather(1, y[:, None])[:, 0]
            loss = F.smooth_l1_loss(q, f)
            opt.zero_grad(); loss.backward(); opt.step(); tot += loss.item() * len(ix)
        # held-out: correlation between predicted value of the taken move and its outcome
        model.eval(); preds = []
        with torch.no_grad():
            for i in range(0, len(va), 4096):
                ix = torch.from_numpy(va[i:i + 4096])
                q = model(Pt[ix].to(dev).float() / 255, St[ix].to(dev)).gather(1, Yt[ix].to(dev)[:, None])[:, 0]
                preds.append(q.cpu().numpy())
        model.train()
        pv = np.concatenate(preds); fv = fut[va]
        r = np.corrcoef(pv, fv)[0, 1]
        lo, hi = np.quantile(pv, [0.2, 0.8])
        print(f"epoch {ep + 1}: loss {tot / len(tr):.4f}  held-out corr {r:.3f}  outcome of moves rated "
              f"top-20% {fv[pv >= hi].mean():+.2f} vs bottom-20% {fv[pv <= lo].mean():+.2f}", flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "planes": 16, "scalars": S.shape[1], "channels": 32, "hidden": 64,
                "kind": "q"}, a.out)
    print("saved", a.out)


if __name__ == "__main__":
    main()
