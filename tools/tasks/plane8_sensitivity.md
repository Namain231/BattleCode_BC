# Task plane8_sensitivity — does the shipped imitation net depend on input plane 8?

Repo: C:\Users\sohan\Downloads\BattleCode_BC (UNSW Battlecode "Loong"). No memory of earlier work assumed.
Read first: AGENT_LOG.md (entries plane8_audit, plane8_opt1), research_new_meta/plane8_opt1_review.md,
research_new_meta/nn_plan.md section on plane 8, ml/build_dataset.py, ml/train.py (network definition and input planes),
baselines/vB19/policy_nn.hpp + policy_weights.hpp (weights format, forward pass), and the bot's input builder in
baselines/vB19/main.cpp (~L1522-1560, where `at(8)` is filled).

## Question
How much does the shipped net's output change when plane 8 (pearl spawn-rate plane: 255*2/(gmin+gmax)*4 per tile,
0 where no bed) is replaced by what the bot would actually know at play time on an UNSEEN map? If the top move changes
in under ~2% of states, plane 8 does not matter (then we zero it in the retrain). If much more, a train/play skew on
unseen maps would hurt.

## What to build (scratch script `ml/p8_sensitivity.py`; write it, run it, keep it small)
1. Load the net weights from `baselines/vB19/policy_weights.hpp` into numpy and implement the forward pass. Validate
   it: it must reproduce the bot's own convention (check `ml/train.py` model + the C++ `forward`); sanity-check by
   confirming the distribution over 4 moves sums to 1 and that on states from `ml/build_dataset.py`-style samples
   the argmax matches the demonstrator move well above chance (~72% was the reported held-out accuracy; do not expect
   exactly that on a different sample, report what you get).
2. Get ~20k states from LOCAL replays (they keep exact per-round state; public replays do not). Local replays exist under
   out/*/ (e.g. out/sw_0, out/b19_live, out/p1_live, out/v4_dev, out/qp_*). Use `ml/build_dataset.py`'s feature code for
   planes (reuse functions; do NOT use `replay.load` which writes .pkl next to every replay and doubles disk use: use
   `tools/replay_lite.py` or pass a no-cache option; free disk is only ~6 GB). Decide which dragons/rounds to sample
   (e.g. every dragon of both teams, every 10th round); document it.
3. For each state compute the net's move distribution with plane 8 set four ways:
   (a) TABLE: true values (from the map file's gaps, as the bot has on known maps);
   (b) ZERO;
   (c) LEARNGAP-EMULATED: only beds the dragon could have learned: a bed counts as known if within the dragon's view
       window at some earlier round of this game AND a reset was observable (use the exact countdown events present in
       local replays: `pearlCountdown`, see replay.py L12 and the critic's notes in the review file; if the decoder lacks
       it, parse it or approximate with "bed seen >= 2 times");
   (d) FIRST-SIGHT-EMULATED: beds ever seen by this dragon (view window) get the table value, others 0.
   Per-dragon history matters (dragons start with no memory; children too); a simpler per-team union is a fallback,
   state which you used.
4. Report overall and separately for states with a fast bed (plane-8 value above the median non-zero value) within the
   input window: % states where argmax changes vs TABLE, mean KL(TABLE || variant), mean max-prob. Include n.
5. Constraints: CPU only, one process, numpy only (no torch needed), keep RAM < 2 GB; another job is running games
   (-j 4), so do not start panels. Delete any cache files you create beyond the script and a small results file.

## Report
Write results to `research_new_meta/plane8_sensitivity.md` (table + method + caveats + the decision rule outcome:
<2% => zero plane 8; large gap => seen-so-far + mask). Append one line to AGENT_LOG.md with >>:
`- [2026-10-02] [executor] [plane8_sensitivity] <headline numbers, decision>`. Final message: the table and anything
you could not do or verify.
