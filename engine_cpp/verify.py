"""Export Python simulation snapshots then compare C++ on the SAME actions.
Export needs replay_lite/unswbc; comparison needs only Python stdlib.
"""
import argparse, ctypes as C, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from engine_sim import load_map,step,SpawnInput

def snapshot(s):
    w=s.board.width
    return {'round':s.round,'over':int(s.over),'winner':2 if s.winner is None else s.winner,
            'dragons':{str(i):[d.team,d.facing,[y*w+x for x,y in d.body]] for i,d in s.dragons.items() if d.alive},
            'deaths':{str(i):d.death for i,d in s.dragons.items() if not d.alive},
            'pearls':[int((x,y) in s.pearls) for y in range(s.board.height) for x in range(w)],
            'countdowns':[s.countdowns[x,y] for y in range(s.board.height) for x in range(w)]}

def export(paths,out):
    from replay_lite import decode_lite
    from engine_sim_test import KINDS,replay_update,check_game
    out.mkdir(parents=True,exist_ok=True)
    reports=[]
    for path in paths:
        report=check_game(path);reports.append(report); print(json.dumps(report),flush=True)
        if report['matching']!=report['rounds']: raise RuntimeError('Python oracle mismatch')
        rep=decode_lite(path,KINDS);s=load_map(rep['map']); rounds=[]
        for e in rep['events']:
            if e['kind']=='roundStart': rounds.append((e['round'],[]))
            elif rounds: rounds[-1][1].append(e)
            else: replay_update(s,e,initial=True)
        w=s.board.width
        with (out/(Path(path).stem+'.jsonl')).open('w',encoding='utf-8') as f:
            f.write(json.dumps({'map':rep['map'],'initial':snapshot(s)})+'\n')
            for r,events in rounds:
                prefix=next((i for i,e in enumerate(events) if e['kind']=='turnStart'),len(events))
                pre=events[:prefix]; turn=events[prefix:]
                sp=SpawnInput({e['tile'] for e in pre if e['kind']=='tileChange' and e['pearl']},
                              {e['tile']:e['countdown'] for e in pre if e['kind']=='pearlCountdown'})
                actions={e['id']:e for e in turn if e['kind']=='dragonAction'}
                s=step(s,actions,sp)
                f.write(json.dumps({'round':r,'spawn':[y*w+x for x,y in sp.pearls],
                    'reset':{str(y*w+x):v for (x,y),v in sp.countdowns.items()},
                    'actions':actions,'turns':[e['id'] for e in turn if e['kind']=='turnStart'],
                    'expected':snapshot(s)})+'\n')
    (out/'python_oracle.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')

def compare(libpath,fixtures,expected_games=4):
    lib=C.CDLL(str(libpath));ip=C.POINTER(C.c_int);vp=C.c_void_p
    signatures={'check_create':([C.c_char_p],vp),'check_destroy':([vp],None),
                'check_seeded_initial':([vp,ip],C.c_int),'check_init':([vp,ip],None),'check_round':([vp,C.c_int,ip,ip,C.c_int],None),
                'check_seeded_round':([vp,C.c_int],None),'check_next':([vp],C.c_int),'check_act':([vp,C.c_int,C.c_int,C.c_char_p],None),
                'check_dump':([vp,ip],C.c_int)}
    for name,(a,r) in signatures.items():getattr(lib,name).argtypes=a;getattr(lib,name).restype=r
    def ints(x):return (C.c_int*len(x))(*x)
    reports=[]
    for path in sorted(fixtures.glob('*.jsonl')):
        matched=total=0;first=None
        with path.open(encoding='utf-8') as f:
            initial=json.loads(next(f));p=lib.check_create(initial['map'].encode());assert p
            cd=initial['initial']['countdowns'];cells=len(cd)
            if initial.get('seeded'):assert lib.check_seeded_initial(p,ints(cd))==0, 'seeded initial countdown mismatch'
            else:lib.check_init(p,ints(cd))
            try:
                for line in f:
                    row=json.loads(line);total+=1
                    resets=[-2147483647]*cells
                    for k,v in row['reset'].items():resets[int(k)]=v
                    if row.get('seeded'):lib.check_seeded_round(p,row['round'])
                    else:lib.check_round(p,row['round'],ints(resets),ints(row['spawn']),len(row['spawn']))
                    turns=[]
                    while (i:=lib.check_next(p))>=0:
                        turns.append(i);a=row['actions'].get(str(i),{})
                        kind={'move':1,'split':2}.get(a.get('act'),0)
                        lib.check_act(p,kind,a.get('size',0),a.get('dirs','').encode())
                    buf=(C.c_int*30000)();size=lib.check_dump(p,buf);it=iter(buf[:size])
                    actual={'round':next(it),'over':next(it),'winner':next(it)};overflow=next(it);assert overflow==0
                    ds={}
                    for _ in range(next(it)):
                        i,team,facing,length=next(it),next(it),next(it),next(it)
                        ds[str(i)]=[team,facing,[next(it) for _ in range(length)]]
                    actual['dragons']=ds;deaths={}
                    for _ in range(next(it)):
                        dead_id,reason=next(it),next(it)
                        deaths[str(dead_id)]=reason
                    actual['deaths']=deaths
                    actual['pearls']=[next(it) for _ in range(cells)]
                    actual['countdowns']=[next(it) for _ in range(cells)]
                    diff=next((k for k in actual if actual[k]!=row['expected'][k]),None)
                    if turns!=row['turns']:diff='turn order'
                    if diff is None:matched+=1
                    elif first is None:
                        first={'round':row['round'],'field':diff}
                        if diff in ('deaths','dragons'):
                            first['actual']=actual[diff];first['expected']=row['expected'][diff]
            finally:lib.check_destroy(p)
        report={'game':path.stem,'matched':matched,'rounds':total,'first_divergence':first}
        reports.append(report);print(json.dumps(report),flush=True)
    summary={'matched':sum(r['matched'] for r in reports),'rounds':sum(r['rounds'] for r in reports),'games':reports}
    (fixtures/'cpp_parity.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k!='games'}))
    return 0 if len(reports)==expected_games and summary['matched']==summary['rounds'] and summary['rounds']>0 else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('paths',nargs='*',type=Path);p.add_argument('--export',type=Path)
    p.add_argument('--library',type=Path);p.add_argument('--fixtures',type=Path);a=p.parse_args()
    if a.export:
        paths=[f for q in a.paths for f in (sorted(q.glob('*.replay')) if q.is_dir() else [q])]
        if len(paths)!=4:raise SystemExit('Need exactly four replay files; zero/skips are not a pass')
        export(paths,a.export)
    else:sys.exit(compare(a.library,a.fixtures))
