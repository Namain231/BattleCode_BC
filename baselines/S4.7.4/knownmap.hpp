#pragma once

// Identify which of the fixed ladder maps we are on from vision (several share
// width/height, so size alone is not always enough) and, once sure, fill in the
// whole board from tools/gen_maps.py's dump instead of learning it tile by tile:
// full kelp/portal layout and every pearl bed's true [min, max] respawn gap.
//
// Why: the plain vision-only World treats every unseen tile as open ground (Board's
// Edge defaults to kind 0), so a walk through unexplored territory can target a cell
// that is actually a real wall -- the move fails for real even though our own search
// thought it had room. Known terrain removes that whole class of "hit a wall" deaths,
// and known pearl gaps let hot-fountain recognition (Params::hotObs/hotGap) fire from
// round 0 instead of after several observed cycles.
//
// This never guesses: it only ever applies a candidate once vision has ruled out every
// other same-size map, so a mismatch (or a map tools/gen_maps.py has never seen) just
// leaves the bot exactly as vision-only as it already was.
#include "maps_data.hpp"
#include "world.hpp"

namespace bc {

struct KnownMapMatcher {
    bool resolved = false;
    int chosen = -1;                 // index into KNOWN_MAPS once resolved, else -1
    std::vector<int> cands;          // remaining candidate indices
    std::vector<std::vector<int8_t>> candKind;  // [cand][cell*2 + 0/1]: N-edge, W-edge kind

    void init(int w, int h, int nc) {
        for (int i = 0; i < N_KNOWN_MAPS; i++) {
            if (KNOWN_MAPS[i].w != w || KNOWN_MAPS[i].h != h) continue;
            cands.push_back(i);
            std::vector<int8_t> k(nc * 2, 0);
            KnownMap const& m = KNOWN_MAPS[i];
            for (int e = 0; e < m.n_edges; e++) {
                int cell = m.edges[4 * e], d = m.edges[4 * e + 1], kind = m.edges[4 * e + 2];
                // dir is 0 (N, -> hE) or 3 (W, -> vE) per tools/gen_maps.py.
                if (d == 0) k[cell * 2 + 0] = static_cast<int8_t>(kind == 1 ? 1 : 2);
                else k[cell * 2 + 1] = static_cast<int8_t>(kind == 1 ? 1 : 2);
            }
            candKind.push_back(std::move(k));
        }
        if (cands.empty()) resolved = true;  // an unlisted map: stay vision-only
    }

    // Drop candidates that disagree with what this turn's vision just showed, then
    // apply the map the moment only one is left.
    void filter(World& w, Turn const& t) {
        if (resolved) return;
        Board const& b = w.board;
        int hx = b.X(w.head), hy = b.Y(w.head);
        std::vector<int> keep;
        std::vector<std::vector<int8_t>> keepKind;
        for (size_t ci = 0; ci < cands.size(); ci++) {
            std::vector<int8_t> const& k = candKind[ci];
            bool ok = true;
            for (int r = 0; r < 8 && ok; r++)
                for (int c = 0; c < 7 && ok; c++) {
                    int cell = b.id(hx + c - 3, hy + r - 3);
                    int kind = t.hRows[r][c].kind;  // 0 empty, 1 kelp, 2 portal
                    int8_t want = k[cell * 2 + 0];  // 0 open, 1 kelp, 2 portal
                    if ((kind == 1) != (want == 1)) ok = false;
                    else if ((kind == 2) != (want == 2)) ok = false;
                }
            for (int r = 0; r < 7 && ok; r++)
                for (int c = 0; c < 8 && ok; c++) {
                    int cell = b.id(hx + c - 3, hy + r - 3);
                    int kind = t.vRows[r][c].kind;
                    int8_t want = k[cell * 2 + 1];
                    if ((kind == 1) != (want == 1)) ok = false;
                    else if ((kind == 2) != (want == 2)) ok = false;
                }
            KnownMap const& m = KNOWN_MAPS[cands[ci]];
            for (int i = 0; i < 49 && ok; i++) {
                VisTile const& v = t.tiles[i];
                int cell = b.id(v.x, v.y);
                int hi = m.gaps[2 * cell + 1];
                if (v.pearl && hi == 0) ok = false;               // a pearl sits where this map has no bed
                else if (v.pearlIn > hi && hi > 0) ok = false;     // countdown exceeds the claimed max gap
            }
            if (ok) { keep.push_back(cands[ci]); keepKind.push_back(k); }
        }
        cands.swap(keep);
        candKind.swap(keepKind);
        if (cands.size() == 1) {
            chosen = cands[0];
            apply(w);
            resolved = true;
        } else if (cands.empty()) {
            resolved = true;  // vision disagreed with every candidate: stay vision-only
        }
    }

    void apply(World& w) {
        Board& b = w.board;
        KnownMap const& m = KNOWN_MAPS[chosen];
        for (int e = 0; e < m.n_edges; e++) {
            int cell = m.edges[4 * e], d = m.edges[4 * e + 1], kind = m.edges[4 * e + 2],
                pid = m.edges[4 * e + 3];
            if (kind == 1) {
                if (d == 0) b.hE[cell] = Edge{1};
                else b.vE[cell] = Edge{1};
            } else {
                int x = b.X(cell), y = b.Y(cell);
                w.notePortal(pid, d == 0 ? 0 : 1, x, y);
            }
        }
        for (int c = 0; c < b.NC; c++) {
            int lo = m.gaps[2 * c], hi = m.gaps[2 * c + 1];
            if (hi > 0) {
                b.bed[c] = 1;
                b.gapMin[c] = static_cast<int16_t>(lo);
                b.gapMax[c] = static_cast<int16_t>(hi);
                w.maxCd[c] = static_cast<int16_t>(hi);
                w.cdObs[c] = 99;  // known for certain: satisfies Params::hotObs immediately
            } else {
                b.bed[c] = 0;
            }
        }
        b.rebuild();
    }
};

}  // namespace bc
