// Viper V8 -- C++ Rewrite of V7 with 64-Bit Sonar, Sentinel-Helper Roles,
// and 4-Tier Pocket Entrapment Detection & Flushing Protocol.

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

// ---------------------------------------------------------------- tunables --

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
  int budUntil = 300;
  int feedFrom = 350;
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
  int dx = abs(a % W - b % W), dy = abs(a / W - b / W);
  return min(dx, W - dx) + min(dy, H - dy);
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
  int k = obsK[c * 4 + d];
  if (k)
    return k;
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
}

static int seenR[MAXN];
static bool pearlSeen[MAXN];
static int spawnAt[MAXN];
static int mirSpawn[MAXN];
static int gmin[MAXN], gmax[MAXN];
static int memExpire[MAXN];
static int maxEnemyId = -1;
static bool swarm = false;
static int radarExpire[MAXN];
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
static void activateMap(int idx, vector<int8_t> &&k, vector<int> &&p) {
  KM = &KNOWN_MAPS[idx];
  {
    string nm = KM->name;
    bigFeed = nm == "portals" || nm == "slithery_fight" || nm == "schooltime";
    if (bigFeed)
      P.budUntil = 330;
  }
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
  for (int c = 0; c < N; c++) {
    gmin[c] = gmax[c] = -1;
  }
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
  if (nbrDirty)
    rebuildNbr();
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
  int id, team;
  int headCell = -1, headFace = 0;
  int visCount = 0;
  bool tailKnown = false;
  int estLen = 0;
};
static vector<Dragon> others;
static int otherBT[MAXN];
static int occId[MAXN];
static bool occHead[MAXN];
static int zoneE[MAXN], zoneF[MAXN];
static int enemyDist[MAXN], friendDist[MAXN], friendMinId[MAXN];
static const int UNKNOWN_EXTRA = 10;

static vector<int> body;
static vector<int> lastPath;
static bool havePrev = false;

static int partAt[MAXN];
static int ownLost[MAXN];
static int eatMargin[256];

static void buildDragons() {
  const auto &parts = V.parts;
  int np = (int)parts.size();
  for (int i = 0; i < 49; i++) {
    partAt[V.cell[i]] = -1;
  }
  for (int c = 0; c < N; c++) {
    otherBT[c] = 0;
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
      int q = stepRaw(c, d);
      if (viewIndex[q] < 0)
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
      otherBT[c] = memExpire[c] - ROUND;
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
  others.clear();
  unordered_map<int, int> idx;
  for (int i = 0; i < np; i++) {
    const Part &q = parts[i];
    if (q.id == MY_ID)
      continue;
    int extra = certain[i] ? 0 : UNKNOWN_EXTRA;
    otherBT[q.cell] = behind[i] + extra + 1 + eatMargin[q.id % 256];
    memExpire[q.cell] = ROUND + otherBT[q.cell];
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
    bool match = pred.size() >= body.size();
    for (size_t i = 0; i < body.size() && match; i++)
      match = pred[i] == body[i];
    if (match) {
      for (size_t i = body.size(); i < pred.size() && (int)body.size() < MY_LEN;
           i++)
        body.push_back(pred[i]);
    } else if (!havePrev && !KM && ROUND == 0 && body.size() >= 2) {
      int a = body[body.size() - 2], b = body.back();
      int dir = -1;
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
      otherBT[parts[i].cell] = max(otherBT[parts[i].cell], MY_LEN);
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

// ---------------------------------------------------------------- simulation
// --

static inline bool pearlNow(int c) {
  return viewIndex[c] >= 0 && V.pearl[viewIndex[c]];
}

struct SimResult {
  bool dead = false;
  bool outside = false;
  int hitHeadId = -1;
  vector<int> body;
  vector<int> cells;
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
    int dest = nbr[head * 4 + dirs[j]];
    if (dest < 0) {
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

// ------------------------------------------------------------ evaluation --

static int distA[MAXN], qA[MAXN];
static int ownBT[MAXN], ownStamp[MAXN], stampCtr = 0;
static double powG[256], powT[256];
static bool recordVals = false;
static double valT[MAXN];
struct QueenInfo {
  int cell = -1, len = 0, round = -1000, id = -1;
};
static QueenInfo queen;
static int goalCell = -1, lastGoal = -1, goalDistNow = -1;
static bool feeding = false;

struct EnemyReach {
  int id;
  int len;
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
    vector<int> frontier{dr.headCell};
    vector<int> seen{dr.headCell};
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

struct Eval {
  double score = -1e18;
  double pDeath = 1.0;
  int space = 0;
  double field = 0, target = 0, danger = 0, hunt = 0;
  int surv = 0;
  int room = 0;
  int targetCell = -1;
  int goalDist = -1;
  int safeClass = 0;
  double corridor = 0;
  bool adjacent = false;
  double pocket = 0;
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
  int sa = spawnAt[c];
  return sa >= 0 && sa <= ROUND + t;
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
    if (c < 0)
      continue;
    if (vt[c] >= t - len + 1)
      continue;
    if (otherBT[c] >= t + 1 ||
        (dfsPessimist && (otherBT[c] > 0 || radarExpire[c] > ROUND ||
                          min(enemyDist[c], friendDist[c]) <= t + 1)))
      continue;
    if (t == 0 && (zoneE[c] || zoneF[c]))
      continue;
    int free = 0;
    for (int e = 0; e < 4; e++) {
      int n2 = nbr[c * 4 + e];
      if (n2 >= 0 && n2 != head && vt[n2] < t + 2 - len && otherBT[n2] < t + 2)
        free++;
    }
    opts[no] = c;
    score[no] = free;
    no++;
  }
  for (int i = 0; i < no; i++)
    for (int j = i + 1; j < no; j++)
      if (score[j] < score[i]) {
        swap(score[i], score[j]);
        swap(opts[i], opts[j]);
      }
  for (int i = 0; i < no; i++) {
    int c = opts[i];
    int old = vt[c];
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

static int staticMark[MAXN], staticCtr = 0;
static int sDist[MAXN];
static inline int otherHeadDist(int c) {
  return min(enemyDist[c], friendDist[c]);
}
static int staticSpace(const vector<int> &B, int cap) {
  staticCtr++;
  for (int c : B)
    if (c >= 0)
      staticMark[c] = staticCtr;
  int qh = 0, qt = 0;
  double cnt = 0;
  qA[qt++] = B[0];
  staticMark[B[0]] = staticCtr;
  sDist[B[0]] = 0;
  while (qh < qt && cnt < cap) {
    int c = qA[qh++];
    for (int d = 0; d < 4; d++) {
      int n = nbr[c * 4 + d];
      if (n < 0 || staticMark[n] == staticCtr ||
          (occId[n] && occId[n] != MY_ID + 1))
        continue;
      if (zoneE[n] || zoneF[n] || otherBT[n] > 0)
        continue;
      if (otherHeadDist(n) <= sDist[c] + 1)
        continue;
      staticMark[n] = staticCtr;
      sDist[n] = sDist[c] + 1;
      qA[qt++] = n;
      cnt += viewIndex[n] >= 0 ? 1.0 : radarExpire[n] > ROUND ? 0.0 : 0.5;
    }
  }
  return (int)cnt;
}

static bool endgame() { return ROUND >= 500 - P.endgameRounds; }

static double corridorRisk(const vector<int> &B) {
  if (B.size() < 2)
    return 0;
  stampCtr++;
  for (int c : B)
    if (c >= 0) {
      ownStamp[c] = stampCtr;
    }
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
      bool foreign = (occId[n] && occId[n] != MY_ID + 1) || otherBT[n] > 0;
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

// --- V8 SONAR PROTOCOL & ROLE DEFINITIONS ---
enum Role : uint8_t {
  ROLE_INDEPENDENT = 0,
  ROLE_QUEEN = 1,
  ROLE_SENTINEL = 2,
  ROLE_HELPER = 3,
  ROLE_FEEDER = 4
};
enum StatusFlags : uint16_t {
  FLAG_NONE = 0,
  FLAG_SEEKING = 1 << 0,
  FLAG_FEED_READY = 1 << 1,
  FLAG_BLOCKING = 1 << 2,
  FLAG_TRAPPED = 1 << 3
};

struct SonarSignal {
  Role role;
  int q_x, q_y, t_x, t_y, q_len, flags, id;
  uint64_t pack() const {
    return ((uint64_t)(role & 0xF) << 60) |
           ((uint64_t)(max(0, q_x) & 0xFF) << 52) |
           ((uint64_t)(max(0, q_y) & 0xFF) << 44) |
           ((uint64_t)(max(0, t_x) & 0xFF) << 36) |
           ((uint64_t)(max(0, t_y) & 0xFF) << 28) |
           ((uint64_t)(max(0, q_len) & 0xFFF) << 16) |
           ((uint64_t)(flags & 0xF) << 12) | ((uint64_t)(id & 0xFFF));
  }
  static SonarSignal unpack(uint64_t raw) {
    SonarSignal sig;
    sig.role = (Role)((raw >> 60) & 0xF);
    sig.q_x = (raw >> 52) & 0xFF;
    sig.q_y = (raw >> 44) & 0xFF;
    sig.t_x = (raw >> 36) & 0xFF;
    sig.t_y = (raw >> 28) & 0xFF;
    sig.q_len = (raw >> 16) & 0xFFF;
    sig.flags = (raw >> 12) & 0xF;
    sig.id = raw & 0xFFF;
    return sig;
  }
};

static vector<SonarSignal> active_claims;
static Role my_role = ROLE_INDEPENDENT;
static int flush_timer = 0;
static int stagnation_counter = 0;
static int last_head_cell = -1;

// --- TIER 1: VOLUMETRIC POCKET DENSITY BFS ---
static int calculate_pocket_capacity(int start_cell,
                                     int max_search_depth = 25) {
  static int visited_mark[MAXN], fill_ctr = 0;
  fill_ctr++;

  int q_head = 0, q_tail = 0;
  qA[q_tail++] = start_cell;
  visited_mark[start_cell] = fill_ctr;

  int free_tiles = 0;

  while (q_head < q_tail && q_head < max_search_depth) {
    int curr = qA[q_head++];
    for (int d = 0; d < 4; d++) {
      int neighbor = nbr[curr * 4 + d];
      if (neighbor < 0 || visited_mark[neighbor] == fill_ctr)
        continue;

      visited_mark[neighbor] = fill_ctr;

      if (occId[neighbor] && occId[neighbor] != MY_ID + 1)
        continue;
      if (otherBT[neighbor] > 0)
        continue;

      free_tiles++;
      qA[q_tail++] = neighbor;
    }
  }
  return free_tiles;
}

static bool is_chokepoint(int c) {
  if (c < 0)
    return false;
  int walls = 0;
  for (int d = 0; d < 4; d++) {
    int k = effK(c, d);
    if (k == 2 || k == 3)
      walls++;
  }
  return walls >= 2;
}

static Eval evaluate(const SimResult &s, bool deepAllowed) {
  if (elapsedMs() > 70)
    deepAllowed = false;
  Eval e;
  const vector<int> &B = s.body;
  int L = s.len;
  int head = B[0];
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
      if (otherBT[n] >= nd)
        continue;
      if (nd <= 1 && (zoneE[n] || zoneF[n]))
        continue;
      distA[n] = nd;
      qA[qt++] = n;
      space++;
      if (nd <= P.fieldCap) {
        double p = pearlProb(n, ROUND + nd);
        if (p > 0) {
          if (enemyDist[n] < nd)
            p *= swarm ? 0.8 : P.enemyCloser;
          else if (enemyDist[n] == nd)
            p *= swarm ? 0.9 : P.enemyTie;
          if (friendDist[n] < nd ||
              (friendDist[n] == nd && friendMinId[n] < MY_ID))
            p *= P.friendCloser;
          p *= farmBonus(n);

          if (my_role != ROLE_SENTINEL) {
            for (const auto &claim : active_claims) {
              if ((claim.flags & FLAG_SEEKING) && claim.t_x == (n % W) &&
                  claim.t_y == (n / W)) {
                p *= 0.15;
              }
            }
          }

          fsum += p * powG[nd];
          double v = p * powT[nd];
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
    int roomy = min(2 * L + 20, left + 1);
    int st = staticSpace(B, roomy);
    e.room = st;
    if (st >= roomy && (L < 20 || !deepAllowed)) {
      e.pDeath = 0;
      e.surv = 999;
      e.safeClass = 2;
    } else {
      int target = min(min(2 * L + 8, 90), left);
      double el = elapsedMs();
      long long budget = el > 55 ? 0 : el > 35 ? 1500 : 12000;
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
      e.pocket = 1.0 - (double)st / roomy;
    }
  }

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
  double greed = endgame() ? 0.35 : 1.0;
  if (L > capLen && !endgame()) {
    greed *= 0.3;
    if (growth > 0)
      growth *= -0.3;
  }
  double score = 0;
  score += growth * (endgame() ? 1.5 : 1.0);
  score += greed * (P.wField * fsum + P.wTarget * fmax);
  score += P.wHunt * hunt;
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
  bool cheap = UNITS >= 4 && L <= 4 && queen.id != MY_ID;
  bool miner = UNITS >= 3 && L <= 4 && queen.id != MY_ID && ROUND < P.mineUntil;
  score -= e.pDeath * (L + (miner ? 1.0 : cheap ? 3.0 : P.deathExtra));
  if (!miner)
    score -= P.wPocket * e.pocket * (2.0 + L / 4.0);
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
  e.corridor = miner ? 0.0 : corridorRisk(B);
  score -= e.corridor * (L / 2.0 + 10.0);
  e.score = score;
  bool riskOk =
      e.pDeath < 0.25 || miner || (cheap && !bigFeed && e.pDeath < 0.9);
  e.safeClass =
      (riskOk && !adjacentThreat && (!s.outside || (KM && e.safeClass > 0)))
          ? 1
          : 0;
  return e;
}

// --------------------------------------------------------------- decisions --

static string indicator;
static bool DEBUG = false;
static int debugFrom = 0, debugTo = -1;

static void dumpState() {
  if (!DEBUG || ROUND < debugFrom || ROUND > debugTo)
    return;
  int R = 7;
  int hx = body[0] % W, hy = body[0] / W;
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
        int bt = min(9, otherBT[c]);
        b = (char)('0' + bt);
      } else if (pearlNow(c))
        a = '*';
      else if (viewIndex[c] < 0)
        a = '?', b = seenR[c] >= 0 ? '.' : '?';
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
    if (UNITS >= 2 && endgame() && dr.estLen >= MY_LEN + 2)
      worth = true;
    if (desperate && !(endgame() && MY_LEN > dr.estLen))
      worth = true;
    if (!worth)
      continue;
    if (torusDist(body[0], dr.headCell) > P.attackMaxSteps)
      continue;
    int maxSteps = min(P.attackMaxSteps, MY_LEN - 1);
    vector<int> path;
    vector<int> found;
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
    vector<int> saved;
    for (int i = 0; i < MY_LEN - c; i++) {
      saved.push_back(otherBT[body[i]]);
      otherBT[body[i]] = 1000;
    }
    SimResult child;
    for (int i = MY_LEN - 1; i >= MY_LEN - c; i--)
      child.body.push_back(body[i]);
    child.len = c;
    int freeN = 0;
    for (int d = 0; d < 4; d++) {
      int n = nbr[child.body[0] * 4 + d];
      if (n >= 0 && !occId[n])
        freeN++;
    }
    double val = 0;
    if (freeN > 0) {
      Eval ce = evaluate(child, true);
      val = (1.0 - ce.pDeath) * c;
    }
    for (int i = 0; i < MY_LEN - c; i++)
      otherBT[body[i]] = saved[i];
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
        if (n < 0 || occId[n])
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

  // Tier 1 Check: Suppress budding if pocket capacity is saturated (< 8 free
  // tiles)
  if (my_role == ROLE_SENTINEL && calculate_pocket_capacity(body[0]) < 8) {
    return false;
  }

  bool narrow = KM && string(KM->name) == "autarky";
  int until =
      (bigFeed || narrow) ? P.budUntil : (UNITS < 40 ? 420 : P.budUntil);
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
      if (UNITS >= min(UNIT_LIMIT, 3))
        return false;
      if (MY_LEN < P.splitMinLen)
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
  int tail = body[MY_LEN - 1];
  int freeN = 0;
  for (int d = 0; d < 4; d++) {
    int n = nbr[tail * 4 + d];
    if (n < 0 || occId[n])
      continue;
    freeN++;
  }
  if (freeN == 0)
    return false;
  SimResult parent;
  parent.body.assign(body.begin(), body.begin() + (MY_LEN - c));
  parent.len = MY_LEN - c;
  Eval pe = evaluate(parent, false);
  if (pe.space < parent.len + 8 && !overlong)
    return false;
  SimResult child;
  for (int i = MY_LEN - 1; i >= MY_LEN - c; i--)
    child.body.push_back(body[i]);
  child.len = c;
  Eval ce = evaluate(child, false);
  if (ce.space < (overlong ? 4 : 12))
    return false;
  printf("SPLIT %d\n", c);
  indicator = "SPLIT";
  return true;
}

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
  active_claims.clear();
  bool distress_detected = false;
  int ready_feeders = 0;

  for (uint64_t v : V.msgs) {
    SonarSignal sig = SonarSignal::unpack(v);
    active_claims.push_back(sig);

    // Tier 3 Sonar Signal Evaluation
    if (sig.flags & FLAG_TRAPPED)
      distress_detected = true;
    if (sig.flags & FLAG_FEED_READY)
      ready_feeders++;

    if (sig.q_x >= 0 && sig.q_y >= 0 && sig.q_x < W && sig.q_y < H) {
      QueenInfo q;
      q.cell = sig.q_y * W + sig.q_x;
      q.len = sig.q_len;
      q.round = ROUND;
      q.id = sig.id;
      considerQueen(q);
    }
  }

  // Trigger Gateway Flush timer if distress is detected or 2+ feeders are
  // waiting
  if (distress_detected || ready_feeders >= 2) {
    flush_timer = 4;
  }

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
  return !bigFeed && ROUND >= P.protectFrom && queen.id == MY_ID && MY_LEN >= 6;
}
static bool outranks(int len, int id) {
  return len > MY_LEN || (len == MY_LEN && id < MY_ID);
}

static bool tryFeed() {
  bool is_feeder = (my_role == ROLE_FEEDER && (bigFeed || ROUND < 450));
  if (!is_feeder &&
      (ROUND < P.feedFrom || iAmQueen() || !outranks(queen.len, queen.id) ||
       ROUND - queen.round > 25))
    return false;
  if (queen.cell < 0 || torusDist(queen.cell, body[0]) > P.feedRadius)
    return false;
  for (auto &dr : others) {
    bool worthy = bigFeed ? (dr.id == queen.id || dr.estLen >= MY_LEN + 3)
                          : dr.estLen >= max(10, 2 * MY_LEN);
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

  // V8 ROLE ASSIGNMENT
  my_role = (MY_ID == 0 || iAmQueen()) ? ROLE_QUEEN : ROLE_INDEPENDENT;
  if (my_role != ROLE_QUEEN) {
    if (MY_LEN >= 6 && is_chokepoint(body[0]))
      my_role = ROLE_SENTINEL;
    else if (MY_LEN == 2 && queen.cell >= 0)
      my_role = ROLE_HELPER;
    else if (MY_LEN >= 4 && MY_LEN < 6 && queen.cell >= 0)
      my_role = ROLE_FEEDER;
  }

  // Tier 2: Helper Stagnation Tracking
  if (!body.empty()) {
    if (body[0] == last_head_cell) {
      stagnation_counter++;
    } else {
      stagnation_counter = 0;
    }
    last_head_cell = body[0];
  }

  // Tier 4: Emergency Self-Sacrifice Fallback
  if (my_role == ROLE_HELPER && stagnation_counter >= 8) {
    printf("SPLIT 1\n");
    indicator = "EMERGENCY_DESPAWN";
    return;
  }

  if (tryFeed())
    return;
  dumpState();
  chosenCells.clear();

  {
    goalCell = -1;
    goalDistNow = -1;
    SimResult here;
    here.body = body;
    here.len = MY_LEN;
    recordVals = true;
    Eval he = evaluate(here, false);
    recordVals = false;
    int best = he.targetCell;
    int g = best;
    if (lastGoal >= 0 && lastGoal != best && best >= 0 && distA[lastGoal] > 0 &&
        valT[lastGoal] >= 0.75 * valT[best])
      g = lastGoal;
    if (g >= 0 && distA[g] > 0) {
      goalCell = g;
      goalDistNow = distA[g];
    }
    feeding = ROUND >= P.feedFrom && !iAmQueen() &&
              (bigFeed ? outranks(queen.len, queen.id)
                       : queen.len >= max(10, 2 * MY_LEN)) &&
              ROUND - queen.round <= 25 && queen.cell >= 0 &&
              torusDist(queen.cell, body[0]) <= P.feedRadius;
    if (feeding && queen.cell >= 0 && distA[queen.cell] != 0) {
      int qd = distA[queen.cell];
      if (qd < 0) {
        for (int d = 0; d < 4; d++) {
          int n = nbr[queen.cell * 4 + d];
          if (n >= 0 && distA[n] > 0 && (qd < 0 || distA[n] < qd))
            qd = distA[n], g = n;
        }
      } else
        g = queen.cell;
      if (qd > 0) {
        goalCell = g;
        goalDistNow = qd;
      }
    }

    // V8 Role Goal Overrides & Sentinel Gateway Flushing Protocol
    if (my_role == ROLE_SENTINEL) {
      if (flush_timer > 0) {
        flush_timer--;
        indicator = "FLUSHING_GATE";
        // Step aside from the choke anchor during flush mode
      } else {
        goalCell = body[0];
        goalDistNow = 0;
        if (swarmSplit())
          return; // Pop Helper into pocket if space permits
      }
    } else if (my_role == ROLE_FEEDER && (bigFeed || ROUND < 450)) {
      goalCell = queen.cell;
      goalDistNow =
          (queen.cell >= 0 && distA[queen.cell] >= 0) ? distA[queen.cell] : -1;
      feeding = true;
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
  if (MY_LEN >= 8 && !endgame()) {
    bool anyThreat = threat;
    if (anyThreat) {
      for (int a = 0; a < 4; a++)
        for (int b = 0; b < 4; b++) {
          if (b == opp(a))
            continue;
          Opt o;
          o.dirs = {a, b};
          o.sim = simulate(o.dirs);
          if (!o.sim.dead)
            opts.push_back(o);
        }
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
  if (DEBUG && ROUND >= debugFrom && ROUND <= debugTo)
    for (auto &o : opts) {
      string m;
      for (int d : o.dirs)
        m += DCH[d];
      printf("LOG opt %s cls%d sc%.2f pd%.2f surv%d rm%d dg%.2f f%.2f t%.2f "
             "cor%.2f out%d len%d\n",
             m.c_str(), o.ev.safeClass, o.ev.score, o.ev.pDeath, o.ev.surv,
             o.ev.room, o.ev.danger, o.ev.field, o.ev.target, o.ev.corridor,
             (int)o.sim.outside, o.sim.len);
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
    emitMove(o.dirs, o.sim.cells);
    char tmp[96];
    snprintf(tmp, sizeof tmp, "L%d s%.1f sp%d rm%d f%.2f t%.2f dg%.2f pd%.2f%s",
             MY_LEN, o.ev.score, o.ev.space, o.ev.room, o.ev.field, o.ev.target,
             o.ev.danger, o.ev.pDeath, KM ? " K" : "");
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

// V8 64-BIT SONAR BROADCASTER
static void castRadar() {
  lastRay.clear();
  SonarSignal sig;
  sig.role = my_role;
  sig.q_x = queen.cell >= 0 ? queen.cell % W : -1;
  sig.q_y = queen.cell >= 0 ? queen.cell / W : -1;
  sig.t_x = goalCell >= 0 ? goalCell % W : -1;
  sig.t_y = goalCell >= 0 ? goalCell / W : -1;
  sig.q_len = queen.len;
  sig.id = MY_ID;
  sig.flags = FLAG_NONE;
  if (goalCell >= 0)
    sig.flags |= FLAG_SEEKING;
  if (my_role == ROLE_SENTINEL)
    sig.flags |= FLAG_BLOCKING;
  if (my_role == ROLE_FEEDER)
    sig.flags |= FLAG_FEED_READY;

  // Broadcast distress signal if trapped
  if (my_role == ROLE_HELPER && stagnation_counter >= 3) {
    sig.flags |= FLAG_TRAPPED;
  }

  uint64_t v = sig.pack();

  int head = body.empty() ? -1 : body[0];
  int dir = MY_DIR;
  if (!chosenCells.empty()) {
    head = chosenCells.back();
    int prev =
        chosenCells.size() >= 2 ? chosenCells[chosenCells.size() - 2] : body[0];
    for (int d = 0; d < 4; d++)
      if (nbr[prev * 4 + d] == head)
        dir = d;
  }
  if (head >= 0) {
    int c = head;
    for (int k = 0; k < W + H; k++) {
      c = nbr[c * 4 + dir];
      if (c < 0)
        break;
      lastRay.push_back(c);
    }
  }

  for (int d = 0; d < 4; d++)
    printf("SONAR %c %llu\n", DCH[d], (unsigned long long)v);
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