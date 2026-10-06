"""Round-robin matches between two bots in the judge's sandbox, in parallel.

    python tools/tourney.py viper_v7 baselines/v7_5 [--maps a,b] [--seeds 2] [-j 10] [--one-side]
                            [--timeout SECONDS] [--max-points 65] [--replays DIR]

Each map is played with the first bot as team A and again as team B (turn
order depends on dragon ids, so sides matter). C/C++ bots are built to wasm
once up front so the parallel runs do not race to compile them.

The sandbox prices every dragon-turn in CPU points exactly as the judge does, and the judge has no
limit on a whole game. So by default a game may take as long as it needs in wall time (--timeout 0);
a build is flagged when a turn's points exceed --max-points (millions), well under the judge's 100M.
Heavy maps are started first so they do not all end up competing for the cores at the end.
"""
import argparse
import concurrent.futures as cf
import hashlib
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
HEAVY = ["slithery_fight", "schooltime", "portals", "devil", "big_empty", "trauma", "autarky", "stronghold"]
GAME_TIMEOUT = 0


def git_head():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "?"


def bot_hash(bot):
    p = ROOT / bot / "main.cpp"
    if not p.is_file():
        p = pathlib.Path(bot) / "main.cpp"
    if not p.is_file():
        return "?"
    return hashlib.sha1(p.read_bytes()).hexdigest()[:12]


def map_path(map_name):
    mp = pathlib.Path(map_name if str(map_name).endswith(".map") else f"{map_name}.map")
    if "/" in str(map_name) or "\\" in str(map_name):
        return mp if mp.is_absolute() else ROOT / mp
    return ROOT / "maps" / mp


def prepare(bot: str) -> str:
    path = ROOT / bot
    if (path / "main.py").is_file():
        return str(path)
    from unswbc import clangtool
    return str(clangtool.build(path))


def play(map_name, a, b, seed, save=None):
    cmd = ["unswbc", "run", str(map_path(map_name)), a, b, "--sandbox", "--seed", str(seed)]
    cmd += ["-o", str(save) + ".replay"] if save else ["--no-replay"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                             timeout=GAME_TIMEOUT or None).stdout
    except subprocess.TimeoutExpired:
        return None, 500, "TIMEOUT", {"A": [], "B": []}, {}
    if save:
        pathlib.Path(str(save) + ".log").write_text(out, encoding="utf-8")
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
    ap.add_argument("--timeout", type=int, default=0, help="wall seconds per game, 0 = none")
    ap.add_argument("--max-points", type=float, default=55.0, help="flag turns above this many million points")
    ap.add_argument("--replays", help="folder for each game's replay and text log (default: none kept)")
    args = ap.parse_args()
    global GAME_TIMEOUT
    GAME_TIMEOUT = args.timeout
    out_dir = None
    if args.replays:
        out_dir = pathlib.Path(args.replays).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
    tag_a = pathlib.Path(args.bot).name
    tag_b = pathlib.Path(args.opponent).name

    print(f"commit {git_head()}  bot {args.bot} hash {bot_hash(args.bot)}"
          f"  vs {args.opponent} hash {bot_hash(args.opponent)}", flush=True)

    a_path, b_path = prepare(args.bot), prepare(args.opponent)
    jobs = []
    for m in args.maps.split(","):
        for s in range(args.seeds):
            seed = 1000 + 17 * s
            jobs.append((m, "A", a_path, b_path, seed))
            if not args.one_side:
                jobs.append((m, "B", b_path, a_path, seed))
    jobs.sort(key=lambda j: HEAVY.index(j[0]) if j[0] in HEAVY else len(HEAVY))

    start = time.time()
    wins = losses = draws = 0
    rows = []
    death_tally = {}
    peak_ms = 0.0
    over_budget = []
    with cf.ThreadPoolExecutor(args.j) as ex:
        futs = {ex.submit(play, m, x, y, s,
                          out_dir / f"{tag_a}-vs-{tag_b}-{pathlib.Path(m).stem}-{tag_a}_as_{side}-seed{s}"
                          if out_dir else None):
                (m, side, s) for m, side, x, y, s in jobs}
        for f in cf.as_completed(futs):
            m, side, s = futs[f]
            winner, rounds, how, deaths, peak = f.result()
            peak_ms = max(peak_ms, peak.get(side, 0.0))
            if peak.get(side, 0.0) > args.max_points:
                over_budget.append(f"{m} as {side} seed {s}: {peak[side]:.1f}M")
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
    if over_budget:
        print(f"CPU WARNING: turns above {args.max_points:.0f}M points (judge limit 100M): " + "; ".join(over_budget))


if __name__ == "__main__":
    main()
