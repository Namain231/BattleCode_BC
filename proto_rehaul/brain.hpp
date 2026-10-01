// PROTOTYPE (throwaway). The new policy: a small role state machine (Loong-style) with scored
// moves, a shared bud-at-4 economy, nearest-friend food assignment, condition-gated queen
// election over sonar, and feeding that dies beside the queen. No map tables, no search.
#pragma once

#include "world.hpp"

namespace bc {

enum Role : int { WORKER = 0, QUEEN = 1, FEEDER = 2 };
inline char const ROLECH[3] = {'W', 'Q', 'F'};

struct Action {
    int kind = 0;       // 0 move, 1 split, 2 die (feed), 3 sprint
    int dir = 0;
    int n = 0;
    std::string steps;
    int dest = -1;
    bool eat = false;
    std::string why;
};

struct Mate { int id, len, cell, stamp; bool queen; };

inline bool gWasQueen = false;  // per process: once a queen, stay one unless a stronger queen is heard

// cached powers for the few discount factors used in inner loops
inline double pw(double g, int k) {
    static double base[4] = {0, 0, 0, 0};
    static double tab[4][130];
    if (k < 0) k = 0;
    if (k > 129) k = 129;
    for (int i = 0; i < 4; i++) {
        if (base[i] == g) return tab[i][k];
        if (base[i] == 0) {
            base[i] = g; tab[i][0] = 1;
            for (int j = 1; j < 130; j++) tab[i][j] = tab[i][j - 1] * g;
            return tab[i][k];
        }
    }
    return std::pow(g, k);
}

// ---- sonar ---------------------------------------------------------------------
inline uint64_t mix(uint64_t x) {
    x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL; x ^= x >> 33;
    return x;
}
inline constexpr uint64_t KEY = 0x5ea5eed0d1a90ULL;
inline uint64_t tagFor(int round) { return mix(KEY ^ static_cast<uint64_t>(round)) & 0xFFF; }

inline uint64_t encode(int type, int id, int len, int x, int y, int round) {
    uint64_t r = static_cast<uint64_t>(round & 511);
    return (tagFor(round & 511) << 52) | (static_cast<uint64_t>(type & 3) << 50) |
           (static_cast<uint64_t>(id & 4095) << 38) | (static_cast<uint64_t>(std::min(len, 1023)) << 28) |
           (static_cast<uint64_t>(x & 63) << 22) | (static_cast<uint64_t>(y & 63) << 16) | (r << 7);
}

struct Brain {
    World& w;
    Board& b;
    int me, L, R, units;
    char team;
    std::vector<Mate>& mates;
    int& lastTarget;

    std::vector<int> blk, blkP, distF, idF, distE, thr, tmp, q;

    Brain(World& world, std::vector<Mate>& m, int& lt)
        : w(world), b(world.board), mates(m), lastTarget(lt) {
        me = w.init.id; L = w.t.length; R = w.t.round; units = w.t.units; team = w.init.team;
    }

    // ---- messages -------------------------------------------------------------
    void hear() {
        for (uint64_t m : w.t.msgs) {
            int round = static_cast<int>((m >> 7) & 511);
            if (((m >> 52) & 0xFFF) != tagFor(round)) continue;
            if (round > R || round < R - 40) continue;
            int id = static_cast<int>((m >> 38) & 4095);
            if (id == me) continue;  // rays wrap and can return to the sender
            int len = static_cast<int>((m >> 28) & 1023);
            int x = static_cast<int>((m >> 22) & 63), y = static_cast<int>((m >> 16) & 63);
            int type = static_cast<int>((m >> 50) & 3);
            note(id, len, b.id(x, y), round, (type & 1) ? 1 : 0);
        }
        // teammates in vision are ground truth for position (queen flag unchanged)
        for (auto const& s : w.others)
            if (s.team == team && s.visible >= 2) note(s.id, s.visible, s.head, R, -1);
    }
    void note(int id, int len, int cell, int stamp, int queen) {
        for (Mate& m : mates)
            if (m.id == id) {
                if (stamp >= m.stamp) {
                    m.len = std::max(len, stamp == m.stamp ? m.len : 0); m.cell = cell; m.stamp = stamp;
                    if (queen >= 0) m.queen = queen;
                }
                return;
            }
        mates.push_back({id, len, cell, stamp, queen == 1});
    }
    // the queen to feed: the best recently heard queen, else the longest teammate
    Mate const* bestMate() const {
        Mate const* best = nullptr;
        for (Mate const& m : mates) {
            if (m.stamp < R - K.heardFor) continue;
            if (!best || (m.queen && !best->queen) ||
                (m.queen == best->queen && (m.len > best->len || (m.len == best->len && m.id < best->id))))
                best = &m;
        }
        return best;
    }

    // ---- grids ----------------------------------------------------------------
    void buildBlk() {
        blk.assign(b.NC, 0);
        for (int c = 0; c < b.NC; c++)
            if (w.occ[c] >= 0) blk[c] = INF;
        int n = std::min(static_cast<int>(w.body.size()), L);
        for (int i = 0; i < n; i++) blk[w.body[i]] = std::max(blk[w.body[i]], L - i + 1);
        for (int c : w.ownVis) blk[c] = std::max(blk[c], 2);  // untracked own segments: assume they stay a while
        // pessimistic copy: any other head may step onto a free neighbour before we get there
        blkP = blk;
        for (auto const& s : w.others)
            for (int d = 0; d < 4; d++) {
                int n = b.nb[s.head * 4 + d];
                if (n >= 0 && blkP[n] < INF) blkP[n] = INF;
            }
    }
    // time-aware BFS: entering tile n at step t needs blk[n] <= t
    void bfs(std::vector<int>& dist, std::vector<int> const& src, int t0, int horizon) {
        dist.assign(b.NC, INF);
        q.clear();
        for (int s : src) { dist[s] = t0; q.push_back(s); }
        for (size_t i = 0; i < q.size(); i++) {
            int c = q[i], nd = dist[c] + 1;
            if (nd > horizon) continue;
            for (int d = 0; d < 4; d++) {
                int n = b.nb[c * 4 + d];
                if (n < 0 || dist[n] != INF || blk[n] > nd) continue;
                dist[n] = nd;
                q.push_back(n);
            }
        }
    }
    int room(int start, int limit, bool pess = false) {
        std::vector<int> const& g = pess ? blkP : blk;
        tmp.assign(b.NC, INF);
        q.clear();
        tmp[start] = 1; q.push_back(start);
        bool blindPortal = false;
        for (size_t i = 0; i < q.size() && static_cast<int>(q.size()) < limit; i++) {
            int c = q[i], nd = tmp[c] + 1;
            for (int d = 0; d < 4; d++) {
                int n = b.nb[c * 4 + d];
                if (n < 0 && unpairedPortal(c, d)) blindPortal = true;
                if (n < 0 || tmp[n] != INF || g[n] > nd) continue;
                tmp[n] = nd; q.push_back(n);
            }
        }
        // a portal whose far end we have not seen leads somewhere: count it as open space
        return static_cast<int>(q.size()) + (blindPortal ? K.blindPortalRoom : 0);
    }
    bool unpairedPortal(int c, int d) const {
        Edge const& e = b.side(c, d);
        return e.kind == 2 && e.partnerOrient < 0;
    }
    void friendField() {
        // multi-source BFS from visible friendly heads; idF = the nearest friend's id (lowest on ties)
        distF.assign(b.NC, INF); idF.assign(b.NC, INF);
        std::vector<std::pair<int, int>> src;
        for (auto const& s : w.others)
            if (s.team == team) src.push_back({s.id, s.head});
        std::sort(src.begin(), src.end());
        q.clear();
        for (auto& p : src) { distF[p.second] = 0; idF[p.second] = p.first; q.push_back(p.second); }
        for (size_t i = 0; i < q.size(); i++) {
            int c = q[i], nd = distF[c] + 1;
            if (nd > 20) continue;
            for (int d = 0; d < 4; d++) {
                int n = b.nb[c * 4 + d];
                if (n < 0 || blk[n] > nd) continue;
                if (distF[n] == INF) { distF[n] = nd; idF[n] = idF[c]; q.push_back(n); }
                else if (distF[n] == nd && idF[c] < idF[n]) idF[n] = idF[c];
            }
        }
        // threat: steps an enemy is short of reaching tile c in its next turn (<= 0: it can hit a head
        // there, by a walk or a sprint of up to length-1 steps). Length is a lower bound, so +1.
        thr.assign(b.NC, INF);
        for (auto const& s : w.others) {
            if (s.team == team) continue;
            int reach = std::clamp(s.visible, 1, K.sprintMax);  // (visible + 1) - 1
            std::vector<int> dd(b.NC, INF), qq{s.head};
            dd[s.head] = 0;
            for (size_t i = 0; i < qq.size(); i++) {
                int c = qq[i];
                thr[c] = std::min(thr[c], dd[c] - reach);
                if (dd[c] >= reach + 2) continue;
                for (int d = 0; d < 4; d++) {
                    int n = b.nb[c * 4 + d];
                    if (n < 0 || dd[n] != INF || w.occ[n] >= 0) continue;
                    dd[n] = dd[c] + 1; qq.push_back(n);
                }
            }
        }
        std::vector<int> src2;
        for (auto const& s : w.others)
            if (s.team != team) src2.push_back(s.head);
        distE.assign(b.NC, INF);
        q.clear();
        for (int s : src2) { distE[s] = 0; q.push_back(s); }
        for (size_t i = 0; i < q.size(); i++) {
            int c = q[i], nd = distE[c] + 1;
            if (nd > 20) continue;
            for (int d = 0; d < 4; d++) {
                int n = b.nb[c * 4 + d];
                if (n < 0 || distE[n] != INF || blk[n] > nd) continue;
                distE[n] = nd; q.push_back(n);
            }
        }
    }

    bool mineFirst(int c, int a) const {  // nearest-friend assignment, id tie-break
        if (distF[c] < a) return false;
        if (distF[c] == a && idF[c] < me) return false;
        return true;
    }

    int enemyHeadsNear(int c, int r) const {
        int n = 0;
        for (auto const& s : w.others) if (s.team != team && b.cheb(s.head, c) <= r) n++;
        return n;
    }
    int friendHeadsNear(int c, int r) const {
        int n = 1;
        for (auto const& s : w.others) if (s.team == team && b.cheb(s.head, c) <= r) n++;
        return n;
    }

    // ---- roles ----------------------------------------------------------------
    Role role(Mate const* best) const {
        bool queenMode = R >= K.queenRound || units >= K.queenUnits;
        if (!queenMode) return WORKER;
        bool beats = !best || L > best->len || (L == best->len && me < best->id);
        bool isQueen;
        if (best && best->queen) isQueen = gWasQueen && beats;  // a heard queen: only the stronger queen stays
        else isQueen = L >= 3 && (gWasQueen || beats);       // no queen heard: elect the longest
        if (isQueen) return QUEEN;
        if (!best || best->len < 3) return WORKER;
        // at the unit cap a new unit is worth nothing: surplus mass goes to the queen
        bool crowded = units >= w.init.unitLimit - K.capSlack;
        if (crowded && L >= 4 && b.cheb(best->cell, w.head) <= 24) return FEEDER;
        if (R < K.feedFrom) return WORKER;
        // feeding ramps from 10% of drones at feedFrom to all at feedAll; the choice is fixed per id
        double pct = std::min(1.0, 0.1 + 0.9 * (R - K.feedFrom) / double(K.feedAll - K.feedFrom));
        bool chosen = (mix(static_cast<uint64_t>(me) * 7919 + 17) % 1000) < pct * 1000;
        if (!chosen) return WORKER;
        if (b.cheb(best->cell, w.head) > 24 && R < K.feedAll) return WORKER;
        return FEEDER;
    }

    // ---- decisions ------------------------------------------------------------
    Action decide(Role& outRole) {
        hear();
        buildBlk();
        friendField();
        Mate const* best = bestMate();
        Role ro = role(best);
        gWasQueen = ro == QUEEN;
        outRole = ro;

        Action a;
        if (Action t; tryTrade(ro, t)) return t;
        if (ro == FEEDER && L >= K.feedMinLen) {
            if (Action f; tryFeed(best, f)) return f;
        }
        if (Action s; trySplit(ro, s)) return s;
        return bestMove(ro, best);
    }

    // Head-on trades, including sprints: enemy heads do not move during our turn, so a dragon of
    // length L reaches any head within L-1 steps of free path (each extra step costs a segment).
    bool tryTrade(Role ro, Action& a) {
        if (ro == QUEEN) return false;
        int maxSteps = std::min(L - 1, K.sprintMax);
        // BFS from our head over tiles we can cross this turn, remembering the first-step path
        std::vector<int> dist(b.NC, INF), par(b.NC, -1), pdir(b.NC, -1);
        std::vector<int> qq{w.head};
        dist[w.head] = 0;
        for (size_t i = 0; i < qq.size(); i++) {
            int c = qq[i];
            if (dist[c] + 1 >= maxSteps) continue;  // leave the last step for the head itself
            for (int d = 0; d < 4; d++) {
                int n = b.nb[c * 4 + d];
                if (n < 0 || dist[n] != INF || blk[n] > dist[c] + 1 || w.occHead[n] >= 0) continue;
                dist[n] = dist[c] + 1; par[n] = c; pdir[n] = d; qq.push_back(n);
            }
        }
        int bestVal = 0;
        std::string bestSteps;
        for (auto const& s : w.others) {
            if (s.team == team) continue;
            int elen = s.visible;
            for (int e = 0; e < 4; e++) {
                int m = b.nb[s.head * 4 + (e ^ 2)];  // tile from which stepping e enters the head
                if (m < 0 || dist[m] == INF || b.nb[m * 4 + e] != s.head) continue;
                int k = dist[m] + 1;
                if (k > maxSteps) continue;
                bool big = elen >= L + 2;                        // worth our whole body
                bool even = elen >= L && k <= 2;
                bool drone = L <= 3 && k <= 2 && units >= K.tradeUnits &&
                             friendHeadsNear(s.head, 4) >= enemyHeadsNear(s.head, 4);
                if (!big && !even && !drone) continue;
                int val = elen * 4 - k;
                if (val <= bestVal) continue;
                std::string steps(1, DCH[e]);
                for (int c = m; c != w.head; c = par[c]) steps.insert(steps.begin(), DCH[pdir[c]]);
                bestVal = val; bestSteps = steps;
            }
        }
        if (bestSteps.empty()) return false;
        if (bestSteps.size() == 1) { a.kind = 0; a.dir = dirFromChar(bestSteps[0]); a.dest = b.nb[w.head * 4 + a.dir]; a.why = "trade"; }
        else { a.kind = 3; a.steps = bestSteps; a.why = "sprint-trade"; }
        return true;
    }

    bool tryFeed(Mate const* best, Action& a) {
        if (!best) return false;
        int qcell = -1;
        for (auto const& s : w.others) if (s.id == best->id) qcell = s.head;
        if (qcell >= 0) {
            // die where the queen can eat: our head within feedRadius steps of hers
            std::vector<int> dq;
            bfs(dq, {qcell}, 0, K.feedRadius + 1);
            // path from the queen passes through our head tile only if it is free; test neighbours
            int best1 = INF;
            for (int d = 0; d < 4; d++) {
                int n = b.nb[w.head * 4 + d];
                if (n == qcell) best1 = 0;
                else if (n >= 0 && dq[n] < INF) best1 = std::min(best1, dq[n]);
            }
            if (best1 + 1 <= K.feedRadius) { a.kind = 2; a.why = "feed"; return true; }
        }
        return false;  // walking there is handled in bestMove
    }

    bool trySplit(Role ro, Action& a) {
        if (ro == QUEEN || ro == FEEDER) return false;
        if (L < K.budLen || R >= K.budStop || units >= w.init.unitLimit - 1) return false;
        if (!w.bodyKnown()) return false;
        int child = L / 2;
        int tail = w.body.back();
        // child's head is our tail; it needs a free exit that is not beside an enemy head
        std::vector<char> parent(b.NC, 0);
        for (int i = 0; i < L - child; i++) parent[w.body[i]] = 1;
        bool childOk = false;
        for (int d = 0; d < 4; d++) {
            int n = b.nb[tail * 4 + d];
            if (n < 0 || parent[n] || w.occ[n] >= 0) continue;
            bool childBody = false;
            for (int i = L - child; i < L; i++) if (w.body[i] == n) childBody = true;
            if (childBody) continue;
            if (distE[n] <= 1) continue;
            std::vector<int> saved = blkP;
            for (int i = 0; i < L; i++) blkP[w.body[i]] = INF;
            int rc = room(n, 8, true);
            blkP.swap(saved);
            if (rc < 5) continue;
            childOk = true;
        }
        bool parentOk = false;
        for (int d = 0; d < 4; d++) {
            int n = b.nb[w.head * 4 + d];
            if (n >= 0 && w.occ[n] < 0 && !parent[n]) parentOk = true;
        }
        if (!childOk || !parentOk) return false;
        a.kind = 1; a.n = child; a.why = "bud";
        return true;
    }

    Action bestMove(Role ro, Mate const* best) {
        int cap = std::min(2 * L + 12, 90);
        int need = std::min(L + 2, cap);
        std::vector<int> dq;
        int qcell = -1;
        if (ro == FEEDER && best) {
            qcell = best->cell;
            for (auto const& s : w.others) if (s.id == best->id) qcell = s.head;
            std::vector<int> saved = blk;
            if (qcell >= 0) { blk[qcell] = 0; bfs(dq, {qcell}, 0, 60); blk = saved; }
        }

        // pearls near a visible queen are hers: other dragons leave them alone
        int queenHead = -1;
        if (ro != QUEEN && best && best->queen)
            for (auto const& s : w.others) if (s.id == best->id) queenHead = s.head;

        double bestScore = -1e18;
        Action bestA;
        int bestRoomDir = -1, bestRoom = -1;
        int bestTargetCell = -1;
        std::vector<int> dist;
        for (int d = 0; d < 4; d++) {
            int n = b.nb[w.head * 4 + d];
            if (n < 0 && K.blindPortalStep && unpairedPortal(w.head, d)) {
                // step through a portal whose exit we have never seen: blind but usually open
                double score = K.wBlindPortal - 1.0 - (ro == QUEEN ? 1.0 : 0.0);  // last resort only
                if (bestRoom < K.blindPortalRoom) { bestRoom = K.blindPortalRoom; bestRoomDir = d; }
                if (score > bestScore) {
                    bestScore = score; bestA = Action{}; bestA.kind = 0; bestA.dir = d; bestA.dest = -1;
                    bestA.why = "portal"; bestTargetCell = -1;
                }
                continue;
            }
            if (n < 0 || blk[n] > 1) continue;
            if (w.occHead[n] >= 0) continue;  // head-on only through tryTrade
            int rm = room(n, cap);
            if (rm > bestRoom) { bestRoom = rm; bestRoomDir = d; }
            if (rm < need) continue;
            int rp = room(n, need, true);

            double score = K.wRoom * rm / double(cap);
            if (rp < need) score -= 2.0;  // a lane another head can close
            bool eat = w.seenRound[n] == R && w.seenPearl[n];
            if (eat) score += 1.0;

            // danger
            int eAdj = 0, fAdj = 0;
            for (int e = 0; e < 4; e++) {
                int m = b.nb[n * 4 + e];
                if (m < 0 || w.occHead[m] < 0) continue;
                for (auto const& s : w.others)
                    if (s.head == m) (s.team == team ? fAdj : eAdj)++;
            }
            if (!K.useThreat) {
                if (ro == QUEEN) { if (distE[n] <= 2) score -= 20.0; else if (distE[n] <= 4) score -= 3.0; }
                else score -= K.wEnemyAdj * eAdj;
            } else if (ro == QUEEN) {
                // any enemy head that can reach her next turn (walk or sprint) trades a drone for her
                if (thr[n] <= 0) score -= 20.0;
                else if (thr[n] <= 1) score -= 5.0;
                else if (thr[n] <= 3) score -= 1.0;
            } else if (K.useThreat == 2) {
                score -= K.wEnemyAdj * (eAdj + (thr[n] <= 0 && eAdj == 0 ? 0.5 * std::min(L, 6) / 3.0 : 0.0));
            } else {
                score -= K.wEnemyAdj * eAdj;  // workers: only adjacency (trading is their job)
            }
            score -= K.wFriendAdj * fAdj;

            // food, nearest-friend assignment, arrival-time spawns
            bfs(dist, {n}, 1, K.horizon);
            double top = 0, sum = 0, explore = 0, fast = 0;
            int topCell = -1;
            for (int c : q) {
                int at = dist[c];
                double p = w.belief(c);
                if (b.bed[c] == 1 && w.next[c] >= 0 && w.next[c] <= at - 1) p = std::max(p, K.spawnSoon);
                if (w.seenRound[c] < 0) explore += K.exploreUnit * pw(0.92, at - 1);
                if (p > 0.01 && ro != FEEDER) {
                    if (ro != QUEEN && !mineFirst(c, at)) continue;
                    if (queenHead >= 0 && b.cheb(c, queenHead) <= 3) continue;
                    if (distE[c] < at) p *= K.enemyCloser;
                    double v = p * pw(K.gamma, at - 1);
                    if (c == lastTarget) v *= K.keepGoal;
                    sum += v;
                    if (v > top) { top = v; topCell = c; }
                }
                if (w.fastBed(c) && ro != FEEDER && (ro == QUEEN || mineFirst(c, at)))
                    fast = std::max(fast, K.wFast / w.maxCd[c] * pw(K.gammaFar, at - 1));
            }
            score += top + 0.2 * std::min(sum - top, 3.0) + std::min(explore, K.exploreCap) + fast;

            if (ro == FEEDER && qcell >= 0 && dq[n] < INF) score += 3.0 - 0.1 * dq[n];
            if (d == w.t.dir) score += 0.01;

            if (score > bestScore) {
                bestScore = score;
                bestA = Action{};
                bestA.kind = 0; bestA.dir = d; bestA.dest = n; bestA.eat = eat;
                bestA.why = "move";
                bestTargetCell = topCell;
            }
        }
        if (bestScore > -1e17) { lastTarget = bestTargetCell; return bestA; }

        // nothing safe: shed the tail if we can, else take the roomiest move
        Action a;
        if (L >= 4 && units < w.init.unitLimit) {
            a.kind = 1; a.n = ro == QUEEN ? 2 : L / 2; a.why = "escape-split"; return a;
        }
        if (bestRoomDir >= 0) {
            a.kind = 0; a.dir = bestRoomDir; a.dest = b.nb[w.head * 4 + bestRoomDir];
            a.eat = a.dest >= 0 && w.seenRound[a.dest] == R && w.seenPearl[a.dest];
            a.why = "cornered";
            return a;
        }
        a.kind = 0; a.dir = w.t.dir; a.why = "doomed";
        for (int d = 0; d < 4; d++) {
            int n = b.nb[w.head * 4 + d];
            a.why += " " + std::to_string(n) + ":" + (n >= 0 ? std::to_string(blk[n]) + "/" + std::to_string(w.occ[n]) : std::string("x"));
        }
        a.why += " h" + std::to_string(w.head) + " L" + std::to_string(L) + " b" + std::to_string(w.body.size());
        return a;
    }
};

}  // namespace bc
