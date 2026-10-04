#include "engine.hpp"
#include <cstdio>
#include <cstdlib>
#include <chrono>
using namespace loong;
static volatile unsigned long long sink;
int main(int argc,char** argv) {
 int n=argc>1?atoi(argv[1]):6, reps=argc>2?atoi(argv[2]):100000;
 if((n!=6 && n!=60)||reps<=0) return 2;
 Map m{};m.width=m.height=64;m.unitLimit=64;
 Game base{};base.map=&m;
 for(int c=0;c<MAX_CELLS;++c) {base.occupant[c]=base.towardHead[c]=base.towardTail[c]=-1;base.countdown[c]=-1;}
 for(int i=0;i<n;++i) {
   auto& d=base.dragon[i];d.id=i;d.team=i%2;d.alive=1;d.facing=E;d.length=4;d.head=i*64+3;d.tail=i*64;
   for(int x=0;x<4;++x) {int c=i*64+x;base.occupant[c]=i;base.towardHead[c]=x==3?-1:c+1;base.towardTail[c]=x==0?-1:c-1;}
   ++base.alive[i%2];
 }
 base.nextId=n;Begin(base,1);
 auto start=std::chrono::steady_clock::now();
 for(int k=0;k<reps;++k) {
   Game branch=base;
   for(int r=0;r<3;++r) {
     branch.round=r;StartRound(branch);
     while(branch.cursor<branch.orderCount) {Action a{};a.kind=MOVE;a.steps=1;a.step[0]=E;Act(branch,a);}
     EndRound(branch);
   }
   sink+=branch.dragon[k%n].head;
 }
 double secs=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
 printf("dragons=%d rollouts=%d seconds=%.6f rounds_per_second=%.3f dragon_turns_per_second=%.3f game_bytes=%zu map_bytes=%zu checksum=%llu\n",n,reps,secs,reps*3.0/secs,reps*3.0*n/secs,sizeof(Game),sizeof(Map),sink);
}
