"""Sequential resumable local hunger experiment. No submission / network / remote lanes.
Each game is checkpointed and bound to build/map/engine/judge by panel_zig.py.
"""
import sys
sys.dont_write_bytecode=True
import difflib, hashlib, json, os, shutil, subprocess
from pathlib import Path
from kamikaze_run import guard, disk_guard

ROOT=Path.cwd(); DATA=Path('F:/BC_hunger_20261008')
MECH='stripes,tower_defense,queen_of_spades,dilemma'
EXTRA='around_unsw,australia,islands,maze'
SAFETY='around_unsw,australia,islands,maze,stripes,tower_defense,weakhold'

def run(args, log):
    with log.open('w',encoding='utf-8') as fh:
        p=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,stdout=fh,stderr=subprocess.STDOUT)
    if p.returncode: raise RuntimeError(f'{args[0]} failed; see {log}')

def panel(bot,name,maps,seeds):
    dest=DATA/name;dest.mkdir(parents=True,exist_ok=True)
    j=min(2,guard())
    if name=='control_mech':
        # An independently running identical control panel may already be complete.
        # Copy only requested completed artifacts onto F:; panel_zig validates every
        # build/map/engine/judge identity, rerunning anything incompatible.
        previous=ROOT/'out/hg_ctl_closed'
        for m in maps.split(','):
            for seed in seeds.split(','):
                for side in 'AB':
                    stem=f'{m}_{seed}_{side}.replay'
                    files=[previous/(stem+s) for s in ('','.cpu.json','.success.json')]
                    if all(p.exists() for p in files):
                        for p in files: shutil.copyfile(p,dest/p.name)
    args=['tools/panel_zig.py',str(bot),'baselines/Y9_6',str(dest),'--maps',maps,'--seeds',seeds,'-j',str(j)]
    print('PANEL',name,flush=True);run(args,DATA/(name+'.log'))
    run(['tools/hunger_metrics.py',str(dest)],DATA/(name+'.metrics.log'))
    (DATA/(name+'.DONE')).write_text('complete\n',encoding='utf-8')
    return json.loads((dest/'hunger_metrics.json').read_text())

def main():
    DATA.mkdir(parents=True,exist_ok=True);os.environ['KAMIKAZE_GUARDS']='1'
    disk_guard()
    seed=DATA/'candidate_source.cpp'
    if not seed.exists():shutil.copyfile(ROOT/'viper_nv30h/main.cpp',seed)
    elif not (DATA/'state.json').exists() and seed.read_bytes() != (ROOT/'viper_nv30h/main.cpp').read_bytes():
        raise RuntimeError('Unsealed source differs; remove only candidate_source.cpp before starting fresh')
    source=seed.read_text(encoding='utf-8')
    settings=[('mild',60,1.0,0.35,0.3),('medium',40,2.0,0.7,0.6),('strong',25,3.0,1.0,0.9)]
    state_path=DATA/'state.json';state=json.loads(state_path.read_text()) if state_path.exists() else {}
    # Resume may legitimately have the selected variant in the candidate directory.
    allowed=[seed.read_bytes()]
    if state.get('chosen'): allowed.append((DATA/'variants'/state['chosen']/'main.cpp').read_bytes())
    if (ROOT/'viper_nv30h/main.cpp').read_bytes() not in allowed:
        raise RuntimeError('Candidate changed outside this sealed run; use a new experiment directory')
    files=[seed,Path(__file__),ROOT/'tools/hunger_metrics.py',ROOT/'tools/replay_lite.py',ROOT/'tools/engine_sim.py']
    files += [ROOT/'viper_nv30k'/f for f in ['main.cpp','bot.toml','maps_data.hpp','policy_nn_v6.hpp','policy_weights_v6.hpp']]
    seal={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    if state.get('_seal',seal)!=seal: raise RuntimeError('Workflow/control/source changed since checkpoint')
    state['_seal']=seal
    def save():
        tmp=state_path.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2),encoding='utf-8');tmp.replace(state_path)
    for name,ramp,expl,revisit,frontier in settings:
        variant=DATA/'variants'/name;variant.mkdir(parents=True,exist_ok=True)
        for file in ['bot.toml','maps_data.hpp','policy_nn_v6.hpp','policy_weights_v6.hpp']:
            shutil.copyfile(ROOT/'viper_nv30k'/file,variant/file)
        text=source.replace('hungerRampN = 40','hungerRampN = '+str(ramp)).replace('hungerExplN = 2.0','hungerExplN = '+str(expl)).replace('hungerRevisitN = 0.7','hungerRevisitN = '+str(revisit)).replace('hungerFrontierN = 0.6','hungerFrontierN = '+str(frontier))
        (variant/'main.cpp').write_text(text,encoding='utf-8')
        state[name]=panel(variant,name,MECH,'1,2,3,4,5,6,7,8');save()
    state['control_mech']=panel('viper_nv30k','control_mech',MECH,'1,2,3,4,5,6,7,8');save()
    # Mechanism-only choice, fixed before the single safety evaluation.
    # Food efficiency first; then lower retracing and greater unique coverage.
    chosen=max(settings,key=lambda s:(state[s[0]]['eats_per_dragon_turn'],-state[s[0]]['retrace_rate'],state[s[0]]['unique_cells_per_dragon']))[0]
    state['chosen']=chosen;save()
    shutil.copyfile(DATA/'variants'/chosen/'main.cpp',ROOT/'viper_nv30h/main.cpp')
    old=(ROOT/'viper_nv30k/main.cpp').read_text(encoding='utf-8').splitlines(True)
    new=(ROOT/'viper_nv30h/main.cpp').read_text(encoding='utf-8').splitlines(True)
    (ROOT/'out/hunger.patch').write_text(''.join(difflib.unified_diff(old,new,fromfile='viper_nv30k/main.cpp',tofile='viper_nv30h/main.cpp')),encoding='utf-8')
    state['extra_candidate']=panel('viper_nv30h','extra_candidate',EXTRA,'3,4');save()
    state['extra_control']=panel('viper_nv30k','extra_control',EXTRA,'3,4');save()
    state['safety_candidate']=panel('viper_nv30h','safety_candidate',SAFETY,'3,4,5,6,7,8,9');save()
    # Reuse the user-authorized 98-game control. No rebuilding or editing it.
    run(['tools/hunger_metrics.py','out/nv30k','--out',str(DATA/'safety_control.json')],DATA/'safety_control.metrics.log')
    state['safety_control']=json.loads((DATA/'safety_control.json').read_text());save()
    run(['tools/panel_queen.py',str(DATA/'safety_candidate'),'out/nv30k'],DATA/'queens.txt')
    for name in (chosen,'control_mech','extra_candidate','extra_control'):
        run(['tools/opening_census.py','--dir',str(DATA/name),'--workers','1','--out',str(DATA/(name+'.census.txt'))],DATA/(name+'.census.log'))
    (DATA/'DONE').write_text('complete\n',encoding='utf-8')
    print(json.dumps(state,indent=2),flush=True)

if __name__=='__main__':main()
