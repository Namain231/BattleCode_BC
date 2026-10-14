"""Farm contract verification; writes fixtures only on F:, no games."""
import csv, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).absolute().parent))
import farm_scale as f
stage=Path(sys.argv[1])
jobs=json.loads((stage/'jobs.json').read_text())
assert len(jobs)==4000
assert len(list((stage/'shards').glob('*.json')))==40
assert all(len(json.loads(p.read_text()))==100 for p in (stage/'shards').glob('*.json'))
assert sum(j['arm']=='candidate' for j in jobs)==2000
assert len({j['opponent'] for j in jobs})==9
assert len({j['map'] for j in jobs if '/' not in j['map']})==17
assert len({j['map'] for j in jobs if '/' in j['map']})==20
pairs={}
for j in jobs: pairs.setdefault((j['opponent'],j['map'],j['seed'],j['side']),[]).append(j['arm'])
assert len(pairs)==2000 and all(sorted(a)==['candidate','sv53'] for a in pairs.values())
seeds={mp:{j['seed'] for j in jobs if j['map']==mp} for mp in {j['map'] for j in jobs}}
assert min(map(len,seeds.values()))>=3
fixture=stage/'verification';(fixture/'state').mkdir(parents=True,exist_ok=True)
(fixture/'out').mkdir(exist_ok=True)
(fixture/'out/opening_census.txt').write_text((f.ROOT/'out/opening_census.txt').read_text(encoding='utf-8'),encoding='utf-8')
rows=[]
for seed in [1,2]:
 for side in 'AB':
  for arm in ['candidate','sv53']:
   row=dict(id=str(len(rows)),arm=arm,opponent='Y9_6',map='stripes',seed=seed,side=side,
     winner=side,rounds=499,units50=3,units100=5+(arm=='candidate'),length100=12,
     first_split=None,eats_rate=.3,queen_id="AB".index(side),queen_death_round=None,
     cpu_max_M=55,cpu_max_opponent_M=50,win=1,seconds=10,lane='local',
     unknown_eats=0,started=seed*100,ended=seed*100+10)
   f.atomic(fixture/'state'/f"{row['id']}.json",row);rows.append(row)
f.atomic(fixture/'manifest.json',dict(map_queens={'stripes':[0,1]}))
f.atomic(fixture/'jobs.json',[{k:r[k] for k in ['id','arm','opponent','map','seed','side']} for r in rows])
original=f.ROOT
f.ROOT=fixture
n,p=f.summarize(fixture)
f.ROOT=original
assert (n,p)==(8,4)
report=(fixture/'farm_report.md').read_text()
assert 'paired delta 1.000 [1.000, 1.000]' in report
assert 'Never split: candidate 4, Sv5.3 4' in report
assert 'top median 12.5' in report
with (fixture/'results.tsv').open(newline='') as fh:
 parsed=list(csv.DictReader(fh,delimiter='\t'))
assert len(parsed)==8 and parsed[0]['first_split']==''
def forbidden(*args,**kwargs): raise AssertionError('cached checkpoint reran judge')
f.panel.play=forbidden
assert f.evaluate(rows[0],fixture)==rows[0]
print('PASS: 4000 evaluations, 40 shards, 17 live+20 dev maps, 9 opponents, >=3 independent seed clusters/map, paired IDs, TSV NA, census benchmark, zero-noise paired CI, checkpoint resume without judge')

# Fixed queen ownership must follow map ordering, including swapped teams.
saved=f.decode_lite
f.decode_lite=lambda *args: dict(map='DRAGON 1 3 0 0 1 0 2 0\nDRAGON 0 3 5 0 6 0 7 0',
 events=[dict(kind='roundStart',round=23),dict(kind='dragonDeath',id=1)], result=dict(winner=1))
assert f.queen_info('fixture',0)==(1,1,23)
assert f.queen_info('fixture',1)==(1,0,None)
f.decode_lite=saved
assert f.bounds([-1,-1])[2]<0
print('PASS: swapped queen IDs, queen death round, surviving queen NA, safety regression signal')
if len(sys.argv)>2:
 rep=Path(sys.argv[2])
 winner,qid,death=f.queen_info(rep,1)
 row=f.opening(dict(path=rep,group='farm',side=1,map='stripes'))
 assert qid in (0,1) and row['validation']['final_body_parity']==1
 print(f'REAL REPLAY PASS: queen id={qid}, death round={death}, units100={row["units100"]}, unknown eats={row["unknown_eats"]}')