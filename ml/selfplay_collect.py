"""Self-play games for filtered self-imitation (SIL / ReST): the cheap alternative to PPO on a laptop.

    python ml/selfplay_collect.py --model ml/models/policy_v1b.pt --games 200 --workers 3 --out ladder/selfplay

Both teams play the imitation network, sampling moves from its softmax (temperature --temp) so the games differ.
Every game is saved as a real engine replay and listed in <out>/index.json with the winner as "side", so
`ml/build_dataset.py --index <out>/index.json` extracts the WINNING team's decisions with exactly the same
features as the top teams' data (the in-process environment only approximates body order; the replay is exact).
Training on a 50/50 mix of these and the top teams' data (RLPD's symmetric sampling) nudges the network towards
the choices that won, without PPO's noisy gradient.
"""
import argparse
import json
import multiprocessing as mp
import os
import pathlib
import random
import sys
import time

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rl_train import MAPS, ROOT, free_gb  # noqa: E402
from train import Policy  # noqa: E402


class TempSampler:
    """Masked sampling from the imitation network at a temperature (CPU, batch 1)."""

    def __init__(self, ck, temp):
        self.net = Policy(planes=ck.get("planes", 16), scalars=ck.get("scalars", 3),
                          ch=ck.get("channels", 32), hidden=ck.get("hidden", 64),
                          classes=ck["state_dict"]["out.weight"].shape[0])
        self.net.load_state_dict(ck["state_dict"]); self.net.eval()
        self.temp = temp; self.rng = np.random.default_rng()

    @torch.no_grad()
    def __call__(self, pl, sc):
        from rl_policy import legal_mask
        logits = self.net(torch.from_numpy(pl[None]).float() / 255, torch.from_numpy(sc[None]))[0, :5].numpy()
        m = legal_mask(pl, int(round(sc[0] * 32)))
        if not m.any():
            return 0, None
        z = np.where(m, logits / self.temp, -1e9)
        p = np.exp(z - z.max()); p /= p.sum()
        return int(self.rng.choice(5, p=p)), None


def play(job):
    model, temp, map_name, seed, path = job
    torch.set_num_threads(1)
    from rl_env import Game
    ck = torch.load(model, map_location="cpu")
    pa, pb = TempSampler(ck, temp), TempSampler(ck, temp)
    g = Game(os.path.join(ROOT, "maps", f"{map_name}.map"), {"A": pa, "B": pb}, seed, record=())
    from unswbc.engine import EngineModule
    eng = EngineModule()
    res = eng.run(g.map_bytes, g.reply, g.death, g.spawn, lambda line: None, 0, seed)
    pathlib.Path(path).write_bytes(eng.replay("selfA", "selfB"))
    return res.winner, map_name, res.rounds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="ml/models/policy_v1b.pt")
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--temp", type=float, default=1.0)
    ap.add_argument("--out", default="ladder/selfplay")
    ap.add_argument("--min-free-gb", type=float, default=3.0)
    ap.add_argument("--maps", default="", help="comma-separated map names (default: all 10)")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ix_path = out / "index.json"
    index = json.load(open(ix_path)) if ix_path.exists() else []
    base = 10 ** 9 + len(index)          # game ids that cannot clash with the ladder's
    maps = a.maps.split(",") if a.maps else MAPS
    jobs = []
    for k in range(a.games):
        gid = base + k
        jobs.append((a.model, a.temp, random.choice(maps), random.randrange(1 << 30), str(out / f"{gid}.replay")))
    t0 = time.time()
    # fresh worker processes every few games: each game's wasm engine and model are not fully freed (7 -> 3 GB free
    # over 120 games otherwise)
    with mp.Pool(a.workers, maxtasksperchild=4) as pool:
        for n, ((winner, m, rounds), job) in enumerate(zip(pool.imap(play, jobs), jobs)):
            gid = int(pathlib.Path(job[4]).stem)
            if winner:
                index.append({"game": gid, "side": winner, "winner": winner, "path": job[4], "map": m,
                              "model": a.model, "temp": a.temp})
            if n % 10 == 9:
                json.dump(index, open(ix_path, "w"))
                print(f"{n + 1}/{a.games} games [{time.time() - t0:.0f}s], {free_gb():.1f} GB free", flush=True)
                while free_gb() < a.min_free_gb:
                    time.sleep(30)
    json.dump(index, open(ix_path, "w"))
    print(f"done: {len(index)} decided games in {ix_path}")


if __name__ == "__main__":
    main()
