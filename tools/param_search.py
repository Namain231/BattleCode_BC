"""Automated coordinate-descent search over viper_vS4.7/common.hpp's Params, using a broad local
tourney (multiple maps and seeds, never a single seed -- a single-seed test already misled a
manual round of tuning this session, see s4_7_v4_and_beyond.md's feedMaxLen revert) against a
reference opponent as the fitness function.

    python tools/param_search.py --opponent viper_v7.12 --maps portals,trauma,default,autarky,dilemma --seeds 2 -j 2

Edits common.hpp in place for each trial, rebuilds (forces a real main.cpp content change so the
sandbox cache actually rebuilds), runs the tourney, and keeps the value only if it improves the
win rate over the current baseline by more than --min-gain (small noise floor). Logs every trial
to <out>/log.jsonl so progress survives a restart. Safe to run for hours unattended: each
parameter's sweep is independent and checkpointed.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tourney  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
# A dedicated copy, not the live viper_vS4.7/ -- this script rewrites common.hpp continuously and
# would otherwise race with any other tourney/gate run reading the same directory concurrently.
# Also not viper_vS4.7_tune by default any more: that directory is routinely used for one-off
# feature A/B tests (see insights.md) and a running param_search overwriting it mid-experiment
# already silently invalidated a result once this session (see S4_7_PLAYBOOK.md's process lessons).
# --bot-dir picks a fresh, dedicated scratch copy instead.
BOT_NAME = None  # set from --bot-dir in main()
BOT = COMMON = MAINCPP = None

# (param name, [candidate multipliers relative to current value])
# Focused 2026-09-30 on the maps bceval_batch.py flagged as early/mid-collapse (trophy, trauma,
# autarky, schooltime -- see insights.md): opening-game claim-speed params (wTarget, swarmSplitLen,
# swarmChild -- faster/more decisive early splitting and pearl commitment) and combat-trade
# params (wDanger, wPredict -- relevant to Schooltime's head-to-head-dominated losses) prioritized
# first since bceval dated these collapses to the opening 20-120 rounds, not the late game.
# wTerritory/wChoke included since they're new (A/B tested separately in parallel; this sweep will
# also suggest a magnitude if either shows promise there).
SWEEP = [
    ("wTarget", [0.5, 1.0, 2.0, 4.0]),
    ("swarmSplitLen", [0.75, 1.0, 1.25]),
    ("swarmChild", [0.5, 1.0, 1.5]),
    ("wDanger", [0.7, 0.85, 1.0, 1.2]),
    ("wPredict", [0.5, 1.0, 1.5, 2.0]),
    ("wTerritory", [0.0, 0.3, 0.6, 1.0]),
    ("wChoke", [0.0, 0.5, 1.0, 2.0]),
    ("wCompass", [0.5, 1.0, 2.0]),
    ("gamma", [0.9, 1.0, 1.1]),
    ("promoteLen", [0.7, 1.0, 1.3]),
    ("growRound", [0.85, 1.0, 1.15]),
    ("wPocket", [0.7, 1.0, 1.3]),
    ("wCrowd", [0.5, 1.0, 2.0]),
    ("feedRound", [0.85, 1.0, 1.15]),
    ("feedMargin", [0.5, 1.0, 2.0]),
    ("queenDeferMargin", [0.5, 1.0, 2.0]),
]


def read_param(name):
    text = COMMON.read_text(encoding="utf-8")
    m = re.search(rf"\b{re.escape(name)}\s*=\s*([0-9.eE+-]+)\s*;", text)
    if not m:
        raise RuntimeError(f"param {name} not found")
    return float(m.group(1)), m.start(1), m.end(1)


def write_param(name, value, is_int):
    text = COMMON.read_text(encoding="utf-8")
    m = re.search(rf"(\b{re.escape(name)}\s*=\s*)([0-9.eE+-]+)(\s*;)", text)
    if not m:
        raise RuntimeError(f"param {name} not found")
    sval = str(int(round(value))) if is_int else f"{value:g}"
    text = text[:m.start(2)] + sval + text[m.end(2):]
    COMMON.write_text(text, encoding="utf-8")


def touch_main():
    text = MAINCPP.read_text(encoding="utf-8")
    text = re.sub(r"// rebuild-marker .*\n?$", "", text)
    text += f"// rebuild-marker {time.time()}\n"
    MAINCPP.write_text(text, encoding="utf-8")


def evaluate(opponent, maps, seeds, j, play_fn):
    touch_main()
    # force a fresh build by clearing tourney's cached path resolution each call
    bot_path = tourney.prepare(BOT_NAME)
    opp_path = tourney.prepare(opponent)
    jobs = []
    for m in maps:
        for s in range(seeds):
            seed = 2000 + 17 * s
            jobs.append((m, "A", bot_path, opp_path, seed))
            jobs.append((m, "B", opp_path, bot_path, seed))
    import concurrent.futures as cf
    wins = games = 0
    with cf.ThreadPoolExecutor(j) as ex:
        futs = {ex.submit(play_fn, m, x, y, s): side for m, side, x, y, s in jobs}
        for f in cf.as_completed(futs):
            side = futs[f]
            winner, rounds, how, deaths, peak = f.result()
            if how.startswith("ERROR") or how == "TIMEOUT":
                continue
            games += 1
            if winner == side:
                wins += 1
            elif winner is None:
                wins += 0.5
    return wins, games


def main():
    global BOT_NAME, BOT, COMMON, MAINCPP
    ap = argparse.ArgumentParser()
    ap.add_argument("--opponent", default="viper_v7.12")
    ap.add_argument("--maps", default="portals,trauma,default,autarky,dilemma,queen_of_spades")
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("-j", type=int, default=2)
    ap.add_argument("--min-gain", type=float, default=0.03, help="min win-rate improvement to keep a change")
    ap.add_argument("--rounds", type=int, default=3, help="full sweeps over all params")
    ap.add_argument("--out", default="ladder/param_search")
    ap.add_argument("--bot-dir", default="viper_vS4.7_tune",
                     help="scratch copy this script rewrites continuously -- use a dedicated dir, "
                          "never one another running test/experiment is also using")
    ap.add_argument("--judge", choices=["sandbox", "zig"], default="zig")
    a = ap.parse_args()
    BOT_NAME = a.bot_dir
    BOT = ROOT / BOT_NAME
    COMMON = BOT / "common.hpp"
    MAINCPP = BOT / "main.cpp"
    play_fn = tourney.play_zig if a.judge == "zig" else tourney.play
    maps = a.maps.split(",")
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "log.jsonl", "a", encoding="utf-8")

    print(f"bot dir: {BOT} | judge: {a.judge}", flush=True)
    print("baseline evaluation...", flush=True)
    base_w, base_g = evaluate(a.opponent, maps, a.seeds, a.j, play_fn)
    base_rate = base_w / max(1, base_g)
    print(f"baseline: {base_w}/{base_g} = {base_rate:.3f}", flush=True)
    log.write(json.dumps({"trial": "baseline", "win_rate": base_rate, "wins": base_w, "games": base_g}) + "\n"); log.flush()

    for rnd in range(a.rounds):
        for name, mults in SWEEP:
            cur, *_ = read_param(name)
            is_int = float(cur).is_integer()
            best_val, best_rate = cur, base_rate
            for mult in mults:
                cand = cur * mult
                if is_int:
                    cand = round(cand)
                if cand == cur:
                    continue
                write_param(name, cand, is_int)
                w, g = evaluate(a.opponent, maps, a.seeds, a.j, play_fn)
                rate = w / max(1, g)
                print(f"round{rnd} {name}={cand} -> {w}/{g}={rate:.3f} (baseline {base_rate:.3f})", flush=True)
                log.write(json.dumps({"round": rnd, "param": name, "value": cand, "win_rate": rate,
                                       "wins": w, "games": g}) + "\n"); log.flush()
                if rate > best_rate + a.min_gain:
                    best_rate, best_val = rate, cand
            write_param(name, best_val, is_int)
            if best_val != cur:
                base_rate = best_rate
                print(f"  KEPT {name} = {best_val} (win rate now {base_rate:.3f})", flush=True)
            else:
                write_param(name, cur, is_int)  # restore exactly (avoid float drift)
    print("search done", flush=True)


if __name__ == "__main__":
    main()
