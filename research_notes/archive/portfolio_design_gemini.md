# Portfolio Design for UNSW Battlecode 2026

## 1. Combining C++ Cores Safely
**How to combine safely:**
The most robust way to combine multiple distinct C++ cores (e.g., `cand_y10` and `s475`) is by wrapping each entirely within its own `namespace` (e.g., `namespace CoreY10 { void run(); }`). 
You create a single master `main.cpp` that reads the `INIT` block and the very first turn's `ROUND` block. Based on that first turn, the master determines the regime, permanently dispatches execution to the selected namespace's `run()` function, and never switches back.

**Pitfalls:**
- **Static State & Globals:** Namespaces isolate global variables, but if both cores include the same header with static definitions (e.g., a shared `policy_nn.hpp` with static arrays), it can cause clashes or bloat.
- **Memory Limit (48 MB):** Combining multiple neural networks and large arrays will quickly exceed the 48 MB RAM limit or the 4 MB zip limit. 
- **stdin/stdout Ownership:** The master `main()` will consume the first turn's stdin to make its decision. The chosen core must be refactored to accept this pre-read first turn state rather than calling its own `readTurn()` immediately, or the master must just peek/buffer it.
- **Irreversibility:** Once a core starts mutating its static state (like `seenR` or `occId`), switching to another core is impossible. The decision must be locked in on Turn 1 for that process.

## 2. Regime Consistency & Sonar Gossip
For a portfolio to work, **every process on the team must agree on the regime**. A mixed team (half playing open, half maze) will fail to consolidate and lose.

**The Strategy:**
1. **Founder Dragon (Round 0):** The first dragon(s) alive at round 0 determines the regime using map size and early vision (or `KNOWN_MAPS` identification via `knownmap.hpp`).
2. **Sonar Gossip:** The founder encodes the regime into the top bits of its 64-bit sonar broadcasts. For example, if using the queen gossip sonar, reserve the top 2 bits: `(REGIME_ID << 62) | queen_data`.
3. **Split Children:** When a split child is created, the protocol guarantees it acts *later in the same round* (because its ID is higher). Thus, it receives the parent's sonar at the start of its *very first turn*. 
4. **Fallback:** If a child's first turn arrives and it hears no sonar (e.g., blocked by kelp), it must fall back. The safest fallback is computing a hash of `(W, H)` to pick a pseudo-random but globally consistent default for the map, or relying strictly on its own 7x7 vision to guess the regime until a sonar arrives. 

## 3. Features for Open vs. Maze vs. Portal
To classify a new map from the initial 7x7 vision window:
- **Kelp Density:** Count the number of kelp edges (`kind == 2`) divided by the total number of edges. 
  - *Open:* `< 0.15* (sparse or border only).
  - *Maze:* `> 0.30` (dense walls and tubes).
- **Corridor Branching Factor:** Run a local BFS up to depth 3. Calculate the average number of free adjacent cells per open cell. 
  - *Open:* Average degree ~3.5 to 4.0.
  - *Maze:* Average degree ~2.0 (mostly 1-wide or 2-wide tubes).
- **Portal Density:** Count of portal edges (`kind == 3`). If `portal_count > 0`, it triggers portal-aware safety logic (e.g., avoiding parking heads on portals).

## 4. Minimal First Version (MVP) & Evaluation
**The MVP (Within a few hours):**
Do not attempt namespace-merging distinct bots yet. Instead, use the unified `cand_y10` codebase and define multiple discrete `Params` profiles: `Params open_map`, `Params maze_map`.
- At Round 0 (or Turn 1 for children), read the initial 7x7 window. 
- If `KNOWN_MAPS` matches, select the corresponding preset.
- If unknown, calculate the `Kelp Density`. If `> 0.25`, set `P = maze_map`; else `P = open_map`.
- Broadcast this choice in the top 2 bits of the sonar.

**Evaluation:**
Since offline self-play panels are unreliable for testing long-term dynamics:
1. Deploy the MVP to the active ladder as an unranked bot.
2. Use the provided curl script (`curl -s $BASE/battles...`) to trigger unranked scrims against top-ranked targets (e.g., S.4.7.5, vB.17) across the 10 known maps (5 open, 5 maze).
3. Compare the unranked win rates on specific map geometries against the baseline `Y.10` panel logs.

## 5. Critique: When a Portfolio Fails & The Alternative
**When it fails:**
A discrete portfolio bot fails terribly on **mixed maps** (e.g., a map with an open center but dense maze-like corners).
- If the founder spawns in the open center, it broadcasts "Open Regime". Dragons that later migrate to the maze corners will stubbornly apply open-map heuristics (e.g., aggressive feeding radiuses) and die trapping themselves or failing to mine.
- If sonar gossip breaks (blocked by kelp tubes), children might misclassify their local 7x7 window and pick a different core, leading to a split team lacking a unified endgame consolidation plan.

**What to do instead:**
Build a **Continuous Adaptive Core** rather than a discrete portfolio. 
Similar to `s475`'s `bedDensity` adaptation, calculate features (like local kelp density or distance to center) *every turn* and use them to smoothly scale parameters. 
For instance, scale `minerGamma` and `feedRadius` proportionally to the local branching factor. This allows dragons in the open center to play like an open-map bot, while dragons mining the maze edges play conservatively, all without needing fragile team-wide discrete consensus.
