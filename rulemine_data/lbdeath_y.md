# Learned rule: death

115172 opportunities, 377 positives, 25 games.

| model | held-out AUC (grouped by game) |
|---|---|
| logistic_l1 | 0.946 |
| tree_d3 | 0.917 |
| gbm_ceiling | 0.980 |

Picked: **logistic_l1**, threshold 0.994: fires on 0.41% of opportunities (the team: 0.33%), precision 0.11, recall 0.13. Ceiling gap +0.034 -- consider the GBM as a score term.

Per-map AUC: Devil 0.97, Portals 0.95, Schooltime 0.85, Slithery Fight 0.97, Trauma 0.83

```
logit = +1.9122
      +1.1611 * len
      -0.0384 * units
      +0.0082 * since_eat
      -0.4205 * n_ally_vis
      -0.1829 * n_enemy_vis
      +0.1676 * top_ally_vlen
      +1.6821 * top_ally_ratio
      -0.0214 * top_ally_dist
      +0.6943 * top_ally_approach
      +0.2766 * allies_near_top
      -0.2461 * mem_top_len
      +0.0335 * mem_top_age
      -0.0928 * mem_top_dist
      -5.7376 * enemy_threat
      -0.1465 * room
      -0.0802 * pearls_r3
```
