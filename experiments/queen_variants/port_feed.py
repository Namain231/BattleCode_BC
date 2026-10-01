import sys,shutil
name,sink,feedFrom,endFeed,gossip=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5])
dst=f"viper_s2_{name}"
shutil.rmtree(dst,ignore_errors=True); shutil.copytree("baselines/y7_12_49",dst)
p=dst+"/main.cpp"; s=open(p,encoding='utf-8').read()
def rep(a,b):
    global s
    assert s.count(a)==1,a
    s=s.replace(a,b)
rep("    int feedFrom = 350;",f"    int qSinkFrom = {sink};  // QFEED: from here the sink the drones feed is our true queen while she lives\n    int feedFrom = {feedFrom};")
rep("    int endFeedFrom = 440;",f"    int endFeedFrom = {endFeed};")
rep("    int gossipFrom = 300;",f"    int gossipFrom = {gossip};")
rep("""static void considerQueen(const QueenInfo& q) {
    if (q.cell < 0) return;
    bool stale = ROUND - queen.round > 40;
""","""static int ourQid = -1;  // QFEED: which of ids 0/1 is our true queen (-1 = not known yet)
static void considerQueen(const QueenInfo& q) {
    if (q.cell < 0) return;
    bool stale = ROUND - queen.round > 40;
    if (ourQid >= 0 && ROUND >= P.qSinkFrom) {  // QFEED
        if (q.id == ourQid) { if (queen.id != ourQid || q.round >= queen.round) queen = q; return; }
        if (queen.id == ourQid && !stale) return;
    }
""")
rep("static void updateQueen() {\n","""static void updateQueen() {
    if (isTrueQueen()) ourQid = MY_ID;  // QFEED
    for (auto& dr : others) if (dr.team == MY_TEAM && isQueenId(dr.id)) ourQid = dr.id;
    if (ourQid < 0 && KM && KM->n_spawn > 0) ourQid = KM->spawns[0] == MY_TEAM ? 0 : 1;
""")
open(p,'w',encoding='utf-8').write(s)
