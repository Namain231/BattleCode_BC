// UNSW Battlecode bot: a 1:1 C++ port of mybot/main.py (same logic, same params in params.cc).
// Every order-dependent choice (tile order, dict insertion order, first-of-equal max, BFS neighbour order)
// and the random number stream (CPython's Mersenne Twister, seeded the same way) match the Python bot,
// so both make the same moves.
#include "helper.hpp"
#include "params.cc"

#include <algorithm>
#include <array>
#include <cstdint>
#include <exception>
#include <set>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

using unswbc::Direction;
using unswbc::EdgeType;

static unswbc::Controller* ct;
static unswbc::Game* game;

// ==========================================
// CPython's random.Random (MT19937, seeded from an int, random() = 53-bit double)
// ==========================================
struct PyRandom {
    uint32_t mt[624];
    int mti = 625;

    void init_genrand(uint32_t s) {
        mt[0] = s;
        for (mti = 1; mti < 624; mti++)
            mt[mti] = 1812433253U * (mt[mti - 1] ^ (mt[mti - 1] >> 30)) + static_cast<uint32_t>(mti);
    }
    void seed(uint64_t s) {
        std::vector<uint32_t> key;
        if (s == 0) key.push_back(0);
        while (s) {
            key.push_back(static_cast<uint32_t>(s & 0xFFFFFFFFU));
            s >>= 32;
        }
        init_genrand(19650218U);
        int i = 1, j = 0;
        int const klen = static_cast<int>(key.size());
        for (int k = std::max(624, klen); k; k--) {
            mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1664525U)) + key[j] + static_cast<uint32_t>(j);
            i++;
            j++;
            if (i >= 624) { mt[0] = mt[623]; i = 1; }
            if (j >= klen) j = 0;
        }
        for (int k = 623; k; k--) {
            mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1566083941U)) - static_cast<uint32_t>(i);
            i++;
            if (i >= 624) { mt[0] = mt[623]; i = 1; }
        }
        mt[0] = 0x80000000U;
        mti = 624;
    }
    uint32_t genrand() {
        static constexpr uint32_t mag01[2] = {0x0U, 0x9908b0dfU};
        uint32_t y;
        if (mti >= 624) {
            int kk;
            for (kk = 0; kk < 624 - 397; kk++) {
                y = (mt[kk] & 0x80000000U) | (mt[kk + 1] & 0x7fffffffU);
                mt[kk] = mt[kk + 397] ^ (y >> 1) ^ mag01[y & 0x1U];
            }
            for (; kk < 623; kk++) {
                y = (mt[kk] & 0x80000000U) | (mt[kk + 1] & 0x7fffffffU);
                mt[kk] = mt[kk + (397 - 624)] ^ (y >> 1) ^ mag01[y & 0x1U];
            }
            y = (mt[623] & 0x80000000U) | (mt[0] & 0x7fffffffU);
            mt[623] = mt[396] ^ (y >> 1) ^ mag01[y & 0x1U];
            mti = 0;
        }
        y = mt[mti++];
        y ^= (y >> 11);
        y ^= (y << 7) & 0x9d2c5680U;
        y ^= (y << 15) & 0xefc60000U;
        y ^= (y >> 18);
        return y;
    }
    double random() {
        uint32_t const a = genrand() >> 5, b = genrand() >> 6;
        return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0);
    }
};
static PyRandom rng;

// ==========================================
// UPGRADED SONAR PROTOCOL
// ==========================================
// Payload structure: [8 bits X] [8 bits Y] [8 bits Type] [8 bits Signature]
constexpr uint64_t SECRET_KEY = 0xAAAAAAAAAAAAAAAAULL;
constexpr uint64_t SONAR_SIG = 0xAA;
constexpr int MSG_PEARL = 1;
constexpr int MSG_THREAT = 2;
constexpr int MSG_KING = 3;
constexpr int MSG_SPAWN = 4;
constexpr int MSG_KING_RELAY = 6;  // CASH2: a king beacon passed on by the dragon that heard it

// A dict with Python's insertion order: an existing key keeps its place when updated.
template <typename V> struct OrderedMap {
    std::vector<std::pair<int, V>> items;
    V* find(int key) {
        for (auto& kv : items)
            if (kv.first == key) return &kv.second;
        return nullptr;
    }
    void set(int key, V value) {
        if (V* v = find(key)) *v = value;
        else items.emplace_back(key, value);
    }
    bool empty() const { return items.empty(); }
};

struct Beacon { int rnd, len; };
static OrderedMap<Beacon> king_beacons;   // tile -> (round heard, sender length)
static OrderedMap<Beacon> king_lengths;   // Tracks {dragon_id: (round_seen, true_length)}
struct Relay { int x, y, len, id; };
static std::vector<Relay> king_relays;    // CASH2: king beacons heard this turn, passed on once
static std::set<std::pair<int, int>> king_relayed;
// Only the last sonar sent in each direction is cast, so sends are queued per direction (highest
// priority wins) and flush_sonar() casts them at the end of the turn.
constexpr int SONAR_KING = 3, SONAR_RELAY = 2, SONAR_BEACON = 1;
static bool sonar_has[4];
static int sonar_pri[4];
static uint64_t sonar_msg[4];

// ==========================================
// V3 1D PATHFINDING ENGINE
// ==========================================
static std::array<Direction, 4> const DIRS = Direction::get_direction_list();
constexpr int DN = 0, DE = 1, DS = 2, DW = 3;
static int dir_of(Direction d) {
    switch (d.value) {
    case Direction::NORTH: return 0;
    case Direction::EAST: return 1;
    case Direction::SOUTH: return 2;
    default: return 3;
    }
}

constexpr int NONE_R = -1000000;  // "not in the dict" for round-valued maps

static int WID = 0, HEI = 0, NT = 0, LAST_ROW = 0;
static std::vector<int8_t> hedge, vedge;  // 0 empty, 1 kelp, 2 portal
// Edge keys: ("h", i) -> i, ("v", i) -> NT + i
static std::vector<int> portal_of;        // edge key -> portal id, -1 if none
static std::vector<int> portal_of_keys;   // insertion order
static std::unordered_map<int, std::vector<int>> portal_ends;
static std::unordered_map<int, int> portal_busy;  // PORTAL TRAFFIC: portal id -> last round an ENEMY touched it
static std::vector<int> portal_taken;     // PORTAL TRAFFIC: edge key -> last round a teammate went through it
static std::vector<int> portal_taken_keys;
static std::vector<int> seen_round, ptime, pearls, others, visits;  // pearls/others: NONE_R if absent
// FARM: largest pearl countdown seen per tile (-1 = never seen as a spawn tile), the spawn tiles we know, and
// countdown restarts seen per tile (a restart = the countdown jumped up since we last saw it)
static std::vector<int> maxpt, pt_last, pt_last_round, pt_restarts;
static std::vector<int> spawn_tiles;
// A fast tile: countdown never seen above FARM_FAST_T, over at least FARM_MIN_RESTARTS restarts
static bool is_fast(int idx) {
    return maxpt[idx] >= 0 && maxpt[idx] <= FARM_FAST_T && pt_restarts[idx] >= FARM_MIN_RESTARTS;
}
struct HeadInfo { int idx; bool enemy; int pid; int dir; };
static std::vector<HeadInfo> heads;       // tile order
static std::vector<int> head_at;          // tile -> index into heads, -1 if none
static std::unordered_map<int, int> seg_count;
static std::unordered_map<int, std::vector<std::pair<int, int>>> bodies;  // enemy id -> [(tile, facing)]
static std::vector<int> mates_near;
static std::vector<char> mate_tile;
static std::vector<int> mate_ids;
static std::vector<int> traj;
static int birth_round = -1;   // King system: first round this dragon was observed
static int splits_done = 0;    // King system: deliberate splits made by this dragon
static int last_rescue = -100; // POPULATION RESCUE: round of this dragon's last rescue split
// search() seeds its first moves in this order, and a tile tied between two first moves is
// credited to the earlier one, so the order tilts exploration. Set at birth (see execute_turn).
static std::array<int, 4> seed_order{0, 1, 2, 3};

// A set of tiles (or edge keys): O(1) membership, insertion-ordered members, O(1) clear.
struct TileSet {
    std::vector<int> stamp;
    std::vector<int> items;
    int cur = 1;
    void init(int size) { stamp.assign(size, 0); items.clear(); cur = 1; }
    void clear() { cur++; items.clear(); }
    void add(int i) {
        if (stamp[i] != cur) { stamp[i] = cur; items.push_back(i); }
    }
    bool has(int i) const { return i >= 0 && i < static_cast<int>(stamp.size()) && stamp[i] == cur; }
    bool empty() const { return items.empty(); }
};

static TileSet room_seen, search_seen, gen_seen;

struct Nbrs {
    int v[4];
    int n = 0;
    void push(int j) { v[n++] = j; }
    int const* begin() const { return v; }
    int const* end() const { return v + n; }
};

static int rnd_now() { return game->get_round_num(); }

static bool is_anchor() { return ANCHOR_ENABLE && 0 <= birth_round && birth_round <= ANCHOR_BORN_BY; }

static void setup() {
    auto const [w, h] = game->get_map_size();
    WID = w;
    HEI = h;
    NT = WID * HEI;
    // Big maps have room (and pearls) for a bigger swarm
    if (NT > BIG_MAP_AREA) {
        MAX_UNITS = BIG_MAX_UNITS;
        MIN_SWARM_UNITS = BIG_MIN_SWARM_UNITS;
        CASH_ROUND -= BIG_CASH_SHIFT;
        CASH_BEACON_ROUND -= BIG_CASH_SHIFT;
        KING_ELECT_ROUND -= BIG_CASH_SHIFT;
        KING_OPEN_ROUND -= BIG_CASH_SHIFT;
    }
    LAST_ROW = (HEI - 1) * WID;
    hedge.assign(NT, 0);
    vedge.assign(NT, 0);
    seen_round.assign(NT, -1);
    ptime.assign(NT, -1);
    pearls.assign(NT, NONE_R);
    others.assign(NT, NONE_R);
    visits.assign(NT, 0);
    maxpt.assign(NT, -1);
    pt_last.assign(NT, -1);
    pt_last_round.assign(NT, -1);
    pt_restarts.assign(NT, 0);
    head_at.assign(NT, -1);
    mate_tile.assign(NT, 0);
    portal_of.assign(2 * NT, -1);
    portal_taken.assign(2 * NT, NONE_R);
    room_seen.init(NT);
    search_seen.init(NT);
    gen_seen.init(NT);
}

static int nb(int idx, int d) {
    if (d == 0) return idx >= WID ? idx - WID : idx + LAST_ROW;
    if (d == 2) return idx < LAST_ROW ? idx + WID : idx - LAST_ROW;
    if (d == 1) {
        int const j = idx + 1;
        return j % WID ? j : j - WID;
    }
    return idx % WID ? idx - 1 : idx - 1 + WID;
}

static int edge_key(int idx, int d) {
    if (d == DN) return idx;
    if (d == DS) return nb(idx, DS);
    if (d == DW) return NT + idx;
    return NT + nb(idx, DE);
}

static int edge_state(int ek) { return ek < NT ? hedge[ek] : vedge[ek - NT]; }
static int edge_tile(int ek) { return ek < NT ? ek : ek - NT; }

static std::vector<int> const* ends_of(int ek) {
    int const pid = portal_of[ek];
    if (pid < 0) return nullptr;
    auto it = portal_ends.find(pid);
    return it == portal_ends.end() ? nullptr : &it->second;
}

static int step(int idx, int d) {
    int const ek = edge_key(idx, d);
    int const st = edge_state(ek);
    if (st == 0) return nb(idx, d);
    if (st == 1) return -1;
    auto const* ends = ends_of(ek);
    int far = -1;
    if (ends)
        for (int e : *ends)
            if (e != ek) far = e;
    if (far < 0) return -2;
    int const fi = edge_tile(far);
    return (d == DS || d == DE) ? fi : nb(fi, d);
}

static int portal_exit(int idx, int d) {
    int const ek = edge_key(idx, d);
    auto const* ends = ends_of(ek);
    if (ends)
        for (int e : *ends)
            if (e != ek) {
                int const fi = edge_tile(e);
                return (d == DS || d == DE) ? fi : nb(fi, d);
            }
    return -2;
}

// Neighbours in the order N, S, E, W (as mybot's nbrs())
static Nbrs nbrs(int idx) {
    Nbrs out;
    int e = hedge[idx];
    if (e == 0) out.push(idx >= WID ? idx - WID : idx + LAST_ROW);
    else if (e == 2) {
        int const j = portal_exit(idx, 0);
        if (j >= 0) out.push(j);
    }
    int j2 = idx < LAST_ROW ? idx + WID : idx - LAST_ROW;
    e = hedge[j2];
    if (e == 0) out.push(j2);
    else if (e == 2) {
        int const j = portal_exit(idx, 2);
        if (j >= 0) out.push(j);
    }
    j2 = idx + 1;
    if (!(j2 % WID)) j2 -= WID;
    e = vedge[j2];
    if (e == 0) out.push(j2);
    else if (e == 2) {
        int const j = portal_exit(idx, 1);
        if (j >= 0) out.push(j);
    }
    e = vedge[idx];
    if (e == 0) out.push(idx % WID ? idx - 1 : idx - 1 + WID);
    else if (e == 2) {
        int const j = portal_exit(idx, 3);
        if (j >= 0) out.push(j);
    }
    return out;
}

// POCKETS: the size of the walled-off area around start, where kelp and portals count as walls and
// unseen edges as open, counted up to cap
static int pocket_size(int start, int cap) {
    gen_seen.clear();
    gen_seen.add(start);
    std::vector<int> q{start};
    std::size_t qh = 0;
    while (qh < q.size()) {
        if (static_cast<int>(q.size()) >= cap) return cap;
        int const i = q[qh++];
        for (int d = 0; d < 4; d++) {
            if (edge_state(edge_key(i, d)) != 0) continue;
            int const j = nb(i, d);
            if (gen_seen.has(j)) continue;
            gen_seen.add(j);
            q.push_back(j);
        }
    }
    return static_cast<int>(q.size());
}

static int seg_of(int pid) {
    auto it = seg_count.find(pid);
    return it == seg_count.end() ? 0 : it->second;
}

static HeadInfo const* head_on(int idx) {
    if (idx < 0) return nullptr;
    int const h = head_at[idx];
    return h < 0 ? nullptr : &heads[h];
}

static void observe() {
    int const rnd = rnd_now();
    int const me = ct->get_id();
    auto const my_team = ct->get_team();
    for (auto const& h : heads) head_at[h.idx] = -1;
    heads.clear();
    seg_count.clear();
    bodies.clear();
    for (int m : mates_near) mate_tile[m] = 0;
    mates_near.clear();
    mate_ids.clear();

    for (auto const& t : ct->get_tiles()) {
        auto const p = t.get_position();
        int const idx = p.y * WID + p.x;

        seen_round[idx] = rnd;
        ptime[idx] = t.get_pearl_time();
        if (ptime[idx] > maxpt[idx]) {
            if (maxpt[idx] < 0) spawn_tiles.push_back(idx);
            maxpt[idx] = ptime[idx];
        }
        if (ptime[idx] >= 0 && pt_last_round[idx] != rnd) {
            if (pt_last_round[idx] >= 0 && ptime[idx] > pt_last[idx] - (rnd - pt_last_round[idx])) pt_restarts[idx]++;
            pt_last[idx] = ptime[idx];
            pt_last_round[idx] = rnd;
        }
        pearls[idx] = t.has_pearl() ? rnd : NONE_R;
        auto const* part = t.get_dragon();
        bool const other = part != nullptr && part->get_id() != me;
        if (other) {
            others[idx] = rnd;
            int const pid = part->get_id();
            seg_count[pid] += 1;
            bool const enemy = !(part->get_team() == my_team);
            if (!enemy) {
                mates_near.push_back(idx);
                mate_tile[idx] = 1;
                if (std::find(mate_ids.begin(), mate_ids.end(), pid) == mate_ids.end()) mate_ids.push_back(pid);
            } else {
                bodies[pid].emplace_back(idx, dir_of(part->get_dir()));
            }
            if (part->is_head()) {
                head_at[idx] = static_cast<int>(heads.size());
                heads.push_back({idx, enemy, pid, dir_of(part->get_dir())});
            }
        } else {
            others[idx] = NONE_R;
        }
        for (int d = 0; d < 4; d++) {
            auto const& e = t.edges[d];
            auto const et = e.get_edge_type();
            if (et == EdgeType::EMPTY) continue;
            int const ek = edge_key(idx, d);
            auto& arr = ek < NT ? hedge : vedge;
            int const i = edge_tile(ek);
            if (et == EdgeType::KELP) {
                arr[i] = 1;
            } else {
                arr[i] = 2;
                int const pid = e.get_portal_id();
                if (other) {
                    if (!(part->get_team() == my_team)) {
                        // its tail may still sit just past the unseen exit
                        portal_busy[pid] = rnd;
                    } else if (dir_of(part->get_dir()) == d) {
                        // a segment faces toward the next one headward: this teammate went through this
                        // edge (from whichever of its two tiles), so leave the edge to it
                        if (portal_taken[ek] == NONE_R) portal_taken_keys.push_back(ek);
                        portal_taken[ek] = rnd;
                    }
                }
                if (portal_of[ek] < 0) portal_of_keys.push_back(ek);
                portal_of[ek] = pid;
                auto& ends = portal_ends[pid];
                if (std::find(ends.begin(), ends.end(), ek) == ends.end()) ends.push_back(ek);
            }
        }
    }
}

// SELF_TRACE: a dragon only remembers its own head positions (traj), so a split child or a round-0 dragon starts
// without its body. Rebuild the missing tail part from the visible own segments: each faces the next one headward.
static void self_trace() {
    int const L = ct->get_length();
    if (traj.empty() || static_cast<int>(traj.size()) >= L) return;
    int const me = ct->get_id();
    std::unordered_map<int, int> prev_of;
    for (auto const& t : ct->get_tiles()) {
        auto const* part = t.get_dragon();
        if (part == nullptr || part->get_id() != me || part->is_head()) continue;
        auto const p = t.get_position();
        int const sgm = p.y * WID + p.x;
        int const nx = step(sgm, dir_of(part->get_dir()));
        if (nx >= 0) prev_of[nx] = sgm;
    }
    std::vector<int> back;
    int cur = traj.front();
    while (static_cast<int>(traj.size() + back.size()) < L) {
        auto f = prev_of.find(cur);
        if (f == prev_of.end()) break;
        cur = f->second;
        if (std::find(back.begin(), back.end(), cur) != back.end() || std::find(traj.begin(), traj.end(), cur) != traj.end())
            break;
        back.push_back(cur);
    }
    if (!back.empty()) traj.insert(traj.begin(), back.rbegin(), back.rend());
}

// Tail-to-head list of our body tiles we know: traj[-L:]
static std::vector<int> my_body(int L) {
    int const start = std::max(0, static_cast<int>(traj.size()) - L);
    return std::vector<int>(traj.begin() + start, traj.end());
}

// The vacate map: depth from which a tile is free again (0 = free now, 1 << 30 = blocked)
static std::vector<int> build_blockers() {
    int const rnd = rnd_now();
    int const L = ct->get_length();
    int const me = ct->get_id();
    std::vector<int> body = my_body(L);
    std::vector<int> vacate(NT, 0);
    for (int k = 0; k < static_cast<int>(body.size()); k++) vacate[body[k]] = k + 2 + VACATE_MARGIN;
    bool const tail_known = static_cast<int>(body.size()) == L;
    std::vector<int> blocked;
    if (!tail_known) {
        for (auto const& t : ct->get_tiles()) {
            auto const* part = t.get_dragon();
            if (part != nullptr && part->get_id() == me) {
                auto const p = t.get_position();
                int const i = p.y * WID + p.x;
                if (vacate[i] == 0) blocked.push_back(i);
            }
        }
        int const off = L - static_cast<int>(body.size());
        gen_seen.clear();
        for (int i : body)
            if (!gen_seen.has(i)) {
                gen_seen.add(i);
                vacate[i] += off;
            }
    }
    for (int i : blocked) vacate[i] = 1 << 30;
    for (int idx = 0; idx < NT; idx++)
        if (others[idx] != NONE_R && rnd - others[idx] <= OTHER_TTL) vacate[idx] = 1 << 30;
    return vacate;
}

static bool passable(int j, int depth, std::vector<int> const& vacate) { return j >= 0 && depth >= vacate[j]; }

static std::vector<int> bfs_q;  // shared queue buffer

// Open tiles reachable from start (start counted), stopping at need
static int room(int start, std::vector<int> const& extra_blocked, std::vector<int> const& vacate, int need) {
    room_seen.clear();
    room_seen.add(start);
    for (int b : extra_blocked) room_seen.add(b);
    // queue of (idx, depth) packed in pairs
    std::vector<int>& q = bfs_q;
    q.clear();
    q.push_back(start);
    q.push_back(1);
    std::size_t qh = 0;
    int count = 0;
    while (qh < q.size()) {
        int const idx = q[qh], depth0 = q[qh + 1];
        qh += 2;
        count++;
        if (count >= need) return count;
        int const depth = depth0 + 1;
        for (int j : nbrs(idx)) {
            if (room_seen.has(j) || depth < vacate[j]) continue;
            room_seen.add(j);
            q.push_back(j);
            q.push_back(depth);
        }
    }
    return count;
}

struct SearchOut {
    std::array<double, 4> best{};
    std::array<int, 4> unknown{};
    std::array<int, 4> tdist{};
    std::array<int, 4> t2dist{};
};

static SearchOut search(int head, std::vector<int> const& vacate, TileSet const* targets, TileSet const* claimed,
                        TileSet const* targets2) {
    int const rnd = rnd_now();
    SearchOut o;
    o.best.fill(0.0);
    o.unknown.fill(0);
    o.tdist.fill(1 << 20);
    o.t2dist.fill(1 << 20);
    search_seen.clear();
    search_seen.add(head);
    std::vector<std::array<int, 3>> q;
    q.reserve(SEARCH_NODES * 2 + 8);
    for (int d : seed_order) {
        int const j = step(head, d);
        if (search_seen.has(j) || !passable(j, 1, vacate)) continue;
        search_seen.add(j);
        q.push_back({j, d, 1});
    }
    int expanded = 0;
    std::size_t qh = 0;

    // Pre-calculate early-game portal gravity (Massive pull before round 50)
    double const curiosity_pull = rnd < SCOUT_ROUNDS ? PEARL_W * PORTAL_SCOUT_MULT : 0;

    while (qh < q.size() && expanded < SEARCH_NODES) {
        auto const [idx, first, dist] = q[qh++];
        expanded++;
        if (targets && targets->has(idx) && dist < o.tdist[first]) o.tdist[first] = dist;
        if (targets2 && targets2->has(idx) && dist < o.t2dist[first]) o.t2dist[first] = dist;

        // DISTANT PORTAL GRAVITY: Pull scouts toward portals before round 50
        if (curiosity_pull > 0) {
            for (int pd = 0; pd < 4; pd++) {
                if (step(idx, pd) == -2) {
                    if (claimed && !claimed->empty() && claimed->has(edge_key(idx, pd))) continue;
                    double const v = curiosity_pull / (1 + dist);
                    if (v > o.best[first]) o.best[first] = v;
                }
            }
        }

        int const sr = seen_round[idx];
        if (sr < 0) {
            o.unknown[first] += 1;
        } else {
            int const pr = pearls[idx];
            if (pr != NONE_R) {
                double const v = (pr == rnd ? PEARL_W : MEMORY_PEARL_W) / (1 + dist);
                if (v > o.best[first]) o.best[first] = v;
            }
            int const pt = ptime[idx];
            if (pt >= 0) {
                int const pred = pt - (rnd - sr);
                if (0 <= pred && pred <= SPAWN_HORIZON) {
                    // FARM: a camper's wait counts FARM_PRED_MULT of a step: it circles the fountain meanwhile
                    bool const fast = is_fast(idx);
                    double const v = fast ? FARM_W / (1 + dist + FARM_PRED_MULT * pred)
                                          : SPAWN_W / (1 + std::max(pred, dist));
                    if (v > o.best[first]) o.best[first] = v;
                }
            }
        }
        int const nd = dist + 1;
        for (int j : nbrs(idx)) {
            if (search_seen.has(j) || nd < vacate[j]) continue;

            // BLIND WRAP PREVENTION: Did we just wrap across the map?
            // A normal step changes X or Y by exactly 1. A wrap changes it by (WID-1) or (HEI-1).
            int const ix = idx % WID, iy = idx / WID;
            int const jx = j % WID, jy = j / WID;
            if (std::abs(ix - jx) > 1 || std::abs(iy - jy) > 1) {
                // If we wrapped through the map boundary into unmapped fog, reject the path
                if (seen_round[j] < 0) continue;
            }

            search_seen.add(j);
            q.push_back({j, first, nd});
        }
    }
    return o;
}

static std::vector<HeadInfo> head_threats(int idx) {
    std::vector<HeadInfo> out;
    for (int d = 0; d < 4; d++) {
        int const j = step(idx, d);
        if (auto const* h = head_on(j)) out.push_back(*h);
    }
    return out;
}

static void ahead_tiles(bool want_enemy, TileSet& out) {
    for (auto const& h : heads) {
        if (h.enemy != want_enemy) continue;
        int const j = step(h.idx, h.dir);
        if (j >= 0) {
            out.add(j);
            int const j2 = step(j, h.dir);
            if (j2 >= 0) out.add(j2);
        }
    }
}

static void around_heads(TileSet& out) {
    for (auto const& h : heads)
        for (int j : nbrs(h.idx)) out.add(j);
}

static int wdist(int a, int b) {
    int const ax = a % WID, ay = a / WID, bx = b % WID, by = b / WID;
    int const dx = std::abs(ax - bx), dy = std::abs(ay - by);
    return std::min(dx, WID - dx) + std::min(dy, HEI - dy);
}

static int pymod(int a, int m) { return ((a % m) + m) % m; }

static bool contains(std::vector<int> const& v, int x) { return std::find(v.begin(), v.end(), x) != v.end(); }

struct Hunt {
    std::vector<int> prey;   // tiles to step on
    std::vector<int> ids;    // prey dragon ids
    std::vector<int> inter;  // intercept tiles to path toward
    std::vector<std::pair<int, int>> targets;  // sprint targets (head idx, visible segs)
};

static bool is_long(int length, int rnd);
static bool is_cash_king(int length, int rnd);

// Returns (prey tiles to step on, prey ids, intercept tiles to path toward, sprint targets)
static Hunt hunt_prey(int length, int units, int rnd, bool has_mates, bool anchor) {
    Hunt out;
    if (anchor && !ANCHOR_HUNT) return out;
    if (!HUNT_ENABLE || heads.empty() || units < HUNT_MIN_UNITS || units < 2) return out;
    int maxlen = HUNT_MAX_LEN;
    if (rnd >= ENDGAME_ROUND && HUNT_ENDGAME_LEN < maxlen) maxlen = HUNT_ENDGAME_LEN;
    if (length > maxlen) return out;

    int const me = ct->get_id();
    double const fill = HUNT_WINDOW_FRAC * 49.0;
    auto add_unique = [](std::vector<int>& v, int x) {
        if (!contains(v, x)) v.push_back(x);
    };
    for (auto const& h : heads) {
        if (!h.enemy) continue;
        int const hidx = h.idx, eid = h.pid, hd = h.dir;
        int const segs = seg_of(eid);
        int const j = step(hidx, hd);

        // Bodyguard Check: Is the enemy about to step onto a friendly segment?
        bool is_threat_to_team = j >= 0 && mate_tile[j];
        if (!is_threat_to_team && has_mates) {
            int const ex = hidx % WID, ey = hidx / WID;
            for (int m : mates_near) {
                int const mx = m % WID, my = m / WID;
                // Wrapped Manhattan distance
                int const dx = std::min(std::abs(mx - ex), WID - std::abs(mx - ex));
                int const dy = std::min(std::abs(my - ey), HEI - std::abs(my - ey));
                if (dx + dy <= HUNT_GUARD_DIST) {
                    is_threat_to_team = true;
                    break;
                }
            }
        }

        // Standard hunting restrictions are bypassed if a teammate is in immediate danger,
        // but a head-on never trades us for a smaller enemy.
        if (is_threat_to_team) {
            if (segs < length) continue;
        } else if (segs <= length || (segs < HUNT_MIN_ENEMY_SEGS && segs < fill)) {
            continue;
        }

        add_unique(out.ids, eid);
        // Vision is live, so its current head is a guaranteed head-on (sprint_attack takes it).
        out.targets.emplace_back(hidx, segs);
        // Close in on the head itself so it falls within sprint reach
        for (int n : nbrs(hidx)) add_unique(out.inter, n);
        if (j >= 0) add_unique(out.inter, j);

        if (eid > me && j >= 0) {
            // Enemy moves after us; step onto their destination to force a crash
            add_unique(out.prey, j);

            // Flank Trapping: Add adjacent tiles to 'inter' to pressure their pathing
            for (int flank_dir = 0; flank_dir < 4; flank_dir++) {
                // Ignore directly ahead and directly behind their facing
                if (flank_dir != hd && flank_dir != (hd + 2) % 4) {
                    int const flank_tile = step(j, flank_dir);
                    if (flank_tile >= 0) add_unique(out.inter, flank_tile);
                }
            }
        }
    }
    return out;
}

// KING HUNT: from CASH_BEACON_ROUND a scout (length <= KING_HUNT_MAXLEN, not a king) goes for any
// visible enemy dragon at least KING_HUNT_RATIO times its length: a head-on kills both whatever their
// size, and the enemy's longest dragon is what wins them the tiebreak. [(head idx, visible segs)]
static std::vector<std::pair<int, int>> king_hunt_targets(int length, int rnd) {
    std::vector<std::pair<int, int>> out;
    if (!(KING_HUNT_ENABLE && CASH_ENABLE) || rnd < CASH_BEACON_ROUND || length > KING_HUNT_MAXLEN) return out;
    if (ct->get_unit_count() < HUNT_MIN_UNITS || is_cash_king(length, rnd)) return out;
    double const need = std::max(static_cast<double>(KING_HUNT_MIN), KING_HUNT_RATIO * length);
    for (auto const& h : heads)
        if (h.enemy && seg_of(h.pid) >= need) out.emplace_back(h.idx, seg_of(h.pid));
    return out;
}

// Sprint head-first into an eligible enemy head reachable this turn. Both die; returns true if sent.
static bool sprint_attack() {
    if (!SPRINT_ENABLE) return false;
    int const length = ct->get_length();
    int const rnd = rnd_now();
    bool const anchor = is_anchor() || is_long(length, rnd);
    Hunt const hp = hunt_prey(length, ct->get_unit_count(), rnd, !mates_near.empty(), anchor);
    std::vector<std::pair<int, int>> targets = hp.targets;
    for (auto const& t : king_hunt_targets(length, rnd)) targets.push_back(t);
    if (targets.empty()) return false;

    // x steps cost x - 1 segments; the head-on kills us anyway, so spend everything but the last one
    int const reach = length - 1;
    auto goal_of = [&](int h) {  // dict(targets): the last entry for a head wins
        int v = -1;
        for (auto const& t : targets)
            if (t.first == h) v = t.second;
        return v;
    };
    int const head = traj.back();
    std::vector<int> const vacate = build_blockers();
    std::unordered_map<int, std::pair<int, int>> prev;
    prev[head] = {-1, -1};
    std::vector<std::pair<int, int>> q{{head, 0}};
    std::size_t qh = 0;
    std::vector<int> found;
    while (qh < q.size()) {
        auto const [idx, dpt] = q[qh++];
        if (dpt >= reach) continue;
        for (int d = 0; d < 4; d++) {
            int const j = step(idx, d);
            if (j < 0 || prev.count(j)) continue;
            if (goal_of(j) >= 0) {
                prev[j] = {idx, d};
                found.push_back(j);
            } else if (passable(j, dpt + 1, vacate)) {
                prev[j] = {idx, d};
                q.push_back({j, dpt + 1});
            }
        }
    }
    if (found.empty()) return false;

    // Biggest prey first; BFS order already makes the first of equal size the shortest
    int tgt = found[0];
    for (int f : found)
        if (goal_of(f) > goal_of(tgt)) tgt = f;
    std::vector<Direction> path;
    int cur = tgt;
    while (prev[cur].first >= 0 || prev[cur].second >= 0) {
        auto const [p, d] = prev[cur];
        path.push_back(DIRS[d]);
        cur = p;
    }
    std::reverse(path.begin(), path.end());
    if (path.size() == 1) ct->make_move(path[0]);
    else ct->make_moves(path);
    return true;
}

// base vacate map with this enemy's visible body freeing up tail-first as it moves
static std::vector<int> enemy_vacate(int eid, int hidx, std::vector<int> const& base) {
    auto it = bodies.find(eid);
    if (it == bodies.end() || it->second.empty()) return base;
    auto const& segs = it->second;
    // Body segments face toward the next segment headward, so invert that to walk head -> tail
    std::unordered_map<int, int> prev_of;
    for (auto const& [s, sd] : segs)
        if (s != hidx) prev_of[step(s, sd)] = s;
    std::vector<int> v = base;
    int const n = static_cast<int>(segs.size());
    int cur = hidx, k = 0;
    while (k < n) {
        auto f = prev_of.find(cur);
        if (f == prev_of.end()) break;
        cur = f->second;
        k++;
        // +2 not +1: room() counts the start tile as depth 1, so its first step is depth 2
        v[cur] = n - k + 2;
    }
    return v;
}

struct Trap { int eh, en; std::vector<int> ev; int eneed, er0; };

// [(enemy head, visible segs, its vacate map, need, room now)] for nearby enemy heads
static std::vector<Trap> trap_setup(int head, std::vector<int> const& vacate) {
    std::vector<std::tuple<int, int, int>> near;
    for (auto const& h : heads)
        if (h.enemy && wdist(head, h.idx) <= TRAP_RADIUS) near.emplace_back(wdist(head, h.idx), h.idx, h.pid);
    std::sort(near.begin(), near.end());
    std::vector<Trap> out;
    for (int k = 0; k < static_cast<int>(near.size()) && k < TRAP_MAX_HEADS; k++) {
        auto const [dd, hidx, eid] = near[k];
        int const n = seg_of(eid);
        std::vector<int> v = enemy_vacate(eid, hidx, vacate);
        int const need = std::min(2 * n + 4, TRAP_CAP);
        int const r0 = room(hidx, {head}, v, need);
        out.push_back({hidx, n, std::move(v), need, r0});
    }
    return out;
}

// Penalty for crossing the portal edge on side d of head: taken (a teammate went through this
// edge within PORTAL_TAKEN_TTL rounds), busy (an enemy touched the portal within PORTAL_BUSY_TTL
// rounds, so its tail may sit past the unseen exit) or claimed (a teammate head is closer to it).
static double portal_traffic_pen(int head, int d, TileSet const& claimed, int rnd) {
    if (!PORTAL_TRAFFIC_ENABLE) return 0.0;
    int const ek = edge_key(head, d);
    int const ppid = portal_of[ek];
    if (ppid < 0) return 0.0;
    int const taken = portal_taken[ek] == NONE_R ? -999 : portal_taken[ek];
    if (rnd - taken <= PORTAL_TAKEN_TTL) return PORTAL_TAKEN_PEN;
    auto b = portal_busy.find(ppid);
    int const busy = b == portal_busy.end() ? -99 : b->second;
    if (rnd - busy <= PORTAL_BUSY_TTL) return PORTAL_BUSY_PEN;
    if (claimed.has(ek)) return PORTAL_CLAIM_PEN;
    return 0.0;
}

static double corridor_pen(int j, int head, std::vector<int> const& vacate) {
    int free = 0;
    for (int k : nbrs(j))
        if (k != head && 2 >= vacate[k]) free++;
    return free < CORRIDOR_MIN ? CORRIDOR_PEN * (CORRIDOR_MIN - free) : 0.0;
}

// True if j lies in a small acyclic pocket reachable only through head (certain death).
static bool dead_end(int j, int head) {
    gen_seen.clear();
    gen_seen.add(head);
    gen_seen.add(j);
    std::vector<int> stack{j};
    int nodes = 0, half = 0;
    while (!stack.empty()) {
        int const x = stack.back();
        stack.pop_back();
        nodes++;
        if (nodes > DEADEND_MAX) return false;
        for (int d = 0; d < 4; d++)
            if (step(x, d) == -2) return false;
        for (int y : nbrs(x)) {
            if (y == head) continue;
            half++;
            if (!gen_seen.has(y)) {
                gen_seen.add(y);
                stack.push_back(y);
            }
        }
    }
    return half / 2 <= nodes - 1;
}

static bool is_long(int length, int rnd) {
    if (!LONG_ENABLE || rnd < LONG_ROUND) return false;
    return is_anchor() || length >= LONG_MIN_LEN;
}

static int mates_within2(int idx) {
    int n = 0;
    int const x = idx % WID, y = idx / WID;
    for (int m : mates_near) {
        int const mx = m % WID, my = m / WID;
        int const dx = std::min(pymod(mx - x, WID), pymod(x - mx, WID));
        int const dy = std::min(pymod(my - y, HEI), pymod(y - my, HEI));
        if (dx <= TEAM_NEAR_RADIUS && dy <= TEAM_NEAR_RADIUS) n++;
    }
    return n;
}

static bool is_king(int length, int rnd) {
    if (!KP_ENABLE || rnd < KP_ROUND || length < KP_MIN_LEN) return false;
    int const my_id = ct->get_id();
    for (int pid : mate_ids) {
        int const mate_len = seg_of(pid);
        // Yield if they are longer, OR if they are the exact same size but older
        if (mate_len > length || (mate_len == length && pid < my_id)) return false;
    }
    // KING MERGE: also yield to a longer (or equal, older) king heard by sonar in the last KING2_SILENCE rounds, so kings that
    // cannot see each other stop splitting the feeding; the smaller one follows the cash-in compass to the bigger one
    for (auto const& [kid, b] : king_lengths.items)
        if (kid != my_id && rnd - b.rnd <= KING2_SILENCE && (b.len > length || (b.len == length && kid < my_id)))
            return false;
    return true;
}

// King for cash-in: a real king, or (CASH2) a self-elected one when no other king has been
// heard for KING_ELECT_SILENCE rounds and no longer teammate is in view, so merging has a target.
static bool is_cash_king(int length, int rnd) {
    if (is_king(length, rnd)) return true;
    if (!CASH2_ENABLE || rnd < KING_ELECT_ROUND || length < KING_ELECT_MIN) return false;
    int const my_id = ct->get_id();
    // KING MERGE: only a longer (or equal, older) king's beacon stops a self-election
    for (auto const& [kid, b] : king_lengths.items)
        if (kid != my_id && rnd - b.rnd <= KING_ELECT_SILENCE && (b.len > length || (b.len == length && kid < my_id)))
            return false;
    for (int pid : mate_ids) {
        int const ml = seg_of(pid);
        if (ml > length || (ml == length && pid < my_id)) return false;
    }
    return true;
}

// CASH2: can the king's head get to our body (where our pearls will drop) within a few steps?
static bool king_can_reach(int kh, std::vector<int> const& body) {
    TileSet& goal = room_seen;  // free here: no room() runs inside this BFS
    goal.clear();
    for (int b : body) goal.add(b);
    int const rnd = rnd_now();
    gen_seen.clear();
    gen_seen.add(kh);
    std::vector<std::pair<int, int>> q{{kh, 0}};
    std::size_t qh = 0;
    while (qh < q.size()) {
        auto const [i, dpt] = q[qh++];
        if (dpt >= CASH_DIST + 3) continue;
        for (int j : nbrs(i)) {
            if (gen_seen.has(j)) continue;
            if (goal.has(j)) return true;
            gen_seen.add(j);
            int const o = others[j] == NONE_R ? -99 : others[j];
            if (rnd - o <= OTHER_TTL) continue;
            q.push_back({j, dpt + 1});
        }
    }
    return false;
}

// Cash-in: (king head idx, king facing) of a visible superior friendly dragon, else {-1, -1}
static TileSet ts_mybody;

// SPRINT DODGE: tiles each visible enemy head could reach in one sprint (visible length - 1 steps, capped at
// DODGE_MAX_REACH, bodies block it), mapped to the shortest such enemy's visible length
static std::unordered_map<int, int> dodge_danger(int head, int slack = 1) {
    std::unordered_map<int, int> out;
    int const rnd = rnd_now();
    ts_mybody.clear();
    for (int b : my_body(ct->get_length())) ts_mybody.add(b);
    for (auto const& h : heads) {
        if (!h.enemy) continue;
        int const le = seg_of(h.pid);
        int const reach = std::min(le - 1, DODGE_MAX_REACH);
        if (reach < 1 || wdist(head, h.idx) > reach + slack) continue;
        std::unordered_map<int, int> seen;
        seen[h.idx] = 0;
        std::vector<std::pair<int, int>> q{{h.idx, 0}};
        for (std::size_t qh = 0; qh < q.size(); qh++) {
            auto const [i, dp] = q[qh];
            if (dp >= reach) continue;
            for (int j : nbrs(i)) {
                if (seen.count(j)) continue;
                seen[j] = dp + 1;
                if (ts_mybody.has(j)) continue;
                if (others[j] != NONE_R && rnd - others[j] <= OTHER_TTL) continue;
                auto it = out.find(j);
                if (it == out.end() || le < it->second) out[j] = le;
                q.push_back({j, dp + 1});
            }
        }
    }
    return out;
}

static std::pair<int, int> cash_target(int length, int rnd) {
    std::pair<int, int> const none{-1, -1};
    if (!CASH_ENABLE || rnd < CASH_ROUND) return none;
    // CASH_NEWBORN_WAIT: a long dragon just born (e.g. the tail of a king's emergency split) doesn't cash in yet: the
    // parent's king beacon (kept up to 10 rounds) still says the parent is long, so the child would feed its own
    // 2-long parent (replays: 14 such newborns of 8-30 length cashed in within 3 rounds of birth)
    if (CASH_NEWBORN_WAIT > 0 && length >= CASH_NEWBORN_LEN && birth_round >= 0 && rnd - birth_round < CASH_NEWBORN_WAIT)
        return none;

    // COMBAT LOCKOUT: Abort suicide instantly if ANY enemy is currently visible
    for (auto const& h : heads)
        if (h.enemy) return none;

    // SPATIAL LOCKOUT: Abort suicide if trapped in a claustrophobic space
    // Dropping pearls in a dead-end forces the massive King to trap itself trying to eat them
    std::vector<int> const vacate = build_blockers();
    int const my_head = traj.back();
    if (room(my_head, {}, vacate, 10) < 10) return none;

    std::pair<int, int> best = none;
    int bl = 0;
    int const my_id = ct->get_id();
    for (auto const& h : heads) {
        if (h.enemy) continue;
        // 1. Read visible segments
        int const physical_len = seg_of(h.pid);
        // 2. Read broadcasted true length
        Beacon* kl = king_lengths.find(h.pid);
        int const broadcast_len = kl ? kl->len : 0;
        // 3. Use the absolute largest known size to bypass the fog illusion
        int const l = std::max(physical_len, broadcast_len);
        // UNIVERSAL HIERARCHY: Yield to strictly larger dragons, OR same size but lower ID
        if (l > length || (l == length && h.pid < my_id)) {
            if ((l >= CASH_KING_MIN || (CASH2_ENABLE && kl != nullptr)) && l > bl) {
                best = {h.idx, h.dir};
                bl = l;
            }
        }
    }
    return best;
}

static TileSet ts_prey, ts_inter, ts_claimed, ts_nopull, ts_sumzone, ts_cut, ts_pess, ts_enemy_ahead;

static int choose() {
    int const head = traj.back();
    int const length = ct->get_length();
    int const units = ct->get_unit_count();
    int const facing = dir_of(ct->get_dir());
    std::vector<int> const vacate = build_blockers();
    int const rnd = rnd_now();
    bool const endgame = rnd >= ENDGAME_ROUND;

    double margin = endgame ? SPACE_MARGIN * ENDGAME_SPACE_MULT : SPACE_MARGIN;

    bool const anchor = is_anchor();
    bool const protect = is_long(length, rnd);
    if (anchor || protect) margin *= ANCHOR_SPACE_MULT;
    double const pmult = (anchor || protect) ? ANCHOR_PORTAL_MULT : 1.0;
    double head_risk = (anchor || protect) ? HEAD_RISK * ANCHOR_HEAD_MULT : HEAD_RISK;
    if (protect && rnd >= LONG_SAFE_ROUND) {
        head_risk *= LONG_SAFE_HEAD_MULT;
        margin *= LONG_SAFE_SPACE_MULT;
    }
    int const need = std::min(static_cast<int>(SPACE_LEN_MULT * length + margin), SPACE_CAP);

    Hunt hp = hunt_prey(length, units, rnd, !mates_near.empty(), anchor || protect);
    ts_prey.clear();
    for (int p : hp.prey) ts_prey.add(p);
    std::vector<int> prey_ids = hp.ids;
    ts_inter.clear();
    for (int t : hp.inter) ts_inter.add(t);
    auto const kh_targets = king_hunt_targets(length, rnd);
    if (!kh_targets.empty()) {
        // an enemy king in view outranks cashing in: count it as prey (no head-risk penalty next to
        // it) and path toward it
        for (auto const& [h, segs] : kh_targets) {
            int const pid = head_on(h)->pid;
            if (!contains(prey_ids, pid)) prey_ids.push_back(pid);
        }
        for (auto const& [h, segs] : kh_targets)
            for (int n : nbrs(h)) ts_inter.add(n);
    }
    // PORTAL TRAFFIC: a teammate head closer to a portal (ties: lower id) claims it, so we don't
    // queue up behind it and pop out into its tail on the unseen far side
    ts_claimed.clear();
    if (PORTAL_TRAFFIC_ENABLE && !portal_of_keys.empty()) {
        int const my_id = ct->get_id();
        std::vector<std::pair<int, int>> mates;
        for (auto const& h : heads)
            if (!h.enemy) mates.emplace_back(h.idx, h.pid);
        if (!mates.empty()) {
            for (int ek : portal_of_keys) {
                int const i = edge_tile(ek);
                int const t0 = i, t1 = ek < NT ? nb(i, DN) : nb(i, DW);
                int const dme = std::min(wdist(head, t0), wdist(head, t1));
                if (dme > PORTAL_CLAIM_DIST + 3) continue;
                for (auto const& [mh, mid] : mates) {
                    int const dm = std::min(wdist(mh, t0), wdist(mh, t1));
                    if (dm <= PORTAL_CLAIM_DIST && (dm < dme || (dm == dme && mid < my_id))) {
                        ts_claimed.add(ek);
                        break;
                    }
                }
            }
        }
    }
    ts_nopull.clear();
    if (PORTAL_TRAFFIC_ENABLE) {
        for (int ek : ts_claimed.items) ts_nopull.add(ek);
        for (int ek : portal_taken_keys)
            if (rnd - portal_taken[ek] <= PORTAL_TAKEN_TTL) ts_nopull.add(ek);
    }
    // CASH2 SUMMONS: from CASH_BEACON_ROUND head for the nearest beaconing king longer than us
    int csum_idx = -1, csum_d = 0;
    if (CASH2_ENABLE && CASH_ENABLE && rnd >= CASH_BEACON_ROUND && !king_beacons.empty() && kh_targets.empty()) {
        for (auto const& [b_idx, b] : king_beacons.items) {
            if (b.len > length) {
                int const d_val = wdist(head, b_idx);
                if (csum_idx < 0 || d_val < csum_d) {
                    csum_idx = b_idx;
                    csum_d = d_val;
                }
            }
        }
    }
    ts_sumzone.clear();
    if (csum_idx >= 0) {
        for (int n : nbrs(csum_idx)) ts_sumzone.add(n);
        ts_sumzone.add(csum_idx);
    }
    SearchOut const so = search(head, vacate, &ts_inter, &ts_nopull, &ts_sumzone);
    // FARM: fast spawn tiles near our head
    std::vector<int> fast_now;
    for (int f : spawn_tiles)
        if (is_fast(f) && wdist(head, f) <= FARM_R + 1) fast_now.push_back(f);
    std::array<double, 4> pearl_val = so.best;
    auto const& unknown = so.unknown;
    auto const& hunt_dist = so.tdist;
    auto const& sum_dist = so.t2dist;
    int const sum_min = csum_idx >= 0 ? *std::min_element(sum_dist.begin(), sum_dist.end()) : (1 << 20);

    bool const king = is_king(length, rnd);
    std::unordered_map<int, int> danger;
    if ((DODGE_ENABLE || TACT_EXITS) && !heads.empty()) danger = dodge_danger(head, TACT_EXITS ? 2 : 1);
    bool const cking = CASH2_ENABLE && is_cash_king(length, rnd);
    std::vector<int> ehs;
    if (KP_ENABLE || NEAR2_ENABLE)
        for (auto const& h : heads)
            if (h.enemy) ehs.push_back(h.idx);
    std::array<int, 4> edist{99, 99, 99, 99};
    if (!ehs.empty()) {
        for (int d = 0; d < 4; d++) {
            int const j = step(head, d);
            if (j >= 0) {
                int m = wdist(j, ehs[0]);
                for (int h : ehs) m = std::min(m, wdist(j, h));
                edist[d] = m;
            }
        }
    }
    if (protect && LONG_PEARL_MULT != 1.0) {
        for (int d = 0; d < 4; d++)
            if (!KP_ENABLE || edist[d] > 3) pearl_val[d] = pearl_val[d] * LONG_PEARL_MULT;
    }
    if (king)
        for (int d = 0; d < 4; d++)
            if (edist[d] <= 3) pearl_val[d] = std::min(pearl_val[d], KP_PEARL_CAP);
    auto const ctgt = cash_target(length, rnd);
    std::vector<Trap> traps;
    if (TRAP_ENABLE && !king && !heads.empty()) traps = trap_setup(head, vacate);

    ts_cut.clear();
    ahead_tiles(false, ts_cut);
    ts_pess.clear();
    for (int t : ts_cut.items) ts_pess.add(t);
    ts_enemy_ahead.clear();
    ahead_tiles(true, ts_enemy_ahead);
    for (int t : ts_enemy_ahead.items) ts_pess.add(t);
    around_heads(ts_pess);
    std::vector<int> const& pessimistic = ts_pess.items;

    // Early-Game Fan Out OR Hub Crowd Control
    double dynamic_team_pen;
    if (rnd < FANOUT_ROUNDS) {
        dynamic_team_pen = TEAM_NEAR_PEN * FANOUT_TEAM_MULT;
    } else {
        // If 3 or more teammates are loitering in the same area, aggressively push them apart
        // This prevents collateral crashes while camping hubs
        dynamic_team_pen = TEAM_NEAR_PEN * (static_cast<int>(mates_near.size()) >= CROWD_MATES ? CROWD_TEAM_MULT : 1.0);
    }

    // THE RELATIVE SUMMONS: Scouts yield to massive dragons; Kings yield to bigger Kings.
    int active_summon = -1;
    int summon_dist = 9999;
    if (CASH_ENABLE && rnd >= CASH_ROUND && !king_beacons.empty() && !CASH2_ENABLE) {
        for (auto const& [b_idx, b] : king_beacons.items) {
            // 1. If I am a King, I yield to any King strictly larger than me
            // 2. If I am a scout, I only suicide if they are at least double my size
            if ((king && b.len > length) || (!king && b.len >= 2 * length)) {
                int const d_val = wdist(head, b_idx);
                if (d_val < summon_dist) {
                    summon_dist = d_val;
                    active_summon = b_idx;
                }
            }
        }
    }

    // POCKET PORTALS: are we inside a small walled cell (portals count as walls)?
    bool const head_in_cell = (POCKET_PORTAL_PEN > 0 || POCKET_EXIT_FREE) && pocket_size(head, POCKET_CELL_SIZE) < POCKET_CELL_SIZE;

    int best_d = -1;
    double best_s = -1e18;
    for (int d = 0; d < 4; d++) {
        int const j = step(head, d);
        if (j == -1) continue;
        double s;
        if (j == -2) {
            // Extreme Curiosity: A blind portal must explicitly outscore an adjacent pearl
            if (rnd < SCOUT_ROUNDS) {
                s = (PEARL_W * PORTAL_SCOUT_MULT) + rng.random();
            } else {
                double curiosity_factor;
                if (PORTAL_LEN_FEAR) {
                    // PORTAL LENGTH FEAR: the longer we are, the more an unseen far side (a dead-end pocket,
                    // an enemy head) costs us, so fear ramps with length: none up to PORTAL_FEAR_MIN_LEN,
                    // full from PORTAL_FEAR_FULL_LEN
                    curiosity_factor = std::min(std::max(length - PORTAL_FEAR_MIN_LEN, 0) /
                                                    static_cast<double>(PORTAL_FEAR_FULL_LEN - PORTAL_FEAR_MIN_LEN),
                                                1.0);
                } else {
                    // Gradual Paranoia: Ramp up the penalty steadily from round 100 to 250
                    int ramp = rnd - SCOUT_ROUNDS;
                    if (PORTAL_AGE_RAMP) {
                        // Portal knowledge is per dragon: one born mid-game has seen no far sides yet,
                        // so ramp on its own age, not the game clock, or it fears every team portal
                        ramp = std::min(ramp, rnd - birth_round);
                    }
                    curiosity_factor = std::min(std::max(ramp, 0) / PORTAL_PARANOIA_RAMP, 1.0);
                }
                s = -(PORTAL_UNKNOWN_PEN * curiosity_factor * pmult) + rng.random();
            }
            if (endgame) s -= ENDGAME_PORTAL_PEN * pmult;
            // POCKET_EXIT_FREE: from inside a cell the portal may be the only way out, so no traffic penalty
            if (!(POCKET_EXIT_FREE && head_in_cell)) s -= portal_traffic_pen(head, d, ts_claimed, rnd);
        } else {
            // Mandatory survival check MUST happen before hunting
            if (!passable(j, 1, vacate)) continue;
            // FARM: j is next to a fast spawn tile we know
            bool farm_zone = false;
            for (int f : fast_now)
                if (wdist(j, f) <= FARM_R) {
                    farm_zone = true;
                    break;
                }

            if (ts_prey.has(j)) s = HUNT_KILL_W + rng.random();
            else s = pearl_val[d];

            // GLOBAL COMPASS: Pull small scouts toward the raycast beacon
            if (active_summon >= 0)
                if (wdist(j, active_summon) < summon_dist) s += CASH_W;

            // CASH2 COMPASS: follow the search's real path to the king if it reached him, else straight line
            if (csum_idx >= 0) {
                if (sum_min < (1 << 20)) {
                    if (sum_dist[d] < (1 << 20)) s += CASH_W / (1.0 + sum_dist[d] - sum_min);
                } else if (wdist(j, csum_idx) < csum_d) {
                    s += CASH_W;
                }
            }

            // Portal Traversal Logic
            if (j != nb(head, d)) {
                if (!(POCKET_EXIT_FREE && head_in_cell)) s -= portal_traffic_pen(head, d, ts_claimed, rnd);
                // POCKET_PORTAL_PEN: a known portal into a small walled cell (e.g. default's middle maze) costs
                // extra, so dragons farm the open corridors instead of piling into the cells
                if (POCKET_PORTAL_PEN > 0 && pocket_size(j, POCKET_CELL_SIZE) < POCKET_CELL_SIZE) s -= POCKET_PORTAL_PEN;
                // Known portals (both ends seen) cost KNOWN_PORTAL_PEN, less than the old PORTAL_PEN
                double raw_pen = KNOWN_PORTAL_PEN * pmult;
                if (endgame) raw_pen += ENDGAME_PORTAL_PEN * pmult;
                // ELASTIC ESCAPE HATCH: The richer the destination, the lower the penalty.
                double const dest_val = pearl_val[d] + (EXPLORE_W * unknown[d] / SEARCH_NODES);
                double const elastic_pen = std::max(0.0, raw_pen - (dest_val * 0.5));
                s -= elastic_pen;
            }

            s -= corridor_pen(j, head, vacate);
            if (!prey_ids.empty() && hunt_dist[d] < (1 << 20)) s += HUNT_W / (1.0 + hunt_dist[d]);
            if (!kh_targets.empty() && hunt_dist[d] < (1 << 20)) s += KING_HUNT_W / (1.0 + hunt_dist[d]);
            int const r = room(j, pessimistic, vacate, need);
            // CASH2: kings move to open ground before cash-in, so scouts can reach them and the drops can be eaten
            if (cking && rnd >= KING_OPEN_ROUND)
                s += KING_OPEN_W * room(j, pessimistic, vacate, KING_OPEN_CAP) / KING_OPEN_CAP;

            // DE_PROFIT: a small dragon may enter a dead end (room below need) that holds at least DE_PROFIT_MIN pearls
            // (in view or remembered, plus spawns due by the time its head gets there): it eats them and at the end
            // the emergency split sends the tail back out, losing the 2-long head (net DE_PROFIT_MIN - 2 or better)
            bool de_ok = false;
            if (r < need && length <= DE_PROFIT_MAX_LEN && !king && !cking) {
                int P = 0;
                for (std::size_t q = 0; q + 1 < bfs_q.size(); q += 2) {
                    int const t = bfs_q[q], dep = bfs_q[q + 1];
                    if (pearls[t] != NONE_R) P++;
                    else if (ptime[t] >= 0 && seen_round[t] >= 0) {
                        int const pred = ptime[t] - (rnd - seen_round[t]);
                        if (0 <= pred && pred <= dep) P++;
                    }
                }
                de_ok = P >= DE_PROFIT_MIN && length + P >= 4;
            }
            if (r < need && !de_ok) {
                s -= (need - r) * TRAP_PEN;
                if (r < length + 2) s -= LETHAL_PEN;
            }

            // HUB CONTEST: body hits only kill the attacker, so wall enemy heads in instead of ramming
            for (auto const& tr : traps) {
                if (wdist(j, tr.eh) > TRAP_RADIUS - 1) continue;
                int const er = room(tr.eh, {j, head}, tr.ev, tr.eneed);
                if (er < tr.en && tr.en <= tr.er0) s += TRAP_KILL_W;
                else if (er < tr.er0) s += SQUEEZE_W * (tr.er0 - er);
            }

            if (DEADEND_PEN > 0 && dead_end(j, head)) s -= DEADEND_PEN;

            // Emergency Desperation Bypass: If we are stepping into certain death (r < length + 2),
            // we refund the portal penalties because jumping blindly is better than suffocating.
            if (r < length + 2 && j != nb(head, d)) s += PORTAL_PEN + ENDGAME_PORTAL_PEN;

            for (auto const& h : head_threats(j)) {
                if (h.enemy && contains(prey_ids, h.pid)) s += HUNT_ADJ_W;
                else s -= head_risk;
            }
            // SPRINT DODGE: stay out of an enemy's sprint reach when that head-on would be a bad trade
            if (DODGE_ENABLE && !danger.empty()) {
                auto it = danger.find(j);
                if (it != danger.end() && (length > it->second || king)) s -= DODGE_PEN * (king ? 2.0 : 1.0);
            }
            // TACTICAL LOOKAHEAD: count next-turn continuations from j (free two moves from now and not reachable by
            // a shorter enemy's sprint); with none left we can be cornered, with one it is risky
            if (TACT_EXITS && !danger.empty()) {
                int exits = 0;
                for (int d2 = 0; d2 < 4; d2++) {
                    int const k = step(j, d2);
                    if (k < 0 || !passable(k, 2, vacate)) continue;
                    auto it = danger.find(k);
                    if (it != danger.end() && (length > it->second || king)) continue;
                    exits++;
                }
                double const km = king ? 2.0 : 1.0;
                if (exits == 0) s -= TACT_CORNER_PEN * km;
                else if (exits == 1) s -= TACT_ONE_EXIT_PEN * km;
            }

            if (ts_cut.has(j)) s -= TEAM_CUT_PEN;
            if (!mates_near.empty()) s -= dynamic_team_pen * mates_within2(j);
            s += (fast_now.empty() ? 1.0 : FARM_EXPLORE_MULT) * EXPLORE_W * unknown[d] / SEARCH_NODES;
            // FARM: no revisit penalty next to a fast spawn tile, so a dragon can circle a fountain
            if (!farm_zone) s -= (j == nb(head, d) ? VISIT_PEN : VISIT_PEN * PORTAL_EXIT_VISIT_MULT) * visits[j];
            if (d == facing) s += STRAIGHT_BONUS;
            if (!ehs.empty()) {
                int const ed = edist[d];
                if (king) {
                    if (ed <= 1) s -= LETHAL_PEN;
                    else if (ed <= 3) s -= KP_NEAR_PEN * (4 - ed);
                    double sum = 0.0;
                    for (int h : ehs) sum += 1.0 / std::max(1, wdist(j, h));
                    s -= KP_FAR_W * sum;
                } else if (NEAR2_ENABLE && length >= 5 && ed == 2) {
                    s -= NEAR2_PEN * length;
                }
            }
            if (FF_ENABLE)
                for (auto const& h : head_threats(j))
                    if (!h.enemy) s -= FF_PEN;
            if (ctgt.first >= 0) {
                int const kh = ctgt.first, kd = ctgt.second;
                if (j == step(kh, kd) || wdist(j, kh) <= 1) s -= LETHAL_PEN;
                else s += CASH_W / (1.0 + wdist(j, kh));
            }
            s += rng.random() * NOISE_W;
        }

        if (s > best_s) {
            best_s = s;
            best_d = d;
        }
    }
    return best_d;
}

static int unit_cap() {
    int const cap = UNIT_AREA <= 0 ? MAX_UNITS : std::min(MAX_UNITS, std::max(UNIT_MIN, (WID * HEI) / UNIT_AREA));
    // UNIT RESERVE: keep slots under the game's unit limit free for emergency splits
    return std::min(cap, game->get_unit_limit() - UNIT_RESERVE);
}

// CHILD ROOM: a split child's head is our tail tip, facing back along our path. True if it has a free tile there with
// CHILD_ROOM_NEED room (false when a teammate follows us down a corridor or a dead end is behind: the child would die)
static bool child_can_escape() {
    int const L = ct->get_length();
    std::vector<int> const body = my_body(L);
    if (static_cast<int>(body.size()) < L || body.size() < 2) return true;
    std::vector<int> const vacate = build_blockers();
    int const tip = body[0], neck = body[1];
    for (int d = 0; d < 4; d++) {
        int const t = step(tip, d);
        if (t < 0 || t == neck || !passable(t, 1, vacate)) continue;
        if (room(t, {tip}, vacate, CHILD_ROOM_NEED) >= CHILD_ROOM_NEED) return true;
    }
    return false;
}

// KING HANDOVER: last round this dragon beaconed as king
static int last_king_beacon = -1000;

static bool maybe_split() {
    int const length = ct->get_length();
    int const units = ct->get_unit_count();
    int const rnd = rnd_now();

    // Long dragons are exempt: blocking their splits in a corridor turns them into permanent gates that
    // box themselves in (doomed-head split every other round) and block our own routes
    // S_BIRTH_POCKET_ONLY: only inside a small walled-off area (portals count as walls), such as a maze cell;
    // corridors and fountain strips that open onto the map are left alone
    if (S_BIRTH_ENABLE && length <= S_BIRTH_MAX_LEN &&
        (!S_BIRTH_POCKET_ONLY || pocket_size(traj.back(), S_BIRTH_POCKET_SIZE) < S_BIRTH_POCKET_SIZE)) {
        // SPATIAL BIRTH CONTROL: Check if we are inside a tiny dead-end or island
        std::vector<int> const vacate = build_blockers();
        // If the local room has fewer than 20 open tiles, abort reproduction
        if (room(traj.back(), {}, vacate, 20) < 20) return false;
    }
    if (CHILD_ROOM && !child_can_escape()) return false;

    // 1. Dynamic Hard Cap (from Version 2)
    if (units >= unit_cap()) return false;

    // 2. Strategy Flags
    bool const is_endgame = rnd >= ENDGAME_ROUND;
    bool const am_king = is_anchor() || is_king(length, rnd);

    // POPULATION RESCUE: long dragons (every king and, from LONG_ROUND, the anchors) never split
    // below, so after heavy losses the survivors can be picked off to elimination. When the swarm
    // falls below RESCUE_FRAC of the unit cap, let them rebuild it (not while cashing in, unless
    // we are nearly wiped out). Early on the swarm is small anyway and splits normally.
    if (RESCUE_ENABLE && is_long(length, rnd) && units < RESCUE_FRAC * unit_cap()) {
        bool const cashing = CASH_ENABLE && rnd >= CASH_ROUND && units > RESCUE_CASH_UNITS;
        if (!cashing && rnd - last_rescue >= RESCUE_EVERY && ct->can_split(RESCUE_CHILD)) {
            ct->do_split(RESCUE_CHILD);
            splits_done++;
            last_rescue = rnd;
            return true;
        }
    }

    // Optional safety from Version 2
    if (is_long(length, rnd)) return false;

    // 3. King / Anchor Economy
    if (am_king) {
        // Emergency Floor Check (from Version 1): Kings MUST split if the swarm is dying.
        bool const emergency = units < MIN_SWARM_UNITS;
        // Standard Anchor conditions (from Version 2)
        bool const can_anchor_split = splits_done < ANCHOR_SPLITS && rnd <= ANCHOR_SPLIT_UNTIL && !is_endgame;
        if (!emergency && !can_anchor_split) return false;
        if (length < ANCHOR_SPLIT_AT || !ct->can_split(ANCHOR_CHILD)) return false;
        ct->do_split(ANCHOR_CHILD);
        splits_done++;
        return true;
    }

    // 4. Standard Swarm Economy
    if (rnd > SPLIT_UNTIL || is_endgame) {
        // Standard units stop splitting late game, UNLESS the swarm floor drops
        if (units >= MIN_SWARM_UNITS) return false;
    }
    if (length < SPLIT_AT || !ct->can_split(CHILD_SIZE)) return false;
    ct->do_split(CHILD_SIZE);
    splits_done++;
    return true;
}

// DOOM NO RAM: with no safe move, ram an adjacent enemy head (both die), else an unknown portal, else die alone
// (wall / body) or return -1 (no action = suicide) rather than step into a teammate's head, which kills both
static int doomed_move() {
    int const head = traj.back();
    auto const my_team = ct->get_team();
    int nbr[4], kind[4] = {0, 0, 0, 0};  // kind 1 = enemy head, 2 = teammate head
    for (int d = 0; d < 4; d++) nbr[d] = step(head, d);
    for (auto const& t : ct->get_tiles()) {
        auto const* part = t.get_dragon();
        if (part == nullptr || !part->is_head() || part->get_id() == ct->get_id()) continue;
        auto const p = t.get_position();
        int const i = p.y * WID + p.x;
        for (int d = 0; d < 4; d++)
            if (nbr[d] == i) kind[d] = part->get_team() == my_team ? 2 : 1;
    }
    for (int d = 0; d < 4; d++)
        if (kind[d] == 1) return d;
    for (int d = 0; d < 4; d++)
        if (nbr[d] == -2) return d;
    int const f = dir_of(ct->get_dir());
    if (kind[f] != 2) return f;
    for (int d = 0; d < 4; d++)
        if (kind[d] != 2 && d != (f + 2) % 4) return d;
    return -1;
}

static int any_safe() {
    int const head = traj.back();
    std::vector<int> const vacate = build_blockers();
    for (int d = 0; d < 4; d++)
        if (passable(step(head, d), 1, vacate)) return d;
    if (DOOM_NO_RAM) return doomed_move();
    for (int d = 0; d < 4; d++)
        if (step(head, d) == -2) return d;
    return dir_of(ct->get_dir());
}

// ==========================================
// SONAR
// ==========================================
// Reads, decrypts broadcasts and injects them directly into memory arrays.
static void process_sonar() {
    int const rnd = rnd_now();
    for (uint64_t msg : ct->get_sonar_messages()) {
        uint64_t const decrypted = msg ^ SECRET_KEY;
        if ((decrypted & 0xFF) != SONAR_SIG) continue;
        int const x = static_cast<int>((decrypted >> 24) & 0xFF);
        int const y = static_cast<int>((decrypted >> 16) & 0xFF);
        int const msg_type = static_cast<int>((decrypted >> 8) & 0xFF);
        int const sender_len = static_cast<int>((decrypted >> 32) & 0xFFFF);  // Unpack the length
        int const timer = static_cast<int>((decrypted >> 48) & 0xFFFF);       // Unpack the exact spawn timer
        if (x >= WID || y >= HEI) continue;
        int const idx = y * WID + x;

        if (msg_type == MSG_PEARL) {
            pearls[idx] = rnd;
            seen_round[idx] = rnd;
        } else if (msg_type == MSG_THREAT) {
            others[idx] = rnd + THREAT_TTL;
        } else if (msg_type == MSG_KING || (CASH2_ENABLE && msg_type == MSG_KING_RELAY)) {
            // Store both the round and the sender's length for the compass
            king_beacons.set(idx, {rnd, sender_len});
            // Map the true length to the Dragon ID to pierce the fog of war
            king_lengths.set(timer, {rnd, sender_len});
            // CASH2: a ray only reaches the first dragon on its line, so pass a beacon on once
            if (CASH2_ENABLE && msg_type == MSG_KING && timer != ct->get_id()) {
                std::pair<int, int> const key{timer, rnd / 4};
                if (!king_relayed.count(key)) {
                    king_relayed.insert(key);
                    king_relays.push_back({x, y, sender_len, timer});
                }
            }
        } else if (msg_type == MSG_SPAWN) {
            seen_round[idx] = rnd;
            ptime[idx] = timer;
        }
    }

    // Clean up stale beacons (older than 10 rounds)
    auto prune = [rnd](OrderedMap<Beacon>& m) {
        std::vector<std::pair<int, Beacon>> keep;
        for (auto const& kv : m.items)
            if (rnd - kv.second.rnd <= 10) keep.push_back(kv);
        m.items.swap(keep);
    };
    prune(king_beacons);
    if (king_relayed.size() > 256) king_relayed.clear();
    // Clean up stale ID lengths
    prune(king_lengths);
}

// Packs coordinates, message type, length, and spawn timer into a 64-bit integer.
static void send_encrypted_sonar(int target_x, int target_y, int msg_type, int length = 0, int timer = 0,
                                 int priority = SONAR_BEACON) {
    uint64_t const message = (static_cast<uint64_t>(timer) << 48) | (static_cast<uint64_t>(length) << 32) |
                             (static_cast<uint64_t>(target_x) << 24) | (static_cast<uint64_t>(target_y) << 16) |
                             (static_cast<uint64_t>(msg_type) << 8) | SONAR_SIG;
    uint64_t const encrypted = message ^ SECRET_KEY;
    for (int d = 0; d < 4; d++) {
        if (!sonar_has[d] || priority > sonar_pri[d]) {
            sonar_has[d] = true;
            sonar_pri[d] = priority;
            sonar_msg[d] = encrypted;
        }
    }
}

static void flush_sonar() {
    for (int d = 0; d < 4; d++)
        if (sonar_has[d]) ct->send_sonar(DIRS[d], sonar_msg[d]);
    for (int d = 0; d < 4; d++) sonar_has[d] = false;
}

// ==========================================
// UNIFIED EXECUTION SEQUENCE
// ==========================================
static void execute_turn() {
    if (birth_round < 0) {
        birth_round = rnd_now();
        if (SEED_ORDER_ENABLE) {
            // Forward, left, right, back of our starting heading: forward wins both forward
            // diagonals, so every dragon leans straight ahead, and the other side gets the
            // mirror image. A split child faces away from its parent, so flip it to inherit
            // the parent's heading.
            int f = dir_of(ct->get_dir());
            if (birth_round > 0 || ct->get_length() < 3) f = (f + 2) % 4;
            seed_order = {f, (f + 3) % 4, (f + 1) % 4, (f + 2) % 4};
        }
    }
    auto const p = ct->get_position();
    int const head = p.y * WID + p.x;
    if (traj.empty() || traj.back() != head) {
        traj.push_back(head);
        visits[head] += 1;
    }

    observe();
    self_trace();
    process_sonar();
    if (ROLE_INDICATOR) {
        // ROLE LAYER: the role this dragon is playing, shown in the replay viewer
        int const L = ct->get_length();
        int const r = rnd_now();
        char const* role = is_cash_king(L, r) ? "KING" : (is_anchor() || is_long(L, r)) ? "LONG" : "SCOUT";
        ct->set_indicator_string(std::string(role) + " " + std::to_string(L));
    }

    if (SPAWN_SONAR_ENABLE) {
        // SPAWN CLUSTER BROADCAST: Announce rich, renewable food hubs
        int const rnd = rnd_now();
        std::vector<int> visible_hubs;
        for (int idx = 0; idx < NT; idx++)
            if (seen_round[idx] == rnd && ptime[idx] >= 0) visible_hubs.push_back(idx);
        if (static_cast<int>(visible_hubs.size()) >= MIN_PEARL_CLUSTER && rng.random() < SONAR_PING_PROB) {
            int const center_idx = visible_hubs[0];
            long long total_time = 0;
            for (int i : visible_hubs)
                if (pearls[i] != rnd) total_time += ptime[i];
            int const avg_timer = static_cast<int>(total_time / static_cast<long long>(visible_hubs.size()));
            send_encrypted_sonar(center_idx % WID, center_idx / WID, MSG_SPAWN, 0, avg_timer);
        }
    }

    if (CASH2_ENABLE && CASH_ENABLE) {
        int const rnd_ = rnd_now();
        if (!king_relays.empty()) {
            auto const& r = king_relays[0];
            send_encrypted_sonar(r.x, r.y, MSG_KING_RELAY, r.len, r.id, SONAR_RELAY);
        }
        king_relays.clear();
        int const my_len = ct->get_length();
        if (rnd_ >= CASH_BEACON_ROUND && is_cash_king(my_len, rnd_) && rng.random() < KING_PING_PROB) {
            send_encrypted_sonar(p.x, p.y, MSG_KING, my_len, ct->get_id(), SONAR_KING);
            last_king_beacon = rnd_;
        }
    } else if (CASH_ENABLE && rnd_now() >= CASH_ROUND) {
        // THE ROYAL BROADCAST: Kings fire 4-way raycasts to summon scouts
        int const my_len = ct->get_length();
        if (is_king(my_len, rnd_now()) && rng.random() < SONAR_PING_PROB)
            send_encrypted_sonar(p.x, p.y, MSG_KING, my_len, ct->get_id());
    }

    if (sprint_attack()) return;
    if (maybe_split()) return;
    if (CASH_ENABLE) {
        int const rnd = rnd_now();
        int const my_len = ct->get_length();
        auto const ct_ = cash_target(my_len, rnd);
        if (ct_.first >= 0) {
            int const kh = ct_.first, kd = ct_.second;
            int const me = traj.back();
            int const dk = wdist(me, kh);
            if (2 <= dk && dk <= CASH_DIST && me != step(kh, kd) &&
                (!CASH2_ENABLE || (ct->get_unit_count() > CASH_RESERVE && king_can_reach(kh, my_body(my_len)))))
                return;  // no action -> engine suicide; pearls drop near the superior dragon
        }
    }

    int d = choose();

    // Restored Emergency Escape Split from main_6.py
    if (d < 0) {
        int const current_len = ct->get_length();
        int const escape_size = current_len - ESCAPE_KEEP;
        // Ensure we actually have enough length to perform this sacrifice
        if (escape_size >= 2 && (ANCHOR_EMERGENCY_SPLIT || !is_anchor()) &&
            !(LONG_NO_ESPLIT && is_long(current_len, rnd_now())) && ct->can_split(escape_size)) {
            ct->output_log("Head doomed! Transferring", escape_size, "length to escaping tail.");
            ct->do_split(escape_size);
            // KING HANDOVER: teammates keep our king beacon for up to 10 rounds; announce our new length so scouts stop
            // feeding the 2-long head (the tail, now the longest, takes over as king)
            if (KING_HANDOVER && rnd_now() - last_king_beacon <= 10)
                send_encrypted_sonar(p.x, p.y, MSG_KING, ESCAPE_KEEP, ct->get_id(), SONAR_KING);
            return;
        }
        d = any_safe();
        if (d < 0) return;  // DOOM_NO_RAM: die alone
    }
    ct->make_move(DIRS[d]);
}

int main() {
    auto [ct_ref, game_ref] = unswbc::init();
    ct = &ct_ref;
    game = &game_ref;
    setup();
    for (TileSet* t : {&ts_prey, &ts_inter, &ts_sumzone, &ts_cut, &ts_pess, &ts_enemy_ahead}) t->init(NT);
    ts_mybody.init(NT);
    ts_claimed.init(2 * NT);
    ts_nopull.init(2 * NT);
    rng.seed(static_cast<uint64_t>(ct->get_id()) * 7919 + 17);
    while (true) {
        try {
            if (!unswbc::update(*ct, *game)) break;
        } catch (std::exception const&) {
            break;
        }
        try {
            for (int d = 0; d < 4; d++) sonar_has[d] = false;
            execute_turn();
            flush_sonar();
        } catch (std::exception const& exc) {
            if (traj.empty()) {
                auto const p = ct->get_position();
                traj.push_back(p.y * WID + p.x);
            }
            ct->output_log("error:", exc.what());
            int const d = any_safe();
            if (d >= 0) ct->make_move(DIRS[d]);
        }
        unswbc::end_turn();
    }
    return 0;
}
