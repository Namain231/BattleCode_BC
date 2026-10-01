# Learned rule: death

33421 opportunities, 156 positives, 12 games.

| model | held-out AUC (grouped by game) |
|---|---|
| logistic_l1 | 0.802 |
| tree_d3 | 0.786 |
| gbm_ceiling | 0.869 |

Picked: **tree_d3**, threshold 0.956: fires on 0.00% of opportunities (the team: 0.47%), precision 0.06, recall 0.06. Ceiling gap +0.083 -- consider the GBM as a score term.

Per-map AUC: Autarky 0.81, Portals 0.75, Slithery Fight 0.79, Trauma 0.80

```
if room <= 1.500:
  if room <= 0.500:
    if units <= 36.500:
      -> p=0.956 (n=343)
    else:
      -> p=0.928 (n=370)
  else:
    -> p=0.729 (n=481)
else:
  if since_eat <= 1.500:
    if top_ally_dist <= 4.500:
      -> p=0.930 (n=737)
    else:
      -> p=0.146 (n=1250)
  else:
    if units <= 22.500:
      -> p=0.558 (n=5257)
    else:
      -> p=0.158 (n=24983)
```
