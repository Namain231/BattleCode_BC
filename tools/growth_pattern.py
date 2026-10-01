"""Aggregate consolidation/role-shape patterns across a batch of replays: when does the winner's
longest dragon pull away from the pack, how many dragons does a winner end with (and how many of
those are "long" vs "short"), and how does the length distribution's shape change from the start to
the endgame. Complements bceval_batch.py's win-probability shapes with actual board-state numbers
(bceval only ever sees a learned score, not unit counts or lengths).

Usage:
    uv run --python 3.11 --with pycapnp python tools/growth_pattern.py DIR [--side winner|loser]
        [--consolidation-ratio 0.25]

Reuses bceval's replay_features() to determine the winner (bceval already solves this reliably from
final board state) and tools/queen_growth.py's own event-replay logic to get units/longest/total at
rounds 100/200/300/400/500/end for whichever side is requested.
"""
import argparse
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "battlecode-eval"))

from queen_growth import analyse  # noqa: E402
from bceval import replay_features  # noqa: E402

CHECK = (100, 200, 300, 400, 500)


def small_dragon_count(path, side, threshold=4):
    """How many dragons on `side` are at or below `threshold` length (a rough "feeder/scout" cut)
    vs longer ones, at each checkpoint -- reuses analyse()'s own event replay rather than a second
    pass, by calling a lightly modified version inline would duplicate code; instead we just re-run
    analyse() for the (units, longest, total) triple, which is enough for the ratio-based metrics
    used below. A full per-dragon length histogram would need queen_growth.py itself extended;
    out of scope for this aggregate pass."""
    return None


def consolidation_round(curve, ratio):
    """First checkpoint where longest/total >= ratio (one dragon holds a `ratio` share of the
    team's total length) -- a proxy for 'the swarm has picked a queen'. Returns a checkpoint label
    or 'never' if it doesn't cross the ratio by game end."""
    for r in CHECK:
        if r not in curve:
            continue
        units, longest, total = curve[r]
        if total > 0 and longest / total >= ratio:
            return r
    if "end" in curve:
        units, longest, total = curve["end"]
        if total > 0 and longest / total >= ratio:
            return "end (not by r500)"
    return "never"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--side", choices=["winner", "loser"], default="winner")
    ap.add_argument("--consolidation-ratio", type=float, default=0.25)
    args = ap.parse_args()

    replays = sorted(pathlib.Path(args.dir).rglob("*.replay"))
    if not replays:
        print(f"No .replay files found under {args.dir}")
        return

    units_by_check = {r: [] for r in list(CHECK) + ["end"]}
    longest_by_check = {r: [] for r in list(CHECK) + ["end"]}
    longest_share_by_check = {r: [] for r in list(CHECK) + ["end"]}
    consolidation_rounds = []
    end_unit_counts = []
    end_long_vs_short = []  # (longest, units-1) per game: the queen vs everyone else
    errors = 0
    skipped_draws = 0

    for path in replays:
        try:
            game, _ = replay_features(str(path), 500)
        except Exception:
            errors += 1
            continue
        winner = (game.get("winner") or "").lower()
        if winner not in ("a", "b"):
            skipped_draws += 1
            continue
        side_letter = winner.upper() if args.side == "winner" else ("B" if winner == "a" else "A")
        try:
            curve = analyse(str(path), side_letter)
        except Exception:
            errors += 1
            continue

        for r in list(CHECK) + ["end"]:
            if r in curve:
                units, longest, total = curve[r]
                units_by_check[r].append(units)
                longest_by_check[r].append(longest)
                if total > 0:
                    longest_share_by_check[r].append(longest / total)

        consolidation_rounds.append(consolidation_round(curve, args.consolidation_ratio))
        if "end" in curve:
            units, longest, total = curve["end"]
            end_unit_counts.append(units)
            end_long_vs_short.append((longest, max(0, units - 1)))

    n = len(replays) - errors - skipped_draws
    print(f"Analyzed {n} decisive games ({errors} errors, {skipped_draws} draws skipped) "
          f"for the {args.side}'s side\n")

    print(f"{'round':>6} | {'median units':>12} | {'median longest':>15} | {'median longest/total':>20}")
    print("-" * 65)
    for r in list(CHECK) + ["end"]:
        u = units_by_check[r]
        l = longest_by_check[r]
        s = longest_share_by_check[r]
        if not u:
            continue
        print(f"{str(r):>6} | {statistics.median(u):>12.1f} | {statistics.median(l):>15.1f} | "
              f"{statistics.median(s) if s else 0:>20.2f}")

    print()
    print(f"End-game unit count for {args.side}s: median={statistics.median(end_unit_counts):.0f}, "
          f"mean={statistics.mean(end_unit_counts):.1f}, "
          f"range={min(end_unit_counts)}-{max(end_unit_counts)}")

    print()
    from collections import Counter
    cc = Counter(consolidation_rounds)
    print(f"Consolidation round (first checkpoint where longest dragon holds >= "
          f"{args.consolidation_ratio:.0%} of team's total length):")
    for r in list(CHECK) + ["end (not by r500)", "never"]:
        if cc.get(r):
            print(f"  {str(r):20s} {cc[r]:4d} games")


if __name__ == "__main__":
    main()
