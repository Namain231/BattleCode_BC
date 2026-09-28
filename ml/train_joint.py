"""One network, two heads: move policy (imitation) + move value (offline Q), sharing the trunk (one forward pass).

    python ml/train_joint.py --data ml/data_v2 --out ml/models/joint_v1.pt [--scalars 3] [--lam 0.5]

Outputs 12 numbers: 0-5 policy logits (forward/right/back/left/split/other), 6-11 predicted 20-round outcome of
each action (meta[:, 4]; only the taken action has a target). Loss = cross-entropy + lam * smooth-L1 on the taken
action's value. Same architecture as ml/train.py Policy with 12 outputs, so ml/export_cpp.py exports it unchanged.
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
    ap.add_argument("--out", default="ml/models/joint_v1.pt")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--max-samples", type=int, default=1100000)
    ap.add_argument("--scalars", type=int, default=0)
    ap.add_argument("--lam", type=float, default=0.5)
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    P, S, Y, G, M = load_shards(a.data, a.max_samples)
    if a.scalars:
        S = np.ascontiguousarray(S[:, :a.scalars])
    fut = np.clip(M[:, 4].astype(np.float32), -8, 8)
    rng = np.random.default_rng(0)
    games = np.unique(G)
    val_games = set(rng.choice(games, max(1, len(games) // 10), replace=False).tolist())
    is_val = np.array([g in val_games for g in G])
    tr, va = np.where(~is_val)[0], np.where(is_val)[0]
    Pt, St, Yt, Ft = (torch.from_numpy(x) for x in (P, S, Y, fut))
    model = Policy(scalars=S.shape[1], classes=12).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    steps = a.epochs * (len(tr) // a.batch + 1)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-3, total_steps=steps)
    mp = torch.tensor(MIRROR_PLANES, device=dev); my = MIRROR_LABELS.to(dev)
    for ep in range(a.epochs):
        perm = rng.permutation(tr)
        for i in range(0, len(perm), a.batch):
            ix = torch.from_numpy(perm[i:i + a.batch])
            x = Pt[ix].to(dev).float() / 255; s = St[ix].to(dev); y = Yt[ix].to(dev); f = Ft[ix].to(dev)
            flip = torch.rand(len(ix), device=dev) < 0.5
            if flip.any():
                x[flip] = x[flip][:, mp].flip(-1); y = torch.where(flip, my[y], y)
            out = model(x, s)
            loss = F.cross_entropy(out[:, :6], y, label_smoothing=0.05) + \
                a.lam * F.smooth_l1_loss(out[:, 6:].gather(1, y[:, None])[:, 0], f)
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
        model.eval(); acc = 0; pv = []
        with torch.no_grad():
            for i in range(0, len(va), 4096):
                ix = torch.from_numpy(va[i:i + 4096])
                out = model(Pt[ix].to(dev).float() / 255, St[ix].to(dev)); y = Yt[ix].to(dev)
                acc += (out[:, :6].argmax(1) == y).sum().item()
                pv.append(out[:, 6:].gather(1, y[:, None])[:, 0].cpu().numpy())
        model.train()
        pv = np.concatenate(pv); fv = fut[va]; lo, hi = np.quantile(pv, [0.2, 0.8])
        print(f"epoch {ep + 1}: policy acc {acc / len(va):.3f}  value corr {np.corrcoef(pv, fv)[0, 1]:.3f}  "
              f"top-20% {fv[pv >= hi].mean():+.2f} bottom-20% {fv[pv <= lo].mean():+.2f}", flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "planes": 16, "scalars": S.shape[1], "channels": 32, "hidden": 64,
                "classes": 12, "kind": "joint"}, a.out)
    print("saved", a.out)


if __name__ == "__main__":
    main()
