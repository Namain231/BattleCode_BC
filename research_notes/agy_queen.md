# vB.21 Queen Survival & Growth Analysis vs cand_y93

This report analyzes how **vB.21** ("Hydra Sovereign Imperator", `opponents/vb21/main.cpp`) consistently keeps its true queen (ID 0 or 1) alive until Round 500 and grows her to length 14–29, while **cand_y93** (`cand_y93/main.cpp`) sees its queen stagnate at length 2–3, die in portal corridors, or get boxed in by friendly swarms.

---

## 1. Exactly How vB.21 Moves, Grows, and Protects Its Queen

vB.21 treats the true queen not merely as a high-value piece, but as the **Sovereign Sink** around which the entire bot's architecture rotates.

### 1.1 Queen Identification & Sovereign Status
- **True Queen Predicate**: [`opponents/vb21/main.cpp:94`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L94)
  ```cpp
  static inline bool isTrueQueen() { return MY_ID <= 1; }
  ```
- **Consensus & Fallback Tracking**: [`opponents/vb21/main.cpp:102-113, 799-810`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L102-L113)
  - `isOurQueenDead()`: Strictly presumes the true queen is **alive** for `ROUND < 150` or within 40 rounds of birth/gossip (`lines 799-805`).
  - `isSovereignSink()`: If `!isOurQueenDead()`, returns `isTrueQueen()` (`lines 807-810`). The true queen is permanently locked as the sovereign sink while alive. Succession by length occurs only if the queen is confirmed dead.
- **Maturity / Protection Threshold**: [`opponents/vb21/main.cpp:822-825`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L822-L825)
  ```cpp
  static inline bool protectedQueen() {
      if (!isSovereignSink()) return false;
      return (ROUND >= 260 || UNITS >= 40);
  }
  ```
  Once our swarm reaches 40 units (typically rounds 80–130) or round 260 is reached, the queen enters protected mode.

### 1.2 Queen Growth & Greed Scaling (Early Expansion + Feeding)
- **Early Growth Multiplier**: [`opponents/vb21/main.cpp:1140-1150`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1140-L1150)
  ```cpp
  if (isSovereignSink()) {
      if (ROUND < 150) {
          growth *= 2.2;
          greed *= 1.2;
      } else if (protectedQueen()) {
          growth *= 1.5;
          greed *= 0.05; // food comes to the sovereign, she doesn't wander into corridors
      } else {
          growth *= 1.5;
          greed *= 0.3;
      }
  }
  ```
  In rounds 0–149, vB.21 actively pushes the queen to eat and grow (`growth *= 2.2, greed *= 1.2`), allowing her to reach length 8–15 naturally before locking down. Later, `greed` drops to `0.05` because feeders bring pearls to her.
- **Sprint Penalty Protection**: [`opponents/vb21/main.cpp:1156-1162`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1156-L1162)
  ```cpp
  if (actualCost > 0) {
      if (isSovereignSink()) score -= actualCost * 50.0;
      ...
  }
  ```
  The queen never burns her own segments on multi-step sprints.
- **Board-Wide Feeding Funnel**:
  - Telemetry: From Round 0, the queen broadcasts `packSink(head, MY_ID, MY_LEN, ROUND)` on all 4 sonar directions every turn ([`opponents/vb21/main.cpp:1990-1995`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1990-L1995)).
  - Homing: `feedRadius = 999` ([`line 64`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L64)). From `ROUND >= P.feedFrom` (`330`, [`line 62`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L62)), non-queen drones across the *entire board* pull toward her:
    ```cpp
    score += 30.0 * (curD - newD); // global pull towards sink!
    score -= 0.5 * newD;
    ```
    ([`opponents/vb21/main.cpp:1174-1181`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1174-L1181), and `goalCell = sinkCell` in `think()` [`lines 1827-1832`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1827-L1832)).
  - Illegal Split Feed: Within `torusDist <= 3`, drones execute `printf("SPLIT 1\n");` ([`opponents/vb21/main.cpp:1677-1681`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1677-L1681)), crystallizing into pearls right in front of the queen. Unit floor: `UNITS <= (ROUND >= 400 ? 5 : 8)` ([`line 1669`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1669)).

### 1.3 Anti-Shrinking & Splitting Bans
- **Opening Split Disabled**: [`opponents/vb21/main.cpp:1759`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1759): The queen never executes an opening split in coiled tubes.
- **Swarm Budding Ban**: [`opponents/vb21/main.cpp:1462`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1462) in `swarmSplit()`:
  ```cpp
  if (protectedQueen()) return false;
  ```
  The queen stops budding off length-2 children as soon as `UNITS >= 40` or `ROUND >= 260`.
- **Voluntary Split Ban**: [`opponents/vb21/main.cpp:1480`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1480) in `trySplit()`:
  ```cpp
  if (protectedQueen()) return false;
  ```
- **Doomed / Shed Split Immunity**: [`opponents/vb21/main.cpp:1394-1395, 1924, 1926`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1394-L1395)
  - `if (isTrueQueen() && ROUND <= 25 && !allowShed) return false;` (no opening uncoil shedding).
  - `if (isSovereignSink() && MY_LEN < 8) return false;` (queen never sheds or splits if under length 8).
  - Danger-shedding (`doomedSplit(false)`) is disabled when `protectedQueen()` ([`line 1926`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1926)).

### 1.4 Portal & Corridor Safety (Zero Blind Portal Steps)
- **BFS Exclusion of Unseen Portals**: [`opponents/vb21/main.cpp:1033`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1033)
  ```cpp
  if (isSovereignSink() && effK(c, d) == 3 && viewIndex[n] < 0) continue;
  ```
  The sovereign sink's pearl/space search *never traverses unseen portals*. She never plans paths into portal tubes.
- **Blind Step Ban**: [`opponents/vb21/main.cpp:1211-1214`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1211-L1214)
  ```cpp
  if (isSovereignSink() && s.outside) {
      score -= 50000.0;  // Sovereign Sink NEVER steps blindly outside vision!
      e.safeClass = 0;
  }
  ```
- **Hard Safety Gate**: [`opponents/vb21/main.cpp:1287-1288`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1287-L1288)
  ```cpp
  bool riskOk = isSovereignSink() ? (e.pDeath < 0.05 && !s.outside) : ...;
  e.safeClass = (riskOk && !adjacentThreat && (!s.outside || (KM && e.safeClass > 0))) ? 1 : 0;
  ```
  Even on known maps (`KM`), sovereign sink steps outside vision are hard-vetoed (`safeClass = 0`).
- **Portal Proximity Penalty**: [`opponents/vb21/main.cpp:1262-1268`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1262-L1268): `-40.0` if adjacent to portal, `-20.0` if 1-hop away.

### 1.5 Sprint-Aware Head-On Protection & Voronoi Space
- **Free Sprint Reach Modeling**: [`opponents/vb21/main.cpp:838`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L838): `spd = max(1, (dr.estLen + 3) / 4)`.
- **Sprint Danger Detection**: [`opponents/vb21/main.cpp:1108-1112`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1108-L1112)
  ```cpp
  if ((isSovereignSink() || L >= 6 || UNITS <= 4) && (dd == 1 || (dd <= 3 && dd <= er.len - 1))) adjacentThreat = true;
  if (isSovereignSink() && dd <= max(2, (er.len + 3) / 4)) {
      danger += 100000.0;
      adjacentThreat = true;
  }
  ```
- **SINK IMMORTALITY in QHIDE**: [`opponents/vb21/main.cpp:1229-1243`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1229-L1243)
  ```cpp
  for (auto& dr : others) {
      if (dr.team != MY_TEAM && dr.headCell >= 0) {
          int enemyReach = max(1, (dr.estLen + 3) / 4); // ceil(L / 4) free sprint reach
          int curD = torusDist(body[0], dr.headCell);
          int newD = torusDist(s.cells.back(), dr.headCell);
          if (newD <= enemyReach) {
              score -= 200000.0;
              e.safeClass = 0;
          } else if (newD <= enemyReach + 1 || (curD <= enemyReach + 3 && newD < curD)) {
              score -= 80000.0;
              e.safeClass = 0;
          }
      }
  }
  ```
  Any move landing within enemy sprint reach is penalized by **-200,000.0** and forced `e.safeClass = 0`.
- **Room / Box-In Gate**: [`opponents/vb21/main.cpp:1244-1249`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1244-L1249)
  ```cpp
  if (protectedQueen()) {
      score -= 80.0 * e.pocket;
      if (e.room < 20) {
          score -= 40.0 * (20 - e.room);
          if (e.room < 12) e.safeClass = 0;
      }
  }
  ```
  If Voronoi room is `< 12`, the move is disqualified (`safeClass = 0`).

### 1.6 Swarm Clearance (ROW) & Assassin Wing
- **All-Game ROW Clearance**: [`opponents/vb21/main.cpp:1275-1282`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1275-L1282)
  Friendly drones penalize ending adjacent to the queen (`torusDist <= 1`, `-15.0`) and within distance 3 (`-2.0 * (4 - qd)`) throughout the **entire match**.
- **Neural Network Attenuation**: [`opponents/vb21/main.cpp:1884`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1884)
  Queen `wNN = 0.2` (drones use 2.0). The NN cannot override Voronoi safety.
- **Enemy Queen Assassins**: [`opponents/vb21/main.cpp:813-819, 1168-1173`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L813-L819): Drones actively hunt and ram the enemy queen, removing the opponent's tiebreaker.

---

## 2. The 3 Biggest Differences Explaining the Survival/Length Gap

### Difference 1: Artificial Growth Stunting & Self-Budding down to L2–3 in cand_y93
- **In cand_y93**:
  1. `swarmSplit()` ([`cand_y93/main.cpp:1403-1421`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1403-L1421)) has **no check for `isTrueQueen()` or `protectedQueen()`**. Whenever the queen reaches length 4 (`P.budAt = 4`), she immediately buds off a child (`SPLIT 2`), cutting herself back to length 2.
  2. `protectedQueen()` in cand_y93 ([`line 1596`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1596)) only activates at `ROUND >= 400` (`protectFrom = 400`) and tracks the longest elected dragon (`queen.id`), NOT the true queen!
  3. `evaluate()` in cand_y93 ([`line 1122`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1122)) intentionally cripples her appetite: `if (isTrueQueen() && ROUND >= 100 && ROUND < P.qfeedFrom) greed *= 0.2;`.
  4. Feeding radius is restricted to `P.feedRadius = 25` ([`line 64`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L64)), with a static `UNITS <= 10` floor ([`line 1606`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1606)) and no pull gradient.
- **In vB.21**:
  1. The queen is encouraged to grow in rounds 0–149 (`growth *= 2.2; greed *= 1.2`, [`line 1142`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1142)), quickly reaching length 8–15.
  2. She stops budding completely once `UNITS >= 40` (typically r80–120) or `ROUND >= 260` via `protectedQueen()` ([`line 824, 1462`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L824)).
  3. Drones across the entire board (`feedRadius = 999`) have a direct geometric pull gradient toward her (`30.0 * (curD - newD)`) and feed her with `SPLIT 1`.

### Difference 2: Blind Portal Traversal and Corridor Traps in cand_y93
- **In cand_y93**:
  1. Stepping outside vision into an unseen portal has only a weak `-120.0` score penalty ([`line 1159`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1159)) and **does not demote `safeClass`**.
  2. On known maps (`KM`), outside portal moves explicitly retain `safeClass = 1` ([`line 1213`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1213): `!s.outside || (KM && e.safeClass > 0)`).
  3. BFS pearl evaluation freely expands across portals ([`line 1012`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1012)), enticing the queen to enter portal tunnels.
  4. Neural network weight `wNN = 2.0` runs on the queen ([`line 1832`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1832)), overwhelming small geometric penalties and steering her into portal mouths.
- **In vB.21**:
  1. The BFS queue strictly skips unseen portals for the sovereign sink ([`line 1033`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1033)).
  2. Stepping outside vision carries a `-50000.0` penalty and immediately sets `safeClass = 0` ([`lines 1211-1214`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1211-L1214)).
  3. `riskOk` explicitly requires `!s.outside` for the sovereign sink ([`line 1287`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1287)), closing the `KM` loophole.
  4. Queen `wNN` is muted to `0.2` ([`line 1884`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1884)).

### Difference 3: Sprint-Unaware Head-On Vulnerability & Swarm Suffocation (Box-In)
- **In cand_y93**:
  1. Head-on threat detection in `evaluate()` ([`line 1089`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1089)) only triggers if `L >= 6 || UNITS <= 4`. Because cand_y93's queen is length 2–3 with >4 units, she is **completely unprotected against adjacent enemy heads**!
  2. Enemy sprint reach (`ceil(L/4)`) is never checked in QHIDE ([`line 1167`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1167)); enemies 2–3 cells away freely sprint-kill her.
  3. **Swarm Box-in**: In cand_y93 ([`lines 1195-1206`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1195-L1206)), allies only avoid distance `<= 3` from the queen when `ROUND >= 150 && ROUND < P.qfeedFrom` (280). From round 280 onwards, this buffer is turned off! 25–30 drones crowd around her, reducing her room from 24 to 0 and suffocating her (as directly observed on Portals vs POFPOF).
- **In vB.21**:
  1. `adjacentThreat` checks `isSovereignSink()` unconditionally ([`line 1108`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1108)).
  2. Any move ending within enemy sprint reach (`max(1, (estLen + 3)/4)`) is penalized by **-200,000.0** and forced `safeClass = 0` ([`lines 1229-1242`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1229-L1242)).
  3. Drones maintain distance `<= 1` (`-15.0`) and distance `<= 3` (`-2.0 * (4 - qd)`) throughout the **entire match** ([`lines 1275-1282`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1275-L1282)), while `room < 12` forces `safeClass = 0` ([`line 1248`](file:///D:/battlecode/BattleCode_BC/opponents/vb21/main.cpp#L1248)).

---

## 3. Three Concrete, Small Code Changes for cand_y93

### Change 1: Seal Blind Portal Corridor Deaths & Outside Steps (Most Promising)
**Function**: `evaluate()` in `cand_y93/main.cpp`
**Action**:
1. At [`cand_y93/main.cpp:1014`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1014) in the BFS loop, prevent queen from planning paths through unseen portals:
   ```cpp
   if (isTrueQueen() && effK(c, d) == 3 && viewIndex[n] < 0) continue;
   ```
2. At [`cand_y93/main.cpp:1159`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1159), replace the weak `-120.0` penalty with a hard safeClass demotion:
   ```cpp
   if (isTrueQueen() && s.outside) {
       score -= 50000.0;
       e.safeClass = 0;
   }
   ```
3. At [`cand_y93/main.cpp:1212-1213`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1212-L1213), enforce that queen moves outside vision never qualify as safe even on known maps:
   ```cpp
   bool riskOk = isTrueQueen() ? (e.pDeath < 0.05 && !s.outside) : (e.pDeath < 0.25 || miner || (cheap && !bigFeed && e.pDeath < 0.9));
   e.safeClass = (riskOk && !adjacentThreat && (!s.outside || (KM && !isTrueQueen() && e.safeClass > 0))) ? 1 : 0;
   ```
4. At [`cand_y93/main.cpp:1832`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1832), de-weight neural network policy on the queen:
   ```cpp
   for (auto& o : opts) o.ev.score += (isTrueQueen() ? 0.2 : P.wNN) * log(max(1e-3f, nnProb[(o.dirs[0] - MY_DIR + 4) % 4]));
   ```

### Change 2: Enable Queen Growth and Ban Mid/Late Self-Budding
**Functions**: `swarmSplit()`, `evaluate()`, `doomedSplit()` in `cand_y93/main.cpp`
**Action**:
1. At [`cand_y93/main.cpp:1403`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1403) (`swarmSplit()`), add an immediate guard:
   ```cpp
   if (isTrueQueen() && (UNITS >= 30 || ROUND >= 150)) return false;
   ```
   *Rationale*: Prevents the queen from endlessly shedding children down to length 2 once the swarm is established.
2. At [`cand_y93/main.cpp:1122`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1122) (`evaluate()`), allow the queen to grow during opening rounds instead of starving her from round 100:
   ```cpp
   if (isTrueQueen()) {
       if (ROUND < 150) { growth *= 2.2; greed *= 1.2; }
       else if (ROUND < P.qfeedFrom) { greed *= 0.2; }
       else { growth *= 1.5; greed *= 0.1; }
   }
   ```
3. At [`cand_y93/main.cpp:1349`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1349) (`doomedSplit()`), prevent shedding when short:
   ```cpp
   if (isTrueQueen() && (ROUND <= 25 || MY_LEN < 8)) return false;
   ```

### Change 3: Sprint-Aware Head-On Immunity & Prevent Swarm Box-In
**Function**: `evaluate()` in `cand_y93/main.cpp`
**Action**:
1. At [`cand_y93/main.cpp:1089`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1089), protect the queen against adjacent enemy heads regardless of her length or unit count:
   ```cpp
   if ((isTrueQueen() || L >= 6 || UNITS <= 4) && (dd == 1 || (dd <= 3 && dd <= er.len - 1))) adjacentThreat = true;
   if (isTrueQueen() && dd <= max(2, (er.len + 3) / 4)) {
       danger += 100000.0;
       adjacentThreat = true;
   }
   ```
2. At [`cand_y93/main.cpp:1167`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1167), add sprint-reach penalty for all visible enemy heads:
   ```cpp
   for (auto& dr : others) {
       if (dr.team != MY_TEAM && dr.headCell >= 0) {
           int enemyReach = max(1, (dr.estLen + 3) / 4);
           int newD = torusDist(s.cells.back(), dr.headCell);
           if (newD <= enemyReach) {
               score -= 200000.0;
               e.safeClass = 0;
           } else if (newD <= enemyReach + 1) {
               score -= 80000.0;
               e.safeClass = 0;
           }
       }
   }
   ```
3. At [`cand_y93/main.cpp:1195-1207`](file:///D:/battlecode/BattleCode_BC/cand_y93/main.cpp#L1195-L1207), keep the ally `qd <= 3` clearance buffer active throughout the entire match:
   Replace the split blocks with:
   ```cpp
   if (!isTrueQueen()) {
       for (auto& dr : others)
           if (dr.team == MY_TEAM && isQueenId(dr.id) && dr.headCell >= 0) {
               for (int c : s.cells) if (torusDist(c, dr.headCell) <= 1) { score -= 15.0; break; }
               if (!s.cells.empty()) { int qd = torusDist(s.cells.back(), dr.headCell); if (qd <= 3) score -= 2.0 * (4 - qd); }
           }
   }
   ```
