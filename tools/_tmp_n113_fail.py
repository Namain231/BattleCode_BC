"""N1.13 live 10: Autarky / Schooltime / Default snaps, econ, EXPAND/FEED/ECHO-ATK."""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import load, DEATHS
from early_game import early
from loss_report import analyse, classify

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "replays" / "n113_live"


def our_side(fn):
    return 0 if "_as_A-" in fn.name else 1


def econ(path, us, until):
    c = early(str(path), us, until)
    dt = max(c["dragon_turns"], 1)
    return (f"eats {c['eats']:4d} ({c['eats']/dt:.3f}/dt) spl {c['splits']:3d} dth {c['deaths']:3d} "
            f"u {c['units_end']:2d}")


def tags(path, us):
    rep = load(str(path))
    team, nid = {}, 0
    for line in rep["map"].splitlines():
        p = line.split()
        if p and p[0] == "DRAGON":
            team[nid] = int(p[1])
            nid += 1
    last = {}
    rnd = 0
    ctr = collections.Counter()
    expands = []
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
        elif k == "dragonIndicator":
            last[e["id"]] = e["text"]
            tag = (e["text"].split() or ["?"])[0]
            if team.get(e["id"]) == us:
                ctr[tag] += 1
                if tag == "EXPAND" and rnd <= 40:
                    expands.append((rnd, e["id"], e["text"]))
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
    return ctr, expands, rep.get("result")


def dump(glob_pat, title):
    print(f"\n======== {title} ========")
    for fn in sorted(LIVE.glob(glob_pat)):
        us = our_side(fn)
        print(f"\n {fn.name} us {'AB'[us]}")
        _, snaps, deaths, last = analyse(str(fn), us)
        print(" classify", classify(snaps, last), "last", last)
        for k, (a, b) in snaps.items():
            print(f"  {k}: us {a} them {b}")
        print(" r0-50 ", econ(fn, us, 50), "| them", econ(fn, 1 - us, 50))
        print(" r0-100", econ(fn, us, 100), "| them", econ(fn, 1 - us, 100))
        print(" r0-200", econ(fn, us, 200), "| them", econ(fn, 1 - us, 200))
        print(" deaths", {p: dict(v) for p, v in deaths.items() if v})
        ctr, expands, res = tags(fn, us)
        print(" result", res)
        print(" our tags", {k: ctr[k] for k in ("EXPAND", "BUD", "ATK", "ECHO-ATK", "FEED", "DOOMED", "ESCAPE-SPLIT") if ctr[k]})
        if expands:
            print(" early EXPAND", expands[:8])


dump("*autarky*.replay", "AUTARKY")
dump("*schooltime*.replay", "SCHOOLTIME")
dump("*default*.replay", "DEFAULT")
