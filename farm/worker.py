"""Offline private-bundle shard worker; no installation or network access."""
import argparse, json, os, sys, concurrent.futures as CF
from pathlib import Path
os.environ['FARM_REMOTE']='1'
os.environ.setdefault('FARM_LANE','kaggle')
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import farm_scale as farm
def main():
    ap=argparse.ArgumentParser();ap.add_argument('shard');ap.add_argument('-j',type=int,default=2)
    a=ap.parse_args()
    if not 1<=a.j<=2: ap.error('remote workers capped at 2 until representative peak RSS is measured')
    os.chdir(ROOT)
    farm.panel.ROOT=str(ROOT)
    farm.panel.JUDGE=str(ROOT/'loong-judge')
    farm.panel.ENGINE=str(ROOT/'engine.wasm')
    farm.panel.USE_WSL=False
    (ROOT/'loong-judge').chmod(0o755)
    jobs=json.loads((ROOT/a.shard).read_text())
    # Translate bundled map paths without exposing the original repository.
    for j in jobs:
        original=j['map']
        src=ROOT/'maps'/('dev' if '/' in original else 'live')/(Path(original).name+'.map')
        dst=ROOT/(original+'.map' if '/' in original else 'maps/'+original+'.map')
        dst.parent.mkdir(parents=True,exist_ok=True)
        if src!=dst:
            import shutil
            shutil.copy2(src,dst)
    farm.verify_seal(ROOT)
    farm.memory_guard(a.j)
    farm.checkpoints(ROOT)
    with farm.panel.panel_lock(str(ROOT)):
        with CF.ThreadPoolExecutor(a.j) as pool:
            for f in CF.as_completed([pool.submit(farm.evaluate,j,ROOT) for j in jobs]): f.result()
    print(f'{len(jobs)} evaluation checkpoints in state/; collect them with --import-results')
if __name__=='__main__': main()
