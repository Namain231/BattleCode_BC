"""Ladder digest: per-game analysis of our replays (named <map>_<A|B>_<gameid>.replay, our side = the letter).

    python tools/ladder_digest.py FOLDER_OR_GLOB

Per game block:
  (a) result + how decided (queen_report.analyse: queen fates and 'how')
  (b) THROWN WIN flag: their queen died before ours AND ours lived past r300 but died before r500
      -> our queen's death round, cause, KILLER (for head-on: the dragon that moved into her, its team,
         whether its step crossed a PORTAL edge)
  (c) economy: pearls eaten per side in r0-50, 50-100, 100-150 (eater = dragon of latest 'turnStart'
      before tileChange that removes pearl); living dragons per side at r50/100/150/300; first round
      r>=10 where their living count >= 1.5x ours (and >= ours+4) ('NUMBERS GAP')
  (d) endgame: mass (sum of lengths) and longest per side at r100/200/300/400/450; feeding collapse =
      our mass drops >= 50% in r340-r370
Summary: thrown wins (count + killers), median eaten gap per window, numbers-gap rounds, feeding
  collapses, and for each LOSS a one-line 'why' (THROWN WIN / ECONOMY / ENDGAME / OTHER).
"""
import collections
import glob as globmod
import pathlib
import re
import statistics as st
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402
from queen_report import analyse as queen_analyse  # noqa: E402

DXY = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}


def our_side(path, rep):
    m = re.search(r"_([AB])_\d+\.replay$", str(path))
    if m:
        return 0 if m.group(1) == "A" else 1
    a, b = rep.get("botA"), rep.get("botB")
    return 0 if a and not b else 1 if b and not a else 0


def analyse(path):
    rep = _decode(str(path))
    L = rep["map"].splitlines()
    W, H = map(int, L[0].split()[1:3])
    kind = {}
    for l in L:
        p = l.split()
        if p and p[0] == "EDGE" and len(p) >= 3:
            kind[int(p[1])] = int(p[2])

    def edge(x, y, d):
        if d == "N":
            return kind.get((2 * y) * (W + 1) + x, 0)
        if d == "S":
            return kind.get((2 * (y + 1)) * (W + 1) + x, 0)
        if d == "W":
            return kind.get((2 * y + 1) * (W + 1) + x, 0)
        if d == "E":
            return kind.get((2 * y + 1) * (W + 1) + x + 1, 0)
        return 0

    team = {}
    body = {}
    head = {}
    alive = set()
    nid = 0
    for l in L:
        p = l.split()
        if p and p[0] == "DRAGON":
            n = int(p[2])
            c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = int(p[1])
            body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]
            head[nid] = (int(p[3]), int(p[4]))
            alive.add(nid)
            nid += 1

    ours = our_side(path, rep)
    qid = {t: min(i for i in team if team[i] == t) for t in (0, 1)}

    rnd = 0
    last = {}
    last_round = {}
    cur = None
    src = {}
    eaten = collections.Counter()  # (who, window) -> count
    living_snap = {}  # round -> (our_living, their_living)
    mass_snap = {}  # round -> (our_mass, their_mass)
    longest_snap = {}  # round -> (our_longest, their_longest)
    h2h_deaths = []  # (round, id) head-on deaths in order
    queen_death = {t: None for t in (0, 1)}
    queen_cause = {t: None for t in (0, 1)}
    feeding_collapse = False

    LIVING_ROUNDS = (50, 100, 150, 300)
    MASS_ROUNDS = (100, 200, 300, 400, 450)

    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd in LIVING_ROUNDS:
                u = sum(1 for i in alive if team.get(i) == ours)
                t = sum(1 for i in alive if team.get(i) == 1 - ours)
                living_snap[rnd] = (u, t)
            if rnd in MASS_ROUNDS:
                um = sum(len(body[i]) for i in alive if team.get(i) == ours)
                tm = sum(len(body[i]) for i in alive if team.get(i) == 1 - ours)
                mass_snap[rnd] = (um, tm)
                lo = max((len(body[i]) for i in alive if team.get(i) == ours), default=0)
                lt = max((len(body[i]) for i in alive if team.get(i) == 1 - ours), default=0)
                longest_snap[rnd] = (lo, lt)
        elif k == "turnStart":
            cur = e["id"]
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            body[e["child"]] = [tuple(x) for x in e["childBody"]]
            body[e["parent"]] = [tuple(x) for x in e["parentBody"]]
            head[e["child"]] = tuple(e["childBody"][0])
            alive.add(e["child"])
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]
            hd = tuple(e["head"])
            if b[0] != hd:
                b.insert(0, hd)
            tl = tuple(e["tail"]) if e.get("tail") else None
            while len(b) > 1 and tl is not None and b[-1] != tl:
                b.pop()
        elif k == "dragonAction":
            last[e["id"]] = e
            last_round[e["id"]] = rnd
        elif k == "dragonDeath":
            i = e["id"]
            cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
            a = last.get(i, {})
            if cause == "no valid action" and (a.get("act") == "suicide" or (a.get("act") == "split" and a.get("size") == 1)):
                cause = "feed"
            if cause == "head to head":
                h2h_deaths.append((rnd, i))
            for t in (0, 1):
                if i == qid[t] and queen_death[t] is None:
                    queen_death[t] = rnd
                    queen_cause[t] = cause
            alive.discard(i)
            for j, c in enumerate(body.get(i, [])):
                if j % 2 == 0:
                    src[c] = "drop-ours" if team.get(i) == ours else "drop-theirs"
        elif k == "tileChange":
            c = tuple(e["tile"])
            if e.get("pearl"):
                src.setdefault(c, "spawn")
            else:
                s = src.pop(c, "spawn")
                eater = cur
                who = "ours" if team.get(eater) == ours else "theirs" if eater is not None else "?"
                if rnd <= 50:
                    w = "r0-50"
                elif rnd <= 100:
                    w = "r50-100"
                elif rnd <= 150:
                    w = "r100-150"
                else:
                    w = None
                if w:
                    eaten[(who, w)] += 1

    # Feeding collapse: our mass drops >= 50% in r340-r370
    u340 = None
    u370 = None
    for e in rep["events"]:
        if e["kind"] == "roundStart":
            r = e["round"]
            if r == 340:
                u340 = sum(len(body[i]) for i in alive if team.get(i) == ours)
            elif r == 370:
                u370 = sum(len(body[i]) for i in alive if team.get(i) == ours)
    if u340 is not None and u370 is not None and u340 > 0 and u370 <= u340 * 0.5:
        feeding_collapse = True

    # Numbers gap: first round r>=20 where their living count >= 1.5x ours (and >= ours+4, both >= 4)
    numbers_gap = None
    for e in rep["events"]:
        if e["kind"] == "roundStart":
            r = e["round"]
            if r < 20:
                continue
            u = sum(1 for i in alive if team.get(i) == ours)
            t = sum(1 for i in alive if team.get(i) == 1 - ours)
            if u >= 4 and t >= 4 and t >= 1.5 * u and t >= u + 4:
                numbers_gap = r
                break

    # THROWN WIN: their queen died before ours AND ours lived past r300 but died before r500
    thrown = False
    killer_info = None
    qo = queen_death[ours]
    qt = queen_death[1 - ours]
    if qt is not None and qo is not None and qt < qo and qo > 300 and qo < 500:
        thrown = True
        if queen_cause[ours] == "head to head":
            for j, (r, i) in enumerate(h2h_deaths):
                if r == qo and i == qid[ours]:
                    partner = None
                    if j + 1 < len(h2h_deaths) and h2h_deaths[j + 1][0] == qo:
                        partner = h2h_deaths[j + 1][1]
                    elif j > 0 and h2h_deaths[j - 1][0] == qo:
                        partner = h2h_deaths[j - 1][1]
                    if partner is not None:
                        mover = None
                        if last_round.get(partner) == qo:
                            mover = partner
                        elif last_round.get(qid[ours]) == qo:
                            mover = qid[ours]
                        if mover is not None:
                            a = last.get(mover, {})
                            d = (a.get("dirs") or " ")[0]
                            h = head.get(mover)
                            kd = edge(h[0], h[1], d) if d in DXY and h else None
                            killer_info = dict(id=mover, team=team.get(mover), portal=(kd == 2))

    qa = queen_analyse(path)

    return dict(
        path=str(path),
        name=pathlib.Path(path).name,
        won=qa["won"],
        how=qa["how"],
        ours=ours,
        qo=qo,
        qc=queen_cause[ours],
        qt=qt,
        qtc=queen_cause[1 - ours],
        thrown=thrown,
        killer=killer_info,
        eaten=eaten,
        living=living_snap,
        mass=mass_snap,
        longest=longest_snap,
        numbers_gap=numbers_gap,
        feeding_collapse=feeding_collapse,
    )


def loss_why(r):
    if r["thrown"]:
        return "THROWN WIN (queen)"
    if r["numbers_gap"] is not None and r["numbers_gap"] < 150:
        return "ECONOMY (numbers gap before r150)"
    if 300 in r["living"] and 300 in r["mass"]:
        u300, _ = r["living"][300]
        m300, _ = r["mass"][300]
        if u300 > 0:
            # ahead on living count or mass at r300 but lost
            their_u = r["living"][300][1] if 300 in r["living"] else 0
            their_m = r["mass"][300][1] if 300 in r["mass"] else 0
            if u300 >= their_u or m300 >= their_m:
                return "ENDGAME (ahead at r300 but lost)"
    return "OTHER"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    files = []
    for arg in sys.argv[1:]:
        if "*" in arg or "?" in arg:
            files.extend(sorted(globmod.glob(arg)))
        else:
            p = pathlib.Path(arg)
            if p.is_dir():
                files.extend(sorted(p.glob("*.replay")))
            else:
                files.append(arg)

    rows = [analyse(f) for f in files]

    for r in rows:
        print(f"=== {r['name']} ===")
        print(f"  result: {'WIN' if r['won'] else 'LOSS'} by {r['how']}")
        print(f"  queen: ours died r{r['qo']} ({r['qc']}), theirs died r{r['qt']} ({r['qtc']})")
        if r["thrown"]:
            k = r["killer"]
            if k:
                print(f"  THROWN WIN: our queen died r{r['qo']}, killer = dragon {k['id']} "
                      f"({'our' if k['team'] == r['ours'] else 'their'} team), "
                      f"{'PORTAL' if k['portal'] else 'open'} edge")
            else:
                print(f"  THROWN WIN: our queen died r{r['qo']} by {r['qc']}")
        for w in ("r0-50", "r50-100", "r100-150"):
            eo = r["eaten"].get(("ours", w), 0)
            et = r["eaten"].get(("theirs", w), 0)
            print(f"  eaten {w}: ours {eo}, theirs {et}")
        for rnd in (50, 100, 150, 300):
            if rnd in r["living"]:
                u, t = r["living"][rnd]
                print(f"  living r{rnd}: ours {u}, theirs {t}")
        if r["numbers_gap"] is not None:
            print(f"  NUMBERS GAP: r{r['numbers_gap']}")
        for rnd in (100, 200, 300, 400, 450):
            if rnd in r["mass"]:
                um, tm = r["mass"][rnd]
                lo, lt = r["longest"][rnd]
                print(f"  mass r{rnd}: ours {um}, theirs {tm}  longest: ours {lo}, theirs {lt}")
        if r["feeding_collapse"]:
            print(f"  FEEDING COLLAPSE: our mass dropped >= 50% in r340-r370")
        print()

    # Summary
    n = len(rows)
    thrown_rows = [r for r in rows if r["thrown"]]
    print(f"=== SUMMARY ({n} games) ===")
    print(f"thrown wins: {len(thrown_rows)}")
    for r in thrown_rows:
        k = r["killer"]
        if k:
            print(f"  {r['name']}: killer dragon {k['id']} "
                  f"({'our' if k['team'] == r['ours'] else 'their'} team), "
                  f"{'PORTAL' if k['portal'] else 'open'} edge")
        else:
            print(f"  {r['name']}: our queen died r{r['qo']} by {r['qc']}")
    for w in ("r0-50", "r50-100", "r100-150"):
        gaps = [r["eaten"].get(("theirs", w), 0) - r["eaten"].get(("ours", w), 0) for r in rows]
        print(f"median eaten gap {w}: {st.median(gaps) if gaps else 0:.1f}")
    ng = [r["numbers_gap"] for r in rows if r["numbers_gap"] is not None]
    print(f"numbers-gap rounds: {ng}")
    fc = sum(1 for r in rows if r["feeding_collapse"])
    print(f"feeding collapses: {fc}")
    print()
    print("=== LOSS ANALYSIS ===")
    for r in rows:
        if not r["won"]:
            print(f"  {r['name']}: {loss_why(r)}")


if __name__ == "__main__":
    main()
