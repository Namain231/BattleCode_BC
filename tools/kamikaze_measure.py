"""Cache-free, sequential turn-state opportunity audit; resume after each game."""
import sys
sys.dont_write_bytecode = True
import argparse, collections, json, statistics, os
import ctypes, time, hashlib
from pathlib import Path
from replay_lite import decode_lite
from engine_sim import load_map

KINDS = {'roundStart','turnStart','dragonAction','dragonUpdate','dragonSplit','dragonDeath','tileChange','dragonIndicator'}

def memory_guard():
    if os.name!='nt': return
    class Status(ctypes.Structure):
        _fields_=[('size',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ('total','free','page','pagefree','virtual','virtualfree','extended')]
    while True:
        s=Status(); s.size=ctypes.sizeof(s)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)): raise OSError('Cannot read memory status')
        if s.free>=1536*1024**2: return
        print('Audit waits for 1.5 GiB free RAM (one replay only)',flush=True); time.sleep(20)

def path_to(board, bodies, alive, pearls, actor, target, paid=0, visible=False, lower=None):
    b = tuple(bodies[actor]); free = (len(b)+3)//4
    occ = {p:i for i in alive if i != actor for p in bodies[i]}
    goal = bodies[target][0]; origin = b[0]
    def seen(p):
        dx=abs(p[0]-origin[0]); dy=abs(p[1]-origin[1])
        return min(dx,board.width-dx)<=3 and min(dy,board.height-dy)<=3
    if visible and not seen(goal): return None
    todo=collections.deque([(b, frozenset(), '')]); visited=set()
    while todo:
        body,eaten,path=todo.popleft()
        if len(path)>=free+paid: continue
        pay=len(path)>=free
        if pay and len(body)<3: continue
        for d,ch in enumerate('NESW'):
            p=board.neighbours[body[0],d]
            if p is None or p in body or (visible and not seen(p)): continue
            if lower is not None and lower.get(p,99999)>free+paid-len(path)-1: continue
            if p==goal: return path+ch
            if p in occ: continue
            ate=p in pearls and p not in eaten
            nb=(p,)+body if ate else (p,)+body[:-1]
            if pay: nb=nb[:-1]
            ne=eaten|{p} if ate else eaten
            key=(nb,ne,len(path)+1)
            if key not in visited:
                visited.add(key); todo.append((nb,ne,path+ch))
    return None

def analyse(path, me, want=None, opportunities=True):
    rep=decode_lite(str(path),KINDS)
    if want and str(rep['bot'+'AB'[me]])!=want: return None
    state=load_map(rep['map']); board=state.board
    bodies={i:list(d.body) for i,d in state.dragons.items()}; teams={i:d.team for i,d in state.dragons.items()}
    alive=set(bodies); pearls=set(); pending={}; actor=None; rnd=-1
    q=next(i for i in (0,1) if teams[i]==me); eq=1-q
    rounds=set(); visible_rounds=set(); lengths=[]; reverse=[]; qdeath=None; qdeath_tick=None; first_opp_tick=None; tags=0; legacy=0; ram_turns=set(); queen_headon_turns=[]
    failures=collections.Counter()
    reverse_edges=collections.defaultdict(list)
    for (p,d),n in board.neighbours.items():
        if n is not None: reverse_edges[n].append(p)
    distance_goal=None; distances={}
    for tick,e in enumerate(rep['events']):
        k=e['kind']
        if k=='roundStart': rnd=e['round']
        elif k=='turnStart':
            actor=e['id']
            if opportunities and actor in alive and actor>1 and teams[actor]==me and eq in alive:
                # Cheap geometry filter: only scouts within graph distance free+2 need a body search.
                cap=(len(bodies[actor])+3)//4+2
                if distance_goal!=bodies[eq][0]:
                    distance_goal=bodies[eq][0]; distances={distance_goal:0}; queue=collections.deque([distance_goal])
                    while queue:
                        p=queue.popleft()
                        for n in reverse_edges[p]:
                            if n not in distances: distances[n]=distances[p]+1; queue.append(n)
                reachable=distances.get(bodies[actor][0],99999)<=cap
                if reachable and path_to(board,bodies,alive,pearls,actor,eq,2,lower=distances):
                    rounds.add(rnd); lengths.append(len(bodies[actor]))
                    if first_opp_tick is None: first_opp_tick=tick
                    if path_to(board,bodies,alive,pearls,actor,eq,2,True,distances): visible_rounds.add(rnd)
        elif k=='dragonAction': actor=e['id']; pending[actor]=list(e.get('dirs',''))
        elif k=='dragonIndicator':
            words=e['text'].split()
            if teams.get(e['id'])==me:
                if words[:1]==['K1']: tags+=1; ram_turns.add((rnd,e['id']))
                elif words[:2]==['ATK',str(eq)]: legacy+=1; ram_turns.add((rnd,e['id']))
        elif k=='tileChange':
            if e['pearl']: pearls.add(e['tile'])
            else: pearls.discard(e['tile'])
        elif k=='dragonUpdate':
            i=e['id']; b=bodies[i]
            if e['head'] is not None and e['head']!=b[0]:
                cur=b[0]; route=[]; used=0
                for ch in pending.get(i,[]):
                    used+=1; cur=board.neighbours[cur,'NESW'.index(ch)]
                    if cur is None: break
                    route.append(cur)
                    if cur==e['head']: break
                if not route or route[-1]!=e['head']: failures['movement']+=1; route=[e['head']]
                pending[i]=pending.get(i,[])[used:]
                for p in route: b.insert(0,p)
            while len(b)>1 and b[-1]!=e['tail']: b.pop()
            if b[-1]!=e['tail']: failures['tail']+=1
        elif k=='dragonSplit':
            i=e['child']; teams[i]=e['team']; alive.add(i)
            bodies[i]=list(e['childBody']); bodies[e['parent']]=list(e['parentBody'])
        elif k=='dragonDeath':
            i=e['id']
            if i==q: qdeath=rnd; qdeath_tick=tick
            if i==eq and e['reason']==3 and teams.get(actor)==me: queen_headon_turns.append((rnd,actor))
            if i==q and e['reason']==3 and actor in alive and actor!=q and teams[actor]!=me and len(bodies[actor])<=4:
                route=pending.get(actor,[]); h=bodies[actor][0]; portal=False; steps=0
                for ch in route:
                    d='NESW'.index(ch); p=board.neighbours[h,d]
                    if p is None: break
                    steps+=1
                    expected=((h[0]+(d==1)-(d==3))%board.width,(h[1]+(d==2)-(d==0))%board.height)
                    portal |= p!=expected; h=p
                    if h==bodies[q][0]: break
                reverse.append({'round':rnd,'length':len(bodies[actor]),'steps':steps,'portal':portal})
            alive.discard(i)
    for t in (0,1):
        lens=[len(bodies[i]) for i in alive if teams[i]==t]; expected=rep['result']['AB'[t]]
        if (len(lens),max(lens,default=0),sum(lens))!=tuple(expected[x] for x in ('count','longest','total')): failures['final']+=1
    return dict(game=path.stem,rounds=len(rounds),visible_rounds=len(visible_rounds),lengths=lengths,
                later_queen_death=qdeath_tick is not None and first_opp_tick is not None and first_opp_tick<qdeath_tick,queen_dead=qdeath is not None,ordered=True,
                reverse=reverse,rams=tags,legacy_rams=legacy,queen_rams=tags+legacy,
                ramkills=sum(t in ram_turns for t in queen_headon_turns),validation=dict(failures),win=rep['result']['winner']==me)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--panel'); ap.add_argument('--repair-order',action='store_true'); ap.add_argument('--output',default='out/kz_measure.json'); a=ap.parse_args()
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    lock=out.with_suffix('.lock').open('a+b')
    if os.name=='nt':
        import msvcrt
        lock.seek(0,2)
        if lock.tell()==0: lock.write(b'0'); lock.flush()
        while True:
            lock.seek(0)
            try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1); break
            except OSError: print('Waiting for existing audit',flush=True); time.sleep(20)
    version=hashlib.sha256(Path(__file__).read_bytes()+Path('tools/replay_lite.py').read_bytes()+Path('tools/engine_sim.py').read_bytes()).hexdigest()
    metadata=out.with_suffix('.identity.json')
    identities=json.loads(metadata.read_text()) if metadata.exists() else {}
    rows=json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
    sources=[('l10','17124'),('sv53','16651'),('sv52','16106')]
    if a.panel:
        jobs=[(p,int(p.stem.rsplit('_',1)[1]=='B'),None,False) for p in Path(a.panel).glob('*.replay')]
    else:
        jobs=[]
        for folder,want in sources:
            for g in json.loads(Path('ladder',folder,'games.json').read_text(encoding='utf-8')):
                if str(g.get('bot',want))!=want: continue
                jobs.append((Path('ladder',folder,str(g['game'])+'.replay'),int(g['side'].lower()=='b'),want,True))
    for p,me,want,opp in jobs:
        key=str(p)
        old=rows.get(key)
        h=hashlib.sha256()
        if p.exists():
            with p.open('rb') as f:
                for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
        identity=dict(version=version,replay=h.hexdigest() if p.exists() else None,me=me,want=want,opportunities=opp)
        needs_repair=a.repair_order and old and not old.get('ordered') and old['rounds']>0 and old['queen_dead'] and not old['later_queen_death']
        if key in rows and identities.get(key)==identity and not needs_repair: continue
        memory_guard()
        r=analyse(p,me,want,opp) if p.exists() else None; rows[key]=r
        tmp=out.with_suffix('.tmp'); tmp.write_text(json.dumps(rows),encoding='utf-8'); os.replace(tmp,out)
        identities[key]=identity
        tmp=metadata.with_suffix('.tmp'); tmp.write_text(json.dumps(identities),encoding='utf-8'); os.replace(tmp,metadata)
        if len(rows)%25==0: print('completed',len(rows),flush=True)
    valid=[r for r in rows.values() if r]
    print(json.dumps({'games':len(valid),'opportunity_games':sum(r['rounds']>0 for r in valid),'visible_games':sum(r['visible_rounds']>0 for r in valid),'later_queen_death':sum(r['later_queen_death'] for r in valid),'reverse_kills':sum(len(r['reverse']) for r in valid),'rams':sum(r['rams'] for r in valid),'ramkills':sum(r['ramkills'] for r in valid),'validation':dict(sum((collections.Counter(r['validation']) for r in valid),collections.Counter()))}))
    out.with_suffix('.DONE').write_text('complete\n',encoding='utf-8')
    lock.close()

if __name__=='__main__': main()
