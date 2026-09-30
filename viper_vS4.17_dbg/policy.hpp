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
    bool grower = false;     // this turn's role, so main.cpp knows whether to gossip queen status
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
#ifdef BC_DEBUG
    int dbgRouteCur() const { return routeCur_; }
    int dbgRouteFire[4] = {-9, -9, -9, -9};  // per-direction (routeCur_ - dist): -1 unreachable, -9 term skipped
#endif

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
        pickRoute();  // after the friend fields: it yields a fountain a teammate is already closer to
        if (grower_ && w_.t.round >= p_.growRound) {
            bool outgrown = false;
            for (World::Seen const& s : w_.others) {
                if (isEnemy(s)) continue;
                if (s.visible > L_ + p_.queenDeferMargin && isGrower(s.id, s.visible)) { outgrown = true; break; }
            }
            // Also defer to a gossiped queen we cannot currently see: this is the only way
            // dragons that never share vision ever agree on a single queen (see Gossip::T_QUEEN).
            bool queenFresh = w_.knownQueenRound >= 0 && w_.t.round - w_.knownQueenRound <= p_.queenStale;
            if (!outgrown && queenFresh && w_.knownQueenLen > L_ + p_.queenDeferMargin && w_.knownQueenCell != w_.head)
                outgrown = true;
            if (outgrown) grower_ = false;
        }
        buildSquadTargets();

        // End-game feeding (see Params::feedRound/feedWindow): each dragon's own start round is
        // staggered by id so the whole army doesn't converge on the queen in one synchronised wave.
        int myFeedRound = p_.feedRound + (w_.init.id % std::max(1, p_.feedWindow));
        if (w_.t.round >= myFeedRound && w_.t.round < p_.feedStop && L_ <= p_.feedMaxLen) {
            int bestLen = L_ + p_.feedMargin - 1;
            for (World::Seen const& s : w_.others)
                if (!isEnemy(s) && s.visible > bestLen) {
                    bestLen = s.visible;
                    feedHead_ = s.head;
                }
            // No teammate visible right now that's worth feeding: fall back to the gossiped
            // queen (Gossip::T_QUEEN) so a feeder far from the queen can still walk toward it
            // instead of only ever reacting to what's in its own 7x7 vision.
            if (feedHead_ < 0) {
                bool queenFresh = w_.knownQueenRound >= 0 && w_.t.round - w_.knownQueenRound <= p_.queenStale;
                if (queenFresh && w_.knownQueenLen > bestLen && w_.knownQueenCell != w_.head)
                    feedHead_ = w_.knownQueenCell;
            }
            // Throughput cap: decentralised per-move safety alone still lets everyone converge on
            // the queen at once and jam up around it (a well-known result for common-target
            // rendezvous in swarm robotics -- collision avoidance alone creates a local-minimum
            // pile-up at the target). If enough teammates are already visibly near the queen,
            // hold back this turn (fall back to normal play) instead of joining the crowd, unless
            // we're already committed close enough that peeling off would waste the trip.
            if (feedHead_ >= 0) {
                int near = 0;
                for (World::Seen const& s : w_.others)
                    if (!isEnemy(s) && b.cheb(s.head, feedHead_) <= p_.feedThroughputRadius) near++;
                if (near > p_.feedThroughputCap && distToHead(myDist_, feedHead_) > p_.feedDist + 1)
                    feedHead_ = -1;
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
                    c.grower = grower_;
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
                s.grower = grower_;
                return s;
            }
        }

        Choice split;
        if (trySplit(split, best)) { split.grower = grower_; return split; }
        // Boxed in: splitting keeps the front half still this turn while the rear half
        // (a new dragon that moves right away) walks off and frees room.
        if (best.score < -500 && L_ >= 4 && w_.t.units < w_.init.unitLimit) {
            // Reverse: keep a 2-long stub here, the child (our old tail, facing out)
            // leaves with the rest.
            split.split = true;
            split.n = L_ - 2;
            split.why = "reverse";
            split.grower = grower_;
            return split;
        }
        best.grower = grower_;
#ifdef BC_DEBUG
        // TEMP: Trophy round-0-40 blind-forage trace (insights.md, 2026-09-30). Per-direction
        // final scores plus whether depth-0 already saw an eat there, to see why a nearby pearl
        // isn't winning.
        for (int d = 0; d < 4; d++) {
            best.why += " " + std::string(1, DCH[d]) + "=" + std::to_string(static_cast<int>(total[d]))
                      + (first[d].eat ? "e" : "");
        }
#endif
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
    Nav macroNav_;
    int macroTarget_ = -1;
    bool macroReady_ = false;  // macroNav_ holds a valid full-board BFS from our head this turn
    int routeCur_ = INF;       // BFS distance from our head to World::routeCell, INF if no route
    std::vector<int> const* macroDist_ = nullptr;

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
            // hotRate is a noise filter for *learned* rates (few, possibly unlucky
            // observations) -- but knownmap.hpp marks a certain (not learned) bed with
            // cdObs==99, and its rate is then exact, not a guess. Gating those the same way
            // as learned ones threw away the long-range pull for the vast majority of a
            // known map's beds whenever their true rate sat just under hotRate (measured:
            // 130 of trauma's 142 beds have rate ~0.0995, just under the 0.1 default --
            // leaving a dragon with no pull toward 92% of known pearl locations and nothing
            // but blind 7x7 exploration; traced one real game to a dragon foraging blind for
            // 78 straight rounds before finding a single pearl, then getting boxed in).
            bool certain = w_.cdObs[c] >= 99;
            if (rate >= p_.hotRate || certain) hot_.push_back({c, rate});
        }
        // Territory bonus: a bed surrounded by other known beds is worth more than an equally-
        // good isolated one, because staying in a dense cluster means the swarm keeps feeding off
        // it turn after turn instead of scattering to chase single targets one at a time. This is
        // the general fix for "a strong opponent claims a pearl-rich pocket early and breeds off
        // it continuously while we spread thin between isolated beds" -- see
        // s4_7_v4_and_beyond.md's replay-analysis Observations 1/3 (Quaker Qubits, and multiple
        // opponents' "infinite breeding pocket" play on pearl-dense corridors). Deliberately a
        // function of *measured local density* (how many other hot beds are nearby), not any
        // map-specific lookup, so it applies identically on an unseen map.
        //
        // Quadratic in hot_'s size -- badly underestimated this: a max-density map (default,
        // bedDensity=1.0, effectively every cell a bed) put >1000 entries in hot_, and the O(n^2)
        // loop alone exceeded the 100M-point per-turn CPU budget on round 0, killing every one of
        // our starting dragons outright ("exceeded CPU limit" -> "no valid action", confirmed via
        // a direct -v run). Skip it above a size cap: the signal is meaningless in this regime
        // anyway (when nearly every cell is a bed, every bed is trivially "surrounded" by
        // hundreds of others, so there's no differential clustering information left to extract,
        // only quadratic cost to pay for it).
        if (static_cast<int>(hot_.size()) <= p_.territoryMaxHot) {
            for (Hot& h : hot_) {
                int nearby = 0;
                for (Hot const& other : hot_)
                    if (other.cell != h.cell && b.cheb(h.cell, other.cell) <= p_.territoryRadius) nearby++;
                h.rate *= 1.0 + p_.territoryWeight * nearby;
            }
        }
        // Macro compass (see Params::wCompass): among hot beds beyond tactical BFS range, pick
        // the best rate-per-distance one and precompute one full-board distance field to it, once
        // per turn, so scoreFrom can nudge the immediate move toward it without needing to fit the
        // whole trip inside `horizon` or surviving gammaFar's decay over 90+ tiles.
        macroTarget_ = -1;
        macroDist_ = nullptr;
        if (!hot_.empty()) {
            macroNav_.bfs(b, w_.head, base_, b.NC);
            int best = -1;
            double bestScore = -1;
            for (Hot const& h : hot_) {
                int dd = macroNav_.dist[h.cell];
                if (dd == INF || dd <= p_.horizon) continue;  // tactical hot pull already covers this
                double score = h.rate / dd;
                if (score > bestScore) { bestScore = score; best = h.cell; }
            }
            if (best >= 0) { macroTarget_ = best; macroDist_ = &macroNav_.dist; }
            macroReady_ = true;
        }
    }

    // Keep, or choose, the one fountain this dragon is walking to. Runs after hot_ and after
    // macroNav_'s full-board BFS from our head, so it needs no BFS of its own.
    //
    // Only real fountains qualify (rate >= hotRate). That matters because knownmap.hpp marks every
    // bed on a resolved map as `certain`, which puts trauma's 130 gap-1..200 beds (rate 0.00995,
    // effectively dead) into hot_ alongside its 12 gap-1 fountains (rate 1.0) -- committing to one
    // of the 130 would be a long walk to nothing.
    void pickRoute() {
        routeCur_ = INF;
        // macroNav_ is only filled when hot_ is non-empty (buildTargets). With no known fountains
        // there is nothing to route to and the dragon falls back to the old field-only behaviour.
        if (!macroReady_) { w_.routeCell = -1; return; }
        std::vector<int> const& d = macroNav_.dist;
        // Let go of a target we have arrived at, that has gone stale, or that we cannot reach.
        if (w_.routeCell >= 0) {
            bool stale = w_.t.round - w_.routeRound > p_.routeTimeout;
            if (w_.routeCell == w_.head || stale || d[w_.routeCell] == INF) w_.routeCell = -1;
        }
        // Nothing committed: take the nearest real fountain no visible teammate is closer to.
        if (w_.routeCell < 0) {
            int best = -1, bestD = INF;
            for (Hot const& h : hot_) {
                if (h.rate < p_.hotRate) continue;
                int dd = d[h.cell];
                if (dd == INF || dd >= bestD) continue;
                if (friendDist_[h.cell] < dd) continue;  // a teammate is already closer: leave it
                best = h.cell;
                bestD = dd;
            }
            if (best >= 0) {
                w_.routeCell = best;
                w_.routeRound = w_.t.round;
            }
        }
        if (w_.routeCell >= 0) routeCur_ = d[w_.routeCell];
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
            // Kamikaze aggression (A/B feature 2026-09-30, per over-yonder.tech/games/loong/roles/'s
            // Champion/Kamikaze/Worker design): their short dragons hunt and trade unconditionally
            // once assigned kamikaze status, regardless of tradeOk's length-parity math -- a
            // deliberately unsafe-looking cheap-aggression policy. Our own tradeOk already permits
            // a short dragon to trade with anything longer (myLen <= enemyLen+slack is nearly
            // always true when myLen is small), so the real gap is initiating a hunt at all: a very
            // short non-grower dragon here still needs tradeOk's `units >= tradeMinUnits` population
            // floor to be considered "worth" attacking. This session's own bceval/growth_pattern.py
            // findings (winners keep a ~50% population lead throughout, and it's the length lead
            // that separates winner/loser only from round ~300 on) suggest a short dragon is cheap
            // to spend removing a threat well before that population floor would otherwise allow.
            // Default 0 (off, exact baseline behavior) until A/B tested.
            bool worth = threat ? e.visible >= 2
                                 : (L_ <= p_.kamikazeLen || tradeOk(L_, e.visible));
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

        double value = 0, bestTargetV = 0;
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
            bestTargetV = std::max(bestTargetV, v);
            v += t.explore * gp(m);
            value += v;
        }
        // V7.12 (the strongest reference bot) scores a pearl field AND a separate, more heavily
        // weighted bonus for the single best reachable target (wField + wTarget) -- Abyss only
        // ever had the flat summed-field term. Consistently across every change tried this
        // session, our worst maps (trophy/trauma/autarky) show lower "our deaths" than the
        // opponent's yet we still lose by elimination/length: a raw growth/eating-speed gap, not
        // a safety or combat problem. This bonus commits more decisively to the single best
        // nearby pearl instead of a diffuse pull toward everything at once.
        value += p_.wTarget * bestTargetV;

        // Long-range pull toward fountains nobody visible is closer to -- but ONLY when this dragon
        // has no committed route. The two mechanisms do the same job, and the summed field does it
        // badly: measured on trauma it is 8-9.5 of a ~10 total score while varying only 0.1-0.3
        // between directions (3%), i.e. it pulls toward the centroid of every fountain at once
        // rather than toward any one of them, and that residual noise is larger than the route
        // term's honest +/-0.6 per tile of progress. With a route committed the route IS the
        // long-range signal, so leaving the field in only drowns it out.
        for (Hot const& h : hot_) {
            if (w_.routeCell >= 0) break;
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

        // Macro compass: only meaningful for the immediate move (macroDist_ is a snapshot from
        // the real current head, not from any hypothetical deeper position). The instantaneous
        // space>=need check above is myopic -- it says this cell is fine to step onto right now,
        // not that following the compass down a long, narrow corridor stays safe several turns
        // later once our own tail has filled in the room behind us (measured: trauma's wall-death
        // count rose from 51 to 69 after wCompass shipped, becoming the map's #1 death cause,
        // while games got longer and death ratios closer -- consistent with dragons now actually
        // traveling through the maze and sometimes committing to a corridor that boxes them in,
        // instead of never moving far enough to hit this failure mode at all). Scale the pull down
        // in tight quarters (full strength once there's 2x the bare safety margin) so two otherwise
        // similarly-far candidates prefer the roomier one instead of the technically-legal narrow
        // one; leave the hard veto above untouched.
        if (k == 0 && macroTarget_ >= 0 && macroDist_) {
            int dd2 = (*macroDist_)[dest];
            if (dd2 != INF) {
                int cur = (*macroDist_)[w_.head];
                double roomFactor = need > 0 ? std::min(1.0, static_cast<double>(space) / (2.0 * need)) : 1.0;
                value += p_.wCompass * roomFactor * (cur - dd2);
            }
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
        if (k == 0) {
            // Enemy head velocity prediction: an enemy continuing straight in its observed
            // facing direction will likely occupy that cell next turn too -- landing there
            // ourselves is a same-cell (head-to-head) collision that nextToEnemyHead's
            // current-position-only check doesn't catch. Cheap (one neighbour lookup per
            // visible enemy), well-established technique (Battlesnake community).
            for (World::Seen const& s : w_.others) {
                if (!isEnemy(s)) continue;
                int predicted = b.nb[s.head * 4 + s.headDir];
                if (predicted != dest) continue;
                bool wanted = !grower_ && tradeOk(newL, s.visible);
                if (!wanted) danger += p_.wPredict * newL * mult;
            }
        }
        if (grower_) {
            // Keep a buffer: enemy heads two steps away are a problem too.
            for (World::Seen const& s : w_.others)
                if (isEnemy(s) && distToHead(dist, s.head) <= 1) danger += p_.wDanger * p_.growerDanger;
        }
        if (k == 0 && p_.wProbeDanger != 0.0) {
            // Sonar-range danger, past vision: a recent single-ray echo (world.hpp's probeKind/
            // probeRound, gossip.hpp's continuous scan) told us this exact direction hit an enemy
            // or enemy head. Same shape as the wPredict vision-range lookahead just above, but from
            // sonar reach -- the one case a probe echo can name an absolute direction with enough
            // confidence to act on directly, without needing to wire the whole probeKind array into
            // a general scoring field first.
            int age = w_.probeRound[d] < 0 ? INF : w_.t.round - w_.probeRound[d];
            int kind = w_.probeKind[d];
            if (age <= p_.probeMemory && (kind == 3 || kind == 4)) danger += p_.wProbeDanger * mult;
        }
        // Territory safety margin (ported from viper_vS4.6, see common.hpp's wTerritory comment):
        // friendDist_/enemyDist_ are already computed this turn; penalize landing somewhere the
        // enemy would reach before any friend could back us up. Off by default (wTerritory=0).
        if (p_.wTerritory != 0.0) {
            int fd2 = friendDist_[dest], ed2 = enemyDist_[dest];
            if (fd2 < INF && ed2 < INF) {
                double margin = std::max(-10.0, std::min(10.0, static_cast<double>(ed2 - fd2)));
                if (margin < 0) danger += p_.wTerritory * (-margin);
            }
        }

        // Pockets: a tile whose only other way out is one more tile is where dragons get sealed in.
        int exits = 0;
        for (int q = 0; q < 4; q++) {
            int n = b.nb[dest * 4 + q];
            if (n >= 0 && n != head && blk[n] <= 1) exits++;
        }
        if (exits <= 1 && k == 0) danger += p_.wPocket;  // corridors would pile this up along a plan
        // Stigmergy: mildly avoid tiles our own team has been crowding lately, so dragons
        // spread out into different corridors instead of piling into the same one.
        if (k == 0) danger += p_.wCrowd * w_.crowd[dest];
        // Chokepoint reservation (T_CHOKE gossip, A/B feature): a teammate broadcast this cell
        // as its own destination while cramped -- avoid stacking on top of it too. Off by
        // default (wChoke=0); see common.hpp's comment.
        if (k == 0 && p_.wChoke != 0.0 && w_.chokeReserved[dest] > w_.t.round) danger += p_.wChoke;
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
        // Committed-route progress (see World::routeCell). In `stepTerm` on purpose: the anytime
        // depth loop keeps `stepTerm` for the real first step and throws `value` away, which is
        // precisely why wCompass never did anything. Free: `dist` is the BFS from `dest` that this
        // function already ran, so the distance to a fixed target is one lookup.
        if (k == 0 && w_.routeCell >= 0 && routeCur_ != INF) {
            int rd = dist[w_.routeCell];
            if (rd != INF) c.stepTerm += p_.wRoute * (routeCur_ - rd);
#ifdef BC_DEBUG
            dbgRouteFire[d] = (rd == INF) ? -1 : (routeCur_ - rd);
#endif
        }
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

        // Emergency escape: `bestMove` is the full-undivided-body evaluation already done this
        // turn -- if even its best direction was a cramped/vetoed move (scoreFrom's -1000+space
        // safety veto, see the comment on that constant below), this dragon has no safe way to
        // stay whole. Splitting off a bare 2-long stub can save the rest of its length even when
        // the routine growth gates (swarmSplitLen/growerChild/lateGame) wouldn't otherwise allow
        // a split yet -- those gates exist to avoid *wasteful* splits, not to block a last resort.
        // See s4_7_v4_and_beyond.md's replay-analysis Observation 2: a cornered long/grower
        // dragon died outright instead of attempting this. This only ever *adds* an option in a
        // position that was already heading for certain death otherwise -- the child still has to
        // pass its own room check below (bareExit/hasRoomyMove), so it can't trade one death for
        // another for free. Distinct from (and not a repeat of) the reverted trySplit experiment
        // above, which tried to *restrict* routine splits rather than unlock emergency ones.
        bool emergency = bestMove.terminal && bestMove.score < 0 && L_ >= 4;

        int n = 0;
        if (w_.t.round >= p_.feedRound && !emergency) return false;  // feeding phase: consolidate, never split
        if (grower_) {
            if (lateGame() && !emergency) return false;  // the longest dragon decides the tiebreak
            int keep = p_.growerKeepBase + w_.t.round / p_.growerKeepEvery;
            if (L_ < keep + p_.growerChild && !emergency) return false;
            n = emergency ? 2 : p_.growerChild;
        } else {
            if (L_ < p_.swarmSplitLen && !emergency) return false;
            // Late game: the tiebreak is the longest dragon, so stop splitting and let
            // length pile up, unless the army needs rebuilding.
            if (w_.t.round >= p_.growRound && w_.t.units >= p_.lateSplitUnits && !emergency) return false;
            n = emergency ? 2 : std::min(p_.swarmChild, L_ - 2);
        }
        // 7x7 vision only reaches Chebyshev distance 3, so gating every split on "no enemy
        // head anywhere in sight" (splitEnemyDist=2) means we stop budding almost entirely
        // once the board is populous -- exactly when a swarm bud is cheapest (V7.12, the
        // strongest reference bot, guards buds with no enemy-distance check at all, only "the
        // tail has a free neighbour"; each new head still gets its own safety search next
        // turn). Keep the caution for the rarer, more valuable grower bud; drop it for swarm.
        if (grower_)
            for (World::Seen const& s : w_.others)
                if (isEnemy(s) && b.cheb(s.head, w_.head) <= p_.splitEnemyDist) return false;

        int keep = L_ - n;
        std::vector<int> parent(w_.body.begin(), w_.body.begin() + keep);
        std::vector<int> child(w_.body.rbegin(), w_.body.rbegin() + n);

        // Parent must still have a roomy move with the child as a wall, and vice versa.
        // Growers/big splits keep the full flood-fill room bar; swarm buds match V7.12's own
        // bud check exactly -- just "the tail has a free neighbour cell" (bareExit), no flood
        // at all. Each new head still gets the full per-move safety search next turn.
        std::vector<int> blk = base_;
        for (int c : child) blk[c] = INF;
        markBody(blk, parent, keep);
        if (!(grower_ ? hasRoomyMove(parent.front(), blk, keep) : bareExit(parent.front(), blk))) return false;

        blk = base_;
        for (int c : parent) blk[c] = INF;
        markBody(blk, child, n);
        // Tried gating the child's room requirement on whether the parent is already trapped
        // (2026-09-29): a same-seed A/B trace on trauma showed this made things *worse* --
        // wall-deaths rose 59->69 and total deaths 104->119 on the identical seed. Reverted;
        // see s4_7_v4_and_beyond.md for the full comparison and the working theory (hasMinRoom
        // was rejecting routine, non-desperate splits that bareExit used to allow, eroding the
        // population-growth benefit bareExit was chosen for in the first place). The underlying
        // observation -- multiple independent dragons dying to a wall within 1-2 moves of a
        // SPLIT -- is still real (see s4_7_v4_and_beyond.md); it just isn't fixed by this.
        if (!(grower_ ? hasRoomyMove(child.front(), blk, n) : bareExit(child.front(), blk))) return false;

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

    // V7.12's own swarm-bud check: no flood-fill at all, just some free neighbour cell to
    // step onto. The per-move safety search protects every move either half makes afterwards.
    // Optionally (Params::chamberCheck) also requires that neighbour not be the mouth of a
    // dead-end/too-narrow corridor -- see chamberBeyond() below.
    bool bareExit(int head, std::vector<int> const& blk) {
        Board const& b = w_.board;
        for (int d = 0; d < 4; d++) {
            int n = b.nb[head * 4 + d];
            if (n < 0 || blk[n] > 1) continue;
            if (!p_.chamberCheck) return true;
            int need = std::max(p_.splitRoom, 4);
            if (chamberBeyond(head, n, blk, need) >= need) return true;
        }
        return false;
    }

    // Articulation-point-lite chamber check (Params::chamberCheck, off by default -- see
    // common.hpp): bareExit's plain "free neighbour" check can't tell a real room from the mouth
    // of a corridor that dead-ends a few tiles further on -- exactly the failure mode Tron/
    // Battlesnake AI postmortems call out (never enter a cut-vertex unless it leads to the
    // largest remaining chamber). Rather than full articulation-point detection (expensive to
    // recompute every candidate move), walk forward through any stretch of true corridor (exactly
    // one way onward, ignoring where we came from) up to chamberMaxCorridor tiles, then flood-fill
    // from wherever it actually opens up or dead-ends. In open space this walk terminates after 0
    // steps (2+ exits immediately), so it's identical to a plain one-step flood there -- it only
    // differs from bareExit's blind guess in genuine narrow-corridor cases.
    int chamberBeyond(int from, int cur, std::vector<int> const& blk, int need) {
        Board const& b = w_.board;
        for (int steps = 0; steps < p_.chamberMaxCorridor; steps++) {
            int nextCell = -1, exits = 0;
            for (int d = 0; d < 4; d++) {
                int n = b.nb[cur * 4 + d];
                if (n < 0 || n == from || blk[n] > 1) continue;
                exits++;
                nextCell = n;
            }
            if (exits != 1) break;  // branch (2+) or dead end (0): stop, measure from here
            from = cur;
            cur = nextCell;
        }
        return nav_.flood(b, cur, blk, need + 1);
    }
};

}  // namespace bc
