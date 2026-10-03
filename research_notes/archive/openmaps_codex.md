# Open-map swarm and consolidation: independent read

**Evidence timestamp:** 30 Sept 2026, 05:40 IST. This is an interpretation of the supplied aggregates and the Y.10/Y.10o policy description; aggregates do not establish a causal explanation for individual deaths.

## A. What the evidence says

### The strong teams run a two-phase economy

The winning-game medians show an unusually clear phase change. Top teams grow to about 60 bodies by r300, then units fall 60 → 35 → 18 → 7 while the longest dragon rises 7 → 11 → 25 → 37 → 48. Total mass is comparatively preserved (156 at r300, 157 at r350, 126 at r400, 104 at r499). The natural reading is deliberate consolidation: they cash short dragons into pearls for a long dragon, and continue growing that dragon while many other bodies disappear. “Swarm” describes their opening and midgame, not their endgame.

Our open-map losses often fail that conversion. We can finish with 34 bodies and 392 total mass against 14 bodies and 91 mass, yet lose 36 vs 40 on longest length. That is not evidence that our economy is weak in total; it is evidence that the mass is in the wrong places at the scoring deadline, or that our leading dragon dies before then. Across 225 losses, our end median longest is 19 vs their 33, and the r400 leader is lost to feeding, head-ons, traps, and body collisions in substantial numbers. Thus “feed earlier” alone is an incomplete diagnosis: the conversion must produce a durable, growing leader without wasting the pearls or killing the leader.

Y.8m’s 0/30 against the current top six is a warning that its previous overall rating and favorable maps do not describe the current top-end matchup. The per-map records are highly uneven: Slithery is 7/46 for the champion and 4/5 for S.4.7.5; Default and Autarky are relatively strong for the champion. A ten-map average hides this style/map interaction. The weak Slithery history and strong S.4.7.5 Slithery result make open-map consolidation a plausible differentiator, but the samples are not controlled head-to-head evidence and do not prove that feeding explains the gap.

The general gap is likely a combination of (1) earlier and more successful expansion to the 60-body ceiling, and (2) better late conversion, focus, and survival of the scoring dragon. The round-100/200 medians (29/47 bodies) imply that the opening race is already mature before Y.10o’s r290 transition. Y.10o cannot repair an early deficit in bodies, pearls, or position; it can only change what we do with the army we still have.

### What could cause 110 “no valid action” deaths by r300?

That count is consistent with deliberate feeding, especially if the game treats an invalid/degenerate split as a suicide that drops pearls. The scale alone does not establish intent. Other plausible causes are failed split attempts at a blocked tail, trapped drones that have no legal move, a deliberate sacrifice to clear or block a lane, or a policy bug/protocol mismatch. With around 60 units, many bodies also create congestion, so accidental death can coexist with purposeful feeding.

For a small, stratified replay sample, reconstruct each such death and check:

1. **Action and indicator immediately before death:** was the command an explicit feed/`SPLIT 1`, a normal move, another split size, or malformed/absent? Record dragon id, length, round, and whether it was the current queen. Compare with the team's other actions that turn. Repeated explicit feed actions are much stronger evidence of intent than an inferred death label.
2. **Death and pearl outcome:** engine death reason, dropped pearl count/location, and whether a teammate (especially the queen) eats those pearls in the next few turns. Measure pearl recovery and queen length gain, not just deaths. A sacrifice far from the queen that is never recovered is not useful feeding.
3. **Geometry and local alternatives:** distance and reachable path to the queen, body/kelp blockage, empty neighboring cells, tail mobility, nearby enemy heads, and whether a lane or fountain is contested. A trapped drone with no safe move differs from a drone that had open moves but deliberately died.
4. **Temporal pattern:** deaths clustered after a queen appears or at a chosen round/distance support a feed protocol. Deaths scattered from r0, repeated in cul-de-sacs, or preceded by failed budding suggest congestion or a stuck-unit policy. Look for several same-team deaths in one round and whether that opens space for survivors.
5. **Counterfactual value:** from the replay state, estimate whether a legal move/split would have survived and whether the sacrifice improved the final longest length or win. Compare winners and losses, plus open maps separately. Do not infer a tactic from winners alone: the supplied winning-game sample is selected on outcome.

Start with perhaps 10–20 games across the three open maps, including wins and losses, and inspect a few deaths per game at r0–300. Aggregate by action class and follow the resulting pearls. That is enough to discriminate obvious intentional feeding from failed splits/stuck bodies before attempting a large replay scan.

## B. Y.10o critique and concrete refinements

Y.10o’s open-map schedule—stop budding at r290, protect from r290, begin homing/feeding at r300, permit whole-map feed eligibility, and call `tryFeed` when a visible queen is within 3—aims at the right broad phase change. Its main risk is treating “eligible to feed” as equivalent to “pearls delivered to a stable queen.” The supplied leader at r300 is often only length 7, so the change begins exactly when the putative sink may still be small, mobile, or not yet reliably identified.

### Failure modes to watch

- **No stable sink:** If queen identity/position changes, or the reported queen is stale, feeders can home toward different leaders. A stable sink needs persistence, not merely the longest dragon in the current partial view. Require current/fresh queen telemetry and a minimum identity/position persistence window; if the leader dies, select a successor and restart that window.
- **Eligibility without reachable delivery:** A whole-map radius says a dragon may feed, not that it can travel to the queen. Long routes consume rounds in which the feeder can be trapped, killed, or block traffic. Rank candidates by a real traversable path estimate and travel time, and disable feed mode if the ETA exceeds the remaining useful feeding window or the route is congested.
- **The 3-cell trigger is not a pearl-transfer guarantee:** If `tryFeed` emits a deliberate invalid action at distance ≤3, a pearl pile can still land on an occupied/body-blocked cell, or outside the queen's route. Inspect the actual drop cell and next-turn collection. Prefer a valid sacrificial location that is reachable by the queen and does not put the queen's head in danger; keep the queen moving through the pile only when its next move remains safe.
- **Homers obstruct the sink:** Many dragons selecting the same queen cell or its neighboring ring can form a traffic jam, block the queen’s exit, or hit friendly bodies. Stagger feeders, reserve approach lanes, and cap the number of nearby homers. Use distance-to-queen to give outbound traffic priority over inbound traffic.
- **Protection can freeze the wrong dragon:** A round-only `protectFrom` rule can shield a short or stale queen while the real scoring dragon changes, or make a would-be feeder refuse a needed escape/split. Verify protection tracks the current queen id and that it does not suppress defensive movement or succession.
- **Cap and unit-slot interaction:** Stopping buds at r290 does not immediately create a low-unit endgame; top teams still have a median 60 units at r300. Feeding removes bodies over time, freeing unit slots, but any still-active budding (or a successor policy that resumes budding) can refill them. Conversely, permitting mass sacrifice too early while at the cap can reduce map control before the pearls are collected. Gate by observed unit count, queen strength, and recoverable pearl value as well as round. Keep enough scouts/defenders to contest food and prevent a sudden wipeout.
- **Too much mass concentrated too late:** Our r400 leader often dies, and only 26/54 top-team r400 leaders survive to the end. A policy must continue feeding a successor or preserve a backup, not assume the first queen survives. Late feed attempts also need a cutoff based on travel/collection time before r499.

### Concrete Y.10o changes to consider

1. Split the state machine into **grow / select sink / stage feeders / deliver / protect / succession**. On open maps, stop routine budding near the cap (for example, when units reach 58–60, rather than solely at a fixed round), but retain emergency/escape splits. Begin staging only after a fresh queen has held the lead for a short window and has enough length to survive; choose feeder count based on how many units remain and the queen's need for protection.
2. Give each feeder a target **drop/approach cell**, not just a radius. Use a reachable path estimate that accounts for visible bodies and kelp. Stagger arrivals by id or travel time; avoid assigning several feeders to the same narrow approach. Trigger sacrifice only when the pearl drop is predicted to be within a short safe route of the queen, and verify that the queen can collect it without a head-on/body collision.
3. Keep a small outer ring of scouts/escorts until the queen is established. Once the queen reaches a target size, scale the number of escorts and feed rate with nearby enemy threat and the number of friendly bodies around her. If she is threatened or blocked, pause delivery and let her escape.
4. Log per-game diagnostics in indicators or replay-readable state: queen id/length/age, feeder count, feeder ETA, feed site, sacrificed length, recovered pearls, and queen length gain. This makes the policy falsifiable instead of judging only the final win.

Do not make the first experiment combine all of these. First check whether Y.10o increases queen length and pearl recovery by r400 while reducing friendly collisions. If feeding rises but the leader does not grow, the location/path/sink assumptions failed. If the leader grows but still dies, test protection and traffic separately.

## C. Two further ideas

### 1. Cap-aware transition with a protected reserve

**Mechanism:** Switch from expansion to consolidation from observed army state, not round alone. When units are near the 64 cap, stop ordinary budding and designate one stable queen plus a small reserve of scouts/escorts. Feed a controlled fraction of short dragons only when a reachable drop route exists. Keep the reserve alive until the queen is both large enough and safe; then allow more feeders. This aligns with the top teams’ observed 60-body plateau while avoiding the all-at-once collapse of map control.

**Where:** the budding gate in `trySplit()`/`swarmSplit()`, the `feeding` and `homingToQueen` decision in `think()`, and queen selection/protection in `updateQueen()`/`protectedQueen()` in `main.cpp`. Prefer a single explicit phase/state decision feeding these gates over separate hard-coded round thresholds.

**Cheap test:** Make one open-map-only candidate against Y.10, with all other rules unchanged. Use Portals, Slithery Fight, and Schooltime, both sides, and inspect matched seeds. Track units, longest length, total mass, queen identity, feed deaths, recovered pearls, and r400-queen survival in addition to wins. The key early read is whether longest length at r400 and end length improve without losing the opening body count. Only then spend ladder games on a controlled all-map comparison.

### 2. Friendly right-of-way around the queen

**Mechanism:** Prevent the army from killing or pinning its own scoring dragon. Give the current queen priority over normal traffic: non-queen dragons should not route into the queen’s head/next cell or occupy her only safe exit; near the queen, choose outward/lateral moves that leave an escape corridor. Preserve emergency overrides when a drone has no safe alternative. This directly targets the measured open-map r400-queen losses to head-on (46) and friendly body collision (17), and can also improve pearl collection by keeping the sink mobile.

**Where:** the per-move candidate evaluation/selection in `think()` (after candidate moves are simulated, before final sorting/emission), using current visible friendly bodies plus fresh queen gossip from `updateQueen()`. Treat stale or unverified queen coordinates conservatively; do not route on old coordinates as if they were exact.

**Cheap test:** Add a narrow rule only on open maps after r350 and only for a non-queen within a small radius of a fresh queen. Compare against Y.10 with the same open maps/seeds, then classify every r400-queen death by cause and measure friendly head-ons/body hits, queen survival to r499, and final longest length. If traffic improves but queen feeding/food intake falls, loosen the radius or preserve a lane toward the feed site. The ladder result should follow only if this focused test improves the target metrics and win rate.

