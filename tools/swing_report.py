"""Where does a candidate actually differ from its base? Only ~1 in 5 paired games swings, so whole-panel medians hide
the effect. This reports on SWING games (paired outcome differs) and on STATE-CONDITIONED subsets, using the bot's own
intent (indicator tags) from tools/replay_cache.py.

    python tools/swing_report.py CAND_DIR BASE_DIR            # e.g. D:/battlecode/tmp/cycle/cand_stack2_* and base_viper_nn_*
    python tools/swing_report.py cand_stack2 base_viper_nn    # prefixes are resolved under D:/battlecode/tmp/cycle

Pairs games by relative path (s<seed>/<opp>/<map>_<side>_<seed>.replay). Sections:
 1. outcome matrix and swing list (map, side, seed, base->cand, end type, units at r100 both)
 2. state-conditioned: games where the BASE was dominant at r100 (>= 2:1 units): converted vs thrown, per build
 3. on swing games only: per-phase deltas (cand - base) of our units/mass at r100/200/300/400, our deaths by
    (cause, decision tag), our decision-tag mix, eats, feeds, sprints, splits
 4. first divergence round (our head positions differ) median over swing vs non-swing games
"""
import collections
import pathlib
import statistics as st
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay_cache import parsed  # noqa: E402

CYCLE = pathlib.Path("D:/battlecode/tmp/cycle")


def resolve(x):
    m = sorted(CYCLE.glob(x + "_*"))   # cycle replay dirs first (a bare name is also a source dir in the repo)
    if m: return m[-1]
    p = pathlib.Path(x)
    if p.exists() and any(p.rglob("*.replay")): return p
    sys.exit(f"no replay dir for {x}")


def pairs(cd, bd):
    c = {str(p.relative_to(cd)): p for p in cd.rglob("*.replay")}
    b = {str(p.relative_to(bd)): p for p in bd.rglob("*.replay")}
    return [(k, c[k], b[k]) for k in sorted(set(c) & set(b))]


def units(g, r, side=None):
    s = g["snaps"].get(r)
    if not s: return 0
    return s[g["ours"] if side is None else side][0]


def mass(g, r):
    s = g["snaps"].get(r)
    return s[g["ours"]][1] if s else 0


def dominant(g, r=100):
    s = g["snaps"].get(r)
    if not s: return False
    o, t = s[g["ours"]][0], s[1 - g["ours"]][0]
    return t > 0 and o >= 2 * t


def first_div(a, b):
    o = a["ours"]
    for r in sorted(set(a["heads"]) & set(b["heads"])):
        if a["heads"][r][o] != b["heads"][r][o]: return r
    return None


def ours(counter, g, keylen):
    """Sum a (team, phase, ...) counter for our team into {rest-of-key: n}."""
    out = collections.Counter()
    for k, v in counter.items():
        if k[0] == g["ours"]: out[k[1:keylen]] += v
    return out


def main():
    cd, bd = resolve(sys.argv[1]), resolve(sys.argv[2])
    P = pairs(cd, bd)
    G = [(k, parsed(c), parsed(b)) for k, c, b in P]
    print(f"{cd.name} vs {bd.name}: {len(G)} paired games; wins cand {sum(c['won'] for _, c, _ in G)} base {sum(b['won'] for _, _, b in G)}")
    mat = collections.Counter((b["won"], c["won"]) for _, c, b in G)
    print(f"  base W->cand W {mat[(True, True)]}, L->L {mat[(False, False)]}, base W->cand L {mat[(True, False)]}, base L->cand W {mat[(False, True)]}")
    swing = [(k, c, b) for k, c, b in G if c["won"] != b["won"]]
    print("\n1. SWING GAMES")
    for k, c, b in swing:
        print(f"  {'+' if c['won'] else '-'} {k:52s} base {'W' if b['won'] else 'L'}({b['end']}) cand {'W' if c['won'] else 'L'}({c['end']})"
              f"  units r100 b{units(b,100)}v{units(b,100,1-b['ours'])} c{units(c,100)}v{units(c,100,1-c['ours'])}"
              f"  r300 b{units(b,300)}v{units(b,300,1-b['ours'])} c{units(c,300)}v{units(c,300,1-c['ours'])}  diverge r{first_div(c, b)}")
    print("\n2. STATE-CONDITIONED (base dominant >= 2:1 units at r100)")
    dom = [(k, c, b) for k, c, b in G if dominant(b)]
    for tag, idx in (("base", 2), ("cand", 1)):
        rows = [x[idx] for x in dom]
        print(f"  {tag}: {len(rows)} games, won {sum(g['won'] for g in rows)} (elim {sum(g['won'] and g['end']=='elim' for g in rows)},"
              f" length {sum(g['won'] and g['end']=='length' for g in rows)}), thrown {sum(not g['won'] for g in rows)}")
    if swing:
        print("\n3. ON SWING GAMES (cand - base, summed over swing games; + = candidate more)")
        for r in (100, 200, 300, 400):
            du = [units(c, r) - units(b, r) for _, c, b in swing]; dm = [mass(c, r) - mass(b, r) for _, c, b in swing]
            print(f"  r{r}: our units delta median {st.median(du):+}, mass delta median {st.median(dm):+}")
        dd = collections.Counter(); dt = collections.Counter(); da = collections.Counter(); de = collections.Counter()
        for _, c, b in swing:
            for g, sgn in ((c, 1), (b, -1)):
                for k, v in ours(g["deaths"], g, 4).items(): dd[k] += sgn * v           # (phase, cause, tag)
                for k, v in ours(g["tags"], g, 3).items(): dt[k] += sgn * v             # (phase, category)
                for k, v in ours(g["acts"], g, 3).items(): da[k] += sgn * v             # (phase, kind)
                for k, v in g["eats"].items():
                    if k[0] == g["ours"]: de[(k[1],)] += sgn * v
        top = lambda c, n=10: ", ".join(f"{'/'.join(map(str, k))} {v:+d}" for k, v in sorted(c.items(), key=lambda kv: -abs(kv[1]))[:n] if v)
        print(f"  our deaths (phase/cause/last tag): {top(dd, 12)}")
        print(f"  our decision tags (phase/category, turns): {top(dt, 12)}")
        print(f"  our actions (phase/kind): {top(da, 10)}")
        print(f"  our pearls eaten by phase: {top(de, 6)}")
    divs = lambda S: [d for d in (first_div(c, b) for _, c, b in S) if d is not None]
    sw = divs(swing); ns = divs([x for x in G if x not in swing])
    if sw and ns:
        print(f"\n4. FIRST DIVERGENCE (our head positions): swing median r{st.median(sw)}, non-swing median r{st.median(ns)}")


if __name__ == "__main__":
    main()
