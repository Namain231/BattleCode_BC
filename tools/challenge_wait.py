"""Wait for challenge battles to finish, download their replays, and report results.

    python tools/challenge_wait.py OUTDIR OUR_SUBMISSION_ID battleId [battleId ...]

The API key comes from the UNSWBC_KEY environment variable.
"""
import json
import os
import pathlib
import subprocess
import sys
import time

BASE = "https://game.battlecode.au/api/v1"
KEY = os.environ["UNSWBC_KEY"]
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
ours = sys.argv[2]
battles = sys.argv[3:]


def get(path):
    for attempt in range(10):
        r = subprocess.run(["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {KEY}"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(5 + 5 * attempt)  # rate limited or a blip: back off and retry
    raise RuntimeError(f"no JSON from {path}")


while True:
    games = []
    for b in battles:
        d = get(f"/battles/{b}")
        opp = d["teamBName"] if d["teamAName"] == "Bhole Chature" else d["teamAName"]
        side = "a" if d["teamAName"] == "Bhole Chature" else "b"
        for g in d.get("games", []):
            games.append((g["id"], opp, g["mapName"], g["status"], g["winner"], side))
    done = sum(1 for g in games if g[3] in ("completed", "failed", "crashed"))
    print(f"{done}/{len(games)} done", flush=True)
    if done == len(games):
        break
    time.sleep(15)

wins = 0
for gid, opp, mp, st, win, side in games:
    ok = win == side
    wins += ok
    print(f"{'W' if ok else 'L'} {opp:12s} {mp}")
    subprocess.run(["curl", "-sL", "-o", str(out / f"{gid}.replay"), f"{BASE}/battles/{gid}/replay",
                    "-H", f"Authorization: Bearer {KEY}"])
print(f"total {wins}/{len(games)}")
