# How our UNSW Battlecode bot works

This is an overview of team calc's bot: what it does each turn, how it was trained, and what we learned along the
way. 

## The game in one paragraph

Every dragon is a snake running its own copy of the team's program. It sees only a 7x7 window around its head, and
dragons talk to each other only through sonar pings sent along the four directions. Dragons grow by eating pearls.
They can split in two, and they can sprint several steps in one turn at the cost of segments. A game that reaches
round 500 goes to the team with the longest living dragon. Each turn has a hard CPU budget, and a dragon that goes
over it dies.

## The big picture

The bot is written in C++ and makes each decision in four layers:

1. **Sonar.** Dragons share what they know with their team.
2. **A small policy net** proposes a move.
3. **A short search** checks the net's likely moves by simulating a few rounds ahead.
4. **Hand-written rules** take over in the situations where the net is known to be blind.

Every dragon also keeps a **memory** of everything it has seen: kelp, portals, pearls, when spawn tiles will drop
their next pearl, and where other dragons were. The net, the search and the rules all read that memory.

## 1. Sonar

Every dragon sends a small packet on all four directions every round. A packet can say:

- "I am a candidate keeper, this long, at this position" (used in the endgame, see below)
- where an enemy was seen
- which map symmetries have been ruled out
- which portals have been explored

Packets are encrypted and signed, so other teams can neither read them nor fake them.

## 2. The policy net

- **Architecture.** A small MLP with two hidden layers (256 and 128 units). It is deliberately small, because it
  has to run many times per turn inside the search.
- **Inputs.** The 7x7 window, a downscaled picture of the remembered map, and a few numbers: length, round,
  dragon count, and whether the dragon can split.
- **Outputs.**
  - turn left, go straight, turn right, or split
  - how much of the body to split off
  - whether to keep sprinting after each step

**Training.** What finally worked was **behaviour cloning**: training the net to copy the moves in replays of the
top teams' games. Those games were mixed with games our own bot played, with the search switched on, on both the
official maps and randomly generated ones. Our earlier nets trained only by self-play reinforcement learning (PPO)
looked strong against each other but lost most of their games on the real ladder.

## 3. The search

On each turn:

1. The net scores every move. Every legal move above a small probability becomes a **candidate**.
2. The dragon builds an **imagined world** from what it can see and remember. Dragons it has never seen don't
   exist there, and unknown tiles are treated as open water.
3. Each candidate is played as this dragon's first move. The game then runs 3 rounds ahead (5 in the opening) in a
   C++ copy of the game engine. **Every dragon on both teams is played by our own net.**
4. Each result is scored by **our total length minus theirs**.
5. Any time left in the turn goes to extra randomized play-outs. These go mostly to the candidates that look best
   so far, which is the standard UCB1 bandit rule.
6. The best-scoring move is played. If the net's own move ties for best, it is kept.

There is no tree here: only the first move branches. It works as a tactical safety and food check, catching moves
that walk into a trap or miss a pearl. Most of the time it agrees with the net. Making the net much cheaper to run,
so the search could try more candidates within the CPU budget, was one of our bigger gains.

## 4. Rules

The rules override the net in situations it handles badly:

- **Opening**
  - **Hidden food.** Walk to food it can only reach by going around kelp, which the net doesn't plan for.
  - **Portals.** Walk through portals nobody has explored when no food is in view, and tell the team over sonar
    whether the other side was worth it.
  - **Symmetry.** Work out the map's symmetry from what has been seen, then mirror the memory, so a dragon knows
    roughly what the unexplored half looks like.
- **Any time**
  - **Escape.** A long dragon that is boxed in splits to get out.
  - **Collisions.** A dragon forced to collide picks the least bad thing to hit, and never an allied head.
- **Late game**
  - **Keeper.** Since only the longest dragon counts at round 500, the team agrees over sonar on one **keeper**
    (normally its longest dragon).
  - **Feeding.** The other dragons travel to the keeper and end themselves next to its head, so it eats the pearls
    they leave behind.
  - **Hunting.** Dragons too far away to help hunt and ram the enemy's longest dragon instead.

## Engineering

- **A C++ copy of the game engine.** It matches the official engine turn for turn. We use it for training data,
  for local test matches, and for the search itself. Automated checks confirm it still matches after changes.
- **Measuring CPU cost.** The judge counts CPU work in points, not time, so we measure CPU use the way the judge
  does before every upload. The net was made about 8x cheaper per decision without changing any move: it skips
  zero inputs, uses SIMD, and caches repeated forward passes.
- **Evaluation.** We compare paired games: the same maps, sides and seeds for the new version and the unchanged
  one. We screen on about 128 games first and play more only when a change looks promising. Results on official
  maps and on randomly generated maps are always reported separately.

## Lessons

- **Copy strong players first.** Cloning the top teams' games beat everything we got out of self-play. Mixing in
  our own games on generated maps stopped the net from simply memorizing the official maps.
- **Generated maps keep you honest.** Several ideas helped only on the known maps and hurt on new ones.
- **Expect smaller gains on the ladder.** A +5% win rate in local testing typically showed up as about +1.5–2% on
  the ladder.
- **Ideas that didn't help** (they made no difference or made the bot worse):
  - training the net to copy the search's choices (AlphaZero-style)
  - a learned value function for scoring the search
  - bigger nets
  - PPO fine-tuning after cloning
  - a deeper search
  - camping on pearl spawners
  - rushing for the map centre in the opening
- **Hand-written rules help most where the net can't see.** The biggest rule gains came from situations outside
  the 7x7 window: trapped long dragons, food behind walls, the coordination at the end of the game.
