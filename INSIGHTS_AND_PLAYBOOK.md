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

## 4. Where we are weak

- Per-map ladder panel (4 panel teams, one game each), V7.5 → V7.10: Trophy 1 → 4, Devil 1 → 3,
  Default 2 → 4, QoS 3 → 3, Dilemma 3 → 2, Trauma 3 → 2, **Autarky 1 → 1**. Single games are noisy, but the
  even-trade doctrine clearly fixed Trophy and Devil, which were head-on wars (on Trophy we already ate about
  as many pearls as the top teams; we were being eliminated).
- **Autarky**: the V7.3–V7.10 rule "stop budding at round 300 on Autarky" came from self-play and was wrong.
  Removing it (V7.11; top teams keep 55–64 units there until ~round 400) took Autarky from 2/8 to 5/8 on the panel.
- **The top three** beat every build on every map. V7.12 still goes 2/5 against 1690+ teams (Rogo, WCTW);
  it beats Blub Blub Blub (1663) 3/5.
- Teams change bots: a target that lost 5/5 an hour earlier (w daniel ma) beat us after a rating jump.
  Re-test right before a ranked challenge if the target's rating moved sharply.

- **Losing on the longest dragon while far ahead on total** (fixed by V7.12): V7.10/V7.11 panel losses included
  Trauma 138 vs 34 total but longest 7 vs 8, Dilemma 55 vs 10 but 6 vs 10, Devil 104 vs 47 but 7 vs 8. Cause:
  every dragon budded at length 4 until round 420, so no queen existed, and maze feeding needs a queen ≥ 10.
  Just stopping the *designated* queen from budding did nothing (the swarm churns at length 3–4 and whoever
  reaches 4 is rarely the id-designated queen). What worked: from round 340 on maze maps, **any dragon tied for
  the longest known (length ≥ 4) stops budding**, the queen ignores the "a friend is closer" pearl discount, and
  drones discount pearls nearer the queen; from round 440 drones within reach feed a queen ≥ their length + 2.
  Self-play 25–17 vs V7.11 on maze maps; ladder panel 23/28 (V7.10 ~19/28).

## 5. Things that did not work (so you don't repeat them blindly)

- **Late cull applied everywhere**: throwing away small drones cost the numbers war on most maps.
- **Mass feeding from round 350 on maze maps**: the queen could not eat the pearls fast enough; units
  collapsed and games were lost on length or total.
- **Stricter mining rules** (require a 4-step escape, viable-child checks): looked better in self-play,
  lost ladder games V7.5 wins.
- **Goal "frustration" and a timed end-of-game feed**: no measurable effect.
- In general: self-play results did not predict the ladder. Judge ideas on the ladder panel.

## 6. Open directions (not yet tried)

Recent variants that were neutral in self-play against V7.10 (≈50%) and have **not** been ladder-tested:
flee when locally outnumbered (`exp_flee`), even trades from 8 units instead of 12 (`exp_trade8`), and
contesting fountains on Devil/Trophy only (`exp_devil`). Self-play among close variants has saturated;
only the ladder panel can separate them now.

Also neutral in self-play against V7.12 (84 games each, maze maps), not ladder-tested: queen from round 300 instead
of 340, late feeding from round 420, and capping the miners' risk-taking at round 100/150/200. Starting the queen
later (380) was worse (43%). Stopping mining altogether at round 150/200 was worse.

**Mid-game gap (V7.12's main loss mode):** in its panel/target losses the opponent grows from ~20 units at round 100
to ~50 at round 300 while we stay flat at 10–15. Per dragon-turn in rounds 100–300 our splits equal our deaths
(0.021 vs 0.022); half our deaths are self-inflicted (walls 0.006, own body 0.005) against the opponent's 0.002 walls.
Self-play cannot show this (both sides share the flaw); study the winners' rounds 100–300 on the ladder.
In V7.12's Autarky loss to 777 every wall/self death in rounds 100–300 was a trapped length-2–3 drone with no
safe move (`DOOMED`), about as many as head-on trades. Idea: keep small drones out of dead-end pockets once the
swarm is past ~15 units, or let them bud *out* of a pocket earlier.

Ideas nobody has tested. Pick one, build it, put it through the gate:
- **Short-horizon targets for early drones (tested, partly positive)**: letting mining drones value pearls
  on a steep distance discount (0.80/step, fountain bonus capped) instead of trekking to far fountains
  raised units at round 100 sharply in self-play and scored 16/28 vs V7.5's 14/28 on the ladder panel
  (gains on Devil, Trophy, Autarky, Default), but lost Prisoners Dilemma to three panel teams and hurt the
  open maps in self-play. Candidate V7.9 applies it only off the open maps and off Dilemma.
- **Contest the fountains**: on Devil the top-8 eat ~200 pearls per game in the first 100 rounds, 78 of
  them in the central fountain block; V7.4/V7.5 ate ~68, only 5 in the center. Removing the "enemy is
  closer" discount on fast-respawning tiles (`exp_center`) brings our Devil early eating to ~220, but did not
  convert into wins across the pool in self-play (45% vs V7.9); ladder panel pending.
- **Early expansion (highest leverage)**: on Trophy, Autarky and Devil the top teams die at about our rate
  but eat 25–35% more pearls per dragon-turn in the first 100 rounds (e.g. Devil 0.110 vs 0.086). Through
  budding that compounds exponentially: Devil ~28 units vs our ~8 at round 100. So the lever is
  pearl-finding efficiency, not safety. Study their first 100 rounds tile by tile (`board_at.py` on their
  replays): target choice, spacing between drones, how they avoid chasing the same pearls.
  Update: V7.9's short-horizon miners closed most of this on Devil. Units at round 100 in panel games went
  from ~9 (V7.5) to ~20 (V7.9/V7.10), level with the panel teams; top-6 teams still reach ~28 there. Trophy
  and Autarky are ~20–23 for us vs ~27 for the top-6.
- **Head-on war doctrine (worked)**: small drones (length ≤ 3) trade evenly into enemy heads when our
  swarm has 12+ units and more heads in view than the enemy. V7.10 = V7.9 + this: 16/21 on the ladder panel
  (ANON_TOKYO, hmm, Aviators; 7 maze maps) vs ~14/21 for V7.9 and 10/21 for V7.5. Next: tune the thresholds,
  and consider a matching *flee* rule when we are locally outnumbered.
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
- One game per map is noisy (random pearl seeds): identical code flipped Dilemma results against two panel
  teams. Compare panel totals, and repeat a map before concluding it regressed.
- Replays show everything, including opponents' indicator strings, so assume ours are read too.
