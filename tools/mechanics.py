"""How a side uses sprints and splits: ours (champion ladder games) vs top teams (their wins from ladder/slope).

    python tools/mechanics.py ours   [--glob "ladder/losses/*/*.replay"] [--sub 11461] [--n 30]
    python tools/mechanics.py top    [--rank-max 6] [--maps maze|open|all] [--n 40]
    python tools/mechanics.py compare [--n 30]                         # both, side by side

Per game, for the chosen side:
  sprints by purpose: ATTACK (ends in a head-on), COMBAT (an enemy head within 3 before it; no head-on), TRAVEL (no
  enemy head near); segments paid; pearls eaten on the sprint path; sprinter length; deaths during the sprint.
  splits: count by phase, child size, parent length, near an enemy head, and "split then a head-on by the parent within 2
  turns" (shrink first so a trade only costs 2 segments).
"""
import argparse
import collections
import glob
import json
import pathlib
import statistics as st
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
OPEN = {"Portals", "Slithery Fight", "Schooltime"}
DXY = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}


def cheb(a, b, W, H):
    dx = abs(a[0] - b[0]); dy = abs(a[1] - b[1])
    return max(min(dx, W - dx), min(dy, H - dy))


def analyse(path, side):
    rep = _decode(path)
    lines = rep["map"].splitlines()
    W, H = map(int, lines[0].split()[1:3])
    name = next((l.split(" ", 1)[1] for l in lines if l.startswith("MAP_NAME")), "?")
    team, body = {}, {}
    nid = 0
    for l in lines:
        p = l.split()
        if p and p[0] == "DRAGON":
            n = int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = int(p[1]); body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    alive = set(team); pearls = set(); rnd = 0
    c = collections.Counter(); lens = []; kids = []; parents = []
    recent_split = {}          # parent id -> round of its split
    inflight = {}              # sprinter id -> (purpose)
    spawn = {}                 # pearl cell -> round it appeared
    wreck = set()              # pearl cells dropped by a death (scavenging)
    pending_wreck = {}         # cell -> death round (becomes a wreck pearl when its pearl appears)
    delays = {0: [], 1: []}    # rounds a pearl waited before this side ate it (0 = ours/side, 1 = other)
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]; inflight = {}
        elif k == "tileChange":
            t = tuple(e["tile"])
            if e.get("pearl"):
                pearls.add(t); spawn.setdefault(t, rnd)
                if t in pending_wreck and rnd - pending_wreck.pop(t) <= 2:
                    wreck.add(t); c["wreck_made"] += 1
            else:
                pearls.discard(t); spawn.pop(t, None); wreck.discard(t)
        if k == "dragonAction" and e.get("act") == "move" and e["id"] in body and body[e["id"]] and e["id"] in team:
            who = 0 if team[e["id"]] == side else 1
            x, y = body[e["id"]][0]
            for ch in e.get("dirs", ""):
                dx, dy = DXY.get(ch, (0, 0)); x, y = (x + dx) % W, (y + dy) % H
                if (x, y) in pearls:
                    delays[who].append(rnd - spawn.get((x, y), rnd))
                    if (x, y) in wreck: c[f"scav{who}"] += 1
        if k == "roundStart":
            n_side = sum(1 for j in alive if team[j] == side)
            if n_side >= 62: c["at_cap"] += 1
        if k == "dragonAction" and team.get(e["id"]) == side and e["id"] in body and body[e["id"]]:
            i = e["id"]; hd = body[i][0]
            near = any(team[j] != side and body.get(j) and cheb(body[j][0], hd, W, H) <= 3 for j in alive)
            if e.get("act") == "move":   # pearls eaten on every move, by phase (the growth race)
                x, y = hd; ph0 = "r0-50" if rnd < 50 else "r50-100" if rnd < 100 else "r100-300" if rnd < 300 else "r300+"
                for ch in e.get("dirs", ""):
                    dx, dy = DXY.get(ch, (0, 0)); x, y = (x + dx) % W, (y + dy) % H
                    if (x, y) in pearls: c[f"eat@{ph0}"] += 1
            if e.get("act") == "move" and len(e.get("dirs", "")) > 1:
                d = e["dirs"]; ph = "r0-100" if rnd < 100 else "r100-300" if rnd < 300 else "r300+"
                purpose = "COMBAT" if near else "TRAVEL"
                c["sprints"] += 1; c[f"sprint@{ph}"] += 1; c["segs"] += len(d) - 1; lens.append(len(body[i]))
                x, y = hd; ate = 0
                for ch in d:
                    dx, dy = DXY.get(ch, (0, 0)); x, y = (x + dx) % W, (y + dy) % H
                    if (x, y) in pearls: ate += 1
                c["sprint_pearls"] += ate
                if ate: c["sprints_eating"] += 1
                inflight[i] = purpose
                c[f"purpose:{purpose}"] += 1
            elif e.get("act") == "split":
                ph = "r0-100" if rnd < 100 else "r100-300" if rnd < 300 else "r300+"
                c["splits"] += 1; c[f"split@{ph}"] += 1; parents.append(len(body[i])); kids.append(e.get("size", 0))
                if near: c["split_near_enemy"] += 1
                recent_split[i] = rnd
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]; hd = tuple(e["head"])
            if b[0] != hd: b.insert(0, hd)
            tl = tuple(e["tail"]) if e.get("tail") else None
            while len(b) > 1 and tl is not None and b[-1] != tl: b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]; body[e["child"]] = [tuple(x) for x in e["childBody"]]
            body[e["parent"]] = [tuple(x) for x in e["parentBody"]]; alive.add(e["child"])
        elif k == "dragonDeath":
            i = e["id"]; alive.discard(i)
            cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
            b = body.get(i) or []
            for cell in b[0::2]: pending_wreck[cell] = rnd          # every second segment becomes a pearl
            if team.get(i) != side and cause == "head to head": c["their_h2h"] += 1
            if team.get(i) == side:
                if i in inflight:
                    p = inflight.pop(i)
                    if cause == "head to head":
                        c[f"purpose:{p}"] -= 1; c["purpose:ATTACK"] += 1
                    else:
                        c["sprint_died_other"] += 1
                if cause == "head to head":
                    c["h2h_deaths"] += 1
                    if i in recent_split and rnd - recent_split[i] <= 2: c["split_then_h2h"] += 1
                    c["h2h_len_sum"] += len(body.get(i) or [])
    won = rep.get("result", {}).get("winner") == side
    c["delay_n0"] = len(delays[0]); c["delay_n1"] = len(delays[1])
    c["delay_fast0"] = sum(1 for d in delays[0] if d <= 1); c["delay_fast1"] = sum(1 for d in delays[1] if d <= 1)
    c["delay_sum0"] = sum(delays[0]); c["delay_sum1"] = sum(delays[1])
    return dict(map=name, c=c, lens=lens, kids=kids, parents=parents, won=won)


def summarise(label, rows):
    g = len(rows)
    if not g:
        print(f"{label}: no games"); return
    c = collections.Counter()
    for r in rows: c.update(r["c"])
    lens = [x for r in rows for x in r["lens"]]; kids = [x for r in rows for x in r["kids"]]; par = [x for r in rows for x in r["parents"]]
    sp = max(1, c["sprints"])
    print(f"\n== {label}: {g} games (won {sum(r['won'] for r in rows)})")
    print(f"  sprints/game {c['sprints'] / g:.1f}  (r0-100 {c['sprint@r0-100'] / g:.1f}, r100-300 {c['sprint@r100-300'] / g:.1f}, r300+ {c['sprint@r300+'] / g:.1f});"
          f" segments paid/game {c['segs'] / g:.1f}")
    print(f"  purpose: ATTACK {100 * c['purpose:ATTACK'] / sp:.0f}%  COMBAT {100 * c['purpose:COMBAT'] / sp:.0f}%  TRAVEL {100 * c['purpose:TRAVEL'] / sp:.0f}%;"
          f" sprints eating a pearl {100 * c['sprints_eating'] / sp:.0f}% ({c['sprint_pearls'] / g:.1f} pearls/game); died otherwise {100 * c['sprint_died_other'] / sp:.0f}%")
    if lens: print(f"  sprinter length median {st.median(lens)}")
    print(f"  splits/game {c['splits'] / g:.1f} (r0-100 {c['split@r0-100'] / g:.1f}, r100-300 {c['split@r100-300'] / g:.1f}, r300+ {c['split@r300+'] / g:.1f});"
          f" near an enemy head {100 * c['split_near_enemy'] / max(1, c['splits']):.0f}%;"
          + (f" child size median {st.median(kids)}, parent length median {st.median(par)}" if kids else ""))
    print(f"  pearl timing: eaten within 1 round of appearing {100 * c['delay_fast0'] / max(1, c['delay_n0']):.0f}% (opponents in these games"
          f" {100 * c['delay_fast1'] / max(1, c['delay_n1']):.0f}%), mean wait {c['delay_sum0'] / max(1, c['delay_n0']):.1f} v {c['delay_sum1'] / max(1, c['delay_n1']):.1f} rounds")
    sv = c["scav0"] + c["scav1"]
    wm = max(1, c["wreck_made"])
    print(f"  death-pearl scavenging: wreck pearls dropped {c['wreck_made'] / g:.0f}/game; eaten by this side {100 * c['scav0'] / wm:.0f}%,"
          f" by opponents {100 * c['scav1'] / wm:.0f}%, never eaten {100 * (wm - sv) / wm:.0f}% ({c['scav0'] / g:.1f} v {c['scav1'] / g:.1f}/game)")
    print(f"  head-on exchange: this side lost {c['h2h_deaths'] / g:.1f}/game, opponents {c['their_h2h'] / g:.1f}/game;"
          f" rounds at the unit cap (>= 62) {c['at_cap'] / g:.0f}/game")
    print("  pearls eaten/game: " + ", ".join(f"{ph} {c['eat@' + ph] / g:.1f}" for ph in ("r0-50", "r50-100", "r100-300", "r300+")))
    h = max(1, c["h2h_deaths"])
    print(f"  head-on deaths/game {c['h2h_deaths'] / g:.1f}, mean length lost per head-on {c['h2h_len_sum'] / h:.1f};"
          f" head-ons within 2 turns after a split {100 * c['split_then_h2h'] / h:.0f}%")


def ours(a):
    files = sorted(glob.glob(a.glob), key=lambda f: pathlib.Path(f).stat().st_mtime, reverse=True)
    rows = []
    for f in files:
        try:
            rep = _decode(f)
            m = __import__("re").search(r"_([AB])_\d+\.replay$", str(f))   # sandbox replays name our side
            side = (0 if m.group(1) == "A" else 1) if m else 0 if rep["botA"] and not rep["botB"] else 1 if rep["botB"] and not rep["botA"] else None
            if m: a_sub = None
            else: a_sub = a.sub
            if side is None or (a_sub and str(rep["botA"] if side == 0 else rep["botB"]) != str(a_sub)): continue
            r = analyse(f, side)
        except Exception:   # noqa: BLE001
            continue
        if keep_map(r["map"], a.maps) and (a.result == "all" or r["won"] == (a.result == "won")): rows.append(r)
        if len(rows) >= a.n: break
    return rows


def keep_map(m, which):
    return which == "all" or (which == "open") == (m in OPEN)


def top(a):
    idx = json.load(open(ROOT / "ladder/slope/index.json", encoding="utf-8"))
    sel = [r for r in idx if r["rank"] <= a.rank_max and r["winner"] == r["side"] and keep_map(r["map"], a.maps)
           and (ROOT / r["path"].replace("\\", "/")).exists()]
    sel.sort(key=lambda r: r["at"], reverse=True)
    rows = []
    for r in sel[:a.n]:
        try:
            rows.append(analyse(str(ROOT / r["path"].replace("\\", "/")), 0 if r["side"] in ("A", 0, "a") else 1))
        except Exception:   # noqa: BLE001
            continue
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["ours", "top", "compare"])
    ap.add_argument("--glob", default="ladder/losses/*/*.replay"); ap.add_argument("--sub", default="11461")
    ap.add_argument("--rank-max", type=int, default=6); ap.add_argument("--maps", default="all", choices=["all", "maze", "open"])
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--result", default="all", choices=["all", "won", "lost"], help="ours: only games this side won/lost")
    a = ap.parse_args()
    if a.mode in ("ours", "compare"): summarise(f"OURS (sub {a.sub}, {a.maps} maps)", ours(a))
    if a.mode in ("top", "compare"): summarise(f"TOP-{a.rank_max} WINS ({a.maps} maps)", top(a))


if __name__ == "__main__":
    main()
