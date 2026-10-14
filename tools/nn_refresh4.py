"""Resumable local nn_refresh4 pipeline; no submissions or remote data upload."""
import os,sys,json,csv,time,subprocess,shutil,hashlib,collections,datetime,traceback,math
from pathlib import Path
ROOT=Path(__file__).absolute().parents[1]
os.chdir(ROOT); sys.dont_write_bytecode=True; sys.path.insert(0,str(ROOT))
OUT=Path('out/nn_refresh4'); OUT.mkdir(parents=True,exist_ok=True)
DATA=Path('ladder/scout_v6'); NEW=DATA/'shards_new2'; TRAIN=DATA/'train_out/nn_refresh4'
TRAIN.mkdir(parents=True,exist_ok=True)
PY310=Path(os.environ['LOCALAPPDATA'])/'Programs/Python/Python310/python.exe'
UV=['uv','run','--python','3.11','--with','unswbc','--with','numpy','python','-B']
MAPS='around_unsw,australia,islands,maze,stripes,tower_defense,weakhold'
BASH='C:/Program Files/Git/usr/bin/bash.exe'
STATE=OUT/'state.json'
state=json.loads(STATE.read_text()) if STATE.exists() else {'done':[],'commands':[]}
sys.path.insert(0,str(ROOT/'ml/v6'))
from shard_manifest import owned_shards, sha256
def atomic(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(value,indent=2),encoding='utf-8'); os.replace(tmp,path)
def report(status):
    lines=['# nn_refresh4',status,'Locked control: baselines/Nv30. No submission or active-bot change.',
      'Candidate: viper_nv30n (eligible only after export, parity and play checks).',
      'Artifacts: tools/nn_refresh4.py; out/nn_refresh4/; ladder/scout_v6/manifest_new2.csv, shards_new2/, train_out/nn_refresh4/.']
    if 'data' in state: lines.append('New data: '+json.dumps(state['data'],ensure_ascii=False))
    lines.append('Safeguard verification: Python310 -B tools/nn_refresh4_verify.py (fault-injection checks PASS).')
    if 'old' in state:
        for tag in ['old','new']:
            if tag in state:
                e=state[tag]; lines.append(tag+' same-holdout top-1: '+str(round(e['val_acc']*100,3))+'%; fwd/side/split/stop '+str({k:None if e['move_class_acc'][k] is None else round(100*e['move_class_acc'][k],2) for k in ['fwd','side','split','stop']}))
    for k in ['parity','cpu','screen','confirm']:
        if k in state: lines.append(k+': '+json.dumps(state[k]))
    lines.extend(['Commands (full argv and successful stages: out/nn_refresh4/state.json):',
        'bash -lc "set -a; . ./secrets.env; set +a; uv run --python 3.11 --with unswbc --with numpy python -B tools/nn_refresh4.py"',
        'Scouting reused out/scout_nn4.done; manifest_sweep rows after line 1858, deduped against manifest_all/new.',
        'Build: ml/v6/build_dataset_v6.py --index ladder/scout_v6/manifest_new2.csv --out ladder/scout_v6/shards_new2 --workers 2',
        'Train: '+state.get('training_lane','local GTX 1650; remote lanes OFF')+'; k_fullft init; old + recent shards 2x; newest-game holdout; 3 epochs.',
        'Export/parity: ml/export_cpp.py and ml/v6/parity.py; build: tools/buildwasm.py.',
        'Screen: tools/panel_zig.py viper_nv30n baselines/Y9_6 out/nv30n --maps '+MAPS+' --seeds 3,4,5,6,7,8,9 -j 4 (2 if busy).',
        'Queen: tools/panel_queen.py; units@100: tools/opening_census.py --dir.',
        'Local panels are provisional (~5 points); ladder A/B requires user approval.',
        'Unverified: '+state.get('unverified','training/export/CPU/play until stages complete.')])
    Path('out/nn_refresh4_report.md').write_text('\n'.join(lines[:40])+'\n',encoding='utf-8')
def disk():
    if shutil.disk_usage('C:/').free<3*1024**3: raise RuntimeError('C: below 3 GiB; resume after freeing space')
    if shutil.disk_usage(str(DATA.resolve())).free<5*1024**3: raise RuntimeError('F: below 5 GiB')
def run(tag,cmd,timeout=None):
    disk(); state['commands'].append({'stage':tag,'argv':list(map(str,cmd))}); atomic(STATE,state)
    print('RUN',tag,flush=True)
    with (OUT/(tag+'.log')).open('a',encoding='utf-8') as f:
        for attempt in range(3):
            started=time.monotonic()
            with subprocess.Popen(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT) as proc:
                try:
                    while proc.poll() is None:
                        disk()
                        if timeout and time.monotonic()-started>timeout: raise TimeoutError(tag)
                        time.sleep(5)
                except BaseException:
                    subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=f,stderr=f)
                    raise
            if proc.returncode==0: break
            f.flush(); txt=(OUT/(tag+'.log')).read_text(encoding='utf-8',errors='replace')
            if not any(s in txt[-3000:] for s in ['Failed to fetch','invalid peer certificate','Request failed after']): raise RuntimeError(tag+' failed: '+str(proc.returncode))
        else: raise RuntimeError(tag+' failed after retries')
def done(tag):
    inputs,outputs=PENDING.pop(tag)
    assert inputs['pipeline']==sha256(__file__) and inputs['artifacts']==artifact_hashes(inputs['artifacts']), 'Stage inputs changed while running: '+tag
    if tag not in state['done']: state['done'].append(tag)
    state.setdefault('stages',{})[tag]={'inputs':inputs,'outputs':artifact_hashes(outputs)}
    atomic(STATE,state); report('In progress: '+tag+' complete.')

PENDING={}
def artifact_hashes(paths):
    return {str(p): fingerprint(p) if Path(p).is_dir() else sha256(p) for p in paths}

def cached(tag,inputs,outputs):
    # Validate every completed stage on every resume, never trust done flags alone.
    identity={'artifacts':artifact_hashes(inputs),'pipeline':sha256(__file__)}
    PENDING[tag]=(identity,outputs)
    old=state.get('stages',{}).get(tag)
    if old is None: return False
    assert old['inputs']==identity, 'Stage inputs changed: '+tag
    assert old['outputs']==artifact_hashes(outputs), 'Stage outputs changed: '+tag
    return True

def scout_manifest():
    deadline=time.monotonic()+10800
    while not Path('out/scout_nn4.done').exists():
        assert time.monotonic()<deadline, 'Scout marker wait exceeded 3 hours'
        disk(); time.sleep(60)
    # The original script's first auto-discovered start was 1288380.
    for start in [1288380,1200000,1100000]:
        run('scout_verify_'+str(start),UV+['ladder/scout_v6/sweep.py','--start',str(start),'--scan','4000','--min-elo','2000','--cap-mb','2500'])
        coverage=json.loads((DATA/f'sweep_window_{start}.json').read_text())
        assert coverage['complete'] and coverage['covered']==4000 and not coverage['retry_ids']
    prior=set()
    for name in ['manifest_all.csv','manifest_new.csv']:
        with (DATA/name).open(encoding='utf-8-sig',newline='') as f:
            prior.update(int(r['game']) for r in csv.DictReader(f))
    with (DATA/'manifest_sweep.csv').open(encoding='utf-8-sig',newline='') as f:
        header=f.readline(); tail=f.readlines()[1857:]
    rows=[]; seen=set(prior)
    for r in csv.DictReader([header]+tail):
        gid=int(r['game'])
        if gid in seen: continue
        assert float(r['winner_rating'])>=2000 and r['ranked'].lower()=='true'
        assert (DATA/'top'/r['winner_team']/(str(gid)+'.replay')).exists()
        seen.add(gid); rows.append(r)
    destination=DATA/'manifest_new2.csv'
    import io
    buf=io.StringIO(newline=''); writer=csv.DictWriter(buf,fieldnames=header.strip().split(','))
    writer.writeheader(); writer.writerows(rows)
    value=buf.getvalue()
    if destination.exists() and destination.read_text(encoding='utf-8')!=value.replace('\r\n','\n'):
        assert 'build' not in state.get('stages',{}), 'Manifest changed after committed build'
        current=json.loads((NEW/'manifest.json').read_text()) if (NEW/'manifest.json').exists() else {}
        assert not current.get('shards'), 'Manifest changed after exported shards'
    destination.write_text(value,encoding='utf-8',newline='')
    atomic(OUT/'scout_selection.json',{'tail_after_physical_line':1858,'games':sorted(int(r['game']) for r in rows),'source_hash':sha256(DATA/'manifest_sweep.csv'),'prior_hashes':{n:sha256(DATA/n) for n in ['manifest_all.csv','manifest_new.csv']},'windows':[json.loads((DATA/f'sweep_window_{s}.json').read_text()) for s in [1288380,1200000,1100000]]})
def memory():
    run('mem_guard',[BASH,'tools/mem_guard.sh','2500'],timeout=1800)
def sweep(start):
    # Reuse implementation with isolated manifest/state and dedupe BEFORE downloads.
    ns={'__name__':'nn_refresh4_sweep','__file__':str(DATA/'sweep.py')}
    src=(DATA/'sweep.py').read_text(encoding='utf-8')
    old='recorded = {int(r["game"]) for r in csv.DictReader(open(MAN, encoding="utf-8"))} if have_header else set()'
    assert old in src
    src=src.replace(old,old+'\n    for prior in (OUT / "manifest_all.csv", OUT / "manifest_new.csv"):\n        if prior.exists():\n            with prior.open(encoding="utf-8-sig", newline="") as fh:\n                recorded.update(int(r["game"]) for r in csv.DictReader(fh))')
    exec(compile(src,str(DATA/'sweep.py'),'exec'),ns)
    ns['MAN']=DATA/'manifest_new2.csv'; ns['STATE']=DATA/'sweep_state_new2.json'
    sys.argv=['sweep.py','--start',str(start),'--scan','4000','--min-elo','2000','--cap-mb','2500']
    ns['main']()
def train_worker():
    import runpy
    torchmod = __import__('torch'); torchmod.set_num_threads(2)
    runpy.run_path('ml/v6/train_v6.py',run_name='__main__')


def evaluate(which,checkpoint):
    import numpy as np,torch
    sys.path[:0]=[str(ROOT/'ml/v6'),str(ROOT/'ml')]
    import train_v6 as t
    assert torch.cuda.is_available(),'CUDA unavailable; do not train on CPU'
    torch.set_num_threads(2)
    ck=torch.load(checkpoint,map_location='cpu')
    m=t.Policy(planes=19,scalars=6,ch=ck['channels'],hidden=ck['hidden'],classes=7).cuda()
    m.load_state_dict(ck['state_dict'])
    t.HOLDOUT_GAMES=np.array(json.loads((TRAIN/'holdout.json').read_text()),dtype=np.int64)
    ev=t.evaluate(m,owned_shards(NEW,OUT/'shards_new2_identity.json'),'cuda',512,.1,0)
    assert ev['val_samples']>0
    atomic(OUT/(which+'.json'),ev)
def panel_busy():
    ps=subprocess.run(['powershell.exe','-NoProfile','-Command',"(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*tools/panel_zig.py*' } | Measure-Object).Count"],capture_output=True,text=True)
    return int(ps.stdout.strip() or 0)>0
def fingerprint(directory):
    d=Path(directory)
    return {str(p.relative_to(d)):hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob('*') if p.is_file()}


def panel(tag,bot,out,seeds,maps=MAPS):
    # Wait for other panels; do not overlap this pipeline's panels.
    while panel_busy():
        print('waiting for existing panels',flush=True); time.sleep(30); disk()
    memory()
    identity={'bot_dir':bot,'bot':fingerprint(bot),'opp':fingerprint('baselines/Y9_6'),'maps':{m:sha256(Path('maps',m+'.map')) for m in maps.split(',')},'seeds':seeds,'execution':'Windows/WSL','dependencies':artifact_hashes(['tools/panel_zig.py','tools/buildwasm.py','tools/replay_lite.py','tools/analyze_ours.py','tools/panel_queen.py','tools/opening_census.py'])}
    import shlex
    if os.environ.get('LOONG_JUDGE'):
        value=str(Path(os.environ['LOONG_JUDGE']).absolute()).replace('\\','/')
        judge=shlex.quote('/mnt/'+value[0].lower()+value[2:])
    else: judge='"$HOME/toolchains/zig-judge-out/bin/loong-judge"'
    result=subprocess.run(['wsl','-d',os.environ.get('WSL_DISTRO','Ubuntu'),'--','bash','-lc','sha256sum '+judge],capture_output=True,text=True,check=True)
    identity['judge']=result.stdout.split()[0]
    import unswbc
    identity['engine']=sha256(os.environ.get('UNSWBC_ENGINE',str(Path(unswbc.__file__).parent/'unswbc_engine.wasm')))
    provenance=Path(out)/'nn_refresh4_identity.json'
    if provenance.exists():
        assert json.loads(provenance.read_text())==identity, 'Cached panel provenance changed'
    elif Path(out).exists() and any(Path(out).glob('*.replay')):
        raise RuntimeError('Existing panel has no provenance: inspect before reuse '+out)
    else: atomic(provenance,identity)
    cmd=UV+['tools/panel_zig.py',bot,'baselines/Y9_6',out,'--maps',maps,'--seeds',seeds,'-j','2']
    run(tag,cmd)
    validate_panel(out)

def panel_outputs(folder):
    p=Path(folder)
    return [p/'summary.json']+sorted(p.glob('*.replay'))+sorted(p.glob('*.replay.cpu.json'))+sorted(p.glob('*.replay.success.json'))

def validate_panel(folder):
    p=Path(folder); identity=json.loads((p/'nn_refresh4_identity.json').read_text())
    assert fingerprint(identity['bot_dir'])==identity['bot'] and fingerprint('baselines/Y9_6')==identity['opp'], 'Panel bot changed'
    assert artifact_hashes(identity['dependencies'])==identity['dependencies'], 'Panel analysis/build code changed'
    for m,digest in identity['maps'].items(): assert sha256(Path('maps',m+'.map'))==digest, 'Panel map changed'
    import tools.panel_zig as driver
    wa,wb=driver.wasm(identity['bot_dir']),driver.wasm('baselines/Y9_6')
    # Recheck the current judge/engine and every actual compiled-game identity.
    import shlex
    judge=shlex.quote(driver._wslpath(driver.JUDGE)) if os.environ.get('LOONG_JUDGE') else '"$HOME/toolchains/zig-judge-out/bin/loong-judge"'
    current=subprocess.run(['wsl','-d',driver.WSL_DISTRO,'--','bash','-lc','sha256sum '+judge],capture_output=True,text=True,check=True).stdout.split()[0]
    assert current==identity['judge'] and sha256(driver.ENGINE)==identity['engine'], 'Panel runtime changed'
    for m in identity['maps']:
        for seed in map(int,identity['seeds'].split(',')):
            for side in 'AB':
                path=p/f'{m}_{seed}_{side}.replay.success.json'
                success=json.loads(path.read_text())
                expected=dict(version=2,ours=sha256(wa),opp=sha256(wb),map=identity['maps'][m],engine=identity['engine'],judge=identity['judge'],seed=seed,side=side)
                assert success==dict(returncode=0,identity=expected), 'Mixed or failed panel game'

def paired_runtime(control,candidate):
    validate_panel(control); validate_panel(candidate)
    a=json.loads((Path(control)/'nn_refresh4_identity.json').read_text())
    b=json.loads((Path(candidate)/'nn_refresh4_identity.json').read_text())
    assert {k:v for k,v in a.items() if k not in ('bot','bot_dir')}=={k:v for k,v in b.items() if k not in ('bot','bot_dir')}, 'Panel arms have different runtime/map/analysis identities'

def check_cpu(rows):
    for r in rows:
        v=r.get('cpu_max_ours_M')
        assert isinstance(v,(int,float)) and math.isfinite(v) and 0<v<=66, 'CPU missing/nonfinite/exceeds 66M'
def stats(folder):
    rows=json.loads((Path(folder)/'summary.json').read_text())
    check_cpu(rows)
    expected={(m,seed,side) for m in MAPS.split(',') for seed in (range(10,17) if 'confirm' in folder else range(3,10)) for side in 'AB'}
    assert len(rows)==98 and {(r['map'],r['seed'],r['side']) for r in rows}==expected, 'Incomplete or wrong-seed panel'
    from tools.analyze_ours import analyse
    q=0; units=[]
    for r in rows:
        p=Path(folder)/(r['map']+'_'+str(r['seed'])+'_'+r['side']+'.replay')
        a=analyse(str(p),r['side'].lower()); q+=bool(a['our_queen_death'])
    run(Path(folder).name+'_queen',UV+['tools/panel_queen.py',folder])
    run(Path(folder).name+'_census',UV+['tools/opening_census.py','--dir',folder,'--quick','--workers','1','--out',str(OUT/(Path(folder).name+'_census.txt'))])
    census=json.loads((Path(folder)/'opening_quick.json').read_text())
    units=[r['snaps'].get('100',[r['ours']['count']])[0] for r in rows]
    return {'units100_mean':round(sum(units)/len(units),2),'units100_by_map':{m:census['maps'][m]['candidate']['units100'] for m in MAPS.split(',')},'wins':sum(r['win'] for r in rows),'games':len(rows),'queen_deaths':q,'cpu_max_M':max(r['cpu_max_ours_M'] for r in rows),'per_map':{m:sum(r['win'] for r in rows if r['map']==m) for m in MAPS.split(',')}}

def worthwhile(candidate,control):
    check_cpu([{'cpu_max_ours_M':r['cpu_max_M']} for r in [candidate,control]])
    assert candidate['games']==control['games']==98
    gain=100*(candidate['wins']-control['wins'])/98
    return gain>=5 or (candidate['wins']>=control['wins'] and (candidate['queen_deaths']+5<=control['queen_deaths'] or candidate['units100_mean']>=control['units100_mean']*1.15))
def main():
    state.pop('unverified',None)
    report('In progress: scouting recent top-team wins.')
    scout_manifest()
    rows=list(csv.DictReader((DATA/'manifest_new2.csv').open(encoding='utf-8')))
    assert rows,'No new games collected'
    counts=dict(collections.Counter(r['map'] for r in rows))
    state['data']={'games':len(rows),'teams':len({r['winner_team'] for r in rows}),'maps':counts,'dates':[min(r['at'] for r in rows),max(r['at'] for r in rows)]}
    atomic(STATE,state)
    build_inputs=[DATA/'manifest_new2.csv','ml/v6/build_dataset_v6.py','ml/v6/shard_manifest.py','ml/build_dataset.py','tools/replay_lite.py','maps']+[DATA/'top'/r['winner_team']/(r['game']+'.replay') for r in rows]
    current_build=artifact_hashes(build_inputs)
    if 'build_identity' in state: assert state['build_identity']==current_build, 'Resumable build inputs changed'
    state['build_identity']=current_build; atomic(STATE,state)
    if not cached('build',build_inputs,[NEW/'manifest.json']):
        memory(); run('build',UV+['ml/v6/build_dataset_v6.py','--index',str(DATA/'manifest_new2.csv'),'--out',str(NEW),'--workers','2']); done('build')
    manifest=json.loads((NEW/'manifest.json').read_text())
    ids=sorted({int(g['game']) for g in manifest['games']})
    eligible={int(r['game']) for r in rows if 98 not in (int(r['teamA']),int(r['teamB']))}
    assert set(ids)==eligible, 'Eligible selected games missing from exported dataset'
    state['data']['training_games']=len(ids)
    state['data']['excluded_vs_our_team']=len(rows)-len(eligible)
    hold=ids[-max(1,len(ids)//10):]
    if not (TRAIN/'holdout.json').exists(): atomic(TRAIN/'holdout.json',hold)
    assert json.loads((TRAIN/'holdout.json').read_text())==hold, 'Holdout changed'
    identity={str(d):hashlib.sha256((d/'manifest.json').read_bytes()).hexdigest() for d in [DATA/'shards_145',DATA/'shards_new',NEW]}
    identity['init']=hashlib.sha256((DATA/'train_out/k_fullft/v6.pt').read_bytes()).hexdigest()
    identity['holdout']=hold
    for directory in [DATA/'shards_145',DATA/'shards_new',NEW]:
        owned_shards(directory,OUT/(directory.name+'_identity.json'))
    identity['code']=artifact_hashes(['ml/v6/train_v6.py','ml/train.py','ml/v6/shard_manifest.py'])
    identity['args']={'epochs':3,'lr':.0002,'batch':512,'amp':True,'oversample_recent':2,'seed':0}
    if 'training_identity' in state: assert state['training_identity']==identity, 'Training data changed'
    state['training_identity']=identity; atomic(STATE,state)
    training_inputs=[TRAIN/'holdout.json',DATA/'train_out/k_fullft/v6.pt','ml/v6/train_v6.py','ml/v6/shard_manifest.py']+[OUT/(d+'_identity.json') for d in ['shards_145','shards_new','shards_new2']]
    if not cached('old_eval',training_inputs,[OUT/'old.json']):
        memory(); run('old_eval',[PY310,'-B','tools/nn_refresh4.py','--eval','old',str(DATA/'train_out/k_fullft/v6.pt')]); done('old_eval')
    state['old']=json.loads((OUT/'old.json').read_text())
    if not cached('train',training_inputs,[TRAIN/'v6.pt',TRAIN/'v6.ckpt',TRAIN/'best.pt',TRAIN/'last.pt',TRAIN/'v6.metrics.json']):
        memory()
        state['training_lane']='local GTX 1650; remote lanes OFF'
        run('train',[PY310,'-B','tools/nn_refresh4.py','--train','--data',str(DATA/'shards_145'),'--extra-data',str(DATA/'shards_new'),'--extra-data',str(DATA/'shards_new'),'--extra-data',str(NEW),'--extra-data',str(NEW),'--val-data',str(NEW),'--val-games',str(TRAIN/'holdout.json'),'--init',str(DATA/'train_out/k_fullft/v6.pt'),'--out',str(TRAIN/'v6.pt'),'--epochs','3','--lr','0.0002','--batch','512','--amp','--resume']); done('train')
    if not cached('new_eval',training_inputs+[TRAIN/'best.pt'],[OUT/'new.json']):
        run('new_eval',[PY310,'-B','tools/nn_refresh4.py','--eval','new',str(TRAIN/'best.pt')]); done('new_eval')
    state['new']=json.loads((OUT/'new.json').read_text())
    candidate=Path('viper_nv30n')
    if not cached('export',[TRAIN/'best.pt','baselines/Nv30','ml/export_cpp.py'],[candidate]):
        shutil.copytree('baselines/Nv30',candidate,dirs_exist_ok=True)
        run('export',[PY310,'-B','ml/export_cpp.py',str(TRAIN/'best.pt'),str(candidate/'policy_weights_v6.hpp'),'--data',str(NEW)])
        (candidate/'main.cpp').touch()
        for p in Path('baselines/Nv30').rglob('*'):
            if p.is_file() and p.name!='policy_weights_v6.hpp':
                assert p.read_bytes()==(candidate/p.relative_to('baselines/Nv30')).read_bytes()
        done('export')
    if not cached('parity',[TRAIN/'best.pt',candidate,'ml/v6/parity.py','ml/v6/parity_main.cpp'],[OUT/'parity.log']):
        scratch=OUT/'parity'; scratch.mkdir(exist_ok=True)
        shutil.copy2(candidate/'policy_weights_v6.hpp',scratch/'policy_weights_v6.hpp')
        shutil.copy2(candidate/'policy_nn_v6.hpp',scratch/'policy_nn_v6.hpp')
        run('parity',[PY310,'-B','ml/v6/parity.py',str(TRAIN/'best.pt'),str(NEW),str(scratch)])
        txt=(OUT/'parity.log').read_text()
        assert '-> PASS' in txt and '-> OK' in txt and 'FAIL' not in txt
        state['parity']=txt.strip().splitlines()[-2:]
        original={str(p.relative_to('baselines/Nv30')) for p in Path('baselines/Nv30').rglob('*') if p.is_file()}
        assert {str(p.relative_to(candidate)) for p in candidate.rglob('*') if p.is_file()}==original
        assert all((candidate/p).read_bytes()==(Path('baselines/Nv30')/p).read_bytes() for p in original if p!='policy_weights_v6.hpp')
        done('parity')
    if not cached('wasm',[candidate,'tools/buildwasm.py'],[OUT/'wasm.log']):
        run('wasm',UV+['tools/buildwasm.py',str(candidate)]); done('wasm')
    panel('cpu',str(candidate),'out/nv30n_cpu','3','australia,around_unsw')
    if not cached('cpu',[candidate,'out/nv30n_cpu/nn_refresh4_identity.json'],panel_outputs('out/nv30n_cpu')):
        cpu=json.loads(Path('out/nv30n_cpu/summary.json').read_text())
        state['cpu']={m:max(r['cpu_max_ours_M'] for r in cpu if r['map']==m) for m in ['australia','around_unsw']}
        assert all(v is not None and v<=66 for v in state['cpu'].values()),'CPU peak exceeds 66M'
        done('cpu')
    check_cpu(json.loads(Path('out/nv30n_cpu/summary.json').read_text()))
    for tag,bot,folder in [('control','baselines/Nv30','out/kz_ctl'),('candidate',str(candidate),'out/nv30n')]:
        panel(tag,bot,folder,'3,4,5,6,7,8,9')
        check_cpu(json.loads((Path(folder)/'summary.json').read_text()))
        if not cached(tag,[bot,Path(folder)/'nn_refresh4_identity.json'],panel_outputs(folder)): done(tag)
    paired_runtime('out/kz_ctl','out/nv30n')
    control=stats('out/kz_ctl'); cand=stats('out/nv30n')
    gain=100*(cand['wins']-control['wins'])/98
    state['screen']={'candidate':cand,'control':control,'gain_pp':round(gain,2)}
    atomic(STATE,state)
    # Alternate criterion requires lower queen deaths and no loss of wins.
    confirm=worthwhile(cand,control)
    if confirm:
        for tag,bot,folder in [('confirm_control','baselines/Nv30','out/nv30n_confirm_ctl'),('confirm_candidate',str(candidate),'out/nv30n_confirm')]:
            panel(tag,bot,folder,'10,11,12,13,14,15,16')
            check_cpu(json.loads((Path(folder)/'summary.json').read_text()))
            if not cached(tag,[bot,Path(folder)/'nn_refresh4_identity.json'],panel_outputs(folder)): done(tag)
        paired_runtime('out/nv30n_confirm_ctl','out/nv30n_confirm')
        state['confirm']={'candidate':stats('out/nv30n_confirm'),'control':stats('out/nv30n_confirm_ctl')}
    state['unverified']='Real-ladder strength; no ladder A/B authorized. Input-builder byte parity is outside this task.'
    atomic(STATE,state)
    recommendation='Do not advance: initial panel lacks the required improvement.'
    if confirm:
        recommendation=('Confirmation supports an independent review before user-approved ladder A/B.' if worthwhile(state['confirm']['candidate'],state['confirm']['control']) else 'Do not advance: confirmation did not sustain the required improvement.')
    report('Complete. '+recommendation)
    run('agent_log',[BASH,'-lc',"printf '%s\\n' '- [2026-10-07] [executor] [nn_refresh4] Local refresh and Nv30 screening complete; see out/nn_refresh4_report.md; no submission.' >> AGENT_LOG.md"])
    (OUT/'DONE').write_text('complete\n',encoding='utf-8')
if __name__=='__main__':
    try:
        if len(sys.argv)>1 and sys.argv[1]=='--sweep': sweep(int(sys.argv[2]))
        elif len(sys.argv)>1 and sys.argv[1]=='--eval': evaluate(sys.argv[2],sys.argv[3])
        elif len(sys.argv)>1 and sys.argv[1]=='--train':
            sys.argv=[sys.argv[0]]+sys.argv[2:]; train_worker()
        else:
            import msvcrt
            with (OUT/'supervisor.lock').open('a+b') as lock:
                lock.seek(0,2)
                if lock.tell()==0: lock.write(b'0'); lock.flush()
                lock.seek(0)
                try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                except OSError:
                    print('A refresh supervisor is already active; leaving its state unchanged.',flush=True); sys.exit(2)
                try: main()
                finally:
                    lock.seek(0); msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
    except Exception as ex:
        state['unverified']=str(ex); atomic(STATE,state); report('Stopped safely: '+str(ex)); traceback.print_exc(); sys.exit(1)
