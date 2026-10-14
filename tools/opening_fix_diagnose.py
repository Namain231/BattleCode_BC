import json,sys,statistics as st,collections
from pathlib import Path
sys.path.insert(0,'tools')
from replay_lite import decode_lite
out=Path('out/opening_fix/diagnosis.json'); data=json.loads(out.read_text()) if out.exists() else {}
for folder in ['or_safety_ctl','or_safety','or_ctl','or_chk_r3']:
 p=Path('out')/folder; rows=json.loads((p/'summary.json').read_text()); target=data.setdefault(folder,{})
 for r in rows:
  key=f"{r['map']}_{r['seed']}_{r['side']}"
  if key in target:continue
  side='AB'.index(r['side']);rep=decode_lite(str(p/(key+'.replay')),{'roundStart','dragonDeath','dragonSplit'})
  owners={i:int(line.split()[1]) for i,line in enumerate(l for l in rep['map'].splitlines() if l.startswith('DRAGON '))}
  queen=next(i for i in (0,1) if owners[i]==side);rnd=-1;first=None;qd=None;deaths=collections.Counter()
  for e in rep['events']:
   if e['kind']=='roundStart':rnd=e['round']
   elif e['kind']=='dragonSplit':
    owners[e['child']]=e['team']
    if e['team']==side and first is None:first=rnd
   elif e['kind']=='dragonDeath' and owners.get(e['id'])==side:
    if rnd<=150:deaths[['wall','self','body','headon','noaction'][e['reason']]]+=1
    if e['id']==queen:qd=rnd
  target[key]={'map':r['map'],'win':r['win'],'first_split':first,'queen_death':qd,'deaths150':dict(deaths),'units50':r['snaps'].get('50',[r['ours']['count']])[0],'units100':r['snaps'].get('100',[r['ours']['count']])[0]}
  tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(data),encoding='utf-8');tmp.replace(out)
 print('DIAG DONE',folder, len(target),flush=True)
print('DIAGNOSIS COMPLETE',flush=True)
