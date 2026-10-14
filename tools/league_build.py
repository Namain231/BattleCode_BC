"""Local league build; run from repo root with Python310 CUDA torch. No remote lanes."""
import os,sys,json,csv,re,subprocess,shutil,time,statistics,collections
from pathlib import Path
ROOT=Path.cwd(); sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'ml/v6')]
import numpy as np
from opening_census import analyse as census
from build_dataset_v6 import extract_game, META
from replay_lite import decode_lite
DATA=Path('F:/BattleCode_data/league_build'); DATA.mkdir(parents=True,exist_ok=True)
STATE=DATA/'state.json'; state=json.loads(STATE.read_text()) if STATE.exists() else {'evaluations':{},'teams':[]}
PY=sys.executable
UV=['uv','run','--python','3.11','--with','unswbc','--with','numpy','python']
MAPS={'Maze':'maze','Stripes':'stripes','Devil':'devil','Trophy':'trophy'}
def save():
 p=STATE.with_suffix('.tmp'); p.write_text(json.dumps(state,indent=2),encoding='utf-8'); os.replace(p,STATE)
def run(cmd,log):
 print('RUN',subprocess.list2cmdline(list(map(str,cmd))),flush=True)
 with (DATA/log).open('a',encoding='utf-8') as fh:
  r=subprocess.run(list(map(str,cmd)),cwd=ROOT,stdout=fh,stderr=subprocess.STDOUT)
 if r.returncode: raise RuntimeError(f'{log}: exit {r.returncode}')
def guard():
 if shutil.disk_usage(DATA).free<6*1024**3: raise RuntimeError('F disk guard: less than 6 GiB free')
 subprocess.run(['C:/Program Files/Git/bin/bash.exe','tools/mem_guard.sh','3000'],cwd=ROOT,check=True)
def report(status):
 lines=['# League build',f'Status: {status}', 'Data/checkpoints/replays: F:/BattleCode_data/league_build; local CUDA + WSL only.',
 'Remote lanes: Kaggle optional via tools/kaggle_train/run_v6.sh; OFF. GitHub Actions/publishing: OFF, require explicit approval.',
 'Architecture: per-team 16-channel/32-hidden v6 net, winning post-rule games, game-held-out validation, 8 epochs.',
 'Shared base: viper_y96qf; wNN=20; NN_TEAM_ID metadata; rules/split/action fallback retained.',
 'Acceptance: equal-map units@100 median within 25% of real winners AND measured league CPU <=66M.',
 'Team | real Sv53 W/N | samples | fidelity | local Sv53 W/N | peak CPU M', '|---|---|---|---|---|---|']
 for t in state['teams']:
  fid=state.get('fidelity',{}).get(t['id'],{}); evs=[v for k,v in state['evaluations'].items() if k.startswith(t['id']+'/')]
  peaks=[v['cpu'] for v in evs if v.get('cpu') is not None]
  record=t.get('real_record','NA'); sv=state.get('sv53',{}).get(t['id'],{})
  lines.append(f"{t['name']} ({t['id']}) | {record} | {state.get('samples',{}).get(t['id'],0)} | {fid.get('verdict','pending')} | {sv.get('wins','?')}/{sv.get('n','?')} | {max(peaks) if peaks else 'unverified'}")
 lines += ['Commands: `Python310/python.exe tools/league_build.py` (resumes state after every game).',
 '`uv run --python 3.11 --with unswbc python tools/panel_zig.py league/<team> baselines/Y9_6 out/league_chk --maps maze,stripes --seeds 1,2 -j 2`',
 'Fidelity: four replay-covered maps x seed 1 x both sides =8; Sv53: five maps x seeds 1,2 x both sides =20.',
 'Files: tools/league_build.py; tools/panel_zig.py (CPU reporting); league/<team>/{sources,bot.wasm}; F: league_build/{datasets,models,state,metrics}; out/league_build_report.md.',
 'Selection: six Sv53 loss opponents (missing scout teams supplemented from cached losses) + two highest peak-rated scout winners.',
 'Detailed per-map units50/100, first split, CPU, acceptance: F:/BattleCode_data/league_build/state.json.',
 'Unverified: '+state.get('unverified','completion pending; no accepted opponent until evaluations finish.'),
 'Movement imitation cannot learn split timing/actions directly; winner-only/opponent/seed confounding remains.']
 (ROOT/'out/league_build_report.md').write_text('\n'.join(lines[:40])+'\n',encoding='utf-8')
def select():
 pool={}
 for fn in ['manifest_all.csv','manifest_new.csv']:
  with (ROOT/'ladder/scout_v6'/fn).open(encoding='utf-8') as fh:
   for r in csv.DictReader(fh):
    p=ROOT/'ladder/scout_v6/top'/r['winner_team']/(r['game']+'.replay')
    if r['at'][:10]>='2026-10-02' and r.get('group')=='top' and p.exists(): pool[r['game']]=r
 teams=collections.defaultdict(list)
 for r in pool.values(): teams[r['winner_team']].append(r)
 names={rs[0]['winner_name']:tid for tid,rs in teams.items()}
 # Add real opponent wins from our cached Sv53 losses when the top scout omitted them.
 leaderboard=json.loads((ROOT/'ladder/scout_v6/refresh_leaderboard.json').read_text(encoding='utf-8'))
 lookup={r['name']:str(r['id']) for r in leaderboard}
 own=json.loads((ROOT/'ladder/sv53/games.json').read_text(encoding='utf-8'))
 for r in own:
  if str(r.get('bot'))!='16651' or r['win'] or r['opp'] not in lookup: continue
  tid=lookup[r['opp']]; gid=str(r['game']); path=ROOT/'ladder/sv53'/(gid+'.replay')
  if not path.exists(): continue
  entry=dict(game=gid,winner_team=tid,winner_name=r['opp'],winner_rating=str(r['oppElo']),winner_side='b' if int(r['me'])==0 else 'a',map=r['map'],at='2026-10-04',path=str(path),source='sv53_loss')
  pool[gid]=entry; teams[tid].append(entry); names[r['opp']]=tid
 wanted=['tungtung67','avid coders','Just Keep Swimming','code matters','Jingling Munmin','hm','btop','Check Raise','Vodyanitsa']
 ids=[names[n] for n in wanted if n in names and len({r['map'] for r in teams[names[n]]})>=4][:6]
 ranked=sorted(teams,key=lambda tid:max(float(r['winner_rating']) for r in teams[tid]),reverse=True)
 ids+= [tid for tid in ranked if tid not in ids][:8-len(ids)]
 text=(ROOT/'out/sv53_losses.txt').read_text(encoding='utf-8')
 state['teams']=[]
 for tid in ids:
  name=teams[tid][0]['winner_name']; match=re.search(r'OPPONENT '+re.escape(name)+r'\s+L\d+ W/N (\d+/\d+)',text)
  available=collections.Counter(r['map'] for r in teams[tid]); choices=[m for m in MAPS if available[m]]
  choices+= [m for m,_ in available.most_common() if m not in choices]
  mapping={}
  for m in choices:
   for f in (ROOT/'maps').glob('*.map'):
    if any(line.strip()=='MAP_NAME '+m for line in f.read_text(encoding='utf-8').splitlines()[:4]): mapping[m]=f.stem; break
  if len(mapping)<4: raise RuntimeError(f'not enough mapped replay maps for {name}: {mapping}')
  mapping=dict(list(mapping.items())[:4])
  state['teams'].append(dict(maps=mapping,id=tid,name=name,slug='team_'+tid,rating=max(float(r['winner_rating']) for r in teams[tid]),games=len(teams[tid]),real_record=match.group(1) if match else (str(sum(bool(r['win']) for r in own if str(r.get('bot'))=='16651' and r['opp']==name))+'/'+str(sum(1 for r in own if str(r.get('bot'))=='16651' and r['opp']==name)) if any(str(r.get('bot'))=='16651' and r['opp']==name for r in own) else 'NA')))
 state['pool']=pool; save(); report('selected teams')
def datasets():
 if state.get('data_done'): return
 counts={}; state.setdefault('dataset_games',{})
 for t in state['teams']:
  tid=t['id']; d=DATA/'datasets_v2'/tid; d.mkdir(parents=True,exist_ok=True)
  pool=[r for r in state['pool'].values() if r['winner_team']==tid]
  selected=[]
  for m in t['maps']:
   selected+=sorted([r for r in pool if r['map']==m],key=lambda r:r['at'],reverse=True)[:3]
  selected+= [r for r in sorted(pool,key=lambda r:r['at'],reverse=True) if r not in selected][:max(0,16-len(selected))]
  counts[tid]=0; holdout=[]
  for number,r in enumerate(selected):
   guard(); gid=int(r['game']); target=d/f'shard_{gid}.npz'
   if number==0: holdout.append(gid)
   if not target.exists():
    path=Path(r['path']) if 'path' in r else ROOT/'ladder/scout_v6/top'/tid/(str(gid)+'.replay')
    arrays,name,stats=extract_game(path,gid,int(tid),'ab'.index(r['winner_side'].lower()))
    mask=arrays['meta'][:,1]==int(tid)
    arrays={k:v[mask] for k,v in arrays.items()}; n=len(arrays['labels'])
    arrays['weights']=np.where(arrays['meta'][:,META.index('is_queen')],3,1).astype(np.float32)
    arrays['game']=np.full(n,gid,dtype=np.int64)
    temp=target.with_suffix('.tmp.npz'); np.savez_compressed(temp,**arrays); os.replace(temp,target)
    state['dataset_games'][str(gid)]=dict(stats,team=tid,samples=n,source=r.get('source','scout')); state.setdefault('samples',{})[tid]=counts[tid]+n; save(); report('building winning datasets')
    print('DATA',t['name'],gid,n,flush=True)
   with np.load(target) as z: counts[tid]+=len(z['labels'])
  (d/'holdout.json').write_text(json.dumps(holdout))
 state['samples']=counts; state['data_done']=True; save(); report('datasets ready')
def train_build(t):
 tid=t['id']; d=DATA/'datasets_v2'/tid; model=DATA/'models8'/f'{tid}.pt'; model.parent.mkdir(exist_ok=True)
 if not model.exists():
  guard(); run([PY,'ml/v6/train_v6.py','--data',d,'--out',model,'--only-teams',tid,'--epochs','8','--channels','16','--hidden','32','--amp','--resume','--val-games',d/'holdout.json'],f'train_{tid}.log')
 bot=ROOT/'league'/t['slug']
 if not state.get('built',{}).get(tid):
  guard()
  bot.mkdir(parents=True,exist_ok=True)
  for f in (ROOT/'viper_y96qf').iterdir():
   if f.suffix in {'.cpp','.hpp','.toml'}: shutil.copy2(f,bot/f.name)
  s=(bot/'main.cpp').read_text(encoding='utf-8').replace('double wNN = 2;','double wNN = 20;')
  (bot/'main.cpp').write_text('#include "team_cond.hpp"\n// League demonstration team '+tid+'; movement imitation, rules fallback.\n'+s,encoding='utf-8')
  (bot/'team_cond.hpp').write_text('#pragma once\n#define NN_TEAM_ID '+tid+'\n',encoding='utf-8')
  h=(bot/'policy_nn_v6.hpp').read_text().replace('C = 32, HID = 64','C = NN_CH, HID = NN_HID')
  (bot/'policy_nn_v6.hpp').write_text(h,encoding='utf-8')
  run([PY,'ml/export_cpp.py',model,bot/'policy_weights_v6.hpp','--data',d],f'export_{tid}.log')
  run([PY,'tools/league_parity.py',tid],f'parity_{tid}.log')
  run(UV+['tools/buildwasm.py',bot],f'build_{tid}.log')
  cache=Path((DATA/f'build_{tid}.log').read_text().strip().splitlines()[-1]); shutil.copy2(cache,bot/'bot.wasm')
  state.setdefault('built',{})[tid]=True; save()
 return bot

def evaluation(t,bot,opp,stage,maps,seeds):
 out=DATA/'eval8'/t['id']/stage
 keys=[f"{t['id']}/{stage}/{mp}/{seed}" for mp in maps for seed in seeds]
 if any(k not in state['evaluations'] for k in keys):
  guard()
  run(UV+['tools/panel_zig.py',bot,opp,out,'--maps',','.join(maps),'--seeds',','.join(map(str,seeds)),'-j','3'],f"eval_{t['id']}_{stage}.log")
  summary=json.loads((out/'summary.json').read_text())
  for mp in maps:
   for seed in seeds:
    key=f"{t['id']}/{stage}/{mp}/{seed}"
    if key in state['evaluations']: continue
    stats=[]
    for side in 'AB':
     path=out/f'{mp}_{seed}_{side}.replay';mine=0 if side=='A' else 1
     r=census(dict(path=path,group='local',side=mine,game=f'{mp}_{seed}_{side}',map=mp,team=t['id']))
     stats.append({k:r[k] for k in ['units50','units100','first_split']})
    subset=[r for r in summary if r['map']==mp and r['seed']==seed]
    measured=[r['cpu_max_ours_M' if stage=='fidelity' else 'cpu_max_theirs_M'] for r in subset]
    state['evaluations'][key]=dict(stats=stats,wins=sum(r['win'] for r in subset),n=len(subset),cpu=max(measured) if all(v is not None for v in measured) else None)
    save();report('evaluation in progress')
 return [state['evaluations'][k] for k in keys]

def fidelity(t,rows):
 tid=t['id']; refs=state.setdefault('references',{}).setdefault(tid,{})
 for name,mp in t['maps'].items():
  if name not in refs or len(refs[name])<min(8,sum(1 for r in state['pool'].values() if r['winner_team']==tid and r['map']==name)):
   games=sorted([r for r in state['pool'].values() if r['winner_team']==tid and r['map']==name],key=lambda r:r['at'],reverse=True)[:8]
   values=list(refs.get(name,[]))
   for r in games[len(values):]:
    job=dict(path=Path(r['path']) if 'path' in r else ROOT/'ladder/scout_v6/top'/tid/(r['game']+'.replay'),group='top',side='ab'.index(r['winner_side'].lower()),game=r['game'],map=name,team=tid)
    a=census(job); values.append({k:a[k] for k in ['units50','units100','first_split']})
    refs.setdefault(name,[]).append(values[-1]); save()
   refs[name]=values; save()
 comparisons=[]; ok=True
 for (name,mp),row in zip(t['maps'].items(),rows):
  rs=refs[name]; local=row['stats']
  med=lambda xs,k:statistics.median([r[k] for r in xs if r[k] is not None]) if any(r[k] is not None for r in xs) else None
  real=med(rs,'units100'); observed=med(local,'units100'); ratio=observed/real if real else None
  passed=ratio is not None and .75<=ratio<=1.25 and row['cpu'] is not None and row['cpu']<=66
  ok &= passed; comparisons.append(dict(map=name,n_real=len(rs),real={k:med(rs,k) for k in ['units50','units100','first_split']},local={k:med(local,k) for k in ['units50','units100','first_split']},ratio=ratio,passed=passed))
 real100=statistics.median(c['real']['units100'] for c in comparisons)
 local100=statistics.median(c['local']['units100'] for c in comparisons)
 ratio=local100/real100 if real100 else None
 cpu_ok=all(row['cpu'] is not None and row['cpu']<=66 for row in rows)
 ok=ratio is not None and .75<=ratio<=1.25 and cpu_ok
 state.setdefault('fidelity',{})[tid]=dict(verdict='accepted' if ok else 'rejected',maps=comparisons,real100=real100,local100=local100,ratio=ratio,cpu_ok=cpu_ok); save(); report('fidelity measured')
def main():
 state['unverified']='Validation pending.'
 if not state['teams']: select()
 datasets()
 for t in state['teams']:
  bot=train_build(t)
  rows=evaluation(t,bot,ROOT/'baselines/Y9_6','fidelity',list(t['maps'].values()),[1]); fidelity(t,rows)
  rows=evaluation(t,ROOT/'out/sv53_pkg',bot,'sv53',['maze','stripes','devil','trophy','portals'],[1,2])
  state.setdefault('sv53',{})[t['id']]=dict(wins=sum(r['wins'] for r in rows),n=sum(r['n'] for r in rows)); save()
 accepted=[t for t in state['teams'] if state['fidelity'][t['id']]['verdict']=='accepted']
 comparable=[t for t in state['teams'] if t['real_record']!='NA']
 local=sorted(comparable,key=lambda t:state['sv53'][t['id']]['wins']/20)
 real=sorted(comparable,key=lambda t:int(t['real_record'].split('/')[0])/int(t['real_record'].split('/')[1]))
 # Ties are partial orders: count discordant strictly ordered pairs.
 discord=0
 for i,a in enumerate(comparable):
  for b in comparable[i+1:]:
   aw,an=map(int,a['real_record'].split('/')); bw,bn=map(int,b['real_record'].split('/'))
   discord+= int((aw/an-bw/bn)*(state['sv53'][a['id']]['wins']-state['sv53'][b['id']]['wins'])<0)
 state['ranking']=dict(local=[t['name'] for t in local],real=[t['name'] for t in real],discordant=discord)
 state['unverified']=f"ranking has {discord} discordant strict pairs; {len(accepted)}/8 accepted. No ladder submission; CPU coverage limited to tested maps; top-only teams without real Sv53 games have no ranking comparison."
 save(); report('complete'); (DATA/'DONE').write_text('complete\n')
if __name__=='__main__':
 try: main()
 except Exception as e:
  state['unverified']=str(e); save(); report('blocked/incomplete'); raise

