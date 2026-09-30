"""Early-stopping A/B test using SPRT instead of a fixed game batch -- the tooling upgrade
recommended after reading over-yonder.tech/games/loong/better-worse-or-undecided/. Plays `bot` vs
`opponent` one game at a time (cycling through --maps and both sides, incrementing the seed each
full cycle -- the closest fit to that post's "paired games" idea for a single-candidate-vs-fixed-
opponent test), feeding each result into an SPRT, and stops as soon as the result is statistically
decided instead of always running a fixed batch.

Usage:
    uv run --python 3.11 --with unswbc python tools/sprt_test.py CANDIDATE OPPONENT \
        --maps trauma,autarky,trophy,default,dilemma,devil,slithery_fight,schooltime \
        --p0 0.5 --p1 0.6 [--max-games 200] [-j 4]

p0/p1 are the null/alternative win-rate hypotheses (e.g. "is this candidate beating the opponent at
least 60% of the time, vs the null that it's only a coin flip"). Use --elo1 instead of --p1 to state
the alternative as an Elo gain over p0.
"""
import argparse
import concurrent.futures as cf
import functools
import pathlib
import sys
import time

print = functools.partial(print, flush=True)  # tourney.py's own lesson this session: unflushed
# prints under a redirected/piped stdout can sit invisible for many real minutes under load.

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tourney  # noqa: E402
from sprt import Sprt, elo_to_p  # noqa: E402


def game_stream(maps, seeds_start=1000, seed_step=17):
    """Yields (map, side) pairs, cycling maps x both sides, bumping the seed each full cycle so
    repeated cycles aren't identical games."""
    cycle = 0
    while True:
        seed = seeds_start + seed_step * cycle
        for m in maps:
            yield (m, "A", seed)
            yield (m, "B", seed)
        cycle += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bot")
    ap.add_argument("opponent")
    ap.add_argument("--maps", default="trauma,autarky,trophy,default,dilemma,devil,slithery_fight,schooltime")
    ap.add_argument("--p0", type=float, default=0.5)
    ap.add_argument("--p1", type=float, default=None)
    ap.add_argument("--elo1", type=float, default=None, help="alternative as an Elo gain over --p0")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--beta", type=float, default=0.05)
    ap.add_argument("--max-games", type=int, default=200)
    ap.add_argument("-j", type=int, default=4, help="games in flight at once (SPRT still checked "
                                                      "in submission order once each batch returns)")
    ap.add_argument("--judge", choices=["sandbox", "zig"], default="zig",
                     help="zig (default): over-yonder.tech's Zig judge via WSL2, ~2-2.5x faster, "
                          "verified identical results. sandbox: unswbc run --sandbox.")
    args = ap.parse_args()
    play_fn = tourney.play_zig if args.judge == "zig" else tourney.play

    if args.p1 is None and args.elo1 is None:
        args.p1 = 0.6  # a clear, practically-meaningful default gain
    p1 = elo_to_p(args.elo1, args.p0) if args.elo1 is not None else args.p1

    sprt = Sprt(args.p0, p1, args.alpha, args.beta, args.max_games)
    print(f"SPRT: p0={args.p0} p1={p1:.3f} alpha={args.alpha} beta={args.beta} "
          f"bounds=({sprt.lower:.3f}, {sprt.upper:.3f}) max_games={args.max_games}")

    a_path, b_path = tourney.prepare(args.bot), tourney.prepare(args.opponent)
    maps = args.maps.split(",")
    stream = game_stream(maps)
    start = time.time()

    with cf.ThreadPoolExecutor(max_workers=args.j) as ex:
        pending = {}
        # Keep `j` games in flight; as each one resolves, feed SPRT and submit a replacement,
        # unless SPRT has already decided or we've hit the game cap.
        while len(pending) < args.j and not sprt.decided:
            m, side, seed = next(stream)
            x, y = (a_path, b_path) if side == "A" else (b_path, a_path)
            fut = ex.submit(play_fn, m, x, y, seed)
            pending[fut] = (m, side, seed)

        while pending and not sprt.decided:
            done, _ = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
            for fut in done:
                m, side, seed = pending.pop(fut)
                winner, rounds, how, deaths, peak = fut.result()
                if how == "TIMEOUT" or winner is None:
                    continue  # draw or infra error: not decisive evidence either way, skip
                won = (winner == side)
                sprt.update(won)
                print(f"[{'W' if won else 'L'}] {m:16s} as {side} seed {seed}: {rounds} rounds "
                      f"({how})  {sprt.status()}")
                if not sprt.decided and len(pending) < args.j:
                    nm, nside, nseed = next(stream)
                    nx, ny = (a_path, b_path) if nside == "A" else (b_path, a_path)
                    nfut = ex.submit(play_fn, nm, nx, ny, nseed)
                    pending[nfut] = (nm, nside, nseed)

    elapsed = time.time() - start
    print()
    print("=" * 70)
    print(f"SPRT finished in {elapsed:.0f}s: {sprt.status()}")
    if sprt.verdict == "accept":
        print(f"Candidate is meaningfully better than the null (p0={args.p0}) at this opponent.")
    elif sprt.verdict == "reject":
        print(f"No material difference from the null (p0={args.p0}) detected.")
    else:
        print("Hit the game cap without a confident decision -- consider a bigger --max-games "
              "or a less ambitious --p1/--elo1.")


if __name__ == "__main__":
    main()
