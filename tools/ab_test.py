"""Same-time ladder A/B test: two or more builds vs the same teams on the same maps, sent back to back.

    UNSWBC_KEY=... python tools/ab_test.py <sub A> <sub B> [<sub C> ...] --champion <sub> --teams 91,507,206
        [--maps 11,4,19,13,15] [--out ladder/ab_results.jsonl]

Battles bind the build that is active when they are requested, so each challenge activates its build just before
sending, and the champion is re-activated at the end. Opponents change bots all the time: only a comparison made in
the same minutes is fair. Waits for the results (retrying on quota) and prints both builds per team and in total.
"""
import argparse
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
    for attempt in range(5):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(3 + 3 * attempt)
    return {"error": "no JSON"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subs", type=int, nargs="+")
    ap.add_argument("--champion", type=int, required=True)
    ap.add_argument("--teams", required=True)
    ap.add_argument("--maps", default="11,4,19,13,15")
    ap.add_argument("--out", default="ladder/ab_results.jsonl", help="one JSON line per battle is appended here")
    a = ap.parse_args()
    teams = [int(t) for t in a.teams.split(",")]
    maps = [int(m) for m in a.maps.split(",")]
    sent = {}   # battle id -> (build, team)
    try:
        for t in teams:
            for sub in a.subs:
                while True:
                    api(f"/submissions/{sub}/activate", method="POST")
                    r = api("/battles", {"teamId": t, "ranked": False, "mapIds": maps})
                    if "ids" in r:
                        sent[r["ids"][0]] = (sub, t)
                        print(f"sent {sub} vs {t}: {r['ids'][0]}", flush=True)
                        break
                    if "free up" not in str(r.get("error", "")):
                        print(f"refused {sub} vs {t}: {r.get('error')}", flush=True)
                        break
                    api(f"/submissions/{a.champion}/activate", method="POST")
                    time.sleep(60)
    finally:
        api(f"/submissions/{a.champion}/activate", method="POST")
    res = {}
    while len(res) < len(sent):
        bl = api("/battles?limit=60")
        bl = bl.get("battles", bl) if isinstance(bl, dict) else bl
        for b in bl:
            if b["id"] in sent and b["id"] not in res and b.get("outcome") not in ("live", "queued"):
                res[b["id"]] = b
        if len(res) < len(sent):
            time.sleep(30)
    tot = {s: [0, 0] for s in a.subs}
    for bid, (sub, t) in sorted(sent.items(), key=lambda x: (x[1][1], x[1][0])):
        b = res[bid]
        tot[sub][0] += b["wins"]; tot[sub][1] += len(b["results"])
        with open(a.out, "a", encoding="utf-8") as f:
            f.write(json.dumps({"battle": bid, "sub": sub, "team": t, "opponent": b["opponent"], "opponentElo": b["opponentElo"],
                                "maps": maps, "results": b["results"], "at": b.get("at")}, ensure_ascii=False) + chr(10))
        print(f"  {b['opponent'][:20]:20s} ({b['opponentElo']})  build {sub}: {b['wins']}/{len(b['results'])} {''.join(r[0].upper() for r in b['results'])}")
    for sub, (w, n) in tot.items():
        print(f"TOTAL build {sub}: {w}/{n}")


if __name__ == "__main__":
    main()
