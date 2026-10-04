// Host-only parity bridge. Not linked into a bot.
#include "host.cc"
#include <map>
struct Check { LoongPort* port; std::map<int,int> deaths; };
extern "C" {
void* check_create(char const* text) {
 char error[512]{}; auto* p=loong_port_create(text,strlen(text),1,error,sizeof(error));
 if(!p) { fprintf(stderr,"%s\n",error); return nullptr; }
 return new Check{p,{}};
}
void check_destroy(void* ptr) { auto* c=(Check*)ptr; loong_port_destroy(c->port); delete c; }
int check_seeded_initial(void* ptr,int const* cd) {
 auto& g=((Check*)ptr)->port->game;int mismatches=0;
 for(int i=0;i<g.map->width*g.map->height;++i) mismatches+=g.countdown[i]!=cd[i];
 return mismatches;
}
void check_init(void* ptr,int const* cd) {
 auto& g=((Check*)ptr)->port->game;
 for(int i=0;i<g.map->width*g.map->height;++i) g.countdown[i]=cd[i];
}
void check_round(void* ptr,int round,int const* cd,int const* pearls,int n) {
 auto& g=((Check*)ptr)->port->game; g.round=round;
 int cells=g.map->width*g.map->height;
 for(int i=0;i<cells;++i) {
   int mirror=loong::MirrorTile(g,i);
   if(mirror<i || !g.map->spawns[i]) continue;
   loong::SetCountdown(g,i,mirror,g.countdown[i]-1);
 }
 for(int i=0;i<cells;++i) if(cd[i]!=-2147483647) g.countdown[i]=cd[i];
 for(int i=0;i<n;++i) g.pearl[pearls[i]]=1;
 loong::StartRound(g,false);
}
void check_seeded_round(void* ptr,int round) {
 auto& g=((Check*)ptr)->port->game;g.round=round;loong::StartRound(g);
}
int check_next(void* ptr) {
 auto& g=((Check*)ptr)->port->game;
 while(g.cursor<g.orderCount) {
   auto t=g.order[g.cursor];
   if(g.dragon[t.slot].alive && g.dragon[t.slot].id==t.id) return t.id;
   ++g.cursor;
 }
 return -1;
}
void check_act(void* ptr,int kind,int size,char const* dirs) {
 auto* c=(Check*)ptr; auto& g=c->port->game;
 loong::Action a{}; a.kind=kind; a.split=size;
 a.steps=(uint16_t)strlen(dirs);
 for(int i=0;i<a.steps && i<loong::MAX_STEPS;++i) {
   char const* p=strchr("NESW",dirs[i]); a.step[i]=p?(uint8_t)(p-"NESW"):255;
 }
 loong::Act(g,a);
 for(auto const& d:g.dragon) if(!d.alive && d.length>0) c->deaths[d.id]=d.death;
}
int check_dump(void* ptr,int* out) {
 auto* c=(Check*)ptr; auto& g=c->port->game; loong::EndRound(g);
 int n=0; out[n++]=g.round; out[n++]=g.over; out[n++]=g.winner; out[n++]=g.overflow;
 out[n++]=g.alive[0]+g.alive[1];
 for(auto const& d:g.dragon) if(d.alive) {
   out[n++]=d.id; out[n++]=d.team; out[n++]=d.facing; out[n++]=d.length;
   for(int cell=d.head;cell>=0;cell=g.towardTail[cell]) out[n++]=cell;
 }
 out[n++]=(int)c->deaths.size(); for(auto [id,reason]:c->deaths) {out[n++]=id;out[n++]=reason;}
 int cells=g.map->width*g.map->height;
 for(int i=0;i<cells;++i) out[n++]=g.pearl[i];
 for(int i=0;i<cells;++i) out[n++]=g.countdown[i];
 return n;
}
}
