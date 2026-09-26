"""Download recent public replays of the top-ranked teams, recording which side each team played.

    UNSWBC_KEY=... python tools/scout.py [--top 12] [--per-team 10] [--out ladder/scout]

Writes <out>/<teamId>/<gameId>.replay and <out>/index.json with
{teamId, team, rank, elo, game, map, side, opponent, opponentElo, winner}.
"""
import argparse
import json
import os
import pathlib
import subprocess
import time

BASE = "https://game.battlecode.au/api/v1"
KEY = os.environ["UNSWBC_KEY"]


def get(path):
    for attempt in range(8):
        r = subprocess.run(["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {KEY}"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(4 + 4 * attempt)
    raise RuntimeError(f"no JSON from {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--per-team", type=int, default=10)
    ap.add_argument("--out", default="ladder/scout")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    board = get("/leaderboard")
    rows = board.get("teams", board) if isinstance(board, dict) else board
    rows = sorted(rows, key=lambda t: t.get("rank") or 1e9)[:a.top]
    index = []
    for t in rows:
        tid, name = t["id"], t["name"]
        prof = get(f"/teams/{tid}")
        games = []
        for b in prof.get("recent", []):
            if len(games) >= a.per_team:
                break
            d = get(f"/battles/{b['id']}")
            if "games" not in d:
                continue
            side = "A" if d["teamAName"] == name else "B"
            opp = d["teamBName"] if side == "A" else d["teamAName"]
            opp_elo = d["teamBElo"] if side == "A" else d["teamAElo"]
            for g in d["games"]:
                if g.get("status") != "completed" or len(games) >= a.per_team:
                    continue
                games.append({"teamId": tid, "team": name, "rank": t.get("rank"), "elo": t.get("elo"),
                              "game": g["id"], "map": g["mapName"], "side": side, "opponent": opp,
                              "opponentElo": opp_elo, "winner": (g.get("winner") or "").upper()})
            time.sleep(0.6)
        tdir = out / str(tid); tdir.mkdir(exist_ok=True)
        for g in games:
            path = tdir / f"{g['game']}.replay"
            if not path.exists():
                subprocess.run(["curl", "-sL", "-o", str(path), f"{BASE}/battles/{g['game']}/replay",
                                "-H", f"Authorization: Bearer {KEY}"])
        index += games
        print(f"#{t.get('rank')} {name} ({t.get('elo')}): {len(games)} games", flush=True)
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
