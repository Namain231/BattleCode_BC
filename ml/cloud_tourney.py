"""Candidate vs champion in the judge's sandbox, on any machine (laptop, Colab, Kaggle, Lightning), with early stopping.

    python cloud_tourney.py --a wasm/cand.wasm --b wasm/champion.wasm --out results/ [--maps all|maze|a,b]
        [--gen 10] [--seeds 4] [--workers N] [--no-sprt]

Bots are prebuilt .wasm files (tools/cloud_test.py builds and ships them), so no compiler is needed. Every map is
played from both sides with the same seed (pearl luck cancels). Games run in parallel; results.jsonl gets one line
per game and summary.json the totals. SPRT (Wald, as in Stockfish's fishtest): H0 p = 0.50 vs H1 p = 0.60,
alpha = beta = 0.1; stops as soon as the evidence crosses a bound (a clearly worse or clearly better candidate
usually decides in 20-40 games), else plays everything. Draws count as half a win.
Layout next to this file: maps/*.map (live), maps_gen/*.map (random), wasm/*.wasm.
"""
import argparse
import json
import math
import multiprocessing as mp
import os
import pathlib
import random
import re
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent
LIVE = ["portals", "slithery_fight", "schooltime", "trophy", "queen_of_spades", "default", "dilemma", "autarky",
        "devil", "trauma"]
MAZE = LIVE[3:]
RESULT = re.compile(r"team (A|B) wins after (\d+) rounds")
DRAW = re.compile(r"draw after (\d+) rounds")
LLR_WIN, LLR_LOSS = math.log(0.6 / 0.5), math.log(0.4 / 0.5)
BOUND = math.log(0.9 / 0.1)


REPLAY_DIR = None   # --replays: keep <map>_<a_side>_<seed>.replay (a_side = the candidate's side), tarred at the end


def play(job):
    a, b, map_path, seed, a_side = job
    first, second = (a, b) if a_side == "A" else (b, a)
    keep = (["--replay", str(pathlib.Path(REPLAY_DIR) / f"{pathlib.Path(map_path).stem}_{a_side}_{seed}.replay")]
            if REPLAY_DIR else ["--no-replay"])
    try:
        r = subprocess.run(["unswbc", "run", map_path, first, second, "--sandbox", *keep, "--seed", str(seed)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        out = r.stdout + r.stderr
        m = RESULT.search(out)
        score = 1.0 if m and m.group(1) == a_side else 0.0 if m else 0.5 if DRAW.search(out) else None
        err = out[-400:] if score is None else ""
    except Exception as e:
        score, err = None, repr(e)[:400]
    res = {"map": pathlib.Path(map_path).stem, "seed": seed, "a_side": a_side, "score": score}
    if err:
        res["err"] = err   # why a game produced no result (shows up in results.jsonl)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--maps", default="all")
    ap.add_argument("--gen", type=int, default=0, help="also play this many random maps from maps_gen/")
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=0, help="first seed index (new games instead of replaying 0..)")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--no-sprt", action="store_true")
    ap.add_argument("--replays", default="", help="keep replays in this dir, tar them into <out>/replays.tgz at the end")
    ap.add_argument("--tourney-seeds", action="store_true", help="seed = 1000 + 17 * i (tools/tourney.py), for pairing")
    a = ap.parse_args()
    global REPLAY_DIR
    if a.replays:
        REPLAY_DIR = a.replays; pathlib.Path(REPLAY_DIR).mkdir(parents=True, exist_ok=True)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    names = LIVE if a.maps == "all" else MAZE if a.maps == "maze" else a.maps.split(",")
    maps = [str(ROOT / "maps" / f"{m}.map") for m in names]
    gen = sorted((ROOT / "maps_gen").glob("*.map"))
    rng = random.Random(12345)
    maps += [str(p) for p in rng.sample(gen, min(a.gen, len(gen)))]
    wa, wb = str(ROOT / a.a), str(ROOT / a.b)
    jobs = []
    for s in range(a.seed_base, a.seed_base + a.seeds):             # round-robin order: every prefix of the list covers many maps
        for m in maps:
            seed = (1000 + 17 * s) if a.tourney_seeds else 1000 + 7919 * s + sum(pathlib.Path(m).stem.encode()) % 997
            jobs += [(wa, wb, m, seed, "A"), (wa, wb, m, seed, "B")]
    wins = n = 0; llr = 0.0; t0 = time.time(); verdict = "no decision (all games played)"
    per = {}
    with mp.Pool(a.workers) as pool, open(out / "results.jsonl", "a") as log:
        for r in pool.imap(play, jobs):
            log.write(json.dumps(r) + "\n"); log.flush()
            if r["score"] is None:
                continue
            n += 1; wins += r["score"]
            per.setdefault(r["map"], [0, 0]); per[r["map"]][0] += r["score"]; per[r["map"]][1] += 1
            llr += LLR_WIN if r["score"] == 1 else LLR_LOSS if r["score"] == 0 else 0
            if n % 10 == 0:
                print(f"{n} games: {wins:.1f} wins ({wins / n:.0%}), LLR {llr:+.2f} [{time.time() - t0:.0f}s]", flush=True)
            if not a.no_sprt and (llr >= BOUND or llr <= -BOUND):
                verdict = "BETTER (SPRT: p >= 0.6 likely)" if llr > 0 else "NOT BETTER (SPRT: p <= 0.5 likely)"
                pool.terminate()
                break
    summary = {"a": a.a, "b": a.b, "games": n, "wins": wins, "rate": wins / n if n else None, "llr": llr,
               "verdict": verdict, "per_map": per, "seconds": round(time.time() - t0)}
    json.dump(summary, open(out / "summary.json", "w"), indent=1)
    if REPLAY_DIR:
        import tarfile
        with tarfile.open(out / "replays.tgz", "w:gz") as t:
            for p in pathlib.Path(REPLAY_DIR).glob("*.replay"):
                t.add(p, arcname=p.name)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
