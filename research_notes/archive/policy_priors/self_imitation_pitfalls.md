# Pitfalls and best practices: training policies on self/bot-generated data, and RL fine-tuning from a BC init

Scope: the team's bot = C++ heuristic (safety filter, flood fill, danger model) + small CNN behaviour-cloned (BC) from top
teams' replays, used as a bonus `w * log p(move)` among safe moves. Observed: (a) PPO self-play from the BC net was worse
(0.25-0.45 greedy vs BC) with an early dip; (b) network-only self-play winners' moves -> net-vs-net even, full bot worse
(16/42); (c) now training on the full bot's own moves (winners only, half random maps), init from replay net, 50/50
replay/self-play mix.

Source note: arXiv abstracts marked (fetched) were read this session; entries marked (not fetched) are well-known papers
cited from prior knowledge at the abstract level only. No numbers are given for them unless fetched.

## Q1. Distribution shift, compounding errors and causal confusion in BC (relevance to "network learns stand-ins for safety logic")

### Takeaway
BC trained on one state distribution fails on another (compounding errors), and a discriminative imitator latches onto
whatever feature is most predictive of the target action in the training data, not the cause of it. Observation (b) is
this failure: in network-only self-play, "avoid death" is only visible to the network as its own move targets, so it
learns the safety logic. In the composite bot that logic is already applied by the C++ filter, so the capacity spent on it
is wasted or double-counted, and the net's ranking among safe moves gets worse.

### Cited Findings
- DAgger (Ross, Gordon & Bagnell 2011): a policy trained by supervised imitation on expert states changes the state
  distribution it later visits. Errors compound, with cost growing quadratically in horizon T (O(T^2 eps)) versus linearly
  for DAgger. DAgger fixes this by labelling states visited by the learner's own policy (not fetched) —
  [arXiv 1011.0686](https://arxiv.org/abs/1011.0686)
- Causal confusion (de Haan, Jayaraman & Levine 2019): BC "trains discriminative models without accounting for causal
  structure", producing "causal misidentification": access to more information can give worse performance. Distribution
  shift makes it worse. Fix: targeted interventions (environment interaction or expert queries) to find the right causal
  model. Shown on control benchmarks and driving, compared against DAgger (fetched) —
  [arXiv 1905.11979](https://arxiv.org/abs/1905.11979)
- Copycat problem (Wen et al., NeurIPS 2020): with observation histories under partial observability, when expert actions
  are strongly correlated over time "the imitator learns to cheat by predicting the expert's previous action, rather than
  the next action". Fix: an adversarial representation that removes information about the previous action while keeping
  what predicts the next one. The abstract reports significant gains but gives no numbers (fetched) —
  [arXiv 2010.14876](https://arxiv.org/abs/2010.14876)
- Invalid action masking (Huang & Ontanon 2020): computing the policy gradient over a softmax restricted to valid actions
  is a valid policy gradient. Masking scales much better than penalising invalid actions as the action space grows (not
  fetched) — [arXiv 2006.14171](https://arxiv.org/abs/2006.14171)

### Inferences
- **Recipe: masked, filter-conditioned targets.** Train the network with the same mask it is used with. Apply a softmax
  cross-entropy only over the moves that pass the C++ safety filter in that state (renormalise over the safe set), and log
  the mask with every self-play/replay sample. The network then cannot lower its loss by learning "don't die"; it can only
  learn to rank safe moves, which is its only job in the bot. This directly targets the failure in (b). Invalid-action
  masking shows the masked objective is well-posed.
- Network-only self-play (b) is also a distribution-shift problem: states reached by a network without the filter differ
  from the composite bot's states (more trapped and dangerous positions). DAgger's lesson is to label the states the
  *deployed* system visits. Using the full bot for self-play (c) does that.
- Copycat risk for this team: the "prev-turn input" and "memory plane" variants in §4 of AGENTS.md add history. Wen et al.
  predict little or negative benefit when actions are temporally correlated (dragons keep going the same way). This matches
  their offline plateau of about 72%.
- Causal confusion also warns against features that correlate with good play but don't cause it, such as the number of
  own units nearby when imitating winners.

### Gaps
- No published study found of "BC net + hand-coded safety filter" composites that measures the double-counting effect
  directly. The masking recipe is an inference from the masking and causal-confusion papers, not a tested result in this
  exact setting.
- Numbers for the copycat fix were not in the abstract; the full paper was not read.

## Q2. Self-imitation, filtered BC, "winners only", AWR, return-conditioned BC: biases and when filtering helps

### Takeaway
Filtering by outcome helps when data quality varies widely and outcomes reflect the policy. It hurts, or turns into noise,
when outcomes are dominated by luck, the opponent, or early decisive events. In mirror self-play most per-move labels in
a won game are not better than those in a lost game. Principled versions weight each action by an advantage (return
minus a learned value), or average returns over similar situations, instead of hard-filtering whole games by final
result.

### Cited Findings
- Self-Imitation Learning (Oh et al. 2018) imitates past decisions only where the achieved return exceeds the value
  estimate (a clipped advantage, `max(R - V(s), 0)`), so it learns only from better-than-expected actions, not from all
  actions of good episodes. It improves A2C on hard-exploration Atari and PPO on MuJoCo (fetched) —
  [arXiv 1806.05635](https://arxiv.org/abs/1806.05635)
- AWR (Peng et al. 2019): supervised regression onto actions weighted by `exp(advantage / beta)`, with a learned value
  baseline; it works off-policy from replay data (not fetched) — [arXiv 1910.00177](https://arxiv.org/abs/1910.00177)
- "You Can't Count on Luck" (Paster, McIlraith & Ba 2022): return-conditioned methods such as Decision Transformer fail in
  stochastic environments because "trajectories that result in a return may have only achieved that return due to luck".
  ESPER clusters trajectories and conditions on each cluster's average return. It aligns target and achieved return much
  better on 2048 and **Connect Four against stochastic opponents** (fetched) —
  [arXiv 2205.15967](https://arxiv.org/abs/2205.15967)
- RvS (Emmons et al. 2021): plain likelihood maximisation with a 2-layer MLP, conditioned on goals or rewards, is
  competitive with TD-based offline RL. Model capacity and regularisation, and the choice of conditioning variable, are
  what matter. RvS methods are "comparatively weak on random data" (fetched) —
  [arXiv 2112.10751](https://arxiv.org/abs/2112.10751)
- Brandfonbrener et al. 2022 ("When does return-conditioned supervised learning work for offline RL?"): return-conditioned
  supervised learning needs near-deterministic dynamics and good data coverage to give guarantees (not fetched) —
  [arXiv 2206.01079](https://arxiv.org/abs/2206.01079)
- Kumar et al. 2022 ("When should we prefer offline RL over BC?"): offline RL beats BC on suboptimal or noisy data,
  especially in long-horizon, sparse-reward tasks. Its edge also depends on "critical states" where the choice of action
  matters a lot (fetched) — [arXiv 2204.05618](https://arxiv.org/abs/2204.05618)
- AlphaStar Unplugged (Mathieu et al. 2023): on millions of human StarCraft II replays, offline actor-critic and MuZero
  variants reach a "90% win rate against previously published AlphaStar behavior cloning agent". Value-based offline
  methods beat pure BC on large, mixed-quality game data (fetched) —
  [arXiv 2308.03526](https://arxiv.org/abs/2308.03526)
- Expert Iteration (Anthony et al. 2017): the network imitates the output of a *stronger* improvement operator (tree
  search), not the network's own moves. The improvement comes from the expert's search, and the apprentice's job is to
  generalise it (not fetched) — [arXiv 1705.08439](https://arxiv.org/abs/1705.08439)

### Inferences
- **Survivorship and credit assignment in "winners only".** In self-play of a bot against itself, AGENTS.md reports the
  state predicts the winner 72% at r50. Many games are decided early by opening luck (trapped drones), and after that both
  winner and loser play the same policy. Winners-only filtering then mostly re-teaches the current policy's own
  distribution, plus a bias toward states that were lucky (Paster et al.). It halves the data without much signal, and
  the gradient pushes toward "moves typical of winning positions" (a causal-confusion issue: those moves are a consequence
  of being ahead).
- **Recipe: replace the hard filter with advantage weighting.**
  1. Train a small value head V(s) (win probability) on all self-play games; they already have a value/"joint value"
     variant.
  2. Weight each move's imitation loss by `clip(exp((z - V(s)) / beta), max=20)` (AWR) or by `max(z - V(s), 0)` (SIL),
     where z is the game result (or a team-standing proxy).
  3. Keep losers' games: their positive-advantage moves count, and winners' moves in positions V already rated as won are
     down-weighted.
  4. Averaging the result over several rollouts from the same position (ESPER-style) reduces luck further.
- If they keep binary filtering, use it as a weak signal: include losers with weight <1 rather than 0, or condition on the
  result (RvS: add a "won" input and use won=1 at test time). Conditioning keeps all data for representation learning.
- The Expert Iteration framing explains why (c) may not improve the net. Imitating the full bot's moves only helps if the
  bot's choice is *better* than the net's alone in ways the net can learn: the heuristic's contribution. After masking
  (Q1), what remains to learn is the heuristic's ranking among safe moves, which is double-counting (Q5). ExIt-style gains
  need a stronger labeller, such as a few rollouts or a small search per decision.

### Gaps
- No source found that quantifies how much winners-only filtering helps or hurts in symmetric self-play games specifically.
  The claim that it adds little signal is an inference.
- AWR and Brandfonbrener numbers were not verified this session.

## Q3. RL fine-tuning from a BC init: the early performance dip, forgetting, and fixes

### Takeaway
The early dip is well documented. It comes from a randomly initialised critic giving bad advantages to a good actor, and
from forgetting in states the new policy stops visiting. Fixes that work: train the critic alone first with the actor
frozen, warm up the actor's learning rate from zero at a small final value, and keep the BC policy as an anchor (a KL
penalty or BC loss on replay states throughout RL). With a strong BC start, expect small gains from RL.

### Cited Findings
- PIRLNav (Ramrakhya et al., CVPR 2023): "Naively finetuning the actor with a randomly-initialized critic leads to a rapid
  drop in performance", "since the critic provides poor value estimates". A critic learned only on demonstrations would
  be "overly optimistic since all it sees are successes". Recipe:
  1. Critic-only phase for 8M steps with the policy frozen; the critic's final layer is initialised near zero.
  2. From 8M to 12M steps, the critic LR decays from 2.5e-4 to 1.5e-5 while the **actor LR warms up from 0 to 1.5e-5**.
     Both then stay at 1.5e-5.

  Ablation gains in success rate over BC: naive BC->RL +1.6%, + critic learning +4.7%, + critic decay +7.4%, + actor
  warmup +6.2%, full +9.9% (52.0% -> 61.9%). SOTA 65.0% ObjectNav (fetched) —
  [ar5iv 2301.07302](https://ar5iv.labs.arxiv.org/html/2301.07302),
  [arXiv 2301.07302](https://arxiv.org/abs/2301.07302)
- PIRLNav also found that "as we increase the size of BC-pretraining dataset and get to high BC accuracies, improvements
  from RL-finetuning are smaller". Human demonstrations were better BC->RL starting points than shortest-path or
  frontier-exploration bot trajectories at equal pretraining success (fetched) —
  [arXiv 2301.07302](https://arxiv.org/abs/2301.07302)
- Wolczyk et al. 2024 ("Fine-tuning Reinforcement Learning Models is Secretly a Forgetting Mitigation Problem"): the main
  failure is "forgetting of pre-trained capabilities". Performance falls on state subspaces not visited early in
  fine-tuning. Standard retention methods (behavioural cloning loss, EWC, kickstarting, episodic memory) fix it. NetHack
  Human Monk SOTA for neural models went from 5K to over 10K points (fetched) —
  [arXiv 2402.02868](https://arxiv.org/abs/2402.02868)
- Jump-Start RL (Uchendu et al. 2022): "naively performing such initialization in RL often works poorly, especially for
  value-based methods". JSRL instead lets a guide policy (e.g. the BC policy) play the first part of each episode and the
  exploration policy the rest, with a curriculum that shortens the guide segment. Theory: sample complexity drops from
  exponential to polynomial in horizon; the largest gains are in the small-data regime (fetched) —
  [arXiv 2204.02372](https://arxiv.org/abs/2204.02372)
- AlphaStar (Vinyals et al., Nature 2019):
  - RL is initialised from the supervised policy and trained with TD(lambda), V-trace and UPGO, **plus a KL loss towards
    the supervised agent**.
  - The policy is conditioned on a statistic z of human build orders (first 20 buildings and units), with pseudo-rewards
    for following z, "to aid in exploration and to preserve strategic diversity".
  - The supervised data was 971k replays from players above MMR 3500 (top 22%).

  Sources: [Nature paper](https://www.nature.com/articles/s41586-019-1724-z) (paywalled; not fetched), summaries in the
  [survey arXiv 2111.07631](https://arxiv.org/pdf/2111.07631) and
  [TStarBot-X arXiv 2011.13729](https://arxiv.org/pdf/2011.13729)
- piKL (Jacob et al., ICML 2022): regularising search or policy toward an imitation-learned anchor with a KL penalty gives
  both higher human-prediction accuracy and more strength than imitation alone (chess, Go). In no-press Diplomacy it
  matches the IL policy's prediction accuracy while being "substantially stronger" (fetched; no numbers in the abstract) —
  [arXiv 2112.07544](https://arxiv.org/abs/2112.07544)
- Cal-QL (Nakamoto et al. 2023): when offline-pretrained value functions are fine-tuned online, there is an initial
  "unlearning" dip because the conservative Q-values are mis-scaled. Calibrating Q to be at least the behaviour policy's
  value removes it (not fetched) — [arXiv 2303.05479](https://arxiv.org/abs/2303.05479)
- Kickstarting (Schmitt et al. 2018): an auxiliary distillation loss toward a teacher policy, with a weight annealed over
  training, speeds up RL and lets the student surpass the teacher (not fetched) —
  [arXiv 1803.03835](https://arxiv.org/abs/1803.03835)

### Inferences
- The team's 0.25-0.45 greedy win rate with an early dip matches the PIRLNav and Wolczyk failure modes exactly: a random
  critic, and forgetting of states the RL policy stops visiting. RL in a network-only environment also reproduces the
  Q1 mismatch (no C++ filter).
- **Recipe for any future RL attempt (all of these together, not one):**
  1. RL inside the composite bot, or with the safety mask applied to the policy's softmax (masked PPO).
  2. Critic-only warmup until value loss plateaus (their `--critic-warmup`), last layer initialised near zero.
  3. Actor LR warmup from 0 to a small value (about 10x below the BC LR).
  4. KL(pi || pi_BC) penalty **plus** a BC cross-entropy term on a stream of replay states (Wolczyk: the BC loss on old
     data was the strongest retention method).
  5. Low entropy bonus, since the BC policy already has the right entropy.
  6. Optionally JSRL-style handoff: BC/champion plays the first k rounds and RL plays after, with k shrinking.
- Expect small gains: PIRLNav says the higher the BC accuracy, the smaller the RL gain. Their v1 is at about 72% top-1,
  which is near their measured ceiling.

### Gaps
- AlphaStar ablation numbers (e.g. effect of removing the KL or z, or of RL without human data) are in the paywalled
  Nature figures and were not retrieved. OpenAI Five was not checked: it did not use BC init, so it is less relevant.
- Recommended KL coefficients: sources give no transferable number. The team tried KL 0.2-1.0 in PPO without success,
  but without critic warmup or masking.

## Q4. Iterated training on own outputs: model collapse and data mixing (implications for the 50/50 mix)

### Takeaway
Training repeatedly on a model's own outputs *in place of* real data loses the tails of the distribution first (rare but
important situations), and the damage compounds over generations. *Accumulating* self-generated data alongside the
original real data keeps error bounded. A fixed 50/50 replay/self-play mix per round is on the safe side, provided the
replay set is never dropped and self-play data accumulates rather than replacing earlier rounds.

### Cited Findings
- Shumailov et al. (arXiv 2023; Nature 2024): "use of model-generated content in training causes irreversible defects in
  the resulting models, where tails of the original content distribution disappear". Shown for VAEs, GMMs and LLMs
  (fetched abstract) — [arXiv 2305.17493](https://arxiv.org/abs/2305.17493),
  [Nature 2024](https://www.nature.com/articles/s41586-024-07566-y) (paywalled, not fetched)
- Gerstgrasser et al. 2024 ("Is Model Collapse Inevitable?"): replacing real data with each generation's synthetic data
  collapses. "Accumulating the successive generations of synthetic data alongside the original real data avoids model
  collapse". In a linear model, test error with accumulation has "a finite upper bound independent of the number of
  iterations". Confirmed for LMs, diffusion models (molecules) and VAEs (fetched) —
  [arXiv 2404.01413](https://arxiv.org/abs/2404.01413)
- PIRLNav: bot-generated demonstrations (shortest path, frontier exploration) were worse pretraining data than human
  demonstrations at equal success, a data-diversity effect (fetched) —
  [arXiv 2301.07302](https://arxiv.org/abs/2301.07302)

### Inferences
- In a game, the "tails" are the rare situations that top opponents create: single-giant endgames, sonar tricks, portal
  plays. Self-play of one bot never generates them. Keeping 50% replay data protects those, which is good. Iterating
  self-play → retrain → self-play with the replay share shrinking each round would drift toward the bot's own style.
- **Recipe:**
  1. Keep the replay set fixed and always present, at ≥ 50% of samples per batch.
  2. Accumulate self-play rounds rather than replacing them.
  3. Keep a *held-out replay validation set of strong-team games* as a collapse detector. If replay-validation accuracy
     falls more than about 1 point while self-play accuracy rises, the net is drifting toward its own style.
  4. Include the opponent-diverse maps (maps_gen) in self-play, as they already do.
- Since the net starts from the replay model and is fine-tuned (lr 5e-4, 4 epochs), forgetting of replay-only situations
  is the Wolczyk risk. The 50/50 mix is the BC-retention remedy they recommend.

### Gaps
- No source gives an optimal real:synthetic ratio for policy imitation in games. Gerstgrasser's result concerns
  accumulation versus replacement, not a specific ratio.

## Q5. Distilling a composite (heuristic + NN) system into the NN; which targets; how to evaluate in-system

### Takeaway
What the net should learn depends on how it is used. Because it is used as an additive bonus on top of the heuristic,
imitating the composite's final actions teaches the net to reproduce the heuristic's contribution too. That contribution
is then counted twice at play time (feedback, not improvement). Better targets are soft distributions (full action
probabilities, or search/rollout visit counts) from a *stronger* labeller, restricted to the safe set, or an explicit
residual target. The only valid metric is in-system win rate (SPRT vs champion); offline accuracy is a weak proxy.

### Cited Findings
- Policy distillation (Rusu et al. 2016): distilling the teacher's full output distribution (softened with a temperature)
  gives better students than distilling only argmax actions (not fetched) —
  [arXiv 1511.06295](https://arxiv.org/abs/1511.06295)
- "Distilling Policy Distillation" (Czarnecki et al. 2019) maps the variants: teacher- vs student-sampled trajectories,
  and different losses. It finds "three distillation techniques that are preferred depending on specifics of the task",
  and proposes expected-entropy-regularised distillation for faster learning with a convergence guarantee (fetched
  abstract; details of which variants fail not retrieved) — [arXiv 1902.02186](https://arxiv.org/abs/1902.02186)
- Expert Iteration / AlphaZero-style training: the target is the search's visit-count distribution, a policy improvement
  over the raw network, so each iteration can raise strength (not fetched) —
  [arXiv 1705.08439](https://arxiv.org/abs/1705.08439)
- DAgger: the student should be trained on states from its own deployed behaviour, labelled by the expert (not fetched) —
  [arXiv 1011.0686](https://arxiv.org/abs/1011.0686)
- PIRLNav: higher BC (offline) accuracy did not translate one-to-one into downstream gains after RL (fetched) —
  [arXiv 2301.07302](https://arxiv.org/abs/2301.07302)

### Inferences
- **Double-counting mechanism.** The bot chooses `argmax_a [H(s,a) + w log p(a|s)]` over safe a. If p is retrained to
  imitate that argmax, p learns ≈ softmax((H + w log p_old)/T). At play time the bot adds H again, so the effective
  heuristic weight grows and w must be re-tuned after every retrain. Iterating pushes p toward H's ranking and away from
  the replay-learned "top team" signal that gave the original win. This predicts that (c) will make the net *look* better
  in net-alone tests and offline accuracy on bot data, but not in-system.
- **Recipes, from simplest to strongest:**
  1. **Masked replay-only prior plus self-play states only as inputs:** use self-play only to get on-distribution *states*
     (DAgger) and label them with something other than the bot's own move. Candidates: (i) an ensemble of replay-trained
     nets (soft labels = distillation), or (ii) the move the winner-labelled advantage (Q2) says is better.
  2. **Residual target:** train p on `softmax(Q_target(s,.) - H(s,.)/w)` so the net learns only what the heuristic does
     not already know. Here Q_target comes from rollouts or search results.
  3. **Rollout labelling (ExIt-lite):** for a sample of self-play states, run k short rollouts of the champion bot for
     each safe move (the in-process engine exists) and use the win-rate-softmax as a soft target. This is a genuinely
     stronger labeller than the bot, which is what makes ExIt improve.
  4. Always train with the **safe-set mask** (Q1) and **soft targets** (Rusu) rather than one-hot bot moves.
- **Evaluation:**
  - Offline top-1 accuracy (their ceiling is about 72%) and net-vs-net results (29/56) both failed to predict in-bot
    results (16/42). The go/no-go test must be the composite bot vs champion with SPRT, with `w` re-swept (e.g. w ∈
    {1, 2, 3}) for each new net, since retraining changes the calibration of log p.
  - Cheap offline diagnostics that track in-system value better than accuracy:
    - (i) accuracy restricted to *safe-set* moves on held-out **strong-team replays**;
    - (ii) agreement with the heuristic (rising agreement = double-counting warning);
    - (iii) entropy of p over the safe set (collapse warning);
    - (iv) replay-validation loss not rising (Q4).
  - Their control ("same build with v1 weights scored exactly 21/42") is the right noise reference: at 42 games the ±11%
    band means only gains ≥ about 60% (25+/42) are distinguishable, so SPRT or 80+ games are needed.

### Gaps
- No published work found that studies distilling a heuristic+NN additive composite back into its NN component. The
  double-counting analysis is an inference from the distillation and ExIt literature.
- Czarnecki et al.'s specific failure cases (e.g. student-sampled distillation without a teacher reward term) were not
  retrieved from the full paper.
