"""Train the move-imitation network on ml/data shards (runs locally on CUDA or on Colab).

    python ml/train.py --data ml/data --out ml/models/policy_v1.pt [--epochs 12] [--batch 1024]

Held-out validation is split by GAME (never by sample) so the score is honest. Every training batch is also
mirrored left<->right (labels right<->left, wall/portal planes right<->left): the rules are mirror-symmetric,
so this doubles the data for free (the Hungry Geese / Lux AI imitation winners all used symmetry augmentation).
The network is sized for the judge: ~125k weights, ~2.3M multiply-adds per decision.
"""
import argparse
import glob
import json
import os
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

LABELS = ["forward", "right", "back", "left", "split", "other"]
MIRROR_PLANES = [0, 3, 2, 1, 4, 7, 6, 5] + list(range(8, 16))   # swap right/left sides of kelp and portal
MIRROR_LABELS = torch.tensor([0, 3, 2, 1, 4, 5])


class Policy(nn.Module):
    def __init__(self, planes=16, scalars=3, ch=32, hidden=64, classes=6):
        super().__init__()
        self.c1 = nn.Conv2d(planes + scalars, ch, 3, padding=1)
        self.c2 = nn.Conv2d(ch, ch, 3, padding=1)
        self.c3 = nn.Conv2d(ch, ch, 3, padding=1)
        self.fc = nn.Linear(ch * 7 * 7, hidden)
        self.out = nn.Linear(hidden + scalars, classes)

    def forward(self, planes, scalars):
        b = planes.shape[0]
        s = scalars[:, :, None, None].expand(b, scalars.shape[1], planes.shape[2], planes.shape[3])
        x = F.relu(self.c1(torch.cat([planes, s], 1)))          # 15x15
        x = F.avg_pool2d(x, 2)                                   # 7x7
        x = F.relu(self.c2(x))
        x = F.relu(self.c3(x) + x)
        x = F.relu(self.fc(x.flatten(1)))
        return self.out(torch.cat([x, scalars], 1))


def load_shards(path, max_samples=0, seed=0):
    """Fill one preallocated array shard by shard (no 2x concatenation peak); optional random subsample."""
    files = sorted(glob.glob(os.path.join(path, "shard_*.npz")))
    sizes = [len(np.load(f)["labels"]) for f in files]
    total = sum(sizes)
    keep = min(total, max_samples) if max_samples else total
    rng = np.random.default_rng(seed)
    d0 = np.load(files[0]); ns = d0["scalars"].shape[1]; nm = d0["meta"].shape[1]
    npl = d0["planes"].shape[1]
    P = np.empty((keep, npl, 15, 15), np.uint8); S = np.empty((keep, ns), np.float32)
    Y = np.empty(keep, np.int64); G = np.empty(keep, np.int64); M = np.empty((keep, nm), np.int16)
    at = 0
    for f, n in zip(files, sizes):
        d = np.load(f)
        take = n if keep == total else min(n, int(round(n * keep / total)), keep - at)
        ix = np.sort(rng.choice(n, take, replace=False)) if take < n else slice(None)
        k = take
        P[at:at + k] = d["planes"][ix]; S[at:at + k] = d["scalars"][ix]; Y[at:at + k] = d["labels"][ix]; G[at:at + k] = d["game"][ix]
        M[at:at + k] = d["meta"][ix]
        at += k
    return P[:at], S[:at], Y[:at], G[:at], M[:at]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", default=["ml/data"],
                    help="one or more shard folders; --max-samples applies to each (e.g. top teams + self-play, 50/50)")
    ap.add_argument("--init", default="", help="fine-tune from this checkpoint instead of training from scratch")
    ap.add_argument("--out", default="ml/models/policy_v1.pt")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--max-samples", type=int, default=0, help="random subsample to fit RAM (0 = all)")
    ap.add_argument("--channels", type=int, default=32)
    ap.add_argument("--scalars", type=int, default=0, help="keep only the first N scalar inputs (0 = all)")
    ap.add_argument("--team-cond", type=int, default=0,
                    help="append a one-hot of the demonstrating team (the N most frequent teams + other) as scalars")
    ap.add_argument("--only-teams", default="", help="train only on these team ids (comma separated)")
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--max-round", type=int, default=500, help="train/validate only on decisions before this round")
    ap.add_argument("--awr-beta", type=float, default=0.0,
                    help="advantage weighting: weight = clip(exp(beta * future_score / std), 0.3, 3); 0 = plain imitation")
    ap.add_argument("--game-weights", default="", help="JSON {game id: weight}; samples of other games weigh 1")
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    parts = [load_shards(d, a.max_samples) for d in a.data]
    ns = min(p[1].shape[1] for p in parts)             # self-play shards and older ones may carry fewer scalars
    P, S, Y, G, M = (np.concatenate([p[k] if k != 1 else p[1][:, :ns] for p in parts]) for k in range(5))
    del parts
    if a.max_round < 500:
        sel = S[:, 1] * 500 < a.max_round
        P, S, Y, G, M = P[sel], S[sel], Y[sel], G[sel], M[sel]
    if a.scalars:
        S = np.ascontiguousarray(S[:, :a.scalars])
    if a.team_cond or a.only_teams:   # which team demonstrated each sample (from the scout indexes)
        import json as _json
        g2t = {}
        for ix in glob.glob("ladder/*/index.json") + glob.glob("ladder/latest_index*.json"):
            try:
                entries = _json.load(open(ix, encoding="utf-8"))
            except Exception:
                continue
            for g in entries if isinstance(entries, list) else []:
                if isinstance(g, dict) and g.get("teamId") and g.get("game") is not None:
                    g2t[int(g["game"])] = int(g["teamId"])
        T = np.array([g2t.get(int(g), -1) for g in G])
        if a.only_teams:
            keep_t = [int(t) for t in a.only_teams.split(",")]
            sel = np.isin(T, keep_t)
            P, S, Y, G, M, T = P[sel], S[sel], Y[sel], G[sel], M[sel], T[sel]
            print(f"only teams {keep_t}: {sel.sum()} samples")
        if a.team_cond:
            ids, cnt = np.unique(T, return_counts=True)
            top = [int(t) for t in ids[np.argsort(-cnt)][:a.team_cond]]
            oh = np.zeros((len(T), a.team_cond + 1), np.float32)
            for k, t in enumerate(top):
                oh[T == t, k] = 1
            oh[~np.isin(T, top), a.team_cond] = 1
            S = np.ascontiguousarray(np.concatenate([S, oh], 1))
            print("team conditioning on", top)
    wts = np.ones(len(Y), np.float32)
    if a.awr_beta > 0 and M.shape[1] >= 5:
        fut = M[:, 4].astype(np.float32)
        wts = np.clip(np.exp(a.awr_beta * fut / max(1e-6, fut.std())), 0.3, 3.0).astype(np.float32)
        print(f"advantage weights: mean {wts.mean():.2f}, share <1: {(wts < 1).mean():.2f}")
    if a.game_weights:
        gw = {int(k): float(v) for k, v in json.load(open(a.game_weights)).items()}
        wts *= np.array([gw.get(int(g), 1.0) for g in G], np.float32)
        print(f"game weights: mean {wts.mean():.2f}, min {wts.min():.2f}, max {wts.max():.2f}")
    games = np.unique(G)
    rng = np.random.default_rng(0)
    val_games = set(rng.choice(games, max(1, int(len(games) * a.val_frac)), replace=False).tolist())
    is_val = np.array([g in val_games for g in G])
    print(f"{len(Y)} samples from {len(games)} games on {dev}; val {is_val.sum()} ({len(val_games)} games)")
    print("label share:", {LABELS[i]: round(float((Y == i).mean()), 3) for i in range(6)})
    tr, va = np.where(~is_val)[0], np.where(is_val)[0]
    # uint8 planes live on the GPU (small); scaled to [0, 1] per batch
    # keep the data on the GPU when it fits (Colab), otherwise stream batches from RAM (4 GB laptop GPU)
    ddev = dev if dev == "cuda" and P.nbytes < 0.35 * torch.cuda.get_device_properties(0).total_memory else "cpu"
    print("data kept on", ddev)
    Pt = torch.from_numpy(P).to(ddev); St = torch.from_numpy(S).to(ddev); Yt = torch.from_numpy(Y).to(ddev)
    Wt = torch.from_numpy(wts).to(ddev)
    model = Policy(planes=P.shape[1], scalars=S.shape[1], ch=a.channels, hidden=a.hidden).to(dev)
    if a.init:
        sd = torch.load(a.init, map_location="cpu")["state_dict"]
        model.load_state_dict({k: (v[:6] if k.startswith("out.") else v) for k, v in sd.items()})
        print("fine-tuning from", a.init)
    print("parameters:", sum(p.numel() for p in model.parameters()))
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    steps = a.epochs * (len(tr) // a.batch + 1)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, a.lr, total_steps=steps)
    mirror_p = torch.tensor(MIRROR_PLANES[:8] + list(range(8, P.shape[1])), device=dev)
    mirror_y = MIRROR_LABELS.to(dev)

    def evaluate():
        model.eval(); correct = 0; per = np.zeros((6, 2))
        with torch.no_grad():
            for i in range(0, len(va), 4096):
                ix = torch.from_numpy(va[i:i + 4096]).to(ddev)
                pred = model(Pt[ix].to(dev).float() / 255, St[ix].to(dev)).argmax(1)
                y = Yt[ix].to(dev)
                correct += (pred == y).sum().item()
                for c in range(6):
                    m = y == c
                    per[c] += [(pred[m] == c).sum().item(), m.sum().item()]
        model.train()
        base = max((Y[va] == c).mean() for c in range(6))
        return correct / len(va), base, {LABELS[c]: round(per[c, 0] / per[c, 1], 3) for c in range(6) if per[c, 1]}

    for ep in range(a.epochs):
        t0 = time.time(); perm = torch.from_numpy(rng.permutation(tr)).to(ddev); tot = 0.0
        for i in range(0, len(perm), a.batch):
            ix = perm[i:i + a.batch]
            x, s, y = Pt[ix].to(dev, non_blocking=True).float() / 255, St[ix].to(dev), Yt[ix].to(dev)
            flip = torch.rand(len(ix), device=dev) < 0.5
            if flip.any():
                x[flip] = x[flip][:, mirror_p].flip(-1)
                if s.shape[1] >= 6:   # previous turn right/left (scalars 4, 5) swap in the mirror too
                    s = s.clone(); s[flip, 4], s[flip, 5] = s[flip, 5].clone(), s[flip, 4].clone()
                y = torch.where(flip, mirror_y[y], y)
            wb = Wt[ix].to(dev)
            loss = (F.cross_entropy(model(x, s), y, label_smoothing=0.05, reduction="none") * wb).sum() / wb.sum()
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
            tot += loss.item() * len(ix)
        acc, base, per = evaluate()
        print(f"epoch {ep + 1}: loss {tot / len(tr):.4f}  val acc {acc:.3f} (always-majority {base:.3f})  per class {per}"
              f"  [{time.time() - t0:.0f}s]", flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "planes": P.shape[1], "scalars": S.shape[1], "channels": a.channels,
                "hidden": a.hidden, "max_round": a.max_round}, a.out)
    print("saved", a.out)


if __name__ == "__main__":
    main()
