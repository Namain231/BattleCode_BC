# UNSW Battlecode — Playbook

What we know about the game and the ladder, and where the open space is. Workflow and tools: `AGENTS.md`.
Only write here what was measured (say how); delete things that stop being true.

---

## 1. Verified mechanics

- Rounds 0–499. Dragons act one at a time in ascending id; a split child gets the next id and moves later in
  the same round.
- The board wraps on both axes (a dragon leaving the bottom appears at the top). Distances, pathfinding,
  enemy reach and sonar all wrap.
- No pearls at the start. Each tile's countdown is drawn from its `[min,max]` gap; unlisted tiles never spawn.
  Countdown `c` seen in round `r` → pearl at round `r+c` if the tile is empty. Mirror tiles share a countdown.
- Portals: crossing a portal edge in direction d exits the partner edge on its d-side, still facing d. Vision
  (7×7) does not cross portals; bodies and sonar do. Portal counts: Default 12, Autarky 8, Trauma 6, Dilemma 4,
  QoS 2, Trophy 1, Devil 0 (plus the open map Portals).
- Enemy heads do not move during our turn, so a length-L dragon can guarantee a head-on at path distance
  ≤ L−1 by sprinting. Head-ons kill both dragons regardless of length.
- An illegal action (e.g. `SPLIT 1`) kills the dragon; its body becomes ⌈L/2⌉ pearls (every second segment
  from the head). This is how teams feed a queen.
- Sonar: up to one 64-bit value per direction per turn. A ray travels straight (through portals and the wrap)
  and stops at kelp or at the **first dragon** in line, which reads it next turn (same round if its id is higher).
- Round-500 tiebreaks: longest living dragon, then total length. Many games are decided by 1–2 segments.
- CPU budget 100M points per dragon-turn; output costs 2.5M + 4000/byte per write.

## 2. What the top of the ladder does

Scouted from the public replays of the top 24 (`tools/scout.py`, `scout_report.py`) and our tests against
1700–1900 teams:
- **Everyone plays a swarm**: bud at length 4 into 2+2 from round 0; 25–36 units by round 100 against us
  (tungtung67, !ghaplebaaz), 30–64 by round 200–300.
- **They own the fast fountains.** Pearls eaten in rounds 0–100 on fast-respawning tiles, tungtung67 vs V7.12:
  Trophy 44 vs 0, Devil 169 vs 49, Trauma 59 vs 10, Autarky 105 vs 50. They reach them early (through portals
  too) and bud there.
- **They accept wall deaths while eating** but, per dragon-turn, net expansion is about double ours.
- **Longest stays 3–10 until ~round 300**, then grows to 12–31 by round 500. Exception: on Trauma
  !ghaplebaaz grows one giant from round 0 (7 at r100, 21 at r300, 25 at the end).
- **Constant head-on trading** (tens of kills per game) and **late consolidation** (suicides next to a queen,
  or a cull where small drones die and the biggest few eat the pearls).

## 3. V7.12, the current design

C++, one process per dragon. Per turn: parse the 7×7 view into persistent memory (edges, portals, pearl
timers; the known maps are embedded and validated against what the dragon sees), rebuild bodies, then
choose an action in this order:
1. Feeding (a small dragon next to a clearly longer friend turns itself into pearls).
2. Escape splits when the head is cornered (a child crawls out of the tail end; a boxed-in tail is shed first).
3. Head-on trades: guaranteed when the enemy is much longer; even trades by small drones (≤ 3) when our swarm
   has 12+ units and more heads in view.
4. Swarm budding (a 2-child at length 4).
5. The best move, scored by growth, a pearl field with spawn timers, a committed goal, head-on danger
   (sprint reach, unit value), survival (room, optimistic and pessimistic DFS) and corridor risk.
   Options are ordered by a coarse safety class, then score.

Macro (tunables in `struct Params` at the top of `main.cpp`):
- Rounds 0–300: greedy **mining drones** (length ≤ 4) with short-horizon targets (0.80/step) except on the
  open maps and Dilemma.
- Open maps (Portals, Slithery Fight, Schooltime): budding to 330, mass feeding of the queen from round 350.
- Maze maps: budding to 420 while under 40 units; from round 340 **any dragon tied for the longest known stops
  budding** and gets pearls first (a queen forms); from round 440 nearby drones feed a queen ≥ their length + 2.
- Sonar: a forward radar ray until round 300, then the queen's position is gossiped.

Lineage (each step was kept only after winning the ladder panel):
V7.5 (miners) → V7.9 (short-horizon miners) → V7.10 (even head-on trades) → V7.11 (keep budding on Autarky)
→ **V7.12** (late queen). Maze panel (777, ANON_TOKYO, hmm, Aviators): V7.5 14/28, V7.10 ~19/28, V7.12 23/28.

## 4. Where V7.12 is weak

- **Against 1690+ teams it scores 7/25** (tungtung67 0/5, !ghaplebaaz 1/5, kfcvme50 2/5, WCTW 2/5, Rogo 2/5)
  and 0–1/5 against 1840+ teams. Every one of those losses is the same shape: by round 100 they have 25–40
  units and we have 4–12, then they win the head-on war.
- **Our opening death rate.** Rounds 0–100 per dragon-turn: we split as often as the strong teams but die
  ~0.020 vs ~0.012, mostly `DOOMED` drones (trapped, no legal move) hitting walls or themselves. On Devil
  (`board_at.py`) the cause is our own traffic: two of our length-2 drones enter the same one-tile lane from
  opposite ends, too far apart to see each other (7×7 vision), and seal each other in. Fix in progress, see §6.
- **Conceded fountains** (see §2).
- **A single giant** (Trauma vs !ghaplebaaz): we lost with 82 total length vs 25 because our queen only starts
  at round 340 and reached 18.
- Teams change bots: targets that lost to us in the morning (All Roads, iced calamansi) beat us 0–1/5 by noon.
  Re-test right before a ranked challenge.

## 5. Things that did not work (so you don't repeat them blindly)

- **Late cull applied everywhere**: throwing away small drones cost the numbers war on most maps.
- **Mass feeding from round 350 on maze maps**: the queen could not eat the pearls fast enough; units collapsed.
- **Stricter mining rules** (require a 4-step escape, viable-child checks): better in self-play, lost ladder games.
- **Stopping budding at round 300 on Autarky** (V7.3–V7.10): wrong; the top teams keep 55–64 units there.
- **A late-feed rule alone** (feed a queen ≥ L+2 from round 440): barely fired, because no queen existed.
- **Opening fountain rush** (V7.13: for 80 rounds, fast fountains got no enemy discount, a bigger bonus and the
  long 0.94 horizon): +10% early eating on the ladder, but early deaths rose too; 5/25 vs the strong teams
  (V7.12 7/25). Eating faster doesn't help until the opening death rate comes down.
- Neutral in self-play, never ladder-tested: flee when outnumbered, even trades from 8 units, queen from round
  300, late feed from 420, capping miner risk at round 100/150/200. Worse: queen from 380, ending mining at 150/200.
- In general: self-play results did not predict the ladder, and cannot see flaws both sides share.

## 6. Open directions

In progress:
- **Lane sonar** (`exp_lane2`): the forward radar ray carries "my head is here, heading d"; in a straight lane
  it reaches exactly the dragon coming the other way, and a lane with another head in it (seen or heard)
  becomes unsafe. On Devil vs V7.12: 6/6 wins, 27–37 units at round 100 instead of 10–15. Next: gate, then the
  strong-team ladder test.
- **Answer a giant** (`exp_adapt`): the longest enemy seen is gossiped; if it is ≥ 10 and ≥ our queen + 3 after
  round 300 on a maze map, the queen forms and feeding starts early. Neutral in self-play; needs a ladder test
  against a giant-grower.

Ideas from past competitions ([Halite III post-mortems](https://mlomb.dev/blog/halite-iii-postmortem), the
[Google AI Challenge "Ants" winner](https://github.com/xathis/AI-Challenge-2011-bot), Kaggle Hungry Geese write-ups):
- **Rate-of-return targets** instead of per-step discounts: score a region by expected pearls over the next ~30
  rounds / (distance + 30). Rich fountain clusters, including ones behind portals, then beat stray pearls
  naturally, and `shortSight`/`minerGamma`/`minerFarmCap` can go.
- **Nearest-dragon assignment** (Ants winner): BFS from each pearl or fountain; only the nearest of our dragons
  goes for it. Every dragon can compute this for the friends it sees, without messages.
- **Exploration value** (Ants winner): each tile's value grows every round until one of ours has seen it;
  rewards scouting portals and far regions early.
- **Richer sonar**: rich-fountain claims, enemy sightings, danger reports. The lane result shows how much
  one well-aimed message can matter.
- **Local combat search**: 2–3 moves of lookahead around nearby heads for the head-on war.
- **Ablation**: switch off one feature at a time (radar, hunting, sprint escapes, …) and keep what matters.
- **Completely different approaches** are fine; the gate is the only judge.

## 7. Climbing the ladder

- Elo per battle: `change = K × (score − expected)`, with `expected = 1/(1+10^((them−us)/400))`.
- **Targets**: teams 20–120 above us. Confirm with a 5-game unranked test and only send a ranked challenge if
  the test was **≥ 3/5 and ≥ expected + 0.2**; pick the maps we won. Five games are noisy: forgot to mention
  (+236) went 2/5 unranked and then 0/5 ranked. `tools/elo_bot.py` does all of this on the champion.
- **Autoscrims** can't be avoided (any active submission is drawn): every 2 h on the even UTC hour (:30 past
  odd hours IST), up to two series against teams within 8 places of us. The champion must be active then
  (`elo_bot.py` re-activates it 5 minutes before).
- **K window** (`docs/elo.md`): a new-code bot starts at K = 96 if no other new bot of ours started in the last
  12 hours; K drops 7.2 per ranked battle (autoscrims included) to 24 after 10. Make the new build active
  **right after** a draw and spend its high-K battles on hand-picked targets within that 2-hour gap. V7.12 got
  this wrong: three high-K wins (+73) lifted us right before a draw, which then paired us with two 1610 teams
  at K ≈ 70.

## 8. Lessons about method

- Measure mechanisms, not just results: eats, splits and deaths per dragon-turn by phase (`early_game.py`),
  then `board_at.py` on the individual deaths. That is how every real leak was found, including the lane traps.
- Self-play can't see what both sides do wrong. Judge on the ladder, against the teams that beat us.
- With 7×7 vision, coordination failures between our own dragons need sonar, not better local scoring.
- Borrow from the very top; one mid-ladder team's quirk is rarely a robust signal.
- One game per map is noisy (random pearl seeds). Compare totals, and repeat before concluding a regression.
- Replays show everything, including indicator strings, so assume opponents read ours.
