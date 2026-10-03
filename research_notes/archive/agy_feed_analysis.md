# Late-Game Feeding Analysis (`cand_sec/main.cpp`)

### 1. How Feeding Wastes Mass in `cand_sec`
- **Cascade multi-hop destruction (`tryFeed:1546`)**: On `bigFeed`, drones feed any ally with `estLen >= MY_LEN + 3`. Each illegal death drops ceil(L/2) pearls, destroying floor(L/2) (~50%) mass. Multi-hop chains (2 -> 5 -> 9 -> queen) destroy >75% of initial mass.
- **Dying out of sink's reach (`tryFeed:1549`)**: Triggers at `torusDist <= 3`. Pearls drop along feeder's body up to 5-6 tiles away, around kelp/corners, or behind the sink, allowing enemies to steal them or pearls to rot before the sink arrives.
- **Uncapped swarm dogpiling & traffic jams (`think:1707-1716`)**: Every drone within `feedRadius = 25` rushes `queen.cell` simultaneously. No throughput limit causes 30+ drones to box the queen in, block her exits, and overwrite pearl drop tiles.
- **En route slaughter (`evaluate:1102`)**: Homing bonus (`+4.0 * prog`) drives feeders across open map; enemies easily intercept and consume them.
- **Premature swarm collapse (`tryFeed:1540`)**: `UNITS <= 10` floor allows 62 -> 10 collapse by r380, wiping out pearl foraging income and map presence.

### 2. Comparison: `vb21` vs `s475`
- **Targeting**: `vb21` prioritizes `sinkId` (True Queen first, succession sink if dead) but still retains `bigFeed` cascade (`estLen >= MY_LEN + 3`). `s475` strictly targets the single gossiped grower/queen; zero cascade feeding.
- **Pacing & Throughput**: `s475` staggers feed start rounds by dragon ID (`id % feedWindow`), and caps traffic: if >2 allies are within Chebyshev distance 4 of the sink, outer feeders hold back and forage. `vb21` and `cand_sec` have no throughput cap.
- **Execution Distance**: `s475` requires `d <= 1` (`p_.feedDist`) right in the sink's path (suiciding into own neck). `cand_sec` and `vb21` trigger at `d <= 3`.
- **Unit Floor**: `vb21` uses a dual floor (8 units r330-399, 5 units r400+). `s475` caps feeder size (`feedMaxLen = 6`). `cand_sec` uses a flat `UNITS <= 10`.

### 3. Top 3 Concrete Improvements
1. **Eliminate Cascade & Enforce Direct Sink Proximity** (`cand_sec/main.cpp:1544-1550`):
   Restrict `worthy` strictly to the consensus queen (`dr.id == queen.id`). Tighten trigger from `torusDist <= 3` to `d <= 1` (adjacent) directly in front of the sink's facing direction.
2. **Stagger Homing & Add Throughput Cap** (`cand_sec/main.cpp:1707-1716`):
   Stagger homing activation (`ROUND >= P.feedFrom + (MY_ID % 30)`). If >2 allies are within distance 4 of `queen.cell`, suppress homing (`feeding = false`) so drones continue foraging pearls.
3. **Dynamic Unit Floor & Feeder Length Ceiling** (`cand_sec/main.cpp:1538-1542`):
   Scale floor by round (`UNITS <= 20` at r350, `UNITS <= 14` at r420, `UNITS <= 8` at r470). Restrict feeders to `MY_LEN <= 5` so large mid-size units maintain map control and secondary tiebreak length.
