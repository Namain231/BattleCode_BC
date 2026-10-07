"""Compile the actual hunger C++ and verify its chosen score direction in engine_sim."""
import sys
sys.dont_write_bytecode=True
import subprocess
from pathlib import Path
from engine_sim import load_map, Dragon, apply_action

SOURCE = r'''
#define main bot_entry
#include "../../viper_nv30h/main.cpp"
#undef main
#include <cassert>
int main() {
 W=H=16; N=W*H; MY_ID=2; MY_TEAM=0; MY_LEN=2; ROUND=0;
 body={5*W+5,5*W+4};
 for(int c=0;c<N;c++) {
  seenR[c]=0; enemyDist[c]=friendDist[c]=9999; spawnAt[c]=mirSpawn[c]=-2; gmax[c]=gmin[c]=-1;
  for(int d=0;d<4;d++) {obsK[c*4+d]=1;nbr[c*4+d]=stepRaw(c,d);}
 }
 updateHunger(); assert(hungerLevel==0);
 ROUND=60; hungerLastEat=0; hungerPrevLen=2;
 visitR[5*W+5]=59; visitR[5*W+4]=58; visitR[4*W+5]=59; visitR[6*W+5]=59;
 updateHunger(); assert(hungerLevel==1); assert(hungerTarget>=0);
 assert(hungerDist[body[0]]==1); int next=-1, dir=-1;
 double best=-1e9;
 for(int d=0;d<4;d++) {int c=nbr[body[0]*4+d];
  SimResult option; option.cells={c};
  double score=hungerMoveScore(option);
  if(score>best) best=score,next=c,dir=d;
 }
 assert(dir==1 && visitR[next]<0); printf("MOVE E\n");
 int c=next; seenR[c]=-1;
 assert(pearlProb(c,80)>pearlProbBase(c,80));
 gmax[c]=0; assert(pearlProb(c,80)==0);gmax[c]=-1;
 obsK[body[0]*4+1]=3; assert(!hungerEdge(body[0],1));obsK[body[0]*4+1]=1;
 MY_LEN=1; ROUND++; updateHunger(); assert(hungerLevel==1); // paid sprint shrink is not a meal
 hungerLastEat=ROUND; updateHunger(); assert(hungerLevel==0); // explicit split reset
 MY_ID=0; MY_LEN=2; hungerPrevLen=2; hungerLastEat=0; ROUND=90; updateHunger(); assert(hungerLevel==0.6 && hungerTarget<0);
 hungerQueenOption=false;assert(pearlProb(c,100)==pearlProbBase(c,100));
 enemyDist[body[0]]=8;updateHunger();assert(hungerLevel==0);
 enemyDist[body[0]]=999;ROUND=100;updateHunger();assert(hungerLevel==0);
 P.hunger=false;ROUND=70;updateHunger();assert(hungerLevel==0 && hungerTarget<0);
 assert(pearlProb(0,80)==pearlProbBase(0,80));
}
'''

def main():
    out=Path('out/hunger_unit');out.mkdir(parents=True,exist_ok=True)
    (out/'unit.cpp').write_text(SOURCE,encoding='utf-8')
    subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-O0','-std=c++17',str(out/'unit.cpp'),'-o',str(out/'unit.exe')],check=True)
    r=subprocess.run([str((out/'unit.exe').resolve())],check=True,capture_output=True,text=True)
    assert 'MOVE E' in r.stdout
    s=load_map('MAP 16 16\nDRAGON 0 2 2 2 1 2\nDRAGON 1 2 12 12 13 12\n')
    s.dragons[2]=Dragon(2,0,[(5,5),(4,5)],1)
    apply_action(s,2,{'act':'move','dirs':'E'})
    assert s.dragons[2].alive and s.dragons[2].body[0]==(6,5)
    print('PASS: actual C++ hunger selects unvisited east over three recent paths; engine_sim move survives; birth/split/queen threat/late/off guards pass.')

if __name__=='__main__':main()
