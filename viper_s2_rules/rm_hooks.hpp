// ------------------------------------------------------------- rulemine hooks --
// (a .hpp only so the submission zip, which takes *.cpp/*.hpp, carries it)
// Learned-rule plumbing for gP (RULE_MINING_SPEC.md). Everything here mirrors rulemine/features.py and
// rulemine/decisions.py exactly, on UNKNOWN-map semantics: terrain only as observed by this process (obsK/obsP,
// never the map tables), occupancy only as known (own body + parts in the window), teammates only as SEEN.
// With both knobs off (the default) nothing here changes a decision.
#include "rules_learned.hpp"

static int rmFirstRound = -1, rmLastEat = 0, rmPrevLen = -1;
struct RmMate { int round, vlen, cell; };
static unordered_map<int, RmMate> rmMates;               // teammates seen: id -> last sighting
static unordered_map<int, int> rmHeadsNow, rmHeadsPrev;  // other heads seen at this / my previous turn
static int rmNbr[MAXN * 4];
static bool rmOcc[MAXN];
static const int RM_NF = 19;
static const char* RM_NAMES[RM_NF] = {"len", "units", "round", "age", "since_eat", "n_ally_vis", "n_enemy_vis",
    "top_ally_vlen", "top_ally_ratio", "top_ally_dist", "top_ally_approach", "allies_near_top", "mem_top_len",
    "mem_top_age", "mem_top_dist", "i_am_top", "enemy_threat", "room", "pearls_r3"};
static double rmF[RM_NF];
static const int RM_FAR = 99;

// an enemy of visible length L reaches L-1 steps in one turn by sprinting (capped at 3, at least 1)
static inline int rmReach(int visLen) { return max(1, min(visLen - 1, 3)); }

static inline int rmCheb(int a, int b) {
    int dx = abs(a % W - b % W), dy = abs(a / W - b / W);
    return max(min(dx, W - dx), min(dy, H - dy));
}

// neighbours from OBSERVED edges only: unknown = open, kelp = wall, portal only when both ends were observed
static void rmBuildNbr() {
    unordered_map<int, vector<int>> portals;
    for (int c = 0; c < N; c++)
        for (int d = 0; d < 4; d++) {
            int k = obsK[c * 4 + d];
            if (k == 2) rmNbr[c * 4 + d] = -1;
            else if (k == 3) {
                rmNbr[c * 4 + d] = -1;
                int code = (d == 1 || d == 2) ? c * 4 + d : stepRaw(c, d) * 4 + opp(d);
                auto& v = portals[obsP[c * 4 + d]];
                if (find(v.begin(), v.end(), code) == v.end()) v.push_back(code);
            } else rmNbr[c * 4 + d] = stepRaw(c, d);
        }
    for (auto& kv : portals) {
        if (kv.second.size() != 2) continue;
        int a1 = kv.second[0] / 4, d1 = kv.second[0] % 4;
        int a2 = kv.second[1] / 4, d2 = kv.second[1] % 4;
        if (d1 != d2) continue;
        int b1 = stepRaw(a1, d1), b2 = stepRaw(a2, d1);
        rmNbr[a1 * 4 + d1] = b2; rmNbr[b1 * 4 + opp(d1)] = a2;
        rmNbr[a2 * 4 + d1] = b1; rmNbr[b2 * 4 + opp(d1)] = a1;
    }
}

static void rmBuildOcc() {
    for (int c = 0; c < N; c++) rmOcc[c] = false;
    for (auto& p : V.parts) rmOcc[p.cell] = true;
    for (int c : body) if (c >= 0) rmOcc[c] = true;
}

// BFS distance from s to t over rmNbr; occupied tiles block except t; -1 -> RM_FAR
static int rmDist(int s, int t, int cap) {
    static int dist[MAXN], q[MAXN], stamp[MAXN], ctr = 0;
    ctr++;
    int qh = 0, qt = 0;
    q[qt++] = s; dist[s] = 0; stamp[s] = ctr;
    while (qh < qt) {
        int c = q[qh++];
        if (c == t) return dist[c];
        if (dist[c] >= cap) continue;
        for (int d = 0; d < 4; d++) {
            int n = rmNbr[c * 4 + d];
            if (n < 0 || stamp[n] == ctr || (rmOcc[n] && n != t)) continue;
            stamp[n] = ctr; dist[n] = dist[c] + 1; q[qt++] = n;
        }
    }
    return RM_FAR;
}

static int rmRoom(int s, int cap) {
    static int q[MAXN], stamp[MAXN], ctr = 0;
    ctr++;
    int qh = 0, qt = 0;
    q[qt++] = s; stamp[s] = ctr;
    while (qh < qt && qt < cap + 1) {
        int c = q[qh++];
        for (int d = 0; d < 4; d++) {
            int n = rmNbr[c * 4 + d];
            if (n < 0 || stamp[n] == ctr || rmOcc[n]) continue;
            stamp[n] = ctr; q[qt++] = n;
            if (qt >= cap + 1) break;
        }
    }
    return min(qt - 1, cap);
}

// Call once per turn, before any decision: memory must advance every turn to match the extractor.
static void rmUpdateMemory() {
    if (rmFirstRound < 0) rmFirstRound = ROUND;
    if (rmPrevLen >= 0 && MY_LEN > rmPrevLen) rmLastEat = ROUND - 1;  // grew: it ate on its previous turn
    if (rmPrevLen < 0) rmLastEat = ROUND;
    rmPrevLen = MY_LEN;
    rmHeadsPrev = rmHeadsNow;
    rmHeadsNow.clear();
    for (auto& dr : others)
        if (dr.headCell >= 0) {
            rmHeadsNow[dr.id] = dr.headCell;
            if (dr.team == MY_TEAM) rmMates[dr.id] = {ROUND, dr.visCount, dr.headCell};
        }
}

static void rmComputeFeatures() {
    rmBuildNbr();
    rmBuildOcc();
    int head = body[0];
    for (int i = 0; i < RM_NF; i++) rmF[i] = 0;
    rmF[0] = MY_LEN; rmF[1] = UNITS; rmF[2] = ROUND; rmF[3] = ROUND - rmFirstRound; rmF[4] = ROUND - rmLastEat;
    int nA = 0, nE = 0, topId = -1, topV = -1, topCell = -1;
    for (auto& dr : others) {
        if (dr.headCell < 0) continue;
        if (dr.team == MY_TEAM) {
            nA++;
            if (dr.visCount > topV || (dr.visCount == topV && dr.id < topId)) { topV = dr.visCount; topId = dr.id; topCell = dr.headCell; }
        } else nE++;
    }
    rmF[5] = nA; rmF[6] = nE;
    rmF[9] = RM_FAR;
    if (topId >= 0) {
        rmF[7] = topV; rmF[8] = (double)topV / MY_LEN;
        rmF[9] = rmDist(head, topCell, 20);
        auto it = rmHeadsPrev.find(topId);
        if (it != rmHeadsPrev.end()) rmF[10] = torusDist(topCell, head) < torusDist(it->second, head);
        int near = 0;
        for (auto& dr : others)
            if (dr.headCell >= 0 && dr.team == MY_TEAM && dr.id != topId && rmCheb(dr.headCell, topCell) <= 3) near++;
        rmF[11] = near;
    }
    // best recent sighting: max (vlen, round, cell) like the extractor's max() over tuples
    bool any = false; RmMate best{0, 0, 0};
    for (auto& kv : rmMates) {
        const RmMate& m = kv.second;
        if (ROUND - m.round > 15) continue;
        if (!any || m.vlen > best.vlen || (m.vlen == best.vlen && (m.round > best.round || (m.round == best.round && m.cell > best.cell))))
            best = m, any = true;
    }
    if (any) { rmF[12] = best.vlen; rmF[13] = ROUND - best.round; rmF[14] = torusDist(best.cell, head); }
    else { rmF[13] = RM_FAR; rmF[14] = RM_FAR; }
    rmF[15] = MY_LEN >= rmF[12];
    int threat = 0;
    for (auto& dr : others) {
        if (dr.headCell < 0 || dr.team == MY_TEAM) continue;
        int reach = rmReach(dr.visCount);
        if (rmDist(dr.headCell, head, reach) <= reach) threat++;
    }
    rmF[16] = threat;
    rmF[17] = rmRoom(head, 40);
    int pr = 0;
    for (int i = 0; i < 49; i++) pr += V.pearl[i];
    rmF[18] = pr;
}

static double rmFeature(const char* name) {
    for (int i = 0; i < RM_NF; i++) if (!strcmp(RM_NAMES[i], name)) return rmF[i];
    return 0;
}

// the extractor's death opportunity: a longer ally in view, or a longer teammate seen in the last 15 rounds within 6
static bool rmDeathOpportunity() {
    for (auto& dr : others) if (dr.headCell >= 0 && dr.team == MY_TEAM && dr.visCount > MY_LEN) return true;
    for (auto& kv : rmMates)
        if (ROUND - kv.second.round <= 15 && kv.second.vlen > MY_LEN && torusDist(kv.second.cell, body[0]) <= 6) return true;
    return false;
}

#ifdef RM_HAS_death
static bool rmDeathFire() {
    double f[rm::death_NF];
    for (int i = 0; i < rm::death_NF; i++) f[i] = rmFeature(rm::death_FEATURES[i]);
    return rm::death_prob(f) >= rm::death_THRESHOLD;
}
#endif

#ifdef RM_HAS_queen_move
// candidate-step features in the order rulemine.decisions.CAND defines them
static double rmQueenUtility(int d) {
    int head = body[0];
    int n = rmNbr[head * 4 + d];
    if (n < 0 || rmOcc[n]) return 0;
    double c[7] = {0};
    c[0] = pearlNow(n);
    c[1] = d == MY_DIR;
    c[2] = rmRoom(n, 40);
    int dE = RM_FAR, dA = RM_FAR, toward = 0, reach = 0;
    for (auto& dr : others) {
        if (dr.headCell < 0) continue;
        int dn = torusDist(n, dr.headCell);
        if (dr.team == MY_TEAM) { dA = min(dA, dn); { int dd = torusDist(head, dr.headCell) - dn; toward += (dd > 0) - (dd < 0); } }
        else { dE = min(dE, dn); if (dn <= rmReach(dr.visCount)) reach++; }
    }
    c[3] = dE; c[4] = dA; c[5] = toward; c[6] = reach;
    // map the model's feature names onto our candidate vector
    static const char* CN[7] = {"eat", "straight", "room_after", "d_enemy", "d_ally", "toward_allies", "enemy_reach"};
    double f[rm::queen_move_NF];
    for (int i = 0; i < rm::queen_move_NF; i++) {
        f[i] = 0;
        for (int j = 0; j < 7; j++) if (!strcmp(rm::queen_move_FEATURES[i], CN[j])) f[i] = c[j];
    }
    return rm::queen_move_utility(f);
}
#endif

// parity log (P.rmLog): one line per turn with the feature vector, read back by rulemine/parity.py
static void rmLogFeatures() {
    printf("LOG RMF %d %d", ROUND, MY_ID);
    for (int i = 0; i < RM_NF; i++) printf(" %.9g", rmF[i]);
    printf("\n");
}
