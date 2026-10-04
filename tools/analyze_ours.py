"""Pull our recent ranked/unranked series since an upload time, download every game's replay, analyse queens and results.

    set -a; . ./secrets.env; set +a
    uv run --python 3.11 --with unswbc python tools/analyze_ours.py --since 2026-10-03T08:12:07Z --out ladder/sv51 [--team 98]

Per game: map, side, opponent, win/loss, end reason, round count, OUR true-queen death round and cause (dragon id 0/1 owned by our team),
whether the enemy queen died and when, our dragons lost by cause, final score pair. Aggregates by map and by opponent.
Writes <out>/games.json and prints tables. Replays are public (GET /battles/<gameId>/replay).
"""
import argparse, collections, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from replay_lite import decode_lite  # noqa: E402

BASE = "https://game.battlecode.au/api/v1"; KEY = os.environ["UNSWBC_KEY"]
DEATHS = ["wall", "self", "body", "headon", "noaction"]
last = 0.0


def pace():
    global last
    time.sleep(max(0.0, 0.7 - (time.monotonic() - last))); last = time.monotonic()


def get(path):
    pace()
    r = subprocess.run(["curl.exe", "-sS", "--max-time", "45", BASE + path, "-H", "Authorization: Bearer " + KEY],
                       capture_output=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def download(game, dest):
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    pace(); dest.parent.mkdir(parents=True, exist_ok=True); tmp = dest.with_suffix(".part")
    r = subprocess.run(["curl.exe", "-sSL", "--max-time", "120", "-o", str(tmp), "-w", "%{http_code}", f"{BASE}/battles/{game}/replay",
                        "-H", "Authorization: Bearer " + KEY], capture_output=True, encoding="utf-8", errors="replace")
    if r.stdout.strip() == "200" and tmp.exists() and tmp.stat().st_size > 1000:
        tmp.replace(dest); return True
    tmp.unlink(missing_ok=True); return False


def analyse(path, our_side):
    rep = decode_lite(str(path), {"roundStart", "dragonDeath", "dragonSplit"})
    teams = [int(l.split()[1]) for l in rep["map"].splitlines() if l.split()[:1] == ["DRAGON"]][:2]
    team_of = {0: teams[0], 1: teams[1]} if len(teams) == 2 else {0: 0, 1: 1}
    me = 0 if our_side == "a" else 1
    our_q = next((q for q in (0, 1) if team_of[q] == me), me); enemy_q = 1 - our_q
    team = {}; births = collections.Counter()
    rnd = -1; qd = {our_q: None, enemy_q: None}; lost = collections.Counter(); n_dragons = 2; last_round = 0
    owner = dict(team_of)
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]; last_round = max(last_round, rnd)
        elif k == "dragonSplit":
            owner[e["child"]] = e["team"]
        elif k == "dragonDeath":
            why = DEATHS[e["reason"]] if e["reason"] < 5 else "?"
            if e["id"] in qd:
                qd[e["id"]] = (rnd, why)
            if owner.get(e["id"]) == me:
                lost[why] += 1
    res = rep["result"]
    return {"our_queen_death": qd[our_q], "enemy_queen_death": qd[enemy_q], "rounds": last_round, "lost": dict(lost),
            "end": res.get("endReason"), "winner": res.get("winner"), "ours": res.get("AB"[me]) if False else res.get("AB"[me]),
            "theirs": res.get("AB"[1 - me]), "me": me, "bot": (rep["botA"] if me == 0 else rep["botB"])}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--since", required=True); ap.add_argument("--out", default="ladder/sv51")
    ap.add_argument("--team", type=int, default=98); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    lst = get("/battles?limit=200"); lst = [b for b in lst if b["at"] >= a.since]
    print(len(lst), "series since", a.since, flush=True)
    games = []
    for b in lst:
        d = get(f"/battles/{b['id']}")
        if not d or "match" not in d:
            continue
        m = d["match"]; our_side = "a" if m["teamAId"] == a.team else "b"
        for g in d["games"]:
            if g.get("status") != "completed" or not g.get("hasReplay"):
                continue
            p = out / f"{g['id']}.replay"
            ok = download(g["id"], p)
            row = {"game": g["id"], "battle": b["id"], "map": g.get("mapName"), "side": our_side, "opp": b["opponent"], "oppElo": b["opponentElo"],
                   "ranked": b["ranked"], "win": g.get("winner") == our_side}
            if ok:
                try:
                    row.update(analyse(p, our_side))
                except Exception as ex:
                    row["error"] = f"{type(ex).__name__}: {ex}"
            games.append(row)
        json.dump(games, open(out / "games.json", "w"), indent=1, default=str)
        print("battle", b["id"], "games so far", len(games), flush=True)
    print("done", len(games), "games")


if __name__ == "__main__":
    main()
