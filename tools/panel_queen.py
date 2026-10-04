"""Queen stats for panel_zig replay dirs: win rate, our queen death round/cause, enemy queen death.
    uv run --python 3.11 --with unswbc python tools/panel_queen.py out/u7_qf out/u7_qg   (UNSWBC_KEY not needed)
Replay names: <map>_<seed>_<A|B>.replay (A/B = the side OUR bot plays)."""
import os, sys, glob, statistics as st, collections
os.environ.setdefault("UNSWBC_KEY", "x")
sys.path.insert(0, os.path.dirname(__file__))
from analyze_ours import analyse
for d in sys.argv[1:]:
    rows = []
    for p in sorted(glob.glob(os.path.join(d, "*.replay"))):
        side = os.path.basename(p).rsplit("_", 1)[1][0].lower()
        try:
            r = analyse(p, side)
        except Exception as ex:
            print("skip", p, ex); continue
        r["map"] = os.path.basename(p).rsplit("_", 2)[0]; r["win"] = r["winner"] == r["me"]; rows.append(r)
    n = len(rows); qd = [r["our_queen_death"] for r in rows if r["our_queen_death"]]
    eq = [r["enemy_queen_death"] for r in rows if r["enemy_queen_death"]]
    print(f"{d}: games {n} win {sum(r['win'] for r in rows)} ({100*sum(r['win'] for r in rows)/max(1,n):.1f}%) | our queen died {len(qd)}/{n} median r {st.median([x[0] for x in qd]) if qd else '-'} causes {dict(collections.Counter(x[1] for x in qd))} | enemy queen died {len(eq)}/{n}")
    bm = collections.defaultdict(list)
    for r in rows: bm[r["map"]].append(r)
    for m, s in sorted(bm.items()):
        q = [r["our_queen_death"][0] for r in s if r["our_queen_death"]]
        print(f"   {m}: W {sum(r['win'] for r in s)}/{len(s)}  queen died {len(q)}/{len(s)} median r {int(st.median(q)) if q else '-'}")
