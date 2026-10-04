"""Standalone seeded-spawn differential; no spawn or countdown injection."""
import sys,json
from pathlib import Path
from verify import snapshot,compare
from engine_sim import load_map,step
out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
base='MAP 12 12\nSYMMETRY xy\nDRAGON 0 4 3 3 2 3 1 3 0 3\nDRAGON 1 4 8 8 9 8 10 8 11 8\n'
for name,rows in [('dense',range(12)),('separated',[5,6])]:
    text=base+''.join(f'TILE {x} {y} {1+(x+y)%3} {4+(x+y)%3}\n' for y in rows for x in range(12))
    s=load_map(text,seed=1)
    with (out/(name+'.jsonl')).open('w') as f:
        f.write(json.dumps({'map':text,'seeded':True,'initial':snapshot(s)})+'\n')
        for r in range(50):
            if s.over:break
            actions={i:{'act':'move','dirs':'E' if d.team==0 else 'W'} for i,d in s.dragons.items() if d.alive}
            turns=sorted(actions);s=step(s,actions)
            f.write(json.dumps({'round':r,'seeded':True,'reset':{},'spawn':[],'actions':actions,'turns':turns,'expected':snapshot(s)})+'\n')
raise SystemExit(compare(sys.argv[1],out,expected_games=2))
