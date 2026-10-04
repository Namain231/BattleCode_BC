#define QS_STATS
#include <unordered_set>
// Y.8m (Y.8a-n4, fixes on maze maps only): n3 network (top wins + upset winners + winners vs us); p2Drone 0.15; minerGamma 0.90; blind portal step 2.0
// nn forward: padded convolutions (build 2)
// Viper V6 "Leviathan" -- C++ rewrite.
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
#include "policy_nn_v6.hpp"   // V6 net: 19 planes + 6 scalars -> 7 logits

using namespace std;

// ---------------------------------------------------------------- tunables --

struct Params {
    int qposFrom = 12; // 0 preserves the legacy r200 QPOS schedule
    bool encryptPayload = true, statusRay = true, guardZone = true;
    bool guardIntercept = true, laneEcho = true, enemyPing = true, qFreeze = false;
    int laneRays = 4; // 3 omits the back ray and its inference

    // pearl field
    double gamma = 0.86;         // per-step discount of pearl value
    double wField = 0.22;        // weight of the discounted pearl sum
    double wTarget = 1.6;        // weight of the single best pearl
    double decayTau = 70.0;      // rounds for a remembered pearl to be presumed eaten
    int fieldCap = 90;           // BFS depth that still contributes to the field
    // competition discounts
    double enemyCloser = 0.55, enemyTie = 0.8, friendCloser = 0.08;
    // danger (probability an enemy head at distance d attacks)
    double p1 = 0.85, p2 = 0.15, p3 = 0.03, p2Drone = 0.15, p3Drone = 0.10;
    // death penalty on top of our own length
    double deathExtra = 30.0;
    bool search1 = true; // SEARCH1
    bool qSearch = true; // QS
    double spaceBonus = 0.6;
    double wPocket = 1.5;
    // attacks
    int attackMargin = 2;        // enemy must be this much longer than us
    int attackMaxSteps = 4;
    // hunting (small dragons steer towards big enemy heads)
    double wProgress = 0.8;     // per step of progress towards the committed goal
    int budAt = 4;              // swarm: split a length-2 child off at this length
    int mineUntil = 300;
    double minerGamma = 0.90;   // miners judge targets on a short horizon: eat what is near
    double minerFarmCap = 1.5;        // greedy mining only while the swarm is still expanding
    int budUntil = 300;         // stop budding late so the dragons grow for the tiebreak
    int feedFrom = 350;
    int endFeedFrom = 440;      // maze maps: from here drones also feed a queen only slightly longer than them
    int feedRadius = 25;        // Y.9.1: vB.19's radius + 10-unit floor (Y.9's FUNNEL collapsed 51 -> 2 units vs python.io)
    int protectFrom = 200;      // GROWER (Y.9.5): ladder A/B on new maps vs 3 top teams 5/15 vs 2/15 (longest 37-27, 32-26 flips); was 400      // from here the longest dragon never splits voluntarily         // from here, small dragons feed themselves to the queen
    int gossipFrom = 300;       // sonar gossip of the queen's position (disables the radar)
    int huntMaxLen = 5;
    double wHunt = 2.2;
    // splitting
    int splitMinLen = 24;
    int splitChild = 6;         // 0 = split in half
    int splitRoundMax = 300;
    // endgame: rounds before the end where greed stops mattering
    int endgameRounds = 25;
    // move-imitation network (top teams' replays): score += wNN * log p(move) while ROUND < nnUntil
    double wNN = 2;             // HYBRID build of the rules line (same code, network on)
    int nnUntil = 500;
    int qfeedFrom = 280;        // QFEED: from here feed the TRUE queen (queen length decides at r500)
    int compassUntil = 150; // COMPASS: early rich-region scouting window.
    double wCompass = 0.8; // COMPASS: score per step toward the selected region.
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
static int MAP_TEAM = -1;  // SWAPFIX: our team's index in the map file's DRAGON lines (ladder maps may swap A/B)
static inline bool isTrueQueen() { return MY_ID <= 1; }  // QID: queens are ids 0 and 1, but WHICH team owns id 0 depends on the map (ladder maps swap)  // NEWRULES
static inline bool isQueenId(int id) { return id >= 0 && id <= 1; }
static int probeDir = -1, probeCell = -1, probeRound = -10;  // PPROBE: last turn's ray through a portal next to the head
static int ECHO[5];  // kelp, ally, ally head, enemy, enemy head (from last turn's sonar)
static int trueQueenCell = -1, trueQueenRound = -1000;  // QPOS: latest reported true-queen location
static int qHeading=0, qMode=0;
static bool enemyPingNow=false, qThreat=false;
struct GuardStatus { int cell, round, id, heading, len, threat, td, hops, enemyLen; };
static vector<GuardStatus> guardFriends;
static uint64_t guardRelay=0; static int guardRelayKind=0;
static int relaySeen[5][4096];
static int relayId=-1, relayRound=-1, emittedSplit=0;
static bool ambiguousRadar=false;
static bool qgEnabled() { return P.qposFrom || P.encryptPayload || P.statusRay || P.guardZone || P.guardIntercept || P.laneEcho || P.enemyPing || P.qFreeze; }
struct EchoLane { vector<int> cells; int resolved=-1; bool kelp=true, unknown=false; int dir=0; };
static vector<EchoLane> echoLanes;
static double laneRisk[MAXN];
static bool huntLongActive = false; // HUNTL
static int huntLongId = -1, huntLongLen = 0; // HUNTL

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
static int SYM = -1;           // 0 flip x, 1 flip y, 2 rotate; valid with KM
static int nbr[MAXN * 4];      // destination, -1 blocked
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
    nbrDirty = false;
}

// pearl memory
static int seenR[MAXN];
static bool pearlSeen[MAXN];
static int spawnAt[MAXN];      // absolute round of next spawn attempt; -1 never; -2 unknown
static int mirSpawn[MAXN];     // spawn round learnt from the mirror tile; -2 unknown
static int gmin[MAXN], gmax[MAXN];  // -1 unknown
static int memExpire[MAXN];   // round until which an unseen cell is presumed still occupied
static double regionRate[MAXN]; // COMPASS: radius-3 production estimate from map gaps.
static int compassDist[MAXN], compassOurStartDist[MAXN], compassEnemyStartDist[MAXN]; // COMPASS
static bool regionRateReady = false, compassStartReady = false;
static bool compassMap = false, compassActive = false;
static int compassTeamUsed = -1;  // SWAPFIX
static int maxEnemyId = -1;   // enemies that split constantly run into high ids
static int maxKnownId = -1; // SECURE
static bool swarm = false;
static int radarExpire[MAXN]; // an enemy was echoed somewhere on a ray through this unseen cell
static vector<int> lastRay;   // cells our forward sonar crossed last turn

static int mirrorCell(int c) {
    int x = c % W, y = c / W;
    if (SYM == 0) x = W - 1 - x;
    else if (SYM == 1) y = H - 1 - y;
    else { x = W - 1 - x; y = H - 1 - y; }
    return y * W + x;
}

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

// COMPASS: precompute radius-3 fountain density and spawn-side Voronoi zones for known maps.
static void precomputeCompass() {
    regionRateReady = compassStartReady = false;
    fill(regionRate, regionRate + N, 0.0);
    if (!KM) return;
    if (nbrDirty) rebuildNbr();
    static int seen[MAXN], dist[MAXN], q[MAXN];
    static int stamp = 0;
    for (int center = 0; center < N; center++) {
        ++stamp;
        int qh = 0, qt = 0;
        q[qt++] = center; seen[center] = stamp; dist[center] = 0;
        double rate = 0.0;
        while (qh < qt) {
            int c = q[qh++];
            if (gmax[c] > 0 && gmin[c] + gmax[c] > 0) rate += 2.0 / (gmin[c] + gmax[c]);
            if (dist[c] >= 3) continue;
            for (int d = 0; d < 4; d++) {
                int n = nbr[c * 4 + d];
                if (n < 0 || effK(c, d) == 3 || seen[n] == stamp) continue;
                seen[n] = stamp; dist[n] = dist[c] + 1; q[qt++] = n;
            }
        }
        regionRate[center] = rate;
    }
    regionRateReady = true;
    auto spawnDistances = [&](int team, int* out) {
        fill(out, out + N, -1);
        int qh = 0, qt = 0, idx = 0;
        for (int k = 0; k < KM->n_spawn; k++) {
            int t = KM->spawns[idx], count = KM->spawns[idx + 1], head = KM->spawns[idx + 2];
            idx += 2 + count;
            if (t == team && head >= 0 && head < N && out[head] < 0) { out[head] = 0; q[qt++] = head; }
        }
        while (qh < qt) {
            int c = q[qh++];
            for (int d = 0; d < 4; d++) { int n = nbr[c * 4 + d]; if (n >= 0 && out[n] < 0) { out[n] = out[c] + 1; q[qt++] = n; } }
        }
        return qt > 0;
    };
    int mt = MAP_TEAM >= 0 ? MAP_TEAM : MY_TEAM;  // SWAPFIX
    compassStartReady = spawnDistances(mt, compassOurStartDist) && spawnDistances(1 - mt, compassEnemyStartDist);
    compassTeamUsed = mt;  // SWAPFIX
} // COMPASS

static bool bigFeed = false;  // aggressive (v7.2-style) consolidation on this map
static bool farSight = false; // keep long-range miner targets (ladder panel: short sight lost Dilemma)
static void activateMap(int idx, vector<int8_t>&& k, vector<int>&& p) {
    KM = &KNOWN_MAPS[idx];
    {
        string nm = KM->name;
        // measured on the ladder and in v7.2 vs v7.3: feeding wins Portals, Slithery Fight, Schooltime
        bigFeed = nm == "portals" || nm == "slithery_fight" || nm == "schooltime";
        if (bigFeed) P.budUntil = 330;
    if (bigFeed) { P.p2Drone = 0.40; P.minerGamma = 0.80; }   // open maps: keep the old champion's values (fixes are for maze maps)
        else P.protectFrom = 200;  // GROWER (was 340)  // maze maps: grow one queen for the longest-dragon tiebreak
        farSight = nm == "dilemma";
        compassMap = nm == "schooltime" || nm == "trophy" || nm == "devil"; // COMPASS
    }
    mapK = std::move(k); mapP = std::move(p);
    for (int c = 0; c < N; c++) { gmin[c] = KM->gaps[2 * c]; gmax[c] = KM->gaps[2 * c + 1]; }
    detectSymmetry();
    nbrDirty = true;
    precomputeCompass(); // COMPASS: map gaps/topology are now loaded.
}
static void dropMap() {
    KM = nullptr; SYM = -1;
    regionRateReady = compassStartReady = compassActive = compassMap = false; // COMPASS
    for (int c = 0; c < N; c++) { gmin[c] = gmax[c] = -1; }
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
        // MAPFIX: ladder games often disagree with our stored pearl tables (QoS/Devil/Dilemma/Schooltime lost the
        // known map in ~half the ladder games): identify by kelp/portals only, learn pearl gaps from what we see.
        (void)gaps;
    }
    return true;
}

static void initKnowledge() {
    N = W * H;
    memset(obsK, 0, sizeof obsK);
    for (int c = 0; c < N; c++) {
        seenR[c] = -1; pearlSeen[c] = false; spawnAt[c] = -2; mirSpawn[c] = -2; memExpire[c] = 0; radarExpire[c] = 0;
        gmin[c] = gmax[c] = -1;
    }
    for (int i = 0; i < N_KNOWN_MAPS; i++) {
        if (KNOWN_MAPS[i].w != W || KNOWN_MAPS[i].h != H) continue;
        Candidate cd; cd.idx = i;
        loadMapLayer(KNOWN_MAPS[i], cd.k, cd.p);
        mapCands.push_back(std::move(cd));
    }
    if (mapCands.empty()) mapResolved = true;
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
        seenR[c] = ROUND;
        pearlSeen[c] = V.pearl[i];
        spawnAt[c] = V.ptime[i] < 0 ? -1 : ROUND + V.ptime[i];
        if (V.ptime[i] < 0 && gmax[c] < 0) { gmax[c] = 0; gmin[c] = 0; }
        if (KM) {  // MAPFIX: correct the stored pearl table where the game contradicts it
            if (V.ptime[i] < 0 && gmax[c] > 0) { gmax[c] = 0; gmin[c] = 0; }
            else if (V.ptime[i] >= 0 && gmax[c] == 0) { gmin[c] = 0; gmax[c] = max(1, V.ptime[i]); }
            else if (V.ptime[i] > gmax[c] && gmax[c] > 0) gmax[c] = V.ptime[i];
        }
    }
    if (KM && SYM >= 0) {
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
static int enemyDist[MAXN], friendDist[MAXN], friendMinId[MAXN], enemyMinId[MAXN]; // CX
static const int UNKNOWN_EXTRA = 10;

static vector<int> body;          // head first, -1 unknown
static vector<int> lastPath;      // cells my head entered last turn, in order
static bool havePrev = false;

static int partAt[MAXN];
static int visFree[MAXN], visFreeRound[MAXN];
static int ownLost[MAXN];
static int eatMargin[256];

static void buildDragons() {
    maxKnownId = max(maxKnownId, MY_ID); // SECURE
    const auto& parts = V.parts;
    int np = (int)parts.size();
    for (int i = 0; i < 49; i++) { partAt[V.cell[i]] = -1; }
    for (int c = 0; c < N; c++) { otherBT[c] = 0; occId[c] = 0; occHead[c] = false; zoneE[c] = 0; zoneF[c] = 0; }
    for (int i = 0; i < np; i++) {
        partAt[parts[i].cell] = i;
        occId[parts[i].cell] = parts[i].id + 1;
        occHead[parts[i].cell] = parts[i].head;
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
    // radar: last turn's forward ray hit an enemy we cannot see -> it is somewhere on that line
    if (!ambiguousRadar && ECHO[3] + ECHO[4] > 0 && !lastRay.empty() && ROUND <= P.gossipFrom) {
        bool explained = false;
        for (int c : lastRay) {
            if (viewIndex[c] < 0) break;
            if (occId[c]) { explained = true; break; }
        }
        if (!explained)
            for (int c : lastRay) if (viewIndex[c] < 0) radarExpire[c] = ROUND + (ECHO[4] ? 8 : 5);
    }
    others.clear();
    unordered_map<int, int> idx;
    for (int i = 0; i < np; i++) {
        const Part& q = parts[i];
        maxKnownId = max(maxKnownId, q.id); // SECURE
        if (q.id == MY_ID) continue;
        int extra = certain[i] ? 0 : UNKNOWN_EXTRA;
        visFree[q.cell] = behind[i] + 1 + (certain[i] ? 0 : 2); visFreeRound[q.cell] = ROUND;
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
            if (!chain.empty() && s[pos + 2] == chain[0]) {  // SWAPFIX: match by head cell, not team (ladder swaps)
                MAP_TEAM = team;
                for (int j = 0; j < cnt; j++) pred.push_back(s[pos + 2 + j]);
            }
            pos += 2 + cnt;
        }
    }
    body = chain;
    // SELFTRACK: ladder Slithery vs err404 r460: our L55 giant (and an L29 at r427) died 'hit self' after "DOOMED unknown
    // body": when it coils inside its 7x7 view the visible chain can link the wrong neighbour, the match below fails and
    // the whole tail becomes -1 forever. Our own move history is exact: trust it when it is complete and the head agrees.
    if (havePrev && (int)pred.size() >= MY_LEN && !chain.empty() && pred[0] == chain[0]) {
        bool full = true;
        for (int i = 0; i < MY_LEN; i++) if (pred[i] < 0) { full = false; break; }
        if (full) body.assign(pred.begin(), pred.begin() + MY_LEN);
    }
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
    for (int c = 0; c < N; c++) { enemyDist[c] = 1 << 20; friendDist[c] = 1 << 20; friendMinId[c] = 1 << 20; enemyMinId[c] = 1 << 20; } // CX
    static int q[MAXN];
    for (int pass = 0; pass < 2; pass++) {
        int* dist = pass == 0 ? enemyDist : friendDist;
        int qh = 0, qt = 0;
        for (auto& dr : others) {
            if (dr.headCell < 0) continue;
            if ((dr.team == MY_TEAM) != (pass == 1)) continue;
            if (dist[dr.headCell] > 0) { dist[dr.headCell] = 0; q[qt++] = dr.headCell; }
            if (pass == 1) friendMinId[dr.headCell] = min(friendMinId[dr.headCell], dr.id);
            else enemyMinId[dr.headCell] = min(enemyMinId[dr.headCell], dr.id); // CX
        }
        while (qh < qt) {
            int c = q[qh++];
            if (dist[c] >= 40) continue;
            for (int d = 0; d < 4; d++) {
                int n = nbr[c * 4 + d];
                if (n < 0) continue;
                if (dist[n] > dist[c] + 1) {
                    dist[n] = dist[c] + 1;
                    if (pass == 1) friendMinId[n] = friendMinId[c];
                    else enemyMinId[n] = enemyMinId[c]; // CX
                    q[qt++] = n;
                } else if (pass == 1 && dist[n] == dist[c] + 1) friendMinId[n] = min(friendMinId[n], friendMinId[c]);
                else if (pass == 0 && dist[n] == dist[c] + 1) enemyMinId[n] = min(enemyMinId[n], enemyMinId[c]); // CX
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
    const int freeSteps = max(1, (MY_LEN + 3) / 4);  // NEWRULES
    for (size_t j = 0; j < dirs.size(); j++) {
        if ((int)j >= freeSteps && r.len < 3) { r.dead = true; return r; }
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
        if ((int)j >= freeSteps) { r.body.pop_back(); r.len--; }  // NEWRULES
    }
    return r;
}

// SEARCH1: copy simulate() for a hypothetical resulting body; preserve the original function unchanged.
static SimResult simulateFrom(const vector<int>& startBody, int startLen, const vector<int>& dirs) {
    SimResult r;
    r.body = startBody;
    r.len = startLen;
    vector<int> eaten;
    const int freeSteps = max(1, (startLen + 3) / 4);
    for (size_t j = 0; j < dirs.size(); j++) {
        if ((int)j >= freeSteps && r.len < 3) { r.dead = true; return r; }
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
        if ((int)j >= freeSteps) { r.body.pop_back(); r.len--; }
    }
    return r;
}
// Queen-only branch state; never modifies live simulator or sonar globals.
struct QSDragon { int id, face; vector<int> b; bool alive=true; };
struct QSWorld { vector<QSDragon> ds; vector<int> occ; vector<unsigned char> pearl; };
enum QSReason { QS_BODY,QS_TICK,QS_UNKNOWN,QS_BUDGET,QS_CAP,QS_ACTORS,QS_REASONS };
struct QSStats { unsigned calls=0,triggered=0,eligible=0,complete=0,fatal=0,overrides=0,reject[QS_REASONS]={}; unsigned chargedMax=0,overshoot=0; double msMax=0,turnMax=0,abortMsMax=0; };
static QSStats qsStats;
static bool qsContact=false;
struct QSClock {
    double start; bool aborted=false; unsigned charged=0; int reason=-1;
    static constexpr unsigned LIMIT=4000;
    bool fail(int r){aborted=true;if(reason<0)reason=r;return false;}
    bool charge(unsigned n=1){if(aborted)return false;if(n>LIMIT-charged)return fail(QS_BUDGET);charged+=n;return true;}
    bool stop(){if(!charge())return true;if(elapsedMs()-start>2 || elapsedMs()>54)fail(QS_BUDGET);return aborted;}
};
// Scope accounting includes entry gates and every early return.
struct QSRecord {
    QSClock& t;
    ~QSRecord(){
        double used=elapsedMs()-t.start;qsStats.msMax=max(qsStats.msMax,used);
        qsStats.chargedMax=max(qsStats.chargedMax,t.charged);
        if(t.reason>=0)qsStats.reject[t.reason]++;
        if(t.reason==QS_BUDGET)qsStats.abortMsMax=max(qsStats.abortMsMax,max(0.0,used-2.0));
#ifdef DEBUG_QS
        printf("INDICATOR QSDBG charge%u overshoot%u ms%.3f abort%.3f points%.0f reason%d\n",t.charged,qsStats.overshoot,used,qsStats.abortMsMax,used*1000000,t.reason);
#endif
    }
};
static bool qsEdge(int c,int d,int& n,QSClock& t) {
    if(t.stop())return false;
    int k=effK(c,d);n=nbr[c*4+d];
    if(!k || (k==3 && n<0)){t.fail(QS_UNKNOWN);return false;}return true;
}
static void qsKill(QSWorld& w,int i,QSClock& t) {
    auto& a=w.ds[i];if(!a.alive)return;
    for(size_t j=0;j<a.b.size();j++){if(!t.charge())return;if(!(j&1))w.pearl[a.b[j]]=1;w.occ[a.b[j]]=0;}
    a.alive=false;
}
// Exact single-turn primitive: self including tail first, both heads die at
// every length, pearl growth, fixed ceil(startLength/4) free allowance.
static bool qsMove(QSWorld& w,int i,const vector<int>& path,QSClock& t) {
    auto& a=w.ds[i];if(!a.alive)return true;
    if(path.empty()){qsKill(w,i,t);return !t.aborted;}
    if(a.b.size()>64 || path.size()>16)return t.fail(QS_CAP);
    int freeSteps=(int(a.b.size())+3)/4;
    for(int j=0;j<int(path.size());j++){
        if(t.stop())return false;
        if(j>=freeSteps && a.b.size()<3){qsKill(w,i,t);return true;}
        int n;if(!qsEdge(a.b[0],path[j],n,t))return false;a.face=path[j];
        if(n<0){qsKill(w,i,t);return true;}
        if(viewIndex[n]<0){t.fail(QS_UNKNOWN);return false;}
        int hit=w.occ[n]-1;
        if(hit>=0){if(hit!=i && w.ds[hit].b[0]==n)qsKill(w,hit,t);qsKill(w,i,t);return true;}
        if(!t.charge(unsigned(a.b.size()+2)))return false;
        if(a.b.size()>=64)return t.fail(QS_CAP);
        a.b.insert(a.b.begin(),n);w.occ[n]=i+1;
        if(w.pearl[n])w.pearl[n]=0;
        else {w.occ[a.b.back()]=0;a.b.pop_back();}
        if(j>=freeSteps){w.occ[a.b.back()]=0;a.b.pop_back();}
    }return true;
}
static bool qsBuild(QSWorld& w,vector<int>& enemies,QSClock& t) {
    // Complete occupancy is required: unseen entrants cannot be certified safe.
    if(N>256 || N<=0)return t.fail(QS_UNKNOWN);
    for(int c=0;c<N;c++){if(t.stop())return false;if(viewIndex[c]<0)return t.fail(QS_UNKNOWN);}
    if(body.empty() || body.size()>64 || int(body.size())!=MY_LEN)return t.fail(QS_BODY);
    if(others.empty() || others.size()>3 || V.parts.size()>192)return t.fail(QS_ACTORS);
    for(int j=0;j<49;j++){if(t.stop())return false;if(V.ptime[j]>=0 && V.ptime[j]<=1)return t.fail(QS_TICK);}
    if(!t.charge(N*2+body.size()))return false;
    w.occ.assign(N,0);w.pearl.assign(N,0);w.ds.reserve(4);w.ds.push_back({MY_ID,MY_DIR,body,true});
    for(const auto& dr:others){
        if(t.stop())return false;
        if(dr.headCell<0 || !dr.tailKnown || dr.visCount!=dr.estLen || dr.visCount<2 || dr.visCount>64)return t.fail(QS_BODY);
        // A split creates another intervening actor; this prototype cannot model it.
        if(dr.estLen>=4)return t.fail(QS_ACTORS);
        QSDragon a;a.id=dr.id;a.face=dr.headFace;a.b.reserve(64);int c=dr.headCell;
        for(int j=0;j<dr.visCount;j++){
            if(t.stop())return false;
            for(int old:a.b){if(!t.charge())return false;if(old==c)return t.fail(QS_BODY);}
            a.b.push_back(c);if(j+1==dr.visCount)break;int next=-1;
            for(const auto& p:V.parts){
                if(t.stop())return false;if(p.id!=dr.id || p.head)continue;
                bool used=false;for(int old:a.b){if(!t.charge())return false;if(old==p.cell)used=true;}if(used)continue;
                int n;if(!qsEdge(p.cell,p.face,n,t))return false;
                if(n==c){if(next>=0)return t.fail(QS_BODY);next=p.cell;}
            }
            if(next<0)return t.fail(QS_BODY);c=next;
        }
        enemies.push_back(int(w.ds.size()));w.ds.push_back(a);
    }
    for(int i=0;i<int(w.ds.size());i++)for(int c:w.ds[i].b){if(t.stop())return false;if(c<0 || c>=N || w.occ[c])return t.fail(QS_BODY);w.occ[c]=i+1;}
    for(int c=0;c<N;c++){if(t.stop())return false;w.pearl[c]=pearlNow(c);}
    // At most three actors, including allies; no omitted/frozen actor.
    for(size_t i=0;i<enemies.size();i++)for(size_t j=i+1;j<enemies.size();j++){
        if(t.stop())return false;int a=w.ds[enemies[i]].id,b=w.ds[enemies[j]].id;
        if((b>=MY_ID && a<MY_ID) || ((a>=MY_ID)==(b>=MY_ID) && b<a))swap(enemies[i],enemies[j]);
    }
    return true;
}
static bool qsCopy(const QSWorld& w,QSWorld& out,QSClock& t){
    unsigned cost=unsigned(w.occ.size()+w.pearl.size()+w.ds.size()*4);
    for(const auto& d:w.ds){if(t.stop())return false;cost+=unsigned(d.b.size());}
    if(!t.charge(cost))return false;out=w;return true;
}
struct QSValue { int life=0,space=0,open=0; };
static bool qsBetter(const QSValue& a,const QSValue& b){
    if(a.life!=b.life)return a.life>b.life;
    if(a.space!=b.space)return a.space>b.space;return a.open>b.open;
}
// Branch version of the existing staticSpace survival flood-fill principle;
// frozen occupied cells, at most 48 observed cells, no expensive evaluate().
static QSValue qsLeaf(const QSWorld& w,QSClock& t){
    QSValue v;if(!w.ds[0].alive)return v;v.life=1;int head=w.ds[0].b[0];
    for(int d=0;d<4;d++){int n;if(!qsEdge(head,d,n,t))return {};
        if(n>=0 && viewIndex[n]>=0 && !w.occ[n])v.open++;}
    if(!t.charge(N))return {};
    int q[48]={head},count=1;unsigned char seen[256]={};seen[head]=1;
    for(size_t j=0;j<size_t(count) && count<48;j++)for(int d=0;d<4;d++){
        int n;if(!qsEdge(q[j],d,n,t))return {};
        if(n>=0 && viewIndex[n]>=0 && !w.occ[n] && !seen[n]){
            seen[n]=1;q[count++]=n;if(count==48)break;}
    }v.space=count;return v;
}
static QSValue qsContinue(const QSWorld& w,QSClock& t){
    QSValue best;if(!w.ds[0].alive)return best;QSWorld leaf;
    for(int d=0;d<4;d++)if(d!=opp(w.ds[0].face)){
        if(!qsCopy(w,leaf,t))return {};if(!qsMove(leaf,0,{d},t))return {};
        QSValue v=qsLeaf(leaf,t);if(qsBetter(v,best))best=v;
    }return best;
}
// Enumerate every movement prefix, including paid steps, blocking paths,
// reversals (engine-legal), oversprint death and suicide. Any truncation aborts.
static void qsRams(const QSWorld& w,int ei,int,vector<int>& path,
                   vector<vector<int>>& replies,QSClock& t){
    if(t.stop() || !w.ds[ei].alive)return;
    if(path.size()>=16){t.fail(QS_CAP);return;}
    QSWorld next;
    for(int d=0;d<4;d++){
        if(t.stop())return;
        if(replies.size()>=40){t.fail(QS_CAP);return;}
        path.push_back(d);if(!t.charge(path.size()))return;replies.push_back(path);
        if(!qsCopy(w,next,t))return;
        // Re-simulate the whole sprint: free allowance belongs to start length.
        if(!qsMove(next,ei,path,t))return;
        if(next.ds[ei].alive)qsRams(w,ei,0,path,replies,t);
        path.pop_back();if(t.aborted)return;
    }
}
static QSValue qsReplies(const QSWorld& w,const vector<int>& enemies,int pos,QSClock& t){
    if(t.stop() || !w.ds[0].alive)return {};
    if(pos==int(enemies.size()))return qsContinue(w,t);
    int ei=enemies[pos];if(!w.ds[ei].alive)return qsReplies(w,enemies,pos+1,t);
    vector<vector<int>> replies;replies.reserve(40);replies.push_back({});
    vector<int> path;path.reserve(16);qsRams(w,ei,0,path,replies,t);
    if(t.aborted)return {};
    QSValue worst{1,MAXN,4};QSWorld next;
    for(const auto& reply:replies){if(t.stop())return {};if(!qsCopy(w,next,t) || !qsMove(next,ei,reply,t))return {};
        QSValue v=qsReplies(next,enemies,pos+1,t);if(qsBetter(worst,v))worst=v;}
    return worst;
}
template<class Options> static bool queenSearch(Options& opts){
    qsStats.calls++;QSClock t{elapsedMs()};QSRecord record{t};
    if(!isTrueQueen() || opts.size()<2 || body.empty() || elapsedMs()>50)return false;
    bool trigger=opts[0].ev.pDeath>=0.05 || enemyPingNow || qThreat;
    if(others.size()>3){qsStats.triggered++;qsContact=true;return t.fail(QS_ACTORS);}
    for(const auto& dr:others){if(t.stop())break;if(dr.team!=MY_TEAM && dr.headCell>=0 && torusDist(body[0],dr.headCell)<=10)trigger=true;}
    if(!trigger)return false;qsStats.triggered++;qsContact=true;
    int roots[3]={0,-1,-1};
    if(opts.size()>64)t.fail(QS_CAP);
    for(int i=1;i<int(opts.size()) && !t.aborted;i++){
        if(t.stop())break;if(opts[i].ev.pDeath>opts[0].ev.pDeath+0.15)continue;
        if(roots[1]<0 || opts[i].ev.score>opts[roots[1]].ev.score){roots[2]=roots[1];roots[1]=i;}
        else if(roots[2]<0 || opts[i].ev.score>opts[roots[2]].ev.score)roots[2]=i;
    }
    QSWorld start;vector<int> enemies;int chosen=0;QSValue winner,best;
    bool complete=!t.aborted && qsBuild(start,enemies,t);if(complete)qsStats.eligible++;
    QSWorld branch;
    if(complete)for(int i:roots){
        if(t.stop()){complete=false;break;}if(i<0)continue;
        if(!qsCopy(start,branch,t) || !qsMove(branch,0,opts[i].dirs,t)){complete=false;break;}
        QSValue v=qsReplies(branch,enemies,0,t);if(t.stop()){complete=false;break;}
        if(i==0){winner=best=v;}
        else if(qsBetter(v,best)){best=v;chosen=i;}
    }
    if(complete && !t.aborted){qsStats.complete++;if(!winner.life)qsStats.fatal++;}
    if(!complete || t.aborted || chosen==0 || best.life-winner.life<1)return false;
    qsStats.overrides++;swap(opts[0],opts[chosen]);return true;
}
// ------------------------------------------------------------ evaluation --

static int distA[MAXN], qA[MAXN];
static int ownBT[MAXN], ownStamp[MAXN], stampCtr = 0;
static double powG[256], powT[256], powM[256];
static bool recordVals = false;
static double valT[MAXN];
struct QueenInfo { int cell = -1, len = 0, round = -1000, id = -1; };
static QueenInfo queen;
static int goalCell = -1, lastGoal = -1, goalDistNow = -1;
static bool feeding = false;
static bool iAmQueen(); // COMPASS: keep the elected queen out of the regional pull.

struct EnemyReach { int id; int len; vector<pair<int, int>> cells; vector<unsigned char> arrival; }; // CPU1: exact reach lookup
static vector<EnemyReach> reaches;

static void buildReaches() {
    reaches.clear();
    for (auto& dr : others) {
        if (dr.team == MY_TEAM || dr.headCell < 0) continue;
        EnemyReach er; er.id = dr.id; er.len = dr.estLen;
        vector<int> frontier{dr.headCell};
        // CPU1: preserve BFS order and blocked landing cells, with O(1) membership.
        er.arrival.assign(N, 99);
        er.arrival[dr.headCell] = 0;
        const int spd = max(1, (dr.estLen + 3) / 4);  // NEWRULES
        for (int depth = 1; depth <= 3 * spd; depth++) {
            vector<int> nf;
            for (int c : frontier)
                for (int d = 0; d < 4; d++) {
                    int n = nbr[c * 4 + d];
                    if (n < 0 || er.arrival[n] != 99) continue;
                    er.arrival[n] = (depth + spd - 1) / spd; // CPU1
                    er.cells.push_back({n, (depth + spd - 1) / spd});  // NEWRULES
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
    // CPU1: interrupted searches return only the depth actually reached.
    if ((dfsNodes & 63) == 0 && elapsedMs() >= 48) { dfsNodes = dfsBudget + 1; return t; }
    int best = t;
    int opts[4], score[4], no = 0;
    for (int d = 0; d < 4; d++) {
        int c = nbr[head * 4 + d];
        if (c < 0) continue;
        if (vt[c] >= t - len + 1) continue;
        if (otherBT[c] >= t + 1 || (dfsPessimist && (otherBT[c] > 0 || radarExpire[c] > ROUND || min(enemyDist[c], friendDist[c]) <= t + 1))) continue;
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
            cnt += viewIndex[n] >= 0 ? 1.0 : radarExpire[n] > ROUND ? 0.0 : 0.5;
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

static int pxTarget = -1; static bool pxHungry = false;  // PEXPLORE: nearest seen cell with an unexplored portal edge (hungry drones head there)
static Eval evaluate(const SimResult& s, bool deepAllowed) {
    if (elapsedMs() >= 48) deepAllowed = false; // CPU1
    Eval e;
    const vector<int>& B = s.body;
    int L = s.len;
    int head = B[0];
    // early small drones: short-horizon targets (don't trek to far, contested fountains)
    bool shortSight = !bigFeed && !farSight && UNITS >= 3 && L <= 4 && queen.id != MY_ID && ROUND < P.mineUntil;
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
                    else if (enemyDist[n] == nd && enemyMinId[n] < MY_ID) p *= swarm ? 0.9 : P.enemyTie; // CX
                    if (!meQueen && (friendDist[n] < nd || (friendDist[n] == nd && friendMinId[n] < MY_ID))) p *= P.friendCloser;
                    if (qCell >= 0 && torusDist(qCell, n) < nd) p *= 0.3;
                    p *= shortSight ? min(P.minerFarmCap, farmBonus(n)) : farmBonus(n);
                    fsum += p * powG[nd];
                    double v = p * (shortSight ? powM[nd] : powT[nd]);
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
            long long budget = el >= 48 ? 0 : el > 35 ? 1500 : 12000;
            if (budget == 0) deepAllowed = false;
            int got, pes = 0;
            if (!deepAllowed) got = min(st, target);
            else {
                dfsPessimist = true;
                pes = survivalDepth(B, L, target, budget);
                dfsPessimist = false;
                got = pes >= target ? pes : elapsedMs() >= 48 ? pes : survivalDepth(B, L, target, budget); // CPU1
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
        // CPU1: the starting head was absent from cells in the original BFS.
        if (er.arrival[head] > 0) dd = er.arrival[head];
        double p = 0;
        if (dd == 1) p = P.p1;
        else if (dd == 2 && er.len <= 4) p = P.p2Drone;   // small ones hunt heads
        else if (dd == 2 && er.len >= 3) p = P.p2;
        else if (dd == 3 && er.len <= 4) p = P.p3Drone;
        else if (dd == 3 && er.len >= 4) p = P.p3;
        if (p <= 0) continue;
        // a lost dragon also brings us a unit closer to elimination
        double unitValue = UNITS <= 2 ? 10.0 : UNITS <= 4 ? 5.0 : 2.0;
        double loss = max(0.5, L - 0.8 * er.len + 3.0) + unitValue;
        if (swarm) p = min(0.95, p * 1.4);
        if (ROUND >= P.feedFrom - 30 && queen.id == MY_ID) loss *= (ROUND >= P.protectFrom ? 3.0 : 2.0);
        // anything that can reach our head this coming turn (sprints included) is a real threat
        if ((L >= 6 || UNITS <= 4) && (dd == 1 || (dd <= 3 && dd <= er.len - 1))) adjacentThreat = true;
        if (UNITS == 1) loss = L + 14.0;
        danger += p * loss;
    }
    e.danger = danger;
    if (adjacentThreat) e.safeClass = min(e.safeClass, 1);
    e.adjacent = adjacentThreat;

    // hunting: small dragons drift towards big enemy heads
    double hunt = 0;
    if (L <= P.huntMaxLen && UNITS >= 2) {
        for (auto& dr : others) {
            bool eq = isQueenId(dr.id);  // NEWRULES
            bool press = UNITS >= 30 && dr.estLen >= 2;  // PRESS2
            if (dr.team == MY_TEAM || dr.headCell < 0 || (dr.estLen < L + P.attackMargin && !eq && !press)) continue;
            int best = 1 << 20;
            for (int d = 0; d < 4; d++) {
                int n = nbr[dr.headCell * 4 + d];
                if (n >= 0 && distA[n] >= 0) best = min(best, distA[n] + 1);
            }
            if (head == dr.headCell) best = 0;
            double pull = max(eq ? 4.0 : press ? 1.0 : 0.0, min(3.0, dr.estLen / 6.0));
            if (eq) pull = 8.0; // HUNTL: visible enemy queen has top priority (Claude: 100 would override all foraging)
            else if (huntLongActive && dr.id == huntLongId) pull = max(pull, 12.0); // HUNTL
            if (best < 64) hunt = max(hunt, powG[best] * pull); // HUNTL
        }
    }
    e.hunt = hunt;

    double growth = s.len - MY_LEN;
    double greed = endgame() ? 0.35 : 1.0;
    // QSAFE: ladder Devil vs Quaker r415-426: our queen (theirs dead since r19 = a sure win) chased pearls T26,15 into
    // enemy heads (dg 14-42) and died. Her length only matters vs a living enemy queen: after r100 she barely forages.
    if (isTrueQueen() && ROUND >= 100 && ROUND < P.qfeedFrom) greed *= 0.2;  // QFEED: she eats the feed late
    if (L > capLen && !endgame()) { greed *= 0.3; if (growth > 0) growth *= -0.3; }
    double score = 0;
    if (pxTarget >= 0 && !s.cells.empty() && body[0] >= 0) score += 2.0 * (torusDist(body[0], pxTarget) - torusDist(s.cells.back(), pxTarget));  // PEXPLORE
    score += growth * (endgame() ? 1.5 : 1.0);
    score += greed * (P.wField * fsum + P.wTarget * fmax);
    score += P.wHunt * hunt;
    if (goalCell >= 0 && goalDistNow >= 0) {
        bool ateGoal = find(s.cells.begin(), s.cells.end(), goalCell) != s.cells.end();
        double prog = ateGoal ? 1.0 : e.goalDist < 0 ? -1.5 : max(-2.0, min(2.0, (double)(goalDistNow - e.goalDist)));
        score += (feeding ? 4.0 : greed) * P.wProgress * prog;
    }
    // COMPASS: safe one-step progress toward a chosen rich region; never steer either queen.
    if (compassActive && elapsedMs() <= 40 && compassMap && ROUND < P.compassUntil && !isTrueQueen() && !iAmQueen() && L <= 6 &&
        s.cells.size() <= 1 && e.pDeath <= 0.25 && body[0] >= 0 && head >= 0 &&
        compassDist[body[0]] >= 0 && compassDist[head] >= 0)
        score += P.wCompass * (compassDist[body[0]] - compassDist[head]);
    score -= isTrueQueen() ? 3.0 * (enemyPingNow ? 1.3 : 1.0) * danger : danger;  // QSAFE
    // in a big swarm a small drone is cheap: its death costs little more than its length
    bool cheap = UNITS >= 4 && L <= 4 && queen.id != MY_ID;
    // greedy miner (what every top team does): a small drone dives into dead-end pockets for
    // pearls; it may die there, but it buds a child out first and the swarm grows 2x faster
    // SHAFT: a 2-long drone that enters a dead end can't bud out of it (Devil vs Adrak: 7 of 10 deaths r60-80 were
    // L2-3 drones DOOMED in 1-wide shafts); the miner excuse needs L >= 3 so one pearl lets it bud a child out the back
    // MINE2 (from vB.19, which out-eats us 2x on Autarky with more but cheap L2 deaths): L2 drones mine too, except on
    // Devil (the SHAFT evidence); the true queen never mines; the elected sink may.
    bool isDevilMap = KM && string(KM->name) == "devil";
    bool miner = UNITS >= 3 && (isDevilMap ? (L >= 3 && L <= 4) : (L <= 4)) && !isTrueQueen() && ROUND < P.mineUntil;
    score -= e.pDeath * (L + (isTrueQueen() ? 250.0 : miner ? 1.0 : cheap ? 3.0 : P.deathExtra));  // NEWRULES
    if (!miner) score -= P.wPocket * e.pocket * (2.0 + L / 4.0);
    score += P.spaceBonus * min(1.0, space / (double)(2 * L + 20));
    if (s.outside) {
        // on a known map we know what is behind a portal except for dragons: a modest risk,
        // unless we remember a body on the far side
        bool remembered = !s.cells.empty() && memExpire[s.cells.back()] > ROUND;
        if ((KM || pxHungry) && !remembered) score -= (bigFeed ? 0.8 : 2.0) + 0.03 * L;  // PEXPLORE: a hungry drone may step through a portal on unknown maps
        else { score -= 3.0 + 0.12 * (L + P.deathExtra); e.safeClass = 0; }
    }
    if (isTrueQueen() && s.outside) score -= 120.0;  // NEWRULES + QSAFE (Trauma vs Quaker r362: portal step -> DOOMED)
    // QHIDE: enemy queens die by r50 in nearly every ladder game, so a queen that merely survives wins at r500. Ours died
    // walking into pockets after pearls (hit self/wall) and next to enemy heads: she stays in fully open space, away from heads.
    if (isTrueQueen()) {
        int roomy = min(2 * L + 20, max(0, 499 - ROUND) + 1);
        if (e.room < roomy) score -= 25.0 * (roomy - e.room) / max(1, roomy);
        if (!s.cells.empty()) {
            int ed = enemyDist[s.cells.back()];
            if (ed <= 3) score -= 12.0 * (4 - ed);
            // QFLEE: Default vs Quaker r408: an L5 enemy 2 cells away sprinted EE (free) into her; she had moved toward
            // pearls in a crowded zone. Prefer cells far from every enemy head (up to 8), on top of the danger term.
            score += 1.5 * min(ed, 8);
            // CROWD: friendly bodies around her head are walls too: prefer thin neighbourhoods
            { int crowd = 0, hx = s.cells.back() % W, hy = s.cells.back() / W;
              for (int dy = -2; dy <= 2; dy++) for (int dx = -2; dx <= 2; dx++) {
                  if (abs(dx) + abs(dy) > 2) continue;
                  int c = ((hy + dy + H) % H) * W + (hx + dx + W) % W;
                  if (occId[c] && occId[c] != MY_ID + 1) crowd++; }
              if (ROUND < P.qfeedFrom) score -= 1.0 * crowd; }  // QFEED2: late she welcomes feeders
            // friends pop out of portals blind: don't loop beside a portal (Trauma r365: boxed in by a friend from P)
            int hc = s.cells.back(); double pp = 0;
            for (int d = 0; d < 4; d++) {
                if (effK(hc, d) == 3) pp = max(pp, 40.0);  // QSAFE: Trauma vs Peanut Butter r452: a friend came out of a portal onto her head (their queen dead since r41)
                int n = stepRaw(hc, d);
                for (int d2 = 0; d2 < 4; d2++) if (effK(n, d2) == 3) pp = max(pp, 20.0);
            }
            score -= pp;
        }
    }
    // NEWRULES PQ: a blind portal step can land on our queen's head (she moves first; vision doesn't cross portals)
    if (!isTrueQueen() && s.outside && !s.cells.empty() && isQueenId(queen.id) && queen.cell >= 0 && ROUND - queen.round <= 4
        && torusDist(s.cells.back(), queen.cell) <= 2 + (ROUND - queen.round)) score -= 30.0;
    // NEWRULES ROW: the queen acts first each round; friends that end next to her head can wall her in. Give way.
    // QROOM: ladder Portals vs POFPOF r287-291: after qfeedFrom ROW switched off and 31 friendly L2 drones boxed the L2
    // queen in (room 24 -> 0, DOOMED) -> lost by queen 0 vs 3 while leading 26 units to 4. Feeders only need distance <= 3,
    // so the no-adjacent-cell rule stays on all game; only the distance-<=3 discouragement stops at qfeedFrom.
    if (!isTrueQueen() && ROUND >= P.qfeedFrom) {
        for (auto& dr : others)
            if (dr.team == MY_TEAM && isQueenId(dr.id) && dr.headCell >= 0)
                for (int c : s.cells) if (torusDist(c, dr.headCell) <= 1) { score -= 15.0; break; }
    }
    if (!isTrueQueen() && ROUND >= 150 && ROUND < P.qfeedFrom) {  // ROWLATE; QFEED2: feeders must reach her late
        for (auto& dr : others)
            if (dr.team == MY_TEAM && isQueenId(dr.id) && dr.headCell >= 0) {
                // CROWD: Portals sandbox r355-364 / r262-271: our own swarm boxed the L2 queen in (room 24 -> 3) -> DOOMED
                for (int c : s.cells) if (torusDist(c, dr.headCell) <= 1) { score -= 15.0; break; }
                if (!s.cells.empty()) { int qd = torusDist(s.cells.back(), dr.headCell); if (qd <= 3) score -= 2.0 * (4 - qd); }
            }
    }
    e.corridor = miner ? 0.0 : corridorRisk(B);
    score -= e.corridor * (L / 2.0 + 10.0);
    e.score = score;
    // one coarse safety class: greed chooses freely among moves that are reasonably safe
    bool riskOk = isTrueQueen() ? e.pDeath < 0.05 : (e.pDeath < 0.25 || miner || (cheap && !bigFeed && e.pDeath < 0.9));  // NEWRULES
    e.safeClass = (riskOk && !adjacentThreat && (!s.outside || ((KM || pxHungry) && e.safeClass > 0))) ? 1 : 0;  // PEXPLORE
    return e;
}

// SEARCH1: one deterministic continuation ply; caller shares the total leaf-evaluation budget.
static bool s1LastSafe = true; static double s1MinPd = 1.0; static int s1N = 0; static int s1DbgN = 0; static double s1DbgPd = 0;  // DEBUG  // SEARCH1v: did the last searched root have a safe continuation?
static bool searchScore(const SimResult& root, const Eval& rootEval, int depth, int& evalCalls, double& out) {
    if (depth < 2 || root.dead || root.body.empty()) return false;
    double best = -1e18;
    bool hasSafeContinuation = false; s1MinPd = 1.0; s1N = 0;
    vector<int> oldBody = body;
    int oldLen = MY_LEN;
    body = root.body;
    MY_LEN = root.len;
    for (int d = 0; d < 4; d++) {
        if (evalCalls >= 12 || elapsedMs() > 50) { body.swap(oldBody); MY_LEN = oldLen; return false; }
        vector<int> dirs(1, d);
        SimResult next = simulateFrom(root.body, root.len, dirs);
        if (next.dead) continue;
        Eval leaf = evaluate(next, true);  // SEARCH1v: deepAllowed=false leaves pDeath at a 0.5 placeholder when room is short
        evalCalls++;
        best = max(best, leaf.score);
        s1MinPd = min(s1MinPd, leaf.pDeath); s1N++;
        if (leaf.pDeath <= 0.25) hasSafeContinuation = true;  // SEARCH1v: safeClass of a shallow leaf is noisy (adjacent heads); use death risk only
        if (elapsedMs() > 50) { body.swap(oldBody); MY_LEN = oldLen; return false; }
    }
    body.swap(oldBody);
    MY_LEN = oldLen;
    if (best < -1e17) best = 0.0;
    out = rootEval.score + 0.7 * best - (hasSafeContinuation ? 0.0 : 25.0);
    s1LastSafe = hasSafeContinuation;
    return true;
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

static void emitMove(const vector<int>& dirs, const vector<int>& cells) {
    string m = "MOVE ";
    for (int d : dirs) m += DCH[d];
    printf("%s\n", m.c_str());
    chosenCells = cells;
}

// search sprint paths ending on an enemy head
static bool findAttack(bool desperate) {
    if (isTrueQueen()) return false;  // NEWRULES
    int best = -1; vector<int> bestPath; double bestVal = -1e9;
    for (auto& dr : others) {
        if (elapsedMs() >= 52) break; // CPU1: attack enumeration shares the turn reserve.
        if (dr.team == MY_TEAM || dr.headCell < 0) continue;
        // a trade costs us a unit too: only take clearly lopsided ones
        bool worth = UNITS >= 2 && dr.estLen >= max(MY_LEN + 4, 2 * MY_LEN);
        // war of numbers: a big swarm trades small drones evenly when it has local superiority
        if (!worth && UNITS >= 12 && MY_LEN <= 4 && queen.id != MY_ID && dr.estLen >= MY_LEN) {  // SPRINT2: L<=4 even trades, but only with the champion's 12+ army (8 bled small armies on QoS)
            int mine = 0, theirs = 0;
            for (auto& o : others) if (o.headCell >= 0) (o.team == MY_TEAM ? mine : theirs)++;
            if (mine >= theirs) worth = true;  // SPRINT2: not outnumbered locally
        }
        if (UNITS >= 2 && endgame() && dr.estLen >= MY_LEN + 2) worth = true;
        if (UNITS >= 30 && MY_LEN <= 4 && queen.id != MY_ID && dr.estLen >= 2) worth = true;  // PRESS2: finish survivors: any trade is worth it with 30+ units
        if (isQueenId(dr.id) && UNITS >= 2) worth = true;  // NEWRULES
        if (huntLongActive && dr.id == huntLongId) worth = true; // HUNTL
        // never throw away a long dragon at the end: it is probably what wins the tiebreak
        if (desperate && !(endgame() && MY_LEN > dr.estLen)) worth = true;
        if (!worth) continue;
        if (torusDist(body[0], dr.headCell) > P.attackMaxSteps) continue;
        int maxSteps = min(P.attackMaxSteps, MY_LEN - 1);
        vector<int> path;
        vector<int> found;
        // iterative deepening over direction sequences
        for (int k = 1; k <= maxSteps && found.empty() && elapsedMs() < 52; k++) { // CPU1
            int total = 1; for (int i = 0; i < k; i++) total *= 4;
            for (int code = 0; code < total && found.empty(); code++) {
                if ((code & 15) == 0 && elapsedMs() >= 52) break; // CPU1
                path.clear();
                int cc = code;
                for (int i = 0; i < k; i++) { path.push_back(cc % 4); cc /= 4; }
                SimResult r = simulate(path);
                if (r.dead && r.hitHeadId == dr.id && (int)r.cells.size() == k - 1) found = path;
            }
        }
        if (found.empty()) continue;
        double val = isQueenId(dr.id) ? 1000000.0 : dr.estLen - MY_LEN - 0.3 * found.size(); // HUNTL queen priority
        if (val > bestVal) { bestVal = val; best = dr.id; bestPath = found; }
    }
    if (best < 0) return false;
    string m = "MOVE ";
    for (int d : bestPath) m += DCH[d];
    printf("%s\n", m.c_str());
    indicator = "ATK " + to_string(best);
    return true;
}

static int maxUnitsForMap() {
    int area = W * H;
    if (area < 400) return 3;
    if (area < 1200) return 5;
    return 6;
}

// Our head is about to be stuck, but the tail end may be free: hand most of the
// length to a child that crawls out from the tail. The split itself does not move
// the head, so it also buys the parent a turn.
static string dsWhy;
// AMPUTATE: the true queen is cornered (no safe move). Her length decides the game, so shed the SHORTEST tail that gives
// her a survivable next turn instead of dying. A split keeps her head in place (it buys a turn); the child's cells stay
// walls EXCEPT the child's tail cell body[L-sz]: the child acts later this round and any move of it vacates that cell
// before her next turn. In a closed coil (Slithery, L25) this is the only way out: sz=18 (parent keeps 7) leaves the
// child's tail adjacent to her head (sim: tools/slithery_opening.py, survives 40+ rounds; every smaller split dies r1).
static bool queenAmputate(double curPd) {
    if (!isTrueQueen() || MY_LEN < 4 || UNITS >= UNIT_LIMIT) return false;
    for (int c : body) if (c < 0) return false;
    const int L = MY_LEN; const vector<int> full = body; const int head = full[0];
    int bestS = -1; double bestPd = curPd - 0.25;   // must beat staying put clearly
    for (int sz = 2; sz <= L - 2; sz++) {
        if (elapsedMs() >= 60) break;
        vector<char> cut(N, 0);
        for (int i = L - sz; i < L; i++) cut[full[i]] = 1;
        cut[full[L - sz]] = 0;                              // the child's tail cell is vacated when the child moves
        // cheap pre-filter: some neighbour of the head must be neither a kept body cell, a wall, nor a walled child cell
        bool open = false;
        for (int d = 0; d < 4 && !open; d++) {
            int n = nbr[head * 4 + d];
            if (n < 0 || cut[n]) continue;
            bool mine = false;
            for (int i = 0; i < L - sz; i++) if (full[i] == n) { mine = true; break; }
            if (!mine && (!occId[n] || occId[n] == MY_ID + 1)) open = true;
        }
        if (!open) continue;
        vector<int> parent(full.begin(), full.begin() + (L - sz));
        body = parent; MY_LEN = L - sz;                      // evaluate() reads the globals
        double minPd = 1.0;
        for (int d = 0; d < 4; d++) {
            SimResult nx = simulateFrom(parent, L - sz, vector<int>(1, d));
            if (nx.dead || nx.cells.empty() || cut[nx.cells[0]]) continue;
            Eval ev = evaluate(nx, true);
            minPd = min(minPd, ev.pDeath);
        }
        body = full; MY_LEN = L;
        if (minPd < bestPd - 1e-9) { bestPd = minPd; bestS = sz; if (minPd <= 0.2) break; }   // shortest size that is safe enough
    }
    body = full; MY_LEN = L;
    if (bestS < 0) {
        // QBOX (from Y.9.6): no move at all and no coil exit (e.g. an L4 queen in a closed 2x2 box, live Schooltime): shed the
        // rear 2. The boxed child dies and frees the cells; a dead child is better than a dead queen.
        if (curPd >= 0.99 && L >= 4) {
            emittedSplit=2; printf("SPLIT 2%c", 10);
            indicator = "QBOX-SHED 2";
            return true;
        }
        return false;
    }
    emittedSplit=bestS; printf("SPLIT %d%c", bestS, 10);
    indicator = "AMPUTATE " + to_string(bestS) + " pd" + to_string((int)(100 * bestPd));
    return true;
}

static bool doomedSplit(bool allowShed = true) {
    if (isTrueQueen()) { dsWhy = "queen: amputate"; return false; }   // AMPUTATE: queenAmputate handles her
    if (MY_LEN < 4 || UNITS >= UNIT_LIMIT) { dsWhy = "len/units"; return false; }
    for (int c : body) if (c < 0) { dsWhy = "unknown body"; return false; }
    double bestVal = 0; int bestC = -1;
    for (int c = MY_LEN - 2; c >= 2; c--) {
        if (elapsedMs() >= 48) break; // CPU1  // largest children first, within budget
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
                emittedSplit=c; printf("SPLIT %d\n", c);
                indicator = "SHED " + to_string(c);
                return true;
            }
        }
        // QBOX: ladder Schooltime vs STAR (variant map): our L4 queen spawns coiled in a closed 2x2 box and died at r0
        // (moving into the own tail kills). STAR split 2 at r0: the boxed child dies, and the L2 queen circles in the box.
        // A dead child is better than a dead queen: shed the rear 2 when nothing else works.
        if (isTrueQueen() && MY_LEN >= 4) {
            emittedSplit=2; printf("SPLIT 2\n");
            indicator = "QBOX-SHED 2";
            return true;
        }
        dsWhy = "val " + to_string(bestVal);
        return false;
    }
    emittedSplit=bestC; printf("SPLIT %d\n", bestC);
    indicator = "ESCAPE-SPLIT " + to_string(bestC);
    return true;
}

// Swarm expansion (the ladder leader's macro): any dragon that reaches length 4 buds off a
// length-2 child until the unit cap. Many heads collect far more pearls, a swarm cannot be
// eliminated, and once the cap stops the splitting the dragons simply grow.
static bool swarmSplit() {
    if (MY_LEN < P.budAt || UNITS >= UNIT_LIMIT) return false;
    // stop budding once late; on the maze maps keep going while the swarm is still small,
    // because a small swarm just loses the head-on war of numbers
    bool narrow = false;  // ladder test: the top teams keep budding on Autarky (55-64 units by r300)
    int until = (bigFeed || narrow) ? P.budUntil : (UNITS < 40 ? 420 : P.budUntil);
    if (ROUND >= until) return false;
    for (int i = MY_LEN - 2; i < MY_LEN; i++) if (body[i] < 0) return false;
    int tail = body[MY_LEN - 1];
    for (int d = 0; d < 4; d++) {
        int n = nbr[tail * 4 + d];
        if (n >= 0 && !occId[n] && n != body[MY_LEN - 2]) {
            emittedSplit=2; printf("SPLIT 2\n");
            indicator = "BUD";
            return true;
        }
    }
    return false;
}

static bool trySplit(const Eval& stayEval) {
    int c = P.splitChild > 0 ? P.splitChild : MY_LEN / 2;
    bool overlong = MY_LEN > capLen && !endgame();
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
    if (elapsedMs() >= 48) return false; // CPU1: split probes share the turn deadline.
    Eval pe = evaluate(parent, false);
    if (pe.space < parent.len + 8 && !overlong) return false;
    SimResult child; for (int i = MY_LEN - 1; i >= MY_LEN - c; i--) child.body.push_back(body[i]); child.len = c;
    if (elapsedMs() >= 48) return false; // CPU1: recheck after the parent evaluation.
    Eval ce = evaluate(child, false);
    if (ce.space < (overlong ? 4 : 12)) return false;
    emittedSplit=c; printf("SPLIT %d\n", c);
    indicator = "SPLIT";
    return true;
}

// ---------------------------------------------------------- queen gossip --
// SECURE: authenticated packets share one 48-bit payload + 16-bit SipHash tag.
enum SecureKind { SEC_QUEEN = 1, SEC_QPOS = 2, SEC_PPROBE = 3, SEC_STATUS = 4 };
static const uint64_t SECURE_PAYLOAD_MASK = (1ULL << 48) - 1;
struct SecureMessage { int kind; uint64_t payload; int txRound; };
static vector<SecureMessage> secureMessages;
static int rejectedPackets = 0;
static int trueQueenId = -1;
static inline uint64_t rotl64(uint64_t x, int b) { return (x << b) | (x >> (64 - b)); }
static uint64_t siphashPacket(uint64_t payload, int kind, int round) {
    // SECURE: team-private 128-bit key; message bytes are payload[6], kind[1], round[2].
    const uint64_t k0 = 0x8F24D19B63A7C50EULL, k1 = 0x31E6B8047AC295DFULL;
    uint64_t v0 = 0x736f6d6570736575ULL ^ k0, v1 = 0x646f72616e646f6dULL ^ k1;
    uint64_t v2 = 0x6c7967656e657261ULL ^ k0, v3 = 0x7465646279746573ULL ^ k1;
    auto sipround = [&]() {
        v0 += v1; v1 = rotl64(v1, 13); v1 ^= v0; v0 = rotl64(v0, 32);
        v2 += v3; v3 = rotl64(v3, 16); v3 ^= v2;
        v0 += v3; v3 = rotl64(v3, 21); v3 ^= v0;
        v2 += v1; v1 = rotl64(v1, 17); v1 ^= v2; v2 = rotl64(v2, 32);
    };
    uint64_t m = (payload & SECURE_PAYLOAD_MASK) | ((uint64_t)(kind & 255) << 48) | ((uint64_t)(round & 255) << 56);
    v3 ^= m; sipround(); sipround(); v0 ^= m;
    uint64_t tail = (9ULL << 56) | (uint64_t)((round >> 8) & 255);
    v3 ^= tail; sipround(); sipround(); v0 ^= tail;
    v2 ^= 0xff; sipround(); sipround(); sipround(); sipround();
    return v0 ^ v1 ^ v2 ^ v3;
}
static uint64_t packSecure(uint64_t payload, int kind, int txRound) {
    // Format is authenticated by a distinct MAC domain, never guessed from plaintext.
    int domain = kind + (P.encryptPayload ? 64 : 0);
    if (P.encryptPayload) payload ^= siphashPacket(0x51474B4559ULL, kind+128, txRound) & SECURE_PAYLOAD_MASK;
    uint16_t tag = (uint16_t)(siphashPacket(payload, domain, txRound) >> 48);
    return ((uint64_t)tag << 48) | (payload & SECURE_PAYLOAD_MASK);
}
static bool openSecure(uint64_t packet, int kind, uint64_t& payload, int& txRound) {
    if(!qgEnabled()) { // Preserve qf's first-match legacy decode exactly.
        payload=packet & SECURE_PAYLOAD_MASK;
        uint16_t tag=packet >> 48;
        for(int r=max(0,ROUND-1);r<=ROUND;r++)
            if((uint16_t)(siphashPacket(payload,kind,r)>>48)==tag) {txRound=r;return true;}
        return false;
    }
    uint64_t wire = packet & SECURE_PAYLOAD_MASK;
    uint16_t tag = packet >> 48;
    int matches=0;
    for (int r=max(0,ROUND-1); r<=ROUND; ++r) {
        for (int format=0; format<=int(qgEnabled()); ++format) {
            if ((uint16_t)(siphashPacket(wire,kind+64*format,r)>>48)!=tag) continue;
            ++matches; txRound=r; payload=wire;
            if(format) payload ^= siphashPacket(0x51474B4559ULL,kind+128,r)&SECURE_PAYLOAD_MASK;
        }
    }
    return matches==1; // MAC-domain collision is rejected, not plausibility-decoded.
}
static int maxSeenDragonLen() {
    int seen = max(1, MY_LEN);
    for (const auto& dr : others) seen = max(seen, dr.estLen);
    if (queen.len > 0 && queen.len <= N && !(ROUND >= P.qfeedFrom && queen.len == 999 && queen.id == trueQueenId)) seen = max(seen, queen.len);
    return seen;
}
static bool securePayloadPlausible(int kind, uint64_t p, int txRound) {
    int cell = (int)(p & 4095ULL);
    if (cell < 0 || cell >= N) return false;
    if (kind == SEC_QUEEN) {
        int len = (p >> 12) & 4095, sourceRound = (p >> 24) & 511, id = (p >> 33) & 4095;
        return (p >> 45) == 0 && len >= 1 && len <= N && (len <= maxSeenDragonLen() + 4 || len <= ROUND / 2 + 20) &&  /* Claude: a far drone that never saw our giant must still accept its gossip; the tag is the real check */ sourceRound <= ROUND && sourceRound <= txRound && id <= maxKnownId;
    }
    if (kind == SEC_QPOS) {
        int sourceRound = (p >> 12) & 511, id = (p >> 21) & 4095;
        return (p >> (qgEnabled()?41:33)) == 0 && sourceRound <= ROUND && sourceRound <= txRound && id <= 1 && id <= maxKnownId;
    }
    if (kind == SEC_STATUS) return (p >> 48)==0 && ((p>>12)&511)<=txRound && ((p>>21)&4095)<=4095;
    return kind == SEC_PPROBE && (p >> 12) == 0;
}
static void authenticateMessages() {
    secureMessages.clear(); enemyPingNow=false; guardRelayKind=0;
    for (uint64_t v : V.msgs) {
        if (!qgEnabled() && v==0) continue; // exact legacy behavior

        int matchedKind = 0, matches = 0, txRound = -1;
        uint64_t payload = 0;
        for (int kind = SEC_QUEEN; kind <= (qgEnabled()?SEC_STATUS:SEC_PPROBE); kind++) {
            uint64_t candidatePayload = 0; int candidateRound = -1;
            if (openSecure(v, kind, candidatePayload, candidateRound)) {
                matches++;
                matchedKind = kind; payload = candidatePayload; txRound = candidateRound;
            }
        }
        if (matches==0 && P.enemyPing) enemyPingNow=true;
        if (matches != 1 || !securePayloadPlausible(matchedKind, payload, txRound)) { rejectedPackets++; continue; }
        secureMessages.push_back({matchedKind, payload, txRound});
    }
}
static uint64_t packQueen(const QueenInfo& q) {
    if (q.cell < 0 || q.cell >= N || q.id < 0 || q.id > 4095) return qgEnabled()?packSecure((uint64_t)body[0],SEC_PPROBE,ROUND):0;
    uint64_t len = (uint64_t)min(max(1, q.len), min(min(N, 4095), maxSeenDragonLen() + 4));
    uint64_t sourceRound = (uint64_t)min(max(0, q.round), 511);
    uint64_t payload = (uint64_t)q.cell | (len << 12) | (sourceRound << 24) | ((uint64_t)q.id << 33);
    return packSecure(payload, SEC_QUEEN, ROUND);
}
static bool unpackQueen(const SecureMessage& m, QueenInfo& q) {
    if (m.kind != SEC_QUEEN) return false;
    q.cell = m.payload & 4095ULL; q.len = (m.payload >> 12) & 4095;
    q.round = (m.payload >> 24) & 511; q.id = (m.payload >> 33) & 4095;
    return true;
}
static uint64_t packTrueQueenPos(int cell, int round, int id) {
    if (cell < 0 || cell >= N || id < 0 || id > 1) return 0;
    uint64_t payload = (uint64_t)cell | ((uint64_t)(round & 511) << 12) | ((uint64_t)id << 21) | (qgEnabled() ? ((uint64_t)qHeading<<33) | ((uint64_t)qMode<<35) | ((uint64_t)qThreat<<37) | (1ULL<<40) : 0);
    return packSecure(payload, SEC_QPOS, ROUND);
}
static bool unpackTrueQueenPos(const SecureMessage& m, int& cell, int& round, int& id) {
    if (m.kind != SEC_QPOS) return false;
    cell = m.payload & 4095ULL; round = (m.payload >> 12) & 511; id = (m.payload >> 21) & 4095;
    return true;
}
static uint64_t packPortalProbe(int cell) {
    return (cell >= 0 && cell < N) ? packSecure((uint64_t)cell, SEC_PPROBE, ROUND) : 0;
}
static void updateTrueQueenPos() {
    for (const auto& m : secureMessages) {
        int cell, round, id;
        if (unpackTrueQueenPos(m, cell, round, id) && round >= trueQueenRound) {
            trueQueenCell = cell; trueQueenRound = round; trueQueenId = id;
            if(m.payload & (1ULL<<40)) { qHeading=(m.payload>>33)&3; qMode=(m.payload>>35)&3; qThreat=(m.payload>>37)&1; }

        }
    }
    // Own view is authoritative; messages reach only 45.855% of queen turns,
    // 24.9% before head-on deaths. Never require a message for nearby protection.
    if(qgEnabled()) for(const auto& dr:others) if(dr.team==MY_TEAM && isQueenId(dr.id) && dr.headCell>=0) {
        trueQueenCell=dr.headCell; trueQueenRound=ROUND; trueQueenId=dr.id; qHeading=dr.headFace; qMode=0;
    }
    if (isTrueQueen() && !body.empty() && body[0] >= 0)
        trueQueenCell = body[0], trueQueenRound = ROUND, trueQueenId = MY_ID;
}
static void considerQueen(const QueenInfo& q) {
    if (q.cell < 0) return;
    bool stale = ROUND - queen.round > 40;
    if (q.id == queen.id) { if (q.round >= queen.round) queen = q; return; }
    // SINK: feeding/homing sink = the old election (longest dragon); the true queen is protected separately.
    if (stale || q.len > queen.len || (q.len == queen.len && q.id < queen.id)) queen = q;
}
static void updateQueen() {
    for (const auto& m : secureMessages) { QueenInfo q; if (unpackQueen(m, q)) considerQueen(q); }
    QueenInfo me; me.cell = body[0]; me.len = MY_LEN; me.round = ROUND; me.id = MY_ID;
    considerQueen(me);
    for (auto& dr : others)
        if (dr.team == MY_TEAM && dr.headCell >= 0) {
            QueenInfo f; f.cell = dr.headCell; f.len = dr.estLen; f.round = ROUND; f.id = dr.id;
            considerQueen(f);
        }
    if (ROUND - queen.round > 40) queen = me;
}
static bool iAmQueen() { return queen.id == MY_ID; }
static bool slitheryGrow() { return KM && string(KM->name) == "slithery_fight" && ROUND >= 100 && queen.id == MY_ID && MY_LEN >= 6; }  // GROWS: ladder Slithery losses: their single grower was L40 at r250 (ours L5) with a full 64-unit swarm
static bool protectedQueen() { return slitheryGrow() || (!bigFeed && ROUND >= P.protectFrom && (queen.id == MY_ID || MY_LEN >= queen.len) && MY_LEN >= (ROUND >= 400 ? 6 : 4)); }
static bool outranks(int len, int id) { return len > MY_LEN || (len == MY_LEN && id < MY_ID); }
// late tiebreak consolidation on maze maps: the longest dragon decides, so pour mass into the queen
static bool lateFeed() { return !bigFeed && ROUND >= P.endFeedFrom && UNITS >= 6; }

// feeding: a small dragon near the queen turns itself into pearls right in her path
static bool tryFeed() {
    if (isTrueQueen()) return false;  // NEWRULES
    // FLOOR: Schooltime vs Adrak r350-360: feeding took us from 22 to 6 units among 62 enemies, then our L36 sink
    // died in a head-on and we lost by ELIMINATION. Keep a body count: no feeding at 10 units or fewer.
    if (UNITS <= 10) return false;  // FLOOR restored (Y.9.1): Schooltime vs python.io: FUNNEL's late floor 2 took us 51 -> 2 units by r400 -> eliminated
    if (ROUND < P.feedFrom || iAmQueen() || !outranks(queen.len, queen.id) || ROUND - queen.round > 25) return false;
    if (queen.cell < 0 || torusDist(queen.cell, body[0]) > P.feedRadius) return false;
    for (auto& dr : others) {
        // only a clearly longer dragon we can see is worth dying for; it must be able to eat us
        bool worthy = (ROUND >= P.qfeedFrom && isQueenId(dr.id)) ||  // QFEED: our true queen is always worth it
                      (bigFeed ? (dr.id == queen.id || dr.estLen >= MY_LEN + 3)
                              : (dr.estLen >= max(10, 2 * MY_LEN) || (lateFeed() && dr.id == queen.id && dr.estLen >= MY_LEN + 2)));
        if (dr.team != MY_TEAM || dr.headCell < 0 || !worthy) continue;
        if (torusDist(dr.headCell, body[0]) <= 3) {
            printf("SPLIT 1\n");  // illegal on purpose: we die and crystallise into pearls
            indicator = "FEED " + to_string(dr.id);
            return true;
        }
    }
    return false;
}

// ---------------------------------------------------------- policy network --
static float nnProb[7];
static bool nnReady = false;
static void nnInput(unsigned char* pl, float* sc) {
    const int R = 7, S = 15, f = MY_DIR;
    int hc = body[0], hx = hc % W, hy = hc / W;
    memset(pl, 0, 16 * S * S);
    unordered_map<int, int> lenOf, teamOf;
    for (auto& dr : others) { lenOf[dr.id] = dr.estLen; teamOf[dr.id] = dr.team; }
    for (int v = 0; v < S; v++)
        for (int u = 0; u < S; u++) {
            int x = u - R, y = v - R;
            for (int k = 0; k < f; k++) { int t = x; x = -y; y = t; }
            int c = (((hy + y) % H + H) % H) * W + (((hx + x) % W + W) % W);
            auto at = [&](int plane) -> unsigned char& { return pl[(plane * S + v) * S + u]; };
            for (int r = 0; r < 4; r++) {
                int k = effK(c, (r + f) % 4);
                if (k == 2) at(r) = 255;
                if (k == 3) at(4 + r) = 255;
            }
            if (gmax[c] > 0) at(8) = (unsigned char)min(255, (int)(255.0 * 2.0 / max(1, gmin[c] + gmax[c]) * 4));
            bool view = abs(x) <= 3 && abs(y) <= 3;
            if (!view) continue;
            at(9) = 255;
            if (pearlNow(c)) at(10) = 255;
            if (occId[c]) {
                int id = occId[c] - 1;
                if (id == MY_ID) {
                    for (int k = 0; k < (int)body.size(); k++)
                        if (body[k] == c) at(11) = (unsigned char)min(255, (MY_LEN - k) * 16);
                } else {
                    bool ally = teamOf.count(id) ? teamOf[id] == MY_TEAM : false;
                    int fr = visFreeRound[c] == ROUND ? visFree[c] : 1;
                    at(ally ? 12 : 13) = (unsigned char)min(255, fr * 16);
                    if (occHead[c]) at(ally ? 14 : 15) = (unsigned char)min(255, (lenOf.count(id) ? lenOf[id] : 2) * 8);
                }
            }
        }
    sc[0] = MY_LEN / 32.0f; sc[1] = ROUND / 500.0f; sc[2] = UNITS / 64.0f;
}
// ---- v6 input builder (19 planes + 6 scalars), mirrors ml/v6/build_dataset_v6.py; parity-tested via a debug hash ----
static int eqMemCell = -1, eqMemRound = -100000;   // per-dragon memory of the enemy queen's last seen head cell
static string nnHashStr;
static void nnInput6(unsigned char* pl, float* sc) {
    const int R = 7, S = 15, f = MY_DIR;
    int hc = body[0], hx = hc % W, hy = hc / W;
    memset(pl, 0, 19 * S * S);
    unordered_map<int, int> lenOf, teamOf;
    for (auto& dr : others) { lenOf[dr.id] = dr.estLen; teamOf[dr.id] = dr.team; }
    auto inView = [&](int c) {
        int dx = abs(c % W - hx), dy = abs(c / W - hy);
        dx = min(dx, W - dx); dy = min(dy, H - dy);
        return dx <= 3 && dy <= 3;
    };
    // world-grid planes 16 (queens + memory) and 17 (enemy free-step reach)
    static unsigned char w16[MAXN], w17[MAXN];
    memset(w16, 0, N); memset(w17, 0, N);
    vector<pair<int, int>> heads;   // visible enemy heads with their estimated length
    for (auto& dr : others) {
        bool ally = dr.team == MY_TEAM;
        if (dr.headCell >= 0 && inView(dr.headCell) && !ally) heads.push_back({dr.headCell, dr.estLen});
    }
    for (int c = 0; c < N; c++) {
        if (!inView(c) || !occId[c]) continue;
        int id = occId[c] - 1;
        if (id == MY_ID || id > 1) continue;
        bool ally = teamOf.count(id) ? teamOf[id] == MY_TEAM : false;
        w16[c] = ally ? 128 : 160;
        if (occHead[c]) w16[c] = 255;
    }
    for (auto& dr : others)
        if (dr.id <= 1 && dr.team != MY_TEAM && dr.headCell >= 0 && inView(dr.headCell)) { eqMemCell = dr.headCell; eqMemRound = ROUND; }
    if (eqMemCell >= 0 && ROUND - eqMemRound <= 100 && !inView(eqMemCell))
        w16[eqMemCell] = (unsigned char)(int)(150.0 * exp(-(double)(ROUND - eqMemRound) / 40.0));
    for (auto& hd : heads) {
        static int qd[MAXN], qc[MAXN]; static int vis[MAXN], stamp = 0; ++stamp;
        int qh = 0, qt = 0, limit = (hd.second + 3) / 4;
        qc[qt] = hd.first; qd[qt++] = 0; vis[hd.first] = stamp;
        while (qh < qt) {
            int c = qc[qh], depth = qd[qh++];
            w17[c] = max<int>(w17[c], max(0, 255 - 60 * max(0, depth - 1)));
            if (depth == limit) continue;
            for (int d = 0; d < 4; d++) {
                int dest = nbr[c * 4 + d];
                if (dest < 0 || vis[dest] == stamp) continue;
                vis[dest] = stamp;
                if (inView(dest) && occId[dest]) w17[dest] = max<int>(w17[dest], max(0, 255 - 60 * depth));
                else { qc[qt] = dest; qd[qt++] = depth + 1; }
            }
        }
    }
    for (int v = 0; v < S; v++)
        for (int u = 0; u < S; u++) {
            int x = u - R, y = v - R;
            for (int k = 0; k < f; k++) { int t = x; x = -y; y = t; }
            int c = (((hy + y) % H + H) % H) * W + (((hx + x) % W + W) % W);
            auto at = [&](int plane) -> unsigned char& { return pl[(plane * S + v) * S + u]; };
            for (int r = 0; r < 4; r++) {
                int k = effK(c, (r + f) % 4);
                if (k == 2) at(r) = 255;
                if (k == 3) at(4 + r) = 255;
            }
            at(17) = w17[c]; at(16) = w16[c];
            bool view = abs(x) <= 3 && abs(y) <= 3;
            if (!view) continue;
            at(9) = 255;
            if (pearlNow(c)) at(10) = 255;
            if (occId[c]) {
                int id = occId[c] - 1;
                if (id == MY_ID) {
                    for (int k = 0; k < (int)body.size(); k++)
                        if (body[k] == c) at(11) = (unsigned char)min(255, (MY_LEN - k) * 16);
                } else {
                    bool ally = teamOf.count(id) ? teamOf[id] == MY_TEAM : false;
                    int fr = visFreeRound[c] == ROUND ? visFree[c] : 1;
                    at(ally ? 12 : 13) = (unsigned char)min(255, fr * 16);
                    if (occHead[c]) at(ally ? 14 : 15) = (unsigned char)min(255, (lenOf.count(id) ? lenOf[id] : 2) * 8);
                }
            }
        }
    // memory cell outside the view window but inside the 15x15 window: written above only for in-view cells, so add it here
    sc[0] = MY_LEN / 32.0f; sc[1] = ROUND / 500.0f; sc[2] = UNITS / 64.0f;
    sc[3] = MY_ID <= 1 ? 1.0f : 0.0f; sc[4] = ((MY_LEN + 3) / 4) / 8.0f; sc[5] = 0.0f;
}
static void nnRun() {
    nnReady = false;
    if (bigFeed || ROUND >= P.nnUntil || P.wNN <= 0 || body.empty() || body[0] < 0 || elapsedMs() > 40) return;
    static unsigned char pl[19 * 15 * 15];
    float sc[6], lg[7];
    nnInput6(pl, sc);   // V6
    nn::forward(pl, sc, lg);
    float mx = lg[0];
    for (int i = 1; i < 7; i++) mx = max(mx, lg[i]);
    float z = 0;
    for (int i = 0; i < 7; i++) { nnProb[i] = exp(lg[i] - mx); z += nnProb[i]; }
    for (int i = 0; i < 7; i++) nnProb[i] /= z;
    nnReady = true;
}
static void nnSelfTest() {
    float lg[7];
    nn::forward(NN_TEST_PLANES, NN_TEST_SCALARS, lg);
    printf("LOG NNTEST");
    for (int i = 0; i < 7; i++) printf(" %.4f/%.4f", lg[i], NN_TEST_LOGITS[i]);
    printf(" t=%.1fms%c", elapsedMs(), 10);
}



static void guardUpdate() {
    guardFriends.erase(remove_if(guardFriends.begin(),guardFriends.end(),[](const GuardStatus& f){return ROUND-f.round>6;}),guardFriends.end());
    for(const auto& m:secureMessages) {
        int id=(m.payload>>21)&4095, r=(m.payload>>12)&511;
        if(P.statusRay && m.kind==SEC_STATUS) {
            GuardStatus f{int(m.payload&4095),r,id,int((m.payload>>33)&3),max(1,int(((m.payload>>35)&7)*4)),int((m.payload>>38)&1),int((m.payload>>39)&3),int((m.payload>>41)&3),int(((m.payload>>43)&31)*4)};
            bool found=false; for(auto& old:guardFriends) if(old.id==id) {if(f.round>=old.round)old=f;found=true;break;} if(!found && guardFriends.size()<64)guardFriends.push_back(f);
        }
        if(((P.statusRay && m.kind==SEC_STATUS) || (P.qposFrom && m.kind==SEC_QPOS)) && r>relaySeen[m.kind][id] && ROUND-r<=3) {
            int shift=m.kind==SEC_STATUS?41:38, hops=(m.payload>>shift)&3;
            if(hops<3 && id!=MY_ID) {guardRelay=(m.payload&~(3ULL<<shift))|((uint64_t)(hops+1)<<shift);guardRelayKind=m.kind;relayId=id;relayRound=r;}
        }
    }
    memset(laneRisk,0,sizeof laneRisk);
    if(!P.laneEcho || !isTrueQueen() || echoLanes.empty())return;
    int counts[6]={ECHO[0],ECHO[1],ECHO[2],ECHO[3],ECHO[4],0};
    int sum=0;for(int i=0;i<5;i++)sum+=counts[i]; counts[5]=int(echoLanes.size())-sum;
    vector<int> unresolved;
    for(int i=0;i<(int)echoLanes.size();i++)if(echoLanes[i].resolved>=0)counts[echoLanes[i].resolved]--;else unresolved.push_back(i);
    for(int c:counts)if(c<0)return;
    double total=0, enemy[4]={}; int assign[4]={};
    auto enumerate=[&](auto&& self,int at,double weight)->void {
        if(at==(int)unresolved.size()) {for(int c:counts)if(c)return;total+=weight;for(int j=0;j<at;j++)if(assign[j]==3||assign[j]==4)enemy[unresolved[j]]+=weight;return;}
        int i=unresolved[at];
        // Terrain-only priors averaged over the two held-out folds; unknown
        // terrain permits both kelp and no-hit outcomes. Never use occupancy
        // to decide whether a kelp outcome is eligible.
        const double kp[6]={.7305,.111,.0877,.041,.0299,.0001};
        const double op[6]={0,.254,.3235,.2235,.1982,.0008};
        for(int k=0;k<6;k++)if(counts[k] && (k!=0 || echoLanes[i].kelp) && (k!=5 || !echoLanes[i].kelp || echoLanes[i].unknown)) {counts[k]--;assign[at]=k;self(self,at+1,weight*(echoLanes[i].unknown?.5*(kp[k]+op[k]):echoLanes[i].kelp?kp[k]:op[k]));counts[k]++;}
    };
    enumerate(enumerate,0,1.0);
    if(total>0)for(int i:unresolved)if(enemy[i]/total>.5)for(int c:echoLanes[i].cells)laneRisk[c]=max(laneRisk[c],enemy[i]/total);
}


static void think() {
    emittedSplit=0;
    compassActive = false; // COMPASS: do not retain last turn's target state.
    buildDragons();
    buildReaches();
    {   // PEXPLORE: hungry small drone on an unknown map -> nearest unexplored portal edge it has seen
        static int pxPrevLen2 = -1, pxLastGrow2 = 0;
        if (MY_LEN > pxPrevLen2) pxLastGrow2 = ROUND;
        pxPrevLen2 = MY_LEN; pxTarget = -1;
        pxHungry = !KM && !isTrueQueen() && MY_LEN <= 4 && ROUND - pxLastGrow2 >= 12;
        if (!KM && !isTrueQueen() && MY_LEN <= 4 && ROUND - pxLastGrow2 >= 12 && !body.empty() && body[0] >= 0) {
            int best = 1 << 30;
            for (int c = 0; c < N; c++) for (int d = 0; d < 4; d++)
                if (obsK[c * 4 + d] == 3 && nbr[c * 4 + d] < 0) { int dd = torusDist(body[0], c); if (dd < best && dd <= 12) { best = dd; pxTarget = c; } }
        }
    }
    computeCap();
    maxKnownId = max(maxKnownId, MY_ID);
    qThreat=false; authenticateMessages(); // SECURE
    updateQueen();
    updateTrueQueenPos();  // QPOS + SECURE
    if(qgEnabled()) guardUpdate(); if(isTrueQueen()) {qMode=0;qThreat=enemyPingNow; if(enemyPingNow)qMode=2;}
    // QFEED: ladder Trauma vs No Idea: both queens alive, they fed THEIR queen 2 -> 16 from r350 and won 'by queen' (ours 3).
    // From qfeedFrom on, our true queen is the feeding/homing sink whenever her position is fresh.
    if (ROUND >= P.qfeedFrom && trueQueenCell >= 0 && ROUND - trueQueenRound <= 6) {
        queen.cell = trueQueenCell; queen.len = 999; queen.round = ROUND; queen.id = trueQueenId;
    }
    // HUNTL: remote non-queen/non-sink length-2-4 drones trade for visible giants.
    huntLongActive = false; huntLongId = -1; huntLongLen = 0; // HUNTL
    bool sinkFresh = queen.cell >= 0 && ROUND - queen.round <= 25;
    bool awayFromSink = body[0] >= 0 && (!sinkFresh || torusDist(queen.cell, body[0]) > P.feedRadius);
    if (!isTrueQueen() && !iAmQueen() && MY_LEN <= 4 && awayFromSink) {
        for (auto& dr : others) if (dr.team != MY_TEAM && dr.headCell >= 0 &&
            (dr.estLen >= 20 || dr.estLen >= 2 * max(1, queen.len)) &&
            (ROUND >= 300 || (ROUND >= 200 && dr.estLen >= 25)) && dr.estLen > huntLongLen) {
            huntLongActive = true; huntLongId = dr.id; huntLongLen = dr.estLen;
        }
    }
    if (tryFeed()) return;
    dumpState();
    chosenCells.clear();

    // COMPASS: choose one rich, reachable region on only the three tested maps.
    {   // SWAPFIX: make 'our start side' the side we really spawned on (ladder maps swap A/B; a child guesses by distance)
        static bool sideFixed = false;
        if (!sideFixed && compassStartReady && !body.empty() && body[0] >= 0) {
            sideFixed = true;
            bool wrong = MAP_TEAM >= 0 ? compassTeamUsed != MAP_TEAM
                                       : (compassEnemyStartDist[body[0]] >= 0 && compassEnemyStartDist[body[0]] < compassOurStartDist[body[0]]);
            if (wrong) for (int c = 0; c < N; c++) swap(compassOurStartDist[c], compassEnemyStartDist[c]);
        }
    }
    int compassTarget = -1;
    bool compassPrepared = false;
    if (KM && compassMap && regionRateReady && compassStartReady && ROUND < P.compassUntil && !isTrueQueen() && !iAmQueen() &&
        MY_LEN <= 6 && MY_ID % 3 == 0 && UNITS >= 6 && body[0] >= 0 && elapsedMs() <= 40) { // only one third of miners
        static int fromDist[MAXN], q[MAXN];
        fill(fromDist, fromDist + N, -1);
        int qh = 0, qt = 0;
        fromDist[body[0]] = 0; q[qt++] = body[0];
        bool complete = true;
        while (qh < qt) {
            if (elapsedMs() > 40) { complete = false; break; }
            int c = q[qh++];
            for (int d = 0; d < 4; d++) { int n = nbr[c * 4 + d]; if (n >= 0 && fromDist[n] < 0) { fromDist[n] = fromDist[c] + 1; q[qt++] = n; } }
        }
        if (complete) {
            double headRate = regionRate[body[0]], bestValue = -1.0;
            for (int c = 0; c < N; c++) {
                if (fromDist[c] <= 3 || fromDist[c] < 0 || regionRate[c] <= 0 || regionRate[c] < 2.0 * headRate) continue;
                if (compassOurStartDist[c] < 0 || (compassEnemyStartDist[c] >= 0 && compassEnemyStartDist[c] < compassOurStartDist[c])) continue;
                double value = regionRate[c] / (1.0 + fromDist[c] / 15.0);
                if (value > bestValue) { bestValue = value; compassTarget = c; }
            }
            if (compassTarget >= 0 && elapsedMs() <= 40) {
                fill(compassDist, compassDist + N, -1);
                qh = qt = 0; compassDist[compassTarget] = 0; q[qt++] = compassTarget;
                while (qh < qt) {
                    if (elapsedMs() > 40) { complete = false; break; }
                    int c = q[qh++];
                    for (int d = 0; d < 4; d++) { int n = nbr[c * 4 + d]; if (n >= 0 && compassDist[n] < 0) { compassDist[n] = compassDist[c] + 1; q[qt++] = n; } }
                }
                compassPrepared = complete;
            }
        }
    }

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
        lastGoal = goalCell;
    }
    struct Opt { vector<int> dirs; SimResult sim; Eval ev; };
    vector<Opt> opts;
    for (int d = 0; d < 4; d++) {
        Opt o; o.dirs = {d}; o.sim = simulate(o.dirs);
        if (!o.sim.dead) opts.push_back(o);
    }
    // FSPRINT: search every free two-step path, and three steps for long dragons.
    bool stopFreePaths = false; // FSPRINT
    for (int k = 2; k <= min(3, (MY_LEN + 3) / 4) && !stopFreePaths; k++) { // FSPRINT
        int total = k == 2 ? 16 : 64; // FSPRINT
        for (int code = 0; code < total; code++) { // FSPRINT
            if (elapsedMs() >= 48) { stopFreePaths = true; break; } // FSPRINT
            Opt o; int cc = code; // FSPRINT
            for (int i = 0; i < k; i++) { o.dirs.push_back(cc % 4); cc /= 4; } // FSPRINT
            bool rev = false; // FSPRINT
            for (int i = 1; i < k; i++) if (o.dirs[i] == opp(o.dirs[i - 1])) rev = true; // FSPRINT
            if (rev) continue; // FSPRINT
            o.sim = simulate(o.dirs); // FSPRINT
            if (!o.sim.dead) opts.push_back(o); // FSPRINT
        } // FSPRINT
    } // FSPRINT
    // CPUGUARD (Y.9.6): new 64x64 / 60x40 open maps: long dragons (L16-29, 2-3 step free sprints, ~30 options) spent
    // 80-93M points evaluating every option with the full-board survival search; one exceeded 100M and died (Australia
    // r409). Shallow evaluation after 45 ms, drop the remaining (sprint) options after 65 ms; 1-step options come first.
    for (size_t i = 0; i < opts.size(); i++) {
        if (i >= 2 && elapsedMs() > 52) { opts.resize(i); break; }   // CPU1: keep >= 2 options, admit more only under the shared deadline
        opts[i].ev = evaluate(opts[i].sim, elapsedMs() < 40);
    }
    // QPOS: widen the landing-cell buffer as reports age; portal paths can be blind to allies.
    if (!isTrueQueen() && trueQueenCell >= 0 && ROUND - trueQueenRound <= 6) {
        int age = ROUND - trueQueenRound;
        for (auto& o : opts) if (o.sim.outside && !o.sim.cells.empty() &&
            torusDist(o.sim.cells.back(), trueQueenCell) <= 2 + age) {
            o.ev.score -= 60.0; o.ev.safeClass = 0;
        }
    }
    if(qgEnabled()) {
    // Guard reports describe a sender and an unlocalized alarm, never an enemy cell.
    struct Intercept { int cell, id, distance; double weight; };
    vector<Intercept> intercepts;
    int age=ROUND-trueQueenRound;
    if(P.guardIntercept && !isTrueQueen() && !feeding && UNITS>=6 && trueQueenCell>=0 && age<=6) {
        unordered_set<int> seen;
        for(const auto& enemy:others) {
            if(elapsedMs()>=52 || intercepts.size()>=8) break;
            if(enemy.team==MY_TEAM || enemy.headCell<0 || !seen.insert(enemy.id).second ||
               MY_LEN<enemy.estLen || torusDist(enemy.headCell,trueQueenCell)>6) continue;
            int dd=torusDist(body[0],enemy.headCell), rank=0;
            unordered_set<int> visible;
            for(const auto& f:others) {
                if(elapsedMs()>=52) break;
                if(f.team!=MY_TEAM || f.headCell<0) continue;
                visible.insert(f.id); // current vision supersedes any report, regardless of length
                if(f.id==MY_ID || isQueenId(f.id) || f.estLen<enemy.estLen) continue;
                int fd=torusDist(f.headCell,enemy.headCell);
                if(fd<dd || (fd==dd && f.id<MY_ID)) ++rank;
            }
            for(const auto& f:guardFriends) {
                if(elapsedMs()>=52) break;
                if(f.id==MY_ID || isQueenId(f.id) || visible.count(f.id) || ROUND-f.round>3 || f.len<enemy.estLen) continue;
                int fd=torusDist(f.cell,enemy.headCell);
                if(fd<dd || (fd==dd && f.id<MY_ID)) ++rank;
            }
            // Reserve at most one interceptor per observed enemy. Independent stale
            // views cannot guarantee a survivor count; the bonus never authorizes a trade.
            if(rank==0 && elapsedMs()<52) intercepts.push_back({enemy.headCell,enemy.id,dd,4.0/(1+age)});
        }
    }
    vector<int> queenExits;
    if(P.guardZone && trueQueenCell>=0 && age<=6) {
        for(int d=0;d<4;d++) {
            if(effK(trueQueenCell,d)==2) continue;
            int c=nbr[trueQueenCell*4+d]; // real portal destination; walls terminate
            if(c>=0) queenExits.push_back(c);
        }
    }
    for(auto& o:opts) if(!o.sim.cells.empty()) {
        if(elapsedMs()>=54) break;
        int dest=o.sim.cells.back();
        if(isTrueQueen()) {
            if(P.laneEcho) {
                double risk=0;
                for(int c:o.sim.cells) risk=max(risk,laneRisk[c]);
                o.ev.score-=12*risk;
            }
            if(P.enemyPing && enemyPingNow) o.ev.score+=2.0*min(1.0,o.ev.space/double(2*MY_LEN+20));
        } else if(trueQueenCell>=0 && age<=6) {
            if(P.guardZone && qMode!=3) {
                // Penalize only new obstruction of legal exits, not the entire old body.
                // A feeder exemption applies only to an approach that actually reaches the queen.
                bool reachesQueen=feeding && dest==trueQueenCell;
                if(feeding) for(int d=0;d<4;d++)
                    if(effK(dest,d)!=2 && nbr[dest*4+d]==trueQueenCell)reachesQueen=true;
                int introduced=0;
                if(!reachesQueen) for(int c:queenExits)
                    if(find(body.begin(),body.end(),c)==body.end() &&
                       find(o.sim.body.begin(),o.sim.body.end(),c)!=o.sim.body.end()) ++introduced;
                o.ev.score-=min(24.0,12.0*introduced)/(1+age);
            }
            if(P.qFreeze && qMode==3 && torusDist(body[0],trueQueenCell)<=4) {
                o.ev.score-=o.dirs.size()>1?25:0;
                if(torusDist(dest,trueQueenCell)<=3)o.ev.score-=30;
                o.ev.score+=2*o.ev.space/double(2*MY_LEN+20);
            }
            double bonus=0;
            for(const auto& t:intercepts)
                if(o.ev.pDeath<.6) bonus+=t.weight*(t.distance-torusDist(dest,t.cell));
            o.ev.score+=max(-8.0,min(8.0,bonus));
        }
    }
    if(P.statusRay || P.qposFrom) {
        double guardMinDeath=1;
        for(const auto& o:opts) guardMinDeath=min(guardMinDeath,o.ev.pDeath);
        if(guardMinDeath>=.6)qThreat=true;
    }
    if(isTrueQueen() && P.qFreeze) {
        bool safe=false;for(const auto& o:opts)if(o.ev.pDeath<.6)safe=true;
        if(!safe)qMode=3;
    }
    }
    // PPROBE: last turn we cast our only ray through the portal beside this head; the first dragon part it met lies
    // just beyond the portal (or further). A head there kills us on a blind step (friends on the far side are unseen).
    if (!ambiguousRadar && probeRound == ROUND - 1 && probeCell == body[0] && probeDir >= 0 && effK(body[0], probeDir) == 3)
        for (auto& o : opts) if (o.dirs[0] == probeDir) {
            if (ECHO[2] + ECHO[4] > 0) { o.ev.score -= 30.0; o.ev.safeClass = 0; }
            else if (ECHO[1] + ECHO[3] > 0) o.ev.score -= 3.0;
        }
    // PPROBE warn: a friend just beyond a portal told us (its probe ray stopped on us) where its head is
    for (const auto& m : secureMessages) if (m.kind == SEC_PPROBE && m.txRound == ROUND - 1) {
        int fc = (int)(m.payload & 4095ULL);
        for (auto& o : opts) if (o.sim.outside && !o.sim.cells.empty() && torusDist(o.sim.cells[0], fc) <= 1) {
            o.ev.score -= 30.0; o.ev.safeClass = 0;
        }
    }
    if (ROUND == 0 && MY_ID == 0 && P.wNN > 0 && elapsedMs() <= 30) nnSelfTest(); // CPU1
    nnRun();
    if (nnReady)  // the network only reorders options inside a safety class
        for (auto& o : opts) o.ev.score += P.wNN * log(max(1e-3f, nnProb[(o.dirs[0] - MY_DIR + 4) % 4]));
    sort(opts.begin(), opts.end(), [](const Opt& a, const Opt& b) {
        if (a.ev.safeClass != b.ev.safeClass) return a.ev.safeClass > b.ev.safeClass;
        return a.ev.score > b.ev.score;
    });
    // COMPASS: activate only when the existing best move is already safe.
    if (compassPrepared && elapsedMs() <= 40 && !opts.empty() && opts[0].ev.pDeath <= 0.25 && compassDist[body[0]] >= 0 && !isTrueQueen()) {
        compassActive = true;
        for (auto& o : opts) if (o.dirs.size() <= 1 && o.ev.pDeath <= 0.25 && compassDist[o.sim.body[0]] >= 0)
            o.ev.score += P.wCompass * (compassDist[body[0]] - compassDist[o.sim.body[0]]);
        sort(opts.begin(), opts.end(), [](const Opt& a, const Opt& b) {
            if (a.ev.safeClass != b.ev.safeClass) return a.ev.safeClass > b.ev.safeClass;
            return a.ev.score > b.ev.score;
        });
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
                if (elapsedMs() >= 48) break;
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
    if (isTrueQueen() && (opts.empty() || opts[0].ev.pDeath >= 0.6) && elapsedMs() < 62 && queenAmputate(opts.empty() ? 1.0 : opts[0].ev.pDeath)) return;   // AMPUTATE
    if ((opts.empty() || (opts[0].ev.pDeath >= (protectedQueen() ? 0.99 : 0.9) && opts[0].ev.surv <= 1)) && elapsedMs() < 55 && doomedSplit()) return;   // CPU1
    // a long dragon about to be rammed: let the tail half escape before the head is lost
    if (!opts.empty() && MY_LEN >= 8 && !protectedQueen() && opts[0].ev.danger >= max(3.0, 0.3 * MY_LEN) && elapsedMs() < 55 && doomedSplit(false)) {   // CPU1
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
        Eval se; bool splitBudget = elapsedMs() < 50;   // CPU1: split probes share the deadline
        if (splitBudget) se = evaluate(stay, false);
        if (!protectedQueen() && (opts[0].ev.pDeath < 0.5 || (MY_LEN <= 4 && ROUND < P.mineUntil)) && !opts[0].ev.adjacent && splitBudget && swarmSplit()) return;
        if (!protectedQueen() && (opts[0].ev.pDeath == 0 || MY_LEN > capLen) && splitBudget && trySplit(se)) return;
        bool qsChanged = false;
        bool searchChanged = false;
        if (P.search1 && opts.size() >= 2 && elapsedMs() <= 50) {
            bool enemyNear = false;
            for (const auto& dr : others) if (dr.team != MY_TEAM && dr.headCell >= 0 && torusDist(body[0], dr.headCell) <= 6) { enemyNear = true; break; }
            bool roomTight = false;
            int topClass = opts[0].ev.safeClass;
            for (const auto& o : opts) if (o.ev.safeClass == topClass && o.ev.room < 2 * MY_LEN + 8) { roomTight = true; break; }
            if (enemyNear || roomTight) {
                int second = -1;
                for (int i = 1; i < (int)opts.size(); i++) if (opts[i].ev.safeClass == topClass) { second = i; break; }
                if (second >= 0) {
                    int evalCalls = 0;
                    double score0 = opts[0].ev.score, score1 = opts[second].ev.score;
                    // SEARCH1v (tuned after replay review: v1 switched 67k times on small score noise): the search is
                    // a TRAP VETO only: switch only when the chosen move has no safe continuation and the runner-up has.
                    bool done0 = opts[0].ev.pDeath < 0.9 && searchScore(opts[0].sim, opts[0].ev, 2, evalCalls, score0);
                    bool safe0 = s1LastSafe; double dbg0 = s1MinPd; int dbgn0 = s1N;
                    bool done1 = done0 && !safe0 && searchScore(opts[second].sim, opts[second].ev, 2, evalCalls, score1);
                    bool safe1 = s1LastSafe;
                    // veto only real traps: every continuation of the chosen move is >= 60% deadly
                    if (done0 && done1 && !safe0 && dbg0 >= 0.6 && safe1 && elapsedMs() <= 50) {
                        swap(opts[0], opts[second]);
                        searchChanged = true; s1DbgN = dbgn0; s1DbgPd = dbg0;
                    }
                }
            }
        }
        if (P.qSearch) qsChanged = queenSearch(opts);
        // PEXPLORE (calc's rule: walk through unexplored portals when no food is reachable): ladder Stripes (new map,
        // 24x12) vs tungtung67: the pearls sit in kelp boxes reachable only through portals; on unknown maps a portal
        // whose partner we have not seen is a wall to us (rebuildNbr pairs only seen ends) -> we ate 4 pearls in r0-150
        // vs their 60 and were eliminated. A small drone that has not grown for 12 rounds steps into such a portal.
        {   static int pxPrevLen = -1, pxLastGrow = 0;
            if (MY_LEN > pxPrevLen) pxLastGrow = ROUND;
            pxPrevLen = MY_LEN;
            if (!KM && !isTrueQueen() && MY_LEN <= 4 && ROUND - pxLastGrow >= 12 && opts[0].ev.pDeath < 0.5 && body[0] >= 0) {
                for (int d = 0; d < 4; d++) if (effK(body[0], d) == 3 && nbr[body[0] * 4 + d] < 0) {
                    emitMove({d}, {});
                    indicator = "PEXPLORE " + to_string(d);
                    pxLastGrow = ROUND;  // one try, then forage again for 12 rounds
                    return;
                }
            }
        }
        auto& o = opts[0];
        emitMove(o.dirs, o.sim.cells);
        char tmp[96];
        snprintf(tmp, sizeof tmp, "L%d s%.1f sp%d rm%d f%.2f t%.2f dg%.2f pd%.2f%s", MY_LEN, o.ev.score, o.ev.space, o.ev.room,
                 o.ev.field, o.ev.target, o.ev.danger, o.ev.pDeath, KM ? " K" : "");
        indicator = tmp;
        if (o.ev.targetCell >= 0) indicator += " T" + to_string(o.ev.targetCell % W) + "," + to_string(o.ev.targetCell / W);
        if (compassActive) indicator += " C" + to_string(compassTarget % W) + "," + to_string(compassTarget / W);  // COMPASS
        if (qsChanged) indicator += " QS";

        if (searchChanged) { char db[48]; snprintf(db, sizeof db, " S1[%d:%.2f]", s1DbgN, s1DbgPd); indicator += db; }  // SEARCH1
        return;
    }
    // nothing survives: take the least bad raw step, never into a friend
    int bestD = MY_DIR, bestRank = -1;
    for (int d = 0; d < 4; d++) {
        int n = nbr[body[0] * 4 + d];
        int rank;
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
        if (rank > bestRank) { bestRank = rank; bestD = d; }
    }
    emitMove({bestD}, {});
    indicator = "DOOMED " + dsWhy;
}

// forward sonar: next turn's echo tells us whether an enemy sits somewhere down this line
static void castLegacyRadar() {
    lastRay.clear();
    int head = -1, dir = MY_DIR;
    if (!body.empty() && body[0] >= 0) {
        head = body[0];
        if (!chosenCells.empty()) {
            head = chosenCells.back();
            int prev = chosenCells.size() >= 2 ? chosenCells[chosenCells.size() - 2] : body[0];
            for (int d = 0; d < 4; d++) if (nbr[prev * 4 + d] == head) dir = d;
        }
    }
    // QPOS: true queen uses all four rays after r200; other dragons keep sink gossip flowing.
    if (isTrueQueen() && ROUND >= 200 && head >= 0) {
        uint64_t v = packTrueQueenPos(head, ROUND, MY_ID);
        trueQueenCell = head; trueQueenRound = ROUND; trueQueenId = MY_ID;
        for (int d = 0; d < 4; d++) printf("SONAR %c %llu\n", DCH[d], (unsigned long long)v);
        return;
    }
    if (ROUND >= P.gossipFrom) {
        uint64_t v = packQueen(queen);
        bool relay = !isTrueQueen() && trueQueenCell >= 0 && ROUND - trueQueenRound <= 6;
        int relayDir = (MY_ID + ROUND) & 3;
        for (int d = 0; d < 4; d++)
            printf("SONAR %c %llu\n", DCH[d], (unsigned long long)(relay && d == relayDir ?
                   packTrueQueenPos(trueQueenCell, trueQueenRound, trueQueenId) : v));
        return;
    }
    if (head < 0) return;
    // PPROBE: a head next to a portal edge sends its ray through that portal (the radar still reads enemy echoes)
    probeDir = -1;
    for (int d = 0; d < 4; d++) if (effK(head, d) == 3 && d != opp(dir)) { probeDir = d; if (d == dir) break; }
    if (probeDir >= 0) { dir = probeDir; probeCell = head; probeRound = ROUND; }
    int c = head;
    for (int k = 0; k < W + H; k++) {
        c = nbr[c * 4 + dir];
        if (c < 0) break;
        lastRay.push_back(c);
    }
    if (probeDir >= 0)  // PPROBE warn: tell a friend on the far side where our head is
        printf("SONAR %c %llu\n", DCH[dir], (unsigned long long)packPortalProbe(head));
    else if(qgEnabled()) printf("SONAR %c %llu\n", DCH[dir], (unsigned long long)packPortalProbe(head));
    else printf("SONAR %c 0\n", DCH[dir]);
}

static void castRadar() {
    ambiguousRadar=false;
    if(!(isTrueQueen() && P.qposFrom>0 && ROUND>=P.qposFrom) &&
       !(!isTrueQueen() && P.statusRay && ROUND>=12)) { castLegacyRadar(); return; }
    if(emittedSplit>0) chosenCells.clear(); // a split does not move the parent head
    lastRay.clear(); echoLanes.clear(); if(body.empty() || body[0]<0 || elapsedMs()>=55)return;
    int head=chosenCells.empty()?body[0]:chosenCells.back(), dir=MY_DIR;
    if(!chosenCells.empty()) {int prev=chosenCells.size()>1?chosenCells[chosenCells.size()-2]:body[0];for(int d=0;d<4;d++)if(nbr[prev*4+d]==head)dir=d;}
    int portalDir=-1;
    for(int d=0;d<4;d++)if(effK(head,d)==3 && d!=opp(dir)){portalDir=d;if(d==dir)break;}
    if(isTrueQueen() && P.qposFrom>0 && ROUND>=P.qposFrom) {
        qHeading=dir;
        if(qMode==0)for(const auto& dr:others)if(dr.team==MY_TEAM && dr.headCell>=0 && torusDist(head,dr.headCell)<=3)qMode=1;
        uint64_t word=packTrueQueenPos(head,ROUND,MY_ID);
        vector<int> predicted=body;
        if(emittedSplit>0 && emittedSplit<(int)predicted.size()) predicted.resize(predicted.size()-emittedSplit);
        if(!chosenCells.empty()) {vector<int> dirs;int prev=body[0];for(int c:chosenCells){for(int d=0;d<4;d++)if(nbr[prev*4+d]==c){dirs.push_back(d);break;}prev=c;}if(dirs.size()==chosenCells.size()){auto sim=simulate(dirs);if(!sim.dead)predicted=sim.body;}}
        vector<char> predictedCell(N,0), splitChild(N,0);
        for(int c:predicted)if(c>=0)predictedCell[c]=1;
        if(emittedSplit>0 && emittedSplit<(int)body.size())
            for(int i=body.size()-emittedSplit;i<(int)body.size();i++)
                if(body[i]>=0)splitChild[body[i]]=i+1==(int)body.size()?2:1;
        int sent=0;
        for(int j=0;j<4;j++) {int d=(dir+j)%4;if(P.laneRays==3 && d==opp(dir))continue;if(elapsedMs()>=60 || (sent>=2 && elapsedMs()>55))break;
            printf("SONAR %c %llu\n",DCH[d],(unsigned long long)(d==portalDir?packPortalProbe(head):word));sent++;
            if(d==portalDir){probeDir=d;probeCell=head;probeRound=ROUND;}
            ambiguousRadar=true; // queen aggregate echoes also cannot identify a portal probe
            if(!P.laneEcho)continue;
            EchoLane lane;lane.dir=d;lane.kelp=false;
            // Refracted rays use the emitted parent tail; the 3-ray schedule omits back.
            int c=head, rayDir=d;
            if(predicted.size()>1 && (d==opp(dir) || (nbr[head*4+d]>=0 && predictedCell[nbr[head*4+d]]))) {
                c=predicted.back();int before=predicted[predicted.size()-2];
                for(int td=0;td<4;td++)if(nbr[c*4+td]==before){rayDir=opp(td);break;}
            }
            for(int k=1;k<=W+H && elapsedMs()<58;k++) {
                int terrain=effK(c,rayDir); if(!terrain){lane.kelp=true;lane.unknown=true;}
                if(terrain==2){lane.kelp=true;lane.resolved=0;break;}
                int next=nbr[c*4+rayDir];if(next<0){lane.kelp=true;lane.unknown=true;break;}c=next;
                if(k<=12 && viewIndex[c]<0)lane.cells.push_back(c);
                if(predictedCell[c]){lane.resolved=c==head?2:1;break;}
                if(splitChild[c]){lane.resolved=splitChild[c];break;} // removed tail is now an ally child
                if(viewIndex[c]>=0 && occId[c] && occId[c]!=MY_ID+1) {bool ally=false;for(const auto& dr:others)if(dr.id==occId[c]-1)ally=dr.team==MY_TEAM;lane.resolved=ally?(occHead[c]?2:1):(occHead[c]?4:3);break;}
                if(viewIndex[c]<0) { // unseen bodies may precede known distant kelp
                    lane.resolved=-1;
                    for(int n=k;n<W+H && elapsedMs()<58;n++){int t=effK(c,rayDir);if(t==0){lane.kelp=true;lane.unknown=true;}if(t==2){lane.kelp=true;break;}int nc=nbr[c*4+rayDir];if(nc<0){lane.kelp=true;lane.unknown=true;break;}c=nc;if(n<12)lane.cells.push_back(c);}break;
                }
            }
            echoLanes.push_back(lane);
        }
        return;
    }
    qThreat=qThreat||enemyPingNow;
    int radarDir=dir;
    for(int d=0;d<4;d++)if(effK(head,d)==3 && d!=opp(dir)){radarDir=d;if(d==dir)break;}
    int sd=-1;
    if(!isTrueQueen() && P.statusRay && ROUND>=12) {
        int best=1<<30;
        for(int j=0;j<4;j++){int d=(j+(MY_ID&1)*2)%4;if(d==radarDir)continue;int dd=trueQueenCell>=0?torusDist(stepRaw(head,d),trueQueenCell):j;if(dd<best){best=dd;sd=d;}}
        bool threat=(P.enemyPing && enemyPingNow)||qThreat||(ECHO[3]+ECHO[4]>0);
        int td=0, enemyLen=0; // STATUS carries no localized enemy observation
        for(const auto& dr:others)if(dr.team!=MY_TEAM && dr.headCell>=0){threat=true;break;}
        uint64_t payload=(uint64_t)head|((uint64_t)ROUND<<12)|((uint64_t)MY_ID<<21)|((uint64_t)dir<<33)|((uint64_t)min(7,MY_LEN/4)<<35)|((uint64_t)threat<<38)|((uint64_t)td<<39)|((uint64_t)enemyLen<<43);
        uint64_t word=guardRelayKind?packSecure(guardRelay,guardRelayKind,ROUND):packSecure(payload,SEC_STATUS,ROUND);
        printf("SONAR %c %llu\n",DCH[sd],(unsigned long long)word);
        if(guardRelayKind) relaySeen[guardRelayKind][relayId]=relayRound;
    }
    if(elapsedMs()>=55)return;
    probeDir=-1;
    for(int d=0;d<4;d++)if(effK(head,d)==3 && d!=opp(dir)) {probeDir=d;if(d==dir)break;}
    if(probeDir>=0){dir=probeDir;probeCell=head;probeRound=ROUND;}
    // Reserve the portal/radar direction before STATUS: do not overwrite a probe.
    if(dir==sd) { lastRay.clear(); ambiguousRadar=true; return; }
    ambiguousRadar=sd>=0; // summed echoes from two rays cannot identify the radar lane
    int c=head;for(int k=0;k<W+H;k++){c=nbr[c*4+dir];if(c<0)break;lastRay.push_back(c);}
    printf("SONAR %c %llu\n",DCH[dir],(unsigned long long)(probeDir>=0?packPortalProbe(head):ROUND>=P.gossipFrom?packQueen(queen):packPortalProbe(head)));
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
    initKnowledge();
#if __has_include("debug_cfg.hpp")
#include "debug_cfg.hpp"
    DEBUG = true; debugFrom = DEBUG_FROM; debugTo = DEBUG_TO;
#endif
    for (int i = 0; i < 256; i++) { powG[i] = pow(P.gamma, i); powT[i] = pow(0.94, i); powM[i] = pow(P.minerGamma, i); }
    for (int c = 0; c < MAXN; c++) vt[c] = INT32_MIN / 2;

    // CPU1: include readTurn parsing in the shared turn clock.
    while (true) {
        T0 = chrono::steady_clock::now();
        if (!readTurn()) break;
        indicator.clear();
        qsContact=false;
        try {
            absorbView();
            think();
        } catch (...) {
            fallback();
        }
        castRadar();
        if (rejectedPackets > 0) indicator += " X" + to_string(rejectedPackets); // SECURE
        if(qsContact)qsStats.turnMax=max(qsStats.turnMax,elapsedMs());
#ifdef QS_STATS
        if(ROUND%100==0 || ROUND==499){char qb[384];snprintf(qb,sizeof qb," QSS c%u t%u e%u b%u p%u u%u a%u r%u x%u done%u fatal%u ov%u charge%u over%u ms%.3f turn%.3f abort%.3f",qsStats.calls,qsStats.triggered,qsStats.eligible,qsStats.reject[QS_BODY],qsStats.reject[QS_TICK],qsStats.reject[QS_UNKNOWN],qsStats.reject[QS_BUDGET],qsStats.reject[QS_CAP],qsStats.reject[QS_ACTORS],qsStats.complete,qsStats.fatal,qsStats.overrides,qsStats.chargedMax,qsStats.overshoot,qsStats.msMax,qsStats.turnMax,qsStats.abortMsMax);indicator+=qb;}
#endif
#ifdef DEBUG_QS
        if(qsContact){char qb[96];snprintf(qb,sizeof qb," QSTURN %.3f",qsStats.turnMax);indicator+=qb;}
#endif
        if (!indicator.empty()) printf("INDICATOR %s\n", indicator.c_str());
        printf("PROTOCOL 3\nENDTURN\n");
        fflush(stdout);
        // remember what we did for body tracking
        lastPath = chosenCells;
        havePrev = true;
    }
    return 0;
}
