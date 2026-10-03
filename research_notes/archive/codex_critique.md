# Independent critique of Y.10 and the current search

## Blunt assessment

The team has built a capable early swarm and then treated the round-500 tiebreak as a late-game feeding problem. The ladder results say that framing is incomplete: open-map games are usually lost with more total mass but a shorter longest dragon, and the longest often dies between rounds 400 and 500. A strategy that maximizes aggregate pearls or unit count can therefore make the actual winning condition worse. The optimization target needs to be the probability that at least one dragon remains longer than the opponent's longest dragon at round 500, not mass as a proxy.

The panel is no longer a useful selector for small changes. Its 59–62% band is saturated, its opponents do not reproduce the ladder's open-map collapse, and a many-game score can still hide a catastrophic map-specific regression. Candidate ranking should come from same-time ladder evidence and per-map outcome/cause data. The internal panel remains useful as a cheap rejection test for large regressions, but a one or two point difference is noise until confirmed.

The design's most dangerous blind spot is coordination under partial information. Queen gossip has a single consensus id and timestamp, but does not establish that the queen's reported location is reachable or still safe; ordinary 7×7 vision cannot see through portals. `tryFeed()` can safely split only when the queen is actually visible nearby, while `think()` can switch to homing based on a remembered cell and a broad toroidal radius. That leaves a gap between “we agree who the queen is” and “our team can deliver length to a viable survivor.” The portal friendly head-on already observed is a concrete example of coordination information being too weak for a high-value late unit.

The rules are also full of fixed thresholds (`feedFrom`, `homingFrom`, `protectFrom`, `endFeedFrom`, unit-count cutoffs) but have little explicit opponent-relative logic. The current `findAttack()` mostly decides from length and local unit count; the homing/feed logic mostly reacts to our own queen. Neither asks early enough whether the enemy already has a giant likely to win the tiebreak. Finally, the code makes a local move choice from a heuristic evaluation and an imitation prior; it does not appear to price the strategic cost of spending the last rounds trapped, feeding the wrong dragon, or exposing the only viable tiebreaker.

## Three high-upside ideas

### 1. Open-map longest-dragon survival mode

**Mechanism.** On Portals, Slithery Fight, and Schooltime, identify the strongest own dragon and the strongest known enemy dragon by length. Once the game is clearly headed to a tiebreak (for example, after round 340, or when both teams still have units and neither is close to elimination), stop treating the longest own dragon as an ordinary miner/attacker. Preserve its length, favor moves with escape room, avoid voluntary head-on trades and sprint length costs, and route other units away so they do not force dangerous body/portal interactions. This directly targets the reported failure mode: surplus total mass is worthless when the longest dies before round 500.

**Where.** `think()` around `updateQueen()`, `feeding`/homing selection, and sprint allowance; the late survival checks in `findAttack()` and `evaluate()`; use map identity via `bigFeed` only if measurements show the behavior should be limited to those three maps. The current `protectedQueen()` is too broad a proxy: it protects a consensus queen after `protectFrom`, not necessarily the dragon whose survival most improves the tiebreak.

**Cheap test.** Add diagnostic replay summaries for rounds 350, 400, 450, and 499: own/enemy longest length and id, whether each longest survives, mass, and death cause. On a small fixed set of existing open-map ladder losses and wins, compare a shadow-mode decision trace that labels turns where the longest dragon accepts avoidable risk. Then implement the narrowest guard (no attack trade/sprint if it can kill the current longest and the enemy longest is not killable) and replay the same seeds before spending ladder games.

### 2. Make queen telemetry carry confidence and a viable route

**Mechanism.** A location-and-length rumor is insufficient when portal topology and visibility matter. Extend the team message with freshness/confidence and a compact safety/route hint, or conservatively derive these locally: accept a queen location for feeding only when its age is short, the queen is known alive, and the map graph gives a real path that does not terminate in an occupied/unsafe cell. Apply a hard friendly-head exclusion to portal exits near the queen. This should reduce chain feeds, bad homing, and late friendly head-ons while allowing feeders to coordinate around one sink instead of wandering toward stale coordinates.

**Where.** `packQueen()`, `unpackQueen()`, `considerQueen()`, `updateQueen()`, `tryFeed()`, and the `feeding` block in `think()`; portal destination safety belongs near candidate generation/evaluation where `nbr` exposes the actual landing cell. Preserve the existing message format compatibility or change sender and receiver together.

**Cheap test.** First instrument a bounded sample of open-map replays (not a full archive scan) to count queen rumors older than 5/10/25 turns at the moment of homing/feed, pathless routes, portal landings within one cell of queen, and friendly head-on deaths. If these events are common, test only the hard safety predicate in replayed games: reject a move whose portal exit is adjacent to the fresh queen cell. It is a small, attributable change with a clear countermetric before a ladder A/B.

### 3. Detect the opponent's giant early and change the objective before round 400

**Mechanism.** Against an opponent with one clearly dominant dragon, an equal swarm contest is often the wrong game: they can preserve a giant while our smaller units die or feed inefficiently. Estimate opponent longest length from visible heads and sonar/history, detect whether it is growing faster than our longest, then choose between (a) protecting and growing our own tiebreak dragon, and (b) focused elimination if a safe head-on can remove their only giant. This is a conditional policy switch, not a global change to feeding thresholds. It uses the actual terminal rule and avoids spending the last 100 rounds accumulating mass that cannot change the winner.

**Where.** Opponent tracking currently surfaced in `others`/`estLen`, attack valuation in `findAttack()`, and target selection/homing in `think()`. Add the opponent-giant state alongside the queen state, and make its policy affect only attack/retreat/feeding priorities in late midgame. Do not make all small units suicide at the giant: the test should distinguish feasible, favorable trades from attempts that simply donate pearls.

**Cheap test.** Reclassify a modest, stratified set of open-map ladder losses by whether the opponent had one dominant dragon at rounds 300–400 and whether it survived. Replay only those seeds with a trace-only giant detector first; check detection precision and whether the bot had a reachable favorable attack window. If the signal is strong, test one policy branch against the unchanged build on those same seeds, then confirm on fresh all-map ladder games because the internal panel does not represent this endgame well.

## Measurement discipline for these ideas

Report open maps separately and record longest-at-400, longest-at-500, longest death cause, winner's longest, and total mass. A gain in mass with no gain in longest-survival rate is not progress for this loss class. Keep a maze-map control to catch collateral damage, but do not let the aggregate panel erase an open-map collapse.
