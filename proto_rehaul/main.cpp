// PROTOTYPE (throwaway): proto_rehaul. See brain.hpp for the policy.
#include "brain.hpp"
#include "io.hpp"
#include "world.hpp"

int main() {
    using namespace bc;
    clockNow();
    std::setvbuf(stdout, nullptr, _IOFBF, 1 << 16);
    Reader in;
    Init init;
    if (!readInit(in, init)) return 0;
    World world;
    world.start(init);
    std::vector<Mate> mates;
    int lastTarget = -1;
    Turn turn;
    std::string out;
    while (readTurn(in, turn)) {
        world.observe(turn);
        Brain brain(world, mates, lastTarget);
        Role ro = WORKER;
        Action a = brain.decide(ro);
        out.clear();
        switch (a.kind) {
        case 0:
            out += "MOVE "; out += DCH[a.dir]; out += '\n';
            if (a.dest >= 0) world.advanceBody(a.dest, a.eat);
            break;
        case 1:
            out += "SPLIT " + std::to_string(a.n) + '\n';
            world.body.resize(std::max(2, turn.length - a.n));
            break;
        case 2:
            out += "SPLIT 1\n";  // illegal on purpose: die here and drop ceil(L/2) pearls
            break;
        case 3:
            out += "MOVE " + a.steps + '\n';
            break;
        }
        // sonar: our own status fore and aft, the best queen we know of to the sides
        int x = world.board.X(world.head), y = world.board.Y(world.head);
        uint64_t self = encode(ro == QUEEN ? 1 : 0, init.id, turn.length, x, y, turn.round);
        Mate const* best = brain.bestMate();
        uint64_t relay = self;
        if (best && ro != QUEEN)
            relay = encode(2 | (best->queen ? 1 : 0), best->id, best->len, world.board.X(best->cell),
                           world.board.Y(best->cell), best->stamp);
        int f = turn.dir;
        out += "SONAR "; out += DCH[f]; out += ' ' + std::to_string(self) + '\n';
        // on a split turn the aft ray leaves our tail straight into the newborn's head: hand it the queen
        out += "SONAR "; out += DCH[f ^ 2]; out += ' ' + std::to_string((a.kind == 1 && K.handoff) ? relay : self) + '\n';
        out += "SONAR "; out += DCH[(f + 1) & 3]; out += ' ' + std::to_string(relay) + '\n';
        out += "SONAR "; out += DCH[(f + 3) & 3]; out += ' ' + std::to_string(relay) + '\n';
        out += "INDICATOR "; out += ROLECH[ro]; out += std::to_string(turn.length) + ' ' + a.why + '\n';
        out += "PROTOCOL 3\nENDTURN\n";
        std::fwrite(out.data(), 1, out.size(), stdout);
        std::fflush(stdout);
    }
    return 0;
}
// rebuild-marker 1790793087
// rebuild-marker 1790793140
