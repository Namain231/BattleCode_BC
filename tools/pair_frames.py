"""Side-by-side frames of two paired replays (same map/seed/side) around the moment they diverge, with each of our
dragons' decision tag (indicator) so you can see WHY the builds moved differently.

    python tools/pair_frames.py BASE.replay CAND.replay [--round R] [--frames 3] [--step 2] [--radius 6]

Without --round it finds the first round where our head positions differ and centres on the first differing head.
Prints the base frame and the candidate frame next to each other (same window), then each build's tags for our dragons
in the window (id, length, tag), and the dragons whose tag differs between the builds.
"""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from viz import Game  # noqa: E402


def states(g, want):
    out = {}
    for rnd, st in g.play():
        if rnd in want: out[rnd] = st
        if rnd > max(want): break
    return out


def heads(g, st):
    return {i: tuple(b[0]) for i, b in st["body"].items() if b and st["team"][i] == g.ours}


def first_divergence(gb, gc, to=500):
    pb, pc = gb.play(), gc.play()
    for (rb, sb), (rc, sc) in zip(pb, pc):
        if rb > to: break
        hb, hc = heads(gb, sb), heads(gc, sc)
        if set(hb.values()) != set(hc.values()):
            diff = sorted(set(hb.values()) ^ set(hc.values()))
            return rb, diff[0]
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base"); ap.add_argument("cand")
    ap.add_argument("--round", type=int, default=-1); ap.add_argument("--frames", type=int, default=3)
    ap.add_argument("--step", type=int, default=2); ap.add_argument("--radius", type=int, default=6)
    ap.add_argument("--center", default="")
    a = ap.parse_args()
    m = re.search(r"_([AB])_\d+\.replay$", a.base); side = m.group(1) if m else None
    gb, gc = Game(a.base, side), Game(a.cand, side)
    r0, cell = (a.round, None) if a.round >= 0 else first_divergence(gb, gc)
    if r0 is None: print("no divergence found"); return
    if a.center: cell = tuple(map(int, a.center.split(",")))
    print(f"first divergence r{r0} at {cell}" if a.round < 0 else f"round {r0}")
    want = set(range(max(0, r0 - a.step), r0 + a.frames * a.step, a.step))
    sb, sc = states(gb, want), states(gc, want)
    for r in sorted(want):
        if r not in sb or r not in sc: continue
        cx, cy = cell if cell else (gb.W // 2, gb.H // 2)
        fb = gb.render(r, sb[r], cx, cy, a.radius).splitlines(); fc = gc.render(r, sc[r], cx, cy, a.radius).splitlines()
        grid_b = [l for l in fb if l.startswith(("+", "|", " ")) and not l.startswith("    ")]
        grid_c = [l for l in fc if l.startswith(("+", "|", " ")) and not l.startswith("    ")]
        w = max((len(l) for l in grid_b), default=0)
        print(f"\n=== r{r}   BASE {gb.stats(sb[r])}   |   CAND {gc.stats(sc[r])}")
        for lb, lc in zip(grid_b, grid_c): print(f"{lb:<{w}}   {lc}")
        def tags(g, st):
            out = {}
            for i, b in st["body"].items():
                if not b or st["team"][i] != g.ours: continue
                x, y = b[0]
                if min(abs(x - cx), g.W - abs(x - cx)) <= a.radius and min(abs(y - cy), g.H - abs(y - cy)) <= a.radius:
                    out[i] = (len(b), (st["ind"].get(i, "") or "")[:70])
            return out
        tb, tc = tags(gb, sb[r]), tags(gc, sc[r])
        for i in sorted(set(tb) | set(tc)):
            x, y = (tb.get(i) or tc.get(i))[0], None
            b_, c_ = tb.get(i), tc.get(i)
            mark = "  <== differs" if (b_ and c_ and b_[1].split()[:1] != c_[1].split()[:1]) or (bool(b_) != bool(c_)) else ""
            print(f"   id{i:<4d} base {('L%d %s' % b_) if b_ else '-':<50s} cand {('L%d %s' % c_) if c_ else '-'}{mark}")


if __name__ == "__main__":
    main()
