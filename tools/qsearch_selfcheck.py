"""Differential tests of the actual WASI C++ simulator against engine_sim."""
import json, random, shutil, sys
from pathlib import Path
from unswbc import clangtool
from unswbc.sandbox import Sandbox, _metered
sys.path.insert(0,str(Path.cwd()/'tools'))
from engine_sim import load_map, apply_action
ROOT=Path.cwd(); work=ROOT/'out/qsearch_selfcheck';work.mkdir(parents=True,exist_ok=True)
rng=random.Random(96104);cases=[]
def add(bodies,path,pearls=(),extra='',actor=0,label='random',size=9):
    text=f'MAP {size} {size}\n'+extra+''.join(f'DRAGON {i%2} {len(b)} '+ ' '.join(f'{x} {y}' for x,y in b)+'\n' for i,b in enumerate(bodies))
    st=load_map(text);st.pearls=set(pearls);before=st.copy()
    apply_action(st,actor,{'act':'move','dirs':''.join('NESW'[d] for d in path)})
    cases.append((before,st,actor,path,label))
for k in range(240):
    occupied=set();bodies=[]
    for i in range(2):
        while True:
            x,y=rng.randrange(9),rng.randrange(9);axis=rng.randrange(2);length=rng.randrange(2,9)
            b=[((x-j*(axis==0))%9,(y-j*(axis==1))%9) for j in range(length)]
            if not occupied.intersection(b):break
        bodies.append(b);occupied.update(b)
    pearls=[(x,y) for x in range(9) for y in range(9) if (x,y) not in occupied and rng.random()<.15]
    add(bodies,[rng.randrange(4) for _ in range(rng.randrange(1,13))],pearls,actor=k%2)
add([[(3,3),(2,3)],[(4,3),(5,3),(6,3),(7,3),(8,3)]],[1],label='unequal-head')
add([[(3,3),(2,3)]],[3],label='own-tail')
add([[(3,3),(2,3)],[(4,4),(4,3)]],[1],label='other-tail')
add([[(3,3),(2,3),(1,3)]],[1,1,1,1],[(4,3),(5,3),(6,3)],label='free-paid-growth')
add([[(3,3),(2,3)]],[1,1],label='oversprint')
add([[(3,3),(2,3)]],[1],extra='EDGE 74 1 -1\n',label='kelp')
add([[(8,3),(7,3)]],[1],label='wrap')
add([[(3,3),(2,3)]],[1],extra='EDGE 74 2 1\nEDGE 116 2 1\n',label='portal')
add([[(3,3),(2,3)],[(6,3),(7,3),(8,3)]],[3,3,3],[(5,3)],actor=1,label='paid-ram')
add([[(3,3),(2,3)],[(5,4),(6,4),(7,4)]],[0,3],actor=1,label='blocking-sprint')
for h in ROOT.joinpath('viper_y96qh').glob('*.hpp'):shutil.copyfile(h,work/h.name)
source=(ROOT/'viper_y96qh/main.cpp').read_text(encoding='utf-8')
lines=['#undef main','int main(){double maxms=0;unsigned maxcharge=0;']
def ints(a):return '{'+','.join(map(str,a))+'}'
for k,(before,expected,actor,path,label) in enumerate(cases):
    n=before.board.width;cells=lambda ps:[y*n+x for x,y in ps]
    lines.append(f'{{ W=H={n};N=W*H; T0=chrono::steady_clock::now(); QSWorld w; w.occ.assign(N,0);w.pearl.assign(N,0);')
    lines.append('for(int c=0;c<N;c++){viewIndex[c]=0;for(int d=0;d<4;d++){obsK[c*4+d]=1;nbr[c*4+d]=stepRaw(c,d);}}')
    for c in range(n*n):
        for d in range(4):
            dest=before.board.neighbours[((c%n,c//n),d)]
            usual=((c%n+(d==1)-(d==3))%n,(c//n+(d==2)-(d==0))%n)
            if dest!=usual:
                lines.append(f'obsK[{c*4+d}]={2 if dest is None else 3};nbr[{c*4+d}]={-1 if dest is None else dest[1]*n+dest[0]};')
    for i,dr in before.dragons.items():lines.append(f'w.ds.push_back({{{i},{dr.facing},{ints(cells(dr.body))},true}});for(int c:w.ds.back().b)w.occ[c]={i+1};')
    for c in cells(before.pearls):lines.append(f'w.pearl[{c}]=1;')
    lines.append(f'QSClock t{{elapsedMs()}};bool ok=qsMove(w,{actor},{ints(path)},t);double ms=elapsedMs()-t.start;maxms=max(maxms,ms);maxcharge=max(maxcharge,t.charged);if(!ok){{printf("ABORT {k} %d\\n",t.reason);return 1;}}')
    # Compare every body's cells, alive, facing, and the entire pearl and occupancy arrays.
    for i,dr in expected.dragons.items():
        lines.append(f'if(w.ds[{i}].alive!={str(dr.alive).lower()} || w.ds[{i}].face!={dr.facing} || w.ds[{i}].b!=vector<int>{ints(cells(dr.body))}){{printf("STATE FAIL {k} {label} actor{i}\\n");return 2;}}')
    pearls=cells(expected.pearls);occ={c:i+1 for i,dr in expected.dragons.items() if dr.alive for c in cells(dr.body)}
    lines.append('vector<unsigned char> ep(N,0);')
    for c in pearls:lines.append(f'ep[{c}]=1;')
    lines.append('vector<int> eo(N,0);')
    for c,i in occ.items():lines.append(f'eo[{c}]={i};')
    lines.append(f'if(w.pearl!=ep || w.occ!=eo){{printf("BOARD FAIL {k} {label}\\n");return 3;}} }}')
lines.append(r'''
 W=H=16;N=256;for(int c=0;c<N;c++){viewIndex[c]=0;for(int d=0;d<4;d++){obsK[c*4+d]=1;nbr[c*4+d]=stepRaw(c,d);}}
 QSWorld w;w.occ.assign(N,0);w.pearl.assign(N,0);w.ds.push_back({0,0,{136,152},true});
 for(int i=1;i<=3;i++){
   vector<int>b;
   for(int col=0;b.size()<40;col++)for(int row=0;row<(i==2?7:8) && b.size()<40;row++){
     int x=i==1?6-col:(i==2?8+col:10+col);
     int y=i==2?(col%2?row:6-row):(col%2?15-row:8+row);
     b.push_back(y*16+x);
   }
   w.ds.push_back({i,i==2?2:0,b,true});
 }
 for(int i=0;i<4;i++)for(int c:w.ds[i].b)w.occ[c]=i+1;
 T0=chrono::steady_clock::now();QSClock t{elapsedMs()};vector<int> path;vector<vector<int>> replies;qsRams(w,1,0,path,replies,t);
 double ms=elapsedMs()-t.start;maxms=max(maxms,ms);maxcharge=max(maxcharge,t.charged);
 if(!t.aborted || replies.size()>40 || t.charged>QSClock::LIMIT)return 4;
 T0=chrono::steady_clock::now();QSClock exhausted{elapsedMs()};exhausted.charged=QSClock::LIMIT;
 if(qsMove(w,1,{1},exhausted) || !exhausted.aborted)return 5;
 // Complete-board gate and omitted/splitting-actor rejection.
 body={136,152};MY_LEN=2;MY_ID=0;MY_DIR=1;others.clear();V.parts.clear();fill(V.ptime,V.ptime+49,-1);
 Dragon enemy;enemy.id=1;enemy.headCell=134;enemy.headFace=1;enemy.visCount=enemy.estLen=40;enemy.tailKnown=true;others.push_back(enemy);
 T0=chrono::steady_clock::now();QSClock omitted{elapsedMs()};QSWorld built;vector<int> actors;
 if(qsBuild(built,actors,omitted) || omitted.reason!=QS_ACTORS)return 6;
 viewIndex[0]=-1;T0=chrono::steady_clock::now();QSClock unseen{elapsedMs()};
 if(qsBuild(built,actors,unseen) || unseen.reason!=QS_UNKNOWN)return 7;
 vector<vector<int>> capped(40);vector<int> cp;T0=chrono::steady_clock::now();QSClock cap{elapsedMs()};qsRams(w,1,0,cp,capped,cap);
 if(!cap.aborted || cap.reason!=QS_CAP || capped.size()!=40)return 10;
 viewIndex[0]=0;V.ptime[0]=1;T0=chrono::steady_clock::now();QSClock tick{elapsedMs()};
 if(qsBuild(built,actors,tick) || tick.reason!=QS_TICK)return 11;
 V.ptime[0]=-1;others[0].headCell=-1;T0=chrono::steady_clock::now();QSClock incomplete{elapsedMs()};
 if(qsBuild(built,actors,incomplete) || incomplete.reason!=QS_BODY)return 12;
 others[0].headCell=134;
 obsK[136*4+1]=0;KM=nullptr;T0=chrono::steady_clock::now();QSClock edge{elapsedMs()};
 if(qsMove(w,0,{1},edge) || edge.reason!=QS_UNKNOWN)return 13;
 obsK[136*4+1]=1;
 // Full call gates on a long-body enemy and on three threatening enemies.
 struct O {vector<int> dirs;SimResult sim;Eval ev;};vector<O> opts(2);opts[0].dirs={1};opts[1].dirs={0};opts[0].ev.pDeath=.5;opts[0].ev.score=2;opts[1].ev.score=1;
 viewIndex[0]=0;MY_TEAM=0;enemyPingNow=true;
 for(int trial=0;trial<2;trial++){
   if(trial){others.push_back(enemy);others.back().id=2;others.back().headCell=104;others.push_back(enemy);others.back().id=3;others.back().headCell=138;}
   T0=chrono::steady_clock::now();double begin=elapsedMs();
   if(queenSearch(opts) || opts[0].dirs!=vector<int>{1})return 9;
   maxms=max(maxms,elapsedMs()-begin);
 }
 // Fully eligible three-actor search must exhaust its budget without a swap.
 others.clear();V.parts.clear();MY_DIR=0;
 int heads[3]={134,104,138},faces[3]={2,3,0},backs[3]={-16,1,16};
 for(int i=0;i<3;i++){
   Dragon dr;dr.id=i+1;dr.team=1;dr.headCell=heads[i];dr.headFace=faces[i];dr.visCount=dr.estLen=3;dr.tailKnown=true;others.push_back(dr);
   for(int j=0;j<3;j++)V.parts.push_back({1,i+1,heads[i]+j*backs[i],faces[i],j==0});
 }
 T0=chrono::steady_clock::now();double begin=elapsedMs();unsigned aborts=qsStats.reject[QS_BUDGET];
 bool swapped=queenSearch(opts);
 if(swapped || opts[0].dirs!=vector<int>{1} || qsStats.reject[QS_BUDGET]<=aborts){printf("FAIL stress e%u body%u unknown%u budget%u cap%u actors%u\n",qsStats.eligible,qsStats.reject[QS_BODY],qsStats.reject[QS_UNKNOWN],qsStats.reject[QS_BUDGET],qsStats.reject[QS_CAP],qsStats.reject[QS_ACTORS]);return 14;}
 maxms=max(maxms,elapsedMs()-begin);maxcharge=max(maxcharge,qsStats.chargedMax);
 printf("PASS differential RANDOM=240 HAND=10 fallback=5 replycap=1 budget=2 adversarial=4 max_call_ms=%.3f charge=%u overshoot=0 added_points_max=%.0f\n",maxms,maxcharge,maxms*1000000);
 return maxms>4 ? 8:0;}
''')
(work/'main.cpp').write_text('#define main original_bot_main\n'+source+'\n'+'\n'.join(lines),encoding='utf-8')
wasm=clangtool.build(work)
box=Sandbox(wasm_path=_metered(wasm,work),root=clangtool.toolchain()/'root',mounts={'/src':work},cwd='/src',argv=['/src/check'],needs_zygote=False,needs_meter=True,max_pages=768)
status=box.run();output=bytes(box.stdout).decode('utf-8','replace');print(output,end='')
assert status==0,(status,bytes(box.stderr).decode('utf-8','replace'))
import re
result={k:(float(v) if '.' in v else int(v)) for k,v in re.findall(r'(\w+)=(\d+(?:\.\d+)?)',output)}
for directory in ('viper_y96qh','viper_y96qh_off','viper_y96qh_dbg'):
    (ROOT/directory/'selfcheck_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

