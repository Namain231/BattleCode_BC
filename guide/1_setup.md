# 1. Setup (about 10 minutes)

## Install

1. Python 3.11 or newer.
2. The game toolkit: `pip install unswbc`
3. That's it. You do **not** need a C++ compiler: `unswbc` builds C++ bots with the judge's own compiler inside
   its sandbox.

## The API key (only for ladder scripts)

Ask the team lead for `secrets.env` and put it in the repo root. Never commit it anywhere public and never
paste it in chat. Most scripts read it themselves; for the others:

```
export $(cat secrets.env | xargs)        # Git Bash / Linux
```

## Run your first match

```
unswbc run maps/trophy.map viper_nn viper_v7
```

- The first bot is team A, the second team B.
- It prints who won and writes a `.replay` file. Open it in VS Code (`unswbc vscode` installs the viewer) to
  watch the game and see every line the bots printed.

## Run many matches at once

```
python tools/tourney.py viper_nn baselines/v7_12 --maps trophy,devil,trauma --seeds 2 -j 8
```

- Each map is played twice per seed, once from each side (sides matter because dragons move in id order).
- `-j 8` = 8 games in parallel. Don't go above about 10 on a laptop, or games time out.

## Why C++ and not Python?

Each dragon gets **100M CPU points per turn**, and going over kills the dragon. The same logic in Python is
far slower, so a Python bot has to think much less per turn. Our bot uses about 5M points plus about 18M for
the network. **Start from our C++ bot**; don't rewrite it in Python. See `docs/timeouts.md`.

## When you change a header file

The sandbox build cache only looks at `main.cpp`. If you change `maps_data.hpp` or `policy_weights.hpp`,
also make a tiny edit to `main.cpp` (even a comment), or you will silently test the old build.
