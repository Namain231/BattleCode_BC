"""proto_rehaul: death causes of our dragons keyed by the last indicator text (why it was doing what it did).

    python tools/proto/proto_deaths.py REPLAY [REPLAY ...]     (side from the _A/_B filename suffix)
"""
import os, sys, collections; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from replay import load
DEATHS = ["wall", "self", "otherbody", "headon", "novalid"]
def diag(path, mine):
    rep=load(path); last={}; team={}; nid=0
    for line in rep['map'].splitlines():
        p=line.split()
        if p and p[0]=='DRAGON': team[nid]=int(p[1]); nid+=1
    c=collections.Counter()
    for e in rep['events']:
        k=e['kind']
        if k=='dragonSplit': team[e['child']]=e['team']
        elif k=='dragonIndicator': last[e['id']]=e['text']
        elif k=='dragonDeath' and team.get(e['id'])==mine:
            t=(last.get(e['id']) or '?').split(' ',1)
            c[(DEATHS[e['reason']], t[1] if len(t)>1 else t[0])]+=1
    return c
tot=collections.Counter()
for p in sys.argv[1:]:
    tot+=diag(p, 0 if p.endswith('_A.replay') else 1)
for k,v in tot.most_common(25): print(v,k)
