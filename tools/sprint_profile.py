"""How do teams use sprints (several steps in one turn, costing steps-1 segments)?

Per team (scout-style dir with index.json): sprint share of move actions by round band, sprint length mix,
the dragon's length when sprinting, and what the sprint achieved: pearls eaten along it, killed an enemy head
(head-to-head in the same turn), ended the dragon's life (died that turn), or plain repositioning.

    uv run --python 3.11 --with unswbc python tools/sprint_profile.py ladder/scout_fresh [--min-games 3]
"""
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import load  # noqa: E402

BANDS = [(0, 100), (100, 250), (250, 400), (400, 501)]


def band(r):
    for i, (a, b) in enumerate(BANDS):
        if a <= r < b:
            return i
    return 3


def analyse(f, side, A):
    rep = load(f)
    w = int(next(l for l in rep['map'].splitlines() if l.startswith('MAP ')).split()[1])
    team, length, nid = {}, {}, 0
    for l in rep['map'].splitlines():
        p = l.split()
        if p and p[0] == 'DRAGON':
            team[nid] = int(p[1]); length[nid] = int(p[2]); nid += 1
    rnd = 0
    pending = {}   # dragon id -> (round, steps, len before)
    tail = {}
    grew = collections.Counter()
    for e in rep['events']:
        k = e['kind']
        if k == 'roundStart':
            # settle sprints of the previous round
            for d, (r0, steps, L0) in pending.items():
                A['sprint_len_mix', min(steps, 5)] += 1
                A['sprint_L', 'sum'] += L0
                A['sprint_ate'] += grew[d]
                if grew[d] >= steps - 1:
                    A['sprint_paid'] += 1
            pending.clear(); grew.clear()
            rnd = e['round']
        elif k == 'dragonSplit':
            team[e['child']] = e['team']
            length[e['parent']] = len(e['parentBody']); length[e['child']] = len(e['childBody'])
        elif k == 'dragonAction' and e.get('act') == 'move' and team.get(e['id']) == side:
            steps = len(e['dirs'])
            b = band(rnd)
            A['moves', b] += 1
            if steps > 1:
                A['sprints', b] += 1
                pending[e['id']] = (rnd, steps, length.get(e['id'], 0))
        elif k == 'tileChange':
            pass
        elif k == 'dragonUpdate' and e['head'] and e['id'] in team:
            tl = e['tail']
            if tl is not None and tail.get(e['id']) == tl:
                grew[e['id']] += 1
            tail[e['id']] = tl
        elif k == 'dragonDeath':
            d = e['id']
            if d in pending:
                cause = str(e.get('reason', e.get('cause', '')))
                A['sprint_died'] += 1
                A['sprint_death_cause', cause[:20]] += 1
                del pending[d]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('--min-games', type=int, default=3)
    a = ap.parse_args()
    root = pathlib.Path(a.dir)
    idx = {(str(e['teamId']), str(e['game'])): e for e in json.load(open(root / 'index.json', encoding='utf-8'))}
    per = collections.defaultdict(collections.Counter)
    games = collections.Counter()
    elo = {}
    for f in sorted(root.rglob('*.replay')):
        m = idx.get((f.parent.name, f.stem))
        if not m:
            continue
        side = 0 if m['side'] in ('A', 0) else 1
        try:
            analyse(f, side, per[m['team']])
            games[m['team']] += 1
            elo[m['team']] = m.get('elo', 0)
        except Exception as ex:  # noqa: BLE001
            print('skip', f, ex, file=sys.stderr)
    print(f"{'team':22s} {'g':>3s} {'elo':>5s} | sprint % of moves r0-100 r100-250 r250-400 r400+ | per game | "
          f"2/3/4/5+ step mix % | mean len | pearls per sprint | paid-for % | died %")
    for t in sorted(per, key=lambda t: -(elo.get(t) or 0)):
        if games[t] < a.min_games:
            continue
        A = per[t]
        ns = sum(A['sprints', i] for i in range(4))
        rates = " ".join(f"{100 * A['sprints', i] / A['moves', i]:6.2f}" if A['moves', i] else "   n/a" for i in range(4))
        mix = "/".join(f"{100 * A['sprint_len_mix', s] / ns:.0f}" if ns else "-" for s in (2, 3, 4, 5))
        settled = sum(A['sprint_len_mix', s] for s in (2, 3, 4, 5)) or 1
        print(f"{t[:22]:22s} {games[t]:3d} {elo.get(t) or 0:5.0f} | {rates} | {ns / games[t]:6.1f} | {mix:>11s} | "
              f"{A['sprint_L', 'sum'] / settled:5.1f} | {A['sprint_ate'] / settled:4.2f} | "
              f"{100 * A['sprint_paid'] / settled:4.0f} | {100 * A['sprint_died'] / max(1, ns):4.0f}")


if __name__ == '__main__':
    main()
