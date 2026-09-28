"""Distil a large teacher policy into the judge-sized student (Hinton et al. knowledge distillation).

    python ml/distill.py --teacher ml/models/teacher64.pt --data ml/data_v2 --out ml/models/student_v2.pt
        [--T 2.0] [--alpha 0.7] [--max-samples 1100000]

Student = the 32-channel Policy (same inputs as the teacher). Loss = alpha * T^2 * KL(teacher_T || student_T)
+ (1 - alpha) * cross-entropy on the real move. The teacher's soft probabilities carry "which other moves were
also reasonable", which a small network learns from far better than from the one move actually taken.
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
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--data", default="ml/data_v2")
    ap.add_argument("--out", default="ml/models/student_v2.pt")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--max-samples", type=int, default=1100000)
    ap.add_argument("--T", type=float, default=2.0)
    ap.add_argument("--alpha", type=float, default=0.7)
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tk = torch.load(a.teacher, map_location="cpu")
    teacher = Policy(scalars=tk["scalars"], ch=tk.get("channels", 64), hidden=tk.get("hidden", 128)).to(dev)
    teacher.load_state_dict(tk["state_dict"]); teacher.eval()
    P, S, Y, G, M = load_shards(a.data, a.max_samples)
    S = np.ascontiguousarray(S[:, :tk["scalars"]])
    rng = np.random.default_rng(0)
    games = np.unique(G)
    val_games = set(rng.choice(games, max(1, len(games) // 10), replace=False).tolist())
    is_val = np.array([g in val_games for g in G])
    tr, va = np.where(~is_val)[0], np.where(is_val)[0]
    Pt, St, Yt = torch.from_numpy(P), torch.from_numpy(S), torch.from_numpy(Y)
    student = Policy(scalars=S.shape[1]).to(dev)
    opt = torch.optim.AdamW(student.parameters(), lr=2e-3, weight_decay=1e-4)
    steps = a.epochs * (len(tr) // a.batch + 1)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-3, total_steps=steps)
    mp = torch.tensor(MIRROR_PLANES, device=dev); my = MIRROR_LABELS.to(dev)
    for ep in range(a.epochs):
        perm = rng.permutation(tr)
        for i in range(0, len(perm), a.batch):
            ix = torch.from_numpy(perm[i:i + a.batch])
            x = Pt[ix].to(dev).float() / 255; s = St[ix].to(dev); y = Yt[ix].to(dev)
            flip = torch.rand(len(ix), device=dev) < 0.5
            if flip.any():
                x[flip] = x[flip][:, mp].flip(-1); y = torch.where(flip, my[y], y)
            with torch.no_grad():
                soft = F.softmax(teacher(x, s) / a.T, 1)
            out = student(x, s)
            loss = a.alpha * a.T * a.T * F.kl_div(F.log_softmax(out / a.T, 1), soft, reduction="batchmean") + \
                (1 - a.alpha) * F.cross_entropy(out, y)
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
        student.eval(); acc = tacc = 0
        with torch.no_grad():
            for i in range(0, len(va), 4096):
                ix = torch.from_numpy(va[i:i + 4096])
                x = Pt[ix].to(dev).float() / 255; s = St[ix].to(dev); y = Yt[ix].to(dev)
                acc += (student(x, s).argmax(1) == y).sum().item(); tacc += (teacher(x, s).argmax(1) == y).sum().item()
        student.train()
        print(f"epoch {ep + 1}: student acc {acc / len(va):.3f}  (teacher {tacc / len(va):.3f})", flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    torch.save({"state_dict": student.state_dict(), "planes": 16, "scalars": S.shape[1], "channels": 32, "hidden": 64,
                "distilled_from": os.path.basename(a.teacher)}, a.out)
    print("saved", a.out)


if __name__ == "__main__":
    main()
