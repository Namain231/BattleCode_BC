"""Aggregate behaviour profiles of scouted teams (see scout.py).

    python tools/scout_report.py [ladder/scout]
"""
import collections
import json
import pathlib
import statistics
import struct
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import replay  # noqa: E402
from replay import load, DEATHS  # noqa: E402

CHECK = (50, 100, 200, 300, 400, 499)


def analyse(path, side):
    rep = load(path)
    lines = rep["map"].splitlines()
    W, H = map(int, lines[0].split()[1:3])
    team, body, nid = {}, {}, 0
    for l in lines:
        p = l.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t; body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    alive = set(team)
    rnd = 0
    m = collections.Counter()
    snaps = {}
    splits = []
    deaths = collections.Counter()
    late_feed_near = 0
    texts = collections.Counter()
    sonar_vals = collections.Counter()
    first_split = None

    def dist(a, b):
        dx = abs(a[0] - b[0]); dy = abs(a[1] - b[1])
        return min(dx, W - dx) + min(dy, H - dy)

    def snap():
        mine = [len(body[i]) for i in alive if team[i] == side]
        theirs = [len(body[i]) for i in alive if team[i] != side]
        return (len(mine), max(mine or [0]), sum(mine), len(theirs), max(theirs or [0]))

    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd in CHECK:
                snaps[rnd] = snap()
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]
            if b[0] != e["head"]: b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]: b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            if e["team"] == side:
                splits.append((rnd, len(e["parentBody"]) + len(e["childBody"]), len(e["childBody"])))
                if first_split is None: first_split = rnd
            body[e["child"]] = e["childBody"]; body[e["parent"]] = e["parentBody"]; alive.add(e["child"])
        elif k == "dragonDeath":
            i = e["id"]
            if team.get(i) == side:
                why = DEATHS[e["reason"]]
                deaths[why] += 1
                if rnd >= 250:
                    mine = [j for j in alive if team[j] == side and j != i]
                    if mine:
                        q = max(mine, key=lambda j: len(body[j]))
                        if len(body[q]) >= 8 and dist(body[i][0], body[q][0]) <= 4:
                            late_feed_near += 1
                    if why == "no valid action": m["late_suicide"] += 1
            elif e["reason"] == 3 and team.get(i) is not None:
                m["h2h_kills"] += 1
            alive.discard(i)
        elif k == "dragonAction" and team.get(e["id"]) == side:
            if e.get("act") == "move":
                m["moves"] += 1
                if len(e.get("dirs", "")) > 1: m["sprints"] += 1
        elif k in ("dragonIndicator", "dragonLog") and team.get(e["id"]) == side:
            texts[e["text"][:50]] += 1
    res = rep.get("result") or {}
    snaps[500] = snap()
    return {"snaps": snaps, "splits": splits, "deaths": deaths, "m": m, "late_feed_near": late_feed_near,
            "texts": texts, "first_split": first_split, "final": res.get("AB"[side]), "opp_final": res.get("AB"[1 - side]),
            "end": res.get("endReason")}


def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ladder/scout")
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    by_team = collections.defaultdict(list)
    for g in index:
        by_team[(g["rank"], g["team"], g["elo"], g["teamId"])].append(g)
    for (rank, name, elo, tid), games in sorted(by_team.items()):
        rows = []
        for g in games:
            path = root / str(tid) / f"{g['game']}.replay"
            try:
                a = analyse(path, 0 if g["side"] == "A" else 1)
            except Exception as ex:  # noqa: BLE001
                continue
            a["win"] = g["winner"] == g["side"]; a["map"] = g["map"]; a["opp"] = g["opponent"]
            rows.append(a)
        if not rows:
            continue
        n = len(rows)
        wins = sum(r["win"] for r in rows)

        def avg_snap(r_, idx):
            vals = [r["snaps"][r_][idx] for r in rows if r_ in r["snaps"]]
            return statistics.mean(vals) if vals else 0

        splits = [s for r in rows for s in r["splits"]]
        child = collections.Counter(s[2] for s in splits)
        parent = [s[1] for s in splits]
        deaths = collections.Counter()
        for r in rows: deaths.update(r["deaths"])
        m = collections.Counter()
        for r in rows: m.update(r["m"])
        texts = collections.Counter()
        for r in rows: texts.update(r["texts"])
        fs = [r["first_split"] for r in rows if r["first_split"] is not None]
        print(f"\n#{rank} {name} ({elo}) — {n} games, won {wins} (vs {collections.Counter(r['opp'] for r in rows).most_common(3)})")
        print("   units   @50/100/200/300/400/end: " + "/".join(f"{avg_snap(x, 0):.0f}" for x in (50, 100, 200, 300, 400, 500)))
        print("   longest @50/100/200/300/400/end: " + "/".join(f"{avg_snap(x, 1):.0f}" for x in (50, 100, 200, 300, 400, 500))
              + f"   (opponent longest end {avg_snap(500, 4):.0f})")
        if splits:
            print(f"   splits/game {len(splits) / n:.0f}; first split round median {statistics.median(fs) if fs else '-'}; "
                  f"parent len median {statistics.median(parent)}; child sizes {child.most_common(4)}")
        else:
            print("   no splits")
        per = {k: round(v / n, 1) for k, v in deaths.items()}
        print(f"   deaths/game {per}; late suicides/game {m['late_suicide'] / n:.1f}; late deaths next to own queen/game "
              f"{sum(r['late_feed_near'] for r in rows) / n:.1f}")
        print(f"   head-on kills/game {m['h2h_kills'] / n:.1f}; sprints per 1000 moves {1000 * m['sprints'] / max(1, m['moves']):.1f}")
        by_map = collections.defaultdict(list)
        for r in rows: by_map[r["map"]].append(r["win"])
        print("   maps: " + ", ".join(f"{k} {sum(v)}/{len(v)}" for k, v in sorted(by_map.items())))
        if texts:
            print(f"   leaked debug text: {texts.most_common(4)}")


if __name__ == "__main__":
    main()
