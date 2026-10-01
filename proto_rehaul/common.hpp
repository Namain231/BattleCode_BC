// PROTOTYPE (throwaway): proto_rehaul, a from-scratch rule bot built from the docs, the
// research notes and the Loong blog. Plumbing (io/board/nav/world) adapted from the public
// Abyss framework; the policy in brain.hpp is new.
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

inline double clockNow() {
    static auto const start = std::chrono::steady_clock::now();
    return std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
}

// Every tunable number. Hand-set, untuned: the prototype asks structural questions.
struct Knobs {
    // economy
    double gamma = 0.80;         // per-step discount for food
    double gammaFar = 0.95;      // per-step discount for the fast-bed pull
    int horizon = 64;            // BFS depth for food
    double spawnSoon = 0.85;     // P(pearl on a bed whose countdown ends before we arrive)
    double seenDecay = 0.97;     // belief a remembered pearl is still there, per round
    double enemyCloser = 0.4;    // value kept for a pearl an enemy head reaches first
    double exploreUnit = 0.02;   // per never-seen tile, discounted
    double exploreCap = 0.30;
    double keepGoal = 1.3;       // hysteresis on last turn's target
    double wFast = 0.8;          // fast-bed pull weight
    int fastGap = 12;            // a bed with every seen countdown <= this is "fast"

    // splitting (the shared top-team engine: bud at 4 into 2+2, one round after the eat)
    int budLen = 4;
    int budStop = 430;           // workers stop budding and turn to feeding after this round

    // queen / feeding (condition-gated, with a clock floor)
    int queenRound = 200;        // a queen is elected from here...
    int queenUnits = 36;         // ...or once the team is this big
    int queenMinLen = 5;
    int heardFor = 20;           // rounds a heard teammate stays in memory
    int feedFrom = 230;          // feeding ramps from here ...
    int feedAll = 440;           // ... to everyone who can reach the queen by here
    int feedMinLen = 3;
    int feedRadius = 2;          // die when the queen's head is this close (BFS steps)
    int blindPortalRoom = 12;    // room credited to a portal whose far end is unknown
    double wBlindPortal = 0.25;  // exploration value of stepping through such a portal
    int capSlack = 6;            // within this many of the unit cap, grown workers feed instead

    // combat
    int sprintMax = 4;
    int useThreat = 1;           // sprint-aware danger zones in move scoring
    int handoff = 1;             // queen info to the newborn on the aft ray
    int blindPortalStep = 1;     // step through an unseen portal as a last resort           // longest sprint trade we plan (steps)
    int tradeUnits = 8;          // small drones trade heads only with this many units
    double wEnemyAdj = 0.6;      // worker penalty for ending beside an enemy head
    double wFriendAdj = 0.25;    // penalty for ending beside a friendly head
    double wRoom = 0.3;
};

inline Knobs const K{};

#ifndef BC_TURN_BUDGET
#define BC_TURN_BUDGET 0.075
#endif

}  // namespace bc
