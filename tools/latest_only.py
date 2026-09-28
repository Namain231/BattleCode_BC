"""Keep only games played by each scouted team's LATEST submission (teams improve; old versions teach old habits).

    UNSWBC_KEY=... python tools/latest_only.py ladder/il_data/index.json ladder/il_data2/index.json ... \
        --out ladder/latest_index.json [--min-games 4]

For every game in the scout indexes, reads the battle record to learn which submission the scouted team used
(cached in ladder/game_subs.json). Per team, keeps the games of its newest submission; if that one has fewer than
--min-games games, also keeps the previous submission's. Writes one combined index with absolute replay paths.
"""
import argparse
import collections
import json
import os
import pathlib
import subprocess
import time

BASE = "https://game.battlecode.au/api/v1"
ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "ladder" / "game_subs.json"


def get(path):
    for attempt in range(6):
        r = subprocess.run(["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(5 + 5 * attempt)
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("indexes", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-games", type=int, default=4)
    a = ap.parse_args()
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    games = {}
    for ix in a.indexes:
        base = pathlib.Path(ix).resolve().parent
        for g in json.load(open(ix, encoding="utf-8")):
            p = base / str(g["teamId"]) / f"{g['game']}.replay"
            if p.exists() and str(g["game"]) not in games:
                g = dict(g); g["path"] = str(p); games[str(g["game"])] = g
    # entries without submission ids (rate-limited lookups) are retried
    todo = [k for k in games if k not in cache or not (cache[k].get("a") and cache[k].get("b"))]
    print(f"{len(games)} games, {len(todo)} to look up", flush=True)
    for n, k in enumerate(todo):
        m = get(f"/battles/{k}").get("match", {})
        cache[k] = {"a": m.get("submissionAId"), "b": m.get("submissionBId"), "at": m.get("completedAt") or m.get("requestedAt")}
        if n % 50 == 49:
            CACHE.write_text(json.dumps(cache), encoding="utf-8"); print(f"  {n + 1}/{len(todo)}", flush=True)
        time.sleep(0.8)    # stay well under 120 requests/minute (other tools use the API too)
    CACHE.write_text(json.dumps(cache), encoding="utf-8")
    by_team = collections.defaultdict(lambda: collections.defaultdict(list))
    for k, g in games.items():
        c = cache.get(k, {})
        sub = c.get("a") if g["side"] == "A" else c.get("b")
        if sub:
            g["sub"] = sub; g["at"] = c.get("at")
            by_team[g["teamId"]][sub].append(g)
    keep = []
    for tid, subs in by_team.items():
        order = sorted(subs, reverse=True)          # submission ids grow over time: newest first
        chosen = subs[order[0]][:]
        if len(chosen) < a.min_games and len(order) > 1:
            chosen += subs[order[1]]
        keep += chosen
        g0 = chosen[0]
        print(f"  {g0['team'][:24]:24s} subs seen {len(order)}, newest {order[0]}: keep {len(chosen)} games"
              f" ({sum(1 for g in chosen if g['winner'] == g['side'])} won)", flush=True)
    json.dump(keep, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"kept {len(keep)} games, {sum(1 for g in keep if g['winner'] == g['side'])} won by the scouted team -> {a.out}")


if __name__ == "__main__":
    main()
