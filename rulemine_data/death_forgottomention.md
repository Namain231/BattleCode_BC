# Learned rule: death

59642 opportunities, 310 positives, 12 games.

| model | held-out AUC (grouped by game) |
|---|---|
| logistic_l1 | 0.911 |
| tree_d3 | 0.927 |
| gbm_ceiling | 0.959 |

Picked: **tree_d3**, threshold 0.977: fires on 0.00% of opportunities (the team: 0.52%), precision 0.13, recall 0.09. Ceiling gap +0.032 -- consider the GBM as a score term.

Per-map AUC: Portals 0.94, Schooltime 0.85, Slithery Fight 0.93

```
if room <= 0.500:
  if top_ally_approach <= 0.500:
    if units <= 41.500:
      -> p=0.884 (n=601)
    else:
      -> p=0.918 (n=599)
  else:
    -> p=0.977 (n=610)
else:
  if top_ally_vlen <= 4.500:
    if top_ally_dist <= 2.500:
      -> p=0.278 (n=7487)
    else:
      -> p=0.035 (n=41749)
  else:
    if top_ally_dist <= 3.500:
      -> p=0.909 (n=2168)
    else:
      -> p=0.295 (n=6428)
```
