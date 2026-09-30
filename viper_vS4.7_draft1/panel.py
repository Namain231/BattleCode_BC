#!/usr/bin/env python3
"""panel.py A B [--maps m1,m2] [--seeds 1] [--out res.jsonl]  -- runs A vs B on both sides, parses winner."""
import subprocess, sys, re, json, argparse, time, os
ap=argparse.ArgumentParser()
ap.add_argument('A'); ap.add_argument('B')
ap.add_argument('--maps',default='arena,Colosseum,default_small,trophy,queen_of_spades,dilemma,devil,autarky')
ap.add_argument('--seeds',type=int,default=1); ap.add_argument('--out',default='res.jsonl')
ap.add_argument('--replays',default='')
a=ap.parse_args()
for seed in range(1,a.seeds+1):
    for m in a.maps.split(','):
        for side in (0,1):
            bots=(a.A,a.B) if side==0 else (a.B,a.A)
            cmd=['unswbc','run',f'maps/{m}.map',bots[0],bots[1],'--seed',str(seed)]
            if a.replays:
                os.makedirs(a.replays,exist_ok=True)
                cmd+=['-o',f'{a.replays}/{a.A}_vs_{a.B}_{m}_s{seed}_side{side}.replay']
            else: cmd+=['--no-replay']
            t0=time.time()
            try:
                r=subprocess.run(cmd,capture_output=True,text=True,timeout=1500)
                out=r.stdout+r.stderr
            except subprocess.TimeoutExpired:
                out='TIMEOUT'
            w=re.search(r'team ([AB]) wins after (\d+) rounds \((.*?)\)',out)
            d=re.search(r'draw',out)
            res={'map':m,'seed':seed,'side':side,'A_is':'A' if side==0 else 'B','secs':round(time.time()-t0)}
            if w:
                winner=w.group(1); res['rounds']=int(w.group(2)); res['how']=w.group(3)
                res['A_win']= (winner=='A')==(side==0)
            elif d: res['A_win']=None; res['how']='draw'
            else: res['A_win']=None; res['how']='ERR '+out[-200:].replace('\n',' | ')
            print(json.dumps(res),flush=True)
            open(a.out,'a').write(json.dumps(res)+'\n')
