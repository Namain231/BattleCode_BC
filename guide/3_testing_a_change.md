# 3. How to test a change (the only way to know)

Games are very noisy: each game draws random pearl spawns, so **the same bot against the same opponent can
win 4/5 one time and 1/5 the next.** Almost every mistake we made came from trusting too few games. Follow
these steps in order and don't skip any.

## Step 1: make your copy

```
cp -r viper_nn my_idea        # start from the champion
```

Change **one** thing in `my_idea/main.cpp` (usually one number in `struct Params`). If you change five things
and it gets worse, you won't know which one did it.

## Step 2: quick local check (15 minutes)

```
python tools/tourney.py my_idea viper_nn --maps trophy,default,autarky,devil,trauma --seeds 2 -j 8
```

That's 20 games against the champion. If you win **fewer than 8/20**, it's almost certainly worse: stop here.

## Step 3: the gate (about 1 hour)

```
python tools/gate.py my_idea
```

- It plays 40 games against the champion and 20 against V7.5, on all 10 live maps, both sides.
- It prints **PASS** or **FAIL**. You need ≥ 55% against the champion and ≥ 50% against V7.5.
- Passing only means "not obviously broken": a build once passed the gate and was still worse on the ladder.

## Step 4: the ladder A/B (the real test)

Local games are our bot against our own bots. The ladder is real opponents, and it's what counts.

1. Submit with a **neutral name**: the next `Y.7.12.<n>` in the table in `AGENTS.md`, and a boring description.
   Other teams can see names, and replays are public. Never write what the build does.
2. Run a same-time A/B against the champion (submission 9285):
   ```
   python tools/ab_test.py <your submission id> 9285 --champion 9285 --teams <6 team ids around our rating>
   ```
   It plays your build and the champion against the **same teams at the same time** (opponents change their
   bots all the time, so comparing with last week's results is unfair), then re-activates the champion.
3. Keep your build only if it wins **clearly more** than the champion: e.g. 20/30 vs 15/30. A 16/30 vs 15/30
   result means "no difference".

## How many games do you need?

| Real difference | Games needed to see it |
|---|---|
| 60% vs 50% | about 100 |
| 70% vs 50% | about 25 |
| 80% vs 50% | about 10 |

A typical swing from luck alone is ±11% with 20 games and ±22% with 5 games (and twice that happens
regularly). So 5 games tell you nothing.

## Afterwards

- Make sure the champion (9285) is active again. Autoscrims run every 2 hours on even UTC hours (5:30, 7:30…
  IST) with whatever is active.
- Write one line in `AGENTS.md` (the name table) and in `INSIGHTS_AND_PLAYBOOK.md`: what you tried and the
  result, even if it failed. A failed idea written down saves someone a day.
