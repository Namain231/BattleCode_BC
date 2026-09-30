// Every dragon runs its own copy of this program. Each turn: read what the dragon
// sees (io.hpp), update what it knows about the map (world.hpp), pick an action
// (policy.hpp) and write it out in a single write.
#include <cstring>

#include "io.hpp"
#include "msgauth.hpp"
#include "policy.hpp"
#include "world.hpp"

// Four rays, one authenticated word each (cast after the action, from the new head):
//   ahead : LANE  - "a head is coming down this line" for whoever meets us in a lane
//   behind: LANE, or QUEEN on a split turn - the child starts with no memory, and its
//           tail-side neighbour is the parent, so this is the parent -> child hand-off
//   sides : QUEEN gossip when we know a queen (we are one, or we heard of one), else LANE
inline void castSonar(bc::Out& out, bc::World const& w, bc::Choice const& c, bool iAmQueen, bc::Params const& p) {
    using namespace bc;
    int round = w.t.round;
    int head = c.dest >= 0 ? c.dest : w.head;
    int dir = c.split ? w.t.dir : (c.sprint.empty() ? c.dir : dirFromChar(c.sprint.back()));
    int len = c.split ? std::max(2, w.t.length - c.n) : w.t.length + (c.eat ? 1 : 0);
    bool fresh = w.queenRec.cell >= 0 && round - w.queenRec.round <= p.queenStale;
    bool haveQueen = iAmQueen || fresh;
    uint32_t lane = World::packLane(head, dir, len);
    uint32_t queen = 0;
    if (iAmQueen) queen = World::packQueen(head, len, 0);
    else if (fresh) queen = World::packQueen(w.queenRec.cell, w.queenRec.len, round - w.queenRec.round);
    auto seal = [&](int ray, int type, uint32_t data) {
        msgauth::Msg m;
        m.type = type;
        m.dir = ray;
        m.sender = w.init.id & 4095;
        m.data = data;
        out.sonar(ray, msgauth::seal(m, round));
    };
    seal(dir, msgauth::T_LANE, lane);
    seal(dir ^ 2, (c.split && haveQueen) ? msgauth::T_QUEEN : msgauth::T_LANE, (c.split && haveQueen) ? queen : lane);
    for (int side : {(dir + 1) & 3, (dir + 3) & 3})
        seal(side, haveQueen ? msgauth::T_QUEEN : msgauth::T_LANE, haveQueen ? queen : lane);
}

int main() {
    using namespace bc;
    clockNow();  // start the meter: setup on the first turn counts against it
    std::setvbuf(stdout, nullptr, _IOFBF, 1 << 16);
    Reader in;
    Init init;
    if (!readInit(in, init)) return 0;

    World world;
    world.start(init);
    Out out;
    Turn turn;
    bool first = true;
    while (readTurn(in, turn)) {
        // The first turn's clock started with the process (setup counts); later ones on arrival.
        double turnStart = first ? 0.0 : clockNow();
        first = false;
        world.observe(turn, kParams);
        Policy policy(world, kParams, turnStart + BC_TURN_BUDGET);
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
        if (!c.sprint.empty() || c.why == "feed") {
            // we die this turn: nothing to announce
        } else {
            castSonar(out, world, c, policy.isQueen(), kParams);
        }
#if BC_INDICATOR
        {
            char lab[48];
            std::snprintf(lab, sizeof lab, "L%d %c U%d d%d", turn.length, policy.role(), turn.units, policy.depthReached());
            out.indicator(lab);
        }
#endif
        out.log("r" + std::to_string(turn.round) + " " + c.why +
                " depth=" + std::to_string(policy.depthReached()) +
                " ms=" + std::to_string(static_cast<int>((clockNow() - turnStart) * 1000)) +
                " L=" + std::to_string(turn.length) +
                " body=" + std::to_string(world.body.size()));
        out.flush();
    }
    return 0;
}
