"""Deliberate feeds per game (a 'no valid action' death right after a SPLIT 1 or a 'suicide' action), from --from,
for our side (or --opponent), plus final longest and final mass. Works on ladder or sandbox (<map>_<A|B>_<seed>) replays.

    python tools/feed_count.py DIR_OR_GLOB [--from 350] [--opponent]
"""
import argparse, glob, pathlib, re, statistics as st, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402

def one(path, r0, flip):
    rep = _decode(str(path)); m = re.search(r"_([AB])_\d+\.replay$", str(path))
    ours = (0 if m.group(1) == "A" else 1) if m else (0 if rep["botA"] and not rep["botB"] else 1)
    if flip: ours = 1 - ours
    team = {}; nid = 0
    for l in rep["map"].splitlines():
        q = l.split()
        if q and q[0] == "DRAGON": team[nid] = int(q[1]); nid += 1
    last = {}; rnd = 0; feeds = 0
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart": rnd = e["round"]
        elif k == "dragonSplit": team[e["child"]] = e["team"]
        elif k == "dragonAction": last[e["id"]] = e
        elif k == "dragonDeath" and rnd >= r0 and team.get(e["id"]) == ours:
            cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
            a = last.get(e["id"], {})
            if cause == "no valid action" and (a.get("act") == "suicide" or (a.get("act") == "split" and a.get("size") == 1)): feeds += 1
    res = rep["result"]; me = res["A"] if ours == 0 else res["B"]
    return feeds, me.get("longest", 0), me.get("total", 0), res.get("winner") == ours

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("--from", dest="r0", type=int, default=350)
    ap.add_argument("--opponent", action="store_true"); a = ap.parse_args(); p = pathlib.Path(a.src)
    files = sorted(p.glob("*.replay")) if p.is_dir() else sorted(glob.glob(a.src))
    rs = [one(f, a.r0, a.opponent) for f in files]
    print(f"{len(rs)} games: deliberate feeds/game {st.mean(r[0] for r in rs):.1f}, final longest median {st.median(r[1] for r in rs)},"
          f" final mass median {st.median(r[2] for r in rs)}, wins {sum(r[3] for r in rs)}")

if __name__ == "__main__":
    main()
