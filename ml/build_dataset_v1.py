"""Imitation-learning dataset from top teams' replays.

    python ml/build_dataset.py --index ladder/il_data/index.json [--index ...] --out ml/data [--workers 11]

One sample = one decision of a dragon of the scouted (top) team, in a game that team won. Input is what our bot
can know at that moment, egocentric and rotated so the dragon faces "up" (the Hungry Geese / Lux AI trick:
the network never has to learn the same pattern in four orientations):

  planes (15x15, uint8), frame = head at the centre, facing up:
    0-3   kelp on the cell's up/right/down/left side        (known map: always visible)
    4-7   portal on the cell's up/right/down/left side      (known map)
    8     pearl spawn rate of the tile (fast fountains high) (known map)
    9     inside the 7x7 view
    10    pearl present                                     (view only)
    11-13 own / ally / enemy body: rounds until the cell frees, x16   (view only)
    14-15 ally / enemy head: that dragon's length, x8       (view only)
  scalars (float32): own length / 32, round / 500, own units / 64
  label: 0 forward, 1 right, 2 back, 3 left (first step of a move or sprint), 4 split, 5 suicide/illegal

Writes compressed shards <out>/shard_<n>.npz with planes, scalars, labels and per-sample metadata.
"""
import argparse
import json
import multiprocessing as mp
import os
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from replay import load  # noqa: E402

R = 7                      # crop radius -> 15x15
S = 2 * R + 1
DIRS = "NESW"
DXY = [(0, -1), (1, 0), (0, 1), (-1, 0)]     # N E S W, y grows downwards (south)

# frame offsets -> world offsets for each facing (rotate the frame so "up" is the facing)
OFF = []
for f in range(4):
    du, dv = np.meshgrid(np.arange(-R, R + 1), np.arange(-R, R + 1))  # du: right, dv: down (frame)
    x, y = du.copy(), dv.copy()
    for _ in range(f):          # one clockwise quarter-turn per facing step
        x, y = -y, x
    OFF.append((x, y))
VIEW = (np.abs(OFF[0][0]) <= 3) & (np.abs(OFF[0][1]) <= 3)   # the 7x7 view is a square: rotation-invariant


def parse_map(text):
    lines = text.splitlines()
    W, H = map(int, lines[0].split()[1:3])
    name = ""
    kelp = np.zeros((H, W, 4), np.uint8)
    portal = np.zeros((H, W, 4), np.uint8)
    rate = np.zeros((H, W), np.uint8)
    for l in lines:
        p = l.split()
        if not p:
            continue
        if p[0] == "MAP_NAME":
            name = " ".join(p[1:])
        elif p[0] == "TILE" and len(p) >= 5:
            x, y, lo, hi = map(int, p[1:5])
            if hi > 0:
                rate[y % H, x % W] = min(255, int(255 * 2.0 / max(1, lo + hi) * 4))
        elif p[0] == "EDGE":
            i, k = int(p[1]), int(p[2])
            if k not in (1, 2):
                continue
            r, c = divmod(i, W + 1)
            arr = kelp if k == 1 else portal
            if r % 2 == 0:   # north side of tile (c, r/2); also the south side of the tile above
                x, y = c % W, (r // 2) % H
                arr[y, x, 0] = 1; arr[(y - 1) % H, x, 2] = 1
            else:            # west side of tile (c, (r-1)/2); also the east side of the tile to the left
                x, y = c % W, ((r - 1) // 2) % H
                arr[y, x, 3] = 1; arr[y, (x - 1) % W, 1] = 1
    return name, W, H, kelp, portal, rate


def game_samples(path, side, keep_late=0.35, seed=0):
    rep = load(path)
    name, W, H, kelp, portal, rate = parse_map(rep["map"])
    rng = np.random.default_rng(seed)
    team, body, facing, nid = {}, {}, {}, 0
    for l in rep["map"].splitlines():
        p = l.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t; body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]
            (hx, hy), (nx, ny) = body[nid][0], body[nid][1]
            dx, dy = (hx - nx + W // 2) % W - W // 2, (hy - ny + H // 2) % H - H // 2
            facing[nid] = DXY.index((int(np.sign(dx)), int(np.sign(dy)))) if (dx == 0) != (dy == 0) else 0
            nid += 1
    alive = set(team)
    pearls = np.zeros((H, W), np.uint8)
    rnd = 0
    pending = None      # (id, planes, scalars, facing) snapshotted at its turnStart
    out_p, out_s, out_y, out_m = [], [], [], []

    def snapshot(i):
        own = np.full((H, W), 0, np.uint8); ally = own.copy(); enemy = own.copy()
        ahead = own.copy(); ehead = own.copy()
        for j in alive:
            b = body[j]; L = len(b)
            tgt = own if j == i else ally if team[j] == team[i] else enemy
            for k, (x, y) in enumerate(b):
                tgt[y % H, x % W] = min(255, (L - k) * 16)
            if j != i:
                (x, y) = b[0]
                (ahead if team[j] == team[i] else ehead)[y % H, x % W] = min(255, L * 8)
        f = facing.get(i, 0)
        hx, hy = body[i][0]
        ox, oy = OFF[f]
        xs, ys = (hx + ox) % W, (hy + oy) % H
        planes = np.zeros((16, S, S), np.uint8)
        for r in range(4):   # 0/255 like every other plane (the bot writes 255)
            planes[r] = kelp[ys, xs, (r + f) % 4] * 255
            planes[4 + r] = portal[ys, xs, (r + f) % 4] * 255
        planes[8] = rate[ys, xs]
        planes[9] = VIEW * 255
        for c, arr in ((10, pearls * 255), (11, own), (12, ally), (13, enemy), (14, ahead), (15, ehead)):
            planes[c] = np.where(VIEW, arr[ys, xs], 0)
        units = sum(1 for j in alive if team[j] == team[i])
        scal = np.array([len(body[i]) / 32, rnd / 500, units / 64], np.float32)
        return planes, scal, f

    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
        elif k == "turnStart":
            i = e["id"]
            pending = None
            if i in alive and team.get(i) == side and (rnd < 200 or rng.random() < keep_late):
                pending = (i,) + snapshot(i)
        elif k == "dragonAction" and pending and e["id"] == pending[0]:
            i, planes, scal, f = pending
            act = e.get("act")
            if act == "move" and e.get("dirs"):
                y = (DIRS.index(e["dirs"][0]) - f) % 4
            elif act == "split":
                y = 4
            else:
                y = 5
            out_p.append(planes); out_s.append(scal); out_y.append(y); out_m.append((rnd, len(body[i]), i, f))
            pending = None
        elif k == "tileChange":
            (x, y) = e["tile"]; pearls[y % H, x % W] = 1 if e["pearl"] else 0
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]
            if b[0] != e["head"]:
                b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]:
                b.pop()
            (x, y) = e["head"]; pearls[y % H, x % W] = 0
            facing[e["id"]] = e["facing"] % 4
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]; body[e["child"]] = e["childBody"]; body[e["parent"]] = e["parentBody"]
            alive.add(e["child"])
            cb = e["childBody"]
            if len(cb) >= 2:
                (hx, hy), (nx, ny) = cb[0], cb[1]
                dx, dy = (hx - nx + W // 2) % W - W // 2, (hy - ny + H // 2) % H - H // 2
                if (dx == 0) != (dy == 0):
                    facing[e["child"]] = DXY.index((int(np.sign(dx)), int(np.sign(dy))))
        elif k == "dragonDeath":
            alive.discard(e["id"])
    if not out_y:
        return None
    return (np.stack(out_p), np.stack(out_s), np.array(out_y, np.uint8),
            np.array(out_m, np.int16), name)


def work(job):
    path, side, gid = job
    try:
        r = game_samples(path, side, seed=gid)
    except Exception as ex:  # a truncated download should not stop the build
        return gid, None, repr(ex)
    return gid, r, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", nargs="+", required=True)
    ap.add_argument("--out", default="ml/data")
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument("--shard", type=int, default=60000)
    a = ap.parse_args()
    jobs, seen = [], set()
    for ix in a.index:
        base = pathlib.Path(ix).parent
        for g in json.load(open(ix, encoding="utf-8")):
            if g.get("winner") != g.get("side") or g["game"] in seen:
                continue   # only games the top team won
            p = base / str(g["teamId"]) / f"{g['game']}.replay"
            if p.exists():
                seen.add(g["game"])
                jobs.append((str(p), 0 if g["side"] == "A" else 1, g["game"]))
    print(f"{len(jobs)} winning games", flush=True)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    buf = [[], [], [], [], []]; n_shard = 0; total = 0; counts = np.zeros(6, np.int64)

    def flush():
        nonlocal buf, n_shard
        if not buf[0]:
            return
        np.savez_compressed(out / f"shard_{n_shard:03d}.npz", planes=np.concatenate(buf[0]),
                            scalars=np.concatenate(buf[1]), labels=np.concatenate(buf[2]),
                            meta=np.concatenate(buf[3]), game=np.concatenate(buf[4]))
        n_shard += 1; buf = [[], [], [], [], []]

    with mp.Pool(a.workers) as pool:
        for n, (gid, r, err) in enumerate(pool.imap_unordered(work, jobs, chunksize=2)):
            if r is None:
                if err:
                    print(f"  skip {gid}: {err[:80]}", flush=True)
                continue
            p, s, y, m, name = r
            for b, v in zip(buf, (p, s, y, m, np.full(len(y), gid, np.int64))):
                b.append(v)
            total += len(y); counts += np.bincount(y, minlength=6)
            if sum(len(v) for v in buf[2]) >= a.shard:
                flush()
            if n % 25 == 0:
                print(f"  {n + 1}/{len(jobs)} games, {total} samples", flush=True)
    flush()
    print(f"done: {total} samples in {n_shard} shards; label counts F/R/B/L/split/other = {counts.tolist()}")


if __name__ == "__main__":
    main()
