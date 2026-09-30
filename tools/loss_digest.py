"""Loss digest: what kind of loss, when the gap opened, what happened to our longest dragon. Works on ladder replays
(our side = the side whose bot field is set) and on sandbox replays from `tourney.py --replays DIR` (our side is in the
file name: <map>_<A|B>_<seed>.replay).

    python tools/loss_digest.py DIR_OR_GLOB [--all] [--sub 11461] [--n 80]
    python tools/loss_digest.py --pair BASE_DIR CAND_DIR          # same seeds: games whose result differs, and where

Loss types: ELIM (we were wiped out), LEN+MASS (lost the longest-dragon tiebreak with >= total mass: consolidation),
LEN-MASS (lost on length with less mass: economy), plus WIN types when --all.
Per game: checkpoints every 50 rounds (units/mass/longest ours v theirs), the round the mass gap opened for good,
units at r100, our longest-at-r350/r400 fate, how many dragons held our "longest" after r300, feeds after r300.
"""
import argparse
import collections
import glob
import pathlib
import re
import statistics as st
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402


def our_side(path, rep):
    m = re.search(r"_([AB])_\d+\.replay$", str(path))
    if m: return 0 if m.group(1) == "A" else 1
    a, b = rep.get("botA"), rep.get("botB")
    return 0 if a and not b else 1 if b and not a else None


def digest(path, sub=None):
    rep = _decode(str(path))
    ours = our_side(path, rep)
    if ours is None: return None
    if sub and not re.search(r"_[AB]_\d+\.replay$", str(path)) and str(rep["botA"] if ours == 0 else rep["botB"]) != str(sub):
        return None
    res = rep.get("result", {})
    lines = rep["map"].splitlines()
    name = next((l.split(" ", 1)[1] for l in lines if l.startswith("MAP_NAME")), pathlib.Path(path).stem.split("_")[0])
    team, body = {}, {}
    nid = 0
    for l in lines:
        p = l.split()
        if p and p[0] == "DRAGON":
            n = int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = int(p[1]); body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    alive = set(team); rnd = 0
    snaps, holders, fate, watch = {}, [], {}, {}
    feeds_late = 0; deaths = collections.Counter()
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            ls = {i: len(body[i]) for i in alive}
            o = [i for i in alive if team[i] == ours]; t = [i for i in alive if team[i] != ours]
            if rnd % 25 == 0 or rnd == 499:
                snaps[rnd] = (len(o), sum(ls[i] for i in o), max((ls[i] for i in o), default=0),
                              len(t), sum(ls[i] for i in t), max((ls[i] for i in t), default=0))
            if rnd >= 300 and o:
                top = max(o, key=lambda i: (ls[i], -i))
                if not holders or holders[-1] != top: holders.append(top)
                if rnd in (350, 400): watch[rnd] = top
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]; hd = tuple(e["head"])
            if b[0] != hd: b.insert(0, hd)
            tl = tuple(e["tail"]) if e.get("tail") else None
            while len(b) > 1 and tl is not None and b[-1] != tl: b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]; body[e["child"]] = [tuple(c) for c in e["childBody"]]
            body[e["parent"]] = [tuple(c) for c in e["parentBody"]]; alive.add(e["child"])
        elif k == "dragonDeath":
            i = e["id"]; alive.discard(i)
            cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
            fate[i] = cause
            if team.get(i) == ours:
                deaths[(cause, "r0-100" if rnd < 100 else "r100-300" if rnd < 300 else "r300+")] += 1
                if rnd >= 300 and cause == "no valid action": feeds_late += 1
    won = res.get("winner") == ours
    last = snaps[max(snaps)] if snaps else (0,) * 6
    elim = res.get("endReason") != 1
    if won: kind = "WIN-ELIM" if elim else "WIN-LEN"
    elif elim: kind = "ELIM"
    else: kind = "LEN+MASS" if last[1] >= last[4] else "LEN-MASS"
    gap = None   # first checkpoint from which our mass stays below theirs to the end
    ks = sorted(snaps)
    for j, r in enumerate(ks):
        if all(snaps[x][1] < snaps[x][4] for x in ks[j:]): gap = r; break
    alive_end = set(i for i in alive if team[i] == ours)
    fates = {cp: ("alive" if i in alive_end else fate.get(i, "?")) for cp, i in watch.items()}
    return dict(path=str(path), map=name, kind=kind, won=won, snaps=snaps, gap=gap, holders=len(set(holders)),
                fates=fates, feeds=feeds_late, deaths=deaths, u100=snaps.get(100, (0,) * 6))


def show(d):
    s = d["snaps"]
    cps = "  ".join(f"r{r}: {v[0]}/{v[1]}/L{v[2]} v {v[3]}/{v[4]}/L{v[5]}" for r, v in sorted(s.items()) if r % 100 == 0 or r == 499)
    return (f"{pathlib.Path(d['path']).name:28s} {d['map'][:14]:14s} {d['kind']:9s} gap@{d['gap']}  holders {d['holders']}"
            f"  feeds300+ {d['feeds']}  longest fate {d['fates']}\n      {cps}")


def aggregate(ds):
    print("\nby map (games, loss types):")
    bym = collections.defaultdict(collections.Counter)
    for d in ds: bym[d["map"]][d["kind"]] += 1
    for m, c in sorted(bym.items()): print(f"  {m[:16]:16s} {sum(c.values()):3d}  {dict(c)}")
    losses = [d for d in ds if not d["won"]]
    if not losses: return
    print(f"\nlosses {len(losses)}: types {dict(collections.Counter(d['kind'] for d in losses))}")
    gaps = [d["gap"] for d in losses if d["gap"] is not None]
    if gaps: print(f"  mass gap opened (median round) {st.median(gaps)}; never behind on mass in {len(losses) - len(gaps)}")
    print(f"  units at r100 ours v theirs (median) {st.median(d['u100'][0] for d in losses)} v {st.median(d['u100'][3] for d in losses)}")
    print(f"  holders of our longest after r300 (median) {st.median(d['holders'] for d in losses)}; feeds r300+ {st.median(d['feeds'] for d in losses)}")
    for cp in (350, 400):
        print(f"  our r{cp}-longest fate: {dict(collections.Counter(d['fates'].get(cp, '-') for d in losses))}")
    dc = collections.Counter()
    for d in losses: dc.update(d["deaths"])
    print("  our deaths per lost game (top):", ", ".join(f"{c}@{p} {n / len(losses):.0f}" for (c, p), n in dc.most_common(6)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default="ladder/losses/*/*.replay")
    ap.add_argument("--all", action="store_true", help="also list wins")
    ap.add_argument("--sub", default="", help="ladder replays: only this submission's games")
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--pair", nargs=2, metavar=("BASE_DIR", "CAND_DIR"))
    a = ap.parse_args()
    if a.pair:
        base, cand = (pathlib.Path(x) for x in a.pair)
        both = sorted(set(p.name for p in base.glob("*.replay")) & set(p.name for p in cand.glob("*.replay")))
        bw = cw = 0; diffs = []
        for n in both:
            db, dc = digest(base / n), digest(cand / n)
            bw += db["won"]; cw += dc["won"]
            if db["won"] != dc["won"]: diffs.append((db, dc))
        print(f"{len(both)} paired games: base {bw} wins, cand {cw} wins; {len(diffs)} differ\n")
        for db, dc in diffs:
            div = next((r for r in sorted(db["snaps"]) if r in dc["snaps"] and db["snaps"][r][:3] != dc["snaps"][r][:3]), None)
            print(f"== {pathlib.Path(db['path']).name}: base {db['kind']}, cand {dc['kind']} (our stats first differ at r{div})")
            print("  base " + show(db)); print("  cand " + show(dc))
        return
    p = pathlib.Path(a.src)
    files = sorted(p.glob("*.replay")) if p.is_dir() else sorted(glob.glob(a.src), key=lambda f: pathlib.Path(f).stat().st_mtime, reverse=True)
    ds = []
    for f in files:
        try:
            d = digest(f, a.sub or None)
        except Exception as ex:   # noqa: BLE001
            print("skip", f, ex); continue
        if d and (a.all or not d["won"]): ds.append(d)
        if len(ds) >= a.n: break
    for d in ds: print(show(d))
    aggregate(ds)


if __name__ == "__main__":
    main()
