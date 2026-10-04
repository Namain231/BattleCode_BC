# v6 input parity: bot (viper_b19_v6in) vs Python builder (2026-10-02)

Method: `viper_b19_v6in` = vB19 + `nnInput6` (19 planes + 6 scalars, plane 8 zero, new queen/reach planes) with a debug hash of each plane
in the replay INDICATOR; `ml/v6/bot_parity.py` recomputes the planes from the replay with `ml/v6/build_dataset_v6.py` for the same
(round, dragon) and compares per plane. One local game (Trauma seed 1, both seats, ours vs vB19, `panel_zig --debug 2`).

| seat | states compared | all 19 planes equal | terrain planes 0-7 differ | planes 8-17 differ |
|---|---:|---:|---:|---:|
| A | 7330 | 90.7% | 8.7% of states | 8 states (0.1%) |
| B | 9423 | 96.2% | 3.8% of states | 0 |

Findings:
- Planes 8-17 (pearls, own/ally/enemy bodies, head lengths, queens + memory, enemy free-step reach) match on 99.9%+ of states.
  The few mismatches (plane 10/11/12/14/16, rounds 375-450) are unexplained edge cases (not investigated).
- Mismatches are the kelp/portal planes: the BOT's terrain knowledge is not always the full map on a known map. By dragon age the
  mismatch rate falls from 29% at birth to 5% after 50 rounds. Against the builder's `--terrain seen` mode the bot matches only 282 of
  the mismatching states, so the bot's knowledge is a hybrid (map identified for some dragons, partial for others), not a clean regime.
  Training on `full` terrain matches the bot ~91-96% of the time on known maps; on unseen maps use `--terrain seen`.
- Not tested: continuation (mid-sprint) states, steps_taken > 0, scalars (computed from L, round, units, is_queen: reviewed, not hashed).
Gate verdict: PASS for planes 8-17 and scalars; terrain-plane skew is documented, not closed. Closing it needs the bot to identify the
known map earlier/for every dragon (a bot-side change) or per-state terrain masks in the builder.
