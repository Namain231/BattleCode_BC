"""Network policy for the in-process environment (ml/rl_env.py): legal-move masking + sampling or greedy.

Relative actions 0 forward, 1 right, 2 back, 3 left. An action is masked when there is kelp on that side of our head
or the neighbouring cell is occupied (own/ally/enemy body planes 11-13 at the neighbour).
"""
import numpy as np
import torch
import torch.nn.functional as F

from train import Policy

NEIGH = {0: (6, 7), 1: (7, 8), 2: (8, 7), 3: (7, 6)}   # frame cell of the neighbour in each relative direction


def legal_mask(pl, length=0):
    m = np.zeros(5, bool)
    m[4] = length >= 4                     # split: bud a length-2 child (the top teams' 2+2 at length 4)
    for a, (v, u) in NEIGH.items():
        if a == 2:
            continue                      # never reverse into our own neck
        if pl[a, 7, 7]:                   # kelp on that side of the head
            continue
        if pl[11, v, u] or pl[12, v, u] or pl[13, v, u]:
            continue
        m[a] = True
    return m


class NetPolicy:
    def __init__(self, path, greedy=False, device="cpu"):
        ck = torch.load(path, map_location="cpu")
        self.net = Policy(planes=ck.get("planes", 16), scalars=ck.get("scalars", 3),
                          ch=ck.get("channels", 32), hidden=ck.get("hidden", 64), classes=ck.get("classes", 6))
        self.net.load_state_dict(ck["state_dict"]); self.net.eval().to(device)
        self.greedy = greedy; self.device = device
        self.rng = np.random.default_rng()

    @torch.no_grad()
    def __call__(self, pl, sc):
        x = torch.from_numpy(pl[None]).to(self.device).float() / 255
        s = torch.from_numpy(sc[None]).to(self.device)
        logits = self.net(x, s)[0, :5].cpu().numpy()
        m = legal_mask(pl, int(round(sc[0] * 32)))
        if not m.any():
            return 0, (float("nan"), m)
        logits = np.where(m, logits, -1e9)
        p = np.exp(logits - logits.max()); p /= p.sum()
        a = int(p.argmax()) if self.greedy else int(self.rng.choice(5, p=p))
        return a, (float(np.log(p[a] + 1e-12)), m)
