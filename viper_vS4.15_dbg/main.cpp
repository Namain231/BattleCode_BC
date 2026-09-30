// Every dragon runs its own copy of this program. Each turn: read what the dragon
// sees (io.hpp), update what it knows about the map (world.hpp), pick an action
// (policy.hpp) and write it out in a single write.
#include <cstring>

#include "gossip.hpp"
#include "io.hpp"
#include "knownmap.hpp"
#include "policy.hpp"
#include "world.hpp"

int main() {
    using namespace bc;
    clockNow();  // start the meter: setup on the first turn counts against it
    std::setvbuf(stdout, nullptr, _IOFBF, 1 << 16);
    Reader in;
    Init init;
    if (!readInit(in, init)) return 0;

    World world;
    world.start(init);
    KnownMapMatcher matcher;
    matcher.init(init.w, init.h, world.board.NC);
    Gossip gossip;
    Out out;
    Turn turn;
    bool first = true;
    while (readTurn(in, turn)) {
        // The first turn's clock started with the process (setup counts); later ones on arrival.
        double turnStart = first ? 0.0 : clockNow();
        first = false;
        world.observe(turn, kParams);
        if (!matcher.resolved) matcher.filter(world, turn);
        gossip.receive(world);
        // Map-adaptive Params (Phase 1, see KnownMapMatcher::adapt()): a function of observed
        // map structure, not map identity, so it degrades to the safe kParams defaults on any
        // map with no known-map match at all, including a brand-new one. Named (not a temporary)
        // because Policy stores Params as a reference member -- binding that straight to a
        // temporary here would dangle the moment this statement ends.
        Params const effectiveParams = matcher.adapt(kParams, world);
        Policy policy(world, effectiveParams, turnStart + BC_TURN_BUDGET);
        Choice c = policy.decide();
        if (c.split) {
            out.split(c.n);
            world.body.resize(std::max(2, world.t.length - c.n));
        } else if (!c.sprint.empty()) {
            out.moveSeq(c.sprint);  // sprint trade: we die with the target
        } else {
            out.move(c.dir);
            if (c.dest >= 0) world.advanceBody(c.dest, c.eat);
        }
        if (!c.split) gossip.broadcast(world, out, c.dest, c.grower, c.why == "cramped");
        out.log("r" + std::to_string(turn.round) + " " + c.why +
                " depth=" + std::to_string(policy.depthReached()) +
                " ms=" + std::to_string(static_cast<int>((clockNow() - turnStart) * 1000)) +
                " L=" + std::to_string(turn.length) +
                " body=" + std::to_string(world.body.size())
#ifdef BC_DEBUG
                + " hot=" + std::to_string(policy.dbgHot)
                + " fast=" + std::to_string(policy.dbgFast)
                + " fdist=" + std::to_string(policy.dbgFountainDist)
                + " [d" + std::to_string(c.dir)
                + " expl=" + std::to_string(policy.dbgComp[c.dir].explore)
                + " bel=" + std::to_string(policy.dbgComp[c.dir].belief)
                + " tgt=" + std::to_string(policy.dbgComp[c.dir].target)
                + " hotSum=" + std::to_string(policy.dbgComp[c.dir].hotSum)
                + " hotMax=" + std::to_string(policy.dbgComp[c.dir].hotMax)
                + " comp=" + std::to_string(policy.dbgComp[c.dir].compass) + "]"
                + " mdist=" + std::to_string(policy.dbgMacroDist)
#endif
                );
        out.flush();
    }
    return 0;
}
// rebuild-marker 1790661047.4004264

// rebuild-marker 1790661487.456370400

// rebuild-marker 1790665200.000000000 (wCompass roomFactor gating fix)

// rebuild-marker 1790666400.000000000 (trySplit child hasMinRoom + rescue-mode bareExit fallback)

// rebuild-marker 1790667000.000000000 (reverted trySplit change, kept wCompass roomFactor gating)

// rebuild-marker 1790750000.000000000 (territory clustering bonus + emergency-split bypass)

// rebuild-marker 1790751000.000000000 (fix: cap territory clustering O(n^2) loop -- was crashing dense maps)

// rebuild-marker 1790760000.000000000 (TEMP TEST: territoryWeight=0, isolating vs emergency-split)

// rebuild-marker 1790761000.000000000 (final: territoryWeight=0 shipped default, confirmed 18/36=50.0% -- see s4_7_v4_and_beyond.md)

// rebuild-marker 1790900000.000000000 (wTerritory + T_CHOKE reservation added, both off by default (0) -- A/B test pending)

// rebuild-marker 1790950000.000000000 (gossip.hpp: filter self-sent sonar messages, wrap-around bug per over-yonder.tech/games/loong/sonar/)

// rebuild-marker 1790960000.000000000 (kamikazeLen gated hunt-aggression experiment, off by default -- A/B test pending)

// rebuild-marker 1790970000.000000000 (applied param_search_bceval's 3 confirmed gains: wTarget=4, wPredict=0, swarmChild=3 -- broad revalidation pending)

// rebuild-marker 1790980000.000000000 (fixed ECHOES parsing bug (was fully discarded) + single-probe sonar echo sensor, off by default via Params::probeEnabled -- infrastructure only, not yet wired into Policy scoring)

// rebuild-marker 1790981000.000000000 (probe no-op message moved from T_INTENT to T_LANE -- T_INTENT is reserved for a future move-intent broadcast, see playbook)

// rebuild-marker 1790982000.000000000 (probe upgraded to continuous: (dir+3)%4 is never used by any message type, so it scans every turn unconditionally, not just on an otherwise-silent turn -- still off by default via Params::probeEnabled)

// rebuild-marker 1790983000.000000000 (first real scoring use of probe echoes: wProbeDanger, sonar-range enemy-head avoidance mirroring wPredict's shape -- off by default, A/B pending)

// rebuild-marker 1790985000.000000000 (map-adaptive wProbeDanger: knownmap.hpp's wallDensity + Params::wProbeDangerWallFactor, gated by measured kelp-edge fraction instead of one flat constant -- off by default, A/B pending)

// rebuild-marker 1790990000.000000000 (Params::exploreValueDensityFactor: map-adaptive exploreValue boost from a BC_DEBUG trace of Trophy's round-0-40 blind-forage bug -- off by default, A/B pending)

// rebuild-marker 1790995000.000000000 (self-sensed wallDensity/bedDensity infrastructure added, but gamma's density adaptation reverted to known-map-only -- self-sensed local sampling made maps_gen worse, not better; infrastructure kept for wProbeDanger)

// rebuild-marker 1791000000.000000000 (Params::chamberCheck: articulation-point-lite corridor-walk chamber check for trySplit's bareExit path, off by default -- A/B pending, targets the Slithery Fight spiral)
// rebuild-marker 1790719751 (self-sensed wallDensity/bedDensity from echo+vision, feeds KnownMapMatcher::adapt() as a fallback for maps with no known-map entry -- gamma now adapts on unseen maps too, exploreValue/wProbeDanger still gated at 0 by default)
// rebuild-marker 1790721025 (reverted self-sensed bedDensity feeding gamma -- local-sampling bias regressed maps_gen 21.7%->18.3%; kept for wProbeDanger/exploreValue where it's still inert at 0 default)
// rebuild-marker 1790801000 (S4.12: knownmap consensus beds while candidates remain)

// rebuild-marker 1790801100 (S4.12 dbg)

// rebuild-marker 1790804000 (score decomposition)
// rebuild-marker 1790805000 (S4.15: wHot single-best instead of sum)
