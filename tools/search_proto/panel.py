"""Compact panel; temporary replay extracts queen deaths then is deleted. No pickle."""
import argparse
import hashlib
import concurrent.futures
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

ROOT=pathlib.Path(__file__).resolve().parents[2]
MAPS='trauma autarky trophy default dilemma devil slithery_fight schooltime portals queen_of_spades'.split()
JUDGE='/home/sohan/toolchains/zig-judge-out-serve/bin/loong-judge'

def memory_guard():
    command=['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-Command',
             '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory']
    while True:
        check=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        if check.returncode: raise RuntimeError('Windows memory guard query failed')
        free_mb=int(check.stdout.strip())/1024
        if free_mb>=3000: return free_mb
        print(f'memory guard waiting: {free_mb:.0f}MB free',flush=True)
        time.sleep(20)


def game(args,mode,map_name,side):
    source_hash=hashlib.sha256((ROOT/'tools/search_proto/serve_search.py').read_bytes()).hexdigest()
    if shutil.disk_usage('/mnt/c').free < 1500000000:
        raise RuntimeError('Windows C disk below 1.5GB floor')
    out=pathlib.Path(args.out); out.mkdir(parents=True,exist_ok=True)
    name=f'{mode}_{map_name}_{side}'; result_path=out/(name+'.json')
    if result_path.exists():
        old=json.loads(result_path.read_text())
        if old.get('complete') and old.get('judge_exit')==0 and old.get('policy_sha256')==source_hash and (mode=='trivial' or old.get('queen_death_rounds_exact')): return old
    sock=f'/tmp/s3_{os.getpid()}_{name}.sock'
    replay=pathlib.Path(f'/tmp/s3_{os.getpid()}_{name}.replay')
    pathlib.Path(sock).unlink(missing_ok=True)
    server_cmd=[sys.executable,str(ROOT/'tools/search_proto/serve_search.py'),'--map',str(ROOT/'maps'/f'{map_name}.map'),
                '--socket',sock,'--out',str(result_path),'--mode',mode,'--depth','1' if mode=='depth1' else '3']
    if mode=='noqueen': server_cmd+=['--noqueen']
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    start=time.time()
    with (out/(name+'.server.log')).open('w') as log:
        server=subprocess.Popen(server_cmd,stdout=log,stderr=log,env=env)
        try:
            for _ in range(300):
                if pathlib.Path(sock).exists(): break
                if server.poll() is not None: raise RuntimeError(f'{name}: server failed; see server.log')
                time.sleep(.1)
            else: raise RuntimeError('socket startup timeout')
            judge_cmd=[JUDGE,'--engine',args.engine,'--timeout',str(args.timeout),
                       '--map',str(ROOT/'maps'/f'{map_name}.map'),'--a',args.bot,'--b',args.bot,
                       '--seed','1','--serve',sock,'--serve-team',side,'--replay',str(replay)]
            judge=subprocess.run(judge_cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                                 timeout=args.timeout+30,env=env)
            server.wait(timeout=30)
            result=json.loads(result_path.read_text())
            result.update(judge_exit=judge.returncode,server_exit=server.returncode,wall_s=time.time()-start,
                          judge_output=judge.stdout,engine=args.engine,bot=args.bot,policy_sha256=source_hash)
            if not replay.exists() and mode!='trivial':
                raise RuntimeError(f'{name}: exact queen telemetry replay missing')
            if replay.exists():
                sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'ml')]
                from p8_sensitivity import iter_events
                rnd=-1; deaths={}
                for event in iter_events(replay):
                    if event['kind']=='roundStart': rnd=event['round']
                    elif event['kind']=='dragonDeath' and event['id'] in (0,1): deaths[str(event['id'])]=rnd
                result['queen_death_rounds_last_served_estimate']=result['queen_death_rounds']
                result['queen_death_rounds']=deaths
                result['queen_death_rounds_exact']=True
                replay.unlink()
            result_path.write_text(json.dumps(result,indent=2))
            if not result.get('complete') or judge.returncode or server.returncode:
                raise RuntimeError(f'{name}: incomplete or process error')
            print(json.dumps({k:result[k] for k in ('mode','map','side','winner','rounds','wall_s','turn_ms_mean')}),flush=True)
            return result
        finally:
            if server.poll() is None: server.terminate(); server.wait(timeout=10)
            pathlib.Path(sock).unlink(missing_ok=True)
            replay.unlink(missing_ok=True)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--engine',required=True); ap.add_argument('--bot',default=str(ROOT/'wasm_cache/vB19-4c23c57aea0e3e6f.wasm'))
    ap.add_argument('--modes',default='trivial,net,search,depth1,noqueen'); ap.add_argument('--maps',default=','.join(MAPS))
    ap.add_argument('--jobs',type=int,default=2); ap.add_argument('--timeout',type=int,default=1800); ap.add_argument('--out',required=True)
    a=ap.parse_args(); assert 1<=a.jobs<=2
    pathlib.Path(a.out).mkdir(parents=True,exist_ok=True)
    pathlib.Path(a.out,'chain_done.json').unlink(missing_ok=True)
    for mode in a.modes.split(','):
        pathlib.Path(a.out,'chain_state.json').write_text(json.dumps({'mode':mode,'started_epoch':time.time(),'complete':False}))
        free_mb=memory_guard()
        print(f'{mode}: memory guard {free_mb:.0f}MB free',flush=True)
        jobs=[(m,s) for m in a.maps.split(',') for s in 'AB']
        if mode=='trivial': jobs=[('default','B')]
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
            futures=[pool.submit(game,a,mode,m,s) for m,s in jobs]
            results=[f.result() for f in futures]
        wins=sum(r['winner']==r['side'] for r in results)
        summary={'mode':mode,'wins':wins,'games':len(results),'draws':sum(r['winner']=='-' for r in results),
                 'policy_sha256':sorted({r.get('policy_sha256','legacy') for r in results}),'results':results}
        pathlib.Path(a.out,f'{mode}_summary.json').write_text(json.dumps(summary,indent=2))
        milestone={'trivial':'M0','net':'M1','search':'M2','depth1':'M3','noqueen':'M3'}[mode]
        label='pilot' if len(results)<20 and mode!='trivial' else 'panel'
        with (ROOT/'AGENT_LOG.md').open('a',encoding='utf-8',newline='\n') as log:
            exact=all(r.get('queen_death_rounds_exact',False) for r in results)
            log.write(f'- [2026-10-02] [executor] [search_followup] {milestone} {mode} {label} {wins}/{len(results)} wins; exact queen telemetry={exact}.\n')
        print(f'{mode}: {wins}/{len(results)}',flush=True)
    pathlib.Path(a.out,'chain_done.json').write_text(json.dumps({'complete':True,'modes':a.modes,'maps':a.maps}))
    pathlib.Path(a.out,'chain_state.json').write_text(json.dumps({'complete':True,'modes':a.modes}))


if __name__=='__main__': main()
