"""Collect top teams' replays from the start of their latest rating climb (older games are a weaker bot).

    UNSWBC_KEY=... python -u tools/slope_collect.py [--top 20] [--every 20] [--drop 50] [--out ladder/slope]

The API only shows a team's ~6 most recent battles, so this polls the top-N profiles every --every minutes and
keeps every new battle played after the team's slope start: walking back from its latest rating, the lowest point
before an earlier value more than --drop above it (the latest climb starts there). A team falling by more than
--drop from its recent peak has its slope start at "now", so nothing is kept until it climbs again.
Writes <out>/<teamId>/<gameId>.replay, <out>/index.json (scout.py format + "at") and <out>/slopes.json.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

BASE = "https://game.battlecode.au/api/v1"
KEY = os.environ["UNSWBC_KEY"]


def get(path):
    for attempt in range(5):
        r = subprocess.run(["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {KEY}"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(5 + 5 * attempt)
    return {}


def slope_start(history, drop):
    """Date where the latest climb began (see module doc)."""
    if not history:
        return ""
    m, t = history[-1]["elo"], history[-1]["date"]
    for h in reversed(history[:-1]):
        if h["elo"] > m + drop:
            break
        if h["elo"] < m:
            m, t = h["elo"], h["date"]
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--every", type=float, default=20, help="minutes between polls")
    ap.add_argument("--drop", type=int, default=50)
    ap.add_argument("--out", default="ladder/slope")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--since", default="", help="ISO time: ignore battles before it (new rules: 2026-10-01T05:30)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ix_path = out / "index.json"
    index = json.loads(ix_path.read_text(encoding="utf-8")) if ix_path.exists() else []
    seen_battles = {g["battle"] for g in index}
    while True:
        board = get("/leaderboard")
        rows = board.get("teams", board) if isinstance(board, dict) else board
        rows = sorted(rows, key=lambda t: t.get("rank") or 1e9)[:a.top]
        slopes, added = {}, 0
        for t in rows:
            tid, name = t["id"], t["name"]
            prof = get(f"/teams/{tid}")
            t0 = max(slope_start(prof.get("history", []), a.drop), a.since)
            slopes[tid] = {"team": name, "rank": t.get("rank"), "elo": t.get("elo"), "slopeStart": t0}
            for b in prof.get("recent", []):
                if b["id"] in seen_battles or b["at"] < t0:
                    continue
                d = get(f"/battles/{b['id']}")
                if "games" not in d or any(g.get("status") != "completed" for g in d["games"]):
                    continue   # unfinished: pick it up on a later poll
                seen_battles.add(b["id"])
                side = "A" if d["match"]["teamAId"] == tid else "B"
                opp = d["teamBName"] if side == "A" else d["teamAName"]
                opp_elo = d["teamBElo"] if side == "A" else d["teamAElo"]
                tdir = out / str(tid); tdir.mkdir(exist_ok=True)
                for g in d["games"]:
                    path = tdir / f"{g['id']}.replay"
                    if not path.exists():
                        subprocess.run(["curl", "-sL", "-o", str(path), f"{BASE}/battles/{g['id']}/replay",
                                        "-H", f"Authorization: Bearer {KEY}"])
                    index.append({"teamId": tid, "team": name, "rank": t.get("rank"), "elo": t.get("elo"),
                                  "battle": b["id"], "game": g["id"], "map": g["mapName"], "side": side,
                                  "opponent": opp, "opponentElo": opp_elo, "winner": (g.get("winner") or "").upper(),
                                  "at": b["at"], "path": str(path)})
                    added += 1
                time.sleep(0.6)
            time.sleep(0.6)
        ix_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "slopes.json").write_text(json.dumps(slopes, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{time.strftime('%H:%M')}] +{added} games, {len(index)} total from {len({g['teamId'] for g in index})} teams",
              flush=True)
        if a.once:
            break
        time.sleep(a.every * 60)


if __name__ == "__main__":
    main()
