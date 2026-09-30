"""Where is each network stronger? Held-out log-loss of two nets and their blends, by map and game phase.

    python ml/ens_eval.py --data ml/data_eval1 --index ladder/slope/index_eval.json models/n4.pt models/policy_v1.pt

Blends: product of experts with weight w on the second net (log p = (1-w) log p1 + w log p2, renormalised) for
w in 0..1, and a per-state confidence mix (each net weighted by exp(-entropy)). Moves only (labels 0-3), renormalised
over the 4 directions, as the bot uses them.
"""
import argparse
import collections
import json

import numpy as np
import torch
import torch.nn.functional as F

from train import Policy, load_shards


def load(path, dev):
    ck = torch.load(path, map_location="cpu")
    m = Policy(planes=ck.get("planes", 16), scalars=3, ch=ck.get("channels", 32), hidden=ck.get("hidden", 64)).to(dev)
    m.load_state_dict({k: (v[:6] if k.startswith("out.") else v) for k, v in ck["state_dict"].items()})
    return m.eval()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("m1"); ap.add_argument("m2")
    ap.add_argument("--data", default="ml/data_eval1")
    ap.add_argument("--index", default="ladder/slope/index_eval.json")
    ap.add_argument("--max-samples", type=int, default=1500000)
    a = ap.parse_args()
    gmap = {int(g["game"]): g["map"] for g in json.load(open(a.index, encoding="utf-8"))}
    P, S, Y, G, M = load_shards(a.data, a.max_samples)
    keep = Y < 4
    P, S, Y, G = P[keep], np.ascontiguousarray(S[keep, :3]), Y[keep], G[keep]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    n1, n2 = load(a.m1, dev), load(a.m2, dev)
    L1, L2 = [], []
    with torch.no_grad():
        for i in range(0, len(Y), 8192):
            x = torch.from_numpy(P[i:i + 8192]).to(dev).float() / 255
            s = torch.from_numpy(S[i:i + 8192]).to(dev)
            L1.append(F.log_softmax(n1(x, s)[:, :4], 1).cpu()); L2.append(F.log_softmax(n2(x, s)[:, :4], 1).cpu())
    L1, L2 = torch.cat(L1), torch.cat(L2)
    y = torch.from_numpy(Y).long()
    rnd = S[:, 1] * 500
    phase = np.where(rnd < 100, "r0-99", np.where(rnd < 300, "r100-299", "r300+"))
    maps = np.array([gmap.get(int(g), "?") for g in G])
    blends = {f"w{w:.2f}": F.log_softmax((1 - w) * L1 + w * L2, 1) for w in (0.0, 0.25, 0.5, 0.75, 1.0)}
    e1 = -(L1.exp() * L1).sum(1, keepdim=True); e2 = -(L2.exp() * L2).sum(1, keepdim=True)
    c1, c2 = torch.exp(-e1), torch.exp(-e2)
    blends["conf"] = F.log_softmax((c1 * L1 + c2 * L2) / (c1 + c2), 1)
    nll = {k: -v.gather(1, y[:, None]).squeeze(1).numpy() for k, v in blends.items()}
    names = list(nll)
    print(f"{len(Y)} moves; columns: {names}  (w = weight on {a.m2})")
    def row(label, m):
        print(f"{label:22s} n={int(m.sum()):7d}  " + "  ".join(f"{nll[k][m].mean():.4f}" for k in names)
              + f"   best {min(names, key=lambda k: nll[k][m].mean())}")
    row("ALL", np.ones(len(Y), bool))
    for ph in ("r0-99", "r100-299", "r300+"):
        row(ph, phase == ph)
    for mp in sorted(set(maps)):
        row(mp, maps == mp)


if __name__ == "__main__":
    main()
