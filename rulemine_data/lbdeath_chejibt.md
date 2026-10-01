# Learned rule: death

64409 opportunities, 513 positives, 25 games.

| model | held-out AUC (grouped by game) |
|---|---|
| logistic_l1 | 0.912 |
| tree_d3 | 0.889 |
| gbm_ceiling | 0.952 |

Picked: **logistic_l1**, threshold 0.979: fires on 1.00% of opportunities (the team: 0.80%), precision 0.20, recall 0.24. Ceiling gap +0.041 -- consider the GBM as a score term.

Per-map AUC: Default 0.95, Portals 0.97, Schooltime 0.90, Slithery Fight 0.89, Trauma 0.93

```
logit = +0.1628
      -0.4480 * len
      -0.0143 * units
      +0.0051 * since_eat
      -0.4420 * n_ally_vis
      +0.2096 * n_enemy_vis
      +1.1131 * top_ally_vlen
      -0.3887 * top_ally_ratio
      -0.0160 * top_ally_dist
      +0.9916 * top_ally_approach
      +0.5575 * allies_near_top
      +0.0896 * mem_top_len
      +0.0234 * mem_top_age
      -0.1010 * mem_top_dist
      -4.9170 * enemy_threat
      -0.0614 * room
      +0.0286 * pearls_r3
```
