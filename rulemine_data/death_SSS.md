# Learned rule: death

35747 opportunities, 214 positives, 8 games.

| model | held-out AUC (grouped by game) |
|---|---|
| logistic_l1 | 0.913 |
| tree_d3 | 0.906 |
| gbm_ceiling | 0.880 |

Picked: **tree_d3**, threshold 0.952: fires on 0.00% of opportunities (the team: 0.60%), precision 0.34, recall 0.09. Ceiling gap -0.026.

Per-map AUC: Default 0.96, Portals 0.95, Schooltime 0.88, Slithery Fight 0.90

```
if top_ally_vlen <= 4.500:
  if room <= 0.500:
    -> p=0.952 (n=397)
  else:
    if top_ally_vlen <= 3.500:
      -> p=0.019 (n=25298)
    else:
      -> p=0.420 (n=5074)
else:
  if top_ally_dist <= 4.500:
    if units <= 62.500:
      -> p=0.939 (n=1547)
    else:
      -> p=0.658 (n=437)
  else:
    if top_ally_vlen <= 7.500:
      -> p=0.213 (n=2462)
    else:
      -> p=0.654 (n=532)
```
