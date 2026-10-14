"""L10 source and ladder audit. Run from repository root: uv run --python 3.11 --with unswbc python -B tools/l10_dive.py.
Writes only out/l10_analysis.txt; serial replay decoding, no pickle caches.
"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import collections as C
import json, math, statistics as S, re, difflib, time, urllib.request
from replay_lite import decode_lite

ROOT = Path.cwd()
LINES=[]
def put(s=''): LINES.append(str(s))
def ci(w,n):
    if not n:return (0,1)
    p=w/n;z=1.959964;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return c-h,c+h
def record(rows):
    n=len(rows);w=sum(g['win'] for g in rows);a,b=ci(w,n)
    return f'{w}/{n} ({100*w/n:.1f}%; Wilson 95% {100*a:.1f}-{100*b:.1f}%)' if n else '0/0'
def mean(xs):return round(S.mean(xs),2) if xs else None

def source():
    put('L10 ANALYSIS -- 2026-10-07 -- original queens determine first tiebreak under current rules')
    put('SOURCE: baselines/L10, Sv5.3=viper_y96qg, Sv5.2=viper_y96qf, Y9_6=baselines/Y9_6.')
    put('L10 is the v6/CPU1/FSPRINT/SEARCH1/queenAmputate rules line with extra aggression, not a new trained v6 model.')
    put('Compared with Y9_6: switches from n4 (16 planes/3 scalars/6 outputs) to v6 (19/6/7), adding queen memory and enemy sprint reach inputs. Only first-direction logits reorder moves within safety classes; extra action outputs are not directly executed.')
    put('Opening changes: enemyCloser .55 -> .85 and enemyTie .8 -> 1.0 value contested pearls more; wCompass .8 -> 1.6; region routing expands from one third of small miners with >=6 units to ALL length<=6 drones with >=2 units before r150. Routing remains known-map-only and excludes true/elected queens. Unknown maps do not receive this compass benefit. URISK19 multiplies head-threat probability by .6 for nonqueen length<=4 drones once >=8 units, reducing risk aversion. QSAFE triples the true queen danger score penalty (all rounds).')
    put('Contains: legacy QPOS four queen rays from r200, stale-position landing buffer, qfeedFrom=280, authenticated queen gossip from r300, portal probes/exploration; CPU1 O(1) enemy reach and 48ms DFS/free-path guards, 52ms attack/option guards, 40ms NN admission; FSPRINT all free 2/3-step paths; SEARCH1 trap veto; queenAmputate and QBOX fallback; updated known-map tables.')
    put('Does NOT contain Sv5.3 early QPOS from r12/heading/mode/threat extensions, encrypted payload, STATUS ray/relay, guardZone new-exit obstruction penalty, guardIntercept assignment, Bayesian laneEcho or enemyPing alarm. qFreeze was false in Sv5.3 anyway. Sv5.2 also lacks that guard system. L10 returns to Sv5.2 sonar layout, with plaintext low-48-bit fields plus a 16-bit SipHash tag; authenticity is not confidentiality. Coordinates/queen length/id/source-round are readable in public replays. Indicators disclose target coordinates, evaluation and AMPUTATE/QBOX/SEARCH1 decisions.')
    put('CPU risk: evaluate disables DFS at 48ms and DFS checks every 64 nodes; options stop after >=2 at >52ms. NN can start at 40ms and forward has no interruption; queenAmputate starts <62ms, checks 60ms only between split sizes, and may run four full evaluations within a size. Flood fill, initial buildReaches/field and minimum two option evaluations are not hard bounded by these admission guards. Removing Sv5.3 status/echo reduces some work but does not establish a safe peak on 64x64.')
    put('Amputation premise risk (shared with Sv5.2/3): assumes child moves and frees its tail before next queen turn; occupied-child cells are only partially modeled during evaluate, and future enemy actions are uncertain. QBOX-SHED is a rescue heuristic, not a survival proof. Attack danger discount and extra routing may trade opening units for growth. Legacy four aggregate rays after r200 disable a uniquely localized forward radar; there is no Sv5.3 ambiguity bookkeeping. Child split does not move parent; legacy code relies on chosenCells being empty on split paths.')
    for d in ['baselines/Y9_6','viper_y96qf','viper_y96qg']:
        a=(ROOT/d/'main.cpp').read_text().splitlines();b=(ROOT/'baselines/L10/main.cpp').read_text().splitlines()
        delta=list(difflib.unified_diff(a,b,n=0));put(f'Normalized source diff vs {d}: added={sum(x.startswith("+") and not x.startswith("+++") for x in delta)} removed={sum(x.startswith("-") and not x.startswith("---") for x in delta)}')
        for f in ['policy_weights.hpp','policy_nn.hpp','policy_weights_v6.hpp','policy_nn_v6.hpp','maps_data.hpp']:
            p=ROOT/'baselines/L10'/f;q=ROOT/d/f
            if q.exists():put(f'{f} vs {d}: byte_equal={p.read_bytes()==q.read_bytes()}, newline_normalized_equal={p.read_text()==q.read_text()}')
    put('Turn clock is reset before readTurn(), so parsing shares the CPU reserve. QSAFE/QROOM/QFLEE are inherited from Sv5.2 and Sv5.3; L10 versus Sv5.2 changes only the four aggression/routing areas listed above.')
    put('n4 policy_weights.hpp differs ONLY in newline encoding: normalized text is identical to Y9_6/Sv5.2/Sv5.3. No weight retraining or manual weight edit; n4 is unused by L10 main include. v6 weights/inference headers byte-identical to both Sv builds.')
    a=(ROOT/'baselines/Y9_6/maps_data.hpp').read_text();b=(ROOT/'baselines/L10/maps_data.hpp').read_text()
    aa=dict(re.findall(r'(m\d+_\w+)\[\]\s*=\s*\{([^}]+)\}',a));bb=dict(re.findall(r'(m\d+_\w+)\[\]\s*=\s*\{([^}]+)\}',b))
    names={idx:name for name,idx in re.findall(r'// ([^\n]+)\nstatic const int (m\d+)_edges',b)}
    for k,v in bb.items():
        if aa.get(k)!=v:put(f'Table changed vs Y9_6: {names.get(k.split("_")[0])} {k}; integer count {len(aa.get(k,"").split(","))}->{len(v.split(","))}')
    put('No tables differ from Sv5.2 or Sv5.3 after newline normalization; 15-map inventory unchanged. Updates are Autarky gaps/spawns, Default edges, Dilemma gaps/spawns, Schooltime edges, Slithery gaps/spawns, Trophy edges/gaps/spawns. Unknown-map generation is not represented by new tables.')
    for i,line in enumerate((ROOT/'baselines/L10/main.cpp').read_text().splitlines(),1):
        if any(t in line for t in ['URISK19','QSAFE','static bool queenAmputate','static uint64_t packSecure','static void castRadar','MY_LEN <= 6 && UNITS >= 2','elapsedMs() > 52','elapsedMs() > 40']):put(f'Source anchor main.cpp:{i}: {line.strip()}')

def audit(g,folder,want):
    p=ROOT/folder/f"{g['game']}.replay"
    rep=decode_lite(str(p),{'roundStart','dragonSplit','dragonDeath','dragonUpdate','dragonAction','dragonIndicator'})
    bot=rep['botA' if g['me']==0 else 'botB']
    if str(bot)!=want:return None,str(bot)
    # Counts start with EVERY initial dragon, not just the two queens.
    owner={};lengths={};qids={}
    for line in rep['map'].splitlines():
        tok=line.split()
        if tok[:1]==['DRAGON']:
            idx=len(owner);owner[idx]=int(tok[1]);lengths[idx]=(len(tok)-2)//2
            if idx<2:qids[owner[idx]]=idx
    alive=set(owner);rnd=-1;snaps={};qd={};tags=C.Counter();points=[]
    # End queen lengths can be recovered exactly from split bodies and updates:
    # keep bodies only for the original queens, walking action paths through map topology.
    from engine_sim import load_map
    board=load_map(rep['map'],1).board
    qb={i:list(d.body) for i,d in load_map(rep['map'],1).dragons.items() if i<2};pending={};validation=C.Counter()
    def snap():return [sum(owner[i]==t for i in alive) for t in (g['me'],1-g['me'])]
    for e in rep['events']:
        k=e['kind'];i=e.get('id')
        if k=='roundStart':
            if rnd in (50,100):snaps[rnd]=snap()
            rnd=e['round']
        elif k=='dragonAction':
            if i in qb:pending[i]=e.get('dirs','')
            if owner.get(i)==g['me'] and e.get('points',0):points.append(e['points'])
        elif k=='dragonSplit':
            owner[e['child']]=e['team'];alive.add(e['child'])
            if e['parent'] in qb:qb[e['parent']]=list(e['parentBody'])
        elif k=='dragonUpdate' and i in qb:
            b=qb[i]
            if e['head'] is not None and e['head']!=b[0]:
                cur=b[0];path=[];used=0
                for ch in pending.get(i,''):
                    cur=board.neighbours[cur,'NESW'.index(ch)];used+=1
                    if cur is None:break
                    path.append(cur)
                    if cur==e['head']:break
                if not path or path[-1]!=e['head']:validation['queen_movement_fallback']+=1;path=[e['head']]
                pending[i]=pending.get(i,'')[used:]
                for p in path:b.insert(0,p)
            while len(b)>1 and b[-1]!=e['tail']:b.pop()
            if b[-1]!=e['tail']:validation['queen_tail_mismatch']+=1
        elif k=='dragonDeath':
            alive.discard(i)
            if i<2:qd[i]=[rnd,['wall','self','body','headon','noaction'][e['reason']] if e['reason']<5 else str(e['reason'])]
        elif k=='dragonIndicator' and owner.get(i)==g['me']:
            for t in ('AMPUTATE','QBOX','S1[','FEED'):
                if t in e['text']:tags[t]+=1
    if rnd in (50,100):snaps[rnd]=snap()
    ours=qids[g['me']];enemy=qids[1-g['me']]
    qlen=[len(qb[q]) if q in alive else 0 for q in (ours,enemy)]
    if snap()!=[g['ours']['count'],g['theirs']['count']]:validation['final_count_mismatch']+=1
    if qd.get(ours)!=g.get('our_queen_death'):validation['queen_metadata_mismatch']+=1
    r=dict(g,snaps=snaps,qlen=qlen,tags=tags,validation=validation,cpu=max(points,default=0),actual_bot=bot)
    if r['win']:bucket='win'
    elif 100 in snaps and snaps[100][1]>0 and snaps[100][0]<=.8*snaps[100][1]:bucket='early unit deficit <=80% at r100'
    elif g['ours']['count']==0:bucket='elimination without measured early deficit'
    elif qlen[0]==0 and qlen[1]>0:bucket='queen-only tiebreak (our queen dead)'
    elif qlen[0]<qlen[1]:bucket='living queen length deficit'
    else:bucket='equal queens; longest/total deficit or draw'
    r['bucket']=bucket
    return r,bot

def aggregate(label,rows):
    put();put(label+' '+record(rows))
    put('Ranked '+record([g for g in rows if g.get('ranked')])+'; unranked '+record([g for g in rows if not g.get('ranked')]))
    put('Draws '+str(sum(g.get('winner') is None for g in rows))+' (strict wins, draws counted in N)')
    q=[g['our_queen_death'] for g in rows if g['our_queen_death']]
    lo,hi=ci(len(q),len(rows));put(f'Queen death {len(q)}/{len(rows)}; 95% {100*lo:.1f}-{100*hi:.1f}%; round mean={mean([x[0] for x in q])} median={S.median([x[0] for x in q]) if q else None}; causes={dict(C.Counter(x[1] for x in q))}; <=50={sum(x[0]<=50 for x in q)} <=100={sum(x[0]<=100 for x in q)}')
    put('Loss buckets (exclusive, early deficit takes precedence): '+str(dict(C.Counter(g['bucket'] for g in rows if not g['win']))))
    put('Loss queen deaths '+str(dict(C.Counter(g['our_queen_death'][1] for g in rows if not g['win'] and g['our_queen_death']))))
    put('Losses our queen dead/enemy living '+str(sum(not g['win'] and g['qlen'][0]==0 and g['qlen'][1]>0 for g in rows)))
    for t in (50,100):
        a=[g for g in rows if t in g['snaps']];put(f'units@r{t}: n={len(a)} mean ours/enemy {[mean([g["snaps"][t][i] for g in a]) for i in (0,1)]}; mean paired margin={mean([g["snaps"][t][0]-g["snaps"][t][1] for g in a])}; early-ended excluded={len(rows)-len(a)}')
    put('Validation '+str(dict(sum((g['validation'] for g in rows),C.Counter()))));put('Indicators '+str(dict(sum((g['tags'] for g in rows),C.Counter()))))
    put('Nonzero replay CPU peak '+str(max((g['cpu'] for g in rows),default=0))+' (zero means stripped/unavailable, not zero cost)')
    for key in ('opp','map'):
        put('BY '+key)
        for v in sorted(set(g[key] for g in rows)):
            a=[g for g in rows if g[key]==v];put(f'{v}: {record(a)}; qdead={sum(bool(g["our_queen_death"]) for g in a)}/{len(a)}')

def comparison(a,b,label):
    put();put('L10 vs '+label+' HISTORICAL SHARED-OPPONENT COMPARISON (not same-seed paired trials)')
    shared=sorted(set(g['opp'] for g in a)&set(g['opp'] for g in b))
    aa=[g for g in a if g['opp'] in shared];bb=[g for g in b if g['opp'] in shared]
    put('Shared pooled L10 '+record(aa)+'; '+label+' '+record(bb))
    for opp in shared:
        x=[g for g in aa if g['opp']==opp];y=[g for g in bb if g['opp']==opp]
        put(opp+': L10 '+record(x)+'; '+label+' '+record(y))
        for t in (50,100):
            put(f'  r{t} units ours/enemy L10 '+str([mean([g['snaps'][t][i] for g in x if t in g['snaps']]) for i in (0,1)])+'; '+label+' '+str([mean([g['snaps'][t][i] for g in y if t in g['snaps']]) for i in (0,1)]))
        for m in sorted(set(g['map'] for g in x)&set(g['map'] for g in y)):
            xx=[g for g in x if g['map']==m];yy=[g for g in y if g['map']==m];put('  matched map '+m+': L10 '+record(xx)+'; '+label+' '+record(yy))
    # Equal-weight shared opponent-map strata remove gross mix differences.
    keys=sorted(set((g['opp'],g['map']) for g in a)&set((g['opp'],g['map']) for g in b))
    if keys:
        rates=[];var=0
        for k in keys:
            x=[g for g in a if (g['opp'],g['map'])==k];y=[g for g in b if (g['opp'],g['map'])==k]
            p=sum(g['win'] for g in x)/len(x);q=sum(g['win'] for g in y)/len(y);rates.append((p,q));var+=p*(1-p)/len(x)+q*(1-q)/len(y)
        mx=S.mean(p for p,q in rates);my=S.mean(q for p,q in rates);h=1.96*math.sqrt(var)/len(keys)
        put(f'Equal-weight {len(keys)} shared opponent-map strata: L10 {100*mx:.1f}%, {label} {100*my:.1f}%, delta {100*(mx-my):+.1f}pp; approximate independent binomial 95% delta [{100*(mx-my-h):+.1f},{100*(mx-my+h):+.1f}]pp. Sparse 0/1 strata understate uncertainty; descriptive only, seeds/time/opponent versions unmatched.')

def main():
    deadline=time.monotonic()+2400
    while not any(x.startswith('done') for x in (ROOT/'out/l10_pull.log').read_text().splitlines()):
        if time.monotonic()>=deadline:raise RuntimeError('pull did not finish within 40 min')
        time.sleep(60)
    source();datasets={}
    for label,folder,want in [('L10','ladder/l10','17124'),('Sv5.3','ladder/sv53','16651'),('Sv5.2','ladder/sv52','16106')]:
        raw=json.loads((ROOT/folder/'games.json').read_text(encoding='utf-8'));put(f'{label} metadata bot counts {dict(C.Counter(str(g.get("bot","missing")) for g in raw))}')
        rows=[];skipped=[]
        selected=[g for g in raw if (str(g.get('bot'))==want or (label=='Sv5.2' and 'bot' not in g))]
        for n,g in enumerate(selected,1):
            r,bot=audit(g,folder,want)
            if r:rows.append(r)
            else:skipped.append((g['game'],bot))
            if n%20==0:print(label,n,'/',len(selected),flush=True)
        put('Replay bot identity exclusions '+str(skipped));datasets[label]=rows;aggregate(label,rows)
    comparison(datasets['L10'],datasets['Sv5.3'],'Sv5.3');comparison(datasets['L10'],datasets['Sv5.2'],'Sv5.2')
    put();put('CPU LOCAL LOG EVIDENCE (historical; no L10 identity established)')
    for name in ['u7_qg.log','u7_qf.log','big_viper_b19_cpu.log','big_vB19.log']:
        p=ROOT/'out'/name
        if p.exists():
            lines=[x for x in p.read_text(errors='replace').splitlines() if x.startswith(('australia_','around_unsw_'))]
            vals=[]
            for line in lines:
                vals.extend(int(x) for x in re.findall(r'\d+/\d+/(\d+)',line))
            put(f'{name}: {len(lines)} Australia/Around-UNSW rows; BOTH-SIDE largest recorded peak={max(vals,default=0):,} points; not attributable to L10 or a side without run manifest. '+(lines[0] if lines else ''))
    put('ELO: metadata includes opponent Elo but no eloChange or timestamps; game IDs provide ordering only. Public team snapshot attempted below; one current rating is not a trajectory.')
    try:
        with urllib.request.urlopen('https://game.battlecode.au/api/v1/teams/98',timeout=20) as f:team=json.load(f)
        put('Team98 current selected fields '+str({k:v for k,v in team.get('team',team).items() if 'elo' in k.lower() or 'rating' in k.lower() or k in ('id','name')}))
    except Exception as e:put('Team98 GET unavailable: '+type(e).__name__+' '+str(e))
    put('LIMITS: replay botA/botB identity is required on every included game; this excludes other builds during the upload-to-present window. No server activation log or current active recheck, so this verifies actual game participation rather than exact wall-clock activation intervals. Sv5.2 missing metadata bot IDs are accepted ONLY after replay identity verification. All data historical; no contemporaneous randomized control, no unknown qualifier maps; Wilson intervals treat games as independent despite repeated opponents/maps. Units are end-of-round and include all initial drones. Early-ended games are right-censored, not assigned zero units. noaction is not classified as CPU death. No bot modifications/submissions/promotions. No L10 smoke run: requested edit scope permits only this script/report, while panel/build tools write additional outputs/caches; historical logs suffice only for contextual CPU risk, not L10 peak verification.')
    put();put('GAME AUDIT: id opponent map side win queens-final bucket r50 r100 CPU')
    for label,rows in datasets.items():
        for g in rows:put(f'{label} {g["game"]} {g["opp"]} {g["map"]} {g["side"]} W={g["win"]} q={g["qlen"]} {g["bucket"]} r50={g["snaps"].get(50)} r100={g["snaps"].get(100)} cpu={g["cpu"]}')
    (ROOT/'out/l10_analysis.txt').write_text('\n'.join(LINES)+'\n',encoding='utf-8')
    print('REPORT out/l10_analysis.txt',len(LINES),'lines',flush=True)

def supplement():
    """Add verification and qualifier decision after the serial audit has completed."""
    import random, subprocess
    p=ROOT/'out/l10_analysis.txt';text=p.read_text(encoding='utf-8').split('\nVERIFICATION APPENDIX AND QUALIFIER RECOMMENDATION')[0]
    if '\nFULL ANALYSIS\n' in text:text=text.split('\nFULL ANALYSIS\n',1)[1]
    text='\n'.join(line.split('; approximate independent binomial')[0]+'; descriptive only: sparse shared strata, unmatched seeds/time/versions.' if line.startswith('Equal-weight ') and '; approximate independent binomial' in line else line for line in text.splitlines())+'\n'
    text=text.replace('Team98 GET unavailable: HTTPError HTTP Error 401: Unauthorized','Unauthenticated Team98 GET: 401; authenticated nested profile/history verified below.')
    text=text.replace('Team98 current selected fields {}','Team98: nested team.elo verified1660 in authenticated profile; see appendix for history.')
    text=text.replace('No L10 smoke run: requested edit scope permits only this script/report, while panel/build tools write additional outputs/caches; historical logs suffice only for contextual CPU risk, not L10 peak verification.', 'The explicitly requested smoke command reused four cached replays; identity and current content hash were checked separately, see verification appendix.')
    text=text.replace('No server activation log or current active recheck,', 'No historical server activation log; current server active submission verified as 17124 on 2026-10-07,')
    lines=['', 'VERIFICATION APPENDIX AND QUALIFIER RECOMMENDATION -- 2026-10-07']
    lines.append('Legacy forward-sonar echo/radar and ROW/QROOM adjacency avoidance remain in L10; what is absent is Sv5.3 Bayesian laneEcho and guardZone introduced-exit logic. Other search/model defaults are otherwise inherited; no network retraining is implicated by the source differences.')
    lines.append('Independent cross-check: game1051078 Default/Sv5.3 compact audit matches tools/sv53_loss_dive.py full-state reconstruction: units r50=[11,10], r100=[19,10], final queen lengths=[0,0], no validation errors.')
    lines.append('AGGR1 contested-pearl multipliers affect queens too, including early rounds; URISK19 excludes true queens and COMPASS excludes true/elected queens.')
    lines.append('L10 vs Sv5.2 normalized main.cpp differs only in contested-pearl weights (.55/.8 -> .85/1), compass weight (.8 -> 1.6), compass eligibility (id%3==0 and >=6 units -> every small drone and >=2 units), and drone threat discount .6. QSAFE, QROOM, QFLEE and other queen heuristics are inherited from Sv5.2, not L10 inventions. No further hidden flag change found.')
    data={}
    for label,folder,bot in [('L10','l10','17124'),('Sv5.3','sv53','16651'),('Sv5.2','sv52',None)]:
        raw=json.loads((ROOT/'ladder'/folder/'games.json').read_text());a=[g for g in raw if bot is None or g.get('bot')==bot];data[label]=a
        lines.append(f'{label} mean historical opponent Elo={S.mean(g["oppElo"] for g in a):.1f}. Ranked/unranked mix differs; pooled advantage is confounded by easier opponents for L10.')
    # Compact game audit keeps enough state for post-run per-opponent opening tables.
    audit_snaps={}
    for line in text.splitlines():
        match=re.match(r'(L10|Sv5\.3|Sv5\.2) (\d+) ',line)
        if not match:continue
        snaps={}
        for t in (50,100):
            ss=re.search(r'r'+str(t)+r'=\[(\d+), (\d+)\]',line)
            if ss:snaps[t]=[int(ss[1]),int(ss[2])]
        audit_snaps[match[1],int(match[2])]=snaps
    lines.append('PER-OPPONENT OPENING COUNTS: means ours/enemy; n excludes games ended before snapshot.')
    for label,rr in data.items():
        for opp in sorted(set(g['opp'] for g in rr)):
            for t in (50,100):
                counts=[audit_snaps[label,g['game']][t] for g in rr if g['opp']==opp and t in audit_snaps.get((label,g['game']),{})]
                lines.append(f'{label} {opp} r{t} n={len(counts)} units={[mean([x[i] for x in counts]) for i in (0,1)]}; margin={mean([x[0]-x[1] for x in counts])}')
    for label in ['Sv5.3','Sv5.2']:
        a=data['L10'];b=data[label];shared=set(g['opp'] for g in a)&set(g['opp'] for g in b)
        aa=[g for g in a if g['opp'] in shared];bb=[g for g in b if g['opp'] in shared]
        for name,rr in [('L10',aa),(label,bb)]:lines.append(f'Shared opponents vs {label}: {name} queen dead={sum(bool(g["our_queen_death"]) for g in rr)}/{len(rr)}; early queen <=100={sum(bool(g["our_queen_death"]) and g["our_queen_death"][0]<=100 for g in rr)}/{len(rr)}.')
        pa=sum(g['win'] for g in aa)/len(aa);pb=sum(g['win'] for g in bb)/len(bb);la,ua=ci(sum(g['win'] for g in aa),len(aa));lb,ub=ci(sum(g['win'] for g in bb),len(bb))
        low=pa-pb-math.sqrt((pa-la)**2+(ub-pb)**2);high=pa-pb+math.sqrt((ua-pa)**2+(pb-lb)**2)
        lines.append(f'Shared-opponent raw win-rate delta L10 minus {label}={100*(pa-pb):+.1f}pp; Newcombe/Wilson independent-samples 95% [{100*low:+.1f},{100*high:+.1f}]pp. This is NOT a same-seed paired estimate.')
        keys=set((g['opp'],g['map']) for g in a)&set((g['opp'],g['map']) for g in b);delta=C.defaultdict(list)
        for k in sorted(keys):
            x=[g for g in a if (g['opp'],g['map'])==k];y=[g for g in b if (g['opp'],g['map'])==k];delta[k[0]].append(sum(g['win'] for g in x)/len(x)-sum(g['win'] for g in y)/len(y))
        names=sorted(delta);rng=random.Random(17124);draws=[]
        for _ in range(10000):
            vals=[v for name in rng.choices(names,k=len(names)) for v in delta[name]];draws.append(S.mean(vals))
        draws.sort();lines.append(f'Equal-weight shared opponent/map delta, exploratory opponent-cluster bootstrap 95% percentile range [{100*draws[249]:+.1f},{100*draws[9749]:+.1f}]pp ({len(names)} opponent clusters). Resamples opponent clusters, not seeds; small clusters and historical version drift limit inference. A plug-in binomial variance would be anti-conservative for sparse 0/1 strata, so no such interval is used.')
    lines.append('LIVE REPLAY CPU: nonzero point fields were present in ALL 752 L10 / 147 Sv5.3 / 77 Sv5.2 games, unlike the older stripped-replay history. L10 largest recorded turn=66.083242M on 64x64 Australia game1244563; Around UNSW peak=65.239199M game1105708. Sv5.3 overall peak=66.162092M Around UNSW game1051081 (Australia64.626724M game1045323); Sv5.2 peak=65.131331M Australia game985911 (Around UNSW64.910041M game985836). These are attributable to replay-verified bot IDs, but historical opponent/board/length mix differs. The L10 live peak exceeds the 65M target by1.083M; it remains below100M on recorded actions. Missing/invalid-action instruction records can censor failures; noaction is not assumed CPU exhaustion. No hard worst-case bound is established.')
    smoke=ROOT/'out/l10_smoke/summary.json'
    if smoke.exists():
        rows=json.loads(smoke.read_text());lines.append('Requested smoke: panel_zig.py baselines/L10 baselines/Y9_6 out/l10_smoke --maps australia,around_unsw --seeds 3 -j 1. --seeds 3 means ONLY seed 3, both sides: four games, all cached, zero failures, L10 0/4; Wilson 95% win interval 0-49.0%. Cache itself does not bind bot identity; replay headers separately verified L10-00050c6e6cb67eae.wasm vs Y9_6-237782e315b0ca3c.wasm, matching currently built content-hash artifact names.')
        for g in rows:lines.append(f'Smoke {g["map"]} seed={g["seed"]} side={g["side"]}: L10 peak {g["cpu_max_ours_M"]:.6f}M; Y9_6 {g["cpu_max_theirs_M"]:.6f}M; W={g["win"]}.')
        lines.append('Australia is 64x64: observed L10 peak 64.899739M. Around UNSW is 60x40: peak 64.925890M. These are below 100M and near the repo 65M target; four games cannot bound rare late/big-body peaks or unknown topology; the live Australia audit actually reaches66.083242M, above these smoke peaks. No guard hard cap proves that evaluation/NN can never overshoot. All four smoke queens died head-on: r395/193 on Australia A/B, r382/418 Around UNSW A/B. Both enemy queens also died; losses therefore reached longest/total tiebreak. CPU survival alone did not make the build competitive in this smoke.')
    lines.append('Historical local comparison out/u7_qf.log: Sv5.2 54.5/98 score points (55.6%, draws half); out/u7_qg.log: Sv5.3 50/98 (51.0%) vs Y9_6. Maze 10.5/14 vs 4/14, Stripes 9/14 vs 13/14, Tower Defense 5/14 vs 2/14, weakhold 9/14 vs 8/14; Australia 6/14 vs 8/14 and Around UNSW 7/14 vs 6/14 (Sv5.2 vs Sv5.3 throughout). Do not mix half-draw local scores with strict ladder wins. Opponent/seed sets appear matched in logs but no fresh sealed-control proof or independent causal isolation was performed here.')
    lines.append('ELO VERIFICATION: authenticated /submissions returned id17124 name L.10 status active. /teams/98 exposes a nested team object: team.elo=1660, rank122, peak1911. Team history last before upload: 1682 at Oct04 21:21:23Z; day-end Oct04 1679, Oct05 1680, latest Oct06 21:55:30Z 1660 (-22 from pre-upload), post-upload range1585-1732 across144 history entries. This is team-level history, not exclusively replay-verified L10 games. /battles?limit=200 returned eloChange; join to the replay-verified L10 metadata battle IDs yields 155 series (140 ranked), net -15 Elo: Oct04 UTC -3 (14 series, 21:40:46Z-23:27:19Z), Oct05 +1 (84 series, 00:08:56Z-23:17:07Z), Oct06 -13 (57 series, 00:07:44Z-17:21:45Z). Seventeen later series since upload are outside the completed pull; not assigned to L10 without replay IDs. These are a partial relative trajectory, not exclusively attributable full-period L10 performance or evidence of individual-game Elo changes.')
    lines.append('RECOMMENDATION: freeze Sv5.2 (viper_y96qf/id16106 source) for 2026-10-09 unknown-map qualifiers, as a conservative choice, not a proven best build. It has the same v6 weights, CPU1 guards, FSPRINT, SEARCH1, queenAmputate/QBOX and updated tables as L10, without L10 aggression changes or Sv5.3 extra guard/status/echo machinery. L10 raw win advantage mostly disappears after matching opponents and turns negative with equal-weight shared map groups; its mean opponent Elo is ~83 below Sv5.3. L10 live peak66.083M is modestly above the 65M target (Sv5.2 observed65.131M); L10 0/4 big-map smoke and recurring both-dead-queen tiebreaks do not support replacing the older conservative baseline. Sv5.3 extra guard system has no convincing ladder gain and the local Maze regression is adverse. The data cannot causally rank the three; the preference uses simplicity, historical unknown-map safety evidence and uncertainty.')
    lines.append('What changes this recommendation: a fresh same-time randomized A/B across strong shared opponents and unseen representative maps, balanced sides/seeds, demonstrating an opening/queen-survival improvement with intervals excluding a material regression; repeat late 64x64 CPU stress with long queens/allied congestion/portals and attributable peak points, including noaction diagnostics. Prefer L10 if it wins that comparison while keeping CPU headroom; prefer Sv5.3 if guard protection beats both on queen survival without the observed Maze/opening costs. Do not tune on the held-out maps or infer causality from one map flip.')
    lines.append('Unverified: unseen Oct09 map distribution, actual live ladder opponent source/version, seed pairing/activation timeline, L10 causal feature benefit, hard worst-case CPU bound, intentional feeding vs noaction, exclusive L10 attribution of the full team Elo history and post-pull games. No source/build was changed or activated; this is advice only. No independent second-agent critique was performed.')
    summary = [
        'L10 ANALYSIS SUMMARY -- 2026-10-07',
        'Recommendation: freeze Sv5.2 (viper_y96qf), conservatively; no activation/submission was performed.',
        'L10 355/752 = 47.2% (Wilson95% 43.7-50.8); Sv5.3 58/147 = 39.5% (31.9-47.5); Sv5.2 29/77 = 37.7% (27.7-48.8).',
        'L10 faced easier opponents (mean Elo1697 vs1780 Sv5.3); its raw lead is not a controlled improvement.',
        'Shared opponents: L10 minus Sv5.3 +2.9pp (Newcombe95% -10.4,+15.7); minus Sv5.2 +1.6pp (-18.8,+20.8).',
        'Equal-weight shared opponent/map rates favor older builds; sparse historical comparisons cannot establish a causal ranking.',
        'L10 queen died503/752 (66.9%), medianr183: headon355, wall90, self43, body15. Shared-opponent survival advantage is small.',
        'L10 losses: early unit deficit231/397; equal-queen longest/total101; dead-queen tiebreak22; living-queen deficit15; elimination28.',
        'L10 mean units ours/enemy: r50 12.36/12.76 (n752); r100 20.09/21.89 (n741; early-ended games excluded).',
        'L10 is Sv5.2 with stronger pearl competition/routing and a small-drone risk discount. v6 weights identical; n4 difference is line endings only.',
        'It retains legacy QPOS/echo/queen spacing, CPU1/FSPRINT/SEARCH1/amputation/QBOX; it lacks Sv5.3 encryption/status/guard/intercept/laneEcho/enemyPing.',
        'Updated map tables are identical to Sv5.2/3. Compass routing benefits known maps only; AGGR1 also changes early queen foraging.',
        'CPU: live L10 peak66.083242M on64x64 Australia; cached current-hash four-game smoke peak64.925890M, 0/4 wins. No hard worst-case CPU guarantee.',
        'Team Elo1682 before upload ->1660 latest; replay-matched155 series net-15. Full history includes later games without replay attribution.',
        'All976 included replays pass ID/count/queen checks; two missing-ID L10 pull rows excluded. Source/model/CPU/seed-control limits are detailed below.',
        'A fresh balanced same-time comparison on unseen maps, including late big-map CPU and queen survival, could change the recommendation.'
    ]
    p.write_text('\n'.join(summary)+'\n\nFULL ANALYSIS\n'+text+'\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':
    main()
    supplement()
