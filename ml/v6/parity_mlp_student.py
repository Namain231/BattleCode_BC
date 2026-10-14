"""1600-state native C++/torch parity; artifacts on F:. Run from repo root."""
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np
import torch
from train_mlp_student import Student, restore_best, current_identity, digest

def wsl(p):
    p=str(Path(p).resolve()).replace('\\','/')
    return '/mnt/'+p[0].lower()+p[2:]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out);ck=torch.load(out/'best.pt',map_location='cpu',weights_only=False)
    _,_,identity=current_identity(ck['width'],ck['identity']['batch'])
    assert ck['identity']==identity, 'checkpoint differs from current trainer/data/teacher'
    candidate=Path('viper_y96qm')
    marker=json.loads((candidate/'mlp_export.json').read_text())
    assert marker['checkpoint_sha256']==digest(out/'best.pt')
    assert marker['weights_sha256']==digest(candidate/'policy_weights_mlp.hpp')
    assert marker['header_sha256']==digest(candidate/'policy_nn_mlp.hpp')
    assert marker['package_sha256']==digest(candidate/'mlp_submission.zip')
    restore_best(out,candidate,identity)
    model=Student(ck['width']);model.load_state_dict(ck['model']);model.eval();torch.set_num_threads(2)
    rng=np.random.default_rng(42);ps=[];ss=[]
    remaining=1200
    for file in sorted(Path('ladder/scout_v6/shards_new').glob('shard_*.npz')):
        with np.load(file) as z:
            count=min(remaining,len(z['labels']),600)
            if not count: continue
            ix=np.sort(rng.choice(len(z['labels']),count,replace=False));ps.append(z['planes'][ix]);ss.append(z['scalars'][ix]);remaining-=count
        if remaining==0: break
    assert remaining==0, 'need 1200 real states'
    ps.append((rng.integers(0,256,(400,19,15,15),dtype=np.uint8)*(rng.random((400,19,1,1))<0.5)).astype('uint8'))
    ss.append(rng.random((400,6),dtype=np.float32));p=np.concatenate(ps);s=np.concatenate(ss).astype('float32')
    assert p.shape==(1600,19,15,15) and s.shape==(1600,6)
    assert not p[:1200,8].any() and not p[:1200,18].any()
    p[:,8]=0;p[:,18]=0  # reserved input planes are zero in every legal bot state
    with torch.no_grad():ref=model(torch.from_numpy(p).float()/255,torch.from_numpy(s)).numpy()
    (out/'input.bin').write_bytes(np.int32(len(p)).tobytes()+p.tobytes()+s.tobytes())
    (out/'parity.cpp').write_text('''#include <cstdio>
#include <vector>
#include "policy_nn_mlp.hpp"
int main(int argc,char**argv){
 if(argc!=3){fprintf(stderr,"expected input and output paths");return 2;}
 FILE*f=fopen(argv[1],"rb");if(!f){perror("input fopen");return 3;}
 int n=0;if(fread(&n,4,1,f)!=1||n!=1600){fprintf(stderr,"invalid state count");fclose(f);return 4;}
 std::vector<unsigned char>p(n*4275);std::vector<float>s(n*6);
 if(fread(p.data(),1,p.size(),f)!=p.size()||fread(s.data(),4,s.size(),f)!=s.size()){fprintf(stderr,"truncated input");fclose(f);return 5;}
 if(fclose(f)!=0){perror("input fclose");return 6;}
 f=fopen(argv[2],"wb");if(!f){perror("output fopen");return 7;}
 for(int i=0;i<n;i++){float y[7];mlp::forward(p.data()+i*4275,s.data()+i*6,y);if(fwrite(y,4,7,f)!=7){perror("output fwrite");fclose(f);return 8;}}
 if(fclose(f)!=0){perror("output fclose");return 9;}return 0;}
''',encoding='utf-8')
    d=wsl(out);inc=wsl('viper_y96qm')
    prefix=['wsl','-d','Ubuntu','--']
    found=subprocess.run(prefix+['which','g++'],capture_output=True,text=True)
    if found.returncode==0:
        compiler=[found.stdout.strip()]
    else:
        home=subprocess.check_output(prefix+['printenv','HOME'],text=True).strip()
        compiler=[home+'/toolchains/zig-linux/zig','c++']
    subprocess.run(prefix+compiler+['-O2','-std=c++17','-I'+inc,d+'/parity.cpp','-o',d+'/parity'],check=True)
    subprocess.run(prefix+[d+'/parity',d+'/input.bin',d+'/output.bin'],check=True)
    actual=np.fromfile(out/'output.bin',np.float32).reshape(-1,7)
    assert actual.shape==ref.shape and np.isfinite(actual).all() and np.isfinite(ref).all()
    result={'states':len(p),'max_logit_error':float(np.abs(actual-ref).max()),'argmax_agreement':float((actual.argmax(1)==ref.argmax(1)).mean())}
    result['pass']=result['max_logit_error']<1e-3 and result['argmax_agreement']==1
    (out/'parity.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));assert result['pass']

if __name__=='__main__':main()
