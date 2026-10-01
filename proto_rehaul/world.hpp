// PROTOTYPE (throwaway). What one dragon knows, all learnt from vision (no map tables).
// Adapted from the Abyss framework's world model.
#pragma once

#include "board.hpp"
#include "io.hpp"

namespace bc {

struct World {
    Init init;
    Board board;

    int simRound = -1;
    std::vector<int> next;         // tracked countdown per tile, -1 unknown
    std::vector<int> lastSpawn;    // round a tracked countdown ran out
    std::vector<int> seenRound;    // last round in vision, -1 never
    std::vector<int8_t> seenPearl;
    std::vector<int16_t> maxCd;    // largest countdown seen on a bed
    std::vector<int16_t> cdObs;

    Turn t;
    int head = -1;
    std::vector<int> body;         // own body, head first (a prefix while the tail is unknown)
    std::vector<int> occ;          // tile -> id of another dragon's segment, -1 free
    std::vector<int> occHead;      // tile -> id if another dragon's head
    std::vector<int> ownVis;       // own segments seen this turn
    struct Seen { int id; char team; int head; int dir; int visible; };
    std::vector<Seen> others;
    struct PortalEnd { int orient, x, y; };
    std::vector<std::pair<int, std::vector<PortalEnd>>> portalEnds;

    void start(Init const& in) {
        init = in;
        board.init(in.w, in.h);
        next.assign(board.NC, -1);
        lastSpawn.assign(board.NC, -1);
        seenRound.assign(board.NC, -1);
        seenPearl.assign(board.NC, 0);
        maxCd.assign(board.NC, 0);
        cdObs.assign(board.NC, 0);
    }

    bool bodyKnown() const { return static_cast<int>(body.size()) == t.length; }
    int visTile(int col, int row) const { return board.id(board.X(head) + col - 3, board.Y(head) + row - 3); }

    void tickTo(int round) {
        while (simRound < round) {
            simRound++;
            for (int c = 0; c < board.NC; c++) {
                if (next[c] < 0) continue;
                if (--next[c] <= 0) { lastSpawn[c] = simRound; next[c] = -1; }
            }
        }
    }

    double belief(int c) const {
        if (seenRound[c] == t.round) return seenPearl[c] ? 1.0 : 0.0;
        double b = 0;
        if (seenPearl[c]) b = std::pow(K.seenDecay, t.round - seenRound[c]);
        if (lastSpawn[c] > seenRound[c]) b = std::max(b, 0.7 * std::pow(K.seenDecay, t.round - lastSpawn[c]));
        return b;
    }

    // A bed is fast once three countdowns were seen on it and none exceeded fastGap.
    bool fastBed(int c) const { return cdObs[c] >= 3 && maxCd[c] <= K.fastGap && maxCd[c] > 0; }

    void observe(Turn const& turn) {
        t = turn;
        std::vector<int> visibleOwn;
        for (Part const& p : t.parts)
            if (p.id == init.id) visibleOwn.push_back(board.id(p.x, p.y));
        head = visibleOwn.empty() ? board.id(t.tiles[24].x, t.tiles[24].y) : visibleOwn.front();
        ownVis = visibleOwn;
        tickTo(t.round);

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
            seenPearl[c] = v.pearl;
            if (v.pearlIn >= 0) {
                board.bed[c] = 1;
                next[c] = v.pearlIn;
                if (v.pearlIn > maxCd[c]) maxCd[c] = static_cast<int16_t>(std::min(v.pearlIn, 30000));
                if (cdObs[c] < 30000) cdObs[c]++;
            } else {
                board.bed[c] = 0;
            }
        }

        // own body: visible contiguous prefix is authoritative, tracking fills the rest
        size_t k = visibleOwn.empty() ? 0 : 1;
        while (k < visibleOwn.size() && adjacent(visibleOwn[k - 1], visibleOwn[k])) k++;
        visibleOwn.resize(k);
        std::vector<int> merged = visibleOwn;
        if (!body.empty() && !visibleOwn.empty())
            for (size_t i = visibleOwn.size(); i < body.size(); i++) merged.push_back(body[i]);
        if (merged.size() == 1 && t.length >= 2) {
            int neck = board.nb[head * 4 + (t.dir ^ 2)];
            if (neck >= 0) merged.push_back(neck);
        }
        if (static_cast<int>(merged.size()) > t.length) merged.resize(t.length);
        body.swap(merged);

        occ.assign(board.NC, -1);
        occHead.assign(board.NC, -1);
        others.clear();
        for (Part const& p : t.parts) {
            if (p.id == init.id) continue;
            int c = board.id(p.x, p.y);
            occ[c] = p.id;
            if (p.head) { occHead[c] = p.id; others.push_back({p.id, p.team, c, p.facing, 0}); }
        }
        for (Seen& s : others)
            for (Part const& p : t.parts)
                if (p.id == s.id) s.visible++;
    }

    bool notePortal(int pid, int orient, int x, int y) {
        std::vector<PortalEnd>* ends = nullptr;
        for (auto& pe : portalEnds)
            if (pe.first == pid) ends = &pe.second;
        if (!ends) { portalEnds.push_back({pid, {}}); ends = &portalEnds.back().second; }
        for (PortalEnd const& e : *ends)
            if (e.orient == orient && e.x == x && e.y == y) return false;
        ends->push_back({orient, x, y});
        if (ends->size() != 2) return false;
        PortalEnd const& a = (*ends)[0];
        PortalEnd const& b = (*ends)[1];
        Edge& ea = a.orient == 0 ? board.hE[board.id(a.x, a.y)] : board.vE[board.id(a.x, a.y)];
        Edge& eb = b.orient == 0 ? board.hE[board.id(b.x, b.y)] : board.vE[board.id(b.x, b.y)];
        ea.kind = eb.kind = 2;
        ea.partnerOrient = static_cast<int8_t>(b.orient); ea.px = static_cast<int16_t>(b.x); ea.py = static_cast<int16_t>(b.y);
        eb.partnerOrient = static_cast<int8_t>(a.orient); eb.px = static_cast<int16_t>(a.x); eb.py = static_cast<int16_t>(a.y);
        return true;
    }

    bool adjacent(int a, int b) const {
        for (int d = 0; d < 4; d++)
            if (board.nb[a * 4 + d] == b) return true;
        return false;
    }

    void advanceBody(int dest, bool grows) {
        body.insert(body.begin(), dest);
        if (!grows && static_cast<int>(body.size()) > t.length) body.pop_back();
    }
};

}  // namespace bc
