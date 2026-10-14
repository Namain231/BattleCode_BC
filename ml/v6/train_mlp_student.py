"""Streaming CE + temperature-2 teacher distillation; restart after every evaluation."""
import argparse, hashlib, json, os, re, sys, time, zipfile
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / 'ml'))
from train import Policy

class Student(torch.nn.Module):
    def __init__(self, width=256):
        super().__init__()
        self.a = torch.nn.Linear(4281, width)
        self.b = torch.nn.Linear(width, 128)
        self.c = torch.nn.Linear(128, 7)
    def forward(self, p, s):
        return self.c(F.relu(self.b(F.relu(self.a(torch.cat([p.flatten(1), s], 1))))))

def atomic(path, obj):
    torch.save(obj, str(path)+'.tmp'); os.replace(str(path)+'.tmp', path)

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def atomic_text(path, text):
    temp=Path(str(path)+".tmp")
    temp.write_text(text,encoding="utf-8");os.replace(temp,path)

def current_identity(width, batch):
    dirs=[ROOT/'ladder/scout_v6/shards_145',ROOT/'ladder/scout_v6/shards_new']
    files=[f for d in dirs for f in sorted(d.glob('shard_*.npz'))]
    assert files, 'no shards'
    manifest=json.loads((dirs[1]/'manifest.json').read_text())
    games=manifest.get('exported_game_ids',manifest.get('game_ids',[]))
    if not games:
        games=set()
        for file in dirs[1].glob('shard_*.npz'):
            with np.load(file) as z:games.update(map(int,np.unique(z['game'])))
    hold=np.array(sorted(set(map(int,games)))[-max(1,len(games)//10):])
    identity={'version':3,'width':width,'batch':batch,'temperature':2,'seed':42,'lr':0.001,'weight_decay':0.0001,'holdout':hold.tolist(),'teacher':digest(ROOT/'viper_y96qg/policy_weights_v6.hpp'),'teacher_implementation':digest(ROOT/'ml/train.py'),'trainer':digest(Path(__file__)),'shards':[(str(f.relative_to(ROOT)),digest(f)) for f in files]}
    return files,hold,json.loads(json.dumps(identity))

def package(candidate):
    # Exact bot.toml include globs, plus mandatory config; no logs/checkpoints.
    path=candidate/'mlp_submission.zip'
    files=sorted(set(candidate.glob('*.cpp'))|set(candidate.glob('*.hpp'))|{candidate/'bot.toml'})
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in files:z.write(f,f.name)
    return path.stat().st_size

def teacher_from_header():
    m = Policy(planes=19, scalars=6, classes=7)
    text = (ROOT/'viper_y96qg/policy_weights_v6.hpp').read_text()
    sd = m.state_dict()
    for k, v in sd.items():
        name = 'NN_'+k.replace('.', '_').upper()
        body = re.search(r'\b'+name+r'\[\d+\]\s*=\s*\{([^}]+)\}', text).group(1)
        values = np.fromstring(body.replace('f',''), sep=',', dtype=np.float32)
        sd[k] = torch.from_numpy(values.reshape(v.shape))
    m.load_state_dict(sd)
    return m.eval()

def batches(files, hold, validation, batch, rng):
    for file in files:
        with np.load(file) as z:
            mask = np.isin(z['game'], hold)
            ix = np.flatnonzero(mask if validation else ~mask)
            if not validation: rng.shuffle(ix)
            if not len(ix): continue
            p,s,y,w = z['planes'],z['scalars'],z['labels'],z['weights']
            n=len(mask)
            assert p.shape==(n,19,15,15) and p.dtype==np.uint8
            assert not p[:,8].any() and not p[:,18].any(), 'dropped planes must be zero'
            assert s.shape==(n,6) and y.shape==(n,) and w.shape==(n,)
            assert np.all((y>=0)&(y<7)) and np.all(y==y.astype('int64'))
            for off in range(0,len(ix),batch):
                j = np.sort(ix[off:off+batch])
                assert np.isfinite(s[j]).all() and np.isfinite(w[j]).all()
                assert (w[j]>=0).all() and w[j].sum()>0
                yield (torch.from_numpy(p[j]).cuda().float()/255,
                       torch.from_numpy(s[j]).cuda(),torch.from_numpy(y[j].astype('int64')).cuda(),
                       torch.from_numpy(w[j]).cuda())
            del p,s,y,w,mask,ix,j

def evaluate(student, teacher, files, hold, batch, rng):
    counts = np.zeros((2,7,2), dtype=np.int64)
    student.eval()
    with torch.no_grad():
        for p,s,y,w in batches(files,hold,True,batch,rng):
            for k, model in enumerate([student,teacher]):
                pred = model(p,s).argmax(1)
                for c in range(7):
                    mask=y==c
                    counts[k,c] += [int(((pred==y)&mask).sum()),int(mask.sum())]
    assert counts[:,:,1].sum(1).min()>0, 'empty validation'
    student.train()
    return {'accuracy':(counts[:,:,0].sum(1)/counts[:,:,1].sum(1)).tolist(),'counts':counts.tolist(), 'move_class_accuracy':[{name:float(counts[k,ids,0].sum()/counts[k,ids,1].sum()) if counts[k,ids,1].sum() else None for name,ids in [('fwd',[0]),('side',[1,3]),('back',[2]),('split',[4]),('other',[5]),('stop',[6])]} for k in range(2)]}

def export(model, candidate):
    width = model.a.out_features
    with (candidate/'policy_weights_mlp.hpp.tmp').open('w',encoding='utf-8') as f:
        f.write('#pragma once\n')
        for name,t in [('MA',torch.cat([model.a.weight.T[:1800],model.a.weight.T[2025:4050],model.a.weight.T[4275:]],0)),('BA',model.a.bias),('MB',model.b.weight),('BB',model.b.bias),('MC',model.c.weight),('BC',model.c.bias)]:
            v=t.detach().cpu().contiguous().numpy().ravel()
            if name.startswith('M'):
                scale=max(float(np.abs(v).max())/16777215,1e-30)
                q=np.rint(v/scale).clip(-16777215,16777215).astype(np.int32)
                f.write('static const float '+name+'_S='+format(scale,'.9e')+'f;\n')
                f.write('static const int '+name+'['+str(len(q))+']={'+','.join(map(str,q))+'};\n')
            else:
                f.write('static const float '+name+'['+str(len(v))+']={'+','.join(format(float(x),'.9e')+'f' for x in v)+'};\n')
    (candidate/'policy_nn_mlp.hpp.tmp').write_text('''#pragma once
#include "policy_weights_mlp.hpp"
namespace mlp {
static void forward(const unsigned char* p,const float* s,float* out) {
 double a[WIDTH],b[128];
 for(int j=0;j<WIDTH;j++)a[j]=BA[j];
 for(int i=0;i<3831;i++) {
  double x=i<3825?p[i<1800?i:i+225]/255.f:s[i-3825];
  if(x==0.f)continue;
  x*=MA_S;
  const int* w=MA+i*WIDTH;
  for(int j=0;j<WIDTH;j++)a[j]+=x*w[j];
 }
 for(int j=0;j<WIDTH;j++)if(a[j]<0.f)a[j]=0.f;
 for(int j=0;j<128;j++) {double z=0.;for(int i=0;i<WIDTH;i++)z+=MB[j*WIDTH+i]*a[i];z=z*MB_S+BB[j];b[j]=z>0.f?z:0.f;}
 for(int j=0;j<7;j++){double z=0.;for(int i=0;i<128;i++)z+=MC[j*128+i]*b[i];out[j]=z*MC_S+BC[j];}
}
}
'''.replace('WIDTH',str(width)),encoding='utf-8')

    marker=candidate/'mlp_export.json'
    if marker.exists(): marker.unlink()
    os.replace(candidate/'policy_weights_mlp.hpp.tmp',candidate/'policy_weights_mlp.hpp')
    os.replace(candidate/'policy_nn_mlp.hpp.tmp',candidate/'policy_nn_mlp.hpp')
    size=package(candidate)
    assert size<=4_000_000, f'packaged bot exceeds 4 MB: {size} bytes; compact export required'
    atomic_text(candidate/'mlp_export.json',json.dumps({'width':width,'package_bytes':size,'package_sha256':digest(candidate/'mlp_submission.zip'),'weights_sha256':digest(candidate/'policy_weights_mlp.hpp'),'header_sha256':digest(candidate/'policy_nn_mlp.hpp')},indent=2))

def restore_best(out, candidate, identity):
    state=torch.load(out/'best.pt',map_location='cpu',weights_only=False)
    assert state['identity']==identity and state['width']==identity['width']
    model=Student(state['width']);model.load_state_dict(state['model'])
    assert all(torch.isfinite(v).all() for v in model.state_dict().values())
    export(model,candidate)
    marker=json.loads((candidate/'mlp_export.json').read_text())
    marker['checkpoint_sha256']=digest(out/'best.pt')
    atomic_text(candidate/'mlp_export.json',json.dumps(marker,indent=2))
    assert marker['weights_sha256']==digest(candidate/'policy_weights_mlp.hpp')
    assert marker['header_sha256']==digest(candidate/'policy_nn_mlp.hpp')
    return state

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--epochs',type=int,default=8);ap.add_argument('--width',type=int,default=256);ap.add_argument('--batch',type=int,default=512)
    a=ap.parse_args();assert a.width>0 and a.batch>0 and a.epochs>0
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(2);torch.manual_seed(42);rng=np.random.default_rng(42)
    files,hold,identity=current_identity(a.width,a.batch)
    assert len(hold)>0
    identity_file=out/'identity.json'
    if identity_file.exists(): assert json.loads(identity_file.read_text())==json.loads(json.dumps(identity)), 'experiment identity changed; use a fresh output directory'
    elif (out/'resume.pt').exists() or (out/'best.pt').exists(): raise ValueError('unbound legacy checkpoint; use fresh output directory')
    else: atomic_text(identity_file,json.dumps(identity,indent=2))
    identity=json.loads(json.dumps(identity))
    atomic_text(out/'holdout.json',json.dumps(hold.tolist()))
    train_n=val_n=0
    for file in files:
        with np.load(file) as z:
            mask=np.isin(z['game'],hold);val_n+=int(mask.sum());train_n+=int((~mask).sum())
        del mask
    assert train_n>0 and val_n>0, 'empty train/validation split'
    candidate=ROOT/'viper_y96qm'
    if (out/'best.pt').exists(): restore_best(out,candidate,identity)
    teacher=teacher_from_header().cuda();student=Student(a.width).cuda()
    opt=torch.optim.AdamW(student.parameters(),lr=0.001,weight_decay=0.0001)
    ck=out/'resume.pt';start=0;best=-1
    if ck.exists():
        state=torch.load(ck,map_location='cuda',weights_only=False);assert state['identity']==identity;student.load_state_dict(state['model']);opt.load_state_dict(state['opt']);start=state['epoch'];best=state['best'];rng.bit_generator.state=state['rng'];torch.set_rng_state(state['torch_rng'].cpu());torch.cuda.set_rng_state_all([x.cpu() for x in state['cuda_rng']])
    if (out/'best.pt').exists():
        best=max(best,float(torch.load(out/'best.pt',map_location='cpu',weights_only=False)['evaluation']['accuracy'][0]))
    assert start<=a.epochs
    if (out/'DONE').exists(): (out/'DONE').unlink()
    for ep in range(start,a.epochs):
        t=time.time();n=0;loss_sum=0.
        for p,s,y,w in batches([files[i] for i in rng.permutation(len(files))],hold,False,a.batch,rng):
            with torch.no_grad(): target=teacher(p,s)
            pred=student(p,s)
            ce=F.cross_entropy(pred,y,reduction='none')
            kl=F.kl_div(F.log_softmax(pred/2,1),F.softmax(target/2,1),reduction='none').sum(1)*4
            loss=((ce+kl)*w).sum()/w.sum()
            assert torch.isfinite(pred).all() and torch.isfinite(target).all() and torch.isfinite(loss)
            opt.zero_grad(set_to_none=True);loss.backward();opt.step();n+=len(y);loss_sum+=float(loss)*len(y)
        assert n>0 and np.isfinite(loss_sum), 'invalid training epoch'
        ev=evaluate(student,teacher,files,hold,a.batch,rng);ev.update(epoch=ep+1,seconds=time.time()-t,train_samples=n,loss=loss_sum/max(n,1))
        print(json.dumps(ev),flush=True)
        if ev['accuracy'][0]>best:
            best=ev['accuracy'][0];atomic(out/'best.pt',{'model':student.state_dict(),'width':a.width,'identity':identity,'evaluation':ev});restore_best(out,candidate,identity)
        atomic(ck,{'identity':identity,'model':student.state_dict(),'opt':opt.state_dict(),'epoch':ep+1,'best':best,'rng':rng.bit_generator.state,'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all()})
        atomic_text(out/f'eval_{ep+1}.json',json.dumps(ev,indent=2))
    final=restore_best(out,candidate,identity)
    assert final['evaluation']['counts'][0] and (out/'resume.pt').exists()
    atomic_text(out/'DONE',json.dumps({'best_sha256':digest(out/'best.pt'),'export':json.loads((candidate/'mlp_export.json').read_text())}))

if __name__=='__main__':main()
