import json,sys
from collections import defaultdict
files=sys.argv[1:]
maps=['arena','Colosseum','default_small','trophy','queen_of_spades','dilemma','devil']
T={}
for f in files:
    d=defaultdict(lambda:[0,0])
    try:
        for l in open(f):
            r=json.loads(l)
            if r['A_win'] is None: continue
            d[r['map']][1]+=1; d[r['map']][0]+=1 if r['A_win'] else 0
    except FileNotFoundError: pass
    T[f]=d
print(f"{'map':16}"+''.join(f'{f[:14]:>16}' for f in files))
for m in maps:
    print(f'{m:16}'+''.join(f'{T[f][m][0]:>10}/{T[f][m][1]:<5}' for f in files))
print(f"{'TOTAL':16}"+''.join(f'{sum(v[0] for v in T[f].values()):>10}/{sum(v[1] for v in T[f].values()):<5}' for f in files))
