"""Bot-vs-builder input parity gate for the v6 network inputs.

    uv run --python 3.11 --with unswbc --with numpy python ml/v6/bot_parity.py REPLAY.replay [--team N]

REPLAY comes from `tools/panel_zig.py viper_b19_v6in <opp> OUT ...` (a debug build whose INDICATOR text starts with
"H" + 19 per-plane FNV-1a/32 hashes of the 19x225 input planes the BOT would feed the v6 net). For the same
(round, dragon) the Python builder (ml/v6/build_dataset_v6.py) recomputes the planes from the replay; we compare per plane.
Exit code 0 only if every compared plane matches on >= --min-match of states (default 1.0).
"""
import argparse, sys, collections
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parent.parent / "tools")]
from build_dataset_v6 import extract_game, META, PLANE_DEFS    # noqa: E402
from replay_lite import decode_lite                            # noqa: E402


def fnv32(b):
    h = 2166136261
    for x in b:
        h = ((h ^ x) * 16777619) & 0xFFFFFFFF
    return h


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("replay"); ap.add_argument("--team", type=int, default=None)
    ap.add_argument("--min-match", type=float, default=1.0); ap.add_argument("--show", type=int, default=3)
    a = ap.parse_args()
    rep = decode_lite(a.replay, {"roundStart", "dragonIndicator"})
    rnd = -1; bot = {}
    for e in rep["events"]:
        if e["kind"] == "roundStart": rnd = e["round"]
        elif e["kind"] == "dragonIndicator":
            t = e.get("text", "")
            if t.startswith("H") and len(t) >= 1 + 19 * 8 and all(c in "0123456789abcdef" for c in t[1:1 + 152]):
                bot[(rnd, e["id"])] = [int(t[1 + 8 * k:9 + 8 * k], 16) for k in range(19)]
    assert bot, "no parity hashes in the replay: use a viper_b19_v6in build with --debug 2"
    # which team is the bot? the team of the dragons that carry hashes (ids -> team from the DRAGON lines is not enough: use the builder's World)
    teams = {}
    for line in rep["map"].splitlines():
        pass
    results = {}
    for team in ([a.team] if a.team is not None else (0, 1)):
        arrays, name, stats = extract_game(a.replay, 0, 0, team, "full", False, require_winner=False)
        P, M = arrays["planes"], arrays["meta"]
        keep = [n for n in range(len(M)) if M[n, META.index("steps_taken")] == 0]
        hit = sum((int(M[n, 3]), int(M[n, 4])) in bot for n in keep)
        results[team] = (arrays, keep, hit, stats)
    team = max(results, key=lambda t: results[t][2])
    arrays, keep, hit, stats = results[team]
    P, M = arrays["planes"], arrays["meta"]
    n_total = n_cmp = 0; per_plane_bad = collections.Counter(); bad_states = 0; shown = 0; allok = 0
    rounds_terrain = collections.Counter(); rounds_other = collections.Counter()
    for n in keep:
        key = (int(M[n, 3]), int(M[n, 4]))
        if key not in bot: continue
        n_cmp += 1
        mine = [fnv32(P[n, p].tobytes()) for p in range(19)]
        bad = [p for p in range(19) if mine[p] != bot[key][p] and PLANE_DEFS[p] not in ("ZERO", "reserved_ZERO")]
        if bad:
            bad_states += 1; per_plane_bad.update(bad)
            (rounds_other if any(p >= 8 for p in bad) else rounds_terrain)[key[0] // 25 * 25] += 1
            if shown < a.show:
                shown += 1; print("mismatch round", key[0], "dragon", key[1], "planes", [(p, PLANE_DEFS[p]) for p in bad])
        else:
            allok += 1
    print(f"bot team {team}: builder states with steps_taken=0: {len(keep)}, bot hashes: {len(bot)}, compared {n_cmp}, all planes equal {allok} "
          f"({allok / max(1, n_cmp):.4f})")
    print("mismatching planes:", {f"{p}:{PLANE_DEFS[p]}": c for p, c in sorted(per_plane_bad.items())})
    print("terrain-only mismatches by round bin:", dict(sorted(rounds_terrain.items())))
    print("mismatches touching planes >= 8 by round bin:", dict(sorted(rounds_other.items())))
    sys.exit(0 if n_cmp and allok / n_cmp >= a.min_match else 1)


if __name__ == "__main__":
    main()
