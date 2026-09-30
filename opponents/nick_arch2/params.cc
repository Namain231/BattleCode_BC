// Port of mybot/params.py (same names and values), included by main.cpp. MAX_UNITS and MIN_SWARM_UNITS
// are not constexpr because setup() raises them on big maps, like the Python version rebinds them.
// This is a .cc (not a header) on purpose: unswbc's build cache only hashes .c/.cc/.cpp files, so editing a
// .hpp would not trigger a rebuild on local runs. As a .cc it is also compiled on its own, which is harmless
// (it only defines constants).

// Phase-Shifted Economy rules
constexpr int SPLIT_UNTIL = 250;
constexpr int SPLIT_AT = 4;
constexpr int CHILD_SIZE = 2;
inline int MAX_UNITS = 48;
constexpr int KING_LENGTH = 12;  // unused
inline int MIN_SWARM_UNITS = 24;
// POPULATION RESCUE: kings/long dragons split a RESCUE_CHILD every RESCUE_EVERY rounds while units are
// below RESCUE_FRAC of the unit cap (off during cash-in unless units <= RESCUE_CASH_UNITS)
constexpr int RESCUE_ENABLE = 1;
constexpr double RESCUE_FRAC = 0.25;
constexpr int RESCUE_EVERY = 5;
constexpr int RESCUE_CHILD = 2;
constexpr int RESCUE_CASH_UNITS = 2;
// Maps with area over BIG_MAP_AREA use these instead (e.g. schooltime, big_empty)
constexpr int BIG_MAP_AREA = 1000;
constexpr int BIG_MAX_UNITS = 64;
constexpr int BIG_MIN_SWARM_UNITS = 64;
// UNIT RESERVE: normal splitting stops this many dragons below the game's unit limit, so a boxed-in dragon can
// always make the emergency split (the engine refuses any split at the limit and the whole dragon dies: 119 long
// dragons died that way in 60 online games). 2 won 34/59 vs 0 on the big maps.
constexpr int UNIT_RESERVE = 2;
// Big maps start the whole cash-in schedule this many rounds earlier (CASH_ROUND, CASH_BEACON_ROUND,
// KING_ELECT_ROUND, KING_OPEN_ROUND); small maps keep it, since early drops there get grabbed by the enemy.
// 40 (cash-in from 380) won 35/60 vs 0 on the big maps; the dev team's kings start feeding around round 380.
constexpr int BIG_CASH_SHIFT = 40;

// Sonar
constexpr int MIN_PEARL_CLUSTER = 3;
constexpr double SONAR_PING_PROB = 0.5;
constexpr int SPAWN_SONAR_ENABLE = 0;

// Movement & Heuristic Weights
constexpr double PEARL_W = 84.0;
constexpr double MEMORY_PEARL_W = 21.0;
constexpr double SPAWN_W = 25.0;
constexpr int SPAWN_HORIZON = 60;
constexpr int SEARCH_NODES = 250;
constexpr int SPACE_MARGIN = 10;
constexpr int SPACE_CAP = 100;
constexpr int SPACE_LEN_MULT = 2;
constexpr double TRAP_PEN = 6.0;

constexpr int SCOUT_ROUNDS = 50;
constexpr double PORTAL_PEN = 8.0;
constexpr double PORTAL_STALE_PEN = 15.0;  // unused
constexpr int PORTAL_STALE_GRACE = 2;      // unused
constexpr double PORTAL_STALE_RATE = 0.8;  // unused
constexpr double PORTAL_SCOUT_MULT = 0.7;
constexpr double PORTAL_PARANOIA_RAMP = 250.0 - SCOUT_ROUNDS;
constexpr double PORTAL_UNKNOWN_PEN = 20.0;
// Portals whose far end we know: cost this instead of PORTAL_PEN (set KNOWN_PORTAL_PEN = PORTAL_PEN for old),
// and the revisit penalty on a portal's exit tile is scaled by PORTAL_EXIT_VISIT_MULT (1.0 = old)
constexpr double KNOWN_PORTAL_PEN = 2.0;
constexpr double PORTAL_EXIT_VISIT_MULT = 0.0;
// PORTAL TRAFFIC: one of our dragons per portal edge. Taken = a teammate went through this edge (from
// either tile touching it) within PORTAL_TAKEN_TTL rounds; the partner edge (exit side) is separate.
// Busy = an enemy touched the portal within PORTAL_BUSY_TTL rounds (its tail may sit past the exit).
// Claimed = a teammate head within PORTAL_CLAIM_DIST is closer to the edge than us.
// 1 = unexplored-portal penalty ramps with the dragon's own age (newborns are not afraid); 0 = game round
constexpr int PORTAL_AGE_RAMP = 1;
// PORTAL LENGTH FEAR: 1 = the unexplored-portal penalty ramps with length instead of game time / age:
// none at length <= PORTAL_FEAR_MIN_LEN, full (PORTAL_UNKNOWN_PEN) from PORTAL_FEAR_FULL_LEN (0 = old ramp,
// which uses PORTAL_AGE_RAMP). 2 -> 5 won 97/175 vs the old ramp on the 11 portal maps; 3 -> 10 lost 38/88.
// 1 -> 5 (length-2 dragons fear a little too; replays: most portals-map wall deaths are length 2-3 dragons in
// portal pockets): 46/80 and 43/80 vs 2 -> 5, portals 7/8 and 8/8.
constexpr int PORTAL_LEN_FEAR = 1;
constexpr int PORTAL_FEAR_MIN_LEN = 1;
constexpr int PORTAL_FEAR_FULL_LEN = 5;
// POCKET PORTALS: a cell is a walled-off area (kelp and portals count as walls) under POCKET_CELL_SIZE tiles.
// A known portal into a cell costs POCKET_PORTAL_PEN extra (0 = off); POCKET_EXIT_FREE = 1 drops the
// portal-traffic penalties while we are inside a cell, so we can always leave. Replays: on default we spent 42-65%
// of turns in the middle maze vs the dev team's 15-22%. vs the previous bot on the 10 online maps: 44/80 and
// 43/80 on fresh seeds (default 5/8, 6/8); vs a portal-avoiding bot 49/80 vs 50/80 without it.
// Turned off 2026-09-28: did not do well online (was POCKET_PORTAL_PEN 30.0, POCKET_EXIT_FREE 1).
constexpr double POCKET_PORTAL_PEN = 0.0;
constexpr int POCKET_EXIT_FREE = 0;
constexpr int POCKET_CELL_SIZE = 40;
constexpr int PORTAL_TRAFFIC_ENABLE = 1;
constexpr int PORTAL_TAKEN_TTL = 60;
constexpr double PORTAL_TAKEN_PEN = 60.0;
constexpr int PORTAL_BUSY_TTL = 2;
constexpr double PORTAL_BUSY_PEN = 60.0;
constexpr int PORTAL_CLAIM_DIST = 3;
constexpr double PORTAL_CLAIM_PEN = 15.0;
// 1 = blind-wrap check only blocks real map-edge wraps, so search can see through known portals
constexpr int PORTAL_LOOKTHROUGH = 1;  // unused (not read by mybot/main.py either)

constexpr double HEAD_RISK = 28.0;
constexpr double TEAM_CUT_PEN = 150.0;
constexpr double TEAM_NEAR_PEN = 1.5;
constexpr int TEAM_NEAR_RADIUS = 2;
constexpr int FANOUT_ROUNDS = 20;
constexpr double FANOUT_TEAM_MULT = 5.0;
constexpr int CROWD_MATES = 3;
constexpr double CROWD_TEAM_MULT = 3.5;

constexpr double LETHAL_PEN = 100.0;
constexpr int LETHAL_SLACK = 2;  // unused
constexpr double VISIT_PEN = 2.8;
constexpr double EXPLORE_W = 12.6;
// 1 = search seeds first moves as forward, left, right, back of each dragon's starting heading
// (children: their parent's), so both sides get the same exploration tilt. 0 = fixed N,E,S,W.
constexpr int SEED_ORDER_ENABLE = 1;
constexpr double STRAIGHT_BONUS = 0.5;
constexpr double NOISE_W = 0.3;
constexpr int OTHER_TTL = 2;
constexpr int VACATE_MARGIN = 1;
constexpr int HUNT_ENABLE = 1;
constexpr int HUNT_MAX_LEN = 5;
constexpr int HUNT_MIN_UNITS = 3;
constexpr int HUNT_MIN_ENEMY_SEGS = 8;
constexpr double HUNT_WINDOW_FRAC = 0.3;
constexpr double HUNT_KILL_W = 1000.0;
constexpr double HUNT_W = 25.0;
constexpr double HUNT_ADJ_W = 8.0;
constexpr int HUNT_ENDGAME_LEN = 3;
constexpr int HUNT_GUARD_DIST = 4;
constexpr int SPRINT_ENABLE = 1;
constexpr int TRAP_ENABLE = 1;
constexpr int TRAP_RADIUS = 4;
constexpr int TRAP_MAX_HEADS = 1;
constexpr int TRAP_CAP = 20;
constexpr double TRAP_KILL_W = 60.0;
constexpr double SQUEEZE_W = 2.0;
constexpr double CORRIDOR_PEN = 8.0;
constexpr int CORRIDOR_MIN = 2;
constexpr int ENDGAME_ROUND = 400;
constexpr double ENDGAME_SPACE_MULT = 2.0;
constexpr double ENDGAME_PORTAL_PEN = 40.0;

constexpr int THREAT_LEN_MARGIN = 8;  // unused
constexpr int THREAT_TTL = 3;
constexpr int ESCAPE_KEEP = 2;
constexpr int ANCHOR_ENABLE = 1;
constexpr int ANCHOR_BORN_BY = 1;
constexpr int ANCHOR_SPLITS = 64;
constexpr int ANCHOR_SPLIT_UNTIL = 250;
constexpr int ANCHOR_SPLIT_AT = 4;
constexpr int ANCHOR_CHILD = 2;
constexpr double ANCHOR_SPACE_MULT = 1.5;
constexpr double ANCHOR_HEAD_MULT = 2.0;
constexpr double ANCHOR_PORTAL_MULT = 2.0;
constexpr int ANCHOR_HUNT = 0;
constexpr int ANCHOR_EMERGENCY_SPLIT = 1;
constexpr int LONG_ENABLE = 1;
constexpr int LONG_ROUND = 80;
constexpr int LONG_MIN_LEN = 5;
constexpr double LONG_PEARL_MULT = 2.5;
constexpr int LONG_SAFE_ROUND = 450;
constexpr double LONG_SAFE_HEAD_MULT = 2.0;
constexpr double LONG_SAFE_SPACE_MULT = 1.5;
constexpr int LONG_NO_ESPLIT = 0;
constexpr double DEADEND_PEN = 0;
constexpr int DEADEND_MAX = 30;
constexpr int UNIT_AREA = 0;
constexpr int UNIT_MIN = 6;

constexpr int KP_ENABLE = 1;
constexpr int KP_ROUND = 250;
constexpr int KP_MIN_LEN = 6;
constexpr double KP_NEAR_PEN = 40.0;
constexpr double KP_FAR_W = 20.0;
constexpr double KP_PEARL_CAP = 70.0;

constexpr int NEAR2_ENABLE = 1;
constexpr double NEAR2_PEN = 3.0;
constexpr int CASH_ENABLE = 1;
inline int CASH_ROUND = 420;
constexpr int CASH_MAXLEN = 5;  // unused
constexpr int CASH_KING_MIN = 6;
constexpr int CASH_DIST = 4;
constexpr double CASH_W = 80.0;
// CASH2: better cash-in (0 = old logic exactly). Kings beacon from CASH_BEACON_ROUND (relayed once,
// per-direction outbox), scouts follow the real path to them, a king is self-elected when none is heard,
// kings seek open ground, and scouts only cash in with a reserve left and where the king can reach the drops.
constexpr int CASH2_ENABLE = 1;
inline int CASH_BEACON_ROUND = 390;
constexpr double KING_PING_PROB = 0.5;
inline int KING_ELECT_ROUND = 400;
constexpr int KING_ELECT_SILENCE = 10;
// 6 (was 3): no self-elected kings under 6, so cash-in doesn't spread over dozens of tiny kings (a 6+ dragon is a
// king from KP_ROUND anyway, so any value of 6+ plays the same). Lab: 129/240 over three seed sets.
constexpr int KING_ELECT_MIN = 6;
inline int KING_OPEN_ROUND = 380;
constexpr double KING_OPEN_W = 20.0;
constexpr int KING_OPEN_CAP = 60;
constexpr int CASH_RESERVE = 3;
// KING HUNT: from CASH_BEACON_ROUND, scouts of length <= KING_HUNT_MAXLEN sprint into / chase any visible
// enemy dragon at least KING_HUNT_RATIO x their length (and >= KING_HUNT_MIN), before splitting or cashing in
constexpr int KING_HUNT_ENABLE = 1;
constexpr int KING_HUNT_MAXLEN = 5;
constexpr double KING_HUNT_RATIO = 2.0;
constexpr int KING_HUNT_MIN = 6;
constexpr double KING_HUNT_W = 40.0;
constexpr int FF_ENABLE = 0;
constexpr double FF_PEN = 80.0;

// SPATIAL BIRTH CONTROL: no splitting when fewer than 20 tiles are free around the head (dragons block, known
// portals count as open). vs our own bot 45/90; vs a portal-avoiding bot default 1/8 -> 4/8, queen 7/8 unchanged,
// autarky and slithery_fight 6/8 -> 3/8.
constexpr int S_BIRTH_ENABLE = 1;
// S_BIRTH only applies to dragons up to this length (999 = all, the first version). Blocking long dragons turned
// them into corridor gates stuck in a doomed-head split loop (249 per game on autarky/dilemma). vs a
// portal-avoiding bot: 999 -> 47/88, 4 -> 54/88 (autarky 3 -> 5/8, slithery_fight 3 -> 6/8); vs our own bot ~even.
constexpr int S_BIRTH_MAX_LEN = 4;
// 1 = S_BIRTH only applies inside a walled-off area (kelp and portals count as walls) under S_BIRTH_POCKET_SIZE tiles,
// e.g. default's maze cells; fountain strips and corridors that open onto the map are left alone. Without it S_BIRTH
// lost trauma 4/30 vs S_BIRTH off (it stalls splitting at the 1-wide fountain strips); with it 16/30.
constexpr int S_BIRTH_POCKET_ONLY = 1;
constexpr int S_BIRTH_POCKET_SIZE = 40;
// DOOM NO RAM: a dragon with no safe move (too short for the emergency split) rams an adjacent enemy head, else takes
// an unknown portal, else dies alone, instead of walking into a teammate's head (the old fallback kept going
// forward). Replays: 1,280 teammate head-ons in 110 games (devil 43/game, dev team 0; portals 41, trauma 8).
constexpr int DOOM_NO_RAM = 1;
// CHILD ROOM: no split unless the child (born at our tail tip, facing back along our path) has a free tile with
// CHILD_ROOM_NEED room; otherwise it is born facing a following teammate's head or a dead end and dies at once.
// DOOM_NO_RAM + CHILD_ROOM + PORTAL_FEAR_MIN_LEN 1 (lab, with pocket portals on): 47/80 vs the lab on fresh seeds;
// vs a portal-avoiding bot 60/80 where the bot without them scored 51/80.
constexpr int CHILD_ROOM = 1;
constexpr int CHILD_ROOM_NEED = 6;
// ===== ARCHITECTURE TEST VERSION (2026-09-29): role layer + tactical lookahead =====
// ROLE LAYER. CASH_NEWBORN_WAIT: dragons of CASH_NEWBORN_LEN+ born less than CASH_NEWBORN_WAIT rounds ago don't cash in
// (a king's emergency-split tail otherwise cashes in next to its 2-long parent, whose old king beacon says it is long).
// KING_HANDOVER: a dragon that beaconed as king in the last 10 rounds and emergency-splits beacons its new length at once.
// ROLE_INDICATOR: each dragon shows KING / LONG / SCOUT and its length in the replay viewer.
constexpr int CASH_NEWBORN_WAIT = 12;
constexpr int CASH_NEWBORN_LEN = 8;
constexpr int KING_HANDOVER = 1;
constexpr int ROLE_INDICATOR = 1;
// TACTICAL LOOKAHEAD. DODGE: -DODGE_PEN (x2 for a king) on tiles a visible enemy head can reach with one sprint
// (visible length - 1 steps, capped at DODGE_MAX_REACH) when we are longer than it. TACT_EXITS: -TACT_CORNER_PEN if no
// next-turn continuation from the move is free and out of a shorter enemy's sprint reach, -TACT_ONE_EXIT_PEN if one.
constexpr int DODGE_ENABLE = 1;
constexpr int DODGE_MAX_REACH = 5;
constexpr double DODGE_PEN = 30.0;
constexpr int TACT_EXITS = 0;
constexpr double TACT_CORNER_PEN = 40.0;
constexpr double TACT_ONE_EXIT_PEN = 10.0;
// ===== ARCH2 TEST VERSION (2026-09-29): mybot_cpp_arch + FARM + FARM_DE_LEN 3 + SELF_TRACE =====
// Lab (mybot_cpp_arch_lab, notes LAB_NOTES_ARCH.md): 49/80 vs mybot_cpp_arch on the 10 online maps (default 7/8, autarky
// 7/8, length decisions 37-17), but FARM + FARM_DE_LEN 3 lost 29/79 on pearl-timing variant maps and was 40/80 on fresh
// seeds. Built with scratchpad cpp/port_arch2.py (farm, farmde, selftrace); plays the same games as the lab set the same way.
// FARM (2026-09-29 arch lab): fast spawn tiles (countdown never seen above FARM_FAST_T after FARM_MIN_RESTARTS restarts) are
// worth FARM_W / (1 + dist + FARM_PRED_MULT x rounds to spawn) instead of SPAWN_W / (1 + max(rounds, dist)); tiles within
// FARM_R of one carry no revisit penalty and exploration counts FARM_EXPLORE_MULT while one is within FARM_R + 1
constexpr int FARM_FAST_T = 20;
constexpr double FARM_W = 60.0;
constexpr int FARM_R = 2;
constexpr double FARM_PRED_MULT = 0.25;
constexpr double FARM_EXPLORE_MULT = 0.3;
constexpr int FARM_MIN_RESTARTS = 1;
// FARM_DE_LEN: dragons up to this length skip the dead-end (room) penalty next to a fast tile, like the opponents' fountain
// loop (enter, eat, split at the end so the tail walks out, the stuck head eats the rest and dies)
constexpr int FARM_DE_LEN = 3;
// SELF_TRACE (2026-09-29 arch lab, always on): split children and round-0 dragons rebuild the unknown tail part of their own
// body from the visible segments (each faces the next one headward) instead of treating it as walls / free tiles
