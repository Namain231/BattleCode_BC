# Learned rule: queen_move

Conditional logit over 2924 decisions from 16 games.
Held-out top-1 agreement 0.651 (chance 0.410).

| feature | weight (raw units) | weight (standardised) |
|---|---|---|
| eat | +2.9749 | +0.958 |
| straight | +0.5608 | +0.269 |
| room_after | +0.0699 | +0.742 |
| d_enemy | +0.0175 | +0.703 |
| d_ally | -0.1275 | -6.096 |
| toward_allies | -0.1407 | -0.133 |
| enemy_reach | -0.2781 | -0.061 |

Single-feature baselines (always pick the max):

- argmax eat: 0.520
- argmax straight: 0.537
- argmax room_after: 0.450
- argmax d_enemy: 0.410
- argmax d_ally: 0.407
- argmax toward_allies: 0.409
- argmax enemy_reach: 0.407
