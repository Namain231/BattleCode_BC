"""In-process game environment for reinforcement learning (no bot processes, no sandbox).

The engine (unswbc EngineModule, WebAssembly) calls back into Python for every dragon turn. Here every dragon of
both teams is controlled by a Python agent that builds the same egocentric 16-plane input the imitation network
uses (see ml/build_dataset.py) from the turn input it receives, plus the known map file.

    from rl_env import play_game
    result, trajectories = play_game("maps/trophy.map", policy_a, policy_b, seed=1)

A policy is a callable(planes uint8[16,15,15], scalars float32[3]) -> (action index 0..3 relative to facing,
extra info to store). Trajectories hold, per team, a list of (planes, scalars, action, info, round, dragon id)
and the per-dragon length history, so rewards can be computed afterwards.
"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_dataset import parse_map, OFF, VIEW  # noqa: E402

from unswbc.engine import EngineModule  # noqa: E402

DIRS = "NESW"
S = 15


class Agent:
    """Per-dragon state: identity, team, facing, length."""

    def __init__(self, init: bytes):
        f = dict(l.split(None, 1) for l in init.decode().splitlines() if " " in l)
        self.id = int(f["ID"]); self.team = f["TEAM"].strip()
        self.length = 2; self.facing = 0


def parse_turn(block: bytes):
    lines = [l for l in block.decode().splitlines() if l.strip()]
    i = 0
    hdr = {}
    while i < len(lines):   # ROUND, DIR, LENGTH, UNIT_COUNT, NUM_MSGS n + n values, optional ECHOES
        p = lines[i].split()
        i += 1
        if p[0] in ("ROUND", "DIR", "LENGTH", "UNIT_COUNT"):
            hdr[p[0]] = p[1]
        elif p[0] == "NUM_MSGS":
            i += int(p[1])
            if i < len(lines) and lines[i].startswith("ECHOES"):
                i += 1
            break
    tiles = []
    for _ in range(49):
        x, y, has, _pin = lines[i].split(); tiles.append((int(x), int(y), has == "1")); i += 1
    n = int(lines[i].split()[1]); i += 1
    parts = []
    for _ in range(n):
        t, did, x, y, face, head = lines[i].split(); parts.append((t, int(did), int(x), int(y), face, head == "1")); i += 1
    return hdr, tiles, parts


class Game:
    def __init__(self, map_path, policies, seed=0, record=("A", "B"), keep=1.0):
        self.map_bytes = pathlib.Path(map_path).read_bytes()
        name, self.W, self.H, self.kelp, self.portal, self.rate = parse_map(self.map_bytes.decode())
        self.policies = policies            # {"A": callable, "B": callable}
        self.seed = seed
        self.record = record; self.keep = keep   # teams whose decisions are stored, and the share kept (memory)
        self.rng = np.random.default_rng(seed)
        self.agents = {}
        self.traj = {"A": [], "B": []}
        self.lengths = {}                   # id -> {round: length}
        self.splits = {}                    # id -> [rounds it budded a length-2 child]
        self.team_of = {}                   # id -> "A" / "B" (kept after death)

    def spawn(self, did, init):
        self.agents[did] = Agent(init)
        self.team_of[did] = self.agents[did].team

    def death(self, did, rnd, reason):
        self.agents.pop(did, None)

    def features(self, ag, rnd, units, parts, tiles):
        W, H = self.W, self.H
        f = ag.facing
        head = next(((x, y) for t, i, x, y, face, h in parts if i == ag.id and h), None)
        if head is None:
            return None
        hx, hy = head
        ox, oy = OFF[f]
        xs, ys = (hx + ox) % W, (hy + oy) % H
        pl = np.zeros((16, S, S), np.uint8)
        for r in range(4):
            pl[r] = self.kelp[ys, xs, (r + f) % 4] * 255
            pl[4 + r] = self.portal[ys, xs, (r + f) % 4] * 255
        pl[8] = self.rate[ys, xs]
        pl[9] = VIEW * 255
        pearls = np.zeros((H, W), np.uint8)
        for x, y, has in tiles:
            if has:
                pearls[y % H, x % W] = 255
        own = np.zeros((H, W), np.uint8); ally = own.copy(); enemy = own.copy(); ahead = own.copy(); ehead = own.copy()
        # segment order along each body is not given directly: approximate "rounds until free" by distance to head
        by_id = {}
        for t, i, x, y, face, h in parts:
            by_id.setdefault(i, []).append((t, x, y, h))
        for i, segs in by_id.items():
            hd = next(((x, y) for t, x, y, h in segs if h), None)
            L = len(segs)
            for t, x, y, h in segs:
                d = 0 if hd is None else abs(x - hd[0]) + abs(y - hd[1])
                val = min(255, max(1, L - d) * 16)
                tgt = own if i == ag.id else ally if t == ag.team else enemy
                tgt[y % H, x % W] = val
                if h and i != ag.id:
                    (ahead if t == ag.team else ehead)[y % H, x % W] = min(255, L * 8)
        for c, arr in ((10, pearls), (11, own), (12, ally), (13, enemy), (14, ahead), (15, ehead)):
            pl[c] = np.where(VIEW, arr[ys, xs], 0)
        sc = np.array([ag.length / 32, rnd / 500, units / 64], np.float32)
        return pl, sc

    def reply(self, did, block):
        ag = self.agents.get(did)
        if ag is None:
            return b"MOVE N\nENDTURN\n"
        hdr, tiles, parts = parse_turn(block)
        rnd = int(hdr.get("ROUND", 0)); ag.facing = DIRS.index(hdr.get("DIR", "N")); ag.length = int(hdr.get("LENGTH", 2))
        self.lengths.setdefault(did, {})[rnd] = ag.length
        feat = self.features(ag, rnd, int(hdr.get("UNIT_COUNT", 1)), parts, tiles)
        if feat is None:
            return b"MOVE N\nENDTURN\n"
        pl, sc = feat
        act, info = self.policies[ag.team](pl, sc)
        if ag.team in self.record and (self.keep >= 1 or self.rng.random() < self.keep):
            self.traj[ag.team].append((pl, sc, act, info, rnd, did))
        if act == 4:
            self.splits.setdefault(did, []).append(rnd)
            return b"SPLIT 2\nENDTURN\n"
        world = DIRS[(act + ag.facing) % 4]
        return f"MOVE {world}\nENDTURN\n".encode()

    def run(self):
        eng = EngineModule()
        res = eng.run(self.map_bytes, self.reply, self.death, self.spawn, lambda line: None, 0, self.seed)
        return res


def play_game(map_path, policy_a, policy_b, seed=0, record=("A", "B"), keep=1.0):
    g = Game(map_path, {"A": policy_a, "B": policy_b}, seed, record, keep)
    res = g.run()
    return res, g.traj, g.lengths, g.splits, g.team_of


def team_potential(lengths, team_of, max_ratio=8.0):
    """Per round, team A's standing in [-1, 1] (team B's is the negative): half log(units ratio), half
    log(total length ratio), each normalised by log(max_ratio) (the generals.io agent's shaping potential)."""
    import math
    units, total = {}, {}
    for did, h in lengths.items():
        t = team_of.get(did)
        for r, L in h.items():
            units.setdefault(r, {"A": 0, "B": 0})[t] += 1
            total.setdefault(r, {"A": 0, "B": 0})[t] += L
    phi = {}
    for r in units:
        u, l = units[r], total[r]
        pu = math.log((u["A"] + 0.5) / (u["B"] + 0.5)) / math.log(max_ratio)
        pl = math.log((l["A"] + 1) / (l["B"] + 1)) / math.log(max_ratio)
        phi[r] = 0.5 * max(-1.0, min(1.0, pu)) + 0.5 * max(-1.0, min(1.0, pl))
    return phi


if __name__ == "__main__":
    import time
    rng = np.random.default_rng(0)

    def random_legal(pl, sc):   # forward/right/left at random, avoiding a kelp wall straight ahead
        choices = [a for a in (0, 1, 3) if pl[a, 7, 7] == 0] or [0]
        return int(rng.choice(choices)), None

    t0 = time.time()
    res, traj, *_ = play_game("maps/trophy.map", random_legal, random_legal, seed=1)
    dt = time.time() - t0
    n = len(traj["A"]) + len(traj["B"])
    print(res)
    print(f"{n} dragon-turns in {dt:.1f}s ({n / dt:.0f} turns/s)")
