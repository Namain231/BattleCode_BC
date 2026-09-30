"""ELO daemon: keeps ranked/test challenges running whenever the hourly quota allows.

    UNSWBC_KEY=... python tools/elo_bot.py --our-sub 8242 [--queue 319,22,524]

Loop (every --poll seconds):
  1. Read our recent battles; record finished tests and ranked series (ladder/elo_log.txt, ladder/elo_state.json).
  2. Ranked battles play 5 random maps of all 10 (the server refuses map picks since 29 Sept), so tests do too:
     5 random maps. A first test with >= 3/5 earns a second test; a ranked challenge needs >= 7/10 over both AND
     the Elo-expected score + --margin. (Old rule "3/5 on our 5 best maps" won 70% in tests but 54% in ranked:
     other maps + regression to the mean of one noisy 5-game test.)
     A team that lost us a ranked series is not challenged again until it is re-tested.
  3. Send the next challenge: ranked first, then tests, at most --max-live series in flight and one send per --gap s.
     A quota error just means "try again next poll".
  4. When nothing is left to test, refresh candidates: teams --min-above..--max-above above us, highest first.
Every test and ranked challenge re-checks that the target is still >= --min-above above us when it is sent.
Pauses while another submission is active (a candidate's unranked test: never spend ranked games or tests on it),
and re-activates --our-sub (the champion) within 5 minutes of every autoscrim draw (even UTC hours).
"""
import argparse
import datetime
import json
import os
import pathlib
import random
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # team names are not ASCII; Windows consoles are cp1252
BASE = "https://game.battlecode.au/api/v1"
ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "ladder" / "elo_state.json"
LOG = ROOT / "ladder" / "elo_log.txt"
ALL_MAPS = [20, 21, 9, 11, 7, 4, 17, 19, 13, 15]   # ranked draws 5 of these at random, so tests do the same
OPEN_MAPS = [20, 21, 9]                  # Portals, Slithery, Schooltime: we usually win these
if "UNSWBC_KEY" not in os.environ and (ROOT / "secrets.env").exists():   # the key file of the private repo
    for _line in (ROOT / "secrets.env").read_text().splitlines():
        if "=" in _line:
            _k, _v = _line.split("=", 1); os.environ.setdefault(_k.strip(), _v.strip())
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
    ap.add_argument("--margin", type=float, default=0.2,
                    help="challenge when the test score beats the Elo-expected score by this much")
    ap.add_argument("--max-live", type=int, default=1)
    ap.add_argument("--gap", type=int, default=300, help="seconds between two challenges we send")
    ap.add_argument("--max-above", type=int, default=120)
    ap.add_argument("--min-above", type=int, default=20, help="only test/challenge teams at least this far above us")
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
            import traceback
            log(f"error: {e!r} at line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
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
    # autoscrim draws happen on even UTC hours: the champion must be active for them
    t = datetime.datetime.now(datetime.timezone.utc)
    mins_to_draw = (60 - t.minute) if t.hour % 2 == 1 else (120 - t.minute if t.minute > 0 else 0)
    if mins_to_draw <= 5 and (not active or active[0]["id"] != a.our_sub):
        api(f"/submissions/{a.our_sub}/activate", method="POST")
        log(f"autoscrim in {mins_to_draw} min: re-activated champion {a.our_sub}")
        return
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
        te = team_elo(info["team"])
        key = str(info["team"])
        prev = st["done"].get(key) if info.get("second") else None
        w = b["wins"] + (prev["w"] if prev else 0); n = len(b["results"]) + (prev["n"] if prev else 0)
        log(f"test{' 2' if prev else ''} vs {b['opponent']} ({te}): {b['wins']}/{len(b['results'])}"
            f"{f' (total {w}/{n})' if prev else ''}")
        st["done"][key] = {"name": b["opponent"], "test": f"{w}/{n}", "w": w, "n": n}
        expected = 1 / (1 + 10 ** ((te - ours) / 400))
        if te < ours + a.min_above:
            continue
        if not prev and b["wins"] >= 3:
            st["queue"].insert(0, info["team"]); st.setdefault("second", []).append(info["team"])
            log(f"  -> second test vs {b['opponent']}")
        elif prev and w >= 7 and w / n >= expected + a.margin:
            st["ranked_queue"].append({"team": info["team"], "name": b["opponent"]})
            log(f"  -> ranked queued vs {b['opponent']} ({w}/{n}, expected {expected:.2f})")
    for bid, info in list(st["ranked"].items()):
        b = by_id.get(bid)
        if not b or b.get("outcome") in ("live", "queued") or info.get("seen"):
            continue
        info["seen"] = True
        log(f"RANKED vs {b['opponent']} ({b['opponentElo']}): {b['wins']}/{len(b['results'])} elo {b['eloChange'] or 0:+d}; now ~{ours}")
        # one more ranked go if we clearly won and they are still eligible; after a loss, retest first
        if b["wins"] >= 4 and team_elo(info["team"]) >= ours + a.min_above and info.get("round", 1) < 2:
            st["ranked_queue"].append({"team": info["team"], "name": b["opponent"], "round": 2})

    # every finished battle with a lost game (tests, ranked, autoscrims, incoming) gets a loss report
    for b in battles:
        bid = str(b["id"])
        if b.get("outcome") in ("live", "queued") or bid in st.setdefault("analysed", []):
            continue
        st["analysed"].append(bid)
        if "loss" not in b.get("results", []):
            continue
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "loss_report.py"), bid], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        with open(ROOT / "ladder" / "loss_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{ist()}] {'RANKED' if b['ranked'] else 'unranked'} {b['wins']}/{len(b['results'])} "
                    f"elo {b.get('eloChange') or 0:+d}\n{r.stdout}{r.stderr[-300:]}\n")
    st["analysed"] = st["analysed"][-300:]

    if live >= a.max_live or time.time() - st.get("last_send", 0) < a.gap:
        return
    # 3. send the next challenge
    if st["ranked_queue"]:
        r = st["ranked_queue"][0]
        if team_elo(r["team"]) < ours + a.min_above:
            log(f"  {r['name']} no longer above us, ranked dropped")
            st["ranked_queue"].pop(0)
            return
        res = api("/battles", {"teamId": r["team"], "ranked": True})
        if "ids" in res:
            st["ranked_queue"].pop(0); st["last_send"] = time.time()
            st["ranked"][str(res["ids"][0])] = {"team": r["team"], "round": r.get("round", 1)}
            log(f"sent RANKED vs {r['name']}")
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
            if not (ours + a.min_above <= e <= ours + a.max_above) or not (t.get("settings") or {}).get("ranked"):
                continue
            if str(t["id"]) in st["done"] or t["id"] in st["queue"]:
                continue
            hist = (t.get("history") or [])[-12:]
            drop = (max(h["elo"] for h in hist) - e) if hist else 0
            cands.append((drop, e, t["id"]))
        if not cands and st["done"]:
            # every eligible team has been tested once; they change bots all the time, so start the round again
            log(f"all {len(st['done'])} tested teams exhausted: clearing the list to re-test")
            st["done"] = {}
            return
        cands.sort(key=lambda c: -c[1])  # highest-rated first: wins there are worth the most
        st["queue"] = [tid for _, _, tid in cands[:8]]
        log(f"refilled queue: {st['queue']}")
        if not st["queue"]:
            return
    tid = st["queue"][0]
    if team_elo(tid) < ours + a.min_above:  # ratings move between refills
        log(f"team {tid} no longer above us, test skipped")
        st["queue"].pop(0)
        return
    maps = random.sample(ALL_MAPS, 5)
    res = api("/battles", {"teamId": tid, "ranked": False, "mapIds": maps})
    if "ids" in res:
        st["queue"].pop(0); st["last_send"] = time.time()
        second = tid in st.get("second", [])
        if second:
            st["second"].remove(tid)
        st["tests"][str(res["ids"][0])] = {"team": tid, "maps": maps, "second": second}
        log(f"sent test{' 2' if second else ''} vs team {tid}")
    elif "free up" not in str(res.get("error", "")):
        log(f"test vs {tid} refused: {res.get('error')}; skipped")
        st["queue"].pop(0)


if __name__ == "__main__":
    main()
