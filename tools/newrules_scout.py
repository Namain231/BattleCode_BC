"""Download recent ladder games played under the new queen rules (after 2026-10-01 05:30 UTC) by the top teams.

    python tools/newrules_scout.py [--top 10] [--per-team 6] [--out D:/battlecode/tmp/newrules/top]

Replays are saved as <out>/<teamId>_<battleId>_<gameId>.replay with a sidecar index.jsonl (team, opponent, map, side).
Our side for tools/queen_report.py: the scouted team (file name has no _A_/_B_, so we write the side into index.jsonl
and also name the file <map>_<A|B>_<gameId>.replay inside <out>/<teamId>/).
"""
import argparse
import json
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ab_live as A  # noqa: E402
import os  # noqa: E402

CUTOFF = "2026-10-01T05:30"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10); ap.add_argument("--per-team", type=int, default=6)
    ap.add_argument("--out", default="D:/battlecode/tmp/newrules/top")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    idx = open(out / "index.jsonl", "a", encoding="utf-8")
    board = A.api("/leaderboard")
    rows = board if isinstance(board, list) else board.get("teams", board.get("leaderboard", board))
    for t in rows[:a.top]:
        tid = t["id"]
        prof = A.api(f"/teams/{tid}")
        recent = [b for b in prof.get("recent", []) if b.get("at", "") >= CUTOFF][:a.per_team]
        got = 0
        for b in recent:
            d = A.api(f"/battles/{b['id']}")
            games = d.get("games", []) if isinstance(d, dict) else []
            m = d.get("match", {})
            side = "A" if m.get("teamAId") == tid else "B"
            for g in games:
                gid = g.get("id")
                mp = str(g.get("mapName") or "map").replace(" ", "_").lower()
                td = out / str(tid); td.mkdir(exist_ok=True)
                path = td / f"{mp}_{side}_{gid}.replay"
                if not path.exists() or path.stat().st_size < 2000:
                    subprocess.run(["curl", "-sL", "-o", str(path), f"{A.BASE}/battles/{gid}/replay",
                                    "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"], check=False)
                    time.sleep(0.6)
                idx.write(json.dumps({"team": tid, "name": t.get("name"), "battle": b["id"], "game": gid, "map": mp,
                                      "side": side, "opponent": b.get("opponent"), "at": b.get("at")}) + "\n")
                got += 1
        print(f"{t.get('name')!s:28s} new-rules battles {len(recent)} games {got}")


if __name__ == "__main__":
    main()
