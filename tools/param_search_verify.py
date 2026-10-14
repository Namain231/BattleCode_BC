"""Pure fixtures for search statistics, log recovery and acceptance guards; no games."""
import csv, math, tempfile
from pathlib import Path
import farm_scale as farm
import param_search as search

def main():
 rows=[]
 for seed in range(1,401):
  mp=search.CLOSED[(seed-1)%4]
  for opponent in ['Y9_6','league_fixture']:
   for side in 'AB':
    for arm in ['candidate','sv53']:
     rows.append(dict(id=str(len(rows)),seed=seed,map=mp,opponent=opponent,side=side,arm=arm,cpu_max_M=65,win=float(arm=='candidate'),units100=20 if arm=='candidate' else 1,eats_rate=1,first_split=0))
 negative=[dict(r,win=1-r['win']) for r in rows]
 assert farm.search_stop(negative,.00625,search.CLOSED,2) is not None
 assert farm.search_stop(negative[:36],.00625,search.CLOSED,2) is None # incomplete cycle
 assert farm.search_stop([dict(rows[0],cpu_max_M=66.01)],.00625,search.CLOSED,2)=='CPU peak exceeds 66M'
 assert farm.search_stop([dict(rows[0],cpu_max_M=66)],.00625,search.CLOSED,2) is None
 original=farm.checkpoints
 try:
  farm.checkpoints=lambda _:rows
  result=search.assess(Path('.'))
  assert result['pairs']==1600 and result['eligible']
  rows[0]['cpu_max_M']=66.01
  assert not search.assess(Path('.'))['eligible']
  rows[0]['cpu_max_M']=65
  rows[0]['units100']=1
  for r in rows:
   if r['arm']=='candidate' and r['map']=='stripes':r['units100']=1
  assert not search.assess(Path('.'))['eligible']
 finally: farm.checkpoints=original
 with tempfile.TemporaryDirectory(dir='F:/BattleCode_data' if Path('F:/BattleCode_data').exists() else None) as d:
  stage=Path(d)/'fixture';stage.mkdir();log=Path(d)/'results.tsv'
  farm.search_log_restore(log,stage,'fixture',[rows[0]])
  farm.search_log_restore(log,stage,'fixture',rows[:2])
  farm.search_log_restore(log,stage,'fixture',rows[:2])
  with log.open(encoding='utf-8') as f:assert len(list(csv.DictReader(f,delimiter='\t')))==2
 print('PASS: balanced-cycle stop, CPU boundary, 1600-pair acceptance, halfway rejection, TSV crash repair/dedup')
if __name__=='__main__':main()
