import sys,shutil,os
name,leash,greed,nosplit=sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),int(sys.argv[4])
dst=f"viper_s2_{name}"
shutil.rmtree(dst,ignore_errors=True); shutil.copytree("baselines/y7_12_49",dst)
p=dst+"/main.cpp"; s=open(p,encoding='utf-8').read()
def rep(a,b):
    global s
    assert s.count(a)==1,a
    s=s.replace(a,b)
rep("    int mineUntil = 300;\n",f"    int mineUntil = 300;\n    // QLEASH: after budding the true queen stays near home and forages little\n    int qSplitUntil = 30; int qLeash = {leash}; double qLeashW = 1.0; double qGreed = {greed};\n")
rep("static inline bool isTrueQueen() { return MY_ID <= 1; }","static int homeCell = -1;\nstatic inline bool isTrueQueen() { return MY_ID <= 1; }")
rep("    double greed = endgame() ? 0.35 : 1.0;\n","    double greed = endgame() ? 0.35 : 1.0;\n    if (isTrueQueen() && ROUND >= P.qSplitUntil) greed *= P.qGreed;  // QLEASH\n")
rep("    score -= danger;\n","    score -= danger;\n    if (isTrueQueen() && homeCell >= 0 && ROUND >= P.qSplitUntil) { int hd = torusDist(head, homeCell); if (hd > P.qLeash) score -= P.qLeashW * (hd - P.qLeash); }  // QLEASH\n")
rep("    if (ROUND == 0 && MY_ID == 0) nnSelfTest();\n","    if (isTrueQueen() && homeCell < 0 && !body.empty()) homeCell = body[0];  // QLEASH\n    if (ROUND == 0 && MY_ID == 0) nnSelfTest();\n")
if nosplit:
    rep("static bool protectedQueen() {","static bool qNoSplit() { return isTrueQueen() && ROUND >= P.qSplitUntil; }  // QLEASH\nstatic bool protectedQueen() {")
    rep("MY_LEN >= 8 && !protectedQueen() && opts[0].ev.danger","MY_LEN >= 8 && !protectedQueen() && !qNoSplit() && opts[0].ev.danger")
    rep("if (!protectedQueen() && (opts[0].ev.pDeath < 0.5","if (!protectedQueen() && !qNoSplit() && (opts[0].ev.pDeath < 0.5")
    rep("if (!protectedQueen() && (opts[0].ev.pDeath == 0","if (!protectedQueen() && !qNoSplit() && (opts[0].ev.pDeath == 0")
open(p,'w',encoding='utf-8').write(s)
