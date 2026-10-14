"""Judge-metered per-call inference on parity's real states; run after export/parity."""
import argparse,json,math,shutil,subprocess,sys
from pathlib import Path
from unswbc import clangtool
from unswbc.sandbox import Sandbox,_metered
ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args()
out=Path(a.out);work=out/'cpu_bench';work.mkdir(exist_ok=True)
candidate=Path('viper_y96qm')
for name in ['policy_nn_mlp.hpp','policy_weights_mlp.hpp','policy_nn_v6.hpp','policy_weights_v6.hpp']:
    shutil.copyfile(candidate/name,work/name)
shutil.copyfile(out/'input.bin',work/'input.bin')
(work/'bot.toml').write_text('[project]\nlanguage="c++"\ninclude=["*.cpp","*.hpp"]\n',encoding='utf-8')
(work/'main.cpp').write_text(r'''#include <cstdio>
#include <vector>
#include <chrono>
#include "policy_nn_mlp.hpp"
#include "policy_nn_v6.hpp"
int main(){FILE*f=fopen("input.bin","rb");if(!f)return 2;int n;fread(&n,4,1,f);std::vector<unsigned char>p(n*4275);std::vector<float>s(n*6);fread(p.data(),1,p.size(),f);fread(s.data(),4,s.size(),f);fclose(f);
 double total[2]={0,0},peak[2]={0,0};volatile float sink=0;int count=64;
 for(int k=0;k<2;k++)for(int j=0;j<count;j++){float y[7];auto begin=std::chrono::steady_clock::now();if(k)mlp::forward(p.data()+(j*1200/count)*4275,s.data()+(j*1200/count)*6,y);else nn::forward(p.data()+(j*1200/count)*4275,s.data()+(j*1200/count)*6,y);auto end=std::chrono::steady_clock::now();double points=std::chrono::duration<double,std::milli>(end-begin).count()*1000000;total[k]+=points;if(points>peak[k])peak[k]=points;sink+=y[j%7];}
 printf("{\"states\":%d,\"conv_mean\":%.0f,\"conv_max\":%.0f,\"mlp_mean\":%.0f,\"mlp_max\":%.0f,\"sink\":%.6f}\n",count,total[0]/count,peak[0],total[1]/count,peak[1],(double)sink);return 0;}
''',encoding='utf-8')
wasm=Path(subprocess.check_output([sys.executable,'tools/buildwasm.py',str(work)],text=True,encoding='utf-8').strip().splitlines()[-1])
box=Sandbox(wasm_path=_metered(wasm,work),root=clangtool.toolchain()/'root',mounts={'/src':work},cwd='/src',argv=['/src/bench'],needs_zygote=False,needs_meter=True,max_pages=768)
status=box.run();output=bytes(box.stdout).decode('utf-8','replace');print(output,end='')
assert status==0,(status,bytes(box.stderr).decode('utf-8','replace'))
result=json.loads(output)
measurements=[result[k] for k in ('conv_mean','conv_max','mlp_mean','mlp_max')]
valid=all(math.isfinite(v) and v>0 for v in measurements)
result['target_pass']=valid and result['mlp_max']<=3000000
result['speedup_mean']=result['conv_mean']/result['mlp_mean'] if valid else None
(out/'cpu.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
if not result['target_pass']:
    raise SystemExit('FAIL: CPU measurements must be finite, positive and sampled MLP max <= 3000000')
