# Learned rule: queen_move

Conditional logit over 4119 decisions from 20 games.
Held-out top-1 agreement 0.694 (chance 0.427).

| feature | weight (raw units) | weight (standardised) |
|---|---|---|
| eat | +1.5567 | +0.524 |
| straight | +0.9124 | +0.440 |
| room_after | +0.0641 | +0.770 |
| d_enemy | +0.0580 | +2.339 |
| d_ally | -0.0889 | -4.239 |
| toward_allies | -0.1387 | -0.126 |
| enemy_reach | -0.6807 | -0.125 |

Single-feature baselines (always pick the max):

- argmax eat: 0.495
- argmax straight: 0.620
- argmax room_after: 0.479
- argmax d_enemy: 0.428
- argmax d_ally: 0.420
- argmax toward_allies: 0.425
- argmax enemy_reach: 0.422
