# Spec: rule mining from top-team replays (v2)

Status: ready-for-agent, pending the grilling round in chat. Written 2026-10-01. v2 replaces v1: the target is now
gP (S.2) for new-map events, and the first decision is consolidation, not feed yes/no.

## Problem Statement

The sprint and the final tournament phase (from Oct 10) are played only on maps no bot has seen. Our best new-map
build, gP (S.2), scores 61% against the live Y.8m on 120 unseen generated maps. It still loses the games that matter
in one recurring way.

About 85% of unseen-map games end on the round-500 longest-dragon tiebreak. We lose them holding more total mass
spread over several medium dragons, against one big enemy dragon. On the ladder, S.2 went 3–7 like this. Schooltime:
our top four were 36/23/20/19, total 323 vs 97, lost to one 56.

Consolidation is broken at several levels, each measured in `insights.md`:
- Drones rarely reach a *visible* queen, so the feed rule rarely fires.
- The queen is often boxed in by our own drones.
- 15–41% of fed pearls are left uneaten.
- The queen's intake is limited to about one pearl per two moves, because drops sit on every second segment.

Hand-written fixes have hit a wall:
- Queen election fixes (gPQ) moved their mechanism but lost 44–76.
- Late merging (gM, gJ) didn't beat gP.
- The "open map" rule bundle lost 22–98 on new maps.

Meanwhile the top teams do this well and in public replays: queens of 30–39 by r400, 3–12% feed waste, drones that
exit and suicide beside the queen from around r280. The user wants those behaviours turned into rules the bot can
run, learned from evidence rather than guessed, and valid on maps nobody has seen.

## Solution

A pipeline that turns top-team replays into small, readable decision rules for gP, using only information gP has on
an unknown map:

1. **Contrast mining first.** Compare situation-by-situation decision rates in top-team games with the same
   situations in our games, and rank where we differ most. The ranking picks what to learn.
2. **Learn one decision family at a time.** The first family is consolidation:
   - where and when a drone dies relative to the queen's head and heading;
   - how the queen moves relative to her feeders (the "queen hunts, drones die on her path" pattern).
3. **Pick the model by decision type.**
   - Yes/no switches: a bake-off of shallow tree, rule list, sparse logistic and gradient-boosted trees, keeping the
     simplest within ~2 points of the best.
   - Movement: fit the weights of gP's own move-scoring terms to the top teams' chosen moves with a ranking model.
4. **Compile the result into gP** behind a knob, and test on unseen maps with the tiebreak mechanism metric. Then a
   same-time ladder check before the event.

## User Stories

1. As the bot developer, I want the pipeline to target gP (S.2), so that improvements land on the build for the new-map events.
2. As the bot developer, I want every feature computed as if the map were unknown (terrain as seen so far, bed gaps learned online the way gP learns them), so that a rule never depends on map tables unavailable in the tournament.
3. As the bot developer, I want a contrast report ranking situations where top teams' decisions differ most from ours, so that I learn the rule with the biggest measured gap first.
4. As the bot developer, I want the contrast report to use our own recent games (ladder and local gP games) against the top-16 replays on identical feature definitions, so that the comparison is fair.
5. As the bot developer, I want the first learned family to be consolidation (drone death placement and timing relative to the queen, and queen movement toward feeders), so that I attack the measured cause of tiebreak losses.
6. As the bot developer, I want feed opportunities defined by what the drone can see and has heard, including "queen approaching me" as well as "queen within 3", so that the rule can learn the top teams' die-on-her-path behaviour.
7. As the bot developer, I want each feed example to record whether its drops were eaten by our own queen within a few rounds, so that I can learn from good feeds, not just any feeds.
8. As the bot developer, I want the queen's moves in top-team replays scored against gP's own candidate-move terms, so that fitted weights replace hand-set ones without changing gP's structure.
9. As the bot developer, I want both positive and negative examples for every yes/no decision, so that the model learns when a decision is chosen.
10. As the bot developer, I want to choose which teams to learn from per decision, defaulting to teams with big late queens and low feed waste, so that I copy the best practitioners and not an average.
11. As the bot developer, I want models evaluated on held-out *games*, with agreement also broken down by map, so that I reject rules that only hold on one map.
12. As the bot developer, I want the round number excluded from features unless a rule fails without it, so that rules key on game state (queen length, travel time, intake budget) rather than the clock.
13. As the bot developer, I want gP's own planned new-map quantities (travel time to the queen, local pearl flux, queen intake budget) available as features, so that learned rules can use the geometry-based signals the notes already identified.
14. As the bot developer, I want a readable report per learned rule (conditions, support, held-out agreement, per-map agreement), so that I can sanity-check it before it goes in.
15. As the bot developer, I want generated C++ with one pure function per decision, versioned with its dataset and model, so that every build records which rule it carries.
16. As the bot developer, I want each learned rule behind a knob in gP (hand-written, learned switch, or learned score term), so that I can A/B test it against the current behaviour.
17. As the bot developer, I want a parity check that gP's C++ features equal the extractor's Python features on the same recorded turn, so that train/serve mismatch can't silently break a rule.
18. As the bot developer, I want evaluation on the unseen-map sets already in use (set A, set B, and the generated dev/test sets), against gP itself as control, so that results compare directly with the existing tables.
19. As the bot developer, I want the tiebreak mechanism metrics (final longest dragon, paired final margin, queen length at r400, feed drops eaten by own queen) reported for every candidate, so that I see in ~30 games whether the mechanism moved.
20. As the bot developer, I want the live-map result reported alongside, so that a new-map gain doesn't hide a regression on the maps the ladder currently uses.
21. As the bot developer, I want jobs to run on the game farm (WSL, GitHub Actions, Kaggle CPU), so that 240-game evaluations take minutes.
22. As the bot developer, I want CPU peak per turn reported for every candidate, so that no learned rule pushes gP past the 65M guard.
23. As the bot developer, I want more top-team replays pulled for the chosen source teams (recent submissions only), so that rare situations have enough examples.
24. As the bot developer, I want the whole first family finished end to end before a second family starts, so that the pipeline is proven once before it widens.
25. As a teammate, I want the feature definitions in one shared table, so that I can add features without breaking parity.
26. As the bot developer, I want a hard freeze date before Oct 10, with ladder validation after it, so that the tournament build is not a same-day change.

## Implementation Decisions

**Target and constraints**
- Base build: gP (S.2). Every candidate is gP plus one learned rule; the control is gP itself.
- New-map honesty: features come from the bot's knowable state on an unknown map. Top-team replays are from known
  maps, so the extractor must deliberately forget the map: terrain as seen by that dragon so far, and bed gaps from
  the same online learning gP does. Map tables are never a feature.
- No map-specific rules. Name-based switches have been shown not to generalise.

**Modules**
1. **Replay corpus.**
   - The top-16 replays plus targeted pulls for chosen teams, recent submissions only.
   - Our own games (ladder S.2 and local gP) as a separate contrast set, never training data.
   - Uses the existing index format and decoder.
2. **Observation reconstructor ("unknown-map mode").** For each dragon-turn of a chosen team, rebuild:
   - its 7×7 view, and terrain seen in its lifetime;
   - bed gaps learned from countdowns it has seen (same method as gP's online gap learning);
   - queen knowledge approximated as "longest teammate seen within the last k rounds". Top teams' sonar is mostly
     hashed, so contents are unavailable; this is a documented approximation.
   - It extends the egocentric reconstruction used for the imitation dataset, with the map layer removed.
3. **Feature library.** One table, implemented in Python and C++:
   - own length, units
   - nearest and longest visible ally: distance, length ratio, whether it is approaching me
   - travel time to the last-known queen cell on remembered terrain
   - enemy heads within their sprint reach
   - room, pearls within 3, local pearl flux from learned gaps
   - queen intake budget (pearls she still needs vs rounds left)
   - allies within 3 of the queen
   - round, off by default.
4. **Contrast miner.** Buckets situations by a few features and compares decision rates (feed, split, stay, move
   toward the queen) between top teams and us. Output: a ranked table of the largest gaps with support counts.
5. **Decision definitions.**
   - **Drone death:**
     - Opportunity: not the longest known, and a longer ally within 6 steps or its recorded cell within reach.
     - Label: died on its own turn by invalid output, own-neck or kelp, or into an ally's body.
     - Outcome tag: drops eaten by that ally within 5 rounds.
   - **Queen move:** the chosen step among the queen's legal steps, for the team's longest dragon from r250.
   - **Stop budding:** opportunity at length ≥ 4 below the cap; label: split or not.
   - Sprints are out of the first cut. The team's own profiling found sprint use is not a gap.
6. **Learner.**
   - Yes/no decisions: bake-off (depth-3/4 tree, rule list, L1-logistic, gradient-boosted trees), grouped
     cross-validation by game, simplest within ~2 points of best.
   - Queen move: conditional-logit ranking over candidate steps, on gP's scoring terms plus new features.
   - Automatic per-map stability check.
7. **Report and code generator.** A readable rule page per model, and a generated C++ header with pure functions and
   version stamps.
8. **Integration into gP.**
   - Hooks at the existing decision points: the feed check at the top of the turn, the feeding goal selection, queen
     protection, swarm budding, and the move-score sum.
   - Each hook gets a knob. Learned movement terms enter as score terms; death placement enters as a switch.
9. **Evaluation.**
   - Farm jobs: candidate vs gP on set A + set B (120 unseen maps) plus the 10 live maps, both sides.
   - Metrics: pooled win rate, paired final margin, final longest, queen length at r400, own-queen feed intake, CPU
     peak.
   - The held-out generated test set is used only for the final check.
   - A same-time ladder panel with control for the chosen candidate.

**Where it runs**
- Replay pulls: the user's PC (API key).
- Reconstruction, contrast mining and learning: the user's PC or Kaggle CPU. No GPU.
- Games: the game farm (Zig judge bundle) on WSL (about 10 threads), GitHub Actions or Kaggle CPU.

**Data volume**
- 184 top-16 replays now, about 12 per team.
- Consolidation happens in the last ~250 rounds of most games, so each game yields dozens of death decisions and
  hundreds of queen-move decisions per team.
- Pull about 50 more recent games for each of the 3–4 chosen source teams.

**Schedule (proposed)**
- Oct 1–2: extractor (unknown-map mode) and contrast report.
- Oct 3–5: death-placement rule into gP, evaluated.
- Oct 6–7: queen-move weights, evaluated.
- Oct 8: freeze.
- Oct 8–9: same-time ladder validation; pick gP or gP + rules.

## Testing Decisions

Test only external behaviour, at the highest seams.
- **Extractor output per replay:** positives must match raw events. Example: death positives equal the team's own
  deaths of the defined kinds. Every positive is also an opportunity. Unknown-map mode must never read map-file
  terrain; checked by running it on a replay whose map file is withheld. Prior art: the replay profilers (death
  context, behaviour profile, sprint profile) cross-check counts the same way.
- **Feature parity, Python vs C++:** on recorded turns, replayed through gP with the Zig judge's inspection mode.
  This is the one new seam.
- **Game-level behaviour on the farm:** the mechanism metric first (endgame length tool, death context), then paired
  win rate. Prior art: the set A/B tables and paired margins in `insights.md`.

## Out of Scope

- Neural networks, reinforcement learning, a GPU simulator.
- Retraining the move-imitation network.
- Sprint rules.
- Map-name switches and opponent-specific play.
- Decoding other teams' sonar.
- Changes to the farm beyond job lists.

## Further Notes

- Mechanism-positive, result-negative has happened repeatedly (gPQ, gM, feedDist). Every candidate reports the end
  metric (paired final margin) next to its mechanism metric, and ships only on the end metric.
- Consolidation behaviours are coupled: queen movement, drone approach and feeding. Learning drone deaths without
  queen movement risks the transplant failure. Family 1 therefore covers both, tested as separate knobs and then
  together.
- The issue tracker isn't configured for these skills; this spec lives in the repo.
