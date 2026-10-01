"""Text visualiser for replays: the TRUE board (what no single dragon sees), frame by frame.

    python tools/viz.py REPLAY timeline [--every 10]
    python tools/viz.py REPLAY frames --round 180 [--frames 4 --step 1] [--center x,y | --dragon ID] [--radius 8 | --full]
    python tools/viz.py REPLAY deaths [--minlen 3] [--before 3] [--radius 6] [--max 12] [--from 0 --to 500]
    python tools/viz.py REPLAY eatmap [--from 0 --to 50]    # where each side ate pearls (the growth race)

Cells are 2 chars: first = what, second = id % 10.  Ours: head 'O', body 'o'. Theirs: head 'X', body 'x'.
'*' pearl, ' ' empty.  Edges: '--' / '|' kelp, 'PP' / 'P' portal.  "Ours" = the side whose replay bot field is
non-empty (our ladder games), or --side A/B.  Each frame header: round, per-team units/mass/longest, and the events
of the previous round (deaths with cause, splits, feeds) inside the window, plus indicators of our dragons there.
"""
import argparse
import collections
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402


class Game:
    def __init__(self, path, side=None):
        self.rep = _decode(path)
        lines = self.rep["map"].splitlines()
        self.W, self.H = map(int, lines[0].split()[1:3])
        self.name = next((l.split(" ", 1)[1] for l in lines if l.startswith("MAP_NAME")), "?")
        W, H = self.W, self.H
        self.edge = {}
        self.team, self.body = {}, {}
        nid = 0
        for l in lines:
            p = l.split()
            if not p: continue
            if p[0] == "EDGE":
                i, k = int(p[1]), int(p[2]); r, c = divmod(i, W + 1)
                key = (c % W, (r // 2) % H, "N") if r % 2 == 0 else (c % W, ((r - 1) // 2) % H, "W")
                self.edge[key] = k
            elif p[0] == "DRAGON":
                t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
                self.team[nid] = t; self.body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
        if side in ("A", "B"):
            self.ours = 0 if side == "A" else 1
        else:
            a, b = self.rep.get("botA"), self.rep.get("botB")
            self.ours = 0 if a and not b else 1 if b and not a else 0
        self.result = self.rep.get("result", {})

    def play(self):
        """Yield (round, state) at the start of every round; state is a snapshot dict."""
        body = {i: list(b) for i, b in self.body.items()}
        team = dict(self.team); alive = set(team); pearls = set(); ind = {}
        events = collections.defaultdict(list)   # round -> list of (text, cell)
        rnd = -1
        for e in self.rep["events"]:
            k = e["kind"]
            if k == "roundStart":
                if rnd >= 0:
                    yield rnd, dict(body={i: list(body[i]) for i in alive}, team=team, pearls=set(pearls),
                                    ind=dict(ind), events=events.get(rnd - 1, []))
                rnd = e["round"]
            elif k == "tileChange":
                t = tuple(e["tile"]); (pearls.add if e.get("pearl") else pearls.discard)(t)
            elif k == "dragonIndicator":
                ind[e["id"]] = e["text"]
            elif k == "dragonUpdate" and e["id"] in body and e["head"]:
                b = body[e["id"]]; hd = tuple(e["head"])
                if b[0] != hd: b.insert(0, hd)
                tl = tuple(e["tail"]) if e.get("tail") else None
                while len(b) > 1 and tl is not None and b[-1] != tl: b.pop()
                pearls.discard(hd)
            elif k == "dragonSplit":
                team[e["child"]] = e["team"]
                body[e["child"]] = [tuple(c) for c in e["childBody"]]
                body[e["parent"]] = [tuple(c) for c in e["parentBody"]]
                alive.add(e["child"])
                events[rnd].append((f"split {e['parent']}->{e['child']}({len(e['childBody'])})", body[e["child"]][0]))
            elif k == "dragonDeath":
                i = e["id"]; alive.discard(i)
                cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
                who = "OUR" if team.get(i) == self.ours else "their"
                cell = body[i][0] if body.get(i) else None
                events[rnd].append((f"{who} {i}(L{len(body.get(i) or [])}) died: {cause}", cell))
        if rnd >= 0:
            yield rnd, dict(body={i: list(body[i]) for i in alive}, team=team, pearls=set(pearls), ind=dict(ind),
                            events=events.get(rnd - 1, []))

    def stats(self, st):
        out = []
        for t in (self.ours, 1 - self.ours):
            ls = [len(b) for i, b in st["body"].items() if st["team"][i] == t]
            out.append(f"{len(ls)}/{sum(ls)}/{max(ls) if ls else 0}")
        return out

    def render(self, rnd, st, cx, cy, R, full=False):
        W, H = self.W, self.H
        occ = {}
        for i, b in st["body"].items():
            for j, c in enumerate(b): occ[tuple(c)] = (i, j)
        xs = range(W) if full else [(cx + d) % W for d in range(-R, R + 1)]
        ys = range(H) if full else [(cy + d) % H for d in range(-R, R + 1)]
        ours, theirs = self.stats(st)
        queen_ours = min(i for i in self.team if self.team[i] == self.ours)      # first dragon of each team (map order)
        queen_theirs = min(i for i in self.team if self.team[i] != self.ours)
        qo = len(st["body"].get(queen_ours, []))
        qt = len(st["body"].get(queen_theirs, []))
        lines = [f"--- r{rnd}  ours units/mass/longest {ours}  theirs {theirs}  Q ours/theirs {qo}/{qt}"]
        for (txt, cell) in st["events"]:
            if cell is None or full or (min(abs(cell[0] - cx), W - abs(cell[0] - cx)) <= R and
                                        min(abs(cell[1] - cy), H - abs(cell[1] - cy)) <= R):
                lines.append(f"    r{rnd - 1}: {txt} at {cell}")
        for y in ys:
            top = row = ""
            for x in xs:
                kn, kw = self.edge.get((x, y, "N"), 0), self.edge.get((x, y, "W"), 0)
                top += "+" + ("--" if kn == 1 else "PP" if kn == 2 else "  ")
                row += "|" if kw == 1 else "P" if kw == 2 else " "
                if (x, y) in occ:
                    i, j = occ[(x, y)]
                    our = st["team"][i] == self.ours
                    row += ("O" if j == 0 else "o") if our else ("X" if j == 0 else "x")
                    row += str(i % 10)
                else:
                    row += ("* " if (x, y) in st["pearls"] else "  ")
            lines.append(top); lines.append(row)
        shown = [i for i, b in st["body"].items() if st["team"][i] == self.ours and b and
                 (full or tuple(b[0]) in {(x, y) for x in xs for y in ys})]
        for i in shown[:12]:
            if i in st["ind"]: lines.append(f"    O{i % 10} id{i} L{len(st['body'][i])}: {st['ind'][i][:90]}")
        return "\n".join(lines)


def eat_map(g, r0, r1):
    """Full map: cells where WE ate a pearl in [r0, r1] ('o', count if > 1), THEY ate ('x'), both ('#'), a pearl that
    appeared and was not eaten in the window ('.'); kelp edges as in frames; start heads 'A'/'B'. Totals per side."""
    rep = g.rep; W, H = g.W, g.H
    team = dict(g.team); heads = {i: tuple(b[0]) for i, b in g.body.items()}
    pearls, ate, seen = set(), {}, set()
    rnd = 0
    DXY = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            if rnd > r1: break
        elif k == "tileChange":
            t = tuple(e["tile"])
            if e.get("pearl"):
                pearls.add(t)
                if rnd >= r0: seen.add(t)
            else: pearls.discard(t)
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]; heads[e["child"]] = tuple(e["childBody"][0])
        elif k == "dragonAction" and e.get("act") == "move" and e["id"] in heads:
            x, y = heads[e["id"]]; side = 0 if team.get(e["id"]) == g.ours else 1
            for ch in e.get("dirs", ""):
                dx, dy = DXY.get(ch, (0, 0)); x, y = (x + dx) % W, (y + dy) % H
                if (x, y) in pearls and r0 <= rnd <= r1:
                    ate.setdefault((x, y), [0, 0])[side] += 1
        elif k == "dragonUpdate" and e.get("head"):
            heads[e["id"]] = tuple(e["head"])
    start = {tuple(b[0]): ("A" if g.team[i] == 0 else "B") for i, b in g.body.items()}
    tot = [sum(v[0] for v in ate.values()), sum(v[1] for v in ate.values())]
    print(f"pearls eaten r{r0}-{r1}: ours {tot[0]}, theirs {tot[1]}; appeared and not eaten: {len(seen - set(ate))}"
          f"   (o = ours, x = theirs, # = both, . = uneaten, A/B = start heads; ours = {'AB'[g.ours]})")
    for y in range(H):
        top = row = ""
        for x in range(W):
            kn, kw = g.edge.get((x, y, "N"), 0), g.edge.get((x, y, "W"), 0)
            top += "+" + ("--" if kn == 1 else "PP" if kn == 2 else "  ")
            row += "|" if kw == 1 else "P" if kw == 2 else " "
            v = ate.get((x, y))
            if v and v[0] and v[1]: cell = "##"
            elif v and v[0]: cell = "o" + (str(min(9, v[0])) if v[0] > 1 else " ")
            elif v and v[1]: cell = "x" + (str(min(9, v[1])) if v[1] > 1 else " ")
            elif (x, y) in start: cell = start[(x, y)] + " "
            elif (x, y) in seen: cell = ". "
            else: cell = "  "
            row += cell
        print(top); print(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay"); ap.add_argument("mode", choices=["timeline", "frames", "deaths", "eatmap"])
    ap.add_argument("--side", default=None)
    ap.add_argument("--every", type=int, default=10)
    ap.add_argument("--round", type=int, default=0); ap.add_argument("--frames", type=int, default=4)
    ap.add_argument("--step", type=int, default=1); ap.add_argument("--center", default="")
    ap.add_argument("--dragon", type=int, default=-1); ap.add_argument("--radius", type=int, default=8)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--minlen", type=int, default=3); ap.add_argument("--before", type=int, default=3)
    ap.add_argument("--max", type=int, default=12); ap.add_argument("--from", dest="rfrom", type=int, default=0)
    ap.add_argument("--to", type=int, default=500)
    a = ap.parse_args()
    g = Game(a.replay, a.side)
    print(f"{g.name}  {g.W}x{g.H}  ours = team {'AB'[g.ours]}  result {g.result}")
    if a.mode == "timeline":
        for rnd, st in g.play():
            evs = [t for t, _ in st["events"] if not t.startswith("split")]
            if rnd % a.every == 0 or any(("OUR" in t and "L" in t and int(t.split("(L")[1].split(")")[0]) >= 8) for t in evs):
                o, t = g.stats(st)
                big = [t for t in evs if "(L" in t and int(t.split("(L")[1].split(")")[0]) >= 6]
                print(f"r{rnd:3d} ours {o:12s} theirs {t:12s} " + ("; ".join(big)[:150] if big else ""))
        return
    if a.mode == "eatmap":
        eat_map(g, a.rfrom, a.to)
        return
    if a.mode == "frames":
        want = set(range(a.round, a.round + a.frames * a.step, a.step))
        for rnd, st in g.play():
            if rnd not in want: continue
            if a.dragon >= 0 and a.dragon in st["body"]:
                cx, cy = st["body"][a.dragon][0]
            elif a.center:
                cx, cy = map(int, a.center.split(","))
            else:
                cx, cy = g.W // 2, g.H // 2
            print(g.render(rnd, st, cx, cy, a.radius, a.full))
        return
    # deaths: remember recent states; when one of our dragons dies (not a feed), print the frames before it
    hist = collections.deque(maxlen=a.before + 1); shown = 0
    for rnd, st in g.play():
        hist.append((rnd, st))
        if not (a.rfrom <= rnd <= a.to): continue
        for (txt, cell) in st["events"]:
            if not txt.startswith("OUR") or "no valid action" in txt or cell is None: continue
            L = int(txt.split("(L")[1].split(")")[0])
            if L < a.minlen: continue
            print(f"\n######## {txt} at {cell} (death in round {rnd - 1})")
            for r0, s0 in list(hist)[:-1]:
                print(g.render(r0, s0, cell[0], cell[1], a.radius))
            shown += 1
            if shown >= a.max: return


if __name__ == "__main__":
    main()
