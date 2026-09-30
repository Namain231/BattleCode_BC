"""How do top teams grow their longest dragon on a map type? Profiles the winning side of sampled top-team replays.

    python tools/giant_profile.py --maps Portals,Slithery Fight,Schooltime --rank-max 5 --n 60
Per game: units/longest/total at checkpoints, deliberate feeds ("no valid action" deaths) per phase, round the longest
first reaches 20/30/40, and whether the longest at r400 is still alive at the end. One replay at a time (low memory).
"""
import argparse, collections, json, pathlib, random, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402
ROOT = pathlib.Path(__file__).resolve().parents[1]
CK = (100, 200, 300, 350, 400, 450, 499)


def profile(path, team):
    rep = _decode(path)
    lines = rep["map"].splitlines()
    tm, body, nid = {}, {}, 0
    for l in lines:
        p = l.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            tm[nid] = t; body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    alive = set(tm); rnd = 0; snaps = {}; feeds = collections.Counter(); reach = {}; long400 = None
    def snap():
        ls = [len(body[i]) for i in alive if tm[i] == team]
        return (len(ls), max(ls) if ls else 0, sum(ls))
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd in CK: snaps[rnd] = snap()
            if rnd == 400:
                cand = [i for i in alive if tm[i] == team]
                long400 = max(cand, key=lambda i: len(body[i])) if cand else None
            L = snap()[1]
            for th in (20, 30, 40):
                if L >= th and th not in reach: reach[th] = rnd
        elif k == "dragonUpdate":
            i = e["id"]; b = body.get(i)
            if b is None or e["head"] is None: continue
            if b[0] != e["head"]: b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]: b.pop()
        elif k == "dragonSplit":
            tm[e["child"]] = e["team"]; body[e["child"]] = e["childBody"]; body[e["parent"]] = e["parentBody"]; alive.add(e["child"])
        elif k == "dragonDeath":
            i = e["id"]; alive.discard(i)
            if tm.get(i) == team and e["reason"] < 5 and DEATHS[e["reason"]] == "no valid action":
                feeds["r0-300" if rnd < 300 else "r300-400" if rnd < 400 else "r400+"] += 1
    snaps["end"] = snap()
    return snaps, feeds, reach, (long400 in alive) if long400 is not None else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default="Portals,Slithery Fight,Schooltime")
    ap.add_argument("--rank-max", type=int, default=5); ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--ours", action="store_true", help="profile OUR side in ladder/attrib + ladder/losses replays")
    a = ap.parse_args()
    maps = set(a.maps.split(","))
    if a.ours:
        import glob
        rows = []
        for f in sorted(glob.glob(str(ROOT / "ladder" / "attrib" / "*.replay")) + glob.glob(str(ROOT / "ladder" / "losses" / "*" / "*.replay"))):
            try:
                rep = _decode(f)
            except Exception:
                continue
            name = next((l.split(" ", 1)[1] for l in rep["map"].splitlines() if l.startswith("MAP_NAME")), "")
            if name not in maps: continue
            side = "A" if rep["botA"] and not rep["botB"] else "B" if rep["botB"] and not rep["botA"] else None
            if side is None: continue
            win = rep.get("result", {}).get("winner")
            rows.append({"team": "us(" + ("W" if win == (0 if side == "A" else 1) else "L") + ")", "map": name, "side": side,
                         "winner": side, "path": str(pathlib.Path(f).relative_to(ROOT))})
            if len(rows) >= 3 * a.n: break
    else:
        idx = json.load(open(ROOT / "ladder" / "slope" / "index.json", encoding="utf-8"))
        rows = [r for r in idx if r["map"] in maps and r["rank"] <= a.rank_max and r["winner"] == r["side"]
                and (ROOT / r["path"].replace("\\", "/")).exists()]
    random.Random(a.seed).shuffle(rows)
    agg = collections.defaultdict(list); fe = collections.Counter(); rc = collections.defaultdict(list); surv = []
    for r in rows[:a.n]:
        try:
            s, f, reach, sv = profile(str(ROOT / r["path"].replace("\\", "/")), 0 if r["side"] == "A" else 1)
        except Exception as ex:
            print("skip", r["path"], ex); continue
        for k, v in s.items(): agg[k].append(v)
        fe.update(f)
        for th in (20, 30, 40): rc[th].append(reach.get(th, 999))
        if sv is not None: surv.append(sv)
        print(f"{r['team'][:12]:12s} {r['map'][:10]:10s} " + " ".join(f"{k}:{v[0]}/{v[1]}/{v[2]}" for k, v in s.items())
              + f"  feeds {dict(f)}  L20@{reach.get(20, '-')} L30@{reach.get(30, '-')} L40@{reach.get(40, '-')}")
    n = len(agg["end"])
    print(f"\nAGGREGATE over {n} winning top-team games on {sorted(maps)} (median units/longest/total):")
    for k in list(CK) + ["end"]:
        v = agg[k]
        if v:
            med = lambda j: sorted(x[j] for x in v)[len(v) // 2]
            print(f"  {k}: {med(0)}/{med(1)}/{med(2)}")
    print(f"  feeds per game: " + ", ".join(f"{k} {fe[k] / max(1, n):.1f}" for k in ("r0-300", "r300-400", "r400+")))
    for th in (20, 30, 40):
        v = sorted(rc[th]); print(f"  median round longest reaches {th}: {v[len(v) // 2] if v else '-'}")
    if surv: print(f"  longest-at-r400 alive at end: {sum(surv)}/{len(surv)}")


if __name__ == "__main__":
    main()
