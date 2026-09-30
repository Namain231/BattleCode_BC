"""Pack shard folders from several machines into one folder, uniformly subsampled, with unique game ids.

    python ml/pack_shards.py --out ml/data_bp1 --total 900000 DIR [DIR ...]

train.py applies --max-samples per folder, so many self-play folders would each contribute that many samples
(and blow the laptop's RAM). Packing them into one folder keeps the top-teams / self-play mix 50/50.
Game ids get a per-source offset (source k: id + k * 1e11) so the train/val split by game never merges games
from different machines. A shard is read whole, so peak RAM is about one shard plus the output buffer.
"""
import argparse
import glob
import os

import numpy as np

KEYS = ("planes", "scalars", "labels", "meta", "game")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("srcs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--total", type=int, default=900000)
    ap.add_argument("--shard", type=int, default=60000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    files = [(k, f) for k, s in enumerate(a.srcs) for f in sorted(glob.glob(os.path.join(s, "shard_*.npz")))]
    sizes = [len(np.load(f)["labels"]) for _, f in files]
    grand = sum(sizes)
    rate = min(1.0, a.total / grand)
    print(f"{len(files)} shards, {grand} samples from {len(a.srcs)} folders; keeping {rate:.3f}")
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    buf, nbuf, nout, kept = {k: [] for k in KEYS}, 0, 0, 0

    def flush():
        nonlocal buf, nbuf, nout
        arrs = {k: np.concatenate(v) for k, v in buf.items()}
        perm = rng.permutation(len(arrs["labels"]))   # mix sources within a shard
        np.savez(os.path.join(a.out, f"shard_{nout:03d}.npz"), **{k: v[perm] for k, v in arrs.items()})
        nout += 1
        buf, nbuf = {k: [] for k in KEYS}, 0

    for (src, f), n in zip(files, sizes):
        d = np.load(f)
        ix = np.sort(rng.choice(n, int(round(n * rate)), replace=False))
        for k in KEYS:
            v = d[k][ix]
            buf[k].append(v + src * 10 ** 11 if k == "game" else v)
        nbuf += len(ix); kept += len(ix)
        if nbuf >= a.shard:
            flush()
    if nbuf:
        flush()
    print(f"wrote {kept} samples in {nout} shards to {a.out}")


if __name__ == "__main__":
    main()
