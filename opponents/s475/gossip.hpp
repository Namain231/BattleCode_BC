#pragma once

// Pearl gossip: share a pearl we can see but are not going for, so a distant teammate can
// beeline to it instead of discovering it on its own. Proven on this ladder (V7.12/Y.7.12.3,
// see ml/results.md): +37% early eating rate, 70% more dragon-turns by round 100 in an A/B test
// -- the single most evidence-backed lever available for the population/growth-speed gap this
// bot is currently behind on (see s4_7_rebuild_progress.md's trophy/portals investigation).
//
// Messages are authenticated with msgauth.hpp (SipHash-based) purely so an opponent's own sonar
// traffic -- which also lands on us, since sonar carries no sender/team info -- can't be
// misread as a false pearl location. K0/K1 are the shared repo defaults; regenerate them (see
// msgauth.hpp's own header) before ever submitting this online, same as every other S4.x build.
#include "msgauth.hpp"
#include "world.hpp"

namespace bc {

struct Gossip {
    msgauth::Dedup dedup;

    static uint32_t packQueen(int len, int cell) {
        return (static_cast<uint32_t>(len) << 13) | (static_cast<uint32_t>(cell) & 0x1FFF);
    }
    static void unpackQueen(uint32_t data, int& len, int& cell) {
        cell = static_cast<int>(data & 0x1FFF);
        len = static_cast<int>((data >> 13) & 0x1FF);
    }

    // Fold in anything teammates told us about, before Policy builds its own targets from
    // vision. A gossiped pearl is treated exactly like a fresh direct sighting: simple, and
    // it's what the proven V7.12 version does. T_QUEEN keeps whichever claim is currently
    // longer (ours or the message's), so the belief converges on the true longest grower
    // without needing everyone to see each other.
    void receive(World& w) {
        for (uint64_t v : w.t.msgs) {
            msgauth::Msg m;
            if (!msgauth::open(v, w.t.round, m) || !dedup.fresh(v, w.t.round)) continue;
            if (m.type == msgauth::T_FOUNTAIN) {
                int cell = static_cast<int>(m.data);
                if (cell < 0 || cell >= w.board.NC) continue;
                if (w.seenRound[cell] == w.t.round) continue;  // already saw it ourselves this turn
                w.seenPearl[cell] = 1;
                w.seenRound[cell] = w.t.round;
            } else if (m.type == msgauth::T_QUEEN) {
                int len, cell;
                unpackQueen(m.data, len, cell);
                if (cell < 0 || cell >= w.board.NC) continue;
                bool stale = w.knownQueenRound < 0 || w.t.round - w.knownQueenRound > kParams.queenStale;
                if (len > w.knownQueenLen || (stale && len > 0)) {
                    w.knownQueenLen = len;
                    w.knownQueenCell = cell;
                    w.knownQueenRound = w.t.round;
                }
            }
        }
        // Our own claim also decays the same way (we may have lost sight of ourselves-as-queen
        // only in the sense that a fresher, longer claim should always win once heard).
        if (w.knownQueenRound >= 0 && w.t.round - w.knownQueenRound > kParams.queenStale) {
            w.knownQueenLen = 0;
            w.knownQueenCell = -1;
        }
    }

    // Called after Policy::decide() so we know our own destination (skip telling teammates
    // about the pearl we're already eating) and whether we're playing as a grower this turn
    // (if so, tell the team how long we are, so a distant feeder can find the real queen).
    void broadcast(World& w, Out& out, int destCell, bool grower) {
        if (grower && w.t.length >= 3) {
            msgauth::Msg qm;
            qm.type = msgauth::T_QUEEN;
            qm.sender = w.init.id % 4096;
            qm.dir = (w.t.dir + 2) % 4;  // opposite ray from the pearl gossip below
            qm.data = packQueen(w.t.length, w.head);
            out.sonar(qm.dir, msgauth::seal(qm, w.t.round));
            // Believe our own broadcast too, so a lone grower with no teammates in radio range
            // still knows it's the (current) queen.
            if (w.t.length > w.knownQueenLen) {
                w.knownQueenLen = w.t.length;
                w.knownQueenCell = w.head;
                w.knownQueenRound = w.t.round;
            }
        }
        for (VisTile const& v : w.t.tiles) {
            if (!v.pearl) continue;
            int cell = w.board.id(v.x, v.y);
            if (cell == destCell) continue;
            msgauth::Msg m;
            m.type = msgauth::T_FOUNTAIN;
            m.sender = w.init.id % 4096;
            m.dir = w.t.dir;
            m.data = static_cast<uint32_t>(cell);
            out.sonar(w.t.dir, msgauth::seal(m, w.t.round));
            return;  // one is enough; SONAR overwrites same-direction anyway
        }
    }
};

}  // namespace bc
