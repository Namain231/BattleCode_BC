# Learned rule: death

100123 opportunities, 507 positives, 25 games.

| model | held-out AUC (grouped by game) |
|---|---|
| logistic_l1 | 0.887 |
| tree_d3 | 0.897 |
| gbm_ceiling | 0.954 |

Picked: **tree_d3**, threshold 0.963: fires on 0.00% of opportunities (the team: 0.51%), precision 0.00, recall 0.00. Ceiling gap +0.057 -- consider the GBM as a score term.

Per-map AUC: Devil 0.99, Portals 0.90, Queen Of Spades 0.90, Schooltime 0.92, Slithery Fight 0.88, Trauma 0.86

```
if room <= 0.500:
  if mem_top_dist <= 3.500:
    -> p=0.963 (n=1706)
  else:
    -> p=0.900 (n=1715)
else:
  if top_ally_vlen <= 4.500:
    if top_ally_vlen <= 3.500:
      -> p=0.066 (n=63935)
    else:
      -> p=0.320 (n=17556)
  else:
    if units <= 59.500:
      -> p=0.822 (n=6812)
    else:
      -> p=0.205 (n=8399)
```
