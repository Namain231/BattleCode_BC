"""What do sprints do? Per team: kill / eat / escape / move, and how often a team's dragons die to enemy sprints.

    python tools/sprint_purpose.py ladder/scout_fresh/index.json ladder/scout_fresh

Complements tools/sprint_profile.py (step mix, death-after-sprint): this one attributes each multi-step move to a
purpose from what happened in the same turn, and counts our deaths by enemy sprint vs enemy single step.
"""
import sys, json, os, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from replay import load

def cheb(a, b, W, H):
    dx = abs(a[0]-b[0]); dy = abs(a[1]-b[1])
    return max(min(dx, W-dx), min(dy, H-dy))

def profile(path, side_idx):
    rep = load(path)
    W, H = map(int, rep['map'].splitlines()[0].split()[1:3])
    team, nid = {}, 0
    for line in rep['map'].splitlines():
        p = line.split()
        if p and p[0] == 'DRAGON':
            team[nid] = int(p[1]); nid += 1
    head = {}
    st = collections.Counter()
    cur = None  # (id, sprintlen, headBefore, events)
    def close(c):
        if not c: return
        did, n, hb, evs, enemy_near = c
        ate = sum(1 for e in evs if e['kind'] == 'tileChange' and e.get('pearl') == 0)
        kills = [e for e in evs if e['kind'] == 'dragonDeath' and e['reason'] == 3 and team.get(e['id']) != team.get(did)]
        died = any(e['kind'] == 'dragonDeath' and e['id'] == did for e in evs)
        mine = team.get(did) == side_idx
        if n >= 2:
            key = 'my' if mine else 'op'
            st[key + '_sprints'] += 1
            if kills: st[key + '_sprint_kill'] += 1
            elif ate: st[key + '_sprint_eat'] += 1
            elif died: st[key + '_sprint_diedother'] += 1
            elif enemy_near: st[key + '_sprint_escape'] += 1
            else: st[key + '_sprint_move'] += 1
            if not mine and kills:
                for k in kills:
                    if team.get(k['id']) == side_idx: st['my_killed_by_sprint'] += 1
        if n == 1 and not mine:
            for e in evs:
                if e['kind'] == 'dragonDeath' and e['reason'] == 3 and team.get(e['id']) == side_idx and e['id'] != did:
                    st['my_killed_by_step'] += 1
    for e in rep['events']:
        k = e['kind']
        if k == 'turnStart':
            close(cur); cur = None
            tid = e['id']
        elif k == 'dragonSplit':
            team[e['child']] = e['team']
        elif k == 'dragonAction':
            did = e['id']; n = len(e.get('dirs', '') or '')
            hb = head.get(did)
            near = False
            if hb is not None:
                for o, h in head.items():
                    if team.get(o) != team.get(did) and o in head and cheb(hb, h, W, H) <= 2:
                        near = True; break
            cur = (did, n, hb, [], near)
        elif k == 'dragonUpdate':
            head[e['id']] = e['head']
            if cur: cur[3].append(e)
        elif k == 'dragonDeath':
            head.pop(e['id'], None)
            if cur: cur[3].append(e)
        elif cur:
            cur[3].append(e)
    close(cur)
    return st

def main():
    idx = json.load(open(sys.argv[1])); root = sys.argv[2]
    per = collections.defaultdict(collections.Counter); seen = set()
    for g in idx:
        paths = glob.glob(os.path.join(root, '*', f"{g['game']}.replay"))
        if not paths or (g['game'], g['side']) in seen: continue
        seen.add((g['game'], g['side']))
        st = profile(paths[0], 0 if g['side'] == 'A' else 1); st['games'] += 1
        per[g['team']] += st
    print(f"{'team':22s} games sprints  kill%  eat%  escape%  move%  diedOther%   our deaths: by enemy sprint / by enemy step")
    for t, s in sorted(per.items(), key=lambda kv: -kv[1]['games']):
        n = max(s['my_sprints'], 1)
        f = lambda k: 100 * s['my_sprint_' + k] / n
        print(f"{t[:22]:22s} {s['games']:5d} {s['my_sprints']:7d} {f('kill'):6.0f} {f('eat'):5.0f} {f('escape'):8.0f} {f('move'):6.0f} {f('diedother'):9.0f}      {s['my_killed_by_sprint']:5d} / {s['my_killed_by_step']}")
main()
