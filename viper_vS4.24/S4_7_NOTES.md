# S4.7 - structural rebuild on the Abyss framework

Base: the Abyss framework (modular C++, learns everything from vision, anytime look-ahead search with
time-aware flood-fill safety, roles, squads, sprint trades). The S4.x topology stack (pocketDepth, branchSize,
territory, corridor risk, hard-horizon pruning, choke reservation, intent memory) is dropped: the framework's
look-ahead flood-fill already answers "can I get out of here?" exactly, including the body freeing tiles.

## Taken from where
| Idea | From | Where |
|---|---|---|
| Time-aware look-ahead + flood-fill room check, reverse-split escape | Abyss | policy.hpp scoreFrom/searchFrom (unchanged) |
| Squads, escorts, sprint trades, hot-bed pull, belief-based pearl memory | Abyss | unchanged |
| Churn "miners": short drones gamble for pearls (greedier discount, lower room need, half danger/pocket cost, contested pearls still worth it) | S4.3/S4.4, 7.12 budding | Params::miner*, Policy::miner_ |
| Authenticated sonar (SipHash tag, round never sent, 2-round window, dedup) | msgauth.hpp | world.hpp readMail, main.cpp castSonar |
| Lane gossip: "my head is here heading d" on the forward ray; oncoming lane = danger | 7.12 lane sonar idea | World::Ghost, Policy::laneDanger |
| Parent -> child hand-off on the tail ray (child starts with no memory) | new | main.cpp castSonar (split turn) |
| Queen gossip on the side rays; election = longest teammate anyone knows of | new | World::queenRec / iAmQueen |
| Apex candidates: id % 5 == 0 stops churning from round 180 and grows as a safe grower | new | Params::apexEvery/apexFrom, Policy::isGrower |
| Staggered consolidation: small dragons walk to the queen (sight or gossip), arrive over a 100-round window | 7.12 late feed, made staggered | Policy::decide feed block |
| Replay label "L<len> <role> U<units> d<depth>" (Q queen, F feeder, M miner, G grower, S swarm) | new | main.cpp |

Fix carried over from Abyss: sonar words were parsed as uint32 (truncating the 64-bit protocol values); now uint64.

## Before you submit
* `BC_INDICATOR` -> 0 in common.hpp (opponents read replays).
* Regenerate K0/K1 in msgauth.hpp and never print them.
* Keep `BC_TURN_BUDGET` at 0.075; the tests below used 0.005 for speed (shallower look-ahead).
* Run `unswbc run maps/<map>.map <bot> <bot> --sandbox` on a big map to confirm no CPU overrun.

## What was measured (local engine, unswbc 1.2.2, seed = 1..N, both sides)
Opponent: your v7.12 source with maps_data.hpp stubbed empty (so weaker than the real one), 5 ms/turn budget.
* 7 fast maps x 5 seeds x 2 sides: S4.7 (first cut) 35/70, Abyss baseline 35/70.
  S4.7 better on dilemma (10/10 vs 6/10), worse on arena (0/10 vs 2/10) and queen_of_spades (0/10 vs 3/10).
* Apex-candidate variants, 3 seeds: every 5th id from r180 = 22/42; every 3rd from r120 = 15/42; every 3rd + safer miners = 19/42.
* 3 big maps, final config (2 seeds x 2 sides): 5/12 (trauma 3/4, portals 2/4, stronghold 0/4). Feeding later/tighter (r420, window 50): 2/12.
* Not tested at all: schooltime, slithery_fight, autarky, default; the real 75 ms budget; --sandbox metering.

## Known weaknesses
* Longest-dragon tiebreak on big maps: S4.7 keeps 26-36 units and 1.5-2x the total length of 7.12 but its queen ends at 8-11
  while 7.12's consolidation makes one dragon 16-23. Feeders are alive at round 499 (walking to a stale queen cell).
* Early arena: first split at round 11 vs 8; one starting dragon lost to a head-on before round 10.
* Sample sizes are small; treat every per-map number as a hint.
