"""Feature table: every feature a learned rule may use, defined once in words (the C++ side mirrors these).

All features are what the ACTING dragon could know on an unknown map: its 7x7 window, terrain it has seen since
birth (unseen edges assumed open, portals only when both ends were seen), teammates it has seen (not heard), its
own length/age, and the team unit count the protocol sends. Nothing reads the map file's terrain directly.
Occupancy is also only what it knows: its own body plus the dragon segments inside its window.
"""
from collections import deque

CAP = 40          # room is counted up to this many tiles
FAR = 99          # "unreachable / unknown" distance

FEATURES = [
    ("len", "own length"),
    ("units", "living dragons on our team (UNIT_COUNT)"),
    ("round", "round number (kept out of models unless asked for)"),
    ("age", "rounds since this dragon was born"),
    ("since_eat", "rounds since this dragon's length last grew between two of its turns (what it can observe)"),
    ("n_ally_vis", "ally heads in the 7x7 window"),
    ("n_enemy_vis", "enemy heads in the 7x7 window"),
    ("top_ally_vlen", "largest visible length among allies with a head in the window (0 if none)"),
    ("top_ally_ratio", "top_ally_vlen / len"),
    ("top_ally_dist", "BFS steps from my head to that ally's head over known terrain, bodies blocking (99 if none)"),
    ("top_ally_approach", "1 if that ally's head is closer (torus Manhattan) to my head now than where I saw it at my previous turn"),
    ("allies_near_top", "other visible ally heads within Chebyshev 3 of that ally's head"),
    ("mem_top_len", "largest visible length of any teammate seen in the last 15 rounds (incl. now)"),
    ("mem_top_age", "rounds since that sighting (99 if none)"),
    ("mem_top_dist", "torus Manhattan distance from my head to that sighting's head cell (99 if none)"),
    ("i_am_top", "1 if len >= mem_top_len"),
    ("enemy_threat", "visible enemy heads that can reach my head this turn: BFS dist <= min(visible len - 1, 3), >= 1"),
    ("room", "tiles reachable from my head over known terrain, bodies blocking, capped at 40"),
    ("pearls_r3", "pearls in my window within Chebyshev 3 (the whole window)"),
]
NAMES = [n for n, _ in FEATURES]


def bfs(geo, known, occ, start, targets=None, cap=64, passable=None):
    """Distances from start over known terrain; occupied tiles block except those in passable."""
    dist = {start: 0}
    q = deque([start])
    while q:
        c = q.popleft()
        if dist[c] >= cap:
            continue
        for d in range(4):
            n = geo.step(c, d, known)
            if n < 0 or n in dist:
                continue
            if n in occ and (passable is None or n not in passable):
                continue
            dist[n] = dist[c] + 1
            if targets is not None and n in targets:
                return dist
            q.append(n)
    return dist


def room(geo, known, occ, start, cap=CAP):
    seen = {start}
    q = deque([start])
    while q and len(seen) < cap + 1:
        c = q.popleft()
        for d in range(4):
            n = geo.step(c, d, known)
            if n < 0 or n in seen or n in occ:
                continue
            seen.add(n)
            q.append(n)
    return min(len(seen) - 1, cap)


def known_occupancy(geo, s, head):
    """Tiles the dragon knows are occupied: its own body, and any segment inside its 7x7 window."""
    occ = {c: v for c, v in s["occ"].items() if geo.cheb(c, head) <= 3}
    for c in s["body"]:
        occ[c] = (-1, 0)
    return occ


def compute(turn):
    g, s, i = turn.game, turn.snapshot, turn.id
    geo, known = g.geo, g.known(i)
    head, L = s["head"], turn.length
    occ = known_occupancy(geo, s, head)
    team = turn.team
    allies = [(j, h, vl) for (j, t, h, vl) in s["visible"] if t == team]
    enemies = [(j, h, vl) for (j, t, h, vl) in s["visible"] if t != team]
    f = dict.fromkeys(NAMES, 0)
    f["len"], f["units"], f["round"] = L, s["units"], turn.round
    f["age"], f["since_eat"] = turn.round - s["born"], turn.round - s["last_eat"]
    f["n_ally_vis"], f["n_enemy_vis"] = len(allies), len(enemies)
    f["top_ally_dist"] = FAR
    if allies:
        j, h, vl = max(allies, key=lambda a: (a[2], -a[0]))
        f["top_ally_vlen"], f["top_ally_ratio"] = vl, vl / L
        dist = bfs(geo, known, occ, head, targets={h}, cap=20, passable={h})
        f["top_ally_dist"] = dist.get(h, FAR)
        ph = s["heads_prev"].get(j, -1)
        if ph >= 0:
            f["top_ally_approach"] = int(geo.torus_manhattan(h, head) < geo.torus_manhattan(ph, head))
        f["allies_near_top"] = sum(1 for (k, h2, _) in allies if k != j and geo.cheb(h2, h) <= 3)
    recent = [(vl, r, h) for (r, vl, h) in s["mates"].values() if turn.round - r <= 15]
    if recent:
        vl, r, h = max(recent)
        f["mem_top_len"], f["mem_top_age"], f["mem_top_dist"] = vl, turn.round - r, geo.torus_manhattan(h, head)
    else:
        f["mem_top_age"] = f["mem_top_dist"] = FAR
    f["i_am_top"] = int(L >= f["mem_top_len"])
    threat = 0
    for (j, h, vl) in enemies:
        reach = max(1, min(vl - 1, 3))
        d = bfs(geo, known, occ, h, targets={head}, cap=reach, passable={head}).get(head, FAR)
        threat += d <= reach
    f["enemy_threat"] = threat
    f["room"] = room(geo, known, occ, head)
    pearls = s["pearls"]
    hx, hy = geo.xy(head)
    f["pearls_r3"] = sum(pearls[geo.cell(hx + dx, hy + dy)] for dy in range(-3, 4) for dx in range(-3, 4))
    return f
