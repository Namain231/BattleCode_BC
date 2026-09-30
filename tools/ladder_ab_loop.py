"""Continuous paired ladder A/B on the real ladder (unranked, free): candidate vs control on the SAME teams/maps/seeds,
round after round, with a generous SPRT on the paired results. Stops when the SPRT decides or after --max-rounds.

    python -u tools/ladder_ab_loop.py --cand 12349:AGY2 --control 12235:Y.10 --maps 21,9,20 [--per-round 5]

Each round: pick the next --per-round teams ranked within +-80 Elo of us that accept challenges (never reused), run
tools/top_scrims.py for both builds (one after the other; it handles quota, draws and champion restore), then pair the
games by (team, map) from ladder/top_scrims.jsonl. SPRT on discordant pairs: H0 p = 0.5 vs H1 p = 0.65, alpha = beta =
0.15. Progress -> ladder/ladder_ab_<cand>.txt
"""
import argparse
import json
import math
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ab_live as A  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


def pool(exclude):
    me = A.api("/team"); me = me.get("team", me); ours = me.get("elo") or 1660
    d = A.api("/leaderboard"); rows = d.get("teams", d) if isinstance(d, dict) else d
    rows = [t for t in rows if isinstance(t, dict) and t.get("id") != 98 and (t.get("settings") or {}).get("ranked")
            and abs((t.get("elo") or 0) - ours) <= 80 and t["id"] not in exclude]
    rows.sort(key=lambda t: abs((t.get("elo") or 0) - ours))
    return [t["id"] for t in rows]


def results(label, teams):
    out = {}
    for l in open(ROOT / "ladder" / "top_scrims.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r.get("label") == label and int(r["team"]) in teams and r.get("attributed_ok"):
            out[(int(r["team"]), r["map"])] = 1.0 if r["won"] else 0.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True); ap.add_argument("--control", required=True)
    ap.add_argument("--maps", default="21,9,20"); ap.add_argument("--per-round", type=int, default=5)
    ap.add_argument("--max-rounds", type=int, default=8); ap.add_argument("--per-team", type=int, default=0); ap.add_argument("--exclude", default="")
    a = ap.parse_args()
    csub, clab = a.cand.split(":"); ksub, klab = a.control.split(":")
    log = open(ROOT / "ladder" / f"ladder_ab_{clab}.txt", "a", encoding="utf-8")
    def say(s):
        A.log(s); log.write(s + "\n"); log.flush()
    used = {int(x) for x in a.exclude.split(",") if x}
    b = c = 0; cw = kw = n = 0
    bound = math.log(0.85 / 0.15)
    for rnd in range(a.max_rounds):
        teams = pool(used)[:a.per_round]
        if not teams:
            say("no more teams"); break
        used.update(teams)
        lab_c, lab_k = f"{clab}_r{rnd}", f"{klab}_r{rnd}"
        subprocess.run([sys.executable, "-u", "-W", "ignore", "tools/top_scrims.py", "--builds",
                        f"{csub}:{lab_c},{ksub}:{lab_k}", "--champion", "11461", "--teams", ",".join(map(str, teams)),
                        "--map-pool", a.maps, "--per-team", str(a.per_team or len(a.maps.split(","))), "--seed", str(100 + rnd)],
                       cwd=ROOT)
        rc, rk = results(lab_c, set(teams)), results(lab_k, set(teams))
        for k in rc:
            if k in rk:
                n += 1; cw += rc[k]; kw += rk[k]
                if rc[k] > rk[k]: b += 1
                elif rc[k] < rk[k]: c += 1
        llr = b * math.log(0.65 / 0.5) + c * math.log(0.35 / 0.5)
        say(f"round {rnd} teams {teams}: {clab} {sum(rc.values()):g}/{len(rc)} vs {klab} {sum(rk.values()):g}/{len(rk)}; "
            f"cumulative paired {clab} {cw:g} vs {klab} {kw:g} of {n}; b={b} c={c} LLR {llr:+.2f} (+-{bound:.2f})")
        if llr >= bound:
            say(f"VERDICT: {clab} BETTER than {klab} on the ladder"); break
        if llr <= -bound:
            say(f"VERDICT: {clab} NOT BETTER than {klab} on the ladder"); break
    A.activate(11461)


if __name__ == "__main__":
    main()
