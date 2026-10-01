# Learned rule: queen_move

Conditional logit over 2535 decisions from 11 games.
Held-out top-1 agreement 0.639 (chance 0.416).

| feature | weight (raw units) | weight (standardised) |
|---|---|---|
| eat | +2.4219 | +0.687 |
| straight | +0.6665 | +0.318 |
| room_after | +0.0473 | +0.548 |
| d_enemy | +0.1091 | +3.376 |
| d_ally | +0.0497 | +2.373 |
| toward_allies | -0.0225 | -0.023 |
| enemy_reach | -0.5364 | -0.061 |

Single-feature baselines (always pick the max):

- argmax eat: 0.488
- argmax straight: 0.554
- argmax room_after: 0.455
- argmax d_enemy: 0.418
- argmax d_ally: 0.420
- argmax toward_allies: 0.399
- argmax enemy_reach: 0.413
