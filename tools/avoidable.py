"""Which of our deaths were AVOIDABLE? Uses the true board from each replay (which our dragons could not see).

    python tools/avoidable.py [--n 150] [--glob "ladder/losses/*/*.replay"] [--out ladder/avoidable.txt]

For every death of our dragons (except deliberate feeds, "no valid action"), at the start of that dragon's last turn:
each of the 4 moves is checked on the true board: blocked by kelp or a body -> illegal/fatal; otherwise a flood fill
from the destination over free cells (bodies and kelp block; portals are treated as open, destination unknown) counts
the reachable space (capped at L + 4). A move is SAFE if the space >= its length L and no enemy head is adjacent to
the destination. The death is AVOIDABLE if some safe move existed. The same check is run 3 turns earlier ("trap
entry"): a pocket death is a bad ENTRY if 3 turns before the head still had a safe move with space >= L but the
dragon then went into the pocket. Output: per map x cause: deaths, % avoidable at the death turn, % bad entry,
median length; plus the bot's last indicator tag for avoidable deaths (what it thought).
Our side = the replay's non-empty botA/botB. Uses _decode (no cache files written).
"""
import argparse
import collections
import glob
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402

DX = (0, 1, 0, -1); DY = (-1, 0, 1, 0)   # N E S W


def parse_map(text):
    W = H = 0; name = "?"; edges = {}; dragons = []
    for l in text.splitlines():
        p = l.split()
        if not p: continue
        if p[0] == "MAP": W, H = int(p[1]), int(p[2])
        elif p[0] == "MAP_NAME": name = l.split(" ", 1)[1].strip()
        elif p[0] == "EDGE": edges[int(p[1])] = int(p[2])
        elif p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            dragons.append((t, [(c[2 * i], c[2 * i + 1]) for i in range(n)]))
    return W, H, name, edges, dragons


def edge_kind(edges, W, H, x, y, d):
    """kind of the edge on side d of tile (x,y): 0 open, 1 kelp, 2 portal."""
    if d == 0: idx = (2 * y) * (W + 1) + x
    elif d == 2: idx = (2 * ((y + 1) % H)) * (W + 1) + x
    elif d == 3: idx = (2 * y + 1) * (W + 1) + x
    else: idx = (2 * y + 1) * (W + 1) + ((x + 1) % W)
    return edges.get(idx, 0)


def space(start, occ, edges, W, H, cap):
    seen = {start}; q = [start]; i = 0
    while i < len(q) and len(seen) < cap:
        x, y = q[i]; i += 1
        for d in range(4):
            k = edge_kind(edges, W, H, x, y, d)
            if k == 1: continue
            if k == 2: return cap          # a portal: unknown far side, count as open
            n = ((x + DX[d]) % W, (y + DY[d]) % H)
            if n in seen or n in occ: continue
            seen.add(n); q.append(n)
    return len(seen)


def safe_moves(did, bodies, occ_all, enemy_heads, edges, W, H):
    body = bodies[did]
    if not body: return 0, 0
    hx, hy = body[0]; L = len(body)
    occ = occ_all - {body[-1]} if len(body) > 1 else occ_all   # our own tail moves away this turn
    legal = safe = 0
    for d in range(4):
        k = edge_kind(edges, W, H, hx, hy, d)
        if k == 1: continue
        n = ((hx + DX[d]) % W, (hy + DY[d]) % H)
        if k != 2 and n in occ: continue
        legal += 1
        if k == 2: safe += 1; continue
        near_enemy = any(((n[0] + DX[e]) % W, (n[1] + DY[e]) % H) in enemy_heads for e in range(4))
        if not near_enemy and space(n, occ | {(hx, hy)}, edges, W, H, L + 4) >= L:
            safe += 1
    return legal, safe


def analyse(path, stats, tags, hist_len=3, sub=None):
    rep = _decode(path)
    ours = 0 if rep["botA"] and not rep["botB"] else 1 if rep["botB"] and not rep["botA"] else None
    if ours is None: return False
    if sub and str(rep["botA"] if ours == 0 else rep["botB"]) != str(sub): return False   # only this build's games
    W, H, name, edges, dragons = parse_map(rep["map"])
    team, bodies = {}, {}
    for i, (t, b) in enumerate(dragons): team[i] = t; bodies[i] = [tuple(c) for c in b]
    alive = set(team); rnd = 0; last_ind = {}
    history = collections.defaultdict(collections.deque)   # our dragon id -> recent (round, legal, safe)
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            occ_all = set()
            for j in alive: occ_all.update(bodies.get(j) or [])
            eh = {bodies[j][0] for j in alive if team.get(j) != ours and bodies.get(j)}
            for i in list(alive):
                if team.get(i) == ours and bodies.get(i):
                    h = history[i]; h.append((rnd,) + safe_moves(i, bodies, occ_all, eh, edges, W, H))
                    while len(h) > hist_len + 1: h.popleft()
        elif k == "dragonIndicator":
            last_ind[e["id"]] = e["text"]
        elif k == "dragonUpdate":
            i = e["id"]; b = bodies.get(i)
            if b is None or e["head"] is None: continue
            hd, tl = tuple(e["head"]), tuple(e["tail"]) if e["tail"] else None
            if b[0] != hd: b.insert(0, hd)
            while len(b) > 1 and tl is not None and b[-1] != tl: b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]; bodies[e["child"]] = [tuple(c) for c in e["childBody"]]
            bodies[e["parent"]] = [tuple(c) for c in e["parentBody"]]; alive.add(e["child"])
        elif k == "dragonDeath":
            i = e["id"]; alive.discard(i)
            if team.get(i) != ours: continue
            cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
            if cause == "no valid action": continue
            h = history.get(i)
            if not h: continue
            _, legal_now, safe_now = h[-1]
            _, legal_old, safe_old = h[0]
            phase = "r0-100" if rnd < 100 else "r100-300" if rnd < 300 else "r300-500"
            key = (name, cause, phase)
            s = stats[key]; s["n"] += 1; s["avoid"] += safe_now > 0; s["len"].append(len(bodies.get(i) or []))
            s["entry"] += safe_now == 0 and safe_old > 0
            if safe_now > 0:
                tags[(name, cause)][(last_ind.get(i, "").split() or ["-"])[0]] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--glob", default="ladder/losses/*/*.replay")
    ap.add_argument("--out", default="ladder/avoidable.txt")
    ap.add_argument("--sub", default="11461", help="only games played by this submission (replay header); '' = all")
    a = ap.parse_args()
    files = sorted(glob.glob(a.glob), key=os.path.getmtime, reverse=True)
    stats = collections.defaultdict(lambda: {"n": 0, "avoid": 0, "entry": 0, "len": []})
    tags = collections.defaultdict(collections.Counter)
    done = 0
    for f in files:
        if done >= a.n: break
        try:
            if analyse(f, stats, tags, sub=a.sub or None) is not False: done += 1
        except Exception as ex:
            print("skip", f, repr(ex)[:80], file=sys.stderr)
    lines = [f"avoidable deaths in {done} replays ({a.glob}); per map x cause x phase:",
             f"{'map':16s} {'cause':15s} {'phase':9s} {'deaths':>6s} {'avoid%':>7s} {'badEntry%':>9s} {'medLen':>6s}"]
    for (m, c, ph), s in sorted(stats.items(), key=lambda kv: -kv[1]["n"]):
        if s["n"] < 5: continue
        med = sorted(s["len"])[len(s["len"]) // 2]
        lines.append(f"{m[:16]:16s} {c[:15]:15s} {ph:9s} {s['n']:6d} {100 * s['avoid'] / s['n']:6.0f}% "
                     f"{100 * s['entry'] / s['n']:8.0f}% {med:6d}")
    lines.append("\nbot's last indicator tag on AVOIDABLE deaths (map, cause): top tags")
    for (m, c), cnt in sorted(tags.items(), key=lambda kv: -sum(kv[1].values()))[:15]:
        lines.append(f"  {m[:16]:16s} {c[:15]:15s} " + ", ".join(f"{t}:{n}" for t, n in cnt.most_common(5)))
    out = "\n".join(lines)
    print(out)
    pathlib.Path(a.out).write_text(out, encoding="utf-8")


if __name__ == "__main__":
    main()
