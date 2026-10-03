# Open-map late-game growth: turn the swarm into a winner

**Status:** first research draft, 30 Sept 2026. This is a design note, not a measured result. No candidate behavior is established below. The target is the observed open-map gap: convert distributed mass and expendable units into one surviving dragon that is at least 45 long by round 500.

## 1. Problem framing

Our open-map losses are not explained by crowding around the leader: our longest has fewer allied heads within four cells (1.0 vs 1.3), almost the same free neighboring cells (2.6 vs 2.5), and similar movement. The team often ends with more total mass, but longest median 19 vs opponents' 33. Top-team trajectories imply a deliberate late-game transfer: about 60 units at r300, 35 at r350, 18 at r400, 7 at r500; their longest grows roughly 11 → 25 → 37 → 48. The r400 leader survives to the end only 26/54 times, so the protocol must support succession rather than assume one immortal queen.

The crucial mechanic is that an illegal action kills its dragon and drops `ceil(L/2)` pearls. Therefore “feeding” is a routing-and-timing problem: place a dying dragon's pearls where the current sink can collect them, while ensuring feed pearls survive long enough to be consumed. With a 7×7 observation and sonar messages, no unit sees the whole swarm; protocols must use deterministic distributed decisions and tolerate stale information. Sonar is not broadcast: each dragon sends up to four directional rays; rays stop at the first dragon part or kelp, and a recipient reads the message on its next turn. Gossip therefore propagates only through encountered relays, can be delayed by turn order, and can miss isolated feeders. Pearl countdowns are visible only on inspectable tiles; map spawn gap bounds are map properties, and a countdown resets after each spawn attempt whether it succeeds or not. A route can estimate opportunities but cannot know exact future pearl timing globally.

### What current `cand_y10o` does

- Open-map `swarmSplit()` stops budding at `P.budUntil` (290); open-map `tryFeed()` can begin at r300.
- `updateQueen()` merges local friendly heads and sonar gossip into one record `(id, cell, len, round)`, preferring the longest (ties by lower id); queen freshness is checked at 25/30 rounds.
- `tryFeed()` directly kills a non-queen via `SPLIT 1` only when the queen is locally visible within distance 3. This is an intentionally illegal split used as suicide/pearl drop.
- Otherwise, `think()` sets `feeding` when the queen is longer, fresh, and within `P.feedRadius` (25), then homes to the queen's cell (or a nearby open goal). `evaluate()` rewards progress to that goal and scores growth / risk.
- Thus the current policy has global intention but only a local, opportunistic death trigger. It does not assign arrival times, choose a stable feeding site, create relay roles, or ensure drops lie on the sink's future path. Its gossip round is the message's observation round, not a proof the target is still alive.

Relevant code: `cand_y10o/main.cpp`, `updateQueen()` / `considerQueen()` around lines 1310–1346; `tryFeed()` around 1355–1369; `think()` around 1433 onward; the `feeding`/homing goal setup around 1483–1513; `evaluate()` around 892–1063. Similar locations exist in `cand_y10/main.cpp`; `cand_y10o` is the open-map variant named in the task.

## 2. Research patterns and what transfers

These are analogies, not evidence that a particular Battlecode rule wins.

1. **Convergecast / aggregation trees:** sensor-network protocols route many source readings toward a sink through a tree; intermediate nodes combine traffic, and topology/latency/energy are explicit costs. Transfer: treat feed-capable dragons as leaves, queen as sink, and use at most one relay tier when direct travel is too slow. Unlike packets, a dragon is consumed and a relay can die, so a relay must be a deliberate collector with enough length and a safe location. [Overview of in-network aggregation and convergecast](https://journals.sagepub.com/doi/10.1155/2012/429719), [optimal data aggregation trees paper](https://ira.lib.polyu.edu.hk/bitstream/10397/794/1/optimal-data_06.pdf).

2. **Swarm aggregation, rendezvous, and leader-following:** decentralized systems can gather agents using local observations and sparse neighbor relations; a uniquely agreed leader can provide a target, but stale or ambiguous election is a failure mode. Transfer: use deterministic `(length descending, id ascending)` election already present, with a freshness lease and a succession rule; move the sink toward a rendezvous site only if its local path remains safe. [Leader election and gathering under limited robot assumptions](https://arxiv.org/abs/1208.4484), [leader-follower swarm navigation with local sensing](https://arxiv.org/abs/2101.07416).

3. **Stigmergy / indirect recruitment:** swarm systems often coordinate by modifying shared environment cues rather than requiring a central controller. This game has no persistent pheromone channel, but pearl drops and visible bodies are environmental cues; sonar is the direct short message. Transfer: make a “feed marker” be a reproducible location/time rule (queen id + rendezvous cell + round window) carried by gossip, and use dropped pearls as the actual local signal. Avoid relying on a single visual cue because pearls may be hidden outside 7×7 vision. [Stigmergy-based swarm behaviours](https://www.nature.com/articles/s44172-024-00175-7), [swarm recruitment under vision/communication uncertainty](https://etheses.whiterose.ac.uk/id/eprint/28028/1/Obute_SO_Computing_PhD_2020.pdf).

4. **Leader election under partial observation:** full visibility is a strong assumption in many gathering algorithms. Here consensus is only eventual through sonar, so election should be stable under delayed updates and tied to an ID. Transfer: never allow each drone to independently crown itself merely because it has not heard gossip recently; require a lease expiration plus a known successor candidate and hysteresis. Current `considerQueen()` tie-break and 25-round age check are a good foundation, but messages do not encode a lease/epoch or death proof. [Gathering and election paper (assumptions explicitly include full visibility)](https://arxiv.org/abs/1208.4484).

5. **RTS merging and endgame resource conversion:** StarCraft's Archon is a direct example of sacrificing two units to produce one stronger unit; crucially the merge takes time and leaves participants vulnerable. Transfer: the value is not “keep every unit alive” but “convert units at a moment/place where the stronger unit benefits”; in Battlecode the conversion is pearls dropped by death rather than a literal merge. Account for conversion delay and exposure. [Official StarCraft Archon description and merge vulnerability](https://classic.battle.net/scc/protoss/units/archon.shtml).

6. **Snake growth heuristics:** snake agents balance food collection against the shrinking space and future collision risk created by growth. This game reverses the usual end objective: a team needs one long snake, and death itself can be a resource transfer. Transfer: evaluate food/drop routes by expected growth and survival of the recipient, not by raw pearl pickup or unit count. [Battlesnake rules: food grows the snake and growth makes movement space harder](https://docs.battlesnake.com/rules).

7. **Lux / Halite game AI:** Lux is a multi-unit resource-management game where units create/maintain city tiles; Halite-style games make ships choose between mining, movement, and conversion. The useful general pattern is explicit phase switching and comparing the remaining value of a worker against its converted late-game contribution. Public material found here does not document a proven “cash-in” policy matching our mechanic, so these are broad design analogies only. [Lux AI Season 1 rules overview](https://www.kaggle.com/competitions/lux-ai-2021/overview/description), [Halite IV resource and conversion example](https://schnack.dev/blog/kaggle/halite-iv-resource-management/).

## 3. Candidate protocols

All three should be open-map-only first (`Portals`, `Slithery Fight`, `Schooltime`) and preserve current maze behavior. Each process can use its own `MY_ID`, `MY_LEN`, position/body, map knowledge, current 7×7 tiles, currently visible friendly heads, current round, and decoded sonar queen gossip `(id, cell, len, round)`. It cannot know unseen live positions, exact unseen path obstacles, whether a gossiped queen has died since its report, or what another unit will choose. `torusDist` is only a geometric lower bound; the path planner / `distA` can account for known map topology, not hidden dragons.

### Protocol A — rendezvous plus moving feeding front (best first candidate)

**Idea:** elect the sink as now, but let it move through a short, safe pearl-rich route while feeders stage ahead of it. A feeder dies only when the sink is in verified pickup range, at the agreed rendezvous cell, and the drop can be reached before the pearls are lost. This addresses the present gap between global homing and strictly local feeding.

**Rules, per dragon:**

1. **Election:** keep existing max `(len desc, id asc)`; accept a queen gossip record only if its round is not in the future and age ≤ 12 during consolidation. If local observation sees that id alive, refresh cell/length. If it is unseen, do not assume death; after age 12, move to successor election only if the local candidate is at least as long as the stale record, otherwise wait / retain ordinary foraging (prevents an inferior drone from self-appointing). Keep `queen.id` and the winner tuple in every sonar broadcast; relay the freshest valid record on every turn because each ray is point-to-point and may hit a different subset of agents.
2. **Sink route:** queen computes candidate next cells using existing safe movement evaluations, plus a small lookahead (3–6 path steps) over countdowns on inspectable tiles and map spawn-gap priors elsewhere. Score route as expected pearl length gain minus death risk and detour; treat unseen spawn times as uncertain and avoid revisiting its last 6 cells. Publish only its current head, length, id and round (existing payload) so other units project a short route from the latest heading when seen, otherwise treat cell as a rendezvous anchor, not a guaranteed trajectory.
3. **Feeder staging:** when `ROUND >= 300`, you are not queen, queen is fresh (≤12 rounds), and queen length < 45, set feed intent. Move toward a staging cell 2–4 steps ahead of the queen along its last observed heading, but only if reachable in ≤ `min(20, 2*torusDist+4)` safe steps. Keep farming if estimated route is longer or target stale. As queen approaches, update the staging target each turn; do not chase a moving point beyond feed radius.
4. **Commit suicide:** perform illegal `SPLIT 1` only when queen is currently visible as a friendly head or was sonar-refreshed within 2 rounds *and* current known queen head is within 2 cells of the intended pearl drop cell, and a simulated queen route can cross at least one drop cell within 1–3 turns. For the first implementation, restrict to queen within 2 and a directly observed clear neighbor corridor; it is safer than speculative remote feeding. Indicator records `FEED_FRONT:<queen_id>:<round>`.
5. **Queen pickup:** `evaluate()` gives strong growth value to a pearl known to come from a feed drop (if visible, or infer with the shared deterministic feed-window cell); accept a route that collects drops even if it turns away from the center. If incoming pearl timing is not known, prioritize avoiding death and collect ordinary pearls.
6. **Succession:** if a feed dies and newer gossip names a longer living candidate, switch. A would-be queen broadcasts its own record immediately; require two observations / local friendly-head confirmation before routing the swarm to a newly elected candidate. Never feed into a shorter queen based solely on stale gossip.

**Code insertion:** `updateQueen()` handles freshness and hysteresis / successor validation; add `FeedPlan {sinkId, anchorCell, eta, phase}` to queen gossip only if bit budget allows (otherwise retain current message and derive phase from round + queen cell). In `think()`, branch after `updateQueen()` and before ordinary target selection: sink-route scoring; feeders' staging goal. Replace the current distance-only `tryFeed()` guard with a `shouldFeedNow()` that checks observed sink proximity and simulated short pickup path. In `evaluate()`, when `homingToQueen` or sink role is active, score expected pickup of pearls on the planned route; keep all ordinary safety classes intact.

**Why this is plausible / main risk:** the mass is moved into a queue in front of a moving consumer rather than asking the consumer to sit on a pile. Main risk is the reports' queen cell lag / route projection error; initial version therefore makes death commitment local and conservative. It may initially feed too slowly; measure pearl pickup latency before widening the trigger.

### Protocol B — two-hop collector tree (for far-flung units)

**Idea:** direct homing can waste the finite 200-round window on distant workers. Choose up to 2 collectors between remote feeders and sink. Collectors gather small drones' dropped pearls locally, then themselves feed to the sink late. This is a literal convergecast tree, but only one relay tier: extra tiers consume time and create stale-target failures.

**Rules, per dragon:**

1. Sink is elected by the same tuple and moves to a safe central / pearl-rich rendezvous cell chosen from the known map: maximize reachable pearl countdown value over a 10-step horizon, minimize expected distance from visible friendly heads (a proxy only), and penalize low-degree/trap regions. Do not relocate after r380 unless current site is unsafe.
2. Candidate collector is non-queen with `MY_LEN >= 6`, visible or recently gossiped as alive, and has a shorter route to a cluster of visible friends than the queen. Deterministic collector election: rank candidates by (travel distance from candidate to sink ascending, length descending, id ascending), using observed / gossiped candidates; at most one collector per 8×8 map region by `id` modulo region count. Collector role expires after 20 rounds without a fresh self-broadcast.
3. Small feeders (`MY_LEN <= 5`) choose direct sink if estimated safe travel ≤ 12; otherwise home to the elected collector if it is fresher and at least 3 cells closer. They suicide only within 2 cells of their collector, with local head confirmation. Collector picks up these pearls and ordinary pearls, maintains length; when its length reaches `max(10, sinkLen-3)` or round 390, it becomes a feeder to sink. If collector is now the longest it becomes sink by ordinary election; never deliberately destroy the current longest to feed a shorter stale target.
4. Limit concurrent collectors and retain at least one direct feeder lane. On maps where only one collector wins the election, another nearest candidate stays on direct homing to prevent total dependence on a single relay.
5. No collector should camp on the queen's body or route through it; `evaluate()` retains body occupancy and danger costs. A collector should park in open cells within distance 2–4 of sink, not in the sink's next 4-cell path.

**Code insertion:** extend queen gossip payload to a role tuple `(role, parentId, targetId, cell, len, round, epoch)` or compactly encode the collector's own `(id, cell, len, round)` and derive role from deterministic ranking. Add `updateRelay()` next to `updateQueen()`; call it from `think()`. Generalize `tryFeed()` to target either sink or collector, with parent id in the suicide indicator. Add collector gather goal to `think()`'s goal selection; use `evaluate()` to favor incoming feed pearls but penalize being parked in sink path. The current static `QueenInfo` should become a `TargetInfo` only if this protocol demonstrates value; avoid premature refactor.

**Why this is plausible / main risk:** it cuts long feeder travel and gives near-field units an intermediate consumer. Main risk is an extra conversion hop reducing total growth due to travel and pearl loss, plus split-brain collectors from partial visibility. Keep a maximum of two collectors and compare against Protocol A; do not build a deep tree.

### Protocol C — time-batched death drops along a fixed rendezvous corridor

**Idea:** a low-complexity fallback that needs little path prediction: queen chooses a stable open corridor/rich region and broadcasts the target; units arrive by distance bands, then die in staggered windows so the queen collects one batch before the next arrives. This is a distributed schedule, not a permanently moving sink.

**Rules, per dragon:**

1. At r300, queen chooses a rendezvous cell within 5 cells of itself from globally known map geometry and its own visible pearls: maximize local open degree + known pearl countdown reward; tie by lowest cell index. Hold near that cell until r420 unless threat or blocked; then follow Protocol A's moving-front rule.
2. Each non-queen computes shortest known-map distance `d` to rendezvous, then arrival window `300 + clamp(d*2, 0, 80) + (MY_ID % 6)*3`. Before its window, continue mining if a good pearl is visible and stay alive. In its 12-round window, home toward an adjacent drop cell. Suicide only if queen is visible within 2, or its latest queen gossip is ≤2 rounds old and the target cell is adjacent to the actual sink; never suicide on the distant rendezvous estimate alone.
3. Queen rotates among its safe adjacent cells using a deterministic 3–5-cell loop that leaves at least one forward escape cell. Do not stand stationary in the middle of a death pile. A dropped pearl patch is consumed before next batch when its visible count is falling or queen has moved across it; if not, delay next batch by 6 rounds.
4. From r420 on, all remaining units home directly; from r470, only feed on immediate local confirmation. Sink election / succession remains active throughout.

**Code insertion:** choose / retain rendezvous in `think()` after `updateQueen()`; derive each unit's phase from `ROUND`, `MY_ID`, map distance and queen gossip. Use existing `goalCell` and `homingToQueen` for route scoring, but distinguish `rendezvousCell` from queen's moving cell. `tryFeed()` enforces the narrow suicide window. `evaluate()` values locally observed pearls and corridor safety; do not make the network override safety.

**Why this is plausible / main risk:** low coordination complexity, allows far units to arrive in a planned order. Main risk is that all units estimate the same path distance from incomplete map knowledge, causing clumps or waits, and that static camps attract enemy pressure / constrain queen escape.

## 4. Replay verification: prove the transfer, not just the final score

Instrument indicators sparsely (event-only, not every turn) and extract a per-round team ledger from replay. For each game and each team, calculate:

### Primary outcomes

- Win/draw/loss; final longest length; final total length; longest length at r300, 325, 350, 375, 400, 425, 450, 475, 499.
- `longest_len(t)` trajectory and ID; count queen handoffs; fraction of games where elected sink survives to r500.
- Growth target: `maxLen(500) - maxLen(300)`; desired ≈ +34 or higher from ~11 to ≥45, but report starting longest so comparisons are fair.
- Team units and mass trajectories at each checkpoint; retain enough units to keep finding food, but avoid maximizing these at the cost of the longest.

### Transfer efficiency and timing

- Death counts by cause, round band (300–349 / 350–399 / 400–449 / 450–499), and dragon length at death; distinguish deliberate illegal-feed deaths from collision / trap / timeout.
- For each deliberate feed: feeder id/length, target sink id, sink length and distance at death, pearl count dropped (`ceil(L/2)`), drop-cell list/centroid, whether the current sink consumed any dropped pearl, rounds from drop to first pickup, total dropped pearls actually consumed by sink, and pearls lost / left at r500.
- Feed conversion efficiency = sink growth credited to feed-drop pearls / pearls dropped; also report total pearl-to-sink growth per game and feed travel turns. Avoid counting ordinary ambient pearls as feed success.
- Number of feed events that target the elected sink vs stale/dead/wrong sink; proportion of feeder deaths occurring before sink arrives, after sink passes, or within pickup window.
- Longest growth source split: ordinary fountain pearls, feeder drops, collector drops. Estimate by replay body growth/pickup events and matched drop cells; mark ambiguous cases separately.

### Protocol operation and safety

- Freshness of queen records when acted on; stale-target switches; split-brain duration (different allies' indicators naming different sink ids); succession delay after sink death.
- Feeder route length (actual steps), geometric distance at intent start, homing completion / failure, congestion isn't assumed—record body blocks, path invalidation, and route detours.
- Sink survival hazard: death cause/round, enemy head distance and estimated length, allied heads within radius 4, free exits at head, own-body collision/trap, blocked-route count. This directly checks the prior false crowding hypothesis while comparing to the actual suspected growth failure.
- Feeders diverted from productive farming: visible pearls passed, estimated pearl value, and turns spent homing vs mining.
- Record indicators with role and event (`SINK`, `RELAY`, `STAGE`, `FEED`, `PICKUP`, `SUCCESSION`) plus tuple `(target_id, target_cell, plan_epoch)` to reconstruct decisions.

### Comparison design

Use matched maps and seeds for baseline `cand_y10o` and one protocol at a time, both sides randomized. Report per-map results, not only aggregate: Slithery Fight is a known weak map, while Schooltime and Portals can behave differently. A protocol “works” only if it increases longest growth / final longest and increases feed-to-sink conversion without reducing wins through sink deaths or lost early economy. If final longest rises but wins do not, inspect enemy giant competition and team wipe outcomes. The key diagnostic plot is `sink length over round` with feed-drop and pickup events overlaid; a raw death count or raw dropped pearls is not proof of successful transfer.

## 5. Suggested implementation order

1. Add replay event indicators / extraction fields first, with no policy change, to establish current `cand_y10o` feed-to-sink conversion and travel/pickup delay.
2. Implement Protocol A narrowly: tighten gossip freshness, stage locally, and make feed commitment require observed sink proximity. Preserve ordinary safety evaluation and all maze rules.
3. Compare conversion efficiency and longest trajectory. Only if many far feeders fail to arrive by r400, prototype Protocol B. If message complexity or split-brain dominates, try Protocol C as the simpler alternative.
4. Keep the experiment's claim precise: a single-source replay demonstrates mechanism, not win-rate improvement; multiple matched games and open-map per-map analysis are needed before promotion.

## Sources

- Yang et al., *An Energy-Efficient and Fault-Tolerant Convergecast Protocol in Wireless Sensor Networks*: https://journals.sagepub.com/doi/10.1155/2012/429719
- *Construction of Optimal Data Aggregation Trees for Wireless Sensor Networks*: https://ira.lib.polyu.edu.hk/bitstream/10397/794/1/optimal-data_06.pdf
- Chaudhuri & Mukhopadhyaya, *Leader Election and Gathering for Asynchronous Transparent Fat Robots without Chirality*: https://arxiv.org/abs/1208.4484
- *Swarm Herding: A Leader-Follower Framework For Multi-Robot Navigation*: https://arxiv.org/abs/2101.07416
- *Automatic design of stigmergy-based behaviours for robot swarms*: https://www.nature.com/articles/s44172-024-00175-7
- Obute, *Swarm Robots Foraging under Vision and Communication Uncertainties*: https://etheses.whiterose.ac.uk/id/eprint/28028/1/Obute_SO_Computing_PhD_2020.pdf
- Blizzard Entertainment, StarCraft Archon unit: https://classic.battle.net/scc/protoss/units/archon.shtml
- Battlesnake official game rules: https://docs.battlesnake.com/rules
- Lux AI 2021 Kaggle challenge overview: https://www.kaggle.com/competitions/lux-ai-2021/overview/description
- Lucas Schnack, Halite IV resource management example: https://schnack.dev/blog/kaggle/halite-iv-resource-management/
