"""ELO daemon: keeps ranked/test challenges running whenever the hourly quota allows.

    UNSWBC_KEY=... python tools/elo_bot.py --our-sub 8242 [--queue 319,22,524]

Loop (every --poll seconds):
  1. Read our recent battles; record finished tests and ranked series (ladder/elo_log.txt, ladder/elo_state.json).
  2. A finished unranked test with >= --need wins (of 5) whose team is still ranked-eligible (rated no more
     than 50 below us) is queued for a ranked challenge on the maps we won, topped up with the open maps.
     A team that lost us a ranked series is not challenged again until it is re-tested.
  3. Send the next challenge: ranked first, then tests (maze maps), at most --max-live series in flight.
     A quota error just means "try again next poll".
  4. When nothing is left to test, refresh candidates: teams above us (up to --max-above), falling first.
Stops if the active submission is no longer --our-sub (someone switched builds: don't spend ranked games on it).
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import time

BASE = "https://game.battlecode.au/api/v1"
ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "ladder" / "elo_state.json"
LOG = ROOT / "ladder" / "elo_log.txt"
TEST_MAPS = [11, 4, 19, 13, 15]          # Trophy, Default, Autarky, Devil, Trauma
OPEN_MAPS = [20, 21, 9]                  # Portals, Slithery, Schooltime: we usually win these
MAP_ID = {"Portals": 20, "Slithery Fight": 21, "Schooltime": 9, "Trophy": 11, "Queen Of Spades": 7,
          "Default": 4, "Prisoners Dilemma": 17, "Autarky": 19, "Devil": 13, "Trauma": 15}


def ist():
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)).strftime("%H:%M IST")


def log(msg):
    line = f"[{ist()}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def api(path, body=None, method=None):
    cmd = ["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    elif method:
        cmd += ["-X", method]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"error": r.stdout[:200]}


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"tests": {}, "ranked": {}, "queue": [], "ranked_queue": [], "done": {}}


def save_state(s):
    STATE.write_text(json.dumps(s, indent=1), encoding="utf-8")


def battle_maps(bid):
    d = api(f"/battles/{bid}")
    games = d.get("games") or []
    return [(g.get("mapName") or g.get("map") or "?", g.get("winner"), g.get("teamAId")) for g in games], d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--our-sub", type=int, required=True)
    ap.add_argument("--queue", default="", help="team ids to test first, comma separated")
    ap.add_argument("--need", type=int, default=3, help="test wins (of 5) needed for a ranked challenge")
    ap.add_argument("--max-live", type=int, default=2)
    ap.add_argument("--max-above", type=int, default=200)
    ap.add_argument("--poll", type=int, default=60)
    a = ap.parse_args()
    st = load_state()
    for t in [int(x) for x in a.queue.split(",") if x]:
        if t not in st["queue"] and str(t) not in st["done"]:
            st["queue"].append(t)
    save_state(st)
    log(f"elo_bot started; queue {st['queue']}")
    while True:
        try:
            tick(a, st)
        except Exception as e:  # network hiccups etc.
            log(f"error: {e!r}")
        save_state(st)
        time.sleep(a.poll)


def our_elo():
    t = api("/team")
    return (t.get("team") or t).get("elo") or 0


def team_elo(tid):
    t = api(f"/teams/{tid}")
    return (t.get("team") or t).get("elo") or 0


def tick(a, st):
    subs = api("/submissions")
    subs = subs.get("submissions", subs) if isinstance(subs, dict) else subs
    active = [s for s in subs if s.get("status") == "active"]
    if not active or active[0]["id"] != a.our_sub:
        log(f"active submission is {active[0]['id'] if active else None}, not {a.our_sub}: pausing")
        return
    battles = api("/battles?limit=30")
    battles = battles.get("battles", battles) if isinstance(battles, dict) else battles
    by_id = {str(b["id"]): b for b in battles}
    mine = set(st["tests"]) | set(st["ranked"])  # autoscrims don't count against our series cap
    live = sum(1 for b in battles if str(b["id"]) in mine and b.get("outcome") in ("live", "queued"))
    ours = our_elo()

    # 1-2. finished tests -> ranked decisions
    for bid, info in list(st["tests"].items()):
        b = by_id.get(bid)
        if not b or b.get("outcome") in ("live", "queued") or info.get("seen"):
            continue
        info["seen"] = True
        won = [m for m, r in zip(info["maps"], b["results"]) if r == "win"]
        te = team_elo(info["team"])
        log(f"test vs {b['opponent']} ({te}): {b['wins']}/{len(b['results'])} won maps {won}")
        st["done"][str(info["team"])] = {"name": b["opponent"], "test": f"{b['wins']}/{len(b['results'])}", "won": won}
        if b["wins"] >= a.need and te >= ours - 50:
            maps = (won + [m for m in OPEN_MAPS if m not in won])[:5]
            st["ranked_queue"].append({"team": info["team"], "name": b["opponent"], "maps": maps})
            log(f"  -> ranked queued vs {b['opponent']} on {maps}")
    for bid, info in list(st["ranked"].items()):
        b = by_id.get(bid)
        if not b or b.get("outcome") in ("live", "queued") or info.get("seen"):
            continue
        info["seen"] = True
        log(f"RANKED vs {b['opponent']} ({b['opponentElo']}): {b['wins']}/{len(b['results'])} elo {b['eloChange'] or 0:+d}; now ~{ours}")
        # one more ranked go if we clearly won and they are still eligible; after a loss, retest first
        if b["wins"] >= 4 and team_elo(info["team"]) >= ours - 50 and info.get("round", 1) < 2:
            st["ranked_queue"].append({"team": info["team"], "name": b["opponent"], "maps": info["maps"], "round": 2})

    if live >= a.max_live:
        return
    # 3. send the next challenge
    if st["ranked_queue"]:
        r = st["ranked_queue"][0]
        if team_elo(r["team"]) < ours - 50:
            log(f"  {r['name']} now out of ranked range, dropped")
            st["ranked_queue"].pop(0)
            return
        res = api("/battles", {"teamId": r["team"], "ranked": True, "mapIds": r["maps"]})
        if "ids" in res:
            st["ranked_queue"].pop(0)
            st["ranked"][str(res["ids"][0])] = {"team": r["team"], "maps": r["maps"], "round": r.get("round", 1)}
            log(f"sent RANKED vs {r['name']} maps {r['maps']}")
        elif "free up" not in str(res.get("error", "")):
            log(f"ranked vs {r['name']} refused: {res.get('error')}; dropped")
            st["ranked_queue"].pop(0)
        return
    # 4. refill candidates
    if not st["queue"]:
        board = api("/leaderboard")
        rows = board.get("teams", board) if isinstance(board, dict) else board
        cands = []
        for t in rows:
            e = t.get("elo") or 0
            if not (ours < e <= ours + a.max_above) or not (t.get("settings") or {}).get("ranked"):
                continue
            if str(t["id"]) in st["done"]:
                continue
            hist = (t.get("history") or [])[-12:]
            drop = (max(h["elo"] for h in hist) - e) if hist else 0
            cands.append((drop, e, t["id"]))
        cands.sort(reverse=True)
        st["queue"] = [tid for _, _, tid in cands[:8]]
        log(f"refilled queue: {st['queue']}")
        if not st["queue"]:
            return
    tid = st["queue"][0]
    res = api("/battles", {"teamId": tid, "ranked": False, "mapIds": TEST_MAPS})
    if "ids" in res:
        st["queue"].pop(0)
        st["tests"][str(res["ids"][0])] = {"team": tid, "maps": TEST_MAPS}
        log(f"sent test vs team {tid}")
    elif "free up" not in str(res.get("error", "")):
        log(f"test vs {tid} refused: {res.get('error')}; skipped")
        st["queue"].pop(0)


if __name__ == "__main__":
    main()
