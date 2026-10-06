import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import load, DEATHS
from early_game import early
from loss_report import analyse, classify
from ladder_report import analyse as ladder

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "replays" / "n110_live"


def our_side(fn):
    return 0 if "_as_A-" in fn.name else 1


def econ(path, us, until):
    c = early(str(path), us, until)
    dt = max(c["dragon_turns"], 1)
    h2h = c.get("death_lost a head-to-head", 0)
    return (f"eats {c['eats']:4d} ({c['eats']/dt:.3f}/dt) spl {c['splits']:3d} dth {c['deaths']:3d} "
            f"u {c['units_end']:2d} h2h={h2h} wall={c.get('death_hit a wall',0)} self={c.get('death_hit itself',0)}")


def autarky_open(path, us, until=80):
    rep = load(str(path))
    team, body, nid = {}, {}, 0
    for line in rep["map"].splitlines():
        p = line.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3 : 3 + 2 * n]]
            team[nid] = t
            body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]
            nid += 1
    last_ind = {}
    rnd = 0
    print("  spawn our L14-ish:", [(i, team[i], len(body[i]), body[i][0], body[i][-1]) for i in team if team[i] == us and len(body[i]) >= 8])
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd > until:
                break
        elif k == "dragonIndicator":
            last_ind[e["id"]] = (rnd, e["text"])
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]
            if b[0] != e["head"]:
                b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]:
                b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            body[e["child"]] = e["childBody"]
            body[e["parent"]] = e["parentBody"]
            if e["team"] == us and rnd <= until:
                pbody, cbody = e["parentBody"], e["childBody"]
                ph, pt = pbody[0], pbody[-1]
                ch, ct = cbody[0], cbody[-1]
                tag = last_ind.get(e["parent"], (rnd, "?"))[1]
                print(f"  r{rnd:3d} SPLIT p={e['parent']}->{len(pbody)} child={e['child']}->{len(cbody)}  "
                      f"pHead={ph} pTail={pt} cHead={ch} cTail={ct}  ind={tag[:70]}")
        elif k == "dragonDeath":
            i = e["id"]
            if team.get(i) == us and rnd <= until:
                why = DEATHS[e["reason"]] if e["reason"] < 5 else str(e["reason"])
                ln = len(body.get(i, []))
                tag = last_ind.get(i, (rnd, ""))[1][:80]
                print(f"  r{rnd:3d} DIE #{i} L{ln} {why:16s} {tag}")


def qos_h2h(path, us):
    rep = load(str(path))
    team, body, nid = {}, {}, 0
    for line in rep["map"].splitlines():
        p = line.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3 : 3 + 2 * n]]
            team[nid] = t
            body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]
            nid += 1
    last_ind = {}
    last_act = {}
    rnd = 0
    # h2h: (rnd, dead_side, dead_id, dead_len, dead_tag, killer_guess)
    h2h = []
    atk_fire = collections.Counter()
    atk_then_die = 0
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
        elif k == "dragonIndicator":
            last_ind[e["id"]] = e["text"]
            tag = (e["text"].split() or ["?"])[0]
            if tag == "ATK" and team.get(e["id"]) == us:
                atk_fire["us"] += 1
            if tag == "ATK" and team.get(e["id"]) == 1 - us:
                atk_fire["them"] += 1
        elif k == "dragonAction":
            last_act[e["id"]] = (rnd, e.get("act"), e.get("dirs"))
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]
            if b[0] != e["head"]:
                b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]:
                b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            body[e["child"]] = e["childBody"]
            body[e["parent"]] = e["parentBody"]
        elif k == "dragonDeath":
            i = e["id"]
            why = DEATHS[e["reason"]] if e["reason"] < 5 else str(e["reason"])
            if why == "lost a head-to-head" and team.get(i) in (0, 1):
                tag = last_ind.get(i, "")
                ln = len(body.get(i, []))
                h2h.append((rnd, team[i], i, ln, tag[:50]))
                if team[i] == us and tag.startswith("ATK"):
                    atk_then_die += 1
            body.pop(i, None)
    return h2h, atk_fire, atk_then_die


print("======== AUTARKY ========")
for fn in sorted(LIVE.glob("*autarky*.replay")):
    us = our_side(fn)
    print("\n", fn.name, "us", "AB"[us])
    rep = load(str(fn))
    print(" result", rep.get("result"))
    _, snaps, deaths, last = analyse(str(fn), us)
    print(" classify", classify(snaps, last), "last", last)
    for k, (a, b) in snaps.items():
        print(f"  {k}: us {a} them {b}")
    print(" r0-50 ", econ(fn, us, 50), "|", econ(fn, 1 - us, 50))
    print(" r0-100", econ(fn, us, 100), "|", econ(fn, 1 - us, 100))
    print(" deaths", {p: dict(v) for p, v in deaths.items() if v})
    autarky_open(fn, us, 60)

print("\n======== QUEEN OF SPADES ========")
for fn in sorted(LIVE.glob("*queen_of_spades*.replay")):
    us = our_side(fn)
    print("\n", fn.name, "us", "AB"[us])
    rep = load(str(fn))
    print(" result", rep.get("result"))
    _, snaps, deaths, last = analyse(str(fn), us)
    print(" classify", classify(snaps, last), "last", last)
    for k, (a, b) in snaps.items():
        print(f"  {k}: us {a} them {b}")
    print(" r0-50 ", econ(fn, us, 50), "| THEM", econ(fn, 1 - us, 50))
    print(" r0-100", econ(fn, us, 100), "| THEM", econ(fn, 1 - us, 100))
    print(" r0-200", econ(fn, us, 200), "| THEM", econ(fn, 1 - us, 200))
    print(" deaths", {p: dict(v) for p, v in deaths.items() if v})
    h2h, atk, atk_die = qos_h2h(fn, us)
    us_h = [x for x in h2h if x[1] == us]
    th_h = [x for x in h2h if x[1] == 1 - us]
    print(f"  H2H count us {len(us_h)} them {len(th_h)}  ATK-fires us {atk['us']} them {atk['them']}  our ATK then we died {atk_die}")

    def bucket(rows):
        b = collections.Counter()
        for r, side, i, ln, tag in rows:
            ph = "0-50" if r < 50 else "50-100" if r < 100 else "100-200" if r < 200 else "200-350" if r < 350 else "350+"
            t0 = (tag.split() or ["?"])[0]
            b[f"{ph} L{ln} {t0}"] += 1
        return b.most_common(8)

    print("  our h2h", bucket(us_h))
    print("  their h2h", bucket(th_h))
    print("  first 8 our h2h", us_h[:8])
    print("  first 8 their h2h", th_h[:8])

print("\n======== TRAUMA ========")
for fn in sorted(LIVE.glob("*trauma*.replay")):
    us = our_side(fn)
    print("\n", fn.name, "us", "AB"[us])
    rep = load(str(fn))
    print(" result", rep.get("result"))
    _, snaps, deaths, last = analyse(str(fn), us)
    print(" classify", classify(snaps, last), "last", last)
    for k, (a, b) in snaps.items():
        print(f"  {k}: us {a} them {b}")
