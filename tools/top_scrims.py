"""Overnight: every build plays the SAME top-ranked teams on the SAME maps (unranked), one build after another.
Metric = score vs the top rankers (the teammates' "8/30 vs top rankers" yardstick). Unattended-safe:

    python -u tools/top_scrims.py --builds 12130:Nv1.9,12301:Y.10 --champion 11461 --top 6 [--per-team 5] [--seed 7]

- teams: the top --top ranked teams that accept challenges (fixed for the whole run), 5 random maps each (fixed);
- per build: activate it, send one unranked battle per team, keep it active until none of its games is pending,
  then the next build; the champion is re-activated after every build and before every autoscrim draw (even UTC
  hours; we pause 8 min before until the draw's games have started);
- a build whose battles are refused (quota) waits and retries; nothing is skipped silently;
- results: every game's real build from the replay header -> ladder/top_scrims.jsonl; running totals printed after
  each build and again at the end (all maps / open / maze).
"""
import argparse
import json
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ab_live as A  # noqa: E402  (api, activate, active_id, our_busy, games_of, mins_to_draw, attribute, log)

ROOT = pathlib.Path(__file__).resolve().parents[1]


def top_teams(n):
    d = A.api("/leaderboard")
    rows = d.get("teams", d) if isinstance(d, dict) else d
    rows = [t for t in rows if isinstance(t, dict) and t.get("id") != 98]
    rows.sort(key=lambda t: -(t.get("elo") or 0))
    return [(t["id"], t.get("name"), t.get("elo")) for t in rows[:n * 3]]


def draw_guard(champion):
    """Near an autoscrim draw: champion active, then wait until the draw has happened and its games have started."""
    if A.mins_to_draw() >= 9:
        return
    A.log(f"autoscrim draw in {A.mins_to_draw()} min: champion on, pausing")
    A.activate(champion)
    while A.mins_to_draw() < 9 or A.mins_to_draw() > 115:   # until ~5 min after the draw
        time.sleep(60)
    while True:
        busy = A.our_busy()
        pending = 0
        for b in busy:
            _, gs = A.games_of(b["id"])
            pending += sum(1 for g in gs if g.get("status") in ("pending", "queued", None))
        if pending == 0:
            break
        time.sleep(60)
    A.log("draw games started; resuming")


def send_build(sub, teams, maps, champion):
    ids = {}
    for t in teams:
        refusals = 0
        while t not in ids and refusals < 3:
            draw_guard(champion)
            if A.active_id() != sub:
                A.activate(sub)
            r = A.api("/battles", {"teamId": t, "ranked": False, "mapIds": maps[t]})
            if "ids" in r:
                ids[t] = r["ids"][0]
            else:
                err = str(r.get("error", ""))
                quota = any(w in err.lower() for w in ("free up", "quota", "limit", "too many", "rate"))
                if not quota:
                    refusals += 1   # a real refusal: give up on this team after 3
                    A.log(f"  team {t}: {err[:90]} (retry in 2 min)")
                    time.sleep(120)
                    continue
                # quota: never leave a test build active while we wait (incoming ranked games would use it)
                import re as _re
                m = _re.search(r"free up in (\d+) min", err)
                wait = (int(m.group(1)) + 1) * 60 if m else 300
                A.log(f"  quota: champion on, waiting {wait // 60} min ({err[:60]})")
                A.activate(champion)
                time.sleep(wait)
    # keep the build active until all its games left the queue
    while True:
        pending = 0
        for bid in ids.values():
            _, gs = A.games_of(bid)
            pending += sum(1 for g in gs if g.get("status") in ("pending", "queued", None))
        if pending == 0:
            break
        if A.mins_to_draw() < 9:
            A.log(f"  {pending} games still pending at a draw: they may be played by the champion (attribution drops them)")
            draw_guard(champion)
            A.activate(sub)
        time.sleep(40)
    A.activate(champion)
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--builds", required=True, help="sub:label,sub:label,...")
    ap.add_argument("--champion", type=int, required=True)
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--teams", default="", help="explicit team ids instead of the current top")
    ap.add_argument("--per-team", type=int, default=5)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--map-pool", default="", help="map ids to draw from (default all 10)")
    ap.add_argument("--out", default=str(ROOT / "ladder" / "top_scrims.jsonl"))
    ap.add_argument("--interleave", action="store_true",
                    help="team-major order: every build plays team 1, then every build plays team 2, ... (running tally per team)")
    a = ap.parse_args()
    builds = [(int(x.split(":")[0]), x.split(":", 1)[1]) for x in a.builds.split(",")]
    if a.teams:
        teams = [int(t) for t in a.teams.split(",")]
    else:
        cands = top_teams(a.top)
        teams = [t for t, _, _ in cands[:a.top]]
        A.log("top teams: " + ", ".join(f"{n} ({e})" for _, n, e in cands[:a.top]))
    rng = random.Random(a.seed)
    pool = [int(m) for m in a.map_pool.split(",")] if a.map_pool else A.ALL_MAPS
    maps = {t: rng.sample(pool, min(a.per_team, len(pool))) for t in teams}
    A.log(f"teams {teams}; maps {maps}")
    results, reported = {}, set()

    def report_finished(final=False):
        for label, (sub, ids) in results.items():
            if label in reported:
                continue
            left = sum(1 for bid in ids.values() for g in A.games_of(bid)[1] if g.get("status") != "completed")
            if left and not final:
                continue
            if left:
                A.wait_done(ids)
            t = A.attribute(ids, sub, label, a.out)
            reported.add(label)
            A.log(f"RESULT {label} ({sub}): {t['all'][0]:g}/{t['all'][1]}  open {t['open'][0]:g}/{t['open'][1]}  "
                  f"maze {t['maze'][0]:g}/{t['maze'][1]}  (other-build games dropped: {t['wrong_build']})")

    def tally():
        out = []
        for label, (sub, ids) in results.items():
            w = n = 0
            for bid in ids.values():
                d, gs = A.games_of(bid)
                ours_a = d.get("match", {}).get("teamAId") == 98
                for g in gs:
                    if g.get("status") == "completed":
                        n += 1; w += g.get("winner") == ("a" if ours_a else "b")
            out.append(f"{label} {w}/{n}")
        return "  ".join(out)

    if a.interleave:
        for t in teams:
            for sub, label in builds:
                while A.our_busy() and A.mins_to_draw() >= 9:
                    time.sleep(60)
                A.log(f"team {t}: build {label} ({sub}) sending")
                ids = send_build(sub, [t], maps, a.champion)
                with open(ROOT / "ladder" / "top_scrims_sent.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"label": label, "sub": sub, "battles": ids, "maps": {t: maps[t]}}) + "\n")
                results.setdefault(label, (sub, {}))[1].update(ids)
            A.log(f"running tally after team {t} (finished games, unattributed): {tally()}")
        builds = []   # everything is sent; fall through to the final report
    for sub, label in builds:
        while A.our_busy() and A.mins_to_draw() >= 9:   # something else of ours is running: let it finish
            time.sleep(60)
        A.log(f"build {label} ({sub}): sending")
        ids = send_build(sub, teams, maps, a.champion)
        A.log(f"build {label}: all games started")
        with open(ROOT / "ladder" / "top_scrims_sent.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"label": label, "sub": sub, "battles": ids, "maps": maps}) + "\n")
        results[label] = (sub, ids)
        report_finished()
    if A.active_id() != a.champion:
        A.activate(a.champion)
    report_finished(final=True)
    A.log("all builds done; champion active")


if __name__ == "__main__":
    main()
