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
        Params const effectiveParams = matcher.adapt(kParams);
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
        if (!c.split) gossip.broadcast(world, out, c.dest, c.grower);
        out.log("r" + std::to_string(turn.round) + " " + c.why +
                " depth=" + std::to_string(policy.depthReached()) +
                " ms=" + std::to_string(static_cast<int>((clockNow() - turnStart) * 1000)) +
                " L=" + std::to_string(turn.length) +
                " body=" + std::to_string(world.body.size()));
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
