"""Private, resumable paired game farm. No remote calls or LLMs."""
import argparse, concurrent.futures as CF, csv, hashlib, json, math, os
from pathlib import Path
import shutil, statistics as S, subprocess, sys, threading, time, uuid
ROOT = Path(__file__).absolute().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / 'tools'))
import panel_zig as panel
from opening_census import analyse as opening
from replay_lite import decode_lite

LIVE = 'around_unsw australia autarky default devil islands maze portals dilemma queen_of_spades schooltime slithery_fight stripes tower_defense trauma trophy weakhold'.split()
LABELS = dict(around_unsw='Around UNSW', australia='Australia', autarky='Autarky',
 default='Default', devil='Devil', islands='Islands', maze='Maze', portals='Portals',
 dilemma='Prisoners Dilemma', queen_of_spades='Queen Of Spades', schooltime='Schooltime',
 slithery_fight='Slithery Fight', stripes='Stripes', tower_defense='Tower Defense',
 trauma='Trauma', trophy='Trophy', weakhold='weakhold')
METRICS = ['units50','units100','length100','first_split','eats_rate']
decode_lock = threading.Lock()
def atomic(path, value):
    tmp = path.with_suffix(path.suffix + f'.tmp-{os.getpid()}-{threading.get_ident()}')
    tmp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(tmp, path)
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def source_hash(root):
    return {str(p.relative_to(root)).replace('\\','/'):digest(p)
            for p in sorted(root.rglob('*')) if p.is_file() and p.suffix in {'.c','.cxx','.cpp','.cc','.hpp','.h','.toml'}}

def map_queens(path):
    teams=[int(line.split()[1]) for line in path.read_text().splitlines() if line.startswith('DRAGON ')]
    return [min(i for i,t in enumerate(teams) if t==side) for side in (0,1)]

def validate(row, job, queens=None):
    if any(row.get(k)!=v for k,v in job.items()): raise ValueError('checkpoint job mismatch')
    expected=set(job)|set(METRICS)|{'winner','win','rounds','queen_id','queen_death_round','cpu_max_M','cpu_max_opponent_M','seconds','lane','unknown_eats','started','ended'}
    if set(row)!=expected: raise ValueError('checkpoint schema mismatch')
    for k in set(METRICS)|{'rounds','cpu_max_M','cpu_max_opponent_M','win','seconds','unknown_eats','started','ended'}:
        v=row[k]
        if k=='first_split' and v is None: continue
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:
            raise ValueError('invalid metric '+k)
    for k in ['units50','units100','length100','rounds','unknown_eats','first_split']:
        if row[k] is not None and type(row[k]) is not int: raise ValueError('Noninteger '+k)
    side=0 if job['side']=='A' else 1
    if queens is None:
        mp=job['map']; queens=map_queens(ROOT/(mp+'.map' if '/' in mp else 'maps/'+mp+'.map'))
    if row['queen_id']!=queens[side]: raise ValueError('Wrong queen ownership')
    if row['winner'] not in ('A','B','-') or row['win'] != (.5 if row['winner']=='-' else float(row['winner']==job['side'])): raise ValueError('invalid winner')
    if type(row['queen_id']) is not int or row['queen_id'] not in (0,1) or row['rounds']>500 or row['ended']<row['started'] or not isinstance(row['lane'],str): raise ValueError('invalid result')
    d=row['queen_death_round']
    if d is not None and (isinstance(d,bool) or not isinstance(d,int) or not 0<=d<=row['rounds']): raise ValueError('invalid queen death')
    return row

def seal_inputs(stage):
    files=[stage/'manifest.json',stage/'jobs.json',stage/'engine.wasm',stage/'loong-judge',stage/'out/opening_census.txt',stage/'artifacts.json']
    for folder in ['bots','tools','farm','maps','maps_rm_dev','shards']:
        files.extend(p for p in (stage/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return {p.relative_to(stage).as_posix():digest(p) for p in sorted(set(files))}

def verify_seal(stage):
    seal=stage/'bundle_seal.json'
    if not seal.exists():
        if any((stage/'state').glob('*.json')): raise ValueError('Unsealed checkpoint state')
        return
    if json.loads(seal.read_text())!=seal_inputs(stage): raise ValueError('Mixed-version or corrupted bundle')
    manifest=json.loads((stage/'manifest.json').read_text())
    for name,expected in manifest['dependencies'].items():
        if digest(stage/name)!=expected: raise ValueError('Dependency/manifest mismatch '+name)
    if digest(stage/'loong-judge')!=manifest['judge_hash'] or digest(stage/'engine.wasm')!=manifest['engine_hash']: raise ValueError('Executable/manifest mismatch')
    for name,expected in json.loads((stage/'artifacts.json').read_text()).items():
        if digest(stage/'bots'/f'{name}.wasm')!=expected: raise ValueError('Bot artifact mismatch')

def checkpoints(stage):
    jobs=json.loads((stage/'jobs.json').read_text()); expected={j['id']:j for j in jobs}
    if len(expected)!=len(jobs): raise ValueError('duplicate job IDs')
    manifest=json.loads((stage/'manifest.json').read_text())
    rows=[]
    for p in sorted((stage/'state').glob('*.json')):
        if p.stem not in expected: raise ValueError('extra checkpoint '+str(p))
        row=json.loads(p.read_text())
        rows.append(validate(row,expected[p.stem],manifest['map_queens'][row['map']]))
    return rows

def guard(stage):
    if not os.environ.get('FARM_REMOTE') and shutil.disk_usage('C:/' if os.name == 'nt' else '/mnt/c').free < 3 * 1024**3:
        raise RuntimeError('C: free space below 3 GiB; stopped safely')
    if shutil.disk_usage(stage).free < 2 * 1024**3:
        raise RuntimeError('F: staging free space below 2 GiB')
def memory_guard(workers=1):
    minimum=max(3000,1500+workers*600)
    if os.name == 'nt':
        cmd = ['powershell','-NoProfile','-Command',
          '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory']
        while int(subprocess.check_output(cmd, text=True).strip()) < minimum*1024:
            time.sleep(20)
    else:
        available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))
        if available < minimum*1024: raise RuntimeError('Insufficient available RAM for worker fan-out')
def queen_info(path, side):
    # Post-2026-10-01 queens are fixed starting IDs 0/1, never indicator-derived.
    rep = decode_lite(str(path), {'roundStart','dragonDeath'})
    teams = {}
    for line in rep['map'].splitlines():
        p = line.split()
        if p and p[0] == 'DRAGON': teams[len(teams)] = int(p[1])
    qid=min(i for i,t in teams.items() if t==side)
    if qid not in (0,1): raise ValueError('Map violates alternating starting queen IDs')
    rnd,death=-1,None
    for e in rep['events']:
        if e['kind']=='roundStart': rnd=e['round']
        elif e['kind']=='dragonDeath' and e['id']==qid: death=rnd
    return rep['result'].get('winner'), qid, death
def evaluate(job, stage):
    guard(stage)
    target = stage/'state'/f"{job['id']}.json"
    if target.exists(): return validate(json.loads(target.read_text()),job,json.loads((stage/'manifest.json').read_text())['map_queens'][job['map']])
    d = stage/'scratch'/(job['id']+'-'+uuid.uuid4().hex); d.mkdir(parents=True, exist_ok=True)
    start=time.monotonic(); epoch=time.time()
    ours=str(stage/'bots'/f"{job['arm']}.wasm")
    opp=str(stage/'bots'/f"{job['opponent']}.wasm")
    replay, msg = panel.play(ours, opp, job['map'], job['seed'], job['side'], str(d), lease=str(stage/'scratch'/(job['id']+'.lease')))
    p=Path(replay)
    if not p.exists() or not Path(replay+'.cpu.json').exists():
        raise RuntimeError(f"{job['id']}: judge failed or CPU missing: {msg[-300:]}")
    # At most one memory-heavy decoder; games remain capped at six.
    with decode_lock:
        row=opening(dict(path=p, group='farm', side=0 if job['side']=='A' else 1, map=job['map']))
        if row['validation']['final_body_parity']!=1: raise ValueError('Replay body parity failed')
        winner,qid,death=queen_info(p, row['side'])
    cpu=json.loads(Path(replay+'.cpu.json').read_text())
    result={**job, **{k:row[k] for k in METRICS},
      'winner': '-' if winner is None else 'AB'[winner],
      'win': .5 if winner is None else float(winner==row['side']),
      'rounds':row['last_round'], 'queen_id':qid, 'queen_death_round':death,
      'cpu_max_M':cpu[job['side']], 'cpu_max_opponent_M':cpu['B' if job['side']=='A' else 'A'],
      'seconds':time.monotonic()-start, 'lane':os.environ.get('FARM_LANE','local'),
      'unknown_eats':row['unknown_eats'], 'started':epoch, 'ended':time.time()}
    validate(result,job)
    atomic(target,result) # durable checkpoint BEFORE discarding replay
    for f in d.iterdir(): f.unlink()
    d.rmdir()
    return result
def wilson(values):
    n=len(values); p=sum(values)/n; z=1.96
    c=(p+z*z/(2*n))/(1+z*z/n)
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return p,c-h,c+h
def bounds(values):
    if len(values)<2: return None
    mean=S.mean(values)
    df=len(values)-1
    critical=[12.706,4.303,3.182,2.776,2.571,2.447,2.365,2.306,2.262,2.228,2.201,2.179,2.160,2.145,2.131,2.120,2.110,2.101,2.093,2.086,2.080,2.074,2.069,2.064,2.060,2.056,2.052,2.048,2.045,2.042]
    t=critical[df-1] if df<=30 else 1.96+(1.96**3+1.96)/(4*df)
    h=t*S.stdev(values)/math.sqrt(len(values))
    return mean,mean-h,mean+h

def estimate(values):
    if not values: return 'NA'
    ci=bounds(values)
    return f'{ci[0]:.3f} [{ci[1]:.3f}, {ci[2]:.3f}]' if ci else f'{S.mean(values):.3f} (CI NA)'
def family(mp):
    return 'live:'+mp if '/' not in mp else panel.family(mp.replace('/','+'))
def summarize(stage, rows=None):
    if rows is None: rows=checkpoints(stage)
    fields=['id','arm','opponent','map','seed','side','winner','rounds',*METRICS,
      'queen_id','queen_death_round','cpu_max_M','cpu_max_opponent_M','win','seconds','lane','unknown_eats','started','ended']
    with (stage/'results.tsv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fields,delimiter='\t');w.writeheader();w.writerows(rows)
    paired={}
    for r in rows: paired.setdefault((r['opponent'],r['map'],r['seed'],r['side']),{})[r['arm']]=r
    pairs=[v for v in paired.values() if set(v)=={'candidate','sv53'}]
    lines=['# Farm metrics','',f'Completed {len(rows)} evaluations; {len(pairs)} complete paired seeds/sides.',
      'Primary: self-driven opening metrics; league wins are secondary safety evidence.',
      'Top-team census is winners-only observational data, not a promotion threshold.',
      'Queen: fixed lowest initial friendly ID (0/1); alive queen has no death round.',
      'Opening snapshots use start-of-round states; early terminal state carries forward.',
      'Paired CIs below use seed clusters (both sides/opponents together), Student t approximation.',
      '', '## Primary opening metrics: candidate minus Sv5.3']
    census={}
    for line in (ROOT/'out/opening_census.txt').read_text(encoding='utf-8').splitlines():
        p=[s.strip() for s in line.split('|')]
        if len(p)==8 and p[0] in LABELS.values():
            census[p[0]]=[float(x.split('/')[1]) for x in p[2:7]]
    for mp in sorted({v['candidate']['map'] for v in pairs}):
        ps=[v for v in pairs if v['candidate']['map']==mp]
        lines.append(f'### {mp}: {len(ps)} pairs')
        for k in METRICS:
            valid=[v for v in ps if v['candidate'][k] is not None and v['sv53'][k] is not None]
            clusters={}
            for v in valid:
                clusters.setdefault(v['candidate']['seed'],[]).append(v['candidate'][k]-v['sv53'][k])
            vals=[S.mean(xs) for xs in clusters.values()]
            cv=[v['candidate'][k] for v in ps if v['candidate'][k] is not None]
            med=S.median(cv) if cv else None
            benchmark=census.get(LABELS.get(mp,''),[None]*5)[METRICS.index(k)]
            lines.append(f'- {k}: candidate median {med}; top median {benchmark}; paired delta {estimate(vals)}; n={len(valid)}')
        lines.append(f"- Never split: candidate {sum(v['candidate']['first_split'] is None for v in ps)}, Sv5.3 {sum(v['sv53']['first_split'] is None for v in ps)}")
    lines+=['','## Opening metrics by map family']
    for fam in sorted({family(v['candidate']['map']) for v in pairs}):
        ps=[v for v in pairs if family(v['candidate']['map'])==fam]
        for k in METRICS:
            clusters={}
            for v in ps:
                c,b=v['candidate'][k],v['sv53'][k]
                if c is not None and b is not None: clusters.setdefault(v['candidate']['seed'],[]).append(c-b)
            lines.append(f'- {fam}, {k}: paired delta {estimate([S.mean(x) for x in clusters.values()])}')
    lines+=['','## Secondary safety: win rates (Wilson 95% intervals; draws half-credit)']
    for group in ['opponent','family']:
        keys=sorted({r['opponent'] if group=='opponent' else family(r['map']) for r in rows})
        for key in keys:
            rs=[r for r in rows if (r['opponent'] if group=='opponent' else family(r['map']))==key]
            for arm in ['candidate','sv53']:
                values=[r['win'] for r in rs if r['arm']==arm]
                if values:
                    p,lo,hi=wilson(values)
                    lines.append(f'- {group} {key}, {arm}: n={len(values)}, {p:.1%} [{lo:.1%}, {hi:.1%}]; achieved half-width {(hi-lo)/2:.2%}')
            ps=[v for v in pairs if (v['candidate']['opponent'] if group=='opponent' else family(v['candidate']['map']))==key]
            clusters={}
            for v in ps: clusters.setdefault(v['candidate']['seed'],[]).append(v['candidate']['win']-v['sv53']['win'])
            vals=[S.mean(x) for x in clusters.values()]
            ci=bounds(vals)
            status='REGRESSION: upper bound below zero' if ci and ci[2]<0 else 'no statistically resolved drop; safety remains unproven' 
            lines.append(f'- Paired win delta: {estimate(vals)}; {status}.')
    intervals=sorted((r['started'],r['ended']) for r in rows if 'started' in r)
    seconds=0; end=0
    for a,b in intervals:
        seconds+=max(0,b-max(a,end));end=max(end,b)
    timing={'seconds':seconds,'games':len(intervals)}
    if not intervals and (stage/'timing.json').exists():
        timing=json.loads((stage/'timing.json').read_text());seconds=timing['seconds']
    hours=seconds/3600
    lines+=['','## Throughput and precision',
      f"All measured lanes combined: {timing['games'] / hours if hours else 0:.1f} games/hour over {timing['games']} games and {hours:.3f} active hours.",
      'Remote lanes OFF by default; default precision budget is 2.2 pp pooled nominal; use --precision-pp for per-opponent sizing.',
      *[f'{lane}: '+lane_rate(rows,lane) for lane in sorted({r['lane'] for r in rows})],
      'At n=2000 independent games, worst-case binomial 95% half-width is about 2.19 percentage points; actual per-group intervals above. Shared seeds induce dependence.',
      'No automatic promotion; assess opening metrics and paired safety intervals.']
    (stage/'farm_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (ROOT/'out/farm_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return len(rows),len(pairs)
def lane_rate(rows,lane):
    intervals=sorted((r['started'],r['ended']) for r in rows if r['lane']==lane and 'started' in r)
    seconds=0;end=0
    for a,b in intervals:
        seconds+=max(0,b-max(a,end));end=max(end,b)
    return f'{len(intervals)*3600/seconds:.1f} games/hour ({len(intervals)} games)' if seconds else 'unmeasured (legacy timestamps absent)'
def search_log_restore(log, stage, name, rows):
    # The validated per-game JSON is authoritative; repair missed/duplicate log rows.
    existing=[]
    if log.exists():
        with log.open(encoding='utf-8',newline='') as fh:
            existing=[r for r in csv.DictReader(fh,delimiter='\t') if r.get('stage')!=stage.name]
    rebuilt=[dict(stage=stage.name,candidate=name,**r) for r in rows]
    allrows=existing+rebuilt
    if not allrows: return
    fields=['stage','candidate','id','arm','opponent','map','seed','side','winner','win','rounds','units50','units100','length100','first_split','eats_rate','queen_id','queen_death_round','cpu_max_M','cpu_max_opponent_M','seconds','lane','unknown_eats','started','ended']
    tmp=log.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8',newline='') as fh:
        writer=csv.DictWriter(fh,fieldnames=fields,delimiter='\t');writer.writeheader();writer.writerows(allrows)
        fh.flush();os.fsync(fh.fileno())
    os.replace(tmp,log)

def search_stop(rows, alpha, maps=None, opponent_count=None, seed_offset=0):
    # Union-bound Hoeffding confidence sequence on independent complete seed clusters.
    # Shared sides/maps/opponents are one observation; incomplete seeds excluded.
    if any(r['arm']=='candidate' and r['cpu_max_M']>66 for r in rows):
        return 'CPU peak exceeds 66M'
    by={}
    for r in rows: by.setdefault((r['seed'],r['map'],r['opponent'],r['side']),{})[r['arm']]=r
    for group in ['Y9_6','league']:
        seeds={}
        for key, arms in by.items():
            if set(arms)!= {'candidate','sv53'}: continue
            if (key[2]=='Y9_6') != (group=='Y9_6'): continue
            seeds.setdefault(key[0],[]).append(arms['candidate']['win']-arms['sv53']['win'])
        # Inspect only balanced complete map cycles; prefixes may bias the map objective.
        count=opponent_count or len({r['opponent'] for r in rows})
        expected=2 if group=='Y9_6' else 2*(count-1)
        width=len(maps) if maps else 1
        cycles={}
        for seed,v in seeds.items():
            if len(v)==expected: cycles.setdefault((seed-1-seed_offset)//width,[]).append(S.mean(v))
        vals=[x for cycle in cycles.values() if len(cycle)==width for x in cycle]
        n=len(vals)
        if n:
            radius=math.sqrt(2*math.log(2*n*(n+1)/alpha)/n)
            if S.mean(vals)+radius<0: return group+' win regression at anytime 95% confidence'
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('candidate');ap.add_argument('--games',type=int,default=2000)
    ap.add_argument('--precision-pp',type=float,default=None,help='nominal independent per-opponent Wilson half-width target; e.g. 1 requires >=9604/opponent')
    ap.add_argument('--control',default='out/sv53_pkg')
    ap.add_argument('--stage',default='F:/BattleCode_data/farm_scale' if os.name=='nt' else '/mnt/f/BattleCode_data/farm_scale')
    ap.add_argument('-j',type=int,default=6)
    ap.add_argument('--search-stop-alpha',type=float,default=None)
    ap.add_argument('--search-limit',type=int,default=None)
    ap.add_argument('--search-seed-offset',type=int,default=0)
    ap.add_argument('--search-log',default=None)
    ap.add_argument('--plan-only',action='store_true')
    ap.add_argument('--pack-only',action='store_true')
    ap.add_argument('--collect-only',action='store_true')
    ap.add_argument('--import-results',help='directory containing returned private bundle state JSONs')
    a=ap.parse_args()
    if a.search_stop_alpha is not None and not 0<a.search_stop_alpha<1: ap.error('alpha must be in (0,1)')
    if a.games<1 or not 1<=a.j<=6: ap.error('games >=1; workers 1..6')
    candidate=Path(a.candidate).resolve()
    if not (candidate/'bot.toml').is_file(): ap.error('candidate needs bot.toml')
    stage=Path(a.stage); stage.mkdir(parents=True,exist_ok=True); guard(stage)
    maps=LIVE+[str(p.with_suffix('')).replace('\\','/') for p in sorted(Path('maps_rm_dev').glob('*.map'))]
    if a.search_stop_alpha is not None:
        closed=['stripes','tower_defense','queen_of_spades','dilemma']
        maps=closed+[m for m in maps if m not in closed]
    opponents={'Y9_6':Path('baselines/Y9_6')}
    opponents.update({p.name:p for p in sorted(Path('league').glob('team_*')) if (p/'bot.toml').exists()})
    bots={'candidate':candidate,'sv53':Path(a.control).resolve(),**opponents}
    if a.precision_pp is not None:
        if not 0<a.precision_pp<50: ap.error('precision-pp must be between 0 and 50')
        a.games=max(a.games,len(opponents)*math.ceil(1.96**2/(4*(a.precision_pp/100)**2)))
    from unswbc import clangtool
    compiler=clangtool.toolchain()
    compiler_hash={p.relative_to(compiler).as_posix():digest(p) for p in sorted(compiler.rglob('*')) if p.is_file()}
    dependencies=['tools/farm_scale.py','tools/panel_zig.py','tools/opening_census.py','tools/replay_lite.py','tools/replay.py','tools/engine_sim.py','tools/buildwasm.py','farm/worker.py','out/opening_census.txt']
    identity={'dependencies':{n:digest(ROOT/n) for n in dependencies},'engine_hash':digest(Path(panel.ENGINE)),'schedule_version':3,'search_stop_alpha':a.search_stop_alpha,'search_seed_offset':a.search_seed_offset,'games':a.games,'precision_pp':a.precision_pp,'map_hashes':{mp:digest(ROOT/(mp+'.map' if '/' in mp else 'maps/'+mp+'.map')) for mp in maps},'maps':maps,'map_queens':{mp:map_queens(ROOT/(mp+'.map' if '/' in mp else 'maps/'+mp+'.map')) for mp in maps},'bots':{k:source_hash(v) for k,v in bots.items()}}
    identity['compiler']=compiler_hash
    identity['compiler_driver']=digest(Path(clangtool.__file__))
    if os.name=='nt':
        judge=panel._wslpath(panel.JUDGE) if os.environ.get('LOONG_JUDGE') else '/home/'+subprocess.check_output(['wsl','-d',panel.WSL_DISTRO,'--','whoami'],text=True).strip()+'/toolchains/zig-judge-out/bin/loong-judge'
        identity['judge_hash']=subprocess.check_output(['wsl','-d',panel.WSL_DISTRO,'--','sha256sum',judge],text=True).split()[0]
    else: identity['judge_hash']=digest(Path(panel.JUDGE))
    stage=stage/(candidate.name+'-'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:12])
    stage.mkdir(exist_ok=True)
    for name in ['state','shards','bots','scratch']: (stage/name).mkdir(exist_ok=True)
    atomic(stage/'manifest.json',identity)
    # Round-robin opponents/maps; complete both sides, even for odd requested counts.
    schedule=[(o,m) for o in opponents for m in maps]
    jobs=[]
    for i in range(math.ceil(a.games/2)):
        opp=list(opponents)[i%len(opponents)]; mp=maps[(i//len(opponents))%len(maps)]; seed=1+i//(len(opponents)*len(maps))
        if a.search_stop_alpha is not None: seed=1+a.search_seed_offset+i//len(opponents)
        for side in 'AB':
            for arm in ['candidate','sv53']:
                jobs.append(dict(id=f'{len(jobs):06d}',arm=arm,opponent=opp,map=mp,seed=seed,side=side))
    for i in range(0,len(jobs),100): atomic(stage/'shards'/f'jobs_{i//100:04d}.json',jobs[i:i+100])
    atomic(stage/'jobs.json',jobs)
    print(f'{stage}: {len(jobs)} total evaluations, {len(jobs)//2} per arm',flush=True)
    if a.plan_only: return
    with panel.panel_lock(str(stage)):
        verify_seal(stage)
        verified_rows=checkpoints(stage)
        if a.search_log: search_log_restore(Path(a.search_log),stage,candidate.name,verified_rows)
        if (stage/'STOPPED.json').exists():
            print('Terminal stop preserved: '+str(stage),flush=True); return
        if a.import_results:
            source=Path(a.import_results)
            if not (stage/'bundle_seal.json').exists(): raise ValueError('Pack local bundle before importing')
            if json.loads((source.parent/'bundle_seal.json').read_text())!=json.loads((stage/'bundle_seal.json').read_text()): raise ValueError('Returned artifact seal mismatch')
            if json.loads((source.parent/'manifest.json').read_text()) != identity:
                raise ValueError('Returned bundle manifest does not match this run')
            expected={j['id']:j for j in jobs}
            for p in source.glob('*.json'):
                row=json.loads(p.read_text())
                if p.stem!=row.get('id') or row.get('id') not in expected or any(row.get(k)!=v for k,v in expected[row['id']].items()):
                    raise ValueError(f'Unexpected remote checkpoint: {p}')
                validate(row,expected[row['id']])
                target=stage/'state'/f"{row['id']}.json"
                if target.exists() and json.loads(target.read_text())!=row:
                    raise ValueError(f'Conflicting checkpoint: {p}')
                atomic(target,row)
            verified_rows=checkpoints(stage)
        if a.collect_only: print(summarize(stage)); return
        memory_guard()
        for name,bot in bots.items():
            guard(stage)
            dest=stage/'bots'/f'{name}.wasm'
            built=Path(panel.wasm(str(bot)))
            if dest.exists() and digest(dest)!=digest(built): raise ValueError('Compiled artifact differs from checkpoint version')
            if not dest.exists(): shutil.copy2(built,dest)
        artifacts={name:digest(stage/'bots'/f'{name}.wasm') for name in bots}
        artifact_path=stage/'artifacts.json'
        if artifact_path.exists() and json.loads(artifact_path.read_text())!=artifacts: raise ValueError('Changed executable artifacts')
        atomic(artifact_path,artifacts)
        # Private portable bundle: explicit whitelist only, never secrets/data or bot sources.
        shutil.copy2(panel.ENGINE,stage/'engine.wasm')
        for name in ['tools/farm_scale.py','tools/panel_zig.py','tools/opening_census.py','tools/replay_lite.py','tools/replay.py','tools/engine_sim.py','tools/buildwasm.py','farm/worker.py']:
            dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
        (stage/'out').mkdir(exist_ok=True)
        shutil.copy2(ROOT/'out/opening_census.txt',stage/'out/opening_census.txt')
        if os.name=='nt':
            home=subprocess.check_output(['wsl','-d',panel.WSL_DISTRO,'--','printenv','HOME'],text=True).strip()
            judge=panel._wslpath(panel.JUDGE) if os.environ.get('LOONG_JUDGE') else home+'/toolchains/zig-judge-out/bin/loong-judge'
            subprocess.run(['wsl','-d',panel.WSL_DISTRO,'--','cp',judge,panel._wslpath(str(stage/'loong-judge'))],check=True)
        else: shutil.copy2(panel.JUDGE,stage/'loong-judge')
        for mp in maps:
            src=ROOT/(mp+'.map' if '/' in mp else 'maps/'+mp+'.map')
            dst=stage/'maps'/('dev' if '/' in mp else 'live')/src.name
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
            runtime=stage/(mp+'.map' if '/' in mp else 'maps/'+mp+'.map')
            runtime.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,runtime)
        if digest(stage/'loong-judge')!=identity['judge_hash']: raise ValueError('Judge changed while packing')
        atomic(stage/'bundle_seal.json',seal_inputs(stage))
        verify_seal(stage)
        panel.ROOT=str(stage)
        panel.ENGINE=str(stage/'engine.wasm')
        panel.JUDGE=str(stage/'loong-judge')
        if os.name=='nt': os.environ['LOONG_JUDGE']=panel.JUDGE
        if a.pack_only:
            print('Private bundle packed; remote dispatch remains OFF',flush=True);return
        for shard in sorted((stage/'shards').glob('*.json')):
            if a.search_limit is not None and sum(r['arm']=='candidate' for r in verified_rows)>=a.search_limit: return
            memory_guard(a.j);guard(stage)
            pending=[j for j in json.loads(shard.read_text()) if not (stage/'state'/f"{j['id']}.json").exists()]
            started=time.monotonic(); completed=0
            try:
                with CF.ThreadPoolExecutor(a.j) as pool:
                    futures=[pool.submit(evaluate,j,stage) for j in pending]
                    try:
                        for future in CF.as_completed(futures):
                            result=future.result(); verified_rows.append(result);completed+=1
                            if a.search_log:
                                log=Path(a.search_log); log.parent.mkdir(parents=True,exist_ok=True)
                                fields=['stage','candidate','id','arm','opponent','map','seed','side','winner','win','rounds','units50','units100','length100','first_split','eats_rate','queen_id','queen_death_round','cpu_max_M','cpu_max_opponent_M','seconds','lane','unknown_eats','started','ended']
                                new=not log.exists()
                                with log.open('a',encoding='utf-8',newline='') as fh:
                                    writer=csv.DictWriter(fh,fieldnames=fields,delimiter='\t')
                                    if new: writer.writeheader()
                                    writer.writerow(dict(stage=stage.name,candidate=candidate.name,**result));fh.flush();os.fsync(fh.fileno())
                    except BaseException:
                        for future in futures: future.cancel()
                        raise
            finally:
                # A failing future can leave other completed checkpoints on disk.
                if completed != len(pending): verified_rows=checkpoints(stage)
                timing_path=stage/'timing.json'
                t=json.loads(timing_path.read_text()) if timing_path.exists() else {'games':0,'seconds':0}
                t['games']+=completed;t['seconds']+=time.monotonic()-started;atomic(timing_path,t)
                summarize(stage, sorted(verified_rows, key=lambda r:r['id']))
            print(f'{shard.name}: {completed} new evaluations; checkpointed',flush=True)
            if a.search_stop_alpha is not None:
                reason=search_stop(verified_rows,a.search_stop_alpha,maps,len(opponents),a.search_seed_offset)
                if reason:
                    atomic(stage/'STOPPED.json',dict(reason=reason,evaluations=len(verified_rows)))
                    print(reason,flush=True); return
        verified=checkpoints(stage)
        if len(verified)!=len(jobs): raise ValueError('incomplete coverage')
        verify_seal(stage)
        atomic(stage/'DONE.json',dict(evaluations=len(verified),candidate_games=sum(r['arm']=='candidate' for r in verified)))
if __name__=='__main__': main()
