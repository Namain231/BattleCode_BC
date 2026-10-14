"""Sequential guarded panels, local only; per-game resume is panel_zig's cache."""
import sys
sys.dont_write_bytecode=True
import subprocess, json, time, shutil
import ctypes
from pathlib import Path
from kamikaze_report import validate_panel
import os, hashlib

MAPS='around_unsw,australia,islands,maze,stripes,tower_defense,weakhold'

def disk_guard():
    for drive,minimum in [('C:/',3),('F:/',6)]:
        if shutil.disk_usage(drive).free<minimum*1024**3: raise RuntimeError(drive+' below disk guard')


def native_judges():
    if os.name!='nt': return 0
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',"@(Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*loong-judge*' }).Count"],capture_output=True,text=True,check=True)
    return int(result.stdout.strip())


def guard():
    while True:
        disk_guard()
        p=subprocess.run(['wsl','-d','Ubuntu','--','pgrep','-c','loong-judge'],capture_output=True,text=True)
        if p.returncode not in (0,1): raise RuntimeError('Cannot establish judge count: '+p.stderr)
        count=int(p.stdout.strip() or '0')+native_judges()
        free=shutil.disk_usage('C:/').free
        if free<3*1024**3: raise RuntimeError('C: below 3 GiB disk guard')
        if count==0: break
        print('Waiting for other judges:',count,flush=True); time.sleep(20)
    subprocess.run(['C:/Program Files/Git/bin/bash.exe','tools/mem_guard.sh','1800'],check=True)
    disk_guard()
    # Other orchestrators may have started a new batch while the memory guard waited.
    p=subprocess.run(['wsl','-d','Ubuntu','--','pgrep','-c','loong-judge'],capture_output=True,text=True)
    if p.returncode not in (0,1): raise RuntimeError('Cannot recheck judge count')
    if int(p.stdout.strip() or '0')+native_judges():
        return guard()
    class Status(ctypes.Structure):
        _fields_=[('size',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ('total','free','page','pagefree','virtual','virtualfree','extended')]
    s=Status(); s.size=ctypes.sizeof(s)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)): raise OSError('Cannot read memory')
    return 2 if s.free>=2500*1024**2 else 1

def offline_ready():
    data_path=Path('out/kz_measure.json'); meta_path=Path('out/kz_measure.identity.json')
    if not Path('out/kz_measure.DONE').exists() or not data_path.exists() or not meta_path.exists(): return False
    data=json.loads(data_path.read_text()); meta=json.loads(meta_path.read_text())
    version=hashlib.sha256(Path('tools/kamikaze_measure.py').read_bytes()+Path('tools/replay_lite.py').read_bytes()+Path('tools/engine_sim.py').read_bytes()).hexdigest()
    expected={str(Path('ladder',folder,str(g['game'])+'.replay')) for folder,want in [('l10','17124'),('sv53','16651'),('sv52','16106')] for g in json.loads(Path('ladder',folder,'games.json').read_text(encoding='utf-8')) if str(g.get('bot',want))==want}
    if set(data)!=expected or set(meta)!=expected or any(m.get('version')!=version for m in meta.values()): return False
    if any(r and r.get('validation') for r in data.values()): raise ValueError('Offline reconstruction errors')
    return True


def main():
    os.environ['KAMIKAZE_GUARDS']='1'
    while not offline_ready():
        print('Waiting for offline audit to finish first',flush=True); time.sleep(20)
    for bot,out,maps,seeds,j in [('viper_y96nk','out/kz_smoke_current','maze','3',1),
                                ('viper_y96nk','out/kz_panel',MAPS,'3,4,5,6,7,8,9',2),
                                ('baselines/Nv30','out/kz_ctl',MAPS,'3,4,5,6,7,8,9',2)]:
        workers=guard(); j=min(j,workers); dest=Path(out); dest.mkdir(parents=True,exist_ok=True)
        cmd=[sys.executable,'-B','tools/panel_zig.py',bot,'baselines/Y9_6',out,'--maps',maps,'--seeds',seeds,'-j',str(j)]
        (dest/'command.json').write_text(json.dumps(cmd),encoding='utf-8')
        print('RUN', ' '.join(cmd),flush=True)
        with (dest/'run.log').open('a',encoding='utf-8') as f: subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
        subprocess.run([sys.executable,'-B','tools/kamikaze_measure.py','--panel',out,'--output',out+'/audit.json'],check=True)
        rows,validated=validate_panel(out); audit={str(i):r for i,r in enumerate(validated)}
        print(out,dict(wins=sum(r['win'] for r in rows),games=len(rows),cpu=max(r['cpu_max_ours_M'] for r in rows),rams=sum(r.get('queen_rams',r['rams']) for r in audit.values()),kills=sum(r['ramkills'] for r in audit.values()),queen_deaths=sum(r['queen_dead'] for r in audit.values())),flush=True)
        (dest/'DONE').write_text('complete\n',encoding='utf-8')
    candidate,_=validate_panel('out/kz_panel'); control,_=validate_panel('out/kz_ctl')
    if {(r['map'],r['seed'],r['side']) for r in candidate}!={(r['map'],r['seed'],r['side']) for r in control}: raise ValueError('Unpaired panels')
    if not offline_ready(): raise ValueError('Offline audit changed during panels')
    subprocess.run([sys.executable,'-B','tools/kamikaze_report.py'],check=True)
    Path('out/kz_work/DONE').write_text('panels complete\n',encoding='utf-8')
    subprocess.run(['C:/Program Files/Git/bin/bash.exe','-lc',"printf '%s\\n' '- [2026-10-07] [executor] [kamikaze] Offline audit, deterministic unit and sequential local candidate/control panels complete; see out/kamikaze_report.md; no submission.' >> AGENT_LOG.md"],check=True)

if __name__=='__main__': main()
