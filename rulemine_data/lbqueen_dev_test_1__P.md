# Learned rule: queen_move

Conditional logit over 2111 decisions from 13 games.
Held-out top-1 agreement 0.699 (chance 0.424).

| feature | weight (raw units) | weight (standardised) |
|---|---|---|
| eat | +1.8891 | +0.502 |
| straight | +1.0906 | +0.524 |
| room_after | +0.0490 | +0.560 |
| d_enemy | +0.4754 | +16.374 |
| d_ally | +0.0722 | +3.439 |
| toward_allies | -0.1422 | -0.157 |
| enemy_reach | -0.1154 | -0.019 |

Single-feature baselines (always pick the max):

- argmax eat: 0.477
- argmax straight: 0.642
- argmax room_after: 0.452
- argmax d_enemy: 0.431
- argmax d_ally: 0.449
- argmax toward_allies: 0.399
- argmax enemy_reach: 0.421
