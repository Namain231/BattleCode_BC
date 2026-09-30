"""Run bceval's win-probability evaluator across a directory of replays and summarize each
game's shape (dominant throughout / close throughout / early / mid / late collapse), not just
win/loss. Works equally on downloaded ladder replays and on local sandbox replays produced by
`tools/tourney.py --keep-replays DIR`.

Usage:
    uv run --python 3.11 --with pycapnp python tools/bceval_batch.py DIR [--ours SUBSTRING]
        [--every N] [--threshold 0.3]

DIR is scanned recursively for *.replay files. `--ours` is a substring to match against the
replay's recorded bot_a/bot_b names to decide which side is "us":
  - Local sandbox replays (from `tourney.py --keep-replays`) record the bot's directory name, e.g.
    pass `--ours vS4.7` or `--ours viper_vS4.7`.
  - Downloaded ladder replays record our own submission id as a bare string (e.g. `--ours 11453`),
    with the opponent's slot blank -- check `ladder/*/results.json` for which id was active.
If omitted, guesses the side whose name looks like a local path over a bare id/blank -- only
reliable for local replays; pass --ours explicitly for ladder replays.

For each replay, classifies our win-probability trajectory:
    dominant   -- never drops below 0.5 for us
    close      -- never drops below --threshold (default 0.3) for us
    early      -- drops below --threshold by round 100 and stays down
    mid        -- drops below --threshold between round 100-300 and stays down
    late       -- drops below --threshold after round 300
    recovered  -- drops below --threshold at some point but climbs back above 0.5 later
Prints a table (file, map, result, our_side, shape, collapse_round) then a shape-count summary,
so a whole local batch test can be read for *how* games were won/lost, not just the tally.
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "battlecode-eval"))

from bceval import evaluate_replay, replay_features  # noqa: E402


def classify(rows, our_is_a, threshold):
    below = None
    for r in rows:
        p_us = r["p_a"] if our_is_a else 1 - r["p_a"]
        if p_us < threshold and below is None:
            below = r["after_round"]
        if p_us >= 0.5 and below is not None:
            return "recovered", below
    if below is None:
        # never dropped below threshold; check if we ever dominated (>0.5)
        dominant = any((r["p_a"] if our_is_a else 1 - r["p_a"]) > 0.5 for r in rows)
        return ("dominant" if dominant else "close"), None
    if below <= 100:
        return "early", below
    if below <= 300:
        return "mid", below
    return "late", below


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--ours", default=None, help="substring matching our bot's recorded name")
    ap.add_argument("--by-winner", action="store_true",
                     help="classify each decisive game's shape relative to whoever won, not a "
                          "fixed --ours side -- for analyzing a general 'how do winners win' "
                          "pattern across replays where neither side is necessarily us (e.g. "
                          "scouted top-team games). Draws are skipped (no winner to be relative "
                          "to). Ignores --ours.")
    ap.add_argument("--every", type=int, default=20)
    ap.add_argument("--threshold", type=float, default=0.3)
    ap.add_argument("--quiet", action="store_true", help="only print the summary, not every row "
                                                           "(use for large batches)")
    ap.add_argument("--by-map", action="store_true", help="also break the shape summary down per map")
    args = ap.parse_args()

    replays = sorted(pathlib.Path(args.dir).rglob("*.replay"))
    if not replays:
        print(f"No .replay files found under {args.dir}")
        return

    counts = {}
    per_map = {}
    errors = 0
    if not args.quiet:
        print(f"{'file':40s} {'map':16s} {'result':6s} {'side':4s} {'shape':10s} collapse")
        print("-" * 90)
    for path in replays:
        try:
            game, _ = replay_features(str(path), 500)
            rows = evaluate_replay(str(path), args.every)
        except Exception:
            errors += 1
            continue

        winner = (game.get("winner") or "").lower()
        bot_a, bot_b = game.get("bot_a") or "", game.get("bot_b") or ""

        if args.by_winner:
            if winner not in ("a", "b"):
                continue  # draw: no winner to be relative to
            side_is_a = winner == "a"
            result = "W"
        else:
            if args.ours:
                side_is_a = args.ours in bot_a
            else:
                # heuristic: prefer whichever name looks like a local path/dev build over a bare
                # ladder submission id/team name -- fall back to "A" if genuinely ambiguous.
                side_is_a = ("/" in bot_a or "\\" in bot_a) or not ("/" in bot_b or "\\" in bot_b)
            if winner == "a":
                result = "W" if side_is_a else "L"
            elif winner == "b":
                result = "L" if side_is_a else "W"
            else:
                result = "D"

        shape, collapse = classify(rows, side_is_a, args.threshold)
        counts[shape] = counts.get(shape, 0) + 1
        m = str(game.get("map"))
        per_map.setdefault(m, {}).setdefault(shape, 0)
        per_map[m][shape] += 1
        if not args.quiet:
            collapse_s = str(collapse) if collapse is not None else "-"
            print(f"{path.name:40s} {m:16s} {result:6s} "
                  f"{'A' if side_is_a else 'B':4s} {shape:10s} {collapse_s}")

    print("-" * 90)
    label = "winner's" if args.by_winner else "our"
    print(f"Shape summary ({label} trajectory, {len(replays) - errors} replays, {errors} errors):",
          ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print("(dominant/close = never really contested either way; early/mid/late = when the losing")
    print(" side fell behind and never recovered; recovered = dipped but came back.)")
    if args.by_map:
        print()
        print("Per-map breakdown:")
        for m in sorted(per_map):
            print(f"  {m:20s} " + ", ".join(f"{k}={v}" for k, v in sorted(per_map[m].items())))


if __name__ == "__main__":
    main()
