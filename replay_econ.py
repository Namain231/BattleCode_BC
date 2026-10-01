#!/usr/bin/env python3
"""
replay_econ.py -- economy / population report for Dragon Game replays.

    python replay_econ.py game1.replay [game2.replay ...] [--ours SUBSTR] [--phase 50] [--csv out.csv]

Replays are Cap'n Proto *packed* messages (no gzip in the files tested).  This tool
contains its own tiny reader, so it needs nothing but Python 3.8+.

What it reports, per team (yours vs the opponent):
  * units alive at milestone rounds, longest dragon and total length (from the L<n> in the
    indicator string; dragons whose indicator has no L keep their last known length)
  * splits per 25 rounds, first-split round, and how many were BUD vs ESCAPE-SPLIT
  * economy per 100 dragon-turns in each phase: pearls eaten, deaths, splits
  * death causes by team

Team identification: initial dragons alternate teams by id, so root-id parity picks the team
(even -> first team name in the replay, odd -> second); children inherit their parent's team.
--ours picks your team by substring of the team name (default: the team that is not v7.12).

Event schema (reverse-engineered, verified on Colosseum + Dilemma replays):
  0 round start (data0 = round)          1 dragon turn start (data0 = dragon id)
  7 indicator text (data0 = dragon id)   4 action (move directions)
  3 pearl eaten (position in ptr0)       0xa split  (low32 = parent id, high32 = child id)
  0xb death  (low32 = dragon id, high32 = reason)
Death reason codes are inferred from the engine doc's order:
  0 hit wall, 1 hit itself, 2 hit other body, 3 head-to-head, 4 no valid action.
  (0 vs 1 is the least certain pair -- check one death with board_at.py before relying on it.)
"""
import re, struct, sys, argparse, csv
from collections import defaultdict, Counter

# ----------------------------------------------------------------- Cap'n Proto
def unpack(b):
    out = bytearray(); i = 0; n = len(b)
    while i < n:
        tag = b[i]; i += 1
        if tag == 0x00:
            out += b'\0' * 8; k = b[i]; i += 1; out += b'\0' * (8 * k)
        elif tag == 0xFF:
            out += b[i:i + 8]; i += 8; k = b[i]; i += 1
            out += b[i:i + 8 * k]; i += 8 * k
        else:
            for bit in range(8):
                if tag >> bit & 1: out.append(b[i]); i += 1
                else: out.append(0)
    return bytes(out)

class Msg:
    def __init__(s, path):
        raw = open(path, 'rb').read()
        if raw[:2] == b'\x1f\x8b':
            import gzip; raw = gzip.decompress(raw)
        u = unpack(raw)
        n = struct.unpack_from('<I', u, 0)[0] + 1
        sizes = struct.unpack_from('<%dI' % n, u, 4)
        off = (4 + 4 * n + 7) // 8 * 8
        s.segs = []
        for z in sizes:
            s.segs.append(u[off:off + 8 * z]); off += 8 * z
    def word(s, seg, i): return struct.unpack_from('<Q', s.segs[seg], 8 * i)[0]
    def resolve(s, seg, i):
        w = s.word(seg, i)
        if w == 0: return None
        if w & 3 == 2:                       # far pointer
            pad = (w >> 3) & 0x1FFFFFFF; tseg = w >> 32
            if not (w >> 2) & 1: return s.resolve(tseg, pad)
            w2 = s.word(tseg, pad); w3 = s.word(tseg, pad + 1)
            return s._decode(w3, w2 >> 32, ((w2 >> 3) & 0x1FFFFFFF) - 1)
        return s._decode(w, seg, i)
    def _decode(s, w, seg, i):
        t = w & 3; off = (w >> 2) & 0x3FFFFFFF
        if off >= 1 << 29: off -= 1 << 30
        st = i + 1 + off
        if t == 0: return ('struct', seg, st, ((w >> 32) & 0xFFFF, (w >> 48) & 0xFFFF))
        if t == 1:
            esz = (w >> 32) & 7; cnt = w >> 35
            if esz == 7:
                tg = s.word(seg, st)
                return ('inlist', seg, st + 1, ((tg >> 2) & 0x3FFFFFFF, (tg >> 32) & 0xFFFF, (tg >> 48) & 0xFFFF))
            return ('list', seg, st, (esz, cnt))
        return None
    def text(s, r):
        _, seg, st, (esz, cnt) = r
        return s.segs[seg][8 * st:8 * st + cnt].rstrip(b'\0').decode('latin1')
    def sfield(s, r, k):
        _, seg, st, (dw, pw) = r
        return s.resolve(seg, st + dw + k) if k < pw else None
    def dfield(s, r, k):
        _, seg, st, (dw, pw) = r
        return s.word(seg, st + k) if k < dw else 0
    def elem(s, r, j):
        _, seg, st, (n, dw, pw) = r
        return ('struct', seg, st + j * (dw + pw), (dw, pw))

REASONS = {0: 'hit wall', 1: 'hit itself', 2: 'hit other body', 3: 'head-to-head', 4: 'no valid action'}
L_RE = re.compile(r'^L(\d+) ')

# ------------------------------------------------------------------- analysis
def parse(path):
    m = Msg(path); root = m.resolve(0, 0)
    names = [m.text(m.sfield(root, 1)), m.text(m.sfield(root, 2))]
    ev = m.sfield(root, 3); n = ev[3][0]
    R = -1; cur = None
    turns = defaultdict(list); ind = defaultdict(list)
    parent = {}; splits = []; eats = []; deaths = []
    for j in range(n):
        e = m.elem(ev, j); t = m.dfield(e, 0); s = m.sfield(e, 0)
        d0 = m.dfield(s, 0) if s else 0
        if t == 0: R = d0
        elif t == 1: cur = d0; turns[R].append(d0)
        elif t == 7:
            tx = m.sfield(s, 0); ind[d0].append((R, m.text(tx) if tx else ''))
        elif t == 3: eats.append((R, cur))
        elif t == 0xa:
            p, c = d0 & 0xffffffff, d0 >> 32; parent[c] = p; splits.append((R, p, c))
        elif t == 0xb: deaths.append((R, d0 & 0xffffffff, d0 >> 32))
    return dict(names=names, turns=turns, ind=ind, parent=parent, splits=splits,
                eats=eats, deaths=deaths, rounds=(max(turns) + 1 if turns else 0))

def team_index(g):
    parent = g['parent']
    def root(x):
        while x in parent: x = parent[x]
        return x
    return lambda d: root(d) % 2, root

def pick_ours(names, sub):
    if sub:
        for i, nm in enumerate(names):
            if sub.lower() in nm.lower(): return i
        raise SystemExit(f'--ours "{sub}" matches none of {names}')
    others = [i for i, nm in enumerate(names) if '7.12' not in nm]
    return others[0] if len(others) == 1 else 1

def report(path, ours_sub, phase):
    g = parse(path); names = g['names']
    tix, root = team_index(g); me = pick_ours(names, ours_sub); opp = 1 - me
    lab = {me: 'OURS ' + names[me], opp: 'OPP  ' + names[opp]}
    R = g['rounds']
    print('=' * 92); print(f"{path}   rounds={R}   ours={names[me]}   opponent={names[opp]}"); print('=' * 92)
    # length per dragon per round (forward fill from indicator)
    lastL = {}; Lat = defaultdict(dict)
    per_round_ind = defaultdict(dict)
    for d, l in g['ind'].items():
        for r, tx in l:
            mm = L_RE.match(tx)
            if mm: per_round_ind[r][d] = int(mm.group(1))
    alive_units = {}
    marks = [m for m in (10, 25, 50, 75, 100, 150, 200, 300, 400) if m < R] + [R - 1]
    lens = {}
    rows = {}
    for r in range(R):
        lens.update(per_round_ind.get(r, {}))
        if r in marks:
            for t in (me, opp):
                ds = [d for d in g['turns'][r] if tix(d) == t]
                Ls = [lens.get(d, 2) for d in ds]
                rows[(r, t)] = (len(ds), max(Ls) if Ls else 0, sum(Ls))
    print('\nUNITS / LONGEST / TOTAL LENGTH at milestone rounds')
    print(f"{'round':>6} | {'ours u':>7} {'long':>5} {'total':>6} | {'opp u':>7} {'long':>5} {'total':>6}")
    for r in marks:
        a, b = rows[(r, me)], rows[(r, opp)]
        print(f'{r:6d} | {a[0]:7d} {a[1]:5d} {a[2]:6d} | {b[0]:7d} {b[1]:5d} {b[2]:6d}')
    # splits
    kind = {}
    for r, p, c in g['splits']:
        tx = next((t for rr, t in g['ind'].get(p, []) if rr == r), '')
        kind[c] = 'ESCAPE' if 'ESCAPE' in tx else 'BUD' if tx.startswith('BUD') else 'other'
    print('\nSPLITS')
    for t in (me, opp):
        ss = [(r, p, c) for r, p, c in g['splits'] if tix(p) == t]
        kinds = Counter(kind.get(c, 'other') for _, _, c in ss)
        per25 = Counter(r // 25 * 25 for r, _, _ in ss)
        first = min((r for r, _, _ in ss), default=None)
        print(f"  {lab[t]:<28} total={len(ss):4d} first={first}  kinds={dict(kinds)}")
        print('     per 25 rounds:', ' '.join(f'{k}:{v}' for k, v in sorted(per25.items())[:12]))
    # economy per phase
    dt = defaultdict(Counter); eat = defaultdict(Counter); die = defaultdict(Counter); spl = defaultdict(Counter)
    for r, ds in g['turns'].items():
        for d in ds: dt[tix(d)][r // phase * phase] += 1
    for r, d in g['eats']:
        if d is not None: eat[tix(d)][r // phase * phase] += 1
    for r, d, why in g['deaths']: die[tix(d)][r // phase * phase] += 1
    for r, p, c in g['splits']: spl[tix(p)][r // phase * phase] += 1
    print(f'\nECONOMY per 100 dragon-turns (phase = {phase} rounds)')
    print(f"{'phase':>10} | {'ours dt':>7} {'eat':>5} {'die':>5} {'spl':>5} | {'opp dt':>7} {'eat':>5} {'die':>5} {'spl':>5}")
    for b in range(0, R, phase):
        cells = []
        for t in (me, opp):
            n = dt[t][b]
            f = lambda c: (100.0 * c[b] / n) if n else 0.0
            cells.append((n, f(eat[t]), f(die[t]), f(spl[t])))
        a, o = cells
        print(f'{b:4d}-{b+phase-1:<5d}| {a[0]:7d} {a[1]:5.1f} {a[2]:5.1f} {a[3]:5.1f} | {o[0]:7d} {o[1]:5.1f} {o[2]:5.1f} {o[3]:5.1f}')
    print('\nDEATH CAUSES')
    for t in (me, opp):
        c = Counter(REASONS.get(why, f'code{why}') for r, d, why in g['deaths'] if tix(d) == t)
        print(f"  {lab[t]:<28} total={sum(c.values()):4d}  {dict(c.most_common())}")
    return dict(path=path, ours=names[me], opp=names[opp], rounds=R,
                units100=(rows.get((100, me), (None,))[0], rows.get((100, opp), (None,))[0]) if 100 in marks else None)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('replays', nargs='+'); ap.add_argument('--ours'); ap.add_argument('--phase', type=int, default=50)
    ap.add_argument('--csv', help='write one summary row per replay')
    a = ap.parse_args()
    out = [report(p, a.ours, a.phase) for p in a.replays]
    if a.csv:
        with open(a.csv, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=out[0].keys()); w.writeheader(); w.writerows(out)

if __name__ == '__main__':
    main()