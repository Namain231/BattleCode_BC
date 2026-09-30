"""Compare trap-related deaths for top teams and our losses.

    python tools/trap_compare.py --n 25 [--maps Schooltime,Portals]

Rates are deaths per 100 dragon-rounds alive. Replay decoding is deliberately
uncached so this analysis never creates .pkl files beside the source replays.
"""
import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from replay import _decode, DEATHS  # noqa: E402

PHASES = ((0, 100), (100, 300), (300, 500))
REASONS = list(DEATHS)


def map_name(text):
    lines = text.splitlines()
    return next((line.split(" ", 1)[1].strip() for line in lines
                 if line.startswith("MAP_NAME ")), lines[0].strip() if lines else "?")


def analyse(path, focus_team):
    rep = _decode(path)
    teams, bodies = {}, {}
    next_id = 0
    for line in rep["map"].splitlines():
        p = line.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2])
            coords = [int(v) for v in p[3:3 + 2 * n]]
            teams[next_id] = t
            bodies[next_id] = [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
            next_id += 1
    alive = set(teams)
    rnd = 0
    last_round = 0
    alive_rounds = [[0] * len(PHASES) for _ in (0, 1)]
    deaths = [[defaultdict(int) for _ in PHASES] for _ in (0, 1)]
    trap_lengths = [[[] for _ in PHASES] for _ in (0, 1)]

    def accrue(stop):
        lo, hi = max(0, last_round), min(500, stop)
        if hi <= lo:
            return
        for pi, (a, b) in enumerate(PHASES):
            span = max(0, min(hi, b) - max(lo, a))
            if span:
                for t in (0, 1):
                    alive_rounds[t][pi] += sum(1 for i in alive if teams.get(i) == t) * span

    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            new_round = max(0, min(500, e["round"]))
            accrue(new_round)
            rnd = e["round"]
            last_round = new_round
        elif k == "dragonUpdate":
            i, head, tail = e["id"], e.get("head"), e.get("tail")
            b = bodies.get(i)
            if b is not None and head is not None:
                if not b or b[0] != head:
                    b.insert(0, head)
                while len(b) > 1 and b[-1] != tail:
                    b.pop()
        elif k == "dragonSplit":
            teams[e["child"]] = e["team"]
            bodies[e["child"]] = e.get("childBody") or []
            bodies[e["parent"]] = e.get("parentBody") or bodies.get(e["parent"], [])
            alive.add(e["child"])
        elif k == "dragonDeath":
            i = e["id"]
            t = teams.get(i)
            if t in (0, 1):
                pi = next((j for j, (a, b) in enumerate(PHASES) if a <= rnd < b), None)
                reason_id = e.get("reason", -1)
                reason = DEATHS[reason_id] if 0 <= reason_id < len(DEATHS) else "unknown"
                if pi is not None:
                    deaths[t][pi][reason] += 1
                    if reason in ("hit wall", "hit self"):
                        trap_lengths[t][pi].append(len(bodies.get(i, [])))
            alive.discard(i)
    accrue(500)
    return map_name(rep["map"]), focus_team, alive_rounds, deaths, trap_lengths


def empty_stats():
    return {"rounds": [0] * 3,
            "deaths": [defaultdict(int) for _ in PHASES],
            "lengths": [[] for _ in PHASES]}


def add(stats, result, team, label):
    _, _, rounds, deaths, lengths = result
    s = stats[(label, "focus")]
    o = stats[(label, "other")]
    for p in range(3):
        s["rounds"][p] += rounds[team][p]
        o["rounds"][p] += rounds[1 - team][p]
        for reason in REASONS:
            s["deaths"][p][reason] += deaths[team][p][reason]
            o["deaths"][p][reason] += deaths[1 - team][p][reason]
        s["lengths"][p].extend(lengths[team][p])
        o["lengths"][p].extend(lengths[1 - team][p])


def resolve_path(path):
    return path if os.path.isabs(path) else os.path.join(ROOT, path.replace("\\", os.sep))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25, help="maximum games in each group")
    ap.add_argument("--maps", default="", help="comma-separated map names; default all")
    args = ap.parse_args()
    wanted = {x.strip().lower() for x in args.maps.split(",") if x.strip()}
    groups = {"top wins": [], "top losses": [], "our losses": []}
    with open(os.path.join(ROOT, "ladder", "slope", "index.json"), encoding="utf-8") as f:
        entries = json.load(f)
    for row in entries:
        if int(row.get("rank", 999999)) > 5 or (wanted and row.get("map", "").lower() not in wanted):
            continue
        group = "top wins" if row.get("winner") == row.get("side") else "top losses"
        if len(groups[group]) < args.n:
            groups[group].append((resolve_path(row["path"]), 0 if row["side"] == "A" else 1))
    loss_root = os.path.join(ROOT, "ladder", "losses")
    for folder, _, files in os.walk(loss_root):
        for name in sorted(files):
            if not name.endswith(".replay") or len(groups["our losses"]) >= args.n:
                continue
            path = os.path.join(folder, name)
            try:
                # Decode once here to identify our side; analyse() will decode it again.
                rep = _decode(path)
                side = 0 if rep.get("botA") else 1 if rep.get("botB") else None
                if side is None:
                    continue
                if wanted and map_name(rep["map"]).lower() not in wanted:
                    continue
                if rep.get("result", {}).get("winner") == side:
                    continue
                groups["our losses"].append((path, side))
            except (OSError, ValueError, IndexError, KeyError):
                continue

    stats = defaultdict(empty_stats)
    errors = []
    for group, games in groups.items():
        for path, focus_team in games:
            try:
                result = analyse(path, focus_team)
                add(stats, result, focus_team, group)
            except (OSError, ValueError, IndexError, KeyError) as exc:
                errors.append(f"{path}: {exc}")

    out = ["Trap comparison: deaths per 100 dragon-rounds alive",
           f"Games requested/group: {args.n}; maps: {', '.join(sorted(wanted)) if wanted else 'all'}",
           "Rates are shown as focus / other. Trap length is mean dying length for hit wall + hit self.", ""]
    out.append(f"{'group':12} {'team':7} {'phase':9} " + " ".join(f"{r[:12]:>12}" for r in REASONS) +
               f"  {'trap len':>8} {'dragon-rd':>10}")
    for group in groups:
        for allegiance in ("focus", "other"):
            s = stats[(group, allegiance)]
            for p, (a, b) in enumerate(PHASES):
                den = s["rounds"][p]
                vals = [100 * s["deaths"][p][r] / den if den else 0.0 for r in REASONS]
                lens = s["lengths"][p]
                mean_len = sum(lens) / len(lens) if lens else 0.0
                out.append(f"{group:12} {allegiance:7} {a:03d}-{b:<3d} " +
                           " ".join(f"{v:12.3f}" for v in vals) +
                           f"  {mean_len:8.2f} {den:10d}")
    out.append("")
    out.append("Games used: " + ", ".join(f"{g}={len(v)}" for g, v in groups.items()))
    if errors:
        out.append(f"Skipped unreadable replays: {len(errors)}")
        out.extend(errors[:20])
    report = "\n".join(out) + "\n"
    print(report, end="")
    target = os.path.join(ROOT, "ladder", "trap_compare.txt")
    with open(target, "w", encoding="utf-8") as f:
        f.write(report)


if __name__ == "__main__":
    main()
