"""New-rules imitation data: bounded per-game decoding, disk staging, resumable export."""
import argparse
import csv
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import sqlite3
import sys
import time
import zlib
from collections import Counter, deque

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "ml"), str(ROOT / "tools")]
from build_dataset import OFF, S, DIRS, DXY, parse_map
from replay_lite import decode_lite

VERSION = "v6.0.1"
KINDS = {"roundStart", "turnStart", "dragonAction", "dragonUpdate",
         "dragonSplit", "dragonDeath", "tileChange"}
PLANE_DEFS = ["kelp_N", "kelp_E", "kelp_S", "kelp_W", "portal_N", "portal_E",
              "portal_S", "portal_W", "ZERO", "turn_start_view", "visible_pearl",
              "own_body_free_x16", "visible_ally_free_x16", "visible_enemy_free_x16",
              "visible_ally_head_estLen_x8", "visible_enemy_head_estLen_x8",
              "queens_and_enemy_queen_memory", "enemy_free_step_reach", "reserved_ZERO"]
SCALARS = ["length/32", "round/500", "units/64", "is_queen", "ceil(length/4)/8", "steps_taken/4"]
META = ["game", "team", "map_hash", "round", "dragon", "length", "facing",
        "steps_taken", "declared_steps", "died_this_turn", "is_queen", "side"]
LABELS = ["forward", "right", "back", "left", "split", "other", "STOP"]


def atomic_json(path, obj):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(temp, path)


def fingerprint(p, s, y):
    return hashlib.blake2b(p.tobytes() + s.tobytes() + bytes([y]), digest_size=16).digest()


def game_holdout(games, fraction=0.1, seed=0):
    """Stable game-only split, unchanged when more games arrive."""
    return np.array([int.from_bytes(hashlib.blake2b(f"{seed}:{int(g)}".encode(),
                      digest_size=8).digest(), "little") / 2**64 < fraction for g in games])


class World:
    def __init__(self, text):
        self.name, self.W, self.H, self.kelp, self.portal, _ = parse_map(text)
        self.team, self.body, self.face = {}, {}, {}
        edges, pairs = {}, {}
        for line in text.splitlines():
            p = line.split()
            if not p:
                continue
            if p[0] == "EDGE":
                n, kind, pid = map(int, p[1:4]); r, c = divmod(n, self.W + 1)
                edge = (r % 2, c % self.W, (r // 2) % self.H)
                edges[edge] = (kind, pid)
            elif p[0] == "DRAGON":
                i = len(self.team); t, n = map(int, p[1:3]); xy = list(map(int, p[3:]))
                self.team[i] = t
                self.body[i] = [(xy[2*k] % self.W, xy[2*k+1] % self.H) for k in range(n)]
        for edge, (kind, pid) in edges.items():
            if kind == 2:
                pairs.setdefault(pid, []).append(edge)
        self.nbr = {}
        for y in range(self.H):
            for x in range(self.W):
                for d, (dx, dy) in enumerate(DXY):
                    edge = [(0, x, y), (1, (x+1) % self.W, y),
                            (0, x, (y+1) % self.H), (1, x, y)][d]
                    kind, pid = edges.get(edge, (0, -1))
                    dest = ((x+dx) % self.W, (y+dy) % self.H)
                    if kind == 1:
                        dest = None
                    elif kind == 2:
                        a, b = pairs[pid]
                        if a[0] != b[0]:
                            raise ValueError("cross-orientation portals are invalid under current rules")
                        o, px, py = b if edge == a else a
                        dest = (px, (py-(d == 0)) % self.H) if o == 0 else ((px-(d == 3)) % self.W, py)
                    self.nbr[(x, y), d] = dest
        for i, b in self.body.items():
            self.face[i] = self.direction(b[1], b[0])
        self.alive = set(self.team)
        self.pearls = set()
        self.seen, self.queen_memory = {}, {}
        self.round = 0

    def direction(self, a, b):
        return next((d for d in range(4) if self.nbr[a, d] == b), 0)

    def view(self, i):
        x, y = self.body[i][0]
        return {((x+dx) % self.W, (y+dy) % self.H) for dy in range(-3, 4) for dx in range(-3, 4)}

    def observe(self, i, terrain):
        view = self.view(i)
        self.seen.setdefault(i, set()).update(view)
        eq = next(q for q in (0, 1) if self.team[q] != self.team[i])
        if eq in self.alive and self.body[eq][0] in view:
            self.queen_memory[i] = (self.body[eq][0], self.round)
        arrays = np.zeros((19, self.H, self.W), np.uint8)
        for x, y in view:
            arrays[9, y, x] = 255
            arrays[10, y, x] = 255 * ((x, y) in self.pearls)
        occupied, heads = set(), []
        # Fragment links use visible segment orientation, never hidden body lengths.
        for q in sorted(self.alive):
            b = self.body[q]
            visible = {c for c in b if c in view}
            occupied.update(visible)
            if q == i:
                continue
            nxt, prv = {}, {}
            for k, c in enumerate(b):
                if c not in visible or k == 0:
                    continue
                to = self.nbr[c, self.direction(c, b[k-1])]
                if to in visible and to not in prv:
                    nxt[c] = to; prv[to] = c
            free = {c: 3 for c in visible}
            for tail in visible - set(prv):
                certain = True
                for d in range(4):
                    x, y = tail
                    if self.kelp[y, x, d]:
                        continue
                    if self.portal[y, x, d] or self.nbr[tail, d] not in view:
                        certain = False; break
                c, k, visited = tail, 1, set()
                while c is not None and c not in visited:
                    visited.add(c); free[c] = k + (0 if certain else 2)
                    c = nxt.get(c); k += 1
            ally = self.team[q] == self.team[i]
            for (x, y), fr in free.items():
                arrays[12 if ally else 13, y, x] = min(255, fr*16)
                if q in (0, 1):
                    arrays[16, y, x] = 128 if ally else 160
            if b[0] in visible:
                x, y = b[0]; est = free[b[0]]
                arrays[14 if ally else 15, y, x] = min(255, est*8)
                if q in (0, 1):
                    arrays[16, y, x] = 255
                if not ally:
                    heads.append((b[0], est))
        memory = self.queen_memory.get(i)
        if memory and self.round - memory[1] <= 100 and memory[0] not in view:
            x, y = memory[0]
            arrays[16, y, x] = int(150 * math.exp(-(self.round-memory[1])/40))
        known = self.seen[i]
        for head, length in heads:
            queue = deque([(head, 0)]); visited = {head}; limit = (length+3)//4
            while queue:
                c, depth = queue.popleft(); x, y = c
                arrays[17, y, x] = max(int(arrays[17, y, x]), max(0, 255-60*max(0, depth-1)))
                if depth == limit:
                    continue
                for d, (dx, dy) in enumerate(DXY):
                    dest = self.nbr[c, d] if terrain == "full" or c in known else ((x+dx) % self.W, (y+dy) % self.H)
                    if dest is not None and dest not in visited:
                        visited.add(dest)
                        if dest in occupied:
                            xx, yy = dest
                            arrays[17, yy, xx] = max(int(arrays[17, yy, xx]), max(0, 255-60*depth))
                        else:
                            queue.append((dest, depth+1))
        return arrays, known.copy()

    def snapshot(self, i, observation, terrain, steps=0, consumed=()):
        arrays, known = observation
        f = self.face[i]; hx, hy = self.body[i][0]; ox, oy = OFF[f]
        xs, ys = (hx+ox) % self.W, (hy+oy) % self.H
        planes = arrays[:, ys, xs].copy()
        for r in range(4):
            mask = np.ones((S, S), bool) if terrain == "full" else np.array(
                [[(int(x), int(y)) in known for x, y in zip(xrow, yrow)] for xrow, yrow in zip(xs, ys)])
            planes[r] = self.kelp[ys, xs, (r+f) % 4] * mask * 255
            planes[4+r] = self.portal[ys, xs, (r+f) % 4] * mask * 255
        for c in consumed:
            planes[10, (xs == c[0]) & (ys == c[1])] = 0
        own = np.zeros((self.H, self.W), np.uint8)
        for k, (x, y) in enumerate(self.body[i]):
            own[y, x] = min(255, (len(self.body[i])-k)*16)
        planes[11] = np.where(planes[9] > 0, own[ys, xs], 0)
        L = len(self.body[i]); units = sum(self.team[q] == self.team[i] for q in self.alive)
        sc = np.array([L/32, self.round/500, units/64, float(i in (0, 1)), (L+3)//4/8, steps/4], np.float32)
        assert planes.shape == (19, 15, 15) and sc.shape == (6,)
        if planes[8].any() or planes[18].any():
            raise AssertionError("ZERO plane is nonzero")
        return planes, sc


def reconstruct(w, i, dirs):
    """Advance only successful steps. Engine checks collision before removing tails."""
    F = (len(w.body[i])+3)//4; consumed = set()
    for j, direction in enumerate(dirs, 1):
        d = DIRS.index(direction); dest = w.nbr[w.body[i][0], d]
        occupied = {c for q in w.alive for c in w.body[q]}
        if dest is None or dest in occupied or (j > F and len(w.body[i]) <= 2):
            break
        w.face[i] = d
        w.body[i].insert(0, dest)
        if dest in w.pearls:
            w.pearls.remove(dest); consumed.add(dest)
        else:
            w.body[i].pop()
        if j > F:
            w.body[i].pop()
        yield j, consumed.copy(), F


def extract_game(path, gid, tid, side, terrain="full", include_losers=False, require_winner=True):
    rep = decode_lite(path, KINDS); w = World(rep["map"])
    if require_winner and rep.get("result", {}).get("winner") != side:
        raise ValueError("manifest winner does not match replay")
    samples, continuation_indices, updates = [], [], {}
    hist, death, births = {}, {}, {}
    mismatch, hidden_differences, sprint_turns = 0, 0, 0
    pending = None; truncated = -1; turn = {}
    maphash = zlib.crc32(w.name.encode()) & 0x7fffffff

    def emit(i, obs, y, j, k, consumed=()):
        p, s = w.snapshot(i, obs, terrain, j, consumed)
        meta = (gid, tid if w.team[i] == side else -1, maphash, w.round, i,
                len(w.body[i]), w.face[i], j, k, 0, int(i in (0, 1)), w.team[i])
        path = np.full(3, -1, np.int8)
        samples.append((p, s, y, meta, path))
        if j:
            continuation_indices.append(len(samples)-1)
        return len(samples)-1

    for e in rep["events"]:
        kind = e["kind"]
        if kind == "roundStart":
            w.round = e["round"]
        elif kind == "turnStart":
            i = e["id"]; pending = None; turn.pop(i, None)
            if i in w.alive:
                hist.setdefault(i, {})[w.round] = len(w.body[i])
                if w.team[i] == side or include_losers:
                    obs = w.observe(i, terrain); pending = (i, obs)
                    view = w.view(i)
                    for q in w.alive - {i}:
                        b = w.body[q]
                        for kk, (x, y) in enumerate(b):
                            if (x, y) in view:
                                pp = 12 if w.team[q] == w.team[i] else 13
                                hidden_differences += int(obs[0][pp, y, x] != min(255, (len(b)-kk)*16))
        elif kind == "dragonAction" and e["id"] in w.alive:
            i = e["id"]; dirs = e.get("dirs", ""); act = e.get("act")
            selected = pending is not None and pending[0] == i
            idx = None
            if selected:
                y = (DIRS.index(dirs[0])-w.face[i]) % 4 if act == "move" and dirs else 4 if act == "split" else 5
                idx = emit(i, pending[1], y, 0, len(dirs))
                if dirs:
                    samples[idx][4][:min(3, len(dirs))] = [(DIRS.index(d)-w.face[i]) % 4 for d in dirs[:3]]
            if act == "move" and dirs:
                if len(dirs) > 1 and selected:
                    sprint_turns += 1
                turn[i] = dict(dirs=dirs, j=0, selected=selected, L=len(w.body[i]), F=(len(w.body[i])+3)//4,
                               obs=pending[1] if selected else None, consumed=set())
            pending = None
        elif kind == "tileChange":
            c = tuple(e["tile"])
            if e["pearl"]:
                w.pearls.add(c)
            else:
                w.pearls.discard(c)
        elif kind == "dragonUpdate" and e["id"] in w.body and e.get("head"):
            # Apply each recorded step exactly: head/tail after the step decide growth or tail pops.
            i = e["id"]; head, tail = tuple(e["head"]), tuple(e["tail"]); old = w.body[i]
            if head == old[0] and tail == old[-1]:
                w.face[i] = e["facing"] % 4        # initial/no-op state announcement (round 0): nothing moved
                continue
            if tail == old[-1]:
                b = [head] + old                      # grew by a pearl (no tail pop)
                grew = True
            elif len(old) >= 2 and tail == old[-2]:
                b = [head] + old[:-1]                 # ordinary step (or pearl + paid pop)
                grew = False
            elif len(old) >= 3 and tail == old[-3]:
                b = [head] + old[:-2]                 # paid step without a pearl
                grew = False
            else:
                mismatch += 1; truncated = w.round; break
            w.body[i] = b; w.face[i] = e["facing"] % 4
            w.pearls.discard(head)
            t = turn.get(i)
            if t:
                t["j"] += 1; j = t["j"]
                if grew:
                    t["consumed"].add(head)
                if t["selected"] and t["L"] >= 5 and (j < len(t["dirs"]) or j < t["F"]+2):
                    y = (DIRS.index(t["dirs"][j])-w.face[i]) % 4 if j < len(t["dirs"]) else 6
                    emit(i, t["obs"], y, j, len(t["dirs"]), t["consumed"])
        elif kind == "dragonSplit":
            c, p = e["child"], e["parent"]
            w.team[c] = e["team"]; w.body[c] = list(map(tuple, e["childBody"]))
            w.body[p] = list(map(tuple, e["parentBody"])); w.alive.add(c)
            w.face[c] = w.direction(w.body[c][1], w.body[c][0])
            births.setdefault(p, []).append((w.round, len(w.body[c])))
        elif kind == "dragonDeath":
            i = e["id"]; w.alive.discard(i); death[i] = w.round
    # Safety: no continuation input from a game with a mismatching reconstruction.
    bad = set(continuation_indices) if mismatch else set()
    keep = [n for n in range(len(samples)) if n not in bad]
    P = np.empty((len(keep), 19, 15, 15), np.uint8)
    SC = np.empty((len(keep), 6), np.float32); Y = np.empty(len(keep), np.uint8)
    M = np.empty((len(keep), len(META)), np.int32); AUX = np.empty((len(keep), 3), np.int8)
    FUT = np.empty(len(keep), np.int16)
    for n, k in enumerate(keep):
        p, sc, y, meta, aux = samples[k]; P[n] = p; SC[n] = sc; Y[n] = y; M[n] = meta; AUX[n] = aux
        rnd, i, L = meta[3], meta[4], meta[5]
        M[n, 9] = death.get(i) == rnd
        h = hist[i]; r1 = min(rnd+20, max(h))
        L1 = 0 if death.get(i, 10**9) <= rnd+20 else h.get(r1, L)
        FUT[n] = L1 + sum(l for r, l in births.get(i, []) if rnd <= r <= rnd+20) - L
    stats = dict(samples=len(Y), reconstruction_mismatches=mismatch,
                 continuation_dropped=len(bad), visible_vs_true_differences=hidden_differences,
                 multi_step_turns=sprint_turns, truncated_round=truncated)
    return dict(planes=P, scalars=SC, labels=Y, meta=M, path=AUX, fut20=FUT), w.name, stats


def worker(job):
    path, gid, tid, side, terrain, losers, stage = job
    start = time.perf_counter()
    arrays, name, stats = extract_game(path, gid, tid, side, terrain, losers)
    dest = Path(stage) / f"game_{gid}.npz"
    temp = dest.with_suffix(".tmp.npz")
    np.savez_compressed(temp, **arrays)
    os.replace(temp, dest)
    stats.update(game=gid, team=tid, side=side, map=name, seconds=time.perf_counter()-start,
                 staging_bytes=dest.stat().st_size)
    return stats


def jobs(a, done, stage):
    # CSV rows and filesystem entries are visited one at a time.
    with open(a.index, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            gid, tid = int(row["game"]), int(row["winner_team"])
            if row["group"] != "top" or tid == 98 or row["at"] < a.rules_since:
                continue
            if gid in done:
                continue
            side = "ab".index(row["winner_side"].lower())
            if 98 in (int(row["teamA"]), int(row["teamB"])):
                continue
            path = Path(a.replays) / str(tid) / f"{gid}.replay"
            if path.exists():
                yield str(path), gid, tid, side, a.terrain, a.include_losers, str(stage)


def capped_counts(counts, cap=0.3):
    """Largest feasible integer total, with each team's quota <= floor(cap*total)."""
    lo, hi = 0, sum(counts.values())
    while lo < hi:
        mid = (lo+hi+1)//2
        if sum(min(v, int(cap*mid)) for v in counts.values()) >= mid:
            lo = mid
        else:
            hi = mid-1
    # Integer rounding can make feasibility nonmonotonic near zero; search downward.
    total = hi
    while total and sum(min(v, int(cap*total)) for v in counts.values()) < total:
        total -= 1
    quotas = {k: min(v, int(cap*total)) for k, v in counts.items()}
    excess = sum(quotas.values())-total
    for k in sorted(quotas, reverse=True):
        cut = min(max(excess, 0), quotas[k]); quotas[k] -= cut; excess -= cut
    return quotas


def export(a, manifest, out, stage):
    """Rebuild selection from staging when new games arrive; decoding is incremental."""
    dbpath = out / "dedupe_work.sqlite"
    if dbpath.exists():
        dbpath.unlink()  # only this builder's disposable index
    db = sqlite3.connect(dbpath)
    db.execute("CREATE TABLE seen (hash BLOB PRIMARY KEY) WITHOUT ROWID")
    unique_counts = Counter(); dropped = 0
    for info in manifest["games"]:
        with np.load(stage / f"game_{info['game']}.npz") as d:
            mask = np.zeros(len(d["labels"]), bool)
            p, s, y, m = (d[k] for k in ("planes", "scalars", "labels", "meta"))
            for n in range(len(y)):
                cur = db.execute("INSERT OR IGNORE INTO seen VALUES (?)", (fingerprint(p[n], s[n], int(y[n])),))
                if cur.rowcount:
                    mask[n] = True; unique_counts[int(m[n, 1])] += 1
                else:
                    dropped += 1
            np.save(stage / f"unique_{info['game']}.npy", mask)
            db.commit()
    db.close(); dbpath.unlink()
    quotas = capped_counts(unique_counts)
    if not sum(quotas.values()):
        raise ValueError("30% cap needs at least four sufficiently represented teams")
    used = Counter(); shards = []; buf = []; buffered = 0; counts = Counter(); maps = Counter(); sides = Counter()
    classes = np.zeros(7, np.int64); nonzero = np.zeros(19, np.int64); queen = continuation = total = 0
    generation = int(manifest.get("generation", 0))+1
    target_samples = 50000

    def flush():
        nonlocal buf, buffered, target_samples
        if not buf:
            return
        data = {k: np.concatenate([b[k] for b in buf]) for k in buf[0]}
        assert data["planes"].shape[1:] == (19, 15, 15) and not data["planes"][:, 8].any()
        file = f"shard_g{generation:04d}_{len(shards):04d}.npz"
        np.savez_compressed(out / file, **data)
        size = (out / file).stat().st_size
        shards.append(dict(file=file, samples=buffered, bytes=size,
                           teams=dict(Counter(map(str, data["meta"][:, 1]))),
                           maps=dict(Counter(map(str, data["meta"][:, 2]))),
                           sides=dict(Counter(map(str, data["meta"][:, 11])))))
        target_samples = min(125000, max(10000, int(buffered * a.shard_mb * 1024**2 / size)))
        print(f"shard {file}: {buffered} samples, {size} bytes", flush=True)
        buf = []; buffered = 0

    for info in manifest["games"]:
        with np.load(stage / f"game_{info['game']}.npz") as d:
            data = {k: d[k] for k in d.files}
        unique = np.load(stage / f"unique_{info['game']}.npy")
        keep = []
        for n in np.flatnonzero(unique):
            t = int(data["meta"][n, 1])
            if used[t] < quotas[t]:
                used[t] += 1; keep.append(n)
        data = {k: v[keep] for k, v in data.items()}
        m = data["meta"]; y = data["labels"]; n = len(y)
        data["weights"] = np.where(m[:, 10], 3, 1).astype(np.float32)
        data["game"] = m[:, 0].copy()
        classes += np.bincount(y, minlength=7); queen += int(m[:, 10].sum())
        continuation += int((m[:, 7] > 0).sum()); total += n
        nonzero += np.count_nonzero(data["planes"], axis=(0, 2, 3))
        counts.update(map(str, m[:, 1])); maps.update(map(str, m[:, 2])); sides.update(map(str, m[:, 11]))
        offset = 0
        while offset < n:
            end = min(n, offset + target_samples-buffered)
            buf.append({k: v[offset:end].copy() for k, v in data.items()}); buffered += end-offset; offset = end
            if buffered >= target_samples:
                flush()
    flush()
    assert max(counts.values()) / total <= 0.3
    old = manifest.get("shards", [])
    manifest.update(generation=generation, shards=shards, total_samples=total,
                    counts_per_team=dict(counts), counts_per_map=dict(maps), counts_per_side=dict(sides),
                    labels=classes.tolist(), queen_samples=queen, continuation_samples=continuation,
                    duplicate_dropped=dropped, cap_dropped=sum(unique_counts.values())-total,
                    plane_nonzero_fractions=(nonzero / (total*225)).tolist(),
                    bytes_per_sample=sum(s["bytes"] for s in shards)/total,
                    unique_counts_before_cap=dict(unique_counts))
    atomic_json(out / "manifest.json", manifest)
    # Remove only former exports that this manifest explicitly owned, after commit.
    for shard in old:
        (out / shard["file"]).unlink(missing_ok=True)
    print(json.dumps({k: manifest[k] for k in ("total_samples", "labels", "queen_samples",
          "continuation_samples", "duplicate_dropped", "cap_dropped", "bytes_per_sample", "plane_nonzero_fractions")}), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="ladder/scout_v6/manifest_fresh.csv")
    ap.add_argument("--replays", default="ladder/scout_v6/top")
    ap.add_argument("--out", default="ladder/scout_v6/shards")
    ap.add_argument("--workers", type=int, choices=range(1, 5), default=1)
    ap.add_argument("--terrain", choices=("full", "seen"), default="full")
    ap.add_argument("--include-losers", action="store_true")
    ap.add_argument("--rules-since", default="2026-10-01T00:00:00")
    ap.add_argument("--shard-mb", type=float, default=50)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    stage = out / "staging"; stage.mkdir(exist_ok=True)
    config = dict(terrain=a.terrain, include_losers=a.include_losers, rules_since=a.rules_since)
    path = out / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else dict(
        schema_version=VERSION, config=config, plane_definitions=PLANE_DEFS, scalar_definitions=SCALARS,
        metadata_columns=META, label_definitions=LABELS, games=[], shards=[])
    if manifest["schema_version"] != VERSION or manifest["config"] != config:
        raise ValueError("resume schema/config mismatch: choose a different output directory")
    done = {g["game"] for g in manifest["games"]}; changed = False
    # Workers write results directly to disk: no unbounded multiprocessing result arrays.
    if a.workers == 1:
        results = map(worker, jobs(a, done, stage))
        pool = None
    else:
        pool = mp.Pool(a.workers, maxtasksperchild=8)
        results = pool.imap(worker, jobs(a, done, stage), chunksize=1)
    try:
        for info in results:
            manifest["games"].append(info); done.add(info["game"]); changed = True
            atomic_json(path, manifest)
            print(json.dumps(info), flush=True)
    finally:
        if pool:
            pool.close(); pool.join()
    if changed or not manifest.get("total_samples"):
        export(a, manifest, out, stage)
    else:
        print(f"resume: {len(done)} games already processed; {manifest['total_samples']} samples unchanged")


if __name__ == "__main__":
    main()
