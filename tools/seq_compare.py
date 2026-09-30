"""Candidate vs base, PAIRED and SEQUENTIAL: stop as soon as the evidence is clear (generous SPRT).

    python tools/seq_compare.py cand_x --base-prefix ladder/open_cand_y10_vs_ --maps schooltime,slithery_fight,portals \
        --seeds 2 [--out ladder/seq_cand_x.txt]

The base's per-game results already exist (tourney.py output files <base-prefix><opponent>.txt, same maps/seeds). The
candidate plays the same opponents one at a time (tourney.py, same seeds), and every game is paired with the base's game
on the same opponent/map/side/seed. Only discordant pairs carry information (cand won & base lost = b, the reverse =
c); after each opponent a Wald SPRT on p = b/(b+c) tests H0 p = 0.5 vs H1 p = 0.65 with alpha = beta = 0.15 (bounds
+-1.73). Stops early with BETTER / NOT BETTER, else plays all opponents.
"""
import argparse
import math
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OPPS = ["opponents/s475", "opponents/s476", "opponents/vb17", "opponents/vb18", "viper_nn", "baselines/y7_12_nn1"]
LINE = re.compile(r"^\[(WIN |LOSS|DRAW)\]\s+(\S+)\s+as (A|B) seed (\d+)")
SCORE = {"WIN ": 1.0, "LOSS": 0.0, "DRAW": 0.5}


def parse(text):
    return {(m.group(2), m.group(3), m.group(4)): SCORE[m.group(1)]
            for l in text.replace("\x00", "").splitlines() if (m := LINE.match(l.strip()))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cand")
    ap.add_argument("--base-prefix", required=True)
    ap.add_argument("--maps", required=True)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--opps", default=",".join(OPPS))
    ap.add_argument("--p1", type=float, default=0.65)
    ap.add_argument("--alpha", type=float, default=0.15)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    out = open(a.out or ROOT / "ladder" / f"seq_{pathlib.Path(a.cand).name}.txt", "w", encoding="utf-8")
    def say(s):
        print(s, flush=True); out.write(s + "\n"); out.flush()
    bound = math.log((1 - a.alpha) / a.alpha)
    b = c = 0; cw = bw = n = 0.0
    for opp in a.opps.split(","):
        name = opp.split("/")[-1]
        bf = ROOT / f"{a.base_prefix}{name}.txt"
        if not bf.exists():
            say(f"{name}: no base results ({bf}), skipped"); continue
        base = parse(bf.read_text(encoding="utf-8", errors="replace"))
        r = subprocess.run([sys.executable, "tools/tourney.py", a.cand, opp, "--maps", a.maps, "--seeds", str(a.seeds),
                            "-j", "10"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        cand = parse(r.stdout)
        for k, v in cand.items():
            if k not in base: continue
            n += 1; cw += v; bw += base[k]
            if v > base[k]: b += 1
            elif v < base[k]: c += 1
        llr = b * math.log(a.p1 / 0.5) + c * math.log((1 - a.p1) / 0.5)
        say(f"{name}: cand {sum(cand.values()):g}/{len(cand)}  | cumulative paired: cand {cw:g} vs base {bw:g} of {n:g};"
            f" discordant b={b} c={c}  LLR {llr:+.2f} (bounds +-{bound:.2f})")
        if llr >= bound:
            say(f"VERDICT {a.cand}: BETTER (early stop)"); return
        if llr <= -bound:
            say(f"VERDICT {a.cand}: NOT BETTER (early stop)"); return
    say(f"VERDICT {a.cand}: no decision after all opponents (cand {cw:g} vs base {bw:g} of {n:g})")


if __name__ == "__main__":
    main()
