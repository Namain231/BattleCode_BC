"""Serial, cache-free Sv5.3 loss dive. Writes only the requested report.
Run from repo root: python -B tools/sv53_loss_dive.py
"""
import sys
sys.dont_write_bytecode = True
import collections as C
import json
import statistics as S
from pathlib import Path
from replay_lite import decode_lite
from engine_sim import load_map
from echo_eval import portal_edges

ROOT = Path.cwd()
NAMES = ['tungtung67', 'Jingling Munmin', 'Check Raise', 'avid coders', 'code matters', 'Vodyanitsa']
CAUSE = ['wall', 'self', 'body', 'headon', 'noaction']
TIMES = [25, 50, 100, 200, 300, 400]
K = {'roundStart','turnStart','dragonAction','dragonUpdate','dragonSplit','dragonDeath','tileChange','dragonIndicator','sonarPing'}

def analyse(g, folder, detail=False):
    rep = decode_lite(str(ROOT/folder/f"{g['game']}.replay"), K)
    state = load_map(rep['map'], 1)
    board = state.board
    portals = portal_edges(rep['map'], board)
    teams = {i:d.team for i,d in state.dragons.items()}
    body = {i:list(d.body) for i,d in state.dragons.items()}
    alive = set(body)
    initial_ids = set(body)
    occ = {p:(i,j) for i in alive for j,p in enumerate(body[i])}
    me = g['me']; qids = [next(i for i in (0,1) if teams[i]==t) for t in (me,1-me)]
    rnd = -1; actor = None; pending = {}; action = {}; indicators = {}; history = C.defaultdict(list)
    deaths = []; snaps = {}; eats = C.Counter(); corpse_eats=C.Counter(); sources={}; first=[None,None]
    splits=C.Counter(); tags=C.Counter(); pings=C.Counter(); lastdeath=None; validation=C.Counter(); collision=None
    dumps=[]; queencontext=[]
    def dist(a,b):
        dx=abs(a[0]-b[0]); dy=abs(a[1]-b[1])
        return max(min(dx,board.width-dx),min(dy,board.height-dy))
    def snapshot():
        out=[]
        for t,q in zip((me,1-me),qids):
            lens=[len(body[i]) for i in alive if teams[i]==t]
            out.append((len(lens),len(body[q]) if q in alive else 0,max(lens,default=0),sum(lens)))
        return out
    def context(i):
        h=body[i][0]; exits=[]
        for d,ch in enumerate('NESW'):
            p=board.neighbours[h,d]; hit=occ.get(p)
            exits.append(f'{ch}:{"wall" if p is None else "open" if hit is None else "self" if hit[0]==i else ("ally" if teams[hit[0]]==teams[i] else "enemy")+str(hit[0])+"/"+str(hit[1])}{"/portal" if (h,d) in portals else ""}')
        friends=[j for j in alive if j!=i and teams[j]==teams[i] and dist(h,body[j][0])<=6]
        enemies=sorted([(dist(h,body[j][0]),j,len(body[j])) for j in alive if teams[j]!=teams[i]])[:4]
        return dict(head=h,length=len(body[i]),exits=exits,allies6=len(friends),enemy_nearest=enemies)
    def dump(i,label):
        if not detail or i not in alive:return
        h=body[i][0]; rows=[]
        for dy in range(-5,6):
            s=''
            for dx in range(-5,6):
                p=((h[0]+dx)%board.width,(h[1]+dy)%board.height); hit=occ.get(p)
                s += '.' if hit is None else ('Q' if hit[0]==i and hit[1]==0 else 'q' if hit[0]==i else 'A' if teams[hit[0]]==me and hit[1]==0 else 'a' if teams[hit[0]]==me else 'E' if hit[1]==0 else 'e')
            rows.append(s)
        dumps.append((rnd,label,context(i),rows))
    # Detail windows are selected from first-pass end-of-round counts.
    target=g.get('_swing',-1000); qround=(g.get('our_queen_death') or [-1000])[0]
    for e in rep['events']:
        k=e['kind']
        if k=='roundStart':
            if rnd>=0:snaps[rnd]=snapshot()
            rnd=e['round']; actor=None;lastdeath=None;collision=None
            if detail and (abs(rnd-qround)<=2 or abs(rnd-target)<=2):
                dump(qids[0],f'round-start queen; swing={target}')
        elif k=='turnStart':
            actor=e['id']; lastdeath=None; collision=None; pending[actor]=[]
        elif k=='dragonIndicator':
            i=e['id']; indicators[i]=(rnd,e['text']); history[i].append((rnd,e['text']))
            history[i]=history[i][-4:]
            if teams.get(i)==me:
                for tag in ('QG','STAT','FEED','QBOX','SHED','HUNT'):
                    if tag in e['text']:tags[tag]+=1
        elif k=='dragonAction':
            actor=e['id']; action[actor]=e;pending[actor]=list(e.get('dirs',''))
            if detail and actor==qids[0] and (abs(rnd-qround)<=2 or abs(rnd-target)<=2):dump(actor,'before queen action '+str(e.get('dirs',e.get('act'))))
        elif k=='dragonUpdate':
            i=e['id'];b=body[i];old=list(b)
            if e['head'] is not None and e['head']!=b[0]:
                cur=b[0]; path=[];used=0
                for ch in pending.get(i,[]):
                    cur=board.neighbours[cur,'NESW'.index(ch)]; used+=1
                    if cur is None:break
                    path.append(cur)
                    if cur==e['head']:break
                if not path or path[-1]!=e['head']:
                    validation['movement_fallback']+=1;path=[e['head']]
                pending[i]=pending.get(i,[])[used:]
                for p in path:b.insert(0,p)
            while len(b)>1 and b[-1]!=e['tail']:b.pop()
            if b[-1]!=e['tail']:validation['tail_mismatch']+=1
            for p in old:
                if occ.get(p,(None,))[0]==i:occ.pop(p,None)
            for j,p in enumerate(b):occ[p]=(i,j)
        elif k=='dragonSplit':
            t=e['team'];i=e['child'];teams[i]=t;alive.add(i)
            for p in body[e['parent']]:occ.pop(p,None)
            body[e['parent']]=list(e['parentBody']);body[i]=list(e['childBody'])
            for di in (i,e['parent']):
                for j,p in enumerate(body[di]):occ[p]=(di,j)
            ix=0 if t==me else 1
            if first[ix] is None:first[ix]=rnd
            splits[ix,rnd]+=1
        elif k=='dragonDeath':
            i=e['id'];reason=CAUSE[e['reason']] if e['reason']<5 else str(e['reason'])
            if collision is None and actor in body and pending.get(actor):
                h=body[actor][0];d='NESW'.index(pending[actor][0]);p=board.neighbours[h,d]
                hit=occ.get(p)
                collision=(actor,hit,p,(h,d) in portals)
            ca,hit,p,portal=collision if collision else (actor,None,None,False)
            targetid=hit[0] if hit else None
            rel='unknown'
            if reason in ('wall','self','noaction'):rel=reason
            elif reason=='headon':
                other=targetid if i==ca else ca
                rel=('ally' if teams.get(other)==teams.get(i) else 'enemy')+('-initiated' if i==ca else '-incoming') if other in teams else 'unknown'
            elif reason=='body' and targetid in teams:
                rel=('ally' if teams[targetid]==teams[i] else 'enemy')+('-tail' if hit[1]==len(body[targetid])-1 else '-body')
            dd=dict(round=rnd,id=i,team=teams.get(i),length=len(body[i]),cause=reason,actor=ca,target=targetid,segment=hit[1] if hit else None,cell=p,portal=portal,relation=rel,ind=history[i][:],dirs=action.get(ca,{}).get('dirs'),ctx=context(i))
            deaths.append(dd)
            if i in qids:queencontext.append(dd)
            for cell in body[i]:
                if occ.get(cell,(None,))[0]==i:occ.pop(cell,None)
            alive.discard(i);lastdeath=i
        elif k=='tileChange':
            p=e['tile']
            if e['pearl']:
                sources[p]=('corpse',teams.get(lastdeath),lastdeath,rnd) if lastdeath is not None else ('spawn',None,None,rnd)
            else:
                if actor in teams:
                    ix=0 if teams[actor]==me else 1;eats[ix,rnd]+=1
                    source=sources.pop(p,None)
                    if source and source[0]=='corpse':corpse_eats[ix,source[1]]+=1
                else:validation['eat_no_actor']+=1
        elif k=='sonarPing':
            sender=e.get('sender')
            if teams.get(sender)==me:
                pings[e.get('hitKind')]+=1
                if e.get('value',0)>>48==0x5155:tags['plaintext_QPOS']+=1
    if rnd>=0:snaps[rnd]=snapshot()
    end=snapshot()
    for ix in (0,1):
        expected=rep['result']['AB'[me if ix==0 else 1-me]]
        if tuple(expected[k] for k in ('count','longest','total')) != (end[ix][0],end[ix][2],end[ix][3]):validation['result_mismatch']+=1
    for key in ('lost',):
        omitted=[d for d in deaths if d['team']==me and d['id'] in initial_ids and d['id'] not in qids]
        actual=C.Counter(d['cause'] for d in deaths if d['team']==me and (d['id'] not in initial_ids or d['id'] in qids))
        if omitted:
            validation['metadata_rows_omitting_initial_drones']+=1
            validation['metadata_omitted_initial_drone_deaths']+=len(omitted)
        if dict(actual)!=g[key]:validation['metadata_death_count_mismatch']+=1
    return dict(g, snaps=snaps, end=end, deaths=deaths, eats=eats,corpse=corpse_eats,first=first,splits=splits,tags=tags,pings=pings,validation=validation,queencontext=queencontext,dumps=dumps,last=rnd,folder=folder)

def classify(r):
    if r['win']:return 'win'
    o,t=r['snaps'].get(100,[(0,0,0,0)]*2)
    if t[0] and o[0]<=.8*t[0]:return 'early economy deficit (units <=80% at r100)'
    if r['end'][0][0]==0:return 'eliminated without early unit deficit'
    if r['end'][0][1]==0 and r['end'][1][1]>0:return 'queen-only tiebreak loss, enemy queen survives'
    if r['end'][0][1]<r['end'][1][1]:return 'living queen length deficit'
    return 'equal queen length: longest/total deficit'

def avg(vals):return round(S.mean(vals),2) if vals else None

def report(rows, old, details):
    lines=[]
    def put(s=''):lines.append(str(s))
    put('SV53 LOSS DIVE -- 2026-10-04; cache-free sequential replay reconstruction')
    put('Scope: bot 16651 only; original queens 0/1; end-of-round snapshots. State=(units, queen length, longest, total).')
    put('Mechanics: other-body collisions kill the mover, head-on kills BOTH; tails do not strike or cut a stationary victim. Dead original queen scores zero; surviving drones cannot replace her (docs/structure.md).')
    put('Methods: replay_lite decode, echo_eval pending sprint reconstruction and portal_edges, engine_sim board topology, ladder_report body/split accounting, analyze_losses early-deficit classifier. No pickle caches, submissions, panels, or replay modifications.')
    put(f"DATA: n={len(rows)} wins={sum(r['win'] for r in rows)} losses={sum(not r['win'] for r in rows)} queen deaths={sum(bool(r['our_queen_death']) for r in rows)}; sv52 n={len(old)}.")
    put('VALIDATION '+str(dict(sum((r['validation'] for r in rows+old),C.Counter()))))
    losses=[r for r in rows if not r['win']]
    put('LOSS CLASSES (exclusive precedence: early deficit, eliminated, queen-only, living queen, equal queens): '+str(dict(C.Counter(classify(r) for r in losses))))
    put('LOSS DRAGON DEATHS '+str(dict(C.Counter(d['cause'] for r in losses for d in r['deaths'] if d['team']==r['me']))))
    put('LOSS COLLISION RELATIONS '+str(dict(C.Counter(d['relation'] for r in losses for d in r['deaths'] if d['team']==r['me']))))
    put('LOSS QUEEN DEATHS '+str(dict(C.Counter(r['our_queen_death'][1] for r in losses if r['our_queen_death']))))
    for label,subset in [('wins',[r for r in rows if r['win']]),('losses',losses)]:
        q=[r['our_queen_death'][0] for r in subset if r['our_queen_death']]
        put(f"{label}: n={len(subset)} our queen deaths={len(q)} median={S.median(q) if q else None}; enemy queen survives={sum(not r['enemy_queen_death'] for r in subset)}; queens both dead={sum(bool(r['enemy_queen_death']) and bool(r['our_queen_death']) for r in subset)}; early queen <=50={sum(x<=50 for x in q)}")
    for name in NAMES:
        rr=[r for r in rows if r['opp']==name]; ll=[r for r in rr if not r['win']]; bb=[r for r in old if r['opp']==name]
        put();put('OPPONENT '+name)
        put(f"W/N {sum(r['win'] for r in rr)}/{len(rr)}; loss classes={dict(C.Counter(classify(r) for r in ll))}; enemy queen survives in losses={sum(not r['enemy_queen_death'] for r in ll)}/{len(ll)}")
        for label,ss in [('all',rr),('loss',ll)]:
            for t in TIMES:
                available=[r for r in ss if t in r['snaps']]
                stateavg=[tuple(avg([r['snaps'][t][ix][j] for r in available]) for j in range(4)) for ix in (0,1)]
                put(f'{label} r{t} n={len(available)} ours|enemy={stateavg}')
        put('first split median ours/enemy='+str([S.median([r['first'][ix] for r in rr if r['first'][ix] is not None]) if any(r['first'][ix] is not None for r in rr) else None for ix in (0,1)]))
        for lo,hi in [(0,24),(25,49),(50,99),(100,199),(200,299),(300,399),(400,499)]:
            denom=sum(max(0,min(hi,r['last'])-lo+1) for r in rr)
            rates=[round(sum(v for r in rr for (side,t),v in r['eats'].items() if side==ix and lo<=t<=hi)/max(1,denom),3) for ix in (0,1)]
            put(f'eats/played round [{lo},{hi}] ours/enemy={rates}; denominator={denom}')
        put('our deaths (all games)='+str(dict(C.Counter(d['cause'] for r in rr for d in r['deaths'] if d['team']==r['me']))))
        put('our collisions (all games)='+str(dict(C.Counter(d['relation'] for r in rr for d in r['deaths'] if d['team']==r['me']))))
        put('queen death games '+str([(r['game'],r['map'],r['our_queen_death'],r['enemy_queen_death']) for r in rr]))
        put('maps enemy wins='+str(dict(C.Counter(r['map'] for r in ll))))
        put('corpse pearls eaten ours/enemy (from either team)='+str([sum(v for r in rr for (ix,_),v in r['corpse'].items() if ix==s) for s in (0,1)]))
        late=C.Counter()
        for r in rr:
            for d in r['deaths']:
                if d['round']>=max(0,r['last']-99):
                    side='ours' if d['team']==r['me'] else 'enemy'
                    late[side+'/'+d['relation']]+=1
        put('last 100 played rounds deaths='+str(dict(late)))
        put('final states per game '+str([(r['game'],r['win'],r['last'],r['end']) for r in rr]))
        put('FEATURE TAGS '+str(dict(sum((r['tags'] for r in rr),C.Counter()))))
        if bb:
            put(f"SV52 same opponent W/N={sum(r['win'] for r in bb)}/{len(bb)}; our queen deaths={sum(bool(r['our_queen_death']) for r in bb)}; enemy queen survives={sum(not r['enemy_queen_death'] for r in bb)}")
            common=sorted(set(r['map'] for r in bb)&set(r['map'] for r in rr))
            for m in common:
                a=[r for r in rr if r['map']==m];b=[r for r in bb if r['map']==m]
                put(f"matched map {m}: Sv53 {sum(r['win'] for r in a)}/{len(a)}, Sv52 {sum(r['win'] for r in b)}/{len(b)}; queen died {sum(bool(r['our_queen_death']) for r in a)}/{len(a)} vs {sum(bool(r['our_queen_death']) for r in b)}/{len(b)}")
            for t in (25,50,100,200,400):
                put(f"SV52 r{t} available={sum(t in r['snaps'] for r in bb)} avg ours/enemy="+str([tuple(avg([r['snaps'][t][ix][j] for r in bb if t in r['snaps']]) for j in range(4)) for ix in (0,1)]))
        else:put('SV52: no same-opponent games.')
    put();put('REPRESENTATIVE LOST GAMES (three per named opponent, earliest/middle/latest queen death, distinct maps where available)')
    for r in details:
        put();put(f"DETAIL game={r['game']} opp={r['opp']} map={r['map']} me={r['me']} class={classify(r)} end={r['end']}")
        put('queen contexts='+str(r['queencontext']))
        swing=r['_swing'];put(f'biggest 10-round own unit drop ends r{swing}: '+str([(t,r['snaps'].get(t)) for t in range(max(0,swing-12),min(r['last'],swing+3)+1)]))
        qround=(r['our_queen_death'] or [-999])[0]
        for d in r['deaths']:
            if abs(d['round']-qround)<=3 or abs(d['round']-swing)<=3:put('event '+str(d))
        for rnd,label,ctx,grid in r['dumps']:
            put(f'BOARD r{rnd} {label}: {ctx}; Q/q own queen, A/a ours, E/e enemy, . empty; 11x11 wrapped occupancy; exits give walls/portals, grid does not show edges.')
            for line in grid:put(line)
        put('last-100 snapshots='+str([(t,r['snaps'][t]) for t in sorted(r['snaps']) if t>=max(0,r['last']-100) and (t%10==0 or t==r['last'])]))
    put();put('ALL GAME AUDIT')
    for r in rows:
        put(f"{r['game']} {r['opp']} {r['map']} win={r['win']} class={classify(r)} qd={r['our_queen_death']} eqd={r['enemy_queen_death']} first={r['first']} end={r['end']} snapshots="+str({t:r['snaps'].get(t) for t in TIMES}))
    put();put('LIMITS: chronology supports tactics, not opponent intent or causal effect of sonar features. No same-seed/same-time ladder control; opponent code/version not available. Late noaction is NOT assumed feeding (may be error); ally-body death is possible feeding only with timing/indicators. Corpse counts identify pearls spawned directly after deaths; cannot establish intentional corpse farming. Portal collision flags use actual board edges. No CPU conclusions: replay point fields may be stripped. QG/STAT decision tags are absent; encrypted packets and bot-local guard state were not decoded, so guard/intercept causality is unverified. Eats count tileChange pearl=false attributed to the active dragon, not net length change. Right-censored snapshots exclude ended games; no missing-round zeros. Original queen stays queen even after death.')
    return lines

def main():
    games=[g for g in json.loads((ROOT/'ladder/sv53/games.json').read_text(encoding='utf-8')) if str(g.get('bot'))=='16651']
    oldgames=json.loads((ROOT/'ladder/sv52/games.json').read_text(encoding='utf-8'))
    rows=[];old=[]
    for folder,gg,dst in [('ladder/sv53',games,rows),('ladder/sv52',oldgames,old)]:
        for n,g in enumerate(gg,1):
            dst.append(analyse(g,folder))
            if n%15==0:print(f'{folder}: {n}/{len(gg)} decoded',flush=True)
    details=[]
    for name in NAMES:
        ll=sorted([r for r in rows if r['opp']==name and not r['win']],key=lambda r:(r['our_queen_death'] or [999])[0])
        selected=[]
        for idx in (0,len(ll)//2,len(ll)-1):
            if ll and ll[idx] not in selected:selected.append(ll[idx])
        for r in selected:
            swing=max((t for t in r['snaps'] if t>=10),key=lambda t:r['snaps'].get(t-10,r['snaps'][t])[0][0]-r['snaps'][t][0][0],default=0)
            g={k:v for k,v in r.items() if k in games[0]};g['_swing']=swing
            details.append(analyse(g,r['folder'],True))
    lines=report(rows,old,details)
    lines.extend(comparison_lines())
    lines.extend(CURATED)
    (ROOT/'out/sv53_losses.txt').write_text('\n'.join(f'L{n:04d} {s}' for n,s in enumerate(lines,1))+'\n',encoding='utf-8')
    print('REPORT out/sv53_losses.txt',len(lines),'lines;',len(details),'detailed games',flush=True)

def comparison_lines():
    """Metadata comparison on genuinely shared opponents; no replay caches."""
    a=[r for r in json.loads((ROOT/'ladder/sv53/games.json').read_text(encoding='utf-8')) if str(r.get('bot'))=='16651']
    b=json.loads((ROOT/'ladder/sv52/games.json').read_text(encoding='utf-8'))
    result=['SHARED-OPPONENT SV52 COMPARISON (historical, unmatched seeds/time; descriptive only)']
    shared=sorted(set(r['opp'] for r in a)&set(r['opp'] for r in b))
    result.append('Only shared opponents: '+', '.join(shared)+'; NONE of the six focus opponents has a Sv52 control.')
    for name in shared:
        aa=[r for r in a if r['opp']==name];bb=[r for r in b if r['opp']==name]
        for tag,ss in [('Sv53',aa),('Sv52',bb)]:
            result.append(f"{name} {tag}: wins={sum(r['win'] for r in ss)}/{len(ss)} queen deaths={sum(bool(r['our_queen_death']) for r in ss)} causes={dict(C.Counter(r['our_queen_death'][1] for r in ss if r['our_queen_death']))}; median death={S.median([r['our_queen_death'][0] for r in ss if r['our_queen_death']]) if any(r['our_queen_death'] for r in ss) else None}; enemy queen survives={sum(not r['enemy_queen_death'] for r in ss)}; eliminated={sum(r['ours']['count']==0 for r in ss)}; avg final ours/enemy="+str([tuple(avg([r[key][field] for r in ss]) for field in ('count','longest','total')) for key in ('ours','theirs')]))
        for m in sorted(set(r['map'] for r in aa)&set(r['map'] for r in bb)):
            x=[r for r in aa if r['map']==m];y=[r for r in bb if r['map']==m]
            result.append(f"{name} matched map {m}: Sv53 {sum(r['win'] for r in x)}/{len(x)}, Sv52 {sum(r['win'] for r in y)}/{len(y)}; queen deaths {sum(bool(r['our_queen_death']) for r in x)}/{len(x)} vs {sum(bool(r['our_queen_death']) for r in y)}/{len(y)}")
    return result
CURATED = ['',
 'ANALYST FINDINGS / RANKED CAUSES (observed outcomes versus causal hypotheses distinguished)',
 'Exclusive diagnostic buckets (L0007): 52/89 early unit deficits at r100; 22 equal-queen longest/total '
 'deficits without early deficit; 9 eliminations without early deficit; 5 dead-queen versus surviving-queen '
 'tiebreaks without early deficit; 1 living-queen length deficit without early deficit. The buckets are '
 'exclusive; ended-before-r100 losses enter elimination rather than being zero-filled at r100. They describe '
 'timing, not a proof that unit counts alone caused the loss.',
 "Exact terminal score priority across all 89 losses: {'elimination': 37, 'queen priority': 15, 'longest "
 "after equal queens': 36, 'total after equal queens and longest': 1}. These differ from diagnostic buckets "
 'because early deficits can finish by any score priority.',
 'Ranked physical losses from FULL replay ownership, not the incomplete games.json lost field: 5430 '
 'wall/self deaths (3210 wall + 2220 self); 4144 enemy head-on deaths (2455 initiated by us + 1689 '
 'incoming); 1285 friendly collision deaths (912 head-on, 373 body/tail); 852 noaction deaths (includes '
 'intentional FEED); 279 enemy-body/tail collisions. Total 11990 own dragons. Head-on pairs involving two of '
 'ours correctly count two dragon deaths, not one collision.',
 'Queen death association: 83/89 losses, 66 head-on; 26/32 wins when our queen survives versus 32/115 when '
 'she dies. This is correlation, not a controlled treatment effect. The 18 representative losses contain 16 '
 "queen deaths: {'headon/enemy-incoming': 12, 'wall/wall': 2, 'self/self': 1, 'body/enemy-body': 1}. All 12 "
 'representative head-on queen deaths are incoming enemy rams; no sampled queen death is an initiated tail '
 'strike.',
 'Detail windows contain 53 confirmed own FEED deaths, including 8 at length >4; those counts cover only the '
 'displayed +/-3-round windows, not all games. Intentional FEED is identified by a same-round indicator; '
 'untagged noaction is not called a timeout or feeding.',
 '',
 'OPPONENT TACTICS -- concrete observed actions; special queen-targeting intent cannot be inferred from a '
 'generic ram',
 'tungtung67: faster pearl economy, more corpse recovery, small-dragon sprint rams, and larger late sinks. '
 'First split median is r0 for both, but r0-24 eats/round 0.339 ours vs 0.496 theirs (L0028-0031). By r200: '
 '23.27 vs 39.73 units (L0025); corpse pearls 3323 vs 6971 (L0040). Trophy 1045337 r42: enemy #4 L3 uses SE '
 'to ram our L3 queen with 5 friendly heads within radius 6; Maze 1045328 r139: #86 uses NW to ram her '
 '(L0209, L0308). Schooltime 1045332: both queens remain L3; at r400 ours 5 units/longest4/total15 versus '
 'theirs 46/35/286, then final longest 3 vs 50 (L0408, L0537). All 17 maps are losses; this is not explained '
 'by a single queen survival bug.',
 'Jingling Munmin: stronger early extraction followed by earlier/better consolidation; our own '
 'pocket/crowding deaths help them. r50-99 eats/round 1.848 vs 2.708, despite ours leading units 38.8 vs '
 '34.4 at r200 (L0057,L0063). Maze 1055006 r141: our L3 queen has three walls and her neck, nearest enemy 7 '
 'cells away, DOOMED queen: amputate (L0540). Slithery 1055008 r238: L2 queen has two walls, self, and '
 'allied #885 segment1 closing the last exit, 12 allies within radius6; nearest enemy 8 away (L0643). This '
 'is allied boxing, not an enemy tail strike. Schooltime 1055005: both queens L3; our longest43 vs theirs10 '
 'at r400 becomes49 vs57 at finish; our swarm falls14 to4 while theirs keeps23 (L0773,L0909). All five maps '
 'lost, four despite their queen dying.',
 'Check Raise: economy-driven swarm pressure plus queen rams, then feeding a surviving queen. In the three '
 'losses r100 units 8.33 vs15, r200 14.33 vs34 (L0088-0089). Stripes 1055026 r74 enemy #8 rams queen; Maze '
 '1055025 r261 enemy #131 uses NE while queen is in a one-exit corridor (L0912,L1073). Tower Defense 1055022 '
 'r107 queen is L2 in a three-wall pocket with her neck blocking the fourth exit (L0991); no enemy-body '
 'contact causes this death. Maze r400 theirs queen9 grows40 at finish, ours dead, despite our fallback '
 'longest24 and total88 versus98 (L1072,L1174). They win Stripes, Tower Defense, Maze; we win Autarky and '
 'Trauma.',
 'avid coders: early economy and repeated incoming queen rams; later a large body blocks an escape, followed '
 'by stronger longest-dragon consolidation. Loss-game units r100 16.82 vs27, r20022 vs39.5 (L0120-0121); '
 'total corpse eats 4475 vs7860 (L0136). Trophy 1035387 r87: enemy #53 rams queen while #56 is also '
 'adjacent; QoS 1035381 r277: #105 rams her (L1177,L1273). Maze 1035378 r375: queen NWN escape fails on '
 'segment7 of enemy #392 L15 after two successful steps, with N/E walls and S own body through a portal '
 '(L1487). This is an enemy body block, not an attacking tail cutting our queen. At r400 ours36 '
 'units/longest4 vs theirs19/21; final ours9/22 vs theirs20/32 (L1598). Their 11 winning maps are listed at '
 'L0135.',
 'code matters contrast: our all-game early eats are better (0.384 vs0.341 at r0-24 and1.274 vs1.052 at '
 'r50-99), explaining why the same macro can win9/17 rather than0/17 (L0157,L0159). Their losses against us '
 'still show the same vulnerability: Trophy r27 queen BUD is followed by enemy #4 NWWW ram; Tower Defense '
 'r183 #24 SSS ram; Dilemma r432 #255 NNNE ram (L1601,L1689,L1780). Those are concrete sprint contacts, not '
 'evidence that STATUS or QPOS directly caused them.',
 'Vodyanitsa contrast: we win5/9 overall, but their four wins all eliminate us; on losses r100 units2.33 '
 'vs44 (n3; one ended earlier, L0184). Trophy #8 SS ram r57; Devil #77 W ram r81 even though their queen '
 'died r18; Tower #44 S ram r165 (L1989,L2070,L2159). They win Devil, Stripes, Tower Defense, Trophy. '
 'Killing their queen early is insufficient against a swarm approaching64 units.',
 '',
 'SV53 FEATURES: visible failure versus attribution',
 'No QG/STAT decision tags occur in the six focus opponents; source viper_y96qg/main.cpp has no such '
 'indicator emission. Ordinary movement, BUD, FEED, DOOMED, and X rejected-packet indicators are present. '
 'QPOS/status/enemy-ping processing is implemented at main.cpp:1632,1893,2360,2414; packets were not '
 'decrypted in this dive.',
 'Guard protection visibly fails to keep exits open in Jingling Slithery (L0643) and does not stop queen '
 'rams with nearby allies in tung Trophy/Maze (L0209,L0308). This shows insufficient protection; it does NOT '
 'establish that guardZone, QPOS, or intercept caused the crowding or death. Self/wall pocket deaths '
 'preclude attributing everything to enemy tactics.',
 'Intercept-specific deaths cannot be identified: the replay does not label intercept selection, and '
 'ordinary ATK/hunting also creates enemy-initiated trades. Enemy-ping caution and status-ray displacement '
 'of useful sonar cannot be isolated from historical outcomes. No verified feature-specific regression is '
 'claimed.',
 'For causal feature checks, use existing single-toggle builds viper_y96qg_nq (qposFrom0), _nz (guardZone '
 'false), _ni (guardIntercept false), _nl (laneEcho false), _np (enemyPing false), compared to viper_y96qg '
 'on identical map/seed/opponent panels. statusRay alone needs a new copy with only that flag false. All-off '
 'viper_y96qg_off is a bundle check, not attribution.',
 '',
 'FIVE CONCRETE, TESTABLE CHANGES -- proposals only; bot code unchanged; tests below NOT run',
 'Common control: from PowerShell, run uv run --python 3.11 --with unswbc python tools/regression_gate.py '
 'viper_y96qg out/sv53_control --opp baselines/Y9_6 --set live --seeds 10,11,12 -j 2 --min-queen-round 200. '
 'Use exactly the same engine/path and map seeds for candidates. This is 17 maps x3 seeds x2 sides if live '
 'still contains17; retain all actual map names. A passing local screen does not substitute for same-time '
 'ladder A/B.',
 '1. Queen sprint-threat exclusion: screen each original-queen move/split endpoint against visible enemy '
 'reachable-head cells, including free/paid sprint steps and real portals; prefer a non-reachable endpoint '
 'before pearl reward. Do not require complete global state. Evidence L0209,L0308,L0912,L1177,L1689: '
 'incoming small-dragon rams, often with last pd0.00. Candidate sv53_qsafe; local test: uv run --python 3.11 '
 '--with unswbc python tools/regression_gate.py sv53_qsafe out/sv53_qsafe --opp baselines/Y9_6 --set live '
 '--seeds 10,11,12 -j 2 --min-queen-round 200. Compare queen head-on counts/median survival and final '
 'queen-length margin to control; reject if safer queens merely starve or total wins fall.',
 '2. Local queen pocket lookahead: before entering a known cul-de-sac, reconstruct the post-move own body '
 'and visible friendly occupancy and require an available next-turn exit; prioritize this for L2/L3 queens '
 'that cannot amputate. Unknown geometry remains a frontier, not a reason to skip all lookahead. Evidence '
 'L0540 (three walls+self), L0643 (two walls+self+ally), L0991 (three walls+self). Candidate sv53_qexit; '
 'local test: uv run --python 3.11 --with unswbc python tools/regression_gate.py sv53_qexit out/sv53_qexit '
 '--opp baselines/Y9_6 --set live --seeds 10,11,12 -j 2 --min-queen-round 200. Track queen wall/self deaths, '
 'blocked-exit states and losses on maze/slithery_fight/tower_defense; require fewer traps without lower '
 'queen-length margins.',
 '3. Shorten early drone pearl horizon: change minerGamma0.90 to0.80 for non-queens through r100 only, '
 'preserving later behavior. Evidence L0028-0031 and L0124-0127: first splits equally early, but '
 'substantially lower early pearl throughput versus the strongest teams; code matters contrast L0157,L0159. '
 'Candidate sv53_near; local test: uv run --python 3.11 --with unswbc python tools/regression_gate.py '
 'sv53_near out/sv53_near --opp baselines/Y9_6 --set live --seeds 10,11,12 -j 2 --min-queen-round 200. '
 'Compare eats/played-round and units/total at r25/50/100; success needs higher r100 economy and wins, with '
 'no higher wall/self losses.',
 '4. Cap deliberate feed sacrifices at L4: in tryFeed return false for MY_LEN>4, retaining larger dragons as '
 'fallback sinks/backups rather than allowing repeated half-mass transfers. Evidence L0319-0325: '
 'FEED543->558,527->628,628(L5)->558,558(L11)->648; L1488,L1598 show late own units33->9 while longest22 '
 'still loses32. Candidate sv53_feed4; local test: uv run --python 3.11 --with unswbc python '
 'tools/regression_gate.py sv53_feed4 out/sv53_feed4 --opp baselines/Y9_6 --set live --seeds 10,11,12 -j 2 '
 '--min-queen-round 200. Verify zero same-round FEED deaths at L5+, compare last100 total retention and '
 'longest margins when queens tie/die, and require no regression in surviving-queen length or elimination '
 'rate.',
 '5. Make blind portal permission require fresh evidence: if a move crosses a portal with unknown landing '
 'occupancy or unmapped own-body cells, stop before crossing and cast a portal probe; take it only after a '
 'fresh clear result. Enforce for the entire sprint path rather than only its endpoint; use real mapped '
 'destinations for known portals. Evidence L0409: Schooltime r284 dies on an enemy tail through a portal; '
 'L0410: r285 dies on its own L2 tail through another portal, despite pd0.00. Candidate sv53_portal; local '
 'test: uv run --python 3.11 --with unswbc python tools/regression_gate.py sv53_portal out/sv53_portal --opp '
 'baselines/Y9_6 --set live --seeds 10,11,12 -j 2 --min-queen-round 200. Compare fatal portal crossings and '
 'per-round eats on schooltime/portals/trophy/maze; reject if reduced crossings merely strand dragons or '
 'erase the economy gain.',
 '',
 'NOT VERIFIED: opponent source/intent, whether opponents changed builds between Sv52/Sv53, packet contents '
 'or guard branch choices, CPU/timeout causes, counterfactual safety of each proposed move, or any proposed '
 'change via local matches. No six-focus-opponent Sv52 comparisons exist. Feature ablations and same-time '
 'ladder controls remain necessary. The only files authored were tools/sv53_loss_dive.py, '
 'out/sv53_losses.txt, and one appended UTF-8 AGENT_LOG.md line.']

if __name__=='__main__':main()
