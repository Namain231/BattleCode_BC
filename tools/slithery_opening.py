"""Prototype: how can a queen starting inside a closed coil (Slithery Fight, L25) survive the opening?

    uv run --python 3.11 python tools/slithery_opening.py [map.map] [--queen 0] [--rounds 40]

Uses the validated simulator tools/engine_sim.py. Only the two queens exist (other dragons removed: this isolates the geometry).
Round 0: the queen splits off a child of size s; the child then sprints along a path of up to ceil(s/4) free steps (all 4^k
paths tried). From round 1 both parts follow a greedy flood-fill policy. We report, per s, the best child path, whether the queen
survives round 1, her length, and how long she lives. Baseline = child does not move at round 0 (what the bot's escape split gets).
"""
import sys, itertools, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_sim import load_map, apply_action, step, DIRS  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("map", nargs="?", default="maps/slithery_fight.map")
ap.add_argument("--queen", type=int, default=0); ap.add_argument("--rounds", type=int, default=40); a = ap.parse_args()
base = load_map(open(a.map, encoding="utf-8").read(), seed=1)
for i in list(base.dragons):
    if i != a.queen:
        del base.dragons[i]
Q = a.queen


def occ(state):
    return {p: i for i, d in state.dragons.items() if d.alive for p in d.body}


def space(state, dragon, d, limit=14):
    nb = state.board.neighbours; o = occ(state)
    dest = nb[dragon.body[0], d]
    if dest is None or dest in o:
        return -1
    seen = {dest}; frontier = [dest]; depth = 0
    while frontier and depth < limit:
        nxt = []
        for c in frontier:
            for k in range(4):
                n = nb[c, k]
                if n is not None and n not in o and n not in seen:
                    seen.add(n); nxt.append(n)
        frontier = nxt; depth += 1
    return len(seen)


def greedy(state, i):
    d = state.dragons[i]
    best, bd = -2, None
    for k in range(4):
        s = space(state, d, k)
        if s > best:
            best, bd = s, k
    return {"act": "move", "dirs": DIRS[bd]} if best >= 0 else {"act": "move", "dirs": DIRS[0]}


def run(state, rounds):
    st = state
    for _ in range(rounds):
        if not st.dragons[Q].alive:
            break
        st.over = False; st.winner = None   # only the queen's own survival matters here
        st = step(st, lambda s, i: greedy(s, i))
    return st


def trial(s, path):
    st = base.copy(); st.round = 0
    o = occ(st)
    child = apply_action(st, Q, {"act": "split", "size": s}, o)
    if child is None:
        return None
    if path:
        apply_action(st, child, {"act": "move", "dirs": path}, o)
        if not st.dragons[child].alive:
            return None
    # other queen must act too: it simply stays out of the way (suicide not allowed to end the game): keep it by greedy
    for i in list(st.dragons):
        if i not in (Q, child) and st.dragons[i].alive and st.dragons[i].team != st.dragons[Q].team:
            apply_action(st, i, greedy(st, i), o)
    st.round = 1
    alive_after = 0
    fin = run(st, a.rounds)
    q = fin.dragons[Q]
    return {"s": s, "path": path, "q_alive": q.alive, "q_len": len(q.body) if q.alive else 0,
            "q_death": (q.death if not q.alive else None), "rounds": fin.round}


L = len(base.dragons[Q].body)
print("queen start length", L, "head", base.dragons[Q].body[0])
results = []
for s in range(2, L - 1):
    F = (s + 3) // 4
    best = None
    for k in range(0, F + 1):
        for path in (itertools.product("NESW", repeat=k) if k else [()]):
            p = "".join(path)
            r = trial(s, p)
            if r is None:
                continue
            key = (r["q_alive"], r["rounds"], r["q_len"])
            if best is None or key > best[0]:
                best = (key, r)
    base_r = trial(s, "")
    results.append((s, base_r, best[1] if best else None))
print("s | parent len | baseline(child idle): alive/rounds/len | best child sprint: path alive/rounds/len")
for s, b, r in results:
    fb = f"{b['q_alive']}/{b['rounds']}/{b['q_len']}" if b else "child died"
    fr = f"{r['path'] or '-'} {r['q_alive']}/{r['rounds']}/{r['q_len']}" if r else "-"
    print(f"{s:2d} | {L - s:2d} | {fb} | {fr}")
