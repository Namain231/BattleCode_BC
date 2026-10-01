# Learned rule: queen_move

Conditional logit over 3714 decisions from 17 games.
Held-out top-1 agreement 0.614 (chance 0.421).

| feature | weight (raw units) | weight (standardised) |
|---|---|---|
| eat | +2.0187 | +0.536 |
| straight | +0.5669 | +0.270 |
| room_after | +0.0430 | +0.538 |
| d_enemy | +0.0255 | +1.082 |
| d_ally | -0.0825 | -3.949 |
| toward_allies | -0.1319 | -0.133 |
| enemy_reach | -0.8006 | -0.150 |

Single-feature baselines (always pick the max):

- argmax eat: 0.475
- argmax straight: 0.537
- argmax room_after: 0.462
- argmax d_enemy: 0.433
- argmax d_ally: 0.432
- argmax toward_allies: 0.408
- argmax enemy_reach: 0.413
