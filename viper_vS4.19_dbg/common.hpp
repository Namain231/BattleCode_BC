#pragma once
#define BC_DEBUG

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
    // Reverted to the original safe default: a flat gamma=0.72 (found by param_search on
    // autarky/trauma/trophy alone, a small noisy sample) helped those but badly regressed
    // dilemma (75-100% -> 17%) when tested broadly. See KnownMapMatcher::adapt() (knownmap.hpp)
    // for the map-density-adaptive replacement -- gamma only drops toward 0.72 on maps where
    // essentially every cell is a pearl bed (trophy/default), and stays near this default
    // everywhere else, including any map with no known-map match at all.
    double gamma = 0.80;
    double gammaDensityFactor = 0.08;
    double eatBonus = 1.0;            // eating right now
    // Extra weight on the single best reachable target, on top of the summed field below --
    // V7.12 (wField=0.22, wTarget=1.6, roughly 7:1) commits more decisively to the nearest good
    // pearl instead of only ever pulling diffusely toward everything in range. New 2026-09-29,
    // targeting a persistent growth/eating-speed gap on trophy/trauma/autarky (see
    // s4_7_v4_and_beyond.md: our deaths are consistently lower than the opponent's there, yet we
    // still lose by elimination/length -- a population-speed problem, not safety or combat).
    double wTarget = 4.0;  // param_search_bceval, 2026-09-30: kept, 0.125->0.25 on trophy/trauma/
                            // autarky/schooltime (16-game sample) -- pending broad revalidation
    double exploreValue = 0.03;       // per never-seen tile
    // Map-adaptive boost on top of the flat exploreValue above (KnownMapMatcher::adapt(),
    // knownmap.hpp), found via a direct BC_DEBUG trace of Trophy's round-0-40 collapse
    // (insights.md, 2026-09-30): World::belief() returns exactly 0 for any tile never directly
    // seen, even when knownmap.hpp already knows it's a bed -- so on a bedDensity=1.0 map (every
    // cell a bed), every unexplored direction looks equally, weakly attractive (only this flat
    // constant distinguishes it from a random tile), producing near-tied scores and a wandering,
    // circling pattern instead of decisive exploration. A dense-bed map makes any exploration
    // highly likely productive, so exploreValue should scale up with measured bedDensity instead
    // of staying flat. Default 0 (no adaptive contribution) until A/B tested.
    double exploreValueDensityFactor = 0.0;
    double seenDecay = 0.97;          // belief a pearl we saw is still there, per round
    double spawnDecay = 0.985;        // belief an unseen spawned pearl is still there, per round
    double enemyCloserFactor = 0.5;   // pearl an enemy head reaches first
    // Territory safety margin (ported from viper_vS4.6's kept FEATURE_TERRITORY, 2026-09-30):
    // friendDist_/enemyDist_ are already computed every turn in buildFriendFields() for the
    // enemyCloserFactor pearl discount above -- this reuses them at zero extra BFS cost to
    // penalize a candidate move that lands where the enemy would reach before any friend, a
    // genuine safety signal distinct from "is this pearl contested." Default 0 (off) until
    // A/B tested against the CORE_PANEL baseline; see insights.md's territory section for why
    // this is expected to be a more principled version of the reverted bed-clustering hack.
    double wTerritory = 0.0;

    // Chokepoint reservation via sonar (world.hpp's chokeReserved, gossip.hpp's T_CHOKE),
    // A/B feature 2026-09-30, ported from viper_vS4.6's unused-in-S4.7 msgauth.hpp T_CHOKE: a
    // decentralized reservation-table technique (see today's collision-avoidance research in
    // insights.md) aimed at Schooltime's head-to-head-dominated losses and general self-crowding
    // (Observation 4). Default 0 (off) until A/B tested against the CORE_PANEL baseline.
    double wChoke = 0.0;
    int chokeDuration = 3;   // rounds a reservation lasts after being broadcast

    // Kamikaze aggression (policy.hpp's buildSquadTargets, A/B feature 2026-09-30): a non-grower
    // dragon at or below this length always treats hunting an enemy head as "worth it," bypassing
    // tradeOk's population-floor gate -- per over-yonder.tech/games/loong/roles/'s Champion/
    // Kamikaze/Worker design (their kamikazes hunt unconditionally once short + has a longer
    // teammate). Default 0 (off, exact baseline -- L_ is never <= 0 since minimum length is 2).
    int kamikazeLen = 0;

    // Single-probe sonar echoes (gossip.hpp, world.hpp's lastProbeDir/probeRound/probeKind):
    // send exactly one exploratory sonar (instead of the usual pearl/queen/choke gossip rays) on
    // a turn with nothing else to report, so the next ECHOES line is unambiguous about which
    // direction it describes -- a teammate's S4.6 experiment sending 3-4 rays together got mixed
    // results because the aggregate echo count can't be attributed to any one ray. Off by default:
    // this only wires up the sensor (stores per-direction reads in World), it does not yet feed
    // Policy's scoring -- see insights.md's sonar-echo section for the plan and why that's a
    // separate, later A/B step.
    bool probeEnabled = false;

    // Articulation-point-style chamber check for swarm buds (Policy::chamberBeyond(),
    // trySplit()'s bareExit path): a Tron/Battlesnake AI technique (see insights.md's research
    // section) -- bareExit only checks "is there a free neighbour cell," with no idea whether
    // that neighbour is the mouth of a long corridor that dead-ends or opens into real space.
    // Aimed at the Slithery Fight spiral (real kelp/wall corridor structure, 514 kelp edges among
    // 3402), the leading untested hypothesis all session for why both bots' ordinary swarm-
    // splitting logic runs away on that map specifically. Off by default: an earlier, different
    // room-check tightening on this same bareExit path (hasMinRoom, 2026-09-29) made trauma worse
    // by over-rejecting routine splits, so this needs the same A/B discipline before trusting it.
    bool chamberCheck = false;
    int chamberMaxCorridor = 12;  // cap on how many single-exit corridor tiles to walk through
    // First real scoring use of the probe sensor above (policy.hpp's k==0 danger block): a recent
    // exact echo of enemy/enemy-head in a candidate move's own direction adds danger, the same
    // shape as wPredict's one-step lookahead but from sonar range instead of vision range. Off by
    // default (0) -- meaningless unless probeEnabled is also true, since otherwise probeKind/
    // probeRound never populate. A/B against CORE_PANEL before ever raising this above 0.
    double wProbeDanger = 0.0;
    int probeMemory = 8;  // rounds a probe echo is still trusted (enemy has likely moved after this)
    // Map-adaptive term added on top of the flat wProbeDanger above (KnownMapMatcher::adapt(),
    // knownmap.hpp's wallDensity): a flat wProbeDanger=1.5 A/B test gained +50pp on Slithery Fight
    // (wallDensity ~0.151) but cost -25/-50pp on Autarky/Trophy/Default (wallDensity ~0.07-0.11) --
    // see knownmap.hpp's wallDensity comment for the full result and its caveats. Default 0 (no
    // adaptive contribution) until this gated version is itself A/B tested.
    double wProbeDangerWallFactor = 0.0;
    int horizon = 48;
    int maxRivalFields = 12;          // distance fields computed for the nearest visible heads
    int maxDepth = 10;                // lookahead cap for the anytime search
    double leanMargin = 0.045;        // < this much turn clock left at decide(): one-step turn only

    // safety
    int spaceMargin = 3;              // reachable tiles needed: spaceFactor * length + margin
    double spaceFactor = 2.0;         // eating keeps the tail still, so plain length is optimistic
    double wSpace = 0.6;              // mild preference for open space
    double wDanger = 1.5;             // per own segment, tile next to an enemy head
    // Enemy head velocity prediction (see Policy::scoreFrom's k==0 block): per own segment,
    // stepping into the cell a visible enemy will likely reach next turn by continuing
    // straight. New feature from the user's 2026-09-29 idea list, item 9.
    double wPredict = 0.0;  // param_search_bceval, 2026-09-30: kept, 0.312->0.375 -- removing the
                             // enemy head-velocity-prediction term helped on the flagged maps;
                             // surprising, not yet understood, pending broad revalidation
    double wPocket = 1.5;             // entering a tile with a single way onward
    // per unit of World::crowd[dest] (decaying own-team traffic). Raised from 0.4: portals
    // testing showed a late-game cluster of self-inflicted deaths (hit wall/self/other dragon,
    // not the deliberate "feed" death) right as many dragons converge on the queen once
    // feedMaxLen stopped blocking most of the population from feeding -- the same mass-
    // convergence self-trap shape diagnosed for S4.6, just smaller. wFeed's pull (3.0) toward
    // the queen likely outweighed crowding's old repulsion during that approach.
    // REVERTED 2026-09-29: was raised to 1.0 to fight a portals mass-feed self-trap cluster, but
    // the first real online unranked test (v10.1, id 10822, vs Z-A/Rogo) came back 1W-9L each with
    // DOOMED deaths (hit wall/hit self) dominant across multiple maps -- far worse than the
    // ~56.6% validated at this original value against V7.12 locally. Reverting to the last
    // broadly-validated value pending a proper re-test; the feedMaxLen revert below is the prime
    // suspect, this one is reverted defensively at the same time since it was never separately
    // validated either.
    double wCrowd = 0.4;
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
    int swarmChild = 3;  // param_search_bceval, 2026-09-30: kept, 0.25->0.312 -- pending broad revalidation
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
    // feedRound is a single global trigger: every eligible dragon starts walking to the queen
    // on the exact same round, so the whole army arrives in one synchronised wave and jams up
    // around the queen (measured: portals still loses on length even at a 1.5x population
    // advantage, with a cluster of hit-wall/hit-self/hit-other-dragon deaths right in the feed
    // window -- wCrowd alone couldn't fully damp a sudden simultaneous convergence, since crowd
    // reacts to where teammates *were* last turn, one turn behind everyone deciding to move to
    // the same place at once). Stagger each dragon's own feed start by its id, spreading arrivals
    // over feedWindow rounds instead of one instant. This is a generic anti-synchronisation
    // technique (staggering by dragon id, not by map identity), not a per-map special case.
    int feedWindow = 80;
    int feedStop = 490;               // later sacrifices cannot be eaten in time
    int feedMargin = 4;
    // V7.12 (the strongest reference bot) gates feeding purely on "does not outrank the current
    // queen" -- no absolute length cap. feedMaxLen=6 was an extra restriction unique to this
    // framework: on long games most surviving dragons grow past 6 well before feedRound, which
    // silently locks most of the population out of ever feeding the queen -- a plausible
    // explanation for "population is fine (or ahead), but nobody grows long enough" losses on
    // portals/default (see s4_7_rebuild_progress.md). The `s.visible > bestLen` check just below
    // already requires a real candidate to be feedMargin longer than us, so this was meant as a
    // generous safety ceiling, not the operative gate.
    // REVERTED 2026-09-29: this relaxation (6->999) let far more of the population walk long
    // cross-map distances toward the queen, plausibly exposing far more dragons to the "unseen
    // tile defaults to open" wall-death hazard (knownmap.hpp's own caveat) for much longer, on
    // unfamiliar ground, against a real opponent's differently-shaped map exploration -- the
    // first online unranked test (v10.1 vs Z-A/Rogo) came back 1W-9L each with DOOMED deaths
    // dominant on several maps, far worse than any local test against V7.12 showed. This was only
    // ever validated on a single portals seed, never broadly -- reverting pending a proper
    // broad re-test with the original value.
    int feedMaxLen = 6;
    int feedDist = 1;                 // die when this close to a tile next to the big head
    double wFeed = 3.0;
    // Throughput cap on the feed approach (see Policy::decide()'s feed block): a common-target
    // rendezvous problem in the swarm-robotics literature -- decentralised per-move collision
    // avoidance alone still lets everyone converge on one point and jam up there. If more than
    // feedThroughputCap teammates are already within feedThroughputRadius of the queen, hold back
    // instead of joining the crowd.
    int feedThroughputRadius = 4;
    int feedThroughputCap = 2;

    // hot beds (fountains): fast-respawning beds, valued as a long-range pull
    // proportional to their yield rate (pearls per round).
    int hotObs = 3;                   // a bed is hot once this many countdowns were seen on it...
    int hotGap = 10;                  // ...and none exceeded this
    double hotRate = 0.1;             // mean respawn gap <= 10 rounds
    double wHot = 2.0;
    double gammaFar = 0.93;           // discount per move for the long-range pull
    int hotYield = 4;                 // yield a hot bed only to a teammate this close to it
    // A direct per-tile nudge toward the single best known bed that sits beyond `horizon`
    // (see Policy::macroTarget_/scoreFrom): the decaying wHot*rate*gammaFar^m pull is fine for
    // fountains within tactical BFS range, but for a large sparse-bed map (trauma: nearest known
    // bed can be 90+ tiles away) gammaFar^m rounds to ~0 long before wHot*rate does anything --
    // measured directly: a dragon foraging blind for 78 straight rounds with a fully-resolved
    // known map and a working hot-bed list, because every reachable bed was beyond `horizon` and
    // every out-of-horizon one contributed a value too small to move the needle. This term is
    // undiscounted (one flat weight per tile closer), computed from one full-board BFS per turn
    // (cheap: at most b.NC nodes), so it works at any distance instead of decaying away.
    double wCompass = 0.05;

    // Territory/region control (see Policy::buildTargets()): a bed's effective rate is boosted
    // by how many other hot beds sit within `territoryRadius` of it, so dense clusters compound
    // their pull instead of every bed competing on its own respawn rate alone.
    int territoryRadius = 6;
    // Disabled by default (2026-09-30): a same-seed isolation test confirmed this mechanism was
    // the sole cause of both trauma's gain (0/6->1/6) AND a larger dilemma regression (4/6->2/6)
    // when combined with the emergency-split fix -- net -2.8pp on the 6-map panel. With this at 0
    // (mechanism off), the panel matches the pre-territory 50.0% baseline exactly (autarky even
    // improved 1/6->2/6 from emergency-split alone). Left implemented and gated behind this weight
    // rather than deleted, since the underlying idea (Observations 1/3 in s4_7_v4_and_beyond.md --
    // opponents claim and hold pearl-rich pockets while we spread thin) is still real; it needs a
    // better gate than a flat radius/weight before it's worth re-enabling (e.g. only fire when
    // *global* bedDensity is low, so it never touches dilemma's regime at all).
    double territoryWeight = 0.0;
    // The O(n^2) clustering pass is skipped above this many hot beds -- a max-density map
    // (bedDensity=1.0, e.g. default) can put 1000+ entries in hot_, and the naive loop alone blew
    // the 100M-point per-turn CPU budget on round 0 before this cap existed (killed every starting
    // dragon outright). 200 comfortably covers the sparser-bed maps the bonus targets (trauma ~142
    // known beds, autarky ~188) while skipping the regime where the signal is meaningless anyway.
    int territoryMaxHot = 200;
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
