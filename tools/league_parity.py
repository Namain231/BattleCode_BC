"""Numerical parity and zero-plane audit for league exports; data artifacts stay on F:."""
import sys,json,subprocess,shutil
from pathlib import Path
import numpy as np,torch
root=Path.cwd();sys.path.insert(0,str(root/'ml'));from train import Policy
team=sys.argv[1];data=Path('F:/BattleCode_data/league_build');bot=root/'league'/('team_'+team)
ck=torch.load(data/'models8'/f'{team}.pt',map_location='cpu',weights_only=False)
m=Policy(planes=19,scalars=6,ch=ck['channels'],hidden=ck['hidden'],classes=7);m.load_state_dict(ck['state_dict']);m.eval()
w=m.c1.weight.detach().numpy();bound=1/np.sqrt(w.shape[1]*9);p8=float(np.abs(w[:,8]).max());assert p8<=bound+1e-6
rng=np.random.default_rng(2504);ps=[];ss=[]
for f in sorted((data/'datasets_v2'/team).glob('shard_*.npz'))[:2]:
 with np.load(f) as z:
  ix=np.sort(rng.choice(len(z['labels']),min(64,len(z['labels'])),replace=False));ps.append(z['planes'][ix]);ss.append(z['scalars'][ix])
p=np.concatenate(ps);s=np.concatenate(ss).astype(np.float32)
with torch.no_grad(): ref=m(torch.from_numpy(p).float()/255,torch.from_numpy(s)).numpy()
out=data/'parity'/team;out.mkdir(parents=True,exist_ok=True)
(out/'in.bin').write_bytes(np.int32(len(p)).tobytes()+p.tobytes()+s.tobytes())
shutil.copy(root/'ml/v6/parity_main.cpp',out/'parity_main.cpp')
def wsl(p):
 p=str(p.resolve()).replace('\\','/');return '/mnt/'+p[0].lower()+p[2:]
script='''#!/bin/bash
set -e
if command -v g++ >/dev/null; then CXX=(g++); else CXX=("$HOME/toolchains/zig-linux/zig" c++); fi
"${CXX[@]}" -O2 -std=c++17 -I"%s" "%s/parity_main.cpp" -o "%s/parity.out"
"%s/parity.out" "%s/in.bin" "%s/out.bin"
'''%(wsl(bot),wsl(out),wsl(out),wsl(out),wsl(out),wsl(out))
(out/'run.sh').write_bytes(script.encode())
subprocess.run(['wsl','-d','Ubuntu','--','bash',wsl(out/'run.sh')],check=True)
y=np.fromfile(out/'out.bin',np.float32).reshape(-1,7);err=float(np.abs(y-ref).max());agree=float((y.argmax(1)==ref.argmax(1)).mean())
r=dict(team=team,states=len(p),max_abs_error=err,argmax_agreement=agree,plane8_max=p8,plane8_init_bound=float(bound),passed=err<1e-3 and agree==1)
(out/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));assert r['passed']
