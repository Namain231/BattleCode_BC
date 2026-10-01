"""Bed farming, queen consolidation and split safety, per team, from replays.

Written to test three observations from watching Stockfish / forgot to mention / Cache me outside
(2026-09-30): (1) their dragons HANG AROUND pearl beds once found and multiply there, which lifts
population and elimination wins despite more self-hit deaths; (2) on Trauma their drones LEAVE THE
MAZE and die beside the queen (~r280), while ours get stuck inside; (3) they fire 3-4 sonar rays per
turn where we mostly fire one forward ray.

FARMING   rich bed = a tile whose mean respawn gap (minGap+maxGap)/2 <= --rich (default 25), from the
          map's own TILE data (what a bot can store as "favourable beds").
            at-bed%   dragon-turns with the head within Chebyshev 2 of a rich bed
            dwell     mean length (rounds) of an unbroken at-bed streak for one dragon
            eat@bed%  share of all eats made while at a rich bed
            split@bed% share of all splits made while at a rich bed (multiplying in place)
            bedctl%   share of rich beds with one of our heads within 2 (vs the opponent's)
QUEEN     queen = our longest dragon; at r250/300/350/400 the queen's length, the median true (kelp
          aware) distance from our other heads to her head, and the share of our units within 8 of her.
            open      median number of cells reachable within 3 steps of our heads, r250-350: small
                      numbers mean dragons sitting in maze corridors, large means open ground
            feed/50r  deaths beside a longer ally (feeding), per 50-round bin from r200
SAFETY    split->death5  share of splits after which the parent or the child dies within 5 rounds

    uv run --python 3.11 --with unswbc python tools/farming_profile.py ladder/scout_fresh [--maps Trauma]
"""
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from profile_style import parse_map  # noqa: E402
from replay import load  # noqa: E402

CHECK = (250, 300, 350, 400)


def phase_of(r):
    return "early" if r < 100 else "mid" if r < 300 else "late"


def bfs(nbr, src, limit=10 ** 9):
    dist = {src: 0}
    q = collections.deque([src])
    while q:
        c = q.popleft()
        if dist[c] >= limit:
            continue
        for n in nbr[c]:
            if n not in dist:
                dist[n] = dist[c] + 1
                q.append(n)
    return dist


MAPS_DIR = pathlib.Path(__file__).resolve().parents[1] / "maps"
_BEDS = None


def bed_gaps(map_name):
    """Exact per-tile (minGap, maxGap) from the bundled maps/*.map files, keyed by MAP_NAME.

    Public replays ZERO every TILE line (all '0 0'), hiding the respawn schedule -- only the pearls that
    actually spawn are visible. So bed data must come from our own copies of the maps. -> {cell: (lo, hi)}
    """
    global _BEDS
    if _BEDS is None:
        _BEDS = {}
        for f in list(MAPS_DIR.glob("*.map")) + list((MAPS_DIR.parent / "maps_gen").glob("*.map")) + list((MAPS_DIR.parent / "maps_dense").glob("*.map")):
            text = f.read_text()
            name, w, gaps = None, 0, {}
            for line in text.splitlines():
                p = line.split()
                if not p:
                    continue
                if p[0] == "MAP":
                    w = int(p[1])
                elif p[0] == "MAP_NAME":
                    name = " ".join(p[1:])
                elif p[0] == "TILE":
                    x, y, lo, hi = (int(v) for v in p[1:5])
                    if hi > 0:
                        gaps[y * w + x] = (lo, hi)
            if name:
                _BEDS[name.lower()] = gaps
    return _BEDS.get(map_name.lower(), {})


def analyse(path, side, rich_gap, S):
    rep = load(path)
    text = rep["map"]
    w, h, nbr, _ = parse_map(text)
    name = next((" ".join(l.split()[1:]) for l in text.splitlines() if l.startswith("MAP_NAME")), "")
    rich = [c for c, (lo, hi) in bed_gaps(name).items() if (lo + hi) / 2 <= rich_gap]
    rich_set = set(rich)
    # cells within Chebyshev 2 of a rich bed -> which bed (first found)
    near = {}
    for b in rich:
        bx, by = b % w, b // w
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                near.setdefault(((by + dy) % h) * w + (bx + dx) % w, b)
    open_cache = {}

    def openness(c):
        if c not in open_cache:
            open_cache[c] = len(bfs(nbr, c, 3))
        return open_cache[c]

    team, body, nid = {}, {}, 0
    for line in text.splitlines():
        p = line.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t
            body[nid] = [c[2 * i + 1] * w + c[2 * i] for i in range(n)]
            nid += 1
    alive = set(team)
    streak = collections.Counter()
    splits_watch = []       # (round, parent, child)
    rnd = 0
    S["games"] += 1
    S["rich_beds"] += len(rich)
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            ph = phase_of(rnd)
            own = [d for d in alive if team.get(d) == side and d in body]
            opp = [d for d in alive if team.get(d) != side and d in body]
            for d in own:
                S[f"dt|{ph}"] += 1
                hd = body[d][0]
                if hd in near:
                    S[f"atbed|{ph}"] += 1
                    streak[d] += 1
                elif streak[d]:
                    S["dwell_sum"] += streak[d]
                    S["dwell_n"] += 1
                    streak[d] = 0
            if rich and rnd % 25 == 0:
                mine = {near[body[d][0]] for d in own if body[d][0] in near}
                theirs = {near[body[d][0]] for d in opp if body[d][0] in near}
                S[f"bedctl_me|{ph}"] += len(mine)
                S[f"bedctl_op|{ph}"] += len(theirs)
                S[f"bedctl_n|{ph}"] += len(rich)
            if rnd in CHECK and own:
                q = max(own, key=lambda d: len(body[d]))
                dist = bfs(nbr, body[q][0])
                others = [dist.get(body[d][0], 999) for d in own if d != q]
                S["qlen|%d" % rnd] += len(body[q])
                S["qn|%d" % rnd] += 1
                if others:
                    others.sort()
                    S["qdist|%d" % rnd] += others[len(others) // 2]
                    S["qnear|%d" % rnd] += sum(1 for x in others if x <= 8) / len(others)
                    S["qd_n|%d" % rnd] += 1
            if 250 <= rnd <= 350 and rnd % 10 == 0:
                for d in own:
                    S["open_sum"] += openness(body[d][0])
                    S["open_n"] += 1
            # resolve split safety
            keep = []
            for (r0, par, ch) in splits_watch:
                if rnd - r0 > 5:
                    S["split_safe"] += 1
                else:
                    keep.append((r0, par, ch))
            splits_watch = keep
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
            if team.get(d) == side and moved and len(b) > before:
                S["eats"] += 1
                if hd in near:
                    S["eats_bed"] += 1
        elif k == "dragonSplit":
            par, ch = e["parent"], e["child"]
            team[ch] = e["team"]
            alive.add(ch)
            body[par] = [q[1] * w + q[0] for q in e["parentBody"]]
            body[ch] = [q[1] * w + q[0] for q in e["childBody"]]
            if e["team"] == side:
                S["splits"] += 1
                if body[par][0] in near:
                    S["splits_bed"] += 1
                splits_watch.append((rnd, par, ch))
        elif k == "dragonDeath":
            d = e["id"]
            alive.discard(d)
            if team.get(d) == side and d in body:
                hd, L = body[d][0], len(body[d])
                hit = [(r0, p, c) for (r0, p, c) in splits_watch if d in (p, c)]
                if hit:
                    S["split_dead"] += 1
                    splits_watch = [s for s in splits_watch if s not in hit]
                if rnd >= 200:
                    ally_longer = any(team.get(o) == side and o in body and len(body[o]) > L
                                      and abs(body[o][0] % w - hd % w) + abs(body[o][0] // w - hd // w) <= 2
                                      for o in alive)
                    if ally_longer:
                        S["feed|%d" % (rnd // 50 * 50)] += 1
    for d, s in streak.items():
        if s:
            S["dwell_sum"] += s
            S["dwell_n"] += 1


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--rich", type=float, default=25.0)
    ap.add_argument("--maps", default=None, help="comma list of map names (index 'map' field) to keep")
    ap.add_argument("--teams", default=None)
    a = ap.parse_args()
    keep_maps = set(m.strip().lower() for m in a.maps.split(",")) if a.maps else None
    keep_teams = set(a.teams.split(",")) if a.teams else None
    stats = collections.defaultdict(collections.Counter)
    for dd in a.dirs:
        root = pathlib.Path(dd)
        idx = {(str(e["teamId"]), str(e["game"])): e
               for e in json.load(open(root / "index.json", encoding="utf-8"))}
        for f in sorted(root.rglob("*.replay")):
            m = idx.get((f.parent.name, f.stem))
            if not m:
                continue
            if keep_maps and m["map"].lower().replace(" ", "_") not in keep_maps and m["map"].lower() not in keep_maps:
                continue
            if keep_teams and m["team"] not in keep_teams:
                continue
            side = 0 if m["side"] in ("A", 0) else 1
            try:
                analyse(f, side, a.rich, stats[m["team"]])
            except Exception as exc:
                print(f"  ! {f}: {type(exc).__name__}: {exc}", file=sys.stderr)

    names = sorted(stats, key=lambda n: -stats[n]["games"])
    print(f"\nrich bed = mean respawn gap <= {a.rich:g}.  e|m|l = early (r<100) | mid | late (r300+)\n")
    print(f"{'team':22s} {'g':>3s} {'at-bed% e|m|l':>15s} {'dwell':>6s} {'eat@bed%':>8s} {'split@bed%':>10s}"
          f" {'bedctl me/op% e|m|l':>24s} {'split->death5':>13s}")
    for n in names:
        S = stats[n]
        ab = "|".join(f"{pct(S[f'atbed|{p}'], S[f'dt|{p}']):3.0f}" for p in ("early", "mid", "late"))
        bc = "|".join(f"{pct(S[f'bedctl_me|{p}'], S[f'bedctl_n|{p}']):2.0f}/{pct(S[f'bedctl_op|{p}'], S[f'bedctl_n|{p}']):2.0f}"
                      for p in ("early", "mid", "late"))
        dwell = S["dwell_sum"] / S["dwell_n"] if S["dwell_n"] else float("nan")
        sd = pct(S["split_dead"], S["split_dead"] + S["split_safe"])
        print(f"{n[:22]:22s} {S['games']:>3d} {ab:>15s} {dwell:>6.1f} {pct(S['eats_bed'], S['eats']):>8.0f}"
              f" {pct(S['splits_bed'], S['splits']):>10.0f} {bc:>24s} {sd:>13.0f}")
    print(f"\n{'team':22s} " + " ".join(f"{'r%d qlen/dist/near8%%' % r:>22s}" for r in CHECK)
          + f" {'open':>6s} " + " ".join(f"{'feed%d' % b:>8s}" for b in (200, 250, 300, 350, 400, 450)))
    for n in names:
        S = stats[n]
        cols = []
        for r in CHECK:
            qn, dn = S["qn|%d" % r], S["qd_n|%d" % r]
            if not qn:
                cols.append(f"{'-':>22s}")
                continue
            cols.append(f"{S['qlen|%d' % r] / qn:6.1f}/{(S['qdist|%d' % r] / dn if dn else float('nan')):5.1f}/"
                        f"{(100 * S['qnear|%d' % r] / dn if dn else float('nan')):4.0f}%".rjust(22))
        op = S["open_sum"] / S["open_n"] if S["open_n"] else float("nan")
        fd = " ".join(f"{S['feed|%d' % b] / max(1, S['games']):>8.1f}" for b in (200, 250, 300, 350, 400, 450))
        print(f"{n[:22]:22s} " + " ".join(cols) + f" {op:>6.1f} {fd}")
    print("\nqlen = queen length; dist = median true distance of our other heads to her head; near8 = share"
          " within 8.\nopen = median-ish cells reachable within 3 steps (r250-350), low = inside maze"
          " corridors.\nfeedNNN = feeding deaths (beside a longer ally) per game in the 50-round bin"
          " starting at NNN.")


if __name__ == "__main__":
    main()
