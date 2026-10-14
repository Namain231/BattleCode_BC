import json, subprocess, sys, re, time, hashlib, statistics as st
from pathlib import Path
ROOT=Path.cwd(); OUT=ROOT/'out/opening_fix'; OUT.mkdir(exist_ok=True)
STATE=OUT/'state.json'
state=json.loads(STATE.read_text()) if STATE.exists() else {'evaluations':{},'safety_looks':0}
def save():
 p=STATE.with_suffix('.tmp'); p.write_text(json.dumps(state,indent=2),encoding='utf-8');p.replace(STATE)
def run(cmd,log):
 with log.open('w',encoding='utf-8') as fh:
  p=subprocess.run(cmd,stdout=fh,stderr=subprocess.STDOUT,cwd=ROOT)
 if p.returncode:raise RuntimeError(str(cmd)+' failed; '+str(log))
def summary(folder):
 rows=json.loads((folder/'summary.json').read_text()); result={}
 manifest=json.loads((folder/'inputs.json').read_text());expected={(m,int(seed),side) for m in manifest['maps'] for seed in manifest['seeds'].split(',') for side in 'AB'}
 assert {(r['map'],r['seed'],r['side']) for r in rows}==expected and len(rows)==len(expected),'Panel coverage mismatch'
 for r in rows:
  assert r['cpu_max_ours_M'] is not None,'Missing CPU'
  for rnd in (50,100): assert str(rnd) in r['snaps'] or r['rounds']<rnd,'Missing snapshot in running game'
 for m in sorted({r['map'] for r in rows}):
  rs=[r for r in rows if r['map']==m]
  result[m]={'wins':sum(r['win'] for r in rs),'n':len(rs),'units50':st.median(r['snaps'].get('50',[r['ours']['count']])[0] for r in rs),'units100':st.median(r['snaps'].get('100',[r['ours']['count']])[0] for r in rs)}
 return {'wins':sum(r['win'] for r in rows),'games':len(rows),'cpu':max(r['cpu_max_ours_M'] for r in rows),'maps':result}
base=(ROOT/'viper_y96qo/main.cpp').read_text(encoding='utf-8')
base=base.replace('bool opening = true,','bool openingCycleEnabled = true, openingUnwindEnabled = true;\n    bool opening = true,')
base=base.replace('if (!openingActive() || isTrueQueen() || MY_LEN < 4 || body.empty())','if (!openingActive() || !P.openingUnwindEnabled || isTrueQueen() || MY_LEN < 4 || body.empty())')
base=base.replace('openingCycle = ROUND - openingLastEat', 'openingCycle = P.openingCycleEnabled && ROUND - openingLastEat')
# Routing remains available to independent queen and portal consumers.
base=base.replace('if (openingCycle && !o.sim.cells.empty())','if (P.openingRoute && openingCycle && !o.sim.cells.empty())')
flags={'cycle':'openingCycleEnabled','split':'openingBud','unwind':'openingUnwindEnabled','separation':'openingChild','portal':'openingPortal','queen':'openingQueen'}
CLOSED='stripes,tower_defense,queen_of_spades,dilemma'; OPEN='around_unsw,australia,islands,maze'
def workers(kind=None):
 cmd=['powershell','-NoProfile','-Command',"@(Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*loong*' }).Count"]
 n=int(subprocess.check_output(cmd,text=True).strip()); w=subprocess.run(['wsl','-d',__import__('os').environ.get('WSL_DISTRO','Ubuntu'),'--','pgrep','-c','-x','loong-judge'],capture_output=True,text=True); assert w.returncode in (0,1),w.stderr; n+=int(w.stdout.strip() or '0'); free=int(subprocess.check_output(['powershell','-NoProfile','-Command','(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'],text=True).strip())/1024; return 2 if n or (kind!='closed' and free<3500) else 4
def guard():
 import shutil
 while True:
  free=int(subprocess.check_output(['powershell','-NoProfile','-Command','(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'],text=True).strip())/1024
  if free>=2200:break
  print('Waiting for RAM',round(free),flush=True);time.sleep(20)
 if shutil.disk_usage('C:/').free<3*1024**3:raise RuntimeError('C disk guard')
def evaluate(name,source,kind):
 key='v2_'+name+'_'+kind; digest=hashlib.sha256(source.encode()).hexdigest()
 if key in state['evaluations']:
  assert state['evaluations'][key]['source_hash']==digest
 (ROOT/'viper_y96qo2/main.cpp').write_text(source,encoding='utf-8')
 snapshot=OUT/(name+'.cpp');snapshot.write_text(source,encoding='utf-8')
 maps,seeds=(CLOSED,'1,2,3,4,5,6,7,8') if kind=='closed' else (OPEN,'3,4')
 if kind=='safety':maps,seeds='around_unsw,australia,islands,maze,stripes,tower_defense,weakhold','3,4,5,6,7,8,9'
 folder=OUT/key; folder.mkdir(exist_ok=True)
 def build_hashes(d):
  return {str(p.relative_to(d)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(d).rglob('*') if p.suffix in ('.c','.cpp','.cxx','.cc','.hpp','.h','.toml')}
 inputs={'source':digest,'candidate':build_hashes(ROOT/'viper_y96qo2'),'opponent':build_hashes(ROOT/'baselines/Y9_6'),'maps':{m:hashlib.sha256((ROOT/'maps'/(m+'.map')).read_bytes()).hexdigest() for m in maps.split(',')},'seeds':seeds,'sides':'AB'}
 manifest=folder/'inputs.json'
 if manifest.exists(): assert json.loads(manifest.read_text())==inputs,'Cache inputs changed: '+key
 else: manifest.write_text(json.dumps(inputs,indent=2),encoding='utf-8')
 if key in state['evaluations']: return state['evaluations'][key]
 guard(); j=workers(kind)
 cmd=[sys.executable,'-B','tools/panel_zig.py','viper_y96qo2','baselines/Y9_6',str(folder),'--maps',maps,'--seeds',seeds,'-j',str(j)]
 if kind=='safety':state['safety_looks']+=1;save()
 print('START',key,'workers',j,flush=True);run(cmd,OUT/(key+'.log'))
 r=summary(folder);r.update(source_hash=digest,command=subprocess.list2cmdline(cmd));state['evaluations'][key]=r;save();print('RESULT',key,json.dumps(r),flush=True);return r
if __name__=='__main__':
 for kind in ['open','closed']:
  for part in ['cycle','queen','split','separation','portal','unwind']:
   flag=flags[part]
   source,n=re.subn(r'\b'+flag+r' = true',flag+' = false',base); assert n==1,(flag,n)
   evaluate('off_'+part,source,kind)
 (ROOT/'viper_y96qo2/main.cpp').write_text(base,encoding='utf-8')
 print('ABLATIONS DONE',flush=True)

def compose_source(disabled=(), stall_only=True):
 """Preserve the opening design; strengthen its exit/risk guards and optionally narrow routing."""
 source=base
 for part in disabled:
  flag=flags[part]; source,n=re.subn(r'\b'+flag+r' = true',flag+' = false',source);assert n==1,(part,n)
 if stall_only:
  old='if (!P.openingRoute || elapsedMs() > 15 || ROUND - openingLastEat < P.openingCycleK) return;'
  new='if (!P.openingRoute || elapsedMs() > 15 || ROUND - openingLastEat < P.openingCycleK || ROUND - openingLastNew < P.openingCycleK) return;'
  assert source.count(old)==1;source=source.replace(old,new)
 # Only observed ordinary edges and paired portal edges qualify as known exits.
 for endpoint,exitflag in [('tail','childExit'),('body[0]','parentExit')]:
  old=f'if (n >= 0 && !occId[n] && otherBT[n] <= 0) {exitflag} = true;'
  new=f'if (n >= 0 && (effK({endpoint}, d) == 1 || effK({endpoint}, d) == 3) && !occId[n] && otherBT[n] <= 0) {exitflag} = true;'
  assert source.count(old)==1;source=source.replace(old,new)
 old='if (openingActive() && !isTrueQueen() && !opts.empty()) {\n        for (auto& o : opts)'
 new='if (openingActive() && !isTrueQueen() && !opts.empty()) {\n        const auto openingBaselineOptions = opts;\n        const auto& openingBaseline = openingBaselineOptions[0];\n        for (auto& o : opts)'
 assert source.count(old)==1;source=source.replace(old,new)
 old='route.ev.safeClass == opts[0].ev.safeClass && route.ev.pDeath <= 0.25'
 new='route.ev.safeClass == openingBaseline.ev.safeClass && route.ev.pDeath <= openingBaseline.ev.pDeath && route.ev.surv >= openingBaseline.ev.surv'
 assert source.count(old)==1;source=source.replace(old,new)
 old='''        }
    }
    if ((opts.empty() || opts[0].ev.pDeath'''
 new='''        }
        // Opening preferences must preserve the original move's measured risk and survival.
        if (opts[0].ev.pDeath > openingBaseline.ev.pDeath || opts[0].ev.safeClass < openingBaseline.ev.safeClass || opts[0].ev.surv < openingBaseline.ev.surv)
            opts = openingBaselineOptions;
    }
    if ((opts.empty() || opts[0].ev.pDeath'''
 assert source.count(old)==1;source=source.replace(old,new)
 return source
