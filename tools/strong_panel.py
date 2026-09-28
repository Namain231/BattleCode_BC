"""Ladder test of a candidate against a set of teams, then restore the champion.

    UNSWBC_KEY=... python tools/strong_panel.py <candidate sub id> <champion sub id> --teams 566,414,319,37,573
        [--maps 11,4,19,13,15] [--deadline-utc 09:55]

Activates the candidate, sends one unranked challenge per team as the hourly quota allows, waits for the
results, prints them map by map, and re-activates the champion. It always re-activates the champion by the
deadline (e.g. just before an autoscrim), even if games are still running.
"""
import argparse
import datetime
import json
import os
import subprocess
import time

BASE = "https://game.battlecode.au/api/v1"


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


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate", type=int)
    ap.add_argument("champion", type=int)
    ap.add_argument("--teams", required=True)
    ap.add_argument("--maps", default="11,4,19,13,15")
    ap.add_argument("--deadline-utc", required=True, help="HH:MM (today, UTC) by which the champion is restored")
    a = ap.parse_args()
    teams = [int(t) for t in a.teams.split(",")]
    maps = [int(m) for m in a.maps.split(",")]
    hh, mm = map(int, a.deadline_utc.split(":"))
    deadline = now_utc().replace(hour=hh, minute=mm, second=0, microsecond=0)
    print("activate candidate:", api(f"/submissions/{a.candidate}/activate", method="POST").get("status"), flush=True)
    sent = {}
    try:
        while len(sent) < len(teams) and now_utc() < deadline:
            for t in teams:
                if t in sent:
                    continue
                res = api("/battles", {"teamId": t, "ranked": False, "mapIds": maps})
                if "ids" in res:
                    sent[t] = res["ids"][0]
                    print(f"sent vs {t}: {res['ids'][0]}", flush=True)
                else:
                    break  # quota: wait
            if len(sent) < len(teams):
                time.sleep(30)
        pending = set(sent.values())
        results = {}
        while pending and now_utc() < deadline:
            bl = api("/battles?limit=40")
            bl = bl.get("battles", bl) if isinstance(bl, dict) else bl
            for b in bl:
                if b["id"] in pending and b.get("outcome") not in ("live", "queued"):
                    results[b["id"]] = b
                    pending.discard(b["id"])
                    print(f"{b['opponent']:20s} {b['wins']}/{len(b['results'])} {b['results']}", flush=True)
            if pending:
                time.sleep(30)
        total = sum(b["wins"] for b in results.values())
        games = sum(len(b["results"]) for b in results.values())
        print(f"TOTAL {total}/{games}  (unfinished series: {len(pending)})", flush=True)
    finally:
        print("restore champion:", api(f"/submissions/{a.champion}/activate", method="POST").get("status"), flush=True)


if __name__ == "__main__":
    main()
