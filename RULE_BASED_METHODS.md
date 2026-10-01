# Rule-based methods for the UNSW Battlecode 2026 dragon-game bot

Written 2026-09-30. Scope: hand-written techniques only (no neural nets, no RL), for a C++ bot where every dragon is a
separate process and coordination is limited to a 7x7 view plus 64-bit sonar.

## 0. Provenance and how to read this

Labels used throughout:
- **[SOURCED]** a claim I read on the cited page. Numbers are copied as the page gave them.
- **[INFERENCE]** my reasoning. It may be wrong. Nothing tagged this way was checked against your bot source.
- **[NOT VERIFIED]** I could not reach a primary source. I say so instead of filling the gap.

Limits you should know about:
1. I did **not** read your bot source (`main.cpp`, `policy.hpp`). Everything about your bot comes from the notes:
   `RESEARCH_METHODS.md`, `HANDOFF.md`, `S4_7_PLAYBOOK.md`, `INSIGHTS_AND_PLAYBOOK.md`, `insights.md` (line 1986 to the
   end) and `game-mechanics-summary.md`. Where an item depends on code I have not seen, it says "verify in source".
2. Web pages were read through a fetch tool that summarises pages with a small model. Text in quotation marks is what
   that tool returned as quotes. The xathis post-mortem and the Loong posts came back with direct quotes. The other
   pages came back as summaries. Treat page-level numbers as "as reported by the fetch tool" and check the page before
   you build anything on a specific figure.
3. Several pages could not be read: Kaggle writeups (they render in JavaScript and returned only metadata), the Royal
   Society 1996 threshold paper (HTTP 403), most of the Loong repo beyond its README, and the Halite III winner's
   write-up (not found). Section 9 lists every gap.
4. `docs/*.md` from your Downloads folder was not staged. I used `game-mechanics-summary.md`, which was already in uploads.

## 1. Bottom line

1. **None of the classic rule-based winners had your coordination constraint.** Ants (xathis), Halite II/III top bots
   and Tron (a1k0n) were single processes that saw every unit. The decentralised evidence base is thin. It is
   essentially the Loong roles bot (+257 Elo, but against a weak first bot and only 27 games) plus your own
   experiments. [INFERENCE from sources in section 2]
2. **Your "hard friend-zero" is the Ants nearest-agent assignment implemented with local vision.** It is not a hack
   to remove. The Ants winner's rule is "search from all foods via bfs and make the first ant found move into the food
   direction." Your rule is the same thing computed from the friends you can see. The difference is that xathis's
   version is exact and global, and yours is local and can leave dead zones. The one untried refinement is to make
   ties and orphaned pearls deterministic without softening the zero (item 5). [INFERENCE]
3. **The strongest transferable pattern is "gate by condition, not by clock", combined with a closed-loop controller.**
   Response-threshold allocation (Bonabeau/Theraulaz), Loong's role-by-rank-with-memory, and xathis's
   "aggressive if 14 own ants are close" are all conditions on observed state. Your clock switches (`budUntil`,
   `feedFrom`) are the opposite. S.1 (shifting the clock) was directionally negative. No source I found validates
   clock-gated phases. [INFERENCE]
4. **Top teams' one visible advantage you can still copy is where their deaths land.** Your own data: head-on drops go
   60/34 own/enemy for you against 71-84/11-23 for calc, cheji bt and FTM, and 24% of your fed pearls are never eaten
   against 3-12% for top teams. Halite III's 6th-place bot gets the same effect by deciding engagements from local
   force balance within radius 8. [SOURCED for both the Halite claim and your numbers; the link between them is INFERENCE]
5. **Search is the wrong first investment.** Tron's winner says evaluation quality dominates depth. In the closest
   search analogue I found (Battlesnake IDAPOS paper), search failed when the evaluation over-weighted territory and
   under-weighted food. Your Voronoi-lite attempt collapsed Dilemma for a related reason, and your own data
   retracted "area control" (area tracks population). Keep search to a bounded, optional, late experiment.
6. **The claim that rule-based bots generalise better than learned ones is not supported by a controlled
   comparison in any source I found.** Evidence is mixed. Halite and generals.io favour heuristics. Hungry Geese top
   entries were learned, with a rule-based safety overlay. The Loong author's own flood-fill bot went from 100% on
   bundled maps to losing on generated maps. The clean way to settle it for your bot is cheap: run the champion with
   and without the network on `maps_gen` (item 2).
7. **Testing:** SPRT with paired seeds is standard practice (fishtest, the Loong verdict tool, a CodinGame Tron
   harness). Your problem is the mechanism metric per change, which you already do well. The missing piece is
   pre-registering the end-metric (queen length at r400) next to the mechanism metric, because feedDist moved its
   mechanism (41% to 94% feed targeting) and nothing downstream.
8. Section 7 is the prioritised shortlist: eight items, two of them diagnostics, one (queen250c ladder A/B) an existing
   lead, and none of them a parameter transplant.

## 2. Q1: what won in the closest analogues

"Central?" means the winning bot was one process with full knowledge of all its units. "Needs decentralised
coordination?" is the question for your constraint.

| Competition / bot | Mechanism (as reported) | Source | Central? | Needs decentralised coordination? |
|---|---|---|---|---|
| Google AI Challenge Ants 2011, **xathis (1st)** | Food: "search from all foods via bfs and make the first ant found move into the food direction"; no saved food locations; no attempt to have one ant take two foods. Exploration: each tile has `exploreValue`, +1 per turn unless an ant of his can reach it within 10 steps; idle ants run BFS to depth 11 for the highest summed value. Hills: up to 4 ants within 20 steps, single ant if total ants <= 10. Defence only with <= 4 hills. Tasks run in fixed order hills, food, explore, combat, defence, escape, and each ant moves immediately when assigned, so later tasks cannot undo it | xathis post-mortem | Yes | No. Every ant is in one process |
| Ants, xathis combat | Divide fighting ants into groups with limits on own moves and enemy count; simulate all own move combinations against all enemy replies, one turn ahead, alpha-beta style. v1 handled up to 7 ants; "move check lists" (a dependency table of which enemy moves matter for each own tile) made larger groups feasible. Eval: aggressive `enemyDead*300 - myDead*180 - distValue`, otherwise `enemyDead*512 - myDead*(512+256) - distValue`. Aggressive only when some own ant has >= 14 own ants close ("Why 14? Mostly because 42 is divisible by 14!") | same | Yes | No |
| Ants, secondary | A later participant says xathis's strategy was "a simpler, solid approach" and that every move depended "entirely on the local environment of the ant" (as relayed by another participant) | merrilledmonds blog; LessWrong post-mortem | n/a | n/a |
| **Halite II, reCurse (1st)** | Strategic pass assigns roles (colonize, defend, attack) by distance scores with penalties and bonuses, including ships allied planets will produce in the next 10 turns. Tactical pass is hill-climbing over ship positions against 19 precomputed enemy response patterns, non-linear health tiers, "will not mind trading ships for no reason, as long as there is no net loss". Survival mode maximises closest-enemy distance | reCurse Halite II post-mortem; lakesidethinks review | Yes | No |
| Halite II, FakePsyho (2nd) | Stateless, single evaluation function, global greedy assignment over all (ship, action) pairs | lakesidethinks review (secondary) | Yes | No |
| Halite II, **Shummie (3rd)** | Behaviour-based roles (settlers, distractors, defenders; about 15% of ships each in the first two roles). Avoids fights when outnumbered and retreats to friendly ships. A "non-aggression pact": a secret handshake sent through ship movements, "0 false positives" in two weeks, but early signals crashed about 30% of games | Shummie Halite-2 post-mortem | Yes | Only cross-team (implicit signalling) |
| **Halite III, reCurse (3rd)** | Priority-ordered roles; candidates sorted by score and assigned greedily, path recomputed and re-sorted on conflict; cycles and swaps detected by a linked list; spawn policy "ultimately defeated by a round of simplification that worked out better with very simple rules"; params separate for 2p/4p | reCurse Halite III post-mortem | Yes | No |
| Halite III, TheDuck314 (6th) | Miners score every square by round-trip time. "Ships were way too eager to abandon the current square", so distance is multiplied by 1.75 and a new target needs 3x the halite of the current square. Traffic control by purpose priority. Combat: local force balance within radius 8; ram when allies outnumber. "Mining is the most important part of any bot." Widening the combat radius gave "big self-play improvements" | halite2018 README | Yes | No |
| Halite III, mlomb (18th), stonet2000 (66th) | mlomb: friendliness metric within distance 4 gates dodging; genetic algorithm + CLOP tuning; no ML. stonet2000: tried an ML library to tune parameters, "don't have enough data from running matches against myself"; tests by running the bot against itself twice with a team switch | both post-mortems | Yes | No |
| Halite III overall winner | **[NOT VERIFIED]** I could not find the winner's write-up | n/a | n/a | n/a |
| **Tron, Google AI Challenge 2010, a1k0n (1st)** | Voronoi evaluation ("whether player 1 can reach it before player 2"), later refined by regression on hundreds of thousands of server games: `K1(N1-N2)+K2(E1-E2)`. Alpha-beta with iterative deepening, discarding the unfinished ply. Endgame: once components separate, switch to survival mode; chamber/cut-vertex analysis for the "battlefront". Kept 14 versions of the bot to compare. Says: "I can't believe I won decisively" | a1k0n post-mortem | Yes (2 players) | No |
| CodinGame Tron reproduction, nathanWolo (hobbyist) | Iterative-deepening negamax, bitboard Voronoi, quiescence, SPRT harness. +89.2 +/- 17.0 Elo (n=446) for bitboard Voronoi over a pre-bitboard baseline in 1v1. The repo reports free-for-all play stays weak ("~12% in 8-player mixed games, where 25% is parity", as the repo states it) | repo README | Yes | No |
| Battlesnake, IDAPOS paper | Iterative deepening with search limited to snakes near the acting snake (distance <= 2x depth). Eval: length advantage, board control by adversarial flood fill, health. Coefficients by genetic algorithm over 10,000 simulated games. Placed 2nd of 65 in the intermediate division. Failure modes: over-weighting board control neglected peripheral food; "sometimes failed to convert its length advantage" | GI-proceedings paper | Yes (single snake) | No |
| Kaggle Hungry Geese | Top entries were learned: a 3rd-place deck reports behaviour cloning + RL with modified MCTS, flood-fill features, 224 fixed matches against standard agents, TrueSkill "coliseum". A student report says top performers used "rule-based oversight to avoid getting into traps and corridors". Flood-fill "Boilergoose" was a rule-based baseline. **This is evidence against a pure rule-based story** | speakerdeck 3rd place; Wild Goose Chase report | Yes | No |
| Lux AI S2 | A rule-based GOAP agent with Dijkstra reached 23rd (top 4%). Winners' write-ups **[NOT VERIFIED]** | AdamSlay repo | Yes | No |
| generals.io | Human.exe (heuristic, "engineered without any machine learning techniques") was the strongest rule-based baseline. A 2025 paper reports a behaviour-cloning + PPO agent reaching the top 0.003% of the 1v1 human leaderboard in 36 hours on one H100, so learning later overtook it | arXiv 2507.06825 | Yes | No |
| Screeps | **[NOT VERIFIED]** I found only hobbyist repos (for example Overmind), with no head-to-head or ladder evidence | search results only | n/a | n/a |

Observations:
- [INFERENCE] The recurring winning recipe is: a strong, simple economy layer; greedy sequential assignment with
  immediate commit; a small local tactical search or evaluation at contact; and heavy testing infrastructure. Two post-mortems
  (reCurse Halite III, TheDuck314) say simplification or a better economy mattered more than clever tactics.
- [SOURCED] xathis's "aggressive when >= 14 close own ants" and your v7.12 rule "even trades by small drones when
  our swarm has 12+ units" (Playbook section 3) are the same idea: accept equal trades only with local numerical
  superiority. [The equivalence is INFERENCE.]
- [SOURCED] TheDuck314's asymmetric switching cost (1.75x distance, 3x richness) is the same device as v7.12's goal
  hysteresis (`valT[lastGoal] >= 0.75*valT[best]`). Your S4.x line had no analogue, and committed routing there was
  null (S4.16-S4.18), for map reasons stated in the notes.

## 3. Q2: coordination with local vision and tiny messages

Channel facts, from `game-mechanics-summary.md` [SOURCED]: one 64-bit value per direction per turn, a straight ray
that stops at the first kelp or the first dragon (friend or foe), no sender or team information attached, read at
the recipient's next turn. Loong's blog adds a 12-turn memory of heard teammate lengths and self-message filtering
because rays wrap.

| Mechanism | What it is, with source | Cheap / deterministic / testable here? | Mechanism metric |
|---|---|---|---|
| **Response threshold** | Individual engages task j with probability `s^2/(s^2+theta^2)`; thresholds fall when a task is performed and rise otherwise, so specialists emerge from identical individuals (Theraulaz, Bonabeau, Deneubourg; SFI PDF). Loong's version is deterministic: champion if length >= longest teammate heard in 12 turns, kamikaze if <= 3 and a longer teammate exists, else worker. It beat the first bot 21-2-4, +257 Elo (CI +122 to +558), verdict after 27 games (cap 155). The same roles without splitting were "+14 Elo after 128 games with an interval from -47 to +75", so the gain came from the combination | Cheap. Make it deterministic by comparing a stimulus to a threshold and breaking ties with a hash of (id, round) instead of random draws. Testable | Role-switch churn per dragon per 100 rounds; fraction of turns in each role (Loong: kamikaze was 5.3% of turns before splitting) |
| **Nearest-agent assignment (Ants)** | xathis: BFS from each food, first ant reached takes it. A decentralised emulation computes "am I the nearest of the friends I can see" for each visible pearl. This is your friend-zero. [Equivalence is INFERENCE] | Cheap, already in the bot. Refinement is item 5 | Double-chase rate; orphaned-pearl latency (both computable from replays) |
| **Contract net** | Smith 1980: manager announces a task, contractors bid, manager awards | Expensive here. It needs an announce/bid/award exchange over rays that stop at the first dragon and carry no sender info. Your own data: receiving a message changes the next move by at most ~4 points for every team, and the #1 team sends no sonar at all (insights.md, "Sonar and echo") | Not recommended; no metric needed |
| **Stigmergy** | Coordination through the shared environment rather than messages. [INFERENCE] Here the environment already carries signals: pearl drops from a death are visible to anyone within 3, and top teams' "designed death channel" is effectively a stigmergic food marker. Your S4.6 fountain-pheromone grids were reverted (S4_7_PLAYBOOK section 7) | Free, but gains are the feed geometry in item 3, not a new grid | Recycled-by-own-team % (death_context.py) |
| **Reservation table** | Silver 2005 (AIIDE): Cooperative A* searches space-time and WHCA* limits the window; every agent consults a shared table of claimed cells | A shared table is not available. Your physical bodies are already a reservation: S4.22 (friendCloser) and S4.25/26 (permeable teammate bodies) showed removing them hurts. `T_INTENT`/`T_CHOKE` from S4.6 are the message version and T_CHOKE was null | Not recommended |
| **ID-based leader election** | Bully algorithm (Garcia-Molina 1982): highest ID wins ties. [INFERENCE] queen250c already made the election depend on visible length and cut identity churn 65 to 17; an id tie-break is the remaining one-line piece (S4_7_PLAYBOOK section 7) | Cheap, deterministic | Queen identity changes per game after r250 (already tracked) |

[INFERENCE] The cheapest, most testable, most deterministic of these for your bot are response-threshold feeding
(item 6), the friend-zero tie-break (item 5) and the id tie-break inside queen election (fold into item 1).

## 4. Q3: rule-based search, reported strengths and failure modes

**Reported strengths [SOURCED]**
- Tron (a1k0n): Voronoi evaluation plus iterative deepening alpha-beta, with endgame survival mode after the board
  separates. The coefficient fit came from regression over hundreds of thousands of server games.
- CodinGame reproduction: bitboard Voronoi gave +89.2 +/- 17.0 Elo in 1v1 against a slower baseline. A paranoid
  free-for-all variant (closest rival as true min, others greedy) gave +57.3 +/- 11.8 Elo in 4-player.
- Ants (xathis): one-turn group minimax limited by "move check lists". It was made tractable by restricting to local
  groups, not by going deeper.
- Halite II (reCurse): hill-climbing against a small set of precomputed enemy responses, so the "search" is over our
  positions only.
- Multi-player pruning (Sturtevant): paranoid search "reduces an n-player game to a 2-player game" and searches about
  (n-1)/n deeper in theory. It won in Chinese Checkers (58-61%) where maxn cannot prune, and tied in Spades and
  4-player Hearts.

**Reported failure modes [SOURCED]**
- a1k0n: "a deep minimax search using a flawed evaluation heuristic is self-deluded about what its opponent is actually
  going to do"; he lost many games "miscounting the opponent's space in the endgame".
- IDAPOS: over-weighting board control neglected peripheral food and failed to convert a length advantage.
- CodinGame reproduction: strong in 1v1, weak in the 8-player free-for-all.
- Nau 1983: deeper minimax can give worse decisions when sibling node values are independent and branching is large.
  It does not appear in chess-like trees with correlated siblings.
- Sturtevant: paranoid is conservative, and "changing the tie-breaking rule may arbitrarily affect the maxn value".

**When heuristics beat search [INFERENCE from the above]**
- The literature supports "evaluation quality before depth" (a1k0n, IDAPOS failure modes). It does not support a rule
  that heuristics always win.
- Search pays when a cheap, correct model exists for a small local region (Ants groups, Halite II hill-climb).
  It fails when the evaluation measures the wrong thing. In Tron the evaluation target (space) is the win condition.
  In your game the win condition is the longest living dragon at r500, and your data says area equals population
  (insights.md cycle 1, section 1), so a Voronoi term measures a proxy of a proxy. That matches your measured
  Voronoi-lite collapse.
- Your structure is favourable to small local search. Dragons move sequentially by id and enemy heads do not move
  during your turn (Playbook section 1), so a 2-ply "my move, then the visible enemy replies" is narrower than
  simultaneous-move Tron. You have about 10x CPU headroom (4-7M mean of 100M). But the cost is a large build, and
  no source shows local combat search is what separates your bot from the top teams. Your own open question (why 4
  of 5 top teams beat the champion 0-2 of 5) is unresolved. Item 5 (trade-site filter) tests the cheap half of the
  idea first.

## 5. Q4: rule-based robustness, and reconciling with "the net was the only big win"

Evidence for "rule-based generalises" [SOURCED]:
- Loong "The shape of the problem": opponents change, maps change, rules shift mid-season, vision is partial, and
  "problems like that reward bots that can be understood and changed quickly". This is an argument, with no measurement.
- Halite III: reCurse, TheDuck314 and mlomb were all rule-based, and stonet2000 abandoned ML because of too little
  self-play data.
- generals.io: the strongest rule-based baseline (Human.exe) stayed competitive until 2025 learning work.

Evidence against [SOURCED]:
- Loong "Maps nobody has seen": the author's flood-fill bot won 100% on bundled maps and lost on generated ones. Two
  bugs appeared: dragons could teleport through a portal onto their own body, and teammates collided. "We'd never
  have spotted this without the new maps." Rule-based bots fail off-distribution too.
- Your own `maps_gen` result: 15-22% against v7.12 on 30 generated maps (S4_7_PLAYBOOK section 4a). That is an
  S4.x rule bot, not the champion.
- Hungry Geese: top entries were learned, with rule-based safety rules on top.
- Ross, Gordon, Bagnell (2011): imitation learners face "poor performance in theory and often in practice" because
  future observations depend on earlier predictions (compounding error under distribution shift). This is the real
  risk for a network trained on a narrow set of maze maps.

**Reconciling with your result [INFERENCE]**
- The network was trained on, and evaluated on, the same handful of maze maps that appear on the ladder, using
  teacher games from v7.12. On that distribution there is no shift to compound, so its win says nothing about unseen
  maps. The 88% local result (`exp_nn_w2m`) and the ladder 53-65% are in-distribution.
- Your rule-only open maps are not evidence that rules are better. They are the maps where you had no network, and
  the notes do not report a rule-vs-network comparison there.
- A hybrid is the defensible design: network as a move prior on maps matching its training distribution, rules
  everywhere else, and rules as the veto (the Hungry Geese top entries did the same: learned policy plus a safety
  overlay). What is missing is the test in item 2: champion with and without the network on `maps_gen`. If the
  network's advantage vanishes there, your belief gains evidence. If it holds, the network generalises further than
  feared.

## 6. Q5: testing methodology for rule bots (short)

| Practice | What it is | Source |
|---|---|---|
| SPRT | Fix elo0 and elo1, stop when the log-likelihood ratio crosses bounds set by alpha and beta. "Generally regarded as the most important process in modern engine development." Gainer bounds test improvement; non-regression bounds test "removal doesn't degrade" | chessprogramming SPRT page |
| Paired openings | Fishtest plays game pairs from the same opening with colours reversed. Pair correlation is about -0.15, so the pentanomial variance is about 15% below the naive trinomial one | fishtest issue 348; fishtest mathematics page |
| Paired seeds and shared maps | Loong verdict tool: same map, side and seed, candidate in the candidate's seat. Changed games are weighted by the share of turns in which the changed behaviour was active. Sign-flip test at the 5% level. Also tests against a random-walk bot as a sanity check. Keeps snapshots of recent versions to catch cycling | Loong "Better, worse or undecided" |
| Harness details | CodinGame harness: 256 seeded openings, seat rotation, Plackett-Luce for N-player, accept when LLR > ln(beta'/(1-alpha)) ~ +2.94 | nathanWolo README |
| Self-play with side swap | Run the bot against itself twice with the team switched | stonet2000 post-mortem |
| Version archive and data mining | a1k0n kept 14 versions and fitted heuristic coefficients by regression over server games | a1k0n post-mortem |
| Ablation | Switch one feature off at a time and keep what matters | your Playbook section 6; reCurse Halite III (simplification beat tinkering) |
| Pre-registered falsifier | State in advance what result kills the idea. Your S4.15 falsifier fired and stopped a dead end. Write the end-metric next to the mechanism metric | insights.md S4.15; [INFERENCE] for the end-metric advice |

Two calculations of mine (Wald approximation, binary win/loss, no draws, true win rate equal to p1, alpha = beta = 0.05;
[INFERENCE], treat as rough): expected games to a verdict under H1 against p0 = 0.5 are about 530 for p1 = 0.55, 132 for
0.60, 58 for 0.65 and 32 for 0.70. This says your ~100-game ladder arms resolve ~15-20 points, which matches your
`RESEARCH_METHODS.md` table. For a continuous paired mechanism metric, the games needed are about
`7.85 * sd_diff^2 / delta^2`. With an **assumed** paired sd of 15 points you need about 18 games to see 10 points and 71
for 5 points. Measure the real paired sd from your existing replays before relying on this.

## 7. Q6: prioritised, map-agnostic shortlist

Conventions:
- "Metric in ~30 games" means a paired same-seed local batch against the champion, read with your existing tools
  (`death_context.py`, `behaviour_profile.py`, `farming_profile.py`, the queen tracker, `tempo.py`,
  `concentration.py`). Local batches are valid for self-driven mechanisms and invalid for win rate (your own finding).
- Every item needs its own pre-registered end-metric, because feedDist proved a mechanism can move without moving
  the outcome.
- Costs are my guesses. I have not seen the source.
- "Overlap" says whether the item repeats something tried.

### Item 1. Ladder A/B of `queen250c` (existing lead, do first)
- **Mechanism:** queen election on visible length cut self-splits from ~36 to ~6.8 per game and identity churn from 65
  to 17 (insights.md, cycle 2). Add the one-line id tie-break from S4_7_PLAYBOOK section 7.
- **Proxy metric:** already measured. For the ladder arm read queen length at r300/350/400 (ours 5.2/6.4/9.6,
  Stockfish 12.4/20.8/29.6), queen splits/game, and feed deaths per 50 rounds.
- **Failure mode:** the stricter election also reduced feeding (noted in the cycle-2 table), and mass feeding has
  collapsed unit counts before (Playbook section 5). Watch units at r400 and eats per dragon-turn.
- **Cost:** low (built). The work is running a same-time control arm against near-rating opponents, about 100 games per arm.
- **Overlap:** none. Not a repeat.

### Item 2. Diagnostic: champion with vs without the network on `maps_gen`
- **Mechanism:** none. It tests whether the network's gain survives unseen maps (section 5).
- **Metric:** win rate and early tempo (`tempo.py` edge@50) on the 30 generated maps, paired seeds and sides. The
  effect you measured in-distribution is large (88% local), so a paired batch of ~60 games can show whether it
  shrinks.
- **Failure mode:** generated maps may not trigger the network's maze-map gate at all (the notes say it is maze-only).
  Check the gate before reading the result. Pin the judge backend identically across both arms (your own lesson, S4_7_PLAYBOOK section 4a).
- **Cost:** very low (runs existing tools).
- **Overlap:** none.

### Item 3. Feed geometry: die only where the queen can win the race for the drops
- **Mechanism [INFERENCE on top of SOURCED rules]:** a dying dragon drops ceil(L/2) pearls on every second segment
  from the head (game rules). Require, in addition to feedDist <= 2: the queen can reach each drop cell no later
  than any visible enemy head (two BFS with arrival times, a cost you can afford at 4-7M of 100M), and the queen's
  heading does not point away from the cluster. INSIGHTS "What changes" item 2 asked for "queen within 1-2 and heading
  toward the drop cells", and feedDist only did the distance half.
- **Proxy metric in ~30 games:** fed pearls eaten by own team from 69% (champion) / 75% (feedDist) to >= 85%, "never
  eaten" from 24% to <= 10%, via `death_context.py`. Top teams: 86-95% own, 3-12% never.
- **End-metric to pre-register:** queen length at r400 must rise by >= 3 against the paired control. If the recycle
  percentages move and queen length does not, feed geometry is not the binding constraint. Stop, as with feedDist.
- **Failure mode:** stricter feeding means fewer feeds. Keep feed deaths per 50 rounds above about 7 (top teams 7-16).
  The hidden-coordination lesson applies in reverse: do not add a rule that makes feeders wait near the queen,
  because clustering jams corridors.
- **Cost:** low to medium (about 50-100 lines if the BFS helpers exist).
- **Overlap:** extends feedDist=2 (real mechanism, gate 42.5% uninformative at 40 games). Not a repeat.

### Item 4. Trade-site filter: accept or decline head-on trades by who will eat the drops
- **Mechanism [INFERENCE]:** your head-on drops split 60/34 own/enemy, while calc 84/11, cheji bt 76/20, FTM 71/23
  (insights.md, section 4). Halite III (TheDuck314) decides engagement from local force balance within radius 8,
  and Halite II (Shummie) avoids fights when outnumbered. The rule: an optional even trade is accepted only if at
  least k of our dragons are within 3 of the collision cell and the enemy has fewer than k in view; otherwise decline.
  Only accept or decline. Do not steer dragons toward friends.
- **Proxy metric in ~30 games:** own/enemy drop share of head-on trades from 60/34 to >= 72/22, with head-on trade
  count falling by no more than 20%.
- **End-metric:** edge@r100 (tempo.py) must not fall.
- **Failure mode:** your data say more deaths go with winning (84% with more deaths). Declining trades could cost
  tempo, and "retreat to friends" is steering that would break the separation friend-zero provides. Keep it a pure
  accept/decline filter.
- **Cost:** low to medium. Needs a friend-count query near a cell and a change in the trade gate.
- **Overlap:** none. `kamikazeLen` is gated off and never tested, and is a different knob.

### Item 5. Friend-zero refinement: deterministic tie-break and no orphaned pearls
- **Mechanism [INFERENCE]:** keep the hard zero for any pearl a visible friend is strictly closer to. Change only
  the boundary: on equal distance the lower id keeps the pearl, so two dragons at distance m never both zero it
  (orphan) or both chase it (double-chase). Optionally add claim hysteresis: a pearl you were closest to last turn
  stays yours while your distance keeps falling.
- **Proxy metric in ~30 games:** orphaned-pearl latency (a pearl with two or more of our dragons within 6 and none
  eating it within 10 rounds) and double-chase rate (two of ours both closing on one pearl). Both come from replay
  positions.
- **End-metric / falsifier:** eats per dragon-turn in r0-250 must not drop by more than 10%. friendCloser (soft 0.08) made
  it fall 10x. If this refinement does anything similar, revert immediately.
- **Failure mode:** this must not soften the zero. A tie-break that lets the higher id "also" value the pearl at even
  a few percent is friendCloser again.
- **Cost:** low. **Verify in source** how the current code treats `fd == m` and whether the champion's `zoneF` /
  `friendMinId` already break ties by id.
- **Overlap:** touches the coordination device S4.22 softened, but hardens instead of softening. Check the code
  before building, because the champion lineage may already do this.

### Item 6. Closed-loop feed rate by response threshold
- **Mechanism:** a stimulus `s = max(0, Ltarget(r) - Lqueen) / Ltarget(r)`, where `Ltarget(r)` is a reference
  trajectory (from the top-team numbers: roughly 12 at r300, 20 at r350, 30 at r400), compared with a per-dragon
  threshold by `s^2/(s^2+theta^2)` (Theraulaz, Bonabeau, Deneubourg), with randomness replaced by a hash of (id,
  round). Eligible feeders are drones near the queen (gossiped or visible). Thresholds drop for a drone that
  recently fed and rise otherwise, as in the source model, so a stable feeding group emerges.
- **Proxy metric in ~30 games:** queen length trajectory against `Ltarget` (mean absolute gap), feed deaths per 50
  rounds (top teams 7-16, you 1-5), role churn per drone.
- **End-metric:** queen length at r400 >= 20 (yours ~10, top 30-39) without units at r400 falling below the control
  by more than 15%.
- **Failure mode:** mass feeding collapsed units on maze maps (Playbook section 5: "the queen could not eat the pearls
  fast enough"). A closed loop should self-limit, but only if the queen actually eats. Tie to item 3 so fed pearls are
  recoverable. The Loong tactics post found the full sacrifice mechanic "consistently underperformed", so watch for
  the same.
- **Cost:** medium. A reference curve, a per-drone threshold and a hash.
- **Overlap:** partly overlaps queen250b (one third of drones feed from radius 40, tried, feeding volume was not the
  binding constraint while the queen kept splitting herself). Do it only after item 1 confirms a stable queen.

### Item 7. Queen bed-hold (layer 3 of the queen problem)
- **Mechanism:** your notes say the stable queen still barely eats (about 9 over r250-500 against Stockfish's 34,
  insights.md cycle 2) and that top team Cache me outside farms fast beds (54/67/80% at-bed time early/mid/late). Rule:
  after r250 the queen uses the miner value function, and at a fast bed (measured online from observed countdown
  resets, not from embedded map tables) it stays adjacent and coils, following Loong's coiling rule
  ("preferring moves that touch its own body segments ... only when sufficient empty space remains").
- **Proxy metric in ~30 games:** queen eats over r250-500 (9 toward 20+), queen at-bed time, queen death rate.
- **End-metric:** queen length at r400.
- **Failure mode:** Loong found a coiled champion "received insufficient food" on large empty boards, and the coiling +
  feeding bot was only "undecided" (80 wins, 45 losses in 264 paired games per the page). A coiled queen is also an
  easy head-on target. Gate coiling on bed pearl rate, not on time.
- **Cost:** medium. The known-map bed tables cannot be used if you want this map-agnostic, so the online gap estimate is
  the real work.
- **Overlap:** none tried. It is the notes' own "next" item.

### Item 8. Lead-holding survival mode for the queen, r470-500
- **Mechanism [INFERENCE]:** a1k0n switches to survival mode once the players separate, and reCurse's Halite II
  survival mode maximises the closest enemy distance. When your gossiped or visible queen is at least as long as the
  longest enemy seen, from about r470 the queen maximises the minimum distance to known enemy heads, avoids
  chamber-poor cells (your flood fill) and coils.
- **Proxy metric in ~30 games:** queen minimum distance to an enemy head over r470-500 and queen deaths r470-500. These
  are continuous per-game values.
- **End-metric:** lead-loss rate (games where your longest was >= the enemy's at r470 and you still lost). Only 36% of
  games reach the length tiebreak, so a 30-game batch has ~11 such games. Treat this as unproven until a larger batch.
- **Failure mode:** hiding stops eating and feeding. Check what `protectedQueen()` (protectFrom 340) already does past
  r470 before building. The item may duplicate it.
- **Cost:** low to medium.
- **Overlap:** extends queen protection. Verify in source.

### Explicitly not recommended (repeat, or weak evidence)

| Idea | Why not |
|---|---|
| Voronoi / territory evaluation | Tried; Dilemma 75% to 0% twice; and "area = population" (insights cycle 1) retracts the premise |
| Articulation-point / chamber-tree search | Tried (`chamberCheck`, null); in Tron it is an endgame tool for a space-winning game, not yours |
| Contract-net over sonar | Channel cannot carry sender identity or acknowledge; no source supports it here |
| Shifting `budUntil`/`feedFrom` | S.1, and the cycle-2 read reversed the premise; conditions beat clocks |
| Wider horizon / `gamma` / soft friendCloser | Five transplants, all worse |
| `exploreValue` (Ants-style staleness) | Already an S4.x term (falsified as a dominant term on Trauma); the dragon-game analogue is arrival-time pearl probability (S4.24, ~54%) |
| Route commitment / Dijkstra | Overlaps S4.16-S4.18 and v7.12's own goal hysteresis. Only revisit if a dither metric on ladder replays shows target flipping is the cause of directness 0.60 |
| Multi-ply local combat search as a first build | No source says it separates you from the top, large build, and item 4 tests the cheap half |

## 8. Standing process items (not counted as experiments)

- **Simplification pass.** reCurse (Halite III): tinkering with spawn metrics lost to "a round of simplification".
  You have 93 params, 11 inert, and `common.hpp` is 57% comments (HANDOFF). One-at-a-time ablation with
  non-regression bounds (fishtest [-5, 0] style) and the mechanism metrics above. Never ablate a physical-blocking
  or friend-zero constraint without the double-chase and eats/dragon-turn checks.
- **Unseen-map regression suite.** Add `maps_gen` to every validation batch (Loong found two real bug classes this way:
  self-portal collision and teammate collision).
- **Per-change record:** hypothesis, mechanism metric with threshold, end-metric, falsifier, written before the run.

## 9. Gaps and things I could not verify

- Halite III winner write-up, Lux AI S1/S2 winners' write-ups, Hungry Geese 1st place write-up, Screeps ladder evidence:
  not reached. Kaggle pages returned metadata only.
- Loong repo (`overyonder/the-loong-game`): only the README outline was visible. I did not read the roles source or
  the verdict tool source. The Loong numbers come from blog pages.
- The Royal Society 1996 Bonabeau paper returned HTTP 403. The threshold formula comes from the 1998 SFI preprint
  "Response threshold reinforcement and division of labour in insect societies".
- Contract Net (Smith 1980), the Bully algorithm (Garcia-Molina 1982), Chang-Roberts (1979) and Wald (1945) were
  identified through search results only and not opened. Treat their descriptions here as textbook summary.
- Fishtest mathematics page did not state its bounds or pairing rationale; the pair-correlation figure comes from
  fishtest issue 348.
- "Top teams are rule-based" is unverifiable from your data: public replays carry no CPU points and no log or indicator
  strings (insights.md, top-16 section 6). I make no claim about what the top ladder teams run.
- Numbers for implementation cost and paired standard deviations are my estimates.

## 10. Sources

Local notes (your repository, staged copies):
- `RESEARCH_METHODS.md`, `HANDOFF.md`, `S4_7_PLAYBOOK.md`, `INSIGHTS_AND_PLAYBOOK.md`, `game-mechanics-summary.md`
- `insights.md` from line 1980 to the end (post-mortem, S4.11 to S4.26, "What the top 16 actually do", cycle 2, queen250c, path directness)

Opened and read (through the fetch tool):
- Loong blog index: https://over-yonder.tech/games/loong
- Loong "Roles": https://over-yonder.tech/games/loong/roles/
- Loong "Tactics": https://over-yonder.tech/games/loong/tactics/
- Loong "Better, worse or undecided": https://over-yonder.tech/games/loong/better-worse-or-undecided/
- Loong "Maps nobody has seen": https://over-yonder.tech/games/loong/maps-nobody-has-seen/
- Loong "The shape of the problem": https://over-yonder.tech/games/loong/the-shape-of-the-problem/
- Loong "Sonar" (design notebook, no measured results): https://over-yonder.tech/games/loong/sonar/
- Loong repository (README outline only): https://github.com/overyonder/the-loong-game
- xathis, "AI Challenge 2011 (Ants) Post Mortem": http://xathis.com/posts/ai-challenge-2011-ants.html
- xathis bot repository (metadata only): https://github.com/xathis/AI-Challenge-2011-bot
- Ants secondary: https://merrilledmonds.com/blog/?p=28 ; https://www.lesswrong.com/posts/ELCsD7MYaqnkarPBi/ai-challenge-ants-post-mortem
- reCurse, Halite II post-mortem: https://recursive.cc/blog/halite-ii-post-mortem.html
- reCurse, Halite III post-mortem: https://recursive.cc/blog/halite-iii-postmortem.html
- Top-3 Halite II review (secondary): https://lakesidethinks.com/post/2018/10/halite2-strategy.html
- Shummie, Halite-2 post-mortem: https://shummie.github.io/Halite-2-Shummie/
- TheDuck314, Halite III 6th place: https://github.com/TheDuck314/halite2018/blob/master/README.md
- mlomb, Halite III post-mortem (18th): https://mlomb.dev/blog/halite-iii-postmortem
- stonet2000, Halite III post-mortem: https://stonet2000.github.io/postmortem/
- a1k0n, Google AI Challenge Tron post-mortem: https://www.a1k0n.net/2010/03/04/google-ai-postmortem.html
- nathanWolo, CodinGame Tron agent with SPRT harness: https://github.com/nathanWolo/tron-codingame
- IDAPOS Battlesnake paper: https://dl.gi.de/server/api/core/bitstreams/358e228c-0917-4849-a4fe-40d155c3232c/content
- Hungry Geese 3rd place deck: https://speakerdeck.com/hoxomaxwell/kaggle-hungry-geese
- Wild Goose Chase (Hungry Geese report): https://tonghuikang.github.io/ai-project/report.pdf
- Lux AI S2 rule-based agent: https://github.com/AdamSlay/LuxAI-competition-agent
- generals.io RL paper (describes Flobot and Human.exe): https://arxiv.org/html/2507.06825v2
- Sturtevant, "A Comparison of Algorithms for Multi-Player Games": https://webdocs.cs.ualberta.ca/~nathanst/papers/comparison_algorithms.pdf
- Nau 1983, "Pathology on game trees revisited": https://www.cs.umd.edu/~nau/papers/nau1983pathology.pdf
- Response threshold reinforcement (SFI preprint): https://sfi-edu.s3.amazonaws.com/sfi-edu/production/uploads/sfi-com/dev/uploads/filer/a7/29/a7299c65-e29c-4f60-af56-102222f8851a/98-01-006.pdf
- Silver, "Cooperative Pathfinding" (AIIDE 2005): https://ojs.aaai.org/index.php/AIIDE/article/view/18726
- Ross, Gordon, Bagnell, "A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning": https://arxiv.org/abs/1011.0686
- Chess Programming Wiki, SPRT: https://www.chessprogramming.org/Sequential_Probability_Ratio_Test
- Fishtest issue 348, game-pair correlation: https://github.com/official-stockfish/fishtest/issues/348
- Fishtest mathematics page (partial content): https://official-stockfish.github.io/docs/fishtest-wiki/Fishtest-Mathematics.html

Found by search, not opened or blocked (not relied on for any number):
- Bonabeau, Theraulaz, Deneubourg 1996 (403): https://royalsocietypublishing.org/rspb/article/263/1376/1565/69462/Quantitative-study-of-the-fixed-threshold-model
- Smith 1980, Contract Net: https://ieeexplore.ieee.org/document/1675516/
- Garcia-Molina 1982 (Bully algorithm), via: https://en.wikipedia.org/wiki/Bully_algorithm
- Korf/Sturtevant, "On Pruning Techniques for Multi-Player Games": https://www.researchgate.net/publication/221603927_On_Pruning_Techniques_for_Multi-Player_Games
- Overmind (Screeps): https://github.com/bencbartlett/Overmind
