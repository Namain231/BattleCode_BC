"""Real-bot self-play for the network: the C++ champion plays itself in the judge's sandbox; the winner's decisions
become training data (residual learning: the network learns what wins *alongside* the heuristics, unlike
network-only self-play, which made the bot worse: sil_r2 38% vs the champion).

    python ml/botplay_collect.py --wasm ml/champion.wasm --games 400 --workers 8 --out <dir> \
        [--maps trophy,...] [--gen-dir maps_gen --gen-share 0.5]

Each game: `unswbc run <map> bot.wasm bot.wasm --sandbox --seed S` with a replay (no indicators/logs), the
winner's decisions are extracted with ml/build_dataset.game_samples (same features as the top-team data), the
replay is deleted, and samples are written as shard_<n>.npz (the build_dataset format) plus results.jsonl.
Live maze maps and random maps (maps_gen/) are mixed, so the network also learns maze play in general.
"""
import argparse
import json
import multiprocessing as mp
import os
import pathlib
import random
import re
import subprocess
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
MAZE = ["trophy", "queen_of_spades", "default", "dilemma", "autarky", "devil", "trauma"]
RESULT = re.compile(r"team (A|B) wins after (\d+) rounds")


def play(job):
    wasm, map_path, seed, gid, tmp = job
    rp = pathlib.Path(tmp) / f"{gid}.replay"
    try:
        r = subprocess.run(["unswbc", "run", map_path, wasm, wasm, "--sandbox", "--seed", str(seed), "-o", str(rp),
                            "--no-indicator", "--no-logs", "--no-draw"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
        m = RESULT.search(r.stdout + r.stderr)
        if not m or not rp.exists():
            return gid, map_path, None, None
        winner = m.group(1)
        from build_dataset import game_samples
        samples = game_samples(str(rp), 0 if winner == "A" else 1, seed=gid)
        return gid, map_path, winner, samples[:4]
    except Exception as e:
        return gid, map_path, "error " + repr(e)[:100], None
    finally:
        if rp.exists():
            rp.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wasm", default="ml/champion.wasm")
    ap.add_argument("--games", type=int, default=400)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--out", required=True)
    ap.add_argument("--maps", default=",".join(MAZE))
    ap.add_argument("--gen-dir", default="maps_gen")
    ap.add_argument("--gen-share", type=float, default=0.5, help="share of games on random maps")
    ap.add_argument("--id-base", type=int, default=5 * 10 ** 9)
    ap.add_argument("--shard", type=int, default=60000)
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tmp = out / "tmp"; tmp.mkdir(exist_ok=True)
    live = [str(ROOT / "maps" / f"{m}.map") for m in a.maps.split(",")]
    gen = sorted(str(p) for p in (ROOT / a.gen_dir).glob("*.map")) if a.gen_share > 0 else []
    rng = random.Random(a.id_base)
    jobs = []
    for k in range(a.games):
        mp_ = rng.choice(gen) if gen and rng.random() < a.gen_share else rng.choice(live)
        jobs.append((str(ROOT / a.wasm), mp_, rng.randrange(1 << 30), a.id_base + k, str(tmp)))
    buf = [[], [], [], [], []]; n_shard = len(list(out.glob("shard_*.npz"))); total = 0; t0 = time.time()

    def flush():
        nonlocal buf, n_shard
        if not buf[0]:
            return
        np.savez_compressed(out / f"shard_{n_shard:03d}.npz", planes=np.concatenate(buf[0]),
                            scalars=np.concatenate(buf[1]), labels=np.concatenate(buf[2]),
                            meta=np.concatenate(buf[3]), game=np.concatenate(buf[4]))
        n_shard += 1; buf = [[], [], [], [], []]

    with mp.Pool(a.workers, maxtasksperchild=8) as pool, open(out / "results.jsonl", "a") as log:
        for n, (gid, map_path, winner, s) in enumerate(pool.imap_unordered(play, jobs)):
            log.write(json.dumps({"game": gid, "map": pathlib.Path(map_path).stem, "winner": winner,
                                  "samples": 0 if s is None else len(s[2])}) + "\n"); log.flush()
            if s is not None:
                p, sc, y, m = s
                for b, v in zip(buf, (p, sc, y, m, np.full(len(y), gid, np.int64))):
                    b.append(v)
                total += len(y)
                if sum(len(v) for v in buf[2]) >= a.shard:
                    flush()
            if n % 10 == 9:
                print(f"{n + 1}/{a.games} games, {total} samples [{time.time() - t0:.0f}s]", flush=True)
    flush()
    print(f"done: {total} samples in {n_shard} shards in {out}", flush=True)


if __name__ == "__main__":
    main()
