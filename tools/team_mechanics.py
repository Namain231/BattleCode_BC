"""Sprint / sonar / echo usage per team from ladder replays.

    python tools/team_mechanics.py ladder/scout_fresh/index.json ladder/scout_fresh

Per team: sprints per 1000 moves, sprint length mix, sprints that end in the sprinter's death, sonar pings per
turn and their direction relative to facing (F/B/L/R), what the rays stopped on, and pings that hit a newborn child.
"""
import sys, json, os, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from replay import load
DIRS = "NESW"
def rel(facing, d):
    k = (DIRS.index(d) - facing) % 4
    return "FRBL"[k]

def profile(path, side_idx):
    rep = load(path)
    team, nid, length = {}, 0, {}
    for line in rep['map'].splitlines():
        p = line.split()
        if p and p[0] == 'DRAGON':
            team[nid] = int(p[1]); length[nid] = int(p[2]); nid += 1
    st = collections.Counter()
    facing = {}
    turn_id = None; rnd = 0
    last_action = {}
    split_this_turn = {}
    for e in rep['events']:
        k = e['kind']
        if k == 'roundStart': rnd = e['round']
        elif k == 'turnStart': turn_id = e['id']
        elif k == 'dragonUpdate': facing[e['id']] = e['facing']
        elif k == 'dragonSplit':
            team[e['child']] = e['team']
            split_this_turn[e['parent']] = (rnd, e['child'])
        elif k == 'dragonAction':
            if team.get(e['id']) != side_idx: continue
            st['turns'] += 1
            n = len(e.get('dirs', '') or '')
            if n >= 2:
                st['sprint'] += 1; st[f'sprint{n}'] += 1
                last_action[e['id']] = ('sprint', rnd)
            else:
                last_action[e['id']] = (e['act'], rnd)
        elif k == 'dragonDeath':
            if team.get(e['id']) != side_idx: continue
            la = last_action.get(e['id'])
            if la and la[0] == 'sprint' and la[1] == rnd:
                st['sprint_died_' + ['wall','self','body','headon','novalid'][e['reason']]] += 1
        elif k == 'sonarPing':
            s = e['sender']
            if team.get(s) != side_idx: continue
            st['pings'] += 1
            f = facing.get(s)
            if f is not None: st['ping_' + rel(f, e['dir'])] += 1
            st['hit_' + (e.get('hitKind') or 'none')] += 1
            sp = split_this_turn.get(s)
            if sp and sp[0] == rnd and e.get('hit') == sp[1]:
                st['ping_to_newborn'] += 1
    return st

def main():
    idx_path, root = sys.argv[1], sys.argv[2]
    idx = json.load(open(idx_path))
    per = collections.defaultdict(collections.Counter)
    seen = set()
    for g in idx:
        path = None
        for cand in glob.glob(os.path.join(root, '*', f"{g['game']}.replay")):
            path = cand
        if not path or (g['game'], g['side']) in seen: continue
        seen.add((g['game'], g['side']))
        try:
            st = profile(path, 0 if g['side'] == 'A' else 1)
        except Exception as ex:
            print('skip', path, ex); continue
        st['games'] += 1
        per[g['team']] += st
    print(f"{'team':24s} games  sprint/1k  s2/s3  sprintDeath(headon/other)  pings/turn  F/B/L/R%   hit ally/allyH/enemy/enemyH/kelp/none %   newborn")
    for t, st in sorted(per.items(), key=lambda kv: -kv[1]['games']):
        tt = max(st['turns'], 1); pp = max(st['pings'], 1)
        sd_h = st['sprint_died_headon']; sd_o = sum(v for k, v in st.items() if k.startswith('sprint_died_')) - sd_h
        fb = "/".join(f"{100*st['ping_'+c]/pp:.0f}" for c in "FBLR")
        hits = "/".join(f"{100*st['hit_'+c]/pp:.0f}" for c in ("ally","ally_head","enemy","enemy_head","kelp","none"))
        print(f"{t[:24]:24s} {st['games']:5d}  {1000*st['sprint']/tt:8.1f}  {st['sprint2']}/{st['sprint3']+st['sprint4']}  {sd_h:5d}/{sd_o:<5d}  {st['pings']/tt:9.2f}  {fb:14s} {hits:30s} {st['ping_to_newborn']}")
main()
