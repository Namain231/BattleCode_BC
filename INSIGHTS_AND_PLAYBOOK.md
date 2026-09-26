# UNSW Battlecode: Comprehensive Strategic Playbook & Competitive Insights

> **Team**: Bhole Chature (`yashguy65`)  
> **Active Ladder Submission**: `v7.2-partial-feed` (Submission ID: `7741`, C++, source `viper_v7/`), updated 2026-09-27  
> **Current Champion**: V7.2 swarm, 60% vs V7.1 and 94% vs V3 locally; on the ladder ~50–60% vs mid-ladder swarms, 0/10 vs the top three  
> **Research Iterations**: V1 (Genesis) $\to$ V2 (Titan) $\to$ V3 (Predator) $\to$ V4 (Tron Prototype) $\to$ V5 (Apex) $\to$ V6 (Leviathan, C++) $\to$ V7 (Swarm)  
> **Start with `AGENTS.md`** for the workflow and tools; sections 10–12 below hold the V6/V7 findings. Sections 1–9 describe the Python era and are partly superseded.  
> **Judge Sandbox Verified**: 100,000,000 CPU points / turn, 48 MB memory, single-threaded WebAssembly

---

## 1. Executive Summary & Current State of the Art

This playbook is the single source of truth for our competitive AI engine in the **UNSW Battlecode** championship. It synthesizes full engine mechanics, judge sandbox constraints, algorithmic breakthroughs from **MIT Battlecode**, **Google AI Challenge (Tron)**, and **Battlesnake World Championships**, alongside empirical head-to-head tournament data across 13 official maps.

### Core Strategic Tenets
1. **Survival Over Pearl Greed**: A dragon must never enter an enclosed space smaller than its own body length ($N_{\text{flood}} < L$), unless a proven escape path to its retreating tail exists.
2. **Friendly Deconfliction (The Multi-Agent Fix)**: Eliminating friendly fratricide through decentralized pearl ownership and strict friendly-hazard exclusion zones ($-50,000$ penalty near teammate heads).
3. **Asymmetric Swarm Hierarchy (Queen & Drones)**: Maximizing the single longest dragon to secure **Tiebreak #1**, while using lightweight drones for peripheral pearl harvesting and sacrificial assassin strikes.
4. **The Kamikaze Assassin Principle (Mutually Assured Destruction)**: Because head-to-head collisions in UNSW Battlecode kill *both* dragons regardless of length, trading a 2-segment drone into an enemy 25-segment Queen guarantees an instant victory.
5. **Articulation Point (Cut-Vertex) Avoidance**: Stepping onto a tile that fragments the remaining connected open space will inevitably wall off access to open water and starve the dragon.
6. **Dual-Phase Playbook (Expansion vs Endgame Lockdown)**: Aggressive pearl harvesting and controlled splitting in rounds 0–200; total lockdown, split cessation, and conservative survival after round 350 to win length tiebreaks.

---

## 2. Deep Engine & Game Mechanics Reference

### 2.1 The Map & Topology
- **Dimensions**: Rectangular grids ($10 \le W, H \le 64$).
- **Toroidal Wrap**: Moving past the East border wraps to West ($x = 0$); moving past South wraps to North ($y = 0$). All distances must use toroidal delta:
  $$\Delta x = \min(|x_2 - x_1|, W - |x_2 - x_1|)$$
  $$\Delta y = \min(|y_2 - y_1|, H - |y_2 - y_1|)$$
- **Tiles vs Edges**:
  - Tiles contain dragons and pearls.
  - Edges contain **Kelp** (impassable walls; moving into kelp is instant death) and **Portals** (paired wormholes).
  - Portals are double-sided; traversing a portal emerges at the matching partner portal edge facing outward. Direct vision does **not** cross portals, but Sonar rays do.
- **Symmetry**: Maps are guaranteed symmetric (horizontal reflection, vertical reflection, or $180^\circ$ rotational symmetry).

### 2.2 Movement & Sprint Mechanics
- **Standard Move**: 1 step in cardinal direction (`N`, `E`, `S`, `W`).
- **Collision Order**: Death checks occur **before** the tail advances. Stepping into your own tail on a 1-step move is fatal if no pearl was eaten, because the tail has not yet moved when the head arrives.
- **Head-to-Head Collisions**: If two dragon heads move into the same tile, or if a dragon steps into an opposing dragon's head, **both dragons die immediately**, regardless of length or team.
- **Sprinting**: A dragon can execute multiple steps in a single turn (`MOVE NNE`).
  - Moving $k$ steps costs $k - 1$ tail segments.
  - If a dragon has length $< k$, attempting the sprint results in suicide (`No Valid Action`).
  - Sprinting evaluates collision step by step: step 2 can safely enter a tile vacated by step 1.

### 2.3 Splitting Dynamics
- A dragon can split itself into a new independent process using `SPLIT child_size`.
- **Preconditions**:
  - `child_size >= 2`
  - Remaining parent length $\ge 2$
  - Team currently has $< 64$ living dragons
- **Child Properties**:
  - Formed from the parent's rear segments in **reverse order** (the parent's old tail becomes the child's head, facing away from the parent).
  - Assigned the next sequential dragon ID.
  - **Takes its first turn later in the same round!**
  - Controlled by a completely fresh process instance with no shared memory.

### 2.4 Death & Crystallisation
- Upon death, every second segment starting from the head turns into a pearl:
  $$\text{Pearls Dropped} = \left\lceil \frac{L}{2} \right\rceil$$
- Death causes recorded by engine:
  - `Hit Wall`: Stepped into kelp edge.
  - `Hit Self`: Stepped into own body or unvacated tail.
  - `Hit Other Body`: Stepped into any segment of another dragon.
  - `Head to Head`: Collided with another dragon's head (mutual death).
  - `No Valid Action`: Malformed command, illegal split, insufficient length for sprint, unhandled crash, or timeout without action.

### 2.5 Scoring & Tiebreak Hierarchy
Games last up to **500 rounds**.
1. **Elimination**: If all dragons of one team die, the surviving team wins immediately.
2. **Round 500 Tiebreaks**:
   - **Tiebreak #1**: The team with the **Longest Living Dragon** ($L_{\max}$).
   - **Tiebreak #2**: The team with the **Greatest Total Length** across all living dragons ($\sum L$).
   - **Tiebreak #3**: Draw.

---

## 3. The Sandbox & Computation Budget

The contest judge runs bots in a strict WebAssembly sandbox:

| Metric | Judge Limit | Our Bot Profile | Safety Margin |
| :--- | :--- | :--- | :--- |
| **CPU Points / Turn** | 100,000,000 | Mean: 28.4M, Peak: 58.2M | **> 40M buffer** |
| **Memory Limit** | 48 MB | ~16–18 MB | **Safe (< 38%)** |
| **Execution Threads** | 1 (single-threaded) | 1 | Compliant |
| **Output Syscall Tax** | 2.5M points + 4,000/byte | Minimal indicator strings | Negligible |
| **Execution Watchdog** | `time.perf_counter()` | 0.1s $\approx$ 100M points | **Exact point watchdog** |

> [!CAUTION]
> Python `print()` writes to stdout, which incurs a heavy syscall tax (2,500,000 base points + 4,000 points per byte). In production matches, all verbose logging is disabled. Use `ct.set_indicator_string()` for lightweight turn indicators visible in replays.

---

## 4. Bot Evolutionary Lineage & Architecture Breakdown

### 4.1 Viper V1 (Genesis) — The Baseline
- **Architecture**: Simple BFS greedy pathfinding toward the nearest visible pearl.
- **Fatal Flaw**: Multi-agent congestion crisis. When two friendly dragons saw the same pearl, both converged on the exact same tile. The lower-ID dragon stepped in, and the higher-ID dragon stepped into the same tile later in the round, causing catastrophic friendly fratricide.

### 4.2 Viper V2 (Titan) — The Foundation Champion
- **Decentralized Pearl Deconfliction**:
  ```python
  claimed = False
  for f_id, f_pos in friendly_heads:
      f_dist = torus_manhattan_dist(f_pos, pos, width, height)
      if f_dist < my_dist or (f_dist == my_dist and f_id < my_id):
          claimed = True
          break
  if claimed:
      continue  # Yield to closer or lower-ID teammate
  ```
- **Friendly Hazard Buffer**: $-50,000$ penalty for any square adjacent to a friendly dragon's head, completely eradicating friendly head-on collisions.
- **Asymmetric Swarm Hierarchy**:
  - Queen (ID 0) prioritizes longevity and length maximization for Tiebreak #1.
  - Drones (IDs > 0) harvest peripheral pearls and harass opponents.
- **Adaptive Area Population Throttling**: Caps unit count based on map area (2 units on small arenas, 3 on medium, 4–5 on large).
- **Predictive Pearl Harvesting**: Intercepts pearls at $t = 0$ using `tile.get_pearl_time()`.
- **Performance**: 13/13 (100%) against Starter Bot; swept V1 in direct head-to-head.

### 4.3 Viper V3 (Predator) — Active Ladder Champion (Submission #7429)
- **The Kamikaze Assassin Missile**:
  - Exploit: Head-on collision destroys *both* dragons regardless of length.
  - Lightweight drones ($L \le 3$) receive an aggressive hunter vector ($+4,000$ bonus) to intercept enemy Queens.
  - Trading a 2-segment drone to kill an enemy 25-segment Queen produces an instant victory.
- **Accelerated Pearl Greed**: Boosted proximity gradient ($+550 / (dist + 1)$) to vacuum up pearls rapidly during open-water phases.
- **Sonar 64-bit Protocol**: Packs sender ID, role, coordinates, target pearl, and enemy sightings into 64-bit bitmasks emitted via `ct.send_sonar()`.
- **Portal Registry**: Discovers paired portal IDs and tracks wormhole teleportation coordinates.
- **Head-to-Head Performance**: **4–1 Victory over V2** (`arena` eliminated in round 76, `Colosseum` eliminated in round 168). Currently holding our active ladder ranking.

### 4.4 Viper V4 (Tron Prototype) — Experimental Findings & Regression Analysis
- **Goal**: Integrate wall-hugging compactness heuristics from the 2010 Google AI Challenge Tron winner, along with tail-vacancy simulation.
- **Observed Results**: V4 regressed against V3, losing 3 out of 5 matches.
- **Root Cause Postmortem**:
  1. *Toroidal Tail Distance Bug*: Calculating tail vacancy via Manhattan distance on a torus produced false positive loop detections in tight chambers.
  2. *Spike in "Hit Itself"*: Dragons believed their tail would vacate even when trapped in dead-ends, leading to self-collisions.
  3. *Lost Hazard Distinctions*: Collapsing the 3 hazard classes into 2 lost fine-grained drone vs queen risk profiling.

### 4.5 Viper V5 (Apex) — Graph Theory & Spatial Control Engine
- **Articulation Point (Cut-Vertex) Avoidance**:
  - From graph theory: an articulation point is a vertex whose removal increases the number of connected components.
  - Stepping onto an articulation point splits the board into isolated chambers, permanently cutting off the larger half of the map.
  - V5 implements `is_cutting_move()`: simulates the move, collects open neighbors, and runs a bounded BFS. If neighbors are disconnected without passing through the new position, a $-4,000$ penalty is applied.
- **Dual Flood Fill with Tail Tracking**:
  - Runs a fast simple BFS for open space, plus a tail-vacancy BFS that verifies if a continuous looping cycle back to the tail exists.
- **Corridor Avoidance Heuristic**:
  - Strictly penalizes 0-exit tiles ($-10,000$) and 1-exit blind corridors ($-2,500$), favoring multi-exit spaces ($+ open\_exits \times 80$).
- **Endgame Survival Shift**:
  - When `round_num > 380`, the Queen dampens pearl collection greed by 60% and increases enemy collision avoidance to $-30,000$, ensuring maximum survival probability for the Round 500 tiebreak.
- **SwarmMemory Persistent Tracking**:
  - Tracks teammate positions, claims targets, and records historical enemy sightings across turns.

---

## 5. Academic & Competitive Postmortem Inspirations

### 5.1 Google AI Challenge (Tron 2010) — Sam "a1k0n" Henderson Postmortem
- **Core Principle**: Tron is fundamentally a game of space-filling and graph connectivity. Simple wall-hugging is an approximation; true dominance comes from **Voronoi territory partitioning** and **cut-vertex detection**.
- **The Golden Rule**: Always maximize the size of the connected component available to you, while minimizing the opponent's accessible territory.
- **Articulation Points**: Entering a cut vertex allows the opponent to seal the entrance with a single move, locking you into a sub-component while they claim the rest of the board.

### 5.2 Battlesnake World Championships
- **Tail-Chasing Loop Invariant**: If a snake can reach its own tail and does not eat food on that turn, the tail space is guaranteed to open up on the next tick. Following the tail maintains an infinite non-colliding loop until the surrounding board clears.
- **Chamber Capacity**: Never enter a cavity where $N_{\text{empty}} < L_{\text{snake}}$ unless the tail-chase invariant holds.
- **Head-to-Head Asymmetry**: Unlike Battlesnake (where the longer snake eats the shorter snake), UNSW Battlecode is **strictly symmetric death**. This heavily favors the player who fields expendable low-length units against giant opposing units.

### 5.3 MIT Battlecode Championship Principles
- **Decentralized Coordination with Zero Shared State**: Because each dragon runs in an isolated process with no shared memory, communication must occur exclusively through board state observation and 64-bit sonar broadcasts.
- **Asymmetric Specialization**: In multi-agent games, homogeneous agents create self-interference. Dividing units into strict roles (Long-lived Queen vs Aggressive Drones) breaks symmetric deadlocks.

---

## 6. Empirical Benchmarks & Tournament Matrix

### 6.1 V2-Titan vs Starter Bot (13-Map Sweep)
```
[WIN] maps/Colosseum.map       : team A wins after 66 rounds (by elimination)
[WIN] maps/arena.map           : team A wins after 47 rounds (by elimination)
[WIN] maps/autarky.map         : team A wins after 255 rounds (by elimination)
[WIN] maps/big_empty.map       : team A wins after 143 rounds (by elimination)
[WIN] maps/default.map         : team A wins after 409 rounds (by elimination)
[WIN] maps/default_small.map   : team A wins after 82 rounds (by elimination)
[WIN] maps/devil.map           : team A wins after 121 rounds (by elimination)
[WIN] maps/dilemma.map         : team A wins after 203 rounds (by elimination)
[WIN] maps/queen_of_spades.map : team A wins after 345 rounds (by elimination)
[WIN] maps/schooltime.map      : team A wins after 208 rounds (by elimination)
[WIN] maps/stronghold.map      : team A wins after 143 rounds (by elimination)
[WIN] maps/trauma.map          : team A wins after 262 rounds (by elimination)
[WIN] maps/trophy.map          : team A wins after 184 rounds (by elimination)

Final Record: 13 / 13 WINS (100.0%)
```

### 6.2 V3-Predator vs V2-Titan (Head-to-Head Matrix)
```
[WIN-V3] maps/arena.map           : V3 wins after 76 rounds (elimination by assassin drone)
[WIN-V3] maps/Colosseum.map       : V3 wins after 168 rounds (elimination by assassin drone)
[WIN-V3] maps/default_small.map   : V3 wins after 312 rounds (elimination)
[LOSS]   maps/dilemma.map         : V2 wins after 500 rounds (on length tiebreak)
[WIN-V3] maps/trophy.map          : V3 wins after 240 rounds (elimination)

Final Record: 4 / 5 WINS (80.0%)
```

### 6.3 V5-Apex vs V3-Predator (Full 13-Map Tournament)
```
============================================================
  viper_v5 (A) vs viper_v3 (B) — Full 13-Map Tournament
============================================================
  [WIN-B] maps/arena.map           : viper_v3 wins after 233 rounds (by elimination)
  [WIN-B] maps/Colosseum.map       : viper_v3 wins after 287 rounds (by elimination)
  [WIN-B] maps/default.map         : viper_v3 wins after 500 rounds (on length)
  [WIN-A] maps/default_small.map   : viper_v5 wins after 253 rounds (by elimination)
  [WIN-B] maps/dilemma.map         : viper_v3 wins after 445 rounds (by elimination)
  [WIN-A] maps/trophy.map          : viper_v5 wins after 321 rounds (by elimination)
  [WIN-B] maps/big_empty.map       : viper_v3 wins after 500 rounds (on length)
  [WIN-B] maps/autarky.map         : viper_v3 wins after 500 rounds (on length)
  [WIN-A] maps/devil.map           : viper_v5 wins after 260 rounds (by elimination)
  [WIN-A] maps/schooltime.map      : viper_v5 wins after 500 rounds (on length)
  [WIN-B] maps/stronghold.map      : viper_v3 wins after 500 rounds (on length)
  [WIN-B] maps/trauma.map          : viper_v3 wins after 500 rounds (on length)
  [WIN-B] maps/queen_of_spades.map : viper_v3 wins after 500 rounds (on length)
============================================================
  viper_v5: 4–5 wins (31%–38%) | viper_v3: 8–9 wins (62%–69%)
============================================================
```

### 6.4 Key Empirical Discovery: The Large-Map Length Bottleneck
Analyzing the V5 vs V3 tournament logs reveals a critical strategic dynamic:
1. **On Tactical / Tight Maps** (`default_small`, `trophy`, `devil`, `schooltime`):
   - V5 consistently wins by elimination or length control. Its articulation point avoidance and corridor pruning keep its dragons alive while V3 gets trapped in tight kelp corridors.
2. **On Massive Open Maps** (`default`, `big_empty`, `autarky`, `stronghold`, `trauma`, `queen_of_spades`):
   - V5 loses **exclusively on Round 500 length tiebreaks**.
   - *Why?* V5's spatial caution (wall-hugging, cutting-move avoidance, chamber checks) causes dragons to take longer, more conservative routes to pearls. In contrast, V3 runs a high-greed direct vector, accumulating significantly more pearls.
   - *Splitting Dilution*: V5 maintains 4–5 living units on large maps, diluting its total length across multiple dragons, whereas V3 maintains 2–3 massive dragons with a dominant Queen that wins Tiebreak #1 ($L_{\max}$).

---

## 7. Current Thinking & Active Strategic Bottlenecks

### 7.1 The "Longest Dragon vs Swarm Volume" Paradox
- **Engine Rule**: Tiebreak #1 is the **Longest Single Dragon** ($L_{\max}$). Tiebreak #2 is **Total Team Length** ($\sum L$).
- Splitting a dragon of length 14 into length 11 and length 3 creates an extra worker, but permanently sets back the Queen's race toward 30+ length.
- If the game reaches Round 500 on a large map, an opponent who never split after reaching length 10 will hold a 28-length Queen and win Tiebreak #1, even if our team has 5 living dragons with a combined length of 50.
- **Strategic Fix**: On large maps, the Queen must stop splitting much earlier (round 120 instead of 200), and must never split if her length is $< 16$.

### 7.2 Pearl Greed vs Safety Pareto Frontier
- High pearl greed creates vulnerability to corridor traps on small maps.
- Low pearl greed loses Round 500 length tiebreaks on large maps.
- **Solution**: Dynamic Map-Scale Weighting. The pearl scoring multiplier must scale directly with map area:
  $$\text{Greed Multiplier} = 1.0 + \frac{\text{Area}}{1000}$$
  On large open maps, greed dominates; on small maze maps, survival dominates.

### 7.3 Total Internal Refraction Exploitation
- Engine rule: Sonar rays sent opposite to dragon heading exhibit Total Internal Refraction and emit from the **tail** facing backwards.
- This allows a dragon to emit simultaneous forward and rearward sonar rays in a single turn, providing $360^\circ$ radar coverage without changing heading.

---

## 8. Comprehensive Strategic TODO & Future Engineering Roadmap

### Phase 1: High-Priority Engine Tuning (V5.1 / V6 Architecture)
- [ ] **Dynamic Pearl Greed Scaling**:
  - Scale pearl attraction weights based on `game.width * game.height`. On maps with area $> 600$, increase pearl bonus from $+700$ to $+1800$ to dominate length tiebreaks against V3.
- [ ] **Conservative Queen Splitting (Tiebreak #1 Guarantee)**:
  - Small maps (area $< 300$): Max 2 dragons. Queen splits only once (round $< 100$).
  - Large maps (area $\ge 300$): Max 3 dragons (reduced from 5). Queen stops splitting after round 140 or once length $\ge 14$.
  - This ensures the Queen remains the undisputed longest dragon on the board for Tiebreak #1.
- [ ] **Portal Graph Integration into BFS**:
  - Re-integrate `PortalRegistry` from V3 into the primary move evaluation. When a portal pair is known, calculate path distances through the portal shortcut, allowing instant flanking across winding maps (`autarky`, `stronghold`).
- [ ] **Total Internal Refraction Dual-Sonar Broadcasting**:
  - Configure the sonar emitter to cast forward (from head) and backward (through tail via internal refraction), maximizing echo detection of surrounding enemies.

### Phase 2: Advanced Game Theory & Predictive Micro
- [ ] **Opponent Path Prediction (Minimax / 1-Step Lookahead)**:
  - For visible enemy heads, calculate their candidate moves based on open space and nearest pearls.
  - If an enemy dragon has only 1 legal escape move, pre-emptively step our assassin drone into that tile to force an unavoidable head-to-head mutual kill.
- [ ] **Adaptive Sprinting for Decisive Interceptions**:
  - If an enemy Queen is 2 tiles away and moving toward a choke point, evaluate a 2-step sprint (`MOVE NN`) to intercept and eliminate the Queen before it can react.
  - Pay the 1-segment sprint cost only when the trade eliminates an opponent with length $\ge 3\times$ our drone.
- [ ] **Voronoi Territory Partitioning**:
  - Implement a fast simultaneous BFS from all friendly heads vs all enemy heads.
  - Compute our team's controlled Voronoi cell area and evaluate moves that maximize our territory while choking enemy space.

### Phase 3: Competition & Ladder Automation
- [ ] **Automated Ladder Challenge Dispatcher (`run_challenges.py`)**:
  - Utilize our 12 ranked battles / hour budget (60 games/hour).
  - Target teams rated within $[-50, +200]$ of our current rating to maximize ELO gains.
  - Leverage the **$K = 96$** initial battle multiplier for newly submitted versions.
- [ ] **Replay Visualizer & Automated Postmortem Script**:
  - Parse replay files in `replays/` to automatically log death round, death cause, and winner for every test match.
  - Flag any self-collision ("hit itself") as a critical regression triggering automated parameter tuning.
- [ ] **Final Submission Gate**:
  - Require a candidate bot to achieve $\ge 10/13$ wins (77%) in the full 13-map tournament against V3 before promoting it as the active ladder submission.

---

## 9. Ladder Rules & Tournament Operation Summary

### 9.1 Autoscrim Cycles
- **Schedule**: Every 2 hours on UTC boundaries (`00:00, 02:00, 04:00, 06:00, 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, 22:00 UTC`).
- **Matchmaking**: Ladder is sorted by ELO; active bots are drawn against up to 2 distinct opponents within $\pm 8$ positions.
- **K-Factor**:
  - Normal matches: $K = 24$.
  - First 10 matches for a new bot: **$K = 96$** (4× acceleration).

### 9.2 Manual Challenge API
- Limit: 12 challenges per hour.
- Target selection: Any team rated no more than 50 points below you, and any team above you.
- Command line execution:
  ```bash
  unswbc challenge <target_team_id>
  ```
- Active Submission Verification:
  ```bash
  unswbc list
  ```

---

## 10. Viper V6 (Leviathan) — C++ Rewrite (submitted as `v6-leviathan`)

**Why C++**: Python V5 peaked at 96M of the 100M points/turn limit. The C++ bot (built with the judge's clang via `unswbc run --sandbox`, no local compiler needed) runs at ~5M median, ~64M worst case.

**Verified mechanics (empirically, not from docs)**
- Rounds start at 0. No pearls at start; countdowns are drawn from each tile's `[min,max]` gap. Tiles not listed in a map file never spawn.
- Portals: crossing a portal edge in direction d exits on the d-side of the partner edge, still facing d. Bodies can be split across portals, so chain reconstruction must follow portal links.
- Enemy heads are static during our turn, so a length-L dragon can **guarantee** a head-on at path distance ≤ L−1 via sprint (used only for favorable trades).

**Architecture** (`viper_v6/main.cpp`)
1. Persistent map memory (edges, portals, pearl countdowns) plus the 13 bundled maps embedded (`tools/gen_maps.py`). Identified by size + first view, re-validated every turn, dropped on any mismatch.
2. Own body tracked exactly (vision chain + move history). Other bodies get a "free-at" time, with an eat margin, and are remembered after leaving view.
3. Survival: a Voronoi-style static room (only cells we reach before any other head; unseen cells half-weight). When tight, an exact DFS runs twice: optimistic (bodies recede) and pessimistic (they don't).
4. Pearl field over time-aware BFS, using spawn timers, a farm bonus for fast-respawn tiles, a committed goal with a progress bonus, and friend/enemy competition discounts.
5. Danger: head-on risk weighted by length asymmetry; small enemy drones at distance 2 count extra. Corridor penalty for tunnels walled by dragon bodies.
6. Length cap ≈ reachable area / 6: beyond it, greed drops and the dragon splits in half. Growing too long on small maps is what killed us.

**Results** (52 games each: 13 maps × both sides × 2 seeds)
| Opponent | V6 win rate |
|---|---|
| starter_bot | 100% |
| viper_v3 | 73% |
| viper_v5 | 73% |
| viper_v2 | 67% |
| viper_bot (V1) | 65% |
| viper_v4 | 63% |

**Known weaknesses / next steps**
- Length losses on big maps (autarky, trauma, stronghold): the enemy's single queen outgrows ours. Trauma's fountains sit in 1-wide dead-end corridors, and safety correctly refuses them.
- About 5 deaths per game, mostly traps sealed by heads we cannot see (7×7 vision). Sonar sharing of teammate positions is the obvious next step.

**Tools**
- `python tools/tourney.py viper_v6 viper_v3 --seeds 2 [--maps a,b]`: parallel sandbox tournament, both sides.
- `python tools/trace.py maps/X.map botA botB --seed N --deaths --ctx 6`: per-dragon decisions before each death.
- Debug board dumps: copy the bot to a folder with `debug_cfg.hpp` defining `DEBUG_FROM`/`DEBUG_TO` (included via `__has_include`, never shipped).

---

## 11. Ladder Reality Check (2026-09-26) — what real opponents do

**Measurement method**: unranked challenges (`POST /battles`, `ranked:false`, all 10 pool maps; no ELO effect, 60 games/hour), then replay analysis with `tools/replay.py` / `tools/ladder_report.py` / `tools/board_at.py`. Server replays are gzip + Cap'n Proto (packed); the decoder reconstructs every body, death reason and our indicator strings.

**Live map pool (10)**: Portals (new, 32×16), Slithery Fight (new, 63×27), Schooltime, Trophy, Queen of Spades, Default, Prisoners Dilemma, Autarky, Devil, Trauma. Not in pool: arena, Colosseum, default_small, big_empty, stronghold.

**Opponent archetypes**
- *Swarm* ("Aviators", "hmm"): split to the 64-unit cap, 30–64 dragons of length 2–8. Drones deliberately ram heads (sprinting 2–3 tiles), and they lose hundreds of dragons per game. Their **longest stays ~5–15**, so one surviving dragon of ~20 wins the tiebreak.
- *Growers* ("just bored"): 5–10 units, longest 26–70.

**Map puzzles**: several maps spawn dragons whose head is sealed (Slithery Fight's 25-long spiral with the head in the centre; heads facing dead-end fountain pockets on Slithery/Dilemma/Autarky). The only survival is to split so a child crawls out from the tail end. If the tail is sealed too, shed the tail first, then split again (`ESCAPE-SPLIT` / `SHED`).

**Fixes that moved the real win rate** (same 3 teams × 10 maps; V6 original went 0-3):
| Version | vs 3 teams | Key change |
|---|---|---|
| v6.1 | 9/30 | sonar radar, safety classes, stricter trades |
| v6.2 | 10/30 | no fragmenting splits, drone-aware danger, endgame horizon fix (the queen suicided on round 499) |
| v6.3 | — | escape/shed splits, walls for unplaced own segments |
| v6.4 | 13/30 | stop sprint bleeding (73 sprints/game vs swarms), swarm insurance splits |
| v6.5 | 15/30 | enemy sprint reach counts as head-on threat (just bored 8/10) |
| v6.6 | pending | danger-escape split for long dragons; small dragons not paralysed by drones |

**Local swarm proxy**: `swarm_bot/` (V3 that splits pairs at every opportunity) reproduces the swarm behaviour for offline testing.

---

## 12. Scouting the Top 12 (2026-09-27) — the meta is swarm + late consolidation

**Method**: `tools/scout.py` pulls each top team's recent public battles and replays (other teams' replays are downloadable), recording which side they played; `tools/scout_report.py` aggregates behaviour per team. 117 games; full output in `ladder/scout_report.txt`.

**Universal (12/12 teams)**
- **Bud at length 4 into 2+2**, starting in round 0 (median first split round 0–9). 180–1100 splits per game, and 75–95% of children are size 2.
- **Fast expansion**: 11–35 units by round 50, 22–47 by round 100, 30–60 by round 200 (cap 64).
- **Longest stays tiny (3–10) until ~round 300**, then climbs to 12–31 by round 500. The tiebreak is won late.
- **Relentless head-on trading**: 26–90 head-on kills per game. Drones are ammunition.
- **Deaths don't matter**: 100–1000 deaths per game. Survival of any individual is irrelevant except the queen's.
- Nobody sprints much (1–11 sprints per 1000 moves).

**Consolidation styles**
- *Explicit suicide* (`no valid action` late): Vibing++ (#9) 89/game (almost the whole swarm; units 41→9 while longest 9→28 by round 400), SSS 32, Sponge 32, #2 20, calc 17, QMT 14.
- *Crash near the queen* (wall/self deaths within 4 tiles of their longest): Sabotage-d (#7) 27/game (longest 10→29 between rounds 300 and 400), SKKU 16, STAR 16, #1 9.
- *Partial*: #2 and #1 keep 17–26 units at the end. Only drones near the queen feed; the rest keep eating (total length helps tiebreak #2 and prevents elimination).

**What we took into V7**: budding at 4, cheap drones, queen-position gossip over sonar, feeding within radius 10 from round 350, budding stops at round 330.

**V7 ladder measurements (unranked, 10 maps each)**
| Opponent | V6.6 | V7.1 |
|---|---|---|
| Aviators | 3/10 | 5/10 |
| Give me a job | 2/10 | 6/10 |
| #2 中国人能飞 | — | 0/10 |
| #1 龙虎豹 | — | 0/10 (V7.0) |

**Remaining gap vs the top**: expansion speed (15 units at round 100 vs their 31) and consolidation yield (we collapse to 2 units with longest 12; #2 keeps 26 units and reaches 23). V7.2 addresses both partially (60% vs V7.1 locally).

---

## 13. Fixing the weak maps (2026-09-27): per-map consolidation (V7.3–V7.4)

**Symptom**: vs mid-ladder swarms (hmm, Aviators, Give me a job) we won Portals, Slithery Fight and Schooltime but lost Devil, Prisoners Dilemma, Autarky and Trophy every time. Ranked 2–3 results were simply unlucky 5-map draws: per-map outcomes were identical between ranked and unranked games with the same submissions.

**Diagnosis from replays** (`ladder/c9–c14`):
1. *Consolidation collapse*: on Trophy we had **60 units vs 9** at round 300, then 35 feeders suicided between rounds 350 and 400 while the longest only went 3→8. The queen was then cut by late danger splits, and we lost with longest 4 vs 7. Mass feeding only pays on big open maps.
2. *Attrition*: without feeding but with budding stopped at round 300, our swarm shrank under one-for-one head-on trades while the opponent kept budding to 30–64 units. Numbers win the pearls and the tiebreak.
3. *Timid drones*: the lexicographic safety class still ranked safe moves above pearl-rich ones for cheap drones, so the tube and pocket fountains went unmined.

**Fixes**
- `bigFeed` maps (Portals, Slithery Fight, Schooltime): v7.2 behaviour, unchanged.
- Other maps: feed only for a visible dragon with length ≥ max(10, 2× the feeder's); from round 400 the longest dragon never splits voluntarily and doubles its danger aversion; cheap drones accept death risk < 0.9 in the safety class; keep budding until round 420 while under 40 units (Autarky: stop at 300).

**Results**: V7.3 70% vs V7.2 locally; V7.4 83% vs V7.3 on changed maps. On the ladder, maze maps vs the three swarms went from 8/21 (V7.1/V7.2) to **15/21** (V7.4); the four problem maps went from 1/12 to 7/12. Remaining: Devil 0/3 (early expansion 6–10 units at round 100 vs 15–38).
