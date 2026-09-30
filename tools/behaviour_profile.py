"""Behavioural reverse-engineering of top teams from public replays.

Public replays carry no CPU points and no indicator/log strings (both stripped for every team), so
everything here is inferred from the event stream: what each dragon saw (its 7x7 vision, the pearls
and heads around it), what it did next, and how that changed after it received sonar or echo data.

Sections, per team, split by game phase (early r<100, mid r100-299, late r300+):

  ECONOMY     eats per dragon-turn, share of all pearls eaten in the game
  GREED       when a pearl is one legal step away, how often the dragon takes it that turn
  PURSUIT     when a pearl is visible (7x7) how often the next move closes the true (kelp-aware)
              distance to it -- low pursuit + high economy = routing to something better than vision
  PATH        straight-move rate, dithering (revisiting a cell from its last 8), sprint (multi-step) rate
  BREEDING    splits per dragon-turn, total length at split, child and kept length, birth->first
              split, rounds from last eat to split
  DEATHS      per 1000 dragon-turns by cause; "no valid action" is what a CPU overrun or crash yields,
              the only CPU signal public replays still carry
  SONAR-SEND  the sender's NEXT action after its rays stopped on an enemy head / enemy body / nothing
              of interest, vs its baseline -- does echo data change behaviour, and how
  SONAR-RECV  the receiver's next action after a teammate's ray delivered it a message, vs baseline
  PAYLOAD     constant-bit layout of each team's 64-bit messages, and an automatic field decoder that
              tests every bit window against sender x/y/cell, round, id, unit count and the pearls in
              the sender's vision

    uv run --python 3.11 --with unswbc --with numpy python tools/behaviour_profile.py ladder/scout_fresh
"""
import argparse
import collections
import json
import pathlib
import random
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from profile_style import parse_map  # noqa: E402
from replay import load, DEATHS  # noqa: E402

DIRS = "NESW"
DXY = [(0, -1), (1, 0), (0, 1), (-1, 0)]
PHASES = ("early", "mid", "late")
RES_SIZE = 6000          # payload reservoir per team


def phase_of(r):
    return "early" if r < 100 else "mid" if r < 300 else "late"


def cheb(w, h, a, b):
    ax, ay, bx, by = a % w, a // w, b % w, b // w
    dx = abs(ax - bx)
    dy = abs(ay - by)
    return max(min(dx, w - dx), min(dy, h - dy))


def local_bfs(nbr, start, radius):
    dist = {start: 0}
    q = collections.deque([start])
    while q:
        c = q.popleft()
        d = dist[c]
        if d >= radius:
            continue
        for n in nbr[c]:
            if n not in dist:
                dist[n] = d + 1
                q.append(n)
    return dist


def facing_of(a, b, w, h):
    """Direction index from cell b (neck) to cell a (head), torus aware."""
    ax, ay, bx, by = a % w, a // w, b % w, b // w
    for i, (dx, dy) in enumerate(DXY):
        if ((bx + dx) % w, (by + dy) % h) == (ax, ay):
            return i
    return None


class Team:
    def __init__(self):
        self.c = collections.Counter()            # scalar counters, key strings
        self.lists = collections.defaultdict(list)
        self.res = []                              # payload reservoir rows
        self.res_seen = 0
        self.games = 0
        self.wins = 0


def analyse(path, side, T, rng):
    rep = load(path)
    w, h, nbr, _spawn = parse_map(rep["map"])
    team, body, face, born, last_eat = {}, {}, {}, {}, {}
    nid = 0
    for line in rep["map"].splitlines():
        p = line.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3:3 + 2 * n]]
            cells = [c[2 * i + 1] * w + c[2 * i] for i in range(n)]
            team[nid] = t
            body[nid] = cells
            face[nid] = facing_of(cells[0], cells[1], w, h) if n > 1 else None
            born[nid] = 0
            nid += 1
    alive = set(team)
    hist = collections.defaultdict(lambda: collections.deque(maxlen=8))
    pearls = set()
    rnd = 0
    ph = "early"
    own = lambda d: team.get(d) == side  # noqa: E731

    pend_greedy = {}      # dragon -> set of adjacent pearl cells at round start
    pend_pursuit = {}     # dragon -> (target set, dist0)
    pend_send = {}        # dragon -> dict of what its rays hit this turn
    pend_recv = collections.Counter()   # dragon -> messages from teammates received this turn
    total_removed = 0
    own_eats = 0

    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            ph = phase_of(rnd)
            pend_greedy.clear()
            pend_pursuit.clear()
            for d in alive:
                if not own(d):
                    continue
                T.c[f"dturn|{ph}"] += 1
                hd = body[d][0]
                adj = {n for n in nbr[hd] if n in pearls}
                if adj:
                    pend_greedy[d] = adj
                if rnd < 150 and pearls:
                    vis = {p for p in pearls if cheb(w, h, p, hd) <= 3}
                    if vis:
                        dist = local_bfs(nbr, hd, 8)
                        d0 = min((dist.get(p, 99) for p in vis), default=99)
                        if d0 < 99:
                            pend_pursuit[d] = (vis, d0)
        elif k == "tileChange":
            c = e["tile"][1] * w + e["tile"][0]
            if e["pearl"]:
                pearls.add(c)
            elif c in pearls:
                pearls.discard(c)
                total_removed += 1
        elif k == "dragonAction":
            d = e["id"]
            if not own(d):
                continue
            act = e.get("act")
            fd = face.get(d)
            if act == "move" and e.get("dirs"):
                first = DIRS.index(e["dirs"][0])
                sprint = len(e["dirs"]) > 1
                rel = "S" if fd is None or first == fd else ("R" if first == (fd + 2) % 4 else "T")
            elif act == "split":
                sprint, rel = False, "split"
            elif act == "suicide":
                sprint, rel = False, "suicide"
            else:
                sprint, rel = False, "?"
            # baseline decision profile
            T.c[f"act|{ph}"] += 1
            T.c[f"act_{rel}|{ph}"] += 1
            if sprint:
                T.c[f"sprint|{ph}"] += 1
            # decisions made right after this dragon's own rays reported back (echo)
            ps = pend_send.pop(d, None)
            if ps is not None:
                cat = "enemy_head" if ps["enemy_head"] else "enemy_body" if ps["enemy"] else "quiet"
                T.c[f"se_{cat}|n"] += 1
                T.c[f"se_{cat}|{rel}"] += 1
                if sprint:
                    T.c[f"se_{cat}|sprint"] += 1
                # directional test, only when exactly one head-emitted ray found an enemy head
                if ps["eh_dirs"] and len(ps["eh_dirs"]) == 1 and act == "move" and e.get("dirs"):
                    rd = ps["eh_dirs"][0]
                    rrel = "toward" if first == rd else "away" if first == (rd + 2) % 4 else "side"
                    T.c[f"se_dir|{rrel}"] += 1
            # decisions made right after receiving a teammate's message
            nmsg = pend_recv.pop(d, 0)
            cat = "recv" if nmsg else "norecv"
            T.c[f"rc_{cat}|n"] += 1
            T.c[f"rc_{cat}|{rel}"] += 1
            if sprint:
                T.c[f"rc_{cat}|sprint"] += 1
        elif k == "dragonUpdate" and e["head"]:
            d = e["id"]
            if d not in body:
                continue
            hd = e["head"][1] * w + e["head"][0]
            tl = e["tail"][1] * w + e["tail"][0] if e["tail"] else None
            b = body[d]
            before = len(b)
            moved = b[0] != hd
            if moved:
                b.insert(0, hd)
            if tl is not None:
                while len(b) > 1 and b[-1] != tl:
                    b.pop()
            newface = e.get("facing")
            if own(d) and moved:
                grew = len(b) > before
                if grew:
                    T.c[f"eat|{ph}"] += 1
                    own_eats += 1
                    last_eat[d] = rnd
                T.c[f"move|{ph}"] += 1
                if face.get(d) is not None and newface == face.get(d):
                    T.c[f"straight|{ph}"] += 1
                if hd in hist[d]:
                    T.c[f"dither|{ph}"] += 1
                hist[d].append(hd)
                g = pend_greedy.pop(d, None)
                if g is not None:
                    T.c[f"greedy_opp|{ph}"] += 1
                    if hd in g:
                        T.c[f"greedy_take|{ph}"] += 1
                pu = pend_pursuit.pop(d, None)
                if pu is not None:
                    vis, d0 = pu
                    live = {p for p in vis if p in pearls or p == hd}
                    if live:
                        if hd in live:
                            closer = True
                        else:
                            dist = local_bfs(nbr, hd, 9)
                            d1 = min((dist.get(p, 99) for p in live), default=99)
                            closer = d1 < d0
                        T.c["pursuit_opp"] += 1
                        if closer:
                            T.c["pursuit_close"] += 1
            if newface is not None:
                face[d] = newface
        elif k == "dragonSplit":
            par, ch = e["parent"], e["child"]
            team[ch] = e["team"]
            alive.add(ch)
            pb = [q[1] * w + q[0] for q in e["parentBody"]]
            cb = [q[1] * w + q[0] for q in e["childBody"]]
            body[par], body[ch] = pb, cb
            face[ch] = facing_of(cb[0], cb[1], w, h) if len(cb) > 1 else None
            if e["team"] == side:
                T.c[f"split|{ph}"] += 1
                T.lists["split_total"].append(len(pb) + len(cb))
                T.lists["split_child"].append(len(cb))
                T.lists["split_keep"].append(len(pb))
                T.lists["split_round"].append(rnd)
                if par not in T.__dict__.setdefault("_first_split", set()):
                    pass
                if born.get(par) is not None and (path, par) not in T.__dict__.setdefault("_fs", set()):
                    T._fs.add((path, par))
                    T.lists["birth_to_split"].append(rnd - born[par])
                if par in last_eat:
                    T.lists["eat_to_split"].append(rnd - last_eat[par])
            born[ch] = rnd
        elif k == "dragonDeath":
            d = e["id"]
            if own(d):
                cause = DEATHS[e["reason"]] if e["reason"] < len(DEATHS) else str(e["reason"])
                T.c[f"death|{cause}"] += 1
                T.c[f"death_ph|{ph}"] += 1
            alive.discard(d)
            pend_send.pop(d, None)
        elif k == "sonarPing":
            s = e["sender"]
            hk = e["hitKind"]
            r_id = e["hit"]
            if own(s):
                ps = pend_send.setdefault(s, {"enemy_head": 0, "enemy": 0, "eh_dirs": []})
                if hk == "enemy_head":
                    ps["enemy_head"] += 1
                    hd = body[s][0] if s in body else None
                    org = e["origin"]
                    if hd is not None and org is not None and org[1] * w + org[0] == hd:
                        ps["eh_dirs"].append(DIRS.index(e["dir"]))
                elif hk == "enemy":
                    ps["enemy"] += 1
                if r_id is not None and team.get(r_id) == side and r_id != s:
                    pend_recv[r_id] += 1
                    T.c["msg_to_ally"] += 1
                # payload reservoir with the sender's context
                T.res_seen += 1
                if len(T.res) < RES_SIZE or rng.random() < RES_SIZE / T.res_seen:
                    hd = body[s][0] if s in body else 0
                    vis = sorted(p for p in pearls if cheb(w, h, p, hd) <= 3)[:6]
                    nun = sum(1 for d in alive if own(d))
                    row = (e["value"], hd % w, hd // w, hd, rnd, s, nun,
                           [p % w for p in vis], [p // w for p in vis], vis, w, h)
                    if len(T.res) < RES_SIZE:
                        T.res.append(row)
                    else:
                        T.res[rng.randrange(RES_SIZE)] = row
            elif r_id is not None and team.get(r_id) == side:
                T.c["msg_from_enemy"] += 1
    T.c["pearls_removed"] += total_removed
    T.c["own_eats"] += own_eats


def decode_payloads(res):
    """Constant-bit layout + best matching bit windows against sender context."""
    if len(res) < 200:
        return None, []
    v = np.array([r[0] for r in res], dtype=np.uint64)
    bits = np.array([((v >> np.uint64(b)) & np.uint64(1)).mean() for b in range(64)])
    layout = "".join("1" if bits[b] > 0.99 else "0" if bits[b] < 0.01 else "." for b in range(63, -1, -1))
    nz = v != 0
    tgt = {
        "head_x": np.array([r[1] for r in res]),
        "head_y": np.array([r[2] for r in res]),
        "head_cell": np.array([r[3] for r in res]),
        "round": np.array([r[4] for r in res]),
        "sender_id": np.array([r[5] for r in res]),
        "own_units": np.array([r[6] for r in res]),
    }
    maxp = 6
    px = np.full((len(res), maxp), -1)
    py = np.full((len(res), maxp), -1)
    pc = np.full((len(res), maxp), -1)
    for i, r in enumerate(res):
        for j in range(len(r[7])):
            px[i, j], py[i, j], pc[i, j] = r[7][j], r[8][j], r[9][j]
    hits = []
    for width in (4, 5, 6, 7, 8, 9, 10, 11, 12, 16):
        mask = np.uint64((1 << width) - 1)
        for shift in range(0, 65 - width):
            f = ((v >> np.uint64(shift)) & mask).astype(np.int64)
            if np.unique(f[nz]).size < 3:
                continue
            chance = 1.0 / (1 << width)
            for name, arr in tgt.items():
                m = (f == arr)[nz].mean() if nz.any() else 0
                if name == "round":
                    m = (f == (arr & ((1 << width) - 1)))[nz].mean()
                if m > max(0.25, 20 * chance):
                    hits.append((m, name, shift, width))
            for name, arr in (("pearl_x", px), ("pearl_y", py), ("pearl_cell", pc)):
                has = (arr >= 0).any(axis=1) & nz
                if has.sum() < 100:
                    continue
                m = (arr == f[:, None]).any(axis=1)[has].mean()
                if m > max(0.25, 20 * chance * maxp):
                    hits.append((m, name, shift, width))
    hits.sort(key=lambda x: (-x[0], x[3]))
    best, seen = [], set()
    for m, name, s, wd in hits:
        key = (name, s // 4)
        if key in seen:
            continue
        seen.add(key)
        best.append((m, name, s, wd))
        if len(best) >= 6:
            break
    return layout, best


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


def med(xs):
    if not xs:
        return float("nan")
    s = sorted(xs)
    return s[len(s) // 2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--teams", default=None, help="comma list to restrict")
    args = ap.parse_args()
    root = pathlib.Path(args.dir)
    idx = {(str(e["teamId"]), str(e["game"])): e
           for e in json.load(open(root / "index.json", encoding="utf-8"))}
    only = set(args.teams.split(",")) if args.teams else None
    teams = collections.defaultdict(Team)
    elo = {}
    rng = random.Random(7)
    files = sorted(root.rglob("*.replay"))
    for i, f in enumerate(files):
        m = idx.get((f.parent.name, f.stem))
        if not m or (only and m["team"] not in only):
            continue
        side = 0 if m["side"] in ("A", 0) else 1
        T = teams[m["team"]]
        elo[m["team"]] = m.get("elo", 0)
        try:
            analyse(f, side, T, rng)
        except Exception as exc:
            print(f"  ! {f}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        T.games += 1
        T.wins += 1 if m.get("winner") == m["side"] else 0
        if i % 20 == 0:
            print(f"  ... {i}/{len(files)}", file=sys.stderr)

    names = sorted(teams, key=lambda n: -elo.get(n, 0))
    out = []
    P = out.append

    P("\n=== ECONOMY / GREED / PURSUIT / PATH  (per team; early | mid | late) ===")
    P(f"{'team':22s} {'elo':>5s} {'W%':>4s} {'eats/dturn e|m|l':>18s} {'pearl%':>6s}"
      f" {'greedy% e|m|l':>15s} {'pursue%':>7s} {'straight% e|m|l':>16s} {'dither% e|m|l':>14s} {'sprint%':>7s}")
    for n in names:
        c = teams[n].c
        eat = "|".join(f"{c[f'eat|{p}'] / c[f'dturn|{p}']:.3f}" if c[f'dturn|{p}'] else " nan " for p in PHASES)
        gr = "|".join(f"{pct(c[f'greedy_take|{p}'], c[f'greedy_opp|{p}']):3.0f}" for p in PHASES)
        st = "|".join(f"{pct(c[f'straight|{p}'], c[f'move|{p}']):3.0f}" for p in PHASES)
        di = "|".join(f"{pct(c[f'dither|{p}'], c[f'move|{p}']):3.0f}" for p in PHASES)
        sp = pct(sum(c[f'sprint|{p}'] for p in PHASES), sum(c[f'act|{p}'] for p in PHASES))
        share = pct(c["own_eats"], c["pearls_removed"])
        P(f"{n[:22]:22s} {elo.get(n, 0):>5d} {pct(teams[n].wins, teams[n].games):>4.0f} {eat:>18s} {share:>6.1f}"
          f" {gr:>15s} {pct(c['pursuit_close'], c['pursuit_opp']):>7.1f} {st:>16s} {di:>14s} {sp:>7.2f}")

    P("\n=== BREEDING ===")
    P(f"{'team':22s} {'splits/1kdt e|m|l':>20s} {'len@split':>9s} {'child':>5s} {'kept':>5s}"
      f" {'birth->split':>12s} {'eat->split':>10s} {'last split rnd':>14s}")
    for n in names:
        c, L = teams[n].c, teams[n].lists
        sp = "|".join(f"{1000 * c[f'split|{p}'] / c[f'dturn|{p}']:5.1f}" if c[f'dturn|{p}'] else "  nan" for p in PHASES)
        lr = sorted(L["split_round"])
        p90 = lr[int(0.9 * len(lr))] if lr else float("nan")
        P(f"{n[:22]:22s} {sp:>20s} {med(L['split_total']):>9} {med(L['split_child']):>5} {med(L['split_keep']):>5}"
          f" {med(L['birth_to_split']):>12} {med(L['eat_to_split']):>10} {p90:>14}")

    P("\n=== DEATHS per 1000 dragon-turns (by cause) ===")
    P(f"{'team':22s} " + " ".join(f"{d[:12]:>12s}" for d in DEATHS) + f" {'early|mid|late':>16s}")
    for n in names:
        c = teams[n].c
        dt = sum(c[f"dturn|{p}"] for p in PHASES) or 1
        row = " ".join(f"{1000 * c[f'death|{d}'] / dt:>12.2f}" for d in DEATHS)
        byph = "|".join(f"{1000 * c[f'death_ph|{p}'] / (c[f'dturn|{p}'] or 1):4.1f}" for p in PHASES)
        P(f"{n[:22]:22s} {row} {byph:>16s}")

    P("\n=== DECISIONS AFTER OWN SONAR ECHOES (sender's next action) ===")
    P("S=straight T=turn R=reverse(into own neck) split sprint; base = all of this team's decisions")
    P(f"{'team':22s} {'base S/T/R/split/sprint':>26s} {'after enemy-head echo':>26s} {'after quiet echo':>26s}"
      f" {'n(eh)':>6s} {'toward/side/away':>17s}")

    def prof(c, pre, nkey):
        n = c[nkey]
        if not n:
            return "        -                 "
        return "/".join(f"{pct(c[f'{pre}|{x}'], n):.0f}" for x in ("S", "T", "R", "split", "sprint"))

    for n in names:
        c = teams[n].c
        base_n = sum(c[f"act|{p}"] for p in PHASES)
        base = "/".join(f"{pct(sum(c[f'act_{x}|{p}'] for p in PHASES), base_n):.0f}" for x in ("S", "T", "R", "split"))
        base += f"/{pct(sum(c[f'sprint|{p}'] for p in PHASES), base_n):.0f}"
        tot = c["se_dir|toward"] + c["se_dir|side"] + c["se_dir|away"]
        dirs = "/".join(f"{pct(c[f'se_dir|{x}'], tot):.0f}" for x in ("toward", "side", "away")) if tot else "-"
        P(f"{n[:22]:22s} {base:>26s} {prof(c, 'se_enemy_head', 'se_enemy_head|n'):>26s}"
          f" {prof(c, 'se_quiet', 'se_quiet|n'):>26s} {c['se_enemy_head|n']:>6d} {dirs:>17s}")

    P("\n=== DECISIONS AFTER RECEIVING A TEAMMATE'S MESSAGE (receiver's next action) ===")
    P(f"{'team':22s} {'no msg S/T/R/split/sprint':>26s} {'got msg S/T/R/split/sprint':>28s} {'n(recv)':>8s}"
      f" {'msgs->ally':>10s} {'enemy msgs in':>13s}")
    for n in names:
        c = teams[n].c
        P(f"{n[:22]:22s} {prof(c, 'rc_norecv', 'rc_norecv|n'):>26s} {prof(c, 'rc_recv', 'rc_recv|n'):>28s}"
          f" {c['rc_recv|n']:>8d} {c['msg_to_ally']:>10d} {c['msg_from_enemy']:>13d}")

    P("\n=== PAYLOAD LAYOUT AND DECODED FIELDS ===")
    P("layout: bit 63 (left) .. bit 0 (right); 1/0 = constant, . = varies. fields: match rate, target, shift, width")
    for n in names:
        layout, best = decode_payloads(teams[n].res)
        if layout is None:
            P(f"{n[:22]:22s} (too few messages)")
            continue
        P(f"{n[:22]:22s} {layout}")
        for m, name, s, wd in best:
            P(f"{'':22s}   {m * 100:5.1f}%  {name:10s} bits {s + wd - 1}..{s}  (width {wd})")

    text = "\n".join(out)
    print(text)


if __name__ == "__main__":
    main()
