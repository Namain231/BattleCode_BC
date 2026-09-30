# Critique and Ideas for Y.10 Bot

## 1. CRITIQUE: What is wrong with our process and bot design

**Process Flaws (Bluntly):**
- **Blindness to Cross-Map Side Effects:** The ladder A/B tests that spawned `Y.8a-n4` were conducted exclusively on maze maps. Because open maps play out completely differently (massive swarms, high density, huge total mass), changes optimized for mazes actively sabatoged open-map performance. We saw the mass advantage on open maps but neglected to study *how* the mass was subsequently lost.
- **Over-reliance on Macro-metrics:** The post-mortems note "numbers war" and "late collapse" but gloss over the actual mechanisms of death. You identified that our longest dragon often dies by "crash or feeding" before r500, but treated this as a statistic rather than an architectural bug to debug in the replays.

**Bot Design Flaws (Blind Spots):**
1. **Self-Suffocation (The Queen Trap):** On open maps (`bigFeed = true`), `P.feedFrom` hits exactly at round 350. Because there is absolutely no throughput throttling, every drone on the map simultaneously homes in on the queen. The queen gets completely boxed in by her own feeders and dies of suffocation (crashing because she has no safe moves). The `protectedQueen()` flag makes her so risk-averse that she refuses to break out, and she cannot `doomedSplit()` or `findAttack()`. This perfectly explains why we have drastically more total mass but the longest dragon mysteriously dies late-game.
2. **Artificial Deadlocks in Maze Feeding:** The hardcoded condition `queen.len >= 10` in `tryFeed()` on maze maps creates an unwinnable deadlock. Because `P.budUntil = 400` prevents any dragon from naturally reaching length 10, the swarm indefinitely waits for a queen that can never exist.
3. **Multi-Queen Dissipation (Feed Chains):** Any drone can claim queen status if it temporarily exceeds the gossiped length, and there is no cap on feeder length. Thus, mid-sized dragons feed into each other in endless chains, halving our mass with every transfer via `SPLIT 1`.
4. **Portal Suicides:** Portals on known maps are currently treated as fully safe (`safeClass = 1`). Teammates blindly step through them directly onto the heads of our own queen or teammates, causing instant game-losing decapitations.
5. **Fountain Starvation:** Our global `friendCloser` penalty (92% reduction) prevents multiple dragons from farming the same fountain cluster. S.4.7.5 limits yielding to distance $\le 4$, allowing them to out-swarm us on early game centers.

---

## 2. IDEAS: Top 5 Promising Changes

### 1. Feeder Throughput Limiting (Anti-Suffocation)
- **Mechanism:** Feeders abort homing/feeding if there are already $\ge 2$ teammates adjacent to the queen.
- **Why I believe it:** Open map losses are caused by the queen being trapped by her own feeders. S.4.7.5 explicitly uses a throughput cap of 2 within radius 4 to prevent traffic jams. Our bot lacks this entirely.
- **Where:** `cand_y10/main.cpp` inside `think()`, specifically around the `feeding` and `homingToQueen` assignments (approx line 1481). Add a loop to count nearby teammates, and if `> 2`, override `feeding = false` and `homingToQueen = false`.
- **Test:** A local panel on open maps (`Portals`, `Slithery Fight`, `Schooltime`) against `viper_nn` (Y.8m).

### 2. Portal Landing Queen Protection
- **Mechanism:** Veto blind portal steps if the landing tile is within Chebyshev distance 1 of `queen.cell`.
- **Why I believe it:** Loss analysis (`s475_vs_y10.md`) explicitly identified friendly decapitations through portals (e.g., Default r480). Our `zoneF` logic does not cross portals, so the queen is invisible to incoming friendly jumpers.
- **Where:** `cand_y10/main.cpp` in `evaluate()` (approx line 1054). If `s.outside` and it's a portal step, check distance to `queen.cell` and set `e.safeClass = 0` if $\le 1$. Additionally, penalize the queen for loitering directly on portal landing pads.
- **Test:** A local panel on `Default` and `Portals` against `S.4.7.5`.

### 3. Strict Queen Consensus & Feeder Length Cap
- **Mechanism:** Impose a strict feeder length cap (`MY_LEN <= 6`) and lower the maze feeding threshold to `max(6, MY_LEN + 2)`. 
- **Why I believe it:** This breaks the maze deadlock (where no dragon reaches 10) and prevents mass-halving feed chains where length-8 dragons feed length-10s. By capping feeder length, we preserve mid-sized dragons as secondary titans for the tiebreak.
- **Where:** `cand_y10/main.cpp` in `tryFeed()` (approx line 1354). Change `queen.len < (bigFeed ? 6 : 10)` to `queen.len < (bigFeed ? 6 : max(6, MY_LEN + 2))` and insert `MY_LEN <= 6` as a prerequisite to feed.
- **Test:** A local panel on Maze maps (`Trauma`, `Devil`) vs `S.4.7.5`.

### 4. Localized Fountain Yielding (`hotYield`)
- **Mechanism:** Only discount pearl value due to a closer teammate if that teammate is $\le 4$ steps away from the pearl.
- **Why I believe it:** We lose the numbers war early on maze maps because only 1 dragon approaches a 5-pearl fountain cluster (the global `friendCloser` penalty repels the rest). S.4.7.5 allows multiple dragons to swarm the same fountain if they aren't directly adjacent.
- **Where:** `cand_y10/main.cpp` in `evaluate()` (approx line 927). Add a condition `friendDist[n] <= 4` for fountain tiles before multiplying `p *= P.friendCloser`.
- **Test:** A local panel on `Trophy`, `Devil`, and `Trauma` vs `S.4.7.5`.

### 5. Remove Artificial Fountain Suppression (Macro Navigation)
- **Mechanism:** Remove the `minerFarmCap` and `minerGamma = 0.90` suppression that drops target valuation for distant fountains on maze maps. 
- **Why I believe it:** On large maze maps (Trauma), `shortSight` causes distant fountains to exert zero navigational pull. Our drones wander blindly for 50+ rounds, while S.4.7.5 uses an undiscounted `wCompass` BFS gradient to beeline directly to fountains.
- **Where:** `cand_y10/main.cpp` in `evaluate()` (approx lines 898 and 928). Disable or raise `minerFarmCap` on mazes, and ensure `powT` (undiscounted) is used for high-yield fountains beyond the local tactical horizon.
- **Test:** A local panel strictly on `Trauma` and `Devil` vs `S.4.7.5`.

---

## 3. Top Replay Uncertainty Question

I would download the top teams' replays (e.g., rank 1 or 2) on open maps (`Slithery Fight`, `Schooltime`) and ask: 
**"How do they dynamically position and maneuver their queen during the late-game feeding phase (r400+) to completely avoid self-suffocation and throughput jamming?"** 
Do they park her in a corner, continuously move her in a wide circle so feeders trail behind, or dynamically route feeders to hit her tail rather than her head? This would definitively solve our open-map collapse.
