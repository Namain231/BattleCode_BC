# Queen succession and enemy-queen hunting (research, 2026-10-02)

Researcher note. No code was edited and no games were run. Tags: **[D]** docs (`docs/`), **[M]** measured here on
`ladder/scout_v6` (306 top-team games, both teams, read-only scripts on `tools/replay_lite.py`), **[R]** code reading or
reasoning, **[U]** unverified: needs a test before anyone relies on it.

## 0. Headline

1. **There is no succession.** A dead queen counts as length 0 at round 500 [D structure.md:17]. Tiebreak 2 (longest
   living dragon) only decides when **both** queens are dead. Replays agree [M]. In 20 r500 games the winner's queen
   lived and the loser's was dead. In 6 of them the loser had the longer longest dragon and still lost, so no
   lowest-id heir takes over. (overview.md's "lowest-id robot of your team" is loose wording.) In all 118 r500 games
   where both queens were dead, the winner's longest dragon was at least as long as the loser's.
2. **What a dragon does after a queen dies depends on both queens, not just ours.** In three of the four states,
   no keeper vote is needed (section 2). A keeper vote matters only when both queens are dead. That is the
   **common** case: 118 of the 142 top games that reach r500 [M]. On Autarky, Dilemma and Slithery Fight, both queens
   are dead by round 10 in **62/62, 60/60 and 62/62** queen-games [M]. **vB19/f1 has no sink at all in that state**:
   feeding goes only to the true queen, and protection covers only the true queen (section 4). Of everything here,
   this is the largest gap that needs no new protocol.
3. **Enemy queens die mostly to rams.** After r10, top-team queens are rammed head-on by an enemy dragon in **40%**
   of deaths (139/350). Ordinary dragons are rammed in 8% of theirs (10,668/131,271) [M], so queens are hunted
   about 5x more often. The killers are length 2 (50) or 3 (77) in 127 of 148 rams. **55% of rams used 2 or more
   steps, so they paid segments** (76 of 139 after r10) [M].
4. **Killing a seen queen is deterministic.** Queens are ids 0 and 1 and move first each round [D execution-order.md:10].
   So when any of our drones (id ≥ 2) takes its turn, the board in its view is exactly the board its move runs on.
   If a free path to her head is no longer than the drone's **kill reach R(L) = ceil(L/4) + (L − 2)**, the ram is
   certain. Our threat model and our attack search both understate R for L ≥ 5 (section 6).
5. **Latent bug [M+R]:** `ourQueenId() = MY_TEAM` and `enemyQueenId() = 1 − MY_TEAM` (vB19:88-89, f1:89-90) are wrong
   in **55% of ladder games**. Dragon 0 belongs to team B in 168 of 306 top games. They are unused today. Delete them
   and always identify queens by `(team, id ≤ 1)` from vision.

---

## 1. Facts the design rests on

| Fact | Source |
|---|---|
| Tiebreaks at r500: longer queen (dead = 0) → longest living dragon → total length → draw. Elimination ends the game at once and beats every tiebreak. | [D structure.md:15-20] |
| Queens = ids 0 and 1, on different teams. Ids follow file order, teams alternate. **On the ladder, id 0 is team B in 168/306 games**; local `maps/*.map` all start with team 0. | [D map-files.md:53], [M] |
| Turn order is ascending id. Both queens act before every drone each round. A split child takes the next id and acts later in the same round. | [D execution-order.md:10-12] |
| Head-to-head: **both die, whatever the lengths**. Body hit: only the mover dies. The hit dragon's death runs first. | [D movement.md "Collisions", execution-order.md] |
| Death drops ceil(L/2) pearls on every second segment, starting at the head **as it stands**. In a head-on, neither head moved. | [D death.md, execution-order.md "death sequence"] |
| Sprint: the first ceil(L/4) steps are free. Each later step first checks it can pay ("a dragon of length 2 cannot"), then removes one tail segment. A death discards the remaining steps **and that turn's sonar**. | [D movement.md, execution-order.md] |
| Vision is 7×7 (Chebyshev 3), does not cross portals, and every segment line is `team id x y facing isHead`. | [D vision.md, protocol.md] |
| There is no death event in the protocol. A dragon learns of a death only from vision (body gone, pearls appear), from messages, or from `UNIT_COUNT` (which does not say who died). | [D protocol.md] |
| Sonar carries no sender or team. A ray that reaches a lower id is read next round; a higher id reads it the same round. | [D sonar.md] |

**Kill reach R(L)** (a ram must be *payable* on the hitting step) [R from D]:

| L | 2 | 3 | 4 | 5 | 6 | 8 | 12 |
|---|---|---|---|---|---|---|---|
| free steps ceil(L/4) | 1 | 1 | 1 | 2 | 2 | 2 | 3 |
| **R(L) = ceil(L/4) + L − 2** | 1 | 2 | 3 | 5 | 6 | 8 | 13 |

Eating on the path adds reach. R counts walking steps through free cells, portals included.

---

## 2. Four states, four macros (Task A core)

Each dragon tracks two beliefs: `ourQ ∈ {alive, dead@d}` and `enQ ∈ {alive, dead@d}`.

| ourQ / enQ | Who wins at r500 | Sink / feed target | Hunting | Election? |
|---|---|---|---|---|
| alive / alive | longer queen | **true queen only** (fixed id, no messages needed to know *who*) | kamikaze on enemy queen = top priority | **No** |
| alive / dead | we win if we are not eliminated; her length is irrelevant (any length beats 0) | **none**: stop feeding (feeders crowd her: CROWD/ROW incidents). Queen goes to pure hide. | defend only; keep unit count | **No** |
| dead / alive | we **lose** unless she dies or they are eliminated | none yet. **Pre-designate the longest dragon as heir**: no budding, protect it, because tiebreak 2 decides if the hunt succeeds | **all-in**: every drone homes on her | **No** (heir = longest, local rule below) |
| dead / dead | longest living dragon, then total | **keeper = our longest dragon** (ties: lowest id, deterministic) | ram their longest dragon (calc's "hunting") | **Only here** |

**The local keeper rule, with no messages** [R]: a dragon calls itself keeper-eligible if no friend it has seen or
heard of in the last 40 rounds is longer, with ties going to the lower id. Feeding keeps y7's vision-gated rule (feed
only a *visible* friend with `estLen ≥ max(10, 2·MY_LEN)`, `UNITS > 10` FLOOR), so the act of feeding never needs a
message. Messages (T_CLAIM below) only help a far drone walk toward the keeper, and only in the both-dead state.
Several claimants are acceptable: only the maximum counts at r500. The cost is the mass fed to the losers, which
the hysteresis below limits.

---

## 3. Detecting a queen's death

There are three channels, cheapest first.

**(a) Vision witness: exact and free [R].** Keep `lastSeen[q] = {round, head h, cells, L}` for each queen seen in view
(own and enemy, by `team` and `id ≤ 1`). At my turn t, suppose:
- I saw queen q at my turn t−1, and
- her old head cell h is in my view now, holds **no segment of q**, and **holds a pearl** that was not there before.

Then she is dead. Record the death as **d = t−1**, the conservative value: a higher-id dragon may have rammed her
after my turn at t−1, or she died in her own move at t. The test is safe because a living queen that moved k steps
still covers h with her k-th segment whenever k ≤ L_after − 1. Free steps alone always satisfy this, since
ceil(L/4) < L. Only a queen that pays for **f + 2p ≥ L** steps (p = paid steps) uncovers h, which queens almost
never do. The pearl test also covers that case and the portal case: a queen that left through a portal still has
segments on h, and a dead one leaves a pearl. Because queens move first, a drone that sees her this round usually
witnesses the death **in the same round**.

**(b) Heartbeat silence: weak, and it needs heartbeats from r0 [R/U].** f1's queen broadcasts T_QUEEN on 4 rays only
from **r100** (f1:1832). But half of all top-game queen deaths happen before r45 (median 45) [M], so silence cannot
detect those. If silence is used, the queen must beat from r0. Before r100, one ray alternating N/E/S/W is enough to
keep some radar; from r100, 4 rays. Rule: if this dragon has received ≥3 heartbeats in the last 20 rounds and then
none (direct or relayed, age-corrected) for S rounds, mark *suspected*. Suspected changes only local hunting weight.
It is never broadcast and never starts an election. S is **[U]**: measure the inter-arrival times of authenticated
T_QUEEN hits per drone in f1 replays first.

**(c) Death notice flood: needed so far drones switch mode [R].** A witness from (a) seals a QSTATE word (layout
below) on all 4 rays for 3 turns. Every receiver merges it and re-sends it on its own rays at low priority, below an
enemy-queen fix and above a stale relay. **A death is permanent**, so a true notice can never go stale. The only
harmful case is a *false* witness. Refutation rule: a T_QUEEN heartbeat whose `reportRound > d` refutes every death
claim with round ≤ d. Store `refutedUpTo` and ignore claims with d ≤ refutedUpTo. A real death is never followed by a
heartbeat, so a real claim is never refuted.

`UNIT_COUNT` cannot confirm a death: it falls on every drone death.

---

## 4. What breaks or goes idle in vB19 / f1 after our queen dies [R, line numbers f1 unless noted]

| Code | After her death |
|---|---|
| `tryFeed` (f1:1487-1500): sink = visible id 0/1 of our team, `ROUND − trueQueenRound ≤ 30` | **No feeding at all**, for the rest of the game. In the both-dead state (the most common r500 state, and the only state on Autarky/Dilemma/Slithery from r10) no consolidation happens. |
| `protectedQueen()` (f1:91) = true queen only | **No dragon is protected.** The longest dragon keeps budding (`swarmSplit`/`trySplit`, f1:1785-1786) and `doomedSplit` thresholds stay normal. y7's "longest never splits from protectFrom" is gone. |
| Feed homing (f1:1667-1674): goal = `trueQueenCell` while ≤ 25 rounds old | **Ghost homing** for 25 rounds toward her last cell. This is partly useful: her death drops pearls there. Then it stops. |
| `qCell` pearl bias (f1:967) | Biases toward the ghost cell for 25 rounds. Harmless. |
| QPOS landing buffer (f1:1701, ≤ 6 rounds) | Expires. Harmless. |
| Relay (f1:1843-1847, ≤ 6 rounds) | Stops. vB19's plaintext relay (vB19:1858) keeps resending a stale cell **forever from r300**, wasting rays. |
| PQ portal guard (f1:1166) uses the **old `queen` election struct** (`isQueenId(queen.id)`), where `queen` = longest known friend (`considerQueen`, f1:1464-1480) | Already wrong while she lives: it fires only when the true queen happens to be the longest friend. After her death `queen.id ≥ 2`, so it is off. It should read `trueQueenCell/Round`. The `queen` struct and `updateQueen()` (f1:1572) are otherwise dead weight. Remove them, or reuse them as the both-dead keeper belief. |
| `iAmQueen()` = `isTrueQueen()` | COMPASS exclusion: fine. |
| ROW/CROWD give-way (f1:1169-1176) | Needs a visible queen, so it goes inactive. Correct. |
| `castRadar` 1 (queen beacons) | Stops (she is dead). EQ alert continues. |
| `findAttack` `desperate && !(endgame() && MY_LEN > dr.estLen)` | Old longest-dragon guard, still sensible in the both-dead state. |
| `hunt` term (f1:1073-1083): eq weight 4, **no `isTrueQueen()` exclusion** | Before her death, **our own queen (L ≤ 5) is pulled toward the enemy queen's neighbour cells**. QHIDE's −500/−250 usually outweighs this pull. Queen-vs-queen head-ons happened 16 times in top games [M]. Exclude the true queen from `hunt`. |

**Audit of the older builds (election while the queen lives).** In `baselines/y7_12_nn1`, `experiments/signed_sonar`
and `experiments/pearl_gossip` (Y.7.12.3), `queen` is an **elected longest dragon**. It is gossiped on 4 rays from
r300 (`packQueen(queen)`, y7_12_nn1:1511; signed in signed_sonar:1524), and feeding, protection and `meQueen`
all key off it. Under the new rules the whole election is **wrong while the true queen lives**: it feeds and protects
the longest drone, not id 0/1. vB19 kept the receive side (vB19:1482-1491, plaintext QMAGIC `0xB0C7`, which y7-lineage
opponents still send, so self-play can poison it) but uses it only in PQ. f1 removed the codecs (f1:1418) but kept
`considerQueen`/`updateQueen` with only self and visible friends as input. **Nothing in f1 sends or needs an election
while the queen is alive.** What remains is the PQ misuse and wasted CPU.

---

## 5. Message spec (msgauth v1, 23 data bits; type in the authenticated header)

All words are sealed with `msgauth::seal`. Receivers reject words with non-zero reserved bits, a cell out of bounds,
or `age > 31`. Relays **keep the original observation time** (f1b's age encoding) and never re-stamp it.

| Type (3 bits) | Name | Data bits | When |
|---|---|---|---|
| 3 `T_QUEEN` | heartbeat | `x[0:5] y[6:11] age[12:16] len[17:22]=min(L,63)` | Queen: every turn from r0 (1 ray before r100, 4 after). Relays: age ≤ 6. `len` tells feeders whether she is worth feeding. Today f1 requires bits 17-22 = 0, so this needs a version bump. |
| 2 `T_GIANT` | enemy-queen fix | `x y age[12:16] facing[17:18] lenB[19:22]=min(L,15)` | Any dragon that sees her, on all rays, in the same turn. Relays: age ≤ 4. Facing allows dead reckoning; her length matters only for her own reach. |
| 6 `T_HANDOFF` | QSTATE | `ourDeath[0:8] enDeath[9:17] wOur[18] wEn[19] rsv[20:22]=0`; death round 0..499, `0x1FF` = not known dead; `w` = 1 for a vision-witnessed death | Witness: 3 turns on 4 rays. Others: one ray per turn, low priority. Merge with min(), subject to the refutation rule (section 3). Accept only `death ≤ m.round`. |
| 5 `T_CLAIM` | keeper claim | `x y age[12:16] len[17:22]` | **Only in the both-dead state**, only from a dragon that passes the local keeper rule, and not relayed past age 8. The claimant has no id field (relays would overwrite the header sender), so ties go to the lower `y·W + x`. **Hysteresis:** a challenger replaces the incumbent only if it is ≥ 2 longer, and a feeder keeps its target for ≥ 10 rounds. |

**Failure modes:**
- **Two claimants:** both grow. Only the longer one counts at r500. The loss is the mass fed to the other, and
  hysteresis plus vision-gated feeding keep it small.
- **Stale death notice:** a death cannot be undone, so a stale *true* notice is still correct. A false notice is
  refuted by the next heartbeat. The remaining risk is a queen whose heartbeats reach no one while a false witness
  floods. Mitigation: only a `w = 1` (vision-witnessed, pearl-confirmed) claim may start the all-in hunt.
  Silence-only suspicion never does.
- **Enemy forging:** the 24-bit tag over a 2-round window gives about 2/2^24 per attempt [R msgauth.hpp:12-16].
  Replaying a captured QSTATE within 2 rounds only re-asserts a true fact. A replayed T_QUEEN is at most 2 rounds old
  and carries its age. The remaining exposure is metadata: f1 sends the **12-bit sender id in clear**, so queen words
  stand out as sender 0 or 1. Use a keyed 12-bit nonce instead (sonar_echo_tactics.md §3.1).
- **Swapped ids:** never derive queen ids from `MY_TEAM` (55% wrong on the ladder [M]). Initial dragons can use parity
  (`ourQueen = MY_ID & 1`, valid only while `MY_ID < DRAGON_COUNT`), but no decision above needs it.

---

## 6. Task B: hunting the enemy queen

### 6.1 How enemy queens die under the new rules [M, 306 top-team games, 612 queens]

- 554/612 queens die (91%): winners' queens 252/306 (82%), losers' 302/306 (99%). Median death round: winners 31,
  losers 57.5. Death-round bins over all queens: r0 6, r1-10 198, r11-50 83, r51-100 112, r101-200 90, r201-300 37,
  r301-400 15, r401-500 13.
- **By r10 (trapped starts):** all 62 Autarky, 60 Dilemma and 62 Slithery queens are dead (wall 119, self 63,
  no-valid-action 2). On Default, 15 die in round 0-9 head-ons (spawns face each other).
- **After r10 (350 deaths):** rammed by an enemy dragon **139 (40%)**; the queen moving into an enemy head 42 (12%);
  hit wall 75 (21%); hit self 39 (11%); hit other body 29 (8%; 3 are enemy bodies, some unresolved through
  portals); own-team head-ons 20 (6%); no valid action 6.
- **Killers in enemy-moved rams (148):** length 2: 50, 3: 77, 4: 10, 5-11: 11. Victim queen length mostly 2-4.
  The longest queens killed were 34 (Trauma r233), 24, 21 and 17. **Winners' drones rammed the loser's queen in 99
  of these 148.**
- **Steps in the ramming move (139 after r10):** 1 step: 63, 2: 58, 3: 11, 4: 4, 5: 3. **76 needed paid steps.**
- **Rammed share, queens vs others:** queens 40% of post-r10 deaths, ordinary dragons 8%. This is strong evidence
  that top teams aim drones at queens. calc's writeup says its far drones "hunt and ram the enemy's longest dragon"
  [calc WRITEUP.md:89].
- Queen alive at the end by winning team: Computers 10/22, Sponge 9/28, C-- 8/20, ???????? 7/20, Cache 7/29,
  Stockfish 5/39, Delusion Tax 0/27, 3.14 0/26. Our 18 wins in scout_v6/own: we rammed 8 of 18 enemy queens, and
  our own queen died "hit self" 6 times (r5 trapped starts).

### 6.2 Detection channels

| Channel | What it gives | Notes |
|---|---|---|
| Vision | exact head, body, facing, length (`team ≠ ours`, `id ≤ 1`) | Robust on swapped maps. Exact for the rest of the round, because she has already moved [R]. |
| Our T_GIANT relay | head and age, plus facing and length in the spec above | A receiver with a higher id than the spotter gets a fix that is exact this round. |
| Echo `enemy_head` | "some ray hit an enemy head" | No id, so it cannot single out the queen. |
| Enemy plaintext | Stockfish sends the sender's head x/y in clear (79% exact, 13 queen words/game reach opponents); horse sends the sender id in clear (66%) | horse words with sender id 0/1 are **queen words**. A word arrives only along a ray, so the queen lies on a line through the hit segment [M sonar_echo_tactics.md]. Format learning is opponent-specific. |
| Dead reckoning | Between fixes she covers ≤ ceil(Lq/4) cells per round (paid sprints are rare for queens). Possible set = walking ball of radius `age·ceil(Lq/4)` from the last fix, minus kelp and bodies; facing narrows it. | A small queen moves 1 cell per round, as fast as an L ≤ 4 hunter, so a single chaser does not close the gap. |

### 6.3 Interception math [R]

- **Strike condition:** at my turn, a free path from my head to her head of length k ≤ R(L) exists in my view
  (cells not occupied now; my own body as `simulate` handles it; portal steps allowed). Every step of the path is
  then exact, because nobody else moves during my turn. The last step must be a payable step, and R(L) already
  enforces that.
- **Cost:** my drone (L length, 1 unit) dies, and so does she. Both drop pearls: ceil(Lq/2) at her body, ceil(L/2)
  at mine. Her pearls feed whoever is close, often her escorts.
- **Approach:** hold position at walking distance ≈ R(L) + 1 from her predicted head *without entering her view*.
  QHIDE-style queens flee visible heads. The next round, after she moves, strike if k ≤ R(L).
- **Hunter choice:** an L4-6 drone has R = 3-6 for one unit. An L2 has R = 1 and must be adjacent. A queen's own
  2-step danger zone (QHIDE `ed ≤ 2`) is outside an L3+ drone's reach and does not account for them.
- **Cooperation, with no messages beyond T_GIANT:** hunter i aims at her predicted head offset by approach direction
  `(id mod 4)`, so three or four hunters close from different sides and a fleeing queen runs into one of them.
  Cap concurrent hunters at `min(4, UNITS/6)` (see FLOOR).
- **Queen vs queen:** never. A head-on kills both, which moves the game to tiebreak 2.

### 6.4 When a kamikaze is worth it

| State | Value of killing her |
|---|---|
| ourQ alive, enQ alive | Converts "longer queen wins" into a near-certain win if ours survives (enemy 0). **Always worth one drone** unless FLOOR applies. |
| ourQ dead, enQ alive | Converts a certain r500 loss into a tiebreak-2 contest. **Worth almost any price.** |
| ourQ alive, enQ dead | n/a |
| both dead | Hunt their *longest* dragon instead, and only when `estLen ≥ MY_LEN + 2`. That is the existing `findAttack` / `endgame()` logic. |

The large head is not what matters. A head-on kills her at any length, so a length-2 drone for a length-30 queen is
the same trade as for a length-2 queen. The difference is only in the pearls she drops.

### 6.5 Existing code against this design

- **`findAttack` (f1:1229-1270):** `worth = true` for any enemy queen when `UNITS ≥ 2`. Good. But the search is capped
  at `maxSteps = min(attackMaxSteps = 4, MY_LEN − 1)` with a `torusDist ≤ 4` prefilter. True reach is R(L): an L5
  drone reaches 5 and an L8 reaches 8. Enumerating 4^k direction codes is too costly beyond k = 5, so use a BFS
  over free cells to her head, cut off at R(L).
- **Homing (f1:1677-1680), the "known defect":** this is only **partly** a defect [R]. For the head cell,
  `otherBT[head] = 0 + extra + 1 + eatMargin` (f1:625), so `distA[eqHead]` is −1 only within roughly
  1 + extra + eatMargin steps. A message-only fix outside our view has no `otherBT` and homes normally. The gap is
  close range inside our view, beyond R(L): there homing sets no goal and the drone relies on the `hunt` term (which
  does target her free neighbours, f1:1078-1081). Fix: target the free neighbour with the smallest `distA` (the same
  fix as V6 feeding), widen the radius from 10 to unlimited in the dead/alive state, and allow fixes up to age 6
  under dead reckoning. Before ranking this, count ATK-on-queen and homing goal events in replays: AGENT_LOG
  b19_v6 shows critic claims like this one need a count first.
- **`hunt` / eq / PRESS2 (f1:1073-1083):** eq gives weight 4 within `huntMaxLen = 5` and ignores the length margin.
  PRESS2 makes any trade worth it at ≥ 30 units. Missing: (1) exclude the true queen from `hunt`; (2) let L6+ drones
  hunt the queen too, since their R is large.
- **Queen defence (QHIDE f1:1134-1160, danger f1:1043-1062):** the reach model `buildReaches` (f1:783-804) uses
  free-step speed only, `spd = ceil(L/4)`, with `dd = turns`. Rams that pay steps are mostly covered by
  `dd ≤ er.len − 1` and `dd ≤ 2 → +300`, but an L5-8 enemy at walking distance 5-8 can strike with certainty and gets
  only the p3 weight. Replace it, for the queen only, with an exact "can strike this round" mask: walking distance
  ≤ R(Le) through free cells. Enemies outside her view with R ≥ 4 (L ≥ 4) need friends' sightings: an "enemy head
  near our queen" alert (sonar_echo_tactics.md §3.3).

---

## 7. The three cheapest experiments

All on `panel_zig.py --judge zig`, vs vB19 (or f1) as control, `--set live` and `--set dev`, seeds 1-2, both sides
(80 games). Metrics come from replay counts using the section 6.1 logic. The researcher's read-only script is in the
session scratchpad (`queen_deaths.py`, not committed). An executor should add it as `tools/queen_deaths.py`. It
tracks bodies from `dragonUpdate` plus action dirs, and attributes `head to head` and `hit other body` deaths to the
mover or to the occupant of the cell entered.

| # | Change (lines) | Primary metric | Secondary |
|---|---|---|---|
| E1 | **Strike reach:** in `findAttack`, for queen targets only, BFS to her head with cutoff R(L) instead of the 4-step code enumeration and the `torusDist ≤ 4` prefilter; exclude our queen from `hunt` (~25 lines) | **enemy-queen kills per game** by our drones, and the round distribution of the kills | win rate; our units at r100/r300 (cost); CPU max ≤ 65M |
| E2 | **Post-death modes, vision witness only (no messages):** detect deaths with the pearl test (section 3a). Dead/alive → homing radius unlimited, all drones `eq` weight ×2. Both dead → y7 keeper back on (protect the longest from `protectFrom`, vision-gated feeding with FLOOR) (~50 lines) | **win rate in games where our queen dies before r300**, and in both-dead r500 games our longest minus their longest at r500 | Autarky/Dilemma/Slithery separately (both dead by r10, so E2 is the whole game there) |
| E3 | **Queen defence with exact reach:** queen-only strike mask (walking distance ≤ R(Le)), hard-excluded like `ed ≤ 1` (~20 lines) | **our queen's death round** (median, % alive at r300/r500); share of her deaths that are rams | queen eats (QHIDE already sets her greed ×0.2) |

Messages (QSTATE, T_CLAIM, heartbeat length) come after E2 shows the modes matter. They extend the mode switch to
drones that never witness a death.

**Zero-code baseline first:** run the section 6.1 counter on existing local panels (vB19 vs y7_12_49 replays under
`out/`) to get our current enemy-queen kills per game and queen-death-round distribution. Then E1-E3 have a
reference point.

---

## 8. Risks

- **Suiciding drones lose units.** Elimination beats every tiebreak. The FLOOR precedent (y7_12_49:1402: feeding
  took us from 22 to 6 units among 62 enemies and we were eliminated) applies equally to kamikazes. Allow at most
  `min(4, UNITS/6)` concurrent hunters, and none below 4 units unless our queen is dead (then the game is lost
  anyway). Never send the last two units.
- **Her pearls feed her escorts.** A kill inside her swarm hands ceil(Lq/2) pearls to enemy drones. That matters only
  in the both-dead state, where totals count.
- **Hunters leave the economy.** Winners' queens die too (82%), so a hunt that costs our own growth may lose
  tiebreak 2. Measure units and total length at r300 in E1.
- **Our queen drawn toward theirs** (`hunt` has no queen exclusion): queen-vs-queen head-ons happened 16 times [M].
- **False death witness:** portal exits and paid sprints. Mitigated by the pearl test plus heartbeat refutation.
  E2's mode switch is irreversible only for `w = 1` claims.
- **Ghost homing on stale fixes:** keep the age limits (4-6), and use dead-reckoning balls rather than the raw cell.
- **CPU:** a BFS to R ≤ 13 is negligible. Do not enumerate 4^k paths for k > 4.
- **Metadata leak:** the sender id in clear marks queen words (section 5).
- **Ladder ≠ local:** local panels carry about 7pp of optimism (post-mortem memory). Confirm any E1-E3 gain with a
  same-time ladder control.

**Unverified items:** the silence threshold S; how often an enemy queen enters any of our drones' view per game (not
measured; it needs a vision replay); whether the E1 reach gain shows up as kills against QHIDE-style queens; the
"homing never fires" count (section 6.5, needs indicator counts).
