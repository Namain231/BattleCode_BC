"""Test build on the ladder with the champion active as much as possible.

    UNSWBC_KEY=... python tools/probe.py <bot dir> <name> <champion id> --targets 777:15,4,19,11,13 45:19,15,4,11,13
        [--not-before-utc HH:MM] [--deadline-utc HH:MM]

Submits <bot dir> as <name> (label it "test-..."), sends one unranked challenge per target, and re-activates the
champion right after each send. The first battle is checked: if the server kept the test build for it (the
submission is bound when the battle is requested), every later challenge is sent the same way, so the test
build is only active for seconds. If not, the test build stays active until its battles finish (or the deadline).
Prints each battle's result and the submission that actually played it.
"""
import argparse
import datetime
import json
import os
import subprocess
import time

BASE = "https://game.battlecode.au/api/v1"
TEAM_ID = 98


def api(path, body=None, method=None):
    cmd = ["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    elif method:
        cmd += ["-X", method]
    for attempt in range(5):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(3 + 3 * attempt)
    return {"error": "no JSON"}


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def ist(t=None):
    return ((t or now()) + datetime.timedelta(hours=5, minutes=30)).strftime("%H:%M IST")


def at_utc(hhmm):
    h, m = map(int, hhmm.split(":"))
    return now().replace(hour=h, minute=m, second=0, microsecond=0)


def activate(sub):
    return api(f"/submissions/{sub}/activate", method="POST").get("status")


def our_sub_in(bid):
    m = api(f"/battles/{bid}").get("match", {})
    return m.get("submissionAId") if m.get("teamAId") == TEAM_ID else m.get("submissionBId")


def wait_done(bids, deadline):
    res = {}
    while len(res) < len(bids) and now() < deadline:
        bl = api("/battles?limit=50")
        bl = bl.get("battles", bl) if isinstance(bl, dict) else bl
        for b in bl:
            if b["id"] in bids and b["id"] not in res and b.get("outcome") not in ("live", "queued"):
                res[b["id"]] = b
        if len(res) < len(bids):
            time.sleep(30)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bot")
    ap.add_argument("name")
    ap.add_argument("champion", type=int)
    ap.add_argument("--targets", nargs="+", required=True, help="team:map,map,...")
    ap.add_argument("--not-before-utc", default=None)
    ap.add_argument("--deadline-utc", required=True)
    a = ap.parse_args()
    targets = [(int(t.split(":")[0]), [int(m) for m in t.split(":")[1].split(",")]) for t in a.targets]
    deadline = at_utc(a.deadline_utc)
    if a.not_before_utc and at_utc(a.not_before_utc) > now():
        time.sleep((at_utc(a.not_before_utc) - now()).total_seconds())
    print(f"[{ist()}] submitting {a.name}", flush=True)
    subprocess.run(["unswbc", "submit", a.bot, "-n", a.name, "-d", "test build (probe.py)"], capture_output=True)
    cand = None
    for _ in range(40):
        subs = api("/submissions")
        subs = subs.get("submissions", subs) if isinstance(subs, dict) else subs
        s = [x for x in subs if x["name"] == a.name]
        if s and s[0].get("status") in ("active", "idle"):
            cand = s[0]["id"]
            break
        time.sleep(10)
    if not cand:
        print("submission never became ready; champion:", activate(a.champion), flush=True)
        return
    print(f"[{ist()}] test build {cand}", flush=True)

    def send(team, maps):
        while now() < deadline:
            activate(cand)
            res = api("/battles", {"teamId": team, "ranked": False, "mapIds": maps})
            activate(a.champion)
            if "ids" in res:
                return res["ids"][0]
            if "free up" not in str(res.get("error", "")):
                print(f"  vs {team} refused: {res.get('error')}", flush=True)
                return None
            time.sleep(30)
        return None

    sent = {}
    try:
        first = send(*targets[0])
        if first is None:
            return
        sent[first] = targets[0][0]
        print(f"[{ist()}] sent vs {targets[0][0]}: {first}; champion re-activated; checking which build plays it", flush=True)
        wait_done({first}, deadline)
        bound = our_sub_in(first)
        quick = bound == cand
        print(f"[{ist()}] battle {first} was played by submission {bound} -> "
              f"{'bound at request: quick mode' if quick else 'bound at play time: keeping the test build active'}", flush=True)
        for team, maps in targets[1:]:
            if quick:
                bid = send(team, maps)
            else:
                activate(cand)
                bid = None
                while bid is None and now() < deadline:
                    res = api("/battles", {"teamId": team, "ranked": False, "mapIds": maps})
                    if "ids" in res:
                        bid = res["ids"][0]
                    elif "free up" in str(res.get("error", "")):
                        time.sleep(30)
                    else:
                        break
            if bid:
                sent[bid] = team
                print(f"[{ist()}] sent vs {team}: {bid}", flush=True)
        res = wait_done(set(sent), deadline)
    finally:
        print(f"[{ist()}] champion:", activate(a.champion), flush=True)
    total = games = 0
    for bid, team in sent.items():
        b = res.get(bid) if 'res' in dir() else None
        if not b:
            print(f"  {bid} vs {team}: unfinished", flush=True)
            continue
        total += b["wins"]; games += len(b["results"])
        print(f"  {b['opponent']:22s} {b['wins']}/{len(b['results'])} {b['results']}  played by {our_sub_in(bid)}", flush=True)
    print(f"TOTAL {total}/{games}", flush=True)


if __name__ == "__main__":
    main()
