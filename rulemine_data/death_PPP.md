# Learned rule: death

36229 opportunities, 367 positives, 12 games.

| model | held-out AUC (grouped by game) |
|---|---|
| logistic_l1 | 0.866 |
| tree_d3 | 0.889 |
| gbm_ceiling | 0.921 |

Picked: **tree_d3**, threshold 0.982: fires on 1.05% of opportunities (the team: 1.01%), precision 0.33, recall 0.14. Ceiling gap +0.032 -- consider the GBM as a score term.

Per-map AUC: Default 0.83, Devil 0.95, Portals 0.89, Slithery Fight 0.84, Trauma 0.96

```
if top_ally_dist <= 3.500:
  if top_ally_ratio <= 1.134:
    if pearls_r3 <= 6.500:
      -> p=0.000 (n=1770)
    else:
      -> p=0.200 (n=391)
  else:
    if room <= 2.500:
      -> p=0.982 (n=381)
    else:
      -> p=0.712 (n=5399)
else:
  if room <= 0.500:
    if mem_top_dist <= 4.500:
      -> p=0.784 (n=1175)
    else:
      -> p=0.298 (n=463)
  else:
    if top_ally_vlen <= 4.500:
      -> p=0.069 (n=23803)
    else:
      -> p=0.534 (n=2847)
```
