#pragma once

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace bc {

// Direction order matches the engine: North is y-1.
enum Dir : int { N = 0, E = 1, S = 2, W = 3 };
inline constexpr int DX[4] = {0, 1, 0, -1};
inline constexpr int DY[4] = {-1, 0, 1, 0};
inline constexpr char DCH[4] = {'N', 'E', 'S', 'W'};
inline constexpr int INF = 1 << 29;

inline int dirFromChar(char c) {
    switch (c) {
    case 'N': return N;
    case 'E': return E;
    case 'S': return S;
    case 'W': return W;
    }
    return -1;
}

// Every tunable number lives here. These are plain hand-set starting values,
// not tuned ones: tuning them is the first thing to try.
struct Params {
    // pearl value
    double gamma = 0.80;              // discount per move of distance
    double eatBonus = 1.0;            // eating right now
    double exploreValue = 0.03;       // per never-seen tile
    double seenDecay = 0.97;          // belief a pearl we saw is still there, per round
    double spawnDecay = 0.985;        // belief an unseen spawned pearl is still there, per round
    double enemyCloserFactor = 0.5;   // pearl an enemy head reaches first
    int horizon = 48;                 // BFS depth considered
    int maxRivalFields = 12;          // distance fields computed for the nearest visible heads
    int maxDepth = 10;                // lookahead cap for the anytime search
    double leanMargin = 0.045;        // < this much turn clock left at decide(): one-step turn only

    // safety
    int spaceMargin = 3;              // reachable tiles needed: spaceFactor * length + margin
    double spaceFactor = 2.0;         // eating keeps the tail still, so plain length is optimistic
    double wSpace = 0.6;              // mild preference for open space
    double wDanger = 1.5;             // per own segment, tile next to an enemy head
    double wPocket = 1.5;             // entering a tile with a single way onward
    // per unit of World::crowd[dest] (decaying own-team traffic). Raised from 0.4: portals
    // testing showed a late-game cluster of self-inflicted deaths (hit wall/self/other dragon,
    // not the deliberate "feed" death) right as many dragons converge on the queen once
    // feedMaxLen stopped blocking most of the population from feeding -- the same mass-
    // convergence self-trap shape diagnosed for S4.6, just smaller. wFeed's pull (3.0) toward
    // the queen likely outweighed crowding's old repulsion during that approach.
    double wCrowd = 1.0;
    double wReverse = 1.5;            // entering a dead end we can only leave by a reverse split
    double wBlind = 2.0;              // portal into unseen tiles where dragons were seen lately
    double wBlindQuiet = 0.3;         // portal into unseen tiles with no recent sightings
    int blindMemory = 6;              // rounds a sighting near a portal exit stays relevant
    double wPortalLoiter = 1.0;       // ending a move on a tile beside a portal

    // phases
    int earlyEnd = 120;               // hunting squads switch on here ("mid game")
    int midEnd = 400;                 // late game: growers stop splitting, play safest

    // roles: growers (the starting dragons, or anyone long) farm and stay safe;
    // the swarm (split children) escorts, hunts and scavenges.
    int promoteLen = 10;              // any dragon this long plays as a grower
    // From growRound, several dragons can independently qualify as growers (any starting
    // dragon, or anyone >= promoteLen), splitting pearl priority between them instead of
    // funnelling it into one dragon for the round-500 longest-dragon tiebreak -- measured
    // losing "on length" with 0 of our own deaths on portals, i.e. survival was fine but no
    // single dragon grew long enough. If a visible teammate is clearly longer and also
    // grower-eligible, defer to it (drop back to swarm) instead of growing in parallel.
    int queenDeferMargin = 2;
    // How long a gossiped queen sighting (Gossip::T_QUEEN) stays believable before we assume it's
    // stale (died, fed, or been outgrown) -- matches old S4.x's queenStale idea.
    int queenStale = 60;
    int growerKeepBase = 4;           // grower keeps at least base + round/keepEvery segments
    int growerKeepEvery = 30;
    int growerChild = 2;              // growers bud off children this long
    double growerDanger = 3.0;        // extra danger multiplier for growers
    int swarmSplitLen = 4;            // swarm dragons bud a child at this length
    // V7.12 (the strongest reference bot) always sheds a fixed length-2 child once a swarm
    // dragon reaches swarmSplitLen, not half its body: "any dragon that reaches length 4 buds
    // off a length-2 child until the unit cap" -- a constant stream of small units, since a
    // swarm cannot be eliminated and more heads collect more pearls. Halving instead (the old
    // behaviour) keeps far more mass with the parent and produces population much slower.
    int swarmChild = 2;
    int splitEnemyDist = 2;           // no split with an enemy head this close
    int splitRoom = 8;                // grower buds and big splits: both halves need this much room
    // Swarm buds skip this room check entirely (Policy::bareExit) -- see its comment.

    // economy / attrition
    int growerMinUnits = 40;          // growers exist only once the army is this big...
    int growRound = 300;              // ...or from this round
    int lateSplitUnits = 20;          // after growRound the swarm splits only below this many units
    int tradeMinUnits = 4;            // below this many units we do not trade heads
    int tradeSlack = 1;               // trade if own length <= enemy visible length + slack
    int survivalUnits = 3;            // at or below: extra caution
    double survivalDanger = 3.0;

    // squads
    int squadSize = 3;                // per enemy target: 1 attacker + (squadSize-1) supporters
    int escortCount = 3;              // swarm dragons that stay around a visible grower
    int escortRadius = 5;             // enemy head this close to a grower is a threat
    int escortRing = 3;               // escorts hold this distance from the grower
    int supportRing = 3;              // supporters hold this distance from the target, ready to eat
    double wHunt = 1.5;
    double wEscort = 0.8;
    double wSupport = 0.6;

    // head-on trades and sprints (a MOVE of k steps needs length k + 1)
    int localRadius = 3;              // heads this close (Chebyshev) to a trade site count as local
    int reachCap = 3;                 // enemy sprint reach considered: min(visible length - 1, cap)
    double wExposed = 1.2;            // per own segment, ending within an enemy head's reach
    double exposedFavour = 0.35;      // multiplier when we have the local numbers there
    int sprintMax = 3;                // our own sprint trades: at most this many steps
    int sprintTrades = 1;             // 0: no sprint trades
    // How enemy heads count as danger:
    // 0: next to an enemy head, unless we would trade with it; sprint reach ignored
    // 1: anywhere inside an enemy's sprint reach, reduced where we have the local numbers
    // 2: like 0, plus sprint-reach danger only where enemies outnumber us
    int exposureMode = 0;

    // end-game feeding: the longest dragon breaks a round-500 tie. A small dragon that
    // sees a teammate at least feedMargin longer walks to its head and dies there,
    // dropping ceil(L/2) pearls where it will eat them.
    int feedRound = 400;
    int feedStop = 490;               // later sacrifices cannot be eaten in time
    int feedMargin = 4;
    // V7.12 (the strongest reference bot) gates feeding purely on "does not outrank the current
    // queen" -- no absolute length cap. feedMaxLen=6 was an extra restriction unique to this
    // framework: on long games most surviving dragons grow past 6 well before feedRound, which
    // silently locks most of the population out of ever feeding the queen -- a plausible
    // explanation for "population is fine (or ahead), but nobody grows long enough" losses on
    // portals/default (see s4_7_rebuild_progress.md). The `s.visible > bestLen` check just below
    // already requires a real candidate to be feedMargin longer than us, so this is now just a
    // generous safety ceiling, not the operative gate.
    int feedMaxLen = 999;
    int feedDist = 1;                 // die when this close to a tile next to the big head
    double wFeed = 3.0;

    // hot beds (fountains): fast-respawning beds, valued as a long-range pull
    // proportional to their yield rate (pearls per round).
    int hotObs = 3;                   // a bed is hot once this many countdowns were seen on it...
    int hotGap = 10;                  // ...and none exceeded this
    double hotRate = 0.1;             // mean respawn gap <= 10 rounds
    double wHot = 2.0;
    double gammaFar = 0.93;           // discount per move for the long-range pull
    int hotYield = 4;                 // yield a hot bed only to a teammate this close to it
};

inline Params const kParams{};

// Seconds since process start. In the judge's sandbox the clock is virtual and
// advances 1 ns per CPU point spent (unswbc sandbox.py: now = spent + slept_ns),
// so the 100M-point turn budget is 0.1 s on this clock.
inline double clockNow() {
    static auto const start = std::chrono::steady_clock::now();
    return std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
}

// Seconds of that clock the search may spend per turn. The deadline check is
// coarse (once per depth), so actual spend can overshoot this by a few M points;
// 0.075 measured up to ~78M actual in local sandbox runs, above the repo's
// documented ~65M safety margin (AGENTS.md), so budget defensively lower.
#ifndef BC_TURN_BUDGET
#define BC_TURN_BUDGET 0.060
#endif

}  // namespace bc
