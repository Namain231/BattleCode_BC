# Follow-up: role assignment, BFS validity, and sonar for navigation (2026-10-01)

Extends `strategy.md` and `algorithms.md` — does not repeat their content. Same tagging: **[S]** sourced, **[R]**
reasoning.

---

## 1. Role-based strategies: is specialization + role-switching the missing piece?

**What `strategy.md` already has.** S2 (escort/nest) and S4 (spotter/striker/hunter) are both roles, cited to the
escort/UNM paper and generals.io. S7's belief-state table changes the *whole team's* policy by game state. What
neither has: an explicit per-dragon **role-assignment or role-switching function** — who becomes an escort, when a
farmer becomes a hunter, and on what signal.

**Evidence that specialization beats homogeneity, and its preconditions.**
- [S] Halite II's two top finishers both ran role-specialized, not homogeneous, fleets: ReCurs3 (1st) used a
  "strategic role pass" assigning "Colonize a planet, Defend an allied docked ship, Attack an enemy docked ship" per
  ship, then a tactical pass; FakePsyho (2nd) used per-unit greedy role/target assignment, explicitly because keeping
  each unit's decision "completely stateless" and independent of other units' outcomes "drastically simplifies the
  solution and reduces bugs"
  ([lakesidethinks](https://lakesidethinks.com/post/2018/10/halite2-strategy.html), already cited in
  `algorithms.md` §6). The precondition stated outright: it works when a unit's evaluation "doesn't depend on
  results of other units" — i.e., when roles are close to independently assignable, which drops once bodies must
  avoid teammate collisions (`algorithms.md`'s 9/10 teammate head-on finding).
- [S] 2022 Battlecode's 5 Musketeers (soldier/miner/builder/sage) used **static, spawn-time** role assignment —
  "it can read that array element to figure out what the data flag was set to" — not runtime switching
  ([postmortem](https://battlecode.org/assets/files/postmortem-2022-5-musketeers.pdf)). I checked this postmortem
  specifically for dynamic reassignment and found none: roles are fixed at birth by what spawned them, not
  recomputed as conditions change.
- [R] Across every multi-agent programming-game postmortem `algorithms.md` and this search surfaced (Halite II,
  Battlecode 2021–2025, Battlesnake), **nobody publishes true runtime role-switching** — a unit that was a farmer
  becoming a hunter mid-game based on a recomputed signal. What's published is either (a) static assignment at
  spawn/birth, or (b) implicit per-unit greedy scoring that happens to produce role-like behavior without a named
  "role" variable. This is itself the finding: role-switching logic is thin in the literature, not just thin in
  `strategy.md`.
- [S] The escort-count cliff (14% → 75% success going from 2 to 3 escorts, `algorithms.md` §4, UNM paper) is the
  strongest *quantitative* evidence that role allocation (how many of N units to commit to protection) matters more
  than which algorithm the escorts run. That's a role-*count* finding, not a role-*switching* one.

**What's actually missing, concretely.** A function `role(dragon, round, teamState) → {queen, escort, hunter, farmer}`
that re-evaluates every round (or every K rounds) rather than fixing role at spawn — e.g. a farmer near the enemy
queen's predicted area switching to hunter, or an escort peeling off when the cut-vertex set (§4, `algorithms.md`)
shrinks and a hunter is needed more. `algorithms.md` §6 already proposes computing roles as "a deterministic function
of `(id, round, map)`" for zero-bandwidth coordination — that's assignment, but it's static per dragon for the whole
game (fixed by id). The switching gap is: should that function also take live state (queen sighted, cut-vertex count,
casualties) as input, re-evaluated each round? No source answers this for grid games under a hard compute budget; it's
untested territory.

**Verdict: partially right.** Role specialization itself is well-supported (Halite II's winners, the escort cliff).
But the user's sharper worry — that *switching* logic specifically is the gap — is also right, and for a reason
`strategy.md` doesn't state: the published record has almost no runtime role-switching to draw on at all, static
spawn-time or id-time assignment is the norm even among winning bots, so this is a build-and-measure item, not a
port-a-technique item.

---

## 2. Is "BFS from the enemy head" sound for threat estimation under length-dependent speed?

**The narrow question.** Not "how do we compute reach correctly" (that's `algorithms.md` §2's `(cell, L)` answer) but
"is single-source/multi-source BFS from an enemy head, treating its length as fixed for the query, a sound *threat
estimate* at all?"

**When it's valid.** [R] Plain BFS answering "which cells can enemy head H reach within `R(L)` steps" is exactly
right **for a one-turn-ahead threat mask**, because `algorithms.md` §2 already establishes that `f(L)` and `R(L)` are
fixed by length *at the start of that one move* — [S] "the free-step count uses its length at the start of the
move." Within a single turn, length cannot change mid-move from feeding (feeding resolves per the rules at each step
eaten, but the free-step budget for that move was already locked in) and cannot change from voluntary splitting
(splitting is the whole action, per `strategy.md`'s "a split is a pause"). So one-turn BFS/multi-source BFS from
known enemy heads, radius `R(L_now)`, is sound and is the right object for "can any enemy kill me if I step here this
round" — this is what S1 already does.

**When it breaks.** [R] It breaks the moment you extend the *same fixed-radius* BFS across multiple turns to answer
"can the enemy reach my required destination in N rounds" — exactly the use `strategy.md`'s S4(c) hunters and S2's
nest-safety checks need. Three failure modes, in order of how badly they bite:
1. **Growth along the path.** A hunter that eats feed drops en route grows, so its `f(L)` and `R(L)` both increase
   turn over turn. A multi-turn BFS run once at radius `R(L_0)` *under*-estimates reach for every later turn —
   dangerously, since it under-counts threat.
2. **Spending along the path.** A fleeing queen that pays segments to escape a trap shrinks, so her own radius
   shrinks turn over turn — a multi-turn BFS of her escape options at her current `L` *over*-estimates her future
   reach, and `d(L)` (`algorithms.md` §2) means the shrinkage isn't linear: crossing a `d(L)=0` boundary costs a
   whole free step, not just one segment of distance.
3. **Variable branching, not just variable radius.** Because `f(L)` changes which cells are "free" versus
   "costs a segment," the *shape* of the reachable set changes between turns, not just its size — so even summing
   `R(L)` over turns (naive multi-turn radius = `Σ R(L_t)`) is wrong whenever a growth or shrink event crosses a
   residue boundary mid-sequence.

**Is there a known fix?** [S] The closest published technique is Resource-Constrained Shortest Path with
state-dependent **replenishment** (not just consumption): a 2026 paper models a budget that depletes with distance
but **resets to full capacity on entering designated regions**, solved by a two-stage wavefront-discretize-then-Dijkstra
method over candidate boundary waypoints, refined by convex optimization
([arXiv 2604.23480](https://arxiv.org/html/2604.23480)). It is not length-replenishment-as-a-function-of-path exactly
— feed drops are discrete growth events at known cells, which is a closer structural match than the generic RCSPP
`algorithms.md` §2 already cites (fixed budget, no replenishment at all). The wavefront/candidate-waypoint idea maps
onto Loong directly: treat feed-drop cells as "reset regions" that bump `L` (and hence `f`, `R`) on an existing path,
and solve as a shortest-path over (turn-start cell, L) states with edges weighted by whether a feed cell was crossed
— which is precisely `algorithms.md`'s own `(cell, L)` turn-layered expansion already recommends, just with
confirmation from a second, more specific source. No paper addresses *consumption-based* shrinkage (our case 2) with
cliffed/non-linear cost the way `d(L)` has it; that remains unformulated.

**Minimal fix for us.** [R] Don't extend a single-turn BFS across multiple turns at all. Use `algorithms.md`'s
`turnsToReach(p, L, maxTurns)` primitive (already on the priority list as item 2, ~90 LOC) for any multi-turn threat
question, and reserve plain fixed-radius BFS strictly for the one-turn "is this cell safe to land on right now"
check, where it is exact. The danger is conflating the two: using a cheap one-turn BFS and silently applying it over
a multi-turn horizon (e.g., "hunter is 8 cells away, it'll take ~3 turns" computed by dividing distance by *current*
`R(L)`) will misjudge exactly the cases that matter — a feeding hunter closing faster than expected, or a fleeing
queen with less reach left than her current length suggests.

**Verdict: the hunch is right, with a specific scope.** Single-turn BFS/multi-source BFS is sound and should stay.
The unsound move is reusing it, or a naive sum of per-turn radii, as a multi-turn estimate — that's where growth
(feeding) and shrinkage (spending) both break it, and the breakage is asymmetric: growth makes a fixed-radius
estimate dangerously optimistic for us, shrinkage makes it dangerously pessimistic for an escaping queen.

---

## 3. Sonar for navigation/nesting versus position gossip

**What `strategy.md` S6 covers:** encrypting queen-position/status gossip, nothing about broadcasting terrain,
safe-path, or frontier information.

**Precedent for broadcast-based map/frontier sharing.** [S] Cooperative multi-agent pathfinding work explicitly
shares *maps*, not just positions: "Cooperative Hybrid Multi-Agent Pathfinding Based on Shared Exploration Maps"
builds and shares an exploration map among agents to cut redundant search and resolve conflicts
([arXiv 2503.22162](https://arxiv.org/html/2503.22162v1)). Separately, "Communication via Shared Memory Improves
Multi-Agent Pathfinding" (NeurIPS workshop) finds that giving agents a shared read/write memory channel —
structurally the same primitive as Loong's sonar broadcast — improves pathfinding coordination over no-communication
baselines ([mlanthology](https://mlanthology.org/neuripsw/2024/sagirova2024neuripsw-communication/)). Neither paper
has an adversarial listener, which is the gap below.
Classic indirect/stigmergic coordination (ant-colony pheromone trails, blackboard architectures) is the older version
of the same idea: agents coordinate through environment-state or a shared store rather than direct peer messages, so
the *content* broadcast is about the world (trail strength, candidate solution, discovered region), not about any
one agent's identity or location — which is the structural property that matters for the adversarial-listener
question below.

**Does precedent exist for terrain/path info specifically being safer to broadcast than positions, under an
adversarial listener?** [S] Partially — from a different angle than exploration-sharing. Blumenkamp & Prorok (already
cited in `algorithms.md` §6) show a self-interested agent on a *shared learned channel* can "significantly outperform"
a cooperative team by exploiting it, and that manipulative strategies emerge "only under resource contention"
([CoRL 2021](https://proceedings.mlr.press/v155/blumenkamp21a/blumenkamp21a.pdf)). That paper is about an insider
exploiting trust, not an outside eavesdropper, but it establishes the general principle `algorithms.md` already
applies to sonar: any message content is a liability *in proportion to how directly actionable it is to an
adversary who can also act on it*.

**[R] Applying that principle to path/terrain versus position.** A position message ("enemy queen at (x,y), length
L, round r") is maximally actionable: an eavesdropper converts it directly into a strike target via `R(L)`, with
essentially zero interpretation cost — this is exactly what S6 already flags. A terrain/safe-path message
("cell (x,y) is kelp," "the corridor through (a,b)-(c,d) is clear," "nest at (x,y) has one entrance") is *not*
directly actionable the same way: terrain facts are largely symmetric information both teams can derive from their
own exploration, so broadcasting them leaks little the enemy didn't already have access to in principle, while a
nest-location or safe-path-to-nest message is **structurally a position message in disguise** — it tells the enemy
exactly where to converge, arguably worse than a single position ping since it implies a destination, not just a
momentary location.

**Verdict: the hunch is only partly right, and the risk is uneven, not uniform.** Pure terrain facts (kelp cells,
wall layout already visible to both sides, generic frontier/explored-area info) are safe to broadcast under the same
logic the exploration-sharing papers rely on — low marginal information to an adversary, real coordination value for
teammates routing toward feed or rallying. But anything that encodes a *destination* for the queen — a nest location,
a "safe path to X" where X is where she's heading — is not safer than a position ping, it's a leading indicator of
one, and should get the same encryption/stale-reject treatment S6 already specifies for position gossip, not the
lighter treatment the user's hunch implies. Recommend splitting sonar payload classes explicitly: {terrain/frontier
— broadcast freely}, {position/destination — encrypt, as S6 already plans}.

---

## Prioritized build list (reconciled with `algorithms.md` §7)

`algorithms.md` §7 already ranks items 1–7 by LOC and lists its own top-3 ("if only three ship: 1, 2, 3" — turn-layered
free-space test, `turnsToReach`, and the `d(L)` length policy). This list adds what this follow-up found; it does not
re-rank what's already there.

1. **`turnsToReach` is the fix for Q2, not a new item — just confirm scope.** No new LOC: `algorithms.md` item 2
   already covers this. The only change is a usage rule, not code: ban raw fixed-radius BFS for any multi-turn
   question, enforced by only exposing `turnsToReach` in threat-estimation call sites. **~0 LOC** (a code-review
   constraint, not a feature).
2. **Sonar payload split: terrain/frontier (open) vs. position/destination (encrypted, per S6).** Add a message-type
   tag and route nest-related and destination broadcasts through S6's encryption path; route kelp/wall/frontier
   facts unencrypted. **~25 LOC** on top of S6's ~50.
3. **Per-round role re-evaluation function**, replacing `algorithms.md` §6's static `(id, round, map)` role map with
   one that also reads live state (queen sighted this round, current cut-vertex count from item 5, a dragon's
   distance to predicted enemy-queen area) and only switches a farmer to hunter/escort when the signal is strong
   enough to beat a hysteresis threshold (avoid role-flapping). **~50 LOC**, tested against the static-role baseline
   on enemy-queen kill rate and queen survival — the comparison `algorithms.md` §7 doesn't run.
4. **Nest safe-path broadcast**, gated behind item 2's encryption split: the queen's escort proposes a nest and
   broadcasts the encrypted route; only teammates decode it. This is the concrete feature the user's Q3 hunch was
   reaching for, and it's safe only once item 2 exists. **~35 LOC**, building on `strategy.md` S2's nest-BFS
   (~120 LOC, already budgeted there).
5. **Escort-count-vs-role-switch interaction test**, not new code: once items 3 and 5 (`algorithms.md`'s cut-vertex
   escort assignment) both exist, A/B whether dynamic role-switching changes the escort-count cliff found at 2→3 in
   the UNM paper — does switching let 2 escorts perform like a static 3 would? **~0 LOC**, a measurement task using
   existing `tools/tempo.py`-style harness.

## Sources

Already-cited sources from `strategy.md`/`algorithms.md` are not relinked. New sources this file adds:
[Halite II strategy, lakesidethinks](https://lakesidethinks.com/post/2018/10/halite2-strategy.html) (re-cited for
the role-assignment angle specifically),
[5 Musketeers 2022 postmortem](https://battlecode.org/assets/files/postmortem-2022-5-musketeers.pdf),
[Resource-Constrained Shortest Path with Polytopic Reset Sets, arXiv 2604.23480](https://arxiv.org/html/2604.23480),
[Cooperative Hybrid Multi-Agent Pathfinding Based on Shared Exploration Maps, arXiv 2503.22162](https://arxiv.org/html/2503.22162v1),
[Communication via Shared Memory Improves Multi-Agent Pathfinding, NeurIPS workshop](https://mlanthology.org/neuripsw/2024/sagirova2024neuripsw-communication/),
[Blumenkamp & Prorok, CoRL 2021](https://proceedings.mlr.press/v155/blumenkamp21a/blumenkamp21a.pdf) (re-cited).
