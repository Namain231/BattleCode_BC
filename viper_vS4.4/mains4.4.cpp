// Viper S4.4 (Disciplined Churn)
//
// 1. Disciplined Kamikaze: Miners apply a 70% discount to pocket/corridor risks
//    instead of complete exemption, and strictly obey HARD_HORIZON_PRUNING and
//    TUNNEL_COLLISION_AVOIDANCE to avoid un-splittable dead ends and guaranteed
//    head-to-head corridor deaths (fixing Dilemma & Schooltime regressions).
// 2. Smooth Phase-Out: Brawler and Kamikaze logic scales down smoothly between
//    rounds 300 and 350, eliminating the Round 300 panic-suicide cliff.
// 3. Dynamic Hysteresis: Goal lock-on is aggressive (0.45) for early miners but
//    relaxes to 0.70 on crowded map states (crampFraction > 0.05) to prevent
//    relentless pathing into late-game traffic jams.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unordered_map>
#include <vector>

#include "maps_data.hpp"

using namespace std;

// ------------------------------------------------------------- Features ---
#define FEATURE_INTENT_MEMORY 1
#define FEATURE_CHOKE_RESERVATION 1
#define FEATURE_HARD_HORIZON_PRUNING 1
#define FEATURE_TUNNEL_COLLISION_AVOIDANCE 1
#define FEATURE_ADAPTIVE_CORRIDOR_DFS 1
#define FEATURE_POCKET_DFS_ORDERING 1
#define FEATURE_DFS_BEST_FIRST 1
#define FEATURE_BRANCH_SIZE 1
#define FEATURE_TERRITORY 1

struct Params {
  double gamma = 0.86;
  double wField = 0.22;
  double wTarget = 1.6;
  double decayTau = 70.0;
  int fieldCap = 90;
  double enemyCloser = 0.55, enemyTie = 0.8, friendCloser = 0.08;
  double p1 = 0.85, p2 = 0.15, p3 = 0.03, p2Drone = 0.40, p3Drone = 0.10;
  double deathExtra = 30.0;
  double spaceBonus = 0.6;
  double wPocket = 1.5;
  int attackMargin = 2;
  int attackMaxSteps = 4;
  double wProgress = 0.8;
  int budAt = 4;
  int mineUntil = 300;
  double minerGamma = 0.80;
  double minerFarmCap = 1.5;
  int budUntil = 300;
  int feedFrom = 350;
  int endFeedFrom = 440;
  int feedRadius = 10;
  int protectFrom = 400;
  int gossipFrom = 300;
  int huntMaxLen = 5;
  double wHunt = 2.2;
  int splitMinLen = 24;
  int splitChild = 6;
  int splitRoundMax = 300;
  int endgameRounds = 25;
};
static Params P;

// ------------------------------------------------------------------- basics --

static const int MAXN = 64 * 64;
static const int DX[4] = {0, 1, 0, -1};
static const int DY[4] = {-1, 0, 1, 0};
static const char DCH[4] = {'N', 'E', 'S', 'W'};
static inline int opp(int d) { return d ^ 2; }

static int W, H, N, MY_ID, UNIT_LIMIT, MY_TEAM;
static int ROUND, MY_DIR, MY_LEN, UNITS;
static int ECHO[5];

static inline int stepRaw(int c, int d) {
  int x = c % W + DX[d], y = c / W + DY[d];
  if (x < 0)
    x += W;
  else if (x >= W)
    x -= W;
  if (y < 0)
    y += H;
  else if (y >= H)
    y -= H;
  return y * W + x;
}
static inline int torusDist(int a, int b) {
  int dx = abs(a % W - b % W);
  int dy2 = abs(a / W - b / W);
  return min(dx, W - dx) + min(dy2, H - dy2);
}

static chrono::steady_clock::time_point T0;
static double elapsedMs() {
  return chrono::duration<double, milli>(chrono::steady_clock::now() - T0)
      .count();
}

// -------------------------------------------------------------------- input --

static char buf[1 << 16];
static bool nextLine() {
  while (fgets(buf, sizeof buf, stdin)) {
    char *p = buf;
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n')
      p++;
    if (*p)
      return true;
  }
  return false;
}
static char *skipWord(char *p) {
  while (*p == ' ' || *p == '\t')
    p++;
  while (*p && *p != ' ' && *p != '\t' && *p != '\n' && *p != '\r')
    p++;
  return p;
}
static long long labelled() { return strtoll(skipWord(buf), nullptr, 10); }
static int dirOf(char c) {
  return c == 'N' ? 0 : c == 'E' ? 1 : c == 'S' ? 2 : 3;
}

struct Part {
  int team, id, cell, face;
  bool head;
};

struct View {
  int cell[49];
  bool pearl[49];
  int ptime[49];
  vector<Part> parts;
  int ek[49][4];
  int ep[49][4];
  vector<uint64_t> msgs;
};
static View V;
static int viewIndex[MAXN];

static void parseEdgeTok(char *&p, int &kind, int &pid) {
  while (*p == ' ' || *p == '\t')
    p++;
  if (*p == '.') {
    kind = 1;
    pid = -1;
    p++;
  } else if (*p == 'w') {
    kind = 2;
    pid = -1;
    p++;
  } else {
    kind = 3;
    pid = (int)strtol(p, &p, 10);
  }
}

static bool readTurn() {
  if (!nextLine())
    return false;
  if (strncmp(buf, "ENDGAME", 7) == 0)
    return false;
  ROUND = (int)labelled();
  nextLine();
  {
    char *p = skipWord(buf);
    while (*p == ' ')
      p++;
    MY_DIR = dirOf(*p);
  }
  nextLine();
  MY_LEN = (int)labelled();
  nextLine();
  UNITS = (int)labelled();
  nextLine();
  int nm = (int)labelled();
  V.msgs.clear();
  for (int i = 0; i < nm; i++) {
    nextLine();
    V.msgs.push_back(strtoull(buf, nullptr, 10));
  }
  nextLine();
  for (int k = 0; k < 5; k++)
    ECHO[k] = 0;
  if (strncmp(buf, "ECHOES", 6) == 0) {
    char *p = skipWord(buf);
    for (int k = 0; k < 5; k++)
      ECHO[k] = (int)strtol(p, &p, 10);
    nextLine();
  }
  for (int i = 0; i < 49; i++) {
    if (i)
      nextLine();
    char *p = buf;
    int x = (int)strtol(p, &p, 10), y = (int)strtol(p, &p, 10);
    int hp = (int)strtol(p, &p, 10), pt = (int)strtol(p, &p, 10);
    V.cell[i] = y * W + x;
    V.pearl[i] = hp == 1;
    V.ptime[i] = pt;
  }
  nextLine();
  int nb = (int)labelled();
  V.parts.clear();
  for (int i = 0; i < nb; i++) {
    nextLine();
    char *p = buf;
    while (*p == ' ')
      p++;
    Part q;
    q.team = (*p == 'A') ? 0 : 1;
    p++;
    q.id = (int)strtol(p, &p, 10);
    int x = (int)strtol(p, &p, 10), y = (int)strtol(p, &p, 10);
    while (*p == ' ')
      p++;
    q.face = dirOf(*p);
    p++;
    q.head = strtol(p, &p, 10) == 1;
    q.cell = y * W + x;
    V.parts.push_back(q);
  }
  for (int y = 0; y < 8; y++) {
    nextLine();
    char *p = buf;
    for (int x = 0; x < 7; x++) {
      int k, pid;
      parseEdgeTok(p, k, pid);
      if (y < 7) {
        V.ek[y * 7 + x][0] = k;
        V.ep[y * 7 + x][0] = pid;
      }
      if (y > 0) {
        V.ek[(y - 1) * 7 + x][2] = k;
        V.ep[(y - 1) * 7 + x][2] = pid;
      }
    }
  }
  for (int y = 0; y < 7; y++) {
    nextLine();
    char *p = buf;
    for (int x = 0; x < 8; x++) {
      int k, pid;
      parseEdgeTok(p, k, pid);
      if (x < 7) {
        V.ek[y * 7 + x][3] = k;
        V.ep[y * 7 + x][3] = pid;
      }
      if (x > 0) {
        V.ek[y * 7 + x - 1][1] = k;
        V.ep[y * 7 + x - 1][1] = pid;
      }
    }
  }
  return true;
}

// ---------------------------------------------------------------- knowledge --

static int8_t obsK[MAXN * 4];
static int obsP[MAXN * 4];
static const KnownMap *KM = nullptr;
static vector<int8_t> mapK;
static vector<int> mapP;
static int SYM = -1;
static int nbr[MAXN * 4];
static bool nbrDirty = true;
static int chokeReserved[MAXN];
static vector<int> committedPath;

static double crampFraction = 0.0;
static bool topoValid = false;
static int8_t pocketDepth[MAXN];
static int branchSize[MAXN];
static int dsuP[MAXN], dsuS[MAXN];

static int dsuFind(int x) {
  while (dsuP[x] != x) {
    dsuP[x] = dsuP[dsuP[x]];
    x = dsuP[x];
  }
  return x;
}
static void dsuUnite(int a, int b) {
  a = dsuFind(a);
  b = dsuFind(b);
  if (a == b)
    return;
  if (dsuS[a] < dsuS[b])
    swap(a, b);
  dsuP[b] = a;
  dsuS[a] += dsuS[b];
}

static void computeTopology() {
  if (N <= 0 || N > MAXN) {
    topoValid = false;
    return;
  }
  static int workDeg[MAXN];
  for (int c = 0; c < N; c++) {
    int d = 0;
    for (int dir = 0; dir < 4; dir++)
      if (nbr[c * 4 + dir] >= 0)
        d++;
    workDeg[c] = d;
    pocketDepth[c] = -1;
    branchSize[c] = 0;
    dsuP[c] = c;
    dsuS[c] = 1;
  }
  static int q[MAXN];
  int qh = 0, qt = 0;
  for (int c = 0; c < N; c++)
    if (workDeg[c] <= 1) {
      pocketDepth[c] = 0;
      q[qt++] = c;
    }
  while (qh < qt) {
    int c = q[qh++];
    for (int dir = 0; dir < 4; dir++) {
      int n = nbr[c * 4 + dir];
      if (n < 0 || pocketDepth[n] >= 0 || workDeg[n] <= 0)
        continue;
      if (--workDeg[n] <= 1) {
        pocketDepth[n] = pocketDepth[c] + 1;
#if FEATURE_BRANCH_SIZE
        dsuUnite(c, n);
#endif
        q[qt++] = n;
      }
    }
  }
  int branch = 0;
  for (int c = 0; c < N; c++)
    if (pocketDepth[c] >= 0) {
      branch++;
#if FEATURE_BRANCH_SIZE
      branchSize[c] = dsuS[dsuFind(c)];
#endif
    }
  crampFraction = (double)branch / N;
  topoValid = true;
}

struct Candidate {
  int idx;
  vector<int8_t> k;
  vector<int> p;
};
static vector<Candidate> mapCands;
static bool mapResolved = false;

static void loadMapLayer(const KnownMap &m, vector<int8_t> &k, vector<int> &p) {
  k.assign(N * 4, 1);
  p.assign(N * 4, -1);
  for (int i = 0; i < m.n_edges; i++) {
    int c = m.edges[4 * i], d = m.edges[4 * i + 1], kind = m.edges[4 * i + 2],
        pid = m.edges[4 * i + 3];
    int kk = kind == 1 ? 2 : 3;
    int o = stepRaw(c, d);
    k[c * 4 + d] = kk;
    p[c * 4 + d] = pid;
    k[o * 4 + opp(d)] = kk;
    p[o * 4 + opp(d)] = pid;
  }
}

static inline int effK(int c, int d) {
  if (obsK[c * 4 + d])
    return obsK[c * 4 + d];
  if (KM)
    return mapK[c * 4 + d];
  return 0;
}
static inline int effP(int c, int d) {
  if (obsK[c * 4 + d])
    return obsP[c * 4 + d];
  if (KM)
    return mapP[c * 4 + d];
  return -1;
}

static void rebuildNbr() {
  unordered_map<int, vector<int>> portals;
  for (int c = 0; c < N; c++) {
    for (int d = 0; d < 4; d++) {
      int k = effK(c, d);
      if (k == 2)
        nbr[c * 4 + d] = -1;
      else if (k == 3) {
        nbr[c * 4 + d] = -1;
        int code = (d == 1 || d == 2) ? c * 4 + d : stepRaw(c, d) * 4 + opp(d);
        auto &v = portals[effP(c, d)];
        if (find(v.begin(), v.end(), code) == v.end())
          v.push_back(code);
      } else
        nbr[c * 4 + d] = stepRaw(c, d);
    }
  }
  for (auto &kv : portals) {
    if (kv.second.size() != 2)
      continue;
    int a1 = kv.second[0] / 4, d1 = kv.second[0] % 4;
    int a2 = kv.second[1] / 4, d2 = kv.second[1] % 4;
    if (d1 != d2)
      continue;
    int b1 = stepRaw(a1, d1), b2 = stepRaw(a2, d1);
    nbr[a1 * 4 + d1] = b2;
    nbr[b1 * 4 + opp(d1)] = a2;
    nbr[a2 * 4 + d1] = b1;
    nbr[b2 * 4 + opp(d1)] = a1;
  }
  nbrDirty = false;
  computeTopology();
}

static int seenR[MAXN], spawnAt[MAXN], mirSpawn[MAXN], gmin[MAXN], gmax[MAXN],
    memExpire[MAXN], radarExpire[MAXN];
static bool pearlSeen[MAXN];
static int maxEnemyId = -1;
static bool swarm = false;
static vector<int> lastRay;

static int mirrorCell(int c) {
  int x = c % W, y = c / W;
  if (SYM == 0)
    x = W - 1 - x;
  else if (SYM == 1)
    y = H - 1 - y;
  else {
    x = W - 1 - x;
    y = H - 1 - y;
  }
  return y * W + x;
}

static void detectSymmetry() {
  SYM = -1;
  for (int s = 0; s < 3 && SYM < 0; s++) {
    SYM = s;
    bool ok = true;
    for (int c = 0; c < N && ok; c++) {
      int m = mirrorCell(c);
      if (KM->gaps[2 * c] != KM->gaps[2 * m] ||
          KM->gaps[2 * c + 1] != KM->gaps[2 * m + 1])
        ok = false;
    }
    if (!ok)
      SYM = -1;
  }
}

static bool bigFeed = false;
static void applyOpenness() {
  if (!topoValid)
    return;
  if (KM) {
    string nm = KM->name;
    if (nm == "portals" || nm == "slithery_fight" || nm == "schooltime") {
      bigFeed = true;
      P.budUntil = 330;
      return;
    }
  }
  bigFeed = crampFraction < 0.05;
  if (bigFeed)
    P.budUntil = 330;
  else
    P.protectFrom = 340;
}
static void activateMap(int idx, vector<int8_t> &&k, vector<int> &&p) {
  KM = &KNOWN_MAPS[idx];
  mapK = std::move(k);
  mapP = std::move(p);
  for (int c = 0; c < N; c++) {
    gmin[c] = KM->gaps[2 * c];
    gmax[c] = KM->gaps[2 * c + 1];
  }
  detectSymmetry();
  nbrDirty = true;
}
static void dropMap() {
  KM = nullptr;
  SYM = -1;
  for (int c = 0; c < N; c++)
    gmin[c] = gmax[c] = -1;
  nbrDirty = true;
}

static bool viewAgrees(const vector<int8_t> &k, const vector<int> &p,
                       const uint16_t *gaps) {
  for (int i = 0; i < 49; i++) {
    int c = V.cell[i];
    for (int d = 0; d < 4; d++) {
      int vk = V.ek[i][d];
      if (k[c * 4 + d] != vk)
        return false;
      if (vk == 3 && p[c * 4 + d] != V.ep[i][d])
        return false;
    }
    int hi = gaps[2 * c + 1];
    if ((V.ptime[i] < 0) != (hi == 0))
      return false;
    if (V.ptime[i] > hi && hi > 0)
      return false;
  }
  return true;
}

static void initKnowledge() {
  N = W * H;
  memset(obsK, 0, sizeof obsK);
  for (int c = 0; c < N; c++) {
    seenR[c] = -1;
    pearlSeen[c] = false;
    spawnAt[c] = -2;
    mirSpawn[c] = -2;
    memExpire[c] = 0;
    radarExpire[c] = 0;
    gmin[c] = gmax[c] = -1;
    chokeReserved[c] = 0;
  }
  for (int i = 0; i < N_KNOWN_MAPS; i++) {
    if (KNOWN_MAPS[i].w != W || KNOWN_MAPS[i].h != H)
      continue;
    Candidate cd;
    cd.idx = i;
    loadMapLayer(KNOWN_MAPS[i], cd.k, cd.p);
    mapCands.push_back(std::move(cd));
  }
  if (mapCands.empty())
    mapResolved = true;
}

static void absorbView() {
  for (int c = 0; c < N; c++)
    viewIndex[c] = -1;
  for (int i = 0; i < 49; i++)
    viewIndex[V.cell[i]] = i;

  if (!mapResolved) {
    vector<Candidate> keep;
    for (auto &cd : mapCands)
      if (viewAgrees(cd.k, cd.p, KNOWN_MAPS[cd.idx].gaps))
        keep.push_back(std::move(cd));
    mapCands = std::move(keep);
    if (mapCands.size() == 1) {
      mapResolved = true;
      activateMap(mapCands[0].idx, std::move(mapCands[0].k),
                  std::move(mapCands[0].p));
      mapCands.clear();
    } else if (mapCands.empty())
      mapResolved = true;
  } else if (KM) {
    if (!viewAgrees(mapK, mapP, KM->gaps))
      dropMap();
  }

  for (int i = 0; i < 49; i++) {
    int c = V.cell[i];
    for (int d = 0; d < 4; d++) {
      if (obsK[c * 4 + d] != V.ek[i][d] || obsP[c * 4 + d] != V.ep[i][d]) {
        obsK[c * 4 + d] = (int8_t)V.ek[i][d];
        obsP[c * 4 + d] = V.ep[i][d];
        int o = stepRaw(c, d);
        obsK[o * 4 + opp(d)] = (int8_t)V.ek[i][d];
        obsP[o * 4 + opp(d)] = V.ep[i][d];
        nbrDirty = true;
      }
    }
    seenR[c] = ROUND;
    pearlSeen[c] = V.pearl[i];
    spawnAt[c] = V.ptime[i] < 0 ? -1 : ROUND + V.ptime[i];
    if (V.ptime[i] < 0 && gmax[c] < 0) {
      gmax[c] = 0;
      gmin[c] = 0;
    }
  }
  if (KM && SYM >= 0) {
    for (int i = 0; i < 49; i++) {
      int m = mirrorCell(V.cell[i]);
      if (viewIndex[m] < 0 && V.ptime[i] >= 0)
        mirSpawn[m] = ROUND + V.ptime[i];
    }
  }
  if (nbrDirty) {
    rebuildNbr();
    applyOpenness();
  }
}

static double pearlProb(int c, int T) {
  int now = ROUND;
  if (seenR[c] == now) {
    if (pearlSeen[c])
      return 1.0;
    int sa = spawnAt[c];
    if (sa < 0)
      return 0.0;
    if (sa <= T)
      return 0.9;
    if (sa - T <= 2)
      return 0.25;
    return 0.0;
  }
  double p = 0.0;
  if (seenR[c] >= 0) {
    int age = now - seenR[c];
    if (pearlSeen[c])
      p = exp(-age / P.decayTau);
    int sa = spawnAt[c];
    if (sa == -1 && !pearlSeen[c])
      return 0.0;
    if (sa >= 0 && sa <= T) {
      double q = 0.85 * exp(-max(0, now - sa) / P.decayTau);
      p = max(p, q);
      if (gmax[c] > 0) {
        double mean = 0.5 * (gmin[c] + gmax[c]);
        double r = 1.0 - exp(-(T - sa) / max(1.0, mean));
        p = max(p, 0.6 * r * exp(-mean / (2 * P.decayTau)));
      }
    }
    return p;
  }
  int sa = mirSpawn[c];
  if (gmax[c] == 0)
    return 0.0;
  if (sa >= 0)
    return sa <= T ? 0.7 * exp(-max(0, now - sa) / P.decayTau) : 0.0;
  if (gmax[c] > 0) {
    double lo = gmin[c], hi = gmax[c];
    double f = (T + 1 - lo + 1) / (hi - lo + 1);
    return 0.6 * max(0.0, min(1.0, f));
  }
  return min(0.22, 0.04 + T / 1500.0);
}

static inline double farmBonus(int c) {
  if (gmax[c] <= 0)
    return 1.0;
  double mean = 0.5 * (gmin[c] + gmax[c]);
  return 1.0 + min(2.0, 8.0 / max(1.0, mean));
}

// ------------------------------------------------------------ dragons state --

struct Dragon {
  int id, team, headCell = -1, headFace = 0, visCount = 0;
  bool tailKnown = false;
  int estLen = 0;
};
static vector<Dragon> others;
static int enemyBT[MAXN], allyBT[MAXN];
static int occId[MAXN], zoneE[MAXN], zoneF[MAXN], enemyDist[MAXN],
    friendDist[MAXN], friendMinId[MAXN];
static bool occHead[MAXN];
static const int UNKNOWN_EXTRA = 10;
static vector<int> body, lastPath;
static bool havePrev = false;
static int partAt[MAXN], ownLost[MAXN], eatMargin[256];

struct QueenInfo {
  int cell = -1, len = 0, round = -1000, id = -1;
};
static QueenInfo queen;

struct ClaimedFountain {
  int distSender, sx, sy, round;
};
static unordered_map<int, ClaimedFountain> claimedFountains;

static void considerQueen(const QueenInfo &q) {
  if (q.cell < 0)
    return;
  bool stale = ROUND - queen.round > 40;
  if (q.id == queen.id) {
    if (q.round >= queen.round)
      queen = q;
    return;
  }
  if (stale || q.len > queen.len || (q.len == queen.len && q.id < queen.id))
    queen = q;
}

static void updateQueen() {
  QueenInfo me;
  me.cell = body[0];
  me.len = MY_LEN;
  me.round = ROUND;
  me.id = MY_ID;
  considerQueen(me);
  for (auto &dr : others)
    if (dr.team == MY_TEAM && dr.headCell >= 0) {
      QueenInfo f;
      f.cell = dr.headCell;
      f.len = dr.estLen;
      f.round = ROUND;
      f.id = dr.id;
      considerQueen(f);
    }
  if (ROUND - queen.round > 40)
    queen = me;
}

static bool iAmQueen() { return queen.id == MY_ID; }
static bool protectedQueen() {
  return !bigFeed && ROUND >= P.protectFrom &&
         (queen.id == MY_ID || MY_LEN >= queen.len) &&
         MY_LEN >= (ROUND >= 400 ? 6 : 4);
}

enum MsgType {
  MSG_INTENT = 0,
  MSG_FOUNTAIN = 1,
  MSG_GIANT = 2,
  MSG_QUEEN = 3,
  MSG_CHOKE = 4
};
struct MsgData {
  MsgType type;
  int sx, sy, p1, p2, round;
};

static uint64_t packMsg(MsgType type, int sx, int sy, int p1, int p2,
                        int round) {
  uint64_t h = 0xB0DULL;
  return (h << 52) | (((uint64_t)type & 15ULL) << 48) |
         (((uint64_t)sx & 63ULL) << 42) | (((uint64_t)sy & 63ULL) << 36) |
         (((uint64_t)p1 & 4095ULL) << 24) | (((uint64_t)p2 & 4095ULL) << 12) |
         (((uint64_t)round & 4095ULL));
}

static bool unpackMsg(uint64_t v, MsgData &m) {
  uint64_t h = (v >> 52) & 4095ULL;
  if (h != 0xB0DULL)
    return false;
  m.type = (MsgType)((v >> 48) & 15ULL);
  m.sx = (int)((v >> 42) & 63ULL);
  m.sy = (int)((v >> 36) & 63ULL);
  m.p1 = (int)((v >> 24) & 4095ULL);
  m.p2 = (int)((v >> 12) & 4095ULL);
  m.round = (int)(v & 4095ULL);
  if (m.round > ROUND || (ROUND - m.round > 10 && ROUND >= m.round))
    return false;
  if (m.sx >= W || m.sy >= H)
    return false;
  return true;
}

static int maxSeenEnemyLen = 0, giantThreatCell = -1, giantThreatLen = 0,
           giantThreatRound = -1;
static int myNextHead = -1, myIntentPath = 0;

static void buildDragons() {
  const auto &parts = V.parts;
  int np = (int)parts.size();
  for (int i = 0; i < 49; i++)
    partAt[V.cell[i]] = -1;
  for (int c = 0; c < N; c++) {
    enemyBT[c] = 0;
    allyBT[c] = 0;
    occId[c] = 0;
    occHead[c] = false;
    zoneE[c] = 0;
    zoneF[c] = 0;
  }
  for (int i = 0; i < np; i++) {
    partAt[parts[i].cell] = i;
    occId[parts[i].cell] = parts[i].id + 1;
    occHead[parts[i].cell] = parts[i].head;
  }
  vector<int> nxt(np, -1), prv(np, -1);
  for (int i = 0; i < np; i++) {
    if (parts[i].head)
      continue;
    int to = nbr[parts[i].cell * 4 + parts[i].face];
    if (to < 0 || viewIndex[to] < 0)
      continue;
    int j = partAt[to];
    if (j >= 0 && parts[j].id == parts[i].id && prv[j] < 0) {
      nxt[i] = j;
      prv[j] = i;
    }
  }
  auto tailCertain = [&](int t) {
    int c = parts[t].cell;
    for (int d = 0; d < 4; d++) {
      int k = effK(c, d);
      if (k == 2)
        continue;
      if (k == 3)
        return false;
      if (viewIndex[stepRaw(c, d)] < 0)
        return false;
    }
    return true;
  };
  for (int i = 0; i < 256; i++)
    eatMargin[i] = 0;
  for (int i = 0; i < np; i++) {
    if (!parts[i].head)
      continue;
    int cnt = 0;
    for (int j = 0; j < 49; j++)
      if (V.pearl[j] && torusDist(V.cell[j], parts[i].cell) <= 3)
        cnt++;
    eatMargin[parts[i].id % 256] = min(4, cnt);
  }
  vector<int> behind(np, 0);
  vector<char> certain(np, 0);
  for (int i = 0; i < np; i++) {
    if (prv[i] >= 0)
      continue;
    bool cert = tailCertain(i);
    int k = 0, cur = i;
    while (cur >= 0) {
      behind[cur] = k++;
      certain[cur] = cert;
      cur = nxt[cur];
    }
  }
  for (int i = 0; i < 49; i++)
    memExpire[V.cell[i]] = 0;
  for (int c = 0; c < N; c++)
    if (viewIndex[c] < 0 && memExpire[c] > ROUND)
      enemyBT[c] = memExpire[c] - ROUND;

  if (ECHO[3] + ECHO[4] > 0 && !lastRay.empty() && ROUND <= P.gossipFrom) {
    bool explained = false;
    for (int c : lastRay) {
      if (viewIndex[c] < 0)
        break;
      if (occId[c]) {
        explained = true;
        break;
      }
    }
    if (!explained)
      for (int c : lastRay)
        if (viewIndex[c] < 0)
          radarExpire[c] = ROUND + (ECHO[4] ? 8 : 5);
  }

  for (uint64_t v : V.msgs) {
    MsgData m;
    if (unpackMsg(v, m)) {
      if (m.type == MSG_INTENT) {
        if (m.p1 != MY_ID) {
          int c = m.sy * W + m.sx;
          int d0 = m.p2 & 3, d1 = (m.p2 >> 2) & 3, d2 = (m.p2 >> 4) & 3;
          int path[3] = {d0, d1, d2};
          if (c >= 0 && c < N) {
            allyBT[c] = max(allyBT[c], 4);
            memExpire[c] = max(memExpire[c], ROUND + 4);
            for (int hop = 0; hop < 3; hop++) {
              int n = nbr[c * 4 + path[hop]];
              if (n < 0)
                break;
              c = n;
              int bt = 3 - hop;
              allyBT[c] = max(allyBT[c], bt);
              memExpire[c] = max(memExpire[c], ROUND + bt);
            }
          }
        }
      } else if (m.type == MSG_CHOKE && m.p1 != MY_ID) {
        int c = m.sy * W + m.sx;
        if (c >= 0 && c < N)
          chokeReserved[c] = ROUND + m.p2 + 2;
      } else if (m.type == MSG_FOUNTAIN) {
        int targetCell = m.p1, sCell = m.sy * W + m.sx;
        if (targetCell >= 0 && targetCell < N)
          claimedFountains[targetCell] = {torusDist(sCell, targetCell), m.sx,
                                          m.sy, m.round};
      } else if (m.type == MSG_GIANT) {
        if (m.p1 > maxSeenEnemyLen)
          maxSeenEnemyLen = m.p1;
        if (m.p1 >= 10 && m.sy * W + m.sx >= 0 && m.sy * W + m.sx < N) {
          giantThreatCell = m.sy * W + m.sx;
          giantThreatLen = m.p1;
          giantThreatRound = ROUND;
        }
      } else if (m.type == MSG_QUEEN) {
        QueenInfo q;
        q.cell = m.sy * W + m.sx;
        q.len = m.p1;
        q.id = m.p2;
        q.round = m.round;
        considerQueen(q);
      }
    }
  }

  others.clear();
  unordered_map<int, int> idx;
  for (int i = 0; i < np; i++) {
    const Part &q = parts[i];
    if (q.id == MY_ID)
      continue;
    int extra = (q.team == MY_TEAM || certain[i]) ? 0 : UNKNOWN_EXTRA;
    int bt = behind[i] + extra + 1 + eatMargin[q.id % 256];
    if (q.team == MY_TEAM)
      allyBT[q.cell] = max(allyBT[q.cell], bt);
    else
      enemyBT[q.cell] = max(enemyBT[q.cell], bt);
    memExpire[q.cell] = ROUND + bt;
    auto it = idx.find(q.id);
    if (it == idx.end()) {
      idx[q.id] = (int)others.size();
      others.push_back(Dragon{q.id, q.team});
      it = idx.find(q.id);
    }
    Dragon &dr = others[it->second];
    if (q.team != MY_TEAM)
      maxEnemyId = max(maxEnemyId, q.id);
    dr.visCount++;
    if (q.head) {
      dr.headCell = q.cell;
      dr.headFace = q.face;
      dr.tailKnown = certain[i];
      dr.estLen = behind[i] + 1 + (certain[i] ? 0 : 2);
    }
  }
  swarm = maxEnemyId >= 20;
  for (auto &dr : others) {
    if (dr.headCell < 0)
      continue;
    for (int d = 0; d < 4; d++) {
      int n = nbr[dr.headCell * 4 + d];
      if (n < 0)
        continue;
      if (dr.team == MY_TEAM)
        zoneF[n] = 1;
      else
        zoneE[n] = 1;
    }
  }

  int headIdx = -1;
  for (int i = 0; i < np; i++)
    if (parts[i].id == MY_ID && parts[i].head)
      headIdx = i;
  vector<int> chain;
  for (int cur = headIdx; cur >= 0 && (int)chain.size() < MY_LEN;
       cur = prv[cur])
    chain.push_back(parts[cur].cell);

  vector<int> pred;
  if (havePrev) {
    for (int i = (int)lastPath.size() - 1; i >= 0; i--)
      pred.push_back(lastPath[i]);
    for (int c : body)
      pred.push_back(c);
  } else if (KM && ROUND == 0) {
    const int *s = KM->spawns;
    for (int k = 0, pos = 0; k < KM->n_spawn; k++) {
      int team = s[pos], cnt = s[pos + 1];
      if (team == MY_TEAM && !chain.empty() && s[pos + 2] == chain[0])
        for (int j = 0; j < cnt; j++)
          pred.push_back(s[pos + 2 + j]);
      pos += 2 + cnt;
    }
  }
  body = chain;

  if ((int)body.size() < MY_LEN) {
    int offset = -1;
    for (size_t k = 0; k < pred.size(); k++) {
      bool ok = true;
      for (size_t i = 0; i < body.size(); i++) {
        if (k + i >= pred.size() || body[i] != pred[k + i]) {
          ok = false;
          break;
        }
      }
      if (ok) {
        offset = (int)k;
        break;
      }
    }
    if (offset >= 0) {
      for (size_t i = body.size();
           offset + i < pred.size() && (int)body.size() < MY_LEN; i++) {
        body.push_back(pred[offset + i]);
      }
    } else if (!havePrev && !KM && ROUND == 0 && body.size() >= 2) {
      int a = body[body.size() - 2], b = body.back(), dir = -1;
      for (int d = 0; d < 4; d++)
        if (stepRaw(a, d) == b)
          dir = d;
      while (dir >= 0 && (int)body.size() < MY_LEN)
        body.push_back(stepRaw(body.back(), dir));
    }
    while ((int)body.size() < MY_LEN)
      body.push_back(-1);
  }
  if ((int)body.size() > MY_LEN)
    body.resize(MY_LEN);

  for (int i = 0; i < np; i++) {
    if (parts[i].id != MY_ID)
      continue;
    if (find(body.begin(), body.end(), parts[i].cell) == body.end()) {
      ownLost[parts[i].cell] = ROUND + 1;
      enemyBT[parts[i].cell] = max(enemyBT[parts[i].cell], MY_LEN);
    }
  }

  for (int c = 0; c < N; c++) {
    enemyDist[c] = 1 << 20;
    friendDist[c] = 1 << 20;
    friendMinId[c] = 1 << 20;
  }
  static int q[MAXN];
  for (int pass = 0; pass < 2; pass++) {
    int *dist = pass == 0 ? enemyDist : friendDist;
    int qh = 0, qt = 0;
    for (auto &dr : others) {
      if (dr.headCell < 0)
        continue;
      if ((dr.team == MY_TEAM) != (pass == 1))
        continue;
      if (dist[dr.headCell] > 0) {
        dist[dr.headCell] = 0;
        q[qt++] = dr.headCell;
      }
      if (pass == 1)
        friendMinId[dr.headCell] = min(friendMinId[dr.headCell], dr.id);
    }
    while (qh < qt) {
      int c = q[qh++];
      if (dist[c] >= 40)
        continue;
      for (int d = 0; d < 4; d++) {
        int n = nbr[c * 4 + d];
        if (n < 0)
          continue;
        if (dist[n] > dist[c] + 1) {
          dist[n] = dist[c] + 1;
          if (pass == 1)
            friendMinId[n] = friendMinId[c];
          q[qt++] = n;
        } else if (pass == 1 && dist[n] == dist[c] + 1)
          friendMinId[n] = min(friendMinId[n], friendMinId[c]);
      }
    }
  }
}

static inline bool pearlNow(int c) {
  return viewIndex[c] >= 0 && V.pearl[viewIndex[c]];
}

struct SimResult {
  bool dead = false, outside = false;
  int hitHeadId = -1;
  vector<int> body, cells;
  int len = 0;
};

static SimResult simulate(const vector<int> &dirs) {
  SimResult r;
  r.body = body;
  r.len = MY_LEN;
  vector<int> eaten;
  for (size_t j = 0; j < dirs.size(); j++) {
    if (j > 0 && r.len < 3) {
      r.dead = true;
      return r;
    }
    int head = r.body[0];
    if (effK(head, dirs[j]) == 2) {
      r.dead = true;
      return r;
    }
    int dest = nbr[head * 4 + dirs[j]];
    if (dest < 0 || chokeReserved[dest] > ROUND) {
      r.dead = true;
      return r;
    }
    for (int c : r.body)
      if (c == dest) {
        r.dead = true;
        return r;
      }
    if (viewIndex[dest] < 0)
      r.outside = true;
    else if (occId[dest] &&
             (occId[dest] != MY_ID + 1 || ownLost[dest] == ROUND + 1)) {
      r.dead = true;
      if (occHead[dest])
        r.hitHeadId = occId[dest] - 1;
      return r;
    }
    r.cells.push_back(dest);
    bool ate =
        pearlNow(dest) && find(eaten.begin(), eaten.end(), dest) == eaten.end();
    r.body.insert(r.body.begin(), dest);
    if (ate) {
      eaten.push_back(dest);
      r.len++;
    } else
      r.body.pop_back();
    if (j > 0) {
      r.body.pop_back();
      r.len--;
    }
  }
  return r;
}

static int distA[MAXN], qA[MAXN], ownBT[MAXN], ownStamp[MAXN], stampCtr = 0;
static double powG[256], powT[256], powM[256];
static bool recordVals = false;
static double valT[MAXN];
static int goalCell = -1, lastGoal = -1, goalDistNow = -1;
static bool feeding = false;

struct EnemyReach {
  int id, len;
  vector<pair<int, int>> cells;
};
static vector<EnemyReach> reaches;

static void buildReaches() {
  reaches.clear();
  for (auto &dr : others) {
    if (dr.team == MY_TEAM || dr.headCell < 0)
      continue;
    EnemyReach er;
    er.id = dr.id;
    er.len = dr.estLen;
    vector<int> frontier{dr.headCell}, seen{dr.headCell};
    for (int depth = 1; depth <= 3; depth++) {
      vector<int> nf;
      for (int c : frontier)
        for (int d = 0; d < 4; d++) {
          int n = nbr[c * 4 + d];
          if (n < 0 || find(seen.begin(), seen.end(), n) != seen.end())
            continue;
          seen.push_back(n);
          er.cells.push_back({n, depth});
          if (occId[n] == 0)
            nf.push_back(n);
        }
      frontier = nf;
    }
    reaches.push_back(er);
  }
}

static bool checkTunnelCollision(int head, int nextCell) {
  int curr = nextCell, prev = head, tunnelLen = 1;
  while (true) {
    int nextNbr = -1, deg = 0;
    for (int d = 0; d < 4; d++) {
      int n = nbr[curr * 4 + d];
      if (n >= 0 && n != prev) {
        deg++;
        nextNbr = n;
      }
    }
    if (deg != 1)
      break;
    tunnelLen++;
    if (enemyBT[curr] > 0 || occId[curr] > 0 || enemyDist[curr] <= tunnelLen)
      return true;
    prev = curr;
    curr = nextNbr;
    if (tunnelLen > 30)
      break;
  }
  return false;
}

struct Eval {
  double score = -1e18, pDeath = 1.0, field = 0, target = 0, danger = 0,
         hunt = 0, corridor = 0, pocket = 0, territory = 0;
  int space = 0, surv = 0, room = 0, targetCell = -1, goalDist = -1,
      safeClass = 0;
  bool adjacent = false;
};

static int vt[MAXN];
static bool dfsAte[MAXN];
static long long dfsNodes, dfsBudget;
static int dfsTarget;
static bool dfsPessimist = false;

static inline bool pearlAtDepth(int c, int t) {
  int i = viewIndex[c];
  if (i < 0 || dfsAte[c])
    return false;
  if (V.pearl[i])
    return true;
  return spawnAt[c] >= 0 && spawnAt[c] <= ROUND + t;
}

static int dfs(int head, int t, int len) {
  if (t >= dfsTarget)
    return t;
  if (++dfsNodes > dfsBudget)
    return t;
  int best = t;
  int opts[4], score[4], no = 0;
  for (int d = 0; d < 4; d++) {
    int c = nbr[head * 4 + d];
    if (c < 0 || vt[c] >= t - len + 1)
      continue;
    if (enemyBT[c] >= t + 1 || allyBT[c] > t + 1 || chokeReserved[c] > ROUND ||
        (dfsPessimist &&
         (enemyBT[c] > 0 || allyBT[c] > 0 || radarExpire[c] > ROUND ||
          min(enemyDist[c], friendDist[c]) <= t + 1)))
      continue;
    if (t == 0 && (zoneE[c] || zoneF[c]))
      continue;
    int free = 0;
    for (int e = 0; e < 4; e++) {
      int n2 = nbr[c * 4 + e];
      if (n2 >= 0 && n2 != head && vt[n2] < t + 2 - len &&
          enemyBT[n2] < t + 2 && allyBT[n2] <= t + 2 &&
          chokeReserved[n2] <= ROUND)
        free++;
    }
    opts[no] = c;
#if FEATURE_POCKET_DFS_ORDERING
    score[no] =
        free * 4 - ((topoValid && pocketDepth[c] >= 0) ? pocketDepth[c] : -1);
#else
    score[no] = free;
#endif
    no++;
  }
#if FEATURE_DFS_BEST_FIRST
  for (int i = 0; i < no; i++)
    for (int j = i + 1; j < no; j++)
      if (score[j] > score[i]) {
        swap(score[i], score[j]);
        swap(opts[i], opts[j]);
      }
#else
  for (int i = 0; i < no; i++)
    for (int j = i + 1; j < no; j++)
      if (score[j] < score[i]) {
        swap(score[i], score[j]);
        swap(opts[i], opts[j]);
      }
#endif
  for (int i = 0; i < no; i++) {
    int c = opts[i], old = vt[c];
    vt[c] = t + 1;
    bool ate = pearlAtDepth(c, t + 1);
    if (ate)
      dfsAte[c] = true;
    int r = dfs(c, t + 1, len + (ate ? 1 : 0));
    if (ate)
      dfsAte[c] = false;
    vt[c] = old;
    if (r > best)
      best = r;
    if (best >= dfsTarget || dfsNodes > dfsBudget)
      break;
  }
  return best;
}

static int survivalDepth(const vector<int> &B, int len, int target,
                         long long budget) {
  for (size_t i = 0; i < B.size(); i++)
    if (B[i] >= 0)
      vt[B[i]] = -(int)i;
  dfsNodes = 0;
  dfsBudget = budget;
  dfsTarget = target;
  int r = dfs(B[0], 0, len);
  for (int c : B)
    if (c >= 0)
      vt[c] = INT32_MIN / 2;
  return r;
}

static bool endgame() { return ROUND >= 500 - P.endgameRounds; }

static double corridorRisk(const vector<int> &B) {
  if (B.size() < 2)
    return 0;
  stampCtr++;
  for (int c : B)
    if (c >= 0)
      ownStamp[c] = stampCtr;
  int h = B[0], k = 0;
  bool flanked = false, unseenExit = false;
  vector<int> path{h};
  for (int step = 0; step < 10; step++) {
    int nf = 0, next = -1;
    for (int d = 0; d < 4; d++) {
      int n = nbr[h * 4 + d];
      if (n < 0)
        continue;
      bool mine = ownStamp[n] == stampCtr ||
                  find(path.begin(), path.end(), n) != path.end();
      bool foreign = (occId[n] && occId[n] != MY_ID + 1) || enemyBT[n] > 0 ||
                     allyBT[n] > 0 || chokeReserved[n] > ROUND;
      if (foreign)
        flanked = true;
      if (mine || foreign)
        continue;
      nf++;
      next = n;
    }
    if (nf != 1)
      break;
    k++;
    if (viewIndex[next] < 0) {
      unseenExit = true;
      break;
    }
    path.push_back(next);
    h = next;
  }
  if (k < 2)
    return 0;
  if (flanked)
    return min(0.4, 0.07 * k + (unseenExit ? 0.12 : 0.0));
  return unseenExit ? min(0.25, 0.03 * k + 0.08) : 0.0;
}

static int capLen = 1 << 20;
static void computeCap() {
  static int seen[MAXN], ctr = 0;
  ctr++;
  int qh = 0, qt = 0;
  qA[qt++] = body[0];
  seen[body[0]] = ctr;
  while (qh < qt) {
    int c = qA[qh++];
    for (int d = 0; d < 4; d++) {
      int n = nbr[c * 4 + d];
      if (n < 0 || seen[n] == ctr)
        continue;
      seen[n] = ctr;
      qA[qt++] = n;
    }
  }
  capLen = max(10, qt / 6);
}

static Eval evaluate(const SimResult &s, bool deepAllowed) {
  if (elapsedMs() > 70)
    deepAllowed = false;
  Eval e;
  const vector<int> &B = s.body;
  int L = s.len, head = B[0];

  bool cheap = UNITS >= 4 && L <= 4 && queen.id != MY_ID;
  bool minerBase = UNITS >= 3 && L <= 4 && queen.id != MY_ID;

  // Smooth phase out for Kamikaze logic instead of a Round 300 cliff
  double phaseOut = 1.0;
  if (ROUND >= P.mineUntil)
    phaseOut = max(0.0, 1.0 - (ROUND - P.mineUntil) / 50.0);
  bool activeMiner = minerBase && phaseOut > 0;

  bool lateQ = !bigFeed && ROUND >= P.protectFrom,
       meQueen = lateQ && queen.id == MY_ID;
  int qCell = (lateQ && !meQueen && queen.cell >= 0 &&
               ROUND - queen.round <= 25 && queen.len > L)
                  ? queen.cell
                  : -1;
  stampCtr++;
  for (size_t i = 0; i < B.size(); i++)
    if (B[i] >= 0) {
      ownStamp[B[i]] = stampCtr;
      ownBT[B[i]] = L - (int)i;
    }
  for (int c = 0; c < N; c++)
    distA[c] = -1;
  if (recordVals)
    for (int c = 0; c < N; c++)
      valT[c] = 0;
  int qh = 0, qt = 0;
  distA[head] = 0;
  qA[qt++] = head;
  int depthCap = max(P.fieldCap, 2 * L + 12);
  double fsum = 0, fmax = 0;
  int space = 0;

  while (qh < qt) {
    int c = qA[qh++];
    int dc = distA[c];
    if (dc >= depthCap)
      continue;
    for (int d = 0; d < 4; d++) {
      int n = nbr[c * 4 + d];
      if (n < 0 || distA[n] >= 0)
        continue;
      int nd = dc + 1;
      if (ownStamp[n] == stampCtr && ownBT[n] >= nd)
        continue;
      if (enemyBT[n] >= nd || allyBT[n] > nd || chokeReserved[n] > ROUND)
        continue;
      if (nd <= 1 && (zoneE[n] || zoneF[n]))
        continue;
      distA[n] = nd;
      qA[qt++] = n;
      space++;
      if (nd <= P.fieldCap) {
        double p = pearlProb(n, ROUND + nd);
        if (p > 0) {
          // Brawler Logic with slightly disciplined proximity ignorance
          if (activeMiner) {
            if (enemyDist[n] < nd)
              p *= 0.85;
            else if (enemyDist[n] == nd)
              p *= 0.90;
          } else {
            if (enemyDist[n] < nd)
              p *= swarm ? 0.8 : P.enemyCloser;
            else if (enemyDist[n] == nd)
              p *= swarm ? 0.9 : P.enemyTie;
          }

          if (!meQueen && (friendDist[n] < nd ||
                           (friendDist[n] == nd && friendMinId[n] < MY_ID)))
            p *= P.friendCloser;
          if (!meQueen && !feeding && claimedFountains.count(n)) {
            auto &cf = claimedFountains[n];
            if (ROUND - cf.round <= 8 &&
                (cf.distSender < nd ||
                 (cf.distSender == nd && cf.sx < (head % W))))
              p *= 0.3;
          }
          if (qCell >= 0 && torusDist(qCell, n) < nd)
            p *= 0.3;
          p *= activeMiner ? min(P.minerFarmCap, farmBonus(n)) : farmBonus(n);
          fsum += p * powG[nd];
          double v = p * (activeMiner ? powM[nd] : powT[nd]);
          if (v > fmax) {
            fmax = v;
            e.targetCell = n;
          }
          if (recordVals)
            valT[n] = v;
        }
      }
    }
  }
  e.space = space;
  e.field = fsum;
  e.target = fmax;
  e.goalDist = goalCell >= 0 ? distA[goalCell] : -1;

  {
    int left = max(0, 499 - ROUND);
    int roomy = min(2 * L + 15, left + 1);
    int st = space;
    e.room = st;
    if (st >= roomy && (L < 20 || !deepAllowed)) {
      e.pDeath = 0;
      e.surv = 999;
      e.safeClass = 2;
      e.pocket = 0.0;
    } else {
      int target = min(min(2 * L + 8, 90), left);
      long long budget = (elapsedMs() > 55)   ? 0
                         : (elapsedMs() > 35) ? 1500
                                              : 12000;
      if (budget == 0)
        deepAllowed = false;
      int got, pes = 0;
      if (!deepAllowed)
        got = min(st, target);
      else {
        dfsPessimist = true;
        pes = survivalDepth(B, L, target, budget);
        dfsPessimist = false;
        got = pes >= target ? pes : survivalDepth(B, L, target, budget);
      }
      e.surv = got;
      e.safeClass = (deepAllowed && pes >= target) ? 2 : got >= target ? 1 : 0;
      if (deepAllowed && pes >= target)
        e.pDeath = 0.0;
      else if (got >= target)
        e.pDeath = 0.5 * (1.0 - (double)pes / target);
      else
        e.pDeath = pow(1.0 - (double)got / target, 0.6);

      if (got >= target)
        e.pocket = 0.0;
      else
        e.pocket = 1.0 - (double)st / roomy;
    }
  }

#if FEATURE_HARD_HORIZON_PRUNING
  // ACTIVE FOR ALL UNITS: Plunging into deep pockets without length to span
  // them is physically fatal
  if (topoValid && !s.cells.empty() && body[0] >= 0) {
    int oldHead = body[0], firstStep = s.cells[0];
    if (pocketDepth[oldHead] == -1 && pocketDepth[firstStep] >= 0) {
      int D = pocketDepth[firstStep];
      double cap =
          activeMiner
              ? 2.0
              : 1.5; // Miners allowed slightly more leniency for kamikaze setup
      if (MY_LEN + 1 > cap * D + 2.0) {
        e.safeClass = 0;
        e.pDeath = 1.0;
        e.score -= 10000.0;
        return e;
      }
    }
  }
#endif

#if FEATURE_TUNNEL_COLLISION_AVOIDANCE
  // ACTIVE FOR ALL UNITS: Tunnel collisions vs closer enemies are guaranteed
  // death
  if (!s.cells.empty() && body[0] >= 0) {
    if (checkTunnelCollision(body[0], s.cells[0])) {
      e.safeClass = min(e.safeClass, 0);
      e.score -= 50.0;
    }
  }
#endif

  double danger = 0;
  bool adjacentThreat = false;
  for (auto &er : reaches) {
    int dd = 99;
    for (auto &pc : er.cells)
      if (pc.first == head) {
        dd = pc.second;
        break;
      }
    double p = 0;
    if (dd == 1)
      p = P.p1;
    else if (dd == 2 && er.len <= 4)
      p = P.p2Drone;
    else if (dd == 2 && er.len >= 3)
      p = P.p2;
    else if (dd == 3 && er.len <= 4)
      p = P.p3Drone;
    else if (dd == 3 && er.len >= 4)
      p = P.p3;
    if (p <= 0)
      continue;
    double unitValue = UNITS <= 2 ? 10.0 : UNITS <= 4 ? 5.0 : 2.0;
    double loss = max(0.5, L - 0.8 * er.len + 3.0) + unitValue;
    if (swarm)
      p = min(0.95, p * 1.4);
    if (ROUND >= P.feedFrom - 30 && queen.id == MY_ID)
      loss *= (ROUND >= P.protectFrom ? 3.0 : 2.0);
    if ((L >= 6 || UNITS <= 4) && (dd == 1 || (dd <= 3 && dd <= er.len - 1)))
      adjacentThreat = true;
    if (UNITS == 1)
      loss = L + 14.0;
    danger += p * loss;
  }
  e.danger = danger;
  if (adjacentThreat)
    e.safeClass = min(e.safeClass, 1);
  e.adjacent = adjacentThreat;

  double hunt = 0;
  if (L <= P.huntMaxLen && UNITS >= 2) {
    for (auto &dr : others) {
      if (dr.team == MY_TEAM || dr.headCell < 0 ||
          dr.estLen < L + P.attackMargin)
        continue;
      int best = 1 << 20;
      for (int d = 0; d < 4; d++) {
        int n = nbr[dr.headCell * 4 + d];
        if (n >= 0 && distA[n] >= 0)
          best = min(best, distA[n] + 1);
      }
      if (head == dr.headCell)
        best = 0;
      if (best < 64)
        hunt = max(hunt, powG[best] * min(3.0, dr.estLen / 6.0));
    }
  }
  e.hunt = hunt;

  double growth = s.len - MY_LEN;
  double greed = endgame() ? 0.35 : (activeMiner ? 3.0 : 1.0);

  if (L > capLen && !endgame()) {
    greed *= 0.3;
    if (growth > 0)
      growth *= -0.3;
  }
  double score = growth * (endgame() ? 1.5 : 1.0) +
                 greed * (P.wField * fsum + P.wTarget * fmax) + P.wHunt * hunt;

  if (goalCell >= 0 && goalDistNow >= 0) {
    bool ateGoal =
        find(s.cells.begin(), s.cells.end(), goalCell) != s.cells.end();
    double prog = ateGoal ? 1.0
                  : e.goalDist < 0
                      ? -1.5
                      : max(-2.0, min(2.0, (double)(goalDistNow - e.goalDist)));
    score += (feeding ? 4.0 : greed) * P.wProgress * prog;
  }

  score -= danger;

  // Kamikaze Death Discount: Scaled by phaseOut to avoid round 300 cliffs
  double deathPenaltyBase = L + (cheap ? 3.0 : P.deathExtra);
  if (activeMiner) {
    double kamikazeBase = L * 0.5;
    deathPenaltyBase =
        kamikazeBase * phaseOut + deathPenaltyBase * (1.0 - phaseOut);
  }
  score -= e.pDeath * deathPenaltyBase;

  e.corridor = corridorRisk(B);

  double headRisk = 0.0;
  if (topoValid && pocketDepth[head] >= 0) {
    double bs = FEATURE_BRANCH_SIZE ? (double)branchSize[head] : 4.0;
    double need = 2.0 * L + 6.0;
    double exitNear = 1.0 / (1.0 + 0.5 * pocketDepth[head]);
    headRisk = (1.0 - min(1.0, bs / need)) * (0.5 + 0.5 * exitNear);
  }

  // Miners receive a 70% discount on structural fear, not a 100% exemption
  double structMult = activeMiner ? (1.0 - 0.7 * phaseOut) : 1.0;

  score -= P.wPocket * e.pocket * (2.0 + L / 4.0) * structMult;
  score -= headRisk * (6.0 + 0.3 * L) * structMult;
  score -=
      e.corridor * (1.0 + crampFraction * 1.5) * (L / 2.0 + 10.0) * structMult;

#if FEATURE_TERRITORY
  int ed = enemyDist[head];
  int fd = friendDist[head];
  if (ed < 40 && fd < 40) {
    double margin = max(-10.0, min(10.0, (double)(ed - fd)));
    if (margin < 0)
      score += margin * 0.6;
  }
#endif

  score += P.spaceBonus * min(1.0, space / (double)(2 * L + 20));
  if (s.outside) {
    bool remembered = !s.cells.empty() && memExpire[s.cells.back()] > ROUND;
    if (KM && !remembered)
      score -= 0.8 + 0.03 * L;
    else {
      score -= 3.0 + 0.12 * (L + P.deathExtra);
      e.safeClass = 0;
    }
  }

  e.score = score;

  bool riskOk = e.pDeath < 0.25 || (L <= 4 && e.pDeath < 0.95) ||
                (cheap && !bigFeed && e.pDeath < 0.9);
  e.safeClass =
      (riskOk && !adjacentThreat && (!s.outside || (KM && e.safeClass > 0)))
          ? 1
          : 0;
  return e;
}

static string indicator;
static bool DEBUG = false;
static int debugFrom = 0, debugTo = -1;

static void dumpState() {
  if (!DEBUG || ROUND < debugFrom || ROUND > debugTo)
    return;
  int R = 7, hx = body[0] % W, hy = body[0] / W;
  vector<int> bidx(N, -1);
  for (size_t i = 0; i < body.size(); i++)
    if (body[i] >= 0)
      bidx[body[i]] = (int)i;
  for (int dy = -R; dy <= R; dy++) {
    string top, row;
    for (int dx = -R; dx <= R; dx++) {
      int x = ((hx + dx) % W + W) % W, y = ((hy + dy) % H + H) % H,
          c = y * W + x;
      int kn = effK(c, 0), kw = effK(c, 3);
      top += "+";
      top += kn == 2 ? "--" : kn == 3 ? "PP" : kn == 0 ? ".." : "  ";
      row += kw == 2 ? "|" : kw == 3 ? "P" : kw == 0 ? ":" : " ";
      char a = ' ', b = ' ';
      if (bidx[c] >= 0) {
        a = bidx[c] == 0 ? '@' : 'o';
        b = "0123456789abcdefghijklmnopqrstuvwxyz"[min(35, bidx[c])];
      } else if (occId[c]) {
        bool fr = false;
        for (auto &dr : others)
          if (dr.id == occId[c] - 1)
            fr = dr.team == MY_TEAM;
        a = occHead[c] ? (fr ? 'F' : 'E') : (fr ? 'f' : 'e');
        int bt = max(min(9, enemyBT[c]), min(9, allyBT[c]));
        b = (char)('0' + bt);
      } else if (pearlNow(c))
        a = '*';
      else if (viewIndex[c] < 0) {
        a = '?';
        b = seenR[c] >= 0 ? '.' : '?';
      }
      row += a;
      row += b;
    }
    printf("LOG %s\nLOG %s\n", top.c_str(), row.c_str());
  }
}
static vector<int> chosenCells;

static void emitMove(const vector<int> &dirs, const vector<int> &cells) {
  string m = "MOVE ";
  for (int d : dirs)
    m += DCH[d];
  printf("%s\n", m.c_str());
  chosenCells = cells;
}

static bool findAttack(bool desperate) {
  int best = -1;
  vector<int> bestPath;
  double bestVal = -1e9;
  for (auto &dr : others) {
    if (dr.team == MY_TEAM || dr.headCell < 0)
      continue;
    bool worth = UNITS >= 2 && dr.estLen >= max(MY_LEN + 4, 2 * MY_LEN);
    if (!worth && UNITS >= 12 && MY_LEN <= 3 && queen.id != MY_ID &&
        dr.estLen >= MY_LEN) {
      int mine = 0, theirs = 0;
      for (auto &o : others)
        if (o.headCell >= 0)
          (o.team == MY_TEAM ? mine : theirs)++;
      if (mine + 1 > theirs)
        worth = true;
    }
    if (UNITS >= 2 && endgame() && dr.estLen >= MY_LEN + 2)
      worth = true;
    if (desperate && !(endgame() && MY_LEN > dr.estLen))
      worth = true;
    if (!worth || torusDist(body[0], dr.headCell) > P.attackMaxSteps)
      continue;
    int maxSteps = min(P.attackMaxSteps, MY_LEN - 1);
    vector<int> path, found;
    for (int k = 1; k <= maxSteps && found.empty(); k++) {
      int total = 1;
      for (int i = 0; i < k; i++)
        total *= 4;
      for (int code = 0; code < total && found.empty(); code++) {
        path.clear();
        int cc = code;
        for (int i = 0; i < k; i++) {
          path.push_back(cc % 4);
          cc /= 4;
        }
        SimResult r = simulate(path);
        if (r.dead && r.hitHeadId == dr.id && (int)r.cells.size() == k - 1)
          found = path;
      }
    }
    if (found.empty())
      continue;
    double val = dr.estLen - MY_LEN - 0.3 * found.size();
    if (val > bestVal) {
      bestVal = val;
      best = dr.id;
      bestPath = found;
    }
  }
  if (best < 0)
    return false;
  string m = "MOVE ";
  for (int d : bestPath)
    m += DCH[d];
  printf("%s\n", m.c_str());
  indicator = "ATK " + to_string(best);
  return true;
}

static string dsWhy;
static bool doomedSplit(bool allowShed = true) {
  if (MY_LEN < 4 || UNITS >= UNIT_LIMIT) {
    dsWhy = "len/units";
    return false;
  }
  for (int c : body)
    if (c < 0) {
      dsWhy = "unknown body";
      return false;
    }
  double bestVal = 0;
  int bestC = -1;
  for (int c = MY_LEN - 2; c >= 2; c--) {
    if (elapsedMs() > 55)
      break;
    vector<int> savedE, savedA;
    for (int i = 0; i < MY_LEN - c; i++) {
      savedE.push_back(enemyBT[body[i]]);
      enemyBT[body[i]] = 1000;
      savedA.push_back(allyBT[body[i]]);
      allyBT[body[i]] = 1000;
    }
    SimResult child;
    for (int i = MY_LEN - 1; i >= MY_LEN - c; i--)
      child.body.push_back(body[i]);
    child.len = c;
    int freeN = 0;
    for (int d = 0; d < 4; d++) {
      int n = nbr[child.body[0] * 4 + d];
      if (n >= 0 && !occId[n] && effK(child.body[0], d) != 2)
        freeN++;
    }
    double val = freeN > 0 ? (1.0 - evaluate(child, true).pDeath) * c : 0;
    for (int i = 0; i < MY_LEN - c; i++) {
      enemyBT[body[i]] = savedE[i];
      allyBT[body[i]] = savedA[i];
    }
    if (val > bestVal + 1e-9) {
      bestVal = val;
      bestC = c;
    }
  }
  if (bestC < 0 || bestVal < 1.0) {
    if (!allowShed)
      return false;
    for (int c = 2; c <= MY_LEN - 4; c++) {
      int newTail = body[MY_LEN - 1 - c];
      bool open = false;
      for (int d = 0; d < 4; d++) {
        int n = nbr[newTail * 4 + d];
        if (n < 0 || occId[n] || effK(newTail, d) == 2)
          continue;
        bool mine = false;
        for (int i = 0; i < MY_LEN; i++)
          if (body[i] == n)
            mine = true;
        if (!mine)
          open = true;
      }
      if (open) {
        printf("SPLIT %d\n", c);
        indicator = "SHED " + to_string(c);
        return true;
      }
    }
    dsWhy = "val " + to_string(bestVal);
    return false;
  }
  printf("SPLIT %d\n", bestC);
  indicator = "ESCAPE-SPLIT " + to_string(bestC);
  return true;
}

static bool swarmSplit() {
  if (MY_LEN < P.budAt || UNITS >= UNIT_LIMIT)
    return false;
  int until = (bigFeed) ? P.budUntil : (UNITS < 40 ? 420 : P.budUntil);
  if (ROUND >= until)
    return false;
  for (int i = MY_LEN - 2; i < MY_LEN; i++)
    if (body[i] < 0)
      return false;
  int tail = body[MY_LEN - 1];
  for (int d = 0; d < 4; d++) {
    int n = nbr[tail * 4 + d];
    if (n >= 0 && !occId[n] && n != body[MY_LEN - 2]) {
      printf("SPLIT 2\n");
      indicator = "BUD";
      return true;
    }
  }
  return false;
}

static bool trySplit(const Eval &stayEval) {
  int c = P.splitChild > 0 ? P.splitChild : MY_LEN / 2;
  bool overlong = MY_LEN > capLen && !endgame();
  if (overlong) {
    c = MY_LEN / 2;
    if (UNITS >= min(UNIT_LIMIT, 6))
      return false;
  } else {
    if (ROUND >= P.splitRoundMax || endgame())
      return false;
    if (swarm) {
      if (UNITS >= 5 || MY_LEN < 8)
        return false;
      c = max(3, MY_LEN / 3);
    } else {
      if (UNITS >= min(UNIT_LIMIT, 3) || MY_LEN < P.splitMinLen)
        return false;
    }
  }
  if (MY_LEN - c < 2 || c < 2)
    return false;
  for (int i = MY_LEN - c; i < MY_LEN; i++)
    if (body[i] < 0)
      return false;
  for (auto &dr : others)
    if (dr.team != MY_TEAM && dr.headCell >= 0 &&
        torusDist(dr.headCell, body[0]) <= (overlong ? 2 : 6))
      return false;
  if (stayEval.pDeath > 0 && !overlong)
    return false;
  int tail = body[MY_LEN - 1], freeN = 0;
  for (int d = 0; d < 4; d++) {
    int n = nbr[tail * 4 + d];
    if (n >= 0 && !occId[n])
      freeN++;
  }
  if (freeN == 0)
    return false;
  SimResult parent;
  parent.body.assign(body.begin(), body.begin() + (MY_LEN - c));
  parent.len = MY_LEN - c;
  if (evaluate(parent, false).space < parent.len + 8 && !overlong)
    return false;
  SimResult child;
  for (int i = MY_LEN - 1; i >= MY_LEN - c; i--)
    child.body.push_back(body[i]);
  child.len = c;
  if (evaluate(child, false).space < (overlong ? 4 : 12))
    return false;
  printf("SPLIT %d\n", c);
  indicator = "SPLIT";
  return true;
}

static bool outranks(int len, int id) {
  return len > MY_LEN || (len == MY_LEN && id < MY_ID);
}
static bool lateFeed() {
  return !bigFeed && ROUND >= P.endFeedFrom && UNITS >= 6;
}
static bool tryFeed() {
  if (ROUND < P.feedFrom || iAmQueen() || !outranks(queen.len, queen.id) ||
      ROUND - queen.round > 25)
    return false;
  if (queen.cell < 0 || torusDist(queen.cell, body[0]) > P.feedRadius)
    return false;
  for (auto &dr : others) {
    bool worthy =
        bigFeed
            ? (dr.id == queen.id || dr.estLen >= MY_LEN + 3)
            : (dr.estLen >= max(10, 2 * MY_LEN) ||
               (lateFeed() && dr.id == queen.id && dr.estLen >= MY_LEN + 2));
    if (dr.team != MY_TEAM || dr.headCell < 0 || !worthy)
      continue;
    if (torusDist(dr.headCell, body[0]) <= 3) {
      printf("SPLIT 1\n");
      indicator = "FEED " + to_string(dr.id);
      return true;
    }
  }
  return false;
}

static void think() {
  buildDragons();
  buildReaches();
  computeCap();
  updateQueen();
  if (tryFeed())
    return;
  dumpState();
  chosenCells.clear();
  myNextHead = -1;
  myIntentPath = 0;

  {
    goalCell = -1;
    goalDistNow = -1;
    SimResult here;
    here.body = body;
    here.len = MY_LEN;
    recordVals = true;
    Eval he = evaluate(here, false);
    recordVals = false;
    int best = he.targetCell, g = best;

    // Dynamic Hysteresis: Strict lock-on during active mining open spaces,
    // relaxed later/crowded
    bool activeMiner = (UNITS >= 3 && MY_LEN <= 4 && queen.id != MY_ID &&
                        ROUND < P.mineUntil + 50);
    double hyst = activeMiner ? 0.45 : (crampFraction > 0.05 ? 0.70 : 0.60);

    if (lastGoal >= 0 && lastGoal != best && best >= 0 && distA[lastGoal] > 0 &&
        valT[lastGoal] >= hyst * valT[best])
      g = lastGoal;

    if (g >= 0 && distA[g] > 0) {
      goalCell = g;
      goalDistNow = distA[g];
    }
    feeding = ROUND >= P.feedFrom && !iAmQueen() &&
              (bigFeed ? outranks(queen.len, queen.id)
                       : (queen.len >= max(10, 2 * MY_LEN) ||
                          (lateFeed() && queen.len >= MY_LEN + 2))) &&
              ROUND - queen.round <= 25 && queen.cell >= 0 &&
              torusDist(queen.cell, body[0]) <= P.feedRadius;
    if (feeding && queen.cell >= 0 && distA[queen.cell] != 0) {
      int qd = distA[queen.cell];
      if (qd < 0) {
        for (int d = 0; d < 4; d++) {
          int n = nbr[queen.cell * 4 + d];
          if (n >= 0 && distA[n] > 0 && (qd < 0 || distA[n] < qd)) {
            qd = distA[n];
            g = n;
          }
        }
      } else
        g = queen.cell;
      if (qd > 0) {
        goalCell = g;
        goalDistNow = qd;
      }
    }
    lastGoal = goalCell;
  }

  struct Opt {
    vector<int> dirs;
    SimResult sim;
    Eval ev;
  };
  vector<Opt> opts;
  for (int d = 0; d < 4; d++) {
    Opt o;
    o.dirs = {d};
    o.sim = simulate(o.dirs);
    if (!o.sim.dead)
      opts.push_back(o);
  }

  bool threat = false;
  for (auto &er : reaches)
    for (auto &pc : er.cells)
      if (pc.second <= 2 && torusDist(pc.first, body[0]) <= 1)
        threat = true;
  bool evaluateSprints =
      threat || (!endgame() && giantThreatLen >= 10 &&
                 ROUND - giantThreatRound <= 15 && MY_LEN >= 4);

  if (evaluateSprints && MY_LEN >= 8 && !endgame()) {
    for (int a = 0; a < 4; a++)
      for (int b = 0; b < 4; b++) {
        if (b == opp(a))
          continue;
        Opt o;
        o.dirs = {a, b};
        o.sim = simulate(o.dirs);
        if (!o.sim.dead && !o.sim.outside)
          opts.push_back(o);
      }
  }
  for (auto &o : opts)
    o.ev = evaluate(o.sim, true);
  sort(opts.begin(), opts.end(), [](const Opt &a, const Opt &b) {
    if (a.ev.safeClass != b.ev.safeClass)
      return a.ev.safeClass > b.ev.safeClass;
    return a.ev.score > b.ev.score;
  });

  if ((opts.empty() || opts[0].ev.pDeath >= (MY_LEN >= 8 ? 0.5 : 0.9)) &&
      MY_LEN >= 3) {
    vector<Opt> extra;
    for (int k = 2; k <= min(3, MY_LEN - 1); k++) {
      int total = k == 2 ? 16 : 64;
      for (int code = 0; code < total; code++) {
        Opt o;
        int cc = code;
        for (int i = 0; i < k; i++) {
          o.dirs.push_back(cc % 4);
          cc /= 4;
        }
        bool rev = false;
        for (int i = 1; i < k; i++)
          if (o.dirs[i] == opp(o.dirs[i - 1]))
            rev = true;
        if (rev)
          continue;
        if (elapsedMs() > 60)
          break;
        o.sim = simulate(o.dirs);
        if (o.sim.dead)
          continue;
        o.ev = evaluate(o.sim, true);
        extra.push_back(o);
      }
    }
    for (auto &o : extra)
      opts.push_back(o);
    sort(opts.begin(), opts.end(), [](const Opt &a, const Opt &b) {
      if (a.ev.safeClass != b.ev.safeClass)
        return a.ev.safeClass > b.ev.safeClass;
      return a.ev.score > b.ev.score;
    });
  }

  if ((opts.empty() || (opts[0].ev.pDeath >= (protectedQueen() ? 0.99 : 0.9) &&
                        opts[0].ev.surv <= 1)) &&
      doomedSplit())
    return;
  if (!opts.empty() && MY_LEN >= 8 && !protectedQueen() &&
      opts[0].ev.danger >= max(3.0, 0.3 * MY_LEN) && doomedSplit(false)) {
    indicator = "DANGER-" + indicator;
    return;
  }

  bool desperate = opts.empty() || opts[0].ev.pDeath >= 0.95;
  if (findAttack(desperate))
    return;

  if (!opts.empty()) {
    SimResult stay;
    stay.body = body;
    stay.len = MY_LEN;
    Eval se = evaluate(stay, false);
    if (!protectedQueen() &&
        (opts[0].ev.pDeath < 0.5 || (MY_LEN <= 4 && ROUND < P.mineUntil)) &&
        !opts[0].ev.adjacent && swarmSplit())
      return;
    if (!protectedQueen() && (opts[0].ev.pDeath == 0 || MY_LEN > capLen) &&
        trySplit(se))
      return;

    auto &o = opts[0];
    committedPath.clear();

    myNextHead = o.sim.cells.empty() ? body[0] : o.sim.cells[0];
    if (o.dirs.size() > 1)
      myIntentPath |= (o.dirs[1] & 3);
    else
      myIntentPath |= (o.dirs[0] & 3);
    if (o.dirs.size() > 2)
      myIntentPath |= ((o.dirs[2] & 3) << 2);
    else
      myIntentPath |= ((myIntentPath & 3) << 2);
    if (o.dirs.size() > 3)
      myIntentPath |= ((o.dirs[3] & 3) << 4);
    else
      myIntentPath |= (((myIntentPath >> 2) & 3) << 4);

    emitMove(o.dirs, o.sim.cells);
    char tmp[160];
    snprintf(tmp, sizeof tmp,
             "L%d s%.1f sp%d rm%d f%.2f t%.2f dg%.2f pd%.2f%s CR%.2f%s U%d",
             MY_LEN, o.ev.score, o.ev.space, o.ev.room, o.ev.field, o.ev.target,
             o.ev.danger, o.ev.pDeath, KM ? " K" : "", crampFraction,
             bigFeed ? "BF" : "", UNITS);
    indicator = tmp;
    if (o.ev.targetCell >= 0)
      indicator += " T" + to_string(o.ev.targetCell % W) + "," +
                   to_string(o.ev.targetCell / W);
    return;
  }

  int bestD = MY_DIR, bestRank = -1;
  for (int d = 0; d < 4; d++) {
    int n = nbr[body[0] * 4 + d];
    int rank;
    if (n < 0)
      rank = 1;
    else if (!occId[n])
      rank = 4;
    else {
      int id = occId[n] - 1;
      bool friendly = false;
      for (auto &dr : others)
        if (dr.id == id)
          friendly = dr.team == MY_TEAM;
      if (id == MY_ID)
        rank = 1;
      else if (friendly)
        rank = 0;
      else
        rank = occHead[n] ? 3 : 2;
    }
    if (rank > bestRank) {
      bestRank = rank;
      bestD = d;
    }
  }
  emitMove({bestD}, {});
  indicator = "DOOMED " + dsWhy;
}

static void castRadar() {
  lastRay.clear();
  if (body.empty() || body[0] < 0)
    return;
  int head = body[0], dir = MY_DIR;
  if (!chosenCells.empty()) {
    head = chosenCells.back();
    int prev =
        chosenCells.size() >= 2 ? chosenCells[chosenCells.size() - 2] : body[0];
    for (int d = 0; d < 4; d++)
      if (nbr[prev * 4 + d] == head)
        dir = d;
  }
  int c = head;
  for (int k = 0; k < W + H; k++) {
    c = nbr[c * 4 + dir];
    if (c < 0)
      break;
    lastRay.push_back(c);
  }

  uint64_t fwdVal = 0;
  int nextCell = chosenCells.empty() ? nbr[head * 4 + MY_DIR] : chosenCells[0];

#if FEATURE_CHOKE_RESERVATION
  bool enteringPocket = (topoValid && pocketDepth[head] == -1 &&
                         nextCell >= 0 && pocketDepth[nextCell] >= 0);
#else
  bool enteringPocket = false;
#endif

  if (enteringPocket) {
    fwdVal = packMsg(MSG_CHOKE, nextCell % W, nextCell / W, MY_ID,
                     pocketDepth[nextCell], ROUND);
  } else if (giantThreatLen >= 10 && ROUND - giantThreatRound <= 10 &&
             giantThreatCell >= 0) {
    fwdVal = packMsg(MSG_GIANT, giantThreatCell % W, giantThreatCell / W,
                     giantThreatLen, MY_ID, ROUND);
  } else if (ROUND >= P.gossipFrom && queen.cell >= 0 &&
             (MY_ID % 3 == ROUND % 3)) {
    fwdVal = packMsg(MSG_QUEEN, queen.cell % W, queen.cell / W, queen.len,
                     queen.id, ROUND);
  } else if (myNextHead >= 0) {
    fwdVal = packMsg(MSG_INTENT, myNextHead % W, myNextHead / W, MY_ID,
                     myIntentPath, ROUND);
  } else {
    int claimCell = -1;
    for (int d = 0; d < 4; d++) {
      int n = nbr[head * 4 + d];
      if (n >= 0 && pearlProb(n, ROUND + 1) > 0.8) {
        claimCell = n;
        break;
      }
    }
    if (claimCell >= 0)
      fwdVal = packMsg(MSG_FOUNTAIN, head % W, head / W, claimCell, 100, ROUND);
  }

  printf("SONAR %c %llu\n", DCH[dir], (unsigned long long)fwdVal);
}

static void fallback() {
  int head = -1;
  for (auto &q : V.parts)
    if (q.id == MY_ID && q.head)
      head = q.cell;
  if (head >= 0) {
    for (int d = 0; d < 4; d++) {
      int i = viewIndex[head];
      if (i < 0 || V.ek[i][d] != 1)
        continue;
      int n = stepRaw(head, d);
      if (viewIndex[n] >= 0 && occId[n] == 0) {
        printf("MOVE %c\n", DCH[d]);
        return;
      }
    }
  }
  printf("MOVE %c\n", DCH[MY_DIR]);
}

int main() {
  setvbuf(stdout, nullptr, _IOFBF, 1 << 16);
  if (!nextLine())
    return 0;
  MY_ID = (int)labelled();
  nextLine();
  {
    char *p = skipWord(buf);
    while (*p == ' ')
      p++;
    MY_TEAM = (*p == 'A') ? 0 : 1;
  }
  nextLine();
  {
    char *p = skipWord(buf);
    W = (int)strtol(p, &p, 10);
    H = (int)strtol(p, &p, 10);
  }
  nextLine();
  UNIT_LIMIT = (int)labelled();
  initKnowledge();
#if __has_include("debug_cfg.hpp")
#include "debug_cfg.hpp"
  DEBUG = true;
  debugFrom = DEBUG_FROM;
  debugTo = DEBUG_TO;
#endif
  for (int i = 0; i < 256; i++) {
    powG[i] = pow(P.gamma, i);
    powT[i] = pow(0.94, i);
    powM[i] = pow(P.minerGamma, i);
  }
  for (int c = 0; c < MAXN; c++)
    vt[c] = INT32_MIN / 2;

  while (readTurn()) {
    T0 = chrono::steady_clock::now();
    indicator.clear();
    try {
      absorbView();
      think();
    } catch (...) {
      fallback();
    }
    castRadar();
    if (!indicator.empty())
      printf("INDICATOR %s\n", indicator.c_str());
    printf("PROTOCOL 3\nENDTURN\n");
    fflush(stdout);
    lastPath = chosenCells;
    havePrev = true;
  }
  return 0;
}