// Viper V8 -- V7.12 generalised for unseen maps.
//
// On top of V7.12: online symmetry and pearl-gap learning, terrain classification by
// similarity to the known maps, encrypted sonar packets (status, queen, enemy giant,
// fountains) on all four rays with per-ray echo attribution, adaptive phase timing,
// a saturation queen, local budding, late queen hunts, lane safety, a two-ply fork check
// in the head-on model, and endgame length management. Every addition has a switch in
// Params so it can be ablated.
//
// Each dragon runs its own copy of this program. Per turn it:
//   1. parses the 7x7 view and folds it into a persistent map memory
//      (edges, portals, pearl countdowns), optionally seeded by a validated
//      copy of a known map;
//   2. rebuilds its own body (vision chain + tracked history) and the visible
//      bodies of every other dragon, with the turn at which each cell frees;
//   3. looks for a guaranteed head-on trade (enemy heads do not move during our
//      turn, so any enemy head within sprint reach can be hit for certain);
//   4. considers a split;
//   5. scores every legal move (and escape sprints) by growth, a pearl value
//      field over time-aware BFS distances, head-on danger, and survival
//      (flood fill, then an exact DFS over our own body when space is tight).

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
#if __has_include("blind_cfg.hpp")
#include "blind_cfg.hpp"
#endif
#ifdef NO_MAP_DB
static const int N_IDENT_MAPS = 0;   // test build: play every map as if unseen
#else
static const int N_IDENT_MAPS = N_KNOWN_MAPS;
#endif

using namespace std;

// ---------------------------------------------------------------- tunables --

struct Params {
    // pearl field
    double gamma = 0.86;         // per-step discount of pearl value
    double wField = 0.22;        // weight of the discounted pearl sum
    double wTarget = 1.6;        // weight of the single best pearl
    double decayTau = 70.0;      // rounds for a remembered pearl to be presumed eaten
    int fieldCap = 90;           // BFS depth that still contributes to the field
    // competition discounts
    double enemyCloser = 0.55, enemyTie = 0.8, friendCloser = 0.08;
    // danger (probability an enemy head at distance d attacks)
    double p1 = 0.85, p2 = 0.15, p3 = 0.03, p2Drone = 0.40, p3Drone = 0.10;
    // death penalty on top of our own length
    double deathExtra = 30.0;
    double spaceBonus = 0.6;
    double wPocket = 1.5;
    // attacks
    int attackMargin = 2;        // enemy must be this much longer than us
    int attackMaxSteps = 4;
    // hunting (small dragons steer towards big enemy heads)
    double wProgress = 0.8;     // per step of progress towards the committed goal
    int budAt = 4;              // swarm: split a length-2 child off at this length
    int mineUntil = 300;
    double minerGamma = 0.80;   // miners judge targets on a short horizon: eat what is near
    double minerFarmCap = 1.5;        // greedy mining only while the swarm is still expanding
    int budUntil = 300;         // stop budding late so the dragons grow for the tiebreak
    int feedFrom = 350;
    int endFeedFrom = 440;      // maze maps: from here drones also feed a queen only slightly longer than them
    int feedRadius = 10;        // only drones this close to the queen feed; the rest keep foraging
    int protectFrom = 400;      // from here the longest dragon never splits voluntarily         // from here, small dragons feed themselves to the queen
    int gossipFrom = 300;       // sonar gossip of the queen's position (disables the radar)
    int huntMaxLen = 5;
    double wHunt = 2.2;
    // splitting
    int splitMinLen = 24;
    int splitChild = 6;         // 0 = split in half
    int splitRoundMax = 300;
    // endgame: rounds before the end where greed stops mattering
    int endgameRounds = 25;

    // V8 switches
    bool fOnlineSym = true, fGapLearn = true, fTerrain = true, fPhase = true, fTerritory = true,
         fSatQueen = true, fLocalBud = true, fHunt = true, fCorridor = true, fEchoAll = true,
         fMoveOrder = true, fDieNearFriends = true, fSprintGain = true, fLookahead = true,
         fReadEnemy = true, fReserves = true, fEndLen = true;
    int huntRadius = 24;
    int endLenFrom = 470;
    // corridor maps (many tiles with <= 2 open sides): miners die in dead ends and the swarm stalls
    bool fNarrowMiner = true, fEarlyPocket = true, fLowUnitBud = true;
    double narrowFracMin = 0.25;
    double narrowMinerCost = 3.0;  // miner death cost on a narrow maze map, instead of 1
    int earlyPocketLen = 4;        // dragons this long weigh dead-end pockets from round 0, miners included
    int lowUnits = 15;             // below this many units, non-queens keep budding past the queen round
    int bud4Until = 150;           // before this round always bud at 4
    // a dead end too short to grow in is a plain death, not a cheap dive
    bool fTrapGuard = true;
    // short-sighted drones still value tiles respawning within rushGap rounds at the long horizon
    bool fFountRush = true;
    int rushGap = 2;
    // the lowest-id starting dragons look far (and ignore territory) until scoutUntil
    bool fScouts = true;
    int nScouts = 2;
    int scoutUntil = 60;
    double wScoutProgress = 3.0;   // like a hunt: nearby pearls must not pull a scout off its way
};
static Params P;

// ------------------------------------------------------------------- basics --

static const int MAXN = 64 * 64;
static const int DX[4] = {0, 1, 0, -1};
static const int DY[4] = {-1, 0, 1, 0};
static const char DCH[4] = {'N', 'E', 'S', 'W'};
static inline int opp(int d) { return d ^ 2; }

static int W, H, N, MY_ID, UNIT_LIMIT, MY_TEAM;  // team 0 = A, 1 = B
static int ROUND, MY_DIR, MY_LEN, UNITS;
static int ECHO[5];  // kelp, ally, ally head, enemy, enemy head (from last turn's sonar)

static inline int stepRaw(int c, int d) {
    int x = c % W + DX[d], y = c / W + DY[d];
    if (x < 0) x += W; else if (x >= W) x -= W;
    if (y < 0) y += H; else if (y >= H) y -= H;
    return y * W + x;
}
static inline int torusDist(int a, int b) {
    int dx = abs(a % W - b % W), dy = abs(a / W - b / W);
    return min(dx, W - dx) + min(dy, H - dy);
}

static chrono::steady_clock::time_point T0;
static double elapsedMs() {
    return chrono::duration<double, milli>(chrono::steady_clock::now() - T0).count();
}

// -------------------------------------------------------------------- input --

static char buf[1 << 16];
static bool nextLine() {
    while (fgets(buf, sizeof buf, stdin)) {
        char* p = buf;
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
        if (*p) return true;
    }
    return false;
}
static char* skipWord(char* p) {
    while (*p == ' ' || *p == '\t') p++;
    while (*p && *p != ' ' && *p != '\t' && *p != '\n' && *p != '\r') p++;
    return p;
}
static long long labelled() { return strtoll(skipWord(buf), nullptr, 10); }
static int dirOf(char c) { return c == 'N' ? 0 : c == 'E' ? 1 : c == 'S' ? 2 : 3; }

struct Part { int team, id, cell, face; bool head; };

// edge codes from the protocol: 1 open, 2 kelp, 3 portal (pid separately)
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
static int viewIndex[MAXN];  // cell -> index into view, -1 outside (valid for this turn)

static void parseEdgeTok(char*& p, int& kind, int& pid) {
    while (*p == ' ' || *p == '\t') p++;
    if (*p == '.') { kind = 1; pid = -1; p++; }
    else if (*p == 'w') { kind = 2; pid = -1; p++; }
    else { kind = 3; pid = (int)strtol(p, &p, 10); }
}

static bool readTurn() {
    if (!nextLine()) return false;
    if (strncmp(buf, "ENDGAME", 7) == 0) return false;
    ROUND = (int)labelled();
    nextLine(); { char* p = skipWord(buf); while (*p == ' ') p++; MY_DIR = dirOf(*p); }
    nextLine(); MY_LEN = (int)labelled();
    nextLine(); UNITS = (int)labelled();
    nextLine(); int nm = (int)labelled();
    V.msgs.clear();
    for (int i = 0; i < nm; i++) { nextLine(); V.msgs.push_back(strtoull(buf, nullptr, 10)); }
    nextLine();
    for (int k = 0; k < 5; k++) ECHO[k] = 0;
    if (strncmp(buf, "ECHOES", 6) == 0) {
        char* p = skipWord(buf);
        for (int k = 0; k < 5; k++) ECHO[k] = (int)strtol(p, &p, 10);
        nextLine();
    }
    for (int i = 0; i < 49; i++) {
        if (i) nextLine();
        char* p = buf;
        int x = (int)strtol(p, &p, 10), y = (int)strtol(p, &p, 10);
        int hp = (int)strtol(p, &p, 10), pt = (int)strtol(p, &p, 10);
        V.cell[i] = y * W + x; V.pearl[i] = hp == 1; V.ptime[i] = pt;
    }
    nextLine(); int nb = (int)labelled();
    V.parts.clear();
    for (int i = 0; i < nb; i++) {
        nextLine();
        char* p = buf; while (*p == ' ') p++;
        Part q; q.team = (*p == 'A') ? 0 : 1; p++;
        q.id = (int)strtol(p, &p, 10);
        int x = (int)strtol(p, &p, 10), y = (int)strtol(p, &p, 10);
        while (*p == ' ') p++;
        q.face = dirOf(*p); p++;
        q.head = strtol(p, &p, 10) == 1;
        q.cell = y * W + x;
        V.parts.push_back(q);
    }
    for (int y = 0; y < 8; y++) {
        nextLine(); char* p = buf;
        for (int x = 0; x < 7; x++) {
            int k, pid; parseEdgeTok(p, k, pid);
            if (y < 7) { V.ek[y * 7 + x][0] = k; V.ep[y * 7 + x][0] = pid; }
            if (y > 0) { V.ek[(y - 1) * 7 + x][2] = k; V.ep[(y - 1) * 7 + x][2] = pid; }
        }
    }
    for (int y = 0; y < 7; y++) {
        nextLine(); char* p = buf;
        for (int x = 0; x < 8; x++) {
            int k, pid; parseEdgeTok(p, k, pid);
            if (x < 7) { V.ek[y * 7 + x][3] = k; V.ep[y * 7 + x][3] = pid; }
            if (x > 0) { V.ek[y * 7 + x - 1][1] = k; V.ep[y * 7 + x - 1][1] = pid; }
        }
    }
    return true;
}

// ---------------------------------------------------------------- knowledge --

static int8_t obsK[MAXN * 4];  // 0 unknown, 1 open, 2 kelp, 3 portal
static int obsP[MAXN * 4];
static const KnownMap* KM = nullptr;
static vector<int8_t> mapK;
static vector<int> mapP;
static int SYM = -1;           // 0 flip x, 1 flip y, 2 rotate; from KM or learnt online
static inline int mirrorCellS(int c, int s) {
    int x = c % W, y = c / W;
    if (s == 0) x = W - 1 - x;
    else if (s == 1) y = H - 1 - y;
    else { x = W - 1 - x; y = H - 1 - y; }
    return y * W + x;
}
static inline int mirrorCell(int c) { return mirrorCellS(c, SYM); }
// direction d at c maps to this direction at the mirror tile
static inline int mirrorDirS(int d, int s) {
    if (s == 0) return (d == 1 || d == 3) ? opp(d) : d;
    if (s == 1) return (d == 0 || d == 2) ? opp(d) : d;
    return opp(d);
}
static int nbr[MAXN * 4];      // destination, -1 blocked
static int degS[MAXN];         // open static exits of a tile (kelp only; dragons ignored)
static bool nbrDirty = true;

struct Candidate { int idx; vector<int8_t> k; vector<int> p; };
static vector<Candidate> mapCands;
static bool mapResolved = false;

static void loadMapLayer(const KnownMap& m, vector<int8_t>& k, vector<int>& p) {
    k.assign(N * 4, 1);
    p.assign(N * 4, -1);
    for (int i = 0; i < m.n_edges; i++) {
        int c = m.edges[4 * i], d = m.edges[4 * i + 1], kind = m.edges[4 * i + 2], pid = m.edges[4 * i + 3];
        int kk = kind == 1 ? 2 : 3;
        int o = stepRaw(c, d);
        k[c * 4 + d] = kk; p[c * 4 + d] = pid;
        k[o * 4 + opp(d)] = kk; p[o * 4 + opp(d)] = pid;
    }
}

static inline int effK(int c, int d) {
    int k = obsK[c * 4 + d];
    if (k) return k;
    if (KM) return mapK[c * 4 + d];
    if (SYM >= 0) {
        // the mirror edge: kelp and open carry over; a portal's partner is unknown
        int mk = obsK[mirrorCell(c) * 4 + mirrorDirS(d, SYM)];
        if (mk == 1 || mk == 2) return mk;
    }
    return 0;
}
static inline int effP(int c, int d) {
    if (obsK[c * 4 + d]) return obsP[c * 4 + d];
    if (KM) return mapP[c * 4 + d];
    return -1;
}

static void rebuildNbr() {
    unordered_map<int, vector<int>> portals;
    for (int c = 0; c < N; c++) {
        for (int d = 0; d < 4; d++) {
            int k = effK(c, d);
            if (k == 2) nbr[c * 4 + d] = -1;
            else if (k == 3) {
                nbr[c * 4 + d] = -1;
                int code = (d == 1 || d == 2) ? c * 4 + d : stepRaw(c, d) * 4 + opp(d);
                auto& v = portals[effP(c, d)];
                if (find(v.begin(), v.end(), code) == v.end()) v.push_back(code);
            } else nbr[c * 4 + d] = stepRaw(c, d);
        }
    }
    for (auto& kv : portals) {
        if (kv.second.size() != 2) continue;
        int a1 = kv.second[0] / 4, d1 = kv.second[0] % 4;
        int a2 = kv.second[1] / 4, d2 = kv.second[1] % 4;
        if (d1 != d2) continue;
        int b1 = stepRaw(a1, d1), b2 = stepRaw(a2, d1);
        nbr[a1 * 4 + d1] = b2; nbr[b1 * 4 + opp(d1)] = a2;
        nbr[a2 * 4 + d1] = b1; nbr[b2 * 4 + opp(d1)] = a1;
    }
    for (int c = 0; c < N; c++) {
        int k = 0;
        for (int d = 0; d < 4; d++) if (nbr[c * 4 + d] >= 0) k++;
        degS[c] = k;
    }
    nbrDirty = false;
}

// pearl memory
static int seenR[MAXN];
static bool pearlSeen[MAXN];
static int spawnAt[MAXN];      // absolute round of next spawn attempt; -1 never; -2 unknown
static int mirSpawn[MAXN];     // spawn round learnt from the mirror tile; -2 unknown
static int gmin[MAXN], gmax[MAXN];  // -1 unknown
static int memExpire[MAXN];   // round until which an unseen cell is presumed still occupied
static int maxEnemyId = -1;   // enemies that split constantly run into high ids
static bool swarm = false;
static int radarExpire[MAXN]; // an enemy was echoed somewhere on a ray through this unseen cell
static int laneExpire[MAXN];  // an ally head faces us somewhere down a ray through this unseen cell
static int friendExpire[MAXN];// an ally body was echoed on a ray through this unseen cell
// online knowledge that the known-map database would otherwise supply
static bool tileSeen[MAXN];   // all four edges of this tile have been observed
static bool neverSp[MAXN];    // observed countdown -1
static int lrnMin[MAXN], lrnMax[MAXN], lrnN[MAXN];  // sampled pearl gaps
static bool symBad[3];
static int symEv[3];

static void detectSymmetry() {
    SYM = -1;
    for (int s = 0; s < 3 && SYM < 0; s++) {
        SYM = s;
        bool ok = true;
        for (int c = 0; c < N && ok; c++) {
            int m = mirrorCell(c);
            if (KM->gaps[2 * c] != KM->gaps[2 * m] || KM->gaps[2 * c + 1] != KM->gaps[2 * m + 1]) ok = false;
        }
        if (!ok) SYM = -1;
    }
}

// ------------------------------------------------------------ map class --
// The macro depends on the kind of map. On the ten live maps the choice was measured on the
// ladder; any other map takes the choice of the live map it resembles most, by terrain
// features computed from what the swarm has seen.
static bool bigFeed = false;  // aggressive (v7.2-style) consolidation on this map
static bool farSight = false; // keep long-range miner targets (ladder panel: short sight lost Dilemma)
static int mapMode = 0;       // 0 unclassified (maze defaults), 1 maze, 2 big feed, 3 maze + far sight
static double narrowFrac = 0; // share of tiles with at most 2 open sides (known map, else as seen)
static int modeConf = 0;      // 0..3, 3 = map identified
static const int NFEAT = 6;
struct RefMap { const char* name; int mode; double f[NFEAT]; };
static vector<RefMap> refs;

static int modeOfName(const string& nm) {
    // measured on the ladder and in v7.2 vs v7.3: feeding wins Portals, Slithery Fight, Schooltime
    if (nm == "portals" || nm == "slithery_fight" || nm == "schooltime") return 2;
    if (nm == "dilemma") return 3;
    if (nm == "trophy" || nm == "queen_of_spades" || nm == "default" || nm == "autarky" || nm == "devil" ||
        nm == "trauma") return 1;
    return 0;  // not a live map: no measured choice
}
static void setMode(int m, int conf) {
    if (m <= 0) return;
    mapMode = m; modeConf = conf;
    bigFeed = m == 2;
    farSight = m == 3;
}
// features: log area, narrow tiles, kelp edges, portal edges, never-spawn tiles, fast tiles
static void featuresOf(int nTiles, int narrow, int kelpE, int knownE, int portalE, int never, int gapT, int fast,
                       double area, double* f) {
    f[0] = log2(max(1.0, area));
    f[1] = nTiles ? (double)narrow / nTiles : 0;
    f[2] = knownE ? (double)kelpE / knownE : 0;
    f[3] = nTiles ? (double)portalE / nTiles : 0;
    f[4] = nTiles ? (double)never / nTiles : 0;
    f[5] = gapT >= 20 ? (double)fast / gapT : -1;
}
static const double FSCALE[NFEAT] = {1.0, 0.08, 0.06, 0.03, 0.15, 0.04};
static void buildRefs() {
    for (int i = 0; i < N_KNOWN_MAPS; i++) {
        const KnownMap& m = KNOWN_MAPS[i];
        int md = modeOfName(m.name);
        if (!md) continue;
#ifdef NO_MAP_DB
        if (m.w == W && m.h == H) continue;  // the test build must not recognise the map by its size
#endif
        int n = m.w * m.h;
        vector<int8_t> k(n * 4, 1);
        int portalE = 0, kelpE = 0;
        for (int e = 0; e < m.n_edges; e++) {
            int c = m.edges[4 * e], d = m.edges[4 * e + 1], kind = m.edges[4 * e + 2];
            int x = c % m.w + DX[d], y = c / m.w + DY[d];
            x = (x + m.w) % m.w; y = (y + m.h) % m.h;
            int o = y * m.w + x;
            int kk = kind == 1 ? 2 : 3;
            k[c * 4 + d] = kk; k[o * 4 + opp(d)] = kk;
        }
        int narrow = 0, never = 0, fast = 0, gapT = 0;
        for (int c = 0; c < n; c++) {
            int open = 0;
            for (int d = 0; d < 4; d++) {
                if (k[c * 4 + d] == 2) kelpE++;
                else if (k[c * 4 + d] == 3) portalE++;
                if (k[c * 4 + d] != 2) open++;
            }
            if (open <= 2) narrow++;
            int hi = m.gaps[2 * c + 1];
            if (hi == 0) never++;
            else { gapT++; if (hi <= 3) fast++; }
        }
        RefMap r; r.name = m.name; r.mode = md;
        featuresOf(n, narrow, kelpE, n * 4, portalE, never, gapT, fast, n, r.f);
        refs.push_back(r);
    }
}
static int featTick = -100;
static void classifyOnline() {
    if (!P.fTerrain || modeConf >= 3 || ROUND >= 280 || ROUND - featTick < 8) return;
    featTick = ROUND;
    int nTiles = 0, narrow = 0, kelpE = 0, knownE = 0, portalE = 0, never = 0, gapT = 0, fast = 0;
    for (int c = 0; c < N; c++) {
        if (!tileSeen[c]) continue;
        nTiles++;
        int open = 0;
        for (int d = 0; d < 4; d++) {
            int k = obsK[c * 4 + d];
            knownE++;
            if (k == 2) kelpE++; else { open++; if (k == 3) portalE++; }
        }
        if (open <= 2) narrow++;
        if (neverSp[c]) never++;
        else if (lrnN[c] > 0) { gapT++; if (lrnMax[c] <= 3) fast++; }
    }
    int conf = nTiles < 60 ? 0 : nTiles < N / 6 ? 1 : 2;
    if (conf == 0 || conf < modeConf || refs.empty()) return;
    double f[NFEAT];
    featuresOf(nTiles, narrow, kelpE, knownE, portalE, never, gapT, fast, N, f);
    narrowFrac = f[1];
    double best = 1e18; int bm = 0;
    for (auto& r : refs) {
        double s = 0;
        for (int i = 0; i < NFEAT; i++) {
            if (f[i] < 0 || r.f[i] < 0) continue;
            double z = (f[i] - r.f[i]) / FSCALE[i];
            s += z * z;
        }
        if (s < best) { best = s; bm = r.mode; }
    }
    setMode(bm, conf);
}

static void activateMap(int idx, vector<int8_t>&& k, vector<int>&& p) {
    KM = &KNOWN_MAPS[idx];
    {
        int md = modeOfName(KM->name);
        if (md) setMode(md, 3);
    }
    mapK = std::move(k); mapP = std::move(p);
    int narrow = 0;
    for (int c = 0; c < N; c++) {
        int open = 0;
        for (int d = 0; d < 4; d++) if (mapK[c * 4 + d] != 2) open++;
        if (open <= 2) narrow++;
    }
    narrowFrac = (double)narrow / N;
    for (int c = 0; c < N; c++) { gmin[c] = KM->gaps[2 * c]; gmax[c] = KM->gaps[2 * c + 1]; }
    detectSymmetry();
    nbrDirty = true;
}
static void dropMap() {
    KM = nullptr; SYM = -1;
    for (int c = 0; c < N; c++) {
        gmin[c] = gmax[c] = -1;
        if (lrnN[c] > 0) { gmin[c] = lrnMin[c]; gmax[c] = lrnMax[c]; }
        else if (neverSp[c]) gmin[c] = gmax[c] = 0;
    }
    if (modeConf >= 3) modeConf = 0;
    nbrDirty = true;
}

static bool viewAgrees(const vector<int8_t>& k, const vector<int>& p, const uint16_t* gaps) {
    for (int i = 0; i < 49; i++) {
        int c = V.cell[i];
        for (int d = 0; d < 4; d++) {
            int vk = V.ek[i][d];
            if (k[c * 4 + d] != vk) return false;
            if (vk == 3 && p[c * 4 + d] != V.ep[i][d]) return false;
        }
        int hi = gaps[2 * c + 1];
        if ((V.ptime[i] < 0) != (hi == 0)) return false;
        if (V.ptime[i] > hi && hi > 0) return false;
    }
    return true;
}

static void initKnowledge() {
    N = W * H;
    memset(obsK, 0, sizeof obsK);
    for (int c = 0; c < N; c++) {
        seenR[c] = -1; pearlSeen[c] = false; spawnAt[c] = -2; mirSpawn[c] = -2; memExpire[c] = 0; radarExpire[c] = 0;
        laneExpire[c] = 0; friendExpire[c] = 0;
        tileSeen[c] = false; neverSp[c] = false; lrnMin[c] = 1 << 20; lrnMax[c] = -1; lrnN[c] = 0;
        gmin[c] = gmax[c] = -1;
    }
    buildRefs();
    for (int i = 0; i < N_IDENT_MAPS; i++) {
        if (KNOWN_MAPS[i].w != W || KNOWN_MAPS[i].h != H) continue;
        Candidate cd; cd.idx = i;
        loadMapLayer(KNOWN_MAPS[i], cd.k, cd.p);
        mapCands.push_back(std::move(cd));
    }
    if (mapCands.empty()) mapResolved = true;
}

static void learnOne(int c, int lo, int hi) {
    lrnMin[c] = min(lrnMin[c], lo); lrnMax[c] = max(lrnMax[c], hi); lrnN[c]++;
    if (!KM) { gmin[c] = lrnMin[c]; gmax[c] = lrnMax[c]; }
}
static void learnGap(int c, int g) {
    learnOne(c, g, g);
    if (SYM >= 0) { int m = mirrorCell(c); if (m != c) learnOne(m, g, g); }
}
static void setSym(int s) {
    SYM = s;
    nbrDirty = true;
    for (int c = 0; c < N; c++) {
        int m = mirrorCell(c);
        if (m == c) continue;
        if (lrnN[c] > 0 && lrnN[m] == 0) learnOne(m, lrnMin[c], lrnMax[c]);
        if (neverSp[c] && !KM && gmax[m] < 0) gmin[m] = gmax[m] = 0;
    }
}
// Maps are mirrored or rotated, and mirror tiles share one countdown: every pair of
// observations either keeps a symmetry possible or rules it out.
static void updateSymmetry() {
    for (int s = 0; s < 3; s++) {
        if (symBad[s]) continue;
        for (int i = 0; i < 49 && !symBad[s]; i++) {
            int c = V.cell[i], m = mirrorCellS(c, s);
            if (m == c) continue;
            int j = viewIndex[m];
            if (j >= 0) {
                if (V.ptime[i] != V.ptime[j]) symBad[s] = true; else symEv[s]++;
                continue;
            }
            if (!tileSeen[m]) continue;
            if (neverSp[m] != (V.ptime[i] < 0)) { symBad[s] = true; break; }
            for (int d = 0; d < 4; d++) {
                int km = obsK[m * 4 + mirrorDirS(d, s)], kc = V.ek[i][d];
                if ((km == 2) != (kc == 2) || (km == 3) != (kc == 3)) { symBad[s] = true; break; }
            }
            if (symBad[s]) break;
            symEv[s]++;
            if (V.ptime[i] >= 0 && spawnAt[m] > ROUND && seenR[m] >= ROUND - 60) {
                if (spawnAt[m] != ROUND + V.ptime[i]) symBad[s] = true; else symEv[s] += 3;
            }
        }
    }
    if (SYM >= 0 && symBad[SYM]) { SYM = -1; nbrDirty = true; }
    if (SYM < 0) {
        int alive = 0, s1 = -1;
        for (int s = 0; s < 3; s++) if (!symBad[s]) { alive++; s1 = s; }
        if (alive == 1 && symEv[s1] >= 12) setSym(s1);
    }
}

static void absorbView() {
    for (int c = 0; c < N; c++) viewIndex[c] = -1;
    for (int i = 0; i < 49; i++) viewIndex[V.cell[i]] = i;

    // map identification / validation
    if (!mapResolved) {
        vector<Candidate> keep;
        for (auto& cd : mapCands)
            if (viewAgrees(cd.k, cd.p, KNOWN_MAPS[cd.idx].gaps)) keep.push_back(std::move(cd));
        mapCands = std::move(keep);
        if (mapCands.size() == 1) {
            mapResolved = true;
            activateMap(mapCands[0].idx, std::move(mapCands[0].k), std::move(mapCands[0].p));
            mapCands.clear();
        } else if (mapCands.empty()) mapResolved = true;
    } else if (KM) {
        if (!viewAgrees(mapK, mapP, KM->gaps)) dropMap();
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
        tileSeen[c] = true;
        // a countdown that reset since we last looked reveals one draw from the tile's gap
        if (P.fGapLearn && V.ptime[i] > 0 && seenR[c] >= 0 && ROUND - seenR[c] <= 12 && spawnAt[c] >= 0 &&
            spawnAt[c] <= ROUND) {
            int g = V.ptime[i] + (ROUND - spawnAt[c]);
            if (g >= 1 && g <= 1000) learnGap(c, g);
        }
        seenR[c] = ROUND;
        pearlSeen[c] = V.pearl[i];
        spawnAt[c] = V.ptime[i] < 0 ? -1 : ROUND + V.ptime[i];
        if (V.ptime[i] < 0) neverSp[c] = true;
        if (V.ptime[i] < 0 && gmax[c] < 0) { gmax[c] = 0; gmin[c] = 0; }
    }
    if (P.fOnlineSym && !KM) updateSymmetry();
    if (SYM >= 0) {
        for (int i = 0; i < 49; i++) {
            int m = mirrorCell(V.cell[i]);
            if (viewIndex[m] < 0 && V.ptime[i] >= 0) mirSpawn[m] = ROUND + V.ptime[i];
        }
    }
    if (nbrDirty) rebuildNbr();
}

// probability that a pearl sits on c when we arrive at round T
static double pearlProb(int c, int T) {
    int now = ROUND;
    if (seenR[c] == now) {
        if (pearlSeen[c]) return 1.0;
        int sa = spawnAt[c];
        if (sa < 0) return 0.0;
        if (sa <= T) return 0.9;
        if (sa - T <= 2) return 0.25;
        return 0.0;
    }
    double p = 0.0;
    if (seenR[c] >= 0) {
        int age = now - seenR[c];
        if (pearlSeen[c]) p = exp(-age / P.decayTau);
        int sa = spawnAt[c];
        if (sa == -1 && !pearlSeen[c]) return 0.0;
        if (sa >= 0 && sa <= T) {
            double q = 0.85 * exp(-max(0, now - sa) / P.decayTau);
            p = max(p, q);
            if (gmax[c] > 0) {  // renewals after the first known spawn
                double mean = 0.5 * (gmin[c] + gmax[c]);
                double r = 1.0 - exp(-(T - sa) / max(1.0, mean)) ;
                p = max(p, 0.6 * r * exp(-mean / (2 * P.decayTau)));
            }
        }
        return p;
    }
    // never seen
    int sa = mirSpawn[c];
    if (gmax[c] == 0) return 0.0;
    if (sa >= 0) return sa <= T ? 0.7 * exp(-max(0, now - sa) / P.decayTau) : 0.0;
    if (gmax[c] > 0) {
        double lo = gmin[c], hi = gmax[c];
        double f = (T + 1 - lo + 1) / (hi - lo + 1);
        return 0.6 * max(0.0, min(1.0, f));
    }
    return min(0.22, 0.04 + T / 1500.0);
}

// tiles that respawn quickly keep paying while we circle them
static inline double farmBonus(int c) {
    if (gmax[c] <= 0) return 1.0;
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
static vector<Dragon> others;     // visible, other than me
static int otherBT[MAXN];         // blocked for BFS depth <= value
static int occId[MAXN];           // id+1 occupying now (any dragon incl. me), 0 free
static bool occHead[MAXN];
static int zoneE[MAXN], zoneF[MAXN];  // adjacency to other heads
static int enemyDist[MAXN], friendDist[MAXN], friendMinId[MAXN], enemyMinId[MAXN];
static int occFace[MAXN], occTeam[MAXN];
static const int UNKNOWN_EXTRA = 10;

// ally heads heard over sonar (position and heading when they cast)
struct HeardAlly { int cell, dir, len, round; };
static vector<HeardAlly> heard;

// sonar rays cast last turn, with what we expected each to stop on
struct RayRec { int kind; vector<int> unseen; };  // kind: 0..4 echo kind, -1 nothing, -2 unknown
static RayRec rays[4];
static int nRays = 0;
static bool raysValid = false;

// echo counts that no in-view prediction explains belong to the rays that left our view
static void attributeEchoes() {
    if (!raysValid || !P.fEchoAll) { raysValid = false; return; }
    raysValid = false;
    int R[5];
    for (int k = 0; k < 5; k++) R[k] = ECHO[k];
    vector<int> unk;
    for (int r = 0; r < nRays; r++) {
        if (rays[r].kind >= 0) R[rays[r].kind]--;
        else if (rays[r].kind == -2) unk.push_back(r);
    }
    for (int k = 0; k < 5; k++) if (R[k] < 0) return;  // prediction broke (something moved): trust nothing
    if (unk.empty()) return;
    int enemy = R[3] + R[4], ally = R[1] + R[2];
    auto mark = [&](int r, int* arr, int until) {
        // a dragon that is now in view explains the echo
        for (int c : rays[r].unseen) {
            if (viewIndex[c] < 0) break;
            if (occId[c]) return;
        }
        for (int c : rays[r].unseen) if (viewIndex[c] < 0) arr[c] = max(arr[c], until);
    };
    if (unk.size() == 1) {
        int r = unk[0];
        if (enemy) mark(r, radarExpire, ROUND + (R[4] ? 8 : 5));
        else if (R[2]) mark(r, laneExpire, ROUND + 5);
        else if (R[1]) mark(r, friendExpire, ROUND + 3);
    } else if (enemy >= (int)unk.size()) {
        for (int r : unk) mark(r, radarExpire, ROUND + 5);
    } else if (enemy == 0 && R[2] >= (int)unk.size()) {
        for (int r : unk) mark(r, laneExpire, ROUND + 5);
    }
}

static vector<int> body;          // head first, -1 unknown
static vector<int> lastPath;      // cells my head entered last turn, in order
static bool havePrev = false;

static int partAt[MAXN];
static int ownLost[MAXN];
static int eatMargin[256];

static void buildDragons() {
    const auto& parts = V.parts;
    int np = (int)parts.size();
    for (int i = 0; i < 49; i++) { partAt[V.cell[i]] = -1; }
    for (int c = 0; c < N; c++) { otherBT[c] = 0; occId[c] = 0; occHead[c] = false; zoneE[c] = 0; zoneF[c] = 0; }
    for (int i = 0; i < np; i++) {
        partAt[parts[i].cell] = i;
        occId[parts[i].cell] = parts[i].id + 1;
        occHead[parts[i].cell] = parts[i].head;
        occFace[parts[i].cell] = parts[i].face;
        occTeam[parts[i].cell] = parts[i].team;
    }
    // link each segment to the one in front (towards the head)
    vector<int> nxt(np, -1), prv(np, -1);
    for (int i = 0; i < np; i++) {
        if (parts[i].head) continue;
        int to = nbr[parts[i].cell * 4 + parts[i].face];
        if (to < 0 || viewIndex[to] < 0) continue;
        int j = partAt[to];
        if (j >= 0 && parts[j].id == parts[i].id && prv[j] < 0) { nxt[i] = j; prv[j] = i; }
    }
    // is fragment tail the dragon's real tail?
    auto tailCertain = [&](int t) {
        int c = parts[t].cell;
        for (int d = 0; d < 4; d++) {
            int k = effK(c, d);
            if (k == 2) continue;
            if (k == 3) return false;
            int q = stepRaw(c, d);
            if (viewIndex[q] < 0) return false;
        }
        return true;
    };
    // dragons standing near pearls will grow, so their tails linger
    for (int i = 0; i < 256; i++) eatMargin[i] = 0;
    for (int i = 0; i < np; i++) {
        if (!parts[i].head) continue;
        int cnt = 0;
        for (int j = 0; j < 49; j++)
            if (V.pearl[j] && torusDist(V.cell[j], parts[i].cell) <= 3) cnt++;
        eatMargin[parts[i].id % 256] = min(4, cnt);
    }
    vector<int> behind(np, 0);
    vector<char> certain(np, 0);
    for (int i = 0; i < np; i++) {
        if (prv[i] >= 0) continue;  // not a fragment tail
        bool cert = tailCertain(i);
        int k = 0, cur = i;
        while (cur >= 0) { behind[cur] = k++; certain[cur] = cert; cur = nxt[cur]; }
    }
    // what we saw of other bodies earlier still blocks cells we cannot see now
    for (int i = 0; i < 49; i++) memExpire[V.cell[i]] = 0;
    for (int c = 0; c < N; c++)
        if (viewIndex[c] < 0 && memExpire[c] > ROUND) otherBT[c] = memExpire[c] - ROUND;
    // radar: echoes of last turn's rays locate dragons we cannot see
    attributeEchoes();
    others.clear();
    unordered_map<int, int> idx;
    for (int i = 0; i < np; i++) {
        const Part& q = parts[i];
        if (q.id == MY_ID) continue;
        int extra = certain[i] ? 0 : UNKNOWN_EXTRA;
        otherBT[q.cell] = behind[i] + extra + 1 + eatMargin[q.id % 256];
        memExpire[q.cell] = ROUND + otherBT[q.cell];
        auto it = idx.find(q.id);
        if (it == idx.end()) { idx[q.id] = (int)others.size(); others.push_back(Dragon{q.id, q.team}); it = idx.find(q.id); }
        Dragon& dr = others[it->second];
        if (q.team != MY_TEAM) maxEnemyId = max(maxEnemyId, q.id);
        dr.visCount++;
        if (q.head) {
            dr.headCell = q.cell; dr.headFace = q.face;
            dr.tailKnown = certain[i];
            dr.estLen = behind[i] + 1 + (certain[i] ? 0 : 2);
        }
    }
    swarm = maxEnemyId >= 20;
    for (auto& dr : others) {
        if (dr.headCell < 0) continue;
        for (int d = 0; d < 4; d++) {
            int n = nbr[dr.headCell * 4 + d];
            if (n < 0) continue;
            if (dr.team == MY_TEAM) zoneF[n] = 1; else zoneE[n] = 1;
        }
    }

    // my own body: vision chain, extended by tracked history
    int headIdx = -1;
    for (int i = 0; i < np; i++) if (parts[i].id == MY_ID && parts[i].head) headIdx = i;
    vector<int> chain;
    for (int cur = headIdx; cur >= 0 && (int)chain.size() < MY_LEN; cur = prv[cur]) chain.push_back(parts[cur].cell);
    vector<int> pred;
    if (havePrev) {
        for (int i = (int)lastPath.size() - 1; i >= 0; i--) pred.push_back(lastPath[i]);
        for (int c : body) pred.push_back(c);
    } else if (KM && ROUND == 0) {
        const int* s = KM->spawns;
        for (int k = 0, pos = 0; k < KM->n_spawn; k++) {
            int team = s[pos], cnt = s[pos + 1];
            if (team == MY_TEAM && !chain.empty() && s[pos + 2] == chain[0])
                for (int j = 0; j < cnt; j++) pred.push_back(s[pos + 2 + j]);
            pos += 2 + cnt;
        }
    }
    body = chain;
    if ((int)body.size() < MY_LEN) {
        bool match = pred.size() >= body.size();
        for (size_t i = 0; i < body.size() && match; i++) match = pred[i] == body[i];
        if (match) {
            for (size_t i = body.size(); i < pred.size() && (int)body.size() < MY_LEN; i++) body.push_back(pred[i]);
        } else if (!havePrev && !KM && ROUND == 0 && body.size() >= 2) {
            // spawn lines are straight: extrapolate
            int a = body[body.size() - 2], b = body.back();
            int dir = -1;
            for (int d = 0; d < 4; d++) if (stepRaw(a, d) == b) dir = d;
            while (dir >= 0 && (int)body.size() < MY_LEN) body.push_back(stepRaw(body.back(), dir));
        }
        while ((int)body.size() < MY_LEN) body.push_back(-1);
    }
    if ((int)body.size() > MY_LEN) body.resize(MY_LEN);
    // parts of us we can see but could not place in order (e.g. a fresh split child):
    // treat them as walls rather than pretend they are not there
    for (int i = 0; i < np; i++) {
        if (parts[i].id != MY_ID) continue;
        if (find(body.begin(), body.end(), parts[i].cell) == body.end()) {
            ownLost[parts[i].cell] = ROUND + 1;
            otherBT[parts[i].cell] = max(otherBT[parts[i].cell], MY_LEN);
        }
    }

    // plain multi-source distances from other heads (for pearl competition)
    for (int c = 0; c < N; c++) {
        enemyDist[c] = 1 << 20; friendDist[c] = 1 << 20; friendMinId[c] = 1 << 20; enemyMinId[c] = 1 << 20;
    }
    static int q[MAXN];
    for (int pass = 0; pass < 2; pass++) {
        int* dist = pass == 0 ? enemyDist : friendDist;
        int* minId = pass == 0 ? enemyMinId : friendMinId;
        int qh = 0, qt = 0;
        for (auto& dr : others) {
            if (dr.headCell < 0) continue;
            if ((dr.team == MY_TEAM) != (pass == 1)) continue;
            if (dist[dr.headCell] > 0) { dist[dr.headCell] = 0; q[qt++] = dr.headCell; }
            minId[dr.headCell] = min(minId[dr.headCell], dr.id);
        }
        while (qh < qt) {
            int c = q[qh++];
            if (dist[c] >= 40) continue;
            for (int d = 0; d < 4; d++) {
                int n = nbr[c * 4 + d];
                if (n < 0) continue;
                if (dist[n] > dist[c] + 1) {
                    dist[n] = dist[c] + 1;
                    minId[n] = minId[c];
                    q[qt++] = n;
                } else if (dist[n] == dist[c] + 1) minId[n] = min(minId[n], minId[c]);
            }
        }
    }
}

// ---------------------------------------------------------------- simulation --

static inline bool pearlNow(int c) { return viewIndex[c] >= 0 && V.pearl[viewIndex[c]]; }

struct SimResult {
    bool dead = false;
    bool outside = false;      // stepped out of what we can see
    int hitHeadId = -1;        // head-on with this dragon on the last step
    vector<int> body;
    vector<int> cells;         // entered, in order
    int len = 0;
};

// applies a (multi-step) move exactly as the engine does
static SimResult simulate(const vector<int>& dirs) {
    SimResult r;
    r.body = body;
    r.len = MY_LEN;
    vector<int> eaten;
    for (size_t j = 0; j < dirs.size(); j++) {
        if (j > 0 && r.len < 3) { r.dead = true; return r; }
        int head = r.body[0];
        int dest = nbr[head * 4 + dirs[j]];
        if (dest < 0) { r.dead = true; return r; }
        for (int c : r.body) if (c == dest) { r.dead = true; return r; }
        if (viewIndex[dest] < 0) r.outside = true;
        else if (occId[dest] && (occId[dest] != MY_ID + 1 || ownLost[dest] == ROUND + 1)) {
            r.dead = true;
            if (occHead[dest]) r.hitHeadId = occId[dest] - 1;
            return r;
        }
        r.cells.push_back(dest);
        bool ate = pearlNow(dest) && find(eaten.begin(), eaten.end(), dest) == eaten.end();
        r.body.insert(r.body.begin(), dest);
        if (ate) { eaten.push_back(dest); r.len++; }
        else r.body.pop_back();
        if (j > 0) { r.body.pop_back(); r.len--; }
    }
    return r;
}

// ------------------------------------------------------------ evaluation --

static int distA[MAXN], qA[MAXN];
static int ownBT[MAXN], ownStamp[MAXN], stampCtr = 0;
static double powG[256], powT[256], powM[256];
static bool recordVals = false;
static double valT[MAXN];
struct QueenInfo { int cell = -1, len = 0, round = -1000, id = -1; };
static QueenInfo queen;
static QueenInfo eq;              // the longest enemy we know of (seen or heard)
static int goalCell = -1, lastGoal = -1, goalDistNow = -1;
static bool feeding = false, hunting = false;
static bool satQueen = false;     // the swarm is saturated: the longest dragon stops budding and grows
static int satResignUntil = -1;   // a longer saturation queen was heard: do not claim the role again yet
static int homeCell = -1;         // where our side started (own spawn, or heard)
static bool scout = false;        // starting dragon that looks for far fountains early
static bool homeOrigin = false;   // homeCell comes from an initial dragon's own spawn
static bool localSup = false;     // we outnumber the visible enemy heads here (heard allies count)
static int earlyQ = 999;          // queen phase pulled forward by an event (ours or heard)
static inline int chebDist(int a, int b) {
    int dx = abs(a % W - b % W), dy = abs(a / W - b / W);
    return max(min(dx, W - dx), min(dy, H - dy));
}
static bool eqFresh(int age) { return eq.cell >= 0 && ROUND - eq.round <= age; }
// late game or a lone giant: our cheap drones go for the longest enemy's head
static bool huntTarget() {
    if (!P.fHunt || !eqFresh(15)) return false;
    if (ROUND >= P.protectFrom + 40 && eq.len >= 8) return true;
    return ROUND >= 60 && eq.len >= 12 && eq.len >= max(queen.len, MY_LEN) + 3;
}

// a one-wide lane we would enter, with something coming the other way down it
static bool laneBlocked(int from, int X) {
    if (!P.fCorridor || degS[X] > 2) return false;
    int prev = from, cur = X, k = 0;
    bool blocked = false;
    for (int step = 0; step < 16; step++) {
        k++;
        if (laneExpire[cur] > ROUND || radarExpire[cur] > ROUND) blocked = true;
        if (occHead[cur] && occId[cur] && occId[cur] != MY_ID + 1 && nbr[cur * 4 + occFace[cur]] == prev) blocked = true;
        for (auto& a : heard)
            if (a.round >= ROUND - 1 && a.cell == cur && nbr[a.cell * 4 + a.dir] == prev) blocked = true;
        if (degS[cur] != 2) break;
        int nxt = -1;
        for (int d = 0; d < 4; d++) { int n = nbr[cur * 4 + d]; if (n >= 0 && n != prev) { nxt = n; break; } }
        if (nxt < 0) break;
        prev = cur; cur = nxt;
    }
    return blocked && k >= 3;
}

struct EnemyReach { int id; int len; vector<pair<int, int>> cells; };
static vector<EnemyReach> reaches;

static void buildReaches() {
    reaches.clear();
    for (auto& dr : others) {
        if (dr.team == MY_TEAM || dr.headCell < 0) continue;
        EnemyReach er; er.id = dr.id; er.len = dr.estLen;
        vector<int> frontier{dr.headCell};
        vector<int> seen{dr.headCell};
        for (int depth = 1; depth <= 3; depth++) {
            vector<int> nf;
            for (int c : frontier)
                for (int d = 0; d < 4; d++) {
                    int n = nbr[c * 4 + d];
                    if (n < 0 || find(seen.begin(), seen.end(), n) != seen.end()) continue;
                    seen.push_back(n);
                    er.cells.push_back({n, depth});
                    if (occId[n] == 0) nf.push_back(n);  // can keep moving through free cells only
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
    int safeClass = 0;   // 2 proven even if nothing recedes, 1 only if bodies recede, 0 unproven
    double corridor = 0;
    bool adjacent = false;
    double pocket = 0;
};

// exact survival search over our own body
static int vt[MAXN];
static bool dfsAte[MAXN];
static long long dfsNodes, dfsBudget;
static int dfsTarget;
static bool dfsPessimist = false;
// a pearl our head would eat on entering c at depth t (only what we can see)
static inline bool pearlAtDepth(int c, int t) {
    int i = viewIndex[c];
    if (i < 0 || dfsAte[c]) return false;
    if (V.pearl[i]) return true;
    int sa = spawnAt[c];
    return sa >= 0 && sa <= ROUND + t;
}
static int dfs(int head, int t, int len) {
    if (t >= dfsTarget) return t;
    if (++dfsNodes > dfsBudget) return t;
    int best = t;
    int opts[4], score[4], no = 0;
    for (int d = 0; d < 4; d++) {
        int c = nbr[head * 4 + d];
        if (c < 0) continue;
        if (vt[c] >= t - len + 1) continue;
        if (otherBT[c] >= t + 1 || (dfsPessimist && (otherBT[c] > 0 || radarExpire[c] > ROUND || laneExpire[c] > ROUND ||
                                                     friendExpire[c] > ROUND || min(enemyDist[c], friendDist[c]) <= t + 1))) continue;
        if (t == 0 && (zoneE[c] || zoneF[c])) continue;
        // Warnsdorff: explore the tighter continuation first
        int free = 0;
        for (int e = 0; e < 4; e++) {
            int n2 = nbr[c * 4 + e];
            if (n2 >= 0 && n2 != head && vt[n2] < t + 2 - len && otherBT[n2] < t + 2) free++;
        }
        opts[no] = c; score[no] = free; no++;
    }
    for (int i = 0; i < no; i++)
        for (int j = i + 1; j < no; j++)
            if (score[j] < score[i]) { swap(score[i], score[j]); swap(opts[i], opts[j]); }
    for (int i = 0; i < no; i++) {
        int c = opts[i];
        int old = vt[c];
        vt[c] = t + 1;
        bool ate = pearlAtDepth(c, t + 1);
        if (ate) dfsAte[c] = true;
        int r = dfs(c, t + 1, len + (ate ? 1 : 0));
        if (ate) dfsAte[c] = false;
        vt[c] = old;
        if (r > best) best = r;
        if (best >= dfsTarget || dfsNodes > dfsBudget) break;
    }
    return best;
}

static int survivalDepth(const vector<int>& B, int len, int target, long long budget) {
    for (size_t i = 0; i < B.size(); i++) if (B[i] >= 0) vt[B[i]] = -(int)i;
    dfsNodes = 0; dfsBudget = budget; dfsTarget = target;
    int r = dfs(B[0], 0, len);
    for (int c : B) if (c >= 0) vt[c] = INT32_MIN / 2;
    return r;
}

// size of the region around the head if nothing moved out of the way
static int staticMark[MAXN], staticCtr = 0;
static int sDist[MAXN];
static inline int otherHeadDist(int c) { return min(enemyDist[c], friendDist[c]); }
// cells we reach strictly before any other head, if nothing moved out of the way
static int staticSpace(const vector<int>& B, int cap) {
    staticCtr++;
    for (int c : B) if (c >= 0) staticMark[c] = staticCtr;
    int qh = 0, qt = 0;
    double cnt = 0;  // cells we cannot see count for less: dragons may be there
    qA[qt++] = B[0]; staticMark[B[0]] = staticCtr; sDist[B[0]] = 0;
    while (qh < qt && cnt < cap) {
        int c = qA[qh++];
        for (int d = 0; d < 4; d++) {
            int n = nbr[c * 4 + d];
            if (n < 0 || staticMark[n] == staticCtr || (occId[n] && occId[n] != MY_ID + 1)) continue;
            if (zoneE[n] || zoneF[n] || otherBT[n] > 0) continue;
            if (otherHeadDist(n) <= sDist[c] + 1) continue;
            staticMark[n] = staticCtr; sDist[n] = sDist[c] + 1; qA[qt++] = n;
            cnt += viewIndex[n] >= 0 ? 1.0 : (radarExpire[n] > ROUND || laneExpire[n] > ROUND) ? 0.0 : 0.5;
        }
    }
    return (int)cnt;
}

static bool endgame() { return ROUND >= 500 - P.endgameRounds; }

// a tunnel walled by dragon bodies can be shut by a head we cannot see
static double corridorRisk(const vector<int>& B) {
    if (B.size() < 2) return 0;
    stampCtr++;
    for (int c : B) if (c >= 0) { ownStamp[c] = stampCtr; }
    int h = B[0], k = 0;
    bool flanked = false, unseenExit = false;
    vector<int> path{h};
    for (int step = 0; step < 10; step++) {
        int nf = 0, next = -1;
        for (int d = 0; d < 4; d++) {
            int n = nbr[h * 4 + d];
            if (n < 0) continue;
            bool mine = ownStamp[n] == stampCtr || find(path.begin(), path.end(), n) != path.end();
            bool foreign = (occId[n] && occId[n] != MY_ID + 1) || otherBT[n] > 0;
            if (foreign) flanked = true;
            if (mine || foreign) continue;
            nf++; next = n;
        }
        if (nf != 1) break;
        k++;
        if (viewIndex[next] < 0) { unseenExit = true; break; }
        path.push_back(next);
        h = next;
    }
    if (k < 2) return 0;
    // bodies move and can shut a tunnel; kelp does not, but an unseen exit may already be blocked
    if (flanked) return min(0.4, 0.07 * k + (unseenExit ? 0.12 : 0.0));
    return unseenExit ? min(0.25, 0.03 * k + 0.08) : 0.0;
}

// how long a dragon can get before the map itself becomes the trap
static int capLen = 1 << 20;
static void computeCap() {
    static int seen[MAXN], ctr = 0;
    ctr++;
    int qh = 0, qt = 0;
    qA[qt++] = body[0]; seen[body[0]] = ctr;
    while (qh < qt) {
        int c = qA[qh++];
        for (int d = 0; d < 4; d++) {
            int n = nbr[c * 4 + d];
            if (n < 0 || seen[n] == ctr) continue;
            seen[n] = ctr; qA[qt++] = n;
        }
    }
    capLen = max(10, qt / 6);
}

static Eval evaluate(const SimResult& s, bool deepAllowed) {
    if (elapsedMs() > 70) deepAllowed = false;
    Eval e;
    const vector<int>& B = s.body;
    int L = s.len;
    int head = B[0];
    bool scouting = scout && ROUND < P.scoutUntil;
    // early small drones: short-horizon targets (don't trek to far, contested fountains)
    bool shortSight = !bigFeed && !farSight && UNITS >= 3 && L <= 4 && queen.id != MY_ID && ROUND < P.mineUntil &&
                      !satQueen && !scouting;
    // territory: early drones mine their own half and the middle, not deep in the enemy's half
    int enemyHome = (P.fTerritory && SYM >= 0 && homeCell >= 0 && L <= 4 && !satQueen && ROUND < P.mineUntil && !scouting)
                        ? mirrorCell(homeCell) : -1;
    // late maze game: pearls go to the queen first
    bool lateQ = !bigFeed && ROUND >= P.protectFrom;
    bool meQueen = lateQ && queen.id == MY_ID;
    int qCell = (lateQ && !meQueen && queen.cell >= 0 && ROUND - queen.round <= 25 && queen.len > L) ? queen.cell : -1;
    stampCtr++;
    for (size_t i = 0; i < B.size(); i++)
        if (B[i] >= 0) { ownStamp[B[i]] = stampCtr; ownBT[B[i]] = L - (int)i; }
    for (int c = 0; c < N; c++) distA[c] = -1;
    if (recordVals) for (int c = 0; c < N; c++) valT[c] = 0;
    int qh = 0, qt = 0;
    distA[head] = 0; qA[qt++] = head;
    int depthCap = max(P.fieldCap, 2 * L + 12);
    double fsum = 0, fmax = 0;
    int space = 0;
    while (qh < qt) {
        int c = qA[qh++];
        int dc = distA[c];
        if (dc >= depthCap) continue;
        for (int d = 0; d < 4; d++) {
            int n = nbr[c * 4 + d];
            if (n < 0 || distA[n] >= 0) continue;
            int nd = dc + 1;
            if (ownStamp[n] == stampCtr && ownBT[n] >= nd) continue;
            if (otherBT[n] >= nd) continue;
            if (nd <= 1 && (zoneE[n] || zoneF[n])) continue;
            distA[n] = nd; qA[qt++] = n; space++;
            if (nd <= P.fieldCap) {
                double p = pearlProb(n, ROUND + nd);
                if (p > 0) {
                    // against a swarm every pearl is contested; discounting them all just starves us
                    if (enemyDist[n] < nd) p *= swarm ? 0.8 : P.enemyCloser;
                    else if (enemyDist[n] == nd) {
                        // equal distance: dragons move in id order, so the lower id gets there first
                        if (!P.fMoveOrder) p *= swarm ? 0.9 : P.enemyTie;
                        else if (enemyMinId[n] < MY_ID) p *= swarm ? 0.8 : P.enemyCloser;
                        else p *= 0.95;
                    }
                    if (enemyHome >= 0 && torusDist(n, enemyHome) + 4 < torusDist(n, homeCell)) p *= 0.8;
                    if (!meQueen && (friendDist[n] < nd || (friendDist[n] == nd && friendMinId[n] < MY_ID))) p *= P.friendCloser;
                    if (qCell >= 0 && torusDist(qCell, n) < nd) p *= 0.3;
                    bool near = shortSight && !(P.fFountRush && gmax[n] > 0 && gmax[n] <= P.rushGap);
                    p *= near ? min(P.minerFarmCap, farmBonus(n)) : farmBonus(n);
                    fsum += p * powG[nd];
                    double v = p * (near ? powM[nd] : powT[nd]);
                    if (v > fmax) { fmax = v; e.targetCell = n; }
                    if (recordVals) valT[n] = v;
                }
            }
        }
    }
    e.space = space;
    e.field = fsum; e.target = fmax;
    e.goalDist = goalCell >= 0 ? distA[goalCell] : -1;

    // survival: open region -> fine; otherwise prove it with an exact search
    {
        int left = max(0, 499 - ROUND);
        int roomy = min(2 * L + 20, left + 1);
        int st = staticSpace(B, roomy);
        e.room = st;
        if (st >= roomy && (L < 20 || !deepAllowed)) { e.pDeath = 0; e.surv = 999; e.safeClass = 2; }
        else {
            int target = min(min(2 * L + 8, 90), left);
            double el = elapsedMs();
            long long budget = el > 55 ? 0 : el > 35 ? 1500 : 12000;
            if (budget == 0) deepAllowed = false;
            int got, pes = 0;
            if (!deepAllowed) got = min(st, target);
            else {
                dfsPessimist = true;
                pes = survivalDepth(B, L, target, budget);
                dfsPessimist = false;
                got = pes >= target ? pes : survivalDepth(B, L, target, budget);
            }
            e.surv = got;
            e.safeClass = (deepAllowed && pes >= target) ? 2 : got >= target ? 1 : 0;
            if (deepAllowed && pes >= target) e.pDeath = 0.0;
            else if (got >= target) e.pDeath = 0.5 * (1.0 - (double)pes / target);
            else e.pDeath = pow(1.0 - (double)got / target, 0.6);
            e.pocket = 1.0 - (double)st / roomy;
        }
    }

    // head-on danger
    double danger = 0;
    bool adjacentThreat = false;
    for (auto& er : reaches) {
        int dd = 99;
        for (auto& pc : er.cells) if (pc.first == head) { dd = pc.second; break; }
        double p = 0;
        if (dd == 1) p = P.p1;
        else if (dd == 2 && er.len <= 4) p = P.p2Drone;   // small ones hunt heads
        else if (dd == 2 && er.len >= 3) p = P.p2;
        else if (dd == 3 && er.len <= 4) p = P.p3Drone;
        else if (dd == 3 && er.len >= 4) p = P.p3;
        if (p <= 0) continue;
        // a head-on kills both: an enemy longer than us gives up more than it takes
        if (P.fLookahead) p *= er.len <= L ? 1.0 : er.len <= L + 3 ? 0.8 : 0.6;
        // a lost dragon also brings us a unit closer to elimination
        double unitValue = UNITS <= 2 ? 10.0 : UNITS <= 4 ? 5.0 : 2.0;
        double loss = max(0.5, L - 0.8 * er.len + 3.0) + unitValue;
        if (swarm) p = min(0.95, p * 1.4);
        if (ROUND >= P.feedFrom - 30 && queen.id == MY_ID) loss *= (ROUND >= P.protectFrom ? 3.0 : 2.0);
        if (satQueen && ROUND < P.feedFrom - 30) loss *= 1.5;
        // anything that can reach our head this coming turn (sprints included) is a real threat
        if ((L >= 6 || UNITS <= 4) && (dd == 1 || (dd <= 3 && dd <= er.len - 1))) adjacentThreat = true;
        if (UNITS == 1) loss = L + 14.0;
        danger += p * loss;
    }
    // two-ply: after the enemies' next moves, is there still a cell we can step to?
    if (P.fLookahead && !reaches.empty()) {
        bool near = false;
        for (auto& er : reaches)
            for (auto& pc : er.cells) if (pc.second <= 2 && pc.first == head) near = true;
        if (near) {
            int escapes = 0;
            for (int d = 0; d < 4; d++) {
                int y = nbr[head * 4 + d];
                if (y < 0 || otherBT[y] >= 2) continue;
                bool own = false;
                for (int i = 0; i + 1 < (int)B.size(); i++) if (B[i] == y) { own = true; break; }
                if (own) continue;
                bool taken = false;
                for (auto& er : reaches) {
                    if (er.len > L + 3) continue;  // big ones rarely trade
                    for (auto& pc : er.cells) if (pc.second == 1 && pc.first == y) { taken = true; break; }
                    if (taken) break;
                }
                if (!taken) escapes++;
            }
            if (escapes == 0) {
                double unitValue = UNITS <= 2 ? 10.0 : UNITS <= 4 ? 5.0 : 2.0;
                danger += 0.5 * (L + unitValue);
            }
        }
    }
    e.danger = danger;
    if (adjacentThreat) e.safeClass = min(e.safeClass, 1);
    e.adjacent = adjacentThreat;

    // hunting: small dragons drift towards big enemy heads
    double hunt = 0;
    if (L <= P.huntMaxLen && UNITS >= 2) {
        for (auto& dr : others) {
            if (dr.team == MY_TEAM || dr.headCell < 0 || dr.estLen < L + P.attackMargin) continue;
            int best = 1 << 20;
            for (int d = 0; d < 4; d++) {
                int n = nbr[dr.headCell * 4 + d];
                if (n >= 0 && distA[n] >= 0) best = min(best, distA[n] + 1);
            }
            if (head == dr.headCell) best = 0;
            if (best < 64) hunt = max(hunt, powG[best] * min(3.0, dr.estLen / 6.0));
        }
    }
    e.hunt = hunt;

    double growth = s.len - MY_LEN;
    double greed = endgame() ? 0.35 : 1.0;
    if (L > capLen && !endgame()) { greed *= 0.3; if (growth > 0) growth *= -0.3; }
    double score = 0;
    score += growth * (endgame() ? 1.5 : 1.0);
    score += greed * (P.wField * fsum + P.wTarget * fmax);
    score += P.wHunt * hunt;
    if (goalCell >= 0 && goalDistNow >= 0) {
        bool ateGoal = find(s.cells.begin(), s.cells.end(), goalCell) != s.cells.end();
        double prog = ateGoal ? 1.0 : e.goalDist < 0 ? -1.5 : max(-2.0, min(2.0, (double)(goalDistNow - e.goalDist)));
        score += (feeding ? 4.0 : hunting ? 3.0 : scouting ? P.wScoutProgress : greed) * P.wProgress * prog;
    }
    score -= danger;
    // in a big swarm a small drone is cheap: its death costs little more than its length
    // a pocket with less room than it takes to grow to a bud and split out: the child is left at
    // the mouth and walks back in, so the dive only loses dragons
    bool trap = P.fTrapGuard && e.pDeath > 0.8 && e.room + L < P.budAt + 2;
    bool cheap = !trap && UNITS >= 4 && L <= 4 && queen.id != MY_ID;
    // greedy miner (what every top team does): a small drone dives into dead-end pockets for
    // pearls; it may die there, but it buds a child out first and the swarm grows 2x faster
    bool miner = !trap && UNITS >= 3 && L <= 4 && queen.id != MY_ID && ROUND < P.mineUntil;
    bool narrowMaze = P.fNarrowMiner && !bigFeed && narrowFrac >= P.narrowFracMin;
    double minerCost = narrowMaze ? P.narrowMinerCost : 1.0;
    score -= e.pDeath * (L + (miner ? minerCost : cheap ? 3.0 : P.deathExtra));
    if (!miner || (P.fEarlyPocket && L >= P.earlyPocketLen)) score -= P.wPocket * e.pocket * (2.0 + L / 4.0);
    score += P.spaceBonus * min(1.0, space / (double)(2 * L + 20));
    if (s.outside) {
        // on a known map we know what is behind a portal except for dragons: a modest risk,
        // unless we remember a body on the far side
        bool remembered = !s.cells.empty() && memExpire[s.cells.back()] > ROUND;
        if (KM && !remembered) score -= 0.8 + 0.03 * L;
        else { score -= 3.0 + 0.12 * (L + P.deathExtra); e.safeClass = 0; }
    }
    e.corridor = miner ? 0.0 : corridorRisk(B);
    score -= e.corridor * (L / 2.0 + 10.0);
    // one-wide lane with a head coming the other way: neither of us can turn round in it
    bool lane = !s.cells.empty() && !body.empty() && body[0] >= 0 && laneBlocked(body[0], s.cells[0]);
    if (lane) score -= 0.8 * (L + 8.0);
    // hidden reserves: without local superiority, cheap drones wait just outside enemy sight
    if (P.fReserves && !localSup && L <= 3 && UNITS >= 12 && queen.id != MY_ID && ROUND < P.protectFrom && !hunting)
        for (auto& dr : others)
            if (dr.team != MY_TEAM && dr.headCell >= 0 && chebDist(head, dr.headCell) <= 3 &&
                chebDist(body[0], dr.headCell) > 3) { score -= 0.3; break; }
    // a likely death drops half our length as pearls: better where friends will collect them
    if (P.fDieNearFriends && e.pDeath > 0.3) {
        double fr = friendDist[head] <= 4 ? 1.0 : 0.0, en = enemyDist[head] <= 4 ? 1.0 : 0.0;
        score += e.pDeath * 0.25 * L * (fr - en);
    }
    e.score = score;
    // one coarse safety class: greed chooses freely among moves that are reasonably safe
    bool riskOk = e.pDeath < 0.25 || miner || (cheap && !bigFeed && e.pDeath < 0.9);
    e.safeClass = (riskOk && !adjacentThreat && !lane && (!s.outside || (KM && e.safeClass > 0))) ? 1 : 0;
    return e;
}

// --------------------------------------------------------------- decisions --

static string indicator;
static bool DEBUG = false;
static int debugFrom = 0, debugTo = -1;

// ASCII picture of what this dragon believes, logged into the replay
static void dumpState() {
    if (!DEBUG || ROUND < debugFrom || ROUND > debugTo) return;
    int R = 7;
    int hx = body[0] % W, hy = body[0] / W;
    vector<int> bidx(N, -1);
    for (size_t i = 0; i < body.size(); i++) if (body[i] >= 0) bidx[body[i]] = (int)i;
    for (int dy = -R; dy <= R; dy++) {
        string top, row;
        for (int dx = -R; dx <= R; dx++) {
            int x = ((hx + dx) % W + W) % W, y = ((hy + dy) % H + H) % H, c = y * W + x;
            int kn = effK(c, 0), kw = effK(c, 3);
            top += "+"; top += kn == 2 ? "--" : kn == 3 ? "PP" : kn == 0 ? ".." : "  ";
            row += kw == 2 ? "|" : kw == 3 ? "P" : kw == 0 ? ":" : " ";
            char a = ' ', b = ' ';
            if (bidx[c] >= 0) { a = bidx[c] == 0 ? '@' : 'o'; b = "0123456789abcdefghijklmnopqrstuvwxyz"[min(35, bidx[c])]; }
            else if (occId[c]) {
                bool fr = false; for (auto& dr : others) if (dr.id == occId[c] - 1) fr = dr.team == MY_TEAM;
                a = occHead[c] ? (fr ? 'F' : 'E') : (fr ? 'f' : 'e');
                int bt = min(9, otherBT[c]); b = (char)('0' + bt);
            } else if (pearlNow(c)) a = '*';
            else if (viewIndex[c] < 0) a = '?', b = seenR[c] >= 0 ? '.' : '?';
            row += a; row += b;
        }
        printf("LOG %s\nLOG %s\n", top.c_str(), row.c_str());
    }
}
static vector<int> chosenCells;
static vector<int> chosenBody;   // our body after this turn's move
static bool moveKnown = false;

static void emitMove(const vector<int>& dirs, const vector<int>& cells) {
    string m = "MOVE ";
    for (int d : dirs) m += DCH[d];
    printf("%s\n", m.c_str());
    chosenCells = cells;
}

// search sprint paths ending on an enemy head
static bool findAttack(bool desperate) {
    int best = -1; vector<int> bestPath; double bestVal = -1e9;
    for (auto& dr : others) {
        if (dr.team == MY_TEAM || dr.headCell < 0) continue;
        // a trade costs us a unit too: only take clearly lopsided ones
        bool worth = UNITS >= 2 && dr.estLen >= max(MY_LEN + 4, 2 * MY_LEN);
        // war of numbers: a big swarm trades small drones evenly when it has local superiority
        if (!worth && UNITS >= 12 && MY_LEN <= 3 && queen.id != MY_ID && !satQueen && dr.estLen >= MY_LEN && localSup)
            worth = true;
        // queen hunt / lone giant: any cheap drone trades itself for the longest enemy
        if (!worth && huntTarget() && dr.id == eq.id && MY_LEN <= 6 && queen.id != MY_ID && !satQueen && UNITS >= 3)
            worth = true;
        if (UNITS >= 2 && endgame() && dr.estLen >= MY_LEN + 2) worth = true;
        // never throw away a long dragon at the end: it is probably what wins the tiebreak
        if (desperate && !(endgame() && MY_LEN > dr.estLen)) worth = true;
        if (!worth) continue;
        if (torusDist(body[0], dr.headCell) > P.attackMaxSteps) continue;
        int maxSteps = min(P.attackMaxSteps, MY_LEN - 1);
        vector<int> path;
        vector<int> found;
        // iterative deepening over direction sequences
        for (int k = 1; k <= maxSteps && found.empty(); k++) {
            int total = 1; for (int i = 0; i < k; i++) total *= 4;
            for (int code = 0; code < total && found.empty(); code++) {
                path.clear();
                int cc = code;
                for (int i = 0; i < k; i++) { path.push_back(cc % 4); cc /= 4; }
                SimResult r = simulate(path);
                if (r.dead && r.hitHeadId == dr.id && (int)r.cells.size() == k - 1) found = path;
            }
        }
        if (found.empty()) continue;
        double val = dr.estLen - MY_LEN - 0.3 * found.size();
        if (val > bestVal) { bestVal = val; best = dr.id; bestPath = found; }
    }
    if (best < 0) return false;
    string m = "MOVE ";
    for (int d : bestPath) m += DCH[d];
    printf("%s\n", m.c_str());
    indicator = "ATK " + to_string(best);
    return true;
}

// swarm size worth budding towards: 40 was measured on the maze maps (512-1152 tiles)
static int unitsTarget() {
    int area = W * H;
    if (area < 500) return max(16, 40 * area / 500);
    if (area > 1200) return min(64, 40 * area / 1200);
    return 40;
}
// bud at 4 where pearls and room allow; grow to 6 first where it is crowded and barren
static int hereRoom = 99;
static int budAtNow() {
    if (!P.fLocalBud || ROUND < P.bud4Until) return P.budAt;
    int pearls = 0, friends = 0;
    for (int i = 0; i < 49; i++) if (V.pearl[i]) pearls++;
    for (auto& dr : others) if (dr.team == MY_TEAM && dr.headCell >= 0) friends++;
    if (pearls == 0 && friends >= 3) return 6;
    if (hereRoom < 10) return 6;
    return P.budAt;
}

// Our head is about to be stuck, but the tail end may be free: hand most of the
// length to a child that crawls out from the tail. The split itself does not move
// the head, so it also buys the parent a turn.
static string dsWhy;
static bool doomedSplit(bool allowShed = true) {
    if (MY_LEN < 4 || UNITS >= UNIT_LIMIT) { dsWhy = "len/units"; return false; }
    for (int c : body) if (c < 0) { dsWhy = "unknown body"; return false; }
    double bestVal = 0; int bestC = -1;
    for (int c = MY_LEN - 2; c >= 2; c--) {
        if (elapsedMs() > 55) break;  // largest children first, within budget
        // the parent's front stays where it is and blocks the child
        vector<int> saved;
        for (int i = 0; i < MY_LEN - c; i++) { saved.push_back(otherBT[body[i]]); otherBT[body[i]] = 1000; }
        SimResult child;
        for (int i = MY_LEN - 1; i >= MY_LEN - c; i--) child.body.push_back(body[i]);
        child.len = c;
        int freeN = 0;
        for (int d = 0; d < 4; d++) {
            int n = nbr[child.body[0] * 4 + d];
            if (n >= 0 && !occId[n]) freeN++;
        }
        double val = 0;
        if (freeN > 0) {
            Eval ce = evaluate(child, true);
            val = (1.0 - ce.pDeath) * c;
        }
        for (int i = 0; i < MY_LEN - c; i++) otherBT[body[i]] = saved[i];
        if (val > bestVal + 1e-9) { bestVal = val; bestC = c; }
    }
    if (bestC < 0 || bestVal < 1.0) {
        if (!allowShed) return false;
        // the tail end is boxed in too: shed the boxed-in tail so that next turn our
        // new tail sits where a child can walk out
        for (int c = 2; c <= MY_LEN - 4; c++) {
            int newTail = body[MY_LEN - 1 - c];
            bool open = false;
            for (int d = 0; d < 4; d++) {
                int n = nbr[newTail * 4 + d];
                if (n < 0 || occId[n]) continue;
                bool mine = false;
                for (int i = 0; i < MY_LEN; i++) if (body[i] == n) mine = true;
                if (!mine) open = true;
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

// Swarm expansion (the ladder leader's macro): any dragon that reaches length 4 buds off a
// length-2 child until the unit cap. Many heads collect far more pearls, a swarm cannot be
// eliminated, and once the cap stops the splitting the dragons simply grow.
static int budLateUntil = 420;
static bool swarmSplit() {
    if (MY_LEN < budAtNow() || UNITS >= UNIT_LIMIT) return false;
    if (satQueen) return false;
    // stop budding once late; on the maze maps keep going while the swarm is still small,
    // because a small swarm just loses the head-on war of numbers
    int until = bigFeed ? P.budUntil : (UNITS < unitsTarget() ? budLateUntil : P.budUntil);
    if (P.fLowUnitBud && UNITS < P.lowUnits && queen.id != MY_ID) until = max(until, P.endFeedFrom);
    if (ROUND >= until) return false;
    for (int i = MY_LEN - 2; i < MY_LEN; i++) if (body[i] < 0) return false;
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

static bool trySplit(const Eval& stayEval) {
    int c = P.splitChild > 0 ? P.splitChild : MY_LEN / 2;
    bool overlong = MY_LEN > (satQueen ? 2 * capLen : capLen) && !endgame();
    if (satQueen && !overlong) return false;
    if (overlong) {
        c = MY_LEN / 2;
        if (UNITS >= min(UNIT_LIMIT, 6)) return false;
    } else {
        if (ROUND >= P.splitRoundMax || endgame()) return false;
        if (swarm) {
            // against a swarm, spread out: losing one dragon must not lose the game
            if (UNITS >= 5 || MY_LEN < 8) return false;
            c = max(3, MY_LEN / 3);
        } else {
            if (UNITS >= min(UNIT_LIMIT, 3)) return false;
            if (MY_LEN < P.splitMinLen) return false;
        }
    }
    if (MY_LEN - c < 2 || c < 2) return false;
    for (int i = MY_LEN - c; i < MY_LEN; i++) if (body[i] < 0) return false;
    for (auto& dr : others)
        if (dr.team != MY_TEAM && dr.headCell >= 0 && torusDist(dr.headCell, body[0]) <= (overlong ? 2 : 6)) return false;
    if (stayEval.pDeath > 0 && !overlong) return false;
    // the child's head is our tail; it needs somewhere to go
    int tail = body[MY_LEN - 1];
    int freeN = 0;
    for (int d = 0; d < 4; d++) {
        int n = nbr[tail * 4 + d];
        if (n < 0 || occId[n]) continue;
        freeN++;
    }
    if (freeN == 0) return false;
    // parent keeps its front; check it still has space
    SimResult parent; parent.body.assign(body.begin(), body.begin() + (MY_LEN - c)); parent.len = MY_LEN - c;
    Eval pe = evaluate(parent, false);
    if (pe.space < parent.len + 8 && !overlong) return false;
    SimResult child; for (int i = MY_LEN - 1; i >= MY_LEN - c; i--) child.body.push_back(body[i]); child.len = c;
    Eval ce = evaluate(child, false);
    if (ce.space < (overlong ? 4 : 12)) return false;
    printf("SPLIT %d\n", c);
    indicator = "SPLIT";
    return true;
}

// ---------------------------------------------------------------- sonar --
// Packets are 4 type bits, 48 data bits and a 12-bit checksum, sealed with a keyed Feistel
// permutation: to anyone without the key every ray carries uniform noise, and a foreign
// value fails the checksum 4095 times in 4096.
enum { PK_STATUS = 1, PK_QUEEN = 2, PK_ENEMYQ = 3, PK_FOUNT = 4 };
static const uint32_t SKEY[4] = {0x9E3779B9u, 0x7F4A7C15u, 0xC2B2AE35u, 0x27D4EB2Fu};
static inline uint32_t fmix32(uint32_t h) {
    h ^= h >> 16; h *= 0x85EBCA6Bu; h ^= h >> 13; h *= 0xC2B2AE35u; h ^= h >> 16;
    return h;
}
static inline uint32_t check12(uint64_t body) {
    return (fmix32((uint32_t)body ^ 0x5bd1e995u) ^ fmix32((uint32_t)(body >> 32) + 0x1b873593u)) & 0xFFF;
}
static uint64_t seal(int type, uint64_t data) {
    uint64_t b = (data & ((1ULL << 48) - 1)) | ((uint64_t)(type & 15) << 48);
    uint64_t x = b | ((uint64_t)check12(b) << 52);
    uint32_t L = (uint32_t)(x >> 32), R = (uint32_t)x;
    for (int i = 0; i < 4; i++) { uint32_t t = L ^ fmix32(R ^ SKEY[i]); L = R; R = t; }
    return ((uint64_t)L << 32) | R;
}
static bool unseal(uint64_t v, int& type, uint64_t& data) {
    uint32_t L = (uint32_t)(v >> 32), R = (uint32_t)v;
    for (int i = 3; i >= 0; i--) { uint32_t t = R ^ fmix32(L ^ SKEY[i]); R = L; L = t; }
    uint64_t x = ((uint64_t)L << 32) | R;
    uint64_t b = x & ((1ULL << 52) - 1);
    if ((x >> 52) != check12(b)) return false;
    type = (int)(b >> 48); data = b & ((1ULL << 48) - 1);
    return true;
}
static inline int roundFrom9(int r9) { return ROUND - ((ROUND - r9) & 511); }
static inline uint64_t earlyBits() {
    return earlyQ < 999 ? (uint64_t)max(0, min(30, (earlyQ - 200) / 8)) : 31ULL;
}
static void takeEarly(int bits) {
    if (bits >= 31 || !P.fPhase) return;
    earlyQ = min(earlyQ, 200 + 8 * bits);
}

// status: head 12, dir 2, len 6, sym 2 (3 unknown), mode 2, conf 2, sat queen 1, home 12, home origin 1,
// early 5, id low 3
static uint64_t packStatus(int cell, int dir) {
    uint64_t d = (uint64_t)cell | ((uint64_t)dir << 12) | ((uint64_t)min(MY_LEN, 63) << 14) |
                 ((uint64_t)(SYM >= 0 ? SYM : 3) << 20) | ((uint64_t)(mapMode & 3) << 22) |
                 ((uint64_t)min(modeConf, 3) << 24) | ((uint64_t)(satQueen ? 1 : 0) << 26) |
                 ((uint64_t)(homeCell >= 0 ? homeCell : 0) << 27) | ((uint64_t)(homeCell >= 0 && homeOrigin ? 1 : 0) << 39) |
                 (earlyBits() << 40) | ((uint64_t)(MY_ID & 7) << 45);
    return seal(PK_STATUS, d);
}
static uint64_t packQueenInfo(int type, const QueenInfo& q) {
    uint64_t d = (uint64_t)q.cell | ((uint64_t)min(q.len, 1023) << 12) | ((uint64_t)(q.round & 511) << 22) |
                 ((uint64_t)(q.id & 4095) << 31) | (earlyBits() << 43);
    return seal(type, d);
}
static bool unpackQueenInfo(uint64_t d, QueenInfo& q) {
    q.cell = (int)(d & 4095);
    if (q.cell >= N) return false;
    q.len = (int)((d >> 12) & 1023);
    q.round = roundFrom9((int)((d >> 22) & 511));
    q.id = (int)((d >> 31) & 4095);
    return true;
}
// up to three fast tiles we have learnt, 12-bit cell and 4-bit gap each
static uint64_t packFount(int rot) {
    vector<pair<int, int>> fast;
    for (int c = 0; c < N; c++)
        if (lrnN[c] > 0 && lrnMax[c] <= 8) fast.push_back({c, max(1, (lrnMin[c] + lrnMax[c]) / 2)});
    if (fast.empty()) return 0;
    // fastest first, and only the fastest dozen rotate, so rush-worthy fountains spread quickly
    stable_sort(fast.begin(), fast.end(), [](const pair<int, int>& a, const pair<int, int>& b) { return a.second < b.second; });
    if (fast.size() > 12) fast.resize(12);
    uint64_t d = 0;
    int k = (int)fast.size();
    for (int j = 0; j < 3 && j < k; j++) {
        auto& f = fast[(rot * 3 + j) % k];
        d |= ((uint64_t)f.first | ((uint64_t)min(15, f.second) << 12)) << (16 * j);
    }
    return seal(PK_FOUNT, d);
}

static void considerQueen(const QueenInfo& q) {
    if (q.cell < 0) return;
    bool stale = ROUND - queen.round > 40;
    if (q.id == queen.id) { if (q.round >= queen.round) queen = q; return; }
    if (stale || q.len > queen.len || (q.len == queen.len && q.id < queen.id)) queen = q;
}
static void considerEnemyQ(const QueenInfo& q) {
    if (q.cell < 0) return;
    bool stale = ROUND - eq.round > 30;
    if (q.id == eq.id) { if (q.round >= eq.round) eq = q; return; }
    if (stale || q.len > eq.len) eq = q;
}

static int foreignMsgs = 0;
static void readInbox() {
    heard.clear();
    for (uint64_t v : V.msgs) {
        int type; uint64_t d;
        if (!unseal(v, type, d)) {
            // enemy sonar: count it, and if it looks like a cell on one of our lines, the
            // sender may be announcing its own position
            foreignMsgs++;
            if (P.fReadEnemy && v > 0 && v < (uint64_t)N && !body.empty() && body[0] >= 0) {
                int c = (int)v;
                if ((c % W == body[0] % W || c / W == body[0] / W) && viewIndex[c] < 0)
                    radarExpire[c] = max(radarExpire[c], ROUND + 3);
            }
            continue;
        }
        if (type == PK_STATUS) {
            HeardAlly a;
            a.cell = (int)(d & 4095); a.dir = (int)((d >> 12) & 3); a.len = (int)((d >> 14) & 63); a.round = ROUND;
            if (a.cell >= N) continue;
            bool mine = false;
            for (int c : body) if (c == a.cell) mine = true;
            if (!mine) heard.push_back(a);
            int s = (int)((d >> 20) & 3), md = (int)((d >> 22) & 3), cf = (int)((d >> 24) & 3);
            if (s < 3 && SYM < 0 && !KM && !symBad[s]) setSym(s);
            if (md > 0 && cf > modeConf && ROUND < 280 && modeConf < 3) setMode(md, cf);
            // one saturation queen per neighbourhood: the longer one (then the lower id) keeps the role
            if (((d >> 26) & 1) && satQueen && !mine &&
                (a.len > MY_LEN || (a.len == MY_LEN && (int)((d >> 45) & 7) < (MY_ID & 7))))
                satQueen = false, satResignUntil = ROUND + 30;
            int hc = (int)((d >> 27) & 4095);
            bool ho = (d >> 39) & 1;
            if (ho && !homeOrigin && hc < N) { homeCell = hc; homeOrigin = true; }
            takeEarly((int)((d >> 40) & 31));
        } else if (type == PK_QUEEN || type == PK_ENEMYQ) {
            QueenInfo q;
            if (!unpackQueenInfo(d, q) || q.round > ROUND) continue;
            if (type == PK_QUEEN) considerQueen(q); else considerEnemyQ(q);
            takeEarly((int)((d >> 43) & 31));
        } else if (type == PK_FOUNT) {
            for (int j = 0; j < 3; j++) {
                int c = (int)((d >> (16 * j)) & 4095), g = (int)((d >> (16 * j + 12)) & 15);
                if (g == 0 || c >= N || KM || lrnN[c] > 0) continue;
                learnGap(c, g);
            }
        }
    }
}

static void updateQueen() {
    QueenInfo me; me.cell = body[0]; me.len = MY_LEN; me.round = ROUND; me.id = MY_ID;
    considerQueen(me);
    for (auto& dr : others)
        if (dr.team == MY_TEAM && dr.headCell >= 0) {
            QueenInfo f; f.cell = dr.headCell; f.len = dr.estLen; f.round = ROUND; f.id = dr.id;
            considerQueen(f);
        }
    for (auto& dr : others)
        if (dr.team != MY_TEAM && dr.headCell >= 0 && dr.estLen >= 6) {
            QueenInfo f; f.cell = dr.headCell; f.len = dr.estLen; f.round = ROUND; f.id = dr.id;
            considerEnemyQ(f);
        }
    if (ROUND - queen.round > 40) queen = me;
}

// Phase timing. The measured schedule (maze: queen 340, feed 350, late feed 440, budding to
// 420 or 300; big feed: queen 400, feed 350, budding to 330) is kept relative to the queen
// round Q, and Q moves earlier when the game calls for it: a giant enemy, or a swarm that
// has already collapsed.
static void applyPhase() {
    int base = bigFeed ? 400 : 340;
    if (P.fPhase && ROUND >= 150 && ROUND < 400) {
        // giant trigger: an enemy dragon far longer than our queen wins the tiebreak unless we
        // start growing ours now (heard over sonar, so the whole swarm switches together)
        if (eqFresh(30) && eq.len >= max(12, queen.len + 3)) earlyQ = min(earlyQ, max(ROUND + 10, 240));
        if (ROUND >= 250 && UNITS <= 5) earlyQ = min(earlyQ, max(ROUND + 10, 260));
    }
    int Q = min(base, max(earlyQ, 240));
    if (!P.fPhase) Q = base;
    P.protectFrom = Q;
    if (bigFeed) {
        P.feedFrom = Q - 50; P.gossipFrom = min(300, Q - 100); P.budUntil = Q - 70;
        P.endFeedFrom = Q + 40; budLateUntil = P.budUntil;
    } else {
        P.feedFrom = Q + 10; P.endFeedFrom = Q + 100; P.gossipFrom = min(300, Q - 40);
        P.budUntil = Q - 40; budLateUntil = Q + 80;
    }
    P.mineUntil = min(300, P.gossipFrom);
}
static bool iAmQueen() { return queen.id == MY_ID; }
static bool protectedQueen() { return !bigFeed && ROUND >= P.protectFrom && (queen.id == MY_ID || MY_LEN >= queen.len) && MY_LEN >= (ROUND >= 400 ? 6 : 4); }
static bool outranks(int len, int id) { return len > MY_LEN || (len == MY_LEN && id < MY_ID); }
// late tiebreak consolidation on maze maps: the longest dragon decides, so pour mass into the queen
static bool lateFeed() { return !bigFeed && ROUND >= P.endFeedFrom && UNITS >= 6; }

// feeding: a small dragon near the queen turns itself into pearls right in her path
// endgame length: the longest dragon decides first and total length second. A safe lead
// keeps the total (feeding loses half of every drone); a close race pours everything in.
static int endLenState() {
    if (!P.fEndLen || ROUND < P.endLenFrom) return 0;
    if (eqFresh(40) && queen.len >= eq.len + 4) return 1;
    if (ROUND >= 480 && (!eqFresh(60) || eq.len >= queen.len - 3)) return 2;
    return 0;
}
static bool tryFeed() {
    if (satQueen && !iAmQueen() && MY_LEN >= 6) return false;
    int els = endLenState();
    if (els == 1) return false;
    if (ROUND < P.feedFrom || iAmQueen() || !outranks(queen.len, queen.id) || ROUND - queen.round > 25) return false;
    if (queen.cell < 0 || torusDist(queen.cell, body[0]) > P.feedRadius) return false;
    for (auto& dr : others) {
        // only a clearly longer dragon we can see is worth dying for; it must be able to eat us
        bool worthy = bigFeed ? (dr.id == queen.id || dr.estLen >= MY_LEN + 3)
                              : (dr.estLen >= max(10, 2 * MY_LEN) || (lateFeed() && dr.id == queen.id && dr.estLen >= MY_LEN + 2));
        if (els == 2 && dr.id == queen.id && dr.estLen >= MY_LEN + 1) worthy = true;
        if (dr.team != MY_TEAM || dr.headCell < 0 || !worthy) continue;
        if (torusDist(dr.headCell, body[0]) <= 3) {
            printf("SPLIT 1\n");  // illegal on purpose: we die and crystallise into pearls
            indicator = "FEED " + to_string(dr.id);
            return true;
        }
    }
    return false;
}

// A scout heads for the richest contested area, not the nearest fast tile: the spawn rate summed
// over a 7x7 block, open tiles counting double (a lone fountain in a one-wide lane is a death
// trap). Our own side keeps until later, the middle goes to whoever gets there first, so areas
// about as close to the enemy's spawn as to ours count fully and the rest a third.
// Uses distA from the last evaluate() from our head.
static int scoutCell = -1, scoutTick = -100;
static int scoutGoal() {
    if (ROUND - scoutTick < 10 && scoutCell >= 0) return scoutCell;
    scoutTick = ROUND;
    static double rate[MAXN];
    for (int c = 0; c < N; c++) {
        rate[c] = gmax[c] > 0 ? 1.0 / max(1.0, 0.5 * (gmin[c] + gmax[c])) : 0.0;
        if (degS[c] >= 3) rate[c] *= 2.0;
    }
    int foe = (SYM >= 0 && homeCell >= 0) ? mirrorCell(homeCell) : -1;
    double best = 0; scoutCell = -1;
    for (int c = 0; c < N; c++) {
        int d = distA[c];
        if (d <= 0 || d > 60) continue;
        double contest = 1.0;
        if (foe >= 0) {
            int dh = torusDist(c, homeCell), df = torusDist(c, foe);
            if (dh > df + 2) continue;
            if (df > dh + 4) contest = 0.35;
        }
        double r = 0;
        int x = c % W, y = c / W;
        for (int dy = -3; dy <= 3; dy++)
            for (int dx = -3; dx <= 3; dx++)
                r += rate[((y + dy + H) % H) * W + (x + dx + W) % W];
        double v = r * contest * powT[d];
        if (v > best) { best = v; scoutCell = c; }
    }
    return scoutCell;
}

static bool firstTurn = true;
static void initProcess() {
    if (!firstTurn) return;
    firstTurn = false;
    homeCell = body[0];
    homeOrigin = ROUND == 0;
    if (P.fScouts && ROUND == 0) {
        int rank = 0;  // among the starting dragons in view; spawns are close together
        for (auto& dr : others) if (dr.team == MY_TEAM && dr.id < MY_ID) rank++;
        scout = rank < P.nScouts;
    }
}

// Saturation queen: once the swarm is as big as budding can usefully make it, extra buds add
// little, so the locally longest dragon stops budding and grows. It starts early on rich maps
// and late on poor ones. The late-queen rules take over from the queen round.
static void updateSatQueen() {
    if (!P.fSatQueen) { satQueen = false; return; }
    int satUnits = min(unitsTarget(), UNIT_LIMIT - 4);
    if (satQueen) {
        bool outgrown = queen.id != MY_ID && queen.len >= MY_LEN + 2 && ROUND - queen.round <= 25;
        if (MY_LEN < 4 || outgrown || UNITS < satUnits - 8) satQueen = false;
        return;
    }
    if (ROUND >= P.protectFrom || ROUND < satResignUntil || UNITS < satUnits || MY_LEN < 4 || queen.id != MY_ID) return;
    satQueen = true;
}

static void think() {
    buildDragons();
    initProcess();
    readInbox();
    buildReaches();
    computeCap();
    updateQueen();
    classifyOnline();
    applyPhase();
    updateSatQueen();
    {
        int mine = 0, theirs = 0;
        for (auto& o : others) if (o.headCell >= 0) (o.team == MY_TEAM ? mine : theirs)++;
        if (P.fReserves)
            for (auto& a : heard) if (viewIndex[a.cell] < 0 && torusDist(a.cell, body[0]) <= 6) mine++;
        localSup = mine + 1 > theirs;
    }
    if (tryFeed()) return;
    dumpState();
    chosenCells.clear();

    // candidates: four single steps, plus two-step sprints when an enemy is close
    // commit to a goal: the best target from where we stand, sticky across turns
    {
        goalCell = -1; goalDistNow = -1;
        SimResult here; here.body = body; here.len = MY_LEN;
        recordVals = true;
        Eval he = evaluate(here, false);
        recordVals = false;
        int best = he.targetCell;
        int g = best;
        if (lastGoal >= 0 && lastGoal != best && best >= 0 && distA[lastGoal] > 0 && valT[lastGoal] >= 0.75 * valT[best])
            g = lastGoal;
        if (g >= 0 && distA[g] > 0) { goalCell = g; goalDistNow = distA[g]; }
        if (scout && ROUND < P.scoutUntil) {
            int sg = scoutGoal();
            if (sg >= 0 && distA[sg] > 2) { goalCell = sg; goalDistNow = distA[sg]; }
            else if (sg >= 0 && distA[sg] >= 0) scout = false;  // arrived: mine the area like everyone else
        }
        feeding = ROUND >= P.feedFrom && !iAmQueen() && (bigFeed ? outranks(queen.len, queen.id) : (queen.len >= max(10, 2 * MY_LEN) || (lateFeed() && queen.len >= MY_LEN + 2)))
                  && ROUND - queen.round <= 25
                  && queen.cell >= 0 && torusDist(queen.cell, body[0]) <= P.feedRadius;
        if (feeding && queen.cell >= 0 && distA[queen.cell] != 0) {
            int qd = distA[queen.cell];
            if (qd < 0) {  // her head cell is occupied: aim next to it
                for (int d = 0; d < 4; d++) { int n = nbr[queen.cell * 4 + d]; if (n >= 0 && distA[n] > 0 && (qd < 0 || distA[n] < qd)) qd = distA[n], g = n; }
            } else g = queen.cell;
            if (qd > 0) { goalCell = g; goalDistNow = qd; }
        }
        hunting = !feeding && huntTarget() && MY_LEN <= 5 && !iAmQueen() && !satQueen && UNITS >= 3 &&
                  torusDist(eq.cell, body[0]) <= P.huntRadius;
        if (hunting) {
            int hd = -1, hg = -1;
            for (int d = 0; d < 4; d++) {
                int n = nbr[eq.cell * 4 + d];
                if (n >= 0 && distA[n] > 0 && (hd < 0 || distA[n] < hd)) { hd = distA[n]; hg = n; }
            }
            if (hd > 0) { goalCell = hg; goalDistNow = hd; } else hunting = false;
        }
        hereRoom = he.room;
        lastGoal = goalCell;
    }
    struct Opt { vector<int> dirs; SimResult sim; Eval ev; };
    vector<Opt> opts;
    for (int d = 0; d < 4; d++) {
        Opt o; o.dirs = {d}; o.sim = simulate(o.dirs);
        if (!o.sim.dead) opts.push_back(o);
    }
    bool threat = false;
    for (auto& er : reaches) for (auto& pc : er.cells) if (pc.second <= 2 && torusDist(pc.first, body[0]) <= 1) threat = true;
    if (MY_LEN >= 8 && !endgame()) {
        bool anyThreat = threat;
        if (anyThreat) {
            for (int a = 0; a < 4; a++) for (int b = 0; b < 4; b++) {
                if (b == opp(a)) continue;
                Opt o; o.dirs = {a, b}; o.sim = simulate(o.dirs);
                if (!o.sim.dead) opts.push_back(o);
            }
        }
    }
    // race sprints: a pearl two steps away that an enemy reaches as soon as we do
    vector<char> race(opts.size(), 0);
    if (P.fSprintGain && MY_LEN >= 5 && !(endgame() && iAmQueen())) {
        for (int a = 0; a < 4; a++) for (int b = 0; b < 4; b++) {
            if (b == opp(a)) continue;
            int c1 = nbr[body[0] * 4 + a];
            if (c1 < 0) continue;
            int c2 = nbr[c1 * 4 + b];
            if (c2 < 0 || !pearlNow(c2) || enemyDist[c2] > 2 || pearlNow(c1)) continue;
            if (enemyDist[c2] == 2 && P.fMoveOrder && enemyMinId[c2] > MY_ID) continue;  // we get there first anyway
            Opt o; o.dirs = {a, b}; o.sim = simulate(o.dirs);
            if (!o.sim.dead) { opts.push_back(o); race.push_back(1); }
        }
    }
    for (size_t i = 0; i < opts.size(); i++) {
        opts[i].ev = evaluate(opts[i].sim, true);
        if (i < race.size() && race[i]) opts[i].ev.score += 0.8;  // the pearl we deny them
    }
    sort(opts.begin(), opts.end(), [](const Opt& a, const Opt& b) {
        if (a.ev.safeClass != b.ev.safeClass) return a.ev.safeClass > b.ev.safeClass;
        return a.ev.score > b.ev.score;
    });
    // a sprint costs a segment: take it only when it beats the best single step by a margin
    if (P.fSprintGain && !opts.empty() && opts[0].dirs.size() > 1 && opts[0].ev.pDeath < 0.5) {
        for (size_t i = 1; i < opts.size(); i++)
            if (opts[i].dirs.size() == 1 && opts[i].ev.safeClass >= opts[0].ev.safeClass) {
                if (opts[0].ev.score - opts[i].ev.score < 0.5) swap(opts[0], opts[i]);
                break;
            }
    }
    if ((opts.empty() || opts[0].ev.pDeath >= (MY_LEN >= 8 ? 0.5 : 0.9)) && MY_LEN >= 3) {
        // sprinting sheds tail segments, which can be what lets us fit
        vector<Opt> extra;
        for (int k = 2; k <= min(3, MY_LEN - 1); k++) {
            int total = k == 2 ? 16 : 64;
            for (int code = 0; code < total; code++) {
                Opt o; int cc = code;
                for (int i = 0; i < k; i++) { o.dirs.push_back(cc % 4); cc /= 4; }
                bool rev = false;
                for (int i = 1; i < k; i++) if (o.dirs[i] == opp(o.dirs[i - 1])) rev = true;
                if (rev) continue;
                if (elapsedMs() > 60) break;
                o.sim = simulate(o.dirs);
                if (o.sim.dead) continue;
                o.ev = evaluate(o.sim, true);
                extra.push_back(o);
            }
        }
        for (auto& o : extra) opts.push_back(o);
        sort(opts.begin(), opts.end(), [](const Opt& a, const Opt& b) {
            if (a.ev.safeClass != b.ev.safeClass) return a.ev.safeClass > b.ev.safeClass;
            return a.ev.score > b.ev.score;
        });
    }
    // head is cornered: at the last moment, let the tail escape as a new dragon
    if ((opts.empty() || (opts[0].ev.pDeath >= (protectedQueen() ? 0.99 : 0.9) && opts[0].ev.surv <= 1)) && doomedSplit()) return;
    // a long dragon about to be rammed: let the tail half escape before the head is lost
    if (!opts.empty() && MY_LEN >= 8 && !protectedQueen() && opts[0].ev.danger >= max(3.0, 0.3 * MY_LEN) && doomedSplit(false)) {
        indicator = "DANGER-" + indicator;
        return;
    }
    if (DEBUG && ROUND >= debugFrom && ROUND <= debugTo)
        for (auto& o : opts) {
            string m; for (int d : o.dirs) m += DCH[d];
            printf("LOG opt %s cls%d sc%.2f pd%.2f surv%d rm%d dg%.2f f%.2f t%.2f cor%.2f out%d len%d\n", m.c_str(), o.ev.safeClass,
                   o.ev.score, o.ev.pDeath, o.ev.surv, o.ev.room, o.ev.danger, o.ev.field, o.ev.target, o.ev.corridor,
                   (int)o.sim.outside, o.sim.len);
        }
    bool desperate = opts.empty() || opts[0].ev.pDeath >= 0.95;
    if (findAttack(desperate)) return;

    if (!opts.empty()) {
        // splitting: evaluate staying put (parent does not move this turn)
        SimResult stay; stay.body = body; stay.len = MY_LEN;
        Eval se = evaluate(stay, false);
        if (!protectedQueen() && (opts[0].ev.pDeath < 0.5 || (MY_LEN <= 4 && ROUND < P.mineUntil)) && !opts[0].ev.adjacent && swarmSplit()) return;
        if (!protectedQueen() && (opts[0].ev.pDeath == 0 || MY_LEN > capLen) && trySplit(se)) return;
        auto& o = opts[0];
        emitMove(o.dirs, o.sim.cells);
        chosenBody = o.sim.body; moveKnown = true;
        char tmp[96];
        snprintf(tmp, sizeof tmp, "L%d s%.1f sp%d rm%d f%.2f t%.2f dg%.2f pd%.2f%s", MY_LEN, o.ev.score, o.ev.space, o.ev.room,
                 o.ev.field, o.ev.target, o.ev.danger, o.ev.pDeath, KM ? " K" : "");
        indicator = tmp;
        if (o.ev.targetCell >= 0) indicator += " T" + to_string(o.ev.targetCell % W) + "," + to_string(o.ev.targetCell / W);
        if (scout && ROUND < P.scoutUntil && scoutCell >= 0) indicator += " SC" + to_string(scoutCell % W) + "," + to_string(scoutCell / W);
        return;
    }
    // nothing survives: take the least bad raw step, never into a friend; among equals,
    // die where friends rather than enemies will pick up our pearls
    int bestD = MY_DIR;
    double bestRank = -1;
    for (int d = 0; d < 4; d++) {
        int n = nbr[body[0] * 4 + d];
        double rank;
        if (n < 0) rank = 1;                                   // kelp: only we die
        else if (!occId[n]) rank = 4;                          // free (only unseen risk)
        else {
            int id = occId[n] - 1;
            bool friendly = false;
            for (auto& dr : others) if (dr.id == id) friendly = dr.team == MY_TEAM;
            if (id == MY_ID) rank = 1;
            else if (friendly) rank = 0;
            else rank = occHead[n] ? 3 : 2;                    // take an enemy with us
        }
        if (P.fDieNearFriends && n >= 0) rank += 0.3 * (friendDist[n] <= 4) - 0.3 * (enemyDist[n] <= 4);
        if (rank > bestRank) { bestRank = rank; bestD = d; }
    }
    emitMove({bestD}, {});
    indicator = "DOOMED " + dsWhy;
}

// Four rays after every action. Forward carries our status and is the radar; the other
// three gossip (queen, enemy giant, fountains). Each ray is traced through what we can see,
// so next turn's echo counts can be split between the rays that left our view.
static void traceRay(const vector<int>& pb, int start, int dir, RayRec& r) {
    r.kind = -1; r.unseen.clear();
    int c = start;
    for (int k = 0; k < W + H; k++) {
        int n = nbr[c * 4 + dir];
        if (n < 0) { if (r.unseen.empty()) r.kind = 0; break; }
        c = n;
        if (viewIndex[c] < 0) { r.unseen.push_back(c); continue; }
        int kind = -1;
        for (size_t i = 0; i < pb.size(); i++) if (pb[i] == c) { kind = i == 0 ? 2 : 1; break; }
        if (kind < 0 && occId[c] && occId[c] != MY_ID + 1)
            kind = occTeam[c] == MY_TEAM ? (occHead[c] ? 2 : 1) : (occHead[c] ? 4 : 3);
        if (kind >= 0) { if (r.unseen.empty()) r.kind = kind; break; }
    }
    if (!r.unseen.empty()) r.kind = -2;
}
static void castRays() {
    nRays = 0; raysValid = false;
    if (body.empty() || body[0] < 0) return;
    const vector<int>& pb = moveKnown ? chosenBody : body;
    if (pb.empty() || pb[0] < 0) return;
    int head = pb[0], hd = MY_DIR;
    if (moveKnown && !chosenCells.empty()) {
        int prev = chosenCells.size() >= 2 ? chosenCells[chosenCells.size() - 2] : body[0];
        for (int d = 0; d < 4; d++) if (nbr[prev * 4 + d] == head) hd = d;
    }
    bool gossip = ROUND >= P.gossipFrom;
    uint64_t status = packStatus(head, hd);
    uint64_t fount = (!KM && !gossip) ? packFount(ROUND) : 0;
    uint64_t qv = packQueenInfo(PK_QUEEN, queen);
    uint64_t ev = eqFresh(20) ? packQueenInfo(PK_ENEMYQ, eq) : 0;
    int dirs[4] = {hd, (hd + 3) % 4, (hd + 1) % 4, opp(hd)};
    uint64_t vals[4];
    vals[0] = status;
    if (gossip) { vals[1] = qv; vals[2] = qv; vals[3] = ev ? ev : qv; }
    else { vals[1] = status; vals[2] = fount ? fount : status; vals[3] = ev ? ev : status; }
    int L = (int)pb.size();
    bool tailOk = L >= 2 && pb[L - 1] >= 0 && pb[L - 2] >= 0;
    for (int r = 0; r < 4; r++) {
        int start = head, dir = dirs[r];
        if (r == 3) {
            // a ray sent backwards leaves from the tail, pointing away from the body
            if (!tailOk) continue;
            start = pb[L - 1]; dir = -1;
            for (int d = 0; d < 4; d++) if (nbr[pb[L - 2] * 4 + d] == pb[L - 1]) dir = d;
            if (dir < 0) continue;
        }
        traceRay(pb, start, dir, rays[nRays]);
        nRays++;
        printf("SONAR %c %llu\n", DCH[dirs[r]], (unsigned long long)vals[r]);
    }
    raysValid = moveKnown;
}

static void fallback() {
    int head = -1;
    for (auto& q : V.parts) if (q.id == MY_ID && q.head) head = q.cell;
    if (head >= 0) {
        for (int d = 0; d < 4; d++) {
            int i = viewIndex[head];
            if (i < 0 || V.ek[i][d] != 1) continue;
            int n = stepRaw(head, d);
            if (viewIndex[n] >= 0 && occId[n] == 0) { printf("MOVE %c\n", DCH[d]); return; }
        }
    }
    printf("MOVE %c\n", DCH[MY_DIR]);
}

int main() {
    setvbuf(stdout, nullptr, _IOFBF, 1 << 16);
    if (!nextLine()) return 0; MY_ID = (int)labelled();
    nextLine(); { char* p = skipWord(buf); while (*p == ' ') p++; MY_TEAM = (*p == 'A') ? 0 : 1; }
    nextLine(); { char* p = skipWord(buf); W = (int)strtol(p, &p, 10); H = (int)strtol(p, &p, 10); }
    nextLine(); UNIT_LIMIT = (int)labelled();
#if __has_include("flags_cfg.hpp")
#include "flags_cfg.hpp"
#endif
    initKnowledge();
#if __has_include("debug_cfg.hpp")
#include "debug_cfg.hpp"
    DEBUG = true; debugFrom = DEBUG_FROM; debugTo = DEBUG_TO;
#endif
    for (int i = 0; i < 256; i++) { powG[i] = pow(P.gamma, i); powT[i] = pow(0.94, i); powM[i] = pow(P.minerGamma, i); }
    for (int c = 0; c < MAXN; c++) vt[c] = INT32_MIN / 2;

    while (readTurn()) {
        T0 = chrono::steady_clock::now();
        indicator.clear();
        moveKnown = false;
        try {
            absorbView();
            think();
            castRays();
        } catch (...) {
            fallback();
        }
        if (!indicator.empty()) printf("INDICATOR %s\n", indicator.c_str());
        printf("PROTOCOL 3\nENDTURN\n");
        fflush(stdout);
        // remember what we did for body tracking
        lastPath = chosenCells;
        havePrev = true;
    }
    return 0;
}
