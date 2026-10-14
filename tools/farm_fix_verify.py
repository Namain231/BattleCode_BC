"""Adversarial farm integrity fixtures and Windows/WSL supervisor-kill lease test."""
import copy,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).absolute().parent))
import farm_scale as f
stage=Path(sys.argv[1]); fixture=stage/'verification'
rows=f.checkpoints(fixture); job=json.loads((fixture/'jobs.json').read_text())[0]
row=rows[0]; tests=0
for key,value in [('cpu_max_M',float('nan')),('units100',-1),('win',.5),('rounds',999),('queen_id',None),('first_split',float('inf')),('seed',999),('units100',1.5),('rounds',100.5),('queen_id',1)]:
 bad=copy.deepcopy(row);bad[key]=value
 try:f.validate(bad,job)
 except ValueError:tests+=1
 else:raise AssertionError(key)
extra=fixture/'state/extra.json';f.atomic(extra,row)
try:f.checkpoints(fixture)
except ValueError:tests+=1
else:raise AssertionError('extra state')
finally:extra.unlink()
# Check seal integrity on an isolated complete private bundle fixture.
bundle=stage/'seal_fixture';bundle.mkdir(exist_ok=True)
for name in ['state','bots','tools','farm','maps','maps_rm_dev','shards','out']:(bundle/name).mkdir(exist_ok=True)
for name in ['manifest.json','jobs.json','engine.wasm','loong-judge','out/opening_census.txt','artifacts.json']:(bundle/name).write_text('{}')
f.atomic(bundle/'manifest.json',dict(dependencies={},judge_hash=f.digest(bundle/'loong-judge'),engine_hash=f.digest(bundle/'engine.wasm')))
f.atomic(bundle/'bundle_seal.json',f.seal_inputs(bundle));f.verify_seal(bundle)
(bundle/'engine.wasm').write_text('changed')
try:f.verify_seal(bundle)
except ValueError:tests+=1
else:raise AssertionError('mixed engine')
# Nonzero judge exit with existing replay must fail; no judge is launched.
(stage/'mock_judge').mkdir(exist_ok=True)
(stage/'mock_judge/stripes_999_A.replay').write_text('partial replay')
saved=f.panel.subprocess.run; use=f.panel.USE_WSL
f.panel.USE_WSL=False
f.panel.subprocess.run=lambda *a,**kw:subprocess.CompletedProcess(a,7,stdout='artifact exists',stderr='fixture failure')
try:f.panel.play('a','b','stripes',999,'A',str(stage/'mock_judge'))
except RuntimeError:tests+=1
else:raise AssertionError('nonzero exit')
finally:f.panel.subprocess.run=saved;f.panel.USE_WSL=use
print(f'PASS: {tests} malformed/extra/mixed-version/nonzero-exit rejection checks')
if os.name=='nt':
 lease=stage/'kill_test.lease'; marker=stage/'kill_test.acquired'
 if marker.exists():marker.unlink()
 wrapper=stage/'lease_supervisor.py'
 child=stage/'lease_child.sh'
 child.write_text('touch '+f.panel._wslpath(str(marker))+'\nsleep 6\n',newline='\n')
 args=['wsl','-d',f.panel.WSL_DISTRO,'--','flock',f.panel._wslpath(str(lease)),'sh',f.panel._wslpath(str(child))]
 wrapper.write_text('import subprocess,time\nsubprocess.Popen('+repr(args)+',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\ntime.sleep(30)\n')
 supervisor=subprocess.Popen([sys.executable,'-B',str(wrapper)])
 try:
  deadline=time.monotonic()+10
  while not marker.exists() and time.monotonic()<deadline:time.sleep(.1)
  assert marker.exists(),'lease acquisition failed'
  supervisor.kill();supervisor.wait(timeout=3)
  retry=['wsl','-d',f.panel.WSL_DISTRO,'--','flock','-n',f.panel._wslpath(str(lease)),'true']
  assert subprocess.run(retry).returncode==1,'surviving child released lease'
  started=time.monotonic()
  retry.remove('-n');subprocess.run(retry,check=True,timeout=15)
  assert time.monotonic()-started>1,'resume did not wait for child'
  print('PASS: killed Windows supervisor; surviving WSL child retained lease; resume waited and acquired after child exit')
 finally:
  if supervisor.poll() is None:supervisor.kill();supervisor.wait()
