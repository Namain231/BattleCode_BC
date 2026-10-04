# Plane-8 sensitivity of the shipped net (vB19 / n4.pt), 2026-10-02

Role: executor. Script `ml/p8_sensitivity.py`; raw numbers `research_new_meta/plane8_sensitivity.json`.
No games were run.

## Result (n = 49,584 states)

Each row compares a plane-8 variant against TABLE. flip6 = the argmax over the 6 outputs changes. flip4 = the argmax over the
4 moves changes. KL = KL(TABLE || variant) over the 6-class softmax. acc = the argmax agrees with the move the
demonstrator actually played.

| subset (n) | variant | flip6 | flip4 | mean KL | KL p95 | mean max-p | acc |
|---|---|---|---|---|---|---|---|
| all (49,584) | table | 0 | 0 | 0 | 0 | 0.657 | 0.742 |
| | zero | **3.59%** | 3.48% | 0.0036 | 0.017 | 0.656 | 0.742 |
| | learnGap (table value) | **1.87%** | 1.81% | 0.0012 | 0.0048 | 0.656 | 0.743 |
| | learnGap (own estimate) | 2.11% | 2.06% | 0.0013 | 0.0054 | 0.656 | 0.743 |
| | first-sight | **0.78%** | 0.74% | 0.0002 | 0.0010 | 0.657 | 0.743 |
| fast bed in crop (45,051) | zero | 3.86% | 3.74% | 0.0040 | 0.019 | 0.658 | 0.742 |
| | learnGap (table) | 1.98% | 1.92% | 0.0013 | 0.0052 | 0.658 | 0.744 |
| | learnGap (est.) | 2.24% | 2.19% | 0.0014 | 0.0058 | 0.658 | 0.744 |
| | first-sight | 0.84% | 0.80% | 0.0003 | 0.0011 | 0.658 | 0.744 |
| live maps (17,082) | zero | 2.66% | 2.56% | 0.0026 | 0.012 | 0.667 | 0.695 |
| | learnGap (table) | 1.40% | 1.38% | 0.0008 | 0.0035 | 0.668 | 0.695 |
| | first-sight | 0.67% | 0.64% | 0.0002 | 0.0011 | 0.668 | 0.694 |
| generated maps (32,502) | zero | 4.08% | 3.97% | 0.0042 | 0.020 | 0.651 | 0.766 |
| | learnGap (table) | 2.11% | 2.04% | 0.0013 | 0.0057 | 0.650 | 0.768 |
| | first-sight | 0.84% | 0.80% | 0.0002 | 0.0010 | 0.650 | 0.769 |
| generated, fast (31,212) | zero | 4.21% | 4.09% | 0.0044 | 0.020 | 0.652 | 0.766 |
| | learnGap (table) | 2.17% | 2.10% | 0.0014 | 0.0058 | 0.651 | 0.768 |
| | first-sight | 0.88% | 0.83% | 0.0003 | 0.0010 | 0.652 | 0.769 |

Fast-bed crop cells (table plane-8 value > 20, the median non-zero value) filled by each variant: learnGap 32.7%,
first-sight 54.7%. These match the critic's figures (32% and 54% on archipelago; on Trauma alone this script gives 62% and
66%, against the critic's 62% and 66%).

## Decision rule outcome

- **ZERO vs TABLE: 3.6% of top moves flip (4.1% on generated maps). That is above the 2% threshold**, so by the stated rule
  plane 8 is not "irrelevant". The effect is still small. The mean KL is 0.004, the mean max-prob is unchanged, and
  agreement with the demonstrator is identical (74.2% vs 74.2%). So the flipped decisions are near-ties that do not move
  agreement in either direction.
- **learnGap-emulated vs TABLE: about 2% flips.** That is the skew a table-trained net would suffer on unseen maps under
  b19_v4's learnGap. It is not "large".
- **First-sight (seen-so-far) vs TABLE: 0.8% flips.** That is under the threshold.
- Reading: the rule gives neither clean outcome. Zero is not below 2%, and no gap is large. Plane 8 matters a little. A
  seen-so-far plane (first-sight reveal) keeps the shipped net within 1% of its table behaviour. Zeroing plane 8 costs
  3–4% of decisions, with no measurable loss in imitation accuracy on this sample. The verdict between "zero" (cheap, exact
  parity) and "seen-so-far + mask" is the director's call. The data says the stakes are small either way.
- Note: **vB19 itself has no learnGap.** On an unseen map `gmax` is only ever set to 0 (`baselines/vB19/main.cpp:464`), so
  the shipped bot already feeds plane 8 = ZERO on unseen maps. It is running the "zero" regime: 3.6–4.1% of its top moves
  differ from what a table would give.

## Method

- **Net:** `NN_*` arrays parsed from `baselines/vB19/policy_weights.hpp` into numpy. The forward pass mirrors
  `policy_nn.hpp` / `ml/train.py Policy`: conv3 + ReLU, 2x2 average pool dropping row/column 14, conv3 + ReLU, conv3 plus
  a residual and ReLU, FC 1568→64, then the output over [h, 3 scalars]. Validated on the embedded `NN_TEST_*` sample: max
  |logit diff| is 7e-7. The softmax over 6 sums to 1, and the 4-move renormalisation sums to 1. On these states the argmax
  matches the played move 74.2% of the time (75.2% over the 4 moves, on move labels only). The always-majority baseline
  ("forward") is 39.8%.
- **States:** 20 local replays.
  - `out/sw_0/*_1_A.replay`: the 10 live maps, 17,082 states.
  - `out/v4_dev/maps_rm_dev+g11_{archipelago,caverns,fortress,labyrinth,open,shrines,wilds}_0_1_A` and `rdense_000..002_1_A`:
    10 generated maps, 32,502 states.
  - Sampled: every alive dragon of **both** teams at its turnStart on every round with round % 10 == 0, for all rounds.
    The label is the dragon's next action, using the build_dataset convention.
  - Planes and scalars follow `ml/build_dataset.py` (its `parse_map`, `OFF`, `VIEW` are imported, and its `snapshot` is
    replicated with the first 3 scalars). The decoder streams events and writes no `.pkl`.
- **Plane-8 variants:** all use the bot's formula, min(255, int(2040/(lo+hi))).
  - TABLE: map-file gaps.
  - ZERO: plane 8 = 0 everywhere.
  - learnGap (table value): the table value is shown where this dragon's emulated `ptCycles >= 1`, i.e. at some
    turn the bed was in its 7x7 view and a reset (`pearlCountdown` event after round start) occurred since its previous
    in-view turn. This is exact given the countdown events: a reset always makes `pt > last - dt`.
  - learnGap (own estimate): same mask, but the value is b19_v4's estimate. gmax = max countdown seen. gmin = smallest
    `pt+1` at a dt = 1 reset, else 1. The visible pt is reconstructed as `value - (round - resetRound)`, which may be off
    by one against the engine.
  - first-sight: the table value for every cell this dragon has ever had in its 7x7 view.
- **Memory is per dragon:** initial dragons and every split child start empty. Memory is updated at each of the dragon's
  own turns before the snapshot, as the bot absorbs its view and then builds the input.
- **Fast bed:** a table plane-8 value above the median non-zero value over all crops (20). 91% of states have one in
  their crop, so this subset is close to "all".

## Caveats

- The demonstrator is **our own bot**, not the top teams. sw_0 is `viper_wnn0` (wNN = 0) vs `baselines/y7_12_49`, from
  `out/sweep.sh`. v4_dev is the b19_v4 games. Where a bot does use a net, it partly follows this one, so the 74% agreement
  is inflated (69.5% on the live sw_0 games, 76.7% on the generated ones). Use it only as a sanity check of the forward
  pass and the input building, not as a held-out accuracy.
- The flip rate measures how much the net's decision changes, not whether the change wins or loses games. Unchanged accuracy
  suggests the flips are near-ties, but that was not tested in games.
- n is about 2.5x the ~20k asked for. Every-10th-round sampling of all 20 games gave 49.6k states, and keeping all of them
  cost nothing extra. The states within a game are correlated, so the effective n is smaller.
- Generated maps are from `maps_rm_dev` only, one seed per style, with the dense-random style over-represented (16k of the
  32k states).
- Bed positions come from `pearlCountdown` events (every bed logs its initial draw). Vision is assumed to be the plain 7x7
  square, as in build_dataset.
- Public (ladder) replays lack `pearlCountdown`, so this cannot be repeated on top-team data.
