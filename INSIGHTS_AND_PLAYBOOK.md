# UNSW Battlecode — Playbook

What we know about the game and the ladder, and where the open space is. Workflow and tools: `AGENTS.md`.
Only write here what was measured (say how); delete things that stop being true.

---

## 1. Verified mechanics

- Rounds 0–499. Dragons act one at a time in ascending id; a split child gets the next id and moves later in
  the same round.
- No pearls at the start. Each tile's countdown is drawn from its `[min,max]` gap; unlisted tiles never spawn.
  Countdown `c` seen in round `r` → pearl at round `r+c` if the tile is empty. Mirror tiles share a countdown.
- Portals: crossing a portal edge in direction d exits the partner edge on its d-side, still facing d. Vision
  does not cross portals; bodies can straddle them.
- Enemy heads do not move during our turn, so a length-L dragon can guarantee a head-on at path distance
  ≤ L−1 by sprinting. Head-ons kill both dragons regardless of length.
- An illegal action (e.g. `SPLIT 1`) kills the dragon; its body becomes ⌈L/2⌉ pearls (every second segment
  from the head). This is how teams feed a queen.
- Round-500 tiebreaks: longest living dragon, then total length. Many games are decided by 1–2 segments, or
  by total length when the longest dragons tie.
- CPU budget 100M points per dragon-turn; output costs 2.5M + 4000/byte per write.

## 2. What the top of the ladder does

Scouted from the public replays of the top 12 (`tools/scout.py`, `scout_report.py`):
- **Everyone plays a swarm**: bud at length 4 into 2+2 from round 0; ~20 units by round 50, ~30–45 by round
  100 (cap 64).
- **Aggressive feeding economy**: they eat about twice as many pearls per dragon-turn as V7.4 did, and die
  about twice as often, mostly against walls: drones dive into dead-end fountain pockets, bud a child out,
  and die there. Net expansion is still about double.
- **Longest stays 3–10 until ~round 300**, then grows to 12–31 by round 500.
- **Constant head-on trading** (tens of kills per game).
- **Consolidation** at the end, in several styles: explicit suicides next to a queen, crashes near it, or a
  late cull where small drones die wherever they are and the biggest few dragons eat the pearls.

## 3. V7.5, the current design

C++, one process per dragon. Per turn: parse the 7×7 view into persistent memory (edges, portals, pearl
timers; the 15 known maps are embedded and validated against what the dragon sees), rebuild bodies, then
choose an action in this order:
1. Late-game feeding (only for a clearly bigger, visible friend; map-dependent).
2. Escape splits when the head is cornered (a child crawls out of the tail end; a boxed-in tail is shed first).
3. Guaranteed head-on trades when the enemy is much longer.
4. Swarm budding (a 2-child at length 4).
5. The best move, scored by growth, a pearl field with spawn timers, a committed goal, head-on danger
   (sprint reach, unit value), survival (Voronoi room, optimistic and pessimistic DFS) and corridor risk.
   Options are ordered by a coarse safety class, then score.

Macro: greedy **mining drones** (length ≤ 4) until round 300, then safe growth; feeding from round 350 on
Portals, Slithery Fight and Schooltime; elsewhere no mass feeding, budding continues to round 420 while under
40 units, and the longest dragon stops splitting from round 400. Sonar: a forward radar ray early, then the
queen's position is gossiped between dragons. Tunables live in `struct Params` at the top of `main.cpp`.

## 4. Where V7.5 is weak

- **Trophy, Autarky, Devil** against strong mid-ladder teams (e.g. 777, iced calamansi). Trophy and Devil are
  numbers wars decided before round 200; Autarky is decided by late growth (opponents reach 15–24).
- **The top three** beat it on every map: they expand faster in the first 100 rounds and end with longest
  23–31.
- Midgame deaths of small drones cornered in pockets are its largest loss of material.

## 5. Things that did not work (so you don't repeat them blindly)

- **Late cull applied everywhere**: throwing away small drones cost the numbers war on most maps.
- **Mass feeding from round 350 on maze maps**: the queen could not eat the pearls fast enough; units
  collapsed and games were lost on length or total.
- **Stricter mining rules** (require a 4-step escape, viable-child checks): looked better in self-play,
  lost ladder games V7.5 wins.
- **Goal "frustration" and a timed end-of-game feed**: no measurable effect.
- In general: self-play results did not predict the ladder. Judge ideas on the ladder panel.

## 6. Open directions (not yet tried)

Ideas nobody has tested. Pick one, build it, put it through the gate:
- **Early expansion (highest leverage)**: on Trophy, Autarky and Devil the top teams die at about our rate
  but eat 25–35% more pearls per dragon-turn in the first 100 rounds (e.g. Devil 0.110 vs 0.086). Through
  budding that compounds exponentially: Devil ~28 units vs our ~8 at round 100. So the lever is
  pearl-finding efficiency, not safety. Study their first 100 rounds tile by tile (`board_at.py` on their
  replays): target choice, spacing between drones, how they avoid chasing the same pearls.
- **Head-on war doctrine**: when to trade drones deliberately (e.g. when we outnumber them), when to flee.
  Currently only lopsided trades are taken.
- **Tiebreak #2 awareness**: protect total length when longest dragons are likely to tie.
- **Opponent modelling**: identify a swarm vs a grower from the first ~50 rounds (unit ids, sightings) and
  adapt the macro instead of hard-coding it per map.
- **Map-aware openings** for Trophy, Autarky and Devil built from what the top teams do on them.
- **Team communication**: sonar is barely used (queen gossip only). Shared targets or danger reports could
  matter more than per-dragon cleverness.
- **Completely different approaches** are fine: a non-swarm strategy that beats swarms, or a simpler,
  faster bot. The gate is the only judge.

## 7. Climbing the ladder

- Elo per battle: `change = K × (score − expected)`, with `expected = 1/(1+10^((them−us)/400))`. Beating a
  team ~100 above 4–1 is worth about +11 at K = 24; losing 2–3 to a team 150 above is still slightly positive.
- **Targets**: teams above us whose rating is falling (a weaker new build) are often beatable. Confirm with a
  5-game unranked test before spending a ranked challenge (`find_targets.py`).
- **K = 96 window**: the first new-code build to play ranked after the team's 12-hour window reopens gets a
  high K for its first battles. Keep a strong new candidate off ranked until then, and point its first battles
  at higher-rated teams it has already beaten unranked.

## 8. Lessons about method

- Measure mechanisms, not just results: per-phase eats, splits and deaths per dragon-turn located every real
  leak we found (starvation on Portals, doomed buds, consolidation collapse).
- Borrow from the very top; one mid-ladder team's quirk is rarely a robust signal.
- Replays show everything, including opponents' indicator strings, so assume ours are read too.
