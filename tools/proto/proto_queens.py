"""proto_rehaul: every dragon that was queen (indicator Q), its reign, length and how it ended.

    python tools/proto/proto_queens.py REPLAY [REPLAY ...]
"""
import os, sys, re, collections; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from replay import load
DEATHS = ["wall", "self", "otherbody", "headon", "novalid"]
def track(path):
    mine = 0 if path.endswith('_A.replay') else 1
    rep=load(path); team={}; nid=0
    for line in rep['map'].splitlines():
        p=line.split()
        if p and p[0]=='DRAGON': team[nid]=int(p[1]); nid+=1
    q={}; rnd=0; last={}
    for e in rep['events']:
        k=e['kind']
        if k=='roundStart': rnd=e['round']
        elif k=='dragonSplit': team[e['child']]=e['team']
        elif k=='dragonIndicator' and team.get(e['id'])==mine:
            m=re.match(r"([WQF])(\d+) ?(.*)", e['text'] or '')
            if not m: continue
            last[e['id']]=(m.group(1),int(m.group(2)),m.group(3))
            if m.group(1)=='Q':
                d=q.setdefault(e['id'],{'from':rnd,'to':rnd,'L0':int(m.group(2)),'L':0,'end':'alive'})
                d['to']=rnd; d['L']=int(m.group(2))
        elif k=='dragonDeath' and e['id'] in q:
            q[e['id']]['end']=DEATHS[e['reason']]+':'+last[e['id']][0]+last[e['id']][2][:12]
    return q
for p in sys.argv[1:]:
    q=track(p)
    spans=sorted(q.items(), key=lambda kv: -(kv[1]['to']-kv[1]['from']))
    ends=collections.Counter(v['end'].split(':')[0] for v in q.values())
    print(p.split('/')[-1], len(q), 'queens; ends', dict(ends))
    for i,v in spans[:6]: print('   ',i,v)
