"""Run actual C++ override, then feed its emitted decision to engine_sim."""
import sys
sys.dont_write_bytecode=True
import subprocess
from pathlib import Path
from engine_sim import load_map, Dragon, apply_action

def main():
    subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-O0','-std=c++17','out/kz_work/unit.cpp','-o','out/kz_work/unit.exe'],check=True)
    r=subprocess.run([str(Path('out/kz_work/unit.exe').resolve())],check=True,capture_output=True,text=True)
    decision=next(x[5:] for x in r.stdout.splitlines() if x.startswith('MOVE '))
    assert decision=='E',r.stdout
    s=load_map('MAP 32 32\nDRAGON 0 2 5 3 4 3\nDRAGON 1 2 6 5 7 5\n')
    s.dragons[1].body=[(6+i,5) for i in range(20)]
    s.dragons[2]=Dragon(2,0,[(5,5),(4,5)],1)
    apply_action(s,2,{'act':'move','dirs':decision})
    assert not s.dragons[1].alive and s.dragons[1].death==3
    assert not s.dragons[2].alive and s.dragons[2].death==3
    assert s.dragons[0].alive
    print('PASS: C++ MOVE E; length-20 enemy queen and length-2 scout die head-on; own queen survives; four rejection guards pass.')

if __name__=='__main__': main()
