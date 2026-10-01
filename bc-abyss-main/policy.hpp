#pragma once

#include "nav.hpp"
#include "world.hpp"

namespace bc {

struct Choice {
    bool split = false;
    int dir = N;
    int n = 0;
    int dest = -1;
    bool eat = false;
    double score = -1e18;
    std::string why;
    // search bookkeeping
    std::string sprint;      // multi-step MOVE (a sprint trade), empty for one step
    bool terminal = false;   // trade or vetoed: nothing to search past it
    double stepTerm = 0;     // what this step alone earns (eat bonus minus danger)
    int newL = 0;
};

// Roles are decided locally every turn from shared facts, so teammates agree
// without talking:
//   grower  - a starting dragon, or anyone long. Farms, buds off short children, avoids fights.
//   swarm   - everyone else. Escorts visible growers, forms squads on long enemies:
//             the closest swarm dragon trades heads, the next (squadSize-1) wait a few
//             tiles back and eat the ceil(L/2) pearls the dead enemy drops.
class Policy {
  public:
    int depthReached() const { return depthReached_; }

    Policy(World& w, Params const& p, double deadline) : w_(w), p_(p), deadline_(deadline) {
        gammaPow_.resize(kPowSize);
        gammaPow_[0] = 1.0;
        for (int i = 1; i < kPowSize; i++) gammaPow_[i] = gammaPow_[i - 1] * p_.gamma;
        farPow_.resize(kPowSize);
        farPow_[0] = 1.0;
        for (int i = 1; i < kPowSize; i++) farPow_[i] = farPow_[i - 1] * p_.gammaFar;
    }

    Choice decide() {
        Board const& b = w_.board;
        L_ = w_.t.length;
        grower_ = isGrower(w_.init.id, L_);
        feedHead_ = -1;
        // A fresh child's setup can eat most of its first turn late in the game:
        // then play a lean one-step turn.
        lean_ = clockNow() > deadline_ - p_.leanMargin;
        buildBase();
        buildTargets();
        if (!lean_) buildFriendFields();
        else noFriendFields();
        buildSquadTargets();

        // End-game feeding (see Params::feedRound).
        if (w_.t.round >= p_.feedRound && w_.t.round < p_.feedStop && L_ <= p_.feedMaxLen) {
            int bestLen = L_ + p_.feedMargin - 1;
            for (World::Seen const& s : w_.others)
                if (!isEnemy(s) && s.visible > bestLen) {
                    bestLen = s.visible;
                    feedHead_ = s.head;
                }
            if (feedHead_ >= 0) {
                grower_ = false;
                hunts_.clear();
                escortOf_ = -1;
                int d = distToHead(myDist_, feedHead_);
                if (d <= p_.feedDist && L_ >= 2) {
                    // Step into our own neck: we die here and the pearls land by its head.
                    Choice c;
                    c.dir = w_.t.dir ^ 2;
                    c.dest = b.nb[w_.head * 4 + c.dir];
                    c.why = "feed";
                    c.score = 1e9;
                    return c;
                }
            } else if (L_ >= p_.feedMargin) {
                grower_ = true;  // nobody visible is longer: we are the one being fed
            }
        }

        // Depth 1 is the plain one-step evaluation; then deepen while the CPU budget lasts.
        std::vector<Choice> first(4);
        std::vector<std::vector<int>> firstBody(4);
        std::vector<int> none;
        for (int d = 0; d < 4; d++) first[d] = scoreFrom(w_.body, L_, d, 0, none, &firstBody[d]);
        std::vector<double> total(4);
        for (int d = 0; d < 4; d++) total[d] = first[d].score;
        depthReached_ = 1;
        for (int depth = 2; depth <= p_.maxDepth && !lean_ && !timeUp(); depth++) {
            std::vector<double> t(4, -1e18);
            bool complete = true;
            for (int d = 0; d < 4 && complete; d++) {
                Choice const& c = first[d];
                if (c.dest < 0) continue;
                if (c.terminal) { t[d] = c.score; continue; }
                std::vector<int> eaten;
                if (c.eat) eaten.push_back(c.dest);
                double rest = searchFrom(firstBody[d], c.newL, depth - 1, 1, eaten);
                if (timedOut_) complete = false;
                t[d] = rest <= -1e17 ? -900.0 : c.stepTerm + rest;
            }
            if (!complete) break;
            total = t;
            depthReached_ = depth;
        }
        Choice best;
        for (int d = 0; d < 4; d++) {
            if (first[d].dest < 0) continue;
            Choice c = first[d];
            c.score = total[d];
            if (c.score > best.score) best = c;
        }
        if (best.dest < 0) {
            // Nothing legal: first try a tile we only gave up as a teammate's last exit,
            // otherwise any well-formed move beats the default suicide.
            best.dir = w_.t.dir;
            best.dest = b.nb[w_.head * 4 + best.dir];
            best.why = "trapped";
            // Doomed: die alone. Prefer an enemy head (trade), then kelp / our own body /
            // a teammate's body (only we die); a teammate's head would take it with us.
            int bestRank = 99;
            for (int d = 0; d < 4; d++) {
                int n = b.nb[w_.head * 4 + d];
                int hid = n >= 0 ? w_.occHeadId[n] : -1;
                bool enemyHead = false, friendHead = false;
                for (World::Seen const& s2 : w_.others)
                    if (s2.id == hid) (isEnemy(s2) ? enemyHead : friendHead) = true;
                int rank = enemyHead ? 0 : friendHead ? 9 : 5;
                if (rank < bestRank) {
                    bestRank = rank;
                    best.dir = d;
                    best.dest = n;
                }
            }
            for (int d = 0; d < 4; d++) {
                int n = b.nb[w_.head * 4 + d];
                if (n < 0 || w_.occ[n] >= 0 || base_[n] < INF || ownCell(n)) continue;
                best.dir = d;
                best.dest = n;
                best.why = "shared-exit";
                break;
            }
            if (best.why == "trapped") {
#ifdef BC_DEBUG
            for (int d = 0; d < 4; d++) {
                int n = b.nb[w_.head * 4 + d];
                char const* r = n < 0 ? "kelp" : n == b.nb[w_.head * 4 + (w_.t.dir ^ 2)] ? "neck"
                              : w_.occ[n] >= 0 ? "dragon" : base_[n] >= INF ? "exit" : "own";
                best.why += std::string(" ") + DCH[d] + ":" + r;
                if (n >= 0 && w_.occ[n] >= 0) best.why += std::to_string(w_.occ[n]);
            }
#endif
            }
        }

        if (p_.sprintTrades && best.why != "trade" && best.why != "defend" && !lean_) {
            std::string path;
            if (sprintTrade(path)) {
                Choice s;
                s.dir = dirFromChar(path[0]);
                s.dest = -1;  // we die with the target: no body to track
                s.sprint = path;
                s.why = "sprint-trade";
                return s;
            }
        }

        Choice split;
        if (trySplit(split, best)) return split;
        // Boxed in: splitting keeps the front half still this turn while the rear half
        // (a new dragon that moves right away) walks off and frees room.
        if (best.score < -500 && L_ >= 4 && w_.t.units < w_.init.unitLimit) {
            // Reverse: keep a 2-long stub here, the child (our old tail, facing out)
            // leaves with the rest.
            split.split = true;
            split.n = L_ - 2;
            split.why = "reverse";
            return split;
        }
        return best;
    }

  private:
    struct Target {
        int cell;
        double belief;
        int countdown;  // rounds until the bed spawns, -1 none
        double explore;
    };
    enum class Job { None, Attack, Support };
    struct Hunt {
        World::Seen const* enemy;
        double gain;     // length we expect to come out ahead by
        Job job;
        bool threat;     // it is closing in on one of our growers
    };

    static constexpr int kPowSize = 256;
    std::vector<double> gammaPow_;
    double gp(int k) const { return k < 0 ? 1.0 : k >= kPowSize ? 0.0 : gammaPow_[k]; }
    std::vector<double> farPow_;
    double fp(int k) const { return k < 0 ? 1.0 : k >= kPowSize ? 0.0 : farPow_[k]; }
    struct Hot { int cell; double rate; };
    std::vector<Hot> hot_;

    World& w_;
    Params const& p_;
    double deadline_ = 1e9;         // seconds on the turn clock
    bool timedOut_ = false;
    int depthReached_ = 0;
    std::vector<int> blkScratch_;
    std::vector<double> belief_;    // per tile, for lookahead pearl pickup
    std::vector<int> countdown_;

    bool lean_ = false;

    void noFriendFields() {
        Board const& b = w_.board;
        friendDist_.assign(b.NC, INF);
        friendId_.assign(b.NC, -1);
        enemyDist_.assign(b.NC, INF);
        friends_.clear();
        enemies_.clear();
        std::vector<int> blk = ownBlk();
        nav_.bfs(b, w_.head, blk, p_.horizon);
        myDist_ = nav_.dist;
    }

    bool timeUp() {
        if (!timedOut_ && clockNow() >= deadline_) timedOut_ = true;
        return timedOut_;
    }
    Nav nav_;
    int L_ = 2;
    bool grower_ = false;
    std::vector<int> base_;       // other dragons' segments = INF, plus own stray segments
    std::vector<Target> targets_;
    std::vector<int> friendDist_; // min distance from any visible teammate head
    std::vector<int> friendId_;
    std::vector<int> enemyDist_;
    struct FriendField { int id; bool grower; int head; std::vector<int> dist; };
    std::vector<FriendField> friends_;
    struct EnemyField { int id; int head; int visible; std::vector<int> dist; };
    std::vector<EnemyField> enemies_;  // the nearest visible enemy heads, with their BFS fields
    std::vector<int> myDist_;     // from our head as it is now
    std::vector<Hunt> hunts_;
    int escortOf_ = -1;           // head tile of the grower we escort, -1 none
    int feedHead_ = -1;           // head of the longer teammate we are walking to, -1 none

    bool ownCell(int c) const {
        for (int x : w_.body)
            if (x == c) return true;
        for (int x : w_.ownExtra)
            if (x == c) return true;
        return false;
    }

    bool isEnemy(World::Seen const& s) const { return s.team != w_.init.team; }
    // Everyone expands until the army is big (or late); only then do the starting
    // dragons and long ones switch to growing for the length tiebreak.
    bool isGrower(int id, int len) const {
        bool growPhase = w_.t.units >= p_.growerMinUnits || w_.t.round >= p_.growRound;
        return growPhase && (w_.isInitial(id) || len >= p_.promoteLen);
    }
    // Head-on trades are one-for-one: worth it while our army is not tiny and we do
    // not give up much more length than we take.
    bool tradeOk(int myLen, int enemyLen) const {
        return w_.t.units >= p_.tradeMinUnits && myLen <= enemyLen + p_.tradeSlack;
    }
    bool survival() const { return w_.t.units <= p_.survivalUnits; }

    // Whoever has more heads around a trade site eats most of the pearls the two dead
    // dragons drop. Counts heads near `site`, leaving out ourselves and the enemy we
    // would trade with (`skip`, -1 none).
    bool localOk(int site, int skip) const {
        Board const& b = w_.board;
        int mine = 0, theirs = 0;
        for (World::Seen const& s : w_.others) {
            if (s.id == skip || b.cheb(s.head, site) > p_.localRadius) continue;
            (isEnemy(s) ? theirs : mine)++;
        }
        return mine >= theirs;
    }
    // How far an enemy head can move in one turn: a MOVE of k steps needs length k + 1.
    int reachOf(int visible) const { return std::min(std::max(visible - 1, 1), p_.reachCap); }
    bool midGame() const { return w_.t.round >= p_.earlyEnd; }
    bool lateGame() const { return w_.t.round >= p_.midEnd; }

    std::vector<int> ownBlk() const {
        std::vector<int> blk = base_;
        markBody(blk, w_.body, L_);
        return blk;
    }

    // Distance from a precomputed field to any tile next to `head` (the head itself is blocked).
    int distToHead(std::vector<int> const& dist, int head) const {
        Board const& b = w_.board;
        int best = INF;
        for (int k = 0; k < 4; k++) {
            int n = b.nb[head * 4 + k];
            if (n >= 0) best = std::min(best, dist[n]);
        }
        return best;
    }

    void buildBase() {
        Board const& b = w_.board;
        base_.assign(b.NC, 0);
        for (int c = 0; c < b.NC; c++)
            if (w_.occ[c] >= 0) base_[c] = INF;
        for (int c : w_.ownExtra) base_[c] = INF;

        // Never take a teammate's last way out.
        std::vector<int> blk = base_;
        markBody(blk, w_.body, L_);
        for (World::Seen const& s : w_.others) {
            if (isEnemy(s)) continue;
            int exits = 0, exit = -1;
            for (int d = 0; d < 4; d++) {
                int n = b.nb[s.head * 4 + d];
                if (n >= 0 && blk[n] <= 1) exits++, exit = n;
            }
            if (exits == 1) base_[exit] = INF;
        }
    }

    void buildTargets() {
        Board const& b = w_.board;
        targets_.clear();
        belief_.assign(b.NC, 0.0);
        countdown_.assign(b.NC, -1);
        for (int c = 0; c < b.NC; c++) {
            double bel = w_.belief(c, p_);
            int cd = (b.bed[c] == 1 && w_.next[c] >= 0 && w_.next[c] < p_.horizon) ? w_.next[c] : -1;
            belief_[c] = bel;
            countdown_[c] = cd;
            double ex = w_.seenRound[c] < 0 ? p_.exploreValue : 0.0;  // never-seen tile
            if (bel > 0.02 || cd >= 0 || ex > 0) targets_.push_back({c, bel, cd, ex});
        }
        hot_.clear();
        for (int c = 0; c < b.NC; c++) {
            if (b.bed[c] != 1 || b.gapMax[c] <= 0) continue;
            double rate = 2.0 / (b.gapMin[c] + b.gapMax[c]);
            if (rate >= p_.hotRate) hot_.push_back({c, rate});
        }
    }

    void buildFriendFields() {
        Board const& b = w_.board;
        friendDist_.assign(b.NC, INF);
        friendId_.assign(b.NC, -1);
        enemyDist_.assign(b.NC, INF);
        friends_.clear();
        enemies_.clear();
        std::vector<int> blk = ownBlk();
        // Only the nearest heads matter; this bounds CPU when 60+ dragons crowd the vision.
        std::vector<World::Seen const*> near;
        for (World::Seen const& s : w_.others) near.push_back(&s);
        std::sort(near.begin(), near.end(), [&](World::Seen const* x, World::Seen const* y) {
            return b.cheb(x->head, w_.head) < b.cheb(y->head, w_.head);
        });
        if (static_cast<int>(near.size()) > p_.maxRivalFields) near.resize(p_.maxRivalFields);
        for (World::Seen const* sp : near) {
            World::Seen const& s = *sp;
            nav_.bfs(b, s.head, blk, p_.horizon);
            if (isEnemy(s)) {
                for (int c = 0; c < b.NC; c++) enemyDist_[c] = std::min(enemyDist_[c], nav_.dist[c]);
                enemies_.push_back({s.id, s.head, s.visible, nav_.dist});
                continue;
            }
            for (int c = 0; c < b.NC; c++) {
                int d = nav_.dist[c];
                if (d < friendDist_[c] || (d == friendDist_[c] && d != INF && s.id < friendId_[c])) {
                    friendDist_[c] = d;
                    friendId_[c] = s.id;
                }
            }
            friends_.push_back({s.id, isGrower(s.id, s.visible), s.head, nav_.dist});
        }
        nav_.bfs(b, w_.head, blk, p_.horizon);
        myDist_ = nav_.dist;
    }

    // How many visible swarm teammates are closer than us to `head` (ties by id).
    int swarmRank(int head, int mine) const {
        int rank = 0;
        for (FriendField const& f : friends_) {
            if (f.grower) continue;
            int d = distToHead(f.dist, head);
            if (d < mine || (d == mine && d != INF && f.id < w_.init.id)) rank++;
        }
        return rank;
    }

    void buildSquadTargets() {
        Board const& b = w_.board;
        hunts_.clear();
        escortOf_ = -1;
        if (grower_) return;

        // Enemy heads near one of our visible growers are threats whatever their length.
        for (World::Seen const& e : w_.others) {
            if (!isEnemy(e)) continue;
            bool threat = false;
            double protect = 0;
            for (FriendField const& f : friends_)
                if (f.grower && b.cheb(f.head, e.head) <= p_.escortRadius) {
                    threat = true;
                    for (World::Seen const& s : w_.others)
                        if (s.id == f.id) protect = std::max<double>(protect, s.visible);
                }
            double gain = threat ? std::max<double>(protect, e.visible) - L_ : e.visible - L_;
            bool worth = threat ? e.visible >= 2 : tradeOk(L_, e.visible);
            if (!worth) continue;
            int mine = distToHead(myDist_, e.head);
            if (mine == INF) continue;
            int rank = swarmRank(e.head, mine);
            Job job = rank == 0 ? Job::Attack : rank < p_.squadSize ? Job::Support : Job::None;
            if (job != Job::None) hunts_.push_back({&e, gain, job, threat});
        }

        // Idle escort: stay near the closest visible grower if we are among its first escorts.
        if (hunts_.empty() && midGame()) {
            int bestD = INF;
            for (FriendField const& f : friends_) {
                if (!f.grower) continue;
                int d = distToHead(myDist_, f.head);
                if (d == INF || d >= bestD) continue;
                if (swarmRank(f.head, d) < p_.escortCount) {
                    bestD = d;
                    escortOf_ = f.head;
                }
            }
        }
    }

    Hunt const* huntAt(int headCell) const {
        for (Hunt const& h : hunts_)
            if (h.enemy->head == headCell) return &h;
        return nullptr;
    }

    bool nextToEnemyHead(int cell, int& enemyLen, bool& isHunt) const {
        Board const& b = w_.board;
        enemyLen = 0;
        isHunt = false;
        bool found = false;
        for (World::Seen const& s : w_.others) {
            if (!isEnemy(s)) continue;
            for (int d = 0; d < 4; d++)
                if (b.nb[s.head * 4 + d] == cell) {
                    found = true;
                    enemyLen = std::max(enemyLen, s.visible);
                    if (huntAt(s.head)) isHunt = true;
                }
        }
        return found;
    }

    // One step from a simulated state: `body` (head first, true length L) after k of
    // our own moves this turn-plan, with `eaten` pearls already taken along the way.
    // k = 0 is the real move; deeper k is lookahead with other dragons held still.
    Choice scoreFrom(std::vector<int> const& body, int L, int d, int k, std::vector<int> const& eaten,
                     std::vector<int>* nextBody = nullptr) {
        Board const& b = w_.board;
        Choice c;
        c.dir = d;
        int head = body.front();
        int dest = b.nb[head * 4 + d];
        if (dest < 0) return c;  // kelp or unknown portal
        for (int x : body)
            if (x == dest) return c;  // own segment, tail included
        if (w_.occ[dest] < 0 && base_[dest] >= INF) return c;  // own stray segment or a teammate's last exit

        if (w_.occ[dest] >= 0) {
            if (k > 0) return c;  // lookahead treats other dragons as walls
            // Stepping onto an enemy head kills both. Swarm does it on squad targets;
            // anyone does it when the trade is clearly good.
            int hid = w_.occHeadId[dest];
            for (World::Seen const& s : w_.others) {
                if (s.id != hid || !isEnemy(s)) continue;
                Hunt const* h = huntAt(s.head);
                double gain = s.visible - L;
                if (h && !grower_) {
                    c.dest = dest;
                    c.score = 100.0 + h->gain;
                    c.why = h->threat ? "defend" : "trade";
                    c.terminal = true;
                } else if (tradeOk(L, s.visible) && !grower_) {
                    c.dest = dest;
                    c.score = 50.0 + gain;
                    c.why = "trade";
                    c.terminal = true;
                }
            }
            return c;
        }

        c.dest = dest;
        bool taken = std::find(eaten.begin(), eaten.end(), dest) != eaten.end();
        if (k == 0) c.eat = w_.seenRound[dest] == w_.t.round && w_.seenPearl[dest];
        else c.eat = !taken && (belief_[dest] >= 0.5 || (countdown_[dest] >= 0 && countdown_[dest] <= k));
        int newL = L + (c.eat ? 1 : 0);

        std::vector<int> local;
        std::vector<int>& nb2 = nextBody ? *nextBody : local;
        nb2.clear();
        nb2.reserve(body.size() + 1);
        nb2.push_back(dest);
        nb2.insert(nb2.end(), body.begin(), body.end());
        if (!c.eat && static_cast<int>(nb2.size()) > newL) nb2.pop_back();
        c.newL = newL;

        std::vector<int>& blk = blkScratch_;
        blk = base_;
        markBody(blk, nb2, newL);

        int need = std::min(static_cast<int>(p_.spaceFactor * newL) + p_.spaceMargin, b.NC / 2);
        int space = nav_.flood(b, dest, blk, need + 1);
        // Reverse by splitting: a dragon of 4+ can split off everything but a 2-long stub;
        // the child's head is our tail and faces out. So a dead end (a fountain corridor,
        // a pocket) is fine as long as the tail side has room; it costs the 2-long stub.
        bool viaReverse = false;
        if (space < need && newL >= 4 && static_cast<int>(body.size()) == newL) {
            int childNeed = std::min(static_cast<int>(p_.spaceFactor * (newL - 2)) + p_.spaceMargin, b.NC / 2);
            std::vector<int> blk2 = base_;
            for (size_t i = 0; i + 1 < body.size(); i++) blk2[body[i]] = INF;
            int tail = body.back();
            int room = 0;
            for (int q = 0; q < 4 && room < childNeed; q++) {
                int n = b.nb[tail * 4 + q];
                if (n >= 0 && blk2[n] <= 1) room = std::max(room, nav_.flood(b, n, blk2, childNeed + 1) + 1);
            }
            if (room >= childNeed) viaReverse = true;
        }

        nav_.bfs(b, dest, blk, p_.horizon);
        std::vector<int> const& dist = nav_.dist;

        double value = 0;
        for (Target const& t : targets_) {
            if (t.cell == dest) continue;
            int dd = dist[t.cell];
            if (dd == INF) continue;
            if (k > 0 && std::find(eaten.begin(), eaten.end(), t.cell) != eaten.end()) continue;
            int m = dd + 1 + k;  // moves from now, counting the ones already planned
            double v = t.belief * gp(m);
            if (t.countdown >= 0 && t.belief < 0.5)
                v = std::max(v, 0.9 * gp(std::max(m, t.countdown + 1)));
            if (v > 0) {
                int fd = friendDist_[t.cell];
                if (fd < m || (fd == m && friendId_[t.cell] < w_.init.id)) v = 0;
                else if (enemyDist_[t.cell] < m) v *= p_.enemyCloserFactor;
            }
            v += t.explore * gp(m);
            value += v;
        }

        // Long-range pull toward fountains nobody visible is closer to.
        for (Hot const& h : hot_) {
            int dd = dist[h.cell];
            if (dd == INF) {
                // beyond the BFS horizon: no pull (keeps CPU bounded)
                continue;
            }
            int m = dd + 1 + k;
            // A fountain cluster feeds several dragons; yield only to a teammate already on it.
            if (friendDist_[h.cell] < m && friendDist_[h.cell] <= p_.hotYield) continue;
            value += p_.wHot * h.rate * fp(m);
        }

        std::string why;
        for (Hunt const& h : hunts_) {
            int dd = distToHead(dist, h.enemy->head);
            if (dd == INF) continue;
            if (h.job == Job::Attack) {
                // Aim at the head and at the tile it is facing into.
                int ahead = b.nb[h.enemy->head * 4 + h.enemy->headDir];
                if (ahead >= 0 && dist[ahead] != INF) dd = std::min(dd, dist[ahead]);
                value += p_.wHunt * (1.0 + h.gain / 4.0) * gp(dd + k);
                why = h.threat ? "intercept" : "hunt";
            } else {
                value += p_.wSupport * gp(std::abs(dd + k - p_.supportRing));
                if (why.empty()) why = "support";
            }
        }
        if (feedHead_ >= 0) {
            int dd = distToHead(dist, feedHead_);
            if (dd != INF) value += p_.wFeed * gp(dd + k);
            why = "to-feed";
        }
        if (escortOf_ >= 0) {
            int dd = distToHead(dist, escortOf_);
            if (dd != INF) value += p_.wEscort * gp(std::abs(dd + k - p_.escortRing));
            if (why.empty()) why = "escort";
        }

        double danger = 0;
        int enemyLen = 0;
        bool huntNext = false;
        double mult = grower_ ? p_.growerDanger : survival() ? p_.survivalDanger : 1.0;
        if (lateGame()) mult *= 2.0;
        if (nextToEnemyHead(dest, enemyLen, huntNext)) {
            // Parking next to an enemy head hands it the choice (and the drops). Only a
            // trade we would take anyway, with the local numbers, makes that acceptable.
            bool wanted = !grower_ && (huntNext || tradeOk(newL, enemyLen));
            double favour = 1.0;
            if (p_.exposureMode == 0) favour = wanted ? 0.0 : 1.0;
            else if (p_.exposureMode == 1) favour = wanted && localOk(dest, -1) ? p_.exposedFavour : 1.0;
            else favour = wanted && localOk(dest, -1) ? 0.0 : 1.0;
            danger = p_.wDanger * newL * mult * favour;
        }
        if (k == 0 && p_.exposureMode != 0) {
            // Sprint reach: an enemy of length Le can MOVE up to Le - 1 steps onto our head.
            for (EnemyField const& e : enemies_) {
                int dd = e.dist[dest];
                if (dd <= 1 || dd > reachOf(e.visible)) continue;
                bool local = localOk(dest, -1);
                if (p_.exposureMode == 2 && local) continue;
                bool wanted = !grower_ && (huntAt(e.head) || tradeOk(newL, e.visible));
                double favour = wanted && local ? p_.exposedFavour : 1.0;
                danger += p_.wExposed * newL * mult * favour;
            }
        }
        if (grower_) {
            // Keep a buffer: enemy heads two steps away are a problem too.
            for (World::Seen const& s : w_.others)
                if (isEnemy(s) && distToHead(dist, s.head) <= 1) danger += p_.wDanger * p_.growerDanger;
        }

        // Pockets: a tile whose only other way out is one more tile is where dragons get sealed in.
        int exits = 0;
        for (int q = 0; q < 4; q++) {
            int n = b.nb[dest * 4 + q];
            if (n >= 0 && n != head && blk[n] <= 1) exits++;
        }
        if (exits <= 1 && k == 0) danger += p_.wPocket;  // corridors would pile this up along a plan
        // Through a portal the far side may be out of vision. Only the real first step
        // pays for that (lookahead leaves vision all the time), and only much when we
        // recently saw dragons around the exit.
        if (k == 0 && !w_.visible(dest) && dest != b.id(b.X(head) + DX[d], b.Y(head) + DY[d])) {
            bool busy = false;
            for (int q = -1; q < 4 && !busy; q++) {
                int n = q < 0 ? dest : b.nb[dest * 4 + q];
                busy = n >= 0 && w_.occSeen[n] >= 0 && w_.t.round - w_.occSeen[n] <= p_.blindMemory;
            }
            danger += busy ? p_.wBlind * (1.0 + 0.25 * newL) : p_.wBlindQuiet;
        }
        // Heads parked next to a portal are what dragons coming through it crash into
        // (they cannot see us). Pass through or move on; do not loiter there.
        // Only pacing counts: staying beside a portal without going through it. Walking up
        // to a portal and crossing it is free.
        bool crossing = dest != b.id(b.X(head) + DX[d], b.Y(head) + DY[d]);
        if (k == 0 && b.portalSide[dest] && b.portalSide[head] && !crossing) danger += p_.wPortalLoiter;

        c.stepTerm = (c.eat ? p_.eatBonus : 0.0) - danger;
        if (viaReverse) c.stepTerm -= p_.wReverse;
        c.score = value + c.stepTerm + p_.wSpace * std::min(space, need) / need;
        if (space < need && !viaReverse) {
            c.score = -1000.0 + space;  // vetoed, kept only as a last resort
            c.terminal = true;
        }
        c.why = space < need ? "cramped" : !why.empty() ? why : (c.eat ? "eat" : "forage");
        return c;
    }

    // Best score reachable from this state within `depth` more moves; NaN-free,
    // returns -1e18 when no move is legal. Sets timedOut_ when the deadline passes.
    double searchFrom(std::vector<int> const& body, int L, int depth, int k, std::vector<int>& eaten) {
        double best = -1e18;
        std::vector<int> next;
        for (int d = 0; d < 4; d++) {
            if (timeUp()) return best;
            Choice c = scoreFrom(body, L, d, k, eaten, &next);
            if (c.dest < 0) continue;
            double v = c.score;
            if (depth > 1 && !c.terminal) {
                if (c.eat) eaten.push_back(c.dest);
                std::vector<int> child = next;
                double rest = searchFrom(child, c.newL, depth - 1, k + 1, eaten);
                if (c.eat) eaten.pop_back();
                // A dead end deeper down is as bad as it looks; otherwise add what this step earned.
                v = rest <= -1e17 ? -900.0 : c.stepTerm * gp(k) + rest;
            }
            best = std::max(best, v);
        }
        return best;
    }

    bool trySplit(Choice& out, Choice const& bestMove) {
        Board const& b = w_.board;
        if (w_.t.units >= w_.init.unitLimit || !w_.bodyKnown()) return false;
        if (bestMove.eat || bestMove.why == "trade" || bestMove.why == "defend") return false;
        for (Hunt const& h : hunts_)
            if (h.job == Job::Attack) return false;  // attackers stay whole and committed

        int n = 0;
        if (w_.t.round >= p_.feedRound) return false;  // feeding phase: consolidate, never split
        if (grower_) {
            if (lateGame()) return false;  // the longest dragon decides the tiebreak
            int keep = p_.growerKeepBase + w_.t.round / p_.growerKeepEvery;
            if (L_ < keep + p_.growerChild) return false;
            n = p_.growerChild;
        } else {
            if (L_ < p_.swarmSplitLen) return false;
            // Late game: the tiebreak is the longest dragon, so stop splitting and let
            // length pile up, unless the army needs rebuilding.
            if (w_.t.round >= p_.growRound && w_.t.units >= p_.lateSplitUnits) return false;
            n = L_ / 2;
        }
        for (World::Seen const& s : w_.others)
            if (isEnemy(s) && b.cheb(s.head, w_.head) <= p_.splitEnemyDist) return false;

        int keep = L_ - n;
        std::vector<int> parent(w_.body.begin(), w_.body.begin() + keep);
        std::vector<int> child(w_.body.rbegin(), w_.body.rbegin() + n);

        // Parent must still have a roomy move with the child as a wall, and vice versa.
        std::vector<int> blk = base_;
        for (int c : child) blk[c] = INF;
        markBody(blk, parent, keep);
        if (!hasRoomyMove(parent.front(), blk, keep)) return false;

        blk = base_;
        for (int c : parent) blk[c] = INF;
        markBody(blk, child, n);
        if (!hasRoomyMove(child.front(), blk, n)) return false;

        out.split = true;
        out.n = n;
        out.why = grower_ ? "bud" : "split";
        return true;
    }

    // A sprint trade: MOVE 2..sprintMax steps (a length-L dragon has at most L - 1) through
    // free tiles onto an enemy head we are allowed to trade with, where we have the local
    // numbers to eat the drops. Picks the longest such enemy, then the shortest path.
    bool sprintTrade(std::string& path) {
        Board const& b = w_.board;
        if (grower_ || L_ < 3) return false;
        int maxSteps = std::min(p_.sprintMax, L_ - 1);
        std::vector<int> blk = ownBlk();
        // BFS over tiles free right now (blk <= 1: no dragon, not our body).
        std::vector<int> dist(b.NC, INF), from(b.NC, -1), dirTo(b.NC, -1);
        std::vector<int> q{w_.head};
        dist[w_.head] = 0;
        for (size_t qi = 0; qi < q.size(); qi++) {
            int c = q[qi];
            if (dist[c] + 1 >= maxSteps) continue;  // the last step goes onto the head itself
            for (int d = 0; d < 4; d++) {
                int n = b.nb[c * 4 + d];
                if (n < 0 || dist[n] != INF || blk[n] > 1) continue;
                dist[n] = dist[c] + 1;
                from[n] = c;
                dirTo[n] = d;
                q.push_back(n);
            }
        }
        int bestLen = -1, bestSteps = INF, bestEnd = -1, bestDir = -1;
        for (EnemyField const& e : enemies_) {
            if (e.visible < 2) continue;
            bool allowed = huntAt(e.head) != nullptr || tradeOk(L_, e.visible);
            if (!allowed || !localOk(e.head, e.id)) continue;
            for (int d = 0; d < 4; d++) {
                // stand on `pre`, step d onto the head
                int pre = -1;
                for (int k = 0; k < 4; k++) {
                    int n = b.nb[e.head * 4 + k];
                    if (n >= 0 && b.nb[n * 4 + d] == e.head) pre = n;
                }
                if (pre < 0 || dist[pre] == INF) continue;
                int steps = dist[pre] + 1;
                if (steps < 2 || steps > maxSteps) continue;
                if (e.visible > bestLen || (e.visible == bestLen && steps < bestSteps)) {
                    bestLen = e.visible;
                    bestSteps = steps;
                    bestEnd = pre;
                    bestDir = d;
                }
            }
        }
        if (bestEnd < 0) return false;
        std::string rev(1, DCH[bestDir]);
        for (int c = bestEnd; c != w_.head; c = from[c]) rev += DCH[dirTo[c]];
        path.assign(rev.rbegin(), rev.rend());
        return true;
    }

    bool hasRoomyMove(int head, std::vector<int> const& blk, int len) {
        Board const& b = w_.board;
        int need = std::min(std::max(static_cast<int>(p_.spaceFactor * len) + p_.spaceMargin, p_.splitRoom), b.NC / 2);
        for (int d = 0; d < 4; d++) {
            int n = b.nb[head * 4 + d];
            if (n < 0 || blk[n] > 1) continue;
            if (nav_.flood(b, n, blk, need + 1) >= need) return true;
        }
        return false;
    }
};

}  // namespace bc
