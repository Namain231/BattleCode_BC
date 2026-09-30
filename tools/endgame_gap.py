"""Why do we lose on length with more mass? Champion games lost at r500 on the longest-dragon tiebreak.

    python tools/endgame_gap.py [--sub 11461] [--glob "ladder/losses/*/*.replay"] [--n 60]

Per game: from r300 every 25 rounds our units / mass / longest vs theirs; how many different dragons held our
"longest" title after r300 (sink churn); how our r300/r350/r400 longest dragons ended (alive at end / fed = no valid
action / head-on / crash); and our feed deaths after r300: pearls dropped vs pearls eaten by our final longest.
"""
import argparse
import collections
import glob
import pathlib
import statistics as st
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402


def analyse(path, sub):
    rep = _decode(path)
    ours = 0 if rep["botA"] and not rep["botB"] else 1 if rep["botB"] and not rep["botA"] else None
    if ours is None: return None
    if sub and str(rep["botA"] if ours == 0 else rep["botB"]) != str(sub): return None
    res = rep.get("result", {})
    if res.get("endReason") != 1 or res.get("winner") == ours: return None
    A, B = res.get("A", {}), res.get("B", {})
    me, th = (A, B) if ours == 0 else (B, A)
    lines = rep["map"].splitlines()
    name = next((l.split(" ", 1)[1] for l in lines if l.startswith("MAP_NAME")), "?")
    team, body = {}, {}
    nid = 0
    for l in lines:
        p = l.split()
        if p and p[0] == "DRAGON":
            n = int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = int(p[1]); body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    alive = set(team); rnd = 0
    snaps = {}; holders = []; fate = {}; feeds = []   # feeds: (round, len, cell)
    watch = {}   # checkpoint -> id of our longest then
    pearls_eaten_by = collections.Counter()
    pearl_cells = set()
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd >= 300:
                ls = {i: len(body[i]) for i in alive}
                o = [i for i in alive if team[i] == ours]; t = [i for i in alive if team[i] != ours]
                if o:
                    top = max(o, key=lambda i: ls[i])
                    if not holders or holders[-1] != top: holders.append(top)
                    if rnd in (300, 350, 400, 450) and rnd not in watch: watch[rnd] = top
                if rnd % 25 == 0:
                    snaps[rnd] = (len(o), sum(ls[i] for i in o), max((ls[i] for i in o), default=0),
                                  len(t), sum(ls[i] for i in t), max((ls[i] for i in t), default=0))
        elif k == "tileChange":
            c = tuple(e["tile"]); (pearl_cells.add if e.get("pearl") else pearl_cells.discard)(c)
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]; hd = tuple(e["head"])
            if b[0] != hd: b.insert(0, hd)
            if hd in pearl_cells and rnd >= 300 and team.get(e["id"]) == ours: pearls_eaten_by[e["id"]] += 1
            tl = tuple(e["tail"]) if e.get("tail") else None
            while len(b) > 1 and tl is not None and b[-1] != tl: b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]; body[e["child"]] = [tuple(c) for c in e["childBody"]]
            body[e["parent"]] = [tuple(c) for c in e["parentBody"]]; alive.add(e["child"])
        elif k == "dragonDeath":
            i = e["id"]; alive.discard(i)
            cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
            fate[i] = (rnd, cause, len(body.get(i) or []))
            if team.get(i) == ours and rnd >= 300 and cause == "no valid action":
                feeds.append((rnd, len(body.get(i) or [])))
    final_o = [i for i in alive if team[i] == ours]
    final_top = max(final_o, key=lambda i: len(body[i])) if final_o else None
    dropped = sum((L + 1) // 2 for _, L in feeds)
    return dict(name=name, me=me, th=th, snaps=snaps, churn=len(set(holders)), watch=watch, fate=fate,
                alive_end=set(final_o), feeds=len(feeds), dropped=dropped,
                eaten_top=pearls_eaten_by.get(final_top, 0), eaten_all=sum(pearls_eaten_by.values()),
                eaten_holders=sum(pearls_eaten_by[i] for i in set(holders)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default="11461"); ap.add_argument("--glob", default="ladder/losses/*/*.replay")
    ap.add_argument("--n", type=int, default=60)
    a = ap.parse_args()
    files = sorted(glob.glob(a.glob), key=lambda f: pathlib.Path(f).stat().st_mtime, reverse=True)
    rows = []
    for f in files:
        try:
            r = analyse(f, a.sub)
        except Exception as ex:   # noqa: BLE001
            print("skip", f, ex); continue
        if r and r["me"].get("total", 0) >= r["th"].get("total", 0): rows.append((f, r))
        if len(rows) >= a.n: break
    print(f"{len(rows)} games lost on length WITH >= total mass (sub {a.sub})\n")
    for f, r in rows:
        print(f"{pathlib.Path(f).stem} {r['name'][:14]:14s} end ours {r['me'].get('count')}/{r['me'].get('total')}/"
              f"L{r['me'].get('longest')} theirs {r['th'].get('count')}/{r['th'].get('total')}/L{r['th'].get('longest')}"
              f"  holders {r['churn']}  feeds {r['feeds']} drop {r['dropped']} eaten: top {r['eaten_top']} all {r['eaten_all']}")
        print("    " + "  ".join(f"r{k}: {v[0]}/{v[1]}/L{v[2]} v {v[3]}/{v[4]}/L{v[5]}" for k, v in sorted(r["snaps"].items()) if k % 50 == 0))
    # aggregates
    print("\nlongest-at-checkpoint fate (our dragon that was longest at rN):")
    for cp in (300, 350, 400, 450):
        c = collections.Counter()
        for _, r in rows:
            i = r["watch"].get(cp)
            if i is None: continue
            c["alive at end" if i in r["alive_end"] else r["fate"].get(i, (0, "?"))[1]] += 1
        print(f"  r{cp}: {dict(c)}")
    if rows:
        print(f"\nmedian: holders after r300 {st.median(r['churn'] for _, r in rows)}, feeds r300+ "
              f"{st.median(r['feeds'] for _, r in rows)}, pearls dropped {st.median(r['dropped'] for _, r in rows)}, "
              f"eaten by final longest {st.median(r['eaten_top'] for _, r in rows)}, by all ours {st.median(r['eaten_all'] for _, r in rows)}")
        for cp in (300, 400, 450):
            g = [(r['snaps'][cp][2], r['snaps'][cp][5], r['snaps'][cp][0], r['snaps'][cp][3]) for _, r in rows if cp in r['snaps']]
            if g: print(f"  r{cp}: our longest {st.median(x[0] for x in g)} vs {st.median(x[1] for x in g)}; units {st.median(x[2] for x in g)} vs {st.median(x[3] for x in g)}")
        print("  maps:", collections.Counter(r['name'] for _, r in rows).most_common())


if __name__ == "__main__":
    main()
