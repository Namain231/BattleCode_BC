"""Small fault-injection checks; no API calls, panels or real dataset mutation."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import warnings
warnings.filterwarnings('ignore',category=FutureWarning)
import numpy as np
import torch

ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(ROOT / 'ml/v6'))
from shard_manifest import owned_shards, sha256


def rejected(fn):
    try: fn()
    except (AssertionError, ValueError): return
    raise AssertionError('unsafe input was accepted')


with tempfile.TemporaryDirectory(prefix='nn4_verify_', dir=ROOT/'out') as temporary:
    scratch = Path(temporary); data = scratch/'data'; data.mkdir()
    rng = np.random.default_rng(1)
    p = rng.integers(0, 256, (16,19,15,15),dtype=np.uint8); p[:,8] = 0
    ids = np.repeat([1,2,3,4],4); meta = np.zeros((16,12),dtype=np.int64); meta[:,0] = ids
    arrays = dict(planes=p,scalars=rng.random((16,6),dtype=np.float32),labels=np.arange(16,dtype=np.uint8)%7,
                  weights=np.ones(16,np.float32),meta=meta,game=ids)
    shard = data/'shard_owned.npz'; np.savez_compressed(shard,**arrays)
    np.savez_compressed(data/'shard_orphan.npz',**arrays)
    manifest = dict(schema_version='v6.fixture',games=[dict(game=i) for i in range(1,5)],exported_game_ids=list(range(1,5)),
                    shards=[dict(file=shard.name,samples=16,sha256=sha256(shard))],total_samples=16)
    (data/'manifest.json').write_text(json.dumps(manifest))
    assert owned_shards(data) == [str(shard)]
    owned_shards(data,scratch/'audit.json')
    original = shard.read_bytes(); shard.write_bytes(original+b'changed')
    rejected(lambda: owned_shards(data)); shard.write_bytes(original)
    (scratch/'holdout.json').write_text('[4]')
    # Run both on CPU for exact tensor comparison and inject a crash between
    # committed checkpoint and publication of its derived best file.
    harness = scratch/'train_harness.py'
    harness.write_text("""import os,runpy,sys,torch
torch.cuda.is_available=lambda:False
torch.set_num_threads(1)
original=torch.save
def save(obj,path,*args,**kwargs):
    if os.environ.get('INJECT') and str(path).endswith('best.pt.tmp'):
        raise RuntimeError('injected publication crash')
    return original(obj,path,*args,**kwargs)
torch.save=save
sys.argv=['train_v6.py']+sys.argv[1:]
runpy.run_path('ml/v6/train_v6.py',run_name='__main__')
""",encoding='utf-8')
    args=['--data',str(data),'--val-data',str(data),'--val-games',str(scratch/'holdout.json'),
          '--epochs','2','--batch','4','--channels','4','--hidden','8']
    def train(directory,inject=False,resume=False):
        env=os.environ.copy(); env.pop('INJECT',None)
        if inject: env['INJECT']='1'
        return subprocess.run([sys.executable,'-B',str(harness),*args,'--out',str(scratch/directory/'v6.pt')]+(['--resume'] if resume else []),
                              cwd=ROOT,env=env,capture_output=True,text=True)
    r=train('full'); assert r.returncode==0,r.stderr
    r=train('crashed',inject=True); assert r.returncode!=0 and 'injected publication crash' in r.stderr
    r=train('crashed',resume=True); assert r.returncode==0,r.stderr
    export_data=scratch/'export'; export_data.mkdir()
    expanded={k:np.concatenate([v]*8) for k,v in arrays.items()}
    export_shard=export_data/'shard_owned.npz'; np.savez_compressed(export_shard,**expanded)
    orphan=dict(expanded,planes=np.zeros_like(expanded['planes']))
    np.savez_compressed(export_data/'shard_orphan.npz',**orphan)
    export_manifest=dict(manifest,shards=[dict(file=export_shard.name,samples=128,sha256=sha256(export_shard))],total_samples=128)
    (export_data/'manifest.json').write_text(json.dumps(export_manifest))
    legacy=scratch/'legacy'; legacy.mkdir()
    np.savez_compressed(legacy/'shard_0000.npz',**expanded)
    (legacy/'manifest.json').write_text(json.dumps([{'legacy':True}]))
    for directory in [export_data,legacy]:
        target=scratch/(directory.name+'.hpp')
        r=subprocess.run([sys.executable,'-B','ml/export_cpp.py',str(scratch/'full/best.pt'),str(target),'--data',str(directory)],cwd=ROOT,capture_output=True,text=True)
        assert r.returncode==0,r.stderr
        vector=target.read_text().split('NN_TEST_PLANES',1)[1].split('{',1)[1].split('}',1)[0]
        assert list(map(int,vector.split(',')))==expanded['planes'][123].reshape(-1).tolist()
    for file in ['last.pt','best.pt']:
        full=torch.load(scratch/'full'/file,map_location='cpu')['state_dict']
        resumed=torch.load(scratch/'crashed'/file,map_location='cpu')['state_dict']
        assert all(torch.equal(full[k],resumed[k]) for k in full), 'resume changed '+file
    checkpoint=torch.load(scratch/'crashed/v6.ckpt',map_location='cpu')
    assert checkpoint['epoch']==len(checkpoint['metrics'])==2
    r=subprocess.run([sys.executable,'-B',str(harness),*args,'--out',str(scratch/'crashed/v6.pt'),'--resume','--lr','.01'],cwd=ROOT,capture_output=True,text=True)
    assert r.returncode!=0 and 'configuration changed' in r.stderr
    spec=importlib.util.spec_from_file_location('nn4',ROOT/'tools/nn_refresh4.py')
    nn=importlib.util.module_from_spec(spec); spec.loader.exec_module(nn)
    for value in [None,float('nan'),float('inf'),70,0]: rejected(lambda v=value: nn.check_cpu([{'cpu_max_ours_M':v}]))
    nn.check_cpu([{'cpu_max_ours_M':66}])
    control=dict(cpu_max_M=65,games=98,wins=50,queen_deaths=10,units100_mean=20)
    candidate=dict(control,wins=58,cpu_max_M=70)
    rejected(lambda:nn.worthwhile(candidate,control))
    assert nn.worthwhile(dict(candidate,cpu_max_M=65),control)
    assert not nn.worthwhile(dict(control,wins=51),control)
    source=scratch/'source'; target=scratch/'target'; source.write_text('a'); target.write_text('b')
    nn.STATE=scratch/'state.json'; nn.report=lambda _:None; nn.state={'done':[],'commands':[]}
    assert not nn.cached('test',[source],[target]); nn.done('test'); assert nn.cached('test',[source],[target])
    source.write_text('changed'); rejected(lambda:nn.cached('test',[source],[target]))
    source.write_text('a'); target.write_text('changed'); rejected(lambda:nn.cached('test',[source],[target]))
    assert not nn.cached('midrun',[source],[target]); source.write_text('changed during command')
    rejected(lambda:nn.done('midrun')); assert 'midrun' not in nn.state['done']
    # A fetched series covers sibling IDs, including pre-existing retries.
    os.environ.setdefault('UNSWBC_KEY','unused-offline-fixture')
    spec=importlib.util.spec_from_file_location('sweep_fixture',ROOT/'ladder/scout_v6/sweep.py')
    sweep=importlib.util.module_from_spec(spec); spec.loader.exec_module(sweep)
    sweep.OUT=scratch/'scout'; sweep.OUT.mkdir(); sweep.TOP=sweep.OUT/'top'
    sweep.STATE=sweep.OUT/'state.json'; sweep.MAN=sweep.OUT/'manifest.csv'
    sweep.STATE.write_text(json.dumps({'scanned':[],'retry':[1,2]}))
    sweep.get=lambda _: {'match':{'status':'completed','ranked':False},'games':[{'id':1},{'id':2}]}
    old_args=sys.argv; sys.argv=['sweep','--start','2','--scan','2']
    sweep.main()
    assert json.loads((sweep.OUT/'sweep_window_2.json').read_text())['complete']
    sweep.STATE.write_text(json.dumps({'scanned':[],'retry':[]}))
    old_disk=sweep.shutil.disk_usage
    class NoSpace: free=0
    sweep.shutil.disk_usage=lambda _:NoSpace()
    try:
        sweep.main()
    except SystemExit as e: assert e.code==2
    else: raise AssertionError('disk early exit reported success')
    finally: sweep.shutil.disk_usage=old_disk; sys.argv=old_args
    assert not json.loads((sweep.OUT/'sweep_window_2.json').read_text())['complete']
    sweep.shutil.disk_usage=old_disk
    sweep.STATE.write_text(json.dumps({'scanned':[],'retry':[]}))
    sys.argv=['sweep','--start','2','--scan','2']
    sweep.get=lambda _: {'error':'No such battle.'}
    sweep.main(); assert json.loads((sweep.OUT/'sweep_window_2.json').read_text())['complete']
    sweep.STATE.write_text(json.dumps({'scanned':[],'retry':[]}))
    sweep.get=lambda _: {'match':{'status':'draw'},'games':[{'id':1},{'id':2}]}
    sweep.main(); assert json.loads((sweep.OUT/'sweep_window_2.json').read_text())['complete']
    sys.argv=old_args
    # Exercise the fallback array invocation with a fake Zig compiler.
    compiler=scratch/'home/toolchains/zig-linux/zig'; compiler.parent.mkdir(parents=True)
    compiler.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n',encoding='utf-8'); compiler.chmod(0o755)
    bash=scratch/'fallback.sh'
    bash.write_text('''#!/bin/bash
HOME="$1"
which() { return 1; }
if which g++ >/dev/null 2>&1; then CXX=(g++); else CXX=("$HOME/toolchains/zig-linux/zig" c++); fi
"${CXX[@]}" -O2
''',encoding='utf-8')
    r=subprocess.run([nn.BASH,str(bash),str(scratch/'home')],capture_output=True,text=True)
    assert r.returncode==0 and r.stdout.splitlines()==['c++','-O2'],r.stderr
    # Reject a complete-looking panel with an unsafe later seed.
    folder=scratch/'panel'; folder.mkdir()
    rows=[{'map':m,'seed':seed,'side':side,'cpu_max_ours_M':65} for m in nn.MAPS.split(',') for seed in range(3,10) for side in 'AB']
    rows[-1]['cpu_max_ours_M']=70
    (folder/'summary.json').write_text(json.dumps(rows)); rejected(lambda:nn.stats(str(folder)))
    # Check compiled-game/runtime provenance without invoking a judge.
    import types
    bot=scratch/'bot'; bot.mkdir(); (bot/'main.cpp').write_text('fixture')
    engine=scratch/'engine'; engine.write_bytes(b'engine')
    wa=scratch/'a.wasm'; wa.write_bytes(b'a'); wb=scratch/'b.wasm'; wb.write_bytes(b'b')
    identity=dict(bot_dir=str(bot),bot=nn.fingerprint(bot),opp=nn.fingerprint('baselines/Y9_6'),
                  maps={'around_unsw':sha256(ROOT/'maps/around_unsw.map')},seeds='3',execution='Windows/WSL',
                  dependencies=nn.artifact_hashes(['tools/analyze_ours.py']),judge='judge-hash',engine=sha256(engine))
    (folder/'nn_refresh4_identity.json').write_text(json.dumps(identity))
    for side in 'AB':
        record=dict(version=2,ours=sha256(wa),opp=sha256(wb),map=identity['maps']['around_unsw'],engine=identity['engine'],judge=identity['judge'],seed=3,side=side)
        (folder/f'around_unsw_3_{side}.replay.success.json').write_text(json.dumps(dict(returncode=0,identity=record)))
    fake=types.ModuleType('tools.panel_zig'); fake.wasm=lambda name: str(wa if name==str(bot) else wb)
    fake.ENGINE=str(engine); fake.JUDGE='judge'; fake.WSL_DISTRO='Ubuntu'; fake._wslpath=lambda x:x
    original_driver=sys.modules.get('tools.panel_zig'); sys.modules['tools.panel_zig']=fake
    original_run=nn.subprocess.run
    nn.subprocess.run=lambda *args,**kwargs: types.SimpleNamespace(stdout='judge-hash fixture\n',returncode=0)
    try:
        nn.validate_panel(str(folder))
        record=json.loads((folder/'around_unsw_3_A.replay.success.json').read_text()); record['identity']['judge']='stale'
        (folder/'around_unsw_3_A.replay.success.json').write_text(json.dumps(record))
        rejected(lambda:nn.validate_panel(str(folder)))
    finally:
        nn.subprocess.run=original_run
        if original_driver is None: sys.modules.pop('tools.panel_zig',None)
        else: sys.modules['tools.panel_zig']=original_driver
print('PASS: manifest-only ownership/hash; exact resume after publication crash; config mismatch; CPU finite/66M; stage input/output mutation')
print('PASS: scout sibling/missing/draw coverage; disk-cap exit cannot mark complete; Zig fallback argument array; unsafe 98-game panel')
print('PASS: compiled-game identity rejects a stale judge within a completed panel')
print('PASS: v6/legacy export compatibility; unsafe improvement cannot advance; inconclusive confirmation cannot advance')
