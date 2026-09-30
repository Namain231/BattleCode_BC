# 2. How our bot works (plain words)

Every dragon runs its own copy of `main.cpp`. It sees only a 7×7 square around its head, plus sonar messages
from friends. Each turn it does these steps.

## Each turn

1. **Remember the map.** It adds what it sees (walls, portals, pearls) to its memory. On the known live maps it
   recognises the map (`activateMap`) and loads the full layout from `maps_data.hpp`, so it knows walls it has
   never seen. On an unknown map it builds the map from what it sees.
2. **Rebuild the bodies** of every dragon in view, and when each body cell will become free again.
3. **Free kill check.** Enemy heads don't move during our turn, so if an enemy head is within reach and a
   head-on trade is good for us, take it.
4. **Split?** When a dragon reaches length 4 (`budAt`) it buds a length-2 child. More dragons = more mouths =
   faster growth. **This is the most important thing in the game**: most games are decided by how many
   units you have by round 100–300.
5. **Score every legal move** and take the best:
   - pearls: nearby pearls are worth more (`gamma` discount over real walking distance);
   - danger: squares an enemy head could also reach (`p1`, `p2`, …);
   - survival: a flood fill checks we won't walk into a dead end we can't get out of (`deathExtra`);
   - **the network** (Y.7.12-nn.1 only): adds `wNN × log(probability a top team would make this move)`. It only
     re-ranks moves that are already safe, and only on maze maps.

## The game plan over time

| Rounds | What the swarm does |
|---|---|
| 0 – 300 | Expand: bud at length 4 and eat nearby pearls greedily ("miners"). |
| 300 | Stop budding (`budUntil`): now grow for the tiebreak. |
| 340+ | **Queen**: the longest dragon stops splitting and gets pearls first. |
| 350 / 440+ | Nearby drones **feed** the queen (they steer into it on purpose so their length goes to her). |
| 500 | Game ends (earlier if a team is wiped out, which loses). Winner: the **longest single living dragon**, then total length. |

Why have many dragons if only the longest counts at the end? Because units win the middle of the game:
more mouths eat more pearls, and a big swarm wipes out or starves a small one. Then the swarm feeds one queen
so it wins the tiebreak.

On the three open maps (Portals, Slithery Fight, Schooltime) there is "mass feeding" (`bigFeed`) and the
network is switched off, because the network was only helpful on maze maps.

## Where to change things

All the tunable numbers are at the top of `main.cpp` in `struct Params`, each with a one-line comment. Most
experiments are "change one number, test it properly". Examples: `budAt`, `budUntil`, `feedFrom`,
`endFeedFrom`, `wHunt`, `wNN`.

## Sonar

Dragons can send one 64-bit message per turn in a direction; it travels until it hits the first dragon. We use
it to share where the queen and big enemies are. Other teams can read our messages in the public replays, so
the experiments folder has a version that signs them (`experiments/signed_sonar`).

## Want more detail?

`AGENTS.md` has the verified game mechanics, what the top teams do, and why each rule exists.
