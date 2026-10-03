# Web findings on our ML problems (29 Sept 2026, 06:30 IST)

## Offline accuracy did not predict in-bot strength (our v1b–v5, bp_r1)
- Validation *accuracy* is a weak proxy; with log-loss training, validation *log-loss* correlates far better with policy return
  (Foster et al. 2024, "Is Behavior Cloning All You Need? Understanding Horizon in Imitation Learning", https://arxiv.org/pdf/2407.15007).
  → select checkpoints / compare networks by held-out NLL on **top-team** replays, not top-1 accuracy.
- DeepMind "Imitating Interactive Intelligence" (https://arxiv.org/pdf/2012.05672): agents with *worse* BC validation loss (GAIL-trained)
  played best; BC loss alone "was not always a useful guide". The real metric is action error on the states the *policy itself* visits
  (distribution shift). → in-bot ladder/sandbox tests stay the only judge.

## ~72% ceiling / partial observability
- Scaling laws for imitation in games (Tuyls et al. 2023, https://arxiv.org/html/2307.09423v3): loss and return follow power laws in
  model size and data; NetHack plateaus below expert level, attributed to partial observability — the expert uses history / features the
  learner lacks. Loss kept improving with longer context (history). Information parity (e.g. inventory features) was necessary.
  → our network sees one frame; top teams act on memory and sonar. Worth another try, judged in-bot: stacked previous frames or a
  recurrent summary, plus features the bot already computes (remembered pearls, known enemy positions from sonar).
- More data alone scales slowly (power law): 6M fresh samples vs 1.1M for v1 should help only modestly offline; quality (slope-filtered,
  winning top teams) matters more.

## RL fine-tuning from the BC network collapsed (our PPO runs)
- Residual off-policy RL on top of a frozen BC policy (https://arxiv.org/pdf/2509.19301): learn only a correction; avoids destroying the BC skill.
- Posterior behavioural cloning (https://arxiv.org/html/2512.16911): pretrain the BC policy to cover the demonstrators' action distribution
  (not collapse to the mode) so RL fine-tuning starts from a policy that explores the right actions.
- PPO hygiene (https://apxml.com/courses/rlhf-reinforcement-learning-human-feedback/chapter-4-rl-ppo-fine-tuning/troubleshooting-ppo-instability):
  watch KL to the reference policy; lower LR, fewer PPO epochs per batch, gradient clipping, reward normalisation.
- "Echo Chamber" (https://arxiv.org/pdf/2504.07912): RL post-training amplifies behaviours already frequent in pretraining — it sharpens,
  it rarely invents. Consistent with our self-imitation results.

## Combining the network with search
- Battlesnake winner (https://medium.com/asymptoticlabs/battlesnake-post-mortem-a5917f9a3428): the RL policy chooses moves; alpha-beta
  search overrides only when it proves a move is a definite loss or win. (IDEAS #13: network autonomy inside the safety class.)

## Round 2 (29 Sept, 08:30 IST): newer/generic searches
- generals.io ("Snake + Risk") competitor (https://eventwaves.substack.com/p/trying-to-win-an-ai-bot-competition): behaviour cloning
  picked "elite-looking" moves that did not add up to winning; copying *macro strategy* found by replay analysis ("spear-tip" army)
  worked; PPO reached #15; the breakthrough was injecting a delayed-reward behaviour top players used (castles) by hand, then self-play.
  → our analogue: macro fixes from replay analysis (opening gap: contest fountains, keep farming), not only move imitation.
- Hungry Geese 11th (https://www.kaggle.com/competitions/hungry-geese/writeups/the-wisdom-of-manjushri-if-three-ducks-approach-11):
  3 stages — IL on agents rated > 1230, HandyRL self-play fine-tune, re-IL; features include temporal info (t-1 positions,
  tail at t+1/t+2) → our prev-turn inputs (n7/n8).
- Kaggle sim comps (Orbit Wars IL solutions): filter to strong players, don't copy every action; a quick BC can beat elaborate
  self-play; "look-ahead" features: roll the environment forward a few steps and feed the trajectory.

## Round 3 (29 Sept, 15:55 IST): broad searches
- Macro decisions learned from replays (StarCraft build/expansion prediction, https://arxiv.org/pdf/1707.03743): a separate
  macro model from replays. → our net already predicts top teams' split timing (split class ~70%) but the bot ignores it.
- Top tournament bots adapt mid-match (strategy recognition → switch plans; SSCAIT / Dota 2 bot competition
  https://arxiv.org/pdf/2103.02943). → add a "single giant" opponent detector (we already detect swarms); endgame losses 17%.
- NetHack: the best agent is rule-based (AutoAscend); imitation scales slowly (https://arxiv.org/html/2307.09423) → keep the
  heuristic core, use learning where it adds information.

## Round 4 (29 Sept, 16:05 IST): combining two models
- Play-time ensembles (Wiering & van Hasselt; Policy Fusion https://arxiv.org/pdf/2104.10610): average / product (Boltzmann
  multiplication = sum of log p) / entropy-weighted mixtures; components must be diverse. Product = our w·log p form.
- Weight averaging / model soups (WARP https://arxiv.org/html/2406.16768v1; rewarded soups): only for models fine-tuned from a
  shared init (n10 + n10q yes; v1 + n4 no).
- Multi-teacher distillation (MOPD https://arxiv.org/abs/2606.30406; reliability-aware https://arxiv.org/html/2609.23697):
  distil a winning ensemble into one net, weighting teachers where reliable.
- Gating / mixture of experts (TeleGate https://arxiv.org/pdf/2602.09628; RPG https://arxiv.org/pdf/2604.21355): frozen experts +
  small gate per state; cf. Orbit Wars 49th meta-controller over teacher pins.

## Round 5 (29 Sept, 18:30 IST): automated parameter tuning
- SPSA (https://chessprogramming.org/SPSA; Stockfish tuner https://github.com/zamar/spsa): gradient-free, one θ+ vs θ− match per
  iteration, perturb all params at once. Planet Wars (Google AI Challenge 2010) heuristic bot reached top 20% by evolving its constants
  (https://link.springer.com/chapter/10.1007/978-3-642-21498-1_41); CMA-ES for higher-dimensional cases.
