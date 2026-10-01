"""Path directness: how straight do a team's dragons travel to the pearls they eat?

For a sample of eats: take the eating dragon's head K moves earlier (default 10), require that the pearl
already existed then (so it was a possible target), and compare the TRUE shortest distance (kelp- and
portal-aware BFS) from that earlier head to the pearl with the K moves actually spent. directness =
BFS distance / K, averaged; 1.0 = walked straight there. Also reports the share of eats reached by a
near-optimal route (moves <= BFS distance + 2).

This is the measurement that decides whether better graph search (Dijkstra with danger costs, A*, etc.)
would pay off: if a team's dragons already reach their food near the shortest-path bound, a better search
cannot buy much; if ours wander while the top teams walk straight, it can.

    uv run --python 3.11 python tools/path_efficiency.py ladder/scout_fresh ladder/scout_self [--k 10] [--sample 5]
"""
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from profile_style import parse_map  # noqa: E402
from replay import load  # noqa: E402


def bfs_to(nbr, src, dst, limit):
    if src == dst:
        return 0
    dist = {src: 0}
    q = collections.deque([src])
    while q:
        c = q.popleft()
        d = dist[c]
        if d >= limit:
            continue
        for n in nbr[c]:
            if n not in dist:
                if n == dst:
                    return d + 1
                dist[n] = d + 1
                q.append(n)
    return None


def analyse(path, side, K, sample, S):
    rep = load(path)
    w, h, nbr, _ = parse_map(rep["map"])
    team, body, nid = {}, {}, 0
    for line in rep["map"].splitlines():
        p = line.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t
            body[nid] = [c[2 * i + 1] * w + c[2 * i] for i in range(n)]
            nid += 1
    hist = collections.defaultdict(list)     # dragon -> head cell per move
    appeared = {}                            # cell -> round the current pearl appeared
    moves_at = collections.defaultdict(list)  # dragon -> rounds of each move
    rnd = 0
    count = 0
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
        elif k == "tileChange":
            c = e["tile"][1] * w + e["tile"][0]
            if e["pearl"]:
                appeared[c] = rnd
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            body[e["parent"]] = [q[1] * w + q[0] for q in e["parentBody"]]
            body[e["child"]] = [q[1] * w + q[0] for q in e["childBody"]]
            hist[e["child"]] = [body[e["child"]][0]]
            moves_at[e["child"]] = [rnd]
        elif k == "dragonUpdate" and e["head"]:
            d = e["id"]
            if d not in body:
                continue
            hd = e["head"][1] * w + e["head"][0]
            tl = e["tail"][1] * w + e["tail"][0] if e["tail"] else None
            b = body[d]
            before = len(b)
            if b[0] != hd:
                b.insert(0, hd)
                hist[d].append(hd)
                moves_at[d].append(rnd)
            if tl is not None:
                while len(b) > 1 and b[-1] != tl:
                    b.pop()
            if team.get(d) == side and len(b) > before:
                count += 1
                if count % sample:
                    continue
                H = hist[d]
                if len(H) <= K:
                    continue
                start = H[-1 - K]
                start_round = moves_at[d][-1 - K]
                if appeared.get(hd, 10 ** 9) > start_round:
                    continue  # pearl did not exist yet: not a routing decision
                dist = bfs_to(nbr, start, hd, K + 1)
                if dist is None:
                    continue
                ph = "early" if rnd < 100 else "mid" if rnd < 300 else "late"
                S["n"] += 1
                S[f"n|{ph}"] += 1
                S["dsum"] += dist / K
                S[f"dsum|{ph}"] += dist / K
                if dist >= K - 2:
                    S["near"] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--sample", type=int, default=5, help="analyse every Nth eat")
    a = ap.parse_args()
    stats = collections.defaultdict(collections.Counter)
    elo = {}
    for dd in a.dirs:
        root = pathlib.Path(dd)
        idx = {(str(e["teamId"]), str(e["game"])): e for e in json.load(open(root / "index.json", encoding="utf-8"))}
        for f in sorted(root.rglob("*.replay")):
            m = idx.get((f.parent.name, f.stem))
            if not m:
                continue
            elo[m["team"]] = m.get("elo") or 0
            try:
                analyse(f, 0 if m["side"] in ("A", 0) else 1, a.k, a.sample, stats[m["team"]])
            except Exception as exc:
                print(f"  ! {f}: {type(exc).__name__}: {exc}", file=sys.stderr)
    print(f"\nPath directness over the last {a.k} moves before an eat (true BFS distance / moves; 1.0 = straight)\n")
    print(f"{'team':24s} {'elo':>5s} {'n':>6s} {'direct':>7s} {'early|mid|late':>18s} {'near-optimal%':>13s}")
    for t in sorted(stats, key=lambda t: -stats[t]["dsum"] / max(1, stats[t]["n"])):
        S = stats[t]
        ph = "|".join(f"{S[f'dsum|{p}'] / S[f'n|{p}']:.2f}" if S[f"n|{p}"] else " nan" for p in ("early", "mid", "late"))
        print(f"{t[:24]:24s} {elo.get(t, 0):>5d} {S['n']:>6d} {S['dsum'] / max(1, S['n']):>7.2f} {ph:>18s}"
              f" {100 * S['near'] / max(1, S['n']):>13.0f}")


if __name__ == "__main__":
    main()
