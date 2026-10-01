# Learned rule: queen_move

Conditional logit over 5418 decisions from 18 games.
Held-out top-1 agreement 0.626 (chance 0.409).

| feature | weight (raw units) | weight (standardised) |
|---|---|---|
| eat | +1.1416 | +0.244 |
| straight | +0.8979 | +0.430 |
| room_after | +0.0603 | +0.486 |
| d_enemy | +0.0108 | +0.434 |
| d_ally | -0.0235 | -1.098 |
| toward_allies | -0.2555 | -0.278 |
| enemy_reach | -0.2736 | -0.054 |

Single-feature baselines (always pick the max):

- argmax eat: 0.432
- argmax straight: 0.597
- argmax room_after: 0.433
- argmax d_enemy: 0.413
- argmax d_ally: 0.452
- argmax toward_allies: 0.356
- argmax enemy_reach: 0.409
