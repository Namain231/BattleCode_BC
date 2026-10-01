"""Longest-dragon timeline per bot from a local_index.py dir (85% of unseen-map games end on the
length tiebreak at r500, so the longest dragon at the end is the number that decides them).

    uv run --python 3.11 --with unswbc python tools/endgame_len.py ladder/x_prof [more dirs]

Per bot: mean longest own dragon at r250/300/350/400/450/end, units at the same rounds, queen splits
and deaths after r250, and the paired final margin (our longest - their longest) with its std error.
"""
import collections
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import load  # noqa: E402

MARKS = [250, 300, 350, 400, 450, 500]


def game_stats(f):
    rep = load(f)
    w = int(next(l for l in rep['map'].splitlines() if l.startswith('MAP ')).split()[1])
    team, body, nid = {}, {}, 0
    for l in rep['map'].splitlines():
        p = l.split()
        if p and p[0] == 'DRAGON':
            t, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t
            body[nid] = [c[2 * i + 1] * w + c[2 * i] for i in range(n)]
            nid += 1
    alive = set(team)
    snap = {0: {}, 1: {}}
    splits = [0, 0]
    qdeaths = [0, 0]
    rnd = 0

    def longest(side):
        own = [d for d in alive if team.get(d) == side]
        return max((len(body[d]) for d in own), default=0), len(own)

    def take(r):
        for s in (0, 1):
            snap[s][r] = longest(s)

    queen = [None, None]
    for e in rep['events']:
        k = e['kind']
        if k == 'roundStart':
            rnd = e['round']
            if rnd in MARKS[:-1]:
                take(rnd)
            if rnd >= 250:
                for s in (0, 1):
                    own = [d for d in alive if team.get(d) == s]
                    queen[s] = max(own, key=lambda d: (len(body[d]), -d)) if own else None
        elif k == 'dragonUpdate' and e['head'] and e['id'] in body:
            hd = e['head'][1] * w + e['head'][0]
            tl = e['tail'][1] * w + e['tail'][0] if e['tail'] else None
            b = body[e['id']]
            if b[0] != hd:
                b.insert(0, hd)
            if tl is not None:
                while len(b) > 1 and b[-1] != tl:
                    b.pop()
        elif k == 'dragonSplit':
            team[e['child']] = e['team']
            alive.add(e['child'])
            body[e['parent']] = [p[1] * w + p[0] for p in e['parentBody']]
            body[e['child']] = [p[1] * w + p[0] for p in e['childBody']]
            s = team.get(e['parent'])
            if s in (0, 1) and e['parent'] == queen[s]:
                splits[s] += 1
        elif k == 'dragonDeath':
            s = team.get(e['id'])
            if s in (0, 1) and e['id'] == queen[s]:
                qdeaths[s] += 1
            alive.discard(e['id'])
    take(500)
    for s in (0, 1):
        for r in MARKS:
            snap[s].setdefault(r, (0, 0))
    return snap, splits, qdeaths


def main():
    for root in map(pathlib.Path, sys.argv[1:]):
        idx = json.load(open(root / 'index.json', encoding='utf-8'))
        by_game = collections.defaultdict(dict)
        for e in idx:
            by_game[e['game']][e['teamId']] = e
        agg = collections.defaultdict(lambda: collections.defaultdict(float))
        margins = collections.defaultdict(list)
        for game, ents in sorted(by_game.items()):
            labels = list(ents)
            f = next((root / l / f"{game}.replay" for l in labels if (root / l / f"{game}.replay").exists()), None)
            if f is None:
                continue
            snap, splits, qd = game_stats(f)
            for l, e in ents.items():
                s = 0 if e['side'] in ('A', 0) else 1
                A = agg[l]
                A['games'] += 1
                A['win'] += 1 if e['winner'] == e['side'] else 0
                for r in MARKS:
                    A[f'L{r}'] += snap[s][r][0]
                    A[f'U{r}'] += snap[s][r][1]
                A['splits'] += splits[s]
                A['qdeaths'] += qd[s]
                margins[l].append(snap[s][500][0] - snap[1 - s][500][0])
        for l, A in agg.items():
            g = A['games']
            m = margins[l]
            mu = sum(m) / len(m)
            sd = math.sqrt(sum((x - mu) ** 2 for x in m) / max(1, len(m) - 1))
            print(f"{root.name} {l:16s} n={g:.0f} win={A['win'] / g:5.1%} "
                  + " ".join(f"L{r}={A[f'L{r}'] / g:5.1f}" for r in MARKS)
                  + " | " + " ".join(f"U{r}={A[f'U{r}'] / g:4.1f}" for r in (250, 400, 500))
                  + f" | qsplit={A['splits'] / g:4.1f} qdeath={A['qdeaths'] / g:4.1f}"
                  + f" | margin500={mu:+5.2f} +-{sd / math.sqrt(len(m)):.2f}")


if __name__ == '__main__':
    main()
