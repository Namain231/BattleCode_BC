"""THE test: a candidate vs a frozen panel of different bots, all 10 maps, both sides. Never vs itself.

    python -u tools/panel.py cand_x [--seeds 1] [-j 10] [--panel opponents/s475,opponents/vb17,viper_nn,baselines/y7_12_nn1]

Prints wins per opponent and per map, and the total (draws count 0.5). Also appends one line to ladder/panel_log.jsonl
so results stay comparable across candidates. ~20 games per opponent per seed; 4 opponents ~ 10-15 min at -j 10.
"""
import argparse
import collections
import json
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAPS = "autarky,devil,trauma,trophy,queen_of_spades,default,dilemma,portals,slithery_fight,schooltime"
PANEL = "opponents/s475,opponents/vb17,viper_nn,baselines/y7_12_nn1"
LINE = re.compile(r"^\[(WIN |LOSS|DRAW)\]\s+(\S+)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cand")
    ap.add_argument("--panel", default=PANEL)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("-j", type=int, default=10)
    a = ap.parse_args()
    t0 = time.time()
    tot = [0.0, 0]; per_map = collections.defaultdict(lambda: [0.0, 0]); per_opp = {}
    for opp in a.panel.split(","):
        r = subprocess.run([sys.executable, "tools/tourney.py", a.cand, opp, "--maps", MAPS, "--seeds", str(a.seeds),
                            "-j", str(a.j)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        w = n = 0.0
        for l in r.stdout.splitlines():
            m = LINE.match(l)
            if m:
                s = {"WIN ": 1.0, "LOSS": 0.0, "DRAW": 0.5}[m.group(1)]
                w += s; n += 1; per_map[m.group(2)][0] += s; per_map[m.group(2)][1] += 1
        per_opp[opp] = (w, int(n)); tot[0] += w; tot[1] += int(n)
        print(f"{a.cand} vs {opp}: {w:g}/{int(n)}", flush=True)
    print("per map: " + "  ".join(f"{m} {v[0]:g}/{v[1]}" for m, v in sorted(per_map.items(), key=lambda x: x[1][0] / max(1, x[1][1]))))
    print(f"TOTAL {a.cand}: {tot[0]:g}/{tot[1]} = {tot[0] / max(1, tot[1]):.0%}  [{time.time() - t0:.0f}s]")
    with open(ROOT / "ladder" / "panel_log.jsonl", "a") as f:
        f.write(json.dumps({"cand": a.cand, "at": time.strftime("%m-%d %H:%M"), "total": tot, "per_opp": per_opp,
                            "per_map": per_map}) + "\n")


if __name__ == "__main__":
    main()
