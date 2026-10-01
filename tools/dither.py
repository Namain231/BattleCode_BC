"""Dithering: dragons that hover near one spot for many moves without eating (e.g. circling the mouth of a
corridor instead of entering it).

A dragon-turn counts as dither when the head is within 2 (torus) of where it was W own moves earlier, the
dragon did not grow in between, and it has been alive for at least W moves. Reported per side and per round
band as dither turns per 100 dragon-turns, plus the longest unbroken dither streak of any single dragon.

    uv run --python 3.11 --with unswbc python tools/dither.py --ours 13685 ladder/losses/739735 ladder/losses/739746
    (--ours = our submission id, read from the replay header; without it both sides are labelled A/B)
"""
import argparse
import collections
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import load  # noqa: E402

BANDS = [(0, 100), (100, 250), (250, 400), (400, 501)]


def band(r):
    for i, (a, b) in enumerate(BANDS):
        if a <= r < b:
            return i
    return len(BANDS) - 1


def analyse(f, W_WIN, agg, ours_id):
    rep = load(f)
    w = int(next(l for l in rep['map'].splitlines() if l.startswith('MAP ')).split()[1])
    h = int(next(l for l in rep['map'].splitlines() if l.startswith('MAP ')).split()[2])
    label = {0: 'A', 1: 'B'}
    if ours_id is not None:
        label = {0: 'ours' if str(rep['botA']) == str(ours_id) else 'opp',
                 1: 'ours' if str(rep['botB']) == str(ours_id) else 'opp'}
    team, hist, length = {}, {}, {}
    nid = 0
    for l in rep['map'].splitlines():
        p = l.split()
        if p and p[0] == 'DRAGON':
            t, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t
            hist[nid] = [(c[1] * w + c[0])]
            length[nid] = n
            nid += 1
    streak = collections.defaultdict(int)
    lasttail = {}
    rnd = 0
    for e in rep['events']:
        k = e['kind']
        if k == 'roundStart':
            rnd = e['round']
        elif k == 'dragonSplit':
            team[e['child']] = e['team']
            hist[e['child']] = []
            length[e['parent']] = len(e['parentBody'])
            length[e['child']] = len(e['childBody'])
            streak[e['parent']] = 0
        elif k == 'dragonUpdate' and e['head'] and e['id'] in hist:
            d = e['id']
            hd = e['head'][1] * w + e['head'][0]
            hs = hist[d]
            if hs and hs[-1] == hd:
                continue
            hs.append(hd)
            tl = e['tail'][1] * w + e['tail'][0] if e['tail'] else None
            grew = tl is not None and lasttail.get(d) == tl and len(hs) > 1
            lasttail[d] = tl
            s = label[team[d]]
            A = agg[s]
            b = band(rnd)
            if len(hs) > W_WIN:
                past = hs[-1 - W_WIN]
                dx = abs(past % w - hd % w)
                dy = abs(past // w - hd // w)
                dist = min(dx, w - dx) + min(dy, h - dy)
                A['turns', b] += 1
                if dist <= 2 and not grew:
                    A['dither', b] += 1
                    streak[d] += 1
                    A['maxstreak'] = max(A['maxstreak'], streak[d])
                else:
                    streak[d] = 0
        elif k == 'dragonDeath':
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--ours', default=None)
    ap.add_argument('--window', type=int, default=12)
    a = ap.parse_args()
    agg = collections.defaultdict(collections.Counter)
    for d in a.dirs:
        for f in sorted(pathlib.Path(d).glob('*.replay')):
            try:
                analyse(f, a.window, agg, a.ours)
            except Exception as ex:  # noqa: BLE001
                print('skip', f, ex)
    for s, A in sorted(agg.items()):
        rates = []
        for i, (x, y) in enumerate(BANDS):
            t = A['turns', i]
            rates.append(f"r{x}-{y}: {100 * A['dither', i] / t:5.1f}" if t else f"r{x}-{y}:   n/a")
        print(f"{s:5s} dither per 100 dragon-turns | " + " | ".join(rates) + f" | longest streak {A['maxstreak']}")


if __name__ == '__main__':
    main()
