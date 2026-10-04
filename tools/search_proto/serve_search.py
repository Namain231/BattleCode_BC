"""Research served policy. Uses only known topology and received observations.

One process controls the team: merged observations are an upper bound on
per-dragon communication. Rollouts begin at the requesting ID mid-round.
"""
import argparse
import json
import math
import pathlib
import socket
import sys
import time
from collections import defaultdict,deque
from dataclasses import replace

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'ml')]
import engine_sim as sim
from p8_sensitivity import load_weights, forward, softmax
from build_dataset import parse_map, OFF, VIEW


class Policy:
    def __init__(self, map_path, mode='net', depth=3, queen=True):
        text = pathlib.Path(map_path).read_text()
        initial = sim.load_map(text)
        # Known topology/gaps, never initial bodies or seeded hidden countdowns.
        self.world = sim.State(initial.board, {}, set(),
                               {p: -1 for p in initial.countdowns}, sim.Rng(1))
        self.world.board = replace(initial.board, symmetry='none')
        _, self.w, self.h, self.kelp, self.portal, self.rate = parse_map(text)
        self.weights = load_weights(ROOT / 'baselines/vB19/policy_weights.hpp')
        test = forward(self.weights, self.weights['NN_TEST_PLANES'].astype(np.uint8).reshape(1,16,15,15),
                       self.weights['NN_TEST_SCALARS'].reshape(1,3))[0]
        assert np.max(np.abs(test-self.weights['NN_TEST_LOGITS'])) < 0.001
        self.mode, self.depth, self.queen = mode, depth, queen
        self.team = 0
        self.last_seen = {}
        self.highwater = 0
        self.last_round = -1
        self.confirmed_dead = set()
        self.times, self.depths, self.calls = [], [], []
        self.queen_deaths = {}
        self.rng = np.random.default_rng(123)
        self.cache = {}

    def observe(self, dragon_id, text):
        lines = [s.split() for s in text.splitlines() if s.strip()]
        rnd = int(next(p[1] for p in lines if p[0]=='ROUND'))
        facing = sim.DIRS.index(next(p[1] for p in lines if p[0]=='DIR'))
        length = int(next(p[1] for p in lines if p[0]=='LENGTH'))
        elapsed=rnd-self.last_round if self.last_round>=0 else 0
        if elapsed:
            self.world.countdowns={p:(v-elapsed if v>elapsed else -1) for p,v in self.world.countdowns.items()}
        self.last_round=rnd
        self.world.round = rnd
        tile_start = next(i for i,p in enumerate(lines) if p[0]=='NUM_MSGS')
        tile_start += 1 + int(lines[tile_start][1])
        if lines[tile_start][0]=='ECHOES':
            tile_start += 1
        tiles = lines[tile_start:tile_start+49]
        visible = set()
        for p in tiles:
            x,y,pearl,cd = map(int,p)
            q=(x,y); visible.add(q)
            if pearl: self.world.pearls.add(q)
            else: self.world.pearls.discard(q)
            self.world.countdowns[q]=cd
        bi = next(i for i,p in enumerate(lines) if p[0]=='DRAGON_BODIES')
        records = defaultdict(dict)
        for p in lines[bi+1:bi+1+int(lines[bi][1])]:
            team,i,x,y,heading,head=p
            records[int(i)][int(x),int(y)]=(sim.DIRS.index(heading),int(head),int(team=='B'))
        # Stale enemy sightings are hypotheses, never confirmed deaths.
        for i,d in list(self.world.dragons.items()):
            if d.team != self.team and rnd-self.last_seen.get(i,-10)>1:
                del self.world.dragons[i]
            elif i not in records and d.body and d.body[0] in visible:
                del self.world.dragons[i]
        for i,cells in records.items():
            heads=[q for q,r in cells.items() if r[1]]
            old=self.world.dragons.get(i)
            if not heads:
                # A tail-only sighting has no known moving head: frozen blocker
                # represented separately when checking legal root actions.
                continue
            head=heads[0]; body=[head]; remaining=set(cells)-{head}
            while remaining:
                tail=next((q for q in remaining
                           if self.world.board.neighbours[q,cells[q][0]]==body[-1]),None)
                if tail is None: break
                body.append(tail); remaining.remove(tail)
            # Preserve legally remembered own tail only where not contradicted.
            if old and old.team==self.team:
                while len(body)<(length if i==dragon_id else len(old.body)):
                    q=next((q for q in old.body if q not in body and q not in visible
                            and any(self.world.board.neighbours[q,d]==body[-1] for d in range(4))),None)
                    if q is None: break
                    body.append(q)
            self.world.dragons[i]=sim.Dragon(i,cells[head][2],body,cells[head][0])
            self.last_seen[i]=rnd
            self.confirmed_dead.discard(i)
        assert dragon_id in self.world.dragons, 'own head missing from observation'
        self.world.dragons[dragon_id].facing=facing
        self.highwater=max(self.highwater,max([*self.world.dragons,dragon_id])+1)
        self.world.next_id=self.highwater
        self.blockers={q for cells in records.values() for q in cells}
        self.length_override={dragon_id:length}
        self.world.over=False
        self.cache={}

    def planes(self,state,i):
        d=state.dragons[i]; hx,hy=d.body[0]; f=max(d.facing,0)
        ox,oy=OFF[f]; xs,ys=(hx+ox)%self.w,(hy+oy)%self.h
        pl=np.zeros((16,15,15),np.uint8)
        for r in range(4):
            pl[r]=self.kelp[ys,xs,(r+f)%4]*255
            pl[4+r]=self.portal[ys,xs,(r+f)%4]*255
        pl[8]=self.rate[ys,xs]; pl[9]=VIEW*255
        arrs=np.zeros((6,self.h,self.w),np.uint8)
        for x,y in state.pearls: arrs[0,y,x]=255
        for j,other in state.dragons.items():
            if not other.alive: continue
            L=len(other.body); c=1 if j==i else 2 if other.team==d.team else 3
            for k,(x,y) in enumerate(other.body): arrs[c,y,x]=min(255,(L-k)*16)
            if j!=i:
                x,y=other.body[0]; arrs[4 if other.team==d.team else 5,y,x]=min(255,L*8)
        for c in range(6): pl[10+c]=np.where(VIEW,arrs[c,ys,xs],0)
        L=self.length_override.get(i,len(d.body)) if state is self.world else len(d.body)
        sc=np.array([L/32,state.round/500,sum(x.alive and x.team==d.team for x in state.dragons.values())/64],np.float32)
        return pl,sc

    def probabilities(self,state,i):
        pl,sc=self.planes(state,i)
        key=pl.tobytes()+sc.tobytes()
        if key not in self.cache:
            self.cache[key]=softmax(forward(self.weights,pl[None],sc[None]))[0]
        return self.cache[key]

    def candidates(self,state,i,root=False):
        d=state.dragons[i]
        occupied={p for o in state.dragons.values() if o.alive for p in o.body}
        if root: occupied |= self.blockers
        legal=[]
        probs=self.probabilities(state,i) if self.mode!='trivial' else np.ones(6)/6
        for rel in range(4):
            direct=(max(d.facing,0)+rel)%4
            q=state.board.neighbours[d.body[0],direct]
            if q is not None and q not in occupied:
                legal.append((rel,{'act':'move','dirs':sim.DIRS[direct]},float(probs[rel])))
        L=self.length_override.get(i,len(d.body)) if root else len(d.body)
        if L>=4 and len(d.body)>=4 and sum(o.alive and o.team==d.team for o in state.dragons.values())<state.board.unit_limit:
            legal.append((4,{'act':'split','size':2},float(probs[4])))
        if not legal:
            # Escape with a legal split is already included. A head trade remains
            # available when all empty moves fail; simulator scores the sacrifice.
            for rel in range(4):
                direct=(max(d.facing,0)+rel)%4
                q=state.board.neighbours[d.body[0],direct]
                if q is not None and q not in d.body:
                    legal.append((rel,{'act':'move','dirs':sim.DIRS[direct]},float(probs[rel])))
        if not legal: return [(5,{'act':'suicide'},float(probs[5]))]
        return sorted(legal,key=lambda t:(-t[2],t[0]))

    def rollout(self,i,action,sample):
        state=self.world.copy()
        # No unseen deterministic pearl spawns: only observed countdowns predict
        # a spawn in this short horizon; disable all unknown beds.
        state.board=replace(state.board,gaps={p:g for p,g in state.board.gaps.items() if state.countdowns[p]>0})
        known_queens={q for q in (0,1) if q in state.dragons and state.dragons[q].alive}
        queue=sorted(j for j,d in state.dragons.items() if d.alive and j>=i)
        reached=0
        for depth in range(self.depth):
            if depth:
                state.round+=1
                occ={p:j for j,d in state.dragons.items() if d.alive for p in d.body}
                sim._tick(state,occ,None)
                queue=sorted(j for j,d in state.dragons.items() if d.alive)
            cursor=0
            while cursor<len(queue):
                j=queue[cursor]; cursor+=1
                if not state.dragons[j].alive: continue
                if depth==0 and j==i: act=action
                else:
                    choices=self.candidates(state,j)
                    if state.dragons[j].team!=self.team:
                        ps=np.array([c[2] for c in choices]); ps/=ps.sum()
                        act=choices[int(sample.choice(len(choices),p=ps))][1]
                    else: act=choices[0][1]
                child=sim.apply_action(state,j,act)
                if child is not None: queue.append(child)
            reached=depth+1
            if state.round>=499: break
        material=sum((1 if d.team==self.team else -1)*len(d.body) for d in state.dragons.values() if d.alive)
        score=float(material)
        if self.queen:
            for q in known_queens:
                d=state.dragons[q]
                if not d.alive:
                    score += -(len(self.world.dragons[q].body)+20) if q==self.team else len(self.world.dragons[q].body)+10
                elif state.round>=499:
                    score += (1 if q==self.team else -1)*1000*len(d.body)
        return score,reached

    def contact(self,i,choices):
        # Plan d.1: contact/close-prior trigger. The fixed queen also searches
        # to test the requested survival term. No rollout is time-truncated.
        if i==self.team: return True
        if len(choices)>1 and (choices[0][2]-choices[1][2])/sum(c[2] for c in choices)<=0.10:
            return True
        d=self.world.dragons[i]
        enemies=[e for e in self.world.dragons.values() if e.alive and e.team!=self.team]
        if not enemies: return False
        own=3*((self.length_override.get(i,len(d.body))+3)//4)
        bounds={e.body[0]:own+3*((len(e.body)+3)//4)+1 for e in enemies}
        maximum=max(bounds.values()); queue=deque([(d.body[0],0)]); seen={d.body[0]}
        while queue:
            p,dist=queue.popleft()
            if p in bounds and dist<=bounds[p]: return True
            if dist>=maximum: continue
            for direct in range(4):
                q=self.world.board.neighbours[p,direct]
                if q is not None and q not in seen:
                    seen.add(q); queue.append((q,dist+1))
        return False

    def decide(self,i,text):
        start=time.perf_counter(); self.observe(i,text)
        choices=self.candidates(self.world,i,True); chosen=choices[0]
        maxdepth=0
        if self.mode not in ('net','trivial') and len(choices)>1:
            # Retain net best and candidates >=5% of legal probability mass.
            mass=sum(c[2] for c in choices)
            choices=[c for k,c in enumerate(choices) if k==0 or c[2]>=0.05*mass][:4]
            if len(choices)==1 or not self.contact(i,choices):
                choices=[]
            # An independent per-decision RNG removes dependence on draws
            # consumed by earlier decisions that did not need search.
            self.rng=np.random.default_rng(123+self.world.round*4096+i)
            n=np.zeros(len(choices),int); totals=np.zeros(len(choices)); rawtotals=np.zeros(len(choices))
            rootmaterial=sum((1 if d.team==self.team else -1)*len(d.body)
                             for d in self.world.dragons.values() if d.alive)
            # Initialise every arm, then one UCB1 allocation. Two independent
            # sampled enemy reply trajectories per arm evaluation.
            for trial in range(len(choices)+1 if choices else 0):
                arm=trial if trial<len(choices) else int(np.argmax(totals/n+np.sqrt(2*np.log(n.sum())/n)))
                value=0; rawvalue=0
                for reply in range(2):
                    score,reached=self.rollout(i,choices[arm][1],self.rng)
                    value+=(0.5+0.5*math.tanh((score-rootmaterial)/8))/2
                    rawvalue+=score/2; maxdepth=max(maxdepth,reached)
                n[arm]+=1; totals[arm]+=value; rawtotals[arm]+=rawvalue
            if choices:
                best=int(np.argmax(rawtotals/n)) # preserve unsaturated leaf ranking
                chosen=choices[best]
        self.times.append(time.perf_counter()-start); self.depths.append(maxdepth)
        self.calls.append(len(self.cache))
        action=chosen[1]
        # Retain own body after the selected action, pending fresh observation.
        child=sim.apply_action(self.world,i,action)
        # Guessed rollout child identity is not an authoritative game ID.
        if child is not None: self.world.dragons.pop(child,None)
        if action['act']=='move': command='MOVE '+action['dirs']
        elif action['act']=='split': command='SPLIT '+str(action['size'])
        else: command='' # no action is official suicide
        return (command+'\nPROTOCOL 3\nENDTURN\n').encode()


def serve(args):
    policy=Policy(args.map,args.mode,args.depth,not args.noqueen)
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    sock.bind(args.socket); sock.listen(1)
    result={'mode':args.mode,'map':pathlib.Path(args.map).stem,'complete':False}
    try:
        conn,_=sock.accept()
        with conn,conn.makefile('rb') as stream:
            while line:=stream.readline():
                p=line.decode().split(); kind=p[0]
                if kind=='GAME': policy.team=int(p[2]=='B'); result.update(seed=int(p[1]),side=p[2])
                elif kind in ('SPAWN','TURN'):
                    body=stream.read(int(p[2])).decode(); i=int(p[1])
                    if kind=='SPAWN': policy.highwater=max(policy.highwater,i+1)
                    if kind=='TURN':
                        reply=policy.decide(i,body)
                        conn.sendall(str(len(reply)).encode()+b'\n'+reply)
                        if len(policy.times)%200==0:
                            pathlib.Path(args.out+'.progress.json').write_text(json.dumps({
                                'round':policy.world.round,'turns':len(policy.times),
                                'turn_ms_mean':float(np.mean(policy.times)*1000),
                                'net_calls_mean':float(np.mean(policy.calls)),
                                'searched_turns':sum(d>0 for d in policy.depths)}))
                elif kind=='DEATH':
                    i=int(p[1]); policy.confirmed_dead.add(i)
                    policy.world.dragons.pop(i,None)
                    if i in (0,1): policy.queen_deaths[str(i)]=policy.world.round
                elif kind=='END':
                    result.update(complete=True,winner=p[1],rounds=int(p[2])); break
    finally:
        sock.close(); pathlib.Path(args.socket).unlink(missing_ok=True)
        t=np.array(policy.times)
        result.update(turns=len(t),turn_ms_mean=float(t.mean()*1000) if len(t) else None,
                      turn_ms_p95=float(np.percentile(t,95)*1000) if len(t) else None,
                      depth_max=max(policy.depths,default=0),searched_turns=sum(d>0 for d in policy.depths),
                      depth_histogram={str(d):policy.depths.count(d) for d in sorted(set(policy.depths))},
                      net_calls_mean=float(np.mean(policy.calls)) if policy.calls else None,
                      queen_death_rounds=policy.queen_deaths)
        pathlib.Path(args.out).write_text(json.dumps(result,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--map',required=True); ap.add_argument('--socket',required=True)
    ap.add_argument('--out',required=True); ap.add_argument('--mode',default='net'); ap.add_argument('--depth',type=int,default=3)
    ap.add_argument('--noqueen',action='store_true'); serve(ap.parse_args())
