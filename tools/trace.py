"""Play one verbose sandbox match and print what chosen dragons did each round.

    python tools/trace.py maps/arena.map viper_v6 starter_bot --seed 5 [--ids 0,2] [--team A]
"""
import argparse
import re
import subprocess

HEAD = re.compile(r"^round (\d+): bot (\d+) \(team (A|B)\) (stdout:|died: .*|points .*)$")

ap = argparse.ArgumentParser()
ap.add_argument("map")
ap.add_argument("a")
ap.add_argument("b")
ap.add_argument("--seed", default="5")
ap.add_argument("--ids", default="")
ap.add_argument("--team", default="A")
ap.add_argument("--rounds", default="0-500")
ap.add_argument("--deaths", action="store_true", help="only show the turns just before each death")
ap.add_argument("--ctx", type=int, default=3)
args = ap.parse_args()
lo, hi = map(int, args.rounds.split("-"))
ids = {int(x) for x in args.ids.split(",") if x}

out = subprocess.run(["unswbc", "run", args.map, args.a, args.b, "--sandbox", "--no-replay", "--seed", args.seed, "-v"],
                     capture_output=True, text=True, errors="replace").stdout
cur = None
lines = []
history = {}


def flush():
    if cur and lines:
        r, bid, team = cur
        if team == args.team and (not ids or bid in ids) and lo <= r <= hi:
            keep = [l for l in lines if not l.startswith(("PROTOCOL", "ENDTURN"))]
            text = f"r{r:3d} #{bid}: " + " | ".join(keep)
            if args.deaths:
                history.setdefault(bid, []).append(text)
            else:
                print(text)


for line in out.splitlines():
    m = HEAD.match(line)
    if m:
        flush()
        lines = []
        r, bid, team, what = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
        if what.startswith("died"):
            if team == args.team:
                if args.deaths:
                    for t in history.get(bid, [])[-args.ctx:]:
                        print(t)
                print(f"r{r:3d} #{bid}: *** {what}")
            cur = None
        elif what.startswith("points"):
            cur = None
        else:
            cur = (r, bid, team)
        continue
    if cur:
        lines.append(line.strip())
flush()
for line in out.splitlines():
    if "wins" in line or "draw" in line:
        print(line)
