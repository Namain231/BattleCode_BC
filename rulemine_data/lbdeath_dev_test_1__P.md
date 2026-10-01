# Learned rule: death

94462 opportunities, 401 positives, 25 games.

| model | held-out AUC (grouped by game) |
|---|---|
| logistic_l1 | 0.927 |
| tree_d3 | 0.921 |
| gbm_ceiling | 0.968 |

Picked: **tree_d3**, threshold 0.975: fires on 0.00% of opportunities (the team: 0.42%), precision 0.13, recall 0.10. Ceiling gap +0.047 -- consider the GBM as a score term.

Per-map AUC: Default 0.91, Portals 0.94, Slithery Fight 0.89, Trauma 0.84

```
if room <= 0.500:
  if since_eat <= 2.500:
    -> p=0.914 (n=1432)
  else:
    -> p=0.975 (n=1291)
else:
  if top_ally_vlen <= 5.500:
    if top_ally_dist <= 2.500:
      -> p=0.423 (n=10920)
    else:
      -> p=0.063 (n=73553)
  else:
    if top_ally_dist <= 4.500:
      -> p=0.912 (n=2230)
    else:
      -> p=0.296 (n=5036)
```
