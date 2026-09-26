"""Find ranked-challenge targets: teams rated above us whose rating is falling.

    UNSWBC_KEY=... python tools/find_targets.py [--max-above 250] [--top 15]

A team on a downward slope is usually running a bot weaker than its rating, so beating
it pays more than its current form deserves. Always confirm with a short unranked test
(5 games) before spending a ranked challenge.
"""
import argparse
import json
import os
import subprocess

BASE = "https://game.battlecode.au/api/v1"


def get(path):
    r = subprocess.run(["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(r.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-above", type=int, default=250)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--since", default="", help="ISO time from which to measure the drop (default: 12h of history)")
    a = ap.parse_args()
    me = get("/team")["team"]
    ours = me["elo"]
    board = get("/leaderboard")
    rows = board.get("teams", board) if isinstance(board, dict) else board
    out = []
    for t in rows:
        e = t.get("elo") or 0
        if not (ours < e <= ours + a.max_above) or not (t.get("settings") or {}).get("ranked"):
            continue
        hist = t.get("history") or []
        if len(hist) < 2:
            continue
        recent = hist[-12:] if not a.since else [h for h in hist if h["date"] >= a.since]
        if not recent:
            continue
        peak = max(h["elo"] for h in recent)
        out.append((peak - e, e, t["id"], t["name"]))
    out.sort(reverse=True)
    print(f"our elo {ours}; candidates rated up to {a.max_above} above us, by recent drop:")
    for drop, e, tid, name in out[:a.top]:
        print(f"  drop {drop:4d}  elo {e}  id {tid:5d}  {name}")


if __name__ == "__main__":
    main()
