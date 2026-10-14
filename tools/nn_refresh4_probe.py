import os,sys,json,importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('sweep',Path('ladder/scout_v6/sweep.py'))
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
for gid in [1196024,1198736,1199037,1098754,1099911,1099921]:
    d=module.get('/battles/'+str(gid))
    print(gid, None if d is None else {'keys':list(d),'status':d.get('match',{}).get('status'),'error':d.get('error')},flush=True)
