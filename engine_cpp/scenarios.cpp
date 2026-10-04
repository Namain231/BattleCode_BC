#ifdef NDEBUG
#undef NDEBUG
#endif
#include "host.cc"
#include <cassert>
#include <type_traits>
using namespace loong;
static_assert(std::is_trivially_copyable<Game>::value,"branch must be a plain value copy");
static void init(Game& g,Map& m,char const* text) {g={};m={};assert(LoadMap(g,m,text).empty());Begin(g,9);}
static Action move(char const* dirs) {Action a{};a.kind=MOVE;a.steps=strlen(dirs);for(int i=0;i<a.steps;++i)a.step[i]=strchr("NESW",dirs[i])-"NESW";return a;}
int main() {
 Game g{};Map m{};
 char const* base="MAP 12 12\nDRAGON 0 4 3 3 2 3 1 3 0 3\nDRAGON 1 4 8 8 9 8 10 8 11 8\n";
 init(g,m,base);auto original=g;StartRound(g);Act(g,move("EEE"));assert(g.dragon[0].alive && g.dragon[0].length==2 && g.dragon[0].head==42);assert(original.dragon[0].head==39);
 init(g,m,base);StartRound(g);Act(g,move("EEEE"));assert(!g.dragon[0].alive && g.dragon[0].death==NO_ACTION && g.pearl[42]);
 init(g,m,"MAP 12 12\nDRAGON 0 5 4 3 3 3 2 3 1 3 0 3\nDRAGON 1 2 8 8 9 8\n");StartRound(g);Act(g,move("EE"));assert(g.dragon[0].length==5);
 init(g,m,base);g.pearl[40]=1;StartRound(g);Act(g,move("EE"));assert(g.dragon[0].length==4);
 init(g,m,"MAP 12 12\nDRAGON 0 4 3 3 3 4 2 4 2 3\nDRAGON 1 2 8 8 9 8\n");StartRound(g);Act(g,move("W"));assert(g.dragon[0].death==SELF);
 init(g,m,"MAP 12 12\nDRAGON 0 2 3 3 2 3\nDRAGON 1 2 4 3 5 3\n");StartRound(g);auto out=Act(g,move("E"));assert(out.deaths[HEAD_ON]==2);
 init(g,m,base);StartRound(g);Action split{};split.kind=SPLIT;split.split=2;Act(g,split);assert(g.orderCount==3 && g.order[2].id==2);Act(g,move("W"));Act(g,move("W"));assert(g.dragon[2].head==47);
 init(g,m,base);g.round=499;g.dragon[0].length=3;g.dragon[1].length=4;EndRound(g);assert(g.winner==1);g.dragon[0].length=4;g.over=0;EndRound(g);assert(g.winner==2);
 init(g,m,base);Kill(g,0,NO_ACTION,nullptr);g.dragon[0].id=2;g.dragon[0].alive=1;g.dragon[0].length=30;g.alive[0]=1;g.round=499;EndRound(g);assert(g.winner==1);
 // Higher ID receives sonar this round. Opposite sonar originates at tail.
 init(g,m,"MAP 12 12\nDRAGON 0 2 3 3 2 3\nDRAGON 1 2 7 3 8 3\n");StartRound(g);auto a=move("E");a.sonarMask=1<<E;a.sonar[E]=123;Act(g,a);assert(g.dragon[1].inboxCount==1 && g.dragon[1].inbox[0]==123 && g.dragon[0].echoes[ENEMY_HEAD]==1);Act(g,move("E"));assert(g.dragon[1].inboxCount==0);
 init(g,m,"MAP 12 12\nDRAGON 0 2 3 3 2 3\nDRAGON 1 2 0 3 1 3\n");StartRound(g);a=move("E");a.sonarMask=1<<W;a.sonar[W]=456;Act(g,a);assert(g.dragon[1].inboxCount==1 && g.dragon[0].echoes[ENEMY]==1);
 init(g,m,"MAP 12 12\nDRAGON 0 4 3 3 2 3 1 3 0 3\nDRAGON 1 4 8 8 9 8 10 8 11 8\nTILE 6 6 1 3\n");auto x=g,y=g;StartRound(x);StartRound(y);assert(memcmp(&x,&y,sizeof(Game))==0);
 puts("12 crafted scenario groups passed; branch independence, free quota, payment, growth, self/head collision, child turn, queen/ties/dead-slot identity, sonar delivery/tail ray, seeded branch reproducibility");
}
