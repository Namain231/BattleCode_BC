# 6. Ideas to try next

Each idea: why it might help, and exactly how to test it. Pick **one**, follow guide 3, and write down the
result.

## Game logic (no ML needed)

1. **Sprint less (from S.2).** V7.12 sprints 30–56 times a game; S.2 sprints 3–10, and each sprint costs
   length. Try limiting sprints to real emergencies (escape or a certain kill).
   *Test:* gate + ladder A/B; also check Trauma and Portals, where S.2 beat us.
2. **Bigger late queen (from S.2 / vS.1).** Their final longest dragon grew +21 after round 300, ours +12. We lose
   some games on the longest-dragon tiebreak while having more total mass.
   *Test:* look at `feedFrom`, `endFeedFrom`, `feedRadius`; ladder A/B against teams that grow one giant.
3. **Fewer trapped drones in the opening.** Being trapped (hitting a wall or our own body with no way out) kills
   about as many of our dragons as head-ons. *Test:* `tools/early_game.py` on replays before and after:
   deaths per dragon-turn in rounds 0–100 must go down, and eating must not.
4. **Play riskier when behind.** The game state predicts the winner early (72% at round 50). When clearly
   behind, trade head-ons and hunt; when ahead, play safe.
5. **Smarter doomed dragons.** When a dragon is about to be trapped, pick the region with the most space
   (the "chambers" idea from the winning Tron bot).

## Generalisation (important for the next phase: new maps)

6. **Check the bot on unseen maps.** `maps_gen/` has 300 random fair maps (`tools/gen_random_maps.py`).
   Run the tournament on some of them, e.g.
   `python tools/tourney.py my_idea viper_nn --maps maps_gen/gen_000,maps_gen/gen_001,maps_gen/gen_002 -j 8`.
   Any rule that only works on the live maps shows up here.
7. **Train the network on random maps** (self-play on `maps_gen/`), so it learns maze play in general
   rather than these 10 mazes.

## Search

8. **Look ahead 2–3 moves in close fights**, using the network to predict what the enemy will do (the Hungry
   Geese winners did this). CPU cost only applies near enemies.

Before starting, check `ml/results.md` (technique ledger) and guide 4, so you don't redo something already
measured.
