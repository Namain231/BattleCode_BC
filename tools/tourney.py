
"""Round-robin matches between two bots in the judge's sandbox, in parallel.

    python tools/tourney.py viper_v7 baselines/v7_5 [--maps a,b] [--seeds 2] [-j 10] [--one-side]

Each map is played with the first bot as team A and again as team B (turn
order depends on dragon ids, so sides matter). C/C++ bots are built to wasm
once up front so the parallel runs do not race to compile them.

The tournament prints a live progress tracker and detailed statistics at the end.
"""
import argparse
import collections
import concurrent.futures as cf
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]

MAPS = [
    "arena", "Colosseum", "default_small", "trophy", "devil", "dilemma",
    "queen_of_spades", "default", "autarky", "stronghold", "trauma",
    "schooltime", "big_empty", "slithery_fight", "portals"
]

# Core panel for quick validation batches: every map a real S.4.7.6 ladder loss
# was traced to, so slithery_fight/schooltime (found 2026-09-30 to be
# catastrophic blind spots never covered by the old 6-map panel) are never
# excluded again. Use `--maps ,`.join(CORE_PANEL)` for fast iteration.
CORE_PANEL = [
    "trauma", "autarky", "trophy", "default", "dilemma", "devil",
    "slithery_fight", "schooltime",
]

RESULT = re.compile(r"team (A|B) wins after (\d+) rounds \((.*?)\)")
DRAW = re.compile(r"draw after (\d+) rounds")
DEATH = re.compile(r"round (\d+): bot (\d+) \(team (A|B)\) died: (.*)")
POINTS = re.compile(r"team (A|B) points per turn: .*max ([\d.]+)M")

# --judge zig: over-yonder.tech/games/loong's from-scratch Zig+wasmtime judge, built and verified
# byte-identical to `unswbc run --sandbox` in WSL2 (2026-09-30, see insights.md) -- ~2.4x faster on
# a real heavy matchup (viper_vS4.7 vs viper_v7.12, trophy: 58.9s vs 142.7s, identical winner/
# rounds/turns/points down to the exact number). Paths are this machine's WSL2 setup, not portable:
# built per s4_7_v4_and_beyond.md's WSL2 setup steps if this ever needs rebuilding elsewhere.
import os as _os
# Configurable per machine (env vars); defaults are the teammate's WSL2 setup.
ZIG_JUDGE_WSL = _os.environ.get("BC_ZIG_JUDGE", "/home/sohan/toolchains/zig-judge-out/bin/loong-judge")
ZIG_ENGINE_WSL = _os.environ.get("BC_ZIG_ENGINE", "/home/sohan/venv/lib/python3.14/site-packages/unswbc/unswbc_engine.wasm")
WSL_DISTRO = _os.environ.get("BC_WSL_DISTRO", "Ubuntu")
# Doc comment in the judge's main.zig / game.zig, verified against a real run's output.
ZIG_DEATH_REASONS = ["hit a wall", "hit itself", "hit another dragon", "lost a head-to-head", "no valid action"]
ZIG_END_REASONS = ["by elimination", "on length"]
ZIG_DRAW_REASONS = ["both teams eliminated", "equal length"]


def to_wsl_path(p) -> str:
    p = pathlib.Path(p).resolve()
    drive = p.drive[0].lower()
    rest = str(p)[len(p.drive) + 1:].replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def prepare(bot: str) -> str:
    path = ROOT / bot
    if (path / "main.py").is_file():
        return str(path)

    from unswbc import clangtool
    return str(clangtool.build(path))


def play(map_name, a, b, seed, replay_path=None):
    # a bare name is a live map (maps/<name>.map); a path like maps_gen/gen_007 or maps_gen/gen_007.map works too
    mp = pathlib.Path(map_name if map_name.endswith(".map") else f"{map_name}.map")
    mp = mp if "/" in map_name or "\\" in map_name else ROOT / "maps" / mp
    cmd = ["unswbc", "run", str(ROOT / mp if not mp.is_absolute() else mp), a, b, "--sandbox",
           "--seed", str(seed)]
    if replay_path:
        cmd += ["--replay", str(replay_path)]
    else:
        cmd.append("--no-replay")
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=900,  # Slithery Fight alone can legitimately take ~5m15s solo; 240s produced
                          # false TIMEOUTs there even with no other contention (2026-09-30).
        ).stdout
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


def play_zig(map_name, a, b, seed, replay_path=None, debug=False):
    # debug=True: --debug 3 (DEBUG_LOGS|DEBUG_INDICATOR) records dragonLog/dragonIndicator events
    # into the replay, matching `unswbc run --sandbox`'s default -- off by default here since the
    # judge omits them with no flag at all (verified 2026-09-30: 0 events either way vs 1450/6501
    # with --debug 3 on an identical game). Needed for any BC_DEBUG root-cause trace; leave off for
    # ordinary win/loss batches, where the extra log volume just adds overhead for no benefit.
    mp = pathlib.Path(map_name if map_name.endswith(".map") else f"{map_name}.map")
    mp = mp if "/" in map_name or "\\" in map_name else ROOT / "maps" / mp
    mp = mp if mp.is_absolute() else ROOT / mp

    cmd = [
        "wsl", "-d", WSL_DISTRO, "--", ZIG_JUDGE_WSL,
        "--engine", ZIG_ENGINE_WSL,
        "--map", to_wsl_path(mp),
        "--a", to_wsl_path(a),
        "--b", to_wsl_path(b),
        "--seed", str(seed),
    ]
    if debug:
        cmd += ["--debug", "3"]
    if replay_path:
        cmd += ["--replay", to_wsl_path(replay_path)]

    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=900,
        ).stdout
    except subprocess.TimeoutExpired:
        return None, 500, "TIMEOUT", {"A": [], "B": []}, {}

    # One tab-separated figures line; see ZIG_* constants above for the field layout.
    line = None
    for candidate in out.splitlines():
        if candidate.count("\t") >= 15:
            line = candidate
            break
    if line is None:
        return None, 500, "ERROR: " + out[-400:], {"A": [], "B": []}, {}

    f = line.split("\t")
    winner_c = f[0]
    rounds = int(f[1]) if f[1] else 500
    reason_code = int(f[2])
    a_deaths = [int(x) for x in f[7].split(",")]
    b_deaths = [int(x) for x in f[8].split(",")]
    a_points = f[12].split("/")  # p50/mean/max
    b_points = f[14].split("/")

    if winner_c == "-":
        winner, how = None, ZIG_DRAW_REASONS[reason_code] if 0 <= reason_code < len(ZIG_DRAW_REASONS) else "draw"
    else:
        winner = winner_c
        how = ZIG_END_REASONS[reason_code] if 0 <= reason_code < len(ZIG_END_REASONS) else "?"

    deaths = {
        "A": [r for r, n in zip(ZIG_DEATH_REASONS, a_deaths) for _ in range(n)],
        "B": [r for r, n in zip(ZIG_DEATH_REASONS, b_deaths) for _ in range(n)],
    }
    peak = {"A": int(a_points[2]) / 1e6, "B": int(b_points[2]) / 1e6}

    return winner, rounds, how, deaths, peak


def pct(x, y):
    return 100.0 * x / max(1, y)


def print_live_tracker(stats, total_jobs, start):
    completed = stats["completed"]
    wins = stats["wins"]
    losses = stats["losses"]
    draws = stats["draws"]

    elapsed = time.time() - start
    rate = completed / max(0.001, elapsed)
    remaining = total_jobs - completed
    eta = remaining / max(0.001, rate)

    errors = stats["errors"]
    print()
    print(
        f"--- Progress: {completed}/{total_jobs} "
        f"({pct(completed, total_jobs):.0f}%) | "
        f"W/L/D/E: {wins}/{losses}/{draws}/{errors} | "
        f"win rate: {pct(wins, completed):.1f}% | "
        f"ETA: {eta:.0f}s ---"
    )

    # Current per-map record
    print("Map progress:")
    for m in stats["map_order"]:
        d = stats["maps"][m]

        played = d["wins"] + d["losses"] + d["draws"]

        if played or d["errors"]:
            print(
                f"  {m:16s} "
                f"{d['wins']:2d}W {d['losses']:2d}L {d['draws']:2d}D {d['errors']:2d}E "
                f"({pct(d['wins'], played):5.1f}% W)"
            )


def print_final_stats(stats, bot, opponent, elapsed):
    print()
    print("=" * 90)
    print("TOURNAMENT SUMMARY")
    print("=" * 90)

    total = stats["wins"] + stats["losses"] + stats["draws"]
    errors = stats["errors"]

    print(
        f"{bot} vs {opponent}: "
        f"{stats['wins']}W {stats['losses']}L {stats['draws']}D "
        f"of {total}"
        + (f"  ({errors} infra error{'s' if errors != 1 else ''}/timeout"
           f"{'s' if errors != 1 else ''}, excluded from the totals above)" if errors else "")
    )

    print(
        f"Win rate: {pct(stats['wins'], total):.1f}%    "
        f"Loss rate: {pct(stats['losses'], total):.1f}%    "
        f"Draw rate: {pct(stats['draws'], total):.1f}%"
    )

    print(f"Total tournament time: {elapsed:.1f}s")
    print(f"Average battle length: {stats['rounds_total'] / max(1, total):.1f} rounds")
    print(
        f"Shortest battle: {stats['shortest_rounds']} rounds    "
        f"Longest battle: {stats['longest_rounds']} rounds"
    )

    # ------------------------------------------------------------------
    # SIDE ADVANTAGE
    # ------------------------------------------------------------------

    print()
    print("-" * 90)
    print("SIDE / TURN-ORDER EFFECT")
    print("-" * 90)

    for side in ("A", "B"):
        d = stats["sides"][side]
        played = d["wins"] + d["losses"] + d["draws"]

        print(
            f"Bot as {side}: "
            f"{d['wins']}W {d['losses']}L {d['draws']}D "
            f"({pct(d['wins'], played):.1f}% win rate)"
        )

    if not stats["one_side"]:
        a = stats["sides"]["A"]
        b = stats["sides"]["B"]

        a_wr = pct(a["wins"], a["wins"] + a["losses"] + a["draws"])
        b_wr = pct(b["wins"], b["wins"] + b["losses"] + b["draws"])

        print(
            f"Observed side win-rate difference: "
            f"{abs(a_wr - b_wr):.1f} percentage points"
        )

    # ------------------------------------------------------------------
    # MAP RESULTS
    # ------------------------------------------------------------------

    print()
    print("-" * 90)
    print("PER-MAP RESULTS")
    print("-" * 90)

    header = (
        f"{'Map':16s} {'W':>4s} {'L':>4s} {'D':>4s} {'E':>3s} "
        f"{'Win%':>7s} {'Avg R':>8s} {'Our deaths':>11s} {'Their deaths':>12s}"
    )
    print(header)
    print("-" * len(header))

    map_records = []

    for m in stats["map_order"]:
        d = stats["maps"][m]
        played = d["wins"] + d["losses"] + d["draws"]

        if not played and not d["errors"]:
            continue

        avg_rounds = d["rounds"] / played if played else 0.0

        print(
            f"{m:16s} "
            f"{d['wins']:4d} "
            f"{d['losses']:4d} "
            f"{d['draws']:4d} "
            f"{d['errors']:3d} "
            f"{pct(d['wins'], played):6.1f}% "
            f"{avg_rounds:8.1f} "
            f"{d['our_deaths']:11d} "
            f"{d['their_deaths']:12d}"
        )

        if played:
            map_records.append((m, d))

    # ------------------------------------------------------------------
    # MAP TENDENCIES
    # ------------------------------------------------------------------

    print()
    print("-" * 90)
    print("MAP TENDENCIES")
    print("-" * 90)

    if map_records:
        highest = max(
            map_records,
            key=lambda x: pct(
                x[1]["wins"],
                x[1]["wins"] + x[1]["losses"] + x[1]["draws"],
            ),
        )

        lowest = min(
            map_records,
            key=lambda x: pct(
                x[1]["wins"],
                x[1]["wins"] + x[1]["losses"] + x[1]["draws"],
            ),
        )

        longest = max(map_records, key=lambda x: x[1]["rounds"] /
                      max(1, x[1]["wins"] + x[1]["losses"] + x[1]["draws"]))

        shortest = min(map_records, key=lambda x: x[1]["rounds"] /
                       max(1, x[1]["wins"] + x[1]["losses"] + x[1]["draws"]))

        print(
            f"Highest observed win rate: {highest[0]} "
            f"({pct(highest[1]['wins'], highest[1]['wins'] + highest[1]['losses'] + highest[1]['draws']):.1f}%)"
        )

        print(
            f"Lowest observed win rate:  {lowest[0]} "
            f"({pct(lowest[1]['wins'], lowest[1]['wins'] + lowest[1]['losses'] + lowest[1]['draws']):.1f}%)"
        )

        print(
            f"Longest average battles:    {longest[0]} "
            f"({longest[1]['rounds'] / max(1, longest[1]['wins'] + longest[1]['losses'] + longest[1]['draws']):.1f} rounds)"
        )

        print(
            f"Shortest average battles:   {shortest[0]} "
            f"({shortest[1]['rounds'] / max(1, shortest[1]['wins'] + shortest[1]['losses'] + shortest[1]['draws']):.1f} rounds)"
        )

    # ------------------------------------------------------------------
    # DEATH CAUSES
    # ------------------------------------------------------------------

    print()
    print("-" * 90)
    print("DEATH CAUSES")
    print("-" * 90)

    if stats["death_tally"]:
        print("Overall:")
        for why, count in stats["death_tally"].most_common():
            print(f"  {count:4d}  {why}")

    print()
    print("By map:")

    for m in stats["map_order"]:
        d = stats["maps"][m]

        if not d["death_causes"]:
            continue

        print(f"\n  {m}:")

        for why, count in d["death_causes"].most_common():
            print(f"    {count:4d}  {why}")

    # ------------------------------------------------------------------
    # DEATH CAUSES BY SIDE
    # ------------------------------------------------------------------

    print()
    print("-" * 90)
    print("DEATH CAUSES BY SIDE")
    print("-" * 90)

    for side in ("A", "B"):
        print(f"\nBot as {side}:")

        causes = stats["side_deaths"][side]

        if not causes:
            print("  none")
            continue

        for why, count in causes.most_common():
            print(f"  {count:4d}  {why}")

    # ------------------------------------------------------------------
    # MOST COMMON DEATH PER MAP
    # ------------------------------------------------------------------

    print()
    print("-" * 90)
    print("MOST COMMON DEATH CAUSE PER MAP")
    print("-" * 90)

    for m in stats["map_order"]:
        causes = stats["maps"][m]["death_causes"]

        if causes:
            why, count = causes.most_common(1)[0]
            print(f"{m:16s}: {why} ({count} deaths)")
        else:
            print(f"{m:16s}: no deaths")

    # ------------------------------------------------------------------
    # ROUND DISTRIBUTION
    # ------------------------------------------------------------------

    print()
    print("-" * 90)
    print("BATTLE LENGTH")
    print("-" * 90)

    if stats["rounds"]:
        rounds = sorted(stats["rounds"])

        median = rounds[len(rounds) // 2]

        print(f"Mean rounds:   {sum(rounds) / len(rounds):.1f}")
        print(f"Median rounds: {median}")
        print(f"Min rounds:    {min(rounds)}")
        print(f"Max rounds:    {max(rounds)}")

        # Simple buckets
        buckets = [
            ("0-99", 0, 99),
            ("100-199", 100, 199),
            ("200-299", 200, 299),
            ("300-399", 300, 399),
            ("400+", 400, float("inf")),
        ]

        print()
        for name, lo, hi in buckets:
            n = sum(lo <= r <= hi for r in rounds)
            if n:
                print(f"{name:8s}: {n:4d} ({pct(n, len(rounds)):.1f}%)")

    # ------------------------------------------------------------------
    # PEAK POINTS
    # ------------------------------------------------------------------

    print()
    print("-" * 90)
    print("PEAK POINTS / TURN")
    print("-" * 90)

    print(f"Overall peak: {stats['peak_ms']:.1f}M")

    for m in stats["map_order"]:
        d = stats["maps"][m]

        if d["peak"] > 0:
            print(f"{m:16s}: {d['peak']:.1f}M")

    # ------------------------------------------------------------------
    # MAP SIDE SPLIT
    # ------------------------------------------------------------------

    if not stats["one_side"]:
        print()
        print("-" * 90)
        print("MAP × SIDE")
        print("-" * 90)

        for m in stats["map_order"]:
            d = stats["maps"][m]

            print(f"\n{m}:")

            for side in ("A", "B"):
                sd = d["sides"][side]
                played = sd["wins"] + sd["losses"] + sd["draws"]

                if played:
                    print(
                        f"  as {side}: "
                        f"{sd['wins']}W {sd['losses']}L {sd['draws']}D "
                        f"({pct(sd['wins'], played):.1f}% win)"
                    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bot")
    ap.add_argument("opponent")
    ap.add_argument("--maps", default=",".join(MAPS))
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("-j", type=int, default=10)
    ap.add_argument("--one-side", action="store_true")
    ap.add_argument("--seed-base", type=int, default=0, help="first seed index (seed = 1000 + 17 * index)")
    ap.add_argument(
        "--judge",
        choices=["sandbox", "zig"],
        default="sandbox",
        help="sandbox (default): unswbc run --sandbox. zig: over-yonder.tech's Zig judge via WSL2, ~2-2.5x "
             "faster, verified identical results (see insights.md) -- needs the WSL2 setup in ZIG_JUDGE_WSL "
             "(one teammate's machine), so it is opt-in.",
    )
    ap.add_argument(
        "--debug", action="store_true",
        help="zig judge only: pass --debug 3 (records dragonLog/dragonIndicator events into the "
             "replay, matching the sandbox's default). Needed for any BC_DEBUG trace; off by "
             "default since ordinary win/loss batches don't need the extra log volume.",
    )
    ap.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="print aggregate progress every N completed battles",
    )
    ap.add_argument(
        "--keep-replays",
        metavar="DIR",
        default=None,
        help="write each game's replay to DIR/<map>_<seed>_<side>.replay instead of discarding it "
             "(enables tools/bceval_batch.py analysis of local games afterward)",
    )
    ap.add_argument(
        "--replays",
        metavar="DIR",
        default=None,
        help="like --keep-replays but named DIR/<map>_<side>_<seed>.replay (side = our side), the layout "
             "tools/loss_digest.py, mechanics.py, game_review.py, feed_count.py expect",
    )
    args = ap.parse_args()

    replay_dir = None
    if args.keep_replays or args.replays:
        replay_dir = pathlib.Path(args.keep_replays or args.replays)
        replay_dir.mkdir(parents=True, exist_ok=True)

    a_path, b_path = prepare(args.bot), prepare(args.opponent)

    jobs = []

    for m in args.maps.split(","):
        for s in range(args.seed_base, args.seed_base + args.seeds):
            seed = 1000 + 17 * s

            jobs.append((m, "A", a_path, b_path, seed))

            if not args.one_side:
                jobs.append((m, "B", b_path, a_path, seed))

    def replay_path_for(m, side, seed):
        if replay_dir is None:
            return None
        if args.replays:   # our layout: <map stem>_<our side>_<seed>
            return replay_dir / f"{pathlib.Path(m).stem}_{side}_{seed}.replay"
        safe_map = m.replace("/", "_").replace("\\", "_")
        return replay_dir / f"{safe_map}_{seed}_{side}.replay"

    total_jobs = len(jobs)
    start = time.time()

    stats = {
        "completed": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "errors": 0,  # timeouts/crashes: isolated from "draws" (see Result classification below) --
                      # a bug this whole project hit repeatedly (Devil/Slithery Fight "draws" that
                      # turned out to be TIMEOUT, per over-yonder.tech/games/loong's own harness
                      # design, which keeps a separate error column for exactly this reason).

        "rounds": [],
        "rounds_total": 0,
        "shortest_rounds": 500,
        "longest_rounds": 0,

        "peak_ms": 0.0,

        "death_tally": collections.Counter(),
        "side_deaths": {
            "A": collections.Counter(),
            "B": collections.Counter(),
        },

        "sides": {
            "A": {"wins": 0, "losses": 0, "draws": 0},
            "B": {"wins": 0, "losses": 0, "draws": 0},
        },

        "maps": {},
        "map_order": args.maps.split(","),

        "one_side": args.one_side,
    }

    # Initialize map stats.
    for m in stats["map_order"]:
        stats["maps"][m] = {
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "errors": 0,
            "rounds": 0,
            "our_deaths": 0,
            "their_deaths": 0,
            "peak": 0.0,
            "death_causes": collections.Counter(),

            "sides": {
                "A": {"wins": 0, "losses": 0, "draws": 0},
                "B": {"wins": 0, "losses": 0, "draws": 0},
            },
        }

    print(
        f"Running {total_jobs} battles: "
        f"{len(stats['map_order'])} maps × {args.seeds} seed(s)"
        f"{' × 1 side' if args.one_side else ' × 2 sides'}"
    )
    print(f"Parallel workers: {args.j}")
    print("=" * 90)

    import functools
    if args.judge == "zig":
        play_fn = functools.partial(play_zig, debug=args.debug)
    else:
        play_fn = play

    with cf.ThreadPoolExecutor(max_workers=args.j) as ex:
        futs = {
            ex.submit(play_fn, m, x, y, s, replay_path_for(m, side, s)): (m, side, s)
            for m, side, x, y, s in jobs
        }

        for f in cf.as_completed(futs):
            m, side, s = futs[f]

            winner, rounds, how, deaths, peak = f.result()

            d = stats["maps"][m]

            # ----------------------------------------------------------
            # Result classification
            # ----------------------------------------------------------

            if winner is None and how == "draw":
                tag = "DRAW"
                stats["draws"] += 1
                d["draws"] += 1
                stats["sides"][side]["draws"] += 1
                d["sides"][side]["draws"] += 1

            elif winner is None:
                # TIMEOUT or ERROR: infra failure, not a real game outcome -- must NOT be counted
                # as a draw (that conflation caused real confusion this session: "0 avg rounds, 0
                # deaths" batches on Devil/Slithery Fight were misread as draws before this fix).
                tag = "ERR "
                stats["errors"] += 1
                d["errors"] += 1

            elif winner == side:
                tag = "WIN "
                stats["wins"] += 1
                d["wins"] += 1
                stats["sides"][side]["wins"] += 1
                d["sides"][side]["wins"] += 1

            else:
                tag = "LOSS"
                stats["losses"] += 1
                d["losses"] += 1
                stats["sides"][side]["losses"] += 1
                d["sides"][side]["losses"] += 1

            # ----------------------------------------------------------
            # Round statistics
            # ----------------------------------------------------------

            if rounds < 500 or winner is not None or how == "draw":
                stats["rounds"].append(rounds)
                stats["rounds_total"] += rounds
                d["rounds"] += rounds

                stats["shortest_rounds"] = min(
                    stats["shortest_rounds"], rounds
                )
                stats["longest_rounds"] = max(
                    stats["longest_rounds"], rounds
                )

            # ----------------------------------------------------------
            # Death statistics
            # ----------------------------------------------------------

            our_deaths = len(deaths[side])
            enemy_side = "B" if side == "A" else "A"
            their_deaths = len(deaths[enemy_side])

            d["our_deaths"] += our_deaths
            d["their_deaths"] += their_deaths

            for why in deaths[side]:
                stats["death_tally"][why] += 1
                stats["side_deaths"][side][why] += 1
                d["death_causes"][why] += 1

            # ----------------------------------------------------------
            # Peak points
            # ----------------------------------------------------------

            this_peak = peak.get(side, 0.0)

            stats["peak_ms"] = max(stats["peak_ms"], this_peak)
            d["peak"] = max(d["peak"], this_peak)

            # ----------------------------------------------------------
            # Print individual result
            # ----------------------------------------------------------

            line = (
                f"[{tag}] {m:16s} as {side} seed {s}: "
                f"{rounds:3d} rounds ({how})"
                f"  our deaths={our_deaths}"
                f" theirs={their_deaths}"
            )

            print(line, flush=True)

            # ----------------------------------------------------------
            # Progress
            # ----------------------------------------------------------

            stats["completed"] += 1

            if (
                stats["completed"] % max(1, args.progress_every) == 0
                or stats["completed"] == total_jobs
            ):
                print_live_tracker(stats, total_jobs, start)

    elapsed = time.time() - start

    print_final_stats(
        stats,
        args.bot,
        args.opponent,
        elapsed,
    )


if __name__ == "__main__":
    main()
