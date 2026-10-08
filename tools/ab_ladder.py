"""Paired ladder A/B: candidate vs champion, same teams, same maps, back-to-back, with mechanism
analysis on the downloaded replays -- not just win/loss.

Built 2026-09-30 after a real mistake: `strong_panel.py` alone tested a candidate against 5 teams
rated 2035-2090 with no champion baseline, got 4/25, and that was nearly reported as "refuted". A
same-time control (this script's method, run by hand) showed the champion itself only scores 8/25
against the same teams -- our own ~1667 rating gives an Elo-expected ~10% there, so 25 games against
teams that far above us has almost no power (a proportion near a 0/1 floor barely moves). **A ladder
test without a same-time control arm is uninterpretable, and testing against teams far from our own
rating wastes the games on a floor/ceiling effect.**

This script always runs both arms, defaults to near-rating opponents (where a real difference is
visible as a real probability, not a floor effect), and turns every replay into a scout.py-style
index.json so `behaviour_profile.py` / `death_context.py` / `profile_style.py` can read the *mechanism*
difference between the two arms directly -- win rate over ~25-80 games per arm is still noisy (see
insights.md's repeated ~7-9pp panel bias), but the per-dragon-turn rates those tools compute need far
fewer games to resolve a real effect.

    UNSWBC_KEY=... uv run --python 3.11 python tools/ab_ladder.py CANDIDATE_ID CHAMPION_ID \
        --teams 133,45,328,456,1067,875,777,311 --maps 11,4,19,13,15 --out ladder/ab_test \
        --deadline-utc 15:30

Always re-activates CHAMPION_ID in a `finally`, exactly like strong_panel.py, so an interrupted run
never leaves the candidate live on the ladder.
"""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys
import time

BASE = "https://game.battlecode.au/api/v1"
OUR_TEAM_ID = 98


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


def send_all(teams, maps):
    """One unranked challenge (a whole map-series 'battle') per team. -> {team_id: battle_id}"""
    sent = {}
    while len(sent) < len(teams):
        progressed = False
        for t in teams:
            if t in sent:
                continue
            res = api("/battles", {"teamId": t, "ranked": False, "mapIds": maps})
            if "ids" in res:
                sent[t] = res["ids"][0]
                progressed = True
                print(f"  sent vs {t}: {res['ids'][0]}", flush=True)
        if not progressed:
            time.sleep(30)  # hourly quota: wait it out
    return sent


def wait_all(battle_ids, deadline):
    """Poll /battles until every id in battle_ids has a non-live outcome, or the deadline passes."""
    pending = set(battle_ids)
    results = {}
    while pending and now_utc() < deadline:
        bl = api("/battles?limit=60")
        bl = bl.get("battles", bl) if isinstance(bl, dict) else bl
        for b in bl:
            if isinstance(b, dict) and b.get("id") in pending and b.get("outcome") not in ("live", "queued"):
                results[b["id"]] = b
                pending.discard(b["id"])
        if pending:
            time.sleep(20)
    return results, pending


def battle_games(battle_id):
    d = api(f"/battles/{battle_id}")
    return d, d.get("games", [])


def download_replay(game_id, dst):
    if dst.exists():
        return
    subprocess.run(["curl", "-sL", "-o", str(dst), f"{BASE}/battles/{game_id}/replay",
                    "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"])


def run_arm(label, sub_id, teams, maps, out, deadline):
    print(f"\n=== arm '{label}': activating {sub_id} ===", flush=True)
    print("  activate:", api(f"/submissions/{sub_id}/activate", method="POST").get("status"), flush=True)
    battle_of_team = send_all(teams, maps)
    results, pending = wait_all(set(battle_of_team.values()), deadline)
    if pending:
        print(f"  ! {len(pending)} battle(s) did not finish before the deadline, skipped", file=sys.stderr)
    (out / label).mkdir(parents=True, exist_ok=True)
    index = []
    wins = losses = 0
    for team_id, bid in battle_of_team.items():
        if bid not in results:
            continue
        _bsum = results[bid]
        detail, games = battle_games(bid)
        for g in games:
            if g.get("status") != "completed":
                continue
            side = "A" if detail["match"]["teamAId"] == OUR_TEAM_ID else "B"
            opp_side = "B" if side == "A" else "A"
            opp_name = detail["teamBName"] if side == "A" else detail["teamAName"]
            opp_elo = detail["teamBElo"] if side == "A" else detail["teamAElo"]
            win = str(g.get("winner")).lower() == side.lower()
            wins += win
            losses += not win
            dst = out / label / f"{g['id']}.replay"
            download_replay(g["id"], dst)
            index.append({"teamId": label, "team": label, "rank": None, "elo": 0, "game": g["id"],
                          "map": g.get("mapName", detail.get("mapName", "")), "side": side,
                          "opponent": opp_name, "opponentElo": opp_elo,
                          "winner": side if win else opp_side})
    print(f"  arm '{label}': {wins}/{wins + losses}", flush=True)
    return index, wins, losses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate", type=int)
    ap.add_argument("champion", type=int)
    ap.add_argument("--teams", required=True)
    ap.add_argument("--maps", default="11,4,19,13,15")
    ap.add_argument("--out", required=True)
    ap.add_argument("--deadline-utc", required=True)
    a = ap.parse_args()
    teams = [int(t) for t in a.teams.split(",")]
    maps = [int(m) for m in a.maps.split(",")]
    hh, mm = map(int, a.deadline_utc.split(":"))
    deadline = now_utc().replace(hour=hh, minute=mm, second=0, microsecond=0)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    all_index = []
    try:
        idx_c, wc, lc = run_arm("candidate", a.candidate, teams, maps, out, deadline)
        idx_h, wh, lh = run_arm("champion", a.champion, teams, maps, out, deadline)
        all_index = idx_c + idx_h
        print(f"\n=== TOTAL  candidate {wc}/{wc + lc}   champion {wh}/{wh + lh} ===")
        print("(win-rate alone is noisy at this sample size -- run behaviour_profile.py / "
              "death_context.py on this dir's index.json for the lower-variance mechanism read)")
    finally:
        (out / "index.json").write_text(json.dumps(all_index, indent=1), encoding="utf-8")
        print("\nrestore champion:", api(f"/submissions/{a.champion}/activate", method="POST").get("status"),
              flush=True)


if __name__ == "__main__":
    main()
