"""Streaming one replay at a time; no pickle cache. Metrics for our L<=6 turns, r0..149.
Usage: python -B tools/hunger_metrics.py PANEL_DIR [--out JSON]
Unique cells/streaks are per dragon; retraces count successful steps in prior 20 turns.
"""
import sys
sys.dont_write_bytecode = True
import argparse, collections, hashlib, json, statistics
from pathlib import Path
from replay_lite import decode_lite
from engine_sim import load_map, DEATHS

KINDS = {'roundStart','turnStart','dragonAction','dragonUpdate','dragonSplit','dragonDeath','tileChange'}

def measure(path):
    rep = decode_lite(str(path), KINDS)
    me = 'AB'.index(path.stem.rsplit('_',1)[1])
    st = load_map(rep['map'], 1)
    bodies = {i:list(d.body) for i,d in st.dragons.items()}
    teams = {i:d.team for i,d in st.dragons.items()}
    alive = set(bodies)
    visits = {i:{b[0]:0} for i,b in bodies.items()}
    unique = collections.defaultdict(set)
    streak = collections.Counter(); longest = collections.Counter()
    eligible = {}; eaten_turn = {}; before_turn = {}; turns = moves = retrace = eats = 0
    rnd = -1; units = {}; deaths = collections.Counter(); qdeath = None
    qid = next(i for i,d in st.dragons.items() if d.team == me and i <= 1)
    removed = set(); pearls = set()
    def finish():
        for i in eligible:
            if eligible[i]:
                streak[i] = 0 if eaten_turn.get(i) else streak[i]+1
                longest[i] = max(longest[i],streak[i])
    for e in rep['events']:
        k = e['kind']
        if k == 'roundStart':
            finish(); eligible = {}; eaten_turn = {}; rnd = e['round']; removed.clear()
            if rnd in (50,100): units[str(rnd)] = sum(teams[i]==me for i in alive)
        elif k == 'turnStart':
            removed.clear(); i=e['id']
            ok = teams.get(i)==me and i in alive and len(bodies[i])<=6 and 0<=rnd<150
            eligible[i]=ok
            if not ok: streak[i]=0
            if ok:
                turns += 1; unique[i].add(bodies[i][0])
                before_turn[i]=dict(visits.get(i,{}))
        elif k == 'tileChange':
            if e['pearl']: pearls.add(e['tile'])
            else:
                if e['tile'] in pearls: removed.add(e['tile'])
                pearls.discard(e['tile'])
        elif k == 'dragonSplit':
            i,c = e['parent'],e['child']; bodies[i]=list(e['parentBody']); bodies[c]=list(e['childBody'])
            teams[c]=e['team']; alive.add(c); visits[c]={bodies[c][0]:rnd}
            streak[i]=streak[c]=0
        elif k == 'dragonUpdate':
            i=e['id']; head=e['head']
            if i not in bodies or head is None: continue
            b=bodies[i]
            if head == b[0]: continue
            if eligible.get(i):
                moves+=1; unique[i].add(head)
                prior=before_turn.get(i,{}).get(head)
                retrace+= prior is not None and 1<=rnd-prior<=20
                if head in removed or head in pearls:
                    eats+=1; eaten_turn[i]=True
            visits.setdefault(i,{})[head]=rnd
            removed.discard(head); pearls.discard(head)
            b.insert(0,head)
            while len(b)>1 and b[-1]!=e['tail']: b.pop()
            if b[-1]!=e['tail']: raise ValueError(f'tail reconstruction {path} {i} r{rnd}')
        elif k == 'dragonDeath':
            i=e['id']; alive.discard(i)
            if i==qid: qdeath=rnd
            if i>1 and teams.get(i)==me and 0<=rnd<150:
                deaths[DEATHS[e['reason']] if e['reason']<len(DEATHS) else str(e['reason'])]+=1
    finish()
    for r in ('50','100'):
        if r not in units: units[r]=sum(teams[i]==me for i in alive)
    cpu=json.loads(Path(str(path)+'.cpu.json').read_text())[ 'AB'[me] ]
    return dict(game=path.stem,turns=turns,moves=moves,retrace=retrace,eats=eats,
        unique=list(map(len,unique.values())),streak=list(longest.values()),units=units,
        deaths=dict(deaths),queen_death=qdeath,win=rep['result']['winner']==me,cpu=cpu)

def aggregate(rows):
    total=lambda k:sum(r[k] for r in rows)
    mean=lambda xs:statistics.mean(xs) if xs else None
    ds=collections.Counter()
    for r in rows: ds.update(r['deaths'])
    q=[r['queen_death'] for r in rows if r['queen_death'] is not None]
    return dict(games=len(rows),wins=total('win'),unique_cells_per_dragon=mean([x for r in rows for x in r['unique']]),
        retrace_rate=total('retrace')/max(1,total('moves')),eats_per_dragon_turn=total('eats')/max(1,total('turns')),
        longest_streak_mean=mean([x for r in rows for x in r['streak']]),longest_streak_max=max([x for r in rows for x in r['streak']],default=0),
        units50=mean([r['units']['50'] for r in rows]),units100=mean([r['units']['100'] for r in rows]),
        queen_deaths=len(q),queen_death_median=statistics.median(q) if q else None,
        deaths=dict(ds),cpu_peak=max([r['cpu'] for r in rows],default=0))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('directory');ap.add_argument('--out');a=ap.parse_args()
    out=Path(a.out or str(Path(a.directory)/'hunger_metrics.json'))
    state=out.with_suffix('.state.json'); saved=json.loads(state.read_text()) if state.exists() else {}
    version=hashlib.sha256(Path(__file__).read_bytes()+Path('tools/replay_lite.py').read_bytes()+Path('tools/engine_sim.py').read_bytes()).hexdigest()
    rows=[]
    for p in sorted(Path(a.directory).glob('*.replay')):
        sig=[p.stat().st_size,p.stat().st_mtime_ns,version,
             hashlib.sha256(Path(str(p)+'.cpu.json').read_bytes()).hexdigest(),
             hashlib.sha256(Path(str(p)+'.success.json').read_bytes()).hexdigest()]
        if saved.get(p.name,{}).get('identity')!=sig:
            saved[p.name]=dict(identity=sig,result=measure(p))
            tmp=state.with_suffix('.tmp');tmp.write_text(json.dumps(saved),encoding='utf-8');tmp.replace(state)
        rows.append(saved[p.name]['result'])
    result=aggregate(rows);out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
