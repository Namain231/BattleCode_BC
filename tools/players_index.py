"""Per-player view of a scout directory: one row per team (rank, rating, id, folder, games, W/L, maps played,
opponents) plus one section per team listing every game (map, side, opponent, result, replay path).

    uv run --python 3.11 python tools/players_index.py ladder/scout_lb        -> ladder/scout_lb/PLAYERS.md

Replays stay where scout.py put them (<dir>/<teamId>/<gameId>.replay), which is already one folder per player;
this adds the readable index the folder ids lack.
"""
import collections
import json
import pathlib
import sys


def main():
    root = pathlib.Path(sys.argv[1])
    idx = json.load(open(root / "index.json", encoding="utf-8"))
    teams = collections.defaultdict(list)
    for e in idx:
        teams[str(e["teamId"])].append(e)
    rows = []
    for tid, es in teams.items():
        e0 = es[0]
        w = sum(1 for e in es if e.get("winner") and e["winner"] == e["side"])
        l = sum(1 for e in es if e.get("winner") and e["winner"] != e["side"])
        rows.append((e0.get("rank") or 999, e0["team"], tid, e0.get("elo") or 0, es, w, l))
    rows.sort()
    out = ["# Players in " + root.as_posix(), "",
           "| rank | team | id | rating | games | W-L | maps | folder |", "|---|---|---|---|---|---|---|---|"]
    for rank, team, tid, elo, es, w, l in rows:
        maps = collections.Counter(e["map"] for e in es)
        mp = ", ".join(f"{m} {n}" for m, n in maps.most_common())
        out.append(f"| {rank} | {team} | {tid} | {elo:.0f} | {len(es)} | {w}-{l} | {mp} | `{tid}/` |")
    for rank, team, tid, elo, es, w, l in rows:
        out += ["", f"## #{rank} {team} (id {tid}, rating {elo:.0f}): {w}-{l}", "",
                "| game | map | side | opponent | opp rating | result |", "|---|---|---|---|---|---|"]
        for e in sorted(es, key=lambda e: (e["map"], str(e["game"]))):
            res = "W" if e.get("winner") == e["side"] else ("L" if e.get("winner") else "?")
            out.append(f"| `{tid}/{e['game']}.replay` | {e['map']} | {e['side']} | {e.get('opponent', '')} | "
                       f"{e.get('opponentElo') or 0:.0f} | {res} |")
    (root / "PLAYERS.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(rows)} players, {len(idx)} games -> {root / 'PLAYERS.md'}")


if __name__ == "__main__":
    main()
