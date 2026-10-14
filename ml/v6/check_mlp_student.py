"""Small failure-path checks; never creates trained candidate weights."""
import ast,json,sys,tempfile,shutil
from pathlib import Path
import numpy as np
import torch
from train_mlp_student import Student,atomic,restore_best,digest,batches,evaluate,export

def main():
    torch.set_num_threads(2);checks=[]
    for f in ['ml/v6/train_mlp_student.py','ml/v6/parity_mlp_student.py']:ast.parse(Path(f).read_text())
    with tempfile.TemporaryDirectory(dir='out',prefix='mlp_fix_check_') as td:
        d=Path(td);candidate=d/'candidate';candidate.mkdir();model=Student(8);identity={'width':8}
        (candidate/'bot.toml').write_text('[project]\nlanguage="c++"\ninclude=["*.cpp","*.hpp"]\n',encoding='utf-8')
        atomic(d/'best.pt',{'model':model.state_dict(),'width':8,'identity':identity,'evaluation':{'accuracy':[.5,.6]}})
        restore_best(d,candidate,identity);initial=(candidate/'policy_weights_mlp.hpp').read_bytes()
        (candidate/'policy_weights_mlp.hpp').write_text('interrupted export');(candidate/'policy_nn_mlp.hpp').unlink()
        restore_best(d,candidate,identity)
        assert (candidate/'policy_weights_mlp.hpp').read_bytes()==initial
        marker=json.loads((candidate/'mlp_export.json').read_text());assert marker['checkpoint_sha256']==digest(d/'best.pt')
        checks.append('interrupted export regenerated and checkpoint hash bound')
        try:restore_best(d,candidate,{'width':9})
        except AssertionError:checks.append('changed resume identity rejected')
        else:raise AssertionError('identity accepted')
        bad=d/'bad.npz'
        for case,shape,weight,scalar,label in [('shape',(1,18,15,15),1,0,0),('weight',(1,19,15,15),0,0,0),('nonfinite',(1,19,15,15),1,float('nan'),0),('label',(1,19,15,15),1,0,7)]:
            np.savez(bad,game=np.array([1]),planes=np.zeros(shape,np.uint8),scalars=np.full((1,6),scalar,np.float32),labels=np.array([label]),weights=np.full(1,weight,np.float32))
            try:next(batches([bad],np.array([2]),False,1,np.random.default_rng(42)))
            except AssertionError:checks.append('invalid '+case+' rejected before CUDA upload')
            else:raise AssertionError(case+' accepted')
        try:evaluate(model,model,[],np.array([1]),1,np.random.default_rng(42))
        except AssertionError:checks.append('empty validation rejected')
        else:raise AssertionError('empty validation accepted')
    checks.append('both scripts AST parse')
    with tempfile.TemporaryDirectory(dir='out',prefix='mlp_size_probe_') as td:
        d=Path(td)
        for f in Path('viper_y96qm').iterdir():
            if f.suffix in ('.cpp','.hpp','.toml'):shutil.copy2(f,d/f.name)
        export(Student(),d)
        package_bytes=json.loads((d/'mlp_export.json').read_text())['package_bytes']
        checks.append('full-width synthetic packaged zip under 4 MB: '+str(package_bytes))
    result={'checks':checks,'pass':True,'trainer_sha256':digest('ml/v6/train_mlp_student.py'),'parity_sha256':digest('ml/v6/parity_mlp_student.py')}
    Path('out/mlp_student_fix_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
