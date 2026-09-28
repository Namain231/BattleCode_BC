"""Per-build ladder record, open vs maze maps, attributing each battle to our build via its first replay.

    UNSWBC_KEY=... python tools/build_record.py [--limit 200]

The battles API no longer says which of our submissions played; the replay header does (botA/botB = submission
id). One replay per battle is enough (a battle uses one build). Replays cached in ladder/attrib/.
Open maps: Portals, Slithery Fight, Schooltime; the rest are maze maps.
"""
import argparse
import collections
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import load  # noqa: E402

BASE = "https://game.battlecode.au/api/v1"
ROOT = pathlib.Path(__file__).resolve().parents[1]
OPEN = {"Portals", "Slithery Fight", "Schooltime"}
if "UNSWBC_KEY" not in os.environ and (ROOT / "secrets.env").exists():   # the key file of the private repo
    for line in (ROOT / "secrets.env").read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())


def get(path):
    for attempt in range(5):
        r = subprocess.run(["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(3 + 3 * attempt)
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    a = ap.parse_args()
    out = ROOT / "ladder" / "attrib"; out.mkdir(parents=True, exist_ok=True)
    battles = get(f"/battles?limit={a.limit}")
    battles = battles.get("battles", battles) if isinstance(battles, dict) else battles
    subs = get("/submissions")
    subs = subs.get("submissions", subs) if isinstance(subs, dict) else subs
    name = {str(s["id"]): s["name"] for s in subs}
    agg = collections.defaultdict(collections.Counter)
    for b in battles:
        if b.get("outcome") in ("live", "queued"):
            continue
        d = get(f"/battles/{b['id']}")
        ours_a = d.get("match", {}).get("teamAId") == 98
        games = [g for g in d.get("games", []) if g.get("status") == "completed"]
        if not games:
            continue
        p = out / f"{games[0]['id']}.replay"
        if not p.exists():
            subprocess.run(["curl", "-sL", "-o", str(p), f"{BASE}/battles/{games[0]['id']}/replay",
                            "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"])
        try:
            rep = load(str(p))
            sub = rep["botA"] if ours_a else rep["botB"]
        except Exception:
            sub = "?"
        for g in games:
            won = g.get("winner") == ("a" if ours_a else "b")
            kind = "open" if g.get("mapName") in OPEN else "maze"
            for rk in ("ranked" if b["ranked"] else "unranked", "all"):
                agg[(sub, kind, rk)]["n"] += 1
                agg[(sub, kind, rk)]["w"] += won
        time.sleep(0.3)

    def cell(sub, kind, rk):
        c = agg[(sub, kind, rk)]
        return f"{c['w']}/{c['n']} {100 * c['w'] / c['n']:3.0f}%" if c["n"] else "-"

    print(f"{'build':32s} {'open (all)':>13s} {'maze (all)':>13s} {'open ranked':>13s} {'maze ranked':>13s}")
    for sub in sorted({k[0] for k in agg}, key=lambda s: -sum(agg[(s, k, 'all')]['n'] for k in ('open', 'maze'))):
        print(f"{(sub + ' ' + name.get(sub, ''))[:32]:32s} {cell(sub, 'open', 'all'):>13s} {cell(sub, 'maze', 'all'):>13s}"
              f" {cell(sub, 'open', 'ranked'):>13s} {cell(sub, 'maze', 'ranked'):>13s}")


if __name__ == "__main__":
    main()
