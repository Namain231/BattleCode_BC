# Learned rule: death

100332 opportunities, 723 positives, 25 games.

| model | held-out AUC (grouped by game) |
|---|---|
| logistic_l1 | 0.896 |
| tree_d3 | 0.917 |
| gbm_ceiling | 0.957 |

Picked: **tree_d3**, threshold 0.922: fires on 0.00% of opportunities (the team: 0.72%), precision 0.06, recall 0.05. Ceiling gap +0.040 -- consider the GBM as a score term.

Per-map AUC: Autarky 0.95, Portals 0.93, Schooltime 0.90, Slithery Fight 0.89, Trauma 0.94

```
if top_ally_vlen <= 3.500:
  if room <= 0.500:
    -> p=0.922 (n=1493)
  else:
    if top_ally_ratio <= 1.250:
      -> p=0.000 (n=30685)
    else:
      -> p=0.120 (n=38286)
else:
  if top_ally_dist <= 4.500:
    if units <= 59.500:
      -> p=0.916 (n=6051)
    else:
      -> p=0.504 (n=3412)
  else:
    if room <= 0.500:
      -> p=0.762 (n=1758)
    else:
      -> p=0.301 (n=18647)
```
