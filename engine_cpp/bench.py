import sys,time,json,subprocess,re,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from engine_sim import load_map,step
binary=sys.argv[1]
for n in (6,60):
    text='MAP 64 64\n'+''.join(f'DRAGON {i%2} 4 3 {i} 2 {i} 1 {i} 0 {i}\n' for i in range(n))
    base=load_map(text);actions={i:{'act':'move','dirs':'E'} for i in range(n)}
    timings=[]
    for trial in range(3):
        start=time.perf_counter()
        for _ in range(300):
            s=base
            for r in range(3):s=step(s,actions)
        timings.append(time.perf_counter()-start)
    secs=statistics.median(timings);python_rate=900/secs
    outputs=[subprocess.check_output([binary,str(n),'100000'],text=True).strip() for _ in range(3)]
    rates=[float(re.search(r'rounds_per_second=([\d.]+)',o)[1]) for o in outputs]
    rate=statistics.median(rates)
    print(json.dumps({'dragons':n,'python_rounds_s':python_rate,'cpp_rounds_s':rate,
        'python_dragon_turns_s':python_rate*n,'cpp_dragon_turns_s':rate*n,'speedup':rate/python_rate,
        'cpp_output':outputs,'python_seconds':timings}),flush=True)
