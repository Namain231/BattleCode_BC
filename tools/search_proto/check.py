"""Targeted search policy lifecycle and terminal horizon verification."""
import pathlib
import sys
import numpy as np
from serve_search import Policy,sim,ROOT

def observation(round=0,length=4):
    lines=[f'ROUND {round}','DIR N',f'LENGTH {length}','UNIT_COUNT 1','NUM_MSGS 0','ECHOES 0 0 0 0 0']
    lines += [f'{x} {y} 0 7' for y in range(7) for x in range(7)]
    lines += ['DRAGON_BODIES 4','A 0 3 3 N 1','A 0 3 4 N 0','A 0 3 5 N 0','A 0 3 6 N 0']
    return '\n'.join(lines)

def main():
    p=Policy(ROOT/'maps/default.map')
    p.team=0; p.highwater=20
    p.observe(0,observation())
    assert p.world.next_id==20
    p.world.countdowns[8,8]=8
    p.observe(0,observation(3))
    assert p.world.countdowns[8,8]==5
    p.observe(0,observation(9))
    assert p.world.countdowns[8,8]==-1
    p.observe(0,observation(499))
    _,depth=p.rollout(0,{'act':'move','dirs':'N'},np.random.default_rng(1))
    assert depth==1
    # No queen1 in observation: no spurious unknown enemy-queen death reward.
    p.queen=True; a,_=p.rollout(0,{'act':'move','dirs':'N'},np.random.default_rng(1))
    p.queen=False; b,_=p.rollout(0,{'act':'move','dirs':'N'},np.random.default_rng(1))
    assert a-b==1000*len(p.world.dragons[0].body)
    p=Policy(ROOT/'maps/default.map',mode='net')
    p.candidates=lambda *a,**k:[(4,{'act':'split','size':2},1.)]
    reply=p.decide(0,observation())
    assert reply.startswith(b'SPLIT 2') and set(p.world.dragons)=={0}
    p=Policy(ROOT/'maps/default.map',mode='net')
    p.candidates=lambda *a,**k:[(5,{'act':'suicide'},1.)]
    reply=p.decide(0,observation())
    assert b'MOVE' not in reply and not p.world.dragons[0].alive
    p=Policy(ROOT/'maps/default.map',mode='search')
    p.candidates=lambda *a,**k:[(0,{'act':'move','dirs':'N'},.5),(1,{'act':'move','dirs':'E'},.5)]
    p.rollout=lambda i,action,sample:(10000 if action['dirs']=='E' else 9000,3)
    assert p.decide(0,observation()).startswith(b'MOVE E') # saturated UCB must not erase raw ranking
    print('PASS: NN reference, countdown aging, ID highwater, guessed-child removal, suicide wire parity, r499 depth, unknown queen exclusion')

if __name__=='__main__': main()
