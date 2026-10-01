#pragma once

#include "board.hpp"
#include "io.hpp"

namespace bc {

// What one dragon process knows. Rebuilt from scratch by every process: a split
// child inherits nothing, so everything here must be recomputable.
//
// Everything is learnt from vision: terrain, portals, pearl beds, their countdowns
// and how fast each bed refills.
struct World {
    Init init;
    Board board;

    // pearls, from vision only
    int simRound = -1;
    std::vector<int> next;        // countdown per tile while tracked from vision, -1 unknown
    std::vector<int> lastSpawn;   // round a tracked countdown ran out (a pearl likely spawned), -1 never
    std::vector<int> seenRound;   // last round the tile was in vision, -1 never
    std::vector<int8_t> seenPearl;
    std::vector<int16_t> maxCd;   // largest countdown ever seen on a bed: its refill gap, roughly
    std::vector<int16_t> cdObs;   // rounds a countdown was seen on the bed

    // this turn
    Turn t;
    int head = -1;
    std::vector<int> body;        // own body, head first; may be a prefix while the tail is unknown
    std::vector<int> ownExtra;    // own segments seen in vision but not part of the tracked prefix
    std::vector<int> occ;         // tile -> dragon id occupying it (other dragons), -1 free
    std::vector<int> occHeadId;   // tile -> id if it holds another dragon's head
    std::vector<int> visRound;    // == t.round when the tile is in this turn's vision
    std::vector<int> occSeen;     // last round another dragon was seen on the tile, -1 never
    struct Seen { int id; char team; int head; int headDir; int visible; };
    std::vector<Seen> others;     // other dragons with a visible head

    // Portal ends seen, by portal id: (orient 0 = hE / 1 = vE, x, y). A portal is only
    // walkable once both ends are known (Board::stepRaw treats an unpaired end as a wall).
    struct PortalEnd { int orient, x, y; };
    std::vector<std::pair<int, std::vector<PortalEnd>>> portalEnds;
    int startUnits = -1;          // UNIT_COUNT on round 0 (starting dragons per team), -1 unknown

    // Starting dragons get the first ids (both teams). Round 0 tells us how many there are;
    // a split child born later cannot know, and assumes 2 per team.
    int initialCount() const { return startUnits > 0 ? 2 * startUnits : 4; }
    bool isInitial(int id) const { return id < initialCount(); }

    bool visible(int c) const { return visRound[c] == t.round; }

    bool bodyKnown() const { return static_cast<int>(body.size()) == t.length; }

    void start(Init const& in) {
        init = in;
        board.init(in.w, in.h);
        next.assign(board.NC, -1);
        lastSpawn.assign(board.NC, -1);
        seenRound.assign(board.NC, -1);
        seenPearl.assign(board.NC, 0);
        visRound.assign(board.NC, -1);
        occSeen.assign(board.NC, -1);
        maxCd.assign(board.NC, 0);
        cdObs.assign(board.NC, 0);
    }

    int visTile(int col, int row) const { return board.id(board.X(head) + col - 3, board.Y(head) + row - 3); }

    // ---- pearls ---------------------------------------------------------------

    void tickTo(int round) {
        while (simRound < round) {
            simRound++;
            for (int c = 0; c < board.NC; c++) {
                if (next[c] < 0) continue;
                if (--next[c] <= 0) {
                    lastSpawn[c] = simRound;
                    next[c] = -1;  // the next gap is unknown until we see the bed again
                }
            }
        }
    }

    // Probability a pearl is on tile c right now.
    double belief(int c, Params const& p) const {
        if (seenRound[c] == t.round) return seenPearl[c] ? 1.0 : 0.0;
        double b = 0;
        if (seenPearl[c]) b = std::pow(p.seenDecay, t.round - seenRound[c]);
        if (lastSpawn[c] > seenRound[c]) b = std::max(b, std::pow(p.spawnDecay, t.round - lastSpawn[c]));
        return b;
    }

    // ---- per turn --------------------------------------------------------------

    void observe(Turn const& turn, Params const& p) {
        t = turn;
        if (t.round == 0 && startUnits < 0) startUnits = t.units;
        // own head from the parts list (segments of one dragon come head first)
        std::vector<int> visibleOwn;
        for (Part const& part : t.parts)
            if (part.id == init.id) visibleOwn.push_back(board.id(part.x, part.y));
        head = visibleOwn.empty() ? board.id(t.tiles[24].x, t.tiles[24].y) : visibleOwn.front();

        tickTo(t.round);

        // learn edges; portal ends are remembered by id and paired once both are seen
        bool changed = false;
        for (int r = 0; r < 8; r++)
            for (int c = 0; c < 7; c++) {
                int cell = visTile(c, r);
                Edge& e = board.hE[cell];
                if (e.kind != t.hRows[r][c].kind) e = Edge{t.hRows[r][c].kind}, changed = true;
                if (e.kind == 2) changed |= notePortal(t.hRows[r][c].pid, 0, board.X(cell), board.Y(cell));
            }
        for (int r = 0; r < 7; r++)
            for (int c = 0; c < 8; c++) {
                int cell = visTile(c, r);
                Edge& e = board.vE[cell];
                if (e.kind != t.vRows[r][c].kind) e = Edge{t.vRows[r][c].kind}, changed = true;
                if (e.kind == 2) changed |= notePortal(t.vRows[r][c].pid, 1, board.X(cell), board.Y(cell));
            }
        if (changed) board.rebuild();

        for (VisTile const& v : t.tiles) {
            int c = board.id(v.x, v.y);
            seenRound[c] = t.round;
            visRound[c] = t.round;
            seenPearl[c] = v.pearl;
            if (v.pearlIn >= 0) {
                board.bed[c] = 1;
                next[c] = v.pearlIn;
                learnGap(c, v.pearlIn, p);
            } else {
                board.bed[c] = 0;
            }
        }

        // own body: the contiguous visible prefix is authoritative, older tracking fills
        // the rest. A body that leaves vision and comes back shows up non-contiguous.
        size_t k = visibleOwn.empty() ? 0 : 1;
        while (k < visibleOwn.size() && adjacent(visibleOwn[k - 1], visibleOwn[k])) k++;
        ownExtra.assign(visibleOwn.begin() + k, visibleOwn.end());
        visibleOwn.resize(k);
        std::vector<int> merged = visibleOwn;
        if (!body.empty() && !visibleOwn.empty()) {
            // body was advanced by our last move; keep the tracked part beyond the visible prefix
            for (size_t i = visibleOwn.size(); i < body.size(); i++) merged.push_back(body[i]);
        }
        // The neck is always one step back along DIR (portals are symmetric), even when
        // it is out of vision because the body runs through a portal.
        if (merged.size() == 1 && t.length >= 2) {
            int neck = board.nb[head * 4 + (t.dir ^ 2)];
            if (neck >= 0) merged.push_back(neck);
        }
        if (static_cast<int>(merged.size()) > t.length) merged.resize(t.length);
        body.swap(merged);

        occ.assign(board.NC, -1);
        occHeadId.assign(board.NC, -1);
        others.clear();
        for (Part const& part : t.parts) {
            if (part.id == init.id) continue;
            int c = board.id(part.x, part.y);
            occ[c] = part.id;
            occSeen[c] = t.round;
            if (part.head) {
                occHeadId[c] = part.id;
                others.push_back({part.id, part.team, c, part.facing, 0});
            }
        }
        for (Seen& s : others)
            for (Part const& part : t.parts)
                if (part.id == s.id) s.visible++;
    }

    // Remember a portal end; pair both ends (like the engine: the two edges sharing an id)
    // as soon as both are known. Returns true when the board's links changed.
    bool notePortal(int pid, int orient, int x, int y) {
        std::vector<PortalEnd>* ends = nullptr;
        for (auto& pe : portalEnds)
            if (pe.first == pid) ends = &pe.second;
        if (!ends) {
            portalEnds.push_back({pid, {}});
            ends = &portalEnds.back().second;
        }
        for (PortalEnd const& e : *ends)
            if (e.orient == orient && e.x == x && e.y == y) return false;
        ends->push_back({orient, x, y});
        if (ends->size() != 2) return false;
        PortalEnd const& a = (*ends)[0];
        PortalEnd const& b = (*ends)[1];
        Edge& ea = a.orient == 0 ? board.hE[board.id(a.x, a.y)] : board.vE[board.id(a.x, a.y)];
        Edge& eb = b.orient == 0 ? board.hE[board.id(b.x, b.y)] : board.vE[board.id(b.x, b.y)];
        ea.kind = eb.kind = 2;
        ea.partnerOrient = static_cast<int8_t>(b.orient);
        ea.px = static_cast<int16_t>(b.x);
        ea.py = static_cast<int16_t>(b.y);
        eb.partnerOrient = static_cast<int8_t>(a.orient);
        eb.px = static_cast<int16_t>(a.x);
        eb.py = static_cast<int16_t>(a.y);
        return true;
    }

    // A bed's countdown right after a spawn is its whole gap, so the largest one seen
    // estimates the gap from above as the bed keeps being watched. Beds are counted
    // as hot (fountains) once enough small countdowns have been seen.
    void learnGap(int c, int cd, Params const& p) {
        if (cd > maxCd[c]) maxCd[c] = static_cast<int16_t>(std::min(cd, 30000));
        if (cdObs[c] < 30000) cdObs[c]++;
        bool hot = cdObs[c] >= p.hotObs && maxCd[c] <= p.hotGap;
        // Policy's hot-bed pull reads the gap range from the board.
        board.gapMin[c] = board.gapMax[c] = static_cast<int16_t>(hot ? std::max<int>(1, maxCd[c]) : 0);
    }

    bool adjacent(int a, int b) const {
        for (int d = 0; d < 4; d++)
            if (board.nb[a * 4 + d] == b) return true;
        return false;
    }

    // Called after choosing a move so next turn's merge has the right prefix.
    void advanceBody(int dest, bool grows) {
        body.insert(body.begin(), dest);
        if (!grows && !body.empty() && static_cast<int>(body.size()) > t.length) body.pop_back();
    }
};

}  // namespace bc
