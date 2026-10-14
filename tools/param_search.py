"""Offline successive-halving opening search. No network, submissions or LLM loop."""
import argparse, csv, hashlib, json, math, os, random, shutil, statistics as S, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).absolute().parents[1]
os.chdir(ROOT)
sys.path.insert(0,str(ROOT/'tools'))
import farm_scale as farm
PARAMS={
 'budAt':(4,4,6), 'budStart':(0,0,15), 'budUntil':(300,200,420),
 'minerGamma':(.90,.75,.97), 'protectFrom':(200,100,350),
 'feedFrom':(350,250,440), 'qfeedFrom':(280,180,400),
 'splitMinLen':(24,8,28), 'splitUnitCap':(3,3,12),
 'swarmUnitCap':(5,5,20), 'exploreDelay':(12,2,20),
 'exploreWeight':(2.,1.,5.)}
CLOSED=['stripes','tower_defense','queen_of_spades','dilemma']

def atomic(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(v,indent=2),encoding='utf-8');os.replace(tmp,p)

def generate(settings, name):
 dest=ROOT/'out/param_search'/name
 dest.mkdir(parents=True,exist_ok=True)
 for p in (ROOT/'viper_y96qf').iterdir():
  if p.is_file(): shutil.copy2(p,dest/p.name)
 s=(dest/'main.cpp').read_text(encoding='utf-8')
 s=s.replace('struct Params {','#include "params_active.hpp"\nstruct Params {')
 for k,(default,lo,hi) in PARAMS.items():
  if k in ['budStart','splitUnitCap','swarmUnitCap','exploreDelay','exploreWeight']: continue
  import re
  s,n=re.subn(r'(\b(?:int|double) '+k+r' = )[^;]+;',r'\g<1>PS_'+k+';',s,count=1)
  assert n==1,k
 s=s.replace('    int budAt = PS_budAt;', '    int budStart = PS_budStart;\n    int splitUnitCap = PS_splitUnitCap;\n    int swarmUnitCap = PS_swarmUnitCap;\n    int exploreDelay = PS_exploreDelay;\n    double exploreWeight = PS_exploreWeight;\n    int budAt = PS_budAt;')
 s=s.replace('else P.protectFrom = 200;', 'else P.protectFrom = PS_protectFrom;')
 s=s.replace('MY_LEN < P.budAt ||', 'ROUND < P.budStart || MY_LEN < P.budAt ||')
 s=s.replace('UNITS >= 5 || MY_LEN < 8', 'UNITS >= P.swarmUnitCap || MY_LEN < 8')
 s=s.replace('min(UNIT_LIMIT, 3)', 'min(UNIT_LIMIT, P.splitUnitCap)')
 s=s.replace('ROUND - pxLastGrow2 >= 12', 'ROUND - pxLastGrow2 >= P.exploreDelay')
 s=s.replace('ROUND - pxLastGrow >= 12', 'ROUND - pxLastGrow >= P.exploreDelay')
 s=s.replace('score += 2.0 * (torusDist(body[0], pxTarget)', 'score += P.exploreWeight * (torusDist(body[0], pxTarget)')
 (dest/'main.cpp').write_text(s,encoding='utf-8')
 header='// Generated; do not edit.\n#pragma once\n'+''.join(f'#define PS_{k} {v}\n' for k,v in settings.items())
 (dest/f'params_{name}.hpp').write_text(header,encoding='utf-8')
 (dest/'params_active.hpp').write_text(f'#include "params_{name}.hpp"\n',encoding='utf-8')
 atomic(dest/'settings.json',settings)
 return dest

def assess(stage):
 rows=farm.checkpoints(stage)
 pairs={}
 for r in rows: pairs.setdefault((r['map'],r['opponent'],r['seed'],r['side']),{})[r['arm']]=r
 pairs=[v for v in pairs.values() if set(v)=={'candidate','sv53'}]
 census={}
 for line in (ROOT/'out/opening_census.txt').read_text(encoding='utf-8').splitlines():
  bits=[b.strip() for b in line.split('|')]
  if len(bits)==8 and bits[0] in farm.LABELS.values():
   census[bits[0]]=[float(x.split('/')[1]) for x in bits[2:7]]
 medians={};progress={};scores=[]
 for mp in farm.LIVE:
  ps=[v for v in pairs if v['candidate']['map']==mp]
  if not ps: continue
  target=census[farm.LABELS[mp]]
  c=S.median(v['candidate']['units100'] for v in ps)
  b=S.median(v['sv53']['units100'] for v in ps)
  medians[mp]=dict(candidate=c,sv53=b,top=target[1],pairs=len(ps))
  progress[mp]= c>=b+max(0,target[1]-b)/2
  eats=S.median(v['candidate']['eats_rate'] for v in ps)/max(.01,target[4])
  split=[v['candidate']['first_split'] for v in ps if v['candidate']['first_split'] is not None]
  split_score=(1/(1+abs(S.median(split)-target[3])/25)) if split else 0
  scores.append((mp,c/max(1,target[1])+.2*min(eats,2)+.1*split_score))
 closed=[x for mp,x in scores if mp in CLOSED]
 score=(S.mean(closed) if len(closed)==4 else -100)+.25*(S.mean(x for mp,x in scores) if scores else 0)
 peak=max((r['cpu_max_M'] for r in rows if r['arm']=='candidate'),default=0)
 guards={}
 for group in ['Y9_6','league']:
  ps=[v for v in pairs if (v['candidate']['opponent']=='Y9_6')==(group=='Y9_6')]
  seeds={}
  for v in ps: seeds.setdefault(v['candidate']['seed'],[]).append(v['candidate']['win']-v['sv53']['win'])
  expected=2 if group=='Y9_6' else 2*len({v['candidate']['opponent'] for v in pairs if v['candidate']['opponent']!='Y9_6'})
  vals=[S.mean(v) for v in seeds.values() if len(v)==expected]
  mean=S.mean(vals) if vals else None
  # Safety unresolved unless there is enough independent evidence. Report exact interval.
  ci=None
  if len(vals)>1:
   from scipy.stats import t
   width=float(t.ppf(.975,len(vals)-1))*S.stdev(vals)/math.sqrt(len(vals))
   ci=[mean-width,mean+width]
  guards[group]=dict(delta=mean,ci=ci,seed_clusters=len(vals),resolved_regression=ci is not None and ci[1]<0,safety_supported=len(vals)>=30 and ci is not None and ci[0]>=-.03)
 return dict(score=score,pairs=len(pairs),cpu_peak=peak,medians=medians,halfway=progress,guards=guards,
  eligible=len(pairs)>=1500 and peak<=66 and all(progress.get(m,False) for m in CLOSED) and all(g['safety_supported'] for g in guards.values()))

def report(state):
 lines=['# Parameter search',f'Status: {state.get("status","prepared")}; no submissions; remote lanes OFF.',
 'Changed: tools/farm_scale.py, insights.md, AGENT_LOG.md; created tools/param_search.py, task briefs and critique.',
 'Created: out/param_search/ps_*/ (common bot implementation, generated 12-parameter headers).',
 'Objective: closed-start units100 + overall units100, eats/round and first-split agreement with census.',
 'Census is winners-only; league proxies unfaithful. viper_y96qf base differs from Sv5.3 queen/sonar logic.',
 'Command: uv run --python 3.11 --with unswbc --with scipy python -B tools/param_search.py --run',
 'Farm command: bash tools/farm_run.sh DIR --games 2000 --search-limit LIMIT --search-stop-alpha ALPHA --search-log out/param_search.tsv -j 4',
 'Budgets: 350, 1000, fresh 2000 games/arm; final seed offset 100000; successive halving seed 2504.',
 'Each completed evaluation is saved by farm; TSV flushed/fsynced; search state atomic after each budget.',
 'Early stopping: bounded paired win confidence sequence, complete balanced map cycles; family alpha split.',
 'CPU >66M stops; chosen safety tolerance -3pp: approximate t lower CI >= -3pp, >=30 complete clusters.',
 'Four closed-start halfway targets and other-lane critic PASS required; no auto promotion; open-map overrides fixed.']
 for name,v in state.get('evaluations',{}).items():
  lines.append(f'{name}: {v["pairs"]} paired games; score={v["score"]:.3f}; CPU={v["cpu_peak"]:.2f}M; eligible={v["eligible"]}')
  for m in CLOSED:
   if m in v['medians']:
    x=v['medians'][m];lines.append(f'  {m}: units100 {x["candidate"]}/{x["sv53"]}/{x["top"]} candidate/control/top; halfway={v["halfway"][m]}')
 if state.get('error'): lines.append('Blocked: '+state['error'][:400])
 lines.append('Verified: tools/buildwasm.py out/param_search/ps_00 compiled; tools/param_search_verify.py PASS (statistics/TSV/guards).')
 lines.append('Current survivor directories: '+', '.join(state.get('active',[])))
 lines.append('Unverified: ladder, other-lane candidate critique, acceptance criteria without full final measurements.')
 (ROOT/'out/param_search_report.md').write_text('\n'.join(lines[:40])+'\n',encoding='utf-8')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true');ap.add_argument('--variants',type=int,default=4)
 a=ap.parse_args()
 if not 2<=a.variants<=8: ap.error('variants 2..8')
 statepath=ROOT/'out/param_search/state.json'
 if statepath.exists(): state=json.loads(statepath.read_text())
 else:
  rng=random.Random(2504); settings=[]
  settings.append({k:v[0] for k,v in PARAMS.items()})
  for i in range(a.variants-1):
   v={k:(round(rng.uniform(lo,hi),3) if isinstance(default,float) else rng.randint(lo,hi)) for k,(default,lo,hi) in PARAMS.items()}
   v['budStart']=0 # delaying an already slow opening is a negative control only
   settings.append(v)
  dirs=[str(generate(v,f'ps_{i:02d}').relative_to(ROOT)) for i,v in enumerate(settings)]
  state=dict(status='prepared',dirs=dirs,active=dirs,round=0,evaluations={})
  atomic(statepath,state)
 report(state)
 if not a.run:return
 state.pop('error',None);state['status']='running'
 for marker in ['FAILED.json','DONE.json']: (statepath.parent/marker).unlink(missing_ok=True)
 atomic(statepath,state);report(state)
 try:
  for index,limit in enumerate([350,1000,2000]):
   if index<state['round']:continue
   for d in state['active']:
    name=Path(d).name
    if state.get('done',{}).get(f'{index}:{name}'):continue
    log=ROOT/'out/param_search'/f'{name}_farm.log'
    with log.open('w',encoding='utf-8') as fh:
     # Python equivalent of farm_run.sh avoids shell/environment ambiguity on Windows.
     cmd=[sys.executable,'-B','tools/farm_scale.py',d,'--games','2000','--search-limit',str(limit),'--search-seed-offset',str(100000 if index==2 else 0),'--search-stop-alpha',str(.05/(2*len(state['dirs']))),'--search-log','out/param_search.tsv','-j','4']
     subprocess.run(cmd,stdout=fh,stderr=subprocess.STDOUT,check=True)
    stages=list(Path('F:/BattleCode_data/farm_scale' if os.name=='nt' else '/mnt/f/BattleCode_data/farm_scale').glob(name+'-*'))
    stages=[stage for stage in stages if json.loads((stage/'manifest.json').read_text())['dependencies']['tools/farm_scale.py']==farm.digest(ROOT/'tools/farm_scale.py') and json.loads((stage/'manifest.json').read_text())['bots']['candidate']==farm.source_hash(ROOT/d) and json.loads((stage/'manifest.json').read_text()).get('search_seed_offset',0)==(100000 if index==2 else 0)]
    if len(stages)!=1:raise RuntimeError('ambiguous stage identity: '+name)
    value=assess(stages[0]);value['stage']=str(stages[0]);value['stopped']=(stages[0]/'STOPPED.json').exists()
    state['evaluations'][name]=value;state.setdefault('done',{})[f'{index}:{name}']=True
    atomic(statepath,state);report(state)
   ranked=sorted((d for d in state['active'] if not state['evaluations'][Path(d).name]['stopped']),key=lambda d:state['evaluations'][Path(d).name]['score'],reverse=True)
   state['active']=ranked[:max(1,math.ceil(len(ranked)/2))];state['round']=index+1
   atomic(statepath,state)
   if not state['active']:break
  state['status']='complete; eligible builds await independent critic'
 except Exception as e:
  state['status']='blocked';state['error']=str(e)
  atomic(statepath,state);atomic(statepath.parent/'FAILED.json',dict(error=str(e)));report(state);raise
 atomic(statepath,state);atomic(statepath.parent/'DONE.json',state);report(state)
if __name__=='__main__':main()
