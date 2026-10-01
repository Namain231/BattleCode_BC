"""Run a decision extractor over a replay corpus and write one CSV.

    python -m rulemine extract --index ladder/scout_fresh/index.json --root ladder/scout_fresh \
        --teams SSS,PPP --decision death --out rulemine_data/death_top.csv [-j 10] [--winners-only]

The corpus index is the scouting format (one entry per team-game: team, game, side, map, winner). Replays are
found as <root>/*/<game>.replay. Our own games use the same format (scout_self).
"""
import csv
import glob
import json
import os
from multiprocessing import Pool

from . import decisions, evalstate


def find_replay(root, game):
    direct = os.path.join(root, f"{game}.replay")
    if os.path.exists(direct):
        return direct
    hits = glob.glob(os.path.join(root, "**", f"{game}.replay"), recursive=True)
    return hits[0] if hits else None


def jobs_from_index(index_path, root, teams=None, winners_only=False):
    idx = json.load(open(index_path))
    seen, jobs = set(), []
    for g in idx:
        if teams and g["team"] not in teams:
            continue
        if winners_only and g.get("winner") != g["side"]:
            continue
        key = (g["game"], g["side"])
        if key in seen:
            continue
        seen.add(key)
        path = find_replay(root, g["game"])
        if path:
            jobs.append((path, 0 if g["side"] == "A" else 1, g["team"]))
    return jobs


def _run(job):
    path, side, team, decision, pwin = job
    try:
        rows = decisions.EXTRACTORS[decision](path, side)
    except Exception as ex:   # a broken replay must not kill a long batch
        return path, [], f"{type(ex).__name__}: {ex}"
    ser = evalstate.series(path, side) if pwin and rows else None
    for r in rows:
        r["team"] = team
        if pwin:
            p = evalstate.at(ser, int(r["round"]))
            r["p_win"] = "" if p is None else round(p, 4)
    return path, rows, ""


def extract(index_path, root, decision, out, teams=None, workers=1, winners_only=False, log=print, pwin=True):
    if pwin and not evalstate.available():
        log("bceval unavailable (pycapnp?): rows get no p_win column")
        pwin = False
    jobs = [(p, s, t, decision, pwin) for p, s, t in jobs_from_index(index_path, root, teams, winners_only)]
    log(f"{len(jobs)} team-games to extract ({decision})")
    rows, errors = [], 0
    with Pool(max(1, workers)) as pool:
        for n, (path, r, err) in enumerate(pool.imap_unordered(_run, jobs), 1):
            if err:
                errors += 1
                log(f"  skip {os.path.basename(path)}: {err}")
            rows.extend(r)
            if n % 10 == 0:
                log(f"  {n}/{len(jobs)} games, {len(rows)} rows")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if rows:
        keys = list(rows[0].keys())
        for r in rows:
            for k in r:
                if k not in keys:
                    keys.append(k)
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    log(f"wrote {len(rows)} rows to {out} ({errors} replays skipped)")
    return rows
