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
#include <algorithm>

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
        // Attribute this turn's ECHOES to the one ray we sent alone last turn, if any (see
        // world.hpp's lastProbeDir comment). Must run before broadcast() below picks this turn's
        // probe direction and overwrites lastProbeDir.
        if (kParams.probeEnabled && w.lastProbeDir >= 0) {
            int kind = -1;
            for (int k = 0; k < 5; k++) if (w.t.echo[k] > 0) { kind = k; break; }
            w.probeRound[w.lastProbeDir] = w.t.round;
            w.probeKind[w.lastProbeDir] = kind;
        }
        for (uint64_t v : w.t.msgs) {
            msgauth::Msg m;
            if (!msgauth::open(v, w.t.round, m) || !dedup.fresh(v, w.t.round)) continue;
            // The board wraps on both axes and a sonar ray travels straight until it hits kelp
            // or the first dragon in line -- an unobstructed ray can loop all the way around and
            // land back on its own sender (a real bug reported by another team's public devlog,
            // over-yonder.tech/games/loong/sonar/, for their own roles bot). T_FOUNTAIN/T_QUEEN
            // self-receipt happens to be harmless here (idempotent -- we already believe our own
            // T_QUEEN broadcast directly in broadcast() below, and a self-echoed T_FOUNTAIN just
            // re-confirms a pearl we already know about), but T_CHOKE self-receipt would reserve
            // our own just-chosen destination cell against ourselves. Filter uniformly rather than
            // relying on each message type happening to be harmless.
            if (m.sender == (w.init.id % 4096)) continue;
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
            } else if (m.type == msgauth::T_CHOKE && kParams.wChoke != 0.0) {
                int cell = static_cast<int>(m.data);
                if (cell < 0 || cell >= w.board.NC) continue;
                w.chokeReserved[cell] = std::max(w.chokeReserved[cell], w.t.round + kParams.chokeDuration);
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
    void broadcast(World& w, Out& out, int destCell, bool grower, bool cramped) {
        int rays = 0, soleDir = -1;
        auto send = [&](int dir, uint64_t word) {
            out.sonar(dir, word);
            rays++;
            soleDir = dir;
        };
        if (cramped && kParams.wChoke != 0.0) {
            msgauth::Msg cm;
            cm.type = msgauth::T_CHOKE;
            cm.sender = w.init.id % 4096;
            cm.dir = (w.t.dir + 1) % 4;  // a ray not used by fountain (w.t.dir) or queen (+2)
            cm.data = static_cast<uint32_t>(destCell);
            send(cm.dir, msgauth::seal(cm, w.t.round));
        }
        if (grower && w.t.length >= 3) {
            msgauth::Msg qm;
            qm.type = msgauth::T_QUEEN;
            qm.sender = w.init.id % 4096;
            qm.dir = (w.t.dir + 2) % 4;  // opposite ray from the pearl gossip below
            qm.data = packQueen(w.t.length, w.head);
            send(qm.dir, msgauth::seal(qm, w.t.round));
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
            send(w.t.dir, msgauth::seal(m, w.t.round));
            break;  // one is enough; SONAR overwrites same-direction anyway
        }
        // Continuous sensing: (w.t.dir + 3) % 4 is never targeted by any message above (fountain
        // uses +0, choke +1, queen +2), so it is free on *every* turn, not just an idle one --
        // send a scan there unconditionally rather than only when nothing else fired. This is
        // strictly better coverage than "only probe on an otherwise-silent turn": the dragon polls
        // its surroundings every single round regardless of what else it's saying. The echo is
        // only trusted as an exact per-direction read when this was the turn's *only* ray (see
        // gossip.hpp receive() / world.hpp lastProbeDir) -- when a message also fired, the scan
        // still went out (continuous polling), but the resulting aggregate echo can't be split
        // between the two rays, so that round's read is deliberately left ambiguous rather than
        // guessed at.
        if (kParams.probeEnabled) {
            int dir = (w.t.dir + 3) % 4;
            msgauth::Msg pm;
            // T_LANE: unused elsewhere, and deliberately not T_INTENT -- that type is reserved
            // for a future move-intent broadcast (S4_7_PLAYBOOK.md §7), not this no-op probe.
            pm.type = msgauth::T_LANE;  // no payload meaning; only its echo matters
            pm.sender = w.init.id % 4096;
            pm.dir = dir;
            pm.data = 0;
            send(dir, msgauth::seal(pm, w.t.round));
        }
        w.lastProbeDir = (rays == 1) ? soleDir : -1;
    }
};

}  // namespace bc
