"""Round-robin matches between two bots in the judge's sandbox, in parallel.

    python tools/tourney.py viper_v6 viper_v3 [--maps a,b] [--seeds 2] [-j 10] [--one-side]

Each map is played with the first bot as team A and again as team B (turn
order depends on dragon ids, so sides matter). C/C++ bots are built to wasm
once up front so the parallel runs do not race to compile them.
"""
import argparse
import concurrent.futures as cf
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAPS = ["arena", "Colosseum", "default_small", "trophy", "devil", "dilemma", "queen_of_spades",
        "default", "autarky", "stronghold", "trauma", "schooltime", "big_empty"]

RESULT = re.compile(r"team (A|B) wins after (\d+) rounds \((.*?)\)")
DRAW = re.compile(r"draw after (\d+) rounds")
DEATH = re.compile(r"round (\d+): bot (\d+) \(team (A|B)\) died: (.*)")
POINTS = re.compile(r"team (A|B) points per turn: .*max ([\d.]+)M")


def prepare(bot: str) -> str:
    path = ROOT / bot
    if (path / "main.py").is_file():
        return str(path)
    from unswbc import clangtool
    return str(clangtool.build(path))


def play(map_name, a, b, seed):
    cmd = ["unswbc", "run", str(ROOT / "maps" / f"{map_name}.map"), a, b, "--sandbox", "--no-replay",
           "--seed", str(seed)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=240).stdout
    except subprocess.TimeoutExpired:
        return None, 500, "TIMEOUT", {"A": [], "B": []}, {}
    winner, rounds, how = None, 500, "?"
    m = RESULT.search(out)
    if m:
        winner, rounds, how = m.group(1), int(m.group(2)), m.group(3)
    else:
        d = DRAW.search(out)
        if d:
            rounds, how = int(d.group(1)), "draw"
        else:
            how = "ERROR: " + out[-400:]
    deaths = {"A": [], "B": []}
    for r, bot_id, team, why in DEATH.findall(out):
        deaths[team].append(why.strip())
    peak = {t: float(v) for t, v in POINTS.findall(out)}
    return winner, rounds, how, deaths, peak


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bot")
    ap.add_argument("opponent")
    ap.add_argument("--maps", default=",".join(MAPS))
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("-j", type=int, default=10)
    ap.add_argument("--one-side", action="store_true")
    args = ap.parse_args()

    a_path, b_path = prepare(args.bot), prepare(args.opponent)
    jobs = []
    for m in args.maps.split(","):
        for s in range(args.seeds):
            seed = 1000 + 17 * s
            jobs.append((m, "A", a_path, b_path, seed))
            if not args.one_side:
                jobs.append((m, "B", b_path, a_path, seed))

    start = time.time()
    wins = losses = draws = 0
    rows = []
    death_tally = {}
    peak_ms = 0.0
    with cf.ThreadPoolExecutor(args.j) as ex:
        futs = {ex.submit(play, m, x, y, s): (m, side, s) for m, side, x, y, s in jobs}
        for f in cf.as_completed(futs):
            m, side, s = futs[f]
            winner, rounds, how, deaths, peak = f.result()
            peak_ms = max(peak_ms, peak.get(side, 0.0))
            for why in deaths[side]:
                death_tally[why] = death_tally.get(why, 0) + 1
            if winner is None:
                tag = "DRAW" if how == "draw" else "ERR "
                draws += 1
            elif winner == side:
                tag = "WIN "
                wins += 1
            else:
                tag = "LOSS"
                losses += 1
            line = (f"[{tag}] {m:16s} as {side} seed {s}: {rounds:3d} rounds ({how})"
                    f"  our deaths={len(deaths[side])} theirs={len(deaths['B' if side == 'A' else 'A'])}")
            rows.append((m, side, s, line))
            print(line, flush=True)
    total = wins + losses + draws
    print("=" * 72)
    print(f"{args.bot} vs {args.opponent}: {wins}W {losses}L {draws}D of {total}"
          f"  ({100.0 * wins / max(1, total):.0f}% wins)  in {time.time() - start:.0f}s")
    print(f"our death causes: {death_tally}   our peak points/turn: {peak_ms:.1f}M")


if __name__ == "__main__":
    main()
