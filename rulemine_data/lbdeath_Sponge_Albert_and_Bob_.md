# Learned rule: death

98122 opportunities, 550 positives, 24 games.

| model | held-out AUC (grouped by game) |
|---|---|
| logistic_l1 | 0.914 |
| tree_d3 | 0.916 |
| gbm_ceiling | 0.962 |

Picked: **tree_d3**, threshold 0.957: fires on 0.00% of opportunities (the team: 0.56%), precision 0.00, recall 0.00. Ceiling gap +0.046 -- consider the GBM as a score term.

Per-map AUC: Default 0.92, Portals 0.95, Prisoners Dilemma 0.97, Schooltime 0.93, Slithery Fight 0.87, Trauma 0.92

```
if top_ally_dist <= 2.500:
  if top_ally_ratio <= 1.094:
    -> p=0.089 (n=1809)
  else:
    if top_ally_dist <= 1.500:
      -> p=0.957 (n=2092)
    else:
      -> p=0.838 (n=4575)
else:
  if room <= 0.500:
    if mem_top_dist <= 3.500:
      -> p=0.916 (n=989)
    else:
      -> p=0.771 (n=1394)
  else:
    if top_ally_vlen <= 5.500:
      -> p=0.078 (n=79567)
    else:
      -> p=0.602 (n=7696)
```
