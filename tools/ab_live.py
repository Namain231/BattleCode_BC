"""Ladder A/B that respects how the server binds builds: every GAME is played by whichever submission is active when
that game RUNS (not when it is requested; 29 Sept: a test "by the champion" was played entirely by a teammate's build).

    python tools/ab_live.py --cand <submission id> --champion 11461 --teams 481,722,... [--per-team 5] [--seed 1]

1. waits until no battle of ours is queued/live (autoscrim games included) and no autoscrim draw is near;
2. activates the candidate, sends one unranked battle per team (5 random maps of all 10, fixed per team);
3. keeps the candidate active until none of those games is pending any more, then re-activates the champion
   (also forced if an even-UTC-hour autoscrim draw is < 8 min away);
4. sends the identical battles for the champion; waits for all results;
5. reads every game's replay header to see which submission really played it, and scores only correctly attributed
   games. Appends one JSON line per game to ladder/ab_live.jsonl and prints totals per build (open vs maze too).
"""
import argparse
import datetime
import json
import os
import pathlib
import random
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import load  # noqa: E402

BASE = "https://game.battlecode.au/api/v1"
ROOT = pathlib.Path(__file__).resolve().parents[1]
ALL_MAPS = [20, 21, 9, 11, 7, 4, 17, 19, 13, 15]
OPEN = {"Portals", "Slithery Fight", "Schooltime"}
if "UNSWBC_KEY" not in os.environ and (ROOT / "secrets.env").exists():
    for _l in (ROOT / "secrets.env").read_text().splitlines():
        if "=" in _l:
            _k, _v = _l.split("=", 1); os.environ.setdefault(_k.strip(), _v.strip())


def log(msg):
    t = (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).strftime("%H:%M")
    print(f"[{t} IST] {msg}", flush=True)


def api(path, body=None, method=None):
    cmd = ["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    elif method:
        cmd += ["-X", method]
    for k in range(6):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(5 + 5 * k)
    return {"error": r.stdout[:200]}


def mins_to_draw():
    t = datetime.datetime.utcnow()
    return (60 - t.minute) if t.hour % 2 == 1 else (120 - t.minute if t.minute > 0 else 0)


def active_id():
    subs = api("/submissions")
    subs = subs.get("submissions", subs) if isinstance(subs, dict) else subs
    act = [s for s in subs if isinstance(s, dict) and s.get("status") == "active"]
    return act[0]["id"] if act else None


def activate(sub):
    api(f"/submissions/{sub}/activate", method="POST")
    for _ in range(20):
        if active_id() == sub:
            return True
        time.sleep(3)
    return False


def our_busy():
    bs = api("/battles?limit=30")
    bs = bs.get("battles", bs) if isinstance(bs, dict) else bs
    return [b for b in bs if isinstance(b, dict) and b.get("outcome") in ("live", "queued")]


def games_of(bid):
    d = api(f"/battles/{bid}")
    return d, d.get("games") or []


def send_all(teams, maps):
    ids = {}
    for t in teams:
        while True:
            r = api("/battles", {"teamId": t, "ranked": False, "mapIds": maps[t]})
            if "ids" in r:
                ids[t] = r["ids"][0]; break
            if "free up" in str(r.get("error", "")) or "quota" in str(r.get("error", "")).lower():
                time.sleep(60); continue
            log(f"team {t} refused: {r.get('error')}"); break
    return ids


def wait_started(ids, guard_champion=None):
    """Until no game of these battles is pending. If guard_champion is set, abort (re-activate it) near a draw."""
    while True:
        pending = 0
        for bid in ids.values():
            _, gs = games_of(bid)
            pending += sum(1 for g in gs if g.get("status") in ("pending", "queued", None))
        if pending == 0:
            return True
        if guard_champion and mins_to_draw() < 8:
            log(f"autoscrim draw in {mins_to_draw()} min with {pending} games pending: re-activating the champion")
            activate(guard_champion)
            return False
        log(f"{pending} games still pending")
        time.sleep(45)


def wait_done(ids):
    while True:
        left = 0
        for bid in ids.values():
            _, gs = games_of(bid)
            left += sum(1 for g in gs if g.get("status") != "completed")
        if left == 0:
            return
        time.sleep(60)


def attribute(ids, want, label, out):
    tot = {"all": [0.0, 0], "open": [0.0, 0], "maze": [0.0, 0], "wrong_build": 0}
    cache = ROOT / "ladder" / "attrib_game"; cache.mkdir(parents=True, exist_ok=True)
    for team, bid in ids.items():
        d, gs = games_of(bid)
        we_a = d.get("match", {}).get("teamAId") == 98
        for g in gs:
            if g.get("status") != "completed":
                continue
            p = cache / f"{g['id']}.replay"
            if not p.exists():
                subprocess.run(["curl", "-sL", "-o", str(p), f"{BASE}/battles/{g['id']}/replay",
                                "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"])
            try:
                rep = load(str(p)); sub = rep["botA"] if we_a else rep["botB"]
            except Exception:
                sub = "?"
            won = (g.get("winner") == "a") == we_a
            ok = str(sub) == str(want)
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps({"label": label, "team": team, "battle": bid, "game": g["id"], "map": g.get("mapName"),
                                    "won": won, "played_by": sub, "attributed_ok": ok}) + "\n")
            if not ok:
                tot["wrong_build"] += 1; continue
            kind = "open" if g.get("mapName") in OPEN else "maze"
            for k in ("all", kind):
                tot[k][0] += won; tot[k][1] += 1
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", type=int, required=True)
    ap.add_argument("--champion", type=int, required=True)
    ap.add_argument("--teams", required=True)
    ap.add_argument("--per-team", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--map-pool", default="", help="map ids to draw from (default all 10), e.g. 20,21,9 = open maps")
    ap.add_argument("--out", default=str(ROOT / "ladder" / "ab_live.jsonl"))
    a = ap.parse_args()
    teams = [int(t) for t in a.teams.split(",")]
    rng = random.Random(a.seed)
    pool = [int(m) for m in a.map_pool.split(",")] if a.map_pool else ALL_MAPS
    maps = {t: rng.sample(pool, min(a.per_team, len(pool))) for t in teams}
    # 1. quiet ladder, no draw near
    while True:
        busy = our_busy()
        if not busy and mins_to_draw() >= 35:
            break
        log(f"waiting: {len(busy)} battles live/queued, draw in {mins_to_draw()} min")
        time.sleep(60)
    # 2-3. candidate
    if not activate(a.cand):
        log("could not activate the candidate"); return
    log(f"candidate {a.cand} active; sending {len(teams)} battles")
    cand_ids = send_all(teams, maps)
    wait_started(cand_ids, guard_champion=a.champion)
    activate(a.champion)
    log(f"champion {a.champion} re-activated")
    # 4. champion, same battles
    champ_ids = send_all(teams, maps)
    wait_done(cand_ids); wait_done(champ_ids)
    if active_id() != a.champion:
        activate(a.champion)
    # 5. attribution
    c = attribute(cand_ids, a.cand, f"cand {a.cand}", a.out)
    h = attribute(champ_ids, a.champion, f"champion {a.champion}", a.out)
    for name, t in (("candidate", c), ("champion", h)):
        log(f"{name}: {t['all'][0]:g}/{t['all'][1]}  open {t['open'][0]:g}/{t['open'][1]}  maze {t['maze'][0]:g}/{t['maze'][1]}"
            f"  (games by another build, not counted: {t['wrong_build']})")


if __name__ == "__main__":
    main()
