"""Collect fresh replays of top teams' CURRENT bots by playing them (unranked), from several of our builds.

    UNSWBC_KEY=... python tools/collect_onpolicy.py --teams 470,566,... --builds 9285,8242,9195 --champion 9285 \
        [--maps 20,21,9,11,7,4,17,19,13,15] [--rounds 1] [--out ladder/il_onpolicy]

Each round sends one challenge per team, cycling through our builds (they bind at request, so each is activated
just before its send; the champion is re-activated at the end). Waits for quota when needed. Downloads every game's
replay to <out>/<teamId>/<gameId>.replay and writes <out>/index.json in the scout format (teamId, team, game, map,
side = the scouted team's side, winner), so ml/build_dataset.py can use it directly (it keeps the games they won).
"""
import argparse
import json
import os
import pathlib
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
    ap.add_argument("--teams", required=True)
    ap.add_argument("--builds", required=True)
    ap.add_argument("--champion", type=int, required=True)
    ap.add_argument("--maps", default="20,21,9,11,7,4,17,19,13,15")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--out", default="ladder/il_onpolicy")
    a = ap.parse_args()
    teams = [int(t) for t in a.teams.split(",")]
    builds = [int(b) for b in a.builds.split(",")]
    maps = [int(m) for m in a.maps.split(",")]
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ixf = out / "index.json"
    index = json.loads(ixf.read_text(encoding="utf-8")) if ixf.exists() else []
    sent = []
    k = 0
    try:
        for rnd in range(a.rounds):
            for t in teams:
                sub = builds[k % len(builds)]; k += 1
                while True:
                    api(f"/submissions/{sub}/activate", method="POST")
                    r = api("/battles", {"teamId": t, "ranked": False, "mapIds": maps})
                    if "ids" in r:
                        sent.append((r["ids"][0], t, sub)); print(f"sent {sub} vs {t}: {r['ids'][0]}", flush=True)
                        break
                    if "free up" not in str(r.get("error", "")):
                        print(f"refused vs {t}: {r.get('error')}", flush=True); break
                    api(f"/submissions/{a.champion}/activate", method="POST")
                    time.sleep(60)
    finally:
        api(f"/submissions/{a.champion}/activate", method="POST")
    pending = {bid for bid, _, _ in sent}
    while pending:
        bl = api("/battles?limit=80")
        bl = bl.get("battles", bl) if isinstance(bl, dict) else bl
        done = {b["id"] for b in bl if b["id"] in pending and b.get("outcome") not in ("live", "queued")}
        for bid, t, sub in sent:
            if bid not in done:
                continue
            d = api(f"/battles/{bid}")
            m = d.get("match", {})
            their_side = "A" if m.get("teamAId") == t else "B"
            name = d["teamAName"] if their_side == "A" else d["teamBName"]
            (out / str(t)).mkdir(exist_ok=True)
            for g in d.get("games", []):
                if g.get("status") != "completed":
                    continue
                p = out / str(t) / f"{g['id']}.replay"
                subprocess.run(["curl", "-sL", "-o", str(p), f"{BASE}/battles/{g['id']}/replay",
                                "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"])
                index.append({"teamId": t, "team": name, "game": g["id"], "map": g.get("mapName"), "side": their_side,
                              "winner": (g.get("winner") or "").upper(), "our_build": sub})
            print(f"  battle {bid} vs {name}: {sum(1 for g in d.get('games', []) if (g.get('winner') or '').upper() == their_side)}"
                  f"/{len(d.get('games', []))} won by them", flush=True)
        pending -= done
        ixf.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        if pending:
            time.sleep(30)
    print(f"index: {len(index)} games in {ixf}")


if __name__ == "__main__":
    main()
