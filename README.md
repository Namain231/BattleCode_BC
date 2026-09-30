# Team Bhole Chature – Battlecode bot

**Start here.** This page tells you what is in the repo and what to read next. Every guide is short.

## Where we are (28 Sept 2026)

- Our best bot is **Y.7.12-nn.1** (ladder rating about 1700).
- It is **V7.12** (a hand-written C++ bot) **plus a small neural network** that copies how the top teams move.
- The network doubled our win rate on maze maps: 32–37% → 53–65% on the ladder.
- Nothing submitted since has beaten it. If your build doesn't beat it in the tests in
  [guide/3_testing_a_change.md](guide/3_testing_a_change.md), don't keep it active.

## The folders you need

| Folder | What it is | Touch it? |
|---|---|---|
| `viper_nn/` | **The champion**, Y.7.12-nn.1 (C++ bot + network). Copy this to start your own version. | Copy it, don't edit it |
| `viper_v7/` | V7.12: the same bot **without** the network. Easier to read first. | Copy it, don't edit it |
| `baselines/` | Frozen copies of kept builds: `y7_12_nn1` (champion), `v7_12`, `v7_5`. Used as test opponents. | Never edit |
| `tools/` | Scripts: run matches, the promotion gate, ladder tests, replay analysis. | Use them |
| `ml/` | Everything about the neural network: dataset building, training, self-play. | Only if you work on the network |
| `docs/` | The official game rules (movement, pearls, sonar, map format, CPU limits). | Read when stuck |
| `maps/` | The live maps. `maps_gen/` holds 300 random maps for testing on unseen layouts. | Read only |
| `experiments/` | Unproven ideas kept for later (signed sonar, pearl gossip, a generic network build). | Ignore at first |

## Read in this order

1. [guide/1_setup.md](guide/1_setup.md): install, run your first match (10 minutes).
2. [guide/2_how_our_bot_works.md](guide/2_how_our_bot_works.md): what the bot does each turn, in plain words.
3. [guide/3_testing_a_change.md](guide/3_testing_a_change.md): **the only way to know if a change helps.** Read this before submitting anything.
4. [guide/4_mistakes_to_avoid.md](guide/4_mistakes_to_avoid.md): what went wrong in earlier builds (ours and yours), with numbers.
5. [guide/5_the_neural_network.md](guide/5_the_neural_network.md): how the network was made and how to retrain it.
6. [guide/6_ideas_to_try.md](guide/6_ideas_to_try.md): good next projects, each with how to test it.

For deeper detail: `AGENTS.md` (current state, everything measured, the full process and all tools).

## Three rules

1. **Start from the champion** (`viper_nn/`), not from scratch or from an old version.
2. **Change one thing at a time**, then test it with enough games (40+ locally, then the ladder A/B).
3. **Five games prove nothing.** Two identical bots can go 4–1 on luck alone.
