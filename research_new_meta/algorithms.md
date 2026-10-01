# The algorithmic canon, mapped onto the queen/free-step rules (2026-10-01)

Companion to `strategy.md`, which covers queen safety, escorts, assassins, sonar and endgame state machines but never
mentions flood fill, area control or search. This file fills that gap. **[S]** marks a sourced claim with its URL.
**[R]** marks my own reasoning, which is untested. Rule facts about Loong come from the rules copies in
`/tmp/claude-0/docs_new/` and are marked [S] without a URL.

Throughout: `L` is a dragon's length, `f(L) = ceil(L/4)` its free steps per turn, `R(L) = L − 2 + f(L)` its maximum
one-turn reach (from `strategy.md` §1), and `d(L) = (L − 1) mod 4` a quantity I define in §2.

---

## 1. Survival pathfinding: not trapping yourself

**What the canon actually says.** The official Battlesnake docs recommend exactly two algorithms, flood fill first: "an
algorithm to determine the boundaries and size of an enclosed space", used to "detect and avoid enclosed spaces that
Battlesnakes may not be able to escape from"
[S] ([docs.battlesnake.com](https://docs.battlesnake.com/guides/useful-algorithms)). Strong published agents implement
it as an evaluation *term*, not a hard filter. Redbrick's bounty snake (42–45, 93%) ran "a floodfill in order to see
how many squares on the board can be reached from my position and the opponent's position", weighted "as a percentage
of the total squares on the board", and its author judged that "writing a heuristic function… was what would ultimately
make or break the bounty snake" [S] ([rdbrck.com](https://rdbrck.com/news/building-bounty-snake-post-mortem/)).
Robosnake calls flood fill twice per leaf, once per snake, inside alpha-beta
[S] ([smallsco/robosnake](https://github.com/smallsco/robosnake)).

**Tail reachability and tail trimming.** The "can I still reach my own tail" invariant appears in the canon as *tail
trimming*: 2018's RUTHLESS "trimmed tails based on route length" to "increase the likelihood of finding valid paths to
goals", ran *dual-mode* space evaluation (pessimistic and optimistic, pessimistic preferred early), and relied on
tail-chasing rather than attacking. The retrospective's headline lessons: defensive survival beat aggression, and a
strong 1v1 specialist "couldn't handle being in close proximity to multiple snakes at once"
[S] ([rdbrck 2018 retrospective](https://www.rdbrck.com/whats-new/battlesnake-2018-retrospective)). Robosnake instead
"remove[s] the tails of ALL snakes from the grid as we recurse", which it notes makes it "vulnerable to tail-chasers"
[S] (robosnake repo).

**Articulation points and chamber decomposition** come from Tron rather than Battlesnake. a1k0n, who won the 2010
Google AI Challenge, used "the standard O(N) algorithm for finding articulation points" to find chokepoints, and then
decomposed reachable space into chambers separated by those cut vertices
[S] ([a1k0n.net](https://www.a1k0n.net/2010/03/04/google-ai-postmortem.html)). Iouri Khramtsov's TronBot built the
same thing as an explicit "tree of chambers, where if the bot goes into one of the branches… it cannot exit that
branch", by BFS labelling with signed distances and then parenting chambers at bottleneck cells
[S] ([github.com/ikhramts/TronBot](https://github.com/ikhramts/TronBot)). a1k0n also used a checkerboard-parity bound:
"if a given space has a lot more red squares than black squares, the surplus red squares will necessarily be wasted"
[S] (a1k0n).

**What survives our rules, and what breaks.**

- **Flood fill survives, but the unit of time changes.** [R] Battlesnake's "reachable area ≥ own length" invariant
  works because head and tail each advance one cell per turn, so a pocket of area A buys A turns. Here a dragon advances
  up to `f(L)` cells per turn for free, so the same pocket buys about `A/f(L)` turns: the *area* threshold is unchanged,
  the *survival horizon* shrinks with length. A length-20 queen with `f = 5` burns a 40-cell nest in eight turns. The
  useful test is therefore not "is reachable area ≥ L" but "is the area reachable **within two turns** ≥ L" — a flood
  fill layered by turns, not by steps.
- **Self-trap is partially recoverable, which is new.** [R] No Battlesnake snake can shorten itself on demand; a Loong
  dragon can, because paying a segment removes a tail segment and frees a cell behind it. A dragon sealed into a pocket
  can tunnel out by paying. So self-trap should be *scored* for drones and *filtered* only for the queen, whose length
  is a tiebreak.
- **Tail chasing mostly dies.** [R] It is a 1-step-per-turn equilibrium: the tail vacates exactly as fast as the head
  arrives. With `f ≥ 2` your head laps your own tail, so the cycle is stable only if you deliberately take one step per
  turn — wasting `f − 1` free steps a round and making you the slowest dragon on the board. Against enemies covering
  `R(L)` cells a turn, slow is fatal.
- **Hamiltonian cycles die outright.** [R] They need one snake, a static known board, one step per turn. We have a
  torus with walls and portals, several dragons per side, and multi-step movement. Not worth a line.
- **Articulation points survive and become *more* valuable.** [R] Only a dragon's **head** can be killed by another
  entering its cell ([S] moving into a body kills only the mover), so the queen's body is a wall she builds herself, and
  the cut vertices of her reachable free component are exactly the cells an attacker must pass through — a small,
  explicitly computable defence target. See §4.

---

## 2. Length-dependent pathfinding: the key question

**The honest answer: there is no published formulation of this problem.** I looked for three things and found three
near-misses, none of which has our feedback loop.

1. **Resource Constrained Shortest Path (RCSPP):** "find a minimum-cost path p from source to target such that
   Σ r_ij ≤ R", each arc carrying a cost *and* a resource consumption, solved over an implicit `(node, resource)` state
   space with dominance pruning (a partial path dominates one with higher cost *and* higher resource use) and
   bidirectional A*; NP-hard
   [S] ([Ahmadi et al., AAAI 2021](https://cdn.aaai.org/ojs/17450/17450-13-20944-1-2-20210518.pdf)). Gives us the
   product state and the dominance rule — but its budget is a *fixed constant R*. Ours regenerates every turn, at a
   rate depending on how much is left.
2. **Per-turn movement allowances in 4X/wargames.** The Unciv developer states the problem exactly: "Limiting turns…
   fundamentally changes the problem. For the bottom-left unit to reach the top-right, it will have a *different optimal
   path* depending on the amount of MP it gets per turn", and plain Dijkstra "cannot model this discontinuity". Their
   solution separates **intra-turn** (BFS inside one turn's budget) from **inter-turn** (an expanding frontier of
   turn-start tiles) with state `(turn_number, path_history)` — turn-optimal, not remaining-movement-optimal. And they
   *tried* the elegant product state: "The attempted unified approach tracked state as (turns, remaining_movement)
   tuples and used priority-queue sorting… profiling revealed the TreeSet overhead… making it 3–7x slower than the
   simpler separated approach"
   [S] ([yairm210](https://yairm210.medium.com/multi-turn-pathfinding-7136bd0bdaf0)). A direct empirical warning for a
   bot on an instruction budget. Still, their MP allowance is identical every turn. Ours is not.
3. **Jump Point Search** assumes a uniform-cost grid — "Each straight… move… has a cost of 1; diagonal moves cost √2" —
   and earns its 25–30x speedup by collapsing symmetric paths that "have the same length and are otherwise identical
   save for the order in which moves occur"
   [S] ([Harabor & Grastien, AAAI 2011](https://harabor.net/data/papers/harabor-grastien-aaai11.pdf)). [R] Our cost
   depends on *when in the turn* a step falls, so reordering moves changes cost, so JPS's path-equivalence assumption
   is violated. JPS is unsound here; do not use it.

So: no direct answer. Here is my formulation, labelled as mine.

**[R] My formulation.**

*Within one turn,* `f` is fixed by the length at the start of the move ([S] rules), so `s` steps cost
`max(0, s − f(L))` and `s_max(L) = L − 2 + f(L) = R(L)`. Intra-turn movement is one layered BFS: free out to depth
`f(L)`, then one segment per extra ring out to `R(L)`. No product state needed.

*Across turns,* the state is `(cell, L)` and the transition is a whole turn: from `(p, L)`, for every `s ≤ R(L)` and
every `q` reachable in exactly `s` steps through remembered-free cells, you reach `(q, L − max(0, s − f(L)))` at turn
`t+1`. Expand turn-by-turn Unciv-style rather than with one priority queue — one BFS layer per turn, seeded by the
previous layer's turn-start cells — keeping per cell only **Pareto-undominated** `(turns, L)` pairs (a later arrival
with strictly greater `L` is not dominated). Two entries per cell in practice (earliest arrival, longest-remaining
arrival) keeps the frontier small.

An admissible heuristic for the turn-count objective: `h(p) = ceil(torusDist(p, goal) / R(L))` — admissible because `L`
only decreases along a path, so `R` only decreases, so no future turn covers more than `R(L_now)` cells.

**[R] The feedback loop, and the quantity that makes it tractable.** Write `L = 4(f − 1) + r`, `r ∈ {1,2,3,4}`. Define

> **`d(L) = (L − 1) mod 4`** — the number of segments the dragon can burn before `f` drops by one.

`d(12) = 3`, `d(11) = 2`, `d(10) = 1`, `d(9) = 0`. This is the whole feedback loop in one integer: paying segments is
**piecewise free**. The first `d(L)` segments cost only length; the `d(L)+1`-th costs one free step **on every
subsequent turn for the rest of the game**. The marginal price of a segment is not constant — it spikes at
`L ≡ 1 (mod 4)`.

Two consequences `strategy.md` does not have:

- **The queen should hold a length `≡ 0 (mod 4)`** (`d = 3`: three segments of slack before her speed drops) and should
  never pay while `d(L) = 0` unless the alternative is death. A fleeing queen at `L = 9` who pays one segment loses a
  free step permanently, making the *next* escape harder. That is what makes this a feedback loop and not a budget.
- **§S8's "lengths 4k+1 gain a free step" is right only for one-shot assassins.** For a dragon that sprints once and
  kills or dies, maximise `R(L)`, and `4k+1` is the cheapest length owning `f = k+1`. For anything that sprints
  *repeatedly* — escort, chaser, fleeing queen — `4k+1` is the worst residue, because `d = 0`. Hunters and escorts want
  different residues; test them separately.

**[R] Practical "cheapest route to X".** Lexicographic, not scalar: minimise `(turns, segments spent)` subject to
`L ≥ L_floor` for the role. When move scoring needs a single scalar, price a segment as
`c(L) = base + bonus·[d(L) = 0]` with the bonus large, so the scorer refuses to cross a free-step boundary of its own
accord. The nearest formal relative is RCSPP with *state-dependent resource replenishment* — energy-constrained shortest
path where the recharge rate is a function of remaining energy. I found no paper on that variant. Implement the
two-level layered expansion, not the product-state queue, on Unciv's evidence that the queue loses by 3–7x [S].

---

## 3. Area control

**Canon.** Tron is the right analogue and the Voronoi partition is the central idea: for each square decide "whether
player 1 can reach it before player 2 does" and score the difference
[S] ([a1k0n](https://www.a1k0n.net/2010/03/04/google-ai-postmortem.html)); TronBot classifies cells as mine-first,
theirs-first, or tied and scores `size(a) − size(b)`
[S] ([TronBot](https://github.com/ikhramts/TronBot)). a1k0n then replaced raw territory size with a regression on
`K1(N1 − N2) + K2(E1 − E2)` — nodes *and edges* of the territory graph — fitted over 11,691 games to `K1 = 0.055`,
`K2 = 0.194` [S] (a1k0n). Edges got nearly 4x the weight of nodes: corridor-shaped territory is worth less than
open territory of the same area. His winning innovation was *battlefront chambers*: finding cut vertices while
"assuming the opponent's territory by the Voronoi metric is disconnected", then deciding which chambers to contest and
which to concede [S] (a1k0n).

For the multi-agent case, the Battlesnake search paper's board-control term is a "queue-based diamond flooder"
determining which tiles each snake reaches first, with ties "controlled by the longest snake"
[S] ([Adversarial N-player Search using Locality, GI](https://dl.gi.de/server/api/core/bitstreams/358e228c-0917-4849-a4fe-40d155c3232c/content)).

**[R] What changes here.** Plain BFS Voronoi is wrong for us, because dragons do not move at the same speed. Dragon
`i` covers `f_i = ceil(L_i/4)` cells per free turn, so the arrival time to a cell at free-space distance `δ` is
`ceil(δ / f_i)` turns. Our board-control map is a **multiplicatively weighted Voronoi diagram with weights `1/f_i`** —
one multi-source BFS where each seed's expansion is rate-limited by its own `f`. A length-20 queen owns roughly five
times the radius of a length-2 drone. That is the missing link between length and territory: length buys *area*, not
only reach.

- **Tie-breaking must not use length.** Battlesnake's "ties go to the longest snake" [S] encodes a rule we do not have
  ([S] both die regardless of length). [R] A contested cell here is *mutually lethal*: score tied cells zero for both
  sides and add the tie set to the queen's danger mask.
- **Count edges, not just nodes.** [R] a1k0n's `K2 = 0.194` on edges versus `K1 = 0.055` on nodes [S] is the finding to
  port: score the queen's nest by its component's edge count, which penalises exactly the long corridors
  `strategy.md`'s coil idea produces.
- **Does area control predict defensibility of a fixed dragon in a pocket?** [R] Only with the chamber tree. Area alone
  does not: a 60-cell pocket with four entrances is worse than a 30-cell pocket with one. The predictive quantity is
  *(area of the queen's component) ÷ (number of cut vertices separating it from enemy-first territory)* — area for
  survival horizon, cut-vertex count for how many cells an escort must cover. A direct transplant of a1k0n's
  battlefront-chamber test [S] onto our asymmetric objective.

---

## 4. Protecting one fixed unit

**Canon.** Three strands, none a clean match. *Learned escort:* escorts protecting a payload through a crowd enforce a
"cordon area" of radius 5, and learn with no explicit reward to "stay close to the payload", "keep pace with it,
maintaining an efficient formation", and "spread evenly around the payload to offer the most coverage". Count matters
sharply — on the hardest scenario "a two-escort team finds a solution 14% of the time while the three-escort team finds
a solution 75% of the time" [S] ([Defensive Escort Teams, UNM](https://www.cs.unm.edu/tapialab/Publications/63.pdf)).
*Hide, don't guard:* generals.io is the closest asymmetric-objective game with one must-survive unit, and its community
consensus is concealment — "Don't let underpopulated cities be seen or the general at all", expand with "hollow parts
then fill outward/inward" against the draw distance of 2; you locate the enemy general by tracing their border and
following "the trail of 1's back to source"
[S] ([gist](https://gist.github.com/twolfson/4bbbb40bd8b7ed670694b5a4dae04931)), the same movement-trace inference
`strategy.md` already cites [S] ([neelr](https://notebook.neelr.dev/stories/on-generals-io-tactics)).
*Interposition:* I found no clean grid interposition formulation in the game-AI literature; the closest is a1k0n's
cut-vertex battlefront analysis [S], an interposition algorithm in all but name.

**[R] Mapping onto Loong.**

- **Concealment is the wrong lever; distance is the right one.** Vision reports every visible segment's team and id
  ([S]), so the queen cannot be disguised and §S9's decision to skip decoys is right. But identification needs a 7×7
  window. The generals.io lesson transfers as a *metric*: minimise rounds the queen spends inside any enemy head's 7×7,
  and treat a sighting as starting a countdown, since a seen queen can be struck from `R(L)` away by anyone who hears
  a relay.
- **Interposition is a vertex cut, and it is computable.** An attacker kills the queen only by entering her head's
  cell. Let `C` be her reachable free component and `X` the cut vertices of `C` separating her head from enemy-first
  territory under §3's weighted Voronoi. Covering `X` with escort bodies is *sufficient* defence for the rest of the
  round, and `|X|` is the escort budget the position demands — replacing §S2's fixed "2–4 drones at 2–4 tiles" with a
  position-dependent count and specific cells.
- **Turn order makes escorts patchers, not blockers.** [S] Dragons act in ascending id order; queens are ids 0 and 1.
  So escorts (high ids) move *after* every enemy drone in the same round. They cannot pre-empt a strike already
  launched, only cover the cell an enemy needs *next* round. The escort objective is "after all enemies have moved, be
  on or adjacent to every cell in `X`" — a one-round-lookahead assignment, not formation keeping. This is the opposite
  of the escort paper's co-moving cordon [S], whose escorts and payload move simultaneously.
- **Test three, not just 0/2/4.** The 14%→75% cliff [S] is from a continuous crowd domain so the number does not
  transfer, but the shape (a threshold where escorts can finally cover every approach) plausibly does, and it is free
  to test.

---

## 5. Search under a hard per-turn compute budget

This is where the evidence is strongest and most consistent, and it all points the same way.

**The explicit claim, from the person who won Tron:** "a deep minimax search using a flawed evaluation heuristic is
self-deluded about what its opponent is actually going to do"
[S] ([a1k0n](https://www.a1k0n.net/2010/03/04/google-ai-postmortem.html)). He won "decisively" with a heuristic-heavy
evaluation (regression-fitted Voronoi, chamber trees, parity bounds) plus alpha-beta and iterative deepening reserved
for the endgame [S].

**Battlesnake, measured.** The GI paper reports that under its time budget "the maxn search depth was only four moves
ahead while alpha-beta search computed up to eight moves ahead" — N-player search costs roughly half the depth. And
the gains came from the evaluation: the GA-tuned evaluation averaged leaderboard position **3.33 (±2.21)** against
greedy's **4.15** and aggressive's **5.02**, while their search improvement (IDAPOS, locality masking of distant
opponents) moved **4.51 → 4.12**
[S] ([GI paper](https://dl.gi.de/server/api/core/bitstreams/358e228c-0917-4849-a4fe-40d155c3232c/content)). Tuning the
evaluation was worth about twice what the search improvement was worth.

**Battlecode, whose budget is an instruction count like ours.** Both teams abandoned search. Wololo (2021) used
"explicit game-state evaluation rather than search", a two-phase micro-then-macro scored decision, and a "short-distance
greedy pathfinding algorithm… avoiding expensive search algorithms given bytecode limits"
[S] ([wololo](https://battlecode.org/assets/files/postmortem-2021-wololo.pdf)). SPAARK (2025) "stuck with our bug2
pathfinding instead of last year's BFS… as it used too much bytecode", wrote a custom XORshift because Java's RNG costs
"~50 bytecode per usage", replaced an O(144) message scan with a 12×12 index map, and ran a flat integer micro score
("20 score for moving in correct direction", "150 score for mopping next to a ruin")
[S] ([SPAARK](https://battlecode.org/assets/files/postmortem-2025-spaark.pdf)).

**Halite II, many units on one global budget.** 2nd-place FakePsyho was pure evaluation plus global greedy assignment:
"If the evaluation of (unit, action) doesn't depend on results of other units, you can just select the best action for
each one", and "completely stateless (other than knowing which turn it is)… drastically simplifies the solution and
reduces bugs". 1st-place ReCurs3 ran a strategic role pass, then a tactical pass, then refined the *joint* action vector
by hill climbing: "Take an allied undocked ship at random. Replace its action with a move of random angle and thrust…
If it's better than the old one, replace that ship's action"
[S] ([lakesidethinks, top 3](https://lakesidethinks.com/post/2018/10/halite2-strategy.html)).

**[R] Conclusion for us.** The marginal win is in the evaluation function and in correctly modelling what the opponent
*can* do, not in depth.

1. Spend the budget on **1-ply scoring with an exact opponent-reach model**: enumerate our candidate turn-moves and for
   each ask whether any enemy head's terrain-aware `R(L)` reach covers the cell we land on. The §2 layered BFS *is* the
   evaluation; it is not a tree search.
2. Spend what remains on **ReCurs3-style hill climbing over the joint action vector** [S], which buys coordination
   (escorts not colliding with each other or the queen) at a cost capped by iteration count. This matters here
   specifically: §S2 reports 9 of 10 head-ons in the roles bot were between teammates ([S] `blog/12-roles.md`). That is
   a joint-action-vector bug and hill climbing is the published cheap fix.
3. **Do not build MCTS or deep minimax.** Two heads entering one cell kills both regardless of length ([S]), so
   branching at contact is large and leaves are near-terminal; the GI paper's depth-4 maxn [S] is the realistic ceiling
   and was worth less than evaluation tuning.
4. **If you ever do search, mask by reach, not distance.** The GI paper masks opponents outside "an L1 distance of twice
   the search depth" for heads, the search depth for bodies [S]. [R] Our analogue masks any enemy whose `R(L)` reach
   cannot intersect ours within the horizon — a strictly larger radius, and it must use `R(L)`, not raw distance.

---

## 6. Coordination and communication

**Task allocation.** Instantaneous single-task/single-robot assignment is the easy case of the standard taxonomy, solved
optimally in polynomial time or greedily at a constant-factor loss
[S] ([MRTA taxonomy, IJRR](https://dl.acm.org/doi/abs/10.1177/0278364913496484)). Competition evidence favours greedy:
ReCurs3 gave every ship one of "Colonize a planet, Defend an allied docked ship, Attack an enemy docked ship" and found
it "important to minimize the sum of all distances between ships and their targets"; FakePsyho used repeated best-pair
greedy [S] ([lakesidethinks](https://lakesidethinks.com/post/2018/10/halite2-strategy.html)).

**Adversarial channels.** Blumenkamp & Prorok: a single self-interested agent sharing a learned channel with a
cooperative team "is capable of learning highly manipulative communication strategies that allows it to significantly
outperform a cooperative team", gaining 112–229%, its messages reconstructing poorly under interpretability probes (mAP
0.11–0.32 versus 0.66–1.00 for honest agents) — and "adversarial communication only emerges under resource contention"
[S] ([CoRL 2021](https://proceedings.mlr.press/v155/blumenkamp21a/blumenkamp21a.pdf)). Loong's sonar is exactly a shared
channel under resource contention.

**[R] What that means for sonar.** Three things; the third is the one `strategy.md` is missing.

- Encryption (§S6) is necessary but not sufficient: an encrypted ray is still an *observable event* at a known position
  and direction, so firing leaks that one of our dragons is on that line. Pad or accept the leak, but do not assume
  encryption hides the transmitter.
- Spoofing is a real offensive option with a large published effect size [S]. A forged "enemy queen seen at (x, y)",
  aimed along a line their dragons sit on, costs one message and can pull escorts off station — if their protocol is
  unauthenticated. §S6 plans a MAC for ours; attacking theirs is the symmetric and cheaper half.
- **Implicit coordination should carry the roles; sonar should carry only observations.** Every dragon knows with zero
  bandwidth: the map, the round, its own id, and the symmetric starting layout ([S] maps are mirror- or
  rotation-symmetric with alternating team lines), hence which ids its team has. So assign roles by a deterministic
  function of `(id, round, map)` every dragon computes identically — ids 0/1 queen; the two lowest live non-queen ids
  escort; `id mod 3 == 0` hunt; rest farm — and never transmit a role. That is FakePsyho's statelessness argument [S]
  applied to a channel the enemy reads. The honest limit: implicit coordination only works on *globally known* facts,
  and with 7×7 vision positional knowledge is private, so enemy-queen sightings genuinely need bandwidth. Spend the
  channel there and nowhere else.

---

## 7. What to implement, in order

Line counts are for gP's `main.cpp` and are rough. Every test is against gQ (`research_new_meta/s2_gQ`) plus the
archetypes named in `strategy.md` §5.

| # | Technique | LOC | Tested against |
|---|---|---|---|
| 1 | **Turn-layered free-space test.** For each candidate first move, layered BFS over remembered-free cells: ring `f(L)` free, then out to `R(L)`. Expand two turns. Reject any move whose 2-turn reachable area `< L` (queen: hard filter; drones: penalty, since §1 self-trap is recoverable). Prefer the move maximising reachable area, tie-broken on edge count (a1k0n `K2 > K1`). | ~70 | Queen self-trap death rate and deaths-in-kelp vs gQ, on labyrinth_1 / caverns_0 / g11_fortress_1. |
| 2 | **`turnsToReach(p, L, maxTurns)` as one shared primitive.** The §2 two-level layered expansion, Pareto-pruned to two entries per cell. Replaces straight-line `R(L)` everywhere: enemy threat masks for the queen, assassin routing in `findAttack`, feeder routing. | ~90 | Threat false-positive/negative rate replayed over existing games; enemy-queen kill rate and kill round vs gQ and vs an S1+S2 turtle. |
| 3 | **`d(L) = (L−1) mod 4` length policy.** Queen targets `L ≡ 0 (mod 4)` and refuses to pay a segment while `d(L) = 0` unless every alternative is lethal; assassins target `L ≡ 1 (mod 4)`; segment price in the move scorer is `base + bonus·[d(L)=0]`. | ~25 | Grid over queen target residue {0,1,2,3} × assassin residue {0,1}: queen length at r250/400/500, count of free-step-boundary crossings per game, win rate. |
| 4 | **Weighted Voronoi board control.** One multi-source BFS, each dragon's frontier rate-limited by its own `f_i`; score `own − enemy`, tied cells scored 0 **and** added to the queen's danger mask. Used as a tiebreak term in move scoring and to pick the nest. | ~60 | A/B the term's weight at 0 / small / large; queen's component area and cut-vertex count at r250/400; win rate. |
| 5 | **Cut vertices of the queen's component → escort cells.** Hopcroft–Tarjan over her reachable free component; escorts are assigned to the cut vertices separating her from enemy-first territory, with the assignment made *after* enemy moves (high ids act last). Escort count = `|X|`, capped. | ~80 | 0/2/3/4 escorts × placement rule (nearest-to-queen vs cut-vertex) on queen survival to r500 and pearls per dragon-turn. The escort paper predicts a cliff at 3. |
| 6 | **Hill climbing over the joint action vector.** After the greedy per-dragon pass, loop while instruction budget remains: pick a random dragon, resample its action, keep if the team score improves. | ~70 | Iteration cap 0 / 8 / 32: teammate head-on rate (baseline 9/10 of head-ons), queen survival, win rate. |
| 7 | **Implicit role assignment; sonar for sightings only.** Roles from `(id, round, map)`; drop every role/intent message; keep encrypted enemy-queen sightings and the heartbeat from §S6. Optionally one spoofed sighting per game at a known enemy line. | ~40 | Bandwidth used per round; queen survival with roles-over-sonar on vs off; spoof test against our own S1+S2 build. |
| — | **Skip:** Hamiltonian cycles, tail chasing, Jump Point Search (unsound, §2), MCTS, deep maxn, learned evaluation. | 0 | — |

**[R] If only three ship before 2026-10-10: 1, 2 and 3.** Items 1 and 2 are the same BFS written once and reused; item 3
is twenty-five lines on top. Together they replace `strategy.md`'s straight-line `R(L)` reach — which overestimates
threat through kelp and underestimates it around portals — with a terrain-aware primitive, and they add the one piece of
the rule change nobody else will have read carefully: the free-step allowance is a recurring *income* with a cliff every
four segments, and the cheapest length at which to *have* a free step is the worst length at which to *spend* one.
