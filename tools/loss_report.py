"""Why did we lose? Downloads the lost games of ladder battles and classifies each loss.

    UNSWBC_KEY=... python tools/loss_report.py <battle id> [<battle id> ...] [--team "Bhole Chature"]

For every lost game: the units/longest/total timeline for both sides, a loss type, and how our dragons died in
the phase where the game turned (cause/indicator tag, e.g. "hit wall/DOOMED" = trapped, "no valid action/FEED" =
fed to the queen, "head to head/ATK" = our attack). Replays go to ladder/losses/<battle id>/.
Loss types:
  WIPED EARLY    - eliminated before round 300
  OUTNUMBERED    - they had >= 1.5x our units (+2) at round 100: the opening economy
  MID-GAME WAR   - even at 100, clearly behind at 300: the head-on war / trapped drones
  LATE COLLAPSE  - we led units and total at 400 but lost
  TIEBREAK       - alive at 500 with more total length but a shorter longest dragon
  BEHIND ON MASS - alive at 500, less total length
"""
import argparse
import collections
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import load, DEATHS  # noqa: E402

BASE = "https://game.battlecode.au/api/v1"
ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECK = (100, 200, 300, 400)


def get(path):
    for attempt in range(6):
        r = subprocess.run(["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(5 + 5 * attempt)
    raise RuntimeError(f"no JSON from {path}")


def analyse(path, side):
    """Timeline snapshots and per-phase death causes of `side` (0 = A, 1 = B)."""
    rep = load(path)
    team, body, nid = {}, {}, 0
    for line in rep["map"].splitlines():
        p = line.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t; body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    alive = set(team)
    ind = {}
    deaths = collections.defaultdict(collections.Counter)  # phase -> cause -> count
    snaps = {}
    longest_ids = {}
    rnd = 0

    def snap():
        out = []
        for s in (side, 1 - side):
            ls = [len(body[i]) for i in alive if team[i] == s]
            out.append((len(ls), max(ls or [0]), sum(ls)))
        return out

    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd in CHECK:
                snaps[rnd] = snap()
                mine = [(len(body[i]), i) for i in alive if team[i] == side]
                if mine:
                    longest_ids[rnd] = max(mine)
        elif k == "dragonIndicator":
            ind[e["id"]] = e["text"]
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]
            if b[0] != e["head"]: b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]: b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            body[e["child"]] = e["childBody"]; body[e["parent"]] = e["parentBody"]; alive.add(e["child"])
        elif k == "dragonDeath":
            i = e["id"]
            if team.get(i) == side:
                tag = (ind.get(i, "").split() or ["-"])[0]
                tag = "" if tag.startswith("L") or tag == "-" else "/" + tag
                phase = "0-100" if rnd < 100 else "100-300" if rnd < 300 else "300-400" if rnd < 400 else "400-500"
                deaths[phase][DEATHS[e["reason"]] + tag] += 1
                if rnd >= 400 and 400 in longest_ids and i == longest_ids[400][1]:
                    deaths["queen"][f"our longest at r400 (len {longest_ids[400][0]}) died r{rnd}: {DEATHS[e['reason']]}{tag}"] += 1
            alive.discard(i)
    snaps["end"] = snap()
    return rep, snaps, deaths, rnd


def classify(snaps, last_round):
    (u, t) = snaps["end"]
    if u[0] == 0 and last_round < 300:
        kind = "WIPED EARLY"
    elif 100 in snaps and snaps[100][1][0] >= 1.5 * snaps[100][0][0] + 2:
        kind = "OUTNUMBERED"
    elif 300 in snaps and snaps[300][1][0] >= 1.5 * snaps[300][0][0] + 2:
        kind = "MID-GAME WAR"
    elif 400 in snaps and snaps[400][0][0] >= snaps[400][1][0] and snaps[400][0][2] >= snaps[400][1][2]:
        kind = "LATE COLLAPSE"
    elif u[0] and u[2] > t[2] and u[1] < t[1]:
        kind = "TIEBREAK"
    elif u[0]:
        kind = "BEHIND ON MASS"
    else:
        kind = "WIPED"
    if kind == "LATE COLLAPSE" and u[0] and u[2] > t[2] and u[1] < t[1]:
        kind += " (lost on longest with more total)"
    return kind


def phase_of(kind):
    return {"OUTNUMBERED": "0-100", "WIPED EARLY": "0-100", "MID-GAME WAR": "100-300"}.get(kind.split(" (")[0], "400-500")


def report(battle_id, team_name):
    d = get(f"/battles/{battle_id}")
    ours_a = d.get("teamAName") == team_name
    opp = d["teamBName"] if ours_a else d["teamAName"]
    side_letter = "a" if ours_a else "b"
    out_dir = ROOT / "ladder" / "losses" / str(battle_id)
    lines = []
    for g in d.get("games", []):
        if g.get("status") != "completed" or g.get("winner") == side_letter:
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{g['id']}.replay"
        if not path.exists():
            subprocess.run(["curl", "-sL", "-o", str(path), f"{BASE}/battles/{g['id']}/replay",
                            "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"])
        try:
            rep, snaps, deaths, last = analyse(str(path), 0 if ours_a else 1)
        except Exception as e:  # a replay we cannot parse should not stop the report
            lines.append(f"  {g.get('mapName', '?'):16s} (replay unreadable: {e!r})")
            continue
        kind = classify(snaps, last)
        tl = " ".join(f"{k}:{a[0]}/{a[1]}/{a[2]}-{b[0]}/{b[1]}/{b[2]}" for k, (a, b) in snaps.items())
        top = ", ".join(f"{c} {n}" for c, n in deaths[phase_of(kind)].most_common(3))
        q = "; ".join(deaths["queen"])
        lines.append(f"  {g.get('mapName', '?'):16s} {kind}\n      {tl}\n      our deaths r{phase_of(kind)}: {top or '-'}"
                     + (f"\n      {q}" if q else ""))
    head = f"battle {battle_id} vs {opp}: {len(lines)} lost game(s)  (units/longest/total, us-them)"
    return head + ("\n" + "\n".join(lines) if lines else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("battles", nargs="+", type=int)
    ap.add_argument("--team", default="Bhole Chature")
    a = ap.parse_args()
    for b in a.battles:
        print(report(b, a.team), flush=True)


if __name__ == "__main__":
    main()
