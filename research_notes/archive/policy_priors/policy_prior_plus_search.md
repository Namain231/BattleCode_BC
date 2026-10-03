# Policy prior (behaviour cloning) + heuristic search / evaluation at small compute

Context: the bot picks a move by heuristic score (BFS pearl field, flood fill, head-on danger, safety class,
linear score) and adds `w * log p_NN(move)` (w = 2) among moves in the best safety class. The network is a small
CNN behaviour-cloned (BC) on top teams' replays (about 72% offline top-1). PPO fine-tuning made it worse, and so
did self-imitation by the network alone. Sources are listed inline. Items marked "(not re-fetched)" are
well-known papers whose details I stated from the published paper but could not re-read in this session
(the OpenReview PDF was blocked by a browser check).

## Q1. AlphaZero PUCT: how the prior enters search, weak priors, and very low simulation counts (Gumbel)

### Takeaway
PUCT uses the prior as a regularizer: the search result is approximately `argmax_y q·y − λ_N·KL(π_prior‖y)`,
where λ_N shrinks as the number of visits grows. So with few simulations the prior dominates and visit
counts make a poor, discretized target. Gumbel AlphaZero/MuZero fixes the low-budget case (it is designed
to guarantee policy improvement with as few as 2 simulations). Its root recipe (sample a few top actions,
evaluate them, pick `argmax g + logit + σ(q)`) is the cheapest principled "shallow search + prior" and fits a
CPU budget of about 75M spare instructions.

### Cited Findings
- AlphaZero/AlphaGo Zero selection rule: `a = argmax_a Q(s,a) + c_puct · π(a|s) · sqrt(Σ_b N(s,b)) / (1 + N(s,a))`.
  The prior only scales the exploration bonus, and the final policy is the root visit-count distribution
  (restated in Grill et al. 2020 and in the piKL appendix) — [Grill et al. 2020](https://arxiv.org/abs/2007.12509);
  [Jacob et al. 2022 (piKL)](https://arxiv.org/abs/2112.07544); original: [Silver et al. 2017, Nature](https://www.nature.com/articles/nature24270),
  [AlphaZero arXiv](https://arxiv.org/abs/1712.01815) (not re-fetched).
- Grill et al. prove that AlphaZero's (and UCT's) selection heuristic approximates the solution of a regularized
  policy optimization, `π̄ = argmax_{y∈simplex} [qᵀy − λ_N · KL(π_θ, y)]`, and that the empirical visit
  distribution π̂ "actively approximates" π̄. The closed form is `π̄ = λ_N · π_θ / (α − q)`, with α a normalizer.
  This is a smoothed argmax of the search Q-values, different from the softmax `∝ π_θ · exp(q/λ_N)` that the
  reverse KL gives — [Grill et al. 2020](https://arxiv.org/abs/2007.12509). In that paper λ_N is
  `c · sqrt(Σ_b n_b) / (|A| + Σ_b n_b)`, so the prior's weight decays roughly as 1/sqrt(N) as visits grow.
  The piKL appendix restates it as `λ = c_puct · sqrt(Σ n_a)/(k + Σ n_a)` and uses k = 0 because k = |A|
  "greatly overestimates the total number of visits" when there are only 50 visits and up to 362 actions —
  [Jacob et al. 2022, App. C](https://arxiv.org/abs/2112.07544).
- Three reasons Grill et al. give for poor behaviour at low budgets: π̂ is noisy, π̂ is "the ratio of two
  integers and has limited expressiveness when N_sim is low", and the prior is trained against π̂, which only
  improves for actions sampled at least once. "This performance drops significantly when N_sim is low," citing
  Hamrick et al. 2020 — [Grill et al. 2020](https://arxiv.org/abs/2007.12509).
- Grill's fix, ALL (act, search and learn with π̄ instead of π̂), "significantly outperforms MuZero" at
  N_sim = 5 with |A| = 18 on Ms Pacman. The two become comparable only around N_sim ≈ 24. On Cheetah Run it was
  tested at 4, 12 and 50 simulations. Using π̄ as the learning target helps most at low budgets:
  "the discretization noise in π̂ makes it a worse training target than π̄" —
  [Grill et al. 2020](https://arxiv.org/abs/2007.12509).
- Gumbel paper abstract: "AlphaZero can fail to improve its policy network, if not visiting all actions at the
  root." Its fix is policy improvement by "sampling actions without replacement". Gumbel AlphaZero/MuZero
  "significantly improve prior performance when planning with few simulations" —
  [Danihelka et al., ICLR 2022](https://mlanthology.org/iclr/2022/danihelka2022iclr-policy/);
  [PDF](https://openreview.net/pdf/4f2c0c813d0fbe127329c69b1ba216fbcd95d52c.pdf).
- ICLR slides: MuZero on 9×9 Go trained with n simulations fails to learn at small n, while Gumbel MuZero
  learns "with n=2 simulations" (evaluation uses 800 simulations) — [ICLR 2022 slides](https://iclr.cc/media/iclr-2022/Slides/6418.pdf).
- Algorithm (from the paper, not re-fetched): at the root, sample k actions without replacement with the
  Gumbel-Top-k trick (`g(a) + logits(a)`). Split the n simulations among them by Sequential Halving and pick
  `argmax_a g(a) + logits(a) + σ(q̂(a))`, where `σ(q̂) = (c_visit + max_b N(b)) · c_scale · q̂` (paper defaults:
  c_visit = 50, c_scale = 1, Q normalized to [0,1]). The training target is `softmax(logits + σ(completed Q))`,
  where unvisited actions get a value estimate instead of 0 visits. Deeper nodes use a deterministic
  improved-policy selection. DeepMind's `mctx` library implements it and recommends it: it "guarantees a policy
  improvement if the action values are correctly evaluated" — [mctx README](https://github.com/google-deepmind/mctx).
- Even an imitation-only prior gains a lot from shallow search. Maia1900 (chess BC) + MCTS with 50 playouts
  beats the raw model 72–94% depending on c_puct, and a Go BC model + MCTS beats its raw model 73–96%. The
  smallest c_puct (weakest prior) gives the strongest play. Human-move prediction still rises (Maia1900 53.2% →
  54.3% at c_puct = 2; Go 57.8% → 58.5%) — [Jacob et al. 2022, Table 1 and Table 4](https://arxiv.org/abs/2112.07544).
- ExIt (Hex): an MCTS guided by a policy network beat plain MCTS 97% of the time, despite a 2× slowdown from
  network evaluations. Doubling vanilla MCTS iterations gave only 56%. The softmax temperature of the network,
  used as a prior, was treated as a search hyperparameter "because there is no reason to suppose that the
  optimal bonus in the UCT formula should be linear in the TPT policy probability" —
  [Anthony et al. 2017](https://arxiv.org/abs/1705.08439).

### Inferences
- The team's rule `score + w·log p` among safe moves is a depth-0 "search". The heuristic score plays the
  role of Q, and there are 0 simulations beyond one evaluation of each move. The Gumbel/Grill results say the
  cheapest real improvement is to evaluate each of the top-k candidates (k = 2–4, chosen by
  `score + w·log p`) one or two plies deeper with the existing heuristic, for example our next-turn flood fill
  or danger after a plausible enemy reply, and then choose `argmax (w·log p + σ(q_deeper))`. That is Gumbel
  root selection with a deterministic `g = 0`. With a 4-move action space (a snake has at most 3 non-reversing
  moves), "visit every root action once" is affordable, which removes the failure mode Danihelka et al. describe.
- Because a snake has only about 3 actions, the low-simulation pathology (actions never visited) mostly does not
  apply. The main open question is whether a 1–2 ply lookahead with the heuristic value beats depth 0 under
  partial observability. This must be measured, because enemy heads outside the 7×7 view are unknown.
- A weak prior is fine inside search provided that the search Q carries real information: in piKL chess/Go,
  lower c_puct (weaker prior) meant stronger play. The equivalent knob here is w, and smaller w is "trust the
  heuristic more".

### Gaps
- I could not re-fetch the Gumbel PDF (OpenReview browser check), so the exact σ constants and 2–16 simulation
  curves (19×19 Go, chess, Atari) are unverified in this session.
- I found no published result on shallow search + BC prior under heavy partial observability with
  per-unit decentralized control like this game. Diplomacy (below) is the closest match.

## Q2. piKL / human-regularized search: the math of "value + λ·log prior", and choosing λ

### Takeaway
`argmax_a [Q(a) + λ·log τ(a)]` is exactly the mode of the KL-regularized optimum `π* ∝ τ·exp(Q/λ)`, which
maximizes `E_π[Q] − λ·KL(π‖τ)`. So the team's `score + 2·log p` is greedy piKL with λ = 2 in score units and
the anchor τ = p_NN. Meta found λ must be tuned on the scale of the payoffs. Mild regularization
(λ = 1e-3 on [0,1]-scale utilities in Diplomacy) was strongest in a mixed population, while large λ
(1e-1) kept human-like prediction accuracy and was still 1.4× the anchor's score. DiL-piKL avoids choosing a
single λ by sampling λ from a distribution.

### Cited Findings
- piKL utility: `U_i(π_i, π_−i) = u_i(π_i, π_−i) − λ_i · D_KL(π_i ‖ τ_i)`, with τ the imitation-learned
  "anchor policy". When λ is large, the policy stays close to the anchor, and when λ is small, reward dominates —
  [Jacob et al. 2022](https://arxiv.org/abs/2112.07544).
- piKL-Hedge update (from the paper's Eq. 6): `π_i^t(a) ∝ exp( (η·CV_i^{t−1}(a) + η·t·λ_i·log τ_i(a)) / (1 + η·t·λ_i) )`,
  where CV is the cumulative utility of action a. This interpolates between exponentiated summed utility and
  log-anchor. The paper proves that the KL of the average policy from the anchor shrinks roughly as 1/λ
  (Theorem 1) — [Jacob et al. 2022](https://arxiv.org/abs/2112.07544).
- The paper notes that its KL direction `D_KL(π‖τ)` is the reverse of the one implicit in MCTS (`D_KL(τ‖π)`),
  and "for our use cases we have not found the exact form of the loss to be critical so much as simply doing
  any reasonable regularized search" — [Jacob et al. 2022, footnote 4](https://arxiv.org/abs/2112.07544).
- The λ sweep in no-press Diplomacy compared the IL anchor, Hedge/RM (λ = 0) and piKL-Hedge:
  - λ = 1e-1 roughly matches IL top-1 accuracy and "improves score by a factor of 1.4x over the IL anchor
    policy".
  - λ = 1e-3 beats unregularized search in both score (about 5%) and human prediction (about 6%).
  - "Mild regularization improves average score, rather than harming it."
  - In an 8-agent population, λ = 1e-3 was best (SoS score 32.9%), and "performance drops as we continue to
    increase λ past 1e-3".
  — [Jacob et al. 2022, §4.3 and App. K](https://arxiv.org/abs/2112.07544).
- "The scale of λ is related to the scale of the payoffs in the game" (Blotto, payoffs in [0,1]). With a uniform
  anchor, piKL converges to a quantal response equilibrium — [Jacob et al. 2022, App.](https://arxiv.org/abs/2112.07544).
- Hanabi (piKL-SPARTA): "at the high lambdas that maintain or improve human accuracy, piKL-SPARTA
  significantly improves playing strength over IL, while at lower lambda values piKL-SPARTA outscores
  unregularized SPARTA" — [Jacob et al. 2022, Table 13](https://arxiv.org/abs/2112.07544).
- DiL-piKL "regularizes a reward-maximizing policy toward a human imitation-learned policy". RL-DiL-piKL extends
  it to self-play RL that both models humans and trains a best response to that model. Diplodocus came first
  and third by Elo in a 200-game tournament with 62 humans — [Bakhtin et al. 2022](https://arxiv.org/abs/2210.05492).
  (From the paper, not re-fetched: DiL-piKL samples each player's λ from a distribution each iteration rather
  than using one fixed λ.)
- Cicero used the same human-regularized planning (piKL family) for its strategic reasoning module —
  [Meta FAIR et al. 2022, Science](https://www.science.org/doi/10.1126/science.ade9097) (not re-fetched).
- AlphaStar: RL was initialized from supervised policies, with a KL penalty toward the supervised policy "to aid
  in exploration and to preserve strategic diversity", plus a human-statistics conditioning variable z
  (first 20 buildings and units, an opening plan) — [Vinyals et al. 2019, Nature](https://www.nature.com/articles/s41586-019-1724-z)
  (summarized via search result; not re-fetched in full).

### Inferences
- Exact correspondence: with scores S(a) and the network prior p, the team plays `argmax S(a) + w·log p(a)`,
  which is the mode of `π ∝ p·exp(S/w)`. Consequences:
  1. **Only the ratio w / (score scale) matters.** If the linear score's scale varies across game phases
     (for example pearl values growing late, or big safety penalties inside a class), the effective λ drifts.
     Consider normalizing S within the candidate set (for example dividing by the spread of S over safe moves)
     before adding `w·log p`. This matches the per-game rescaling of Q in Gumbel/Grill (Q normalized to [0,1]).
  2. **Temperature and w are the same knob.** `w·log softmax(z/T)(a) = (w/T)·z_a − const(state)`, so
     temperature-scaling the network changes nothing beyond w/T for greedy selection. Calibration matters only
     if w is state-dependent or log p is clipped (see Q5).
  3. **Make λ state-dependent, as PUCT does.** Grill's λ_N decays with evidence. The analogue is to shrink w
     where the heuristic has strong, reliable evidence (tactical danger, a clear pearl gradient, a large score
     gap between candidates) and to grow w where the heuristic is flat or blind (ties, open areas, early-game
     formation, unseen enemies). A cheap version is `w_eff = w · f(ΔS)`, where ΔS is the gap between the best
     and second-best safe S. The network then only breaks near-ties. Tune by A/B.
  4. **Sample λ during tuning, as DiL-piKL does.** Instead of committing to w = 2, run sandbox sweeps
     w ∈ {0.5, 1, 2, 4, 8}. Given the Diplomacy result, mild regularization is best against a diverse
     population and heavy regularization only matches the anchor, so a peak at moderate w is expected.
     The ladder, not self-play, is the arbiter, because piKL's gains were population-dependent.
- The BC prior also doubles as an **opponent model** (Diplomacy's use of the IL policy). Running p_NN from a
  visible enemy head's perspective would give a learned distribution over enemy moves to feed the head-on
  danger model instead of worst-case assumptions. Cost: one extra 18M-instruction forward pass per visible
  enemy, which fits within 100M only for 1–3 enemies.

### Gaps
- No source gives a principled way to set λ from data other than sweeps. Meta's papers report sweeps over a
  few orders of magnitude.
- I found no study of piKL-style regularization where the "value" is a hand-written heuristic rather than a
  learned value or search Q, though the math is identical.

## Q3. Expert Iteration and DAgger: using the full bot as the expert; fixed-point traps; which target to distill

### Takeaway
ExIt = (expert improvement by search that uses the apprentice) + (imitation of the expert), with DAgger-style
aggregation over states from the current policy. It improves only if the expert is strictly better than the
apprentice through information the apprentice lacks, such as search Q or deeper lookahead. Distilling a
cost-sensitive, search-improved distribution (tree-policy target, or Grill/Gumbel's π̄) beats distilling the
chosen action (+50 ± 13 Elo in Hex at equal accuracy). Distilling the combined bot's argmax, where the bot is
`heuristic + w·log p_NN`, partly feeds the network's own prior back as its target: a self-reinforcing loop
that sharpens rather than improves. The target should be the heuristic/search part alone (or π̄ built from
it), restricted to the safety class.

### Cited Findings
- ExIt loop: create states by self-play of the apprentice, compute an expert target at each (for example the
  expert's action distribution), train a new apprentice, and use it to improve the expert. "Expert improvement
  can be achieved either by using the apprentice as an initial bias in the search direction, or to assist in
  quickly estimating the value of states... or both" — [Anthony et al. 2017](https://arxiv.org/abs/1705.08439).
- Online ExIt aggregates all datasets, "similar to the DAGGER algorithm. Indeed, removing the expert
  improvement step from online EXIT reduces it to DAGGER". Online (aggregated) ExIt "substantially outperforms
  the batch mode", and keeping a larger dataset was marginally stronger than a recent-only buffer —
  [Anthony et al. 2017](https://arxiv.org/abs/1705.08439).
- Chosen-action target (CAT, `−log π(a*|s)`) vs tree-policy target (TPT, root visit distribution): top-1
  errors were similar (47.0% vs 47.7%), but "the TPT network is 50 ± 13 Elo stronger". TPT is cost-sensitive,
  so it "penalises misclassifications less severely" when the expert is unsure. Three more DAgger batches of
  100k positions each added +120 Elo, and the final network nearly matched the MCTS it imitated —
  [Anthony et al. 2017](https://arxiv.org/abs/1705.08439).
- AlphaGo Zero gated each new expert (it must beat the current one); ExIt found this unnecessary at their scale —
  [Anthony et al. 2017](https://arxiv.org/abs/1705.08439).
- DAgger: train on states visited by the learner's own policy, labelled by the expert, and aggregate datasets.
  This reduces imitation learning to no-regret online learning and avoids the compounding errors of training
  only on expert state distributions — [Ross, Gordon & Bagnell 2011](https://arxiv.org/abs/1011.0686)
  (cited via the ExIt paper; not re-fetched).
- Grill et al.: AlphaZero "entangles search and learning, which is not desirable". Using π̄ (computed from
  search Q-values) as the learning target "partially disentangles these components", making it "less sensitive
  to e.g., the action selection formula". The LEARN variant (train the prior on π̄) helps most at low budgets —
  [Grill et al. 2020](https://arxiv.org/abs/2007.12509).
- Danihelka et al.: the improved-policy target `softmax(logits + σ(completedQ))` gives an improvement guarantee
  when Q is correct, whereas visit counts can fail to improve the policy —
  [mctx README](https://github.com/google-deepmind/mctx); [Danihelka et al. 2022](https://mlanthology.org/iclr/2022/danihelka2022iclr-policy/).

### Inferences
- **Why self-imitation made things worse (the team's result): it is consistent with theory.** The network-alone
  self-play targets were whole-game winners' moves. They contain moves that exist *because* the C++ safety
  logic is absent in network-only play, so the network learned to stand in for logic it will never need inside
  the bot and moved away from what the bot needs from it (tie-breaking among safe moves). In ExIt terms, the
  "expert" (the network alone) was not better than the apprentice-inside-the-bot, so no improvement signal existed.
- **Imitating the combined bot's chosen move is mostly a fixed-point trap.** If the bot picks
  `argmax S + w·log p`, then among safe moves where S is flat, the label is p's own argmax. Training on it
  sharpens p toward its current mode (lower entropy, same errors). Where S dominates, the label is the
  heuristic's choice, which the network could learn, but then `w·log p` double-counts S at play time
  (the heuristic is counted twice). Better targets, in order:
  1. **Heuristic-improved distribution over the safety class, excluding the prior's own term**:
     `π̄(a) ∝ p_NN(a)·exp(S_deeper(a)/λ)` over safe a (Grill/Gumbel's π̄ with the heuristic as Q). Use a
     *deeper* or *better* evaluation than the one used at play time, for example a 2-ply lookahead or
     S computed with hindsight information from the replay. Otherwise there is nothing new to learn.
  2. **Outcome-weighted variants** (for example advantage-weighted, as in the team's AWR attempt) only on
     states and moves inside the safe set, so the network never spends capacity on safety.
  3. **Keep the top-teams' BC data in the mix** (DAgger-style aggregation, "exponential dataset" in ExIt). Pure
     self-data drifts and loses the opponent-modelling information that made v1 good.
- **Mask the loss to the safety class.** Compute the cross-entropy over safe moves only (renormalize p over the
  safe set). The network then learns exactly the conditional distribution that is used at play time, which is
  a residual on top of the heuristic.
- **Gate each ExIt iteration** on a sandbox SPRT + ladder A/B, as AlphaGo Zero did. At this data scale the
  cheap gate is worth it: the team has already seen offline-equal networks lose in play.

### Gaps
- No source directly studies ExIt where the expert is "hand heuristic + the apprentice", as opposed to MCTS +
  apprentice. The fixed-point argument above is my inference from Grill's entanglement remark and the CAT/TPT
  result.
- I did not verify in this session the DAgger paper's exact bounds.

## Q4. Residual policy learning, correcting a hand-coded controller, and reward shaping

### Takeaway
Residual policy learning (RPL, Silver et al. 2018; Johannink et al. 2019) learns an additive correction
`π(s) = π_0(s) + f_θ(s)` on a fixed hand-coded controller. f is zero-initialized so the start equals the
controller, and the critic is trained alone ("burn-in") before the policy updates, because a poor initial
critic otherwise degrades a good initial policy. This matches the team's PPO symptom (fine-tuning dips first)
and suggests an RL formulation: learn residual logits added to the combined score, zero-initialized, with
critic warm-up and a KL to the current bot.

### Cited Findings
- RPL: "improving nondifferentiable policies using model-free deep reinforcement learning... where good but
  imperfect controllers are available". The final policy is `π(s) = π_0(s) + f_θ(s)` —
  [Silver, Allen, Tenenbaum, Kaelbling 2018](https://arxiv.org/abs/1812.06298).
- "A desirable property of RPL is that it should never make a good initial policy worse". The last layer of f
  is initialized to zero — [Silver et al. 2018](https://arxiv.org/abs/1812.06298).
- Critic burn-in: "If we begin with a perfect initial policy and a poor critic, the policy performance may
  degrade... We therefore propose to train the critic alone for a 'burn in' period while leaving the policy
  fixed", until the critic loss falls below a threshold (β = 1.0). Even so, "the performance of RPL drops early
  in training before quickly recovering" — [Silver et al. 2018](https://arxiv.org/abs/1812.06298).
- RPL on PickAndPlace: "nearly 10x improvement" in data efficiency over learning from scratch. An "Expert
  Explore" baseline (the controller used only for exploration) shows that "not all of the advantage can be
  explained by improved exploration; the good parameterization and initialization of the policy is also to
  credit" — [Silver et al. 2018](https://arxiv.org/abs/1812.06298).
- For partial observability, RPL used a one-step history (current + previous state) as a cheap alternative to
  recurrence — [Silver et al. 2018](https://arxiv.org/abs/1812.06298).
- Concurrent residual RL on real robots (block insertion): [Johannink et al. 2019](https://arxiv.org/abs/1812.03201)
  (cited in RPL; not re-fetched).
- AlphaStar's KL-to-supervised-policy term during RL (see Q2) plays the same role as keeping close to the base
  controller — [Vinyals et al. 2019](https://www.nature.com/articles/s41586-019-1724-z).
- Potential-based reward shaping `F = γΦ(s') − Φ(s)` leaves the optimal policy unchanged, so the heuristic's
  state value (for example pearl-field potential or flood-fill area) can be used as Φ to densify RL rewards
  safely — [Ng, Harada & Russell 1999](https://people.eecs.berkeley.edu/~pabbeel/cs287-fa09/readings/NgHaradaRussell-shaping-ICML1999.pdf)
  (not re-fetched).

### Inferences
- The team's PPO attempts fine-tuned the *network* from its BC init, in an environment where the network acts
  inside or near the bot. RPL says to parameterize the RL output as a **residual on the full bot's decision**:
  logits `ℓ(a) = S(a)/λ + log p_NN(a) + r_θ(a)`, with r_θ a small head initialized to 0, trained with the
  safety mask applied and PPO/KL anchored to the current bot, not the raw network. The rollout policy at step 0
  is then exactly the champion, so there is no initial dip if the critic is warmed up first (the
  `--critic-warmup` flag already exists and should be tested this way).
- Potential-based shaping with the bot's own evaluation (for example the length difference, or reachable area)
  is a safe way to add density to the sparse "win at round 500" reward without changing the optimum.
- RPL's "Expert Explore" finding suggests that even without RL, using the bot to generate states (DAgger
  distribution) is a big part of the value. The team's real-bot self-play shards already do this.

### Gaps
- No source found on residual RL for discrete-action game bots specifically. The robotics results are
  continuous-control.

## Q5. Practical tips: prior weight, temperature, calibration of BC policies used as priors

### Takeaway
Treat prior strength (w, or c_puct) and softmax temperature as search hyperparameters tuned by play, not by
offline loss (ExIt, Lc0 and piKL all do this). For greedy `S + w·log p`, temperature scaling is absorbed into
w, so calibration matters mainly for (a) clipping or flooring log p so a single overconfident zero cannot veto a
good heuristic move, and (b) any state-dependent weighting. Avoid label smoothing if the network will later be
a teacher for distillation. Temperature scaling is the standard post-hoc calibration.

### Cited Findings
- ExIt tuned the prior network's softmax temperature as an N-MCTS hyperparameter to maximize playing
  strength — [Anthony et al. 2017](https://arxiv.org/abs/1705.08439).
- Lc0 exposes `PolicyTemperature` (policy softmax temperature) as a tunable search option. Higher values
  "make priors of move candidates closer to each other, widening the search". Defaults have changed across
  versions (a wiki revision lists 2.20) — [Lc0 options wiki](https://github.com/LeelaChessZero/lc0/wiki/Lc0-options/c78e73bd3bbb48140a5f2558e7430f95dda2bd87);
  a proposal for visit-based policy-temperature decay: [lc0 PR #1150](https://github.com/LeelaChessZero/lc0/pull/1150).
- piKL: in chess, the best c_puct for predicting humans decreases as player rating rises ("stronger players
  plan more deeply"), and the smallest c_puct gives the most strength (up to 94–96% vs the raw model) —
  [Jacob et al. 2022](https://arxiv.org/abs/2112.07544).
- "Modern neural networks... are poorly calibrated" and "temperature scaling — a single-parameter variant of
  Platt Scaling — is surprisingly effective" — [Guo et al. 2017](https://arxiv.org/abs/1706.04599).
- Label smoothing "improves model calibration", but "if a teacher network is trained with label smoothing,
  knowledge distillation into a student network is much less effective", because it erases inter-class
  similarity information — [Müller, Kornblith & Hinton 2019](https://arxiv.org/abs/1906.02629).
- Grill et al.: the regularization weight should shrink with the evidence behind Q (λ_N ∝ sqrt(N)/(N + |A|)) —
  [Grill et al. 2020](https://arxiv.org/abs/2007.12509).

### Inferences
- **Tuning recipe for w** (cheap, highest expected value):
  1. Sweep w ∈ {1, 2, 3, 4} (and 0 as a control) in the sandbox vs the champion, separately for maze and open
     maps (the network is enabled only on mazes now; open maps with small w could be tested too).
  2. Check the distribution of the gap between the best and second-best S among safe moves. If w·(log p gap)
     routinely exceeds the S gap, the network is effectively choosing the move and the heuristic only filters
     safety.
  3. Try a state-dependent w that decays with the S margin (the PUCT analogue).
  4. Floor log p at about log(0.01–0.02) so that a confident-but-wrong network (72% ceiling, partial
     observability) cannot override a large heuristic advantage. With a floor, temperature and calibration
     start to matter.
- **Calibrate on held-out replays** (fit T minimizing NLL). Report the ECE of p restricted to the safe set: it
  tells whether w = 2 means "2 nats of trust" or something inflated by overconfidence. After fitting T, re-express
  w as w' = w·T to keep behaviour identical, then tune w' from a meaningful baseline.
- **Ensembles / TTA in the prior** (already tried offline, ≤ +1.4%) mostly smooth p. That is equivalent to a
  temperature change plus a small accuracy change, so no big play gain is expected, consistent with the team's
  result.
- **Distillation hygiene**: if a future network is distilled from π̄ targets (Q3), train the teacher without
  label smoothing, and train the student on soft targets (TPT/π̄), not argmax labels.

### Gaps
- I found no primary source for KataGo's specific policy-temperature defaults or a documented rule for
  choosing them. The Lc0 "Layman's guide" blog post returned joke-like formula defaults and was not used.
- No source quantifies how BC-prior calibration interacts with a hand-written evaluation's scale. That has to
  be measured locally.
