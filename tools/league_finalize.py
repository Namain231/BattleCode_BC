"""Finalize league decisions and a <=40-line report after the requested checks."""
import json,statistics,hashlib,os
from pathlib import Path
root=Path.cwd();data=Path('F:/BattleCode_data/league_build');sp=data/'state.json';s=json.loads(sp.read_text());teams=s['teams']
assert all(t['id'] in s.get('sv53',{}) and s['sv53'][t['id']]['n']==20 for t in teams),'20-game panels incomplete'
verify=json.loads((root/'out/league_chk/summary.json').read_text());assert len(verify)==8
common_main={hashlib.sha256((root/'league'/t['slug']/'main.cpp').read_text(encoding='utf-8').split('\n',2)[2].encode()).hexdigest() for t in teams}
assert len(common_main)==1,'league rules diverged between teams'
for name in ['bot.toml','maps_data.hpp','policy_nn_v6.hpp']:
 assert len({hashlib.sha256((root/'league'/t['slug']/name).read_bytes()).hexdigest() for t in teams})==1,name
accepted=[];rejected=[]
for t in teams:
 tid=t['id'];f=s['fidelity'][tid];ev=[v for k,v in s['evaluations'].items() if k.startswith(tid+'/')]
 assert sum(v['n'] for v in ev)==28
 peaks=[v['cpu'] for v in ev];known=all(p is not None for p in peaks)
 if tid=='566':peaks +=[r['cpu_max_ours_M'] for r in verify];known &=all(p is not None for p in peaks)
 f['cpu_ok']=known and max(peaks)<=66;f['peak']=max([p for p in peaks if p is not None],default=None)
 f['verdict']='accepted' if f['ratio'] is not None and .75<=f['ratio']<=1.25 and f['cpu_ok'] else 'rejected'
 (accepted if f['verdict']=='accepted' else rejected).append(t['name'])
 assert json.loads((data/'parity'/tid/'result.json').read_text())['passed']
comparable=[t for t in teams if t['real_record']!='NA']
def rate(t):
 w,n=map(int,t['real_record'].split('/'));return w/n
def localrate(t):return s['sv53'][t['id']]['wins']/20
def groups(order,key):
 pairs=[]
 for t in sorted(order,key=key):
  r=key(t)
  if not pairs or pairs[-1][0]!=r:pairs.append((r,[t['name']]))
  else:pairs[-1][1].append(t['name'])
 return ' < '.join(' / '.join(names)+f' ({r:.0%})' for r,names in pairs)
discord=0;ties=0;ordered=0
for i,a in enumerate(comparable):
 for b in comparable[i+1:]:
  real=rate(a)-rate(b);local=localrate(a)-localrate(b)
  if real:
   ordered+=1;discord+=int(real*local<0);ties+=int(local==0)
s['ranking']=dict(comparable=len(comparable),strict_pairs=ordered,discordant=discord,collapsed_ties=ties,matched=discord==0 and ties==0,real=groups(comparable,rate),local=groups(comparable,localrate))
index=dict(accepted=accepted,rejected=rejected,ranking=s['ranking'],teams=[])
for t in teams:
 bot=root/'league'/t['slug'];index['teams'].append(dict(t,fidelity=s['fidelity'][t['id']],source_hash=hashlib.sha256(b''.join(p.read_bytes() for p in sorted(bot.iterdir()) if p.suffix in {'.cpp','.hpp','.toml'})).hexdigest()))
(root/'league/index.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
s['verify']=dict(games=8,wins=sum(r['win'] for r in verify),cpu_peak=max(r['cpu_max_ours_M'] for r in verify));tmp=sp.with_suffix('.tmp');tmp.write_text(json.dumps(s,indent=2));os.replace(tmp,sp)
def fmt(v):return 'NA' if v is None else f'{v:g}'
def medmap(f,k,which):
 vs=[r[which][k] for r in f['maps'] if r[which][k] is not None];return statistics.median(vs) if vs else None
lines=['# League build report','',
 f"Outcome: {len(accepted)}/8 accepted; {len(rejected)}/8 rejected. Ranking {'matches' if s['ranking']['matched'] else 'FAILS'} ({discord}/{ordered} discordant strict pairs, {ties} collapsed ties).",
 'Accepted: '+(', '.join(accepted) or 'none')+'.',
 'Rejected: '+(', '.join(rejected) or 'none')+'.',
 'Built 8 wasm bots; completed 64 fidelity + 160 Sv53 + 8 verification games; no judge/build failures in the final run.',
 'Data, checkpoints, CPU state and replays: F:/BattleCode_data/league_build; decisions: league/index.json.',
 'Shared viper_y96qf rules; wNN=20; per-team 16-channel/32-hidden net (33,649 parameters), 8 CUDA epochs, whole-game holdout.',
 'Six Sv53 loss opponents + two highest peak-rated scout winners; missing scout teams use cached Sv53 opponent wins.',
 '',
 'Team | samples / val% | units50 real/local | units100 real/local | first split real/local | Sv53 local / real W/N | CPU M | decision',
 '|---|---|---|---|---|---|---|---|']
for t in teams:
 tid=t['id'];f=s['fidelity'][tid];metric=json.loads((data/'models8'/f'{tid}.metrics.json').read_text())[-1];record=s['sv53'][tid]
 vals=['/'.join(fmt(medmap(f,k,which)) for which in ['real','local']) for k in ['units50','units100','first_split']]
 lines.append(f"{t['name']} ({tid}) | {s['samples'][tid]} / {100*metric['val_acc']:.1f} | {' | '.join(vals)} | {fmt(record['wins'])}/20 / {t['real_record']} | {fmt(f['peak'])} | {f['verdict']}")
lines += [
 'Sv53 uses the same Maze/Stripes/Devil/Trophy/Portals schedule for all teams, seeds 1,2, both sides.',
 'Metrics are medians of four map medians; first split excludes never-split games. Per-map counts/values are in state.json.',
 'Acceptance: units100 local/real within [0.75,1.25], with measured league CPU <=66M across every tested game.',
 'Hardest first, local: '+s['ranking']['local'],
 'Hardest first, real: '+s['ranking']['real'],
 'Files: tools/league_build.py, league_parity.py, league_finalize.py, README_LEAGUE.md; tools/panel_zig.py CPU capture; league/<team> sources/wasm/index.',
 'Commands (repo cwd): `& C:/Users/sohan/AppData/Local/Programs/Python/Python310/python.exe tools/league_build.py`',
 '`& C:/Users/sohan/AppData/Local/Programs/Python/Python310/python.exe tools/league_parity.py 566` (supervisor runs all teams)',
 '`uv run --python 3.11 --with unswbc python tools/panel_zig.py league/team_566 baselines/Y9_6 out/league_chk --maps maze,stripes --seeds 1,2 -j 2`',
 f"Verification: {s['verify']['wins']:g}/8 wins; CPU max league {s['verify']['cpu_peak']:.3f}M; command completed and printed CPU max.",
 'All eight exports passed C++/PyTorch numerical parity and plane-8 audit; individual results: F: league_build/parity/<id>/result.json.',
 'Crash resume: atomic CPU state after every game; atomic aggregate state after map/seed evaluation; streaming replay extraction; max 3 jobs, 3GB RAM/6GiB disk guard.',
 'Remote lanes OFF: Kaggle optional via tools/kaggle_train/run_v6.sh; GitHub Actions/publishing require explicit approval. No LLM in loops.',
 'Limitations: movement-only nets cannot choose splits/feeding/actions; input-builder vs runtime feature parity remains unverified.',
 'Real records use different maps/seeds/opponents and winner-only sampling; 8 fidelity games/team are noisy. Top two have no real Sv53 record.',
 'No submission/activation/promotion. Rejected proxies must not be treated as faithful opponents.'
]
assert len(lines)<=40,len(lines)
(root/'out/league_build_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(dict(accepted=accepted,rejected=rejected,ranking=s['ranking'],verify=s['verify'],lines=len(lines)),indent=2))
