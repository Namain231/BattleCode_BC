# Strategy for the queen rules (2026-10-01)

**[S]** marks a sourced fact (a rules page, one of our files, or a URL). **[R]** marks my reasoning, which is
untested. The rules pages are the copies in `/tmp/claude-0/docs_new/`. The map numbers come from a script over
`repo/maps` and `maps_rm_dev` that uses torus Manhattan distance and ignores kelp, so every distance below is a
lower bound.

## TL;DR

1. **Turn order is the key fact.** [S] Dragons act in ascending id order (`structure.md`). [R] So both queens
   (ids 0 and 1) act before every drone in every round. A queen seen anywhere in round r stays on that cell until
   round r+1. She can't dodge a strike once a round has started. Her safety depends on where she moves before
   the drones act.
2. **Killing the queen is cheap and decides the game.** [S] Any head-on kills both dragons whatever their
   lengths, and a dead queen counts as length 0. [R] Trading a length-2 drone for the enemy queen wins the
   tiebreak. Length gives no protection here, unlike Battlesnake, where the longer snake survives a head-on
   ([rules](https://docs.battlesnake.com/rules)). Length buys speed and strike reach.
3. **Strike reach now grows with length.** [S] Paying for an extra step needs a length of at least 3
   (`execution-order.md`). [R] So a dragon of length L can sprint into a known head up to R(L) = L−2+ceil(L/4)
   steps away (it was L−1). Dragons of length 5 to 12 become long-range assassins.
4. **The swarm economy is unchanged; only the queen should stay long.** [R] Length-2 drones still get the most
   movement per segment. For the queen, length means speed, and she needs speed to escape and to eat feed drops.
5. **The first meta will be random queen deaths.** [R] Most first patches only change "longest dragon" to
   "id 0/1". Those queens will still bud down to length 2 and wander among the swarm's head-on trades ([S] "tens of
   kills per game", `INSIGHTS_AND_PLAYBOOK.md` §2). A queen that stays long and avoids enemy heads, plus drones
   that strike the enemy queen, should pay off early.

## 1. What the change does

| L | free steps f=ceil(L/4) | strike reach R(L) (old) | free steps per segment |
|---|---|---|---|
| 2 | 1 | 1 (1) | **0.50** |
| 3 | 1 | 2 (2) | 0.33 |
| 4 | 1 | 3 (3) | 0.25 |
| 5 | 2 | **5** (4) | 0.40 |
| 9 | 3 | **10** (8) | 0.33 |
| 12 | 3 | 13 (11) | 0.25 |
| 16 | 4 | 18 (15) | 0.25 |
| 40 | 10 | 48 (39) | 0.25 |

[R] What follows:
- **The queen is a fixed dragon.** The team must keep one known dragon alive for 500 rounds, and enemies can
  recognise her on sight ([S] vision reports each segment's team and id). Her death does not end the game
  ([S] only elimination does). If both queens die, the old rules apply again: longest dragon, then total length.
- **Only her head can be hit.** [S] A dragon that moves into a body kills only itself. [R] So the queen's body
  works as her own wall. A long, coiled queen leaves few paths into her head, which gives the blog's coil
  ([S] `blog/13-tactics.md`) a new reason to exist.
- **Chases.** [R] A queen with f ≥ 2 (L ≥ 5) gets away from 1-step drones for free. A drone can sprint only L−2
  extra steps before it has to eat again. A queen of length 2–4 is no faster than a drone.
- **Feeding.** [S] A dragon eats at every step of a multi-step move, and the free-step count uses its length at the
  start of the move. [R] A length-20 queen can sweep 5 cells of feed drops per turn. This removes the intake
  bottleneck where 15–41% of drops went uneaten ([S] `insights.md`, "New-map cycle").
- **Splitting** costs the dragon speed, not the team. The real cost is the queen splitting: [S] she keeps her
  head and id. [R] But she loses speed and reach.
- **A split is a pause.** [S] A split is the whole action, so the dragon doesn't move that turn. [R] A trapped
  queen with L ≥ 4 can stay put by splitting off 2 segments each turn. gP's `doomedSplit` assumes the parent dies
  and the child lives, which is wrong for the queen.
- **Start positions are known.** [S] Maps are mirror- or rotation-symmetric, and team lines alternate, so enemy
  dragon 2k+1 is the mirror of our dragon 2k. [R] There are 3 candidate positions for the enemy queen's start. A
  dragon that sees its mirror partner learns which symmetry the map uses.
- **Current maps.** [R] On Default and Colosseum the queens start 2 apart through the wrap, so a round-0 queen
  trade is possible. On Dilemma, Slithery Fight, g11_fortress_1 and g11_open_* a long starting dragon is within
  reach of the enemy queen at round 0: on Slithery Fight a 25-long non-queen reaches 29 tiles against a queen 18
  away. Margins are 0–2 tiles on Arena, Portals, caverns_0 and labyrinth_1. The tournament's new maps will
  probably be designed around queens, so don't rely on these numbers.

## 2. Candidate strategies

The control for every test is gQ (`research_new_meta/s2_gQ`, the other agent's id-0/1 fix to gP). Setup: zig
judge on unswbc 1.2.3, set B plus the live maps, paired seeds, both sides. Metrics: queen survival to r500,
enemy-queen kill rate, queen length at r250/400/500, then win rate. Line counts are for gP's `main.cpp`.

### S1. Queen safety core (first)
- **Idea.** The queen (`MY_ID == MY_TEAM`) never takes a head-on. Her danger uses the enemy's full R(L),
  computed over remembered free cells. Any step inside an enemy's reach is filtered out, not just penalised. She
  doesn't split voluntarily below length 5. If every move is fatal, she splits to stay put.
- **Why.** [R] Losing the queen loses the game, and drones always act after her.
- **Counter.** Enemy assassins outside her view (S4).
- **Information.** Enemy heads she sees, plus heads her drones report this round.
- **Cost.** About 60 lines (`reaches`, `findAttack` desperate path, `protectedQueen`, `doomedSplit`).
- **Test.** Queen survival against gQ and against an S4 hunter build.

### S2. Escort, screen and nest
- **Idea.** 2–4 high-id drones stay 2–4 tiles from the queen, between her and enemy heads. Bodies block strike
  paths, and high ids move after the enemy drones, so they can close gaps. In mazes the queen finds a nest: a
  dead-end pocket she fills with her coil, so her head is exposed only at the entrance. Our own drones must never
  hit her head. [S] In the blog's roles bot, 9 of 10 head-ons were between teammates (`blog/12-roles.md`).
- **Why.** [S] In Battlecode 2024, cheap flag snipes by mid-ladder teams forced a detect-and-reinforce defence
  ([Cout for Clout](https://battlecode.org/assets/files/postmortem-2024-cout-for-clout.pdf)). In 2023, defenders
  waited one step outside the action radius instead of crowding the base
  ([4 Musketeers](https://battlecode.org/assets/files/postmortem-2023-4-musketeers.pdf)).
- **Counter.** Strikes through gaps. Escort duty also starves the economy, so give it a budget.
- **Cost.** Escort about 80 lines, nest BFS about 120.
- **Test.** Against S4 hunters, compare 0, 2 and 4 escorts on queen survival and pearls per dragon-turn.

### S3. Queen growth: reach length 9 early, then keep growing
- **Idea.** The queen buds only at L ≥ 7, never below 5. Feeding starts early. Drop the `max(10, 2·MY_LEN)`
  threshold, which deadlocked feeding ([S] `insights.md`, "Cycle 2"). Feeders die only 1–2 cells ahead of her head
  ([S] top teams waste 3–12% of feeds, we waste 24%; `insights.md` §3). The target is above the 30–40 length
  top queens reached at r500 ([S] `insights.md`).
- **Why.** [R] At length 9 (f = 3) she outruns every short drone and can sweep feed drops. Queen length is the
  only tiebreak that counts while both queens live.
- **Counter.** Fewer buds early costs population ([S] the edge at r50 predicted results against v7.12,
  `HANDOFF.md`. The top-16 read says early economy is not what separates the top teams). On 1-dragon maps the
  queen has to bud, keeping L ≥ 4.
- **Cost.** Parameters plus about 30 lines (`trySplit`, `swarmSplit`, `tryFeed`).
- **Test.** Grid of queen minimum length {2, 4, 5, 9} × feeding start round {0, 150, 250}. Read `tools/tempo.py`
  at r50 alongside queen survival.

### S4. Spotter and striker hunting
- **Idea.**
  - (a) Any dragon except the queen strikes if the enemy queen's head is within R(L) on a known-safe path. In
    `findAttack`, set `worth` when `dr.id == 1-MY_TEAM`, set `maxSteps = R(L)`, and lift the 4-step cap.
  - (b) A spotter that sees her sends her cell, length and round by sonar. A teammate with a higher id receives it
    the same round, while she is still there, and strikes if its remembered path is within R.
  - (c) Hunters of length 5–9 drift toward her last known or predicted area (reuse `wHunt`).
- **Why.** [R] One drone for the game. [S] Halite II: "substantially easier to execute a strong rush than to
  defend" ([recursive.cc](https://recursive.cc/blog/halite-ii-post-mortem.html)). generals.io players find the
  hidden general from movement traces ([neelr](https://notebook.neelr.dev/stories/on-generals-io-tactics)).
- **Counter.** S1 and S2.
- **Information.** Remembered terrain along the path (a blind sprint dies in kelp), and a sighting of her this
  round.
- **Cost.** (a) about 20 lines, (b) about 60, (c) about 40.
- **Test.** Enemy-queen kill rate and kill round against gQ, S1 and S1+S2. Ship (a) first.

### S5. Opening rush and anti-rush
- **Idea.** In round 0 the queen works out the 3 candidate starts for the enemy queen and broadcasts them. Drones
  near a candidate check it.
- **Anti-rush.** If any enemy is already within reach at round 0, the queen moves away first. She acts before
  every drone, and queen A acts before queen B.
- **Queen-for-queen trades.** [R] Trading queens takes the game back to the old rules. Accept the trade only when
  our longest other dragon and our total length lead.
- **Why.** [R] Queens start at length 3–4 (R = 2–3, f = 1) at a known place, before any defence exists.
- **Cost.** About 70 lines.
- **Test.** Default, Colosseum, Dilemma, Slithery Fight, caverns_0, plus generated maps with the queens close
  together. Measure queen kills before r50.

### S6. Encrypted sonar and queen-status flags
- **Idea.** gP's queen gossip is plaintext (`main.cpp:1286`: magic `0xB0C7`, x, y, len, round, id). Any enemy
  segment a ray hits learns where our queen is. Encrypt it with a keyed PRF (64-bit secret mixed with the round),
  add a MAC, and reject stale messages. Add three flags: "enemy queen seen at", "enemy queen dead", and a queen
  heartbeat. If the heartbeat is silent for N rounds, presume our queen dead.
- **Why.** [S] The enemy hears every ray, and messages can be spoofed (`blog/14-sonar.md`). Six top teams sent
  plaintext (`insights.md` §5). [R] Decode theirs and look for queen positions.
- **Cost.** About 50 lines.
- **Test.** Unit-test encode and decode. Check that our payloads look uniform in replays.

### S7. Endgame state machine for the three tiebreaks

| Belief state | Policy |
|---|---|
| Both queens alive | S1–S4, and the queen grows. Optionally keep one spare dragon of length 12+ as insurance for tiebreak 2. |
| **Enemy queen dead, ours alive** | We win unless our queen dies or we are eliminated. Maximum safety: nest, escort, no risky eating. Drones block or kill the enemy's all-in hunters. |
| Our queen dead | All-in hunt (S4). Also grow our longest dragon, because a kill sends the game to tiebreak 2. |
| Both dead | The old game: gP's longest-dragon consolidation. |

[R] About 60 lines. Test on scripted maps.

### S8. Worker lengths
[R] Keep 2+2 budding ([S] every top team buds at length 4, `insights.md`). Add a hunter class at length 5 or 9:
lengths 4k+1 gain a free step. Test hunter shares of 0, 10 and 20%.

### S9. Decoys: skip
[R] Vision shows each dragon's id.

## 3. Likely meta and early exploits

1. **Days 1–2: the id-fix wave.** [R] Most teams' queens keep budding into the swarm and die at the background
   head-on rate. Exploit it with S1 plus S4(a), which is cheap and pays off fastest, and S5 on maps where the queens
   start close.
2. **Days 2–5: protected queens.** [R] Teams add no-split and flee rules. Exploit it with S4(b) and (c): hunters
   strike from beyond the queen's 7×7 view, and queens that haven't reached f ≥ 2 are still slow.
3. **Days 5+: grown, escorted and nested queens with spotter networks.** [R] The game turns into early
   protection plus steady growth, and sonar gets contested (decoding, spoofing). [S] The organisers say the
   constant 4 is subject to rebalancing. Compute f and R from one shared function. [S] Past seasons' metas
   turned after balance patches
   ([BC2017](https://devyaoyh.github.io/battlecode2017_edoctablet/), 4 Musketeers 2023).

**Order before the 2026-10-10 phase:** S1, S4(a), S6, S3, then S2 and S4(b), then S7.

## 4. What transfers from our work

| Item | Verdict |
|---|---|
| Queen election by longest dragon (`considerQueen`, gPQ) | **Drop.** The queen is `MY_TEAM` (gQ). |
| `protectFrom` 340 / `protectedQueen()` | **Change:** protect from round 0, with a length floor. |
| `tryFeed` thresholds, `feedRadius` 10 | **Change:** feed the fixed queen from about r150, dying 1–2 cells ahead of her head. |
| `findAttack` (cap 4, L−1), `reaches` | **Change:** use R(L). The enemy queen is always worth it. The queen herself never attacks. |
| Sprint cost x−1 | **Change** to max(0, x−ceil(L/4)). The old cost is safe but wastes free steps ([S] `CHANGES`). |
| `doomedSplit` for the queen | **Change:** stall-split instead. |
| Queen gossip | **Change:** encrypt (S6). |
| Bed-gap learning, swarm budding, mining | **Keep:** the economy is unchanged. |
| gD tabu | Optional. It was neutral on unseen maps ([S] `insights.md`). |
| rulemine | **Keep the machinery.** The old-rule corpus is stale for queen decisions. Re-scout about 300 new-rule games from day 3. Add features `is_queen`, `d_enemy_queen`, `queen_threat` and a `queen_strike` decision. Re-check old death and feed rules. |
| `tempo.py`, `endgame_len.py`, `death_context.py` | **Keep.** Add a queen report: survival, death cause and round, kills, and length. It becomes the main measure of whether a change works. |
| bceval | Retrain on new-rule games or drop it. |
| `gen_random_maps.py` | **Fix** team alternation. Add maps with queen distances from 2 to 30, and maps where the queen is not the longest starting dragon. |
| `elo_bot.py`, `strong_panel.py` | **Rewrite** for continuous autoscrims. |

## 5. ELO and autoscrims

[S] (`elo.md`, `game-format.md`)
- Each submission has its own rating plus a per-map offset, updated by a Kalman filter. The team rating is the
  active submission's rating averaged over the ranked map pool.
- A new submission inherits the previous one's rating with ±75 extra uncertainty. Identical code resumes its
  old rating, and so does reactivating an old submission.
- Autoscrims run continuously at 3 per hour per team, each a five-game ranked battle. Opponents are within 50
  places either side. DEV battles are a separate 60 games per hour. Moving first is worth +20.

[R] What that means for us:
- **The ladder is a free A/B test.** It plays about 15 ranked games an hour and shows per-map ratings for each
  version, and switching back costs nothing. Promote a version only once its uncertainty has settled (1–2 days).
- **Don't churn.** Every upload resets the uncertainty, and a bad version moves the team rating quickly. Batch
  changes and screen them locally first against three archetypes: gQ (naive), a rusher (all-in S4) and a turtle
  (S1+S2). Mixing in old opponents breaks self-play cycles
  ([Asymptotic Labs](https://medium.com/asymptoticlabs/battlesnake-post-mortem-a5917f9a3428)).
- **Per-map offsets reward map hacks, but the final is all new maps.** Judge a version by its overall rating
  and by local unseen-map panels, in line with our no-map-specific-strategy rule.
- **Use DEV battles** to play specific top teams.

## Sources

Sources are linked inline. There is no public discussion of the queen change yet: not on over-yonder.tech/games/loong,
the organisers' blog, or [ryuken101's repo](https://github.com/ryuken101/UNSW-Battlecode-2026). Battlecode 2022
also used surviving bases as a tiebreak ([5 Musketeers](https://battlecode.org/assets/files/postmortem-2022-5-musketeers.pdf)).
