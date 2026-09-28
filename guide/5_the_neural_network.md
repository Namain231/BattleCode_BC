# 5. The neural network (how Y.7.12-nn.1 was made)

You don't need this to improve the bot: most gains still come from game logic. Read it if you want to
retrain or change the network.

## The idea in one paragraph

Other teams' replays are public. We downloaded about 900 games that top teams won with their latest bots, and
for every decision their dragons made we saved **what that dragon could see** (a 15×15 picture around its head,
rotated so it always faces "up") and **which way it moved**. A small network (about 125k weights) learns to
predict the move. It gets it right about **72%** of the time; the rest is invisible to it (memory, sonar,
plans). Inside our bot, the network doesn't decide alone: it adds a bonus `wNN × log p(move)` to moves our
safety checks already allow.

## The pipeline

| Step | Command | Output |
|---|---|---|
| 1. Download top teams' games | `python tools/scout.py …` then `python tools/latest_only.py …` | `ladder/…/index.json` + replays |
| 2. Build the dataset | `python ml/build_dataset.py --index <index.json> --out ml/data_x` | `ml/data_x/shard_*.npz` |
| 3. Train (laptop GPU or Colab) | `python ml/train.py --data ml/data_x --out ml/models/x.pt --scalars 3` | a `.pt` model |
| 4. Export to C++ | `python ml/export_cpp.py ml/models/x.pt <bot>/policy_weights.hpp --data ml/data_x` | a header with the weights |
| 5. Build a bot with it | copy `viper_nn/`, replace `policy_weights.hpp`, **touch `main.cpp`** | a candidate bot |
| 6. Test | guide 3 (tourney → gate → ladder A/B) | keep or drop |

`export_cpp.py` also writes a self-test: the bot checks at startup that its C++ output matches Python's on a
sample input.

## CPU cost

The forward pass costs about 18M of the 100M points per dragon-turn. Keep the network this size or check
`max` in the `unswbc run --sandbox` output stays below about 65M.

## What we tried and learned (details in `ml/results.md`)

- More data, bigger networks, ensembles, distillation: at most +1% prediction accuracy, **no gain in play**.
- Prediction accuracy is not the goal. What counts is winning games.
- Reinforcement learning (PPO self-play) made the network **worse** at our compute budget: 0.25–0.45 against
  the imitation model. PPO fine-tuning is known to dip first, then recover; the trainer now has
  `--critic-warmup`, not yet tested.
- **Self-imitation** (play the network against itself, keep the winners' moves, retrain on 50% winners + 50% top
  teams) scored 17/28 on maze maps in round 1. Round 2 with about 3,800 games is in progress.

## Free compute we use

- **Colab**: `ml/colab_worker.ipynb` watches `MyDrive/viper_ml/jobs/` for job files. Stop a job by creating
  `jobs/STOP_<job name>`.
- **Kaggle** (CLI only): private notebooks `sp-run-*` run self-play; `kaggle kernels output …` downloads results.
- **Lightning AI**: a 4-CPU studio via the `lightning_sdk` Python package.
- Laptop: 12 threads, 15 GB RAM. Before a heavy job, check no old Python processes are still running (a
  forgotten run once used all the RAM and crashed everything).
